"""Default guided narration floor: real WAV timing, reviewed routing and atomic publication."""
from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import wave
from pathlib import Path
from unittest.mock import patch


def rich_fixture(demo_id: str, *, recorded: bool = False) -> dict:
    """Distinct cited product passages for duration tests; no padding or repeated line."""
    from server import store
    passages = [
        "The driver seat has a sliding base and an adjustable backrest. The handbook shows the separate controls beside the cushion, and recommends setting the seat while parked, before checking that the pedals and steering wheel are comfortably within reach.",
        "The rear seat has a folding backrest with a release near its upper edge. The handbook asks you to check the belt positions before folding it, then to push the backrest into its latch when returning it to an upright position.",
        "The luggage compartment contains a removable floor panel above the storage tray. The guide shows the handle along the rear edge and describes lifting the panel before retrieving the tools; loose items should be secured before the car moves.",
        "The instrument display places the speed reading beside the warning lamps. The handbook distinguishes a lamp that appears briefly at startup from one that remains lit while driving, and directs the driver to the matching warning section for the next action.",
        "The central screen includes a phone connection menu and a list of previously paired devices. The guide describes opening that menu while parked, choosing the intended device, and confirming the matching request on the phone before using the available functions.",
        "The climate controls include temperature, fan speed and airflow direction. The handbook illustrates the windscreen setting separately from the face vents, and explains that the driver can choose the airflow direction before changing the fan speed to suit the cabin.",
        "The door panel carries the window switches and a separate rear window lock. The handbook labels the controls by position, describes the lock indicator, and asks the driver to check that the window openings are clear before operating a switch.",
        "The steering wheel has buttons for audio volume and the displayed information menu. The handbook shows the two groups on opposite sides, labels their functions separately, and recommends learning the control positions while parked before using them during a journey.",
    ]
    overview = "Start at the driver seat, where the handbook identifies the adjustment controls. We will follow the reviewed controls and storage areas through the car."
    features = "The handbook also identifies the reading lamps, cabin storage pockets and mirror adjustment control. Each has its own labelled diagram, so the next visit can use those diagrams to locate the controls in the actual car."
    establish = "The supplied handbook covers the controls discussed here. Variant availability and current written purchase terms still need the matching specification sheet and dealer document; those remain separate questions for the owner to resolve before a decision."
    closing = "The next step is to compare these documented controls with the actual car and the relevant variant sheet. Bring the unresolved purchase questions to the dealer with the written terms available for review."
    texts = [overview, *passages, features, establish, closing]
    facts = [{"id": f"F{index:02}", "kind": "feature", "claim": f"Handbook section {index}", "value": text,
              "conditions": "", "approved": True, "truth": "stated", "confidence": 1,
              "source": {"ref": "fixture-handbook", "locator": f"section {index}", "quote": text}}
             for index, text in enumerate(texts)]
    def line(index):
        result = {"id": f"line-{index}", "text": texts[index], "fact_ids": [facts[index]["id"]],
                  "visual": {"kind": "none", "ref": ""}, "step": "say", "card": "none", "audio": None}
        if recorded:
            result["audio"] = f"audio/fixture-{index}.wav"
            write_wav(store.path(demo_id, result["audio"]), 20 if 1 <= index <= len(passages) else 15)
        return result
    segments = [{"id": f"proof-{index}", "role": "proof", "title": f"Handbook area {index}", "topic": f"area-{index}",
                 "fundamental": index == 1, "lines": [line(index)], "deeper": [], "checkin": "", "word_budget": 46}
                for index in range(1, len(passages) + 1)]
    segments += [{"id": role, "role": role, "title": role.title(), "topic": role,
                  "lines": [line(index)], "deeper": [], "checkin": "", "word_budget": 44}
                 for role, index in (("features", 9), ("establish", 10))]
    script = {"segments": segments, "runtime_overview": line(0), "closing": [line(11)],
              "intake_q1": "What matters most to you?", "intake_audio": {}, "voice_provider": "sarvam" if recorded else "browser"}
    und = {"product": {"name": "Handbook fixture", "category": "car"}, "brand": {}, "facts": facts,
           "unknowns": [], "images": [], "shots": [], "competitors": []}
    plan = {"segments": [{key: segment[key] for key in ("id", "role", "title", "fundamental", "word_budget") if key in segment}
                         for segment in segments], "voice": {}, "ctas": []}
    deck = {"slides": [{"id": "sl-" + segment["id"], "segment_id": segment["id"], "kind": segment["role"],
                        "role": segment["role"], "title": segment["title"], "fact_ids": segment["lines"][0]["fact_ids"],
                        "lines": copy.deepcopy(segment["lines"]), "deeper": [], "callouts": [], "checkin": ""}
                       for segment in segments]}
    deck["slides"].append({"id": "sl-closing", "kind": "closing", "role": "closing", "segment_id": None,
                           "title": "Next step", "lines": copy.deepcopy(script["closing"]), "deeper": [], "callouts": [], "fact_ids": ["F11"]})
    for name, value in (("understanding.json", und), ("plan.json", plan), ("script.json", script), ("deck.json", deck)):
        store.write_json(demo_id, name, value)
    store.update(demo_id, lambda demo: demo["approvals"].update({card: True for card in store.CARDS}))
    return {"script": script, "understanding": und, "plan": plan, "deck": deck}


