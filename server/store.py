"""Folder-per-demo file store.  data/demos/<id>/demo.json + stage outputs + media.

Everything is plain JSON so a demo can be inspected (or fixed) with a text editor.
Swapping in a database later means re-implementing this module only.
"""
from __future__ import annotations

import json
import mimetypes
import re
import secrets
import shutil
import threading
import time
from pathlib import Path
from typing import Any

from . import config

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

STAGES = ["understand", "plan", "author", "faq", "voice", "rehearsal", "bundle"]
CARDS = ["visuals", "facts", "script", "faq", "persona", "ctas"]  # what the user aligns on, in order

KIND_BY_EXT = {
    ".mp4": "video", ".mov": "video", ".webm": "video", ".m4v": "video",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image", ".avif": "image", ".heic": "image", ".heif": "image",
    ".pdf": "pdf", ".docx": "doc", ".doc": "doc", ".txt": "text", ".md": "text",
    ".csv": "text", ".json": "text",
}


def now() -> float:
    return time.time()


def _lock(demo_id: str) -> threading.Lock:
    with _locks_guard:
        if demo_id not in _locks:
            _locks[demo_id] = threading.Lock()
        return _locks[demo_id]


def demo_dir(demo_id: str) -> Path:
    if not re.fullmatch(r"dm_[a-z0-9]{8}", demo_id):
        raise KeyError("bad demo id")
    return config.DATA_DIR / demo_id


def path(demo_id: str, *parts: str) -> Path:
    return demo_dir(demo_id).joinpath(*parts)


def exists(demo_id: str) -> bool:
    try:
        return (demo_dir(demo_id) / "demo.json").exists()
    except KeyError:
        return False


def new_demo(name: str) -> dict:
    demo_id = "dm_" + secrets.token_hex(4)
    d = demo_dir(demo_id)
    for sub in ("sources", "audio", "sessions", "logs", "leads", "visual/inputs", "visual/frames", "visual/generated", "visual/attempts"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    demo = {
        "id": demo_id,
        "name": name.strip() or "Untitled demo",
        "product": {"name": name.strip(), "category": "", "url": ""},
        "status": "sources",  # sources | reading | align | building | ready | error
        "created_at": now(),
        "updated_at": now(),
        "version": 0,
        "sources": [],
        "stages": {s: {"status": "idle", "updated_at": None, "error": None, "message": ""} for s in STAGES},
        "approvals": {c: False for c in CARDS},
        "settings": {
            "tts_provider": config.TTS_PROVIDER,
            "voice_name": config.GEMINI_TTS_VOICE if config.TTS_PROVIDER == "gemini" else config.GCLOUD_TTS_VOICE,
            "language": "en-IN",  # en-IN | hinglish | hi-IN | ta-IN | te-IN | kn-IN | mr-IN | bn-IN | gu-IN | ml-IN | pa-IN
            "competition": "off",  # off | on — compare only against competitor URLs the user added, always with a verify caveat
            "audience": "everyday",  # everyday | informed | expert — controls jargon and technical depth
            "pitch_minutes": 3,  # narration budget before Q&A
            "languages": ["en-IN"],  # additional demo languages are translated + voiced at build
            "rehearsal_questions": config.REHEARSAL_QUESTIONS,
        },
        "running": None,
        "visual_asset": None,
    }
    save(demo_id, demo)
    write_json(demo_id, "conversation.json", [])
    return demo


def load(demo_id: str) -> dict:
    p = path(demo_id, "demo.json")
    if not p.exists():
        raise KeyError(demo_id)
    return _migrate(json.loads(p.read_text()))


def _migrate(demo: dict) -> dict:
    """Older demos: add missing stages and cards (pitch → script; faq)."""
    st = demo.setdefault("stages", {})
    for k in STAGES:
        st.setdefault(k, {"status": "idle", "updated_at": None, "error": None, "message": ""})
    ap = demo.setdefault("approvals", {})
    if "pitch" in ap and "script" not in ap:
        ap["script"] = ap.pop("pitch")
    for c in CARDS:
        ap.setdefault(c, False)
    demo["approvals"] = {c: ap.get(c, False) for c in CARDS}
    demo.setdefault("visual_asset", None)
    return demo


def save(demo_id: str, demo: dict) -> None:
    demo["updated_at"] = now()
    p = path(demo_id, "demo.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(demo, indent=2, ensure_ascii=False))
    tmp.replace(p)


def update(demo_id: str, fn) -> dict:
    """Atomic read-modify-write under a per-demo lock. fn(demo) mutates in place."""
    with _lock(demo_id):
        demo = load(demo_id)
        fn(demo)
        save(demo_id, demo)
        return demo


def list_demos() -> list[dict]:
    out = []
    for d in sorted(config.DATA_DIR.glob("dm_*")):
        p = d / "demo.json"
        if p.exists():
            try:
                demo = json.loads(p.read_text())
            except json.JSONDecodeError:
                continue
            out.append({
                "id": demo["id"], "name": demo["name"], "status": demo["status"],
                "product": demo.get("product", {}), "created_at": demo["created_at"],
                "updated_at": demo["updated_at"], "version": demo.get("version", 0),
                "sources": len(demo.get("sources", [])),
                "approvals": demo.get("approvals", {}),
                "sessions": len(list((d / "sessions").glob("*.json"))) if (d / "sessions").exists() else 0,
                "visual_asset": demo.get("visual_asset"),
            })
    out.sort(key=lambda x: x["updated_at"], reverse=True)
    return out


def delete_demo(demo_id: str) -> None:
    d = demo_dir(demo_id)
    if d.exists():
        shutil.rmtree(d)


def duplicate_demo(demo_id: str) -> dict:
    src = load(demo_id)
    new = new_demo(src["name"] + " (copy)")
    nid = new["id"]
    shutil.rmtree(demo_dir(nid))
    shutil.copytree(demo_dir(demo_id), demo_dir(nid))
    demo = load(demo_id)
    demo["id"] = nid
    demo["name"] = src["name"] + " (copy)"
    demo["created_at"] = now()
    demo["running"] = None
    save(nid, demo)
    return demo


# ---------- stage outputs ----------

def write_json(demo_id: str, name: str, obj: Any) -> None:
    p = path(demo_id, name)
    p.parent.mkdir(parents=True, exist_ok=True)
    # Readers may poll stage artifacts while a worker is updating them. Publish
    # the complete payload in one replace so a partial JSON document can never
    # be mistaken for a missing artifact and reset live state.
    tmp = p.with_name(f".{p.name}.{secrets.token_hex(6)}.tmp")
    try:
        tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False))
        tmp.replace(p)
    finally:
        tmp.unlink(missing_ok=True)


