"""Offline regression for real paid-plan scalar budgets versus whole speech batches."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import re
import socket
import sys
import tempfile
import unittest

_TEMP = tempfile.TemporaryDirectory(prefix="prepared-budget-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=_TEMP.name, DEMO_STUDIO_GRAPH_DB=str(Path(_TEMP.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ATTEMPTS = []


def blocked(*args, **kwargs):
    ATTEMPTS.append(True)
    raise AssertionError("Budget regression must not open sockets or resolve DNS")


socket.socket.connect = socket.socket.connect_ex = socket.create_connection = socket.getaddrinfo = blocked
from server.agents import author, narration, plan


def segment(sid, facts, role="proof", stop=None, budget=45):
    return {"id": sid, "title": sid, "role": role, "topic": stop or sid,
            "stop_id": stop, "fundamental": sid == "powertrain", "fact_ids": facts,
            "goal": f"Keep the source conditions. word_budget: {budget}", "word_budget": budget}


def actual_shape():
    """The paid plan's nine segment budgets and two overlapping tail assignments."""
    groups = ["powertrain", "stance-and-ride", "space-and-practicality", "safety",
              "cabin-and-tech", "delighters", "ownership"]
    evidence = {key: [f"{key}-{i}" for i in range(4)] for key in groups}
    evidence["delighters"] += ["F138", "F140"]
    evidence["ownership"] += ["F177", "F181", "F185"]
    segments = [segment(key, evidence[key], stop=key, budget=budget)
                for key, budget in zip(groups, [51, 51, 51, 50, 45, 45, 45])]
    segments += [segment("more_features", ["F138", "F140"], "features"),
                 segment("establish", ["F177", "F181", "F185"], "establish", budget=44)]
    segments[-1]["topic"] = "ownership"
    outline = {"segments": segments, "narration_preparation": {"version": 1, "target_words": 495}}
    book = {"category": "Compact SUV", "stops": [{"id": key, "fact_ids": ids} for key, ids in evidence.items()]}
    return outline, {"product": {"category": "Compact SUV"}, "settings": {"pitch_minutes": 3}}, book


def count(row):
    match = re.search(r"Prepared delivery allocation: (\d+) complete main", row["goal"])
    return int(match[1]) if match else 0


