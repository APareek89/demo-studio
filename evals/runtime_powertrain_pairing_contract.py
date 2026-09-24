"""Captured collective gearbox overclaim: offline guard, repair and cache regression."""
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

_TMP = tempfile.TemporaryDirectory(prefix="runtime-powertrain-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", DEMO_STUDIO_DATA=_TMP.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(_TMP.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
OUTBOUND = []
def blocked(*args, **kwargs):
    OUTBOUND.append(True)
    raise AssertionError("Powertrain contracts forbid outbound calls")
socket.socket.connect = socket.socket.connect_ex = socket.create_connection = blocked

from server import runtime_graph as graph, knowledge, store
from server.agents import faq
from server.runtime_state import TurnControl
from server.runtime_facts import unsupported_powertrain_pairing as unsafe

FIXTURE = json.loads((Path(__file__).parent / "fixtures/runtime_powertrain_pairing.json").read_text())
BAD = " ".join(row["text"] for row in FIXTURE["repaired_rows"])

def decision(text, ids=None):
    return {"action":"answer", "sentences":[{"text":text, "fact_ids":ids or ["F150"], "kind":"fact"}]}

class PowertrainPairing(unittest.TestCase):
    def setUp(self):
        self.facts = copy.deepcopy(FIXTURE["facts"])

    def tearDown(self):
        self.assertEqual(OUTBOUND, [])

    def check(self, candidate, facts=None):
        return graph.validate_decision(candidate, facts or self.facts, FIXTURE["question"], audience="expert")

    def test_actual_repaired_rows_reject_collective_manual_but_keep_engine_list(self):
        result, errors = self.check({"action":"answer", "sentences":FIXTURE["repaired_rows"]})
        self.assertIn("unsupported_powertrain_pairing", errors)
        self.assertIn("turbo petrol engine", result["answer"])
        self.assertNotIn("pair them", result["answer"])

    def test_actual_cached_whole_answer_rejects_same_overclaim(self):
        result, errors = self.check(decision(BAD, ["F149", "F150"]))
        self.assertIn("unsupported_powertrain_pairing", errors)
        self.assertFalse(result["answered"])

    def test_original_specific_gearbox_row_passes_without_failed_quantity_row(self):
        result, errors = self.check({"action":"answer", "sentences":[FIXTURE["original_rows"][1]]})
        self.assertFalse(errors)
        self.assertEqual(result["answer"], FIXTURE["original_rows"][1]["text"])

    def test_bad_repair_is_rejected_once_and_original_valid_pairing_is_retained(self):
        state = {"demo_id":"fixture", "session_id":"fixture", "turn_id":"t1", "question":FIXTURE["question"],
                 "decision":{"action":"answer", "sentences":FIXTURE["original_rows"]}, "evidence":self.facts,
                 "control":TurnControl(time.monotonic()+12), "errors":[], "tool_results":[]}
        with patch.object(graph.config, "MOCK_LLM", False), \
             patch.object(graph.runtime, "structured", return_value=graph._CompositionRepair(sentences=FIXTURE["repaired_rows"])) as model, \
             patch.object(graph.store, "read_json", return_value={}), patch.object(graph.usage, "trace"):
            final = asyncio.run(graph.validate(state))["result"]
        self.assertEqual(model.call_count, 1)
        self.assertIn("unsupported_powertrain_pairing", final["validation_repair"]["validation_errors"])
        self.assertFalse(final["validation_repair"]["accepted"])
        self.assertIn("petrol and diesel engines", final["answer"])
        self.assertNotIn("pair them", final["answer"])

    def test_shared_options_keep_petrol_and_diesel_bound_separately_from_turbo(self):
        for text in (
            "The petrol and diesel each offer a manual or automatic; the turbo petrol has a DCT.",
            "The regular petrol and diesel both come with a manual or automatic, and a dual-clutch automatic is offered for the turbo petrol.",
            "The non-turbo petrol and diesel both have a manual or automatic.",
            "The naturally aspirated petrol and diesel each have a manual or automatic.",
        ):
            with self.subTest(text=text):
                self.assertFalse(unsafe(text, self.facts))
                _, errors = self.check(decision(text))
                self.assertFalse(errors)

    def test_named_collective_cannot_borrow_manual_from_other_engine(self):
        for text in (
            "The petrol, diesel and turbo petrol engines all offer a manual or automatic.",
            "The petrol, diesel, and turbo petrol engines each offer a manual or automatic.",
            "The petrol, diesel, and turbo petrol engines offer a manual or automatic.",
            "The petrol and turbo petrol both have a manual or automatic.",
            "All engines are available with a manual or automatic.",
            "The diesel and turbo petrol each have an IVT automatic.",
        ):
            with self.subTest(text=text): self.assertTrue(unsafe(text, self.facts))

    def test_automatic_family_is_valid_for_all_three_but_not_each_named_family(self):
        prefix = FIXTURE["repaired_rows"][0]["text"]
        for gearbox in ("an automatic", "a manual", "an IVT automatic", "a dual-clutch automatic"):
            with self.subTest(gearbox=gearbox):
                self.assertEqual(unsafe(prefix+" They each come with "+gearbox+".", self.facts), gearbox != "an automatic")

    def test_single_engine_and_explicit_negative_claims_do_not_trigger_collective_guard(self):
        for text in ("The turbo petrol is not offered with a manual.", "The petrol offers a manual.",
                     "The diesel has a manual.", "The petrol and diesel do not both offer a DCT."):
            with self.subTest(text=text): self.assertFalse(unsafe(text, self.facts))

    def test_granular_approved_claim_identity_can_bind_its_gearbox_value(self):
        facts = [{"id":"F080", "claim":"1.5 l MPi petrol transmission options", "value":"6-speed manual or IVT", "approved":True},
                 {"id":"F084", "claim":"1.5 l U2 CRDi diesel transmission options", "value":"6-speed manual or 6-speed automatic", "approved":True}]
        self.assertFalse(unsafe("The petrol and diesel both offer a manual or automatic.", facts))
        facts.append({"id":"F088", "claim":"1.5 l Turbo GDi petrol transmission options", "value":"7-speed DCT", "approved":True})
        self.assertFalse(unsafe("The petrol, diesel and turbo petrol engines are all available with an automatic.", facts))
        self.assertTrue(unsafe("The petrol, diesel and turbo petrol engines are all available with a manual.", facts))
        facts[1]["claim"] = "Transmission options"
        facts[1]["source"] = {"quote":"Diesel transmission options"}
        self.assertTrue(unsafe("The petrol and diesel both offer a manual or automatic.", facts))

    def test_all_engines_does_not_shrink_to_one_previous_negative_engine_mention(self):
        self.assertTrue(unsafe("The turbo petrol does not have a manual, but all three engines offer a manual or automatic.", self.facts))

    def test_generic_non_automotive_pairing_and_separate_option_lists_are_unchanged(self):
        for text in ("The speaker and display are paired with voice control.",
                     "Manual and automatic gearboxes are available.",
                     "Engine options include petrol and diesel. Gearbox options include manual and automatic."):
            with self.subTest(text=text): self.assertFalse(unsafe(text, self.facts))

    def test_automatic_climate_and_manual_seat_adjectives_are_not_transmission_claims(self):
        for text, fact in (
            ("The petrol and diesel models have automatic climate control.", {"claim":"Petrol and diesel climate-control options", "value":"Automatic climate control"}),
            ("The petrol and turbo petrol both have manual seats.", {"claim":"Seat adjustment for petrol and turbo petrol", "value":"Manual seat adjustment"}),
            ("The petrol and diesel both have automatic headlamps.", {"claim":"Petrol and diesel lighting", "value":"Automatic headlamps"}),
        ):
            with self.subTest(text=text):
                self.assertFalse(unsafe(text, [{"id":"F1", "approved":True, **fact}]))
                self.assertFalse(unsafe(text, self.facts))

    def test_source_quote_or_uncertain_negative_mapping_never_licenses_shared_choices(self):
        text = "The petrol and turbo petrol both have a manual or automatic."
        for value in ("Engine options include petrol and turbo petrol. Gearbox options include manual and automatic.",
                      "Manual or automatic for the petrol; no manual for the turbo petrol.",
                      "Manual or automatic for the petrol; manual or automatic for the turbo petrol is unconfirmed."):
            fact = {**self.facts[1], "value":value, "source":{"quote":"Manual or automatic for the petrol and turbo petrol."}}
            with self.subTest(value=value): self.assertTrue(unsafe(text, [fact]))

    def test_held_or_conflicted_mapping_never_licenses_shared_choices(self):
        text = "The petrol and diesel each offer a manual or automatic."
        for changes in ({"approved":False}, {"knowledge":{"excluded_by_precedence":True}},
                        {"knowledge":{"conflict_status":"suppressed"}}, {"knowledge":{"conflict_status":"unresolved"}}):
            with self.subTest(changes=changes): self.assertTrue(unsafe(text, [{**self.facts[1], **changes}]))

    def test_pronoun_uses_immediately_accepted_engine_list_and_cannot_borrow_its_citations(self):
        previous = {"text":"The petrol and diesel are offered.", "facts":self.facts}
        text = "You can pair them with a manual or automatic."
        self.assertFalse(unsafe(text, self.facts, previous))
        self.assertTrue(unsafe(text, [self.facts[0]], previous))
        previous["text"] = FIXTURE["repaired_rows"][0]["text"]
        self.assertTrue(unsafe(text, self.facts, previous))

    def test_rejected_lead_row_does_not_supply_a_collective_antecedent(self):
        # The original model's unsupported numeral rejects the lead row. The
        # guard must not borrow that row as accepted product evidence.
        candidate = {"action":"answer", "sentences":[FIXTURE["original_rows"][0], FIXTURE["original_rows"][1]]}
        result, errors = self.check(candidate)
        self.assertEqual(errors, ["unsupported_quantity"])
        self.assertIn("petrol and diesel engines", result["answer"])

    def seed_cache(self, text):
        did = store.new_demo("Isolated gearbox cache regression")["id"]
        store.write_json(did, "understanding.json", {"product":{"name":"Creta", "category":"Car"}, "facts":self.facts, "unknowns":[], "images":[], "shots":[]})
        store.update(did, lambda demo: demo["settings"].update(audience="expert"))
        sid = knowledge.snapshot(did)["id"]
        fingerprint = faq._registry_hash(did, snapshot_id=sid)
        # Reproduce a pre-fix cache entry through the same storage API. The
        # captured response was accepted by the old validator, as the red run shows.
        entry = faq.cache_answer(did, FIXTURE["question"], {"answer":text, "answered":True,
            "fact_ids":["F149", "F150"], "facts":self.facts, "validation_errors":[], "tool_results":[]},
            snapshot_id=sid, registry_hash=fingerprint, session_id="pre-fix")
        self.assertIsNotNone(entry)
        return did, sid, fingerprint, entry

    def test_existing_bad_cache_hit_falls_through_before_count_or_audio_even_if_reviewed(self):
        for reviewed in (False, True):
            did, sid, fingerprint, entry = self.seed_cache(BAD)
            if reviewed: faq.review_entry(did, entry["id"], action="approve")
            async def fake_graph(state, config):
                return await graph.delivery_plan({**state, "result":{"answer":"I'm having trouble checking that right now.",
                    "answered":False, "fact_ids":[], "from_bank":False, "provider_failed":True}})
            with patch.object(graph.graph, "ainvoke", side_effect=fake_graph) as runner, \
                 patch.object(graph.voice, "_cached", side_effect=AssertionError("Unsafe cached audio must not be consulted")):
                output = asyncio.run(graph.run_turn(did, {"question":FIXTURE["question"], "snapshot_id":sid, "session_id":"next"}))
            self.assertEqual(runner.call_count, 1)
            self.assertFalse(output["result"]["from_bank"])
            saved = faq.match(did, FIXTURE["question"], snapshot_id=sid, registry_hash=fingerprint)
            self.assertEqual(saved["asked_count"], 1)
            self.assertEqual(saved["answer"], BAD)

    def test_safe_existing_cache_still_returns_verbatim_before_graph_and_counts(self):
        text = FIXTURE["original_rows"][1]["text"]
        did, sid, fingerprint, _ = self.seed_cache(text)
        with patch.object(graph.graph, "ainvoke", side_effect=AssertionError("Safe cache must precede graph")):
            output = asyncio.run(graph.run_turn(did, {"question":FIXTURE["question"], "snapshot_id":sid, "session_id":"next"}))
        self.assertTrue(output["result"]["from_bank"])
        self.assertEqual(output["result"]["answer"], text)
        self.assertEqual(faq.match(did, FIXTURE["question"], snapshot_id=sid, registry_hash=fingerprint)["asked_count"], 2)

    def test_failed_repair_partial_is_not_newly_cached(self):
        did, sid, fingerprint, _ = self.seed_cache("The petrol and diesel each offer a manual or automatic.")
        result, errors = self.check({"action":"answer", "sentences":FIXTURE["repaired_rows"]})
        result.update(validation_errors=errors, validation_repair={"attempted":True, "accepted":False})
        self.assertIsNone(faq.cache_answer(did, "Can each engine have a manual?", result, snapshot_id=sid, registry_hash=fingerprint, session_id="new"))

if __name__ == "__main__":
    run = unittest.main(exit=False, verbosity=2)
    print("OUTBOUND_SOCKET_ATTEMPTS="+str(len(OUTBOUND)))
    raise SystemExit(0 if run.result.wasSuccessful() and not OUTBOUND else 1)
