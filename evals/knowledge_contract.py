"""Free evidence/knowledge regressions: isolated files, fake HTTP, no model calls."""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ["MOCK_LLM"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import config, crawl, knowledge, sources, store


def fact(value="400 litres", ref="doc", claim="Boot capacity", **kwargs):
    return {"id": "ignored", "kind": "spec", "claim": claim, "value": value,
            "source": {"ref": ref, "locator": "page 1", "quote": value}, "confidence": 1,
            "conditions": "", "truth": "stated", "approved": True, "edited": False,
            "scope": {"model": "Creta", "model_year": "2026", "market": "India", "variant": "SX"}, **kwargs}


def understanding(rows):
    return {"product": {"name": "Hyundai Creta", "category": "car", "summary": "", "audience": ""}, "facts": rows,
            "competitors": [], "brand": {"tone": "", "voice_style": "", "dos": [], "donts": [], "persona_hint": ""}}


class KnowledgeContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="knowledge-contract-")
        self.old_data = config.DATA_DIR
        config.DATA_DIR = Path(self.tmp.name)
        self.demo = store.new_demo("Hyundai Creta")
        self.did = self.demo["id"]
        store.update(self.did, lambda d: d.update(sources=[{"id": "doc", "name": "brochure.pdf", "kind": "pdf", "path": "sources/doc.pdf"},
                                                           {"id": "web", "name": "site", "kind": "url", "url": "https://example.com/creta"}]))

    def tearDown(self):
        config.DATA_DIR = self.old_data
        self.tmp.cleanup()

    def reconcile(self, rows, previous=None):
        return knowledge.reconcile(self.did, understanding(rows), previous)

    def test_reorder_preserves_citation_meaning(self):
        first = self.reconcile([fact(), fact("6 airbags", claim="Airbags")])
        second = self.reconcile([fact("6 airbags", claim="Airbags"), fact()], first)
        self.assertEqual([f["id"] for f in first["facts"]], ["F001", "F002"])
        self.assertEqual([f["id"] for f in second["facts"]], ["F002", "F001"])

    def test_change_and_removal_never_retarget_ids(self):
        first = self.reconcile([fact()])
        second = self.reconcile([fact("420 litres")], first)
        self.assertEqual(second["facts"][0]["id"], "F002")
        self.assertFalse(second["facts"][0]["approved"])
        self.assertEqual(second["knowledge"]["diff"]["changed"][0]["previous_ids"], ["F001"])
        third = self.reconcile([], second)
        fourth = self.reconcile([fact("6 airbags", claim="Airbags")], third)
        self.assertEqual(fourth["facts"][0]["id"], "F003")

    def test_quote_change_versions_assertion_source_revision_versions_evidence(self):
        first = self.reconcile([fact()])
        changed = fact()
        changed["source"]["quote"] = "Luggage: 400 litres"
        second = self.reconcile([changed], first)
        self.assertNotEqual(first["facts"][0]["id"], second["facts"][0]["id"])
        store.update(self.did, lambda d: d["sources"][0].update(revision="next-document-bytes"))
        third = self.reconcile([changed], second)
        self.assertEqual(second["facts"][0]["id"], third["facts"][0]["id"])
        self.assertNotEqual(second["facts"][0]["knowledge"]["evidence_id"], third["facts"][0]["knowledge"]["evidence_id"])

    def test_document_wins_only_true_same_scope_conflict(self):
        result = self.reconcile([fact(), fact("420 litres", ref="web")])
        self.assertTrue(result["facts"][0]["approved"])
        self.assertFalse(result["facts"][1]["approved"])
        self.assertEqual(result["knowledge"]["conflicts"][0]["resolution"], "uploaded_document")
        web = fact("420 litres", ref="web")
        web["scope"]["variant"] = "E"
        separate = self.reconcile([fact(), web])
        self.assertEqual(separate["knowledge"]["conflicts"], [])
        self.assertTrue(all(f["approved"] for f in separate["facts"]))

    def test_missing_scope_does_not_trigger_precedence(self):
        a, b = fact(), fact("420 litres", ref="web")
        del b["scope"]["model_year"]
        result = self.reconcile([a, b])
        self.assertEqual(result["knowledge"]["conflicts"], [])
        a["scope"]["effective_from"] = b["scope"]["effective_from"] = "2020-01-01"
        a["scope"]["effective_to"] = b["scope"]["effective_to"] = "2020-12-31"
        a["kind"] = b["kind"] = "price"
        self.assertFalse(knowledge._same_scope(a, b))

    def test_two_documents_require_review_download_is_not_upload(self):
        store.update(self.did, lambda d: d["sources"].append({"id": "doc2", "kind": "pdf", "name": "second.pdf"}))
        result = self.reconcile([fact(), fact("420 litres", ref="doc2")])
        self.assertFalse(any(f["approved"] for f in result["facts"]))
        self.assertEqual(result["knowledge"]["conflicts"][0]["status"], "unresolved")
        self.assertFalse(knowledge._uploaded_document({"kind": "pdf", "origin": "website"}))

    def displacement_rows(self):
        # This reproduces the compound-label miss without a model/ID special case.
        return [fact("1 482 cm3", claim="1.5l Turbo GDi petrol engine displacement",
                     conditions="1.5l Turbo GDi petrol engine; 4 cylinders, 16 valves DOHC",
                     scope={"model":"Aster", "market":"India", "powertrain":"1.5l Turbo GDi petrol"}),
                fact("1497 cc Turbo GDi petrol engine delivering 160 PS", ref="web",
                     claim="Turbo petrol engine displacement and power",
                     conditions="1.5-litre Turbo GDi petrol paired with 7-speed DCT",
                     scope={"model":"Aster", "powertrain":"1.5L Turbo GDi petrol", "transmission":"7-speed DCT"})]

    def test_compound_engine_displacement_conflict_holds_unreviewed_values(self):
        inputs = self.displacement_rows()
        result = self.reconcile(inputs)
        self.assertFalse(any(f["approved"] for f in result["facts"]))
        conflict = result["knowledge"]["conflicts"][0]
        self.assertEqual(conflict["status"], "unresolved")
        self.assertEqual(conflict["dimensional_conflict"]["predicate"], "engine_displacement")
        self.assertEqual(set(conflict["dimensional_conflict"]["values"].values()), {"1482", "1497"})
        # Incomplete applicability cannot acquire automatic document precedence.
        self.assertFalse(conflict["dimensional_conflict"]["scope_complete"])
        self.assertEqual([f["value"] for f in result["facts"]], [f["value"] for f in inputs])
        self.assertEqual([f["source"] for f in result["facts"]], [f["source"] for f in inputs])

    def test_reviewed_displacement_stays_preferred_and_ids_survive_reread(self):
        good, bad = self.displacement_rows()
        first = self.reconcile([good])
        first["facts"][0].update(edited=True, approved=True)
        old_id = first["facts"][0]["id"]
        second = self.reconcile([bad, good], first)
        rows = {f["id"]: f for f in second["facts"]}
        self.assertTrue(rows[old_id]["approved"])
        self.assertFalse(next(f for fid, f in rows.items() if fid != old_id)["approved"])
        conflict = next(c for c in second["knowledge"]["conflicts"] if c.get("dimensional_conflict"))
        self.assertEqual((conflict["resolution"], conflict["preferred_fact_id"]), ("human_edit", old_id))
        third = self.reconcile([good, bad], second)
        self.assertEqual({f["id"] for f in second["facts"]}, {f["id"] for f in third["facts"]})
        self.assertEqual(next(f for f in third["facts"] if f["id"] == old_id)["source"], good["source"])
        self.assertTrue(next(f for f in third["facts"] if f["id"] == old_id)["approved"])

    def test_two_reviewed_displacement_values_require_fresh_conflict_decision(self):
        rows = self.displacement_rows()
        previous = self.reconcile([rows[0]])
        # Independently reviewed rows cannot silently choose one another's winner.
        second = self.reconcile([rows[1]])
        previous["facts"] += second["facts"]
        for row in previous["facts"]:
            row.update(edited=True, approved=True)
        result = self.reconcile(rows, previous)
        self.assertFalse(any(f["approved"] for f in result["facts"]))
        self.assertEqual(result["knowledge"]["conflicts"][0]["status"], "unresolved")

    def test_displacement_units_normalize_without_comparing_power_or_nominal_litres(self):
        for value in ("1,482 cc", "1482 cm³", "1482 cubic centimeters", "1482 cc delivering 160 PS"):
            with self.subTest(value=value):
                a, b = self.displacement_rows()
                b["value"] = value
                self.assertEqual(self.reconcile([a, b])["knowledge"]["conflicts"], [])
        for value in ("1.5 litres delivering 160 PS", "1497 PS", "1482–1497 cc", "approximately 1497 cc", "1482 cc or 1497 cc"):
            with self.subTest(value=value):
                a, b = self.displacement_rows()
                b["value"] = value
                self.assertEqual(self.reconcile([a, b])["knowledge"]["conflicts"], [])

    def test_displacement_never_borrows_broad_quote_or_unrelated_claim(self):
        a, b = self.displacement_rows()
        b.update(value="160 PS", claim="Turbo engine power")
        b["source"]["quote"] = "1497 cc petrol; 1482 cc turbo petrol; 160 PS"
        self.assertEqual(self.reconcile([a, b])["knowledge"]["conflicts"], [])
        b.update(value="1497 cc", claim="Fuel tank capacity")
        self.assertEqual(self.reconcile([a, b])["knowledge"]["conflicts"], [])

    def test_displacement_requires_explicit_compatible_engine_and_scope(self):
        for key, a_value, b_value in (
            ("model", "Aster", "Nova"), ("powertrain", "1.5l Turbo GDi petrol", "1.5l MPi petrol"),
            ("powertrain", "1.5l Turbo GDi petrol", "2.0l Turbo GDi petrol"),
            ("powertrain", "1.5l Turbo GDi petrol", "petrol"),
            ("powertrain", "1.5l petrol", "1.5l petrol"),
            ("market", "India", "South Africa"), ("model_year", "2026", "2025"),
            ("variant", "Entry", "Premium"), ("transmission", "6MT", "7DCT"),
            ("test_basis", "standard", "modified"), ("generation", "second", "first"),
            ("model_year", "2026", None), ("variant", "Entry", None)):
            with self.subTest(key=key, value=b_value):
                a, b = self.displacement_rows()
                a["scope"][key] = a_value
                if b_value is None:
                    b["scope"].pop(key, None)
                else:
                    b["scope"][key] = b_value
                self.assertEqual(self.reconcile([a, b])["knowledge"]["conflicts"], [])

    def test_displacement_respects_explicit_human_resolution_on_unchanged_assertions(self):
        inputs = self.displacement_rows()
        initial = self.reconcile(inputs)
        store.write_json(self.did, "understanding.json", initial)
        winner = initial["facts"][1]["id"]
        reviewed = knowledge.resolve_conflict(self.did, initial["knowledge"]["conflicts"][0]["id"], winner)["understanding"]
        after = self.reconcile(inputs, reviewed)
        self.assertTrue(next(f for f in after["facts"] if f["id"] == winner)["approved"])
        self.assertEqual(after["knowledge"]["conflicts"][0]["resolution"], "human_review")

    def test_human_full_edit_preserved_on_same_evidence(self):
        first = self.reconcile([fact()])
        first["facts"][0].update(value="400 litres (reviewed)", edited=True, approved=False)
        second = self.reconcile([fact()], first)
        self.assertEqual(second["facts"][0]["value"], "400 litres (reviewed)")
        self.assertFalse(second["facts"][0]["approved"])
        self.assertTrue(second["facts"][0]["edited"])
        self.assertEqual(second["knowledge"]["conflicts"][0]["resolution"], "human_edit")

    def test_direct_edit_versions_identity_and_preserves_override_on_reread(self):
        first = self.reconcile([fact()])
        store.write_json(self.did, "understanding.json", first)
        old = copy.deepcopy(first["facts"][0])
        candidate = {**copy.deepcopy(old), "claim": "Reviewed luggage capacity", "value": "400 litres (reviewed)", "conditions": "Seats raised"}
        changed = knowledge.copy_on_edit(self.did, old, candidate)
        self.assertNotEqual(changed["id"], old["id"])
        ledger = store.read_json(self.did, "knowledge/identities.json")
        self.assertEqual(ledger["ids"][old["id"]]["identity"], knowledge._identity(old))
        self.assertEqual(ledger["ids"][changed["id"]]["identity"], knowledge._identity(changed))
        self.assertEqual(changed["knowledge"]["previous_id"], old["id"])
        first["facts"] = [changed]
        again = self.reconcile([fact()], first)
        self.assertEqual(len(again["facts"]), 1)
        self.assertEqual(again["facts"][0]["id"], changed["id"])
        self.assertEqual(again["facts"][0]["claim"], "Reviewed luggage capacity")
        no_op = knowledge.copy_on_edit(self.did, changed, copy.deepcopy(changed))
        self.assertEqual(no_op["id"], changed["id"])

    def test_repeated_and_competitor_edits_never_reuse_a_citation(self):
        first = self.reconcile([fact()])
        store.write_json(self.did, "understanding.json", first)
        original = first["facts"][0]
        one = knowledge.copy_on_edit(self.did, original, {**original, "value": "410 litres"})
        two = knowledge.copy_on_edit(self.did, one, {**one, "value": "420 litres"})
        self.assertEqual(len({original["id"], one["id"], two["id"]}), 3)
        self.assertEqual(two["knowledge"]["override_of"], knowledge._identity(original))
        rival = fact(id="C001")
        changed = knowledge.copy_on_edit(self.did, rival, {**rival, "value": "450 litres"}, competitor=True)
        self.assertTrue(changed["id"].startswith("C"))
        self.assertNotEqual(changed["id"], "C001")

    def test_snapshot_publication_and_old_citations_are_immutable(self):
        first = self.reconcile([fact()])
        store.write_json(self.did, "understanding.json", first)
        with self.assertRaises(ValueError):
            knowledge.snapshot(self.did, publish=True)
        store.update(self.did, lambda d: d.update(approvals={c: True for c in store.CARDS}))
        snap = knowledge.snapshot(self.did, publish=True)
        first["facts"][0]["value"] = "new direct Align edit"
        store.write_json(self.did, "understanding.json", first)
        new = knowledge.snapshot(self.did)
        self.assertNotEqual(snap["id"], new["id"])
        hit = knowledge.retrieve(self.did, "luggage suitcase")
        self.assertEqual(hit["snapshot_id"], snap["id"])
        self.assertEqual(hit["evidence"][0]["value"], "400 litres")
        self.assertEqual(knowledge.retrieve(self.did, "boot", snapshot_id=snap["id"])["evidence"][0]["value"], "400 litres")

    def test_scope_approval_and_competitor_retrieval_filters(self):
        und = understanding([fact(), fact("6 airbags", claim="Airbags", approved=False)])
        und["facts"][0]["id"] = "F001"
        und["facts"][1]["id"] = "F002"
        und["competitors"] = [{"name": "Seltos", "facts": [fact("430 litres", id="C001")]}]
        store.write_json(self.did, "understanding.json", und)
        self.assertEqual(knowledge.retrieve(self.did, "boot", scope={"variant": "E"})["evidence"], [])
        self.assertEqual(len(knowledge.retrieve(self.did, "boot", scope={"variant": "SX"})["evidence"]), 1)
        self.assertEqual(len(knowledge.retrieve(self.did, "boot", competition=True)["evidence"]), 2)
        self.assertFalse(any(f["id"] == "F002" for f in knowledge.retrieve(self.did, "airbag safety")["evidence"]))

    def test_explicit_conflict_review_preserves_sources_and_survives_reread(self):
        und = self.reconcile([fact(), fact("420 litres", ref="web")])
        store.write_json(self.did, "understanding.json", und)
        decision = und["knowledge"]["conflicts"][0]
        web = und["facts"][1]
        result = knowledge.resolve_conflict(self.did, decision["id"], web["id"], note="Reviewed the current specification.")
        reviewed = result["understanding"]
        self.assertTrue(reviewed["facts"][1]["approved"])
        self.assertFalse(reviewed["facts"][0]["approved"])
        self.assertEqual(reviewed["facts"][1]["source"], web["source"])
        self.assertNotIn("excluded_by_precedence", reviewed["facts"][1]["knowledge"])
        next_read = self.reconcile([fact(), fact("420 litres", ref="web")], reviewed)
        self.assertEqual(next_read["knowledge"]["conflicts"][0]["resolution"], "human_review")
        self.assertEqual(next_read["knowledge"]["conflicts"][0]["preferred_fact_id"], web["id"])
        self.assertTrue(next_read["facts"][1]["approved"])
        with self.assertRaises(ValueError):
            knowledge.resolve_conflict(self.did, decision["id"], "F999")

    def test_human_correction_survives_unrelated_source_byte_change(self):
        first = self.reconcile([fact()])
        first["facts"][0].update(value="400 litres reviewed", edited=True)
        store.update(self.did, lambda d: d["sources"][0].update(revision="new-footer-only"))
        second = self.reconcile([fact()], first)
        self.assertEqual(second["facts"][0]["id"], first["facts"][0]["id"])
        self.assertEqual(second["facts"][0]["value"], "400 litres reviewed")
        self.assertEqual(second["facts"][0]["knowledge"]["source_revision"], "new-footer-only")

    def test_bad_snapshot_id_rejected(self):
        with self.assertRaises(ValueError):
            knowledge.retrieve(self.did, "boot", snapshot_id="../../demo")

    def test_variant_comparison_filters_and_future_offers(self):
        rows = []
        for i, variant in enumerate(("SX", "SX(O)", "E"), 1):
            item = fact(id=f"F{i:03d}")
            item["scope"].update(variant=variant, model="Hyundai CRETA")
            rows.append(item)
        future = fact(id="F004", kind="offer", claim="Boot offer", value="400 litres offer")
        future["scope"].update(effective_from="2099-01-01", effective_to="2099-02-01")
        rows.append(future)
        store.write_json(self.did, "understanding.json", understanding(rows))
        result = knowledge.retrieve(self.did, "boot", scope={"model": "Creta", "variant": ["SX", "SX(O)"]})
        self.assertEqual({f["id"] for f in result["evidence"]}, {"F001", "F002"})
        self.assertNotIn("F004", {f["id"] for f in knowledge.retrieve(self.did, "boot offer")["evidence"]})

    def test_explicit_variant_lists_are_atomic_but_relative_trim_order_is_not_inferred(self):
        grouped = fact(id="F001")
        grouped["scope"]["variant"] = "King, King Knight"
        store.write_json(self.did, "understanding.json", understanding([grouped]))
        for variant in ("King", "King Knight"):
            self.assertEqual(len(knowledge.retrieve(self.did, "boot", scope={"variant": variant})["evidence"]), 1)
        self.assertEqual(knowledge.retrieve(self.did, "boot", scope={"variant": "E"})["evidence"], [])
        self.assertEqual(knowledge.scope_values("King; King Knight", "variant"), {"king", "king knight"})
        grouped["scope"]["variant"] = "SX and above"
        self.assertFalse(knowledge.scope_matches(grouped, {"variant": "King"}))
        self.assertFalse(knowledge.scope_matches(grouped, {"variant": "SX"}))

    def test_powertrain_family_retrieval_keeps_capacity_and_technology_strict(self):
        turbo = fact(id="F001",claim="Maximum power",value="160 PS",scope={"model":"CRETA","powertrain":"1.5l Turbo GDi petrol"})
        identity = knowledge._identity(turbo)
        self.assertTrue(knowledge.scope_matches(turbo,{"powertrain":"turbo petrol"}))
        self.assertTrue(knowledge.scope_matches(turbo,{"powertrain":"1.5-litre turbo petrol"}))
        self.assertFalse(knowledge.scope_matches(turbo,{"powertrain":"2.0-litre turbo petrol"}))
        self.assertFalse(knowledge.scope_matches(turbo,{"powertrain":"diesel"}))
        self.assertFalse(knowledge.scope_matches(turbo,{"powertrain":"1.5-litre TSI turbo petrol"}))
        self.assertEqual(knowledge._identity(turbo),identity)
        store.write_json(self.did,"understanding.json",understanding([turbo]))
        self.assertEqual([f["id"] for f in knowledge.retrieve(self.did,"turbo power",scope={"powertrain":"turbo petrol"})["evidence"]],["F001"])

    def test_automatic_family_matches_explicit_transmission_only(self):
        for value in ("7-speed DCT","IVT","6-speed automatic","6 AT"):
            self.assertTrue(knowledge.scope_matches({"scope":{"transmission":value}},{"transmission":"automatic"}))
        self.assertFalse(knowledge.scope_matches({"scope":{"transmission":"6-speed manual"}},{"transmission":"automatic"}))
        self.assertFalse(knowledge.scope_matches({"scope":{}},{"transmission":"automatic"}))
        self.assertFalse(knowledge.scope_matches({"scope":{"transmission":"7-speed DCT"}},{"transmission":"8-speed automatic"}))

    def test_retrieval_deduplicates_identical_assertions_not_distinct_applicability(self):
        first=fact(id="F001");duplicate=fact(id="F002",ref="web");other=fact(id="F003");other["scope"]["variant"]="E"
        store.write_json(self.did,"understanding.json",understanding([first,duplicate,other]))
        pack=knowledge.retrieve(self.did,"boot",scope={"variant":["SX","E"]})
        self.assertEqual(len(pack["evidence"]),2)
        self.assertEqual({f["scope"]["variant"] for f in pack["evidence"]},{"SX","E"})
        self.assertEqual(len(store.read_json(self.did,"understanding.json")["facts"]),3)

    def test_parking_comparison_retrieves_standard_sensors_before_unrelated_trim_equipment(self):
        registry=json.loads((Path(__file__).parent/"fixtures/runtime_final_decisions.json").read_text())["v6_scope_registry"]["facts"]
        store.write_json(self.did,"understanding.json",understanding(registry))
        pack=knowledge.retrieve(self.did,"Compare only E and King on parking features, not other variants.",scope={"variant":["E","King"]},limit=14)
        ids={f["id"] for f in pack["evidence"]}
        self.assertTrue(ids & {"F174","F195"},ids)
        self.assertTrue({"F215","F248","F064"} <= ids,ids)
        self.assertLessEqual(len(pack["evidence"]),14)
        self.assertTrue(all(f.get("approved",True) and not f.get("knowledge",{}).get("excluded_by_precedence") for f in pack["evidence"]))
        self.assertEqual(store.read_json(self.did,"understanding.json")["facts"],registry)
        broad=knowledge.retrieve(self.did,"How is S(O) Knight different from S(O)?",scope={"variant":["S(O) Knight","S(O)"]},limit=14)
        self.assertIn("F049",{f["id"] for f in broad["evidence"]})

    def test_comfort_comparison_retrieves_reviewed_seat_differences_without_reindexing(self):
        registry=json.loads((Path(__file__).parent/"fixtures/runtime_v7_limits.json").read_text())["lineage_registry"]["facts"]
        store.write_json(self.did,"understanding.json",understanding(registry))
        snap=knowledge.snapshot(self.did)
        snap_path=store.path(self.did,f"knowledge/snapshots/{snap['id']}.json")
        index_path=store.path(self.did,f"knowledge/index/{snap['id']}.json")
        before_snapshot,before_index=snap_path.read_bytes(),index_path.read_bytes()
        pack=knowledge.retrieve(self.did,"Compare SX and SX Premium on comfort features.",snapshot_id=snap["id"],scope={"variant":["SX","SX Premium"]},limit=14)
        rows={f["id"]:f for f in pack["evidence"]}
        self.assertTrue({"F063","F160","F069","F159"}<=rows.keys())
        self.assertLessEqual(len(rows),14)
        projection=rows["F063"]["applicability_projection"]["rows"]
        self.assertTrue(any(r["polarity"]=="negative" and "SX" in r["variants"] for r in projection))
        self.assertTrue(any(r["polarity"]=="positive" and "SX Premium" in r["variants"] for r in projection))
        self.assertEqual(before_snapshot,snap_path.read_bytes())
        self.assertEqual(before_index,index_path.read_bytes())

    def test_comfort_topic_expansion_does_not_change_eligibility_or_other_topics(self):
        scope={"model":"Aster","market":"India","variant":"SX"}
        rows=[fact(id="F001",claim="Front ventilated seats",value="Ventilated front seats",scope=scope),
              fact(id="F002",claim="Climate control",value="Dual zone automatic climate control",scope=scope),
              fact(id="F003",claim="Front ventilated seats",value="Ventilated front seats",scope=scope,approved=False),
              fact(id="F004",claim="Front ventilated seats",value="Ventilated front seats",scope={**scope,"market":"Japan"}),
              fact(id="F005",claim="Front ventilated seats",value="Ventilated front seats",scope={**scope,"variant":"SX(O)"}),
              fact(id="F006",claim="Front ventilated seats",value="Ventilated front seats",scope=scope,knowledge={"excluded_by_precedence":True}),
              fact(id="F007",claim="Engine torque",value="Engine torque 250 Nm",scope=scope),
              fact(id="F008",claim="Front ventilated seats",value="Ventilated front seats",scope={**scope,"model":"Other"})]
        store.write_json(self.did,"understanding.json",understanding(rows))
        comfort=knowledge.retrieve(self.did,"Which comfort features does SX offer?",scope=scope,limit=14)
        self.assertEqual({f["id"] for f in comfort["evidence"]},{"F001","F002"})
        torque=knowledge.retrieve(self.did,"What engine torque does SX offer?",scope=scope,limit=1)
        self.assertEqual([f["id"] for f in torque["evidence"]],["F007"])
        self.assertEqual(knowledge._query_features("Compare SX on engine torque",scope),knowledge._features("engine torque"))

    def test_topic_ranking_does_not_relax_scope_or_merge_edition_names(self):
        rows=[fact(id="F001",claim="Rear parking sensors",value="Rear parking sensors",conditions="Standard on E",scope={"model":"Aster","market":"India","variant":"E"}),
              fact(id="F002",claim="Parking camera",value="Rear parking camera",scope={"model":"Aster","market":"India","variant":"E"},approved=False),
              fact(id="F003",claim="Parking camera",value="Rear parking camera",scope={"model":"Aster","market":"Japan","variant":"E"}),
              fact(id="F004",claim="Parking camera",value="Rear parking camera",scope={"model":"Aster","market":"India","variant":"Sport"}),
              fact(id="F005",claim="Parking camera",value="Rear parking camera",scope={"model":"Aster","market":"India","variant":"E"},knowledge={"excluded_by_precedence":True})]
        store.write_json(self.did,"understanding.json",understanding(rows))
        pack=knowledge.retrieve(self.did,"Which parking features does the E variant offer?",scope={"variant":"E","market":"India"},limit=14)
        self.assertEqual([f["id"] for f in pack["evidence"]],["F001"])
        for left,right in [("Sport","Sport Edition"),("King","King Knight"),("SX","SX(O)"),("S(O)","S(O) Knight"),("Lounge","Lounge Edition")]:
            self.assertFalse(knowledge.scope_matches({"scope":{"variant":left}},{"variant":right}),(left,right))
            self.assertFalse(knowledge.scope_matches({"scope":{"variant":right}},{"variant":left}),(right,left))

    def test_explicit_negative_applicability_is_retrieved_with_polarity(self):
        row=fact(id="F001",claim="Panoramic sunroof",value="Standard on King",conditions="Excludes E and EX variants",scope={"model":"CRETA","variant":"King"})
        store.write_json(self.did,"understanding.json",understanding([row]))
        pack=knowledge.retrieve(self.did,"E sunroof",scope={"variant":"E"})
        self.assertEqual(len(pack["evidence"]),1)
        projected=pack["evidence"][0]
        self.assertEqual(projected["scope"]["variant"],"King")
        self.assertEqual(projected["applicability_projection"]["rows"][0]["polarity"],"negative")
        self.assertFalse(knowledge.scope_matches(row,{"variant":"E"}))
        self.assertEqual(knowledge.retrieve(self.did,"E sunroof",scope={"variant":"E","market":"India"})["evidence"],[])

    def test_projection_uses_only_approved_literal_assertions_not_provenance_or_order(self):
        row=fact(id="F001",conditions="Not available on SX and above")
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"SX"}))
        row["conditions"]="";row["source"]["quote"]="Excludes E variants"
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"E"}))
        row["conditions"]="Excludes E variants";row["approved"]=False
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"E"}))
        store.write_json(self.did,"understanding.json",understanding([row]))
        self.assertEqual(knowledge.retrieve(self.did,"E boot",scope={"variant":"E"})["evidence"],[])

    def test_explicit_mixed_variant_clauses_never_expand_relative_order(self):
        row=fact(id="F001",claim="Air conditioning",value="Manual on E, EX; Automatic on SX and above",conditions="DATC on King, King Knight",scope={"model":"CRETA"})
        projection=knowledge.variant_projection(row,{"variant":["E","King","SX"]})
        self.assertEqual([r["variants"] for r in projection["rows"]],[["E"],["King"]])
        self.assertNotIn("SX",[v for r in projection["rows"] for v in r["variants"]])

    def test_parenthetical_matrix_preserves_exact_variant_value_pairs(self):
        row = fact(id="F049", claim="Wheel size availability", value="R16 steel (E, EX), R16 styled steel (EX(O)), R17 alloy (S(O), SX, SX Premium), R18 alloy (S(O) Knight, King, King Knight, Lounge Edition)",
                   conditions="Varies strictly by variant", scope={"model":"CRETA","market":"India"})
        identity = knowledge._identity(row)
        projection = knowledge.variant_projection(row, {"variant":["S(O)","S(O) Knight"]})
        self.assertEqual([(r["label"],r["variants"]) for r in projection["rows"]], [("R17 alloy",["S(O)"]),("R18 alloy",["S(O) Knight"])])
        exact = knowledge.variant_projection(row,{"variant":"EX"})
        self.assertEqual([r["label"] for r in exact["rows"]],["R16 steel"])
        self.assertEqual(knowledge._identity(row), identity)
        store.write_json(self.did,"understanding.json",understanding([row]))
        retrieved = knowledge.retrieve(self.did,"How is S(O) Knight different from S(O)?",scope={"variant":["S(O) Knight","S(O)"]})["evidence"]
        self.assertEqual([f["id"] for f in retrieved],["F049"])
        self.assertEqual(retrieved[0]["value"],row["value"])

    def test_matrix_projection_ignores_dimensions_held_rows_and_source_tables(self):
        row = fact(id="F001",claim="Wheels",value="205/65 R16 (D=405.6 mm) steel (E, EX)",scope={"model":"CRETA"})
        projected = knowledge.variant_projection(row,{"variant":"EX"})
        self.assertEqual(projected["rows"][0]["label"],"205/65 R16 (D=405.6 mm) steel")
        row["approved"] = False
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"EX"}))
        row["approved"] = True; row["value"] = "Equipment not specified"
        row["source"]["quote"] = "R18 alloy (E, EX)"
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"EX"}))

    def test_named_fitment_keeps_trailing_transmission_restriction(self):
        row=fact(id="F001",claim="Smart Cruise Control with Stop & Go",
                 value="Standard on King, S(O), Lounge Edition (IVT/AT/DCT only)",
                 conditions="IVT/AT/DCT transmissions only",
                 scope={"model":"Aster","market":"India","transmission":"IVT, AT, DCT"})
        identity=knowledge._identity(row)
        projection=knowledge.variant_projection(row,{"variant":"Lounge Edition"})
        self.assertEqual([(r["variants"],r["polarity"]) for r in projection["rows"]],[( ["Lounge Edition"],"positive")])
        self.assertEqual(projection["rows"][0]["assertion"],row["value"])
        self.assertEqual(knowledge.variant_projection(row,{"variant":"S(O)"})["rows"][0]["variants"],["S(O)"])
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"S"}))
        store.write_json(self.did,"understanding.json",understanding([row]))
        pack=knowledge.retrieve(self.did,"Lounge Edition cruise control",scope={"variant":"Lounge Edition","transmission":"automatic"})
        self.assertEqual([f["id"] for f in pack["evidence"]],["F001"])
        self.assertEqual(pack["evidence"][0]["conditions"],row["conditions"])
        self.assertEqual(pack["evidence"][0]["applicability_projection"]["rows"][0]["assertion"],row["value"])
        self.assertEqual(knowledge.retrieve(self.did,"Lounge Edition cruise control",scope={"variant":"Lounge Edition","transmission":"manual"})["evidence"],[])
        self.assertEqual(knowledge._identity(row),identity)

    def test_transmission_suffix_never_licenses_negative_or_inferred_fitment(self):
        row=fact(id="F001",claim="Cruise control",conditions="",scope={"model":"Aster"})
        for value in ("Not standard on Lounge Edition (IVT/AT/DCT only)",
                      "Not unavailable on Lounge Edition (IVT/AT/DCT only)",
                      "Standard on Lounge Edition and above (IVT/AT/DCT only)",
                      "Standard on Lounge Edition (not IVT/AT/DCT only)",
                      "Standard on Lounge Edition (IVT/AT/DCT only) but not confirmed"):
            row["value"]=value
            self.assertIsNone(knowledge.variant_projection(row,{"variant":"Lounge Edition"}),value)
        row["value"]="Standard on Lounge Edition (IVT/AT/DCT only)";row["approved"]=False
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"Lounge Edition"}))
        row["approved"]=True;row["source"]["quote"]=row["value"];row["value"]="Fitment unknown"
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"Lounge Edition"}))

    def test_explicit_universal_equipment_is_available_for_named_trim_retrieval(self):
        row = fact(id="F174",claim="Standard safety equipment",value="six airbags and rear parking sensors",conditions="Standard equipment across the range.",scope={"model":"CRETA","market":"India"})
        self.assertFalse(knowledge.scope_matches(row,{"variant":"SX"}))
        projection = knowledge.variant_projection(row,{"variant":"SX"})
        self.assertEqual(projection["rows"][0]["variants"],["SX"])
        self.assertIn("rear parking sensors",projection["rows"][0]["assertion"])
        store.write_json(self.did,"understanding.json",understanding([row]))
        self.assertEqual([f["id"] for f in knowledge.retrieve(self.did,"SX parking assistance",scope={"variant":"SX","market":"India"})["evidence"]],["F174"])
        self.assertEqual(knowledge.retrieve(self.did,"SX parking",scope={"variant":"SX","market":"Nigeria"})["evidence"],[])

    def test_generic_or_qualified_availability_never_becomes_universal(self):
        row = fact(id="F001",claim="Parking sensors",value="Rear parking sensors",scope={"model":"CRETA"})
        for condition in ("Selected variants only", "Not standard on all variants", "Standard on most variants", "Across the range except E", "Available from SX and above"):
            row["conditions"] = condition
            self.assertIsNone(knowledge.variant_projection(row,{"variant":"E"}),condition)
        row["conditions"] = "Standard across all variants"; row["scope"]["variant"] = "King"
        self.assertIsNone(knowledge.variant_projection(row,{"variant":"E"}))

    def test_lineup_membership_keeps_market_and_does_not_establish_equipment(self):
        row = fact(id="F192",kind="availability",claim="Available variants listed in Pune FAQ",value="E, EX, S, SX, and SX(O)",conditions="Market-specific variant listing in Pune FAQ",scope={"model":"CRETA","market":"Pune, India"})
        projection = knowledge.variant_projection(row,{"variant":"SX(O)"})
        self.assertEqual(projection["rows"][0]["variants"],["SX(O)"])
        self.assertIn("Pune FAQ",projection["rows"][0]["assertion"])
        store.write_json(self.did,"understanding.json",understanding([row]))
        found = knowledge.retrieve(self.did,"What does the source say about SX(O) lineup?",scope={"variant":"SX(O)"})["evidence"]
        self.assertEqual([f["id"] for f in found],["F192"])
        self.assertEqual(found[0]["scope"]["market"],"Pune, India")
        self.assertEqual(knowledge.retrieve(self.did,"SX(O) lineup",scope={"variant":"SX(O)","model_year":"2026"})["evidence"],[])

    def test_old_html_cache_is_reparsed_without_overwriting_old_revision(self):
        src = store.load(self.did)["sources"][1]
        revision = "a" * 64
        base = f"knowledge/sources/web/{revision}"
        old_path = base + ".json"
        store.write_json(self.did, old_path, {"text": "Old flattened table", "mime": "text/html"})
        store.path(self.did, base + ".html").write_text("<table><tr><th>Variant</th><th>Boot</th></tr><tr><td>SX</td><td>400 litres</td></tr></table>")
        src.update(revision=revision, evidence_path=old_path)
        store.update(self.did, lambda d: d["sources"][1].update(src))
        with patch.object(sources, "fetch_url", side_effect=AssertionError("must reparse stored bytes")):
            upgraded = sources.source_text(self.did, src, persist=True)
        self.assertEqual(upgraded["sections"][0]["rows"][1], ["SX", "400 litres"])
        self.assertEqual(store.read_json(self.did, old_path)["text"], "Old flattened table")
        self.assertTrue(store.load(self.did)["sources"][1]["evidence_path"].endswith(".extract-v2.json"))

    def test_pdf_layout_removes_padding_and_retains_raw_null_table_cells(self):
        from unittest.mock import MagicMock
        page = MagicMock()
        page.extract_text.return_value = "  Variant       E     EX    " + " " * 10000 + "\n\n  Airbags       6     6\n"
        page.extract_tables.return_value = [[["Variant", None, "E", "EX"], ["Airbags", None, "6", "6"]]]
        document = MagicMock()
        document.pages = [page]
        document.__enter__.return_value = document
        with patch("pdfplumber.open", return_value=document):
            result = sources.extract_pdf("fixture.pdf")
        self.assertLess(len(result["pages"][0]), 100)
        self.assertTrue(result["pages"][0].startswith("  Variant"))
        self.assertIsNone(result["sections"][0]["tables"][0][0][1])
        self.assertEqual(result["sections"][0]["tables"][0][0][2:], ["E", "EX"])

    def test_identical_uploaded_and_url_documents_extract_once(self):
        import hashlib
        from server.agents import understand
        raw = b"Fixture brochure bytes"
        path = store.path(self.did, "sources/doc.pdf")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        store.update(self.did, lambda d: d["sources"][1].update(revision=hashlib.sha256(raw).hexdigest()))
        calls = []
        def extraction(_demo, src, **kwargs):
            calls.append(src["id"])
            return {"id": src["id"], "name": src["name"], "text": "Boot capacity 400 litres", "chunks": [{"text": "Boot capacity 400 litres", "locator": "page 1"}], "pages": ["Boot capacity 400 litres"]}
        with patch.object(sources, "source_text", side_effect=extraction):
            understand.run(self.did, lambda text: None)
        self.assertEqual(calls, ["doc"])
        duplicate = store.read_json(self.did, "knowledge/coverage.json")["duplicates"][0]
        self.assertEqual((duplicate["source_id"], duplicate["canonical_source_id"]), ("web", "doc"))

    def test_extraction_cache_resumes_and_versions_inputs_without_provider_calls(self):
        from server.agents import understand
        from server import schemas
        from server.llm import mock
        calls = []
        def result():
            calls.append(True)
            return mock.fake(schemas.ImagesOut)
        with patch.object(config, "MOCK_LLM", False):
            for _ in range(2):
                understand._cached_extraction(self.did, "images", "prompt", ["byteshash"], schemas.ImagesOut, result, source_versions=["v1"])
            self.assertEqual(len(calls), 1)
            understand._cached_extraction(self.did, "images", "prompt changed", ["byteshash"], schemas.ImagesOut, result, source_versions=["v1"])
            understand._cached_extraction(self.did, "images", "prompt", ["byteshash"], schemas.ImagesOut, result, source_versions=["v2"])
            with patch.object(config, "GEMINI_MODEL", "new-vision-model"):
                understand._cached_extraction(self.did, "images", "prompt", ["byteshash"], schemas.ImagesOut, result, source_versions=["v1"])
            self.assertEqual(len(calls), 4)
            with self.assertRaises(RuntimeError):
                understand._cached_extraction(self.did, "images", "failed", [], schemas.ImagesOut, lambda: (_ for _ in ()).throw(RuntimeError("fixture outage")))
            understand._cached_extraction(self.did, "images", "failed", [], schemas.ImagesOut, result)
            self.assertEqual(len(calls), 5)

    def test_sparse_specification_table_attempts_rendered_evidence(self):
        seed = "https://example.com/in/en/creta/specification"
        store.update(self.did, lambda d: d.update(sources=[{"id": "web", "name": "Creta", "kind": "url", "url": seed}]))
        html = ("<title>Creta specifications</title><script src='/specs.js'></script><p>" + "Specifications are being prepared. " * 20 + "</p><table><tr><th>Engine</th></tr></table>").encode()
        def fetch(url, **kwargs):
            if url.endswith("robots.txt"):
                return {"text": "User-agent: *\nAllow: /", "raw": b"User-agent: *\nAllow: /"}
            if "sitemap" in url:
                return {"raw": b"<urlset></urlset>"}
            return {**crawl.parse_html(html, url), "raw": html, "final_url": url, "mime": "text/html"}
        rendered = {**crawl.parse_html("<table><tr><th>Engine</th><th>Value</th></tr><tr><td>Capacity</td><td>1497 cc</td></tr></table>" + "<p>" + "Useful details " * 80 + "</p>", seed), "raw": html, "final_url": seed, "mime": "text/html"}
        with patch.object(crawl, "render_public", return_value=rendered) as render:
            crawl.ingest(self.did, lambda text: None, fetcher=fetch)
        self.assertEqual(render.call_count, 1)
        record = store.load(self.did)["sources"][0]
        self.assertIn("1497 cc", store.read_json(self.did, record["evidence_path"])["text"])

    def test_public_url_safety(self):
        for url in ["file:///etc/passwd", "http://user:pass@example.com", "http://127.0.0.1/", "http://[::1]/", "http://169.254.169.254/", "http://224.0.0.1/", "http://[ff02::1]/", "http://example.com:8080/"]:
            with self.subTest(url=url), self.assertRaises(ValueError):
                crawl._public_address(url)
        with patch("server.crawl.socket.getaddrinfo", return_value=[(None, None, None, None, ("10.1.2.3", 443))]), self.assertRaises(ValueError):
            crawl._public_address("https://looks-public.example/")

    def test_safe_transport_pins_dns_and_revalidates_redirects(self):
        import httpx
        real_client = httpx.Client
        requested = []
        def handler(request):
            requested.append(request)
            return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})
        def address(url, *args, **kwargs):
            if "127.0.0.1" in url:
                raise ValueError("private target")
            return "example.com", "8.8.8.8"
        with patch.object(crawl, "_public_address", side_effect=address), patch.object(crawl.httpx, "Client", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw)):
            with self.assertRaises(ValueError):
                crawl.fetch_public("https://example.com/creta")
        self.assertEqual(str(requested[0].url), "https://8.8.8.8/creta")
        self.assertEqual(requested[0].headers["host"], "example.com")
        self.assertEqual(requested[0].extensions["sni_hostname"], "example.com")

    def test_html_table_footnotes_and_chunks_survive(self):
        html = "<title>Creta specs</title><h2>Boot</h2><table id='boot'><tr><th>Variant</th><th>Litres</th></tr><tr><td>SX</td><td>400</td></tr></table><p>*With rear seats raised.</p>"
        parsed = crawl.parse_html(html, "https://example.com/creta")
        table = next(s for s in parsed["sections"] if s["kind"] == "table")
        self.assertIn("Variant | Litres", table["text"])
        self.assertIn("rear seats raised", table["footnote"])
        table["rows"] *= 80
        table["text"] *= 80
        pieces = sources.chunks({"id": "web", "sections": [table]}, max_chars=200)
        self.assertGreater(len(pieces), 1)
        self.assertTrue(all("Variant | Litres" in p["text"] and "rear seats raised" in p["text"] for p in pieces))

    def test_no_silent_text_truncation(self):
        text = "alpha " * 30000 + "FINAL DOCUMENT FACT"
        parts = sources.chunks({"id": "doc", "text": text})
        self.assertIn("FINAL DOCUMENT FACT", parts[-1]["text"])
        self.assertTrue(all(len(part["text"]) <= 24000 for part in parts))

    def test_actual_creta_seed_excludes_slogans_other_markets_and_other_models(self):
        seed = "https://www.hyundai.com/in/en/find-a-car/creta/highlights"
        demo = {"name": "Hyundai CRETA • Explore your everyday upgrade", "product": {"name": "Hyundai CRETA • Explore your everyday upgrade"}}
        tokens = crawl._model_tokens({"url": seed, "role": "product"}, demo)
        self.assertEqual(tokens, ["creta"])
        for path in ["/worldwide/en/brand-journal/ioniq/garden", "/worldwide/en/brand-journal/lifestyle/explore-your-everyday", "/gd/en/creta-su2id-r", "/et/en/creta", "/ng/en/creta-2021", "/in/en/find-a-car/creta-electric/highlights", "/in/en/find-a-car/venue/highlights"]:
            self.assertFalse(crawl._eligible("https://www.hyundai.com" + path, "Explore your everyday Creta upgrade", seed, tokens), path)
        self.assertTrue(crawl._eligible("https://www.hyundai.com/in/en/find-a-car/creta/specification", "Specifications", seed, tokens))
        self.assertTrue(crawl._eligible("https://www.hyundai.com/content/dam/hyundai/in/en/data/brochure/creta-brochure.pdf", "Creta brochure", seed, tokens))
        self.assertFalse(crawl._eligible("https://www.hyundai.com/ng/en/creta-brochure.pdf", "Creta brochure", seed, tokens))
        self.assertFalse(crawl._eligible("https://www.hyundai.com/worldwide/creta-brochure.pdf", "Creta brochure", seed, tokens))

    def test_prior_foreign_crawl_children_are_deactivated_on_next_ingest(self):
        seed = "https://www.hyundai.com/in/en/find-a-car/creta/highlights"
        bad = {"id": "foreign", "kind": "url", "url": "https://www.hyundai.com/ng/en/creta-2021", "name": "Creta", "crawl_parent": "seed", "evidence_path": "knowledge/old.json", "crawl_active": True}
        store.update(self.did, lambda d: d.update(name="Hyundai CRETA • Explore your everyday upgrade", sources=[{"id": "seed", "kind": "url", "url": seed}, bad]))
        def fake(url, **kwargs):
            if url.endswith("robots.txt"):
                return {"text": "User-agent: *\nAllow: /"}
            if url.endswith("sitemap.xml"):
                return {"raw": b"<urlset/>"}
            html = "<p>" + "Readable Creta source evidence. " * 30 + "</p>"
            return {"raw": html.encode(), "mime": "text/html", "final_url": url, **crawl.parse_html(html, url)}
        coverage = crawl.ingest(self.did, fetcher=fake)
        old = next(s for s in store.load(self.did)["sources"] if s["id"] == "foreign")
        self.assertFalse(old["crawl_active"])
        self.assertTrue(old["scope_excluded"])
        self.assertFalse(coverage["seeds"][0]["retained"])
        self.assertTrue(any("Earlier crawl excluded" in s["reason"] for s in coverage["seeds"][0]["skipped"]))

    def test_document_redirect_cannot_escape_model_market_scope(self):
        seed = "https://www.hyundai.com/in/en/find-a-car/creta/highlights"
        brochure = "https://www.hyundai.com/content/dam/hyundai/in/en/data/brochure/creta.pdf"
        foreign = "https://www.hyundai.com/content/dam/hyundai/ng/en/data/brochure/creta.pdf"
        store.update(self.did, lambda d: d.update(sources=[{"id": "web", "name": "Creta", "kind": "url", "url": seed}]))
        def fake(url, **kwargs):
            if url.endswith("robots.txt"):
                return {"text": "User-agent: *\nAllow: /"}
            if "sitemap" in url:
                return {"raw": b"<urlset/>"}
            if url == brochure:
                return {"raw": b"foreign PDF fixture", "mime": "application/pdf", "final_url": foreign, "title": "Creta", "text": "Foreign market specifications", "sections": [], "links": []}
            html = "<p>" + "Readable India Creta source. " * 30 + f"</p><a href='{brochure}'>Creta brochure</a>"
            return {"raw": html.encode(), "mime": "text/html", "final_url": url, **crawl.parse_html(html, url)}
        report = crawl.ingest(self.did, fetcher=fake)
        self.assertTrue(any("Redirect left" in row["reason"] for row in report["seeds"][0]["blocked"]))
        self.assertFalse(any(s.get("final_url") == foreign for s in store.load(self.did)["sources"]))

    def test_crawl_budget_model_scope_and_coverage(self):
        seed = "https://example.com/creta"
        store.update(self.did, lambda d: d.update(sources=[{"id": "web", "name": "Creta", "kind": "url", "url": seed}]))
        seen = []
        def fake(url, **kwargs):
            seen.append(url)
            if url.endswith("robots.txt"):
                return {"text": "User-agent: *\nDisallow: /creta/private\nSitemap: https://example.com/sitemap.xml"}
            if url.endswith("sitemap.xml"):
                return {"raw": b"<urlset><url><loc>https://example.com/creta/safety</loc></url><url><loc>https://example.com/tucson</loc></url></urlset>"}
            html = "<title>Creta</title><p>" + "Readable model evidence. " * 30 + "</p><a href='/creta/interior'>Creta interior</a><a href='/creta/private'>Creta private</a><a href='/tucson'>Tucson</a>"
            return {"raw": html.encode(), "mime": "text/html", "final_url": url, **crawl.parse_html(html, url)}
        with patch.object(crawl, "render_public", side_effect=AssertionError("unneeded rendering")):
            report = crawl.ingest(self.did, budget={"html_pages": 1}, fetcher=fake)
        self.assertEqual(report["used"]["html_pages"], 1)
        self.assertFalse(report["complete"])
        self.assertTrue(report["seeds"][0]["deferred"])
        self.assertNotIn("https://example.com/tucson", seen)
        self.assertTrue(store.load(self.did)["sources"][0]["revision"])
        cached = sources.source_text(self.did, store.load(self.did)["sources"][0])
        self.assertIn("Readable model evidence", cached["text"])

    def test_bounded_continuation_retains_prior_revision_with_visible_freshness_gap(self):
        seed = "https://example.com/creta"
        store.update(self.did, lambda d: d.update(sources=[{"id": "web", "name": "Creta", "kind": "url", "url": seed}]))
        def fake(url, **kwargs):
            if url.endswith("robots.txt"):
                return {"text": "User-agent: *\nAllow: /"}
            if url.endswith("sitemap.xml"):
                return {"raw": b"<urlset/>"}
            html = "<p>" + "Readable source evidence. " * 30 + "</p><a href='/creta/interior'>Creta interior</a>"
            return {"raw": html.encode(), "mime": "text/html", "final_url": url, **crawl.parse_html(html, url)}
        crawl.ingest(self.did, budget={"html_pages": 2}, fetcher=fake)
        child = next(s for s in store.load(self.did)["sources"] if s.get("crawl_parent"))
        before = store.path(self.did, child["evidence_path"]).read_bytes()
        coverage = crawl.ingest(self.did, budget={"html_pages": 1}, fetcher=fake)
        retained = next(s for s in store.load(self.did)["sources"] if s["id"] == child["id"])
        self.assertTrue(retained["crawl_active"] and retained["crawl_cached"])
        self.assertTrue(coverage["seeds"][0]["retained"])
        self.assertFalse(coverage["complete"])
        self.assertEqual(before, store.path(self.did, child["evidence_path"]).read_bytes())
        self.assertTrue(any("freshness" in text for text in sources.source_text(self.did, retained)["warnings"]))

    def test_crawl_does_not_reuse_failed_stale_pages(self):
        store.update(self.did, lambda d: d.update(sources=[{"id": "web", "kind": "url", "url": "https://example.com/creta", "revision": "old"}]))
        def failed(url, **kwargs):
            raise RuntimeError("blocked")
        report = crawl.ingest(self.did, fetcher=failed)
        self.assertFalse(store.load(self.did)["sources"][0]["crawl_active"])
        self.assertTrue(report["seeds"][0]["blocked"])

    def test_runtime_lookup_preserves_final_url_table_header_and_footnote(self):
        from server.runtime_tools import source_lookup
        section = {"locator": "boot-table", "heading": "Boot capacity", "kind": "table", "rows": [["Variant", "Litres"], ["SX", "400"]],
                   "footnote": "Seats raised", "text": "Variant | Litres\nSX | 400\nFootnote: Seats raised"}
        page = {"url": "https://example.com/creta", "final_url": "https://example.com/creta/specs", "sections": [section], "links": [], "fetched_at": 123}
        with patch.object(crawl, "fetch_public", return_value=page):
            result = source_lookup({"tool": "source_lookup", "url": page["url"], "query": "boot capacity"}, "Check " + page["url"], [])
        evidence = result["evidence"][0]
        self.assertEqual(evidence["source"]["ref"], page["final_url"])
        self.assertEqual(evidence["source"]["locator"], "boot-table")
        self.assertEqual(evidence["source"]["quote"], section["text"])
        self.assertEqual(evidence["context"]["rows"], section["rows"])
        self.assertTrue(evidence["scope_unverified"])

    def test_runtime_lookup_rejects_unrelated_and_oversized_sections(self):
        from server.runtime_tools import source_lookup
        request = {"tool": "source_lookup", "url": "https://example.com/creta", "query": "boot capacity"}
        for passage in ["Our company was founded long ago and has many employees.", "boot capacity " * 2000]:
            with patch.object(crawl, "fetch_public", return_value={"text": passage, "final_url": request["url"]}), self.assertRaises(ValueError):
                source_lookup(request, "Check " + request["url"], [])

    def test_runtime_lookup_reads_only_two_relevant_same_host_children(self):
        from server.runtime_tools import source_lookup
        seed = "https://example.com/creta"
        called = []
        def fake(url, **kwargs):
            called.append(url)
            self.assertEqual(kwargs["allowed_hosts"], {"example.com"})
            self.assertLessEqual(kwargs["timeout"], 5)
            return {"final_url": url, "sections": [{"text": "Boot capacity details preserve the original specification context.", "locator": "boot", "kind": "text"}],
                    "links": [{"url": "https://example.com/creta/boot-one", "label": "Boot details"},
                              {"url": "https://example.com/creta/boot-two", "label": "Boot sizes"},
                              {"url": "https://example.com/creta/boot-three", "label": "Boot further detail"},
                              {"url": "https://other.example/creta/boot", "label": "Boot comparison"},
                              {"url": "https://example.com/careers", "label": "Careers"}]}
        with patch.object(crawl, "fetch_public", side_effect=fake):
            result = source_lookup({"tool": "source_lookup", "url": seed, "query": "boot"}, "Check " + seed, [])
        self.assertEqual(len(called), 3)
        self.assertTrue(all(url.startswith("https://example.com/") for url in called))
        self.assertTrue(any("unvisited" in warning for warning in result["coverage"]))

    def test_actual_local_renderer_uses_only_fake_safe_fetch(self):
        if not Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists():
            self.skipTest("Installed Chrome unavailable")
        requested = []
        html = b"<title>Creta dynamic specs</title><script src='/specs.js'></script><h1>Creta</h1>"
        script = b"document.addEventListener('DOMContentLoaded',()=>{const p=document.createElement('p');p.textContent='DYNAMIC SPEC: Boot capacity 400 litres with rear seats raised.';document.body.appendChild(p);fetch('http://127.0.0.1/private').catch(()=>{});});"
        def fake(url, **kwargs):
            requested.append(url)
            return {"raw": script if url.endswith("specs.js") else html,
                    "mime": "application/javascript" if url.endswith("specs.js") else "text/html"}
        result = crawl.render_public("https://example.com/creta", timeout=12, fetcher=fake)
        self.assertIn("DYNAMIC SPEC: Boot capacity", result["text"])
        self.assertTrue(any("127.0.0.1" in u for u in result["render"]["blocked"]))
        self.assertFalse(any("127.0.0.1" in u for u in requested))

    def test_actual_local_ocr_of_image_only_pdf(self):
        import shutil
        from PIL import Image, ImageDraw, ImageFont
        if not shutil.which("pdftoppm") or not shutil.which("tesseract"):
            self.skipTest("Local OCR tools unavailable")
        image = Image.new("RGB", (1800, 700), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 72)
        draw.text((90, 200), "BOOT CAPACITY 400 LITRES", fill="black", font=font)
        path = Path(self.tmp.name) / "scanned.pdf"
        image.save(path, "PDF", resolution=150)
        pages = sources.pdf_pages(path)
        self.assertFalse(pages[0].strip())
        pages, report = sources.ocr_pdf_pages(path, pages, max_ocr_pages=1, timeout=20)
        self.assertIn("400", pages[0])
        self.assertEqual(report[0]["status"], "extracted")
        self.assertTrue(report[0]["review_required"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
