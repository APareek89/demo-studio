"""Actual q032 diesel recovery, retaining assertion and unit rejection gates.

This is a local validator replay: no provider, fetch, source or publication write.
The fixture retains original live drafts and restores the full pinned assertions.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import unittest

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
OUTBOUND = []


def no_network(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Grouped quantity contracts must not open sockets")


socket.socket.connect = no_network
socket.create_connection = no_network

from server import runtime_graph as graph


FIXTURE_PATH = Path(__file__).parent / "fixtures/runtime_grouped_quantities.json"
FIXTURE_BYTES = FIXTURE_PATH.read_bytes()
FIXTURE = json.loads(FIXTURE_BYTES)
REGISTRY = {fact["id"]: fact for fact in FIXTURE["full_pinned_assertions"]}


def actual(phase="repair"):
    event = FIXTURE["events"][1 if phase == "repair" else 0]
    payload = copy.deepcopy(event["payload"])
    evidence = []
    for model_fact in payload["evidence"]:
        fact = copy.deepcopy(REGISTRY.get(model_fact["id"], model_fact))
        fact.update({key: copy.deepcopy(model_fact[key]) for key in
                     ("applicability_projection", "runtime_variant_boundary", "entity", "competition")
                     if key in model_fact})
        evidence.append(fact)
    return {"action": "answer", **json.loads(event["response"])}, evidence, payload


def validate(decision=None, phase="repair"):
    recorded, evidence, payload = actual(phase)
    feedback = []
    result, errors = graph.validate_decision(
        decision or recorded, evidence, payload["question"],
        requested_scope=payload.get("requested_scope"), row_feedback=feedback)
    return result, errors, feedback


def power(text):
    return {"action": "answer", "sentences": [
        {"text": text, "fact_ids": ["F227"], "kind": "fact"}]}


class GroupedQuantityContract(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def test_immutable_actual_fixture_identity_and_hydrated_assertions(self):
        self.assertEqual(hashlib.sha256(FIXTURE_BYTES).hexdigest(),
                         "38805917629ff85148f2d7c9ac955e06a06b4e3b2c7a950c18f80f51d5a29c48")
        self.assertEqual(FIXTURE["code_commit"], "d7c4bbedfb2d2007fc57413bccb7d34b32946689")
        self.assertEqual(FIXTURE["original_result_row"]["result"]["answered"], False)
        self.assertEqual(REGISTRY["F227"]["value"], "85 kW (116 PS) @ 4 000 r/min")
        self.assertEqual(REGISTRY["F228"]["value"], "250 Nm (25.5 kgm) @ 1 500-2 750 r/min")
        for event in FIXTURE["events"]:
            self.assertRegex(event["raw_trace_sha256"], r"^[a-f0-9]{64}$")

    def test_exact_actual_repair_delivers_both_reviewed_figures(self):
        result, errors, _ = validate()
        self.assertEqual(errors, [])
        self.assertTrue(result["answered"])
        self.assertEqual(result["fact_ids"], ["F227", "F228"])
        for phrase in ("85 kW (116 PS) @ 4 000 r/min", "250 Nm (25.5 kgm) @ 1 500-2 750 r/min"):
            self.assertIn(phrase, result["answer"])

    def test_initial_ambiguous_pulling_power_stays_conservatively_rejected(self):
        result, errors, feedback = validate(phase="initial")
        self.assertEqual(errors, ["unsupported_assertion_feature"])
        self.assertEqual(result["fact_ids"], ["F227"])
        self.assertIn("85 kW", result["answer"])
        self.assertNotIn("pulling power", result["answer"])
        self.assertEqual(feedback[0]["fact_ids"], ["F228"])

    def test_plain_nbsp_narrow_and_compact_grouping_preserve_same_quantities(self):
        for separator in (" ", "\u00a0", "\u202f", ""):
            with self.subTest(separator=repr(separator)):
                decision, _, _ = actual()
                for row in decision["sentences"]:
                    for grouped in ("4 000", "1 500", "2 750"):
                        row["text"] = row["text"].replace(grouped, grouped.replace(" ", separator))
                result, errors, _ = validate(decision)
                self.assertEqual(errors, [])
                self.assertEqual(result["fact_ids"], ["F227", "F228"])

    def test_malformed_or_cross_line_groups_are_not_repaired_into_valid_rpm(self):
        for malformed in ("40 00", "4 00", "4 0000", "4  000", "4\n000", "4\t000"):
            with self.subTest(malformed=repr(malformed)):
                result, errors, _ = validate(power("The diesel engine produces 85 kW (116 PS) at " + malformed + " r/min."))
                self.assertIn("unsupported_quantity", errors)
                self.assertFalse(result["fact_ids"])

    def test_changed_grouped_values_and_range_endpoints_remain_unsupported(self):
        for old, new in (("4 000", "5 000"), ("1 500", "1 600"), ("2 750", "3 500")):
            with self.subTest(old=old, new=new):
                decision, _, _ = actual()
                changed = next(row for row in decision["sentences"] if old in row["text"])
                changed["text"] = changed["text"].replace(old, new)
                result, errors, feedback = validate({"action": "answer", "sentences": [changed]})
                self.assertIn("unsupported_quantity", errors)
                self.assertFalse(result["fact_ids"])

    def test_same_number_cannot_borrow_another_unit_or_convert_units(self):
        for text in (
            "The diesel engine makes maximum power of 85 PS (116 kW) at 4 000 r/min.",
            "The diesel engine makes maximum power of 85 bhp at 4 000 r/min.",
            "The diesel engine makes maximum power of 85 kW at 4 000 Nm.",
        ):
            with self.subTest(text=text):
                result, errors, _ = validate(power(text))
                self.assertTrue(errors)
                self.assertFalse(result["fact_ids"])
        decision, _, _ = actual()
        row = decision["sentences"][1]
        row["text"] = row["text"].replace("250 Nm", "250 kW")
        result, errors, _ = validate({"action": "answer", "sentences": [row]})
        self.assertTrue(errors)
        self.assertFalse(result["fact_ids"])

    def test_full_provenance_table_is_not_quantity_authority_for_cited_assertion(self):
        # 6300 belongs to the petrol column in the same PDF extract. Citation F227
        # only approves diesel 85 kW/116 PS at 4000 rpm; the raw table cannot lend 6300.
        self.assertIn("6 300 r/min", REGISTRY["F227"]["source"]["quote"])
        result, errors, _ = validate(power("The diesel maximum power is 85 kW (116 PS) at 6 300 r/min."))
        self.assertIn("unsupported_quantity", errors)
        self.assertFalse(result["fact_ids"])


if __name__ == "__main__":
    unittest.main()
