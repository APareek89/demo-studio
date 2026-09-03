"""Stage 4 — Voice.  Render narration audio with the configured provider; cache by content hash."""
from __future__ import annotations

import base64
import contextvars
import hashlib
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import httpx

from .. import config, store, usage
from . import translate
from ..llm import gemini, sarvam

GEMINI_VOICES = ["Sulafat", "Aoede", "Leda", "Despina", "Kore", "Achernar", "Zephyr"]


VOICE_WORKERS = max(1, int(os.getenv("VOICE_WORKERS", "3")))  # parallel narration lines per stage


def provider_chain(demo: dict) -> list[str]:
    """Primary provider first, then every other configured provider; 'browser' last (= no server audio)."""
    if config.MOCK_LLM:
        return ["sarvam", "gemini"]
    p = demo.get("settings", {}).get("tts_provider") or config.TTS_PROVIDER
    avail = [x for x, ok in (("sarvam", bool(config.SARVAM_API_KEY)), ("gemini", bool(config.GEMINI_API_KEY)), ("gcloud", bool(config.GCLOUD_TTS_API_KEY))) if ok]
    chain = ([p] if p in avail else []) + [x for x in avail if x != p]
    return chain or ["browser"]


def provider_for(demo: dict) -> str:
    return provider_chain(demo)[0]


GCLOUD_LANG = {"hinglish": "hi-IN"}


def voice_name_for(demo: dict, provider: str) -> str:
    st = demo.get("settings", {})
    lang = st.get("language", "en-IN") or "en-IN"
    if provider == "sarvam":
        v = st.get("sarvam_speaker", "")
        return v if v in sarvam.SPEAKERS else "priya"
    v = st.get("voice_name", "")
    if provider == "gemini":
        return v if v in GEMINI_VOICES else config.GEMINI_TTS_VOICE  # Gemini voices are language-agnostic
    if provider == "gcloud":
        lang = GCLOUD_LANG.get(lang, lang)
        if v.startswith(lang + "-"):
            return v
        return f"{lang}-Chirp3-HD-Aoede"
    return v


def _style(demo_id: str) -> str:
    plan = store.read_json(demo_id, "plan.json") or {}
    v = plan.get("voice", {})
    if not v:
        return "Speak as a warm, welcoming product guide, natural conversational pace, Indian English:"
    demo = store.load(demo_id)
    lang = demo.get("settings", {}).get("language", "en-IN")
    lang_note = "" if lang in ("", "en-IN") else f" The text is in {lang}; pronounce it natively."
    return f"Speak as {v.get('persona_description','a warm product guide')} Tone: {v.get('tone','warm and direct')}. Natural conversational pace, no rush.{lang_note}"


