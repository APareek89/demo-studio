"""Optional Demo Visual workflow: source views/video → TRELLIS.2 → approved reusable asset."""
from __future__ import annotations

import mimetypes
import re
import shutil
import threading
import time
from pathlib import Path

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field

from . import cloud, config, events, media, runlog, store, usage
from .llm import gemini, runware

STATE = "visual/state.json"
VEHICLE_ANGLES = [
    ("front", "Front", True, "Straight on, entire product visible"),
    ("front_three_quarter", "Front ¾", True, "Best hero view; show front and one side"),
    ("side", "Side", True, "Full side profile, level camera"),
    ("rear_three_quarter", "Rear ¾", True, "Show rear and one side"),
    ("rear", "Rear", True, "Straight rear view, entire product visible"),
    ("top", "Top", False, "Optional overhead view"),
    ("interior", "Interior / detail", False, "Optional cabin or signature detail"),
]
GENERIC_ANGLES = [
    ("front", "Front", True, "Straight on, entire product visible"),
    ("front_three_quarter", "Front ¾", True, "Best hero view; show front and one side"),
    ("side", "Side", True, "Full side profile"),
    ("rear_three_quarter", "Rear ¾", True, "Show rear and one side"),
    ("rear", "Rear", True, "Straight rear view"),
    ("top", "Top", False, "Optional overhead view"),
    ("detail", "Detail", False, "Optional signature feature"),
]
_locks: dict[str, threading.Lock] = {}
_cancels: dict[str, threading.Event] = {}
_guard = threading.Lock()


class AnglePick(BaseModel):
    angle: str
    frame_index: int = Field(ge=1)
    timestamp: float = Field(ge=0)
    confidence: float = Field(ge=0, le=1)


class AngleSelection(BaseModel):
    picks: list[AnglePick]
    missing_angles: list[str]
    primary_angle: str


def _category(demo: dict) -> str:
    text = " ".join([demo.get("product", {}).get("category", ""), demo.get("product", {}).get("name", ""), demo.get("name", "")]).lower()
    return "vehicle" if re.search(r"\b(car|vehicle|scooter|motorcycle|bike|auto|ev|sedan|suv|iqube)\b", text) else "object"


def schema_for(demo: dict) -> list[dict]:
    rows = VEHICLE_ANGLES if _category(demo) == "vehicle" else GENERIC_ANGLES
    return [{"key": key, "label": label, "required": required, "guidance": guidance} for key, label, required, guidance in rows]


def _base_state(demo_id: str) -> dict:
    demo = store.load(demo_id)
    return {"category": _category(demo), "mode": "images", "status": "empty", "angles": {}, "video": None,
            "attempts": [], "active_attempt": None, "approved_attempt": None, "progress": 0,
            "message": "Add product views or a turntable video", "error": "", "updated_at": time.time()}


def _read(demo_id: str) -> dict:
    state = store.read_json(demo_id, STATE)
    if not state:
        state = _base_state(demo_id)
        store.write_json(demo_id, STATE, state)
    state.setdefault("angles", {})
    state.setdefault("attempts", [])
    return state


def _write(demo_id: str, state: dict) -> None:
    state["updated_at"] = time.time()
    store.write_json(demo_id, STATE, state)


def _url(demo_id: str, rel: str | None) -> str | None:
    return f"/media/{demo_id}/{rel}" if rel else None


def public_state(demo_id: str) -> dict:
    state = _read(demo_id)
    lock = _locks.get(demo_id)
    if state.get("status") == "generating" and (lock is None or not lock.locked()):
        state.update({"status": "error", "progress": 0, "message": "The local worker stopped before completion",
                      "error": "Generation was interrupted by a server restart. Retry the build; the saved Runware task id remains in version history."})
        for attempt in state.get("attempts", []):
            if attempt.get("number") == state.get("active_attempt") and attempt.get("status") == "running":
                attempt.update({"status": "error", "error": state["error"], "completed_at": time.time()})
        _write(demo_id, state)
    out = {**state, "schema": schema_for(store.load(demo_id)), "runware_ready": bool(config.RUNWARE_API_KEY or config.MOCK_LLM), "model": config.RUNWARE_MODEL}
    out["angles"] = {key: {**value, "url": _url(demo_id, value.get("path"))} for key, value in state.get("angles", {}).items()}
    if state.get("video"):
        out["video"] = {**state["video"], "url": _url(demo_id, state["video"].get("path"))}
    out["attempts"] = [{**a, "glb_url": _url(demo_id, a.get("glb")), "preview_url": _url(demo_id, a.get("preview"))} for a in state.get("attempts", [])]
    return out