def read_json(demo_id: str, name: str, default: Any = None) -> Any:
    p = path(demo_id, name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return default


def log(demo_id: str, stage: str, payload: Any) -> None:
    p = path(demo_id, "logs", f"{int(now())}-{stage}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    except Exception:
        pass


# ---------- sources ----------

def add_file_source(demo_id: str, filename: str, data: bytes, role: str = "product") -> dict:
    ext = Path(filename).suffix.lower()
    kind = KIND_BY_EXT.get(ext, "text" if ext in (".txt", ".md") else "other")
    if kind == "other":
        raise ValueError(f"unsupported file type {ext}")
    sid = "src_" + secrets.token_hex(3)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(filename).name)[:80]
    rel = f"sources/{sid}_{safe}"
    p = path(demo_id, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    src = {
        "id": sid, "kind": kind, "name": Path(filename).name, "path": rel, "url": "",
        "mime": mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "size": len(data), "role": role, "added_at": now(), "use_in_demo": True,
    }
    update(demo_id, lambda d: d["sources"].append(src))
    return src


def add_url_source(demo_id: str, url: str, role: str = "product") -> dict:
    sid = "src_" + secrets.token_hex(3)
    src = {"id": sid, "kind": "url", "name": url, "path": "", "url": url, "mime": "text/html",
           "size": 0, "role": role, "added_at": now(), "use_in_demo": True}
    update(demo_id, lambda d: d["sources"].append(src))
    return src


def add_text_source(demo_id: str, name: str, text: str, role: str = "brand") -> dict:
    return add_file_source(demo_id, f"{name}.md", text.encode("utf-8"), role)


def remove_source(demo_id: str, source_id: str) -> None:
    def fn(d):
        keep = []
        for s in d["sources"]:
            if s["id"] == source_id:
                if s.get("path"):
                    try:
                        path(demo_id, s["path"]).unlink(missing_ok=True)
                    except Exception:
                        pass
            else:
                keep.append(s)
        d["sources"] = keep
    update(demo_id, fn)


def patch_source(demo_id: str, source_id: str, fields: dict) -> dict:
    allowed = {k: v for k, v in fields.items() if k in ("use_in_demo", "role", "name", "play", "proxy")}
    def fn(d):
        for s in d["sources"]:
            if s["id"] == source_id:
                s.update(allowed)
    return update(demo_id, fn)


def visual_allowed(demo: dict, source_id: str) -> bool:
    for s in demo.get("sources", []):
        if s["id"] == source_id:
            return s.get("use_in_demo", True) is not False
    return True


def media_path(demo_id: str, rel: str) -> Path:
    base = demo_dir(demo_id).resolve()
    p = (base / rel).resolve()
    if base not in p.parents:
        raise KeyError("outside demo folder")
    return p


def digest(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode()).hexdigest()[:16]
