"""CR46 actual draft + condition-only dependency controls. Never calls providers."""
import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import time
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
outbound = []
def no_network(*args, **kwargs):
    outbound.append(1)
    raise AssertionError("Transmission condition contracts forbid outbound calls")
socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network

from server import runtime_graph as graph
from server.runtime_facts import transmission_condition_dependencies as dependencies
from server.runtime_state import TurnControl

FIXTURE = json.loads((Path(__file__).parent / "fixtures/runtime_transmission_conditions.json").read_text())
REGISTRY = {fact["id"]: fact for fact in FIXTURE["registry"]}

def enriched(scope=None):
    return [{**copy.deepcopy(fact), "runtime_transmission_conditions": dependencies(
        fact["value"], [fact], FIXTURE["registry"], scope or {})} for fact in FIXTURE["evidence"]]

def sample():
    base = {"id": "B1", "claim": "Driver assistance", "value": "Lane keeping assist and adaptive distance control",
            "conditions": "Available on selected trims", "approved": True,
            "scope": {"model": "Aurora", "market": "India", "model_year": "2026"}}
    donor = {"id": "D1", "claim": "Adaptive distance control", "value": "Available on Nimbus",
             "conditions": "IVT/AT/DCT transmissions only", "approved": True,
             "scope": {"model": "Aurora", "market": "India", "model_year": "2026", "transmission": "IVT, AT, DCT"}}
    return base, donor

