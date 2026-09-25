"""Gemini — the model that looks (video, images) and speaks (TTS)."""
from __future__ import annotations

import io
import json
import mimetypes
import math
import struct
import re
import threading
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .. import config, usage
from . import mock

TRACE_SYS = 20000  # chars of the system prompt kept in a runtime trace row
_client = None
_client_lock = threading.Lock()
_hard_quota_until = 0.0
_hard_quota_reason = ""


def client():
    global _client
    if _client is None:
        # Runtime pitch and QA can arrive on different workers at cold start.
        # Replacing a live Client closes its SDK transport via Client.__del__.
        with _client_lock:
            if _client is None:
                if not config.GEMINI_API_KEY:
                    raise RuntimeError("GEMINI_API_KEY is not set in .env")
                from google import genai
                _client = genai.Client(api_key=config.GEMINI_API_KEY, http_options={"timeout": 90_000})
    return _client


def _types():
    from google.genai import types
    return types


def _quota_cooldown(message: str) -> tuple[int, str]:
    """How long to stop calling Gemini after a quota error, and why. A zero quota (no billing) is worth ten minutes;
    a burst limit ("exceeded your current quota … retry in 12s") is worth exactly what Gemini asks, else 30 s —
    a free-tier key must not lose ten minutes of builds to one busy second."""
    low = message.lower()
    if "limit: 0" in low or "quota_value: 0" in low:
        return 600, "zero quota on this key — enable billing or use another key"
    if "exceeded your current quota" in low or "check your plan and billing" in low:
        m = re.search(r"retry in ([\d.]+)\s*s", low) or re.search(r"retrydelay[^\d]{0,6}([\d.]+)s", low)
        secs = int(float(m.group(1))) + 1 if m else 30
        return secs, f"burst limit — waiting {secs}s"
    return 0, ""


def _is_hard_quota(message: str) -> bool:
    return _quota_cooldown(message)[0] > 0


def _retry(fn, tries: int = 4, waits=(4, 10, 25)):
    """Gemini returns 503 'high demand' and 429 transiently; the SDK's own retry is short. Back off and try again."""
    global _hard_quota_until, _hard_quota_reason
    if time.time() < _hard_quota_until:
        raise RuntimeError(f"Gemini rate limit cooldown: {_hard_quota_reason}")
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            s = str(e)
            # A zero/current-quota response is not a burst limit. Retrying it
            # for every later image, planning and FAQ call turns a clean
            # fallback into minutes of dead time, so remember it briefly.
            secs, why = _quota_cooldown(s)
            if secs:
                _hard_quota_reason = why
                _hard_quota_until = time.time() + secs
                raise
            transient = any(k in s for k in ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "500 INTERNAL", "502", "504", "overloaded", "high demand"))
            last = e
            if not transient or i == tries - 1:
                raise
            time.sleep(waits[min(i, len(waits) - 1)])
    raise last


def upload_file(p: Path, mime: str | None = None):
    """Upload to the Gemini Files API and wait until it is processed (video needs this)."""
    if config.MOCK_LLM:
        return None
    c = client()
    mime = mime or mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    try:
        f = c.files.upload(file=str(p), config={"mime_type": mime})
    except TypeError:  # older SDK signature
        f = c.files.upload(path=str(p), config={"mime_type": mime})
    deadline = time.time() + 600
    while getattr(f.state, "name", str(f.state)) == "PROCESSING" and time.time() < deadline:
        time.sleep(3)
        f = c.files.get(name=f.name)
    state = getattr(f.state, "name", str(f.state))
    if state != "ACTIVE":
        raise RuntimeError(f"Gemini file processing failed: {state}")
    return f


def structured(prompt: str, parts: list[Any], schema: type[BaseModel], *, temperature: float = 0.2) -> Any:
    """generate_content with a JSON schema; returns the validated Pydantic object."""
    if config.MOCK_LLM:
        return mock.fake(schema)
    t = _types()
    contents = [p for p in parts if p is not None] + [prompt]
    t0 = time.time()
    resp = _retry(lambda: client().models.generate_content(
        model=config.GEMINI_MODEL,
        contents=contents,
        config=t.GenerateContentConfig(response_mime_type="application/json", response_json_schema=schema.model_json_schema(), temperature=temperature),
    ))
    text = resp.text or ""
    try:
        um = resp.usage_metadata
        usage.record("gemini", config.GEMINI_MODEL, input_tokens=um.prompt_token_count or 0, output_tokens=um.candidates_token_count or 0)
        usage.trace("gemini", config.GEMINI_MODEL, latency_ms=(time.time() - t0) * 1000, user=prompt + f"\n[{len([p for p in parts if p is not None])} media part(s)]", response=text, input_tokens=um.prompt_token_count or 0, output_tokens=um.candidates_token_count or 0)
    except Exception:
        pass
    try:
        return schema.model_validate_json(text)
    except Exception:
        # tolerate trailing text around the JSON
        s, e = text.find("{"), text.rfind("}")
        return schema.model_validate_json(text[s:e + 1])


