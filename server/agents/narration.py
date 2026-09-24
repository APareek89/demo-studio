"""Deterministic default-tour narration accounting; never manufactures speech."""
from __future__ import annotations

import re
import math
import hashlib
import json
from functools import lru_cache

MIN_SECONDS = 180.0
OVERVIEW_WORDS = 23  # The lower edge of the reviewed 23–28 word opening.
ROLES = {"proof", "features", "establish"}
PREPARATION_VERSION = 1
NATURAL_WPS = 2.5
CONTENT_HEADROOM = 1.10
PREPARATION_INSTRUCTION = ("Expand the default guided narration to the selected demo duration using distinct supported detail from the approved facts. "
                           "Preserve the reviewed story, voice and CTAs. Film, questions, deeper-only lines and repeated claims do not count; do not pad or slow the voice.")


def validate_minutes(value) -> int:
    """Duration is an explicit whole-minute preference, never a voice-speed change."""
    if type(value) is not int or not 1 <= value <= 5:
        raise ValueError("pitch_minutes must be a whole number from 1 to 5")
    return value


def minimum_seconds(demo: dict | None = None) -> float:
    settings = (demo or {}).get("settings", {})
    try:
        return float(validate_minutes(settings.get("pitch_minutes", 3)) * 60)
    except ValueError:
        return MIN_SECONDS  # Older invalid/missing settings retain the historic default.


