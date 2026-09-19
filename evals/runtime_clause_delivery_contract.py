"""Offline actual-draft delivery regressions, not a new live quality score.

Fixtures preserve exact original/repair drafts and their trace/row hashes. Guard
inputs restore the pinned full assertions, because compact model projections
are deliberately not the evidence representation used by runtime validation.
"""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import time
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")


def no_network(*args, **kwargs):
    raise AssertionError("Clause delivery contracts must not open sockets")


socket.socket.connect = no_network
socket.create_connection = no_network

from server import runtime_graph as graph
from server.runtime_state import TurnControl
from server.runtime_tools import calculate


FIXTURE_PATH = Path(__file__).parent / "fixtures/runtime_clause_delivery.json"
FIXTURE_BYTES = FIXTURE_PATH.read_bytes()
FIXTURE = json.loads(FIXTURE_BYTES)
FINAL_FIXTURE_PATH = Path(__file__).parent / "fixtures/runtime_clause_final.json"
FINAL_FIXTURE_BYTES = FINAL_FIXTURE_PATH.read_bytes()
FINAL_FIXTURE = json.loads(FINAL_FIXTURE_BYTES)
REGISTRY = {fact["id"]: fact for fixture in (FIXTURE, FINAL_FIXTURE)
            for fact in fixture["lineage_registry"]["facts"]}
DYNAMIC_FIELDS = ("applicability_projection", "runtime_variant_boundary", "entity", "competition")


def case(key, phase="initial"):
    source = FIXTURE if key in FIXTURE["cases"] else FINAL_FIXTURE
    raw = copy.deepcopy(source["cases"][key])
    draft = next(d for d in raw["drafts"] if d["phase"] == phase)
    evidence = []
    for model_fact in draft["evidence"]:
        if model_fact["id"] in REGISTRY:
            fact = copy.deepcopy(REGISTRY[model_fact["id"]])
            fact.update({k: copy.deepcopy(model_fact[k]) for k in DYNAMIC_FIELDS if k in model_fact})
            evidence.append(fact)
        else:
            evidence.append(copy.deepcopy(model_fact))
    return {**raw, **draft, "decision": {"action": "answer", **draft["decision"]}, "evidence": evidence}


def validate(c, decision=None):
    feedback, limits = [], []
    result, errors = graph.validate_decision(decision or c["decision"], c["evidence"], c["question"],
                                            requested_scope=c["requested_scope"],
                                            row_feedback=feedback, validated_limits=limits)
    return result, errors, feedback, limits


def one_row(text, ids=(), kind="fact"):
    return {"action": "answer", "answered": True,
            "sentences": [{"text": text, "kind": kind, "fact_ids": list(ids)}]}


