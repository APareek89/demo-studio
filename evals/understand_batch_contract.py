"""Free reader-input contracts: complete pages, exact tables and cache identity.

Model completeness remains a paid-output quality check. These tests establish
that smaller inputs preserve the evidence and use the existing extraction path.
"""
from __future__ import annotations

import copy
import json
import os
import socket
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

os.environ["MOCK_LLM"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, schemas, store
from server.agents import understand


def fixture(chunks, source_id="source", kind="pdf"):
    return ([{"id": source_id, "kind": kind, "role": "product"}],
            {source_id: {"name": "Evidence guide", "text": "", "chunks": chunks}})


def output():
    return schemas.FactsOut(product=schemas.Product(name="Fixture", category="car", summary="", audience=""),
                            facts=[], unknowns=[], brand=schemas.Brand(tone="", voice_style="", dos=[], donts=[], persona_hint=""))


class UnderstandBatchContract(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temp = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="understand-batch-"))
        self.stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(temp)))
        self.network = [self.stack.enter_context(patch.object(socket, method, side_effect=AssertionError("Network forbidden")))
                        for method in ("create_connection",)]
        self.network += [self.stack.enter_context(patch.object(socket.socket, method, side_effect=AssertionError("Network forbidden")))
                         for method in ("connect", "connect_ex", "sendto")]
        self.providers = [self.stack.enter_context(patch(name, side_effect=AssertionError("Provider forbidden")))
                          for name in ("server.llm.gemini.client", "server.llm.claude._client_opts", "server.llm.runware._post")]

    def tearDown(self):
        self.assertFalse(any(call.called for call in self.network + self.providers))

    def test_default_twenty_thousand_budget_preserves_page_order(self):
        docs, extracted = fixture([{"locator": f"page {i}", "text": f"page-{i}:" + "x" * 7000} for i in range(1, 7)])
        batches = understand._fact_batches(docs, extracted)
        self.assertEqual([len(batch) for batch in batches], [2, 2, 2])
        self.assertTrue(all(sum(map(len, batch)) <= 20000 for batch in batches))
        self.assertEqual([text.split(" ===\n")[1] for batch in batches for text in batch],
                         [chunk["text"] for chunk in extracted["source"]["chunks"]])

    def test_exact_tables_nulls_unicode_locators_and_roles_survive(self):
        table = [["Engine", "Gearbox", "E", "King"], ["1.5 l turbo", "DCT", "–", "●"], [None, "MT", "S", None]]
        docs, extracted = fixture([{"locator": "page 31", "text": "* Automatic only. FAQ is stale.", "tables": [table]}])
        docs[0]["role"] = "catalogue"
        before = copy.deepcopy((docs, extracted))
        text = understand._fact_batches(docs, extracted)[0][0]
        self.assertIn("source · pdf · role=catalogue · Evidence guide · page 31", text)
        self.assertTrue(text.endswith(json.dumps([table], ensure_ascii=False)))
        self.assertIn("* Automatic only. FAQ is stale.", text)
        self.assertEqual((docs, extracted), before)

    def test_single_oversized_page_is_not_split_or_truncated(self):
        docs, extracted = fixture([{"locator": "page 1", "text": "a" * 25000},
                                   {"locator": "page 2", "text": "next page"}])
        batches = understand._fact_batches(docs, extracted)
        self.assertEqual([len(batch) for batch in batches], [1, 1])
        self.assertIn("a" * 25000, batches[0][0])

    def test_existing_pieces_of_one_pdf_page_stay_together(self):
        docs, extracted = fixture([{"locator": "page 1", "text": "a" * 14000},
                                   {"locator": "page 1", "text": "b" * 14000},
                                   {"locator": "page 2", "text": "next page"}])
        batches = understand._fact_batches(docs, extracted)
        self.assertEqual([len(batch) for batch in batches], [2, 1])
        self.assertIn("a" * 14000, batches[0][0])
        self.assertIn("b" * 14000, batches[0][1])

    def test_equal_page_numbers_in_different_sources_remain_separate(self):
        docs, extracted = fixture([{"locator": "page 1", "text": "a" * 14000}])
        other_docs, other_extracted = fixture([{"locator": "page 1", "text": "b" * 14000}], "other")
        batches = understand._fact_batches(docs + other_docs, {**extracted, **other_extracted})
        self.assertEqual([len(batch) for batch in batches], [1, 1])
        self.assertIn("SOURCE source", batches[0][0])
        self.assertIn("SOURCE other", batches[1][0])

    def test_nonpage_document_chunks_remain_bounded(self):
        docs, extracted = fixture([{"locator": "document", "text": "a" * 14000},
                                   {"locator": "document", "text": "b" * 14000}], kind="text")
        self.assertEqual([len(batch) for batch in understand._fact_batches(docs, extracted)], [1, 1])

    def test_empty_and_legacy_text_fallback_keep_evidence_state(self):
        self.assertEqual(understand._fact_batches([], {}),
                         [["No documents or URL provided. Leave unsupported facts empty and report the gaps."]])
        docs, extracted = fixture([])
        extracted["source"]["text"] = "Complete legacy document"
        batches = understand._fact_batches(docs, extracted)
        self.assertEqual(len(batches), 1)
        self.assertTrue(batches[0][0].endswith("Complete legacy document"))

    def test_run_supplies_batch_context_revision_and_full_evidence(self):
        did = store.new_demo("Reader fixture")["id"]
        for n in range(3):
            store.add_text_source(did, f"document {n}", f"distinct-{n}\n" + "content " * 1500, "product")
        calls = []
        def reader(system, blocks, schema, **kwargs):
            self.assertIs(schema, schemas.FactsOut)
            self.assertEqual(kwargs["max_tokens"], 32000)
            calls.append((system, blocks))
            return output()
        with patch.object(understand.claude, "structured", side_effect=reader):
            result = understand.run(did, lambda _: None, instruction="Preserve feature fitment")
        self.assertEqual(len(calls), 3)
        for n, (system, blocks) in enumerate(calls, 1):
            self.assertIn(f"EVIDENCE BATCH {n}/3", blocks[-1]["text"])
            self.assertIn("partial evidence", blocks[-1]["text"])
            self.assertIn("Preserve feature fitment", blocks[-1]["text"])
            self.assertIn(f"distinct-{n-1}", blocks[0]["text"])
            self.assertIn("engine-to-gearbox", system)
            self.assertIn("stale-content warnings", system)
            self.assertIn("absence from this batch does not establish absence from the whole upload", system)
        self.assertEqual(result["facts"], [])

    def test_single_batch_marks_all_chunks_without_claiming_factual_completeness(self):
        did = store.new_demo("Small reader fixture")["id"]
        store.add_text_source(did, "facts", "Six airbags are standard.", "product")
        with patch.object(understand.claude, "structured", return_value=output()) as reader:
            understand.run(did, lambda _: None)
        self.assertIn("EVIDENCE BATCH 1/1", reader.call_args.args[1][-1]["text"])
        self.assertIn("all supplied document chunks", reader.call_args.args[1][-1]["text"])

    def test_cache_reuses_only_exact_prompt_content_and_revision(self):
        did = store.new_demo("Cache fixture")["id"]
        docs, extracted = fixture([{"locator": "page 1", "text": "ABS is standard.", "tables": [[["ABS", "S"]]]}])
        blocks = [{"type": "text", "text": text} for text in understand._fact_batches(docs, extracted)[0]]
        calls = []
        def reader():
            calls.append(True)
            return output()
        def cached(system=understand.FACTS_SYSTEM, content=None, revision="v1"):
            return understand._cached_extraction(did, "facts", system, {"blocks": content or blocks, "max_tokens": 32000},
                                                 schemas.FactsOut, reader, source_versions=[revision])
        # Exercise persistent cache with only a canned callable; provider/socket
        # entry points remain blocked even while bypassing the MOCK cache shortcut.
        with patch.object(config, "MOCK_LLM", False):
            cached(); cached()
            self.assertEqual(len(calls), 1)
            cached(system=understand.FACTS_SYSTEM + " Retain another condition.")
            changed = copy.deepcopy(blocks); changed[0]["text"] += "\n* Automatic only."
            cached(content=changed)
            cached(revision="v2")
            self.assertEqual(len(calls), 4)
        self.assertEqual(len(list(store.path(did, "knowledge/extractions").glob("facts_*.json"))), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
