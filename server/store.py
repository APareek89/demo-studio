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
from urllib.parse import urlsplit

from . import config, schemas

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

# Name the persisted build stages and the human approval cards separately.
# Input: these fixed lists. Output: initial status/approval entries when new_demo() creates a demo.
# Linked: server/graph.py runs the stages; server/orchestrator.py:changed_cards decides which cards reopen.
STAGES = ["understand", "coach", "plan", "author", "deck", "faq", "voice", "rehearsal", "bundle"]
CARDS = ["visuals", "facts", "script", "faq", "persona", "ctas"]  # what the user aligns on, in order

KIND_BY_EXT = {
    ".mp4": "video", ".mov": "video", ".webm": "video", ".m4v": "video",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image", ".gif": "image", ".avif": "image", ".heic": "image", ".heif": "image",
    ".pdf": "pdf", ".docx": "doc", ".doc": "doc", ".txt": "text", ".md": "text",
    ".csv": "text", ".json": "text",
}


# Provide the timestamp format used in stored demo records.
# Input: none. Output: current Unix time in seconds.
# Linked: server/orchestrator.py and server/agents/understand.py use these times in saved progress/evidence.
def now() -> float:
    return time.time()


# Return one shared thread lock for changes to a particular demo.
# Input: demo ID. Output: that demo lock, creating it once if needed.
# Linked: server/orchestrator.py uses update() so concurrent progress changes do not overwrite one another.
def _lock(demo_id: str) -> threading.Lock:
    with _locks_guard:
        if demo_id not in _locks:
            _locks[demo_id] = threading.Lock()
        return _locks[demo_id]


# Validate a demo ID and locate its folder below the configured data directory.
# Input: demo ID. Output: a Path, or KeyError for an invalid ID.
# Linked: server/config.py:DATA_DIR selects local, test or deployed storage.
def demo_dir(demo_id: str) -> Path:
    if not re.fullmatch(r"dm_[a-z0-9]{8}", demo_id):
        raise KeyError("bad demo id")
    return config.DATA_DIR / demo_id


# Build the path to an artifact inside a named demo folder.
# Input: demo ID and path pieces. Output: a Path; this helper does not check arbitrary path traversal.
# Linked: server/app.py:media uses the stricter media_path() boundary for request-supplied media paths.
def path(demo_id: str, *parts: str) -> Path:
    return demo_dir(demo_id).joinpath(*parts)


# Check for a demo metadata file without raising on an invalid ID.
# Input: demo ID. Output: whether demo.json exists.
# Linked: server/app.py:_demo_or_404 uses this before reading or restoring a demo.
def exists(demo_id: str) -> bool:
    try:
        return (demo_dir(demo_id) / "demo.json").exists()
    except KeyError:
        return False


# Create the demo folders, initial settings and unapproved review cards.
# Input: display name. Output: saved demo.json, empty conversation.json and the demo record.
# Linked: server/config.py supplies defaults; server/app.py creates demos through this store.
def new_demo(name: str) -> dict:
    demo_id = "dm_" + secrets.token_hex(4)
    d = demo_dir(demo_id)
    for sub in ("sources", "audio", "sessions", "logs", "leads"):
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
    }
    save(demo_id, demo)
    write_json(demo_id, "conversation.json", [])
    return demo


# Read demo.json and adapt older metadata to the current stages/cards in memory.
# Input: demo ID. Output: the demo dictionary, or KeyError if missing.
# Linked: server/graph.py nodes and server/agents/* use this for source/settings/status inputs.
def load(demo_id: str) -> dict:
    p = path(demo_id, "demo.json")
    if not p.exists():
        raise KeyError(demo_id)
    return _migrate(json.loads(p.read_text()))


# Fill missing stage/card entries so older demos can still open.
# Input: a loaded demo dictionary. Output: the same dictionary with current review/status keys.
# Linked: server/graph.py:align_wait expects the six current approval cards.
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
    return demo


# Publish a complete demo metadata file using a temporary file and rename.
# Input: demo ID and record. Output: updated demo.json with a fresh updated_at timestamp.
# Linked: server/orchestrator.py uses update() for locked status changes before this writer runs.
def save(demo_id: str, demo: dict) -> None:
    demo["updated_at"] = now()
    p = path(demo_id, "demo.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(demo, indent=2, ensure_ascii=False))
    tmp.replace(p)


# Protect a read-change-save operation with the per-demo lock.
# Input: demo ID and a function that edits its record. Output: the changed and saved record.
# Linked: server/orchestrator.py:set_stage and apply_actions supply update callbacks.
def update(demo_id: str, fn) -> dict:
    """Atomic read-modify-write under a per-demo lock. fn(demo) mutates in place."""
    with _lock(demo_id):
        demo = load(demo_id)
        fn(demo)
        save(demo_id, demo)
        return demo


# Build lightweight library rows from saved demo folders, newest update first.
# Input: server/config.py:DATA_DIR. Output: summaries with status, sources, approvals and session counts.
# Linked: server/app.py:list_demos returns these summaries to the home/library UI.
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
            })
    out.sort(key=lambda x: x["updated_at"], reverse=True)
    return out


