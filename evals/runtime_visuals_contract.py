"""Free published-picture retrieval checks; isolated files, no model/network calls."""
import asyncio
import copy
import os
import socket
import tempfile
import time
import unittest
from unittest.mock import patch

_tmp = tempfile.TemporaryDirectory(prefix="runtime-visuals-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local",
                  DEMO_STUDIO_DATA=_tmp.name + "/demos", DEMO_STUDIO_GRAPH_DB=_tmp.name + "/graph.sqlite")

from server import knowledge, runtime_graph as rg, runtime_visuals as rv, store
from server.agents import faq
from server.runtime_state import TurnControl, TurnDecision


class PublishedPictures(unittest.TestCase):
    def setUp(self):
        self.network = [patch.object(socket.socket, method, side_effect=AssertionError("Network forbidden"))
                        for method in ("connect", "connect_ex", "sendto")]
        for guard in self.network:
            guard.start()
        self.addCleanup(lambda: [guard.stop() for guard in reversed(self.network)])
        self.did = store.new_demo("Contract car")["id"]
        self.facts = [
            {"id": "F001", "claim": "Cabin seating", "value": "Six seats include two individual second-row seats.", "approved": True,
             "source": {"ref": "src_doc", "quote": "Six seats include two individual second-row seats.", "locator": "p1"}},
            {"id": "F002", "claim": "Driving Assistant", "value": "Driving Assistant includes Lane Change Warning.", "approved": True,
             "source": {"ref": "src_doc", "quote": "Driving Assistant includes Lane Change Warning.", "locator": "p2"}},
        ]
        store.write_json(self.did, "understanding.json", {"product": {"name": "Contract car"}, "facts": self.facts})
        store.write_json(self.did, "plan.json", {"voice": {"persona_name": "Guide", "tone": "warm"}, "segments": [], "ctas": []})
        store.update(self.did, lambda d: d["approvals"].update({card: True for card in store.CARDS}))
        self.pin = knowledge.snapshot(self.did, publish=True)["id"]
        def media(iid, line=0, proxy=False):
            path = store.path(self.did, "sources", iid + ".jpg")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"contract-image")
            return {"image_id": iid, "image_url": f"/media/{self.did}/sources/{iid}.jpg", "from_line": line, "proxy": proxy}
        def label(cid, text, fid, iid, line=0):
            return {"id": cid, "text": text, "fact_ids": [fid], "image_id": iid, "reveal_on_line": line,
                    "anchor": {"x": .3, "y": .4}, "part_box": {"x": .2, "y": .3, "w": .2, "h": .2}}
        self.bundle = {"version": 1, "knowledge_snapshot_id": self.pin, "runtime": {"version": 1}, "slides": [
            {"id": "sl1", "kind": "outcome", "title": "Overview", "fact_ids": ["F002"], "media": [media("im1", proxy=True)],
             "callouts": [label("c1", "Driving Assistant lane support", "F002", "im1")]},
            {"id": "sl2", "kind": "proof", "title": "Driving Assistant features", "fact_ids": ["F002"], "media": [media("im2", proxy=True)],
             "callouts": [label("c2", "Lane Change Warning", "F002", "im2")]},
            {"id": "sl3", "kind": "proof", "title": "Explore the six-seat cabin", "fact_ids": ["F001"], "media": [media("im3"), media("im4", 1)],
             "callouts": [label("c3", "Third-row seating", "F001", "im3"), label("c4", "Two individual second-row seats", "F001", "im4", 1)]},
        ]}
        store.write_json(self.did, "bundle.json", self.bundle)

    def select(self, **kw):
        return rv.select(self.did, self.bundle, **dict(snapshot_id=self.pin, demo_version=1,
            question="Tell me about lane change", current_id="sl1", evidence=self.facts, fact_ids=["F002"], **kw))

    def test_specific_picture_beats_current_generic_summary(self):
        result = self.select()
        self.assertEqual((result["slide_id"], result["visual"]["ref"], result["route"]), ("sl2", "im2", "jump"))

    def test_pure_show_picks_matching_second_photo_and_bound_line(self):
        result = rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
            question="Show me the second-row seats", current_id="sl3", evidence=self.facts, visual_only=True)
        self.assertEqual((result["route"], result["visual"]["ref"], result["callout_id"], result["visual"]["line_index"]), ("stay", "im4", "c4", 1))

    def test_lookup_never_changes_reviewed_coordinates_or_bundle(self):
        before = copy.deepcopy(self.bundle)
        result = self.select()
        self.assertNotIn("anchor", result["visual"])
        self.assertEqual(self.bundle, before)

    def test_generic_controls_and_mixed_questions_cannot_bypass_reasoning(self):
        for q in ("show me around", "show the demo", "show me everything", "show me", "continue", "show me seats and tell me the price", "show me whether it has six seats"):
            self.assertFalse(rv.show_request(q), q)
        for q in ("Show me the seats", "Could you show me the cabin?", "I would like to see the display", "Bring up the seats please"):
            self.assertTrue(rv.show_request(q), q)

    def test_caption_search_hint_is_bounded_and_never_changes_question_or_scope(self):
        question = "Show me the second-row seats on variant Premium"
        state = {"demo_id": self.did, "question": question, "snapshot_id": self.pin, "demo_version": 1,
                 "control": TurnControl(deadline=time.monotonic() + 30), "profile": {}, "history": []}
        original = knowledge.retrieve
        with patch.object(knowledge, "retrieve", wraps=original) as search:
            result = asyncio.run(rg.retrieve(state))
        self.assertEqual(state["question"], question)
        self.assertEqual(search.call_args.kwargs["scope"], {"variant": "Premium"})
        self.assertEqual(result["requested_scope"], {"variant": "Premium"})
        self.assertIn("Two individual second-row seats", search.call_args.args[1])
        duplicate = copy.deepcopy(self.bundle["slides"][2]["callouts"][1])
        self.bundle["slides"][2]["callouts"] = [duplicate] * 30
        hint = rv.retrieval_hint(self.bundle, "Show me the second-row seats")
        self.assertEqual(hint.count("Two individual"), 4)

    def test_unrelated_request_and_position_only_overlap_have_no_fallback(self):
        for q in ("Show me the sunroof", "Show me the second-row armrest", "Show me the reclining seats", "Show me eight seats"):
            result = rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
                question=q, current_id="sl1", evidence=self.facts, visual_only=True)
            self.assertIsNone(result, q)

    def test_broad_slide_title_cannot_license_another_rows_picture(self):
        self.bundle["slides"][2]["title"] = "First and second row heated seating"
        self.bundle["slides"][2]["callouts"] = [self.bundle["slides"][2]["callouts"][1]]
        for q in ("Show me first row seats", "Show me heated second row seats"):
            self.assertIsNone(rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
                question=q, current_id="sl3", evidence=self.facts, visual_only=True), q)

    def test_other_parts_in_same_photo_cannot_donate_a_different_caption_qualifier(self):
        self.bundle["slides"][2]["callouts"] = [self.bundle["slides"][2]["callouts"][1]]
        self.bundle["slides"][2]["media"][1]["image_parts"] = [{"name": "first-row seat"}, {"name": "second-row seat"}, {"name": "heated seat"}]
        for q in ("Show me first-row seats", "Show me heated second-row seats"):
            self.assertIsNone(rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
                question=q, current_id="sl3", evidence=self.facts, visual_only=True), q)

    def test_negative_requested_variant_projection_never_selects_positive_photo(self):
        facts = [{**self.facts[0], "applicability_projection": {"rows": [
            {"polarity": "negative", "variants": ["Base"], "assertion": "Not available on Base"}]}}]
        for visual_only in (True, False):
            self.assertIsNone(rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
                question="Show me the seats", current_id="sl3", evidence=facts,
                fact_ids=["F001"], visual_only=visual_only))
        result = {"answered": True, "fact_ids": ["F001"], "route": "jump", "slide_id": "sl3", "callout_id": "c3"}
        rv.attach({"demo_id": self.did, "snapshot_id": self.pin, "demo_version": 1, "question": "Seats on Base?",
                   "slide_id": "sl1", "evidence": facts}, result, self.bundle)
        self.assertEqual((result["visual"], result["route"], result["slide_id"]), (None, "none", "sl1"))

    def test_explicit_show_never_presents_proxy_as_requested_part(self):
        self.assertIsNone(rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
            question="Show me Lane Change Warning", current_id="sl1", evidence=self.facts, visual_only=True))

    def test_rejected_suppressed_competitor_and_condition_donors_cannot_match(self):
        for update in ({"approved": False}, {"knowledge": {"conflict_status": "suppressed"}},
                       {"knowledge": {"excluded_by_precedence": True}}, {"competition": True},
                       {"runtime_role": "condition"}, {"provenance": "live_web"}):
            facts = [{**f, **update} for f in self.facts]
            self.assertIsNone(rv.select(self.did, self.bundle, snapshot_id=self.pin, demo_version=1,
                question="Lane Change Warning", current_id="sl1", evidence=facts, fact_ids=["F002"]))

    def test_compound_caption_with_unapproved_fact_is_ineligible(self):
        for slide in self.bundle["slides"][:2]:
            slide["callouts"][0]["fact_ids"].append("F999")
        self.assertIsNone(self.select())

    def test_unknown_caption_owner_does_not_fall_back_to_first_photo(self):
        for slide in self.bundle["slides"]:
            for callout in slide["callouts"]:
                callout["image_id"] = "not-published"
        self.assertIsNone(self.select())

    def test_missing_external_other_demo_and_traversal_images_are_rejected(self):
        for path in ("https://example.com/image.jpg", "/media/dm_other/sources/im1.jpg", f"/media/{self.did}/sources/%2e%2e/sources/im1.jpg", f"/media/{self.did}/sources/missing.jpg"):
            for slide in self.bundle["slides"]:
                for item in slide["media"]:
                    item["image_url"] = path
            self.assertIsNone(self.select(), path)

    def test_stale_snapshot_and_republished_same_snapshot_version_fail_closed(self):
        for key, value in (("knowledge_snapshot_id", "kb_" + "f" * 24), ("version", 2)):
            current = copy.deepcopy(self.bundle)
            current[key] = value
            self.assertIsNone(rv.select(self.did, current, snapshot_id=self.pin, demo_version=1,
                question="lane change", current_id="sl1", evidence=self.facts, fact_ids=["F002"]))

    def test_model_failure_and_clarification_never_gain_a_visual(self):
        for update in ({"answered": False}, {"clarifying_question": "Which trim?"}, {"provider_failed": True}, {"repair_failed": True}):
            result = {"answered": True, "fact_ids": ["F002"], **update}
            rv.attach({"demo_id": self.did, "snapshot_id": self.pin, "demo_version": 1, "question": "lane change", "evidence": self.facts}, result, self.bundle)
            self.assertNotIn("visual", result)

    def test_stale_pin_clears_legacy_slide_route_and_cached_visual(self):
        result = {"answered": True, "fact_ids": ["F002"], "visual": {"ref": "im2"}, "slide_id": "sl2", "route": "jump"}
        rv.attach({"demo_id": self.did, "snapshot_id": self.pin, "demo_version": 0, "slide_id": "old-slide"}, result, self.bundle)
        self.assertEqual((result["visual"], result["slide_id"], result["route"]), (None, "old-slide", "none"))

    def test_publication_race_and_disappearing_media_cannot_claim_picture_is_shown(self):
        for change in ("version", "file"):
            bundle = copy.deepcopy(self.bundle)
            if change == "version":
                bundle["version"] = 2
            else:
                for item in bundle["slides"][2]["media"]:
                    item["image_url"] = f"/media/{self.did}/sources/missing.jpg"
            result = {"answered": True, "visual_only": True, "answer": "Here is the reviewed image.", "fact_ids": []}
            rv.attach({"demo_id": self.did, "snapshot_id": self.pin, "demo_version": 1, "slide_id": "sl1",
                "question": "Show me the seats", "evidence": self.facts}, result, bundle)
            self.assertFalse(result["answered"])
            self.assertIsNone(result["visual"])
            self.assertIn("don't have", result["answer"])

    def test_show_only_serves_before_graph_without_learning_a_fact_or_unknown(self):
        before = copy.deepcopy(store.read_json(self.did, "understanding.json"))
        with patch.object(rg.graph, "ainvoke", side_effect=AssertionError("Show must not call model")):
            final = asyncio.run(rg.run_turn(self.did, {"question": "Show me the second-row seats", "slide_id": "sl1", "session_id": "show"}))
        result = final["result"]
        self.assertTrue(result["visual_only"])
        self.assertEqual((result["visual"]["ref"], result["fact_ids"]), ("im4", []))
        self.assertFalse(store.read_json(self.did, "faq.json"))
        self.assertEqual(store.read_json(self.did, "understanding.json"), before)
        self.assertEqual(final["delivery"]["result"]["visual"], result["visual"])

    def test_real_graph_attaches_picture_after_normal_fact_validation(self):
        decision = TurnDecision(action="answer", answered=True, sentences=[{"text": self.facts[1]["value"], "fact_ids": ["F002"]}])
        with patch.object(rg.runtime, "structured", return_value=decision):
            final = asyncio.run(rg.run_turn(self.did, {"question": "Tell me about Lane Change Warning", "slide_id": "sl1", "session_id": "answer", "skip_bank": True}))
        self.assertTrue(final["result"]["answered"], final["result"])
        self.assertEqual(final["result"]["visual"]["ref"], "im2")
        self.assertEqual(final["delivery"]["result"]["visual"], final["result"]["visual"])

    def test_missing_photo_is_a_neutral_navigation_limit_not_a_new_unknown(self):
        before = copy.deepcopy(store.read_json(self.did, "understanding.json"))
        with patch.object(rg.graph, "ainvoke", side_effect=AssertionError("Navigation must not call model")):
            final = asyncio.run(rg.run_turn(self.did, {"question": "Show me the sunroof", "session_id": "missing"}))
        result = final["result"]
        self.assertTrue(result["visual_only"])
        self.assertFalse(result["answered"])
        self.assertIsNone(result["visual"])
        self.assertIn("reviewed image", result["answer"])
        self.assertFalse(store.read_json(self.did, "faq.json"))
        self.assertEqual(store.read_json(self.did, "understanding.json"), before)

    def test_faq_hit_gets_same_fresh_picture_without_graph(self):
        q = "Tell me about Lane Change Warning"
        entry = faq.cache_answer(self.did, q, {"answered": True, "answer": self.facts[1]["value"], "fact_ids": ["F002"], "facts": [self.facts[1]]}, snapshot_id=self.pin)
        self.assertIsNotNone(entry)
        with patch.object(rg.graph, "ainvoke", side_effect=AssertionError("Cache must avoid graph")):
            final = asyncio.run(rg.run_turn(self.did, {"question": q, "slide_id": "sl1", "session_id": "cache"}))
        self.assertTrue(final["result"]["from_bank"], final["result"])
        self.assertEqual(final["result"]["visual"]["ref"], "im2")

    def test_requested_variant_filters_show_before_any_picture_selection(self):
        und = store.read_json(self.did, "understanding.json")
        und["facts"][0]["scope"] = {"variant": "Premium"}
        store.write_json(self.did, "understanding.json", und)
        sid = knowledge.snapshot(self.did, publish=True)["id"]
        bundle = {**self.bundle, "knowledge_snapshot_id": sid}
        store.write_json(self.did, "bundle.json", bundle)
        decision = TurnDecision(action="answer", answered=False, sentences=[])
        with patch.object(rg.runtime, "structured", return_value=decision):
            final = asyncio.run(rg.run_turn(self.did, {"question": "Show me the seats on variant Base", "session_id": "base"}))
        self.assertTrue(final["result"].get("visual_only"))
        self.assertFalse(final["result"]["answered"])
        self.assertIsNone(final["result"].get("visual"))
        with patch.object(rg.graph, "ainvoke", side_effect=AssertionError("Matching picture is navigation")):
            premium = asyncio.run(rg.run_turn(self.did, {"question": "Show me the seats on variant Premium", "session_id": "premium"}))
        self.assertTrue(premium["result"]["answered"])
        self.assertEqual(premium["result"]["visual"]["ref"], "im3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