def preparation_identity(demo: dict, persona: dict | None = None) -> str:
    """Retain calibration only for the same selected voice, languages and duration."""
    from . import voice
    settings = demo.get("settings", {})
    provider = voice.provider_for(demo)
    identity = {"provider": provider, "speaker": voice.voice_name_for(demo, provider),
                "language": settings.get("language", "en-IN"),
                "languages": sorted(set(settings.get("languages") or [])),
                "pitch_minutes": minimum_seconds(demo) / 60,
                "persona": persona or {}}
    return hashlib.sha256(json.dumps(identity, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _alternate_matches(script: dict, alternate: dict, provider: str) -> bool:
    if alternate.get("voice_provider") != provider or alternate.get("voice_name") != script.get("voice_name"):
        return False
    if alternate.get("source_digest"):
        from .. import store
        from ..orchestrator import semantic
        from .translate import TRANSLATE_SYSTEM
        source_digest = store.digest(json.dumps({"s": semantic(script.get("segments")), "c": semantic(script.get("closing")),
            "q": [script.get("intake_q1"), script.get("intake_q2")], "overview": semantic(script.get("runtime_overview")),
            "prompt": TRANSLATE_SYSTEM}, sort_keys=True))
        return alternate["source_digest"] == source_digest
    return True


def word_target(demo: dict, script: dict | None = None, demo_id: str | None = None) -> int:
    """Plan enough supported words; never change a recording or its delivery speed."""
    rate = NATURAL_WPS
    if script and demo_id and script.get("voice_input_hash"):
        from . import voice
        from .. import store
        provider = voice.provider_for(demo)
        matching = (script.get("voice_provider") == provider
                    and script.get("voice_name") == voice.voice_name_for(demo, provider)
                    and script["voice_input_hash"] == voice.input_hash(demo_id))
        if matching:
            measured = preparation_report(script, demo_id=demo_id)
            if measured["measured"] and measured["seconds"] > 0:
                rate = max(rate, measured["words"] / measured["seconds"])
                # Translate the old language duration into required main-script
                # content, not a cross-language words-per-second assumption.
                for language in demo.get("settings", {}).get("languages") or []:
                    if not language or language == demo.get("settings", {}).get("language", "en-IN"):
                        continue
                    alternate = store.read_json(demo_id, f"script.{language}.json") or {}
                    if not _alternate_matches(script, alternate, provider):
                        continue
                    alt_measured = preparation_report(alternate, demo_id=demo_id)
                    if alt_measured["measured"] and alt_measured["seconds"] > 0:
                        rate = max(rate, measured["words"] / alt_measured["seconds"])
    seconds = minimum_seconds(demo)
    target = math.ceil(seconds * rate * CONTENT_HEADROOM - 1e-9)
    if demo_id:
        from .. import store
        previous = store.read_json(demo_id, "plan.json") or {}
        preparation = previous.get("narration_preparation") or {}
        if (preparation.get("version") == PREPARATION_VERSION
                and preparation.get("identity") == preparation_identity(demo, previous.get("voice"))):
            target = max(target, int(preparation.get("target_words") or 0))
    return target


class NarrationTooShort(RuntimeError):
    def __init__(self, message: str, result: dict | None = None):
        super().__init__(message)
        self.result = result


def explicit_short_tour(profile: dict) -> bool:
    """Only direct customer wording can waive the default visit's minimum."""
    text = "\n".join(str(profile.get(key) or "") for key in ("why", "followup"))
    text = re.sub(r'"[^"\n]*"|“[^”\n]*”|`[^`\n]*`', "", text)
    for clause in re.split(r"[.!?;\n]", text):
        if re.search(r"\b(?:not|don't|don’t|never|avoid|without)\b", clause, re.I):
            continue
        if re.search(r"^\s*(?:please\s+)?(?:(?:give|show)\s+me\s+|(?:I|we)\s+(?:want|need|would like)\s+|just\s+)?(?:a\s+)?(?:short|quick|brief)\s+(?:tour|demo|overview)\b", clause, re.I):
            return True
        if re.search(r"^\s*(?:please\s+)?keep\s+(?:it|the demo|the tour)\s+(?:short|brief)\b", clause, re.I):
            return True
    return False


def _audio_path(demo_id: str | None, value: str | None) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    if demo_id and value.startswith(f"/media/{demo_id}/"):
        value = value[len(f"/media/{demo_id}/"):]
    return value if value.startswith("audio/") and ".." not in value.split("/") else None


@lru_cache(maxsize=512)
def _compressed_seconds(path: str, modified: int, size: int) -> float | None:
    from pathlib import Path
    from ..media import ffprobe_duration
    duration = ffprobe_duration(Path(path))
    return duration if duration is not None and math.isfinite(duration) and duration > 0 else None


def _recorded_seconds(demo_id: str | None, path: str | None) -> float | None:
    from .. import store
    from .author import _audio_seconds
    measured = _audio_seconds(demo_id, path)
    if measured is not None and measured > 0:
        return measured
    if demo_id and path and path.lower().endswith((".mp3", ".m4a", ".ogg")):
        try:
            file = store.path(demo_id, path)
            stat = file.stat()
            return _compressed_seconds(str(file), stat.st_mtime_ns, stat.st_size)
        except OSError:
            pass
    return None


def _closing(segment: dict) -> dict:
    value = segment.get("checkin")
    return value if isinstance(value, dict) else {"text": value or "", "audio": segment.get("checkin_audio")}


def report(script: dict, *, demo_id: str | None = None, route_ids: list[str] | None = None,
           replacements: list[dict] | None = None, allowed_fact_ids: set[str] | None = None,
           minimum_seconds: float = MIN_SECONDS) -> dict:
    """Count only unique playable guide narration; estimates never masquerade as recordings."""
    from .author import WPS, words
    by_id = {segment["id"]: segment for segment in script.get("segments", []) if segment.get("id")}
    replacement = {segment.get("segment_id", segment.get("id")): segment for segment in replacements or []}
    ids = list(dict.fromkeys(route_ids if route_ids is not None else [sid for sid, segment in by_id.items() if segment.get("role") in ROLES]))
    rows, seen, duplicates = [], set(), 0

    def add(line: dict, owner: str, *, statement: bool = False):
        nonlocal duplicates
        text = " ".join(str(line.get("text") or "").split())
        if not text or line.get("unverified") or re.search(r"[?？]", text):
            return
        if allowed_fact_ids is not None and set(line.get("fact_ids") or []) - allowed_fact_ids:
            return
        key = text.casefold()
        if key in seen:
            duplicates += 1
            return
        seen.add(key)
        measured = _recorded_seconds(demo_id, _audio_path(demo_id, line.get("audio")))
        count = words(text)
        rows.append({"owner": owner, "line_id": line.get("id"), "words": count,
                     "seconds": measured if measured is not None else count / WPS,
                     "measured": measured is not None})

    overview = script.get("runtime_overview") or script.get("overview") or {}
    if overview.get("text") and not overview.get("unverified"):
        add(overview, "overview")
    else:
        for segment in by_id.values():
            if segment.get("role") in {"intro", "outcome"}:
                for line in segment.get("lines", []):
                    add(line, segment["id"])
    for sid in ids:
        segment = replacement.get(sid) or by_id.get(sid)
        if not segment:
            continue
        for line in segment.get("lines", []):
            add(line, sid)
        add(_closing(segment), sid, statement=True)
    for line in script.get("closing", []):
        add(line, "closing")
    total = sum(row["seconds"] for row in rows)
    measured_count = sum(row["measured"] for row in rows)
    return {"minimum_seconds": minimum_seconds, "seconds": round(total, 2),
            "sufficient": total + 1e-9 >= minimum_seconds, "words": sum(row["words"] for row in rows),
            "measured": bool(rows) and measured_count == len(rows),
            "basis": "measured" if rows and measured_count == len(rows) else "mixed" if measured_count else "estimated",
            "measured_seconds": round(sum(row["seconds"] for row in rows if row["measured"]), 2),
            "estimated_seconds": round(sum(row["seconds"] for row in rows if not row["measured"]), 2),
            "route": [sid for sid in ids if sid in by_id], "duplicate_lines_excluded": duplicates}


def default_route(script: dict, *, demo_id: str | None = None, preferred: list[str] | None = None,
                  allowed_fact_ids: set[str] | None = None, include_all_proofs: bool = False,
                  minimum_seconds: float = MIN_SECONDS) -> tuple[list[str], dict]:
    """Retain buyer order, then add unseen reviewed proofs until the minimum is met."""
    segments = [segment for segment in script.get("segments", []) if segment.get("role") in ROLES]
    by_id = {segment["id"]: segment for segment in segments}
    # A story stop can use several short delivery batches. Select and move the
    # whole stop; neither proof nor closing-role continuations may be orphaned.
    groups, group_for = {}, {}
    for segment in segments:
        key = (segment.get("role"), segment.get("budget_source_id") or segment["id"])
        groups.setdefault(key, []).append(segment["id"])
        group_for[segment["id"]] = key
    proofs = [key for key in groups if key[0] == "proof"]
    requested = list(dict.fromkeys(sid for sid in preferred or [] if sid in by_id))
    requested_groups = list(dict.fromkeys(group_for[sid] for sid in requested))
    chosen = [key for key in requested_groups if key[0] == "proof"][:3] or proofs[:3]
    if include_all_proofs:
        chosen = proofs[:]
    fundamental = next((key for key in proofs if any(by_id[sid].get("fundamental") for sid in groups[key])), None)
    if fundamental:
        chosen = [fundamental, *[sid for sid in chosen if sid != fundamental]]
    tail = []
    for role in ("features", "establish"):
        candidates = [key for key in requested_groups if key[0] == role] or [key for key in groups if key[0] == role]
        tail.extend(candidates[:1])
    flatten = lambda selected: [sid for key in selected for sid in groups[key]]
    result = report(script, demo_id=demo_id, route_ids=flatten(chosen + tail), allowed_fact_ids=allowed_fact_ids, minimum_seconds=minimum_seconds)
    for sid in proofs:
        if result["sufficient"]:
            break
        if sid not in chosen:
            chosen.append(sid)
            result = report(script, demo_id=demo_id, route_ids=flatten(chosen + tail), allowed_fact_ids=allowed_fact_ids, minimum_seconds=minimum_seconds)
    return flatten(chosen + tail), result


def preparation_report(script: dict, *, demo_id: str | None = None,
                       allowed_fact_ids: set[str] | None = None, minimum_seconds: float = MIN_SECONDS) -> dict:
    """Count all available proof stops and only the default route's closing-role stops."""
    return default_route(script, demo_id=demo_id, allowed_fact_ids=allowed_fact_ids,
                         include_all_proofs=True, minimum_seconds=minimum_seconds)[1]


def preparation_status(demo_id: str, script: dict | None = None, plan: dict | None = None) -> dict:
    """One current readiness decision for drafting, review and the Build boundary."""
    from .. import store
    from . import voice
    script = store.read_json(demo_id, "script.json") or {} if script is None else script
    plan = store.read_json(demo_id, "plan.json") or {} if plan is None else plan
    demo = store.load(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    allowed = {fact["id"] for fact in und.get("facts", []) if fact.get("approved", True)}
    saved = script.get("narration_preparation") or {}
    target = word_target(demo, script, demo_id)
    planned = plan.get("narration_preparation") or {}
    if planned.get("identity") == preparation_identity(demo, plan.get("voice")):
        target = max(target, int(planned.get("target_words") or 0))
    required = minimum_seconds(demo)
    reviewed_duration = plan.get("guided_minimum_seconds", saved.get("minimum_seconds"))
    duration_changed = (isinstance(reviewed_duration, (int, float))
                        and not isinstance(reviewed_duration, bool)
                        and reviewed_duration != required)
    draft = preparation_report(script, allowed_fact_ids=allowed, minimum_seconds=required)
    provider = voice.provider_for(demo)
    current_recording = bool(script.get("voice_input_hash")) and (
        script["voice_input_hash"] == voice.input_hash(demo_id)
        and script.get("voice_provider") == provider
        and script.get("voice_name") == voice.voice_name_for(demo, provider))
    recorded_rows = [script.get("runtime_overview") or script.get("overview") or {}, *script.get("closing", [])]
    for segment in script.get("segments", []):
        recorded_rows.extend([*segment.get("lines", []), *segment.get("deeper", []), _closing(segment)])
    prior_recording = bool(script.get("voice_provider") and
                           (any(_audio_path(demo_id, row.get("audio")) for row in recorded_rows)
                            or ((demo.get("stages") or {}).get("voice") or {}).get("status") == "done"))
    _, duration = default_route(script, demo_id=demo_id if current_recording else None, allowed_fact_ids=allowed, minimum_seconds=required)
    all_recorded = current_recording and duration["measured"]
    recorded_ready = current_recording and duration["measured"] and duration["sufficient"]
    if current_recording:
        for language in demo.get("settings", {}).get("languages") or []:
            if not language or language == demo.get("settings", {}).get("language", "en-IN"):
                continue
            alternate = store.read_json(demo_id, f"script.{language}.json") or {}
            _, alt_duration = default_route(alternate, demo_id=demo_id, allowed_fact_ids=allowed, minimum_seconds=required)
            identity_matches = _alternate_matches(script, alternate, provider)
            all_recorded = all_recorded and identity_matches and alt_duration["measured"]
            recorded_ready = recorded_ready and identity_matches and alt_duration["measured"] and alt_duration["sufficient"]
            if (alt_duration["measured"] and alt_duration["sufficient"], alt_duration["seconds"]) < (duration["measured"] and duration["sufficient"], duration["seconds"]):
                duration = {**alt_duration, "language": language}
    texts = [script.get("intake_q1", ""), script.get("intake_q2", ""),
             (script.get("runtime_overview") or script.get("overview") or {}).get("text", "")]
    texts.extend(row.get("text", "") for row in script.get("closing", []))
    for segment in script.get("segments", []):
        texts.extend(row.get("text", "") for row in [*segment.get("lines", []), *segment.get("deeper", [])])
        texts.append(_closing(segment).get("text", ""))
    mock_preview = any("(mock)" in str(text).casefold() for text in texts)
    errors = [str(error)[:300] for error in list(saved.get("errors") or [])[:3]]
    incomplete_reason = ("Mock placeholder speech is not a prepared customer demo." if mock_preview else
                         "Narration preparation could not finish because a drafting request failed." if errors else
                         "Narration preparation has not yet produced enough distinct supported speech.")
    has_draft = bool(script.get("segments") or script.get("closing")
                     or (script.get("runtime_overview") or script.get("overview") or {}).get("text"))
    if not allowed:
        status, reason = "needs_sources", "No approved source facts are available for the narration."
    elif not has_draft:
        status = "incomplete"
        author_stage = (demo.get("stages") or {}).get("author") or {}
        if author_stage.get("status") == "error":
            reason = "Narration drafting failed before a draft was produced. Check the reported error before retrying."
            if author_stage.get("error"):
                errors = [*errors, str(author_stage["error"])[:300]][:3]
        else:
            reason = "Narration drafting has not produced a draft for review yet."
    elif duration_changed:
        # A longer old recording can satisfy a shorter minimum without being
        # the draft the user selected. Reprepare on their next Build. Explicit
        # manual edits remain blocked for review instead of being overwritten.
        status = "incomplete" if saved.get("status") == "incomplete" else "needs_preparation"
        reason = (f"This draft was prepared for {reviewed_duration / 60:g} minutes; the selected duration is now {required / 60:g} minutes. "
                  + ("Keep the manual draft for review; explicitly retry drafting for the selected duration before approving it."
                     if status == "incomplete" else "Build will prepare narration for the selected duration and return it to Align for fresh review."))
    elif recorded_ready:
        status, reason = "ready", f"Current recordings meet the {required / 60:g}-minute minimum in every selected language."
    elif all_recorded:
        status, reason = "needs_preparation", "The current recordings are short; the next build will prepare supported narration for review."
    elif not current_recording and saved.get("status") == "incomplete" and draft["words"] < target:
        status, reason = "incomplete", incomplete_reason
    elif current_recording or prior_recording:
        status, reason = "needs_recording", "Some selected recordings are missing, unreadable or no longer current. Build will retry recording the reviewed words."
    elif draft["words"] >= target and not current_recording:
        status, reason = "ready", "The supported draft is prepared for review; recording will verify its duration."
    elif saved.get("status") is None:
        status, reason = "needs_preparation", "This older draft needs automatic narration preparation before a new build."
    else:
        status, reason = "incomplete", incomplete_reason
    return {"version": PREPARATION_VERSION, "identity": planned.get("identity"), "status": status,
            "minimum_seconds": required, "duration_changed": duration_changed, "target_words": target, "words": draft["words"], "missing_words": max(0, target - draft["words"]),
            "attempts": int(saved.get("attempts") or 0), "mock_preview": mock_preview,
            "measured": bool(current_recording and duration["measured"]), "seconds": duration["seconds"],
            "basis": duration["basis"], "reason": reason, "errors": errors,
            "current_recording": bool(current_recording), "recorded_short": bool(all_recorded and not recorded_ready),
            "recording_incomplete": bool((current_recording or prior_recording) and not recorded_ready and not all_recorded)}


def deficit_message(result: dict) -> str:
    return (f"Default guided narration is {result['seconds']:.1f}s ({result['basis']}); at least {result.get('minimum_seconds', MIN_SECONDS):g}s is required "
            "before publication. The draft needs more distinct supported narration before it can be reviewed for a new build. "
            "Film, customer Q&A, deeper-only lines and repeated speech do not count; "
            "do not pad, duplicate claims or slow the voice to meet the minimum.")


def require_minimum(script: dict, *, demo_id: str | None = None,
                    allowed_fact_ids: set[str] | None = None, require_recorded: bool = False,
                    minimum_seconds: float = MIN_SECONDS) -> dict:
    _, result = default_route(script, demo_id=demo_id, allowed_fact_ids=allowed_fact_ids, minimum_seconds=minimum_seconds)
    if not result["sufficient"]:
        raise NarrationTooShort(deficit_message(result), result)
    if require_recorded and not result["measured"]:
        raise NarrationTooShort(f"Default guided narration has missing or unreadable audio. Record every counted line before publication; estimated words cannot establish the {minimum_seconds:g}-second minimum.", result)
    return result
