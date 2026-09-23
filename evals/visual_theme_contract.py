"""Selected demo colors belong to the existing Visuals approval, with no paid work."""
from __future__ import annotations
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="visual-theme-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=TEMP.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(TEMP.name)/"graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
def blocked(*args, **kwargs):
    raise AssertionError("No outbound calls")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
from fastapi.testclient import TestClient
from server import graph, store
from server.agents import align
from server.app import app

class VisualThemeContract(unittest.TestCase):
    def setUp(self):
        self.did = store.new_demo("Reviewed demo colors")["id"]
        self.api = TestClient(app)
        self.url = f"/api/demos/{self.did}"
        def ready(demo):
            demo["status"] = "ready"
            demo["approvals"] = {card:True for card in store.CARDS}
            for stage in demo["stages"].values(): stage["status"] = "done"
        store.update(self.did, ready)
        store.write_json(self.did,"bundle.json",{"version":1,"visual_theme":"marine"})

    def choose(self, theme):
        return self.api.patch(self.url,json={"settings":{"visual_theme":theme}})

    def test_new_demo_defaults_to_approved_marine_design(self):
        self.assertEqual(store.load(self.did)["settings"]["visual_theme"],"marine")
        self.assertEqual(align.cards(self.did)["visuals"]["visual_theme"],"marine")

    def test_change_requires_visual_review_and_rebundle_only(self):
        before=store.load(self.did)
        response=self.choose("sage")
        self.assertEqual(response.status_code,200)
        after=store.load(self.did)
        self.assertEqual(after["status"],"align")
        self.assertFalse(after["approvals"]["visuals"])
        self.assertEqual(after["stages"]["bundle"]["status"],"stale")
        self.assertEqual(align.cards(self.did)["visuals"]["visual_theme"],"sage")
        for card in store.CARDS:
            if card!="visuals": self.assertEqual(after["approvals"][card],before["approvals"][card])
        for stage in before["stages"]:
            if stage!="bundle": self.assertEqual(after["stages"][stage],before["stages"][stage])

    def test_identical_selection_retains_approval_and_ready_state(self):
        self.assertEqual(self.choose("marine").status_code,200)
        after=store.load(self.did)
        self.assertTrue(all(after["approvals"].values()))
        self.assertEqual(after["status"],"ready")
        self.assertEqual(after["stages"]["bundle"]["status"],"done")

    def test_each_supported_color_round_trips(self):
        for theme in ("sage","graphite","marine"):
            self.assertEqual(self.choose(theme).status_code,200)
            self.assertEqual(store.load(self.did)["settings"]["visual_theme"],theme)

    def test_invalid_value_rejects_entire_payload(self):
        before=store.path(self.did,"demo.json").read_bytes()
        for value in ("blue","MARINE",None,True,[],{}):
            response=self.api.patch(self.url,json={"name":"Must not save","settings":{"visual_theme":value}})
            self.assertEqual(response.status_code,400)
            self.assertEqual(store.path(self.did,"demo.json").read_bytes(),before)

    def test_active_worker_blocks_change(self):
        before=store.path(self.did,"demo.json").read_bytes()
        with patch.object(graph,"is_running",return_value=True):
            self.assertEqual(self.choose("sage").status_code,409)
        self.assertEqual(store.path(self.did,"demo.json").read_bytes(),before)

    def test_active_stage_blocks_change(self):
        store.update(self.did,lambda demo:demo.update(running="deck"))
        self.assertEqual(self.choose("sage").status_code,409)
        self.assertEqual(store.load(self.did)["settings"]["visual_theme"],"marine")

    def test_draft_color_does_not_mutate_published_bundle(self):
        before=store.path(self.did,"bundle.json").read_bytes()
        self.choose("graphite")
        self.assertEqual(store.path(self.did,"bundle.json").read_bytes(),before)

    def test_review_still_has_six_cards(self):
        self.choose("sage")
        self.assertEqual(store.CARDS,["visuals","facts","script","faq","persona","ctas"])
        self.assertEqual(align.current_card(store.load(self.did)),"visuals")

    def test_legacy_demo_without_color_uses_marine(self):
        store.update(self.did,lambda demo:demo["settings"].pop("visual_theme"))
        self.assertEqual(align.cards(self.did)["visuals"]["visual_theme"],"marine")
        self.choose("marine")
        self.assertTrue(store.load(self.did)["approvals"]["visuals"])

    def test_unrelated_setting_preserves_color(self):
        self.choose("graphite")
        self.api.patch(self.url,json={"settings":{"audience":"expert"}})
        self.assertEqual(store.load(self.did)["settings"]["visual_theme"],"graphite")

    def test_reviewed_color_reaches_new_publication(self):
        from evals.minimum_narration_contract import rich_fixture
        from server.agents import bundle
        self.choose("sage")
        rich_fixture(self.did, recorded=True)
        store.update(self.did,lambda demo:demo["approvals"].update(visuals=True))
        published=bundle.build(self.did,lambda _:None)
        self.assertEqual(published["visual_theme"],"sage")
        self.assertGreaterEqual(published["runtime"]["narration_minimum"]["seconds"],180)
        self.assertTrue(published["runtime"]["narration_minimum"]["measured"])

if __name__=="__main__": unittest.main(verbosity=2)
