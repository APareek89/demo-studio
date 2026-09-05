"""Runware TRELLIS.2 image-to-3D client.

The API is asynchronous: submit one conditioning image, then poll the same endpoint with
getResponse. Only safe metadata is written to traces; the image data URI and API key never are.
"""
from __future__ import annotations

import base64
import io
import json
import time
import uuid
from pathlib import Path
from typing import Callable

import httpx
from PIL import Image

from .. import config, usage
from . import mock

API = "https://api.runware.ai/v1"
TRANSIENT = {429, 500, 502, 503, 504}


def _image_data_uri(path: Path) -> tuple[str, int]:
    with Image.open(path) as image:
        image = image.convert("RGB")
        if max(image.size) > 1536:
            image.thumbnail((1536, 1536), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        image.save(buf, "JPEG", quality=90, optimize=True)
    raw = buf.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode(), len(raw)


def _post(client: httpx.Client, body: list[dict]) -> dict:
    last: Exception | None = None
    for wait in (0, 2, 5, 12):
        if wait:
            time.sleep(wait)
        try:
            response = client.post(API, json=body)
            if response.status_code in TRANSIENT:
                last = RuntimeError(f"Runware temporarily unavailable ({response.status_code})")
                continue
            response.raise_for_status()
            payload = response.json()
            errors = payload.get("errors") or []
            if errors:
                message = "; ".join(str(e.get("message") or e) for e in errors)
                raise RuntimeError("Runware: " + message[:500])
            return payload
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last = exc
    raise RuntimeError(str(last or "Runware request failed"))


def _first_data(payload: dict) -> dict:
    data = payload.get("data") or []
    return data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})


def _find_glb_url(obj) -> str | None:
    if isinstance(obj, str) and (obj.lower().split("?")[0].endswith(".glb") or obj.startswith("http")):
        return obj
    if isinstance(obj, dict):
        for key in ("outputURL", "modelURL", "url", "outputUrl", "modelUrl"):
            val = obj.get(key)
            if isinstance(val, str) and val.startswith("http"):
                return val
        for value in obj.values():
            found = _find_glb_url(value)
            if found:
                return found
    if isinstance(obj, list):
        for value in obj:
            found = _find_glb_url(value)
            if found:
                return found
    return None


def generate(image_path: Path, *, progress: Callable[[int, str], None] = lambda _p, _m: None,
             cancelled: Callable[[], bool] = lambda: False) -> dict:
    """Return GLB bytes and job metadata. Stop local polling when skipped."""
    if config.MOCK_LLM:
        for pct, message in ((12, "Submitting to TRELLIS.2"), (42, "Building geometry"), (76, "Texturing the asset"), (100, "3D asset ready")):
            if cancelled():
                raise RuntimeError("3D generation skipped")
            time.sleep(0.08)
            progress(pct, message)
        return {"bytes": mock.cube_glb(), "task_uuid": str(uuid.uuid4()), "cost": 0.0, "response": {"status": "success", "mock": True}}
    if not config.RUNWARE_API_KEY:
        raise RuntimeError("RUNWARE_API_KEY is missing in .env")

    data_uri, image_bytes = _image_data_uri(image_path)
    task_uuid = str(uuid.uuid4())
    request = {"taskType": "3dInference", "taskUUID": task_uuid, "model": config.RUNWARE_MODEL,
               "inputs": {"image": data_uri}, "deliveryMethod": "async", "outputFormat": "GLB",
               "outputType": "URL", "includeCost": True,
               "settings": {"resolution": config.RUNWARE_RESOLUTION}}
    safe_request = {**request, "inputs": {"image": f"[data URI redacted; {image_bytes} bytes]"}}
    headers = {"Authorization": f"Bearer {config.RUNWARE_API_KEY}", "Content-Type": "application/json"}
    started = time.time()
    final: dict = {}
    try:
        with httpx.Client(headers=headers, timeout=httpx.Timeout(90, connect=20)) as client:
            progress(8, "Submitting to TRELLIS.2")
            submitted = _post(client, [request])
            first = _first_data(submitted)
            if first.get("status") in ("success", "completed") and _find_glb_url(first):
                final = first
            else:
                deadline = time.time() + 20 * 60
                delay = 1.5
                while time.time() < deadline:
                    if cancelled():
                        raise RuntimeError("3D generation skipped; remote processing may finish separately")
                    time.sleep(delay)
                    polled = _post(client, [{"taskType": "getResponse", "taskUUID": task_uuid}])
                    row = _first_data(polled)
                    status = str(row.get("status") or "processing").lower()
                    pct = int(float(row.get("progress") or 0))
                    progress(max(10, min(96, pct or 20)), "TRELLIS.2 is building the 3D asset")
                    if status in ("success", "completed") or _find_glb_url(row):
                        final = row
                        break
                    if status in ("error", "failed", "cancelled"):
                        raise RuntimeError("Runware generation failed: " + str(row.get("message") or row)[:400])
                    delay = min(10, delay * 1.6)
                if not final:
                    raise RuntimeError("Runware generation timed out after 20 minutes")
            url = _find_glb_url(final)
            if not url:
                raise RuntimeError("Runware completed but returned no GLB URL")
            result = client.get(url, timeout=180)
            result.raise_for_status()
            glb = result.content
            if len(glb) < 20 or glb[:4] != b"glTF":
                raise RuntimeError("Runware returned an invalid GLB file")
        cost = float(final.get("cost") or final.get("totalCost") or 0)
        elapsed = time.time() - started
        usage.record("runware-3d", config.RUNWARE_MODEL, seconds=elapsed, usd=cost or None)
        usage.trace("runware-3d", config.RUNWARE_MODEL, latency_ms=elapsed * 1000,
                    user=json.dumps(safe_request), response=json.dumps({"taskUUID": task_uuid, "status": final.get("status"), "cost": cost, "bytes": len(glb)}), usd=cost or None)
        progress(100, "3D asset ready")
        return {"bytes": glb, "task_uuid": task_uuid, "cost": cost, "response": final}
    except Exception as exc:
        usage.trace("runware-3d", config.RUNWARE_MODEL, latency_ms=(time.time() - started) * 1000,
                    user=json.dumps(safe_request), error=str(exc)[:400])
        raise
