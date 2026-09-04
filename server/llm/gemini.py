"""Gemini — the model that looks (video, images) and speaks (TTS)."""
from __future__ import annotations

import io
import json
import mimetypes
import struct
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .. import config, usage
from . import mock

_client = None


def client():
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        from google import genai
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


def _types():
    from google.genai import types
    return types


def _retry(fn, tries: int = 4, waits=(4, 10, 25)):
    """Gemini returns 503 'high demand' and 429 transiently; the SDK's own retry is short. Back off and try again."""
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            s = str(e)
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
        config=t.GenerateContentConfig(response_mime_type="application/json", response_schema=schema, temperature=temperature),
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
    """Returns (audio_bytes, extension). Gemini returns raw PCM; we wrap it as WAV."""
    if config.MOCK_LLM:
        return mock.silent_wav(max(0.6, min(4.0, len(text) / 40))), "wav"
    t = _types()
    prompt = (f"{style.strip()} " if style else "") + text
    t0 = time.time()
    resp = _retry(lambda: client().models.generate_content(
        model=config.GEMINI_TTS_MODEL,
        contents=prompt,
        config=t.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=t.SpeechConfig(voice_config=t.VoiceConfig(prebuilt_voice_config=t.PrebuiltVoiceConfig(voice_name=voice_name))),
        ),
    ))
    try:
        um = resp.usage_metadata
        usage.record("gemini-tts", config.GEMINI_TTS_MODEL, input_tokens=um.prompt_token_count or 0, output_tokens=um.candidates_token_count or 0, chars=len(text))
        usage.trace("gemini-tts", config.GEMINI_TTS_MODEL, latency_ms=(time.time() - t0) * 1000, user=text, response="[audio]", input_tokens=um.prompt_token_count or 0, output_tokens=um.candidates_token_count or 0, chars=len(text))
    except Exception:
        pass
    part = None
    for cand in resp.candidates or []:
        for p in (cand.content.parts if cand.content else []) or []:
            if getattr(p, "inline_data", None) and p.inline_data.data:
                part = p
                break
        if part:
            break
    if part is None:
        raise RuntimeError("Gemini TTS returned no audio")
    data = part.inline_data.data
    if isinstance(data, str):
        import base64
        data = base64.b64decode(data)
    mime = part.inline_data.mime_type or "audio/L16;codec=pcm;rate=24000"
    if "pcm" in mime or "L16" in mime:
        rate = 24000
        for chunk in mime.split(";"):
            if chunk.strip().startswith("rate="):
                rate = int(chunk.strip()[5:])
        return _pcm_to_wav(data, rate), "wav"
    if "mp3" in mime or "mpeg" in mime:
        return data, "mp3"
    return data, "wav"


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
    import time as _time
    model = model or config.GEMINI_IMAGE_MODEL
    t = _types()
    t0 = _time.time()
    try:
        resp = _retry(lambda: client().models.generate_content(model=model, contents=[*parts, prompt], config=t.GenerateContentConfig(response_modalities=["IMAGE"])), tries=2, waits=(5,))
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
