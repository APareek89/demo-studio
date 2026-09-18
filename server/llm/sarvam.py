"""Sarvam AI — Indian-language speech. Bulbul (TTS) and Saarika (STT).
Primary for India; Gemini / Google Cloud / browser are the fallbacks."""
from __future__ import annotations

import base64
import math
import threading
import time
from datetime import timezone
from email.utils import parsedate_to_datetime

import httpx

from .. import config, usage
from . import mock

BASE = "https://api.sarvam.ai"
SPEAKERS = {"aditya": "Aditya", "ritu": "Ritu", "priya": "Priya", "neha": "Neha", "rahul": "Rahul", "pooja": "Pooja", "rohan": "Rohan", "simran": "Simran", "kavya": "Kavya", "amit": "Amit", "dev": "Dev", "ishita": "Ishita", "shreya": "Shreya", "ratan": "Ratan", "varun": "Varun", "manan": "Manan", "sumit": "Sumit", "roopa": "Roopa", "kabir": "Kabir", "aayan": "Aayan", "shubh": "Shubh", "ashutosh": "Ashutosh", "advait": "Advait", "anand": "Anand", "tanya": "Tanya", "tarun": "Tarun", "sunny": "Sunny", "mani": "Mani", "gokul": "Gokul", "vijay": "Vijay", "shruti": "Shruti", "suhani": "Suhani", "mohit": "Mohit", "kavitha": "Kavitha", "rehan": "Rehan", "soham": "Soham", "rupali": "Rupali"}  # bulbul:v3 speakers, probed from the API 2026-09-03
LANG = {"hinglish": "hi-IN", "en": "en-IN", "hi": "hi-IN"}
SUPPORTED = {"en-IN", "hi-IN", "bn-IN", "gu-IN", "kn-IN", "ml-IN", "mr-IN", "od-IN", "pa-IN", "ta-IN", "te-IN"}

# Bulbul v3 Starter is documented at 30 REST requests/minute, shared by the
# account. Pace this process conservatively; a 429 still owns the cooldown.
# https://docs.sarvam.ai/api/getting-started/ratelimits
_TTS_INTERVAL = 2.1
_TTS_WAIT_BUDGET = 30.0
_TTS_LOCK = threading.Lock()
_TTS_NEXT_REQUEST = 0.0


class RateLimitError(RuntimeError):
    def __init__(self, retry_after: float, detail: str = "rate limit window"):
        self.retry_after = max(0.0, retry_after)
        super().__init__(f"sarvam tts 429: {detail}; retry after {math.ceil(self.retry_after)}s")


def _retry_after(value: str | None, fallback: float) -> float:
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            date = parsedate_to_datetime(value or "")
            seconds = date.replace(tzinfo=date.tzinfo or timezone.utc).timestamp() - time.time()
        except (ValueError, TypeError, OverflowError):
            return fallback
    return max(0.0, seconds) if math.isfinite(seconds) else fallback


def _tts_slot(deadline: float) -> None:
    global _TTS_NEXT_REQUEST
    while True:
        with _TTS_LOCK:
            now = time.monotonic()
            wait = max(0.0, _TTS_NEXT_REQUEST - now)
            if wait <= 0:
                _TTS_NEXT_REQUEST = now + _TTS_INTERVAL
                return
        if wait > max(0.0, deadline - now):
            raise RateLimitError(wait, "pacing/cooldown exceeds this call's wait budget")
        time.sleep(wait)


def _tts_request(client, body: dict, deadline: float):
    global _TTS_NEXT_REQUEST
    for attempt in range(3):
        _tts_slot(deadline)
        response = client.post(f"{BASE}/text-to-speech", headers={**_headers(), "content-type": "application/json"}, json=body)
        if response.status_code != 429:
            return response  # account, policy and other failures are not rate-limit retries
        delay = _retry_after(response.headers.get("Retry-After"), 2.0 * (2 ** attempt))
        with _TTS_LOCK:
            _TTS_NEXT_REQUEST = max(_TTS_NEXT_REQUEST, time.monotonic() + delay)
            remaining = max(0.0, _TTS_NEXT_REQUEST - time.monotonic())
        if attempt == 2 or remaining > max(0.0, deadline - time.monotonic()):
            raise RateLimitError(remaining, response.text[:160])
    raise AssertionError("unreachable")


def lang_code(code: str | None) -> str:
    c = LANG.get(code or "en-IN", code or "en-IN")
    return c if c in SUPPORTED else "en-IN"


def _headers() -> dict:
    if not config.SARVAM_API_KEY:
        raise RuntimeError("SARVAM_API_KEY is not set in .env")
    return {"api-subscription-key": config.SARVAM_API_KEY}


