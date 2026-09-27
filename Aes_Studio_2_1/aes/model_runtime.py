from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import base64, json, os, re, threading, urllib.request, urllib.error

# Tool results may reference images (e.g. screenshots) with this marker.
# Vision-capable runtimes turn them into real image inputs; text-only runtimes strip them.
IMAGE_MARKER = re.compile(r'\[\[aes-image:(.+?)\]\]')

class ModelRuntimeError(RuntimeError):
    pass

@dataclass
class ModelConfig:
    name: str
    runtime: str
    model_path: str
    context_size: int = 8192
    gpu_layers: int = -1
    temperature: float = 0.25
    max_tokens: int = 2048
    endpoint: str = ''
    api_key: str = ''

def resolve_secret(value: str) -> str:
    """API keys may be stored literally or as env:VARIABLE_NAME (recommended)."""
    value = (value or '').strip()
    if value.startswith('env:'):
        return os.environ.get(value[4:].strip(), '')
    return value

def _split_images(text: str):
    """Return (clean_text, [image_paths]) for a message body."""
    paths = [m.strip() for m in IMAGE_MARKER.findall(text or '')]
    return IMAGE_MARKER.sub('[image attached]', text or ''), [p for p in paths if Path(p).is_file()]

def _image_b64(path: str):
    ext = Path(path).suffix.lower()
    media = {'.jpg':'image/jpeg','.jpeg':'image/jpeg','.gif':'image/gif','.webp':'image/webp'}.get(ext,'image/png')
    return media, base64.standard_b64encode(Path(path).read_bytes()).decode('ascii')

def _text_only(messages):
    return [{'role': m['role'], 'content': _split_images(m.get('content',''))[0]} for m in messages]

class BaseRuntime:
    def complete(self, messages: list[dict], config: ModelConfig, on_token=None) -> str:
        """Return the full reply. If on_token is given, call it with text pieces as they arrive (streaming)."""
        raise NotImplementedError
    def close(self):
        pass

class DemoRuntime(BaseRuntime):
    def complete(self, messages, config, on_token=None):
        out = self._reply(messages, config)
        if on_token: on_token(out)
        return out

    def _reply(self, messages, config):
        user = next((m.get('content','') for m in reversed(_text_only(messages)) if m.get('role')=='user'), '')
        if '<tool_result' in user:
            return "I received the tool result. Demo mode cannot reason deeply, but the Aes agent loop is working."
        if 'list the files' in user.lower() or 'show files' in user.lower() or 'اعرض الملفات' in user:
            return '<tool_call>{"name":"list_files","arguments":{"path":"."}}</tool_call>'
        return (
            f"{config.name} is running in local Demo mode. The Aes Studio agent, memory, skills, tools, "
            "permissions, training data and eval pipeline are active, but a real local GGUF model has not been imported yet.\n\n"
            f"You said: {user[:1200]}"
        )

class LlamaCppRuntime(BaseRuntime):
    def __init__(self, model_path: str, n_ctx: int, n_gpu_layers: int):
        try:
            from llama_cpp import Llama
        except Exception as e:
            raise ModelRuntimeError(
                "llama-cpp-python is not installed. Run setup_local_model.bat or install requirements-local-model.txt"
            ) from e
        p = Path(model_path)
        if not p.exists():
            raise ModelRuntimeError(f"GGUF model not found: {p}")
        try:
            self.llm = Llama(
                model_path=str(p),
                n_ctx=max(2048, int(n_ctx)),
                n_gpu_layers=int(n_gpu_layers),
                verbose=False,
            )
        except Exception as e:
            raise ModelRuntimeError(f"Failed to load GGUF: {e}") from e

    def complete(self, messages, config, on_token=None):
        try:
            if on_token:
                parts = []
                for chunk in self.llm.create_chat_completion(messages=_text_only(messages), temperature=float(config.temperature),
                                                             max_tokens=int(config.max_tokens), stream=True):
                    piece = chunk['choices'][0].get('delta', {}).get('content') or ''
                    if piece: parts.append(piece); on_token(piece)
                return ''.join(parts)
            out = self.llm.create_chat_completion(
                messages=_text_only(messages),
                temperature=float(config.temperature),
                max_tokens=int(config.max_tokens),
                stream=False,
            )
            return out['choices'][0]['message']['content'] or ''
        except Exception as e:
            raise ModelRuntimeError(str(e)) from e

