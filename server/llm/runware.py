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
from urllib.parse import urlparse

import httpx
from PIL import Image

from .. import config, usage
from . import mock

API = "https://api.runware.ai/v1"
TRANSIENT = {429, 500, 502, 503, 504}
TRANSIENT_CODES = {"timeoutProvider", "providerRateLimitExceeded", "rateLimit"}


class RunwareAPIError(RuntimeError):
    """A provider error safe to show in the studio and traces."""

    def __init__(self, message: str, *, status_code: int | None = None, codes: tuple[str, ...] = ()):
        super().__init__(message)
        self.status_code = status_code
        self.codes = codes


def _error_message(errors: list, status_code: int | None = None) -> tuple[str, tuple[str, ...]]:
    parts: list[str] = []
    codes: list[str] = []
    for error in errors:
        if not isinstance(error, dict):
            parts.append(str(error)[:300])
            continue
        code = str(error.get("code") or "providerError")
        codes.append(code)
        if code == "insufficientCredits":
            message = "Insufficient credits. Top up the Runware wallet, then try again."
        elif code == "invalidApiKey":
            message = "The Runware API key is invalid or has been revoked."
        else:
            message = str(error.get("message") or "The provider rejected the request").strip()
        parameter = error.get("parameter")
        parts.append(f"{code}: {message}" + (f" (parameter: {parameter})" if parameter else ""))
    if not parts:
        parts.append(f"HTTP {status_code or 'request'} failed")
    return "Runware: " + "; ".join(parts)[:700], tuple(codes)


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
            try:
                payload = response.json()
            except (ValueError, json.JSONDecodeError):
                payload = {}
            errors = payload.get("errors") or [] if isinstance(payload, dict) else []
            message, codes = _error_message(errors, response.status_code)
            if response.status_code in TRANSIENT:
                last = RunwareAPIError(message, status_code=response.status_code, codes=codes)
                continue
            if errors:
                error = RunwareAPIError(message, status_code=response.status_code, codes=codes)
                if any(code in TRANSIENT_CODES for code in codes):
                    last = error
                    continue
                raise error
            if not response.is_success:
                detail = response.text.strip().replace("\n", " ")[:300]
                raise RunwareAPIError(
                    f"Runware: HTTP {response.status_code} failed" + (f" — {detail}" if detail else ""),
                    status_code=response.status_code,
                )
            return payload
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last = exc
    if last:
        raise last
    raise RuntimeError("Runware request failed")


def _task_data(payload: dict, task_uuid: str) -> dict:
    data = payload.get("data") or []
    if isinstance(data, dict):
        return data
    rows = [row for row in data if isinstance(row, dict)] if isinstance(data, list) else []
    matching = [row for row in rows if not row.get("taskUUID") or row.get("taskUUID") == task_uuid]
    rows = matching or rows
    for row in reversed(rows):
        if _find_glb_url(row) or str(row.get("status") or "").lower() in {"success", "completed", "error", "failed", "cancelled"}:
            return row
    return max(rows, key=lambda row: _progress_value(row.get("progress")), default={})


def _progress_value(value) -> int:
    try:
        return max(0, min(100, int(float(value or 0))))
    except (TypeError, ValueError):
        return 0


def _safe_https_url(value) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and bool(parsed.hostname) else None


def _find_glb_url(obj) -> str | None:
    if isinstance(obj, str) and obj.lower().split("?")[0].endswith(".glb"):
        return _safe_https_url(obj)
    if isinstance(obj, dict):
        for key in ("outputURL", "modelURL", "model3DURL", "meshURL", "outputUrl", "modelUrl", "model3DUrl", "meshUrl"):
            val = _safe_https_url(obj.get(key))
            if val:
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


def _cost_value(row: dict) -> float | None:
    raw = row.get("cost") if row.get("cost") is not None else row.get("totalCost")
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _row_error(row: dict) -> str:
    nested = row.get("error") if isinstance(row.get("error"), dict) else {}
    code = nested.get("code") or row.get("code") or "providerError"
    message = nested.get("message") or row.get("message") or "The provider reported an error"
    return f"Runware generation failed ({code}): {str(message)[:400]}"


def preflight() -> dict | None:
    """Check auth/balance before video analysis or a paid 3D submission; never retain account details."""
    if config.MOCK_LLM:
        return {"available": True, "mock": True}
    if not config.RUNWARE_API_KEY:
        raise RunwareAPIError("Runware: The API key is missing from .env", codes=("missingApiKey",))
    headers = {"Authorization": f"Bearer {config.RUNWARE_API_KEY}", "Content-Type": "application/json"}
    task_uuid = str(uuid.uuid4())
    try:
        with httpx.Client(headers=headers, timeout=httpx.Timeout(20, connect=10)) as client:
            payload = _post(client, [{"taskType": "accountManagement", "taskUUID": task_uuid, "operation": "getDetails"}])
    except RunwareAPIError as exc:
        if set(exc.codes) & {"invalidApiKey", "insufficientCredits"}:
            raise
        return None  # Account telemetry must not become a new availability dependency.
    except Exception:
        return None
    row = _task_data(payload, task_uuid)
    balance = row.get("balance")
    if balance is None:
        return None
    currency = "USD"
    try:
        if isinstance(balance, dict):
            available = max(0.0, float(balance.get("amount") or 0)) + max(0.0, float(balance.get("freeBalance") or 0))
            currency = str(balance.get("currency") or currency)
        else:
            # The live REST API currently returns a scalar even though the docs show an object.
            available = float(balance)
    except (TypeError, ValueError):
        return None
    if available <= 0:
        raise RunwareAPIError(
            "Runware: insufficientCredits: Insufficient credits. Top up the Runware wallet, then try again.",
            status_code=402,
            codes=("insufficientCredits",),
        )
    return {"available": True, "currency": currency}


