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
socket.socket.connect = socket.socket.connect_ex = socket.socket.sendto = socket.create_connection = socket.getaddrinfo = blocked
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


class PdfTableCitationContract(unittest.TestCase):
    # Exercise the same retained PDF shape as sources.pdf_pages produces. The
    # layout text deliberately interleaves columns, unlike individual cells.
    rows=FactRetryContract.rows
    tearDown=FactRetryContract.tearDown

    def setUp(self):
        FactRetryContract.setUp(self)
        self.source["kind"]="pdf"
        store.update(self.did, lambda demo: demo.update(sources=[self.source]))
        self.fact["source"]={"ref":"doc", "locator":"Page 16, Section 6 / Page 29, Section 10",
                             "quote":"250 Nm (25.5 kgm) @ 1,500–2,750 r/min"}
        self.extraction={"id":"doc", "revision":"v1", "text":"250 Nm (25.5 kgm) @ 6-speed manual or 1,500–2,750 r/min",
                         "sections":[{"kind":"pdf", "locator":"page 16", "tables":[[
                             ["Engine", "Max. torque", "Transmission"],
                             ["1.5 l U2 CRDi diesel", "250 Nm (25.5 kgm) @\n1,500–2,750 r/min", "6-speed manual or\n6-speed automatic"]]]}]}
        self.write_evidence()

    def write_evidence(self):
        store.write_json(self.did,"evidence/doc.json",self.extraction)

    def verifies(self, fact=None, source=None):
        return knowledge.citation_verified(self.did,fact or self.fact,source or self.source)

    def test_exact_wrapped_cells_keep_all_three_engine_torque_quotes(self):
        for quote,cell in (
            ("143.8 Nm (14.7 kgm) @ 4,500 r/min", "143.8 Nm (14.7 kgm) @ 4,500\nr/min"),
            ("250 Nm (25.5 kgm) @ 1,500–2,750 r/min", "250 Nm (25.5 kgm) @\n1,500–2,750 r/min"),
            ("253 Nm (25.8 kgm) @ 1,500–3,500 r/min", "253 Nm (25.8 kgm) @\n1,500–3,500 r/min")):
            with self.subTest(quote=quote):
                self.fact["source"]["quote"]=quote
                self.extraction["sections"][0]["tables"][0][1][1]=cell
                self.write_evidence()
                self.assertNotIn(knowledge._norm(quote),knowledge._norm(self.extraction["text"]))
                self.assertTrue(self.verifies())

    def test_same_quote_on_wrong_or_uncited_page_stays_held(self):
        for locator in ("page 15", "page 116", "Section 16", "page 0", ""):
            with self.subTest(locator=locator):
                candidate=copy.deepcopy(self.fact);candidate["source"]["locator"]=locator
                self.assertFalse(self.verifies(candidate))

    def test_wrong_source_or_revision_cannot_supply_a_table_quote(self):
        for change in ({"id":"other"},{"revision":"v2"},{"id":None}):
            with self.subTest(change=change):
                self.assertFalse(self.verifies(source={**self.source,**change}))
        candidate=copy.deepcopy(self.fact);candidate["source"]["ref"]="other"
        self.assertFalse(self.verifies(candidate))
        for field,value in (("id","other"),("revision","v2"),("id",None)):
            with self.subTest(extraction_field=field,value=value):
                altered={**self.extraction,field:value}
                store.write_json(self.did,"evidence/doc.json",altered)
                self.assertFalse(self.verifies())
        for revision in (None, ""):
            with self.subTest(missing_revision=revision):
                store.write_json(self.did,"evidence/doc.json",{**self.extraction,"revision":revision})
                self.assertFalse(self.verifies(source={**self.source,"revision":revision}))

    def test_no_cross_cell_or_cross_row_concat_creates_a_quote(self):
        for table in (
            [["250 Nm (25.5 kgm) @", "1,500–2,750 r/min"]],
            [["250 Nm (25.5 kgm) @"], ["1,500–2,750 r/min"]],
            [["1,500–2,750 r/min", "250 Nm (25.5 kgm) @"]]):
            self.extraction["sections"][0]["tables"]=[table]
            self.write_evidence()
            self.assertFalse(self.verifies())

    def test_paraphrase_changed_number_or_unit_is_never_fuzzy_matched(self):
        for quote in ("250 Nm at 1,500–2,750 r/min", "253 Nm (25.5 kgm) @ 1,500–2,750 r/min",
                      "250 Nm (25.5 kgm) @ 1,500–2,750 rpm", "250 Nm (25.5 kgm) @ 1,500–2,750 r/min on every trim"):
            candidate=copy.deepcopy(self.fact);candidate["source"]["quote"]=quote
            self.assertFalse(self.verifies(candidate))

    def test_null_or_unlocated_non_pdf_cells_are_not_evidence(self):
        for section in (
            {"kind":"pdf","locator":"page 16","tables":[[[None, ""]]]},
            {"kind":"pdf","locator":"","tables":self.extraction["sections"][0]["tables"]},
            {"kind":"table","locator":"page 16","tables":self.extraction["sections"][0]["tables"]}):
            store.write_json(self.did,"evidence/doc.json",{**self.extraction,"sections":[section]})
            self.assertFalse(self.verifies())

    def test_cell_retry_retains_original_assertion_and_conflict_exclusion(self):
        self.und["facts"][0]=copy.deepcopy(self.fact)
        store.write_json(self.did,"understanding.json",self.und)
        result=knowledge.review_held_citations(self.did,"retry")
        self.assertEqual(result["changed_fact_ids"],["F001"])
        self.assertEqual(result["skipped_conflicts"],["F003"])
        self.assertEqual(self.rows()[0]["source"],self.fact["source"])
        self.assertNotIn("citation_override",self.rows()[0]["knowledge"])
        self.assertEqual(self.rows()[1:],self.und["facts"][1:])


if __name__=="__main__": unittest.main(verbosity=2)
