"""Publication shares ownership with live FAQ learning; all data and audio are temporary."""
from __future__ import annotations

import concurrent.futures
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

_STORAGE = tempfile.TemporaryDirectory(prefix="publication-approval-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=_STORAGE.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_STORAGE.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import graph, store
from server.agents import bundle, faq, voice
from evals.minimum_narration_contract import rich_fixture


class PublicationApproval(unittest.TestCase):
    def setUp(self):
        self.blockers = [patch.object(socket.socket, "connect", side_effect=AssertionError("outbound forbidden")),
                         patch.object(socket, "create_connection", side_effect=AssertionError("outbound forbidden"))]
        for blocker in self.blockers:
            blocker.start()
        self.did = store.new_demo("Publication approval fixture")["id"]
        self.fixture = rich_fixture(self.did, recorded=True)
        self.old = bundle.build(self.did, lambda _: None)
        self.pin = self.old["knowledge_snapshot_id"]
        self.before = self.saved_publication()

    def tearDown(self):
        for blocker in reversed(self.blockers):
            blocker.stop()

    def saved_publication(self):
        return (store.path(self.did, "bundle.json").read_bytes(),
                store.path(self.did, "knowledge/published.json").read_bytes(), store.load(self.did)["version"])

    def learn(self):
        fact = self.fixture["understanding"]["facts"][1]
        result = {"answered": True, "answer": fact["value"], "fact_ids": [fact["id"]], "facts": [fact]}
        return faq.cache_answer(self.did, "How does the driver seat adjust?", result, snapshot_id=self.pin,
                                registry_hash=faq._registry_hash(self.did, snapshot_id=self.pin))

    def test_runtime_learning_during_voice_returns_to_align(self):
        self.assertIsNotNone(self.learn())
        self.assertFalse(store.load(self.did)["approvals"]["faq"])
        self.assertEqual(graph.after_voice({"demo_id": self.did, "entry": "build"}), "align_enter")
        self.assertEqual(self.saved_publication(), self.before)

    def test_last_moment_invalidation_preserves_every_publication_file(self):
        self.assertEqual(graph.after_voice({"demo_id": self.did}), "bundle")
        self.learn()
        with self.assertRaises(bundle.ApprovalRequired):
            bundle.build(self.did, lambda _: None)
        self.assertEqual(self.saved_publication(), self.before)

    def test_bundle_node_treats_review_pause_as_pending_not_failed(self):
        self.learn()
        command = graph.bundle({"demo_id": self.did, "entry": "build"})
        self.assertEqual(command.goto, "align_enter")
        stage = store.load(self.did)["stages"]["bundle"]
        self.assertEqual(stage["status"], "pending")
        self.assertFalse(stage.get("error"))
        self.assertEqual(self.saved_publication(), self.before)

    def test_all_six_cards_are_required_at_final_boundary(self):
        for card in store.CARDS:
            store.update(self.did, lambda demo: demo["approvals"].update({key: key != card for key in store.CARDS}))
            with self.assertRaises(bundle.ApprovalRequired, msg=card):
                bundle.build(self.did, lambda _: None)
            self.assertEqual(self.saved_publication(), self.before)

    def test_live_writer_waits_until_approved_bundle_has_been_published(self):
        attempted, finished = threading.Event(), threading.Event()
        def writer():
            attempted.set()
            try:
                return self.learn()
            finally:
                finished.set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as workers:
            pending = []
            def emit(message):
                if message.startswith("Assembling"):
                    pending.append(workers.submit(writer))
                    self.assertTrue(attempted.wait(1))
                    self.assertFalse(finished.wait(.05), "FAQ writer crossed the publication ownership boundary")
            published = bundle.build(self.did, emit)
            self.assertIsNotNone(pending[0].result(timeout=2))
        self.assertEqual(published["faq"], [])
        self.assertEqual(store.read_json(self.did, "bundle.json")["faq"], [])
        self.assertEqual(published["version"], self.old["version"] + 1)
        self.assertEqual(len(faq.current_entries(store.read_json(self.did, "faq.json"))), 1)
        self.assertFalse(store.load(self.did)["approvals"]["faq"])

    def test_approved_bundle_progress_can_reenter_the_metadata_lock(self):
        # Production emit_for persists stage progress with store.update while the
        # bundle owns the same demo lock; the ownership boundary is reentrant.
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as workers:
            future = workers.submit(graph.bundle, {"demo_id": self.did, "entry": "build"})
            command = future.result(timeout=3)
        self.assertEqual(command.goto, "finish")
        self.assertEqual(store.load(self.did)["stages"]["bundle"]["status"], "done")

    def test_actual_graph_stops_at_review_after_learning_during_recording(self):
        store.write_json(self.did, "faq.json", {"entries": [], "question_policy": faq.QUESTION_POLICY})
        store.update(self.did, lambda demo: [demo["stages"][stage].update(status="done") for stage in ("author", "deck", "faq")])
        def record(demo_id, emit):
            self.learn()
            return store.read_json(demo_id, "script.json")
        with patch.object(voice, "render_script", side_effect=record):
            graph.graph.invoke({"demo_id": self.did, "entry": "build"}, graph._cfg(self.did))
        self.assertEqual(store.load(self.did)["status"], "align")
        self.assertEqual(self.saved_publication(), self.before)
        self.assertIn("align_wait", graph.graph.get_state(graph._cfg(self.did)).next)

    def test_reapproval_publishes_the_reviewed_new_bank(self):
        entry = self.learn()
        faq.review_entry(self.did, entry["id"], action="approve")
        store.update(self.did, lambda demo: demo["approvals"].update(faq=True))
        published = bundle.build(self.did, lambda _: None)
        self.assertEqual(published["version"], self.old["version"] + 1)
        self.assertTrue(published["faq"][0]["reviewed"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
