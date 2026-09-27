from __future__ import annotations
import os, sys, shutil
from pathlib import Path

APP_NAME = "AesStudio"
APP_VERSION = "2.2.0"
MODEL_FAMILY = "Aes"

if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', BUNDLE_ROOT))
else:
    BUNDLE_ROOT = Path(__file__).resolve().parents[1]
    RESOURCE_ROOT = BUNDLE_ROOT

# Where Aes keeps its brain on disk (memory, knowledge, conversations, reports).
# Priority: AES_DATA_DIR env var -> aes_data_location.txt next to the app -> OS default.
# To give Aes its own dedicated drive, put e.g.  D:\AesBrain  in aes_data_location.txt.
_POINTER = BUNDLE_ROOT / "aes_data_location.txt"
_custom = os.environ.get("AES_DATA_DIR", "").strip()
if not _custom and _POINTER.exists():
    try:
        _custom = next((l.strip() for l in _POINTER.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")), "")
    except Exception:
        _custom = ""
if _custom:
    DATA = Path(os.path.expandvars(_custom)).expanduser()
elif os.name == "nt" and os.environ.get("AES_PORTABLE") != "1":
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    DATA = base / APP_NAME
else:
    DATA = BUNDLE_ROOT / "aes_data"

WORKSPACE = DATA / "workspace"
MODELS = DATA / "models"
KNOWLEDGE = DATA / "knowledge"
EXPORTS = DATA / "exports"
LOGS = DATA / "logs"
REPORTS = DATA / "reports"
for p in (DATA, WORKSPACE, MODELS, KNOWLEDGE, EXPORTS, LOGS, REPORTS):
    p.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA / "aes2.db"

IDENTITY_BUNDLE = RESOURCE_ROOT / "identity"
IDENTITY_DATA = DATA / "identity"
IDENTITY_DATA.mkdir(parents=True, exist_ok=True)
IDENTITY_VERSION_TAG = "aes-identity-version: 2.2"
for _name in ("SOUL.md", "IDENTITY.md", "USER.md"):
    _src = IDENTITY_BUNDLE / _name
    _dst = IDENTITY_DATA / _name
    if not _src.exists():
        continue
    try:
        if not _dst.exists():
            shutil.copy2(_src, _dst)
        elif IDENTITY_VERSION_TAG not in _dst.read_text(encoding="utf-8", errors="replace"):
            # Upgrade older identity files, keeping the owner's previous copy.
            shutil.copy2(_dst, _dst.with_suffix(".md.bak"))
            shutil.copy2(_src, _dst)
    except Exception:
        pass

# Preserve Aes Studio 1.x data by leaving it untouched. The importer in db.py
# can read the legacy aes.db on first run when it is discoverable.
LEGACY_CANDIDATES = [
    DATA / "aes.db",
    BUNDLE_ROOT / "aes_data" / "aes.db",
]