def _chunks(text: str, limit: int = 450) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    out, cur = [], ""
    for sent in text.replace("? ", "?|").replace("! ", "!|").replace(". ", ".|").split("|"):
        if len(cur) + len(sent) + 1 > limit and cur:
            out.append(cur.strip())
            cur = sent
        else:
            cur = (cur + " " + sent).strip()
    if cur:
        out.append(cur.strip())
    return out


def _wav_concat(parts: list[bytes]) -> bytes:
    if len(parts) == 1:
        return parts[0]
    import io
    import wave
    frames, params = [], None
    for p in parts:
        with wave.open(io.BytesIO(p)) as w:
            params = params or w.getparams()
            frames.append(w.readframes(w.getnframes()))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        for f in frames:
            w.writeframes(f)
    return buf.getvalue()


def tts(text: str, speaker: str = "priya", language: str = "en-IN", pace: float = 1.0) -> tuple[bytes, str]:
    """Bulbul v3. Returns (wav_bytes, 'wav')."""
    if config.MOCK_LLM:
        return mock.silent_wav(max(0.6, min(4.0, len(text) / 40))), "wav"
    speaker = speaker if speaker in SPEAKERS else "priya"
    parts = []
    t0 = time.time()
    deadline = time.monotonic() + _TTS_WAIT_BUDGET
    with httpx.Client(timeout=60) as c:
        for chunk in _chunks(text):
            body = {"text": chunk, "target_language_code": lang_code(language), "speaker": speaker, "model": config.SARVAM_TTS_MODEL,
                    "speech_sample_rate": 22050, "enable_preprocessing": True}
            if pace and abs(pace - 1.0) > 1e-3:
                body["pace"] = pace  # bulbul:v3 rejects pitch/loudness; pace only when changed
            try:
                r = _tts_request(c, body, deadline)
            except RateLimitError as exc:
                usage.trace("sarvam-tts", config.SARVAM_TTS_MODEL, latency_ms=(time.time() - t0) * 1000, user=f"[{speaker} · {lang_code(language)}] " + text, error=str(exc), chars=len(text))
                raise
            if r.status_code == 400 and "inputs" in r.text:  # older bulbul:v1 request shape
                body.pop("text")
                body["inputs"] = [chunk]
                r = _tts_request(c, body, deadline)
            if r.status_code != 200:
                usage.trace("sarvam-tts", config.SARVAM_TTS_MODEL, latency_ms=(time.time() - t0) * 1000, user=f"[{speaker} · {lang_code(language)}] " + text, error=f"{r.status_code}: {r.text[:300]}", chars=len(text))
                raise RuntimeError(f"sarvam tts {r.status_code}: {r.text[:160]}")
            audios = r.json().get("audios") or []
            if not audios:
                raise RuntimeError("sarvam tts: no audio returned")
            parts.append(base64.b64decode(audios[0]))
    usage.record("sarvam-tts", config.SARVAM_TTS_MODEL, chars=len(text))
    usage.trace("sarvam-tts", config.SARVAM_TTS_MODEL, latency_ms=(time.time() - t0) * 1000, user=f"[{speaker} · {lang_code(language)}] " + text, response="[audio]", chars=len(text))
    return _wav_concat(parts), "wav"


def stt(audio: bytes, filename: str = "audio.wav", language: str = "en-IN", mime: str = "audio/wav") -> str:
    """Saarika. Returns the transcript ('' when nothing was heard)."""
    if config.MOCK_LLM:
        return "(mock transcript)"
    code = lang_code(language)
    t0 = time.time()
    with httpx.Client(timeout=60) as c:
        r = c.post(f"{BASE}/speech-to-text", headers=_headers(), files={"file": (filename, audio, mime)},
                   data={"model": config.SARVAM_STT_MODEL, "language_code": code if language not in ("", None) else "unknown"})
        if r.status_code != 200:
            raise RuntimeError(f"sarvam stt {r.status_code}: {r.text[:160]}")
        usage.record("sarvam-stt", config.SARVAM_STT_MODEL, seconds=max(0.5, len(audio) / 32000))
        txt = (r.json().get("transcript") or "").strip()
        usage.trace("sarvam-stt", config.SARVAM_STT_MODEL, latency_ms=(time.time() - t0) * 1000, user=f"[{code} audio {len(audio)//1024} KB]", response=txt)
        return txt


def describe_error(e: Exception) -> str:
    s = str(e)
    if "401" in s or "403" in s or "subscription" in s.lower():
        return "Sarvam API key was rejected — check SARVAM_API_KEY in .env"
    if "429" in s:
        return "Sarvam rate limit hit"
    return s[:300]
