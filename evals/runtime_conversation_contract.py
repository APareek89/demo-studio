"""Offline graph controls for typed conversation and preserved useful repairs."""
import asyncio
import copy
import os
import time
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
from pydantic import ValidationError
from server import runtime_graph as rg
from server.runtime_state import InteractionAct, SpokenClaim, TurnControl, TurnDecision


def act(mode, *, subject=None, inputs=None):
    return {"mode":mode,"subject_ids":[subject] if subject else [],"input_ids":inputs or []}


SPLIT={"id":"F096","kind":"feature","claim":"Rear seat split functionality","value":"60:40 Split rear seat",
       "conditions":"Standard rear seating arrangement","scope":{"model":"CRETA","market":"India"},"approved":True}
RECLINE={"id":"F197","kind":"feature","claim":"Interior comfort and convenience features",
         "value":"Ventilated front seats, panoramic sunroof, wireless charging, dual-zone automatic climate control, D-cut steering wheel, 60:40 split rear seats, rear-seat recline function, and digital instrument cluster",
         "conditions":"Availability depends on selected variant","scope":{"model":"CRETA"},"approved":True}


class ConversationContract(unittest.TestCase):
    def test_old_decisions_keep_optional_defaults(self):
        decision=TurnDecision(action="answer",sentences=[{"text":"I cannot guarantee that.","kind":"limitation"}])
        self.assertIsNone(decision.clarification_act)
        self.assertIsNone(decision.sentences[0].interaction)
        result,errors=rg.validate_decision(decision.model_dump(),[],"Can you guarantee that?")
        self.assertEqual(result["answer"],"I cannot guarantee that.")
        self.assertFalse(errors)

    def test_schema_cannot_carry_free_form_act_payload(self):
        for payload in (act("verification_limit",subject="airbags_on_every_trim"),
                        {**act("fit_check",subject="personal_comfort"),"wording":"All trims are safe"},
                        act("input_request",inputs=["password"])):
            with self.assertRaises(ValidationError):InteractionAct.model_validate(payload)

    def test_missing_rate_and_tenure_are_real_wait_not_rejected_text(self):
        decision=TurnDecision(action="clarify",clarification_act=act("input_request",inputs=["loan_amount","interest_rate","loan_tenure"]))
        result,errors=rg.validate_decision(decision.model_dump(),[],"Calculate EMI for a 10 lakh rupee loan. What else do you need?")
        self.assertFalse(errors)
        self.assertEqual(result["answer"],result["clarifying_question"])
        self.assertEqual(result["answer"].count("?"),1)
        self.assertIn("interest",result["answer"])
        self.assertNotIn("loan amount",result["answer"])
        self.assertFalse(result["fact_ids"])

    def test_missing_fuel_inputs_do_not_repeat_known_distance(self):
        decision=TurnDecision(action="clarify",clarification_act=act("input_request",inputs=["travel_distance","fuel_efficiency","fuel_price"]))
        result,errors=rg.validate_decision(decision.model_dump(),[],"I drive 1000 km each month. What information do you need before estimating fuel cost?")
        self.assertFalse(errors)
        self.assertIn("efficiency",result["answer"])
        self.assertIn("fuel price",result["answer"])
        self.assertNotIn("distance",result["answer"])

    def test_verified_act_never_voices_its_raw_model_text(self):
        row={"kind":"limitation","fact_ids":[],"text":"The car has twelve airbags.","interaction":act("verification_limit",subject="rear_armrest")}
        result,errors=rg.validate_decision({"action":"answer","sentences":[row]},[],"Does it have a rear-seat armrest?")
        self.assertFalse(errors)
        self.assertIn("armrest",result["answer"])
        self.assertNotIn("airbag",result["answer"])

    def test_act_cannot_authorize_a_product_row_or_citation(self):
        for extra in ({"kind":"fact"},{"fact_ids":["F096"]},{"kind":"context"}):
            row={"kind":"limitation","fact_ids":[],"text":"The car has twelve airbags.","interaction":act("verification_limit",subject="rear_armrest"),**extra}
            result,errors=rg.validate_decision({"action":"answer","sentences":[row]},[SPLIT],"Does it have a rear-seat armrest?")
            self.assertIn("invalid_interaction_act",errors)
            self.assertNotIn("twelve",result["answer"])
            self.assertFalse(result["fact_ids"])

    def test_invalid_top_level_act_cannot_fall_back_to_unchecked_question(self):
        result,errors=rg.validate_decision({"action":"clarify","clarification":"It has twelve airbags, right?","clarification_act":act("input_request",inputs=["password"])},[],"What do you need to calculate fuel cost?")
        self.assertIn("invalid_interaction_act",errors)
        self.assertFalse(result["clarifying_question"])

    def test_personal_limit_and_fit_check_preserve_equipment(self):
        rows=[{"text":"The CRETA features a standard 60:40 split rear seat.","kind":"fact","fact_ids":["F096"]},
              {"kind":"limitation","interaction":act("verification_limit",subject="personal_comfort")},
              {"kind":"context","interaction":act("fit_check",subject="personal_comfort")}]
        result,errors=rg.validate_decision({"action":"answer","answered":True,"sentences":rows},[SPLIT],"Will the rear seat be comfortable on a long family trip?")
        self.assertFalse(errors)
        self.assertEqual(result["fact_ids"],["F096"])
        self.assertIn("comfort",result["answer"])
        self.assertIn("test drive",result["answer"])

    def test_fact_with_one_typed_question_waits_without_automatic_slide_jump(self):
        state={"demo_id":"contract-unused","question":"I carry luggage. Which variant should I choose?",
               "evidence":[SPLIT],"slide_id":"sl-current","snapshot_id":"fixture","errors":[],"tool_results":[],
               "decision":{"action":"answer","answered":True,"sentences":[
                   {"text":"The CRETA features a standard 60:40 split rear seat.","kind":"fact","fact_ids":["F096"]},
                   {"kind":"context","interaction":act("input_request",inputs=["variant"])}]}}
        # Ask a current local-price question so variant is a relevant missing input.
        state["question"]="What is the on-road price in Pune?"
        with patch("server.runtime_graph.store.read_json",return_value={}),patch("server.runtime_graph.deck.route_for") as route:
            result=asyncio.run(rg.validate(state))["result"]
        self.assertTrue(result["clarifying_question"])
        self.assertEqual(result["route"],"none")
        self.assertEqual(result["slide_id"],"sl-current")
        route.assert_not_called()

    def test_typed_input_question_is_spoken_last_before_waiting(self):
        rows=[{"kind":"context","interaction":act("input_request",inputs=["city","variant"])},
              {"text":"The CRETA features a standard 60:40 split rear seat.","kind":"fact","fact_ids":["F096"]}]
        result,errors=rg.validate_decision({"action":"answer","answered":True,"sentences":rows},[SPLIT],"What is the on-road price?")
        self.assertFalse(errors)
        self.assertTrue(result["clarifying_question"])
        self.assertTrue(result["answer"].endswith(result["clarifying_question"]))
        self.assertTrue(result["answer"].startswith("The CRETA"))

    def test_actual_luggage_repair_keeps_supported_new_fact_despite_optional_aside(self):
        question="I carry luggage every weekend. What practical storage details can you confirm?"
        original=[{"text":"The CRETA comes with a 60:40 split rear seat to adapt your cargo space.","fact_ids":["F096"],"kind":"fact"},
                  {"text":"A rear-seat recline function is also available depending on your selected variant.","fact_ids":["F197"],"kind":"fact"},
                  {"text":"I do not have the exact boot volume measurement or specific cubby dimensions in my verified records.","fact_ids":[],"kind":"limitation"}]
        repair=rg._CompositionRepair(sentences=[
            {"text":"The CRETA features a standard 60:40 split rear seat.","fact_ids":["F096"],"kind":"fact"},
            {"text":"A rear-seat recline function is also offered depending on your chosen variant.","fact_ids":["F197"],"kind":"fact"},
            {"text":"I cannot verify exact boot volume figures or luggage dimensions in our approved details.","fact_ids":[],"kind":"limitation"}])
        state={"demo_id":"contract-unused","question":question,"evidence":copy.deepcopy([SPLIT,RECLINE]),
               "control":TurnControl(time.monotonic()+12),"errors":[],"tool_results":[],"decision":{"action":"answer","answered":True,"sentences":original}}
        with patch("server.runtime_graph.config.MOCK_LLM",False),patch("server.runtime_graph.runtime.structured",return_value=repair) as model,patch("server.runtime_graph.store.read_json",return_value={}),patch("server.runtime_graph.usage.trace"):
            result=asyncio.run(rg.validate(state))["result"]
        self.assertEqual(model.call_count,1)
        self.assertTrue(result["validation_repair"]["accepted"])
        self.assertEqual(set(result["fact_ids"]),{"F096","F197"})
        self.assertNotIn("adapt your cargo",result["answer"])
        self.assertIn("60:40",result["answer"])


if __name__=="__main__":unittest.main(verbosity=2)
