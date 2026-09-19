"""No-network controls for literal feature-specific trim threshold licensing."""
import copy
import json
import os
from pathlib import Path
import unittest

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
from server.runtime_facts import unsupported_ordinal_fitment as rejects


def fact(value, conditions="", variant="", **scope):
    return {"id":"Ftest", "approved":True, "claim":"Rear camera", "value":value,
            "conditions":conditions, "scope":{"model":"Example", "market":"India", "variant":variant, **scope}}


class OrdinalContract(unittest.TestCase):
    def test_actual_sequential_and_hedged_answers(self):
        fixture=json.loads((Path(__file__).parent / "fixtures/runtime_ordinal.json").read_text())
        facts={f["id"]:f for f in fixture["facts"]}
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(case["expected_rejected"], rejects(case["text"], [facts[i] for i in case["fact_ids"]]))

    def test_exact_lists_cannot_be_sorted_into_thresholds(self):
        f=fact("Rear camera on Nimbus, Aurora, Zenith", variant="Nimbus, Aurora, Zenith")
        for text in ("Rear camera is available from Nimbus.", "Rear camera is available starting from the Nimbus trim upwards.",
                     "Rear camera is standard on Nimbus and above.", "Rear camera is standard on Nimbus onwards.",
                     "Rear camera is standard on trims up to Zenith.", "Rear camera is standard on Zenith and below.", "From Nimbus, rear camera is standard."):
            with self.subTest(text=text): self.assertTrue(rejects(text,[f]))
        self.assertFalse(rejects("Rear camera is standard on Nimbus, Aurora and Zenith.",[f]))
        self.assertFalse(rejects("Rear camera is not available on Base.",[f]))  # polarity belongs to the other guard

    def test_literal_same_feature_thresholds_remain_opaque(self):
        f=fact("Rear camera available on Nimbus and above")
        for text in ("Rear camera is available from Nimbus upwards.", "Rear camera is standard starting from the Nimbus trim.",
                     "Rear camera is available on Nimbus trim and above."):
            self.assertFalse(rejects(text,[f]))
        for text in ("Rear camera is available from Aurora upwards.", "Rear camera is standard up to Nimbus.",
                     "Front camera is standard from Nimbus upwards."):
            self.assertTrue(rejects(text,[f]))
        # This helper does not expand Nimbus into a claimed list of higher names.
        self.assertFalse(rejects("Rear camera is available on Aurora.",[f]))

    def test_conditions_and_literal_scope_bind_only_their_own_feature(self):
        for f in (fact("Rear camera", "Available on Nimbus and above"),
                  fact("Rear camera", variant="Nimbus and above")):
            self.assertFalse(rejects("Rear camera is available on Nimbus trim and above.",[f]))
            self.assertTrue(rejects("Heated seats are available on Nimbus and above.",[f]))
        ordinary=fact("Rear camera", variant="Nimbus, Aurora, Zenith")
        self.assertTrue(rejects("Rear camera is available from Nimbus upwards.",[ordinary]))

    def test_mixed_features_cannot_borrow_another_clause_threshold(self):
        f=fact("Rear camera on Nimbus and above; Heated seats on Aurora and above")
        for text in ("Rear camera on Aurora and above.",
                     "Rear camera on Nimbus and above; heated seats on Nimbus and above.",
                     "Rear camera on Nimbus and above and heated seats on Nimbus and above.",
                     "Rear camera and heated seats are available from Nimbus upwards."):
            self.assertTrue(rejects(text,[f]))
        for text in ("Rear camera on Nimbus and above; heated seats on Aurora and above.",
                     "Rear camera on Nimbus and above and heated seats on Aurora and above."):
            self.assertFalse(rejects(text,[f]))
        f=fact("Panoramic sunroof on Nimbus, Aurora", "Panoramic sunroof from Nimbus upwards; voice control on Aurora and above")
        self.assertTrue(rejects("Panoramic sunroof is available from Aurora upwards.",[f]))
        self.assertFalse(rejects("Voice control is available from Aurora upwards.",[f]))

    def test_quote_claim_or_table_is_not_threshold_proof(self):
        f=fact("Rear camera on Nimbus, Aurora, Zenith")
        f["source"]={"quote":"Rear camera on Nimbus and above"}
        f["claim"]="Rear camera from Nimbus upwards"
        self.assertTrue(rejects("Rear camera is available from Nimbus upwards.",[f]))
        f["knowledge"]={"applicable_projection":{"rows":[{"assertion":"Rear camera on Nimbus and above"}]}}
        self.assertTrue(rejects("Rear camera is available from Nimbus upwards.",[f]))

    def test_held_conflicting_and_incompatible_scope_proof_is_excluded(self):
        f=fact("Rear camera on Nimbus and above")
        for change in ({"approved":False}, {"knowledge":{"excluded_by_precedence":True}},
                       {"knowledge":{"conflict_status":"unresolved"}}, {"knowledge":{"conflict_status":"suppressed"}}):
            changed={**f,**change}
            self.assertTrue(rejects("Rear camera on Nimbus and above.",[changed]))
        for key,value in (("market","Nigeria"),("model","Other"),("model_year","2025"),("generation","Previous")):
            f2=copy.deepcopy(f);f2["scope"][key]=value
            self.assertTrue(rejects("Rear camera on Nimbus and above.",[f2],{key:"2026" if key=="model_year" else "Current" if key=="generation" else "India" if key=="market" else "Example"}))

    def test_negative_and_uncertain_thresholds_do_not_license_positive_fitment(self):
        for text in ("Rear camera not available on Nimbus and above", "Rear camera unconfirmed on Nimbus and above",
                     "Rear camera not yet verified on Nimbus and above"):
            self.assertTrue(rejects("Rear camera available on Nimbus and above.",[fact(text)]))
        self.assertTrue(rejects("Rear camera not available on Nimbus and above.",[fact("Rear camera available on Nimbus and above")]))
        self.assertFalse(rejects("Rear camera not available on Nimbus and above.",[fact("Rear camera not available on Nimbus and above")]))
        self.assertTrue(rejects("Rear camera available on Nimbus and above.",[fact("Rear camera not available", variant="Nimbus and above")]))
        self.assertTrue(rejects("Rear camera available on Nimbus and above.",[fact("Rear camera", "Fitment pending confirmation", "Nimbus and above")]))
        self.assertTrue(rejects("Rear camera available on Nimbus and above.",[fact("Rear camera on Nimbus and above", "Fitment pending confirmation")]))

    def test_literal_threshold_exceptions_cannot_be_removed_or_invented(self):
        f=fact("Rear camera on Nimbus and above, excluding Zenith")
        self.assertFalse(rejects("Rear camera available from Nimbus upwards, except Zenith.",[f]))
        self.assertTrue(rejects("Rear camera available from Nimbus upwards.",[f]))
        self.assertTrue(rejects("Rear camera available from Nimbus upwards, except Aurora.",[f]))

    def test_quantities_and_units_stay_bound_to_threshold_feature(self):
        f=fact("12-inch display on Nimbus and above")
        self.assertFalse(rejects("12-inch display available from Nimbus upwards.",[f]))
        self.assertTrue(rejects("8-inch display available from Nimbus upwards.",[f]))
        self.assertTrue(rejects("12-speaker display available from Nimbus upwards.",[f]))
        f=fact("R16 spare wheel on Nimbus and below; R18 road wheel on Aurora and above")
        self.assertTrue(rejects("R18 spare wheel on Nimbus and below.",[f]))
        self.assertFalse(rejects("R16 spare wheel on Nimbus and below.",[f]))

    def test_lookalike_names_and_direction_are_not_equated(self):
        for a,b in (("Aurora","Aurora Sport"),("SX","SX(O)"),("Sport","Sport Edition")):
            f=fact(f"Rear camera on {a} and above")
            self.assertTrue(rejects(f"Rear camera on {b} and above.",[f]))
        self.assertTrue(rejects("Rear camera from Nimbus and below.",[fact("Rear camera on Nimbus and below")]))
        self.assertFalse(rejects("Rear camera up to Nimbus.",[fact("Rear camera on Nimbus and below")]))

    def test_non_threshold_language_is_unchanged(self):
        for text in ("This information comes from the brochure.", "Prices start from ₹10 lakh.",
                     "An extended warranty of up to seven years is available on petrol models on a payable basis.",
                     "From our separate records, an extended warranty of up to 7 years is available on petrol variants on a payable basis.",
                     "The rear camera is shown above the tyre table.", "The higher trims named here are Aurora and Zenith.",
                     "Rear camera on Nimbus; heated seats on Aurora."):
            self.assertFalse(rejects(text,[fact("Rear camera on Nimbus, Aurora")]))

    def test_actual_opaque_scope_keeps_spoken_numbers_and_determiner(self):
        f={"id":"F046","approved":True,"claim":"Connected car suite complimentary subscription",
           "value":"Hyundai Bluelink connected car technology with 70+ features, 3 years complimentary",
           "conditions":"Available on SX trim and above; includes 3 years complimentary service",
           "scope":{"model":"CRETA","variant":"SX and above"}}
        text="On the SX trim and above, Hyundai Bluelink connected car technology includes over seventy features with three years of complimentary service."
        self.assertFalse(rejects(text,[f]))
        self.assertTrue(rejects(text.replace("SX trim", "King trim"),[f]))
        self.assertTrue(rejects(text.replace("seventy", "eighty"),[f]))
        self.assertTrue(rejects("Eight-inch display on Nimbus and above.",[fact("12-inch display on Nimbus and above")]))

    def test_actual_graph_drops_unsupported_threshold_without_dropping_all_valid_facts(self):
        from server.runtime_graph import validate_decision
        fixture=json.loads((Path(__file__).parent / "fixtures/runtime_ordinal.json").read_text())
        facts={f["id"]:f for f in fixture["facts"]}
        decision={"intent":"qa","response_kind":"answer","sentences":[
            {"text":"Rear parking sensors are standard across all variants.","fact_ids":["F174"],"kind":"fact"},
            {"text":"A rear camera with dynamic guidelines is standard from EX(O) upwards.","fact_ids":["F248"],"kind":"fact"}],"followup":""}
        result,errors=validate_decision(decision,[facts["F174"],facts["F248"]],"What parking assistance is offered?")
        self.assertIn("unsupported_ordinal_fitment",errors)
        self.assertIn("Rear parking sensors",result["answer"])
        self.assertNotIn("EX(O) upwards",result["answer"])

    def test_actual_connected_feature_paraphrase_preserves_threshold_and_count(self):
        case=json.loads((Path(__file__).parent / "fixtures/runtime_ordinal.json").read_text())["typed_q025_repair"]
        feature=next(f for f in case["facts"] if f["id"]=="F046")
        text=case["sentences"][1]["text"]
        self.assertFalse(rejects(text,[feature]))
        for changed in (
            text.replace("SX trim", "King trim"),
            text.replace("70 connected", "80 connected"),
            text.replace("three years", "four years"),
            text.replace("three years", "three months"),
            text.replace("connected features", "safety features"),
            text.replace("connected features", "connected cameras"),
            text.replace("70 connected features", "70 years features"),
            text.replace("complimentary service", "complimentary battery"),
        ):
            with self.subTest(text=changed): self.assertTrue(rejects(changed,[feature]))

    def test_entire_saved_connected_repair_retains_independent_scope_and_purchase(self):
        from server.runtime_graph import validate_decision
        case=json.loads((Path(__file__).parent / "fixtures/runtime_ordinal.json").read_text())["typed_q025_repair"]
        decision={"action":"answer","answered":True,"sentences":case["sentences"]}
        result,errors=validate_decision(decision,case["facts"],case["question"])
        self.assertFalse(errors)
        self.assertEqual(set(result["fact_ids"]),{"F168","F046","F198"})
        for phrase in ("over-the-air updates", "third-party Echo device purchase", "SX trim and above", "70 connected features", "three years", "Bose"):
            self.assertIn(phrase,result["answer"])
        for row in case["sentences"]:
            result,errors=validate_decision({"action":"answer","answered":True,"sentences":[row]},case["facts"],case["question"])
            self.assertFalse(errors)
            self.assertIn(row["text"],result["answer"])

    def test_distinct_feature_counts_cannot_exchange_their_modifiers(self):
        for head in ("features", "functions"):
            for shared_modifier in ("", "advanced "):
                f=fact(f"70 {shared_modifier}connected {head} and 3 {shared_modifier}safety {head}","Available on Nimbus and above","Nimbus and above")
                f["claim"]="Equipment suite"
                for count,kind,rejected in ((70,"connected",False),(3,"safety",False),(3,"connected",True),(70,"safety",True)):
                    text=f"{count} {shared_modifier}{kind} {head} are available on Nimbus and above."
                    with self.subTest(text=text):self.assertEqual(rejects(text,[f]),rejected)

    def test_comma_coordinated_open_ranges_are_not_named_enumerations(self):
        f=fact("Rear camera on Nimbus, Aurora, Zenith", variant="Nimbus, Aurora, Zenith")
        for text in (
            "Rear camera is standard on Nimbus, Aurora, and higher.",
            "Rear camera is standard on trims like Nimbus, Aurora, and above.",
            "Rear camera is standard on Nimbus, Aurora, and lower.",
            "Rear camera is standard from Nimbus, and above.",
        ):
            with self.subTest(text=text): self.assertTrue(rejects(text,[f]))
        self.assertFalse(rejects("Rear camera is standard on Nimbus, Aurora, and Zenith.",[f]))

    def test_comma_threshold_spelling_still_needs_same_feature_literal_proof(self):
        for assertion in ("Rear camera on Nimbus and above", "Rear camera on Nimbus, and above"):
            f=fact(assertion)
            for text in ("Rear camera on Nimbus, and higher.", "Rear camera from Nimbus, and above."):
                with self.subTest(assertion=assertion,text=text): self.assertFalse(rejects(text,[f]))
            for text in ("Front camera on Nimbus, and higher.", "Rear camera on Aurora, and higher.",
                         "Rear camera on Nimbus, and lower."):
                self.assertTrue(rejects(text,[f]))

    def test_comma_ranges_do_not_merge_independent_feature_proofs(self):
        f=fact("Rear camera on Nimbus and above; heated seats on Aurora and above")
        self.assertFalse(rejects("Rear camera on Nimbus, and above, and heated seats on Aurora, and higher.",[f]))
        self.assertTrue(rejects("Rear camera on Aurora, and higher, and heated seats on Aurora, and higher.",[f]))
        self.assertTrue(rejects("Rear camera on Nimbus, and higher, while heated seats on Nimbus, and higher.",[f]))
        self.assertFalse(rejects("Rear camera on Nimbus, Aurora, and Zenith, and heated seats on Aurora, and above.",[f]))

    def test_actual_comma_range_is_rejected_through_graph_without_losing_other_rows(self):
        from server.runtime_graph import validate_decision
        case=json.loads((Path(__file__).parent / "fixtures/runtime_guard_coordination.json").read_text())["q033"]
        self.assertTrue(rejects(case["decision"]["sentences"][1]["text"],case["facts"]))
        result,errors=validate_decision(case["decision"],case["facts"],case["question"])
        self.assertIn("unsupported_ordinal_fitment",errors)
        self.assertNotIn("and higher",result["answer"])
        self.assertIn("Rear parking sensors",result["answer"])
        self.assertIn("electric parking brake",result["answer"])
        self.assertNotIn("F248",result["fact_ids"])


if __name__=="__main__": unittest.main()