def generate(image_path: Path, *, progress: Callable[[int, str], None] = lambda _p, _m: None,
             cancelled: Callable[[], bool] = lambda: False, submitted: Callable[[str], None] = lambda _task: None) -> dict:
    """Return GLB bytes and job metadata. Stop local polling when skipped."""
    if config.MOCK_LLM:
        task_uuid = str(uuid.uuid4())
        submitted(task_uuid)
        for pct, message in ((12, "Submitting to TRELLIS.2"), (42, "Building geometry"), (76, "Texturing the asset"), (100, "3D asset ready")):
            if cancelled():
                raise RuntimeError("3D generation skipped")
            time.sleep(0.08)
            progress(pct, message)
        return {"bytes": mock.cube_glb(), "task_uuid": task_uuid, "cost": 0.0, "response": {"status": "success", "mock": True}}
    if not config.RUNWARE_API_KEY:
        raise RuntimeError("RUNWARE_API_KEY is missing in .env")

    data_uri, image_bytes = _image_data_uri(image_path)
    task_uuid = str(uuid.uuid4())
    submitted(task_uuid)
    request = {"taskType": "3dInference", "taskUUID": task_uuid, "model": config.RUNWARE_MODEL,
               "inputs": {"image": data_uri}, "deliveryMethod": "async", "outputFormat": "GLB",
               "outputType": "URL", "includeCost": True,
               "settings": {"resolution": config.RUNWARE_RESOLUTION}}
    safe_request = {**request, "inputs": {"image": f"[data URI redacted; {image_bytes} bytes]"}}
    headers = {"Authorization": f"Bearer {config.RUNWARE_API_KEY}", "Content-Type": "application/json"}
    started = time.time()
    final: dict = {}
    provider_cost: float | None = None
    accepted = False
    try:
        with httpx.Client(headers=headers, timeout=httpx.Timeout(90, connect=20)) as client:
            progress(8, "Submitting to TRELLIS.2")
            submission = _post(client, [request])
            accepted = True
            first = _task_data(submission, task_uuid)
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
                    row = _task_data(polled, task_uuid)
                    status = str(row.get("status") or "processing").lower()
                    pct = _progress_value(row.get("progress"))
                    progress(max(10, min(96, pct or 20)), "TRELLIS.2 is building the 3D asset")
                    if status in ("success", "completed") or _find_glb_url(row):
                        final = row
                        break
                    if status in ("error", "failed", "cancelled"):
                        raise RuntimeError(_row_error(row))
                    delay = min(10, delay * 1.6)
                if not final:
                    raise RuntimeError("Runware generation timed out after 20 minutes")
            url = _find_glb_url(final)
            if not url:
                raise RuntimeError("Runware completed but returned no GLB URL")
            provider_cost = _cost_value(final)
            chunks = bytearray()
            # Never forward the Runware bearer token to a provider/CDN download URL.
            with httpx.stream("GET", url, timeout=180, follow_redirects=True) as result:
                result.raise_for_status()
                try:
                    declared = int(result.headers.get("content-length") or 0)
                except ValueError:
                    declared = 0
                if declared > 250 * 1024 * 1024:
                    raise RuntimeError("Runware GLB is larger than the 250 MB safety limit")
                for chunk in result.iter_bytes():
                    chunks.extend(chunk)
                    if len(chunks) > 250 * 1024 * 1024:
                        raise RuntimeError("Runware GLB exceeded the 250 MB safety limit")
            glb = bytes(chunks)
            if len(glb) < 20 or glb[:4] != b"glTF":
                raise RuntimeError("Runware returned an invalid GLB file")
        elapsed = time.time() - started
        usage.record("runware-3d", config.RUNWARE_MODEL, seconds=elapsed, usd=provider_cost)
        usage.trace("runware-3d", config.RUNWARE_MODEL, latency_ms=elapsed * 1000,
                    user=json.dumps(safe_request), response=json.dumps({"taskUUID": task_uuid, "status": final.get("status"), "cost": provider_cost, "bytes": len(glb)}), usd=provider_cost)
        progress(100, "3D asset ready")
        return {"bytes": glb, "task_uuid": task_uuid, "cost": provider_cost or 0.0, "response": final}
    except Exception as exc:
        if accepted:
            usage.record("runware-3d", config.RUNWARE_MODEL, seconds=time.time() - started, usd=provider_cost)
        usage.trace("runware-3d", config.RUNWARE_MODEL, latency_ms=(time.time() - started) * 1000,
                    user=json.dumps(safe_request), error=str(exc)[:400], usd=provider_cost if accepted else 0.0)
        raise
