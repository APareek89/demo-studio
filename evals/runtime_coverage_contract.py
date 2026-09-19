"""Offline source-coverage controls; no sources, snapshot writes or providers."""
import json
from pathlib import Path
import unittest

from server.runtime_coverage import coverage_limitation, unsupported_coverage_claim


LIMIT = "I couldn't verify that from the retrieved evidence."
COORDINATION = json.loads((Path(__file__).parent / "fixtures/runtime_coverage_coordination.json").read_text())


class CoverageContract(unittest.TestCase):
    def test_actual_market_statement_does_not_license_page_absence(self):
        case=json.loads((Path(__file__).parent / "fixtures/runtime_guard_coordination.json").read_text())["q071"]
        claim=case["decision"]["sentences"][1]["text"]
        self.assertEqual(len(case["tool_results"][0]["evidence"]),6)
        self.assertTrue(unsupported_coverage_claim(claim))
        self.assertTrue(unsupported_coverage_claim(case["answer"]))
        self.assertEqual(coverage_limitation(claim,precise=True),LIMIT)
        self.assertEqual(coverage_limitation(case["decision"]["sentences"][0]["text"]),"")
        from server.runtime_graph import validate_decision
        result,errors=validate_decision(case["decision"],case["facts"],case["question"])
        self.assertIn("unverified_coverage_claim",errors)
        self.assertNotIn("doesn't specify",result["answer"])
        self.assertIn("1482",result["answer"])

    def test_source_pronoun_ownership_is_not_limited_to_reporting_verbs(self):
        for text in (
            "The page reflects the Indian market, but it doesn't specify variant names.",
            "The document targets buyers, yet it does not detail refund terms.",
            "The brochure is intended for families, but it does not mention warranty terms.",
            "The page describes Highlights, but it does not detail warranty terms.",
            "The page addresses the Indian market and it does not list trim names.",
        ):
            with self.subTest(text=text): self.assertEqual(coverage_limitation(text),LIMIT)

    def test_generic_positive_predicate_preserves_explicit_nested_and_product_subjects(self):
        for text in (
            "The page reflects the Indian market, but the E trim does not include heated seats.",
            "The page explains that E has manual seats, but it does not include heated seats.",
            "The page describes E, which has manual seats, but it does not include heated seats.",
            "The page reflects the market and the E trim has manual seats, but it does not include heated seats.",
            "The page describes SX, but it does not include ventilated seats.",
            "The page describes Aurora Premium, but it does not provide heated seats.",
            "The page describes the warranty, but it does not cover wear and tear.",
            "According to the page about E, it does not include ventilated seats.",
            "The page reflects the Indian market. It does not include ventilated seats.",
        ):
            with self.subTest(text=text): self.assertFalse(unsupported_coverage_claim(text))

    def test_actual_coordinated_source_pronoun_is_not_complete_page_evidence(self):
        original = COORDINATION["rows"][0]
        self.assertEqual(original["id"], "q073")
        self.assertEqual(original["selected_passage_count"], 3)
        self.assertEqual(original["coverage"], [])
        self.assertTrue(unsupported_coverage_claim(original["answer"]))
        self.assertEqual(coverage_limitation(original["source_claim"]), LIMIT)
        self.assertEqual(coverage_limitation(original["source_claim"], precise=True), LIMIT)
        self.assertEqual(coverage_limitation(original["separate_warranty_claim"]), "")

    def test_coordinated_source_reporting_is_generic_and_discards_the_whole_claim(self):
        for text in (
            "The document lists delivery dates and milestones, but it does not specify refund terms.",
            "The website reports sales figures and it doesn't mention payment terms.",
            "The brochure covers dimensions, yet it has not provided test conditions.",
            "The page lists Highlights, but it does not detail warranty terms.",
            "The document lists Product Overview, but it does not mention refund terms.",
            "The page lists specifications, but it does not detail warranty terms, so every car has seven years free.",
        ):
            with self.subTest(text=text):
                self.assertEqual(coverage_limitation(text, precise=True), LIMIT)
                self.assertFalse(unsupported_coverage_claim(coverage_limitation(text)))

    def test_source_pronoun_does_not_take_ownership_of_product_fitment(self):
        for text in (
            "The page covers sales milestones, but the E trim does not include ventilated seats.",
            "According to the feature page, the E trim does not include ventilated seats.",
            "The page states that the E trim has manual seats, but it does not include ventilated seats.",
            "The page lists the E trim, but it does not include ventilated seats.",
            "The page lists SX, but it does not include ventilated seats.",
            "The page lists Aurora Premium, but it does not include heated seats.",
            "The page lists S(O), but it does not include ventilated seats.",
            "The page covers the warranty, but it does not cover wear and tear.",
            "The page lists specifications, but the warranty policy only covers manufacturing defects.",
            "The page lists specifications, and it includes tyre sizes.",
            "I couldn't verify warranty duration from the retrieved page.",
        ):
            with self.subTest(text=text):
                self.assertFalse(unsupported_coverage_claim(text))
                self.assertEqual(coverage_limitation(text, precise=True), "")

    def test_policy_catalogue_ambiguity_is_left_to_existing_grounding(self):
        # Preserved observed noncritical gap: 'available policies' is not enough
        # to distinguish a record inventory from a real contract's coverage.
        policy_case = COORDINATION["rows"][1]
        self.assertEqual(policy_case["id"], "q079")
        self.assertFalse(unsupported_coverage_claim(policy_case["answer"]))
        for text in (
            "This warranty policy only covers manufacturing defects.",
            "The available warranty policies only cover manufacturing defects.",
            "The extended warranty is payable and applies only to petrol variants.",
        ):
            self.assertFalse(unsupported_coverage_claim(text))

    def test_global_source_origin_cannot_be_inferred_from_selected_citations(self):
        for text in (
            "All details and variant lineups provided here come directly from Hyundai Motor India.",
            "All the information is sourced from the manufacturer.",
            "Every specification comes directly from the brochure.",
        ):
            self.assertEqual(coverage_limitation(text), LIMIT)
        self.assertFalse(unsupported_coverage_claim("This particular fact comes from the uploaded brochure."))
        self.assertFalse(unsupported_coverage_claim("Six airbags come standard on all variants."))

    def test_actual_q073_cannot_convert_three_unrelated_passages_into_absence(self):
        # Actual draft cited anniversary copy and two variant-count passages.
        # A successful fetch/empty warning list is not complete-page evidence.
        draft = "I checked the highlights page, but the warranty duration is not mentioned there."
        self.assertTrue(unsupported_coverage_claim(draft))
        self.assertEqual(coverage_limitation(draft), LIMIT)
        for unsafe in ("checked", "not mentioned", "hyundai.com", "warranty duration"):
            self.assertNotIn(unsafe, coverage_limitation(draft))

    def test_deictic_and_explicit_source_passives_are_equally_rejected(self):
        for text in (
            "The warranty duration isn't mentioned there.",
            "Warranty terms are not listed here, but the dealer can explain them.",
            "The duration was never explicitly stated on the supplied page.",
            "The warranty is not detailed anywhere.",
            "The tyre size is not specified in that brochure.",
            "Warranty duration is missing from the highlights page.",
            "Warranty duration is absent from the source.",
        ):
            with self.subTest(text=text):
                self.assertEqual(coverage_limitation(text), LIMIT)

    def test_coverage_grammar_handles_other_subjects_and_reporting_forms(self):
        for text in (
            "The highlights page doesn't state the warranty duration.",
            "The document has not specified the boot measurement basis.",
            "That website never mentions a safety rating.",
            "The page makes no mention of warranty.",
            "The brochure lacks the warranty duration.",
            "The source omits the expiry date.",
            "The webpage is silent on warranty duration.",
            "There is no mention of warranty on the highlights page.",
            "There is nothing about warranty there.",
            "None of the sources list an exclusive feature.",
            "The page only lists the engines.",
        ):
            with self.subTest(text=text):
                self.assertTrue(unsupported_coverage_claim(text))

    def test_exhaustive_checking_is_not_licensed_by_a_successful_partial_lookup(self):
        for text in (
            "I checked the entire page and found no warranty duration.",
            "I read all sections of the page.",
            "The whole website was searched for warranty information.",
            "I reviewed every part of the document.",
        ):
            with self.subTest(text=text):
                self.assertEqual(coverage_limitation(text), LIMIT)

    def test_actual_source_facts_and_product_absence_still_use_normal_grounding(self):
        for text in (
            "According to the highlights page, CRETA offers seven variants.",
            "The page lists six airbags on all variants.",
            "According to the feature page, the E trim does not include ventilated seats.",
            "Ventilated seats are not included in the E trim.",
            "This quote does not include registration fees or insurance.",
            "The warranty does not cover wear and tear.",
            "The package includes all the listed safety features.",
            "The brochure states that coverage excludes commercial use.",
            "A separate purchase is required for the Echo device.",
        ):
            with self.subTest(text=text):
                self.assertFalse(unsupported_coverage_claim(text))
                self.assertEqual(coverage_limitation(text), "")

    def test_own_verification_limits_are_not_whole_source_assertions(self):
        for text in (
            LIMIT,
            "I couldn't verify the warranty duration from that page.",
            "I did not find the warranty duration in the retrieved passages.",
            "I could not access the source.",
            "I cannot guarantee that an unlisted feature is absent.",
            "The retrieved passage states that the warranty is payable.",
        ):
            with self.subTest(text=text):
                self.assertFalse(unsupported_coverage_claim(text))

    def test_normalization_never_salvages_appended_world_claims_or_fresh_attribution(self):
        for text in (
            "According to www.hyundai.com, I checked the highlights page, but warranty duration is not mentioned there.",
            "Warranty is not mentioned there, so the car has no warranty.",
            "The website is silent on warranty; every trim therefore includes seven years free.",
            "I checked the entire page; the car is the safest vehicle in the world.",
        ):
            with self.subTest(text=text):
                self.assertEqual(coverage_limitation(text), LIMIT)
                self.assertFalse(unsupported_coverage_claim(coverage_limitation(text)))

    def test_whitespace_and_typographic_contractions_do_not_change_the_result(self):
        self.assertTrue(unsupported_coverage_claim("The page doesn’t\n mention the warranty."))
        self.assertTrue(unsupported_coverage_claim("The duration is not\tmentioned there."))
        for text in ("", None, {}, 3):
            self.assertFalse(unsupported_coverage_claim(text))
            self.assertEqual(coverage_limitation(text), "")

    def test_actual_q002_preserves_both_unknown_facets_only_with_uncited_opt_in(self):
        draft = "However, the exact boot capacity in litres and the seat configuration it was measured under are not specified in the current records."
        self.assertEqual(coverage_limitation(draft), LIMIT)
        self.assertEqual(coverage_limitation(draft, precise=True),
                         "I couldn't verify the exact boot capacity in litres or the seat configuration used for the measurement from the retrieved evidence.")
        self.assertEqual(coverage_limitation("The extended warranty terms are not detailed there.", precise=True),
                         "I couldn't verify the extended warranty terms from the retrieved evidence.")
        self.assertEqual(coverage_limitation("The standard warranty duration is not specified on the website.", precise=True),
                         "I couldn't verify the standard warranty duration from the retrieved evidence.")

    def test_precise_normalization_keeps_unknown_or_product_clauses_out(self):
        for draft in (
            "The boot capacity of 500 litres is not specified there.",
            "The boot capacity and guaranteed family comfort are not specified there.",
            "The seat configuration that has airbags is not specified there.",
            "The warranty duration for all variants is not specified there.",
            "The boot capacity is not specified there, but it exceeds 500 litres.",
            "The warranty duration is not mentioned there because no warranty exists.",
            "I checked the highlights page, but the warranty duration is not mentioned there.",
        ):
            with self.subTest(draft=draft):
                self.assertEqual(coverage_limitation(draft, precise=True), LIMIT)

    def test_negative_fitment_and_purchase_conditions_are_never_rewritten(self):
        for draft in (
            "Ventilated seats are not available on E, EX, or EX(O).",
            "An extended warranty is payable and available on petrol variants only.",
            "The warranty excludes wear and tear.",
            "Alexa integration requires a separate third-party Echo device purchase.",
        ):
            with self.subTest(draft=draft):
                self.assertEqual(coverage_limitation(draft, precise=True), "")

    def test_source_only_inventory_and_record_availability_are_coverage_claims(self):
        for draft in (
            "All our reviewed material currently covers only Hyundai CRETA specifications, features, and policies.",
            "The available records cover only the Hyundai CRETA lineup.",
            "Insurance costs vary by state and city, and future renewal rates are not available in our records.",
            "The renewal rates are unavailable from the supplied document.",
        ):
            with self.subTest(draft=draft):
                self.assertEqual(coverage_limitation(draft, precise=True), LIMIT)
        for draft in (
            "The extended warranty is available only on petrol variants on a payable basis.",
            "Ventilated seats are not available on the E trim.",
            "The E trim lacks ventilated seats.",
            "The feature is not available there.",
            "The page states that ventilated seats are not available on E.",
            "The warranty covers only the listed components.",
        ):
            with self.subTest(draft=draft):
                self.assertFalse(unsupported_coverage_claim(draft))


if __name__ == "__main__":
    unittest.main(verbosity=2)
