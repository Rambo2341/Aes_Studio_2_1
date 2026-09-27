from __future__ import annotations
import os, sys, shutil
from pathlib import Path

APP_NAME = "AesStudio"
APP_VERSION = "2.1.0"
MODEL_FAMILY = "Aes"

if getattr(sys, "frozen", False):
    BUNDLE_ROOT = Path(sys.executable).resolve().parent
    RESOURCE_ROOT = Path(getattr(sys, '_MEIPASS', BUNDLE_ROOT))
else:
    BUNDLE_ROOT = Path(__file__).resolve().parents[1]
    RESOURCE_ROOT = BUNDLE_ROOT

if os.name == "nt" and os.environ.get("AES_PORTABLE") != "1":
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    DATA = base / APP_NAME
else:
    DATA = BUNDLE_ROOT / "aes_data"

WORKSPACE = DATA / "workspace"
MODELS = DATA / "models"
KNOWLEDGE = DATA / "knowledge"
EXPORTS = DATA / "exports"
LOGS = DATA / "logs"
for p in (DATA, WORKSPACE, MODELS, KNOWLEDGE, EXPORTS, LOGS):
    p.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA / "aes2.db"

IDENTITY_BUNDLE = RESOURCE_ROOT / "identity"
IDENTITY_DATA = DATA / "identity"
IDENTITY_DATA.mkdir(parents=True, exist_ok=True)
for _name in ("SOUL.md", "IDENTITY.md", "USER.md"):
    _src = IDENTITY_BUNDLE / _name
    _dst = IDENTITY_DATA / _name
    if _src.exists() and not _dst.exists():
        try:
            shutil.copy2(_src, _dst)
        except Exception:
            pass

# Preserve Aes Studio 1.x data by leaving it untouched. The importer in db.py
# can read the legacy aes.db on first run when it is discoverable.
LEGACY_CANDIDATES = [
    DATA / "aes.db",
    BUNDLE_ROOT / "aes_data" / "aes.db",
]
