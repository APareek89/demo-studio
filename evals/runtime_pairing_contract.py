"""Offline cross-assertion equipment pairing controls, including saved q024."""
import copy
import json
import os
from pathlib import Path
import unittest

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
from server.runtime_facts import unsupported_equipment_pairing as rejects


def fact(identifier, value, variant="Aurora", **scope):
    return {"id": identifier, "approved": True, "claim": "Equipment specification", "value": value,
            "conditions": "", "scope": {"model": "Example", "market": "India", "variant": variant, **scope}}


class PairingContract(unittest.TestCase):
    def setUp(self):
        self.audio = fact("Fa", "Sonata premium sound system", "Aurora, Zenith")
        self.display = fact("Fd", "8-inch touchscreen on Base; 12-inch display on Aurora, Zenith", "")
        self.prior = {"text": "Sonata premium sound is available on Aurora and Zenith.", "facts": [self.audio]}

    def test_saved_pairing_is_rejected_while_reviewed_audio_survives(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/runtime_pairing.json").read_text())
        facts = {f["id"]: f for f in fixture["facts"]}
        first, second = fixture["sentences"]
        prior = {"text": first["text"], "facts": [facts[i] for i in first["fact_ids"]]}
        self.assertFalse(rejects(first["text"], prior["facts"]))
        self.assertTrue(rejects(second["text"], [facts[i] for i in second["fact_ids"]], prior))
        self.assertFalse(rejects("It pairs with a 10.25-inch navigation display.", [facts["F162"]], prior))

    def test_arbitrary_trim_names_keep_size_and_object_binding(self):
        self.assertTrue(rejects("It pairs with an 8-inch touchscreen.", [self.display], self.prior))
        self.assertFalse(rejects("It pairs with a 12-inch display.", [self.display], self.prior))
        self.assertTrue(rejects("It pairs with either an 8-inch touchscreen or a 12-inch display.", [self.display], self.prior))
        self.assertTrue(rejects("It pairs with a 12-speaker display.", [self.display], self.prior))

    def test_explicit_subject_and_non_audio_features_use_same_contract(self):
        self.assertTrue(rejects("The Sonata sound system pairs with an 8-inch touchscreen.", [self.audio, self.display]))
        self.assertFalse(rejects("The Sonata sound system pairs with a 12-inch display.", [self.audio, self.display]))
        roof = fact("Fr", "Panoramic roof", "Aurora")
        seats = fact("Fs", "Heated seats", "Base")
        self.assertTrue(rejects("The panoramic roof is paired with heated seats.", [roof, seats]))
        seats["scope"]["variant"] = "Aurora"
        self.assertFalse(rejects("The panoramic roof is paired with heated seats.", [roof, seats]))

    def test_decimal_subject_is_not_split_as_a_sentence_boundary(self):
        display = fact("Fd", "10.25-inch display", "Aurora")
        self.assertFalse(rejects("The 10.25-inch display pairs with the Sonata sound system.", [display, self.audio]))
        self.assertTrue(rejects("The 12.25-inch display pairs with the Sonata sound system.", [display, self.audio]))

    def test_missing_scope_or_antecedent_cannot_prove_pairing(self):
        unknown = fact("Fd", "12-inch display", "")
        self.assertTrue(rejects("It pairs with a 12-inch display.", [unknown], self.prior))
        self.assertTrue(rejects("It pairs with a 12-inch display.", [self.display]))
        unknown_prior = {"text": "Premium sound is available.", "facts": [fact("Fa", "Premium sound", "")]}
        self.assertTrue(rejects("It pairs with a 12-inch display.", [self.display], unknown_prior))

    def test_scope_identity_and_requested_trim_stay_literal(self):
        for key, value in (("model", "Different"), ("market", "Nigeria"), ("model_year", "2025")):
            with self.subTest(key=key):
                audio = copy.deepcopy(self.audio); audio["scope"]["model_year"] = "2026"
                display = copy.deepcopy(self.display); display["scope"][key] = value
                self.assertTrue(rejects("It pairs with a 12-inch display.", [display], {**self.prior, "facts": [audio]}))
        self.assertTrue(rejects("It pairs with a 12-inch display.", [self.display], self.prior, {"variant": "Base"}))
        lookalike = fact("Fd", "12-inch display", "Aurora Sport, Zenith Edition")
        self.assertTrue(rejects("It pairs with a 12-inch display.", [lookalike], self.prior))

    def test_negative_and_unknown_fitment_never_license_positive_pairing(self):
        for value in ("Not available on Aurora, Zenith", "12-inch display on Base; Not available on Aurora, Zenith"):
            display = fact("Fd", value, "")
            display["claim"] = "12-inch display"
            self.assertTrue(rejects("It pairs with a 12-inch display.", [display], self.prior))
        absent = {"text": "Sonata sound is not available on Aurora.", "facts": [self.audio]}
        self.assertTrue(rejects("It pairs with a 12-inch display.", [self.display], absent))
        uncertain = fact("Fd", "12-inch display", "Aurora, Zenith")
        uncertain["conditions"] = "Fitment is unconfirmed"
        self.assertTrue(rejects("It pairs with a 12-inch display.", [uncertain], self.prior))
        uncertain["value"] = "12-inch display on Aurora, Zenith"
        self.assertTrue(rejects("It pairs with a 12-inch display.", [uncertain], self.prior))

    def test_quotes_held_and_precedence_losers_cannot_supply_relation(self):
        for transform in (
            lambda f: f.update(approved=False),
            lambda f: f.update(knowledge={"excluded_by_precedence": True}),
            lambda f: f.update(knowledge={"conflict_status": "unresolved"}),
        ):
            candidate = copy.deepcopy(self.display); transform(candidate)
            self.assertTrue(rejects("It pairs with a 12-inch display.", [candidate], self.prior))
        misleading = fact("Fd", "8-inch display", "Base")
        misleading["source"] = {"quote": "12-inch display on Aurora, Zenith; Sonata sound pairs with 12-inch display"}
        self.assertTrue(rejects("It pairs with a 12-inch display.", [misleading], self.prior))

    def test_explicit_same_assertion_relation_and_independent_lists(self):
        direct = fact("Fcombo", "Hybrid motor is paired with a 6-speed transmission", "")
        self.assertFalse(rejects("The hybrid motor is paired with a 6-speed transmission.", [direct]))
        self.assertTrue(rejects("The hybrid motor is paired with an 8-speed transmission.", [direct]))
        for text in (
            "The range offers either an 8-inch touchscreen or a 12-inch display, depending on the variant.",
            "The range also offers a 12-inch display.",
            "Sonata sound and an 8-inch display are separate feature options in the range.",
        ):
            self.assertFalse(rejects(text, [self.display], self.prior))

    def test_ambiguous_prior_feature_list_cannot_choose_convenient_antecedent(self):
        other = fact("Fx", "Heated seats", "Base")
        prior = {"text": "Sonata sound and heated seats are offered on different trims.", "facts": [self.audio, other]}
        self.assertTrue(rejects("It pairs with a 12-inch display.", [self.display], prior))

    def test_actual_graph_retains_reviewed_audio_but_rejects_wrong_pairing(self):
        from server.runtime_graph import validate_decision
        fixture = json.loads((Path(__file__).parent / "fixtures/runtime_pairing.json").read_text())
        decision = {"action": "answer", "answered": True, "sentences": fixture["sentences"]}
        result, errors = validate_decision(decision, fixture["facts"], fixture["question"])
        self.assertEqual(errors, ["unsupported_equipment_pairing"])
        self.assertEqual(result["fact_ids"], ["F164"])
        self.assertIn("Bose", result["answer"])
        self.assertNotIn("8.0-inch", result["answer"])
        decision["sentences"] = [fixture["sentences"][0], {"kind": "fact", "fact_ids": ["F162"],
                                                     "text": "It pairs with a 10.25-inch navigation display."}]
        result, errors = validate_decision(decision, fixture["facts"], fixture["question"])
        self.assertFalse(errors)
        self.assertEqual(result["fact_ids"], ["F164", "F162"])
        self.assertIn("10.25-inch", result["answer"])

    def test_graph_does_not_reuse_a_stale_antecedent_across_other_rows(self):
        from server.runtime_graph import validate_decision
        fixture = json.loads((Path(__file__).parent / "fixtures/runtime_pairing.json").read_text())
        for intervening in (
            {"kind": "context", "fact_ids": [], "text": "What would you like to explore next?"},
            {"kind": "fact", "fact_ids": ["NONEXISTENT"], "text": "The unrelated equipment is available."},
        ):
            with self.subTest(intervening=intervening):
                decision = {"action": "answer", "answered": True, "sentences": [
                    fixture["sentences"][0], intervening,
                    {"kind": "fact", "fact_ids": ["F162"], "text": "It pairs with a 10.25-inch navigation display."}]}
                result, errors = validate_decision(decision, fixture["facts"], fixture["question"])
                self.assertIn("unsupported_equipment_pairing", errors)
                self.assertNotIn("F162", result["fact_ids"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
