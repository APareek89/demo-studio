"""Private copies of reviewed examples; no customer history or provider calls."""
from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from pathlib import Path
import shutil
import wave

from . import config, store
from .agents import bundle


def is_cached_only(demo_id: str) -> bool:
    """The server-created record, never a request field, controls free playback."""
    return store.load(demo_id).get("example_kind") in {"synthetic_silent", "curated_cached"}


def public_bundle(demo_id: str, published: dict) -> dict:
    result = copy.deepcopy(published)
    silent = store.load(demo_id).get("example_kind") == "synthetic_silent"
    result["example"] = {"cached_only": True, "silent": silent,
                         "label": "Synthetic silent preview" if silent else "Cached example · free to explore"}
    result.setdefault("runtime", {}).update(continuous_voice=False, tools=[])
    result["ctas"] = []  # A portfolio example never books or collects sales leads.
    return result


def cached_audio(demo_id: str, text: str) -> str | None:
    """Only exact authored speech in the published bundle can resolve audio."""
    published = store.read_json(demo_id, "bundle.json") or {}
    prefix = f"/media/{demo_id}/"
    def find(value):
        if isinstance(value, dict):
            if value.get("text") == text and isinstance(value.get("audio"), str):
                url = value["audio"]
                if url.startswith(prefix + "audio/") and re.fullmatch(r"audio/[a-f0-9]{20}\.(wav|mp3|m4a)", url[len(prefix):]):
                    return url
            for child in value.values():
                found = find(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = find(child)
                if found:
                    return found
        return None
    return find(published)


def cached_answer(demo_id: str, question: str, slide_id: str | None = None) -> dict:
    """Select reviewed answers or literal published evidence without model calls."""
    from .agents import deck, faq
    published = store.read_json(demo_id, "bundle.json") or {}
    facts = {f["id"]: f for f in published.get("facts", [])}
    hit = faq.match(demo_id, question, snapshot_id=published.get("knowledge_snapshot_id"))
    if hit and set(hit.get("fact_ids", [])) <= facts.keys():
        text, ids = hit["answer"], hit.get("fact_ids", [])
    else:
        # Conservative keyword overlap retrieves literal evidence; no paraphrase
        # or claim about understanding an unseen question is generated.
        product_words = faq._tokens(published.get("product", {}).get("name", ""))
        words = faq._tokens(question) - product_words - {"use", "using", "used", "work"}
        def rank(fact):
            claim = faq._tokens(fact.get("claim", "")) - product_words
            claim_hits = len(words & claim)
            context = faq._tokens(str(fact.get("value", "")) + " " + str(fact.get("conditions", "")))
            return (claim_hits / max(1, len(claim)), claim_hits, len(words & (claim | context)))
        fact = max(facts.values(), key=rank, default={})
        exact_claim, claim_hits, total_hits = rank(fact)
        if (claim_hits and total_hits / max(1, len(words)) >= .5) or total_hits >= 2:
            text = "From the prepared source: " + str(fact.get("claim", ""))
            value, conditions = str(fact.get("value") or ""), str(fact.get("conditions") or "")
            if value and value not in text:
                text += " — " + value
            if conditions and conditions not in text:
                text += ". " + conditions
            ids = [fact["id"]]
        else:
            text, ids = "This free example uses prepared content. Explore its slides or ask about a visible feature; a new answer is not generated here.", []
    result = {"answer": text, "fact_ids": ids, "facts": [facts[fid] for fid in ids],
              "answered": bool(ids), "from_bank": True, "cached_only": True,
              "audio": cached_audio(demo_id, text), "offer_callback": False,
              "clarifying_question": "", "escalate": "", "topic": "", "cta": ""}
    result.update(deck.route_for(published.get("slides", []), slide_id, ids, question) if ids
                  else {"slide_id": slide_id, "route": "none", "callout_id": None, "by": ""})
    return result


def cached_pitch(demo_id: str) -> dict:
    published = store.read_json(demo_id, "bundle.json") or {}
    route = published.get("runtime", {}).get("narration_minimum", {}).get("route", [])
    return {"customer_state": "unknown", "decision_frame": "Prepared example route",
            "follow_up_question": "", "primary_outcome": "Explore the prepared demonstration",
            "focus_topics": [], "route": [{"segment_id": sid, "bridge": "", "bridge_fact_ids": []} for sid in route],
            "skipped": [], "usp_order": [], "advance": "Review your visit", "advance_cta": "",
            "custom_batches": [], "personalized_segments": [], "cached_only": True}


def cached_summary(demo_id: str, session: dict) -> dict:
    return {"customer_name": (session.get("profile") or {}).get("name", ""),
            "context": "A visit to the free prepared example; no AI summary was generated.",
            "cared_about": [], "objections": [], "unanswered": list(session.get("unresolved", [])),
            "opening_line": "", "questions_asked": list(session.get("questions", [])),
            "slides_visited": list(session.get("slides_visited", [])), "cta_result": session.get("cta", ""),
            "leads": [], "minutes": session.get("minutes"), "model": "none-cached-example",
            "generated_at": time.time(), "transcript_lines": len(session.get("transcript", []))}


def create_example(owner_user_id: str | None, *, synthetic: bool = False) -> dict:
    source = config.ROOT / ("samples/portfolio-example" if synthetic else "samples/bmw-example")
    template = json.loads((source / "template.json").read_text())
    # Validate every committed asset before reserving a new creator-owned record.
    for rel, expected in template["assets"].items():
        asset = source / rel
        if (Path(rel).is_absolute() or ".." in Path(rel).parts or asset.is_symlink()
                or hashlib.sha256(asset.read_bytes()).hexdigest() != expected):
            raise RuntimeError("The example assets could not be verified")
    demo = store.new_demo(template["metadata"].get("name", "Example handbook · silent preview"), owner_user_id=owner_user_id)
    did = demo["id"]
    old_prefix, new_prefix = f"/media/{template['source_demo_id']}/", f"/media/{did}/"
    def rebind(value):
        if isinstance(value, str):
            return new_prefix + value[len(old_prefix):] if value.startswith(old_prefix) else value
        if isinstance(value, dict):
            return {key:rebind(item) for key,item in value.items()}
        if isinstance(value, list):
            return [rebind(item) for item in value]
        return value
    for rel in template["assets"]:
        target = store.path(did, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / rel, target)
    for rel, audio in template.get("silent_audio", {}).items():
        target = store.path(did, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(target), "wb") as recording:
            recording.setnchannels(audio["channels"])
            recording.setsampwidth(audio["width"])
            recording.setframerate(audio["rate"])
            remaining = audio["frames"] * audio["channels"] * audio["width"]
            while remaining:
                length = min(remaining, 65536)
                recording.writeframesraw(bytes(length))
                remaining -= length
    for name, value in template["artifacts"].items():
        store.write_json(did, name, rebind(copy.deepcopy(value)))
    def prepared(record):
        record.update(rebind(copy.deepcopy(template["metadata"])))
        record["example_kind"] = "synthetic_silent" if synthetic else "curated_cached"
        record["approvals"] = {card:True for card in store.CARDS}
        record["status"] = "align"
        record["running"] = None
        for stage in ("understand", "coach", "plan", "author", "deck", "faq", "voice"):
            record["stages"][stage] = {"status":"done", "error":None}
    store.update(did, prepared)
    # Do not copy an old bundle, snapshot, session or publication registry row.
    # This deterministic stage enforces normal approval and measured-WAV gates.
    bundle.build(did, lambda _message: None)
    store.update(did, lambda record: record.update(status="ready", running=None))
    return store.load(did)
