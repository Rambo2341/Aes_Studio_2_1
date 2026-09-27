from __future__ import annotations
"""Hardware detection, local-model recommendations and a 'doctor' report.

Aes is local-first: this module reads the real GPU/RAM so recommendations are based on the
owner's machine, and checks whether the local model server (Ollama) and tools are available.
"""
import json, os, platform, shutil, subprocess, urllib.request
from dataclasses import dataclass, field


@dataclass
class Hardware:
    os: str = ''
    cpu: str = ''
    ram_gb: float = 0.0
    gpus: list = field(default_factory=list)   # [{'name':..., 'vram_gb':...}]

    @property
    def vram_gb(self) -> float:
        return max((g['vram_gb'] for g in self.gpus), default=0.0)


def _ram_gb() -> float:
    try:
        import psutil
        return psutil.virtual_memory().total / 2**30
    except Exception:
        pass
    if os.name == 'nt':
        try:
            import ctypes
            class MS(ctypes.Structure):
                _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                            ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                            ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]
            m = MS(); m.dwLength = ctypes.sizeof(MS); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
            return m.ullTotalPhys / 2**30
        except Exception:
            return 0.0
    try:
        with open('/proc/meminfo') as f:
            return int(f.readline().split()[1]) / 2**20
    except Exception:
        return 0.0


def _gpus() -> list:
    exe = shutil.which('nvidia-smi')
    if not exe:
        return []
    try:
        out = subprocess.run([exe, '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
                             capture_output=True, text=True, timeout=10).stdout
        gpus = []
        for line in out.strip().splitlines():
            name, mem = [x.strip() for x in line.rsplit(',', 1)]
            gpus.append({'name': name, 'vram_gb': round(float(mem) / 1024, 1)})
        return gpus
    except Exception:
        return []


def detect() -> Hardware:
    return Hardware(os=f'{platform.system()} {platform.release()}', cpu=platform.processor() or platform.machine(),
                    ram_gb=round(_ram_gb(), 1), gpus=_gpus())


def recommend(vram_gb: float) -> dict:
    """Free, local, legally usable models that fit the GPU (Q4 GGUF / Ollama sizes)."""
    if vram_gb >= 22:
        return {'brain': 'qwen2.5-coder:32b', 'vision': 'qwen2.5vl:32b', 'train_base': 'Qwen/Qwen2.5-Coder-14B-Instruct',
                'train_where': 'this PC (QLoRA)'}
    if vram_gb >= 14:
        return {'brain': 'qwen2.5-coder:14b', 'vision': 'qwen2.5vl:7b', 'train_base': 'Qwen/Qwen2.5-Coder-7B-Instruct',
                'train_where': 'this PC (QLoRA)'}
    if vram_gb >= 7.5:   # RTX 3070 / 3060 Ti / 4060 Ti 8GB
        return {'brain': 'qwen2.5vl:7b', 'vision': 'qwen2.5vl:7b', 'train_base': 'Qwen/Qwen2.5-Coder-7B-Instruct',
                'train_where': 'this PC with --qlora --max-seq 1024 --rank 16 (slow but free); if out of memory use Qwen2.5-Coder-1.5B-Instruct'}
    if vram_gb >= 5.5:
        return {'brain': 'qwen2.5-coder:7b', 'vision': 'qwen2.5vl:3b', 'train_base': 'Qwen/Qwen2.5-Coder-1.5B-Instruct',
                'train_where': 'this PC (QLoRA)'}
    return {'brain': 'qwen2.5-coder:3b', 'vision': 'qwen2.5vl:3b', 'train_base': 'Qwen/Qwen2.5-Coder-0.5B-Instruct',
            'train_where': 'rented GPU recommended'}


def ollama_models(url='http://127.0.0.1:11434') -> list | None:
    """Installed Ollama models, or None if Ollama is not running."""
    try:
        with urllib.request.urlopen(url.rstrip('/') + '/api/tags', timeout=3) as r:
            return [m['name'] for m in json.loads(r.read().decode()).get('models', [])]
    except Exception:
        return None


def doctor(db=None) -> str:
    hw = detect(); rec = recommend(hw.vram_gb)
    lines = ['Aes doctor', '==========',
             f'OS: {hw.os}', f'CPU: {hw.cpu}', f'RAM: {hw.ram_gb} GB',
             'GPU: ' + (', '.join(f"{g['name']} ({g['vram_gb']} GB)" for g in hw.gpus) or 'no NVIDIA GPU detected (nvidia-smi not found)')]
    om = ollama_models()
    lines.append('Ollama: ' + ('not running / not installed  ->  https://ollama.com/download' if om is None else f'running, models: {", ".join(om) or "none yet"}'))
    lines += ['', 'Recommended FREE local setup for this PC:',
              f'  brain:  ollama pull {rec["brain"]}', f'  vision: ollama pull {rec["vision"]}',
              f'  train Aes 3.0 from: {rec["train_base"]}  ({rec["train_where"]})']
    if om is not None and not any(rec['brain'].split(':')[0] in m for m in om):
        lines.append(f'  -> model not installed yet: run  ollama pull {rec["brain"]}')
    tools = {'git': 'git', 'rojo': 'rojo', 'blender': 'blender', 'yt-dlp': 'yt-dlp', 'ffmpeg': 'ffmpeg'}
    if db is not None:
        for k in ('blender_path', 'unity_path', 'rojo_path'):
            v = db.setting(k, '')
            if v: tools[k.replace('_path', '')] = v
    lines += ['', 'Tools:'] + [f'  {k}: {"found" if (shutil.which(v) or os.path.exists(v)) else "missing"}' for k, v in tools.items()]
    pk = []
    for mod in ('pyautogui', 'pyperclip', 'playwright', 'faster_whisper', 'youtube_transcript_api', 'llama_cpp', 'torch', 'peft', 'bitsandbytes', 'PySide6'):
        try:
            __import__(mod); pk.append(f'  {mod}: ok')
        except Exception:
            pk.append(f'  {mod}: missing')
    lines += ['', 'Python packages:'] + pk
    if db is not None:
        m = db.model(db.setting('default_model', ''))
        lines += ['', f"Default brain: {db.setting('default_model', '')} ({m['runtime'] if m else 'missing'}"
                      f"{', CLOUD - costs money' if m and is_cloud(m) else ', local - free'})"]
    return '\n'.join(lines)


def is_cloud(row) -> bool:
    """True when a profile sends data to a paid remote service."""
    rt = row['runtime']
    if rt == 'anthropic':
        return True
    if rt == 'openai_compat':
        ep = (row['endpoint'] if 'endpoint' in row.keys() else '') or ''
        return not any(h in ep for h in ('127.0.0.1', 'localhost', '0.0.0.0', '192.168.', '10.0.'))
    return False
