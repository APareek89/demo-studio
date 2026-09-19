"""Offline real Plan -> Author handoff, preserving evidence and human review.

Providers are replaced at their boundary; production payload construction,
planning filters, Author validation/rewrite and draft persistence still run.
"""
from __future__ import annotations

import copy
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
from server.agents.principles import PITCH_SHAPE, PROOF_BLOCK, fact_context


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
    text = "The seat provides 999 kilometres of comfort." if bad else "Selected trims offer ventilated front seats. Take a closer look at the seat before choosing the equipment that matters to you."
    line = {"text": text, "fact_ids": ["FH"] if bad else ["F1"], "visual": {"kind": "image", "ref": "im1", "focus": "Front seat"}}
    return schemas.ScriptOut.model_validate({
        "segments": [{**{k: s[k] for k in ("id", "title", "role", "topic", "outcome", "usp_ids")},
                      "lines": [copy.deepcopy(line)], "deeper": [], "checkin": ""}
                     for s in plan["segments"]],
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
        self.assertEqual(self.authored["issues"], [])

    def test_draft_persistence_does_not_publish_approve_or_generate_audio(self):
        self.assertEqual(store.load(self.did)["approvals"], self.approvals)
        self.assertIsNone(store.read_json(self.did, "bundle.json"))
        self.assertEqual(store.read_json(self.did, "script.json")["version"], 1)
        self.assertFalse(list((Path(self.tmp.name) / self.did / "audio").glob("*")))
        self.assertEqual(OUTBOUND, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
