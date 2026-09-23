"""Offline plain-runtime contracts: approved speech, repair, demo settings and saved delivery."""
from __future__ import annotations

import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

_STORAGE = tempfile.TemporaryDirectory(prefix="runtime-plain-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=_STORAGE.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_STORAGE.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []


def blocked(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Plain-language contracts must not open outbound sockets")


socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked

from server import config, runtime_graph as rg, store
from server.agents import faq, plain_terms
from server.runtime_state import TurnControl


def fact(value="The front suspension uses McPherson strut.", id="F1"):
    return {"id": id, "claim": "Front suspension", "value": value, "kind": "feature", "truth": "stated", "approved": True,
            "source": {"ref": "approved-spec", "quote": value, "locator": "Suspension"}, "provenance": "uploaded", "conditions": "", "scope": {}}


def decision(text, ids=None):
    return {"action": "answer", "answered": True, "sentences": [{"text": text, "kind": "fact", "fact_ids": ["F1"] if ids is None else ids}]}


class PlainLanguageContract(unittest.TestCase):
    def setUp(self):
        self.did = store.new_demo("Plain-language runtime")["id"]
        self.evidence = [fact()]
        self.text = self.evidence[0]["value"]
        self.question = "Tell me about the front suspension."
        self.und = {"product": {"name": "Example", "category": "Compact SUV"}, "facts": self.evidence, "images": [], "shots": [], "unknowns": []}
        store.write_json(self.did, "understanding.json", self.und)

    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def state(self, text=None):
        return {"demo_id": self.did, "session_id": "plain-session", "turn_id": "plain-turn", "question": self.question,
                "history": [], "profile": {}, "evidence": self.evidence, "decision": decision(text or self.text), "requested_scope": {},
                "errors": [], "tool_results": [], "timings": {}, "control": TurnControl(time.monotonic() + 12)}

    def test_mcpherson_substituted_after_grounding_with_same_citation(self):
        result, errors = rg.validate_decision(decision(self.text), self.evidence, self.question)
        self.assertEqual(errors, [])
        self.assertEqual(result["answer"], "The front suspension uses strut-type front suspension.")
        self.assertEqual(result["fact_ids"], ["F1"])
        self.assertEqual(result["facts"][0]["value"], self.text)
        self.assertTrue(result["answered"])
        self.assertEqual(result["plain_language_substitutions"], [("mcpherson strut", "strut-type front suspension")])

    def test_unsupported_citation_rejected_before_plain_rewriting(self):
        with patch.object(plain_terms, "substitute", wraps=plain_terms.substitute) as substitute:
            result, errors = rg.validate_decision(decision(self.text, ["invented"]), self.evidence, self.question)
        self.assertIn("unsupported_citation", errors)
        self.assertFalse(substitute.called)
        self.assertFalse(result["answered"])
        self.assertEqual(result["plain_language_substitutions"], [])

    def test_scope_conditions_survive_neutral_substitution(self):
        evidence = [fact("Selected variants have IVT.")]
        evidence[0].update(claim="Gearbox", conditions="selected variants")
        result, errors = rg.validate_decision(decision("Selected variants have IVT."), evidence, "Tell me about the gearbox.")
        self.assertEqual(errors, [])
        self.assertIn("Selected variants", result["answer"])
        self.assertIn("automatic gearbox", result["answer"])
        self.assertEqual(result["fact_ids"], ["F1"])

    def test_unmapped_term_has_actionable_repair_feedback(self):
        text = "The front suspension uses double wishbone."
        feedback = []
        with patch.dict(plain_terms.JARGON, {"double wishbone": None}):
            result, errors = rg.validate_decision(decision(text), [fact(text)], self.question, row_feedback=feedback)
        self.assertIn("technical_term", errors)
        self.assertFalse(result["answered"])
        self.assertEqual(feedback[-1]["instruction"], "replace 'double wishbone' with everyday words or drop the sentence")
        self.assertNotIn("double wishbone", result["answer"])

    def test_residual_rejection_reaches_one_repair_and_repaired_sentence_passes(self):
        text = "The front suspension uses double wishbone."
        state = self.state(text)
        state["evidence"] = [fact(text)]
        repaired = rg._CompositionRepair(sentences=[{"text": "The front suspension is listed.", "fact_ids": ["F1"], "kind": "fact"}])
        with patch.dict(plain_terms.JARGON, {"double wishbone": None}), patch.object(config, "MOCK_LLM", False), \
             patch.object(rg.runtime, "structured", return_value=repaired) as model, patch.object(rg.usage, "trace"):
            output = asyncio.run(rg.validate(state))
        self.assertEqual(model.call_count, 1)
        payload = json.loads(model.call_args.args[1])
        self.assertEqual(payload["validation_feedback"][0]["error"], "technical_term")
        self.assertIn("replace 'double wishbone' with everyday words or drop the sentence", payload["validation_feedback"][0]["instruction"])
        self.assertTrue(output["result"]["validation_repair"]["accepted"])
        self.assertEqual(output["result"]["answer"], "The front suspension is listed.")
        self.assertEqual(output["result"]["validation_errors"], [])

    def test_repair_candidate_also_uses_plain_rendering_and_metadata(self):
        state = self.state("The front suspension uses double wishbone.")
        state["evidence"] = [fact("The front suspension uses double wishbone or McPherson strut.")]
        repaired = rg._CompositionRepair(sentences=[{"text": self.text, "fact_ids": ["F1"], "kind": "fact"}])
        with patch.dict(plain_terms.JARGON, {"double wishbone": None}), patch.object(config, "MOCK_LLM", False), \
             patch.object(rg.runtime, "structured", return_value=repaired), patch.object(rg.usage, "trace") as trace:
            output = asyncio.run(rg.validate(state))
        self.assertTrue(output["result"]["validation_repair"]["accepted"])
        self.assertIn("strut-type front suspension", output["result"]["answer"])
        self.assertTrue(output["result"]["plain_language_substitutions"])
        repair_trace = next(call for call in trace.call_args_list if call.args[0] == "runtime-validation-repair")
        self.assertTrue(json.loads(repair_trace.kwargs["response"])["plain_language_substitutions"])

    def test_explicit_technical_request_keeps_exact_cited_term(self):
        for question in ("What is the exact type of front suspension?", "Give the technical specification.", "Which type of suspension is listed?"):
            result, errors = rg.validate_decision(decision(self.text), self.evidence, question)
            self.assertEqual(errors, [])
            self.assertEqual(result["answer"], self.text)
            self.assertEqual(result["fact_ids"], ["F1"])
            self.assertEqual(result["plain_language_substitutions"], [])

    def test_expert_and_technical_audiences_bypass_substitution(self):
        for audience in ("expert", "technical"):
            result, errors = rg.validate_decision(decision(self.text), self.evidence, self.question, audience=audience)
            self.assertEqual(errors, [])
            self.assertEqual(result["answer"], self.text)
            self.assertEqual(result["plain_language_substitutions"], [])

    def test_common_terms_are_allowed_and_unchanged(self):
        for term in plain_terms.COMMON_TERMS:
            self.assertTrue(plain_terms.allowed(term.upper()))
            self.assertEqual(plain_terms.substitute(term), (term, []))
        self.assertFalse(plain_terms.allowed("McPherson strut"))

    def test_whole_phrase_boundaries_do_not_replace_word_fragments(self):
        text = "Absolutely GDiBadge is different from IVTune and McPherson strutural."
        self.assertEqual(plain_terms.find_jargon(text), [])
        self.assertEqual(plain_terms.substitute(text), (text, []))

    def test_longest_phrase_wins_without_reprocessing_replacements(self):
        text, subs = plain_terms.substitute("Level 2 ADAS, 7-speed DCT and coupled torsion beam axle.")
        self.assertEqual(text, "advanced driver-assistance features, seven-speed dual-clutch automatic and a simple rear suspension setup.")
        self.assertEqual([item[0] for item in subs], ["level 2 adas", "7-speed dct", "coupled torsion beam axle"])
        self.assertEqual(plain_terms.find_jargon(text), [])

    def test_word_cap_counts_expanded_speech_and_keeps_no_truncated_claim(self):
        text = " ".join(["IVT"] * 60) + "."
        result, errors = rg.validate_decision(decision(text), [fact(text)], "Tell me about the gearbox.")
        self.assertLess(len(text.split()), 115)
        self.assertIn("answer_too_long", errors)
        self.assertFalse(result["answered"])
        self.assertEqual(result["fact_ids"], [])
        self.assertEqual(result["plain_language_substitutions"], [])
        self.assertNotIn("IVT", result["answer"])

    def test_branded_adjacent_aliases_render_once_without_changing_scope(self):
        for original in ("Hyundai SmartSense", "HYUNDAI SmartSense", "Hyundai's SmartSense",
                         "Hyundai SmartSense Level 2 ADAS suite", "SmartSense ADAS package"):
            text = f"On selected higher trims, {original} includes lane-keeping assist."
            evidence = [fact(text)]
            evidence[0]["conditions"] = "selected higher trims"
            result, errors = rg.validate_decision(decision(text), evidence, "What driver assistance is listed?")
            self.assertEqual(errors, [], original)
            self.assertEqual(result["answer"], "On selected higher trims, Hyundai's driver-assistance package includes lane-keeping assist.")
            self.assertEqual(result["fact_ids"], ["F1"])
            self.assertEqual(result["facts"][0]["value"], text)
            self.assertEqual(result["plain_language_substitutions"], [("smartsense", plain_terms.JARGON["smartsense"])])
            technical, errors = rg.validate_decision(decision(text), evidence, "Give the exact technical specification.")
            self.assertEqual(errors, [])
            self.assertEqual(technical["answer"], text)
            self.assertEqual(technical["plain_language_substitutions"], [])
        for original in ("NotHyundai SmartSense", "Hyundai SmartSense and ADAS", "Hyundai SmartSense. Level 2 ADAS suite"):
            rendered, _ = plain_terms.substitute(original)
            self.assertIn("Hyundai's driver-assistance package", rendered)
            if original.startswith("NotHyundai"):
                self.assertTrue(rendered.startswith("NotHyundai "))
            else:
                self.assertIn("driver-assistance features", rendered)
        for original in ("ISOFIX child seat anchors", "ISOFIX child-seat mounts"):
            text = f"Selected variants have {original}."
            result, errors = rg.validate_decision(decision(text), [fact(text)], "What child-seat equipment is listed?")
            self.assertEqual(errors, [])
            self.assertEqual(result["answer"], "Selected variants have child-seat mounts.")
            self.assertEqual(result["fact_ids"], ["F1"])
            self.assertEqual(result["plain_language_substitutions"], [("isofix", plain_terms.JARGON["isofix"])])
        self.assertEqual(plain_terms.substitute("ISOFIX and child seat anchors")[0], "child-seat mounts and child seat anchors")
        self.assertEqual(plain_terms.substitute("ISOFIX child seat storage")[0], "child-seat mounts child seat storage")

    def test_live_hostname_stays_exact_while_its_claim_is_plain(self):
        evidence = [fact("ADAS is available.")]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": evidence[0]["value"]})
        result, errors = rg.validate_decision(decision(evidence[0]["value"]), evidence, "What driver assistance is listed?")
        self.assertEqual(errors, [])
        self.assertEqual(result["answer"], "According to adas.example, driver-assistance features is available.")
        self.assertEqual(result["plain_language_substitutions"], [("adas", "driver-assistance features")])
        self.assertEqual(result["fact_ids"], ["F1"])
        self.assertEqual(result["facts"][0]["source"]["ref"], "https://adas.example/car")

    def test_live_hostname_is_neither_product_claim_nor_unmapped_jargon(self):
        evidence = [fact("Six airbags are available.")]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": evidence[0]["value"]})
        with patch.dict(plain_terms.JARGON, {"adas": None}):
            result, errors = rg.validate_decision(decision(evidence[0]["value"]), evidence, "What safety equipment is listed?")
        self.assertEqual(errors, [])
        self.assertEqual(result["answer"], "According to adas.example, six airbags are available.")
        self.assertTrue(result["answered"])
        self.assertEqual(result["plain_language_substitutions"], [])

    def test_model_leading_cited_hostname_is_protected_and_normalized(self):
        evidence = [fact("ADAS is available.")]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": evidence[0]["value"]})
        for prefix in ("According to adas.example, ", "According to ADAS.EXAMPLE, ", "As per adas.example, "):
            result, errors = rg.validate_decision(decision(prefix + evidence[0]["value"]), evidence, "What driver assistance is listed?")
            self.assertEqual(errors, [])
            self.assertEqual(result["answer"], "According to adas.example, driver-assistance features is available.")
            self.assertEqual(result["plain_language_substitutions"], [("adas", "driver-assistance features")])

    def test_model_leading_uncited_hostname_is_rejected_before_substitution(self):
        evidence = [fact("ADAS is available.")]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": evidence[0]["value"]})
        for prefix in ("According to wrong.example, ", "According to adas.example and wrong.example, ", "As per wrong.example's page, "):
            with patch.object(plain_terms, "substitute", wraps=plain_terms.substitute) as substitute:
                result, errors = rg.validate_decision(decision(prefix + evidence[0]["value"]), evidence, "What driver assistance is listed?")
            self.assertIn("unverified_web_attribution", errors)
            self.assertFalse(result["answered"])
            self.assertFalse(substitute.called)
        evidence[0]["provenance"] = "uploaded"
        result, errors = rg.validate_decision(decision("According to adas.example, ADAS is available."), evidence, "What driver assistance is listed?")
        self.assertIn("unverified_web_attribution", errors)
        self.assertFalse(result["answered"])

    def test_filename_shaped_attribution_still_requires_the_exact_live_host(self):
        evidence = [fact("ADAS is available.")]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": evidence[0]["value"]})
        for host in ("creta.pdf", "node.js", "specs.xlsx"):
            with patch.object(plain_terms, "substitute", wraps=plain_terms.substitute) as substitute:
                result, errors = rg.validate_decision(decision(f"According to {host}, ADAS is available."), evidence, "What driver assistance is listed?")
            self.assertIn("unverified_web_attribution", errors)
            self.assertFalse(result["answered"])
            self.assertFalse(substitute.called)
        evidence[0]["source"]["ref"] = "https://node.js/car"
        result, errors = rg.validate_decision(decision("According to node.js, ADAS is available."), evidence, "What driver assistance is listed?")
        self.assertEqual(errors, [])
        self.assertEqual(result["answer"], "According to node.js, driver-assistance features is available.")

    def test_live_attribution_counts_toward_final_word_cap(self):
        text = " ".join(["suspension"] * 113) + "."
        evidence = [fact(text)]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": text})
        for model_text in (text, "According to adas.example, " + text):
            result, errors = rg.validate_decision(decision(model_text), evidence, self.question)
            self.assertLessEqual(len(text.split()), 115)
            self.assertIn("answer_too_long", errors)
            self.assertFalse(result["answered"])
            self.assertEqual(result["fact_ids"], [])
            self.assertNotIn("adas.example", result["answer"])

    def test_repaired_live_claim_preserves_hostname_and_plain_metadata(self):
        state = self.state("The front suspension uses double wishbone.")
        state["evidence"] = [fact("The front suspension uses double wishbone or McPherson strut.")]
        state["evidence"][0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": state["evidence"][0]["value"]})
        repaired = rg._CompositionRepair(sentences=[{"text": "According to adas.example, " + self.text, "fact_ids": ["F1"], "kind": "fact"}])
        with patch.dict(plain_terms.JARGON, {"double wishbone": None}), patch.object(config, "MOCK_LLM", False), \
             patch.object(rg.runtime, "structured", return_value=repaired) as model, patch.object(rg.usage, "trace"):
            output = asyncio.run(rg.validate(state))
        self.assertEqual(model.call_count, 1)
        self.assertTrue(output["result"]["validation_repair"]["accepted"])
        self.assertEqual(output["result"]["answer"], "According to adas.example, the front suspension uses strut-type front suspension.")
        self.assertEqual(output["result"]["plain_language_substitutions"], [("mcpherson strut", "strut-type front suspension")])
        self.assertEqual(output["result"]["validation_errors"], [])

    def test_live_hostname_and_plain_claim_reach_spoken_delivery_and_checkpoint(self):
        evidence = [fact("ADAS is available.")]
        evidence[0].update(provenance="live_web", source={"ref": "https://adas.example/car", "quote": evidence[0]["value"]})
        pack = {"evidence": evidence, "snapshot_id": "", "coverage": {}, "conflicts": []}
        with patch("server.knowledge.retrieve", return_value=pack), patch.object(rg.usage, "trace"):
            final = asyncio.run(rg.run_turn(self.did, {"session_id": "live-plain-session", "turn_id": "live-plain-turn", "question": "What driver assistance is listed?"}))
        expected = "According to adas.example, driver-assistance features is available."
        self.assertEqual(final["delivery"]["speech"], expected)
        self.assertEqual(final["result"]["plain_language_substitutions"], [("adas", "driver-assistance features")])
        saved = store.read_json(self.did, "runtime/live-plain-session.json")
        self.assertEqual(saved["delivery"]["speech"], expected)
        self.assertEqual(saved["delivery"]["result"]["facts"][0]["source"]["ref"], "https://adas.example/car")

    def test_real_demo_audience_wins_over_customer_profile(self):
        state = self.state()
        state["profile"]["audience"] = "expert"
        result = asyncio.run(rg.validate(state))["result"]
        self.assertIn("strut-type front suspension", result["answer"])
        store.update(self.did, lambda demo: demo["settings"].update(audience="expert"))
        state["profile"]["audience"] = "everyday"
        result = asyncio.run(rg.validate(state))["result"]
        self.assertEqual(result["answer"], self.text)
        self.assertEqual(result["plain_language_substitutions"], [])

    def test_faq_build_applies_same_reviewed_substitution(self):
        store.update(self.did, lambda demo: demo["settings"].update(faq_questions=1))
        response = {"answer": self.text, "fact_ids": ["F1"], "answered": True}
        with patch.object(faq, "doc_questions", return_value=[self.question]), patch.object(faq.qa, "answer", return_value=response):
            result = faq.run(self.did, lambda _: None)
        entry = result["entries"][0]
        self.assertIn("strut-type front suspension", entry["answer"])
        self.assertEqual(entry["fact_ids"], ["F1"])
        self.assertTrue(entry["plain_language_substitutions"])

    def test_real_mock_graph_saves_rendered_speech_and_substitutions(self):
        pack = {"evidence": self.evidence, "snapshot_id": "", "coverage": {}, "conflicts": []}
        with patch("server.knowledge.retrieve", return_value=pack), patch.object(rg.usage, "trace") as trace:
            final = asyncio.run(rg.run_turn(self.did, {"session_id": "saved-plain-session", "turn_id": "saved-plain-turn", "question": self.question}))
        self.assertIn("strut-type front suspension", final["delivery"]["speech"])
        self.assertTrue(final["result"]["plain_language_substitutions"])
        saved = store.read_json(self.did, "runtime/saved-plain-session.json")
        self.assertEqual(saved["delivery"]["speech"], final["delivery"]["speech"])
        self.assertTrue(saved["delivery"]["result"]["plain_language_substitutions"])
        graph_trace = next(call for call in trace.call_args_list if call.args[0] == "runtime-graph")
        self.assertTrue(json.loads(graph_trace.kwargs["response"])["plain_language_substitutions"])

    def test_exact_plain_language_prompt_present_and_storage_isolated(self):
        self.assertIn("PLAIN LANGUAGE. The listener is an everyday buyer. Use ordinary words.", rg.SYSTEM)
        self.assertIn("If the customer explicitly asks for the technical specification, you may give the exact term with its citation.", rg.SYSTEM)
        self.assertEqual(config.DATA_DIR, Path(_STORAGE.name).resolve())
        self.assertEqual(OUTBOUND, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
