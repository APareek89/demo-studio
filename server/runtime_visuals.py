"""Resolve runtime pictures from the reviewed publication, never a mutable upload.

The published slide already owns the photo, caption and trusted pointer. This
lookup selects that existing association; it does not infer image coordinates,
send a gallery to a model, or treat a picture as new product evidence.
"""
from __future__ import annotations

import re
from urllib.parse import unquote, urlsplit

from . import store

_STOP = set("a an the me us you your my its it this that these those please can could would will i we like want see look show view picture pictures photo photos image images of at to for on in with and is are has have tell about more feature features car vehicle demo around again now variant variants trim trims version".split())
_ALIASES = {"seats": "seat", "seating": "seat", "wheels": "wheel", "headlights": "headlamp", "headlight": "headlamp", "headlamps": "headlamp", "screens": "display", "screen": "display", "touchscreen": "display", "displays": "display", "interior": "cabin"}
_POSITION = {"front", "rear", "left", "right", "side", "row", "first", "second", "third", "upper", "lower", "new", "old", "model", "variant", "version"}
_PHOTO_NOUNS = {"display", "seat", "cabin", "console", "dashboard", "wheel", "door", "roof", "body", "exterior"}
_SHOW = re.compile(r"^(?:(?:please\s+)?(?:can|could|would)\s+you\s+|(?:i(?:'d| would) like|i want)\s+to\s+)?(?:please\s+)?(?:show(?:\s+(?:me|us))?|let\s+me\s+see|see|view|look\s+at|bring\s+up)\s+(.+?)[?.!]*$", re.I)
_MIXED = re.compile(r"\b(?:tell|explain|why|how|whether|compare|cost|costs|price|prices|guarantee|does|can it|is it|what is|what are)\b|\b(?:and|also)\b", re.I)


def terms(text: str) -> set[str]:
    return {_ALIASES.get(word, word) for word in re.findall(r"[a-z0-9]+", str(text).casefold()) if word not in _STOP}


def show_request(question: str) -> bool:
    """Only a picture-navigation request may bypass factual reasoning."""
    match = _SHOW.fullmatch(question.strip())
    return bool(match and terms(match[1]) and not _MIXED.search(match[1])
                and not re.search(r"\b(?:around|tour|demo|everything|anything|something)\b", match[1], re.I))


def _subject_terms(question: str, bundle: dict, requested_scope: dict | None = None) -> set[str]:
    product = bundle.get("product") or {}
    names = " ".join(str(product.get(key, "")) for key in ("name", "brand", "model")) if isinstance(product, dict) else str(product)
    scope_names = " ".join(str(value) for value in (requested_scope or {}).values())
    return terms(question) - terms(names) - terms(scope_names)


def _literal_subject(query: set[str], label: set[str], context: set[str]) -> bool:
    # An armrest request cannot match just 'rear'; 'reclining seats' cannot
    # silently become any seat. Unknown qualifiers fail closed, not by rank.
    return bool((query & label) - _POSITION) and query <= label | context


def retrieval_hint(bundle: dict, question: str, requested_scope: dict | None = None) -> str:
    """At most four reviewed labels improve recall, never scope or user intent.

    A picture label may say 'cabin' while its cited assertion says 'seats'. This
    supplies the assertion's reviewed label words to the existing fact index.
    Eligibility remains entirely with normal snapshot/scope retrieval.
    """
    query = _subject_terms(question, bundle, requested_scope)
    labels = []
    for slide in bundle.get("slides", []):
        title = terms(slide.get("title", ""))
        for callout in slide.get("callouts", []):
            text = str(callout.get("text", ""))
            if _literal_subject(query, terms(text + " " + callout.get("part", "")), title):
                labels.append(text[:160])
                if len(labels) == 4:
                    return " ".join(labels)
    return " ".join(labels)


def _local_image(demo_id: str, url: str) -> bool:
    parsed = urlsplit(url)
    path = unquote(parsed.path)
    prefix = f"/media/{demo_id}/"
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not path.startswith(prefix):
        return False
    rel = path[len(prefix):]
    if (rel.split("/", 1)[0] not in {"sources", "derived", "media"}
            or any(part in {"", ".", ".."} for part in rel.split("/"))
            or not re.search(r"\.(?:jpe?g|png|webp|gif|avif)$", rel, re.I)):
        return False
    base = store.path(demo_id).resolve()
    target = (base / rel).resolve()
    return target.is_relative_to(base) and target.is_file()


