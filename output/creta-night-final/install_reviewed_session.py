"""Default: isolated dry run. --render-publish is a separate, one-shot paid step.

No planner/author/FAQ/rehearsal/image model runs. Complete candidates need the
production schemas/validators because Align PATCH edits cannot insert/reorder
their lines and segments. A hash-bound six-card receipt is required for live use.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
import shutil
import socket
import sys
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.environ["CLOUD_SYNC"] = "0"
os.environ["STORAGE_BACKEND"] = "local"
from server import config, knowledge, orchestrator, schemas, store, usage
from server.agents import author, bundle, deck, speech_style, voice

DID = "dm_41513908"
SID = "kb_2d616ba1bcec1469e8c7ab40"
PLAN = OUT / "plan.session.json"
SCRIPT = OUT / "script.session.json"
REAL_DATA = ROOT / "data/demos"
# Session-authored, reviewed labels. Qualifiers fit intact; unseen functions and
# compound/count claims stay in the panel rather than acquiring a guessed box.
REVIEWED_CALLOUTS = {
    "creta-cabin-intro": [("Panoramic roof · selected trims", ["F247"], "sunroof", 0)],
    "cabin-comfort-proof": [("Panoramic roof · selected trims", ["F247"], "sunroof", 0),
                            ("Ventilated front seats · selected trims", ["F063"], "", 0)],
    "seating-and-cargo": [("Split rear seat", ["F096"], "rear seat", 0)],
    "driver-cockpit-tech": [("Two displays · selected trims", ["F162", "F165"], "", 0)],
    "standard-safety-suite": [("Six airbags as standard", ["F237"], "", 0)],
    "convenience-features": [("Bose audio · selected trims", ["F164"], "", 0)],
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

def protected_hashes(base):
    files = [base / "understanding.json"]
    for name in ("sources", "knowledge/snapshots", "knowledge/sources"):
        folder = base / name
        files += [p for p in folder.rglob("*") if p.is_file()] if folder.exists() else []
    return {str(p.relative_to(base)): sha(p) for p in files}

def runtime_candidate():
    old = store.read_json(DID, "script.json")
    sc = schemas.ScriptOut.model_validate_json(SCRIPT.read_text()).model_dump()
    und = store.read_json(DID, "understanding.json")
    issues = author.validate(sc, und, store.load(DID)["settings"].get("audience", "everyday"))
    if issues:
        raise ValueError(issues)
    author._assign_ids(sc)
    sc.update(version=int(old.get("version", 0)) + 1, issues=[], intake_audio={"q1": None, "q2": None})
    for seg in sc["segments"]:
        seg["checkin_audio"] = None
    for line in all_lines(sc):
        line["audio"] = None
    sc["content_hash"] = digest(schemas.ScriptOut.model_validate_json(SCRIPT.read_text()).model_dump())
    schemas.Script.model_validate(sc)
    author.timeline(sc)
    return sc

def all_lines(sc):
    return [l for s in sc["segments"] for l in s["lines"] + s.get("deeper", [])] + sc["closing"] + [sc["runtime_overview"]]

def speech_items(sc):
    rows = [(l["id"], l["text"], l.get("delivery")) for l in all_lines(sc) if not l.get("unverified")]
    rows += [(s["id"] + "-checkin", s["checkin"], None) for s in sc["segments"] if s.get("checkin")]
    rows += [("intake-q1", sc["intake_q1"], None)]
    rows += [("faq-" + e["id"], e["answer"], None) for e in (store.read_json(DID, "faq.json") or {}).get("entries", []) if e.get("answer")]
    rows += [("filler-" + k, t, None) for k, t in voice.FILLERS.items() if t]
    return rows

def estimate(sc, plan):
    demo = store.load(DID)
    original_read = store.read_json
    def candidate_read(did, name, *args, **kwargs):
        return plan if did == DID and name == "plan.json" else original_read(did, name, *args, **kwargs)
    rows = []
    with patch.object(store, "read_json", side_effect=candidate_read):
        for identifier, text, delivery in speech_items(sc):
            normalized = speech_style.prepare(text, delivery)["text"]
            cached = voice._cached(DID, text, demo, delivery=delivery)
            rows.append({"id": identifier, "characters": len(normalized), "cached": bool(cached), "cache_path": cached})
    chars = sum(row["characters"] for row in rows if not row["cached"])
    rate = usage.PRICES["sarvam-tts"]["per_1k_chars_inr"]
    return {"clip_count": len(rows), "cached_clip_count": sum(row["cached"] for row in rows),
            "new_clip_count": sum(not row["cached"] for row in rows), "new_characters": chars,
            "configured_inr_per_1000_characters": rate, "configured_inr_per_usd": usage.FX_INR,
            "estimated_usd": round(chars / 1000 * rate / usage.FX_INR, 6),
            "basis": "Configured usage-tracker estimate, not a fresh provider quote; excludes retry charges and the separate live stress session.",
            "clips": rows}

def install(plan, sc, emit):
    # Match Align's invalidation semantics without its partial-edit limitations.
    store.write_json(DID, "plan.json", plan)
    store.write_json(DID, "script.json", sc)
    orchestrator.invalidate(DID, "plan")
    orchestrator.set_stage(DID, "plan", "done", message="Reviewed session outline installed; no generation call")
    orchestrator.set_stage(DID, "author", "done", message="Reviewed session script installed and validated; audio cleared")
    store.update(DID, lambda d: d["approvals"].update({c: False for c in store.CARDS}))

    # Old overrides use positional slide IDs; reordered proof blocks must never
    # inherit an old safety image/title/callout at the new cockpit's position.
    store.write_json(DID, "deck-overrides.json", {"slides": []})
    with patch.object(config, "MOCK_LLM", True):
        de = deck.build(DID, emit)
    de["method"] = "derived; reviewed session image plan"
    plans = {s["id"]: s for s in plan["segments"]}
    und = store.read_json(DID, "understanding.json")
    demo = store.load(DID)
    images = {i["id"]: i for i in und["images"] if store.visual_allowed(demo, i["source_id"])}
    allowed = {f["id"] for f in und["facts"] if f.get("approved", True)}
    overrides = []
    for slide in de["slides"]:
        planned = plans.get(slide.get("segment_id"))
        if planned:
            refs = [r for r in planned.get("visual_refs", []) if r in images]
            slide["image_id"] = refs[0] if refs else None
            slide["image_reason"] = "reviewed Planner subject; contextual image where literal detail is unavailable"
            slide["title"] = next(s["title"] for s in sc["segments"] if s["id"] == planned["id"])
            if author.words(slide["title"]) > deck.MAX_TITLE_WORDS:
                raise ValueError("Reviewed title exceeds deck budget")
            raw = [{"text": text, "fact_ids": ids, "part": part, "reveal_on_line": index}
                   for text, ids, part, index in REVIEWED_CALLOUTS.get(planned["id"], [])]
            for callout in raw:
                if not set(callout["fact_ids"]) <= set(slide["lines"][callout["reveal_on_line"]]["fact_ids"]):
                    raise ValueError("A reviewed callout no longer matches its spoken line")
            slide["callouts"] = deck.clean_callouts(raw, slide, allowed, images.get(slide["image_id"]))
            if len(slide["callouts"]) != len(raw):
                raise ValueError("A reviewed callout was rejected by the production validator")
            for n, callout in enumerate(slide["callouts"], 1):
                callout["id"] = f"{slide['id']}-reviewed-{n}"
            deck.place_callouts(slide, images.get(slide["image_id"]))
        overrides.append({"slide_id": slide["id"], "title": slide["title"], "image_id": slide["image_id"],
                          "callouts": [{k: c[k] for k in ("id", "text", "fact_ids", "part", "reveal_on_line")} for c in slide["callouts"]]})
    schemas.Deck.model_validate(de)
    store.write_json(DID, "deck.json", de)
    store.write_json(DID, "deck-overrides.json", {"slides": overrides})
    emit(f"Reviewed on-screen layer: {sum(len(s['callouts']) for s in de['slides'])} cited callouts; exact planned images and titles applied.")
    orchestrator.set_stage(DID, "deck", "done", message="Deterministic layout of reviewed script and image plan; no model calls")
    bank = store.read_json(DID, "faq.json") or {}
    for entry in bank.get("entries", []):
        if set(entry.get("fact_ids", [])) - allowed:
            raise ValueError("FAQ contains an unapproved citation")
        # Same routing function as faq.run; old positional slide IDs must not
        # jump into a reordered segment with an unrelated subject.
        entry["slide_id"] = deck.slide_for(de["slides"], entry.get("fact_ids"), entry.get("question", ""))[0]
        entry["audio"] = None
    store.write_json(DID, "faq.json", bank)
    store.write_json(DID, "fillers.json", {k: {"text": text, "audio": None} for k, text in voice.FILLERS.items()})
    return de

def require_matching_voice():
    sc, demo = store.read_json(DID, "script.json"), store.load(DID)
    if not demo["settings"].get("voice_locked") or sc.get("voice_provider") != "sarvam" or sc.get("voice_name") != "priya":
        raise RuntimeError("Publication requires the locked Sarvam/Priya voice")
    assigned = {l["id"]: l.get("audio") for l in all_lines(sc)}
    assigned.update({s["id"] + "-checkin": s.get("checkin_audio") for s in sc["segments"] if s.get("checkin")})
    assigned["intake-q1"] = sc.get("intake_audio", {}).get("q1")
    assigned.update({"faq-" + e["id"]: e.get("audio") for e in (store.read_json(DID, "faq.json") or {}).get("entries", []) if e.get("answer")})
    assigned.update({"filler-" + k: e.get("audio") for k, e in (store.read_json(DID, "fillers.json") or {}).items()})
    bad = [identifier for identifier, text, delivery in speech_items(sc)
           if not assigned.get(identifier) or assigned[identifier] != voice._cached(DID, text, demo, delivery=delivery)]
    if bad or sc.get("voice_input_hash") != voice.input_hash(DID):
        raise RuntimeError("Missing or mismatched current-content audio: " + ", ".join(bad))
    if sc.get("voice_failures"):
        raise RuntimeError("Voice stage recorded failures; publication withheld")
    overview = sc["runtime_overview"]
    if not overview.get("duration_exact") or not overview.get("duration_in_range"):
        raise RuntimeError("Recorded overview must actually meet the 10–15 second target; no automatic retry")

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-publish", action="store_true")
    parser.add_argument("--review-receipt", type=Path)
    args = parser.parse_args()
    live = args.render_publish
    base = REAL_DATA / DID
    original_bundle_sha = sha(base / "bundle.json")
    old_bundle = json.loads((base / "bundle.json").read_text())
    if old_bundle["version"] != 7 or old_bundle["knowledge_snapshot_id"] != SID:
        raise RuntimeError("Expected immutable reviewed v7 baseline; refusing changed publication")
    plan = schemas.Plan.model_validate_json(PLAN.read_text()).model_dump()
    plan["voice_sample_audio"] = None
    if plan["voice"]["suggested_voice"] != "priya":
        raise RuntimeError("Candidate changed the locked voice")
    before = protected_hashes(base)
    manifest = {"plan_sha256": sha(PLAN), "script_sha256": sha(SCRIPT), "baseline_bundle_sha256": original_bundle_sha,
                "baseline_faq_sha256": sha(base / "faq.json"),
                "knowledge_snapshot_id": SID, "baseline_version": 7, "new_version": 8}
    messages = []
    def emit(message):
        messages.append(str(message)); print(message, flush=True)
    blocked_calls = []
    def blocked(*a, **kw):
        blocked_calls.append(True); raise AssertionError("No network permitted in deterministic integration")
    with ExitStack() as stack:
        if not live:
            sandbox = Path(tempfile.mkdtemp(prefix="session-dry-run-", dir=OUT))
            clone = sandbox / "demos" / DID
            clone.mkdir(parents=True)
            for p in base.glob("*.json"):
                shutil.copy2(p, clone / p.name)
            shutil.copytree(base / "knowledge", clone / "knowledge")
            # Read-only source/cache references; no generation or media writes
            # exist on the dry-run branch.
            for name in ("sources", "audio"):
                if (base / name).exists():
                    (clone / name).symlink_to(base / name, target_is_directory=True)
            stack.enter_context(patch.object(config, "DATA_DIR", sandbox / "demos"))
            for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
                stack.enter_context(patch(name, side_effect=blocked))
        else:
            if config.DATA_DIR.resolve() != REAL_DATA.resolve() or config.MOCK_LLM:
                raise RuntimeError("Live mode requires real local storage and non-mock speech")
            if not args.review_receipt:
                raise RuntimeError("Explicit reviewed six-card receipt is required")
            receipt = json.loads(args.review_receipt.read_text())
            if any(receipt.get(k) != value for k, value in manifest.items()) or not receipt.get("reviewer") or not all(receipt.get("approvals", {}).get(c) is True for c in store.CARDS):
                raise RuntimeError("Review receipt does not approve these exact candidates and v7 baseline")

        # These paths are forbidden even in the paid narration mode.
        for name in ("server.llm.claude.structured", "server.agents.deck._ask_model", "server.agents.rehearsal.run", "server.media.enhance_images"):
            stack.enter_context(patch(name, side_effect=AssertionError("No model/rehearsal/image generation in reviewed integration")))
        sc = runtime_candidate()
        cost = estimate(sc, plan)
        manifest["narration_estimate"] = cost
        save(OUT / "integration-voice-estimate.json", cost)
        if cost["estimated_usd"] > 1.50:
            raise RuntimeError("Configured narration estimate exceeds the $1.50 reserve")
        if live:
            marker = OUT / "render-publish.started.json"
            with marker.open("x") as handle:
                json.dump({"started": time.time(), **manifest}, handle, indent=2)
            backup = OUT / "before-reviewed-install"
            backup.mkdir(exist_ok=False)
            for p in base.glob("*.json"):
                shutil.copy2(p, backup / p.name)
            shutil.copytree(base / "knowledge", backup / "knowledge")
            save(backup / "protected-hashes.json", before)
            if sha(backup / "bundle.json") != original_bundle_sha:
                raise RuntimeError("Baseline backup mismatch")

        de = install(plan, sc, emit)
        manifest["deck_semantic_sha256"] = digest(orchestrator.semantic(de))
        manifest["faq_semantic_sha256"] = digest(orchestrator.semantic(store.read_json(DID, "faq.json")))
        if live and receipt.get("deck_semantic_sha256") != manifest["deck_semantic_sha256"]:
            raise RuntimeError("Deterministic deck differs from the reviewed dry-run deck; no narration or publication")
        if live and receipt.get("faq_semantic_sha256") != manifest["faq_semantic_sha256"]:
            raise RuntimeError("FAQ routing differs from reviewed dry run; no narration or publication")
        orchestrator.apply_actions(DID, [{"type": "approve", "card": c} for c in store.CARDS], [], "align")
        if not all(store.load(DID)["approvals"].get(c) for c in store.CARDS):
            raise RuntimeError("All six cards must be approved")

        if live:
            usage.current_demo.set(DID); usage.current_stage.set("voice")
            orchestrator.set_stage(DID, "voice", "running", message="One authorized matching-narration pass; no voice tests or automatic rerun")
            try:
                voice.render_script(DID, emit)
                require_matching_voice()
            except Exception as exc:
                orchestrator.set_stage(DID, "voice", "error", error=str(exc))
                if sha(base / "bundle.json") != original_bundle_sha:
                    raise AssertionError("Failed voice changed the published bundle") from exc
                raise
            orchestrator.set_stage(DID, "voice", "done", message="Exact current-content Priya clips verified")
        else:
            try:
                require_matching_voice()
            except RuntimeError as exc:
                manifest["unvoiced_publication_guard"] = str(exc)
            else:
                raise AssertionError("An unvoiced candidate unexpectedly passed publication guard")
            manifest["sandbox"] = str(sandbox)

        # The dry-run bundle is a sandbox preview only; the actual branch cannot
        # reach this point until the matching-audio guard has passed.
        built = bundle.build(DID, emit)
        assert built["version"] == 8 and built["knowledge_snapshot_id"] == SID
        assert [s["id"] for s in built["segments"]] == [s["id"] for s in sc["segments"]]
        assert [s["segment_id"] for s in built["slides"] if s.get("segment_id")] == [s["id"] for s in sc["segments"]]
        assert built["voice"]["persona"] == plan["voice"]
        manifest["bundle_sha256"] = sha(store.path(DID, "bundle.json"))
        manifest["script_version"] = sc["version"]
        manifest["deck_version"] = de["version"]
        manifest["messages"] = messages
        manifest["outbound_socket_attempts_in_dry_run"] = len(blocked_calls)
        manifest["mode"] = "published" if live else "sandbox preview, not published"
        if live:
            orchestrator.set_stage(DID, "bundle", "done", message="Reviewed session v8; immutable v7 evidence preserved")
            orchestrator._set_status(DID, "ready")
        else:
            save(OUT / "deck.session.preview.json", de)
            save(OUT / "bundle.session.preview.json", built)
            template = {**{k:manifest[k] for k in ("plan_sha256", "script_sha256", "baseline_bundle_sha256", "baseline_faq_sha256", "knowledge_snapshot_id", "baseline_version", "new_version", "deck_semantic_sha256", "faq_semantic_sha256")},
                        "reviewer": "", "approvals": {c: False for c in store.CARDS}}
            save(OUT / "integration-review.template.json", template)
        if protected_hashes(base) != before:
            raise AssertionError("Original sources, understanding or immutable knowledge snapshots changed")
        if not live and sha(base / "bundle.json") != original_bundle_sha:
            raise AssertionError("Dry run changed the published bundle")
        save(OUT / ("integration-published.json" if live else "integration-dry-run.json"), manifest)
        print(json.dumps({"mode":manifest["mode"], "version":built["version"], "estimated_voice_usd":cost["estimated_usd"], "new_clips":cost["new_clip_count"], "outbound_dry_run":len(blocked_calls)}))

if __name__ == "__main__":
    main()
