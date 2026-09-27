from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import threading

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

class BaseRuntime:
    def complete(self, messages: list[dict], config: ModelConfig) -> str:
        raise NotImplementedError
    def close(self):
        pass

class DemoRuntime(BaseRuntime):
    def complete(self, messages, config):
        user = next((m.get('content','') for m in reversed(messages) if m.get('role')=='user'), '')
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

    def complete(self, messages, config):
        try:
            out = self.llm.create_chat_completion(
                messages=messages,
                temperature=float(config.temperature),
                max_tokens=int(config.max_tokens),
                stream=False,
            )
            return out['choices'][0]['message']['content'] or ''
        except Exception as e:
            raise ModelRuntimeError(str(e)) from e

class RuntimeManager:
    def __init__(self):
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[tuple, BaseRuntime]] = {}

    def _key(self, cfg: ModelConfig):
        return (cfg.runtime, cfg.model_path, cfg.context_size, cfg.gpu_layers)

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

    def complete(self, row, messages):
        cfg = ModelConfig(
            name=row['name'], runtime=row['runtime'], model_path=row['model_path'] or '',
            context_size=int(row['context_size']), gpu_layers=int(row['gpu_layers']),
            temperature=float(row['temperature']), max_tokens=int(row['max_tokens'])
        )
        return self.get(cfg).complete(messages, cfg)