def text_structured(system: str, transcript: str, schema: type[BaseModel], *, max_tokens: int = 16000,
                    temperature: float = 0.2, fallback_reason: str = "", timeout_s: float | None = None,
                    model: str | None = None, tries: int = 2, kind: str = "gemini-fallback",
                    thinking_level: str | None = None) -> Any:
    """Text-only structured call: the fallback when Claude is unavailable, and the primary at runtime."""
    if config.MOCK_LLM:
        return mock.fake(schema)
    t = _types()
    model = model or config.GEMINI_TEXT_MODEL
    # Preserve the existing diagnostic transcript, but give the SDK the real
    # system role instead of flattening policy into user/source material.
    prompt = f"SYSTEM INSTRUCTIONS:\n{system}\n\nCONVERSATION / TASK:\n{transcript}"
    # The legacy response_schema converter rejects dictionary properties locally.
    # Send JSON Schema intact; validate the response with the same Pydantic model.
    cfg: dict = dict(system_instruction=system, response_mime_type="application/json", response_json_schema=schema.model_json_schema(), temperature=temperature,
                     max_output_tokens=min(max(256, max_tokens), 32768))
    if thinking_level is not None and model == "gemini-3.8-flash":
        # Only this exact model's support is verified; unknown overrides retain their defaults.
        cfg["thinking_config"] = t.ThinkingConfig(thinking_level=thinking_level)
    http_options = {}
    if timeout_s:
        # genai otherwise copies the local HTTP timeout to X-Server-Timeout.
        # Gemini rejects that server deadline below 10s. Keep our short local
        # attempt budget (and the graph's whole-turn deadline) independent.
        http_options.update(timeout=max(1, int(timeout_s * 1000)),
                            headers={"X-Server-Timeout": str(max(10, math.ceil(timeout_s)))})
    if tries == 1:
        # A bounded runtime attempt must not trigger the SDK's five retries.
        http_options["retry_options"] = t.HttpRetryOptions(attempts=1)
    if http_options:
        cfg["http_options"] = t.HttpOptions(**http_options)
    t0 = time.time()
    try:
        resp = _retry(lambda: client().models.generate_content(model=model, contents=transcript, config=t.GenerateContentConfig(**cfg)),
                      tries=tries, waits=(2,))
    except Exception as exc:
        usage.trace(kind,model,latency_ms=(time.time()-t0)*1000,system=system[:TRACE_SYS],user=prompt,error=usage.redact(str(exc))[:500])
        raise
    text = resp.text or ""
    try:
        um = resp.usage_metadata
        inp = um.prompt_token_count or 0
        out = (um.candidates_token_count or 0) + (getattr(um, "thoughts_token_count", 0) or 0)
        usage.record(kind, model, input_tokens=inp, output_tokens=out)
        usage.trace(kind, model, latency_ms=(time.time() - t0) * 1000,
                    system=f"Primary unavailable: {fallback_reason}" if fallback_reason else system[:TRACE_SYS],
                    user=prompt, response=text, input_tokens=inp, output_tokens=out)
    except Exception:
        pass
    try:
        return schema.model_validate_json(text)
    except Exception:
        s, e = text.find("{"), text.rfind("}")
        return schema.model_validate_json(text[s:e + 1])


def file_part(uploaded):
    if uploaded is None:
        return None
    t = _types()
    return t.Part.from_uri(file_uri=uploaded.uri, mime_type=uploaded.mime_type)


def bytes_part(p: Path):
    if config.MOCK_LLM:
        return None
    t = _types()
    mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    return t.Part.from_bytes(data=p.read_bytes(), mime_type=mime)


# ---------- text to speech ----------

