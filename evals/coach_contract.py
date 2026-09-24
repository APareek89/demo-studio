"""Free Coach contracts: evidence-only story order, safe revisions and isolated storage."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

_STORAGE = tempfile.TemporaryDirectory(prefix="coach-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=_STORAGE.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_STORAGE.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []


def no_network(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Coach contracts must not open outbound sockets")


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network

from server import config, schemas, store
from server.agents import coach, plan, playbooks
from server.llm import mock


def understanding(category="Compact SUV"):
    claims = [("F1", "Engine and gearbox choice"), ("F2", "Suspension and wheels"),
              ("F3", "Rear seat and boot"), ("F4", "Sunroof"), ("HOLD", "Safety airbags")]
    return {"product": {"name": "Example", "category": category},
            "facts": [{"id": fid, "claim": claim, "value": "Shown in the specification", "kind": "feature", "approved": fid != "HOLD",
                       "knowledge": {"origin": "website" if fid == "F1" else "uploaded"}, "source": {"ref": "doc", "locator": "page one", "quote": claim}} for fid, claim in claims],
            "shots": [], "images": [{"id": "im1", "source_id": "img", "quality": 4, "angle": "engine bay", "parts": [], "description": "Engine bay"},
                                       {"id": "im2", "source_id": "excluded", "quality": 4, "angle": "side", "parts": [], "description": "Wheels"}],
            "image_map": {"F1": ["im1"], "F2": ["im2"]},
            "unknowns": [{"id": "U1", "question": "What is the ground clearance?", "status": "open"}]}


class CoachContract(unittest.TestCase):
    def setUp(self):
        self.demo = store.new_demo("Coach contract")
        self.did = self.demo["id"]
        self.und = understanding()
        store.write_json(self.did, "understanding.json", self.und)
        self.events = []

    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def playbook(self):
        return coach.mock_playbook(self.und, playbooks.match(self.und["product"]["category"])[1])

    def test_library_matches_aliases_and_specificity(self):
        for category, expected in [("MID-SIZE SUV", "compact suv"), ("A luxury SUV", "premium suv"),
                                   ("premium SUV", "premium suv"), ("E-scooter", "electric scooter"), ("crossover", "compact suv")]:
            self.assertEqual(playbooks.match(category)[0], expected)
        self.assertEqual([s["id"] for s in playbooks.LIBRARY["compact suv"]["order"]],
                         ["powertrain", "stance-and-ride", "space-and-practicality", "safety", "cabin-and-tech", "delighters", "ownership"])

    def test_generic_is_inferred_and_sparse_evidence_is_explicit(self):
        self.und["product"]["category"] = "Unlisted product class"
        self.und["facts"] = []
        store.write_json(self.did, "understanding.json", self.und)
        result = coach.run(self.did, self.events.append)
        self.assertEqual(result["category_source"], "inferred")
        self.assertEqual(len(result["usps"]), 3)
        self.assertTrue(result["evidence_gaps"])
        self.assertTrue(any("supporting evidence" in issue for issue in result["issues"]))
        self.assertFalse(any(u["fact_ids"] for u in result["usps"]))

    def test_first_fundamental_and_delighter_order_enforced(self):
        pb = self.playbook()
        pb["stops"].insert(0, pb["stops"].pop(5))
        issues = coach.validate(pb, self.und)
        self.assertEqual(pb["stops"][0]["kind"], "fundamental")
        self.assertGreater(next(i for i, s in enumerate(pb["stops"]) if s["kind"] == "delighter"),
                           max(i for i, s in enumerate(pb["stops"]) if s["kind"] == "fundamental"))
        self.assertTrue(any("fundamental" in issue for issue in issues))

    def test_three_usps_have_approved_fundamental_support(self):
        pb = self.playbook()
        coach.validate(pb, self.und)
        self.assertEqual(len(pb["usps"]), 3)
        stops = {s["id"]: s for s in pb["stops"]}
        self.assertTrue(all(set(u["fact_ids"]) <= set(stops[u["stop_id"]]["fact_ids"]) for u in pb["usps"]))
        self.assertGreaterEqual(sum(stops[u["stop_id"]]["kind"] == "fundamental" for u in pb["usps"]), 2)

    def test_unsafe_usp_too_short_after_cleanup_is_dropped_without_aborting(self):
        pb = self.playbook()
        pb["usps"][0]["name"] = "Power from 1500 cc"
        issues = coach.validate(pb, self.und)
        self.assertTrue(any("rejected USP name" in issue for issue in issues))
        self.assertEqual(len(pb["usps"]), 2)
        self.assertNotIn("usp-1", [u["id"] for u in pb["usps"]])
        with patch.object(config, "MOCK_LLM", False), patch.object(coach.claude, "structured", return_value=schemas.Playbook.model_validate(pb)):
            result = coach.run(self.did, self.events.append)
        self.assertEqual(len(result["usps"]), 2)
        self.assertEqual(store.read_json(self.did, "playbook.json"), result)

    def test_unsafe_usp_cleanup_removes_whole_number_unit_and_code_tokens(self):
        for unsafe in ("1500 cc", "SX1500", "100km", "six airbags", "7-seater", "50%", "₹ 12000", "32 GB", "2 years", "DCT", "hp"):
            with self.subTest(unsafe=unsafe):
                pb = self.playbook()
                pb["usps"][0]["name"] = f"Comfort  {unsafe}  for your family"
                issues = coach.validate(pb, self.und)
                self.assertEqual(pb["usps"][0]["name"], "Comfort for your family")
                self.assertEqual(pb["usps"][0]["fact_ids"], ["F1"])
                self.assertTrue(any("stripped figures, units or model codes" in issue for issue in issues))
                self.assertFalse(coach._unsafe_usp_name(pb["usps"][0]["name"]))

    def test_unsafe_usp_still_over_word_limit_is_dropped(self):
        pb = self.playbook()
        pb["usps"][0]["name"] = "These many everyday words still make this selling promise too long"
        self.assertTrue(any("rejected USP name" in issue for issue in coach.validate(pb, self.und)))
        self.assertEqual(len(pb["usps"]), 2)

    def test_power_and_capacity_units_do_not_survive_digit_cleanup(self):
        for original, expected in (("150 PS for easy highway trips", "for easy highway trips"),
                                   ("1.5 L engine for daily drives", "engine for daily drives")):
            with self.subTest(name=original):
                pb = self.playbook()
                pb["usps"][0]["name"] = original
                issues = coach.validate(pb, self.und)
                self.assertEqual(pb["usps"][0]["name"], expected)
                self.assertEqual(pb["usps"][0]["fact_ids"], ["F1"])
                self.assertTrue(any("stripped figures, units or model codes" in issue for issue in issues))
                self.assertFalse(coach._unsafe_usp_name(expected))

    def test_unsupported_stop_retained_with_gap(self):
        pb = self.playbook()
        stop = next(s for s in pb["stops"] if s["id"] == "safety")
        stop.update(must_cover=True, gaps=[])
        issues = coach.validate(pb, self.und)
        self.assertFalse(stop["must_cover"])
        self.assertTrue(stop["gaps"])
        self.assertTrue(any("no approved facts" in issue for issue in issues))

    def test_unapproved_unknown_and_wrong_stop_facts_dropped(self):
        pb = self.playbook()
        pb["stops"][0]["fact_ids"] += ["HOLD", "invented"]
        pb["usps"][0]["fact_ids"] += ["F4", "invented"]
        coach.validate(pb, self.und)
        self.assertEqual(pb["stops"][0]["fact_ids"], ["F1"])
        self.assertEqual(pb["usps"][0]["fact_ids"], ["F1"])

    def test_unknown_and_excluded_pictures_dropped(self):
        pb = self.playbook()
        pb["stops"][0]["picture_ids"] += ["imaginary"]
        coach.validate(pb, self.und)
        self.assertEqual(pb["stops"][0]["picture_ids"], ["im1"])
        store.update(self.did, lambda d: d["sources"].append({"id": "excluded", "kind": "image", "use_in_demo": False}))
        result = coach.run(self.did, self.events.append)
        self.assertNotIn("im2", [ref for s in result["stops"] for ref in s["picture_ids"]])

    def test_picture_gap_per_supported_stop(self):
        pb = self.playbook()
        coach.validate(pb, self.und)
        for stop in pb["stops"]:
            if stop["must_cover"]:
                self.assertTrue(stop["picture_ids"] or any("picture" in gap.lower() for gap in stop["gaps"]))

    def test_duplicate_stop_ids_keep_first_occurrence_and_report_issue(self):
        pb = self.playbook()
        first = copy.deepcopy(pb["stops"][0])
        duplicate = {**first, "label": "Later duplicate", "fact_ids": ["F4"], "picture_ids": ["im2"]}
        pb["stops"].append(duplicate)
        issues = coach.validate(pb, self.und)
        self.assertEqual(pb["stops"][0], first)
        self.assertEqual(len([s for s in pb["stops"] if s["id"] == first["id"]]), 1)
        self.assertTrue(any("duplicate stop ID; kept the first occurrence" in issue for issue in issues))

    def test_cache_returns_identical_artifact_without_model_or_write(self):
        first = coach.run(self.did, self.events.append)
        before = store.path(self.did, "playbook.json").read_bytes()
        with patch.object(coach, "mock_playbook", side_effect=AssertionError("cache must not regenerate")), patch.object(coach, "apply_overrides", side_effect=AssertionError("cache must not rewrite")):
            again = coach.run(self.did, self.events.append)
        self.assertEqual(again, first)
        self.assertEqual(store.path(self.did, "playbook.json").read_bytes(), before)
        self.assertEqual(self.events[-1], "Playbook unchanged — reused")

    def test_audience_registry_version_and_instruction_invalidate_cache(self):
        coach.run(self.did, self.events.append)
        with patch.object(coach, "mock_playbook", wraps=coach.mock_playbook) as generate:
            store.update(self.did, lambda d: d["settings"].update(audience="technical"))
            coach.run(self.did, self.events.append)
            self.und["facts"][0]["value"] = "New approved value"
            store.write_json(self.did, "understanding.json", self.und)
            coach.run(self.did, self.events.append)
            with patch.object(playbooks, "VERSION", "next-library"):
                coach.run(self.did, self.events.append)
            coach.run(self.did, self.events.append, "Put practical choices first")
            self.assertEqual(generate.call_count, 4)

    def test_changed_coach_guidance_regenerates_once_without_changing_evidence(self):
        before = coach.run(self.did, self.events.append)
        evidence = store.path(self.did, "understanding.json").read_bytes()
        with patch.object(coach, "COACH_SYSTEM", coach.COACH_SYSTEM + "\nGive the lead stop a clear buyer choice."), \
                patch.object(coach, "mock_playbook", wraps=coach.mock_playbook) as generate:
            revised = coach.run(self.did, self.events.append)
            repeated = coach.run(self.did, self.events.append)
        self.assertEqual(generate.call_count, 1)
        self.assertNotEqual(before["input_hash"], revised["input_hash"])
        self.assertEqual(revised, repeated)
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), evidence)

    def test_overrides_reorder_relabel_and_revalidate(self):
        pb = coach.run(self.did, self.events.append)
        original = copy.deepcopy(pb)
        store.write_json(self.did, "playbook-overrides.json", {"stop_order": ["space-and-practicality", "powertrain"], "kinds": {"cabin-and-tech": "hygiene"}})
        result = coach.apply_overrides(pb, self.did)
        self.assertEqual(result["stops"][0]["id"], "space-and-practicality")
        self.assertEqual(next(s for s in result["stops"] if s["id"] == "cabin-and-tech")["kind"], "hygiene")
        self.assertEqual(pb, original)
        store.write_json(self.did, "playbook-overrides.json", {"stop_order": ["delighters", "powertrain"]})
        self.assertEqual(coach.apply_overrides(pb, self.did)["stops"][0]["kind"], "fundamental")

    def test_customer_unknowns_are_live_evidence_gaps_never_facts(self):
        pb = coach.run(self.did, self.events.append)
        before_facts = copy.deepcopy(self.und["facts"])
        self.und["unknowns"].append({"id": "U2", "question": "Is doorstep servicing available?", "source": "customer",
                                     "status": "open", "asked_count": 4, "suggested_document": "Official service policy"})
        pb["evidence_gaps"].append({"what": "Is doorstep servicing available?", "why_it_matters": "A model-proposed customer gap", "suggested_source": "Service policy"})
        store.write_json(self.did, "understanding.json", self.und)
        with patch.object(coach.claude, "structured", side_effect=AssertionError("Align gap refresh must be free")):
            refreshed = coach.apply_overrides(pb, self.did)
            gap = next(g for g in refreshed["evidence_gaps"] if g.get("unknown_id") == "U2")
            self.assertEqual(gap["asked_count"], 4)
            self.assertEqual(gap["what"], "Is doorstep servicing available?")
            self.assertEqual(gap["suggested_source"], "Official service policy")
            self.assertEqual(sum(g["what"] == gap["what"] for g in refreshed["evidence_gaps"]), 1)
            self.assertEqual(store.read_json(self.did, "understanding.json")["facts"], before_facts)
            self.assertEqual(coach.apply_overrides(refreshed, self.did)["evidence_gaps"], refreshed["evidence_gaps"])
            self.und["unknowns"][-1]["status"] = "resolved"
            store.write_json(self.did, "understanding.json", self.und)
            self.assertFalse(any(g.get("unknown_id") == "U2" for g in coach.apply_overrides(refreshed, self.did)["evidence_gaps"]))

    def test_category_and_picture_changes_invalidate_cache_without_fact_changes(self):
        first = coach.run(self.did, self.events.append)
        store.update(self.did, lambda d: d["sources"].append({"id": "img", "kind": "image", "use_in_demo": False}))
        without_image = coach.run(self.did, self.events.append)
        self.assertEqual(first["registry_hash"], without_image["registry_hash"])
        self.assertNotIn("im1", [ref for stop in without_image["stops"] for ref in stop["picture_ids"]])
        self.und["product"]["category"] = "Electric scooter"
        store.write_json(self.did, "understanding.json", self.und)
        scooter = coach.run(self.did, self.events.append)
        self.assertEqual(first["registry_hash"], scooter["registry_hash"])
        self.assertEqual(scooter["library_key"], "electric scooter")
        self.assertEqual(scooter["stops"][0]["id"], "range")

    def test_missing_or_failed_model_preserves_previous_file(self):
        coach.run(self.did, self.events.append)
        before = store.path(self.did, "playbook.json").read_bytes()
        with patch.object(config, "MOCK_LLM", False), patch.object(coach.claude, "structured", side_effect=RuntimeError("provider unavailable")):
            with self.assertRaises(RuntimeError):
                coach.run(self.did, self.events.append, "Revise this story")
        self.assertEqual(store.path(self.did, "playbook.json").read_bytes(), before)
        store.write_json(self.did, "understanding.json", {})
        with self.assertRaises(RuntimeError):
            coach.run(self.did, self.events.append)
        self.assertEqual(store.path(self.did, "playbook.json").read_bytes(), before)

    def test_two_model_usps_are_saved_with_an_issue(self):
        first = coach.run(self.did, self.events.append)
        first["usps"].pop()
        self.assertIn("coach returned 2 USPs", coach.validate(first, self.und))
        with patch.object(config, "MOCK_LLM", False), patch.object(coach.claude, "structured", return_value=schemas.Playbook.model_validate(first)):
            result = coach.run(self.did, self.events.append, "Revise this story")
        self.assertEqual(len(result["usps"]), 2)
        self.assertIn("coach returned 2 USPs", result["issues"])
        self.assertEqual(store.read_json(self.did, "playbook.json"), result)

    def test_four_model_usps_keep_the_first_three_and_save(self):
        pb = self.playbook()
        pb["usps"].append({**pb["usps"][0], "id": "usp-fourth", "name": "Additional approved selling promise"})
        expected = copy.deepcopy(pb["usps"][:3])
        with patch.object(config, "MOCK_LLM", False), patch.object(coach.claude, "structured", return_value=schemas.Playbook.model_validate(pb)):
            result = coach.run(self.did, self.events.append)
        self.assertEqual(result["usps"], expected)
        self.assertIn("coach returned 4 USPs; kept the first three", result["issues"])
        self.assertEqual(store.read_json(self.did, "playbook.json"), result)

    def test_coach_prompt_receives_registry_provenance_and_revision(self):
        pb = coach.run(self.did, self.events.append)
        with patch.object(config, "MOCK_LLM", False), patch.object(coach.claude, "structured", return_value=schemas.Playbook.model_validate(pb)) as model:
            coach.run(self.did, self.events.append, "Explain the ride before the space")
        system, content, schema = model.call_args.args
        self.assertEqual(schema, schemas.Playbook)
        self.assertEqual(model.call_args.kwargs["max_tokens"], 12000)
        self.assertEqual(system, coach.COACH_SYSTEM.format(category="Compact SUV"))
        for text in ("PRODUCT:", "CATEGORY LIBRARY ORDER (version", "APPROVED FACT REGISTRY (4)", "OPEN UNKNOWNS:", "IMAGES (2)",
                     "(pictures: im1)", "(origin: uploaded)", "PREVIOUS PLAYBOOK:", "REVISION INSTRUCTION FROM THE USER — follow it precisely"):
            self.assertIn(text, content)
        self.assertNotIn("HOLD [", content)

    def test_nested_registry_origins_reach_coach_and_planner_prompts(self):
        self.und["brand"] = {}
        self.und["facts"][0]["origin"] = "legacy-ignored"
        store.write_json(self.did, "understanding.json", self.und)
        pb = coach.run(self.did, self.events.append)
        with patch.object(config, "MOCK_LLM", False), patch.object(coach.claude, "structured", return_value=schemas.Playbook.model_validate(pb)) as coach_model:
            coach.run(self.did, self.events.append, "Review source provenance")
        with patch.object(plan.claude, "structured", return_value=mock.fake(schemas.Plan)) as plan_model:
            plan.run(self.did, self.events.append)
        for content in (coach_model.call_args.args[1], plan_model.call_args.args[1]):
            self.assertIn("(origin: website)", content)
            self.assertIn("(origin: uploaded)", content)
            self.assertNotIn("(origin: legacy-ignored)", content)

    def test_progress_stage_schema_and_faker(self):
        from server import graph, runlog
        self.assertLess(store.STAGES.index("understand"), store.STAGES.index("coach"))
        self.assertLess(store.STAGES.index("coach"), store.STAGES.index("plan"))
        self.assertIn("coach", runlog._REPORTS)
        self.assertEqual(graph.router({"entry": "revise", "revise_stage": "coach", "stage": "coach"}).goto, "coach")
        self.assertEqual(schemas.AlignAction(type="revise", stage="coach").stage, "coach")
        self.assertEqual(mock.fake(schemas.Playbook).category_source, "library")
        self.assertTrue(all(stop.kind == "fundamental" for stop in mock.fake(schemas.Playbook).stops))

    def test_coach_keeps_stats_ban_and_ownership_emphasis_inside_library_order(self):
        stats_ban = """Never build a USP or a narration line on a company or market statistic: units sold, monthly or annual