def _safe_ext(filename: str, fallback: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if re.fullmatch(r"\.[a-z0-9]{2,5}", ext) else fallback


def add_image(demo_id: str, angle: str, filename: str, data: bytes) -> dict:
    state = _read(demo_id)
    if state.get("status") == "generating":
        raise ValueError("Skip or finish the current 3D build before replacing inputs")
    allowed = {x["key"] for x in schema_for(store.load(demo_id))}
    if angle not in allowed:
        raise ValueError("unknown product angle")
    if not data:
        raise ValueError("image is empty")
    if len(data) > 30 * 1024 * 1024:
        raise ValueError("image is larger than 30 MB")
    ext = _safe_ext(filename, ".jpg")
    rel = f"visual/inputs/{angle}{ext}"
    target = store.path(demo_id, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    try:
        media._codecs()
        with Image.open(target) as im:
            im.verify()
        with Image.open(target) as im:
            width, height = im.size
    except Exception:
        target.unlink(missing_ok=True)
        raise ValueError("file is not a readable image")
    old = state.get("angles", {}).get(angle, {}).get("path")
    if old and old != rel:
        store.path(demo_id, old).unlink(missing_ok=True)
    label = next(x["label"] for x in schema_for(store.load(demo_id)) if x["key"] == angle)
    state["mode"] = "images"
    state["status"] = "collecting"
    state["error"] = ""
    state["angles"][angle] = {"angle": angle, "label": label, "path": rel, "name": Path(filename).name,
                               "size": len(data), "width": width, "height": height, "origin": "real", "generated": False}
    _write(demo_id, state)
    runlog.event(demo_id, f"Demo Visual · {label} image uploaded", f"`{Path(filename).name}` · {width}×{height} · {len(data) / 1e6:.1f} MB · real source")
    cloud.sync_demo_async(demo_id)
    return public_state(demo_id)


def remove_image(demo_id: str, angle: str) -> dict:
    state = _read(demo_id)
    if state.get("status") == "generating":
        raise ValueError("Skip or finish the current 3D build before replacing inputs")
    item = state.get("angles", {}).pop(angle, None)
    if item and item.get("path"):
        store.path(demo_id, item["path"]).unlink(missing_ok=True)
        cloud.delete_file(demo_id, item["path"])
    state["status"] = "collecting" if state.get("angles") else "empty"
    _write(demo_id, state)
    runlog.event(demo_id, f"Demo Visual · {angle} image removed")
    return public_state(demo_id)


def add_video(demo_id: str, filename: str, data: bytes) -> dict:
    state = _read(demo_id)
    if state.get("status") == "generating":
        raise ValueError("Skip or finish the current 3D build before replacing inputs")
    if not data:
        raise ValueError("video is empty")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValueError(f"video is larger than {config.MAX_UPLOAD_MB} MB")
    ext = _safe_ext(filename, ".mp4")
    if ext not in (".mp4", ".mov", ".webm", ".m4v"):
        raise ValueError("use MP4, MOV, M4V or WebM video")
    rel = f"visual/inputs/turntable{ext}"
    target = store.path(demo_id, rel)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    old = (state.get("video") or {}).get("path")
    if old and old != rel:
        store.path(demo_id, old).unlink(missing_ok=True)
    state.update({"mode": "video", "status": "collecting", "video": {"path": rel, "name": Path(filename).name, "size": len(data)}, "error": ""})
    _write(demo_id, state)
    runlog.event(demo_id, "Demo Visual · turntable video uploaded", f"`{Path(filename).name}` · {len(data) / 1e6:.1f} MB")
    cloud.sync_demo_async(demo_id)
    return public_state(demo_id)


def set_mode(demo_id: str, mode: str) -> dict:
    if mode not in ("images", "video"):
        raise ValueError("mode must be images or video")
    state = _read(demo_id)
    if state.get("status") == "generating":
        raise ValueError("Wait for the current build or skip it before switching input modes")
    state["mode"] = mode
    _write(demo_id, state)
    return public_state(demo_id)


def _set_progress(demo_id: str, pct: int, message: str) -> None:
    state = _read(demo_id)
    state["progress"], state["message"] = int(pct), message
    _write(demo_id, state)
    events.publish(demo_id, "progress", phase="visual", percent=int(pct), message=message)


def _required(demo_id: str) -> list[str]:
    return [x["key"] for x in schema_for(store.load(demo_id)) if x["required"]]


def _mock_generated(source: Path, target: Path, angle: str) -> None:
    with Image.open(source) as im:
        im = im.convert("RGB")
        if max(im.size) > 1280:
            im.thumbnail((1280, 1280))
        draw = ImageDraw.Draw(im)
        draw.rounded_rectangle((18, 18, 230, 58), 10, fill=(20, 35, 58))
        draw.text((30, 30), f"MOCK · {angle.replace('_', ' ')}", fill="white")
        target.parent.mkdir(parents=True, exist_ok=True)
        im.save(target, "JPEG", quality=88)


def _select_video_angles(demo_id: str, state: dict) -> None:
    video = store.path(demo_id, state["video"]["path"])
    frames = media.extract_candidate_frames(video, store.path(demo_id, "visual/frames/candidates"))
    if not frames:
        raise RuntimeError("No readable product frames were found in the video")
    runlog.event(demo_id, "Demo Visual · candidate frames extracted", f"{len(frames)} frames sampled every 2 seconds from `{state['video']['name']}`")
    required = _required(demo_id)
    if config.MOCK_LLM:
        picks = [AnglePick(angle=angle, frame_index=min(i + 1, len(frames)), timestamp=frames[min(i, len(frames) - 1)]["timestamp"], confidence=.9)
                 for i, angle in enumerate(required[:min(len(required), len(frames))])]
        selection = AngleSelection(picks=picks, missing_angles=required[len(picks):], primary_angle="front_three_quarter" if "front_three_quarter" in [p.angle for p in picks] else picks[0].angle)
    else:
        parts = [gemini.bytes_part(f["path"]) for f in frames]
        labels = ", ".join(required)
        prompt = (f"These {len(frames)} images are ordered frames from one product turntable video. Select the sharpest frame for each visible required angle: {labels}. "
                  "frame_index is 1-based and must identify the supplied image. Never invent a visible angle; list it in missing_angles instead. "
                  "Pick front_three_quarter as primary when it is clear; otherwise choose the strongest real product frame. Return distinct frames where possible.")
        selection = gemini.structured(prompt, parts, AngleSelection)
    valid: dict[str, AnglePick] = {}
    for pick in selection.picks:
        if pick.angle in required and 1 <= pick.frame_index <= len(frames):
            valid[pick.angle] = pick
    if not valid:
        raise RuntimeError("The video did not contain a clear usable product view")
    state["angles"] = {}
    schema = {x["key"]: x for x in schema_for(store.load(demo_id))}
    for angle, pick in valid.items():
        source = frames[pick.frame_index - 1]["path"]
        rel = f"visual/frames/{angle}.jpg"
        shutil.copy2(source, store.path(demo_id, rel))
        state["angles"][angle] = {"angle": angle, "label": schema[angle]["label"], "path": rel,
                                  "name": f"{state['video']['name']} @ {pick.timestamp:.1f}s", "size": store.path(demo_id, rel).stat().st_size,
                                  "origin": "real", "generated": False, "timestamp": pick.timestamp, "confidence": pick.confidence}
    state["primary_angle"] = selection.primary_angle if selection.primary_angle in valid else ("front_three_quarter" if "front_three_quarter" in valid else next(iter(valid)))
    missing = [angle for angle in required if angle not in valid]
    runlog.event(demo_id, "Demo Visual · Gemini angle selection", f"Real angles: {', '.join(valid)}. Missing: {', '.join(missing) or 'none'}. Primary: {state['primary_angle']}.")
    primary = store.path(demo_id, state["angles"][state["primary_angle"]]["path"])
    for i, angle in enumerate(missing):
        _set_progress(demo_id, 18 + int((i + 1) / max(1, len(missing)) * 22), f"Creating missing {schema[angle]['label']} view")
        rel = f"visual/generated/{angle}.jpg"
        target = store.path(demo_id, rel)
        try:
            if config.MOCK_LLM:
                _mock_generated(primary, target, angle)
            else:
                reference_paths = [store.path(demo_id, item["path"]) for item in state["angles"].values() if item["origin"] == "real"][:3]
                prompt = (f"Create the {schema[angle]['label']} view of this exact same product for multi-view 3D preparation. "
                          "Preserve identity, shape, proportions, colour, trim, logos and every visible detail. Clean neutral studio background, full object, no text, no new design elements.")
                result = gemini.generate_image([gemini.bytes_part(p) for p in reference_paths], prompt)
                if not result:
                    raise RuntimeError("Gemini returned no image")
                raw, _mime = result
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
            state["angles"][angle] = {"angle": angle, "label": schema[angle]["label"], "path": rel,
                                      "name": f"AI-created {schema[angle]['label']}", "size": target.stat().st_size,
                                      "origin": "generated", "generated": True}
            runlog.event(demo_id, f"Demo Visual · missing {schema[angle]['label']} created", "Gemini-generated and labelled; a real video frame remains the TRELLIS.2 input.")
        except Exception as exc:
            runlog.event(demo_id, f"Demo Visual · missing {schema[angle]['label']} not created", str(exc)[:300])
            state.setdefault("missing_angles", []).append(angle)
    _write(demo_id, state)


def _worker(demo_id: str, attempt_no: int, cancel: threading.Event) -> None:
    usage.current_demo.set(demo_id)
    usage.current_stage.set("visual")
    started = time.time()
    try:
        state = _read(demo_id)
        if state.get("mode") == "video":
            _set_progress(demo_id, 5, "Extracting product views from video")
            _select_video_angles(demo_id, state)
            state = _read(demo_id)
        required = _required(demo_id)
        if state.get("mode") == "images" and any(angle not in state.get("angles", {}) for angle in required):
            missing = [angle for angle in required if angle not in state.get("angles", {})]
            raise RuntimeError("Add the required views first: " + ", ".join(missing))
        real = [key for key, value in state.get("angles", {}).items() if value.get("origin") == "real"]
        if not real:
            raise RuntimeError("At least one real product image is required")
        primary = "front_three_quarter" if "front_three_quarter" in real else "front" if "front" in real else real[0]
        state["primary_angle"] = primary
        _write(demo_id, state)
        def submitted(task_uuid: str) -> None:
            current = _read(demo_id)
            for attempt in current.get("attempts", []):
                if attempt.get("number") == attempt_no:
                    attempt["task_uuid"] = task_uuid
            _write(demo_id, current)
        result = runware.generate(store.path(demo_id, state["angles"][primary]["path"]),
                                  progress=lambda pct, msg: _set_progress(demo_id, max(45, pct), msg), cancelled=cancel.is_set,
                                  submitted=submitted)
        if cancel.is_set():
            raise RuntimeError("3D generation skipped")
        rel = f"visual/attempts/{attempt_no:03d}/model.glb"
        target = store.path(demo_id, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(result["bytes"])
        state = _read(demo_id)
        previous = state.get("attempts", [])[-2] if len(state.get("attempts", [])) > 1 else None
        angles = [{"angle": key, "origin": value.get("origin"), "path": value.get("path")} for key, value in state.get("angles", {}).items()]
        change = "First 3D build" if not previous else f"Regenerated from {primary}; previous attempt preserved"
        for attempt in state["attempts"]:
            if attempt["number"] == attempt_no:
                attempt.update({"status": "review", "glb": rel, "preview": state["angles"][primary]["path"], "primary_angle": primary,
                                "angles": angles, "real_count": sum(1 for a in angles if a["origin"] == "real"),
                                "generated_count": sum(1 for a in angles if a["origin"] == "generated"), "task_uuid": result["task_uuid"],
                                "cost_usd": result.get("cost", 0), "size": len(result["bytes"]), "change": change, "completed_at": time.time()})
        state.update({"status": "review", "active_attempt": attempt_no, "progress": 100, "message": "Rotate and inspect the asset before approval", "error": ""})
        _write(demo_id, state)
        runlog.event(demo_id, f"Demo Visual · TRELLIS.2 attempt {attempt_no} ready", f"GLB {len(result['bytes']) / 1e6:.1f} MB · primary real view `{primary}` · cost ${result.get('cost', 0):.4f} · task `{result['task_uuid']}`")
        events.publish(demo_id, "phase_done", phase="visual", message="3D asset ready for review")
        cloud.sync_demo_async(demo_id)
    except Exception as exc:
        state = _read(demo_id)
        skipped = cancel.is_set() or "skipped" in str(exc).lower()
        for attempt in state.get("attempts", []):
            if attempt["number"] == attempt_no:
                attempt.update({"status": "skipped" if skipped else "error", "error": str(exc)[:500], "completed_at": time.time()})
        state.update({"status": "skipped" if skipped else "error", "progress": 0, "message": "Visual step skipped" if skipped else "3D build needs attention", "error": "" if skipped else str(exc)[:500]})
        _write(demo_id, state)
        runlog.event(demo_id, f"Demo Visual · attempt {attempt_no} {'skipped' if skipped else 'failed'}", f"{str(exc)[:500]} · elapsed {time.time() - started:.1f}s")
        events.publish(demo_id, "phase_error", phase="visual", message=str(exc)[:300], skipped=skipped)


def start(demo_id: str) -> dict:
    with _guard:
        lock = _locks.setdefault(demo_id, threading.Lock())
    if not lock.acquire(blocking=False):
        raise RuntimeError("A 3D build is already running for this demo")
    state = _read(demo_id)
    if state.get("mode") == "video" and not state.get("video"):
        lock.release()
        raise ValueError("Add a turntable video first")
    if state.get("mode") == "images":
        missing = [angle for angle in _required(demo_id) if angle not in state.get("angles", {})]
        if missing:
            lock.release()
            raise ValueError("Add the required views first: " + ", ".join(missing))
    if not config.MOCK_LLM and not config.RUNWARE_API_KEY:
        lock.release()
        raise ValueError("RUNWARE_API_KEY is missing in .env")
    attempt_no = max([a.get("number", 0) for a in state.get("attempts", [])] or [0]) + 1
    state["attempts"].append({"number": attempt_no, "status": "running", "started_at": time.time(), "model": config.RUNWARE_MODEL})
    state.update({"status": "generating", "active_attempt": attempt_no, "progress": 1, "message": "Preparing the 3D build", "error": ""})
    _write(demo_id, state)
    cancel = threading.Event()
    _cancels[demo_id] = cancel
    runlog.event(demo_id, f"Demo Visual · attempt {attempt_no} started", f"Mode: {state.get('mode')} · model: `{config.RUNWARE_MODEL}`")

    def run():
        try:
            _worker(demo_id, attempt_no, cancel)
        finally:
            lock.release()
    threading.Thread(target=run, daemon=True, name=f"visual-{demo_id}-{attempt_no}").start()
    return public_state(demo_id)


def skip(demo_id: str) -> dict:
    cancel = _cancels.get(demo_id)
    if cancel:
        cancel.set()
    state = _read(demo_id)
    submitted = any(a.get("number") == state.get("active_attempt") and a.get("task_uuid") for a in state.get("attempts", []))
    state.update({"status": "skipped", "message": "Visual step skipped — you can return any time", "progress": 0, "error": "",
                  "remote_may_continue": bool(submitted)})
    _write(demo_id, state)
    note = " The submitted Runware job may still finish and bill because the provider has no documented cancel operation." if submitted and not config.MOCK_LLM else ""
    runlog.event(demo_id, "Demo Visual · skipped", "The demo content flow remains available; saved inputs and prior attempts are preserved." + note)
    return public_state(demo_id)


def _asset_summary(demo_id: str, state: dict, attempt: dict) -> dict:
    angles = [{**value, "url": _url(demo_id, value.get("path"))} for value in state.get("angles", {}).values()]
    return {"demo_id": demo_id, "attempt": attempt["number"], "model": config.RUNWARE_MODEL, "glb": attempt["glb"],
            "glb_url": _url(demo_id, attempt["glb"]), "preview": attempt.get("preview"), "preview_url": _url(demo_id, attempt.get("preview")),
            "primary_angle": attempt.get("primary_angle"), "source_mode": state.get("mode"), "real_count": attempt.get("real_count", 0),
            "generated_count": attempt.get("generated_count", 0), "angles": angles, "size": attempt.get("size", 0),
            "cost_usd": attempt.get("cost_usd", 0), "created_at": time.time(), "source_demo": None}


def approve(demo_id: str) -> dict:
    state = _read(demo_id)
    number = state.get("active_attempt")
    attempt = next((a for a in state.get("attempts", []) if a.get("number") == number and a.get("status") == "review"), None)
    if not attempt:
        raise ValueError("No review-ready 3D attempt to approve")
    attempt["status"] = "approved"
    attempt["approved_at"] = time.time()
    state.update({"status": "approved", "approved_attempt": number, "message": "3D asset approved for this demo", "error": ""})
    _write(demo_id, state)
    asset = _asset_summary(demo_id, state, attempt)
    demo = store.update(demo_id, lambda d: d.__setitem__("visual_asset", asset))
    from .agents import bundle
    bundle.attach_visual_asset(demo_id)
    runlog.event(demo_id, f"Demo Visual · attempt {number} approved", "This GLB is now the main player visual; all angle images remain supporting thumbnails with real/generated labels.")
    cloud.put_event(demo_id, "visual_approved", {"attempt": number, "model": config.RUNWARE_MODEL, "real_count": asset["real_count"], "generated_count": asset["generated_count"]})
    cloud.sync_demo_async(demo_id)
    return {"demo": demo, "visual": public_state(demo_id), "asset": asset}


def assets() -> list[dict]:
    out = []
    seen = set()
    for item in store.list_demos():
        asset = item.get("visual_asset")
        if not asset:
            continue
        seen.add(item["id"])
        out.append({**asset, "demo_id": item["id"], "demo_name": item["name"], "product": item.get("product", {})})
    for item in cloud.list_cloud_demos():
        if item.get("demo_id") in seen or not item.get("visual_asset"):
            continue
        demo_id = item["demo_id"]
        asset = item["visual_asset"]
        out.append({**asset, "demo_id": demo_id, "demo_name": item.get("name", demo_id), "product": item.get("product", {}),
                    "glb_url": _url(demo_id, asset.get("glb")), "preview_url": _url(demo_id, asset.get("preview")),
                    "angles": [{**a, "url": _url(demo_id, a.get("path"))} for a in asset.get("angles", [])]})
    return out


def use_in_demo(source_demo_id: str, target_demo_id: str) -> dict:
    source = store.load(source_demo_id)
    target = store.load(target_demo_id)
    asset = source.get("visual_asset")
    if not asset:
        raise ValueError("Source demo has no approved asset")
    root = f"visual/imported/{source_demo_id}"
    copied = {}
    for rel in [asset.get("glb"), asset.get("preview")] + [a.get("path") for a in asset.get("angles", [])]:
        if not rel or rel in copied:
            continue
        src = store.path(source_demo_id, rel)
        if not src.exists() and cloud.enabled():
            cloud.fetch_file(source_demo_id, rel)
        if not src.exists():
            continue
        dest_rel = f"{root}/{Path(rel).name}"
        dest = store.path(target_demo_id, dest_rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        copied[rel] = dest_rel
    if asset.get("glb") not in copied:
        raise RuntimeError("Approved GLB is not available to copy")
    imported = {**asset, "demo_id": target_demo_id, "glb": copied[asset["glb"]], "preview": copied.get(asset.get("preview")),
                "glb_url": _url(target_demo_id, copied[asset["glb"]]), "preview_url": _url(target_demo_id, copied.get(asset.get("preview"))),
                "source_demo": source_demo_id, "created_at": time.time(),
                "angles": [{**a, "path": copied.get(a.get("path"), a.get("path")), "url": _url(target_demo_id, copied.get(a.get("path"), a.get("path")))} for a in asset.get("angles", [])]}
    store.update(target_demo_id, lambda d: d.__setitem__("visual_asset", imported))
    state = _read(target_demo_id)
    state.update({"status": "approved", "message": f"Using asset from {source.get('name')}", "approved_attempt": None})
    _write(target_demo_id, state)
    from .agents import bundle
    bundle.attach_visual_asset(target_demo_id)
    runlog.event(target_demo_id, "Demo Visual · reusable asset attached", f"Copied from `{source_demo_id}` ({source.get('name')}) into `{target.get('name')}`.")
    cloud.sync_demo_async(target_demo_id)
    return store.load(target_demo_id)


def delete_asset(demo_id: str) -> dict:
    demo = store.load(demo_id)
    asset = demo.get("visual_asset")
    if not asset:
        raise ValueError("Demo has no approved asset")
    rel = asset.get("glb")
    if rel:
        store.path(demo_id, rel).unlink(missing_ok=True)
        cloud.delete_file(demo_id, rel)
    store.update(demo_id, lambda d: d.__setitem__("visual_asset", None))
    state = _read(demo_id)
    state.update({"status": "collecting" if state.get("angles") or state.get("video") else "empty", "approved_attempt": None, "message": "Approved asset deleted; inputs remain available"})
    for attempt in state.get("attempts", []):
        if attempt.get("glb") == rel:
            attempt.update({"status": "deleted", "glb": None, "deleted_at": time.time()})
    _write(demo_id, state)
    from .agents import bundle
    bundle.attach_visual_asset(demo_id)
    runlog.event(demo_id, "Demo Visual · approved asset deleted", "The GLB was removed locally and from S3 when connected. Source views remain available for regeneration.")
    cloud.sync_demo_async(demo_id)
    return {"ok": True}