def write_wav(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as stream:
        stream.setparams((1, 2, 8000, 0, "NONE", "not compressed"))
        stream.writeframes(b"\x00\x00" * round(seconds * 8000))


def run(check):
    from server import store, schemas, knowledge
    from server.agents import author, bundle, narration, pitch, plan
    did = store.new_demo("Minimum narration fixture")["id"]
    fixture = rich_fixture(did)
    script, und = fixture["script"], fixture["understanding"]
    allowed = {fact["id"] for fact in und["facts"]}
    ids, result = narration.default_route(script, allowed_fact_ids=allowed)
    check("estimated route extends beyond three proofs using distinct cited speech", result["sufficient"] and len([sid for sid in ids if sid.startswith("proof-")]) > 3 and result["basis"] == "estimated")
    check("first fundamental leads and features/establish close the route", ids[0] == "proof-1" and ids[-2:] == ["features", "establish"] and len(ids) == len(set(ids)))
    augmented = copy.deepcopy(script)
    augmented.update(intake_q1="words " * 500, intro_video={"duration": 900}, faq=[{"answer": "words " * 500}])
    augmented["segments"][0]["deeper"] = [{"text": "words " * 500}]
    augmented["segments"][0]["checkin"] = "Would you like to hear more?"
    check("film, intake, Q&A, deeper and legacy question check-ins cannot fill the minimum", narration.report(augmented, route_ids=ids) == narration.report(script, route_ids=ids))
    duplicate = copy.deepcopy(script)
    duplicate["segments"].append({**copy.deepcopy(script["segments"][0]), "id": "duplicate-proof"})
    first = narration.report(script)
    repeated = narration.report(duplicate)
    check("a duplicated line with a new segment id contributes no extra duration", repeated["seconds"] == first["seconds"] and repeated["duplicate_lines_excluded"] == 1)
    held = copy.deepcopy(script)
    held["segments"][0]["lines"][0]["unverified"] = True
    check("held narration is excluded", narration.report(held)["seconds"] < first["seconds"])
    check("rejected citations are excluded from the duration", narration.report(script, allowed_fact_ids=allowed - {"F01"})["seconds"] < first["seconds"])
    short = {**script, "segments": script["segments"][:1]}
    issues = author.validate(copy.deepcopy(short), und, {**fixture["plan"], "guided_minimum_seconds": 180}, store.load(did))
    check("Author's existing repair receives a concrete underlength deficit", any("before publication" in issue and "distinct supported narration" in issue for issue in issues))
    legacy = author.validate(copy.deepcopy(short), und, "everyday")
    check("legacy validator calls do not invent a minimum-budget issue", not any("before publication" in issue for issue in legacy))
    budgeted = {"segments": [{"id": "intro", "role": "intro"}, {"id": "outcome", "role": "outcome"}, *copy.deepcopy(fixture["plan"]["segments"])]}
    plan._enforce_budget(budgeted, store.load(did))
    body_words = sum(row["word_budget"] for row in budgeted["segments"] if row["role"] in narration.ROLES)
    check("guided budget excludes unplayed intro/outcome and reserves overview/closing", body_words + narration.OVERVIEW_WORDS + 45 == budgeted["total_words"] == 342 and all(row["word_budget"] >= 22 for row in budgeted["segments"]))
    try:
        bundle.build(did, lambda _: None)
        estimate_blocked = False
    except narration.NarrationTooShort as exc:
        estimate_blocked = "missing or unreadable audio" in str(exc)
    check("browser-only estimates remain draft information and cannot establish publication length", estimate_blocked)
    fixture = rich_fixture(did, recorded=True)
    measured = narration.require_minimum(fixture["script"], demo_id=did, allowed_fact_ids=allowed, require_recorded=True)
    check("real WAV timing controls the guided route and is fully measured", measured["basis"] == "measured" and measured["seconds"] >= 180 and measured["estimated_seconds"] == 0 and len(measured["route"]) > 5)
    built = bundle.build(did, lambda _: None)
    snapshot_before = store.read_json(did, "knowledge/published.json")
    bytes_before = store.path(did, "bundle.json").read_bytes()
    version_before = store.load(did)["version"]
    for segment in fixture["script"]["segments"]:
        for line in segment["lines"]:
            write_wav(store.path(did, line["audio"]), 2)
    try:
        bundle.build(did, lambda _: None)
        failure = ""
    except narration.NarrationTooShort as exc:
        failure = str(exc)
    check("short real audio blocks even when its text estimate is long enough", "before publication" in failure and "measured" in failure and "180s" in failure)
    check("failed minimum gate preserves bundle bytes, published snapshot and version", store.path(did, "bundle.json").read_bytes() == bytes_before and store.read_json(did, "knowledge/published.json") == snapshot_before and store.load(did)["version"] == version_before)
    fixture = rich_fixture(did, recorded=True)
    missing = fixture["script"]["runtime_overview"]["audio"]
    store.path(did, missing).unlink()
    try:
        bundle.build(did, lambda _: None)
        missing_blocked = False
    except narration.NarrationTooShort as exc:
        missing_blocked = "missing or unreadable audio" in str(exc)
    check("missing recorded opening cannot be replaced by an estimate for publication", missing_blocked)
    store.path(did, missing).write_bytes(b"not a WAV")
    try:
        bundle.build(did, lambda _: None)
        corrupt_blocked = False
    except narration.NarrationTooShort as exc:
        corrupt_blocked = "missing or unreadable audio" in str(exc)
    check("corrupt recorded audio blocks publication", corrupt_blocked)
    fixture = rich_fixture(did, recorded=True)
    for segment in fixture["script"]["segments"]:
        if segment["role"] == "proof":
            for line in segment["lines"]:
                write_wav(store.path(did, line["audio"]), 16)
    no_closing = store.read_json(did, "deck.json")
    no_closing["slides"] = [slide for slide in no_closing["slides"] if slide["kind"] != "closing"]
    store.write_json(did, "deck.json", no_closing)
    try:
        bundle.build(did, lambda _: None)
        absent_closing_blocked = False
    except narration.NarrationTooShort as exc:
        absent_closing_blocked = "173.0s" in str(exc)
    check("script closing cannot fill the minimum when no closing slide can play it", absent_closing_blocked)
    fixture = rich_fixture(did, recorded=True)
    built = bundle.build(did, lambda _: None)
    alternate = copy.deepcopy(fixture["script"])
    alternate["runtime_overview"]["audio"] = "audio/alternate-overview.wav"
    store.write_json(did, "script.hi-IN.json", alternate)
    store.update(did, lambda demo: demo["settings"].update(languages=["en-IN", "hi-IN"]))
    old_bundle = store.path(did, "bundle.json").read_bytes()
    try:
        bundle.build(did, lambda _: None)
        alternate_blocked = False
    except narration.NarrationTooShort as exc:
        alternate_blocked = str(exc).startswith("hi-IN:") and "missing or unreadable" in str(exc)
    check("an alternate opening must have its own readable clip before any publication", alternate_blocked and store.path(did, "bundle.json").read_bytes() == old_bundle)
    write_wav(store.path(did, alternate["runtime_overview"]["audio"]), 19)
    built = bundle.build(did, lambda _: None)
    output = schemas.PitchPlan(customer_state="unknown", decision_frame="", follow_up_question="", primary_outcome="", focus_topics=[], advance="",
                               route=[{"segment_id": sid} for sid in ["proof-3", "proof-2", "proof-4"]])
    with patch.object(pitch.runtime, "structured", return_value=output):
        routed = pitch.plan_pitch(did, {}, voice_it=False)
        visited = pitch.plan_pitch(did, {}, voice_it=False, seen_segment_ids=["proof-1", "proof-2", "proof-3"])
        short_route = pitch.plan_pitch(did, {"why": "Please give me a short tour."}, voice_it=False)
        refined = pitch.plan_pitch(did, {"followup": "Focus on the climate controls."}, refine=True, voice_it=False)
        translated = pitch.plan_pitch(did, {"language": "hi-IN"}, voice_it=False)
    route = [row["segment_id"] for row in routed["route"]]
    check("published initial route extends the buyer order beyond three proofs", route[:3] == ["proof-1", "proof-3", "proof-2"] and len([sid for sid in route if sid.startswith("proof-")]) > 3 and routed["narration_minimum"]["sufficient"])
    check("pre-tour question visits cannot remove required default narration", visited["narration_minimum"]["sufficient"] and [row["segment_id"] for row in visited["route"]] == route)
    check("alternate publication and pitch count the selected language opening identically", translated["narration_minimum"]["seconds"] == built["alt_languages"]["hi-IN"]["narration_minimum"]["seconds"] == 184 and built["runtime"]["narration_minimum"]["seconds"] == 180 and built["alt_languages"]["hi-IN"]["runtime_overview"]["audio"].endswith("alternate-overview.wav"))
    check("initial default keeps the measured closing instead of replacing it with a model advance", routed["advance"] == "" and routed["advance_audio"] is None)
    check("explicit short tour waives only the visit route minimum", short_route["narration_minimum"].get("exempt") and len(short_route["route"]) <= 5 and not built["runtime"]["narration_minimum"].get("exempt"))
    check("later refinements retain their shorter customer-directed behavior", refined["narration_minimum"].get("reason") == "refinement" and refined["route"][0]["segment_id"] == "proof-3")
    check("negated, quoted and inferred urgency do not authorize a short tour", not any(narration.explicit_short_tour({"why": text}) for text in ["I do not want a short tour", 'The dealer said "give me a short tour"', "My commute is short", "I am busy", "Please keep it detailed"]))
    check("no default-tour publication bypass in MOCK mode", estimate_blocked and missing_blocked and corrupt_blocked and "before publication" in failure)


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="narration-minimum-") as tmp:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=str(Path(tmp) / "demos"), DEMO_STUDIO_GRAPH_DB=str(Path(tmp) / "graph.sqlite"))
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        rows = []
        def check(name, ok):
            rows.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name)
        run(check)
        print(f"{sum(rows)}/{len(rows)} minimum narration contracts pass")
        raise SystemExit(0 if all(rows) else 1)