class PreparedBudgetContract(unittest.TestCase):
    def tearDown(self):
        self.assertFalse(ATTEMPTS)

    def legal(self, outline):
        for row in outline["segments"]:
            if row["role"] not in narration.ROLES:
                continue
            n = count(row)
            self.assertTrue(26 * n <= row["word_budget"] <= 33 * n, row)
            self.assertLessEqual(33, author.LIMITS[row["role"]])

    def test_actual_nine_stop_scalar_contradiction_is_repaired(self):
        p, d, pb = actual_shape()
        self.assertEqual([s["word_budget"] for s in p["segments"]], [51, 51, 51, 50, 45, 45, 45, 45, 44])
        plan._enforce_budget(p, d, pb)
        self.legal(p)
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 427)
        self.assertEqual(count(p["segments"][0]), 3)
        self.assertFalse(p["issues"])

    def test_unlabelled_tails_share_coach_evidence_attention(self):
        p, d, pb = actual_shape(); plan._enforce_budget(p, d, pb)
        self.assertEqual(count(p["segments"][5]) + count(p["segments"][7]), 2)
        self.assertEqual(count(p["segments"][6]) + count(p["segments"][8]), 2)
        self.assertEqual([count(s) for s in p["segments"]], [3, 2, 2, 2, 2, 1, 1, 1, 1])

    def test_explicit_shared_ids_cannot_multiply_capacity(self):
        p, d, pb = actual_shape(); p["segments"][7]["stop_id"] = "delighters"
        plan._enforce_budget(p, d, pb)
        self.assertEqual(count(p["segments"][5]) + count(p["segments"][7]), 2)
        self.legal(p)

    def test_repeat_preparation_preserves_exact_goals_and_budgets(self):
        p, d, pb = actual_shape(); plan._enforce_budget(p, d, pb); once = copy.deepcopy(p)
        plan._enforce_budget(p, d, pb); self.assertEqual(p, once)
        self.assertTrue(all(s["goal"].count("Prepared delivery allocation:") == 1 for s in p["segments"]))

    def test_story_ids_facts_order_and_conditions_are_unchanged(self):
        p, d, pb = actual_shape(); before = copy.deepcopy(p)
        plan._enforce_budget(p, d, pb)
        for old, new in zip(before["segments"], p["segments"]):
            for key in ("id", "title", "role", "topic", "stop_id", "fact_ids", "fundamental"):
                self.assertEqual(old[key], new[key])
            self.assertTrue(new["goal"].startswith("Keep the source conditions."))
            self.assertIn(f"word_budget: {new['word_budget']}", new["goal"])

    def test_empty_evidence_has_zero_capacity_and_explicit_infeasibility(self):
        p, d, pb = actual_shape()
        for s in p["segments"]: s["fact_ids"] = []
        plan._enforce_budget(p, d, pb)
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 0)
        self.assertTrue(any("cannot fit" in issue for issue in p["issues"]))
        self.legal(p)

    def test_thin_compact_lead_cannot_fake_three_batches(self):
        p, d, pb = actual_shape(); p["segments"][0]["fact_ids"] = ["powertrain-0"]
        plan._enforce_budget(p, d, pb)
        self.assertTrue(any("three planned delivery batches" in issue for issue in p["issues"]))
        self.assertLess(sum(s["word_budget"] for s in p["segments"]), 427)

    def test_five_supported_library_stops_cannot_claim_seven_stop_duration(self):
        p, d, pb = actual_shape()
        p["segments"] = [s for s in p["segments"] if s.get("stop_id") not in {"cabin-and-tech", "delighters"}]
        p["segments"] = [s for s in p["segments"] if s["id"] != "more_features"]
        plan._enforce_budget(p, d, pb)
        self.assertLess(sum(s["word_budget"] for s in p["segments"]) + 68, 495)
        self.assertTrue(any("cannot fit" in issue for issue in p["issues"]))
        self.legal(p)

    def test_mixed_tail_is_not_a_new_independent_stop(self):
        p, d, pb = actual_shape(); p["segments"][7]["fact_ids"] = ["F138", "F177"]
        plan._enforce_budget(p, d, pb)
        self.assertEqual(p["segments"][7]["word_budget"], 0)
        self.assertTrue(any("mixed stop evidence" in issue for issue in p["issues"]))
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 427)
        self.assertFalse(any("cannot fit" in issue for issue in p["issues"]))

    def test_unmapped_compact_tail_needs_review_not_extra_capacity(self):
        p, d, pb = actual_shape(); p["segments"][7]["fact_ids"] = ["unmapped-approved-detail"]
        plan._enforce_budget(p, d, pb)
        self.assertEqual(p["segments"][7]["word_budget"], 0)
        self.assertTrue(any("reviewed stop assignment" in issue for issue in p["issues"]))

    def test_generic_no_coach_outline_retains_supported_capacity(self):
        p = {"segments": [segment(f"stop{i}", [f"F{i}a", f"F{i}b", f"F{i}c"], budget=70) for i in range(6)],
             "narration_preparation": {"version": 1, "target_words": 495}}
        plan._enforce_budget(p, {})
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 427)
        self.assertFalse(p["issues"])
        self.legal(p)

    def test_one_to_five_minutes_respect_target_and_existing_role_capacity(self):
        for minutes in range(1, 6):
            with self.subTest(minutes=minutes):
                p = {"segments": [segment(f"stop{i}", [f"{i}-{j}" for j in range(4)]) for i in range(2 * minutes)],
                     "narration_preparation": {"version": 1, "target_words": 165 * minutes}}
                d = {"settings": {"pitch_minutes": minutes}}
                plan._enforce_budget(p, d); self.legal(p)
                body = sum(s["word_budget"] for s in p["segments"])
                self.assertGreaterEqual(body + 68, minutes * 165)
                self.assertLessEqual(body + 28 + 45, author.route_limit(d, p))
                self.assertFalse(p["issues"])
                for s in p["segments"]:
                    self.assertLessEqual(count(s), min(max(3, minutes), len(s["fact_ids"])))

    def test_smallest_feasible_surplus_uses_existing_route_headroom(self):
        p = {"segments": [segment("stop", ["F1", "F2"])],
             "narration_preparation": {"version": 1, "target_words": 102}}
        plan._enforce_budget(p, {"settings": {"pitch_minutes": 1}})
        self.assertEqual(p["segments"][0]["word_budget"], 52)  # 34 cannot form whole thoughts.
        self.assertLessEqual(52 + 28 + 45, author.route_limit({}, p))
        self.assertFalse(p["issues"])

    def test_secondary_tail_role_never_contributes_unplayed_capacity(self):
        p, d, pb = actual_shape(); extra = copy.deepcopy(p["segments"][7]); extra["id"] = "second_features"
        p["segments"].append(extra); plan._enforce_budget(p, d, pb)
        self.assertEqual(p["segments"][-1]["word_budget"], 0)
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 427)

    def test_excessive_required_stops_report_infeasible_with_bounded_states(self):
        p = {"segments": [segment(f"stop{i}", [f"F{i}"]) for i in range(80)],
             "narration_preparation": {"version": 1, "target_words": 165}}
        plan._enforce_budget(p, {"settings": {"pitch_minutes": 1}})
        self.assertTrue(any("cannot fit" in issue for issue in p["issues"]))
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 0)

    def test_one_minute_cannot_silently_skip_seven_required_library_stops(self):
        p, d, pb = actual_shape(); d["settings"]["pitch_minutes"] = 1
        p["narration_preparation"]["target_words"] = 165
        identities = [s["id"] for s in p["segments"]]
        plan._enforce_budget(p, d, pb)
        self.assertEqual([s["id"] for s in p["segments"]], identities)
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 0)
        self.assertTrue(any("cannot fit" in issue for issue in p["issues"]))

    def test_legacy_unprepared_allocation_is_unchanged(self):
        p = {"segments": [segment(f"stop{i}", [f"F{i}"]) for i in range(7)]}
        plan._enforce_budget(p, {})
        self.assertEqual(p["total_words"], 342)
        self.assertEqual(sum(s["word_budget"] for s in p["segments"]), 274)
        self.assertFalse(any("Prepared delivery allocation:" in s["goal"] for s in p["segments"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
