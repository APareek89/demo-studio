"""Free Planner/Coach contracts, including a real mock Read through the graph."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

_STORAGE = tempfile.TemporaryDirectory(prefix="plan-playbook-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=_STORAGE.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_STORAGE.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []


def no_network(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Planner contracts must not open outbound sockets")


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network

from fastapi.testclient import TestClient
from server import config, schemas, store
from server.agents import author, coach, plan, playbooks
from server.llm import mock


def segment(id, role="proof", fact_ids=None, stop_id=None, budget=30):
    return {"id": id, "title": id.title(), "role": role, "goal": "MOMENT: inspect the subject. SPOKEN: keep the approved scope. HANDOFF: leave the choice in view.",
            "outcome": "Explore the listed choice", "topic": id, "fact_ids": fact_ids or [], "visual_refs": ["im1"], "usp_ids": [],
            "priority_topic": False, "stop_id": stop_id, "fundamental": False, "word_budget": budget}


def fixture():
    facts = [{"id": fid, "claim": claim, "value": value, "kind": "feature", "approved": True, "knowledge": {"origin": "website" if fid == "F1" else "uploaded"},
              "source": {"ref": "spec", "locator": "page one", "quote": value}} for fid, claim, value in
             [("F1", "Engine and gearbox choice", "Engine options are listed"), ("F2", "Suspension and wheels", "Wheel options are listed"),
              ("F3", "Rear seat and boot", "Rear seats are shown"), ("F4", "Sunroof", "Available on selected variants")]]
    und = {"product": {"name": "Example", "category": "Compact SUV"}, "brand": {}, "facts": facts, "shots": [], "unknowns": [],
           "images": [{"id": "im1", "source_id": "img", "quality": 4, "angle": "engine bay", "parts": [], "description": "Engine bay"}],
           "image_map": {"F1": ["im1"]}}
    pb = coach.mock_playbook(und, playbooks.LIBRARY["compact suv"])
    coach.validate(pb, und)
    pb["library_version"] = playbooks.VERSION
    p = mock.fake(schemas.Plan).model_dump()
    p["segments"] = [segment("intro", "intro"), segment("outcome", "outcome"), segment("sunroof", fact_ids=["F4"], stop_id="delighters"),
                     segment("engine", fact_ids=["F1"], stop_id="powertrain"), segment("wheels", fact_ids=["F2"], stop_id="stance-and-ride"),
                     segment("space", fact_ids=["F3"], stop_id="space-and-practicality"), segment("features", "features"), segment("establish", "establish")]
    p["visual_gaps"] = []
    return und, pb, p


class PlanPlaybookContract(unittest.TestCase):
    def setUp(self):
        self.und, self.pb, self.plan = fixture()
        self.did = store.new_demo("Planner contract")["id"]
        store.write_json(self.did, "understanding.json", self.und)
        store.write_json(self.did, "playbook.json", self.pb)

    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def test_typed_fields_and_legacy_defaults(self):
        old = segment("old")
        for key in ("stop_id", "fundamental", "word_budget"):
            old.pop(key)
        parsed = schemas.SegmentPlan.model_validate(old)
        self.assertIsNone(parsed.stop_id)
        self.assertFalse(parsed.fundamental)
        self.assertEqual(parsed.word_budget, 0)
        self.assertEqual(schemas.Plan.model_fields["total_words"].default, 0)
        self.assertEqual(schemas.Plan.model_fields["playbook_version"].default, "")

    def test_proof_order_matches_supported_playbook_and_role_order(self):
        plan._enforce_playbook(self.plan, self.pb)
        proof = [s for s in self.plan["segments"] if s["role"] == "proof"]
        self.assertEqual([s["stop_id"] for s in proof], [s["id"] for s in self.pb["stops"] if s["must_cover"]])
        self.assertEqual([s["role"] for s in self.plan["segments"]], ["intro", "outcome", "proof", "proof", "proof", "proof", "features", "establish"])
        self.assertEqual(proof[0]["id"], "engine")
        self.assertTrue(proof[0]["fundamental"])

    def test_missing_supported_stop_added_with_minimal_brief_and_issue(self):
        self.plan["segments"] = [s for s in self.plan["segments"] if s["id"] != "engine"]
        plan._enforce_playbook(self.plan, self.pb)
        added = next(s for s in self.plan["segments"] if s.get("stop_id") == "powertrain")
        self.assertEqual(added["title"], "Powertrain")
        self.assertEqual(added["fact_ids"], ["F1"])
        self.assertEqual(added["visual_refs"], ["im1"])
        for part in ("MOMENT", "SPOKEN", "HANDOFF"):
            self.assertIn(part, added["goal"])
        self.assertTrue(any("powertrain: added missing" in issue for issue in self.plan["issues"]))

    def test_false_stop_drops_proof_keeps_deeper_and_gap(self):
        stop = next(s for s in self.pb["stops"] if s["id"] == "delighters")
        stop.update(must_cover=False, gaps=["A photo showing the sunroof"])
        plan._enforce_playbook(self.plan, self.pb)
        self.assertNotIn("delighters", [s.get("stop_id") for s in self.plan["segments"]])
        nearest = next(s for s in self.plan["segments"] if s.get("stop_id") == "space-and-practicality")
        self.assertIn("F4", nearest["fact_ids"])
        self.assertIn("DEEPER ONLY: F4", nearest["goal"])
        self.assertIn("A photo showing the sunroof", [g["what"] for g in self.plan["visual_gaps"]])

    def test_overlap_fallback_unknown_and_duplicate_proofs(self):
        engine = next(s for s in self.plan["segments"] if s["id"] == "engine")
        engine["stop_id"] = None
        self.plan["segments"] += [segment("duplicate-engine", fact_ids=["F1"]), segment("invented", fact_ids=["NOPE"])]
        plan._enforce_playbook(self.plan, self.pb)
        self.assertEqual(next(s for s in self.plan["segments"] if s["id"] == "engine")["stop_id"], "powertrain")
        self.assertFalse({"duplicate-engine", "invented"} & {s["id"] for s in self.plan["segments"]})
        self.assertTrue(any("duplicate proof" in issue for issue in self.plan["issues"]))

    def test_fundamental_flags_and_exact_usps_version(self):
        original_usps = copy.deepcopy(self.pb["usps"])
        plan._enforce_playbook(self.plan, self.pb)
        for seg in self.plan["segments"]:
            if seg["role"] == "proof":
                stop = next(s for s in self.pb["stops"] if s["id"] == seg["stop_id"])
                self.assertEqual(seg["fundamental"], stop["kind"] == "fundamental")
        self.assertEqual(self.plan["usps"], original_usps)
        self.assertEqual(self.plan["playbook_version"], playbooks.VERSION)
        schemas.Plan.model_validate(self.plan)

    def test_incomplete_or_invalid_playbook_usps_retain_planner_usps(self):
        retained = [{"id": "planner-usp", "name": "Explore your engine choices", "why_it_matters": "An approved choice", "fact_ids": ["F1"]}]
        for change in ("two", "unsafe", "unsupported"):
            with self.subTest(change=change):
                p, pb = copy.deepcopy(self.plan), copy.deepcopy(self.pb)
                p["usps"] = copy.deepcopy(retained)
                if change == "two": pb["usps"].pop()
                elif change == "unsafe": pb["usps"][0]["name"] = "Power from 1500 cc"
                else: pb["usps"][0]["fact_ids"] = []
                plan._enforce_playbook(p, pb)
                self.assertEqual(p["usps"], retained)
                self.assertIn("playbook USPs incomplete; planner USPs retained", p["issues"])
                self.assertEqual(next(s for s in p["segments"] if s["id"] == "engine")["usp_ids"], ["planner-usp"])

    def test_stop_evidence_precedes_other_approved_planner_references(self):
        self.und["facts"].append({**self.und["facts"][0], "id": "HOLD", "approved": False})
        self.und["images"] += [{**self.und["images"][0], "id": "im2", "source_id": "img-two"},
                               {**self.und["images"][0], "id": "im3", "source_id": "excluded"}]
        store.write_json(self.did, "understanding.json", self.und)
        store.update(self.did, lambda demo: demo["sources"].append({"id": "excluded", "kind": "image", "use_in_demo": False}))
        engine = next(s for s in self.plan["segments"] if s["id"] == "engine")
        engine.update(fact_ids=["F2", "F1", "F2", "HOLD", "invented"], visual_refs=["im2", "im1", "im2", "im3", "invented"])
        with patch.object(plan.claude, "structured", return_value=schemas.Plan.model_validate(self.plan)):
            result = plan.run(self.did, lambda _: None)
        engine = next(s for s in result["segments"] if s["id"] == "engine")
        self.assertEqual(engine["fact_ids"], ["F1", "F2"])
        self.assertEqual(engine["visual_refs"], ["im1", "im2"])

    def test_budget_total_three_minutes_and_proportional_allocation(self):
        plan._enforce_playbook(self.plan, self.pb)
        for index, seg in enumerate(self.plan["segments"]):
            seg["word_budget"] = 22 + index
        plan._enforce_budget(self.plan, {"settings": {"pitch_minutes": 3}})
        self.assertEqual(self.plan["total_words"], 342)
        self.assertEqual(sum(s["word_budget"] for s in self.plan["segments"] if s["role"] in {"proof", "features", "establish"}), 274)
        self.assertEqual([s["word_budget"] for s in self.plan["segments"] if s["role"] in {"intro", "outcome"}], [22, 23])
        self.assertEqual(self.plan["guided_minimum_seconds"], 180)
        self.assertGreater(len({s["word_budget"] for s in self.plan["segments"]}), 1)
        self.assertTrue(all(22 <= s["word_budget"] <= author.LIMITS[s["role"]] for s in self.plan["segments"]))

    def test_missing_duration_defaults_to_three_minutes_in_prompt_and_saved_plan(self):
        store.update(self.did, lambda demo: demo["settings"].pop("pitch_minutes", None))
        with patch.object(plan.claude, "structured", return_value=schemas.Plan.model_validate(self.plan)) as model:
            result = plan.run(self.did, lambda _: None)
        timing = json.loads(model.call_args.args[1].split("DEMO WORD BUDGET: ", 1)[1].split("\n", 1)[0])
        self.assertEqual(timing["pitch_minutes"], 3)
        self.assertEqual(timing["total_words"], 495)
        self.assertEqual(result["total_words"], 495)
        self.assertEqual(result["narration_preparation"]["version"], 1)
        self.assertEqual(result["narration_preparation"]["target_words"], 495)
        self.assertRegex(result["narration_preparation"]["identity"], r"^[0-9a-f]{64}$")

    def test_budget_clamps_extremes_and_reports_unachievable_lengths(self):
        self.plan["segments"][0]["word_budget"] = -500
        self.plan["segments"][1]["word_budget"] = 9000
        plan._enforce_budget(self.plan, {"settings": {"pitch_minutes": 5}})
        self.assertEqual(self.plan["total_words"], round(5 * 60 * author.WPS))
        self.assertTrue(all(22 <= s["word_budget"] <= author.LIMITS[s["role"]] for s in self.plan["segments"]))
        self.assertTrue(any("cannot fit" in issue for issue in self.plan["issues"]))

    def test_default_budget_emphasizes_lead_fundamental(self):
        plan._enforce_playbook(self.plan, self.pb)
        # Extra supported allocation slots give the writer room to vary attention;
        # a nearly saturated four-proof plan must spend close to every hard ceiling.
        for index in range(2):
            self.plan["segments"].insert(-2, segment(f"budget-extra-{index}", fact_ids=["F3"]))
        for seg in self.plan["segments"]:
            seg["word_budget"] = 0
        plan._enforce_budget(self.plan, {"settings": {"pitch_minutes": 3}})
        proofs = [s for s in self.plan["segments"] if s["role"] == "proof"]
        self.assertGreater(proofs[0]["word_budget"], proofs[-1]["word_budget"])

    def test_planner_and_author_share_exact_role_ceilings(self):
        expected = {"intro": 46, "outcome": 46, "proof": 46, "features": 48, "establish": 44}
        self.assertEqual(author.LIMITS, expected)
        for seg in self.plan["segments"]:
            seg["word_budget"] = 500
        plan._enforce_budget(self.plan, {"settings": {"pitch_minutes": 4}})
        for seg in self.plan["segments"]:
            self.assertEqual(seg["word_budget"], author.LIMITS[seg["role"]])
        with patch.object(plan.claude, "structured", return_value=schemas.Plan.model_validate(self.plan)) as model:
            plan.run(self.did, lambda _: None)
        content = model.call_args.args[1]
        timing = json.loads(content.split("DEMO WORD BUDGET: ", 1)[1].split("\n", 1)[0])
        self.assertEqual(timing["role_ceilings"], author.LIMITS)
        self.assertNotIn("38 words each", plan.PLAN_SYSTEM)

    def test_playbook_overrides_and_registry_provenance_reach_model(self):
        store.update(self.did, lambda d: d["settings"].update(pitch_minutes=3))
        store.write_json(self.did, "playbook-overrides.json", {"stop_order": ["stance-and-ride", "powertrain"]})
        with patch.object(plan.claude, "structured", return_value=schemas.Plan.model_validate(self.plan)) as model:
            result = plan.run(self.did, lambda _: None)
        content = model.call_args.args[1]
        self.assertLess(content.index("PLAYBOOK:"), content.index("APPROVED FACT REGISTRY"))
        payload = json.loads(content.split("PLAYBOOK:\n", 1)[1].split("\n\nAPPROVED FACT REGISTRY", 1)[0])
        self.assertEqual(payload["stops"][0]["id"], "stance-and-ride")
        self.assertIn('(pictures: im1)', content)
        self.assertIn('(origin: website)', content)
        self.assertIn('(origin: uploaded)', content)
        self.assertIn('"total_words": 495', content)
        self.assertIn('"role_ceilings"', content)
        self.assertEqual([s for s in result["segments"] if s["role"] == "proof"][0]["stop_id"], "stance-and-ride")

    def test_legacy_direct_plan_without_playbook_remains_readable(self):
        store.path(self.did, "playbook.json").unlink()
        with patch.object(plan.claude, "structured", return_value=schemas.Plan.model_validate(self.plan)):
            result = plan.run(self.did, lambda _: None)
        self.assertEqual([s["id"] for s in result["segments"] if s["role"] == "proof"], ["sunroof", "engine", "wheels", "space"])
        self.assertTrue(all(s["word_budget"] >= 22 for s in result["segments"]
                            if s["role"] in {"intro", "outcome"} or s["fact_ids"]))
        self.assertTrue(all(s["word_budget"] == 0 for s in result["segments"]
                            if s["role"] in {"features", "establish"} and not s["fact_ids"]))

    def test_settled_story_and_audit_prompt_clauses(self):
        for text in ("THE PLAYBOOK IS SETTLED", "WORD BUDGETS", "Never build a USP or a narration line on a company or market statistic",
                     "Reserve the two closing statements for the final summary and next action. Segment checkins stay empty.", "Titles are sometimes SPOKEN at runtime",
                     "Do not open two consecutive segments the same way", "These are the ONLY pictures that segment may use.",
                     "The segment goal is the Author's brief"):
            self.assertIn(text, plan.PLAN_SYSTEM)
        for text in ("strongest supported standout feature first", "For everyday buyers, plan around a standout visible feature", "panoramic sunroof"):
            self.assertNotIn(text, plan.PLAN_SYSTEM)

    def test_model_failure_preserves_saved_plan(self):
        store.write_json(self.did, "plan.json", self.plan)
        before = store.path(self.did, "plan.json").read_bytes()
        with patch.object(plan.claude, "structured", side_effect=ValueError("invalid output")):
            with self.assertRaises(RuntimeError):
                plan.run(self.did, lambda _: None)
        self.assertEqual(store.path(self.did, "plan.json").read_bytes(), before)

    def test_mock_read_real_graph_creates_coach_then_plan(self):
        from server.app import app
        with TestClient(app) as api:
            did = api.post("/api/demos", json={"name": "Mock playbook graph"}).json()["id"]
            response = api.post(f"/api/demos/{did}/sources", data={"role": "catalogue", "text": "The product specification lists engine, wheels and rear seats."})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(api.post(f"/api/demos/{did}/read").status_code, 200)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                saved = store.load(did)
                if saved["status"] in ("align", "error"):
                    break
                time.sleep(.05)
            self.assertEqual(saved["status"], "align", saved["stages"])
            pb = store.read_json(did, "playbook.json")
            planned = store.read_json(did, "plan.json")
            script = store.read_json(did, "script.json")
            self.assertEqual(saved["stages"]["coach"]["status"], "done")
            self.assertEqual(saved["stages"]["plan"]["status"], "done")
            self.assertEqual([s["stop_id"] for s in planned["segments"] if s["role"] == "proof"], [s["id"] for s in pb["stops"] if s["must_cover"]])
            self.assertEqual(planned["playbook_version"], playbooks.VERSION)
            if all(usp["fact_ids"] for usp in pb["usps"]) and len(pb["usps"]) == 3:
                self.assertEqual(planned["usps"], pb["usps"])
            else:
                self.assertIn("playbook USPs incomplete; planner USPs retained", planned["issues"])
            self.assertEqual([s["id"] for s in script["segments"]], [s["id"] for s in planned["segments"]])
            self.assertEqual([s["role"] for s in script["segments"]], [s["role"] for s in planned["segments"]])
        self.assertEqual(config.DATA_DIR, Path(_STORAGE.name).resolve())

    def test_mock_read_with_incomplete_coach_usps_reaches_align(self):
        from server.app import app
        real_mock = coach.mock_playbook
        def incomplete(und, entry):
            pb = real_mock(und, entry)
            pb["usps"] = pb["usps"][:2]
            return pb
        with patch.object(coach, "mock_playbook", side_effect=incomplete), TestClient(app) as api:
            did = api.post("/api/demos", json={"name": "Incomplete Coach USP Read"}).json()["id"]
            self.assertEqual(api.post(f"/api/demos/{did}/sources", data={"role": "catalogue", "text": "The product specification lists engine, wheels and rear seats."}).status_code, 200)
            self.assertEqual(api.post(f"/api/demos/{did}/read").status_code, 200)
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                saved = store.load(did)
                if saved["status"] in ("align", "error"):
                    break
                time.sleep(.05)
            self.assertEqual(saved["status"], "align", saved["stages"])
            self.assertEqual(saved["stages"]["coach"]["status"], "done")
            self.assertIn("coach returned 2 USPs", store.read_json(did, "playbook.json")["issues"])
            self.assertIn("playbook USPs incomplete; planner USPs retained", store.read_json(did, "plan.json")["issues"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
