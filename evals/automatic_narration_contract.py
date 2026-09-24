"""Ordinary source upload → Read prepares narration before the human checkpoint.

Only provider responses are canned. Actual extraction, Coach validation, Plan,
Author, graph, approval guards and measured publication accounting remain active.
The fixture passages are distinct uploaded evidence; no minimum/readiness bypass
or prewritten saved final script is used in these successful Read journeys.
"""
from __future__ import annotations

import atexit
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

_TEMP = tempfile.TemporaryDirectory(prefix="automatic-narration-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=str(Path(_TEMP.name) / "demos"),
                  DEMO_STUDIO_GRAPH_DB=str(Path(_TEMP.name) / "graph.sqlite"))
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
OUTBOUND = []
def blocked(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Automatic narration tests cannot use outbound sockets")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
atexit.register(lambda: print("OUTBOUND_ATTEMPTS", len(OUTBOUND), flush=True))

from fastapi.testclient import TestClient
from server import events, graph, orchestrator, schemas, store
from server.agents import align, author, bundle, coach, narration, voice
from server.app import app
from server.llm import mock
from narration_preparation_contract import fixture as equipment_fixture, OVERVIEW, CLOSING, record


class AutomaticNarration(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.did = self.client.post("/api/demos", json={"name": "Automatic narration fixture"}).json()["id"]
        store.update(self.did, lambda d: d["settings"].update(tts_provider="sarvam", sarvam_speaker="priya", voice_locked=True, language="en-IN", languages=[]))
        und, self.outline = equipment_fixture()
        self.texts = [fact["value"] for fact in und["facts"]]
        self.id_map = {fact["id"]: f"F{index + 1:03d}" for index, fact in enumerate(und["facts"])}
        for segment in self.outline["segments"]:
            segment["fact_ids"] = [self.id_map[fid] for fid in segment["fact_ids"]]
            if segment["role"] == "proof": segment["stop_id"] = segment["id"]
        for usp in self.outline["usps"]:
            usp["fact_ids"] = [self.id_map[fid] for fid in usp["fact_ids"]]
        response = self.client.post(f"/api/demos/{self.did}/sources", data={
            "role": "catalogue", "text_name": "equipment-handbook.txt", "text": "\n\n".join(self.texts)})
        self.assertEqual(response.status_code, 200, response.text)
        self.source_id = response.json()["added"][0]["id"]
        self.outcomes = ["complete"]
        self.no_facts = False
        self.calls = []
        self.original_fake = mock.fake
        self.fake_patch = patch.object(mock, "fake", side_effect=self.fake)
        self.fake_patch.start()
        self.original_coach = coach.mock_playbook
        self.coach_patch = patch.object(coach, "mock_playbook", side_effect=self.playbook)
        self.coach_patch.start()
        # Persona samples are outside narration preparation and never a runtime
        # recording. Skip this provider-facing preview in the graph fixture.
        self.sample_patch = patch.object(orchestrator, "_persona_sample")
        self.sample = self.sample_patch.start()
        self.voice_patch = patch.object(voice, "render_script", side_effect=AssertionError("Read must not record main narration"))
        self.voice = self.voice_patch.start()

    def tearDown(self):
        self.assertFalse(graph.is_running(self.did))
        self.assertEqual(OUTBOUND, [])
        self.voice_patch.stop(); self.sample_patch.stop(); self.coach_patch.stop(); self.fake_patch.stop()
        self.client.close()

    def fake(self, schema, content=None):
        if schema is schemas.FactsOut:
            out = mock.fake_dict(schema)
            out.update(product={"name": "Equipment handbook car", "category": "car", "summary": "Listed equipment", "audience": "Everyday drivers"}, unknowns=[],
                       facts=[] if self.no_facts else [{"kind": "feature", "claim": text.split(".")[0], "value": text,
                              "source": {"ref": self.source_id, "quote": text, "locator": f"Paragraph {index + 1}"},
                              "confidence": 1, "truth": "stated", "conditions": ""} for index, text in enumerate(self.texts)])
            return schema.model_validate(out)
        if schema is schemas.Plan:
            return schema.model_validate(self.outline)
        if schema is schemas.ScriptOut:
            self.calls.append(content)
            outcome = self.outcomes[min(len(self.calls) - 1, len(self.outcomes) - 1)]
            if outcome == "failure": raise RuntimeError("fixture reasoning provider unavailable")
            p, _ = json.JSONDecoder().raw_decode(content.split("\nPLAN: ", 1)[1])
            def line(text, fid=None):
                return {"text": text, "fact_ids": [fid] if fid else [], "visual": {"kind": "none", "ref": "", "focus": ""}, "step": "say"}
            segments = []
            for segment in p["segments"]:
                fids = segment["fact_ids"] if outcome == "complete" else segment["fact_ids"][:1]
                if segment["role"] == "intro":
                    lines = [line("The seat and steering controls can be adjusted separately before departure, so begin by looking at where each control sits around the driver.", fids[0] if fids else None)]
                elif segment["role"] == "outcome":
                    lines = [line("The equipment list and chosen trim provide the written reference for the conversation. Keep unresolved equipment questions attached to that list, and ask the dealer to confirm them before arranging a further visit or proceeding.", fids[0] if fids else None)]
                else:
                    lines = [line(self.texts[int(fid[1:]) - 1], fid) for fid in fids]
                    if not lines: lines = [line("Please review the available product documents.")]
                segments.append({**{key: segment[key] for key in ("id", "title", "role", "topic")}, "lines": lines, "deeper": [], "checkin": ""})
            return schema.model_validate({"overview": line(OVERVIEW, None if self.no_facts else "F014"), "closing": [line(CLOSING, None if self.no_facts else "F015")],
                                          "segments": segments, "intake_q1": "Welcome. What matters most?", "intake_q2": ""})
        return self.original_fake(schema, content)

    def playbook(self, und, entry):
        stops = [{"id": s["id"], "label": s["title"], "kind": "fundamental" if s["id"] == "seat" else "differentiator",
                 "why_here": "Inspect the documented controls in order.", "fact_ids": [] if self.no_facts else s["fact_ids"], "picture_ids": [], "must_cover": True, "gaps": []}
                for s in self.outline["segments"] if s["role"] == "proof"]
        return {"category": "car", "category_source": "library", "stops": stops,
                "usps": [{"id": f"usp-{index}", "name": name, "fact_ids": stops[index]["fact_ids"], "stop_id": stops[index]["id"]}
                         for index, name in enumerate(["Explore separate seating controls", "Inspect the loading arrangement", "Find the storage spaces"])] if not self.no_facts else [],
                "objections": [], "evidence_gaps": [], "notes": "Explicit provider fixture from the uploaded handbook."}

    def state(self):
        response = self.client.get(f"/api/demos/{self.did}")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def idle(self):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            state = self.state()
            if not state["running"] and state["demo"]["status"] in {"align", "ready", "error"}: return state
            time.sleep(.03)
        self.fail("Graph did not become idle")

    def read(self):
        response = self.client.post(f"/api/demos/{self.did}/read")
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertEqual(state["demo"]["status"], "align", state["demo"]["stages"])
        self.assertTrue(graph.is_waiting(self.did))
        return state

    def assert_review_boundary(self, state):
        self.assertFalse(state["demo"]["approvals"]["script"])
        self.assertFalse(state["demo"]["approvals"]["visuals"])
        self.assertFalse(state["demo"]["approvals"]["persona"])
        self.assertFalse(state["demo"]["approvals"]["ctas"])
        self.assertTrue(state["demo"]["approvals"]["faq"])
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))
        self.assertIsNone(store.read_json(self.did, "knowledge/published.json"))
        self.assertFalse(any("REVISION INSTRUCTION FROM THE USER" in content for content in self.calls))
        self.assertFalse(any(event["type"] == "phase_error" for event in events.since(self.did, 0)))
        preparation = state["cards"]["script"]["preparation"]
        if preparation["status"] in {"incomplete", "needs_sources"}:
            with patch.object(align.claude, "text", side_effect=AssertionError("Explain the known drafting state without a provider")) as wording:
                messages = [align.opening_message(self.did), align.card_prompt(self.did, "script"), align.card_prompt(self.did, "done")]
            wording.assert_not_called()
            expected = "MOCK preview" if preparation["mock_preview"] else "approved product evidence" if preparation["status"] == "needs_sources" else "draft is incomplete"
            self.assertTrue(all(expected in message for message in messages), messages)
            self.assertTrue(all("All six cards are approved" not in message for message in messages))

    def test_adequate_first_draft_reaches_align_ready_without_manual_preparation(self):
        state = self.read()
        self.assertEqual(len(self.calls), 1)
        status = state["cards"]["script"]["preparation"]
        self.assertEqual((status["status"], status["target_words"], status["words"], status["attempts"]), ("ready", 495, 495, 1))
        self.assertFalse(status["mock_preview"])
        self.assertEqual(state["demo"]["stages"]["author"]["status"], "done")
        script = store.read_json(self.did, "script.json")
        self.assertFalse(script["issues"], script["issues"])
        self.assertEqual(narration.preparation_report(script)["words"], 495)
        self.assertTrue(all(line["fact_ids"] and not line["unverified"] for segment in script["segments"] for line in segment["lines"]))
        self.assert_review_boundary(state)

    def test_two_short_drafts_get_one_automatic_completion_before_align(self):
        self.outcomes = ["short", "short", "complete"]
        state = self.read()
        self.assertEqual(len(self.calls), 3)
        self.assertIn("GLOBAL NARRATION TARGET", self.calls[1])
        self.assertEqual(state["cards"]["script"]["preparation"]["status"], "ready")
        self.assertEqual(state["cards"]["script"]["preparation"]["attempts"], 3)
        self.assertEqual(narration.preparation_report(store.read_json(self.did, "script.json"))["words"], 495)
        self.assert_review_boundary(state)

    def test_repeated_short_output_stops_with_incomplete_draft_after_three_calls(self):
        self.outcomes = ["short"]
        with patch.object(author.visuals, "align", side_effect=AssertionError("Do not audit pictures for an unfinished draft")) as audit:
            state = self.read()
        audit.assert_not_called()
        self.assertEqual(len(self.calls), 3)
        status = state["cards"]["script"]["preparation"]
        self.assertEqual(status["status"], "incomplete")
        self.assertEqual(status["missing_words"], status["target_words"] - status["words"])
        self.assertGreater(status["missing_words"], 0)
        self.assertTrue(status["reason"])
        self.assertEqual(state["demo"]["stages"]["author"]["status"], "pending")
        self.assertNotEqual(state["demo"]["stages"]["deck"]["status"], "done")
        self.assertEqual(store.read_json(self.did, "script.json")["visual_audit"]["method"], "pending_narration")
        self.assert_review_boundary(state)

    def test_no_available_facts_requests_sources_and_never_pads_to_the_target(self):
        self.no_facts = True
        state = self.read()
        status = state["cards"]["script"]["preparation"]
        self.assertEqual(status["status"], "needs_sources")
        self.assertLessEqual(len(self.calls), 2)
        self.assertLess(status["words"], status["target_words"])
        self.assertEqual(store.read_json(self.did, "understanding.json")["facts"], [])
        self.assert_review_boundary(state)

    def test_repair_provider_failure_stays_distinct_from_missing_source_evidence(self):
        self.outcomes = ["short", "failure"]
        state = self.read()
        status = state["cards"]["script"]["preparation"]
        self.assertEqual(status["status"], "incomplete")
        self.assertEqual(len(self.calls), 2)
        self.assertIn("fixture reasoning provider unavailable", json.dumps(status["errors"]))
        self.assertTrue(store.read_json(self.did, "understanding.json")["facts"])
        self.assert_review_boundary(state)

    def test_first_author_request_failure_blocks_empty_script_and_normal_retry_recovers(self):
        self.outcomes = ["failure"]
        response = self.client.post(f"/api/demos/{self.did}/read")
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertEqual(state["demo"]["stages"]["author"]["status"], "error")
        self.assertIsNone(store.read_json(self.did, "script.json"))
        self.assertEqual(state["cards"]["script"]["preparation"]["status"], "incomplete")
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.client.post(f"/api/demos/{self.did}/approve/script").status_code, 409)
        store.update(self.did, lambda demo: demo["approvals"].update({card: True for card in store.CARDS}))
        self.assertEqual(self.client.post(f"/api/demos/{self.did}/build").status_code, 409)
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))
        self.outcomes = ["complete"]
        response = self.client.post(f"/api/demos/{self.did}/revise", json={"stage": "author", "instruction": "Retry drafting the supported narration."})
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertEqual(state["demo"]["status"], "align")
        self.assertEqual(state["cards"]["script"]["preparation"]["status"], "ready")
        self.assertEqual(len(self.calls), 2)
        self.assertFalse(state["demo"]["approvals"]["script"])
        self.assertFalse(state["demo"]["approvals"]["visuals"])
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))

    def test_first_request_failure_on_revision_preserves_the_previous_valid_draft(self):
        self.read()
        before = store.path(self.did, "script.json").read_bytes()
        facts = store.path(self.did, "understanding.json").read_bytes()
        self.outcomes = ["failure"]
        response = self.client.post(f"/api/demos/{self.did}/revise", json={"stage": "author", "instruction": "Review the supported opening."})
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertEqual(state["demo"]["stages"]["author"]["status"], "error")
        self.assertEqual(store.path(self.did, "script.json").read_bytes(), before)
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), facts)
        self.assertEqual(state["cards"]["script"]["preparation"]["status"], "ready")
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))

    def test_incomplete_script_cannot_be_approved_directly(self):
        self.outcomes = ["short"]
        self.read()
        response = self.client.post(f"/api/demos/{self.did}/approve/script")
        self.assertEqual(response.status_code, 409, response.text)
        self.assertFalse(self.state()["demo"]["approvals"]["script"])

    def test_multi_action_and_chat_approval_cannot_bypass_incomplete_script(self):
        self.outcomes = ["short"]
        self.read()
        actions = [{"type": "approve", "card": card} for card in store.CARDS]
        notes = orchestrator.apply_actions(self.did, actions, [], "align")
        self.assertFalse(self.state()["demo"]["approvals"]["script"])
        self.assertTrue(any("script" in str(note).lower() for note in notes))
        reply = schemas.AlignOut(reply="Review actions returned.", actions=[schemas.AlignAction(**action) for action in actions])
        with patch.object(align, "respond", return_value=reply):
            response = self.client.post(f"/api/demos/{self.did}/align", data={"message": "Approve all cards", "context": "align"})
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertFalse(state["demo"]["approvals"]["script"])
        self.assertEqual(state["demo"]["status"], "align")

    def test_build_refuses_incomplete_draft_even_if_saved_approvals_are_forged(self):
        self.outcomes = ["short"]
        self.read()
        store.update(self.did, lambda d: d["approvals"].update({card: True for card in store.CARDS}))
        response = self.client.post(f"/api/demos/{self.did}/build")
        self.assertEqual(response.status_code, 409, response.text)
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))

    def test_generic_mock_placeholders_remain_an_incomplete_preview_without_padding(self):
        with patch.object(mock, "fake", self.original_fake), patch.object(coach, "mock_playbook", self.original_coach):
            state = self.read()
        status = state["cards"]["script"]["preparation"]
        self.assertEqual(status["status"], "incomplete")
        self.assertTrue(status["mock_preview"])
        self.assertLess(status["words"], status["target_words"])
        self.assertLessEqual(status["attempts"], 3)
        script = store.read_json(self.did, "script.json")
        self.assertTrue(all(line["text"] == "text (mock)" for segment in script["segments"] for line in segment["lines"]))
        self.assertEqual(self.client.post(f"/api/demos/{self.did}/approve/script").status_code, 409)
        self.assert_review_boundary(state)

    def manual_shortening(self, voiced):
        self.read()
        for card in store.CARDS:
            response = self.client.post(f"/api/demos/{self.did}/approve/{card}")
            self.assertEqual(response.status_code, 200, response.text)
        script = store.read_json(self.did, "script.json")
        record(self.did, script, prefix="reviewed-before-edit")
        script.update(voice_provider="sarvam", voice_name="priya")
        store.write_json(self.did, "script.json", script)
        script["voice_input_hash"] = voice.input_hash(self.did)
        store.write_json(self.did, "script.json", script)
        store.update(self.did, lambda demo: demo["stages"]["voice"].update(status="done"))
        bundle.build(self.did, lambda _: None)
        publication = (store.path(self.did, "bundle.json").read_bytes(), store.path(self.did, "knowledge/published.json").read_bytes(), store.load(self.did)["version"])
        audio = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in store.path(self.did, "audio").glob("*.wav")}
        facts = copy.deepcopy(store.read_json(self.did, "understanding.json")["facts"])
        if not voiced:
            for row in [script["runtime_overview"], *script["closing"], *[line for segment in script["segments"] for line in segment["lines"]]]:
                row["audio"] = None
            for key in ("voice_input_hash", "voice_provider", "voice_name"):
                script.pop(key, None)
            store.write_json(self.did, "script.json", script)
            store.update(self.did, lambda demo: demo["stages"]["voice"].update(status="pending"))
        previous_preparation = copy.deepcopy(script["narration_preparation"])
        line = next(segment for segment in script["segments"] if segment["id"] == "seat")["lines"][0]
        with patch.object(author.visuals, "align", side_effect=AssertionError("An incomplete manual edit must not spend on picture auditing")) as audit:
            response = self.client.patch(f"/api/demos/{self.did}/align/script", json={"lines": [{"id": line["id"], "text": "The front seat slides.", "fact_ids": line["fact_ids"]}]})
        self.assertEqual(response.status_code, 200, response.text)
        audit.assert_not_called()
        status = response.json()["cards"]["script"]["preparation"]
        self.assertEqual(status["status"], "incomplete")
        self.assertGreater(status["missing_words"], 0)
        self.assertEqual(status["attempts"], previous_preparation["attempts"])
        self.assertEqual(status["errors"], previous_preparation["errors"])
        saved = store.read_json(self.did, "script.json")
        self.assertEqual(saved["narration_preparation"]["status"], "incomplete")
        self.assertEqual(saved["visual_audit"]["method"], "pending_narration")
        self.assertEqual(next(segment for segment in saved["segments"] if segment["id"] == "seat")["lines"][0]["text"], "The front seat slides.")
        self.assertEqual(self.client.post(f"/api/demos/{self.did}/approve/script").status_code, 409)
        approvals = self.state()["demo"]["approvals"]
        self.assertFalse(approvals["script"])
        self.assertFalse(approvals["visuals"])
        self.assertTrue(all(approved for card, approved in approvals.items() if card not in {"script", "visuals"}))
        # A stale approval flag cannot bypass the preparation boundary either.
        store.update(self.did, lambda demo: demo["approvals"].update(script=True, visuals=True))
        self.assertEqual(self.client.post(f"/api/demos/{self.did}/build").status_code, 409)
        self.voice.assert_not_called()
        self.assertEqual(len(self.calls), 1)
        self.assertEqual((store.path(self.did, "bundle.json").read_bytes(), store.path(self.did, "knowledge/published.json").read_bytes(), store.load(self.did)["version"]), publication)
        self.assertTrue(all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in audio.items()))
        self.assertEqual(store.read_json(self.did, "understanding.json")["facts"], facts)

    def test_manual_shortening_of_prepared_unvoiced_script_stays_incomplete(self):
        self.manual_shortening(voiced=False)

    def test_manual_shortening_of_voiced_script_cannot_hide_behind_stale_audio(self):
        self.manual_shortening(voiced=True)

    def test_adequate_manual_edit_remains_ready_and_can_be_reviewed(self):
        self.read()
        script = store.read_json(self.did, "script.json")
        line = next(segment for segment in script["segments"] if segment["id"] == "seat")["lines"][0]
        edited = line["text"].replace("backwards and forwards", "forwards and backwards")
        self.assertNotEqual(edited, line["text"])
        with patch.object(author.visuals, "align", wraps=author.visuals.align) as audit:
            response = self.client.patch(f"/api/demos/{self.did}/align/script", json={"lines": [{"id": line["id"], "text": edited, "fact_ids": line["fact_ids"]}]})
        self.assertEqual(response.status_code, 200, response.text)
        audit.assert_called_once()
        status = response.json()["cards"]["script"]["preparation"]
        self.assertEqual((status["status"], status["words"]), ("ready", 495))
        self.assertEqual(status["attempts"], script["narration_preparation"]["attempts"])
        self.assertEqual(self.client.post(f"/api/demos/{self.did}/approve/script").status_code, 200)
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))

    def test_legacy_build_prepares_automatically_and_returns_for_fresh_review(self):
        self.read()
        for filename in ("plan.json", "script.json"):
            artifact = store.read_json(self.did, filename)
            artifact.pop("narration_preparation", None)
            if filename == "script.json":
                # An actual short legacy draft, not a sufficient draft whose
                # marker alone is missing: retain each original stop's first batch.
                artifact["segments"] = [segment for segment in artifact["segments"]
                    if not segment.get("budget_source_id") or segment["id"] == segment["budget_source_id"]]
            store.write_json(self.did, filename, artifact)
        store.update(self.did, lambda demo: demo["approvals"].update({card: True for card in store.CARDS}))
        self.assertEqual(narration.preparation_status(self.did)["status"], "needs_preparation")
        facts = store.path(self.did, "understanding.json").read_bytes()
        old_plan = store.read_json(self.did, "plan.json")
        self.calls.clear()
        response = self.client.post(f"/api/demos/{self.did}/build")
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertEqual(state["demo"]["status"], "align")
        self.assertEqual(state["cards"]["script"]["preparation"]["status"], "ready")
        self.assertEqual(len(self.calls), 1)
        self.assertFalse(state["demo"]["approvals"]["script"])
        self.assertFalse(state["demo"]["approvals"]["visuals"])
        self.assertTrue(all(value for key, value in state["demo"]["approvals"].items() if key not in {"script", "visuals"}))
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), facts)
        new_plan = store.read_json(self.did, "plan.json")
        for field in ("voice", "ctas"):
            self.assertEqual(new_plan[field], old_plan[field])
        self.voice.assert_not_called()
        self.assertIsNone(store.read_json(self.did, "bundle.json"))

    def test_short_recording_triggers_one_draft_preparation_and_preserves_old_publication(self):
        self.read()
        script = store.read_json(self.did, "script.json")
        record(self.did, script, prefix="old-publication")
        script.update(voice_provider="sarvam", voice_name="priya")
        store.write_json(self.did, "script.json", script)
        script["voice_input_hash"] = voice.input_hash(self.did)
        store.write_json(self.did, "script.json", script)
        store.update(self.did, lambda demo: demo["approvals"].update({card: True for card in store.CARDS}))
        bundle.build(self.did, lambda _: None)
        publication = (store.path(self.did, "bundle.json").read_bytes(), store.path(self.did, "knowledge/published.json").read_bytes(), store.load(self.did)["version"])
        old_audio = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in store.path(self.did, "audio").glob("*.wav")}
        facts = store.path(self.did, "understanding.json").read_bytes()
        for row in [script.get("runtime_overview"), *script.get("closing", []), *[line for segment in script["segments"] for line in segment["lines"]]]:
            if row: row["audio"] = None
        script.pop("voice_input_hash", None)
        store.write_json(self.did, "script.json", script)
        store.update(self.did, lambda demo: demo["stages"]["voice"].update(status="pending", error=None))
        self.assertEqual(narration.preparation_status(self.did)["status"], "ready")
        def short_voice(did, emit):
            candidate = store.read_json(did, "script.json")
            record(did, candidate, wps=495 / 128.3, prefix="new-short-recording")
            candidate.update(voice_provider="sarvam", voice_name="priya")
            store.write_json(did, "script.json", candidate)
            candidate["voice_input_hash"] = voice.input_hash(did)
            store.write_json(did, "script.json", candidate)
            measured = narration.preparation_report(candidate, demo_id=did)
            self.assertAlmostEqual(measured["seconds"], 128.3, delta=.1)
            return candidate
        self.voice.side_effect = short_voice
        self.calls.clear()
        response = self.client.post(f"/api/demos/{self.did}/build")
        self.assertEqual(response.status_code, 200, response.text)
        state = self.idle()
        self.assertEqual(state["demo"]["status"], "align", state["demo"]["stages"])
        self.assertEqual(self.voice.call_count, 1)
        self.assertGreaterEqual(len(self.calls), 1)
        self.assertLessEqual(len(self.calls), 3)
        self.assertFalse(state["demo"]["approvals"]["script"])
        self.assertFalse(state["demo"]["approvals"]["visuals"])
        self.assertEqual((store.path(self.did, "bundle.json").read_bytes(), store.path(self.did, "knowledge/published.json").read_bytes(), store.load(self.did)["version"]), publication)
        self.assertTrue(all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in old_audio.items()))
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), facts)
        self.assertFalse(any(event["type"] == "phase_error" for event in events.since(self.did, 0)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
