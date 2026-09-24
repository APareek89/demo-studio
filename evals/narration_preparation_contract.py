"""Free preparation contracts: actual Plan/Author repair, supported words and recorded pacing."""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
import wave
from unittest.mock import patch

_TEMP = tempfile.TemporaryDirectory(prefix="narration-preparation-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=_TEMP.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_TEMP.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []
def blocked(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Preparation tests must not use outbound services")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
from server import schemas, store
from server.agents import author, bundle, deck, narration, pitch, plan, voice
from server.llm import mock

passages = [
"The front seat slides backwards and forwards on a floor rail, while its backrest adjusts separately. These two controls let the driver change the seat position without having to move the backrest at the same time.",
"The steering column adjusts for height and reach. Its locking lever sits below the wheel, so the driver can set the wheel position after moving the seat and then secure the column before setting off.",
"The rear bench folds in two sections. Either section can be lowered independently, leaving part of the rear bench upright when a longer item needs the extra loading space behind the front seats.",
"The luggage floor has a removable panel above a storage tray. Smaller loose items can sit below that panel, leaving the upper loading surface available for larger bags when the rear seats remain upright.",
"The centre console contains an open tray ahead of the gear selector. A separate covered compartment sits beneath the armrest, with its lid opening from the front edge to reveal the storage space inside.",
"The front doors each contain a lower storage pocket, and the dashboard has a covered glove compartment. These are separate spaces around the front row, so the driver and passenger can reach their respective door pockets.",
"The roof opening has an interior shade that moves separately from the glass. Keeping the glass closed while moving the shade changes whether the opening is covered from inside the cabin.",
"The rear cabin has its own air outlets behind the centre console. Their direction can be adjusted at the outlet, placing that control within reach of passengers sitting on the rear bench.",
"The charging area includes a socket beside the front storage tray. The socket has a protective cover, which opens to expose the connection and closes again when the socket is not being used.",
"The rear reading lights have individual switches beside the lamps. A passenger can operate one reading light without reaching for the front lighting controls, while the other rear reading light remains independently controlled.",
"The equipment guide separates standard equipment from options, with each option listed against its applicable trim. Confirm the selected trim before treating an optional item as part of the vehicle being discussed.",
"The delivery checklist records the chosen trim and any selected accessories. Compare those entries with the order before confirming delivery, keeping any unresolved equipment question attached to that written checklist.",
]

passages.append("Head restraints adjust separately from the backrest. Individual release buttons sit beside the support posts, and the restraints can be raised or lowered before the seat is occupied.")
OVERVIEW = "Start at the seat: its sliding base, adjustable backrest and movable steering column give separate controls for setting the driving position before departure."
CLOSING = "Use the written equipment list and selected trim as the basis for the next conversation. The dealer can confirm the order details, show the listed controls and resolve any remaining equipment question before you choose whether to arrange a visit with the dealer or proceed."

def line(text, fid):
    return {"text": text, "fact_ids": [fid], "visual": {"kind": "none", "ref": "", "focus": ""}, "step": "say"}

def fixture():
    facts = [{"id": f"F{i}", "kind": "feature", "claim": text.split(".")[0], "value": text,
              "approved": True, "source": {"ref": "fixture-guide", "locator": f"paragraph {i}", "quote": text}}
             for i, text in enumerate([*passages, OVERVIEW, CLOSING])]
    p = mock.fake(schemas.Plan).model_dump()
    groups = [("seat", "proof", [0, 1, 12]), ("loading", "proof", [2, 3]),
              ("storage", "proof", [4, 5]), ("cabin", "proof", [6, 7]),
              ("details", "features", [8, 9]), ("confirm", "establish", [10, 11])]
    p["segments"] = []
    for sid, role, ids in [("intro", "intro", [13]), ("outcome", "outcome", [14]), *groups]:
        p["segments"].append({"id": sid, "title": sid.title(), "role": role, "topic": sid,
                              "goal": "Use the distinct assigned equipment descriptions and retain their conditions.",
                              "outcome": "Inspect the listed equipment", "fact_ids": [f"F{i}" for i in ids],
                              "visual_refs": [], "usp_ids": [], "priority_topic": role == "proof",
                              "word_budget": sum(author.words(facts[i]["value"]) for i in ids), "fundamental": sid == "seat"})
    for usp in p["usps"]:
        usp["fact_ids"] = ["F0"]
    p["concerns"] = []
    p["ctas"] = [{"id": "contact", "label": "Ask the dealer", "kind": "contact", "url": "", "primary": True}]
    return {"product": {"name": "Fixture car"}, "brand": {}, "facts": facts, "shots": [], "images": [], "unknowns": []}, p

def draft(p, facts, *, complete):
    indexed = {fact["id"]: fact for fact in facts}
    segments = []
    for seg in p["segments"]:
        ids = seg["fact_ids"] if complete else seg["fact_ids"][:1]
        if seg["role"] in {"intro", "outcome"}:
            text = ("The seat and steering controls can be adjusted separately before departure, so begin by looking at where each control sits around the driver." if seg["role"] == "intro" else "The equipment list and chosen trim provide the written reference for the conversation. Keep unresolved equipment questions attached to that list, and ask the dealer to confirm them before arranging a further visit or proceeding.")
            lines = [line(text, ids[0])]
        else:
            lines = [line(indexed[fid]["value"], fid) for fid in ids]
        segments.append({**{k: seg[k] for k in ("id", "title", "role", "topic")},
                         "lines": lines, "deeper": [], "checkin": ""})
    return {"overview": line(OVERVIEW, "F13"), "segments": segments, "closing": [line(CLOSING, "F14")],
            "intake_q1": "Welcome. What matters most?", "intake_q2": ""}

def record(did, script, *, wps=2.5, prefix="test"):
    rows = [script.get("runtime_overview") or script.get("overview")]
    rows += [ln for seg in script["segments"] for ln in seg["lines"]]
    rows += script.get("closing", [])
    for i, row in enumerate(rows):
        if not row: continue
        rel = f"audio/{prefix}-{i}.wav"
        path = store.path(did, rel); path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(1000)
            wav.writeframes(b"\0\0" * round(author.words(row["text"]) / wps * 1000))
        row["audio"] = rel

class NarrationPreparationContract(unittest.TestCase):
    def setUp(self):
        self.did = store.new_demo("Preparation fixture")["id"]
        store.update(self.did, lambda d: d["settings"].update(tts_provider="sarvam", sarvam_speaker="priya", voice_locked=True, language="en-IN", languages=[]))
        self.demo = store.load(self.did)
        self.und, self.plan = fixture()
        store.write_json(self.did, "understanding.json", self.und)

    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def prepared(self):
        p = copy.deepcopy(self.plan)
        p["narration_preparation"] = {"version": 1, "target_words": 495}
        plan._enforce_budget(p, self.demo)
        return p

    def calibrated(self, wps=3):
        sc = draft(self.prepared(), self.und["facts"], complete=True)
        author._assign_ids(sc)
        record(self.did, sc, wps=wps)
        sc.update(voice_provider="sarvam", voice_name="priya")
        store.write_json(self.did, "script.json", sc)
        sc["voice_input_hash"] = voice.input_hash(self.did)
        store.write_json(self.did, "script.json", sc)
        return sc

    def test_natural_target_has_headroom_without_changing_voice_speed(self):
        self.assertEqual(narration.word_target({}), 495)
        self.assertEqual(narration.word_target({"settings": {"pitch_minutes": 4}}), 660)
        self.assertEqual(author.WPS, 1.9)
        self.assertEqual(author.LIMITS, {"intro": 46, "outcome": 46, "proof": 46, "features": 48, "establish": 44})

    def test_matching_recorded_rate_can_raise_but_not_lower_target(self):
        sc = self.calibrated(3)
        self.assertGreaterEqual(narration.word_target(self.demo, sc, self.did), 594)
        sc = self.calibrated(2)
        self.assertEqual(narration.word_target(self.demo, sc, self.did), 495)

    def test_changed_voice_language_or_incomplete_recording_uses_baseline(self):
        sc = self.calibrated(3)
        for key, value in (("sarvam_speaker", "neha"), ("language", "hi-IN")):
            with self.subTest(key=key):
                changed = copy.deepcopy(self.demo); changed["settings"][key] = value
                store.write_json(self.did, "demo.json", changed)
                self.assertEqual(narration.word_target(changed, sc, self.did), 495)
                store.write_json(self.did, "demo.json", self.demo)
        Path(store.path(self.did, sc["runtime_overview"]["audio"])).write_bytes(b"corrupt")
        self.assertEqual(narration.word_target(self.demo, sc, self.did), 495)

    def test_selected_shorter_language_raises_content_target_not_speech_rate(self):
        store.update(self.did, lambda d: d["settings"].update(languages=["hi-IN"]))
        self.demo = store.load(self.did)
        sc = self.calibrated(495 / 200)
        alternate = copy.deepcopy(sc); record(self.did, alternate, wps=495 / 128, prefix="hindi")
        store.write_json(self.did, "script.hi-IN.json", alternate)
        self.assertGreaterEqual(narration.word_target(self.demo, sc, self.did), 766)
        self.demo["settings"]["languages"] = []
        store.write_json(self.did, "demo.json", self.demo)
        sc["voice_input_hash"] = voice.input_hash(self.did)
        self.assertEqual(narration.word_target(self.demo, sc, self.did), 495)

    def test_calibrated_target_survives_unvoiced_retry_for_same_identity(self):
        store.write_json(self.did, "plan.json", self.plan)
        sc = self.calibrated(3)
        with patch.object(plan.claude, "structured", side_effect=AssertionError("No model for preparation")):
            first = plan.run(self.did, lambda *_: None, narration.PREPARATION_INSTRUCTION)
            unvoiced = draft(first, self.und["facts"], complete=True)
            store.write_json(self.did, "script.json", unvoiced)
            second = plan.run(self.did, lambda *_: None, narration.PREPARATION_INSTRUCTION)
        self.assertGreaterEqual(first["total_words"], 594)
        self.assertEqual(second["total_words"], first["total_words"])
        changed = copy.deepcopy(self.demo); changed["settings"]["sarvam_speaker"] = "neha"
        self.assertEqual(narration.word_target(changed, unvoiced, self.did), 495)

    def test_prepared_allowances_cover_all_stops_without_new_facts(self):
        p = self.prepared()
        self.assertEqual(p["total_words"], 495)
        guided = [s for s in p["segments"] if s["role"] in narration.ROLES]
        self.assertEqual(sum(s["word_budget"] for s in guided), 427)
        for old, new in zip(self.plan["segments"], p["segments"]):
            self.assertEqual(new["fact_ids"], old["fact_ids"])
            if new["role"] in narration.ROLES:
                self.assertLessEqual(new["word_budget"], author.LIMITS[new["role"]] * min(3, max(2, len(new["fact_ids"]))))
        self.assertEqual(author.route_limit(self.demo, p), 535)

    def test_unprepared_legacy_allowances_are_unchanged(self):
        p = copy.deepcopy(self.plan); plan._enforce_budget(p, self.demo)
        self.assertEqual(p["total_words"], 342)
        self.assertEqual(author.route_limit(self.demo), 382)
        self.assertTrue(all(s["word_budget"] <= author.LIMITS[s["role"]] for s in p["segments"]))

    def test_empty_or_thin_outline_reports_infeasible_without_inventing_stops(self):
        p = self.prepared(); p["segments"] = p["segments"][:3]
        p["segments"][-1]["fact_ids"] = []
        original = [s["id"] for s in p["segments"]]
        plan._enforce_budget(p, self.demo)
        self.assertEqual([s["id"] for s in p["segments"]], original)
        self.assertLessEqual(p["segments"][-1]["word_budget"], 46)
        self.assertTrue(any("cannot fit" in issue for issue in p["issues"]))

    def test_global_minimum_uses_all_eligible_narration_not_early_route_prefix(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=True)
        issues = author.validate(sc, self.und, p, self.demo)
        self.assertFalse([i for i in issues if "GLOBAL NARRATION" in i], issues)
        self.assertEqual(narration.report(sc)["words"], 495)
        self.assertLess(narration.default_route(sc)[1]["words"], 495)
        sc["segments"][2]["deeper"] = sc["segments"][2]["lines"][1:]
        sc["segments"][2]["lines"] = sc["segments"][2]["lines"][:1]
        self.assertTrue(any("GLOBAL NARRATION TARGET" in i for i in author.validate(sc, self.und, p, self.demo)))

    def test_second_tail_role_cannot_fill_preparation_target_with_unplayed_words(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=False)
        before = narration.preparation_report(sc)["words"]
        extra = copy.deepcopy(next(s for s in draft(p, self.und["facts"], complete=True)["segments"] if s["role"] == "features"))
        extra["id"] = "extra-details"
        for ln in extra["lines"]: ln["text"] = "Separately, " + ln["text"]
        sc["segments"].append(extra)
        self.assertGreater(narration.report(sc)["words"], before)
        self.assertEqual(narration.preparation_report(sc)["words"], before)
        self.assertTrue(any("GLOBAL NARRATION TARGET" in issue for issue in author.validate(sc, self.und, p, self.demo)))

    def test_duplicate_and_held_lines_cannot_meet_target(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=False)
        repeated = copy.deepcopy(sc["segments"][2]["lines"][0])
        sc["segments"][2]["lines"] += [repeated] * 8
        issues = author.validate(sc, self.und, p, self.demo)
        self.assertTrue(any("GLOBAL NARRATION TARGET" in i for i in issues))
        sc["segments"][2]["lines"] = [{**repeated, "unverified": True}]
        self.assertLess(narration.report(sc)["words"], 495)

    def test_questions_in_main_overview_or_closing_do_not_fill_minimum(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=True)
        for row in [sc["overview"], *sc["closing"], *[ln for seg in sc["segments"] for ln in seg["lines"]]]:
            row["text"] += "?"
        issues = author.validate(sc, self.und, p, self.demo)
        self.assertTrue(any("GLOBAL NARRATION TARGET" in i for i in issues))
        self.assertEqual(narration.preparation_report(sc)["words"], 0)

    def test_single_overlong_line_requires_rewrite_not_unsafe_fragmentation(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=True)
        target = sc["segments"][2]
        target["lines"] = [line(" ".join(l["text"] for l in target["lines"]), "F0")]
        issues = author.validate(sc, self.und, p, self.demo)
        self.assertTrue(any("complete thought exceeds" in i for i in issues))
        author.split_long_batches(sc, strict=True)
        self.assertEqual(len(next(s for s in sc["segments"] if s["id"] == "seat")["lines"]), 1)

    def test_strict_split_preserves_complete_lines_budget_and_unique_ids(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=True)
        author.validate(sc, self.und, p, self.demo); author._assign_ids(sc)
        original = copy.deepcopy(sc)
        extra = copy.deepcopy(sc["segments"][0]); extra["id"] = "seat-2"
        sc["segments"].append(extra)
        author.split_long_batches(sc, strict=True)
        ids = [s["id"] for s in sc["segments"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("seat-3", ids)
        for old in original["segments"]:
            pieces = [s for s in sc["segments"] if (s.get("budget_source_id") or s["id"]) == old["id"]]
            self.assertEqual([ln for s in pieces for ln in s["lines"]], old["lines"])
            self.assertEqual(sum(s["word_budget"] for s in pieces), old["word_budget"])
            self.assertTrue(all(sum(author.words(l["text"]) for l in s["lines"]) <= author.LIMITS[s["role"]] for s in pieces))
        for s in sc["segments"]:
            if s["id"].startswith("seat") and s["id"] != "seat-2":
                self.assertEqual(s["budget_source_id"], "seat")

    def test_measured_route_keeps_whole_proof_and_tail_groups(self):
        p = self.prepared(); sc = draft(p, self.und["facts"], complete=True)
        author.validate(sc, self.und, p, self.demo); author._assign_ids(sc); author.split_long_batches(sc, strict=True)
        record(self.did, sc)
        ids, measured = narration.default_route(sc, demo_id=self.did, preferred=["storage-2", "details-2", "confirm-2"])
        self.assertEqual(ids[0], "seat")
        self.assertGreaterEqual(measured["seconds"], 180)
        for role in narration.ROLES:
            for group in {s.get("budget_source_id") or s["id"] for s in sc["segments"] if s["role"] == role}:
                pieces = [s["id"] for s in sc["segments"] if (s.get("budget_source_id") or s["id"]) == group]
                if set(pieces) & set(ids): self.assertTrue(set(pieces) <= set(ids))
        self.assertIn("details-2", ids); self.assertIn("confirm-2", ids)

    def test_actual_plan_author_single_repair_reaches_recorded_minimum(self):
        calls = []
        def model(system, content, schema, **kwargs):
            calls.append((schema, content))
            if schema is schemas.Plan: return schemas.Plan.model_validate(self.plan)
            self.assertIs(schema, schemas.ScriptOut)
            p = json.loads(content.split("\nPLAN: ", 1)[1].split("\n\nFACT REGISTRY", 1)[0])
            self.assertEqual(p["narration_preparation"]["target_words"], 495)
            return schemas.ScriptOut.model_validate(draft(p, self.und["facts"], complete="GLOBAL NARRATION TARGET" in content))
        with patch.object(plan.claude, "structured", side_effect=model), patch.object(author.visuals, "align", side_effect=lambda did, sc, und, emit: sc):
            p = plan.run(self.did, lambda *_: None)
            sc = author.run(self.did, lambda *_: None)
        self.assertEqual([c[0] for c in calls], [schemas.Plan, schemas.ScriptOut, schemas.ScriptOut])
        self.assertFalse(sc["issues"], sc["issues"])
        self.assertEqual(narration.report(sc)["words"], 495)
        record(self.did, sc)
        result = narration.require_minimum(sc, demo_id=self.did, require_recorded=True)
        self.assertEqual(result["seconds"], 198)
        self.assertTrue(result["measured"])
        sc.update(voice_provider="sarvam", voice_name="priya")
        store.write_json(self.did, "script.json", sc)
        deck.build(self.did, lambda *_: None)
        store.update(self.did, lambda demo: demo["approvals"].update({card: True for card in store.CARDS}))
        built = bundle.build(self.did, lambda *_: None)
        self.assertEqual(built["runtime"]["narration_minimum"]["seconds"], 198)
        for row in built["segments"]:
            source = next(s for s in sc["segments"] if s["id"] == row["id"])
            self.assertEqual(row.get("budget_source_id"), source.get("budget_source_id"))
        choice = schemas.PitchPlan(customer_state="unknown", decision_frame="", follow_up_question="",
                                   primary_outcome="", focus_topics=[], advance="",
                                   route=[{"segment_id": sid} for sid in ("storage-2", "loading-2", "cabin-2")])
        with patch.object(pitch.runtime, "structured", return_value=choice):
            visit = pitch.plan_pitch(self.did, {}, voice_it=False)
        played = [row["segment_id"] for row in visit["route"]]
        guided_ids = [s["id"] for s in sc["segments"] if s["role"] in narration.ROLES]
        self.assertEqual(set(played), set(guided_ids))
        self.assertEqual(played[:3], ["seat", "seat-2", "seat-3"])
        self.assertEqual(played[-4:], ["details", "details-2", "confirm", "confirm-2"])
        self.assertEqual(visit["narration_minimum"]["seconds"], 198)
        self.assertEqual(visit["narration_minimum"]["words"], 495)
        slide_ids = {slide["segment_id"] for slide in built["slides"]}
        self.assertTrue(set(played) <= slide_ids)
        self.assertEqual(set(p["segments"][2]["fact_ids"]), {"F0", "F1", "F12"})
        self.assertTrue(all(sum(author.words(l["text"]) for l in s["lines"]) <= author.LIMITS[s["role"]] for s in sc["segments"]))

    def test_preparation_keeps_reviewed_plan_voice_ctas_without_model_call(self):
        plan._keep_locked_persona(self.plan, plan._configured_voice(self.demo))
        store.write_json(self.did, "plan.json", self.plan)
        # First establish the currently locked voice, exactly as the normal plan does.
        with patch.object(plan.claude, "structured", side_effect=AssertionError("Preparation must not re-plan the reviewed story")):
            first = plan.run(self.did, lambda *_: None, narration.PREPARATION_INSTRUCTION)
            self.assertEqual(first["voice"], self.plan["voice"])
            self.assertEqual(first["ctas"], self.plan["ctas"])
            saved = copy.deepcopy(first)
            second = plan.run(self.did, lambda *_: None, narration.PREPARATION_INSTRUCTION)
        for key in ("voice", "ctas", "customer_persona", "takeaway", "intake"):
            self.assertEqual(saved[key], second[key])
        for old, new in zip(self.plan["segments"], second["segments"]):
            for key in ("id", "title", "role", "goal", "fact_ids"):
                self.assertEqual(old[key], new[key])

    def test_insufficient_repair_stays_explicit_and_bounded(self):
        p = self.prepared(); store.write_json(self.did, "plan.json", p)
        short = schemas.ScriptOut.model_validate(draft(p, self.und["facts"], complete=False))
        with patch.object(author.claude, "structured", return_value=short) as model, patch.object(author.visuals, "align", side_effect=lambda did, sc, und, emit: sc):
            result = author.run(self.did, lambda *_: None)
        self.assertEqual(model.call_count, 2)
        self.assertTrue(any("GLOBAL NARRATION TARGET" in i for i in result["issues"]))
        self.assertLess(narration.report(result)["words"], 495)

if __name__ == "__main__":
    unittest.main()
