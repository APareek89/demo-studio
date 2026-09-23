"""Offline real Plan -> Author handoff, preserving evidence and human review.

Providers are replaced at their boundary; production payload construction,
planning filters, Author validation/rewrite and draft persistence still run.
"""
from __future__ import annotations

import copy
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []


def no_network(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Narrative role contracts must not open sockets")


socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network

from server import config, schemas, store
from server.agents import author, plan as planner
from server.agents.principles import PITCH_SHAPE, PROOF_BLOCK, SIGNPOSTS, TRANSLATION_LADDER, fact_context
from server.llm import mock


def fixture_plan():
    roles = ["intro", "outcome", "proof", "features", "establish"]
    return {
        "customer_persona": "An everyday buyer whose priorities are unknown.",
        "decision_frame": "Choose the equipment, then verify the exact trim.",
        "takeaway": "Look closely at the seat before choosing a trim.",
        "primary_outcome": "Compare the seat equipment", "supporting_outcomes": [],
        "concerns": [{"topic": "seat", "why": "Trim fitment matters", "fact_ids": ["F1", "FH"]}],
        "usps": [{"id": f"u{i}", "name": f"Seat choice {i}",
                  "why_it_matters": "Compare the available equipment.", "fact_ids": ["F1"]}
                 for i in range(3)],
        "segments": [{"id": f"s{i}", "title": "The seat", "role": role,
                      "goal": "MOMENT: inspect the pictured seat. SPOKEN: F1 with selected-trim condition; DEEPER: exact fitment. VISUAL / HANDOFF: im1 seat, leave attention on the chosen trim, budget 30 words.",
                      "outcome": "Compare the equipment", "topic": "seat",
                      "fact_ids": ["F1", "FH"], "usp_ids": ["u0"],
                      "visual_refs": ["im1", "hidden-image", "invented-image"], "priority_topic": role == "proof"}
                     for i, role in enumerate(roles)],
        "ctas": [{"id": "contact", "label": "Ask the dealer", "kind": "contact", "url": "", "primary": True}],
        "voice": {"persona_name": "Invented", "persona_description": "She explains the seat.",
                  "tone": "Warm", "sample_line": "Hello, I am Invented.", "suggested_voice": "different"},
        "visual_gaps": [], "intake": {"q1": "Hello from Invented. What matters most?", "q2": "Unwanted second question?", "chips": []},
        "state_questions": [], "do_not_recommend_if": "The required trim feature remains unverified.",
        "advance": "Ask the dealer to confirm the trim.",
        "notes": "Editorial handoff: warm observation, no measured comfort promise."
    }


def fixture_script(plan, bad=False):
    text = "The seat provides 999 kilometres of comfort." if bad else "Selected trims offer ventilated front seats. Take a closer look at the seat before choosing the equipment that matters to you. Start with the seat in view, then compare its equipment against the exact trim you are considering today."
    line = {"text": text, "fact_ids": ["FH"] if bad else ["F1"], "visual": {"kind": "image", "ref": "im1", "focus": "Front seat"}}
    return schemas.ScriptOut.model_validate({
        "segments": [{**{k: s[k] for k in ("id", "title", "role", "topic", "outcome", "usp_ids")},
                      "lines": [copy.deepcopy(line) if bad or s["role"] not in {"intro", "outcome"} else {**copy.deepcopy(line), "text": "Selected trims offer ventilated front seats. Look at the seat in view, then compare its equipment with the exact trim you are considering."}], "deeper": [], "checkin": "Shall we continue?" if bad and index == 2 else ""}
                     for index, s in enumerate(plan["segments"])],
        "closing": [], "intake_q1": "Welcome. What matters most, or shall we begin?", "intake_q2": ""
    })


class NarrativeRolesContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="narrative-roles-")
        cls.data = patch.object(config, "DATA_DIR", Path(cls.tmp.name)); cls.data.start()
        cls.mock = patch.object(config, "MOCK_LLM", True); cls.mock.start()
        cls.provider_order = copy.deepcopy(config.BUILD_PROVIDERS)
        demo = store.new_demo("Fixture product"); cls.did = demo["id"]
        store.update(cls.did, lambda d: d["settings"].update(
            tts_provider="sarvam", voice_locked=True, sarvam_speaker="priya", language="en-IN"))
        store.update(cls.did, lambda d: d["sources"].extend([
            {"id": "visible", "kind": "image", "use_in_demo": True},
            {"id": "hidden", "kind": "image", "use_in_demo": False}]))
        cls.approvals = copy.deepcopy(store.load(cls.did)["approvals"])
        cls.fact = {"id": "F1", "kind": "feature", "claim": "Front seat ventilation",
                    "value": "Ventilated front seats", "conditions": "Selected trims only",
                    "scope": {"model": "Fixture product"}, "approved": True,
                    "source": {"ref": "official", "locator": "page 2", "quote": "Ventilated front seats on selected trims"}}
        held = {**cls.fact, "id": "FH", "value": "HIDDEN_HELD_ASSERTION", "approved": False}
        cls.und = {"product": {"name": "Fixture product"}, "brand": {}, "facts": [cls.fact, held],
                   "shots": [], "unknowns": [], "images": [
                       {"id": "im1", "source_id": "visible", "angle": "interior", "description": "A front seat", "parts": [{"name": "seat"}], "quality": 5},
                       {"id": "hidden-image", "source_id": "hidden", "angle": "detail", "description": "HIDDEN_VISUAL", "parts": [], "quality": 5}]}
        store.write_json(cls.did, "understanding.json", cls.und)
        store.write_json(cls.did, "playbook.json", {
            "category": "Fixture product", "category_source": "inferred", "library_version": "2026-09-23",
            "stops": [{"id": "seat", "label": "The front seat", "kind": "fundamental",
                       "why_here": "Begin with the everyday seating choice.", "fact_ids": ["F1"],
                       "picture_ids": ["im1"], "must_cover": True, "gaps": []}],
            "usps": [{"id": f"u{i}", "name": name, "fact_ids": ["F1"], "stop_id": "seat"}
                     for i, name in enumerate(["Choose the seat equipment", "Know your seating choices", "Review the right trim"])],
            "objections": [], "evidence_gaps": [], "notes": "", "issues": []})
        cls.calls = []

        def fake_provider(system, content, schema, **kwargs):
            cls.calls.append({"system": system, "content": content, "schema": schema})
            if schema is schemas.Plan:
                return schemas.Plan.model_validate(fixture_plan())
            plan_payload = json.loads(content.split("\nPLAN: ", 1)[1].split("\n\nFACT REGISTRY", 1)[0])
            return fixture_script(plan_payload, bad=sum(c["schema"] is schemas.ScriptOut for c in cls.calls) == 1)

        with patch.object(planner.claude, "structured", side_effect=fake_provider):
            cls.planned = planner.run(cls.did, lambda _: None)
            cls.authored = author.run(cls.did, lambda _: None)
        cls.author_calls = [c for c in cls.calls if c["schema"] is schemas.ScriptOut]
        cls.author_plan = json.loads(cls.author_calls[0]["content"].split("\nPLAN: ", 1)[1].split("\n\nFACT REGISTRY", 1)[0])

    @classmethod
    def tearDownClass(cls):
        cls.mock.stop(); cls.data.stop(); cls.tmp.cleanup()

    def test_real_payload_roles_use_distinct_contracts(self):
        self.assertEqual([c["schema"] for c in self.calls], [schemas.Plan, schemas.ScriptOut, schemas.ScriptOut])
        self.assertIn(PITCH_SHAPE, self.calls[0]["system"])
        self.assertIn(PROOF_BLOCK, self.calls[0]["system"])
        self.assertNotIn(PITCH_SHAPE, self.author_calls[0]["system"])
        self.assertNotIn(PROOF_BLOCK, self.author_calls[0]["system"])
        self.assertEqual(self.provider_order, config.BUILD_PROVIDERS)

    def test_author_formatter_has_no_planner_flow_injection(self):
        formatter = inspect.getsource(author.run).split("sys = AUTHOR_SYSTEM.format", 1)[1].split("\n    try:", 1)[0]
        self.assertNotIn("PITCH_SHAPE", formatter)
        self.assertNotIn("proof_block", formatter)

    def test_author_continuity_ladder_and_openings_reach_the_real_provider(self):
        prompt = self.author_calls[0]["system"]
        self.assertIn("CONTINUITY AND STANDING ALONE", prompt)
        self.assertIn("TRANSLATION LADDER", prompt)
        self.assertIn(TRANSLATION_LADDER, prompt)
        self.assertIn("A FIT-CHECK IS A LAST RESORT", prompt)
        self.assertLess(prompt.index("TRANSLATION LADDER"), prompt.index("A FIT-CHECK IS A LAST RESORT"))
        self.assertIn("OPENINGS. Never open a segment with a stock signpost", prompt)
        self.assertTrue(all(shape in prompt for shape in SIGNPOSTS))
        self.assertNotIn("panoramic sunroof", author.AUTHOR_SYSTEM)
        self.assertNotIn("Show standout features early", author.AUTHOR_SYSTEM)

    def test_playbook_owns_order_while_author_follows_typed_budget(self):
        self.assertNotIn("standout feature first", PITCH_SHAPE)
        self.assertIn("the playbook's stops in order, spoken as a walk", PITCH_SHAPE)
        self.assertIn("The first stop of the playbook, in everyday words", PITCH_SHAPE)
        prompt = self.author_calls[0]["system"]
        self.assertIn("4. THE PLAN IS SETTLED", prompt)
        self.assertIn("a segment under its word_budget that flows", prompt)
        self.assertIn("within the segment's word_budget", prompt)
        self.assertIn("the first supported fundamental in the playbook", prompt)
        self.assertIn("No greeting, question, decision frame, digits or dimensions. Delighters come later.", prompt)
        self.assertTrue(all(isinstance(segment["word_budget"], int) and segment["word_budget"] > 0 for segment in self.author_plan["segments"]))
        self.assertEqual(self.author_plan["total_words"], self.planned["total_words"])
        self.assertEqual(self.author_plan["playbook_version"], "2026-09-23")

    def test_mock_author_uses_the_actual_planned_stops(self):
        draft = mock.fake(schemas.ScriptOut, "PRODUCT: {}\nPLAN: " + json.dumps(self.planned)).model_dump()
        self.assertEqual([(segment["id"], segment["role"], segment["title"]) for segment in draft["segments"]],
                         [(segment["id"], segment["role"], segment["title"]) for segment in self.planned["segments"]])
        for segment, planned in zip(draft["segments"], self.planned["segments"]):
            self.assertTrue(all(line["fact_ids"] == planned["fact_ids"] for line in segment["lines"]))

    def test_opening_prompts_do_not_reintroduce_cabin_or_standout_first(self):
        prompts = " ".join((author.AUTHOR_SYSTEM + "\n" + PITCH_SHAPE).split())
        self.assertNotIn("A good opening makes the buyer want to see the cabin or try a feature", prompts)
        self.assertNotIn("lead with the strongest sourced reason to explore this product and the feature that demonstrates it", prompts)
        self.assertIn("lead with the playbook's first stop, in everyday words, and the feature that demonstrates it.", PITCH_SHAPE)

    def test_new_draft_question_is_preserved_for_the_author_repair_pass(self):
        rewrite = self.author_calls[1]["content"]
        draft = json.loads(rewrite.split("\n\nYOUR DRAFT:\n", 1)[1].split("\n\nVALIDATOR ISSUES", 1)[0])
        self.assertEqual(draft["segments"][2]["checkin"], "Shall we continue?")
        self.assertIn("s2 checkin: must be a short closing statement, never a question", rewrite)
        self.assertEqual(self.authored["segments"][2]["checkin"], "")

    def test_overview_schema_and_runtime_plan_agree_on_fundamental_first(self):
        description = schemas.ScriptOut.model_fields["overview"].description
        self.assertIn("Lead with the first supported fundamental in the reviewed playbook, as mapped to PLAN.segments", description)
        self.assertIn("retain variant qualifiers and cite facts", description)
        self.assertIn("No greeting, question, decision frame, digits or spec list; delighters come later", description)
        self.assertNotIn("standout", description)
        prompt = " ".join(self.calls[0]["system"].split())
        self.assertIn("The initial runtime route leads with the first unseen fundamental, then follows the buyer’s strongest signal; later refinements retain the buyer’s requested order, so each proof must stand alone.", prompt)
        self.assertNotIn("runtime plays the buyer's strongest signal first", prompt)

    def test_rewrite_preserves_unflagged_lines_and_repairs_whole_ideas(self):
        rewrite = self.author_calls[1]["content"]
        self.assertIn("VALIDATOR ISSUES — each names a specific segment or line. Fix ONLY those.", rewrite)
        self.assertIn("every unflagged line reproduced exactly as you wrote it", rewrite)
        self.assertIn("CUT A WHOLE\nIDEA, DO NOT COMPRESS A SENTENCE", rewrite)
        self.assertIn('Issues whose text contains the word "warning" are advisory', rewrite)

    def test_story_intent_visual_order_and_editorial_notes_reach_author(self):
        self.assertEqual(self.author_plan["segments"], self.planned["segments"])
        self.assertEqual(self.author_plan["notes"], fixture_plan()["notes"])
        self.assertEqual(self.author_plan["segments"][2]["goal"], fixture_plan()["segments"][2]["goal"])
        self.assertEqual(self.author_plan["segments"][2]["visual_refs"], ["im1"])
        self.assertEqual([s["id"] for s in self.authored["segments"]], [s["id"] for s in self.planned["segments"]])

    def test_approved_registry_and_full_conditions_remain_the_only_factual_input(self):
        for call in self.calls:
            self.assertIn(fact_context(self.fact), call["content"])
            self.assertNotIn("HIDDEN_HELD_ASSERTION", call["content"])
            self.assertNotIn("HIDDEN_VISUAL", call["content"])
        self.assertTrue(all(s["fact_ids"] == ["F1"] for s in self.planned["segments"]))
        self.assertEqual(self.planned["concerns"][0]["fact_ids"], ["F1"])

    def test_locked_voice_and_single_intake_survive_planner_to_author(self):
        self.assertEqual(self.author_plan["voice"]["persona_name"], "Priya")
        self.assertEqual(self.author_plan["voice"]["suggested_voice"], "priya")
        self.assertNotIn("Invented", self.author_plan["intake"]["q1"])
        self.assertEqual(self.author_plan["intake"]["q2"], "")
        self.assertEqual(self.authored["intake_q2"], "")

    def test_actual_validation_rewrites_figure_using_a_rejected_citation(self):
        self.assertEqual(len(self.author_calls), 2)
        rewrite = self.author_calls[1]["content"]
        self.assertIn("VALIDATOR ISSUES", rewrite)
        self.assertIn("999", rewrite)
        self.assertIn(self.planned["segments"][2]["goal"], rewrite)
        self.assertTrue(all("999" not in l["text"] and not l["unverified"]
                            for s in self.authored["segments"] for l in s["lines"]))
        self.assertTrue(self.authored["issues"])
        self.assertTrue(all("before publication" in issue for issue in self.authored["issues"]), self.authored["issues"])
        self.assertFalse(self.authored["narration_minimum"]["sufficient"])

    def test_draft_persistence_does_not_publish_approve_or_generate_audio(self):
        self.assertEqual(store.load(self.did)["approvals"], self.approvals)
        self.assertIsNone(store.read_json(self.did, "bundle.json"))
        self.assertEqual(store.read_json(self.did, "script.json")["version"], 1)
        self.assertFalse(list((Path(self.tmp.name) / self.did / "audio").glob("*")))
        self.assertEqual(OUTBOUND, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
