"""CR50 actual comfort input through production retrieval, with no network/writes."""
import asyncio
import copy
import json
import os
from pathlib import Path
import socket
import time
import unittest
from unittest.mock import patch

os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0")
outbound = []
def no_network(*args, **kwargs):
    outbound.append(1)
    raise AssertionError("Universal-scope checks forbid outbound calls")
socket.socket.connect = no_network
socket.socket.connect_ex = no_network
socket.create_connection = no_network

from server import knowledge, runtime_graph as graph
from server.runtime_state import TurnControl

HERE = Path(__file__).parent / "fixtures"
ACTUAL = json.loads((HERE / "runtime_universal_scope.json").read_text())
REGISTRY = json.loads((HERE / "runtime_transmission_conditions.json").read_text())["registry"]

class UniversalScope(unittest.TestCase):
    def test_actual_profile_drops_only_universal_variant_scope(self):
        profile = copy.deepcopy(ACTUAL["profile"])
        scope = graph.explicit_scope(ACTUAL["question"], REGISTRY, profile)
        self.assertEqual(scope, {"model": "CRETA"})
        self.assertEqual(profile, ACTUAL["profile"])

    def test_actual_production_retrieval_recovers_comfort_evidence_without_writes(self):
        sid = ACTUAL["provenance"]["snapshot_id"]
        snap = {"id": sid, "facts": copy.deepcopy(REGISTRY), "product": {"name": "CRETA"}, "sources": []}
        memory = {"knowledge/snapshots/"+sid+".json": snap}
        # Build a disposable in-memory index via the real index builder. Nothing
        # is installed into the demo, and production retrieval still ranks it.
        with patch.object(knowledge.store, "write_json", side_effect=lambda d,p,v: memory.__setitem__(p,v)):
            knowledge._write_index("fixture", snap)
        def read(demo, path): return memory.get(path)
        history = ACTUAL["history"]
        previous = [str(m.get("text", "")) for m in history if m.get("role") == "user"][-2:]
        query = ACTUAL["question"]+" "+" ".join(previous)
        with patch.object(graph.store, "read_json", side_effect=read), patch.object(graph.store, "load", return_value={"settings": {}}), \
             patch.object(graph.store, "write_json", side_effect=AssertionError("No persistent write")):
            old = knowledge.retrieve("fixture", query, snapshot_id=sid, scope=ACTUAL["original_requested_scope"], limit=14)
            state = {"demo_id": "fixture", "snapshot_id": sid, "question": ACTUAL["question"], "profile": copy.deepcopy(ACTUAL["profile"]),
                     "history": history, "control": TurnControl(time.monotonic()+12)}
            new = asyncio.run(graph.retrieve(state))
        self.assertEqual({f["id"] for f in old["evidence"]}, {"F214", "F237"})
        self.assertTrue({"F097", "F096"} <= {f["id"] for f in new["evidence"]})
        self.assertEqual(new["requested_scope"], {"model": "CRETA"})
        self.assertLessEqual(len(new["evidence"]), 14)
        self.assertEqual(new["snapshot_id"], sid)

    def test_current_explicit_universal_question_is_preserved(self):
        for question in ("Are rear AC vents standard on every trim?", "Which features are on all variants?", "What is standard across the range?"):
            with self.subTest(question=question):
                self.assertEqual(graph.explicit_scope(question, REGISTRY, ACTUAL["profile"])["variant"], "all variants")

    def test_explicit_quantified_followup_retains_universal_request(self):
        for question in ("And do all of them have rear AC vents?", "Is that included on each of those?"):
            self.assertEqual(graph.explicit_scope(question, REGISTRY, ACTUAL["profile"])["variant"], "all variants")
        self.assertNotIn("variant", graph.explicit_scope("And what does that same page show about rear AC vents?", REGISTRY, ACTUAL["profile"]))

    def test_named_trim_and_exact_comparison_remain_customer_context(self):
        for selected in ("King", ["E", "King"]):
            profile = {"scope": {"model": "CRETA", "variant": selected}}
            self.assertEqual(graph.explicit_scope("What rear-seat comfort features are documented?", REGISTRY, profile)["variant"], selected)
        self.assertEqual(graph.explicit_scope("Compare E and King.", REGISTRY, ACTUAL["profile"])["variant"], ["E", "King"])

    def test_universal_tokens_do_not_become_named_trim_identifiers(self):
        self.assertEqual(graph._requested_variants("Which features are standard on every trim?", ["E", "King"], {"variant": "all variants"}), [])
        self.assertEqual(graph._requested_variants("What rear-seat comfort features and trim conditions apply?", ["E", "King"], {"variant": "all variants"}), [])

    def test_model_correction_clears_previous_trim_and_preserves_current_universal_intent(self):
        registry = [*REGISTRY, {"id": "other", "scope": {"model": "Aurora"}}]
        prior = {"scope": {"model": "CRETA", "variant": "King", "transmission": "DCT"}}
        result = graph.explicit_scope("Actually, switch to Aurora. What comfort features does it offer?", registry, prior)
        self.assertEqual(result, {"model": "Aurora"})
        result = graph.explicit_scope("Switch to Aurora. What is standard on all variants?", registry, prior)
        self.assertEqual(result, {"model": "Aurora", "variant": "all variants"})

    def test_unknown_trim_stays_a_restrictive_literal_scope(self):
        result = graph.explicit_scope("Actually, I meant the ZZ trim.", REGISTRY, ACTUAL["profile"])
        self.assertEqual(result["variant"], "ZZ")

if __name__ == "__main__":
    run = unittest.main(exit=False)
    print("OUTBOUND_SOCKET_ATTEMPTS="+str(len(outbound)))
    raise SystemExit(0 if run.result.wasSuccessful() and not outbound else 1)
