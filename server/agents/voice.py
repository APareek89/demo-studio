"""Stage 4 — Voice.  Render narration audio with the configured provider; cache by content hash."""
from __future__ import annotations

import base64
import contextvars
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

import httpx

from .. import config, store, usage
from . import speech_style, translate
from ..llm import gemini, sarvam, mock as speech_mock

GEMINI_VOICES = ["Sulafat", "Aoede", "Leda", "Despina", "Kore", "Achernar", "Zephyr"]


VOICE_WORKERS = max(1, int(os.getenv("VOICE_WORKERS", "3")))  # parallel narration lines per stage


def provider_chain(demo: dict) -> list[str]:
    """Locked demos retain the configured provider; unlocked demos may use configured fallbacks."""
    p = demo.get("settings", {}).get("tts_provider") or config.TTS_PROVIDER
    if demo.get("settings", {}).get("voice_locked"):
        return [p]  # Keep identity even without a key: matching cached audio can still be used.
    if config.MOCK_LLM:
        return ["sarvam", "gemini"]
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


def _gcloud(text: str, voice: str, *, allow_voice_fallback: bool = True, pace: float = 1.0) -> tuple[bytes, str]:
    if config.MOCK_LLM:
        return speech_mock.silent_wav(max(0.6, min(4.0, len(text) / 40))), "wav"
    body = {"input": {"text": text}, "voice": {"languageCode": "-".join(voice.split("-")[:2]) if voice.count("-") >= 2 else "en-IN", "name": voice},
            "audioConfig": {"audioEncoding": "MP3", "speakingRate": pace}}
    with httpx.Client(timeout=60) as c:
        r = c.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": config.GCLOUD_TTS_API_KEY}, json=body)
        if allow_voice_fallback and r.status_code != 200 and "Neural2" not in voice and "Wavenet" not in voice:
            body["voice"]["name"] = body["voice"]["languageCode"] + "-Wavenet-A"
            r = c.post("https://texttospeech.googleapis.com/v1/text:synthesize", params={"key": config.GCLOUD_TTS_API_KEY}, json=body)
        r.raise_for_status()
        return base64.b64decode(r.json()["audioContent"]), "mp3"


# Circuit breaker: a provider that answers "no credits" / "unauthorized" is skipped for a while instead of
# being retried on every line (it failed 10× in a row on 2026-09-03 when Sarvam ran out of credits).
_TRIPPED: dict[str, tuple[float, str]] = {}
_TRIP_LOCK = threading.Lock()
_TRIP_SECONDS = 600
_HARD_MARKERS = ("402", "insufficient_quota", "no credits", "invalid api key", "unauthorized", " 401", " 403")  # account-level: 10 min
_SOFT_MARKERS = ("quota", "rate limit", "resource_exhausted")  # transient windows: 90 s
_SOFT_SECONDS = 90


def _tripped(provider: str) -> bool:
    with _TRIP_LOCK:
        t = _TRIPPED.get(provider)
        if not t:
            return False
        if time.time() > t[0]:
            _TRIPPED.pop(provider, None)
            return False
        return True


def _maybe_trip(provider: str, err: Exception) -> None:
    msg = str(err).lower()
    with _TRIP_LOCK:
        if isinstance(err, sarvam.RateLimitError):
            _TRIPPED[provider] = (time.time() + max(0.0, err.retry_after), str(err)[:160])
        elif any(m in msg for m in _HARD_MARKERS):
            _TRIPPED[provider] = (time.time() + _TRIP_SECONDS, str(err)[:160])
        elif any(m in msg for m in _SOFT_MARKERS):
            _TRIPPED[provider] = (time.time() + _SOFT_SECONDS, str(err)[:160])


def tripped_providers() -> dict[str, str]:
    with _TRIP_LOCK:
        now = time.time()
        expired = [k for k, v in _TRIPPED.items() if now > v[0]]
        for k in expired:
            _TRIPPED.pop(k, None)
        return {k: v[1] for k, v in _TRIPPED.items()}


