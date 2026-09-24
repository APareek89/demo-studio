"""Free two-picture/proxy contracts; reusable by qa_deck and isolated when run alone."""
from __future__ import annotations

import copy
import os
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    with tempfile.TemporaryDirectory(prefix="deck-media-contract-") as tmp, patch.dict(os.environ, {
            "MOCK_LLM": "1", "CLOUD_SYNC": "0", "DEMO_STUDIO_DATA": tmp, "DEMO_STUDIO_GRAPH_DB": str(Path(tmp) / "graph.sqlite")}):
        from server import config, schemas, store
        from server.agents import bundle, deck
        with patch.object(config, "DATA_DIR", Path(tmp)), patch.object(config, "MOCK_LLM", True), \
             patch.object(socket.socket, "connect", side_effect=AssertionError("Outbound blocked")) as connect, \
             patch.object(socket.socket, "connect_ex", side_effect=AssertionError("Outbound blocked")) as connect_ex, \
             patch.object(socket, "create_connection", side_effect=AssertionError("Outbound blocked")) as create_connection:
            did = store.new_demo("Deck media contract")["id"]
            sources = [store.add_file_source(did, f"picture-{i}.png", b"fixture", role="hero" if i == 0 else "product") for i in range(3)]
            def image(id, source, part, x):
                return {"id": id, "source_id": source["id"], "quality": 4, "angle": "front", "description": part,
                        "parts": [{"name": part, "confidence": .9, "box": {"x": x, "y": .35, "w": .15, "h": .15}}]}
            images = [image("im08", sources[0], "bonnet", .1), image("im06", sources[1], "wheel", .65), image("im03", sources[2], "headlamp", .4)]
            by_id = {im["id"]: im for im in images}
            facts = [{"id": fid, "claim": claim, "value": value, "approved": True, "kind": "feature", "truth": "stated",
                      "source": {"ref": sources[0]["id"], "locator": "fixture", "quote": f"{claim}: {value}"}}
                     for fid, claim, value in [("F1", "Engine", "Turbo"), ("F2", "Wheel", "Alloy"), ("F3", "Headlamp", "LED")]]
            lines = [{"id": f"l{i}", "text": f"{fact['claim']}: {fact['value']}", "fact_ids": [fact["id"]], "visual": {"kind": "image", "ref": im["id"]}}
                     for i, (fact, im) in enumerate(zip(facts, images))]
            und = {"product": {"name": "Example", "category": "Compact SUV"}, "facts": facts, "images": images, "shots": [], "unknowns": []}
            seg = {"id": "engine", "title": "Engine choices", "topic": "engine", "role": "proof", "lines": lines[:2], "deeper": [], "checkin": "", "fundamental": True}
            audit = {"lines": [{"line_id": line["id"], "visual": line["visual"]["ref"], "coverage": "full"} for line in lines]}
            media = deck.choose_media(seg, lines[:2], und, audit, "im08")
            check("media: audited bindings retain two picture IDs in spoken order", [entry["image_id"] for entry in media] == ["im08", "im06"])
            check("media: each picture retains its first spoken line index", [entry["from_line"] for entry in media] == [0, 1])
            check("media: audited pictures are not marked illustration", all(not entry["proxy"] for entry in media))
            check("media: a third distinct picture is not added", len(deck.choose_media(seg, lines, und, audit, "im08")) == 2)
            repeated = [lines[0], {**lines[0], "id": "repeat"}, lines[1], lines[0]]
            repeat_media = deck.choose_media(seg, repeated, und, None, "im08")
            check("media: repeated references collapse and retain first indexes", [entry["from_line"] for entry in repeat_media] == [0, 2])
            check("media: absent audit accepts the Author's actual binding", deck.choose_media(seg, lines[:2], und, None, "im08") == media)
            legacy_binding = [{**line, "visual": {"ref": line["visual"]["ref"]}} for line in lines[:2]]
            check("media: full audited legacy bindings recover only the missing image kind", deck.choose_media(seg, legacy_binding, und, audit, "im08") == media)
            explicit_none = [{**lines[0], "visual": {"kind": "none", "ref": "im08"}}]
            check("media: explicit none is never promoted to audited picture proof", deck.choose_media(seg, explicit_none, und, audit, "im08")[0]["proxy"])
            partial = {"lines": [{"line_id": line["id"], "coverage": "partial"} for line in lines]}
            proxy = deck.choose_media(seg, lines[:2], und, partial, "im08")
            check("media: partial coverage cannot become literal evidence", len(proxy) == 1 and proxy[0]["proxy"])
            mismatch = {"lines": [{"line_id": "l0", "coverage": "full", "visual": "im06"}]}
            check("media: stale audit for a different picture cannot approve its binding", deck.choose_media(seg, lines[:1], und, mismatch, "im08")[0]["proxy"])
            check("media: unknown pictures and shots are not accepted as slide images", deck.choose_media(seg, [{**lines[0], "visual": {"kind": "shot", "ref": "im08"}}], und, None, "im08")[0]["proxy"])
            engine = deck.choose_proxy("engine", images, "im06")
            check("proxy: engine chooses the confidently tagged bonnet", engine["image_id"] == "im08" and engine["proxy_reason"] == "closest by part: bonnet")
            weak = copy.deepcopy(images)
            for im in weak:
                im["parts"][0]["confidence"] = .2
            check("proxy: weak part tags fall back to hero", deck.choose_proxy("engine", weak, "im06")["image_id"] == "im06")
            no_box = copy.deepcopy(images)
            no_box[0]["parts"][0].pop("box")
            no_box_proxy = deck.choose_proxy("engine", no_box, "im06")
            check("proxy: a confident tag without a box still selects the illustration", no_box_proxy["image_id"] == "im08")
            unplaced = {"callouts": [{"part": "bonnet"}]}
            deck.place_callouts(unplaced, no_box[0])
            check("proxy: a missing part box keeps its label in the panel", unplaced["callouts"][0]["placement"] == "panel" and unplaced["callouts"][0]["anchor"] is None)
            check("proxy: price has no visual proof and uses hero illustration", deck.choose_proxy("price", images, "im06")["proxy_reason"] == "hero — no picture for this topic")
            check("proxy: no allowed hero produces no invented picture", deck.choose_proxy("price", [], "excluded") == {})
            held = [{**lines[0], "unverified": True}, lines[1]]
            check("media: held lines do not consume the displayed line index", deck.choose_media(seg, held, und, None, "im08")[0]["from_line"] == 0)
            second_view = {**audit, "images": [{"visual": "im06", "script_line_ids": ["l0"],
                                               "visible_features": ["engine detail"], "confidence": .9}]}
            paired = deck.choose_media(seg, lines[:1], und, second_view, "im08")
            check("workbook media: saved full pixel coverage supplies a distinct second view", [m["image_id"] for m in paired] == ["im08", "im06"])
            check("workbook media: additional view retains its supported narration timing", paired[1]["from_line"] == 0 and not paired[1]["proxy"])
            check("workbook media: one available supported view is not duplicated", len(deck.choose_media(seg, lines[:1], und, audit, "im08")) == 1)
            def candidate(**changes):
                return {**second_view, "images": [{**second_view["images"][0], **changes}]}
            check("workbook media: weak pixel evidence cannot supply the second picture", len(deck.choose_media(seg, lines[:1], und, candidate(confidence=.2), "im08")) == 1)
            check("workbook media: absent visible features cannot supply the second picture", len(deck.choose_media(seg, lines[:1], und, candidate(visible_features=[]), "im08")) == 1)
            check("workbook media: excluded pictures cannot enter the second slot", len(deck.choose_media(seg, lines[:1], und, candidate(visual="excluded"), "im08")) == 1)
            check("workbook media: another segment's audit is not reused", len(deck.choose_media(seg, lines[:1], und, candidate(script_line_ids=["other"]), "im08")) == 1)
            check("workbook media: held narration cannot promote another view", deck._additional_picture_lines([{**lines[0], "unverified": True}], second_view, set(by_id))["im06"] == set())
            check("workbook media: partial line coverage cannot promote another view", deck._additional_picture_lines(lines[:1], {**second_view, "lines": partial["lines"]}, set(by_id))["im06"] == set())
            check("workbook media: explicit none cannot promote another view", deck._additional_picture_lines(explicit_none, second_view, set(by_id))["im06"] == set())
            check("workbook media: an existing pair keeps its reviewed narration order", deck.choose_media(seg, lines[:2], und, second_view, "im08") == media)
            check("workbook media: a repeated picture ID cannot fill the second slot", len(deck.choose_media(seg, lines[:1], und, candidate(visual="im08"), "im08")) == 1)
            store.write_json(did, "understanding.json", und)
            store.write_json(did, "plan.json", {"segments": [], "ctas": [], "intake": {}, "voice": {}})
            script = {"segments": [seg], "closing": [], "visual_audit": audit, "version": 1}
            store.write_json(did, "script.json", script)
            store.write_json(did, "visual-audit.json", audit)
            before_audit = store.path(did, "visual-audit.json").read_bytes()
            built = deck.build(did, lambda _: None)
            slide = next(s for s in built["slides"] if s.get("segment_id") == "engine")
            check("deck: media list persists and legacy image_id mirrors its first picture", slide["media"] == media and slide["image_id"] == "im08")
            check("deck: fundamental status survives media selection and script joins", slide["fundamental"] and deck.slides_with_script([slide], script)[0]["fundamental"])
            check("deck: derived labels attach to the picture their source line uses", {c["image_id"] for c in slide["callouts"]} == {"im08", "im06"})
            wheel = next(c for c in slide["callouts"] if c["image_id"] == "im06")
            check("deck: second-picture geometry uses its own part box", wheel["placement"] == "overlay" and abs(wheel["anchor"]["x"] - .725) < 1e-6)
            alternative_script = {**script, "segments": [{**seg, "lines": lines[:1]}], "visual_audit": second_view}
            store.write_json(did, "script.json", alternative_script)
            alternative_slide = next(s for s in deck.build(did, lambda _: None)["slides"] if s.get("segment_id") == "engine")
            check("workbook deck: audited alternative persists through the real deck build", [m["image_id"] for m in alternative_slide["media"]] == ["im08", "im06"])
            alternative_labels = [c for c in alternative_slide["callouts"] if c["image_id"] == "im06"]
            check("workbook deck: alternative labels use only their audited line's citations", bool(alternative_labels) and all(c["fact_ids"] == ["F1"] for c in alternative_labels))
            check("workbook deck: absent matching part uses a caption without a guessed marker", all(c["placement"] == "panel" and c["anchor"] is None for c in alternative_labels))
            store.write_json(did, "script.json", {**script, "visual_audit": partial})
            proxy_built = deck.build(did, lambda _: None)
            proxy_slide = next(s for s in proxy_built["slides"] if s.get("segment_id") == "engine")
            check("proxy: one complete cited label anchors on the matching bonnet", len(proxy_slide["callouts"]) == 1 and proxy_slide["callouts"][0]["fact_ids"] == ["F1"] and proxy_slide["callouts"][0]["part"] == "bonnet" and proxy_slide["callouts"][0]["placement"] == "overlay")
            check("proxy: illustrative label reveals at the start", proxy_slide["callouts"][0]["reveal_on_line"] == 0)
            check("proxy: building illustrations never changes the pixel audit", store.path(did, "visual-audit.json").read_bytes() == before_audit)
            multi_cited = copy.deepcopy(script)
            multi_cited["visual_audit"] = partial
            multi_cited["segments"][0]["lines"][0]["fact_ids"] = ["F1", "F2"]
            store.write_json(did, "script.json", multi_cited)
            multi_proxy = next(s for s in deck.build(did, lambda _: None)["slides"] if s.get("segment_id") == "engine")
            check("proxy: derived illustration retains every citation from its source line", len(multi_proxy["callouts"]) == 1 and multi_proxy["callouts"][0]["fact_ids"] == ["F1", "F2"] and multi_proxy["callouts"][0]["text"] == proxy_slide["callouts"][0]["text"])
            store.write_json(did, "script.json", {**script, "visual_audit": partial})
            scoped = copy.deepcopy(und)
            scoped["facts"][0]["conditions"] = "only on selected variants with the optional equipment package fitted"
            store.write_json(did, "understanding.json", scoped)
            scoped_deck = deck.build(did, lambda _: None)
            check("proxy: overlong scope is omitted whole instead of shortened", next(s for s in scoped_deck["slides"] if s.get("segment_id") == "engine")["callouts"] == [])
            store.write_json(did, "understanding.json", und)
            changed = copy.deepcopy(slide)
            deck.apply_overrides([changed], {"slides": [{"slide_id": changed["id"], "media": ["im08", "im03"],
                                                      "callouts": [{"id": wheel["id"], "image_id": "im03", "part": "headlamp", "label_pos": {"x": .1, "y": .1}}]}]}, by_id, {"F1", "F2", "F3"})
            changed_label = next(c for c in changed["callouts"] if c["id"] == wheel["id"])
            check("override: second-slot swap preserves timing and marks unaudited illustration", changed["media"][1]["image_id"] == "im03" and changed["media"][1]["from_line"] == 1 and changed["media"][1]["proxy"])
            check("override: unchanged picture retains its audited metadata", changed["media"][0] == slide["media"][0])
            check("override: moved callout uses new picture geometry and independent drag", abs(changed_label["anchor"]["x"] - .475) < 1e-6 and changed_label["label_pos"] == {"x": .1, "y": .1})
            null_default = copy.deepcopy(slide)
            deck.apply_overrides([null_default], {"slides": [{"slide_id": slide["id"], "callouts": [{"id": wheel["id"], "image_id": None}]}]}, by_id, {"F1", "F2", "F3"})
            check("override: null picture attachment means the first picture", next(c for c in null_default["callouts"] if c["id"] == wheel["id"])["image_id"] == "im08")
            cleared = copy.deepcopy(slide)
            deck.apply_overrides([cleared], {"slides": [{"slide_id": slide["id"], "media": [], "callouts": [{"id": wheel["id"], "image_id": None}]}]}, by_id, {"F1", "F2", "F3"})
            check("override: removing both pictures accepts the editor's null attachments", cleared["media"] == [] and cleared["image_id"] is None and cleared["callouts"] == [])
            for label, override in [("third picture", {"media": ["im08", "im06", "im03"]}), ("excluded picture", {"media": ["excluded"]}),
                                    ("foreign callout attachment", {"callouts": [{"id": wheel["id"], "image_id": "im03"}]})]:
                rejected = False
                try:
                    deck.apply_overrides([copy.deepcopy(slide)], {"slides": [{"slide_id": slide["id"], **override}]}, by_id, {"F1", "F2", "F3"})
                except ValueError:
                    rejected = True
                check(f"override: rejects {label}", rejected)
            six = deck.DeckOut(titles=[], callouts=[deck.CalloutOut(slide_id=slide["id"], image_id=ref, text=f"Listed option {n}", fact_ids=[fid], part=part, reveal_on_line=index)
                for ref, fid, part, index in [("im08", "F1", "bonnet", 0), ("im06", "F2", "wheel", 1)] for n in range(3)])
            store.write_json(did, "script.json", script)
            with patch.object(config, "MOCK_LLM", False), patch.object(deck, "_ask_model", return_value=six):
                model_deck = deck.build(did, lambda _: None)
            six_slide = next(s for s in model_deck["slides"] if s.get("segment_id") == "engine")
            check("deck: two pictures can each carry three independently validated callouts", len(six_slide["callouts"]) == 6 and all(sum(c["image_id"] == ref for c in six_slide["callouts"]) == 3 for ref in ("im08", "im06")))
            over_limit = False
            try:
                deck.apply_overrides([copy.deepcopy(six_slide)], {"slides": [{"slide_id": six_slide["id"], "callouts": [{"id": six_slide["callouts"][-1]["id"], "image_id": "im08"}]}]}, by_id, {"F1", "F2", "F3"})
            except ValueError:
                over_limit = True
            check("override: moving a fourth label onto a picture is rejected", over_limit)
            with patch.object(deck.claude, "structured", return_value=six) as model:
                deck._ask_model(store.load(did), und, {}, [slide], by_id, {f["id"]: f for f in facts})
            prompt = model.call_args.args[0]
            check("deck: model sees picture IDs with separate exact part lists", "im08 from line 0" in prompt and "PARTS: bonnet" in prompt and "im06 from line 1" in prompt and "PARTS: wheel" in prompt)
            store.write_json(did, "deck-overrides.json", {"slides": [{"slide_id": slide["id"], "media": ["im06"], "callouts": [{"id": wheel["id"], "image_id": "im06"}]}]})
            store.update(did, lambda d: next(src for src in d["sources"] if src["id"] == sources[1]["id"]).update(use_in_demo=False))
            rebuilt = deck.build(did, lambda _: None)
            safe_slide = next(s for s in rebuilt["slides"] if s.get("segment_id") == "engine")
            check("override: rebuild survives a later exclusion of the saved picture", safe_slide["image_id"] == "im08" and all(m["image_id"] != "im06" for m in safe_slide["media"]))
            check("override: stale callout attachments cannot restore an excluded picture", all(c.get("image_id") != "im06" for c in safe_slide["callouts"]))
            store.update(did, lambda d: next(src for src in d["sources"] if src["id"] == sources[1]["id"]).update(use_in_demo=True))
            store.write_json(did, "deck-overrides.json", {})
            store.write_json(did, "script.json", script)
            store.write_json(did, "deck.json", built)
            # This two-line media fixture tests packaging, not narration length.
            # Real-WAV minimum and atomic failure live in minimum_narration_contract.py.
            store.update(did, lambda d: d["approvals"].update({card: True for card in store.CARDS}))
            with patch.object(bundle.narration, "require_minimum", return_value={"minimum_seconds": 180, "seconds": 180, "sufficient": True, "basis": "synthetic media fixture", "measured": False, "route": []}):
                result = bundle.build(did, lambda _: None)
            published = next(s for s in result["slides"] if s.get("segment_id") == "engine")
            check("bundle: both media URLs and own part boxes are resolved", len(published["media"]) == 2 and all(m["image_url"].startswith(f"/media/{did}/") and m["image_parts"] for m in published["media"]))
            check("bundle: legacy image_url and new first media URL agree", published["image_url"] == published["media"][0]["image_url"])
            check("bundle: callout picture identities survive publication", {c["image_id"] for c in published["callouts"]} == {"im08", "im06"})
            check("bundle: segments and slides preserve the lead-fundamental flag", published["fundamental"] and result["segments"][0]["fundamental"])
            check("media: no outbound requests and all storage is isolated", not any(m.called for m in (connect, connect_ex, create_connection)) and store.demo_dir(did).is_relative_to(Path(tmp)))


if __name__ == "__main__":
    results = []
    def check(label, ok):
        results.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + label)
    run(check)
    print(f"Deck media: {sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)
