"""Bounded Runware image generation with PixelBin prediction fallback.

Only product cleanup and guide mascots use this module. Text/speech routing is
unchanged. Mock mode never opens a connection. Provider errors never expose raw
bodies, prompts, image bytes, signed URLs or credentials.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import math
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from PIL import Image

from .. import config, usage

RUNWARE_URL = "https://api.runware.ai/v1"
PIXELBIN_URL = "https://api.pixelbin.io/service/platform/transformation/v1.0/predictions"
MAX_IMAGE_BYTES = 12 * 1024 * 1024
MAX_JSON_BYTES = 18 * 1024 * 1024
MAX_PIXELS = 20_000_000
PROVIDER_SECONDS = 100
LOG = logging.getLogger("uvicorn.error")


class MediaError(RuntimeError):
    """Fixed, safe error category for the caller's local-art fallback."""


class SafetyRefusal(MediaError):
    """A safety refusal is terminal and must not trigger another provider."""


class RequestRejected(MediaError):
    """An unclassified invalid request must not be resubmitted elsewhere."""


def _safety_rejected(value, depth=0):
    """Read only bounded machine codes; never expose a provider's raw message."""
    if depth > 4: return False
    if isinstance(value, list): return any(_safety_rejected(v, depth+1) for v in value[:20])
    if not isinstance(value, dict): return False
    if value.get("NSFWContent") is True: return True
    codes = {"contentpolicyviolation", "safetyviolation", "contentfilter", "contentfiltered",
             "contentblocked", "safetyblocked", "unsafeprompt", "unsafeimage", "nsfwcontent"}
    for key in ("code", "type", "reason", "reasonCode"):
        code = value.get(key)
        if isinstance(code, str) and len(code) < 100 and re.sub(r"[^a-z]", "", code.lower()) in codes:
            return True
    return any(_safety_rejected(value[key], depth+1) for key in ("errors", "error", "data") if key in value)


@dataclass(frozen=True)
class ImageResult:
    png: bytes
    provider: str
    model: str
    usd: float | None = None
    credits: float | None = None
    mocked: bool = False

    def metadata(self):
        result = {"provider": self.provider, "model": self.model, "mock": self.mocked}
        if self.usd is not None: result["cost_usd"] = self.usd
        if self.credits is not None: result["credits"] = self.credits
        return result


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    return float(value) if math.isfinite(value) and value >= 0 else None


def _png(raw: bytes) -> bytes:
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise MediaError("image_size_rejected")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.width * image.height > MAX_PIXELS or image.width < 1 or image.height < 1:
                raise MediaError("image_dimensions_rejected")
            if getattr(image, "is_animated", False):
                raise MediaError("animated_output_rejected")
            output = io.BytesIO()
            image.convert("RGBA").save(output, format="PNG")
            value = output.getvalue()
            if len(value) > MAX_IMAGE_BYTES:
                raise MediaError("image_size_rejected")
            return value
    except MediaError:
        raise
    except Exception:
        raise MediaError("invalid_image_output") from None


def _input(path: Path | None):
    if path is None: return None
    if path.stat().st_size > MAX_IMAGE_BYTES: raise MediaError("reference_image_too_large")
    return _png(path.read_bytes())


def _read(client, method, url, *, deadline, limit, **kwargs):
    remaining = deadline - time.monotonic()
    if remaining <= 0: raise MediaError("provider_deadline_exceeded")
    with client.stream(method, url, timeout=min(remaining, 45), **kwargs) as response:
        # Redirects are never followed, including authenticated prediction URLs.
        if not 200 <= response.status_code < 300:
            raw = bytearray()
            for chunk in response.iter_bytes(chunk_size=65536):
                if len(raw)+len(chunk) > 65536 or time.monotonic() >= deadline: break
                raw.extend(chunk)
            try: error = json.loads(raw)
            except (ValueError, UnicodeError, RecursionError): error = None
            if _safety_rejected(error): raise SafetyRefusal("image_safety_refusal")
            # Provider error schemas can vary. Unknown request rejections fail
            # closed too, rather than potentially bypassing a content refusal.
            if response.status_code in {400, 422}: raise RequestRejected("provider_request_rejected")
            raise MediaError("provider_http_failure")
        total = 0; chunks = []
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > limit: raise MediaError("provider_response_too_large")
            if time.monotonic() >= deadline: raise MediaError("provider_deadline_exceeded")
            chunks.append(chunk)
        return b"".join(chunks)


def _json(client, method, url, *, deadline, **kwargs):
    try:
        value = json.loads(_read(client, method, url, deadline=deadline, limit=MAX_JSON_BYTES, **kwargs))
    except (ValueError, UnicodeError):
        raise MediaError("invalid_provider_json") from None
    if not isinstance(value, dict): raise MediaError("invalid_provider_json")
    return value


