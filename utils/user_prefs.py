from __future__ import annotations
import json, threading
from pathlib import Path
import os

# На Vercel/Serverless пишем во временную директорию
_is_vercel = bool(os.getenv("VERCEL") or os.getenv("VC_ENV"))
_PATH = Path("/tmp/user_prefs.json") if _is_vercel else Path("data/user_prefs.json")
_LOCK = threading.Lock()
_DEFAULT = {"lang": "ru-RU", "voice": "ru-RU-Wavenet-D", "style": "neutral"}  # style: neutral|calm|cheerful

def _load() -> dict:
    if not _PATH.exists():
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text("{}", encoding="utf-8")
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}

def get(user_id: int) -> dict:
    with _LOCK:
        db = _load()
        return {**_DEFAULT, **db.get(str(user_id), {})}

def set(user_id: int, **kwargs) -> dict:
    with _LOCK:
        db = _load()
        cur = {**_DEFAULT, **db.get(str(user_id), {})}
        cur.update({k:v for k,v in kwargs.items() if v is not None})
        db[str(user_id)] = cur
        _PATH.write_text(json.dumps(db, ensure_ascii=False, indent=2), encoding="utf-8")
        return cur