def select(demo_id: str, bundle: dict, *, snapshot_id: str, demo_version: int | None,
           question: str, current_id: str | None, evidence: list[dict],
           fact_ids: list[str] | None = None, visual_only: bool = False, requested_scope: dict | None = None) -> dict | None:
    """Return a known slide/media identity only for this session's publication.

    Evidence has already passed the normal snapshot/scope retrieval. Captions
    with a missing, rejected, conflicted or differently scoped citation cannot
    select a picture. Explicit show requests additionally require a literal
    subject match and a non-illustrative photo; a hero fallback is not a match.
    """
    if (not snapshot_id or bundle.get("knowledge_snapshot_id") != snapshot_id
            or demo_version is None or bundle.get("version") != demo_version):
        return None
    eligible = {f["id"] for f in evidence if f.get("id") and f.get("approved", True)
                and f.get("provenance") not in {"live_web", "calculation"}
                and not f.get("competition") and not f.get("knowledge", {}).get("excluded_by_precedence")
                and f.get("knowledge", {}).get("conflict_status") not in {"suppressed", "unresolved"}
                and f.get("runtime_role") != "condition"
                and not any(row.get("polarity") == "negative" for row in f.get("applicability_projection", {}).get("rows", []))}
    primary = set(fact_ids or []) & eligible
    if not eligible or (not visual_only and not primary):
        return None
    query = _subject_terms(question, bundle, requested_scope)
    if visual_only and not query:
        return None
    ranked = []
    for position, slide in enumerate(bundle.get("slides", [])):
        if slide.get("kind") in {"hero_open", "hero_close", "closing"}:
            continue
        media = slide.get("media") or ([{"image_id": slide.get("image_id"), "image_url": slide.get("image_url"), "from_line": 0}] if slide.get("image_id") else [])
        for media_position, item in enumerate(media):
            iid, url = item.get("image_id"), item.get("image_url")
            if not iid or not isinstance(url, str) or not _local_image(demo_id, url):
                continue
            if visual_only and item.get("proxy"):
                continue  # An illustration cannot prove the requested part is visible.
            for callout in slide.get("callouts", []):
                owner = callout.get("image_id") or (media[0].get("image_id") if len(media) == 1 else None)
                ids = set(callout.get("fact_ids") or [])
                if owner != iid or not ids or not ids <= eligible or (not visual_only and not ids & primary):
                    continue
                label = terms(callout.get("text", "") + " " + callout.get("part", ""))
                overlap = len(query & label)
                # Slide/topic words break ties but cannot make an unrelated photo eligible.
                # Only this picture's reviewed physical tags can complete a
                # caption's subject. A broad slide title must not license a
                # different row/feature shown by another picture on the slide.
                # Shared physical tags may complete a container noun ('display')
                # but never donate another feature's qualifier or row identity
                # to this caption. The pointer still belongs to this caption.
                parts = terms(" ".join(str(part.get("name", "")) for part in item.get("image_parts", []))) & _PHOTO_NOUNS
                if visual_only and not _literal_subject(query, label, parts):
                    continue
                topic_overlap = len(query & terms(slide.get("title", "") + " " + " ".join(slide.get("topics", []))))
                score = (overlap, topic_overlap, len(ids & primary),
                         not bool(item.get("proxy")), bool(callout.get("anchor")), slide.get("id") == current_id,
                         -position, -media_position)
                ranked.append((score, slide, item, callout))
    if not ranked:
        return None
    _, slide, item, callout = max(ranked, key=lambda row: row[0])
    sid = slide["id"]
    return {"slide_id": sid, "route": "stay" if sid == current_id else "jump",
            "callout_id": callout["id"], "by": "published_visual",
            "visual": {"kind": "image", "ref": item["image_id"], "url": item["image_url"],
                       "focus": callout.get("part") or callout.get("text", ""),
                       "line_index": max(0, int(callout.get("reveal_on_line") or item.get("from_line") or 0)),
                       "snapshot_id": snapshot_id, "demo_version": demo_version}}


def attach(state: dict, result: dict, bundle: dict) -> None:
    """Attach a fresh selection to both model answers and reviewed FAQ hits."""
    if (not result.get("answered") or result.get("clarifying_question")
            or any(result.get(key) for key in ("provider_failed", "reasoning_failed", "repair_failed", "timed_out"))):
        return
    if (bundle.get("knowledge_snapshot_id") != state.get("snapshot_id")
            or bundle.get("version") != state.get("demo_version")):
        result.update(visual=None, slide_id=state.get("slide_id"), route="none", callout_id=None, by="")
        if result.get("visual_only"):
            result.update(answer="I don't have a reviewed image for that request in this demo.", answered=False)
        return
    selected = select(state["demo_id"], bundle, snapshot_id=state.get("snapshot_id", ""),
                      demo_version=state.get("demo_version"), question=state.get("question", ""),
                      current_id=state.get("slide_id"), evidence=state.get("evidence", []),
                      fact_ids=result.get("fact_ids", []), visual_only=bool(result.get("visual_only")),
                      requested_scope=state.get("requested_scope"))
    result["visual"] = None  # Never trust an old cached image after selection changes.
    if selected:
        result.update(selected)
    elif result.get("visual_only"):
        result.update(answer="I don't have a reviewed image for that request in this demo.", answered=False,
                      slide_id=state.get("slide_id"), route="none", callout_id=None, by="")
    elif any(f.get("id") in result.get("fact_ids", [])
             and any(row.get("polarity") == "negative" for row in f.get("applicability_projection", {}).get("rows", []))
             for f in state.get("evidence", [])):
        # The older fact-ID-only slide router cannot distinguish an exclusion
        # on Base from a positive photo for Premium sharing that assertion ID.
        result.update(slide_id=state.get("slide_id"), route="none", callout_id=None, by="")