# Remove the complete local folder for a demo when the caller requests deletion.
# Input: demo ID. Output: no return value; metadata, artifacts and media in that folder are removed.
# Linked: server/app.py:delete_demo is the route that invokes this storage action.
def delete_demo(demo_id: str) -> None:
    d = demo_dir(demo_id)
    if d.exists():
        shutil.rmtree(d)


# Copy a demo folder under a new identity while retaining its existing content.
# Input: source demo ID. Output: a new demo record/folder, including copied artifacts and records.
# Linked: server/app.py:duplicate exposes this; it is a folder copy rather than fresh agent generation.
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

# Write a stage artifact as a complete JSON file, then atomically replace its old version.
# Input: demo ID, relative filename and JSON-compatible value. Output: the saved file; no return value.
# Linked: server/agents/plan.py:run, author.py:run and other agents hand off work through these files.
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


# Visit own-product and competitor facts while retaining who owns each fact.
# Input: understanding data. Output: fact/competitor pairs, with no owner for product facts.
# Linked: server/orchestrator.py fact-review actions must not mix competitor evidence into product claims.
def fact_entries(understanding: dict):
    """Review both registries without copying competitor facts into product facts."""
    for fact in understanding.get("facts", []):
        yield fact, None
    for competitor in understanding.get("competitors", []):
        for fact in competitor.get("facts", []):
            yield fact, competitor


# Find exactly one fact and its owner, rejecting missing or ambiguous IDs.
# Input: understanding data and fact ID. Output: one fact/owner pair or an error.
# Linked: server/app.py fact-edit routes reach this through edit_fact/set_fact_approval.
def _fact_entry(understanding: dict, fact_id: str):
    matches = [(fact, owner) for fact, owner in fact_entries(understanding) if fact.get("id") == fact_id]
    if not matches:
        raise KeyError("fact not found")
    if len(matches) != 1:
        raise ValueError("Fact id is ambiguous in the registry")
    return matches[0]


# Apply a human fact correction while holding the demo write lock.
# Input: demo ID, fact ID and edited fields. Output: the validated current/new assertion.
# Linked: server/orchestrator.py:apply_actions and server/app.py fact-edit routes call this boundary.
def edit_fact(demo_id: str, fact_id: str, edits: dict) -> dict:
    """Validate and version a human correction under the demo's write lock."""
    with _lock(demo_id):
        return _edit_fact_locked(demo_id, fact_id, edits)


