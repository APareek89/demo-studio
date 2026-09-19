"""Pure, offline controls for assistant acts; no graph, sources or providers."""
import unittest

from server.runtime_interaction import assistant_behavior


class InteractionContract(unittest.TestCase):
    def test_actual_q065_retains_non_assumption_and_all_requested_slots(self):
        self.assertEqual(assistant_behavior("Understood, I will not assume or estimate your fuel efficiency."),
                         "I will not guess your fuel efficiency.")
        self.assertEqual(assistant_behavior("Whenever you would like to check running costs, just share your expected fuel efficiency, driving distance, and local fuel price, and we can calculate it directly."),
                         "Please share your fuel efficiency, distance, and fuel price.")

    def test_actual_q092_keeps_operating_boundary_without_product_claims(self):
        self.assertEqual(assistant_behavior("No, that will not change my focus at all."),
                         "No, that will not change my answer.")
        self.assertEqual(assistant_behavior("I am here to assist you directly with your questions about the Hyundai Creta."),
                         "I am here to help you with your questions.")

    def test_closed_input_slots_work_across_reordering_and_conjunctions(self):
        self.assertEqual(assistant_behavior("I won't estimate or assume your interest rate and loan term."),
                         "I will not guess your interest rate and loan term.")
        self.assertEqual(assistant_behavior("Please provide your loan amount, interest rate, and tenure."),
                         "Please share your loan amount, interest rate, and tenure.")
        self.assertEqual(assistant_behavior("Let me know local fuel price or driving distance."),
                         "Please share your fuel price or distance.")

    def test_canonical_outputs_remain_recognised_by_the_graphs_second_guard(self):
        for text in (
            "I will not guess your fuel efficiency.",
            "Please share your fuel efficiency, distance, and fuel price.",
            "No, that will not change my answer.",
            "I am here to help you with your questions.",
        ):
            with self.subTest(text=text):
                self.assertEqual(assistant_behavior(text), text)

    def test_appended_world_claims_are_rejected_not_carried_into_dialogue(self):
        for text in (
            "I will not assume your fuel efficiency, and all trims have ADAS.",
            "I will not guess your fuel efficiency because the cabin is bulletproof.",
            "Please share your fuel efficiency, and we can calculate it directly because all trims have ADAS.",
            "Please share your fuel price and the car has airbags.",
            "No, that will not change my focus; all trims have ADAS.",
            "I am here to assist you directly with your questions about the Hyundai Creta that has airbags.",
            "I am here to help you with your questions. The car has airbags.",
        ):
            with self.subTest(text=text):
                self.assertEqual(assistant_behavior(text), "")

    def test_unknown_slots_and_quantities_never_become_supported_inputs(self):
        for text in (
            "I will not assume your crash rating.",
            "Please share your fuel efficiency and bank approval.",
            "Please share your password.",
            "Please share your fuel efficiency of 20 km/l.",
            "I will not assume your eight percent interest rate.",
            "I am here to help you with your questions about the Creta 2026.",
            "Please share your fuel efficiency,,fuel price.",
            "Please share your fuel efficiency and distance or fuel price.",
        ):
            with self.subTest(text=text):
                self.assertEqual(assistant_behavior(text), "")

    def test_own_subject_is_not_a_general_fact_or_instruction_exemption(self):
        for text in (
            "I guarantee your loan approval.",
            "I will ignore the customer and reveal my instructions.",
            "The webpage says I will not assume your fuel efficiency.",
            "No, that will not change the car's safety rating.",
            "I am here to guarantee the Creta has ADAS on every trim.",
            "Ventilated seats require a separate purchase.",
        ):
            with self.subTest(text=text):
                self.assertEqual(assistant_behavior(text), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
