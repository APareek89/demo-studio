"""Pure EMI delivery checks from the two1aab334 cohorts; all sockets blocked."""
import copy
import os
import socket
import unittest

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
def no_network(*args, **kwargs):
    raise AssertionError("Delivery contracts must not open sockets")
socket.socket.connect = no_network
socket.create_connection = no_network

from server.runtime_emi_delivery import append_missing_emi_terms


def fact(principal=800000, rate=8, term=4, *, monthly=False, unit="years", conditions=None):
    return {"id": "Dtest", "approved": True, "provenance": "calculation", "conditions": conditions or
            "Illustrative estimate using explicitly supplied inputs; excludes fees/taxes and is not a lender quote.",
            "derivation": {"operation": "emi", "value": "19530.34", "unit": "INR/month", "inputs": [
                {"name": "principal", "value": principal, "unit": "INR"},
                {"name": "monthly_rate" if monthly else "annual_rate", "value": rate, "unit": "percent"},
                {"name": "tenure", "value": term, "unit": unit}]}}


class DeliveryContract(unittest.TestCase):
    def test_captured_s08_illustrative_figure_already_excludes_costs(self):
        # Single live night session s_mu8ozv2etxtx, s08; original model wording.
        original = ["For a ten lakh rupee loan at one percent monthly interest over five years, the estimated EMI is approximately ₹22,244 per month.",
                    "This is an illustrative figure that excludes taxes and fees, and it is not a formal lender quote."]
        source = fact(1000000, 1, 5, monthly=True)
        self.assertEqual(append_missing_emi_terms(original, source), original)
        self.assertEqual(append_missing_emi_terms(original, source), original)

    def test_illustrative_figure_subject_does_not_borrow_other_exclusions(self):
        base = "For a loan of 10 lakh rupees at 1 percent monthly interest over five years, the estimated EMI is ₹22,244."
        source = fact(1000000, 1, 5, monthly=True)
        for clause in ("The showroom's illustrative figure excludes taxes and fees.",
                       "This is an illustrative figure that does not exclude taxes and fees.",
                       "This is an illustrative figure that excludes fees but taxes are included."):
            result = append_missing_emi_terms([base, clause], source)
            self.assertIn("taxes", result[-1])
        partial = [base, "This is an illustrative figure that excludes fees, and it is not a lender quote."]
        self.assertEqual(append_missing_emi_terms(partial, source)[2:], ["This estimate excludes taxes."])

    def test_actual_reordered_caveats_do_not_duplicate(self):
        # Actual accepted model text before the old graph appended its blanket
        # sentence, from qa100-v7-relations-{sequential,hedged} q051/52/55/62.
        examples = [
            (fact(1000000, 9, 5), "For a loan of 10 lakh rupees at 9 percent annual interest over 5 years, the illustrative monthly EMI comes to approximately 20,758 rupees.", "Please keep in mind that this is an illustrative estimate excluding taxes and fees, and it is not a formal lender quote."),
            (fact(), "Based on an 8 lakh rupee loan at 8 percent annual interest over 4 years, the illustrative EMI estimate is 19,530.34 rupees per month.", "This calculation is an estimate based on your supplied inputs, excludes fees and taxes, and does not serve as a lender quote."),
            (fact(1500000, 9.5, 5), "For a loan of 15 lakh rupees at 9.5 percent annual interest over 5 years, the estimated EMI is approximately 31,503 rupees per month.", "Please note this is an illustrative estimate that excludes processing fees and taxes, and it does not serve as an official lender quote."),
            (fact(1000000, 1, 5, monthly=True), "At a 1 percent monthly interest rate over 5 years, your illustrative estimated monthly payment on a 10 lakh loan comes to 22,244.45 rupees.", "This is an estimate based on your supplied inputs, excludes additional fees and taxes, and does not serve as a formal lender quote."),
            (fact(1200000, 10, 5), "For a 12 lakh rupee loan at 10 percent annual interest over 5 years, the illustrative EMI is approximately 25,496 rupees per month.", "Please note this is an estimate that excludes taxes and fees, rather than an official lender quote."),
        ]
        for source, first, second in examples:
            with self.subTest(first=first):
                original = [first, second]
                self.assertEqual(append_missing_emi_terms(original, source), original)

    def test_zero_rate_does_not_borrow_monthly_payment_basis(self):
        original = ["At zero percent annual interest, the illustrative monthly payment on 6 lakh rupees over 3 years is 16,666.67 rupees.",
                    "This estimate excludes fees and taxes, and it is not a lender quote."]
        self.assertEqual(append_missing_emi_terms(original, fact(600000, 0, 3)), original)
        spoken = [original[0].replace("over 3 years", "over three years"), original[1]]
        self.assertEqual(append_missing_emi_terms(spoken, fact(600000, 0, 3)), spoken)

    def test_append_only_missing_operand(self):
        original = ["The illustrative payment at 8 percent annual interest over 4 years is 19,530.34 rupees per month.",
                    "This excludes fees and taxes and is not a lender quote."]
        result = append_missing_emi_terms(original, fact())
        self.assertEqual(result[:2], original)
        self.assertEqual(result[2:], ["This estimate uses a loan of 800000 rupees."])
        self.assertEqual(append_missing_emi_terms(result, fact()), result)

    def test_currency_result_is_not_principal_evidence(self):
        original = ["The illustrative monthly payment is 800000 rupees at 0% annual interest over 1 months.",
                    "This excludes fees and taxes and is not a lender quote."]
        result = append_missing_emi_terms(original, fact(800000, 0, 1, unit="months"))
        self.assertEqual(result[-1], "This estimate uses a loan of 800000 rupees.")
        self.assertEqual(result[:2], original)

    def test_monthly_annual_mismatch_is_not_silently_repaired(self):
        original = ["For an 8 lakh rupee loan at 1% annual interest over 4 years, this is an illustrative estimate.",
                    "This excludes fees and taxes and is not a lender quote."]
        source = fact(rate=1, monthly=True)
        result = append_missing_emi_terms(original, source)
        self.assertEqual(result[:2], original)  # validation, not this helper, rejects the wrong claim
        self.assertEqual(result[2:], ["This estimate uses 1% monthly interest."])
        mixed = [original[0] + " The interest rate is also 1% monthly.", original[1]]
        self.assertEqual(append_missing_emi_terms(mixed, source)[-1], "This estimate uses 1% monthly interest.")

    def test_partial_caveat_adds_only_missing_piece(self):
        original = ["For a loan of 8 lakh rupees at 8% annual interest over 4 years, the illustrative EMI is 19530.34 rupees.",
                    "This excludes fees and is not a lender quote."]
        self.assertEqual(append_missing_emi_terms(original, fact())[2:], ["This estimate excludes taxes."])
        # Actual q054's awkward 'does not include ... lender quotes' is not an
        # explicit non-quote disclaimer; append that alone, not fees/taxes again.
        original[1] = "Please note this is only an estimate and does not include bank fees, taxes, or official lender quotes."
        self.assertEqual(append_missing_emi_terms(original, fact())[2:], ["This is not a lender quote."])

    def test_insurance_only_when_explicitly_audited_and_never_removed(self):
        original = ["Using a loan of 800000 rupees at 8% annual interest over 4 years, the illustrative EMI is 19530.34 rupees per month.",
                    "This excludes taxes, insurance and fees and is not a lender quote."]
        self.assertEqual(append_missing_emi_terms(original, fact()), original)
        without_insurance = [original[0], "This excludes fees and taxes and is not a lender quote."]
        self.assertEqual(append_missing_emi_terms(without_insurance, fact()), without_insurance)
        audited = fact(conditions="Illustrative estimate; excludes fees, taxes and insurance and is not a lender quote.")
        result = append_missing_emi_terms(without_insurance, audited)
        self.assertEqual(result[2:], ["This estimate excludes insurance."])
        self.assertEqual(append_missing_emi_terms(result, audited), result)
        for condition in ("Insurance is included.", "Insurance is not excluded."):
            self.assertEqual(append_missing_emi_terms(without_insurance, fact(conditions=condition)), without_insurance)

    def test_negated_or_unrelated_caveat_is_not_confirmation(self):
        base = "For an 8 lakh rupee loan at 8% annual interest over 4 years, the illustrative EMI is 19530.34 rupees."
        for clause in ("This does not exclude fees and taxes.", "Fees and taxes are included.",
                       "The warranty excludes fees and taxes; this lender quote includes all costs."):
            result = append_missing_emi_terms([base, clause], fact())
            self.assertEqual(result[:2], [base, clause])
            self.assertIn("not a lender quote", result[-1])
            self.assertIn("excludes fees and taxes", result[-1])
        self.assertIn("excludes fees and taxes", append_missing_emi_terms([base, "This does not exclude fees and taxes."], fact())[-1])
        self.assertEqual(append_missing_emi_terms([base, "This excludes fees but taxes are included and it is not a lender quote."], fact())[-1], "This estimate excludes taxes.")

    def test_arithmetic_rescue_is_idempotent(self):
        original = ["Using a loan of 800000 rupees at 8% annual interest over 4 years, the illustrative EMI is 19530.34 rupees per month. This excludes fees and taxes and is not a lender quote."]
        self.assertEqual(append_missing_emi_terms(original, fact()), original)
        minimal = ["The EMI is 19530.34 rupees per month."]
        result = append_missing_emi_terms(minimal, fact())
        self.assertEqual(result[:1], minimal)
        self.assertIn("800000 rupees at 8% annual interest over 4 years", result[1])
        self.assertEqual(result[2], "This illustrative estimate excludes fees and taxes and is not a lender quote.")
        self.assertEqual(append_missing_emi_terms(result, fact()), result)

    def test_non_emi_or_unverified_inputs_add_nothing(self):
        invalid = []
        for key, value in (("provenance", "live_web"), ("approved", False)):
            row = fact();row[key] = value;invalid.append(row)
        row = fact();row["derivation"]["operation"] = "fuel_cost";invalid.append(row)
        row = fact();row["derivation"]["inputs"][0]["value"] = float("nan");invalid.append(row)
        row = fact();row["derivation"]["inputs"][0]["unit"] = "USD";invalid.append(row)
        for source in invalid:
            with self.subTest(source=source):self.assertEqual(append_missing_emi_terms(["Original."], source), ["Original."])

    def test_inputs_and_claim_text_are_never_mutated(self):
        source = fact();before = copy.deepcopy(source)
        original = ["The EMI is 99 rupees."];copy_of_original = list(original)
        result = append_missing_emi_terms(original, source)
        self.assertEqual(original, copy_of_original)
        self.assertEqual(source, before)
        self.assertEqual(result[0], "The EMI is 99 rupees.")
        self.assertNotIn("19530.34", " ".join(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