def _gcloud(text: str, voice: str) -> tuple[bytes, str]:
    body = {"input": {"text": text}, "voice": {"languageCode": "-".join(voice.split("-")[:2]) if voice.count("-") >= 2 else "en-IN", "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0}}
    with httpx.Client(timeout=60) as c:
        r = c.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": config.GCLOUD_TTS_API_KEY}, json=body)
        if r.status_code != 200 and "Neural2" not in voice and "Wavenet" not in voice:
            body["voice"]["name"] = body["voice"]["languageCode"] + "-Wavenet-A"
            r = c.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": config.GCLOUD_TTS_API_KEY}, json=body)
        r.raise_for_status()
        return base64.b64decode(r.json()["audioContent"]), "mp3"


# Circuit breaker: a provider that answers "no credits" / "unauthorized" is skipped for a while instead of
# being retried on every line (it failed 10× in a row on 2026-09-03 when Sarvam ran out of credits).
_TRIPPED: dict[str, tuple[float, str]] = {}
_TRIP_SECONDS = 600
_TRIP_MARKERS = ("402", "insufficient_quota", "no credits", "quota", "401", "403", "invalid api key", "unauthorized")


def _tripped(provider: str) -> bool:
    t = _TRIPPED.get(provider)
    if not t:
        return False
    if time.time() > t[0]:
        _TRIPPED.pop(provider, None)
        return False
    return True


def _maybe_trip(provider: str, err: Exception) -> None:
    msg = str(err).lower()
    if any(m in msg for m in _TRIP_MARKERS):
        _TRIPPED[provider] = (time.time() + _TRIP_SECONDS, str(err)[:160])


def tripped_providers() -> dict[str, str]:
    return {k: v[1] for k, v in _TRIPPED.items() if _tripped(k)}


def render_line(demo_id: str, text: str, *, demo: dict | None = None, lang: str | None = None) -> str | None:
    """Returns a media-relative path like 'audio/<hash>.wav', or None when only the browser voice is available.
    Tries the provider chain in order (Sarvam → Gemini → Cloud TTS); a failure on one falls through to the next."""
    demo = demo or store.load(demo_id)
    if not text.strip():
        return None
    chain = provider_chain(demo)
    if chain == ["browser"]:
        return None
    lang = lang or demo.get("settings", {}).get("language", "en-IN")
    last_err: Exception | None = None
    for provider in chain:
        if _tripped(provider):
            last_err = RuntimeError(f"{provider} skipped: {_TRIPPED[provider][1]}")
            continue
        voice = voice_name_for(demo, provider)
        key = hashlib.sha1(f"{provider}|{voice}|{lang}|{text.strip()}".encode()).hexdigest()[:20]
        for ext in ("wav", "mp3"):
            p = store.path(demo_id, "audio", f"{key}.{ext}")
            if p.exists():
                return f"audio/{key}.{ext}"
        try:
            if provider == "sarvam":
                data, ext = sarvam.tts(text, voice, lang)
            elif provider == "gemini":
                data, ext = gemini.tts(text, voice, _style(demo_id))
            else:
                data, ext = _gcloud(text, voice)
        except Exception as e:
            last_err = e
            _maybe_trip(provider, e)
            if provider != "sarvam":  # sarvam traces its own failures; gemini / gcloud failures were invisible before
                usage.trace(f"{provider}-tts", provider, latency_ms=0, user=text, error=str(e)[:300], chars=len(text))
            continue
        p = store.path(demo_id, "audio", f"{key}.{ext}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"audio/{key}.{ext}"
    raise RuntimeError(f"all voice providers failed: {str(last_err)[:160]}")


def render_script(demo_id: str, emit) -> dict:
    """Voice the main script, then translate + voice every extra language from settings.languages."""
    demo = store.load(demo_id)
    script = _render_one(demo_id, emit, demo, "script.json", None)
    extra = [l for l in (demo.get("settings", {}).get("languages") or []) if l and l != demo.get("settings", {}).get("language", "en-IN")]
    for lang in extra:
        try:
            translate.translate(demo_id, lang, emit)
            _render_one(demo_id, emit, demo, translate.script_path(lang), lang)
        except Exception as e:
            emit(f"{lang}: skipped ({str(e)[:120]}).")
    return script


def _render_one(demo_id: str, emit, demo: dict, path: str, lang: str | None) -> dict:
    script = store.read_json(demo_id, path)
    if not script:
        raise RuntimeError("No script to voice")
    provider = provider_for(demo)
    chain = provider_chain(demo)
    if provider == "browser":
        emit("No TTS key configured — the player will use the browser voice.")
        script["voice_provider"] = "browser"
        store.write_json(demo_id, path, script)
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
    emit(f"Recording narration with {provider}" + (f" in {lang}" if lang else "") + (f" (fallbacks: {', '.join(chain[1:])})" if len(chain) > 1 else "") + f" — {total} lines…")
    # Lines render in parallel (VOICE_WORKERS, default 4); contextvars are copied per task so usage/trace rows keep the demo id.
    lock = threading.Lock()
    stop = threading.Event()

    def work(item):
        obj, key = item
        if stop.is_set():
            return (obj, key, None, "skipped")
        text = obj["text"] if key == "audio" else obj["checkin"]
        try:
            return (obj, key, render_line(demo_id, text, demo=demo, lang=lang), None)
        except Exception as e:
            return (obj, key, None, str(e)[:160])

    with ThreadPoolExecutor(max_workers=VOICE_WORKERS) as pool:
        futures = [pool.submit(contextvars.copy_context().run, work, item) for item in todo]
        for fut in as_completed(futures):
            obj, key, rel, err = fut.result()
            with lock:
                if err == "skipped":
                    obj[key] = None
                    continue
                obj[key] = rel
                if err:
                    failures += 1
                    if failures == 1:
                        emit(f"Voice provider error: {err} — continuing; missing lines fall back to the browser voice.")
                    if failures >= 4 and not stop.is_set():
                        stop.set()
                        emit("Too many voice errors — stopping narration rendering; the player will use the browser voice for the rest.")
                done += 1
                if done % 8 == 0:
                    emit(f"Recorded {done}/{total} lines…")
                    store.write_json(demo_id, path, script)
    # Second pass, one at a time: lines that failed under parallel load (rate limits) usually succeed alone.
    retry = [(obj, key) for obj, key in todo if obj.get(key) is None]
    if retry and not stop.is_set():
        emit(f"Re-recording {len(retry)} line(s) that failed the first time…")
        recovered = 0
        for obj, key in retry:
            text = obj["text"] if key == "audio" else obj["checkin"]
            try:
                obj[key] = render_line(demo_id, text, demo=demo, lang=lang)
                recovered += 1
                time.sleep(0.5)
            except Exception as e:
                obj[key] = None
                emit(f"Still no audio for one line ({str(e)[:100]}) — the player will use the browser voice for it.")
        failures = max(0, failures - recovered)
    for k, text in intake.items():
        try:
            script.setdefault("intake_audio", {})[k] = render_line(demo_id, text, demo=demo, lang=lang) if failures < 4 else None
        except Exception:
            script.setdefault("intake_audio", {})[k] = None
    if tripped_providers():
        for prov, why in tripped_providers().items():
            emit(f"{prov} is unavailable ({why[:90]}) — lines used the next provider in the chain. Top up / fix the key, then rebuild to re-record.")
        used = next((c for c in chain if not _tripped(c)), "browser")
        provider = used if used != "browser" else provider
    script["voice_provider"] = provider
    script["voice_name"] = voice_name_for(demo, provider)
    script["voice_failures"] = failures
    store.write_json(demo_id, path, script)
    store.log(demo_id, "voice", {"provider": provider, "lines": total, "failures": failures, "language": lang})
    emit("Narration ready." if not failures else f"Narration ready with {failures} line(s) on browser voice.")
    return script


def sample(demo_id: str, text: str) -> str | None:
    return render_line(demo_id, text)
