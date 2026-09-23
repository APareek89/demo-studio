"""Deterministic default-tour narration accounting; never manufactures speech."""
from __future__ import annotations

import re
import math
from functools import lru_cache

MIN_SECONDS = 180.0
OVERVIEW_WORDS = 23  # The lower edge of the reviewed 23–28 word opening.
ROLES = {"proof", "features", "establish"}


class NarrationTooShort(RuntimeError):
    pass


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
           replacements: list[dict] | None = None, allowed_fact_ids: set[str] | None = None) -> dict:
    """Count only unique playable guide narration; estimates never masquerade as recordings."""
    from .author import WPS, words
    by_id = {segment["id"]: segment for segment in script.get("segments", []) if segment.get("id")}
    replacement = {segment.get("segment_id", segment.get("id")): segment for segment in replacements or []}
    ids = list(dict.fromkeys(route_ids if route_ids is not None else [sid for sid, segment in by_id.items() if segment.get("role") in ROLES]))
    rows, seen, duplicates = [], set(), 0

    def add(line: dict, owner: str, *, statement: bool = False):
        nonlocal duplicates
        text = " ".join(str(line.get("text") or "").split())
        if not text or line.get("unverified") or (statement and re.search(r"[?？]", text)):
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
    return {"minimum_seconds": MIN_SECONDS, "seconds": round(total, 2),
            "sufficient": total + 1e-9 >= MIN_SECONDS, "words": sum(row["words"] for row in rows),
            "measured": bool(rows) and measured_count == len(rows),
            "basis": "measured" if rows and measured_count == len(rows) else "mixed" if measured_count else "estimated",
            "measured_seconds": round(sum(row["seconds"] for row in rows if row["measured"]), 2),
            "estimated_seconds": round(sum(row["seconds"] for row in rows if not row["measured"]), 2),
            "route": [sid for sid in ids if sid in by_id], "duplicate_lines_excluded": duplicates}


def default_route(script: dict, *, demo_id: str | None = None, preferred: list[str] | None = None,
                  allowed_fact_ids: set[str] | None = None) -> tuple[list[str], dict]:
    """Retain buyer order, then add unseen reviewed proofs until the minimum is met."""
    segments = [segment for segment in script.get("segments", []) if segment.get("role") in ROLES]
    by_id = {segment["id"]: segment for segment in segments}
    proofs = [segment["id"] for segment in segments if segment.get("role") == "proof"]
    requested = list(dict.fromkeys(sid for sid in preferred or [] if sid in by_id))
    chosen = [sid for sid in requested if by_id[sid].get("role") == "proof"][:3] or proofs[:3]
    fundamental = next((sid for sid in proofs if by_id[sid].get("fundamental")), None)
    if fundamental:
        chosen = [fundamental, *[sid for sid in chosen if sid != fundamental]]
    tail = []
    for role in ("features", "establish"):
        candidates = [sid for sid in requested if by_id[sid].get("role") == role] or [segment["id"] for segment in segments if segment.get("role") == role]
        tail.extend(candidates[:1])
    result = report(script, demo_id=demo_id, route_ids=chosen + tail, allowed_fact_ids=allowed_fact_ids)
    for sid in proofs:
        if result["sufficient"]:
            break
        if sid not in chosen:
            chosen.append(sid)
            result = report(script, demo_id=demo_id, route_ids=chosen + tail, allowed_fact_ids=allowed_fact_ids)
    return chosen + tail, result


def deficit_message(result: dict) -> str:
    missing = max(0, MIN_SECONDS - result["seconds"])
    return (f"Default guided narration is {result['seconds']:.1f}s ({result['basis']}); at least 180s is required "
            f"before publication. Add {missing:.1f}s of distinct supported narration in Align, using additional cited "
            "material or supported detail. Film, customer Q&A, deeper-only lines and repeated speech do not count; "
            "do not pad, duplicate claims or slow the voice to meet the minimum.")


def require_minimum(script: dict, *, demo_id: str | None = None,
                    allowed_fact_ids: set[str] | None = None, require_recorded: bool = False) -> dict:
    _, result = default_route(script, demo_id=demo_id, allowed_fact_ids=allowed_fact_ids)
    if not result["sufficient"]:
        raise NarrationTooShort(deficit_message(result))
    if require_recorded and not result["measured"]:
        raise NarrationTooShort("Default guided narration has missing or unreadable audio. Record every counted line before publication; estimated words cannot establish the 180-second minimum.")
    return result