def _pcm_to_wav(pcm: bytes, rate: int, channels: int = 1, bits: int = 16) -> bytes:
    buf = io.BytesIO()
    datalen = len(pcm)
    buf.write(b"RIFF"); buf.write(struct.pack("<I", 36 + datalen)); buf.write(b"WAVE")
    buf.write(b"fmt "); buf.write(struct.pack("<IHHIIHH", 16, 1, channels, rate, rate * channels * bits // 8, channels * bits // 8, bits))
    buf.write(b"data"); buf.write(struct.pack("<I", datalen)); buf.write(pcm)
    return buf.getvalue()


def tts(text: str, voice_name: str, style: str = "") -> tuple[bytes, str]:
    """Returns (audio_bytes, extension) through Gemini's current Interactions audio contract."""
    if config.MOCK_LLM:
        return mock.silent_wav(max(0.6, min(4.0, len(text) / 40))), "wav"
    prompt = (f"{style.strip()} " if style else "") + text
    t0 = time.time()
    resp = _retry(lambda: client().interactions.create(
        model=config.GEMINI_TTS_MODEL,
        input=prompt,
        response_format={"type": "audio"},
        generation_config={"speech_config": [{"voice": voice_name}]},
    ))
    try:
        um = getattr(resp, "usage", None)
        inp = getattr(um, "input_tokens", 0) or getattr(um, "input_token_count", 0) or 0
        out = getattr(um, "output_tokens", 0) or getattr(um, "output_token_count", 0) or 0
        usage.record("gemini-tts", config.GEMINI_TTS_MODEL, input_tokens=inp, output_tokens=out, chars=len(text))
        usage.trace("gemini-tts", config.GEMINI_TTS_MODEL, latency_ms=(time.time() - t0) * 1000, user=text, response="[audio]", input_tokens=inp, output_tokens=out, chars=len(text))
    except Exception:
        pass
    audio = getattr(resp, "output_audio", None)
    if audio is None or not getattr(audio, "data", None):
        raise RuntimeError("Gemini TTS returned no audio")
    data = audio.data
    if isinstance(data, str):
        import base64
        data = base64.b64decode(data)
    mime = str(getattr(audio, "mime_type", "") or "audio/l16").lower()
    if "wav" in mime:
        return data, "wav"
    if "mp3" in mime or "mpeg" in mime:
        return data, "mp3"
    if "aac" in mime or "m4a" in mime:
        return data, "m4a"
    rate = int(getattr(audio, "sample_rate", 0) or 24000)
    channels = int(getattr(audio, "channels", 0) or 1)
    return _pcm_to_wav(data, rate, channels), "wav"


def describe_error(e: Exception) -> str:
    s = str(e)
    if "API key" in s or "403" in s or "PERMISSION_DENIED" in s:
        return "Gemini API key was rejected — check GEMINI_API_KEY in .env"
    if "429" in s or "RESOURCE_EXHAUSTED" in s or "quota" in s.lower():
        return "Gemini quota/rate limit hit — the free tier is small; wait or enable billing"
    return s[:300]


def generate_image(parts: list, prompt: str, *, model: str | None = None) -> tuple[bytes, str] | None:
    """One image from the Gemini image model (edit when `parts` carries a source image, generate when empty).
    Returns (bytes, mime) or None when the response has no image. Quota/billing errors raise — callers fall back."""
    if config.MOCK_LLM:
        return None  # Optional image generation must never leave the free path.
    import time as _time
    model = model or config.GEMINI_IMAGE_MODEL
    t = _types()
    t0 = _time.time()
    try:
        # Nano Banana 2 Lite supports minimal/high thinking. Minimal is explicit here:
        # this path fills a missing product angle and should optimize for latency/cost,
        # while the human review gate protects fidelity before the Runware spend.
        resp = _retry(lambda: client().models.generate_content(
            model=model,
            contents=[*parts, prompt],
            config=t.GenerateContentConfig(
                response_modalities=["IMAGE"],
                thinking_config=t.ThinkingConfig(thinking_level=t.ThinkingLevel.MINIMAL),
            ),
        ), tries=2, waits=(5,))
    except Exception as e:
        usage.trace("gemini-image", model, latency_ms=(_time.time() - t0) * 1000, user=prompt, error=str(e)[:400])
        raise
    out = None
    mime = "image/png"
    for part in (resp.candidates[0].content.parts if resp.candidates else []):
        data = getattr(getattr(part, "inline_data", None), "data", None)
        if data:
            out, mime = data, part.inline_data.mime_type or mime
    um = getattr(resp, "usage_metadata", None)
    usage.record("gemini-image", model, input_tokens=getattr(um, "prompt_token_count", 0) or 0, output_tokens=getattr(um, "candidates_token_count", 0) or 0)
    usage.trace("gemini-image", model, latency_ms=(_time.time() - t0) * 1000, user=prompt, response=f"[image {len(out)} bytes {mime}]" if out else "[no image]")
    return (out, mime) if out else None
