"""Free retrieval I/O checks: exact evidence, per-call reads and pinned isolation."""
import copy
from collections import Counter
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ["MOCK_LLM"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, knowledge, store

PIN = "kb_" + "1" * 24
OTHER_PIN = "kb_" + "2" * 24
DOC = "knowledge/sources/doc/old.json"
OTHER = "knowledge/sources/other/old.json"
RIVAL = "knowledge/sources/rival/old.json"


def fact(fid, claim, value, *, ref="doc", locator="page 1", quote=None, **extra):
    return {"id": fid, "kind": "feature", "claim": claim, "value": value,
            "conditions": "", "approved": True, "truth": "stated",
            "scope": {"model": "Aster", "variant": "Premium", "market": "India"},
            "source": {"ref": ref, "locator": locator, "quote": value if quote is None else quote}, **extra}


class RetrievalIOContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="retrieval-io-")
        self.old_data = config.DATA_DIR
        config.DATA_DIR = Path(self.tmp.name)
        self.did = store.new_demo("Aster")["id"]
        self.sources = [{"id": sid, "name": sid + ".pdf", "kind": "pdf", "evidence_path": path}
                        for sid, path in (("doc", DOC), ("other", OTHER), ("rival", RIVAL))]
        self.rows = [fact("F001", "Panoramic roof", "Panoramic roof with a sliding glass panel."),
                     fact("F002", "Roof shade", "The panoramic roof has a powered shade.", locator="page 2"),
                     fact("F003", "Comfort seats", "Ventilated seats with adjustable lumbar support.", locator="page 3"),
                     fact("F004", "Engine", "The petrol engine uses an automatic gearbox.", ref="other"),
                     fact("F005", "Roof inspection", "The roof has an inspection hatch.", ref="other")]
        self.sections = {DOC: [{"locator": "page 1", "text": self.rows[0]["value"], "rows": [["glass", "sliding"]]},
                              {"locator": "page 2", "text": self.rows[1]["value"]},
                              {"locator": "appendix", "text": self.rows[0]["value"] + " Maintenance notes."},
                              {"locator": "page 3", "text": self.rows[2]["value"]},
                              {"locator": "end", "text": self.rows[0]["value"]}],
                         OTHER: [{"locator": "page 1", "text": self.rows[3]["value"]},
                                 {"locator": "page 1", "text": self.rows[4]["value"]}],
                         RIVAL: [{"locator": "page 1", "text": "A fixed roof."}]}
        self.snap = {"id": PIN, "version": 1, "product": {"name": "Aster"}, "facts": self.rows,
                     "competitors": [{"name": "Nova", "facts": [fact("C001", "Roof", "A fixed roof.", ref="rival")]}],
                     "sources": self.sources, "conflicts": [{"id": "conflict-note", "status": "resolved"}],
                     "coverage": {"source_count": 3}}
        for name, sections in self.sections.items():
            store.write_json(self.did, name, {"sections": sections})
        self.save(self.snap)
        store.write_json(self.did, "knowledge/published.json", {"id": PIN})

    def tearDown(self):
        config.DATA_DIR = self.old_data
        self.tmp.cleanup()

    def save(self, snap):
        store.write_json(self.did, f"knowledge/snapshots/{snap['id']}.json", snap)
        knowledge._write_index(self.did, snap)

    def retrieve(self, query, **kwargs):
        return knowledge.retrieve(self.did, query, snapshot_id=kwargs.pop("snapshot_id", PIN), **kwargs)

    def counted(self, query, **kwargs):
        counts = Counter()
        original = store.read_json
        def read(demo_id, name, *args, **options):
            counts[name] += 1
            return original(demo_id, name, *args, **options)
        with patch.object(store, "read_json", side_effect=read):
            result = self.retrieve(query, **kwargs)
        return result, counts

    def test_complete_evidence_matches_pre_optimization_reference(self):
        # The row order/scores/context below were captured from e80a180, before
        # this I/O change. Build full expected payloads from literal fixture data.
        for query, options, rows in GOLDEN:
            with self.subTest(query=query, options=options):
                expected = {"snapshot_id": PIN, "evidence": [], "conflicts": copy.deepcopy(self.snap["conflicts"]),
                            "coverage": copy.deepcopy(self.snap["coverage"]), "method": "BM25 + fixed concept/character cosine"}
                by_id = {f["id"]: (f, "Aster", False) for f in self.rows}
                by_id["C001"] = (self.snap["competitors"][0]["facts"][0], "Nova", True)
                for fid, score, sections in rows:
                    base, entity, competition = by_id[fid]
                    row = copy.deepcopy(base)
                    source = next(s for s in self.sources if s["id"] == base["source"]["ref"])
                    row.update(score=score, entity=entity, competition=competition, snapshot_id=PIN,
                               source_metadata=copy.deepcopy(source),
                               context=[copy.deepcopy(self.sections[source["evidence_path"]][i]) for i in sections])
                    expected["evidence"].append(row)
                self.assertEqual(self.retrieve(query, **options), expected)

    def test_multiple_selected_facts_parse_each_source_once(self):
        result, counts = self.counted("panoramic roof shade", limit=30)
        self.assertGreater(sum(row["source"]["ref"] == "doc" for row in result["evidence"]), 1)
        self.assertEqual(counts[DOC], 1)
        self.assertLessEqual(counts[OTHER], 1)

    def test_sources_outside_final_limit_are_never_read(self):
        result, counts = self.counted("panoramic roof shade", limit=1)
        self.assertEqual(len(result["evidence"]), 1)
        paths = {row["source_metadata"]["evidence_path"] for row in result["evidence"]}
        self.assertEqual({p for p in counts if p.startswith("knowledge/sources/")}, paths)
        self.assertEqual(counts[RIVAL], 0)

    def test_semantic_duplicates_do_not_read_the_discarded_source(self):
        duplicate = copy.deepcopy(self.rows[0])
        duplicate.update(id="F099", source={**duplicate["source"], "ref": "other"})
        self.snap["facts"].append(duplicate)
        self.save(self.snap)
        result, counts = self.counted("panoramic sliding glass", limit=1)
        self.assertEqual(result["evidence"][0]["id"], "F001")
        self.assertEqual(counts[OTHER], 0)

    def test_excluded_scope_and_competitor_sources_are_not_read(self):
        result, counts = self.counted("roof", scope={"market": "Nigeria"})
        self.assertEqual(result["evidence"], [])
        self.assertFalse(any(p.startswith("knowledge/sources/") for p in counts))
        result, counts = self.counted("roof", competition=False)
        self.assertFalse(any(row["competition"] for row in result["evidence"]))
        self.assertEqual(counts[RIVAL], 0)

    def test_unapproved_and_expired_rows_do_not_load_context(self):
        self.snap["facts"] = [fact("F010", "Roof", "Unavailable roof.", ref="other", approved=False),
                              fact("F011", "Roof", "Expired roof offer.", ref="rival", scope={"effective_to": "2000-01-01"})]
        self.snap["competitors"] = []
        self.save(self.snap)
        result, counts = self.counted("roof")
        self.assertEqual(result["evidence"], [])
        self.assertEqual(counts[OTHER] + counts[RIVAL], 0)

    def test_context_rows_do_not_share_mutable_nested_values(self):
        self.snap["facts"] = [self.rows[0], fact("F006", "Sliding glass", self.rows[0]["value"])]
        self.save(self.snap)
        result = self.retrieve("sliding glass")
        self.assertEqual(len(result["evidence"]), 2)
        first, second = result["evidence"]
        first["context"][0]["rows"][0][0] = "changed by a caller"
        self.assertEqual(second["context"][0]["rows"][0][0], "glass")
        self.assertEqual(self.retrieve("sliding glass")["evidence"][0]["context"][0]["rows"][0][0], "glass")

    def test_extraction_memo_does_not_survive_a_request(self):
        first = self.retrieve("panoramic roof", limit=1)
        replacement = {"locator": "page 1", "text": "Later available extraction context."}
        store.write_json(self.did, DOC, {"sections": [replacement]})
        second = self.retrieve("panoramic roof", limit=1)
        self.assertNotEqual(first["evidence"][0]["context"], second["evidence"][0]["context"])
        self.assertEqual(second["evidence"][0]["context"], [replacement])

    def test_old_and_new_published_snapshots_keep_separate_contexts(self):
        old = self.retrieve("panoramic roof")
        newer = copy.deepcopy(self.snap)
        newer["id"] = OTHER_PIN
        new_path = "knowledge/sources/doc/new.json"
        newer["sources"][0]["evidence_path"] = new_path
        replacement = {"locator": "page 1", "text": "Different revision context."}
        store.write_json(self.did, new_path, {"sections": [replacement]})
        self.save(newer)
        store.write_json(self.did, "knowledge/published.json", {"id": OTHER_PIN})
        self.assertEqual(self.retrieve("panoramic roof"), old)
        latest = self.retrieve("panoramic roof", snapshot_id=OTHER_PIN)
        self.assertNotEqual(latest["evidence"][0]["context"], old["evidence"][0]["context"])
        self.assertEqual(knowledge.retrieve(self.did, "panoramic roof"), latest)

    def test_missing_or_malformed_selected_extraction_stays_empty(self):
        store.path(self.did, DOC).unlink()
        result, counts = self.counted("panoramic roof shade", limit=30)
        self.assertTrue(all(row["context"] == [] for row in result["evidence"] if row["source"]["ref"] == "doc"))
        self.assertEqual(counts[DOC], 1)
        store.path(self.did, DOC).write_text("broken json")
        result, counts = self.counted("panoramic roof shade", limit=30)
        self.assertEqual(counts[DOC], 1)
        self.assertTrue(all(row["context"] == [] for row in result["evidence"] if row["source"]["ref"] == "doc"))

    def test_no_evidence_path_does_not_add_a_context_field(self):
        self.snap["sources"][0].pop("evidence_path")
        self.save(self.snap)
        result, counts = self.counted("panoramic roof", limit=1)
        self.assertNotIn("context", result["evidence"][0])
        self.assertEqual(counts[DOC], 0)

    def test_invalid_and_missing_snapshot_fail_before_source_reads(self):
        for sid in ("../../another-demo", "kb_" + "f" * 24):
            with self.subTest(snapshot_id=sid), self.assertRaises(ValueError):
                self.retrieve("roof", snapshot_id=sid)


# Filled from the frozen pre-change implementation by the baseline harness.
GOLDEN = [['panoramic roof shade',
  {'limit': 4},
  [['F002', 4.70313, [1]], ['F001', 2.76699, [0, 2]], ['F005', 0.86047, [0, 1]]]],
 ['seats comfort', {'limit': 2}, [['F003', 15.90814, [3]]]],
 ['petrol engine gearbox', {'limit': 3}, [['F004', 15.02347, [0, 1]]]],
 ['roof',
  {'competition': True, 'limit': 30},
  [['C001', 1.22088, [0]], ['F005', 1.06508, [0, 1]], ['F002', 1.04014, [1]], ['F001', 1.03887, [0, 2]]]],
 ['roof', {'scope': {'market': 'Nigeria'}}, []]]

if __name__ == "__main__":
    unittest.main(verbosity=2)
