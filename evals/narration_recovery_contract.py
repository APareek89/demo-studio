"""Measured narration failures return to human review without replacing publication.

These are workflow/recovery fixtures, not evidence that a model can write a long
enough draft. narration_preparation_contract exercises actual Plan/Author
preparation separately. All recordings here are synthetic WAVs in temporary
storage; the production duration counter and publication gate remain active.
"""
from __future__ import annotations

import atexit
import copy
import hashlib
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

_STORAGE = tempfile.TemporaryDirectory(prefix="narration-recovery-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=str(Path(_STORAGE.name) / "demos"),
                  DEMO_STUDIO_GRAPH_DB=str(Path(_STORAGE.name) / "graph.sqlite"))
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parent)]
OUTBOUND = []


def blocked(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Narration recovery must not open outbound sockets")


socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
atexit.register(lambda: print("OUTBOUND_ATTEMPTS", len(OUTBOUND), flush=True))

from fastapi.testclient import TestClient
from server import config, events, graph, orchestrator, readiness, store
from server.agents import author, bundle, deck, faq, narration, plan, voice
from server.app import app
from minimum_narration_contract import rich_fixture, write_wav


class NarrationRecovery(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.did = store.new_demo("Disposable narration recovery")["id"]
        store.update(self.did, lambda demo: demo["settings"].update(tts_provider="sarvam", sarvam_speaker="priya", voice_locked=True))
        self.fixture = rich_fixture(self.did, recorded=True)
        self.fixture["script"].update(voice_provider="sarvam", voice_name="priya")
        # The duration helper omits unused outline fields. Real Align/API calls
        # also need the normal per-stop visual reference list.
        for segment in self.fixture["plan"]["segments"]:
            segment["visual_refs"] = []
        store.write_json(self.did, "plan.json", self.fixture["plan"])
        self.published = bundle.build(self.did, lambda _: None)
        self.publication_before = self.publication()
        self.original_audio = self.audio_hashes()
        self.registry_before = store.path(self.did, "understanding.json").read_bytes()
        store.write_json(self.did, "faq.json", {"entries": [], "question_policy": faq.QUESTION_POLICY})
        self.stage_script(self.fixture["script"])

    def tearDown(self):
        self.assertFalse(graph.is_running(self.did))
        self.assertEqual(OUTBOUND, [])
        self.client.close()

    def publication(self):
        return (store.path(self.did, "bundle.json").read_bytes(),
                store.path(self.did, "knowledge/published.json").read_bytes(),
                store.load(self.did)["version"])

    def audio_hashes(self):
        return {str(path.relative_to(store.demo_dir(self.did))): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in store.path(self.did, "audio").glob("*.wav")}

    def stage_script(self, script):
        """Install a reviewed candidate; completed recording is reused by actual Build."""
        script = copy.deepcopy(script)
        store.write_json(self.did, "script.json", script)
        script["voice_input_hash"] = voice.input_hash(self.did)
        store.write_json(self.did, "script.json", script)
        def ready(demo):
            demo["status"] = "align"
            demo["approvals"].update({card: True for card in store.CARDS})
            for stage in ("author", "deck", "faq", "voice"):
                demo["stages"][stage].update(status="done", error=None)
        store.update(self.did, ready)
        return script

    def short_candidate(self):
        # New candidate paths keep the old publication's clips byte-identical.
        script = copy.deepcopy(self.fixture["script"])
        rows = [(script["runtime_overview"], 6.0)]
        rows += [(line, 12.5 if segment["role"] == "proof" else 8.0)
                 for segment in script["segments"] for line in segment["lines"]]
        rows += [(script["closing"][0], 6.3)]
        for index, (line, duration) in enumerate(rows):
            line["audio"] = f"audio/candidate-{index}.wav"
            write_wav(store.path(self.did, line["audio"]), duration)
        candidate = self.stage_script(script)
        self.assertEqual(narration.default_route(candidate, demo_id=self.did)[1]["seconds"], 128.3)
        return candidate

    def wait_idle(self):
        deadline = time.monotonic() + 15
        while graph.is_running(self.did) and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertFalse(graph.is_running(self.did), "Graph did not finish the bounded fixture")
        return store.load(self.did)

    def build(self):
        response = self.client.post(f"/api/demos/{self.did}/build")
        self.assertEqual(response.status_code, 200, response.text)
        return self.wait_idle()

    def assert_review_pause(self, since, script_before, audio_before):
        saved = store.load(self.did)
        self.assertEqual(saved["status"], "align", saved["stages"])
        self.assertTrue(graph.is_waiting(self.did))
        self.assertEqual(saved["stages"]["bundle"]["status"], "pending")
        self.assertFalse(saved["stages"]["bundle"].get("error"))
        self.assertFalse(saved["approvals"]["script"])
        self.assertTrue(all(value for card, value in saved["approvals"].items() if card != "script"))
        self.assertEqual(store.path(self.did, "script.json").read_bytes(), script_before)
        self.assertEqual(self.audio_hashes(), audio_before)
        self.assertEqual(self.publication(), self.publication_before)
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), self.registry_before)
        self.assertFalse(any(event["type"] == "phase_error" for event in events.since(self.did, since)))
        self.assertFalse(any(event["type"] == "phase_done" and event.get("phase") == "build"
                             for event in events.since(self.did, since)))

    def test_measured_128_seconds_automatically_prepares_a_draft_without_recording(self):
        self.short_candidate()
        audio = self.audio_hashes()
        since = events.latest_seq(self.did)
        def prepare(did, emit, instruction=""):
            self.assertEqual(instruction, narration.PREPARATION_INSTRUCTION)
            draft = store.read_json(did, "script.json")
            for field in ("voice_input_hash", "voice_provider", "voice_name"):
                draft.pop(field, None)
            for line in [draft["runtime_overview"], *draft["closing"], *[line for segment in draft["segments"] for line in segment["lines"]]]:
                line["audio"] = None
            draft["narration_preparation"] = {"version": 1, "status": "incomplete", "target_words": 495, "attempts": 1}
            store.write_json(did, "script.json", draft)
            return draft
        with patch.object(author, "run", side_effect=prepare) as author_run, \
                patch.object(voice, "render_script", side_effect=AssertionError("Reuse completed recordings")):
            saved = self.build()
        self.assertEqual(author_run.call_count, 1)
        self.assertEqual(saved["status"], "align")
        self.assertTrue(graph.is_waiting(self.did))
        self.assertFalse(saved["approvals"]["script"])
        self.assertFalse(saved["approvals"]["visuals"])
        self.assertEqual(narration.preparation_status(self.did)["status"], "incomplete")
        self.assertEqual(self.audio_hashes(), audio)
        self.assertEqual(self.publication(), self.publication_before)
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), self.registry_before)
        self.assertFalse(any(event["type"] == "phase_error" for event in events.since(self.did, since)))

    def test_missing_recording_returns_to_review_and_keeps_existing_clips(self):
        candidate = self.stage_script(self.fixture["script"])
        # Copy first: a draft-only missing path must not delete a published clip.
        candidate["runtime_overview"]["audio"] = "audio/missing-candidate.wav"
        self.stage_script(candidate)
        before, audio = store.path(self.did, "script.json").read_bytes(), self.audio_hashes()
        since = events.latest_seq(self.did)
        # Voice is retried by the requested Build. If it still returns a missing
        # clip, publication must pause without using Author to rewrite the text.
        with patch.object(voice, "render_script", side_effect=lambda did, emit: store.read_json(did, "script.json")) as render, \
                patch.object(author, "run", side_effect=AssertionError("Missing audio must not rewrite the script")):
            self.build()
        render.assert_called_once()
        self.assert_review_pause(since, before, audio)
        self.assertTrue(any("missing or unreadable" in row.get("text", "")
                            for row in store.read_json(self.did, "conversation.json")))

    def test_corrupt_recording_returns_to_review_without_discarding_text(self):
        candidate = copy.deepcopy(self.fixture["script"])
        candidate["runtime_overview"]["audio"] = "audio/corrupt-candidate.wav"
        store.path(self.did, "audio/corrupt-candidate.wav").write_bytes(b"not a WAV")
        self.stage_script(candidate)
        before, audio = store.path(self.did, "script.json").read_bytes(), self.audio_hashes()
        since = events.latest_seq(self.did)
        with patch.object(voice, "render_script", side_effect=lambda did, emit: store.read_json(did, "script.json")) as render, \
                patch.object(author, "run", side_effect=AssertionError("Corrupt audio must not rewrite the script")):
            self.build()
        render.assert_called_once()
        self.assert_review_pause(since, before, audio)

    def test_repeated_build_requires_reapproval_and_keeps_the_review_checkpoint(self):
        self.short_candidate()
        self.build()
        response = self.client.post(f"/api/demos/{self.did}/build")
        self.assertEqual(response.status_code, 409)
        self.assertIn(narration.preparation_status(self.did)["reason"], response.text)
        self.assertFalse(store.load(self.did)["approvals"]["script"])
        self.assertTrue(graph.is_waiting(self.did))
        self.assertEqual(self.publication(), self.publication_before)

    def test_explicitly_restored_recordings_and_reapproval_can_publish(self):
        self.short_candidate()
        self.build()
        # The reviewer restores the previous sufficiently recorded draft. This
        # tests recovery only; generation and speech-rate calibration are separate.
        self.stage_script(self.fixture["script"])
        store.update(self.did, lambda demo: demo["approvals"].update(script=False))
        response = self.client.post(f"/api/demos/{self.did}/approve/script")
        self.assertEqual(response.status_code, 200, response.text)
        saved = self.build()
        self.assertEqual(saved["status"], "ready")
        published = store.read_json(self.did, "bundle.json")
        self.assertEqual(published["version"], self.published["version"] + 1)
        self.assertTrue(published["runtime"]["narration_minimum"]["sufficient"])
        self.assertTrue(published["runtime"]["narration_minimum"]["measured"])
        self.assertTrue(all(self.audio_hashes()[path] == digest for path, digest in self.original_audio.items()))

    def test_provider_failure_remains_an_error_instead_of_a_length_review_pause(self):
        store.update(self.did, lambda demo: demo["stages"]["voice"].update(status="pending"))
        since = events.latest_seq(self.did)
        with patch.object(voice, "render_script", side_effect=RuntimeError("Fixture provider unavailable")):
            saved = self.build()
        self.assertEqual(saved["status"], "error")
        self.assertEqual(saved["stages"]["voice"]["status"], "error")
        self.assertTrue(any(event["type"] == "phase_error" for event in events.since(self.did, since)))
        self.assertEqual(self.publication(), self.publication_before)

    def test_explicit_plan_author_preparation_returns_to_review_without_auto_build(self):
        self.short_candidate()
        original_plan = store.read_json(self.did, "plan.json")
        original_settings = copy.deepcopy(store.load(self.did)["settings"])
        stages = []
        def prepare(did, emit, instruction=""):
            stages.append(("plan", instruction))
            draft = copy.deepcopy(original_plan)
            draft["notes"] = "Fixture: more supported detail needs review."
            store.write_json(did, "plan.json", draft)
            return draft
        def write(did, emit, instruction=""):
            stages.append(("author", instruction))
            draft = store.read_json(did, "script.json")
            draft["segments"][0]["lines"][0]["text"] += " The adjustment controls sit beside the cushion."
            for field in ("voice_input_hash", "voice_provider", "voice_name"):
                draft.pop(field, None)
            for line in [draft["runtime_overview"], *draft["closing"], *[line for segment in draft["segments"] for line in segment["lines"]]]:
                line["audio"] = None
            draft["narration_preparation"] = {"version": 1, "status": "incomplete", "target_words": 495, "attempts": 1}
            store.write_json(did, "script.json", draft)
            return draft
        def design(did, emit, instruction=""):
            stages.append(("deck", instruction))
            return store.read_json(did, "deck.json")
        with patch.object(plan, "run", side_effect=prepare), patch.object(author, "run", side_effect=write), \
                patch.object(deck, "build", side_effect=design), \
                patch.object(orchestrator, "_persona_sample", side_effect=AssertionError("Preparation must not regenerate the persona sample")) as sample, \
                patch.object(voice, "render_script", side_effect=AssertionError("Preparation must return to review")):
            response = self.client.post(f"/api/demos/{self.did}/revise", json={
                "stage": "plan", "instruction": narration.PREPARATION_INSTRUCTION})
            self.assertEqual(response.status_code, 200, response.text)
            saved = self.wait_idle()
            sample.assert_not_called()
        self.assertEqual([stage for stage, _ in stages], ["plan", "author"])
        self.assertEqual(saved["stages"]["author"]["status"], "pending")
        self.assertEqual(stages[0][1], narration.PREPARATION_INSTRUCTION)
        self.assertEqual(saved["status"], "align")
        self.assertTrue(graph.is_waiting(self.did))
        self.assertFalse(saved["approvals"]["script"])
        self.assertFalse(saved["approvals"]["visuals"])
        self.assertTrue(all(saved["approvals"][card] for card in ("facts", "persona", "ctas", "faq")))
        self.assertEqual(saved["settings"], original_settings)
        revised_plan = store.read_json(self.did, "plan.json")
        self.assertEqual(revised_plan["voice"], original_plan["voice"])
        self.assertEqual(revised_plan["ctas"], original_plan["ctas"])
        self.assertEqual(store.path(self.did, "understanding.json").read_bytes(), self.registry_before)
        self.assertEqual(self.publication(), self.publication_before)

    def preparation_request(self, query="", **body):
        return self.client.post(f"/api/demos/{self.did}/revise{query}", json={
            "stage": "plan", "instruction": narration.PREPARATION_INSTRUCTION, **body})

    def test_failed_real_readiness_blocks_canonical_preparation_before_graph_starts(self):
        failed = {"stale": False, "mock": False, "checks": {"reasoning": {"ready": False}}}
        before = store.path(self.did, "demo.json").read_bytes()
        with patch.object(config, "MOCK_LLM", False), patch.object(readiness, "status", return_value=failed), \
                patch.object(readiness, "probe", side_effect=AssertionError("Never probe implicitly")) as probe, \
                patch.object(graph, "start_revise") as start:
            for query in ("", "?override_readiness=false"):
                response = self.preparation_request(query)
                self.assertEqual(response.status_code, 409, response.text)
                self.assertIn("reasoning has not passed", response.text)
            start.assert_not_called()
            probe.assert_not_called()
        self.assertEqual(store.path(self.did, "demo.json").read_bytes(), before)

    def test_fresh_reasoning_readiness_allows_preparation_without_a_speech_probe(self):
        ready = {"stale": False, "mock": False, "checks": {
            "reasoning": {"ready": True}, "streaming_speech": {"ready": False}}}
        with patch.object(config, "MOCK_LLM", False), patch.object(readiness, "status", return_value=ready) as status, \
                patch.object(readiness, "probe", side_effect=AssertionError("No paid readiness call")) as probe, \
                patch.object(graph, "start_revise") as start:
            response = self.preparation_request()
            self.assertEqual(response.status_code, 200, response.text)
            status.assert_called_once_with(self.did)
            start.assert_called_once_with(self.did, "plan", narration.PREPARATION_INSTRUCTION, False)
            probe.assert_not_called()

    def test_explicit_preparation_readiness_override_is_audited_and_allows_dispatch(self):
        with patch.object(config, "MOCK_LLM", False), \
                patch.object(readiness, "status", side_effect=AssertionError("Override should not probe")) as status, \
                patch.object(readiness, "probe", side_effect=AssertionError("No provider calls")) as probe, \
                patch.object(graph, "start_revise") as start:
            response = self.preparation_request("?override_readiness=true")
            self.assertEqual(response.status_code, 200, response.text)
            start.assert_called_once_with(self.did, "plan", narration.PREPARATION_INSTRUCTION, False)
            status.assert_not_called()
            probe.assert_not_called()
        audit = store.path(self.did, "RUN.md").read_text()
        self.assertIn("Provider readiness override", audit)
        self.assertIn("Operator explicitly continued", audit)

    def test_mock_preparation_bypasses_readiness_without_probing_or_calling_providers(self):
        with patch.object(config, "MOCK_LLM", True), \
                patch.object(readiness, "status", side_effect=AssertionError("Mock fixtures need no real readiness")) as status, \
                patch.object(readiness, "probe", side_effect=AssertionError("No provider calls")) as probe, \
                patch.object(graph, "start_revise") as start:
            response = self.preparation_request()
            self.assertEqual(response.status_code, 200, response.text)
            start.assert_called_once_with(self.did, "plan", narration.PREPARATION_INSTRUCTION, False)
            status.assert_not_called()
            probe.assert_not_called()

    def test_author_revision_gate_preserves_the_unrelated_plan_revision_route(self):
        failed = {"stale": False, "mock": False, "checks": {"reasoning": {"ready": False}}}
        with patch.object(config, "MOCK_LLM", False), \
                patch.object(readiness, "status", return_value=failed) as status, \
                patch.object(readiness, "probe", side_effect=AssertionError("No implicit provider probe")) as probe, \
                patch.object(graph, "start_revise") as start:
            self.assertEqual(self.preparation_request(stage="author").status_code, 409)
            self.assertEqual(self.preparation_request(instruction="Review the current plan.").status_code, 200)
            status.assert_called_once_with(self.did)
            start.assert_called_once_with(self.did, "plan", "Review the current plan.", False)
            probe.assert_not_called()

    def unrecorded_preparation(self):
        draft = copy.deepcopy(self.fixture["script"])
        for line in [draft["runtime_overview"], *draft["closing"],
                     *[line for segment in draft["segments"] for line in segment["lines"]]]:
            line["audio"] = None
        outline = copy.deepcopy(self.fixture["plan"])
        outline["narration_preparation"] = {"version": 1, "target_words": 495}
        store.write_json(self.did, "plan.json", outline)
        store.write_json(self.did, "script.json", draft)
        # Independent expected count: every distinct original main passage,
        # plus the separate opening and closing, rather than the shortened route.
        words = sum(author.words(line["text"]) for line in [draft["runtime_overview"], *draft["closing"],
                    *[line for segment in draft["segments"] for line in segment["lines"]]])
        return draft, words

    def test_align_reports_incomplete_preparation_even_when_old_estimate_reaches_three_minutes(self):
        _, expected = self.unrecorded_preparation()
        minimum = self.client.get(f"/api/demos/{self.did}").json()["cards"]["script"]["narration_minimum"]
        self.assertGreaterEqual(minimum["seconds"], 180)
        self.assertEqual(minimum["basis"], "estimated")
        self.assertTrue(minimum["sufficient"])
        self.assertLess(expected, 495)
        self.assertEqual(minimum["preparation"], {"target_words": 495, "words": expected, "sufficient": False})
        self.assertGreater(expected, narration.default_route(store.read_json(self.did, "script.json"))[1]["words"])

    def test_align_preparation_excludes_duplicate_held_rejected_and_deeper_lines(self):
        draft, expected = self.unrecorded_preparation()
        repeated = copy.deepcopy(draft["segments"][0])
        repeated["id"] = "duplicate-stop"
        draft["segments"].append(repeated)
        held = copy.deepcopy(repeated)
        held["id"] = "held-stop"
        held["lines"][0].update(text="Held draft content must never make the reviewed narration appear complete.", unverified=True)
        draft["segments"].append(held)
        draft["segments"][0]["deeper"] = [{"id": "deeper-only", "text": "Unspoken detail " * 300, "fact_ids": ["F01"]}]
        rejected = draft["segments"][1]["lines"][0]
        expected -= author.words(rejected["text"])
        und = store.read_json(self.did, "understanding.json")
        for fact in und["facts"]:
            if fact["id"] in rejected["fact_ids"]:
                fact["approved"] = False
        store.write_json(self.did, "understanding.json", und)
        store.write_json(self.did, "script.json", draft)
        preparation = self.client.get(f"/api/demos/{self.did}").json()["cards"]["script"]["narration_minimum"]["preparation"]
        self.assertEqual(preparation, {"target_words": 495, "words": expected, "sufficient": False})

    def test_align_counts_reachable_tail_continuations_but_not_a_second_features_group(self):
        draft, expected = self.unrecorded_preparation()
        features = next(segment for segment in draft["segments"] if segment["role"] == "features")
        continued = copy.deepcopy(features)
        continued.update(id="features-continuation", budget_source_id=features["id"])
        continued["lines"][0].update(id="feature-continued-line", text="The handbook labels the cabin controls individually beside their own diagrams.")
        expected += author.words(continued["lines"][0]["text"])
        unreachable = copy.deepcopy(features)
        unreachable.update(id="other-features-group")
        unreachable["lines"][0].update(id="other-features-line", text="A different feature passage belongs to another group that this route never selects.")
        draft["segments"].extend([continued, unreachable])
        store.write_json(self.did, "script.json", draft)
        preparation = self.client.get(f"/api/demos/{self.did}").json()["cards"]["script"]["narration_minimum"]["preparation"]
        self.assertEqual(preparation, {"target_words": 495, "words": expected, "sufficient": False})

    def selected_short_alternate(self):
        # Text is an explicit workflow fixture; synthetic timings stand in for
        # an independently recorded selected language, not translation quality.
        alternate = self.short_candidate()
        store.write_json(self.did, "script.hi-IN.json", alternate)
        store.update(self.did, lambda demo: demo["settings"].update(language="en-IN", languages=["hi-IN"]))
        return self.stage_script(self.fixture["script"])

    def test_align_shows_the_selected_short_language_when_current_main_recording_passes(self):
        main = self.selected_short_alternate()
        self.assertTrue(narration.default_route(main, demo_id=self.did)[1]["sufficient"])
        minimum = self.client.get(f"/api/demos/{self.did}").json()["cards"]["script"]["narration_minimum"]
        self.assertEqual(minimum["language"], "hi-IN")
        self.assertEqual(minimum["seconds"], 128.3)
        self.assertTrue(minimum["measured"])
        self.assertFalse(minimum["sufficient"])

    def test_align_ignores_a_stored_alternate_that_is_no_longer_selected(self):
        self.selected_short_alternate()
        store.update(self.did, lambda demo: demo["settings"].update(languages=[]))
        self.stage_script(self.fixture["script"])
        minimum = self.client.get(f"/api/demos/{self.did}").json()["cards"]["script"]["narration_minimum"]
        self.assertTrue(minimum["sufficient"])
        self.assertTrue(minimum["measured"])
        self.assertNotIn("language", minimum)
        self.assertTrue(store.path(self.did, "script.hi-IN.json").is_file())

    def test_align_ignores_old_alternate_audio_after_a_new_unrecorded_draft(self):
        main = self.selected_short_alternate()
        previous_hash = main["voice_input_hash"]
        main["segments"][0]["lines"][0]["text"] += " The control is shown beside the cushion."
        main["segments"][0]["lines"][0]["audio"] = None
        for stored_hash in (previous_hash, None):
            with self.subTest(stale_hash=bool(stored_hash)):
                main["voice_input_hash"] = stored_hash
                store.write_json(self.did, "script.json", main)
                self.assertNotEqual(stored_hash, voice.input_hash(self.did))
                minimum = self.client.get(f"/api/demos/{self.did}").json()["cards"]["script"]["narration_minimum"]
                self.assertNotIn("language", minimum)
                self.assertEqual(minimum["basis"], "mixed")
                self.assertNotEqual(minimum["seconds"], 128.3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