class OpenAICompatRuntime(BaseRuntime):
    """Any server that speaks the OpenAI chat-completions protocol:
    Ollama (http://127.0.0.1:11434/v1), LM Studio (http://127.0.0.1:1234/v1),
    llama.cpp server, vLLM, DeepSeek (https://api.deepseek.com/v1), OpenRouter, Groq, etc.
    model_path holds the remote model id (e.g. qwen2.5-coder:32b or deepseek-chat)."""
    def __init__(self, endpoint: str, api_key: str):
        if not endpoint:
            raise ModelRuntimeError('Set the endpoint URL for this profile (e.g. http://127.0.0.1:11434/v1 for Ollama).')
        self.url = endpoint.rstrip('/') + '/chat/completions'
        self.api_key = resolve_secret(api_key)

    def _convert(self, messages):
        out = []
        for m in messages:
            text, images = _split_images(m.get('content', ''))
            if images and m['role'] == 'user':
                parts = [{'type': 'text', 'text': text}]
                for p in images[:4]:
                    media, data = _image_b64(p)
                    parts.append({'type': 'image_url', 'image_url': {'url': f'data:{media};base64,{data}'}})
                out.append({'role': 'user', 'content': parts})
            else:
                out.append({'role': m['role'], 'content': text})
        return out

    def _stream(self, body, headers, on_token):
        body = dict(body, stream=True); parts = []; other = []
        req = urllib.request.Request(self.url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
        with urllib.request.urlopen(req, timeout=600) as r:
            for raw in r:
                line = raw.decode('utf-8', errors='replace').strip()
                if not line.startswith('data:'):
                    other.append(line); continue
                data = line[5:].strip()
                if data == '[DONE]': break
                try: piece = (json.loads(data)['choices'][0].get('delta') or {}).get('content') or ''
                except Exception: continue
                if piece: parts.append(piece); on_token(piece)
        if not parts and other:   # server ignored stream=true and sent a normal JSON reply
            text = json.loads(''.join(other))['choices'][0]['message'].get('content') or ''
            on_token(text); return text
        return ''.join(parts)

    def complete(self, messages, config, on_token=None):
        body = {'model': config.model_path, 'messages': self._convert(messages),
                'temperature': float(config.temperature), 'max_tokens': int(config.max_tokens)}
        if on_token:
            headers = {'Content-Type': 'application/json'}
            if self.api_key: headers['Authorization'] = 'Bearer ' + self.api_key
            try:
                return self._stream(body, headers, on_token)
            except Exception:
                pass  # fall back to a normal request below
        headers = {'Content-Type': 'application/json'}
        if self.api_key: headers['Authorization'] = 'Bearer ' + self.api_key
        req = urllib.request.Request(self.url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                data = json.loads(r.read().decode('utf-8', errors='replace'))
        except urllib.error.HTTPError as e:
            detail = e.read().decode('utf-8', errors='replace')[:800]
            if e.code == 400 and any(isinstance(m['content'], list) for m in body['messages']):
                # Model probably lacks vision; retry text-only.
                body['messages'] = _text_only(messages)
                req = urllib.request.Request(self.url, data=json.dumps(body).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=600) as r:
                    data = json.loads(r.read().decode('utf-8', errors='replace'))
            else:
                raise ModelRuntimeError(f'HTTP {e.code} from {self.url}: {detail}') from e
        except Exception as e:
            raise ModelRuntimeError(f'Model server error ({self.url}): {e}') from e
        try:
            return data['choices'][0]['message'].get('content') or ''
        except Exception as e:
            raise ModelRuntimeError(f'Unexpected response: {str(data)[:500]}') from e

class AnthropicRuntime(BaseRuntime):
    """Claude through the official Anthropic Python SDK (pip install anthropic).
    model_path holds the Claude model id, default claude-opus-5."""
    def __init__(self, api_key: str, endpoint: str = ''):
        try:
            import anthropic
        except Exception as e:
            raise ModelRuntimeError('The anthropic package is not installed. Run: pip install anthropic') from e
        key = resolve_secret(api_key) or None  # None -> SDK resolves ANTHROPIC_API_KEY / ant auth profile
        kwargs = {'api_key': key} if key else {}
        if endpoint: kwargs['base_url'] = endpoint
        self.client = anthropic.Anthropic(**kwargs)
        self._fallbacks = True

    def _convert(self, messages):
        system = '\n\n'.join(m['content'] for m in messages if m['role'] == 'system')
        out = []
        for m in messages:
            if m['role'] == 'system': continue
            text, images = _split_images(m.get('content', ''))
            if images and m['role'] == 'user':
                blocks = []
                for p in images[:4]:
                    media, data = _image_b64(p)
                    blocks.append({'type': 'image', 'source': {'type': 'base64', 'media_type': media, 'data': data}})
                blocks.append({'type': 'text', 'text': text or '(image)'})
                out.append({'role': 'user', 'content': blocks})
            else:
                out.append({'role': m['role'], 'content': text or '(empty)'})
        if not out or out[0]['role'] != 'user':
            out.insert(0, {'role': 'user', 'content': '(start)'})
        return system, out

    def complete(self, messages, config, on_token=None):
        import anthropic
        system, msgs = self._convert(messages)
        params = dict(model=config.model_path or 'claude-opus-5', max_tokens=max(1024, int(config.max_tokens)),
                      system=system, messages=msgs, thinking={'type': 'adaptive'})
        try:
            if self._fallbacks:
                try:
                    with self.client.beta.messages.stream(betas=['server-side-fallback-2026-07-01'],
                                                          extra_body={'fallbacks': 'default'}, **params) as stream:
                        if on_token:
                            for piece in stream.text_stream: on_token(piece)
                        msg = stream.get_final_message()
                except anthropic.BadRequestError:
                    self._fallbacks = False  # model/account without server-side fallbacks
                    return self.complete(messages, config, on_token)
            else:
                with self.client.messages.stream(**params) as stream:
                    if on_token:
                        for piece in stream.text_stream: on_token(piece)
                    msg = stream.get_final_message()
        except anthropic.AuthenticationError as e:
            raise ModelRuntimeError('Claude API key is invalid or missing (set ANTHROPIC_API_KEY or the profile key).') from e
        except anthropic.RateLimitError as e:
            raise ModelRuntimeError('Claude API rate limit reached; try again shortly.') from e
        except anthropic.APIStatusError as e:
            raise ModelRuntimeError(f'Claude API error {e.status_code}: {e.message}') from e
        except anthropic.APIConnectionError as e:
            raise ModelRuntimeError('Cannot reach the Claude API (network).') from e
        if msg.stop_reason == 'refusal':
            return 'The model declined this request.'
        return ''.join(b.text for b in msg.content if b.type == 'text')

RUNTIMES = ('demo', 'llama_cpp', 'openai_compat', 'anthropic')

class RuntimeManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[tuple, BaseRuntime]] = {}

    def _key(self, cfg: ModelConfig):
        return (cfg.runtime, cfg.model_path, cfg.context_size, cfg.gpu_layers, cfg.endpoint, cfg.api_key)

    def get(self, cfg: ModelConfig) -> BaseRuntime:
        with self._lock:
            key = self._key(cfg)
            cached = self._cache.get(cfg.name)
            if cached and cached[0] == key:
                return cached[1]
            if cached:
                try: cached[1].close()
                except Exception: pass
            if cfg.runtime == 'demo':
                rt = DemoRuntime()
            elif cfg.runtime == 'llama_cpp':
                if not cfg.model_path:
                    raise ModelRuntimeError("This Aes profile has no GGUF file selected. Open Models and choose a local .gguf model.")
                rt = LlamaCppRuntime(cfg.model_path, cfg.context_size, cfg.gpu_layers)
            elif cfg.runtime == 'openai_compat':
                rt = OpenAICompatRuntime(cfg.endpoint, cfg.api_key)
            elif cfg.runtime == 'anthropic':
                rt = AnthropicRuntime(cfg.api_key, cfg.endpoint)
            else:
                raise ModelRuntimeError(f"Unsupported local runtime: {cfg.runtime}")
            self._cache[cfg.name] = (key, rt)
            return rt

    def unload(self, model_name: str | None = None):
        with self._lock:
            names = [model_name] if model_name else list(self._cache)
            for name in names:
                cached = self._cache.pop(name, None)
                if cached:
                    try: cached[1].close()
                    except Exception: pass

    def complete(self, row, messages, on_token=None):
        cfg = ModelConfig(
            name=row['name'], runtime=row['runtime'], model_path=row['model_path'] or '',
            context_size=int(row['context_size']), gpu_layers=int(row['gpu_layers']),
            temperature=float(row['temperature']), max_tokens=int(row['max_tokens']),
            endpoint=_get(row, 'endpoint'), api_key=_get(row, 'api_key')
        )
        return self.get(cfg).complete(messages, cfg, on_token)

def _get(row, key, default=''):
    try: return row[key] or default
    except (KeyError, IndexError): return default
