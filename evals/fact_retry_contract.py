"""Offline citation retry and bulk-owner-review contracts; no model or network calls."""
from __future__ import annotations
import copy
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

TEMP = tempfile.TemporaryDirectory(prefix="fact-retry-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=TEMP.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(TEMP.name)/"graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ATTEMPTS = []
def blocked(*args, **kwargs):
    ATTEMPTS.append(True)
    raise AssertionError("No outbound calls")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked
from fastapi.testclient import TestClient
from server import graph, knowledge, store
from server.app import app


class FactRetryContract(unittest.TestCase):
    def setUp(self):
        self.did = store.new_demo("Held citation review")["id"]
        self.source = {"id":"doc", "kind":"text", "name":"Brochure", "revision":"v1", "evidence_path":"evidence/doc.json"}
        store.update(self.did, lambda demo: demo.update(sources=[self.source]))
        self.fact = {"id":"F001", "kind":"spec", "claim":"Length", "value":"4330 mm", "approved":False,
                     "source":{"ref":"doc", "locator":"Dimensions", "quote":"Length 4330 mm"},
                     "knowledge":{"review_required":knowledge.CITATION_REVIEW_REQUIRED, "source_revision":"v1"}}
        self.manual = {**copy.deepcopy(self.fact), "id":"F002", "knowledge":{}}
        self.conflict = {**copy.deepcopy(self.fact), "id":"F003", "knowledge":{**self.fact["knowledge"], "excluded_by_precedence":True}}
        self.und = {"product":{"name":"Example"}, "facts":[self.fact,self.manual,self.conflict], "competitors":[], "unknowns":[]}
        store.write_json(self.did,"understanding.json",self.und)
        store.write_json(self.did,"evidence/doc.json",{"text":"Overall length 4330 mm. Width 1790 mm."})
        def ready(demo):
            for stage in demo["stages"].values(): stage["status"]="done"
            demo["approvals"].update({key:True for key in store.CARDS})
        store.update(self.did,ready)
        self.api=TestClient(app)
        self.url=f"/api/demos/{self.did}/align/facts/review-held"

    def tearDown(self): self.assertEqual(ATTEMPTS,[])
    def rows(self): return store.read_json(self.did,"understanding.json")["facts"]

    def test_retry_accepts_exact_quote_and_locator_without_rewriting_fact(self):
        result=knowledge.review_held_citations(self.did,"retry")
        self.assertEqual(result["changed_fact_ids"],["F001"])
        row=self.rows()[0]
        self.assertTrue(row["approved"])
        self.assertEqual(row["source"],self.fact["source"])
        self.assertEqual(row["id"],self.fact["id"])
        self.assertNotIn("review_required",row["knowledge"])

    def test_reordered_table_tokens_remain_held(self):
        store.write_json(self.did,"evidence/doc.json",{"text":"4330 mm 1790 mm Length Width"})
        result=knowledge.review_held_citations(self.did,"retry")
        self.assertEqual(result["still_held"],["F001"])
        self.assertFalse(self.rows()[0]["approved"])

    def test_retry_preserves_manual_and_conflict_exclusions(self):
        result=knowledge.review_held_citations(self.did,"retry")
        self.assertEqual(result["skipped_conflicts"],["F003"])
        self.assertEqual(self.rows()[1:],self.und["facts"][1:])

    def test_bulk_restore_is_explicit_owner_override_not_machine_verification(self):
        store.write_json(self.did,"evidence/doc.json",{"text":"A different passage"})
        result=knowledge.review_held_citations(self.did,"restore")
        self.assertEqual(result["changed_fact_ids"],["F001"])
        row=self.rows()[0]
        self.assertEqual(row["knowledge"]["review_required"],knowledge.CITATION_REVIEW_REQUIRED)
        self.assertEqual(row["knowledge"]["citation_override"]["source"],"owner_bulk_restore")
        self.assertEqual(self.rows()[1:],self.und["facts"][1:])

    def test_open_conflict_members_are_skipped_even_without_per_fact_flag(self):
        self.und["knowledge"]={"conflicts":[{"status":"unresolved","fact_ids":["F001"]}]}
        store.write_json(self.did,"understanding.json",self.und)
        result=knowledge.review_held_citations(self.did,"restore")
        self.assertEqual(result["changed_fact_ids"],[])
        self.assertFalse(self.rows()[0]["approved"])

    def test_retry_never_uses_another_source_revision_or_cached_fetch(self):
        for change in ({"revision":"v2"},{"crawl_cached":True}):
            store.update(self.did,lambda demo:demo.update(sources=[{**self.source,**change}]))
            self.assertEqual(knowledge.review_held_citations(self.did,"retry")["still_held"],["F001"])

    def test_missing_locator_or_quote_cannot_be_retried_into_a_fact(self):
        for field in ("quote","locator"):
            fact=copy.deepcopy(self.fact);fact["source"][field]=""
            self.assertFalse(knowledge.citation_verified(self.did,fact,self.source))

    def test_retry_is_bounded_and_can_observe_a_completed_retained_source_write(self):
        with patch.object(store,"read_json",side_effect=[None,{"text":"Length 4330 mm"}]) as reads:
            self.assertTrue(knowledge.citation_verified(self.did,self.fact,self.source))
        self.assertEqual(reads.call_count,2)
        with patch.object(store,"read_json",return_value={"text":"No matching quote"}) as reads:
            self.assertFalse(knowledge.citation_verified(self.did,self.fact,self.source,attempts=100))
        self.assertEqual(reads.call_count,2)

    def test_api_invalidates_dependent_work_only_when_facts_change(self):
        response=self.api.post(self.url,json={"action":"retry"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["changed_fact_ids"],["F001"])
        demo=store.load(self.did)
        self.assertFalse(any(demo["approvals"].values()))
        self.assertEqual(demo["stages"]["understand"]["status"],"done")
        self.assertEqual(demo["stages"]["coach"]["status"],"stale")
        self.assertEqual(demo["stages"]["faq"]["status"],"stale")

    def test_noop_retry_keeps_approvals(self):
        store.write_json(self.did,"evidence/doc.json",{"text":"No matching quote"})
        response=self.api.post(self.url,json={"action":"retry"})
        self.assertEqual(response.status_code,200)
        self.assertTrue(all(store.load(self.did)["approvals"].values()))

    def test_api_rejects_arbitrary_ids_actions_and_running_work_atomically(self):
        before=store.path(self.did,"understanding.json").read_bytes()
        for payload in ({"action":"restore","fact_ids":["F002"]},{"action":"approve"},[]):
            self.assertEqual(self.api.post(self.url,json=payload).status_code,400)
        with patch.object(graph,"is_running",return_value=True):
            self.assertEqual(self.api.post(self.url,json={"action":"restore"}).status_code,409)
        self.assertEqual(store.path(self.did,"understanding.json").read_bytes(),before)

    def test_published_snapshot_keeps_original_approval_after_draft_restore(self):
        old=knowledge.snapshot(self.did,publish=True)
        knowledge.review_held_citations(self.did,"restore")
        saved=store.read_json(self.did,f"knowledge/snapshots/{old['id']}.json")
        self.assertFalse(saved["facts"][0]["approved"])
        self.assertEqual(saved["facts"][0]["source"],self.fact["source"])
        self.assertNotEqual(knowledge.snapshot(self.did)["id"],old["id"])


if __name__=="__main__": unittest.main(verbosity=2)