def _runware(client, prompt, reference, aspect):
    if not config.RUNWARE_API_KEY: raise MediaError("provider_not_configured")
    identifier = str(uuid.uuid4())
    task = {"taskType": "imageInference", "taskUUID": identifier,
            "model": config.RUNWARE_IMAGE_MODEL, "positivePrompt": prompt,
            "outputType": "base64Data", "outputFormat": "PNG", "numberResults": 1,
            "includeCost": True, "safety": {"checkContent": True}}
    task.update({"width": 1200, "height": 896} if aspect == "4:3" else {"width": 1024, "height": 1024})
    if reference: task["inputs"] = {"referenceImages": ["data:image/png;base64," + base64.b64encode(reference).decode()]}
    body = _json(client, "POST", RUNWARE_URL, deadline=time.monotonic()+PROVIDER_SECONDS,
                 headers={"Authorization": "Bearer " + config.RUNWARE_API_KEY}, json=[task])
    if body.get("errors") or body.get("error"):
        if _safety_rejected(body): raise SafetyRefusal("image_safety_refusal")
        raise MediaError("provider_task_failed")
    values = body.get("data")
    if not isinstance(values, list) or len(values) != 1 or not isinstance(values[0], dict):
        raise MediaError("unexpected_provider_result")
    value = values[0]
    if value.get("taskUUID") != identifier: raise MediaError("provider_task_mismatch")
    if value.get("NSFWContent") is True: raise SafetyRefusal("image_safety_refusal")
    encoded = value.get("imageBase64Data")
    if not isinstance(encoded, str) or len(encoded) > MAX_JSON_BYTES: raise MediaError("missing_image_output")
    try: raw = base64.b64decode(encoded, validate=True)
    except ValueError: raise MediaError("invalid_image_output") from None
    return ImageResult(_png(raw), "runware", config.RUNWARE_IMAGE_MODEL, usd=_number(value.get("cost")))


def _pixelbin(client, prompt, reference, aspect):
    if not config.PIXELBIN_API_TOKEN: raise MediaError("provider_not_configured")
    # Official @pixelbin/admin 4.2.0 uses base64(raw apiSecret), not the raw token.
    bearer = base64.b64encode(config.PIXELBIN_API_TOKEN.encode()).decode()
    headers = {"Authorization": "Bearer " + bearer}
    parts = [("input.prompt", (None, prompt)), ("input.aspect_ratio", (None, aspect))]
    if reference: parts.append(("input.images", ("reference.png", reference, "image/png")))
    deadline = time.monotonic()+PROVIDER_SECONDS
    value = _json(client, "POST", PIXELBIN_URL+"/nanoBanana/generate", deadline=deadline, headers=headers, files=parts)
    identifier = value.get("_id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", identifier):
        raise MediaError("invalid_prediction_id")
    for _ in range(40):
        if _safety_rejected(value): raise SafetyRefusal("image_safety_refusal")
        status = value.get("status")
        if status == "SUCCESS": break
        if status == "FAILURE": raise MediaError("provider_task_failed")
        if status not in {"PENDING", "PROCESSING", "RUNNING", "STARTING"}: raise MediaError("unexpected_prediction_status")
        if time.monotonic()+2 >= deadline: raise MediaError("provider_deadline_exceeded")
        time.sleep(2)
        value = _json(client, "GET", PIXELBIN_URL+"/"+identifier, deadline=deadline, headers=headers)
        if value.get("_id") not in {None, identifier}: raise MediaError("provider_task_mismatch")
    else: raise MediaError("provider_deadline_exceeded")
    outputs = value.get("output")
    if not isinstance(outputs, list) or len(outputs) != 1 or not isinstance(outputs[0], str):
        raise MediaError("missing_image_output")
    parsed = urlsplit(outputs[0])
    if (parsed.scheme != "https" or parsed.hostname != "delivery.pixelbin.io" or parsed.port not in {None, 443}
            or parsed.username or parsed.password or parsed.fragment or not parsed.path.startswith("/predictions/outputs/")):
        raise MediaError("untrusted_image_output_url")
    # Delivery receives no API Authorization header, and redirects stay disabled.
    raw = _read(client, "GET", outputs[0], deadline=deadline, limit=MAX_IMAGE_BYTES)
    return ImageResult(_png(raw), "pixelbin", "nanoBanana_generate", credits=_number(value.get("consumedCredits")))


def generate(prompt: str, *, reference: Path | None = None, aspect="1:1") -> ImageResult:
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 6000 or aspect not in {"1:1", "4:3"}:
        raise MediaError("invalid_image_request")
    image = _input(reference)
    if config.MOCK_LLM:
        if image is None:
            output = io.BytesIO();Image.new("RGB", (32, 32), "#e6e6e6").save(output, format="PNG");image=output.getvalue()
        return ImageResult(image, "mock", "local-fixture", usd=0, mocked=True)
    with httpx.Client(follow_redirects=False, trust_env=False) as client:
        for provider in config.MEDIA_PROVIDER_ORDER:
            try:
                result = {"runware": _runware, "pixelbin": _pixelbin}[provider](client, prompt, image, aspect)
                LOG.info("[media-provider] %s", json.dumps({"provider": provider, "status": "success"}))
                # PixelBin returns credits, not USD; do not invent a conversion.
                if result.usd is not None: usage.record(provider+"-image", result.model, usd=result.usd)
                return result
            except SafetyRefusal:
                LOG.info("[media-provider] %s", json.dumps({"provider": provider, "status": "refused"}))
                raise
            except RequestRejected:
                LOG.info("[media-provider] %s", json.dumps({"provider": provider, "status": "rejected"}))
                raise
            except Exception as exc:
                reason = str(exc) if isinstance(exc, MediaError) else "provider_transport_failure"
                LOG.info("[media-provider] %s", json.dumps({"provider": provider, "status": "fallback", "reason": reason}))
    raise MediaError("image_providers_unavailable")