# Validate applicability/source changes and preserve prior assertion meaning when content changes.
# Input: an existing fact and requested edits. Output: a saved versioned fact, or the unchanged fact for a no-op.
# Linked: server/schemas.py:Fact checks shape; server/knowledge.py:copy_on_edit creates the new assertion identity.
def _edit_fact_locked(demo_id: str, fact_id: str, edits: dict) -> dict:
    from datetime import date
    from . import knowledge
    allowed = {"value", "claim", "conditions", "truth", "source", "scope"}
    if not isinstance(edits, dict) or not edits or set(edits) - allowed:
        raise ValueError("Send value, claim, conditions, truth, source or scope fields only")
    und = read_json(demo_id, "understanding.json") or {}
    fact, owner = _fact_entry(und, fact_id)
    candidate = {**fact, "source": dict(fact.get("source") or {})}
    for field, limit in (("value", 1000), ("claim", 500), ("conditions", 1000), ("truth", 30)):
        if field not in edits:
            continue
        value = edits[field]
        if not isinstance(value, str) or len(value.strip()) > limit or (field != "conditions" and not value.strip()):
            raise ValueError(f"{field} must be text of {'0' if field == 'conditions' else '1'}–{limit} characters")
        candidate[field] = value.strip()
    # Check model/market/date applicability fields without silently accepting unknown keys or invalid dates.
    # Input: requested scope edits. Output: normalized scope on the candidate, or a validation error.
    # Linked: server/knowledge.py:SCOPE_KEYS defines supported applicability fields.
    if "scope" in edits:
        scope = edits["scope"]
        if not isinstance(scope, dict) or set(scope) - knowledge.SCOPE_KEYS:
            raise ValueError("scope must be an object containing only known applicability fields")
        if any(not isinstance(value, str) or len(value.strip()) > 500 for value in scope.values()):
            raise ValueError("Every scope value must be text of at most 500 characters")
        candidate["scope"] = {key: value.strip() for key, value in scope.items() if value.strip()}
        for key in ("effective_from", "effective_to"):
            if key in candidate["scope"]:
                try:
                    parsed = date.fromisoformat(candidate["scope"][key])
                    if parsed.isoformat() != candidate["scope"][key]:
                        raise ValueError("not ISO date")
                except ValueError as exc:
                    raise ValueError(f"scope.{key} must be an ISO YYYY-MM-DD date") from exc
        if candidate["scope"].get("effective_from", "") > candidate["scope"].get("effective_to", "9999-12-31"):
            raise ValueError("scope.effective_to cannot precede effective_from")
    # Require a traceable quote and explicit conditions when an edit changes its evidence source.
    # Input: source reference, locator and quote edits. Output: updated candidate source metadata or a refusal.
    # Linked: server/knowledge.py:copy_on_edit later records the changed assertion without rewriting old snapshots.
    if "source" in edits:
        source = edits["source"]
        if not isinstance(source, dict) or not source or set(source) - {"ref", "locator", "quote"}:
            raise ValueError("source must contain ref, locator or quote only")
        for field, value in source.items():
            if not isinstance(value, str) or len(value.strip()) > (10000 if field == "quote" else 2000):
                raise ValueError(f"source.{field} must be text within the source field limit")
        candidate["source"].update({key: value.strip() for key, value in source.items()})
        if candidate["source"].get("ref") != (fact.get("source") or {}).get("ref"):
            if not all(isinstance(source.get(key), str) and source[key].strip() for key in ("locator", "quote")) or "conditions" not in edits:
                raise ValueError("Changing source.ref requires its locator, exact quote and explicit conditions")
    try:
        schemas.Fact.model_validate(candidate, strict=True)
    except ValueError as exc:
        raise ValueError("Fact correction does not match the existing fact schema") from exc
    sources = {source["id"]: source for source in load(demo_id)["sources"]}
    ref = candidate["source"].get("ref")
    source = sources.get(ref)
    if not source:
        raise ValueError("source.ref must name an existing source in this demo")
    if owner is not None:
        owner_ref = owner.get("source_id") or (fact.get("source") or {}).get("ref")
        if source.get("role") != "competitor" or ref != owner_ref:
            raise ValueError("A competitor fact must keep its owning competitor source; review the fact from the other source instead")
    elif source.get("role") == "competitor":
        raise ValueError("A product fact cannot cite a competitor source")
    # Give changed evidence a new assertion identity and retire conflicts referring to the old meaning.
    # Input: old fact and validated candidate. Output: saved understanding.json with current assertion metadata.
    # Linked: server/knowledge.py:copy_on_edit preserves the historical assertion for published snapshots.
    candidate = knowledge.copy_on_edit(demo_id, fact, candidate, competitor=owner is not None)
    if candidate["id"] == fact["id"]:
        return fact  # A no-op preserves approvals, metadata and cached draft inputs.
    fact.clear()
    fact.update(candidate)
    for conflict in und.get("knowledge", {}).get("conflicts", []):
        if fact_id in conflict.get("fact_ids", []):
            conflict.update(status="superseded", resolution="assertion_edited", superseded_by=fact["id"],
                            reason="A referenced assertion was corrected. Re-read to compare the current evidence; the earlier decision is not transferred.")
    write_json(demo_id, "understanding.json", und)
    return fact


# Include or exclude an existing fact from approved content.
# Input: demo ID, fact ID and a strict boolean. Output: the saved fact with its approval flag changed.
# Linked: server/orchestrator.py:apply_actions uses this for removal without deleting historical evidence.
def set_fact_approval(demo_id: str, fact_id: str, approved: bool) -> dict:
    if not isinstance(approved, bool):
        raise ValueError("approved must be true or false")
    und = read_json(demo_id, "understanding.json") or {}
    fact, _owner = _fact_entry(und, fact_id)
    fact["approved"] = approved
    write_json(demo_id, "understanding.json", und)
    return fact


# Load a saved artifact while allowing a caller-provided fallback for missing or malformed JSON.
# Input: demo ID, filename and optional default. Output: parsed data or that default.
# Linked: server/agents/author.py:run reads understanding.json and plan.json through this helper.
def read_json(demo_id: str, name: str, default: Any = None) -> Any:
    p = path(demo_id, name)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return default