class TransmissionConditions(unittest.TestCase):
    def test_actual_original_draft_rejected_without_losing_other_supported_sentences(self):
        feedback = []
        result, errors = graph.validate_decision(FIXTURE["decision"], enriched(), FIXTURE["question"], row_feedback=feedback)
        self.assertEqual(errors, ["missing_required_condition"])
        self.assertIn("six airbags", result["answer"])
        self.assertIn("Level 2 ADAS suite", result["answer"])
        self.assertNotIn("smart cruise", result["answer"].lower())
        self.assertEqual(feedback[0]["required_conditions"][0]["fact_id"], "F154")
        self.assertEqual(feedback[0]["required_conditions"][0]["feature"], "Smart Cruise Control with Stop & Go")
        self.assertEqual(feedback[0]["required_conditions"][0]["condition"], "IVT/AT/DCT transmissions only")

    def test_actual_qualified_duplicate_keeps_speech_and_condition_provenance(self):
        decision = copy.deepcopy(FIXTURE["decision"])
        decision["sentences"][2]["text"] = decision["sentences"][2]["text"].replace(
            "smart cruise control with stop-and-go.", "smart cruise control with stop-and-go on automatic versions only.")
        result, errors = graph.validate_decision(decision, enriched(), FIXTURE["question"])
        self.assertEqual(errors, [])
        self.assertIn("smart cruise control with stop-and-go on automatic versions only", result["answer"])
        self.assertIn("On selected higher trims, that package includes", result["answer"])
        self.assertEqual(result["condition_fact_ids"], ["F154"])
        self.assertNotIn("F154", result["fact_ids"])

    def test_qualification_prefix_preserves_proper_product_and_acronym_initials(self):
        for text in ("Hyundai SmartSense includes lane-keeping assist.", "ADAS includes lane-keeping assist."):
            decision = {"action": "answer", "sentences": [{"text": text, "fact_ids": ["F196"], "kind": "fact"}]}
            result, errors = graph.validate_decision(decision, enriched(), "What lane assistance is offered?")
            self.assertFalse(errors)
            self.assertIn("On selected higher trims, "+text, result["answer"])

    def test_one_mocked_repair_receives_feature_owned_condition_and_passes_all_guards(self):
        decision = copy.deepcopy(FIXTURE["decision"])
        corrected = copy.deepcopy(decision["sentences"])
        corrected[2]["text"] = corrected[2]["text"].replace("smart cruise control with stop-and-go.", "smart cruise control with stop-and-go on automatic versions only.")
        state = {"demo_id": "fixture", "session_id": "fixture", "turn_id": "t1", "question": FIXTURE["question"],
                 "decision": decision, "evidence": enriched(), "control": TurnControl(time.monotonic()+12), "errors": [], "tool_results": []}
        with patch.object(graph.config, "MOCK_LLM", False), patch.object(graph.runtime, "structured", return_value=graph._CompositionRepair(sentences=corrected)) as model, \
             patch.object(graph.store, "read_json", return_value={}), patch.object(graph.usage, "trace"):
            final = asyncio.run(graph.validate(state))
        self.assertEqual(model.call_count, 1)
        payload = json.loads(model.call_args.args[1])
        requirement = payload["validation_feedback"][0]["required_conditions"][0]
        self.assertEqual(requirement["feature"], "Smart Cruise Control with Stop & Go")
        self.assertEqual(final["result"]["validation_repair"]["validation_errors"], [])
        self.assertTrue(final["result"]["validation_repair"]["accepted"])
        self.assertIn("automatic versions only", final["result"]["answer"])

    def test_unrelated_automatic_headlamps_do_not_satisfy_transmission_requirement(self):
        text = "Higher trims have automatic headlamps and smart cruise control with stop-and-go."
        self.assertTrue(graph._missing_required_condition(text, [REGISTRY["F154"]]))
        self.assertTrue(graph._missing_required_condition("Smart cruise control with stop-and-go is available on manual and automatic versions.", [REGISTRY["F154"]]))

    def test_automatic_qualifier_cannot_move_between_independent_feature_clauses(self):
        for text in ("Lane-keeping assist is offered on automatic versions, while selected higher trims offer smart cruise control with stop-and-go.",
                     "Automatic versions offer lane-keeping assist, and selected higher trims offer smart cruise control with stop-and-go."):
            decision = copy.deepcopy(FIXTURE["decision"])
            decision["sentences"][2]["text"] = text
            with self.subTest(text=text):
                result, errors = graph.validate_decision(decision, enriched(), FIXTURE["question"])
                self.assertIn("missing_required_condition", errors)
                self.assertNotIn("smart cruise", result["answer"].lower())

    def test_actual_retrieve_uses_pinned_registry_without_expanding_fourteen_citeable_facts(self):
        state = {"demo_id": "fixture", "question": FIXTURE["question"], "snapshot_id": FIXTURE["provenance"]["snapshot_id"],
                 "control": TurnControl(time.monotonic()+12), "profile": {}, "history": []}
        pack = {"evidence": copy.deepcopy(FIXTURE["evidence"]), "snapshot_id": state["snapshot_id"]}
        def read(demo, path):
            self.assertEqual(path, "knowledge/snapshots/"+state["snapshot_id"]+".json")
            return {"facts": copy.deepcopy(FIXTURE["registry"])}
        with patch.object(graph.store, "load", return_value={"settings": {}}), patch.object(graph.store, "read_json", side_effect=read), \
             patch("server.knowledge.retrieve", return_value=pack) as retrieve, patch.object(graph.store, "write_json", side_effect=AssertionError("no writes")):
            result = asyncio.run(graph.retrieve(state))
        self.assertEqual(retrieve.call_args.kwargs["limit"], 14)
        self.assertEqual([f["id"] for f in result["evidence"]], [f["id"] for f in FIXTURE["evidence"]])
        payload = graph._dependency_payload(result["evidence"], {})
        linked = {row["assertion_id"]: row["requirements"] for row in payload}
        for base in ("F176", "F196"):
            self.assertEqual(linked[base][0]["fact_id"], "F154")
            self.assertNotIn("value", linked[base][0])
        result, errors = graph.validate_decision(FIXTURE["decision"], result["evidence"], FIXTURE["question"])
        self.assertIn("missing_required_condition", errors)

    def test_model_visible_evidence_does_not_expose_dependency_values_as_citeable_facts(self):
        pack = enriched()
        self.assertFalse(any("runtime_transmission_conditions" in graph._reason_evidence(f) for f in pack))
        decision = {"action": "answer", "sentences": [{"text": "Smart cruise control is available on automatic versions only.", "fact_ids": ["F154"], "kind": "fact"}]}
        result, errors = graph.validate_decision(decision, pack, FIXTURE["question"])
        self.assertTrue(errors)
        self.assertNotIn("F154", result["fact_ids"])

    def test_unrelated_lane_and_ordinary_cruise_do_not_inherit_stop_and_go_condition(self):
        base = REGISTRY["F196"]
        for text in ("Lane-keeping assist is available on higher trims.", "Ordinary cruise control is available on higher trims."):
            with self.subTest(text=text):
                self.assertEqual(dependencies(text, [base], FIXTURE["registry"]), [])
        row = {"action": "answer", "sentences": [{"text": "Lane-keeping assist is available on higher trims.", "fact_ids": ["F196"], "kind": "fact"}]}
        result, errors = graph.validate_decision(row, enriched(), "What lane assistance is available?")
        self.assertFalse(errors)
        self.assertEqual(result["condition_fact_ids"], [])

    def test_manual_customer_cannot_filter_out_requirement(self):
        scope = {"model": "CRETA", "market": "India", "transmission": "MT"}
        text = FIXTURE["decision"]["sentences"][2]["text"]
        base = [REGISTRY["F176"], REGISTRY["F196"]]
        self.assertEqual([f["id"] for f in dependencies(text, base, FIXTURE["registry"], scope)], ["F154"])
        result, errors = graph.validate_decision(FIXTURE["decision"], enriched(scope), FIXTURE["question"], requested_scope=scope)
        self.assertIn("missing_required_condition", errors)
        self.assertNotIn("smart cruise", result["answer"].lower())

    def test_eligible_exact_feature_on_arbitrary_product(self):
        base, donor = sample()
        self.assertEqual([f["id"] for f in dependencies("Adaptive distance control is available.", [base], [donor])], ["D1"])
        self.assertEqual(dependencies("Distance alerts are available.", [base], [donor]), [])

    def test_held_conflicted_precedence_and_live_records_cannot_supply_conditions(self):
        for changes in ({"approved": False}, {"knowledge": {"excluded_by_precedence": True}},
                        {"knowledge": {"conflict_status": "unresolved"}}, {"knowledge": {"conflict_status": "suppressed"}},
                        {"provenance": "live_web"}, {"provenance": "calculation"}):
            base, donor = sample(); donor.update(changes)
            with self.subTest(changes=changes):
                self.assertEqual(dependencies(base["value"], [base], [donor]), [])

    def test_incompatible_identity_or_unknown_donor_year_cannot_supply_conditions(self):
        for key, value in (("model", "Orion"), ("market", "Japan"), ("model_year", "2020"), ("generation", "old"), ("powertrain", "diesel")):
            base, donor = sample()
            if key in {"generation", "powertrain"}: base["scope"][key] = "new" if key == "generation" else "petrol"
            donor["scope"][key] = value
            with self.subTest(key=key): self.assertEqual(dependencies(base["value"], [base], [donor]), [])
        base, donor = sample(); base["scope"].pop("model_year")
        self.assertEqual(dependencies(base["value"], [base], [donor]), [])

    def test_requested_identity_mismatch_excludes_donor_but_not_transmission_restriction(self):
        base, donor = sample()
        for scope in ({"model": "Orion"}, {"market": "Japan"}, {"model_year": "2025"}):
            self.assertEqual(dependencies(base["value"], [base], [donor], scope), [])
        self.assertEqual([f["id"] for f in dependencies(base["value"], [base], [donor], {"transmission": "MT"})], ["D1"])

    def test_negative_feature_and_quote_only_overlap_cannot_create_requirement(self):
        base, donor = sample()
        base["value"] = "Adaptive distance control is unavailable."
        self.assertEqual(dependencies("Adaptive distance control is available.", [base], [donor]), [])
        base["value"] = "Lane keeping assist"; base["source"] = {"quote": "Adaptive distance control"}
        self.assertEqual(dependencies("Adaptive distance control is available.", [base], [donor]), [])
        base, donor = sample(); donor["value"] = "Adaptive distance control is unverified."
        self.assertEqual(dependencies(base["value"], [base], [donor]), [])

    def test_requirement_does_not_license_extra_donor_value_quantity(self):
        base, donor = sample(); donor["value"] += "; twelve airbags"
        base["runtime_transmission_conditions"] = [donor]
        row = {"action": "answer", "sentences": [{"text": "On selected trims, adaptive distance control is available on automatic versions only, with twelve airbags.", "fact_ids": ["B1"], "kind": "fact"}]}
        result, errors = graph.validate_decision(row, [base], "What driver assistance is available?")
        self.assertTrue(errors)
        self.assertNotIn("twelve airbags", result["answer"])

    def test_existing_device_and_warranty_constraints_still_apply(self):
        alexa = REGISTRY["F168"]; warranty = REGISTRY["F245"]
        self.assertTrue(graph._missing_required_condition("Alexa Home-to-Car is available.", [alexa]))
        self.assertFalse(graph._missing_required_condition("Alexa Home-to-Car needs an Echo device bought separately.", [alexa]))
        self.assertTrue(graph._missing_required_condition("An extended warranty is available for petrol variants.", [warranty]))
        self.assertFalse(graph._missing_required_condition("An extended warranty is available for petrol variants on a payable basis.", [warranty]))

if __name__ == "__main__":
    run = unittest.main(exit=False)
    print("OUTBOUND_SOCKET_ATTEMPTS="+str(len(outbound)))
    raise SystemExit(0 if run.result.wasSuccessful() and not outbound else 1)