FILLERS = {
    "ack_with_context": "Thanks for sharing that — I'll keep the demo focused on what matters to you.",
    "ack_no_context": "No problem — you can steer me at any time.",
    "bridge_to_custom": "Now, let me get to what you asked about.",
    "hold_on_question": "Let me check that.",
    "hold_on_lookup": "Give me one moment, please, while I pull that up.",
    "back_to_demo": "Let's get back to where we were.",
    "nudge_continue": "I'll carry on — stop me whenever you like.",
    "put_in_writing": "My voice dropped for a moment — I've put the answer on screen for you.",
    "still_working": "Give me one moment, please — I'm tailoring this to what you just told me.",
    "good": "Good — moving on.",
    "glad": "Glad that helps.",
    "did_that_answer": "Did that answer it?",
    "clearer": "Is that clearer?",
    "lets_go": "Alright — here we go.",
    "focus_first": "Got it — let me show you the part that matters most for that first.",
    "how_i_go": "Here's how I'll go about it.",
    "no_guess": "I'm not sure about that from the material I've been given, so I won't guess. I can have a salesperson call you about it.",
    "before_video": "First, here's a quick film to bring it to life. Then I'll walk you through it around what you just told me.",
    "after_video": "Now, let's get into what matters to you.",
}


def _cache_key(provider: str, voice: str, lang: str, text: str, delivery_identity: dict | None = None) -> str:
    identity = f"{provider}|{voice}|{lang}|{text.strip()}"
    if delivery_identity:
        identity += "|delivery-v1|" + json.dumps(delivery_identity, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(identity.encode()).hexdigest()[:20]


def _delivery_identity(demo_id: str, delivery: dict | None) -> dict | None:
    persona = (store.read_json(demo_id, "plan.json") or {}).get("voice") or {}
    if not persona and not delivery:
        return None  # Existing unstyled caches remain compatible.
    return {"delivery": speech_style.normalize(delivery), "persona": persona}


def _cached(demo_id: str, text: str, demo: dict, lang: str | None = None, provider: str | None = None, *, delivery: dict | None = None) -> str | None:
    lang = lang or demo.get("settings", {}).get("language", "en-IN")
    provider = provider or provider_for(demo)
    key = _cache_key(provider, voice_name_for(demo, provider), lang, speech_style.prepare(text, delivery)["text"], _delivery_identity(demo_id, delivery))
    for ext in ("wav", "mp3", "m4a"):
        path = store.path(demo_id, "audio", f"{key}.{ext}")
        if path.is_file() and path.stat().st_size:
            return f"audio/{key}.{ext}"
    return None


class VoicePolicyError(RuntimeError):
    pass


def render_line(demo_id: str, text: str, *, demo: dict | None = None, lang: str | None = None, strict: bool = False, delivery: dict | None = None) -> str | None:
    """Returns a media-relative path like 'audio/<hash>.wav', or None when only the browser voice is available.
    Locked/strict calls use one provider and speaker; cache reads precede cooldown checks.
    Unlocked calls may try configured fallbacks, except a content-policy refusal never falls through."""
    demo = demo or store.load(demo_id)
    prepared = speech_style.prepare(text, delivery)
    text = prepared["text"]
    if not text.strip():
        return None
    chain = provider_chain(demo)
    if chain == ["browser"]:
        return None
    locked = bool(demo.get("settings", {}).get("voice_locked"))
    if strict or locked:
        chain = chain[:1]  # runtime rule: never change voice mid-demo — same provider or no audio
    lang = lang or demo.get("settings", {}).get("language", "en-IN")
    last_err: Exception | None = None
    for provider in chain:
        voice = voice_name_for(demo, provider)
        cached = _cached(demo_id, text, demo, lang, provider, delivery=delivery)
        if cached:
            return cached  # Breakers block new spend, never usable cached audio.
        if _tripped(provider):
            last_err = RuntimeError(f"{provider} skipped: {_TRIPPED.get(provider, (0, 'provider cooldown'))[1]}")
            continue
        key = _cache_key(provider, voice, lang, text, _delivery_identity(demo_id, delivery))
        try:
            if provider == "sarvam":
                data, ext = sarvam.tts(text, voice, lang, pace=prepared["pace"]) if prepared["pace"] != 1.0 else sarvam.tts(text, voice, lang)
            elif provider == "gemini":
                style = _style(demo_id)
                if delivery:
                    style += f" Subtly {speech_style.normalize(delivery)['tone']}; pace {prepared['pace']}, never theatrical."
                data, ext = gemini.tts(text, voice, style)
            else:
                data, ext = _gcloud(text, voice, allow_voice_fallback=not (strict or locked), **({"pace": prepared["pace"]} if prepared["pace"] != 1.0 else {}))
        except Exception as e:
            last_err = e
            _maybe_trip(provider, e)
            if provider != "sarvam":  # sarvam traces its own failures; gemini / gcloud failures were invisible before
                usage.trace(f"{provider}-tts", provider, latency_ms=0, user=text, error=str(e)[:300], chars=len(text))
            if provider == "gemini" and any(marker in str(e).lower() for marker in ("policy", "prohibited", "safety", "refus", "input blocked", "sensitive words")):
                raise VoicePolicyError(f"Gemini speech refused by policy; not retried or sent to another provider: {str(e)[:160]}") from e
            continue
        p = store.path(demo_id, "audio", f"{key}.{ext}")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return f"audio/{key}.{ext}"
    label = f"locked voice {chain[0]}/{voice_name_for(demo, chain[0])} unavailable" if locked else "all voice providers failed"
    raise RuntimeError(f"{label}: {str(last_err)[:160]}")


def render_script(demo_id: str, emit) -> dict:
    """Voice the main script, then translate + voice every extra language from settings.languages."""
    demo = store.load(demo_id)
    script = _render_one(demo_id, emit, demo, "script.json", None)
    _render_bank_and_fillers(demo_id, emit, demo)
    try:
        from . import author as _author
        _author.timeline(script, demo_id)
        store.write_json(demo_id, "script.json", script)
    except Exception as e:
        emit(f"Timeline not updated ({str(e)[:60]}).")
    extra = [l for l in (demo.get("settings", {}).get("languages") or []) if l and l != demo.get("settings", {}).get("language", "en-IN")]
    complete = not script.get("voice_failures")
    for lang in extra:
        try:
            translate.translate(demo_id, lang, emit)
            _render_one(demo_id, emit, demo, translate.script_path(lang), lang)
        except Exception as e:
            complete = False
            emit(f"{lang}: skipped ({str(e)[:120]}).")
            if demo.get("settings", {}).get("voice_locked"):
                raise
            continue
        try:
            translate.translate_deck(demo_id, lang, emit)
        except Exception as e:  # noqa: BLE001 — titles/callouts fall back to the main language; narration is already voiced
            emit(f"{lang}: slide text kept in the main language ({str(e)[:80]}).")
    if complete:
        script["voice_input_hash"] = input_hash(demo_id)
    else:
        script.pop("voice_input_hash", None)
    store.write_json(demo_id, "script.json", script)
    return script


def input_hash(demo_id: str) -> str:
    """Identity/settings/text hash used only to skip an unchanged voice stage."""
    demo = store.load(demo_id)
    script = store.read_json(demo_id, "script.json") or {}
    def line_input(line):
        return {"text": line.get("text", ""), "delivery": speech_style.normalize(line.get("delivery")), "unverified": line.get("unverified", False)}
    spoken = [line_input(line) for segment in script.get("segments", []) for line in [*segment.get("lines", []), *segment.get("deeper", [])]]
    spoken += [line_input(line) for line in script.get("closing", [])]
    spoken.append(line_input(script.get("runtime_overview") or {}))
    settings = demo.get("settings", {})
    inputs = {"settings": {key: settings.get(key) for key in ("tts_provider", "voice_name", "sarvam_speaker", "voice_locked", "language", "languages")},
              "persona": (store.read_json(demo_id, "plan.json") or {}).get("voice"), "lines": spoken,
              "questions": [script.get("intake_q1", ""), *[segment.get("checkin", "") for segment in script.get("segments", [])]],
              "faq": [entry.get("answer", "") for entry in (store.read_json(demo_id, "faq.json") or {}).get("entries", [])], "fillers": FILLERS}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _render_bank_and_fillers(demo_id: str, emit, demo: dict) -> None:
    """Voice the FAQ bank answers and the persona's filler lines (acknowledgements, bridges, holds) so nothing at
    runtime has to be voiced live except a genuinely new answer."""
    if provider_for(demo) == "browser":
        return
    bank = store.read_json(demo_id, "faq.json") or {}
    locked = bool(demo.get("settings", {}).get("voice_locked"))
    if locked:
        for entry in bank.get("entries", []):
            if entry.get("answer"):
                entry["audio"] = _cached(demo_id, entry["answer"], demo)
    todo = [(e, "audio", e["answer"]) for e in bank.get("entries", []) if e.get("answer") and not e.get("audio")]
    fill = store.read_json(demo_id, "fillers.json") or {}
    for key, text in FILLERS.items():
        if locked:
            fill[key] = {"text": text, "audio": _cached(demo_id, text, demo)}
        if not (fill.get(key) or {}).get("audio"):
            fill[key] = {"text": text, "audio": None}
            todo.append((fill[key], "audio", text))
    if not todo:
        if locked:
            if bank:
                store.write_json(demo_id, "faq.json", bank)
            store.write_json(demo_id, "fillers.json", fill)
        return
    emit(f"Recording {len(todo)} FAQ answers and filler lines…")
    done = 0
    errors = []
    with ThreadPoolExecutor(max_workers=VOICE_WORKERS) as pool:
        futs = {pool.submit(contextvars.copy_context().run, render_line, demo_id, text, demo=demo): (obj, key) for obj, key, text in todo}
        for fut in as_completed(futs):
            obj, key = futs[fut]
            try:
                obj[key] = fut.result()
                done += 1
            except Exception as exc:
                obj[key] = None
                errors.append(str(exc)[:180])
    if bank:
        store.write_json(demo_id, "faq.json", bank)
    store.write_json(demo_id, "fillers.json", fill)
    emit(f"FAQ bank and fillers recorded ({done}/{len(todo)}).")
    missing_faq = [e.get("id", "?") for e in bank.get("entries", []) if e.get("answer") and not e.get("audio")]
    missing_fillers = [key for key, item in fill.items() if item.get("text") and not item.get("audio")]
    if missing_faq or missing_fillers:
        raise RuntimeError(
            f"Voice bank incomplete: {len(missing_faq)} FAQ answer(s) and {len(missing_fillers)} filler line(s) have no audio. "
            "Wait for the provider window to reset, then rebuild; matching audio was checkpointed. "
            + (errors[0] if errors else "")
        )


def _render_one(demo_id: str, emit, demo: dict, path: str, lang: str | None) -> dict:
    script = store.read_json(demo_id, path)
    if not script:
        raise RuntimeError("No script to voice")
    provider = provider_for(demo)
    chain = provider_chain(demo)
    locked = bool(demo.get("settings", {}).get("voice_locked"))
    if provider == "browser":
        if locked:
            raise RuntimeError("Locked voice has no server speech provider configured")
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
    overview = script.get("runtime_overview")
    if overview and not overview.get("unverified"):
        todo.append((overview, "audio"))
    intake = {"q1": script.get("intake_q1", "")}
    total = len(todo) + 1
    done, failures = 0, 0
    errors = []
    emit(f"Recording narration with {provider}" + (f" in {lang}" if lang else "") + (f" (fallbacks: {', '.join(chain[1:])})" if len(chain) > 1 else "") + f" — {total} lines…")
    # Lines render in parallel (VOICE_WORKERS, default 3); Sarvam spaces request starts across these workers.
    # Contextvars are copied per task so usage/trace rows keep the demo id.
    lock = threading.Lock()
    stop = threading.Event()
    policy_failed = set()

    def work(item):
        obj, key = item
        text = obj["text"] if key == "audio" else obj["checkin"]
        delivery = obj.get("delivery") if key == "audio" else None
        if stop.is_set():
            return (obj, key, _cached(demo_id, text, demo, lang, delivery=delivery), "skipped")
        try:
            return (obj, key, render_line(demo_id, text, demo=demo, lang=lang, delivery=delivery), None)
        except VoicePolicyError as e:
            with lock:
                policy_failed.add((id(obj), key))
            return (obj, key, None, str(e)[:160])
        except Exception as e:
            return (obj, key, None, str(e)[:160])

    with ThreadPoolExecutor(max_workers=VOICE_WORKERS) as pool:
        futures = [pool.submit(contextvars.copy_context().run, work, item) for item in todo]
        for fut in as_completed(futures):
            obj, key, rel, err = fut.result()
            with lock:
                if err == "skipped":
                    obj[key] = rel
                    continue
                obj[key] = rel
                if err:
                    errors.append(err)
                    failures += 1
                    if failures == 1:
                        emit(f"Voice provider error: {err} — matching completed audio is kept; missing locked audio will stop this build." if locked else f"Voice provider error: {err} — continuing; any missing line will use timed captions.")
                    if failures >= 4 and not stop.is_set():
                        stop.set()
                        emit("Too many voice errors — stopping new narration requests; completed matching audio is kept." if locked else "Too many voice errors — stopping narration rendering; remaining lines will use timed captions.")
                done += 1
                if done % 8 == 0:
                    emit(f"Recorded {done}/{total} lines…")
                    store.write_json(demo_id, path, script)
    # Second pass, one at a time: lines that failed under parallel load (rate limits) usually succeed alone.
    retry = [(obj, key) for obj, key in todo if obj.get(key) is None and (id(obj), key) not in policy_failed]
    if retry and not stop.is_set() and not locked:  # Sarvam already owns its bounded 429 retry; locked builds never switch/retry content policy failures.
        emit(f"Re-recording {len(retry)} line(s) that failed the first time…")
        recovered = 0
        for obj, key in retry:
            text = obj["text"] if key == "audio" else obj["checkin"]
            try:
                obj[key] = render_line(demo_id, text, demo=demo, lang=lang, delivery=obj.get("delivery") if key == "audio" else None)
                recovered += 1
                time.sleep(0.5)
            except Exception as e:
                obj[key] = None
                emit(f"Still no audio for one line ({str(e)[:100]}) — the player will show timed captions for it.")
        failures = max(0, failures - recovered)
    for k, text in intake.items():
        try:
            script.setdefault("intake_audio", {})[k] = render_line(demo_id, text, demo=demo, lang=lang) if failures < 4 else _cached(demo_id, text, demo, lang)
        except Exception:
            script.setdefault("intake_audio", {})[k] = None
    if tripped_providers():
        for prov, why in tripped_providers().items():
            emit(f"{prov} is unavailable ({why[:90]}) — locked voice retained; wait for recovery before rebuilding missing clips." if locked else f"{prov} is unavailable ({why[:90]}) — lines used the next provider in the chain. Top up / fix the key, then rebuild to re-record.")
        if not locked:
            used = next((c for c in chain if not _tripped(c)), "browser")
            provider = used if used != "browser" else provider
    script["voice_provider"] = provider
    script["voice_name"] = voice_name_for(demo, provider)
    script["voice_failures"] = failures
    if overview and not overview.get("unverified"):
        from .author import _audio_seconds, words, WPS
        measured = _audio_seconds(demo_id, overview.get("audio"))
        overview["duration_seconds"] = measured if measured is not None else round(words(overview.get("text", "")) / WPS, 2)
        overview["duration_exact"] = measured is not None
        overview["duration_in_range"] = measured is not None and 10 <= measured <= 15
        if measured is not None and not overview["duration_in_range"]:
            emit(f"Explore overview is {measured:.1f}s; its 10–15s target needs a script/pacing review.")
    store.write_json(demo_id, path, script)
    store.log(demo_id, "voice", {"provider": provider, "lines": total, "failures": failures, "language": lang})
    missing = sum(1 for obj, key in todo if not obj.get(key)) + sum(1 for key, text in intake.items() if text.strip() and not script.get("intake_audio", {}).get(key))
    if locked and missing:
        raise RuntimeError(f"Locked voice {provider}/{script['voice_name']} incomplete: {missing} narration/question clip(s) missing. Matching audio is checkpointed; wait for provider recovery and rebuild. " + (errors[0] if errors else ""))
    emit("Narration ready." if not failures else f"Narration ready with {failures} line(s) on timed captions.")
    return script


def sample(demo_id: str, text: str) -> str | None:
    return render_line(demo_id, text)
