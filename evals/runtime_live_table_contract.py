"""Pure live-table universal-fitment controls with exact saved q068 replay."""
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import unittest

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
OUTBOUND = []


def block(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("No provider or source fetch in live-table contracts")


socket.socket.connect = block
socket.create_connection = block

from server.runtime_tables import unsupported_live_table_universal as rejects
from server.runtime_graph import validate_decision

FIXTURE_BYTES = (Path(__file__).parent / "fixtures/runtime_live_table_universal.json").read_bytes()
FIXTURE = json.loads(FIXTURE_BYTES)


def table(rows=None, footnote="", header=None):
    return {"id": "Wtest", "provenance": "live_web", "approved": True,
            "claim": "Customer-selected website passage", "value": "",
            "source": {"ref": "https://example.com/model/features"},
            "context": {"kind": "table", "footnote": footnote,
                        "rows": [header or ["Feature", "Base", "Plus", "Premium"],
                                 *(rows or [["Rear AC vent", "Standard", "Standard", "Standard"]])]}}


class LiveTableContract(unittest.TestCase):
    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def test_exact_recorded_case_retains_hashes_and_scope_error(self):
        self.assertEqual(hashlib.sha256(FIXTURE_BYTES).hexdigest(),
                         "4515b0fa84caa9b1323ab248e10d6766fd488b935006688a3ed6e51e05cac23f")
        self.assertEqual(FIXTURE["code_commit"], "b01b0c66781388b8de363cd6f915e2e98facee72")
        row = FIXTURE["original_result_row"]
        self.assertTrue(rejects(row["result"]["answer"], row["result"]["facts"]))
        decision = json.loads(FIXTURE["events"][0]["response"])
        result, errors = validate_decision(decision, row["result"]["facts"], row["question"])
        self.assertIn("unsupported_live_table_universal", errors)
        self.assertNotIn("across the lineup", result["answer"])
        self.assertIn("front ventilated seats on select higher variants", result["answer"])

    def test_model_context_or_limitation_label_cannot_bypass_cited_claim_guard(self):
        row = FIXTURE["original_result_row"]
        for kind in ("context", "limitation"):
            decision = json.loads(FIXTURE["events"][0]["response"])
            decision["sentences"][1]["kind"] = kind
            result, errors = validate_decision(decision, row["result"]["facts"], row["question"])
            with self.subTest(kind=kind):
                self.assertIn("unsupported_live_table_universal", errors)
                self.assertNotIn("across the lineup", result["answer"])
                self.assertIn("front ventilated seats on select higher variants", result["answer"])
        decision = {"action": "answer", "sentences": [{
            "kind": "limitation", "fact_ids": [], "text": "I cannot verify that."}]}
        result, errors = validate_decision(decision, row["result"]["facts"], row["question"])
        self.assertEqual(result["answer"], "I couldn't verify that.")
        self.assertEqual(errors, [])

    def test_all_every_and_across_phrases_need_own_full_row(self):
        good = table()
        bad = table([["Rear AC vent", "Standard", "-", "Standard"]])
        for phrase in ("on all trims", "on every variant", "on each version", "across the lineup",
                       "throughout the full range", "across the entire line-up"):
            text = "Rear air-conditioning vents are available " + phrase + "."
            with self.subTest(phrase=phrase):
                self.assertFalse(rejects(text, [good]))
                self.assertTrue(rejects(text, [bad]))

    def test_shared_list_requires_each_named_feature_not_one_good_row(self):
        f = table([["Rear AC vent", "Standard", "Standard", "Standard"],
                   ["Smartphone wireless charger", "-", "Standard", "Standard"],
                   ["Cruise control", "-", "Standard", "Standard"],
                   ["Rear center armrest with cup holders", "Yes", "Yes", "Yes"]])
        self.assertTrue(rejects("It highlights wireless smartphone charging, rear air-conditioning vents, cruise control, and a rear centre armrest with cup holders across the lineup.", [f]))
        self.assertFalse(rejects("Rear air-conditioning vents and a rear centre armrest with cup holders are standard across the lineup.", [f]))
        self.assertTrue(rejects("Heated seats are standard across the lineup.", [f]))
        self.assertTrue(rejects("Rear air-conditioning vents and heated seats are standard across the lineup.", [f]))

    def test_bare_s_needs_captured_legend_even_when_all_cells_are_s(self):
        f = table([["Rear AC vent", "S", "S", "S"]])
        text = "Every trim has rear air-conditioning vents."
        self.assertTrue(rejects(text, [f]))
        f["context"]["footnote"] = "S: Standard; O: Optional; -: Not available"
        self.assertFalse(rejects(text, [f]))
        f["context"]["footnote"] = "S: Not standard"
        self.assertTrue(rejects(text, [f]))

    def test_unknown_conditional_and_footnoted_status_never_grants_universal(self):
        for mark in ("-", "", "?", "O", "Available", "S*", "✓", "TBD", "Unknown"):
            f = table([["Rear AC vent", "Standard", mark, "Standard"]], "S: Standard")
            with self.subTest(mark=mark):
                self.assertTrue(rejects("All trims have rear AC vents.", [f]))
        for f in (table([["Rear AC vent*", "Standard", "Standard", "Standard"]]),
                  table(footnote="Only available with automatic transmission"),
                  table([["Rear AC vent", "S", "S", "S"]], "S: Standard on selected engines")):
            self.assertTrue(rejects("All trims have rear AC vents.", [f]))

    def test_malformed_extra_status_or_missing_cells_cannot_shift_columns(self):
        for row in (["Rear AC vent", "Standard", "Standard"],
                    ["Rear AC vent", "-", "Standard", "Standard", "Standard"],
                    ["Rear AC vent", "X", "Standard", "Standard", "Standard"],
                    ["Rear AC vent", "Standard", "Standard", "Standard", "Standard", "Standard"]):
            with self.subTest(row=row):
                self.assertTrue(rejects("Rear AC vents are standard on every trim.", [table([row])]))

    def test_duplicate_empty_truncated_or_missing_headers_cannot_license(self):
        for header in (["Feature", "Base", "Base", "Premium"],
                       ["Feature", "Base", "", "Premium"],
                       ["Feature", "Base", "...", "Premium"],
                       ["Feature", "Base", "Plus"],
                       ["Feature"]):
            self.assertTrue(rejects("Rear AC vents are standard on every trim.", [table(header=header)]))
        f = table(); f["context"].pop("rows")
        self.assertTrue(rejects("All trims have rear AC vents.", [f]))

    def test_two_label_cells_preserve_both_descriptors_and_exact_columns(self):
        f = table([["Power windows", "Front", "Standard", "Standard", "Standard"]])
        self.assertFalse(rejects("Front power windows are standard on every trim.", [f]))
        self.assertTrue(rejects("Rear power windows are standard on every trim.", [f]))
        self.assertTrue(rejects("Power windows are standard on every trim.", [f]))

    def test_multiple_tables_cannot_merge_different_header_universes(self):
        first = table([["Front wireless charger", "Yes", "Yes", "Yes"]])
        second = table([["Rear AC vent", "Yes", "Yes", "Yes"]])
        text = "Front wireless charging and rear AC vents are standard across the lineup."
        self.assertFalse(rejects(text, [first, second]))
        second["context"]["rows"][0] = ["Feature", "Premium", "Base", "Plus"]
        self.assertFalse(rejects(text, [first, second]))  # no trim order inferred
        second["context"]["rows"][0] = ["Feature", "Base", "Sport", "Premium"]
        self.assertTrue(rejects(text, [first, second]))

    def test_own_feature_modifiers_and_numbers_cannot_be_borrowed(self):
        f = table([["Front wireless charger", "Yes", "Yes", "Yes"],
                   ["Rear wireless charger", "-", "Yes", "Yes"],
                   ["12 inch display", "Yes", "Yes", "Yes"]])
        self.assertFalse(rejects("Front wireless charging is available on every trim.", [f]))
        self.assertTrue(rejects("Rear wireless charging is available on every trim.", [f]))
        self.assertFalse(rejects("12-inch displays are available on every trim.", [f]))
        self.assertTrue(rejects("8-inch displays are available on every trim.", [f]))

    def test_coordinated_features_cannot_swap_front_rear_modifiers(self):
        f = table([["Front wireless charger", "Yes", "Yes", "Yes"],
                   ["Rear AC vent", "Yes", "Yes", "Yes"]])
        self.assertFalse(rejects("Front wireless charging and rear AC vents are available across the lineup.", [f]))
        for text in (
            "Rear wireless charging and front AC vents are available across the lineup.",
            "Rear wireless charging, front AC vents are available across the lineup.",
            "Rear wireless charging with front AC vents is available across the lineup.",
        ):
            with self.subTest(text=text): self.assertTrue(rejects(text, [f]))

    def test_negated_quantifier_cannot_exempt_another_positive_universal(self):
        f = table([["Heated seats", "-", "Yes", "Yes"],
                   ["Wireless charger", "-", "Yes", "Yes"]])
        self.assertFalse(rejects("Not all trims have heated seats.", [f]))
        for text in (
            "Not all trims have heated seats, and wireless charging is standard on all trims.",
            "Not every variant has heated seats and wireless charging is standard across the lineup.",
            "Wireless charging is standard on all trims, and not all trims have heated seats.",
        ):
            with self.subTest(text=text): self.assertTrue(rejects(text, [f]))

    def test_nonuniversal_inventory_and_selected_fitment_are_unchanged(self):
        f = table([["Smartphone wireless charger", "-", "S", "S"]])
        for text in ("The page lists wireless smartphone charging.",
                     "Wireless smartphone charging is available on selected trims.",
                     "The range offers wireless smartphone charging on equipped variants.",
                     "Not all trims have wireless smartphone charging."):
            with self.subTest(text=text): self.assertFalse(rejects(text, [f]))

    def test_independent_clause_can_keep_its_own_universal_qualification(self):
        f = table([["Rear AC vent", "Standard", "Standard", "Standard"],
                   ["Smartphone wireless charger", "-", "Standard", "Standard"]])
        self.assertFalse(rejects("Rear AC vents are standard across the lineup, while wireless smartphone charging is available on selected trims.", [f]))
        self.assertTrue(rejects("Rear AC vents and wireless smartphone charging are standard across the lineup.", [f]))

    def test_later_verb_cannot_strip_an_earlier_restricted_feature(self):
        f = table([["Rear AC vent", "Standard", "Standard", "Standard"],
                   ["Wireless charger", "-", "Standard", "Standard"],
                   ["Storage", "Standard", "Standard", "Standard"]])
        self.assertTrue(rejects("Rear AC vents and wireless charging across the lineup, and the armrest has storage.", [f]))

    def test_positive_row_cannot_authorize_universal_negative(self):
        self.assertTrue(rejects("Every trim does not include rear AC vents.", [table()]))

    def test_nonlive_and_non_table_assertions_remain_existing_guard_owned(self):
        f = table(); f["provenance"] = "uploaded"
        self.assertFalse(rejects("All trims have rear AC vents.", [f]))
        f = table(); f["context"]["kind"] = "text"
        self.assertFalse(rejects("All trims have rear AC vents.", [f]))


if __name__ == "__main__":
    unittest.main()