sales figures, customer totals, market share, sales rank, years on sale, or award counts. These are the
brand's numbers, not the buyer's experience; they date within weeks and no one buys because of a units
figure. A derived reputational line is allowed ONCE, in the intro, with no figure and no rank — "one of
the cars you see most on Indian roads" — still citing the fact id it rests on."""
        self.assertIn(stats_ban, coach.COACH_SYSTEM)
        self.assertLess(coach.COACH_SYSTEM.index("- usps:"), coach.COACH_SYSTEM.index(stats_ban))
        self.assertLess(coach.COACH_SYSTEM.index(stats_ban), coach.COACH_SYSTEM.index("- objections:"))
        self.assertIn("Choose the ordinary ownership moment that connects the tour", coach.COACH_SYSTEM)
        self.assertIn("the first fundamental stays first, and each delighter stays at its supplied", coach.COACH_SYSTEM)
        self.assertNotIn("place the delighter that serves it right after the fundamentals", coach.COACH_SYSTEM)
        self.assertNotIn("make the first proof stop the one closest to it", coach.COACH_SYSTEM)

    def test_storage_is_temporary_and_sockets_are_blocked(self):
        self.assertEqual(config.DATA_DIR, Path(_STORAGE.name).resolve())
        self.assertNotIn("data/demos", str(store.demo_dir(self.did)))
        self.assertIs(socket.create_connection, no_network)
        self.assertEqual(OUTBOUND, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
