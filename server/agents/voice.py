"""Stage 4 — Voice.  Render narration audio with the configured provider; cache by content hash."""
from __future__ import annotations

import base64
import hashlib
import time

import httpx

from .. import config, store
from ..llm import gemini

GEMINI_VOICES = ["Sulafat", "Aoede", "Leda", "Despina", "Kore", "Achernar", "Zephyr"]


def provider_for(demo: dict) -> str:
    p = demo.get("settings", {}).get("tts_provider") or config.TTS_PROVIDER
    if config.MOCK_LLM:
        return "gemini"
    if p not in ("gemini", "gcloud", "browser"):  # a typo must not route to the wrong provider
        p = "gemini" if config.GEMINI_API_KEY else ("gcloud" if config.GCLOUD_TTS_API_KEY else "browser")
    if p == "gemini" and not config.GEMINI_API_KEY:
        p = "gcloud" if config.GCLOUD_TTS_API_KEY else "browser"
    if p == "gcloud" and not config.GCLOUD_TTS_API_KEY:
        p = "gemini" if config.GEMINI_API_KEY else "browser"
    return p


def voice_name_for(demo: dict, provider: str) -> str:
    v = demo.get("settings", {}).get("voice_name", "")
    if provider == "gemini":
        return v if v in GEMINI_VOICES else config.GEMINI_TTS_VOICE
    if provider == "gcloud":
        return v if v.startswith("en-") else config.GCLOUD_TTS_VOICE
    return v


def _style(demo_id: str) -> str:
    plan = store.read_json(demo_id, "plan.json") or {}
    v = plan.get("voice", {})
    if not v:
        return "Speak as a warm, welcoming product guide, natural conversational pace, Indian English:"
    return f"Speak as {v.get('persona_description','a warm product guide')} Tone: {v.get('tone','warm and direct')}. Natural conversational pace, no rush:"


def _gcloud(text: str, voice: str) -> tuple[bytes, str]:
    body = {"input": {"text": text}, "voice": {"languageCode": "-".join(voice.split("-")[:2]) if voice.count("-") >= 2 else "en-IN", "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0}}
    with httpx.Client(timeout=60) as c:
        r = c.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": config.GCLOUD_TTS_API_KEY}, json=body)
        if r.status_code != 200 and voice != "en-IN-Neural2-A":
            body["voice"]["name"] = "en-IN-Neural2-A"
            r = c.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": config.GCLOUD_TTS_API_KEY}, json=body)
        r.raise_for_status()
        return base64.b64decode(r.json()["audioContent"]), "mp3"


def render_line(demo_id: str, text: str, *, demo: dict | None = None) -> str | None:
    """Returns a media-relative path like 'audio/<hash>.wav' or None when using the browser voice."""
    demo = demo or store.load(demo_id)
    provider = provider_for(demo)
    if provider == "browser" or not text.strip():
        return None
    voice = voice_name_for(demo, provider)
    key = hashlib.sha1(f"{provider}|{voice}|{text.strip()}".encode()).hexdigest()[:20]
    for ext in ("wav", "mp3"):
        p = store.path(demo_id, "audio", f"{key}.{ext}")
        if p.exists():
            return f"audio/{key}.{ext}"
    if provider == "gemini":
        data, ext = gemini.tts(text, voice, _style(demo_id))
    else:
        data, ext = _gcloud(text, voice)
    p = store.path(demo_id, "audio", f"{key}.{ext}")
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return f"audio/{key}.{ext}"


def render_script(demo_id: str, emit) -> dict:
    demo = store.load(demo_id)
    script = store.read_json(demo_id, "script.json")
    if not script:
        raise RuntimeError("No script to voice")
    provider = provider_for(demo)
    if provider == "browser":
        emit("No TTS key configured — the player will use the browser voice.")
        script["voice_provider"] = "browser"
        store.write_json(demo_id, "script.json", script)
        return script
    todo: list[tuple[dict, str]] = []
    for seg in script["segments"]:
        for ln in seg["lines"]:
            if not ln.get("unverified"):
                todo.append((ln, "audio"))
        for ln in seg.get("deeper", []):
            if not ln.get("unverified"):
                todo.append((ln, "audio"))
        if seg.get("checkin"):
            todo.append((seg, "checkin_audio"))
    for ln in script.get("closing", []):
        todo.append((ln, "audio"))
    intake = {"q1": script.get("intake_q1", ""), "q2": script.get("intake_q2", "")}
    total = len(todo) + 2
    done, failures = 0, 0
    emit(f"Recording narration with {provider} ({total} lines)…")
    for obj, key in todo:
        text = obj["text"] if key == "audio" else obj["checkin"]
        try:
            obj[key] = render_line(demo_id, text, demo=demo)
            time.sleep(0.25)
        except Exception as e:
            failures += 1
            obj[key] = None
            msg = gemini.describe_error(e) if provider == "gemini" else str(e)[:160]
            if failures == 1:
                emit(f"Voice provider error: {msg} — continuing; missing lines fall back to the browser voice.")
            if failures >= 4:
                emit("Too many voice errors — stopping narration rendering; the player will use the browser voice for the rest.")
                break
        done += 1
        if done % 8 == 0:
            emit(f"Recorded {done}/{total} lines…")
            store.write_json(demo_id, "script.json", script)
    for k, text in intake.items():
        try:
            script.setdefault("intake_audio", {})[k] = render_line(demo_id, text, demo=demo) if failures < 4 else None
        except Exception:
            script.setdefault("intake_audio", {})[k] = None
    script["voice_provider"] = provider
    script["voice_name"] = voice_name_for(demo, provider)
    script["voice_failures"] = failures
    store.write_json(demo_id, "script.json", script)
    store.log(demo_id, "voice", {"provider": provider, "lines": total, "failures": failures})
    emit("Narration ready." if not failures else f"Narration ready with {failures} line(s) on browser voice.")
    return script


def sample(demo_id: str, text: str) -> str | None:
    return render_line(demo_id, text)