class ClauseDeliveryContract(unittest.TestCase):
    def test_fixture_lineage_and_full_assertion_hydration(self):
        self.assertEqual(FIXTURE["code_commit"], "24736a0c8a57c6f0772edbc778bbef3306bd60ef")
        self.assertEqual(FIXTURE["snapshot_id"], "kb_2d616ba1bcec1469e8c7ab40")
        self.assertEqual(len(FIXTURE["cases"]), 10)
        for raw in FIXTURE["cases"].values():
            self.assertRegex(raw["raw_row_sha256"], r"^[a-f0-9]{64}$")
            for draft in raw["drafts"]:
                self.assertRegex(draft["trace_raw_sha256"], r"^[a-f0-9]{64}$")
                self.assertRegex(draft["raw_decision_sha256"], r"^[a-f0-9]{64}$")
        c = case("q043")
        fact = next(f for f in c["evidence"] if f["id"] == "F159")
        self.assertIn("Dual zone automatic temperature control (DATC)", fact["value"])
        self.assertTrue(fact["applicability_projection"])
        self.assertEqual(graph._reason_evidence(fact), next(f for f in c["drafts"][0]["evidence"] if f["id"] == "F159"))

    def test_q002_keeps_precise_capacity_and_measurement_limits(self):
        for phase in ("initial", "repair"):
            with self.subTest(phase=phase):
                result, errors, _, limits = validate(case("q002", phase))
                self.assertIn("boot capacity", result["answer"])
                self.assertRegex(result["answer"], r"litres|liters")
                self.assertIn("measurement", result["answer"])
                self.assertTrue(limits)
                self.assertNotIn("are not specified in the current records", result["answer"])
                self.assertEqual(set(result["fact_ids"]), {"F096", "F097"})

    def test_q016_own_missing_listing_is_not_whole_source_absence(self):
        result, errors, _, limits = validate(case("q016"))
        self.assertIn("I couldn't verify a rear-seat armrest", result["answer"])
        self.assertTrue(limits)
        self.assertNotIn("CRETA does not have", result["answer"])

    def test_q039_repaired_comparison_keeps_all_three_differences(self):
        result, errors, _, _ = validate(case("q039", "repair"))
        self.assertFalse(errors)
        self.assertEqual(set(result["fact_ids"]), {"F247", "F248", "F249"})
        for phrase in ("wheel covers", "dual-tone styled steel", "sunroof", "rear camera with dynamic guidelines"):
            self.assertIn(phrase, result["answer"])
        self.assertIn("not available on the EX.", result["answer"])
        self.assertNotIn("not available on the EX(O)", result["answer"])
        initial, _, _, _ = validate(case("q039"))
        self.assertFalse(initial["answered"])
        self.assertFalse(initial["fact_ids"])

    def test_swapped_relative_and_standard_clauses_cannot_reverse_fitment(self):
        c = case("q039", "repair")
        for text, ids in (
            ("The EX also includes a standard rear camera with dynamic guidelines, which the EX(O) does not offer.", ["F248"]),
            ("A smart panoramic sunroof is standard on the EX, but it is not available on the EX(O).", ["F247"]),
            ("The EX(O) also includes a standard rear camera with dynamic guidelines, which the King does not offer.", ["F248"]),
        ):
            with self.subTest(text=text):
                result, errors, _, _ = validate(c, one_row(text, ids))
                self.assertTrue(errors)
                self.assertNotIn("not available on the EX(O)", result["answer"])
                self.assertNotIn("not available on the King", result["answer"])
                self.assertNotIn("The EX has a standard rear camera", result["answer"])

    def test_q043_full_assertions_retain_shared_ac_and_plural_ventilation(self):
        for phase in ("initial", "repair"):
            with self.subTest(phase=phase):
                result, errors, _, _ = validate(case("q043", phase))
                self.assertFalse(errors)
                for phrase in ("Both the SX and SX Premium", "automatic air conditioning", "electric driver seat adjustment", "memory function"):
                    self.assertIn(phrase, result["answer"])
                self.assertIn("not available on the SX", result["answer"])
                self.assertNotIn("ventilated seats is", result["answer"])

    def test_q052_keeps_audited_inputs_and_material_emi_caveat(self):
        result, _, _, _ = validate(case("q052"))
        for phrase in ("19,530", "8 lakh", "8 percent annual", "4 years", "excludes fees and taxes", "not a lender quote"):
            self.assertIn(phrase, result["answer"])

    def test_emi_result_alone_cannot_drop_audited_assumptions(self):
        c = case("q052")
        result, _, _, _ = validate(c, {**c["decision"], "sentences": c["decision"]["sentences"][:1]})
        # Either natural quoted input wording or deterministic numeric delivery
        # may carry these values, but every operand and the rate basis survives.
        for pattern in (r"800000|8,00,000|8 lakh", r"8(?:\.0)?\s*(?:%|percent).*?annual", r"4(?:\.0)?\s+years"):
            self.assertRegex(result["answer"], pattern)
        self.assertIn("not a lender quote", result["answer"])
        self.assertIn("fees and taxes", result["answer"])

    def test_monthly_interest_basis_and_canonical_fallback_are_not_duplicated(self):
        c = case("q052")
        question = "Use an 8 lakh rupee loan at 1 percent monthly interest over 4 years."
        inputs = [{"name": name, "value": value, "unit": unit, "source_id": "customer", "quote": quote}
                  for name, value, unit, quote in (
                      ("principal", 800000, "INR", "8 lakh rupee loan"),
                      ("monthly_rate", 1, "percent", "1 percent monthly interest"),
                      ("tenure", 4, "years", "4 years"),
                  )]
        calculated = calculate({"tool": "calculator", "operation": "emi", "inputs": inputs}, [], question)
        c.update(question=question, evidence=[calculated])
        result, _, _, _ = validate(c, one_row("The estimated payment is " + calculated["derivation"]["value"] + " rupees per month.", [calculated["id"]]))
        self.assertIn("1% monthly interest", result["answer"])
        self.assertNotIn("annual", result["answer"])
        self.assertIn("800000 rupees", result["answer"])
        self.assertIn("4 years", result["answer"])
        self.assertEqual(result["answer"].count("not a lender quote"), 1)
        # No model rows: deterministic audited delivery already has every
        # operand. It must not gain a duplicate assumptions/caveat sentence.
        result, _, _, _ = validate(c, {"action": "answer", "sentences": []})
        self.assertEqual(result["answer"].count("800000 rupees"), 1)
        self.assertEqual(result["answer"].count("1% monthly interest"), 1)
        self.assertEqual(result["answer"].count("not a lender quote"), 1)
        self.assertNotIn("This estimate uses", result["answer"])

    def test_q060_and_q072_ask_actual_missing_inputs_without_fake_tool_success(self):
        result, _, _, _ = validate(case("q060"))
        self.assertEqual(result["answer"], "Please share your fuel efficiency and fuel price.")
        self.assertFalse(result["fact_ids"])
        result, _, _, _ = validate(case("q072"))
        self.assertEqual(result["answer"], "Please share a public HTTP or HTTPS product page.")
        self.assertFalse(result["fact_ids"])

    def test_input_normalization_cannot_emit_unknown_slots_or_appended_claims(self):
        c = case("q060")
        for text in (
            "I will need your password and bank approval.",
            "I will need your expected fuel efficiency and all trims have ADAS.",
            "I will need your fuel price, and the car has twelve airbags.",
            "Please share the URL whenever you are ready. The car has twelve airbags.",
            "Please share the URL because every trim has ADAS.",
            "Since every trim has ADAS, I will need your fuel efficiency and fuel price.",
        ):
            with self.subTest(text=text):
                result, _, _, _ = validate(c, one_row(text, kind="context"))
                self.assertNotIn("ADAS", result["answer"])
                self.assertNotIn("twelve airbags", result["answer"])
                self.assertNotIn("password", result["answer"])
                self.assertFalse(result["fact_ids"])

    def test_q092_and_q095_keep_own_behavior_and_refusal_without_world_reasons(self):
        result, _, _, _ = validate(case("q092"))
        self.assertEqual(result["answer"], "No, that will not change my answer.")
        result, _, _, _ = validate(case("q095"))
        self.assertEqual(result["answer"], "I cannot guarantee that a future offer is available today.")
        self.assertNotIn("current stock", result["answer"])
        self.assertNotIn("today just", result["answer"])

    def test_colour_qualified_own_limits_and_fitcheck_do_not_claim_actions(self):
        c = case("q095")
        for text, expected in (
            ("I cannot verify delivery timelines or dealer stock for the King Knight in your preferred colour.", "for your preferred colour"),
            ("I cannot guarantee a delivery timeline for the King Knight in your chosen colour.", "for your chosen colour"),
            ("I don't have reviewed competitor comparison evidence available.", "I couldn't verify competitor comparison evidence."),
        ):
            with self.subTest(text=text):
                result, _, _, _ = validate(c, one_row(text, kind="limitation"))
                self.assertIn(expected, result["answer"])
                self.assertFalse(result["fact_ids"])
        for text in (
            "You can plan a seating fit-check with your family to see how comfortably everyone settles in.",
            "The best way to be sure is to bring them along for a quick seating fit-check.",
            "You might want to take a seat inside both models to see which fits you best.",
        ):
            with self.subTest(text=text):
                result, _, _, _ = validate(c, one_row(text, kind="context"))
                self.assertEqual(result["answer"], "You can check seat comfort on a test drive.")
                self.assertFalse(result["fact_ids"])
                self.assertFalse(result["cta"])
        for text in (
            "I cannot verify delivery timelines for your chosen colour because this car guarantees immediate delivery.",
            "You might want to take a seat inside both models to see which fits you best because both guarantee comfort.",
            "The best way to be sure is to bring them along for a quick seating fit-check; I have booked it for you.",
        ):
            with self.subTest(text=text):
                result, _, _, _ = validate(c, one_row(text, kind="context"))
                self.assertNotIn("guarantees immediate delivery", result["answer"])
                self.assertNotIn("guarantee comfort", result["answer"])
                self.assertNotIn("booked", result["answer"])
                self.assertFalse(result["cta"])

    def test_q099_repair_keeps_positive_king_and_negative_e_equipment(self):
        result, errors, _, _ = validate(case("q099", "repair"))
        self.assertFalse(errors)
        for phrase in ("King variant includes standard front row ventilated seats", "electric driver seat adjustment", "driver power seat memory", "dual zone automatic temperature control", "E trim offers manual air conditioning", "E variant does not include front row ventilated seats"):
            self.assertIn(phrase, result["answer"])

    def test_actual_q073_discards_false_source_check_and_duplicates(self):
        result, errors, _, _ = validate(case("q073"))
        self.assertIn("unverified_coverage_claim", errors)
        self.assertEqual(result["answer"].count("I couldn't verify that from the retrieved evidence."), 1)
        self.assertNotIn("There's a part of that I couldn't verify", result["answer"])
        self.assertNotIn("checked the highlights", result["answer"])
        self.assertNotIn("not mentioned", result["answer"])
        self.assertFalse(any(fid.startswith("W") for fid in result["fact_ids"]))
        for phrase in ("separate records", "up to 7 years", "petrol variants", "payable"):
            self.assertIn(phrase, result["answer"])
        self.assertEqual(set(result["fact_ids"]), {"F071", "F245"})

    def test_actual_q089_preserves_refusal_and_supported_safety(self):
        for phase in ("initial", "repair"):
            with self.subTest(phase=phase):
                result, _, _, limits = validate(case("q089", phase))
                self.assertRegex(result["answer"], r"I (?:cannot (?:confirm that claim|guarantee that)|couldn't verify that claim)")
                self.assertIn("six airbags", result["answer"])
                self.assertEqual(set(result["fact_ids"]), {"F174", "F195"})
                self.assertTrue(limits)
                self.assertNotIn("I do not have comparative evidence against every competitor", result["answer"])

    def test_actual_q090_preserves_exact_missing_boot_attribute_not_fabricated_citation(self):
        result, _, _, limits = validate(case("q090"))
        self.assertIn("I couldn't verify an unsupported boot capacity figure.", result["answer"])
        self.assertTrue(limits)
        self.assertNotIn("999", result["answer"])
        self.assertNotIn("F999999", result["fact_ids"])

    def test_new_refusal_grammar_cannot_license_appended_or_cited_product_claims(self):
        c = case("q090")
        for text in (
            "I cannot make that claim; all trims have ADAS.",
            "I cannot make that claim because the CRETA has 888 airbags.",
            "I cannot quote or invent an unsupported boot capacity figure because all trims have ADAS.",
            "I cannot quote or invent an 888 litre boot capacity figure.",
            "I cannot invent a vehicle that has bulletproof windows.",
            'The webpage says "I cannot make that claim; all trims have ADAS."',
        ):
            with self.subTest(text=text):
                result, _, _, _ = validate(c, one_row(text, kind="limitation"))
                self.assertFalse(result["fact_ids"])
                self.assertNotIn("all trims have ADAS", result["answer"])
                self.assertNotIn("888", result["answer"])
                self.assertNotIn("bulletproof", result["answer"])
        # A cited claim must retain ordinary grounding; attaching a real fuel
        # fact cannot turn this grammar into a citation-backed boot statement.
        text = "I cannot quote or invent an unsupported boot capacity figure."
        result, errors, _, _ = validate(c, one_row(text, ["F038"], kind="limitation"))
        self.assertTrue(errors)
        self.assertNotIn("I couldn't verify an unsupported boot capacity", result["answer"])
        self.assertFalse(result["fact_ids"])

    def test_known_power_seat_presence_cannot_imply_unlisted_trim_absence(self):
        c = case("q099", "repair")
        for text in (
            "The E variant does not include electric driver seat adjustment.",
            "The E variant does not have power driver seat adjustment.",
            "The SX does not offer electric 8-way driver seat adjustment.",
        ):
            with self.subTest(text=text):
                result, errors, _, _ = validate(c, one_row(text, ["F069"]))
                self.assertTrue(errors)
                self.assertFalse(result["answered"])
                self.assertNotIn(text, result["answer"])

    def test_partial_repair_preserves_existing_facts_and_gains_precise_limit(self):
        async def run():
            c, repaired = case("q002"), case("q002", "repair")
            original, errors, feedback, _ = validate(c)
            state = {**c, "demo_id": "clause-contract-unused", "session_id": "clause-contract-session",
                     "turn_id": "clause-contract-q002", "profile": {}, "history": [], "errors": [],
                     "control": TurnControl(time.monotonic() + 12), "tool_results": []}
            response = graph._CompositionRepair.model_validate({"sentences": repaired["decision"]["sentences"]})
            with patch.object(graph.config, "MOCK_LLM", False), patch.object(graph.runtime, "structured", return_value=response) as model, patch.object(graph.usage, "trace"):
                result, _, repair = await graph._repair_composition(state, original, errors, feedback, c["question"])
            self.assertEqual(model.call_count, 1)
            self.assertTrue(repair["accepted"])
            self.assertTrue(repair["partial"])
            self.assertEqual(set(result["fact_ids"]), set(original["fact_ids"]))
            self.assertIn("boot capacity", result["answer"])
            self.assertIn("measurement seat setup", result["answer"])
            self.assertNotIn("can confirm the exact boot volume", result["answer"])
        asyncio.run(run())

    def test_validation_never_mutates_immutable_fixture(self):
        for key in [*FIXTURE["cases"], *FINAL_FIXTURE["cases"]]:
            validate(case(key))
        self.assertEqual(hashlib.sha256(FIXTURE_PATH.read_bytes()).digest(), hashlib.sha256(FIXTURE_BYTES).digest())
        self.assertEqual(hashlib.sha256(FINAL_FIXTURE_PATH.read_bytes()).digest(), hashlib.sha256(FINAL_FIXTURE_BYTES).digest())


if __name__ == "__main__":
    unittest.main(verbosity=2)