# Write a stage diagnostic record, ignoring JSON/write errors after its folder is prepared.
# Input: demo ID, stage label and payload. Output: a timestamped file under logs when writing succeeds.
# Linked: server/orchestrator.py:_run_stage records stage errors through this helper.
def log(demo_id: str, stage: str, payload: Any) -> None:
    p = path(demo_id, "logs", f"{int(now())}-{stage}.json")
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    except Exception:
        pass


# ---------- sources ----------

# Save uploaded bytes and register their source identity, type and role.
# Input: demo ID, filename, bytes and role. Output: a saved source file plus its demo.json source record.
# Linked: server/app.py upload routes call this; server/agents/understand.py:run later consumes the source.
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


# Register a source URL without fetching its pages in this function.
# Input: demo ID, URL and role. Output: a new URL source record in demo.json.
# Linked: server/crawl.py:ingest and server/agents/understand.py:run perform the later reading work.
def add_url_source(demo_id: str, url: str, role: str = "product") -> dict:
    sid = "src_" + secrets.token_hex(3)
    src = {"id": sid, "kind": "url", "name": url, "path": "", "url": url, "mime": "text/html",
           "size": 0, "role": role, "added_at": now(), "use_in_demo": True}
    update(demo_id, lambda d: d["sources"].append(src))
    return src


# Store typed source text using the same file-source path as an uploaded document.
# Input: demo ID, name, text and role. Output: a Markdown source file and source record.
# Linked: server/agents/understand.py:run can read the resulting text as source material.
def add_text_source(demo_id: str, name: str, text: str, role: str = "brand") -> dict:
    return add_file_source(demo_id, f"{name}.md", text.encode("utf-8"), role)


# Remove a source record and attempt to delete its original file.
# Input: demo ID and source ID. Output: updated sources metadata; file deletion is best effort.
# Linked: server/app.py:remove_source coordinates the broader application response to this change.
def remove_source(demo_id: str, source_id: str) -> None:
    # Retain every other source while removing the selected source and its local file if possible.
    # Input: mutable demo record. Output: a replacement sources list in the same record.
    # Linked: server/app.py:remove_source calls the outer helper; update() saves this callback change.
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


# Allow supported source settings to change and validate supplied HTTP(S) URL metadata.
# Input: demo ID, source ID and field edits. Output: updated demo metadata or a URL validation error.
# Linked: server/agents/understand.py:run uses this to record video playback/proxy paths.
def patch_source(demo_id: str, source_id: str, fields: dict) -> dict:
    allowed = {k: v for k, v in fields.items() if k in ("use_in_demo", "role", "name", "play", "proxy", "derived_from", "url")}
    if "url" in allowed:
        url = allowed["url"]
        try:
            if not isinstance(url, str) or not url.strip() or any(char.isspace() for char in url.strip()):
                raise ValueError
            parsed = urlsplit(url.strip())
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError
            _ = parsed.port  # reject malformed/out-of-range ports before saving
        except (ValueError, TypeError):
            raise ValueError("Source URL must be an absolute http(s) URL without credentials") from None
        allowed["url"] = url.strip()
    # Apply the allowed fields to the matching source, preserving all other source records.
    # Input: mutable demo record and captured validated edits. Output: changed source metadata in place.
    # Linked: server/agents/understand.py:run later reads these source settings; update() persists the callback.
    def fn(d):
        for s in d["sources"]:
            if s["id"] == source_id:
                s.update(allowed)
    return update(demo_id, fn)


# Check whether a known source was explicitly excluded from demo visuals.
# Input: demo metadata and source ID. Output: false only for an explicit exclusion; unknown IDs return true.
# Linked: server/agents/plan.py:run, author.py:run and deck.py:build use it when filtering registered visuals.
def visual_allowed(demo: dict, source_id: str) -> bool:
    for s in demo.get("sources", []):
        if s["id"] == source_id:
            return s.get("use_in_demo", True) is not False
    return True


# Resolve a requested media file and refuse paths outside its demo folder.
# Input: demo ID and relative media path. Output: an absolute safe Path or KeyError.
# Linked: server/app.py:media serves only paths returned through this boundary.
def media_path(demo_id: str, rel: str) -> Path:
    base = demo_dir(demo_id).resolve()
    p = (base / rel).resolve()
    if base not in p.parents:
        raise KeyError("outside demo folder")
    return p


# Create a short repeatable identifier from text; this is not an authentication secret.
# Input: text. Output: the first 16 hexadecimal characters of its SHA-1 digest.
# Linked: server/agents/voice.py uses its own richer audio cache key; this helper is a general store utility.
def digest(text: str) -> str:
    import hashlib
    return hashlib.sha1(text.encode()).hexdigest()[:16]
