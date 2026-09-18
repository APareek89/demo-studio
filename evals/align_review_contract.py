"""Free contracts for human fact provenance and spoken-question review."""
from __future__ import annotations

import copy
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check, _demo_id=None):
    from fastapi.testclient import TestClient
    from server import config, orchestrator, schemas, store
    from server.agents import align, bundle, qa, visuals
    from server.app import app

    with tempfile.TemporaryDirectory(prefix="align-review-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(tmp)))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected paid or outbound call")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex",
                                "server.llm.gemini.client", "server.llm.runware._post", "server.llm.claude._client_opts")]
        stack.enter_context(patch.object(visuals, "build_map", return_value={}))
        realign = stack.enter_context(patch.object(visuals, "align", side_effect=lambda _id, script, _und: script))
        demo = store.new_demo("Review fixture"); did = demo["id"]
        product = store.add_text_source(did, "Product brochure", "Product length 3995 mm.", "product")
        product2 = store.add_text_source(did, "Product dimensions", "Product length 3990 mm.", "catalogue")
        rival = store.add_text_source(did, "Rival brochure", "Rival HX8 length 3995 mm.", "competitor")
        rival2 = store.add_text_source(did, "Other rival brochure", "Other rival length 3990 mm.", "competitor")
        def fact(fid, ref):
            return schemas.Fact(id=fid, kind="spec", claim="Length", value="3995 mm", confidence=1,
                                truth="certified", source=schemas.FactSource(ref=ref, locator="page 1", quote="length 3995 mm")).model_dump()
        und = {"product":{"name":"Product fixture", "category":"Car"}, "facts":[fact("F001", product["id"])],
               "competitors":[{"name":"Rival", "source_id":rival["id"], "url":"https://example.com/rival", "facts":[fact("C001", rival["id"])]},
                              {"name":"Other rival", "source_id":rival2["id"], "facts":[fact("C002", rival2["id"])]}],
               "unknowns":[], "shots":[], "images":[], "brand":{}}
        script = {"intake_q1":"What matters to you?", "intake_q2":"An old second question?", "intake_audio":{"q1":"old.wav", "q2":"old2.wav"},
                  "segments":[{"id":"proof", "title":"Product", "role":"proof", "outcome":"Old outcome",
                               "checkin":"Is that useful?", "checkin_audio":"old-checkin.wav",
                               "lines":[{"id":"proof-L1", "text":"Length is 3995 mm.", "fact_ids":["F001"], "audio":"keep.wav"}], "deeper":[]},
                              {"id":"intro", "title":"Introduction", "role":"opening", "outcome":"",
                               "checkin":"", "lines":[{"id":"intro-L1", "text":"Take a closer look.", "fact_ids":[]}], "deeper":[]}], "closing":[]}
        store.write_json(did, "understanding.json", und)
        store.write_json(did, "plan.json", {"voice":{}, "segments":[], "ctas":[]})
        store.write_json(did, "script.json", script)
        def approve_all():
            def mutate(d):
                d["approvals"].update({key:True for key in store.CARDS})
                for stage in d["stages"].values():
                    stage["status"] = "done"
            store.update(did, mutate)
        def snapshot():
            return {name:store.path(did, name).read_bytes() for name in ("understanding.json", "script.json", "demo.json")}
        api = TestClient(app)
        cards = align.cards(did)
        check("align review: F and C facts appear with competitor identity even when competition is off",
              [(f["id"], f["scope"], f["competitor_name"]) for f in cards["facts"]["facts"]]
              == [("F001", "product", ""), ("C001", "competitor", "Rival"), ("C002", "competitor", "Other rival")])
        chat = align._cards_text(cards)
        check("align review: chat sees competitor truth, conditions, approval and exact provenance",
              all(text in chat for text in ('"id": "C001"', '"truth": "certified"', '"approved": true', '"conditions": ""', '"quote": "length 3995 mm"')))
        response = align.respond(did, "looks fine", [], [])
        check("align review: the expanded fact prompt formats and returns a valid mock Align response", isinstance(response, schemas.AlignOut))
        approve_all()
        result = api.patch(f"/api/demos/{did}/align/facts/C001", json={"truth":"stated", "conditions":"HX8 only", "source":{"locator":"specification table", "quote":"Rival HX8 length 3995 mm."}})
        saved = store.read_json(did, "understanding.json")
        corrected = saved["competitors"][0]["facts"][0]
        check("align review: C truth and citation can be corrected without resending its value",
              result.status_code == 200 and corrected["truth"] == "stated" and corrected["conditions"] == "HX8 only"
              and corrected["source"] == {"ref":rival["id"], "locator":"specification table", "quote":"Rival HX8 length 3995 mm."}
              and corrected["value"] == "3995 mm" and corrected["edited"])
        check("align review: C edits preserve separate storage, source owner and all product facts",
              saved["facts"] == und["facts"] and saved["competitors"][0]["source_id"] == rival["id"]
              and saved["competitors"][1] == und["competitors"][1]
              and "scope" not in corrected and "competitor_name" not in corrected)
        current = store.load(did)
        check("align review: fact edit invalidates downstream work and all approvals, keeping corrected understanding done",
              not any(current["approvals"].values()) and current["stages"]["understand"]["status"] == "done"
              and all(current["stages"][key]["status"] == "stale" for key in orchestrator.DOWNSTREAM["understand"]))
        for label, fid, payload, status in (
            ("unknown fact", "C999", {"value":"3990 mm"}, 404),
            ("invalid truth", "C001", {"truth":"official"}, 400),
            ("non-text value", "F001", {"value":3990}, 400),
            ("empty value", "F001", {"value":" "}, 400),
            ("unknown source", "F001", {"source":{"ref":"missing", "locator":"p1", "quote":"x"}, "conditions":""}, 400),
            ("blended source ids", "F001", {"source":{"ref":product["id"] + "," + product2["id"], "locator":"p1", "quote":"x"}, "conditions":""}, 400),
            ("product citing competitor", "F001", {"source":{"ref":rival["id"], "locator":"p1", "quote":"x"}, "conditions":""}, 400),
            ("competitor citing product", "C001", {"source":{"ref":product["id"], "locator":"p1", "quote":"x"}, "conditions":""}, 400),
            ("competitor source reassignment", "C001", {"source":{"ref":rival2["id"], "locator":"p1", "quote":"x"}, "conditions":""}, 400),
            ("source change retaining old evidence", "F001", {"source":{"ref":product2["id"]}}, 400),
            ("unsupported citation field", "F001", {"source":{"url":"https://example.com"}}, 400),
            ("structural fact mutation", "F001", {"id":"C003"}, 400),
        ):
            before = snapshot()
            result = api.patch(f"/api/demos/{did}/align/facts/{fid}", json=payload)
            check(f"align review: {label} is rejected without any mutation", result.status_code == status and snapshot() == before)
        result = api.patch(f"/api/demos/{did}/align/facts/F001", json={"value":"3990 mm", "truth":"stated", "conditions":"current brochure", "source":{"ref":product2["id"], "locator":"dimensions", "quote":"Product length 3990 mm."}})
        updated = store.read_json(did, "understanding.json")["facts"][0]
        check("align review: product citation replacement requires and saves its own exact evidence",
              result.status_code == 200 and updated["source"] == {"ref":product2["id"], "locator":"dimensions", "quote":"Product length 3990 mm."}
              and updated["conditions"] == "current brochure" and updated["truth"] == "stated")
        result = api.post(f"/api/demos/{did}/align/facts/C001/approval", json={"approved":False})
        saved = store.read_json(did, "understanding.json")
        check("align review: rejecting a C fact removes its QA eligibility while keeping it reviewable",
              result.status_code == 200 and "C001" not in qa.approved_fact_ids(saved, True)
              and any(f["id"] == "C001" and not f["approved"] for f in result.json()["cards"]["facts"]["facts"]))
        result = api.post(f"/api/demos/{did}/align/facts/C001/approval", json={"approved":True})
        saved = store.read_json(did, "understanding.json")
        check("align review: restoring a C fact still respects competition-off at runtime",
              result.status_code == 200 and "C001" in qa.approved_fact_ids(saved, True) and "C001" not in qa.approved_fact_ids(saved, False))
        for payload in ({"approved":"false"}, {}, []):
            before = snapshot()
            result = api.post(f"/api/demos/{did}/align/facts/C001/approval", json=payload)
            check("align review: approval requires a literal boolean and is atomic", result.status_code == 400 and snapshot() == before)

        approve_all()
        action = schemas.AlignAction(type="edit_fact", fact_id="C001", fact_value="3990 mm", fact_truth="stated", fact_conditions="HX8 only", fact_source=schemas.FactSource(ref=rival["id"], locator="reviewed table", quote="HX8 length 3990 mm")).model_dump()
        notes = orchestrator.apply_actions(did, [action], [], "align", {})
        corrected = store.read_json(did, "understanding.json")["competitors"][0]["facts"][0]
        check("align review: structured chat corrections use the same C lookup, provenance and approval invalidation",
              notes == ["edited C001"] and corrected["value"] == "3990 mm" and corrected["source"]["locator"] == "reviewed table"
              and not any(store.load(did)["approvals"].values()))
        before = snapshot()
        notes = orchestrator.apply_actions(did, [{"type":"edit_fact", "fact_id":"C001", "fact_truth":"unsupported"}], [], "align", {})
        check("align review: an invalid chat correction reports failure without writing", snapshot() == before and "Could not edit" in notes[0])
        notes = orchestrator.apply_actions(did, [{"type":"remove_fact", "fact_id":"C001"}], [], "align", {})
        check("align review: chat rejection targets C storage and removes runtime eligibility", notes == ["removed C001"] and "C001" not in qa.approved_fact_ids(store.read_json(did, "understanding.json"), True))

        approve_all()
        result = api.patch(f"/api/demos/{did}/align/script", json={"intake_q1":"What would you like to explore?", "checkins":[{"segment_id":"proof", "text":"Does that suit your use?"}], "segments":[{"id":"proof", "title":"Dimensions", "outcome":""}], "realign_visuals":False})
        saved_script = store.read_json(did, "script.json")
        check("align review: intake, checkin and metadata save without line edits or a paid call",
              result.status_code == 200 and saved_script["intake_q1"] == "What would you like to explore?"
              and saved_script["segments"][0]["checkin"] == "Does that suit your use?"
              and saved_script["segments"][0]["title"] == "Dimensions" and saved_script["segments"][0]["outcome"] == "" and not realign.called)
        check("align review: question edits clear only their stale audio and disable the old second intake",
              saved_script["intake_audio"] == {} and saved_script["intake_q2"] == "" and saved_script["segments"][0]["checkin_audio"] is None
              and saved_script["segments"][0]["lines"][0]["audio"] == "keep.wav")
        current = store.load(did)
        check("align review: question review invalidates downstream audio/deck and requires script/visual approval",
              current["stages"]["author"]["status"] == "done" and current["stages"]["voice"]["status"] == "stale"
              and current["stages"]["deck"]["status"] == "stale" and not current["approvals"]["script"] and not current["approvals"]["visuals"])
        for label, payload, status in (
            ("uncited intake equipment count", {"intake_q1":"Would 6 airbags reassure you?"}, 400),
            ("uncited checkin claim", {"checkins":[{"segment_id":"proof", "text":"Does the best-in-class safety suit you?"}]}, 400),
            ("unknown checkin segment", {"checkins":[{"segment_id":"missing", "text":"Does it fit?"}]}, 404),
            ("duplicate checkin segment", {"checkins":[{"segment_id":"proof", "text":"Does it fit?"}]*2}, 400),
            ("second intake", {"intake_q1":"What matters?", "intake_q2":"Anything else?"}, 400),
            ("empty intake", {"intake_q1":" "}, 400),
            ("uncited metadata", {"segments":[{"id":"intro", "outcome":"Get 6 airbags."}]}, 400),
            ("structural segment edit", {"segments":[{"id":"proof", "role":"opening"}]}, 400),
            ("unknown metadata segment", {"segments":[{"id":"missing", "title":"New"}]}, 404),
            ("mixed valid question and invalid line", {"intake_q1":"What would you like?", "lines":[{"id":"missing", "text":"Hello."}]}, 404),
        ):
            before = snapshot()
            result = api.patch(f"/api/demos/{did}/align/script", json={**payload, "realign_visuals":False})
            check(f"align review: {label} rejects atomically", result.status_code == status and snapshot() == before)
        result = api.patch(f"/api/demos/{did}/align/script", json={"lines":[{"id":"proof-L1", "text":"Length is 3990 mm.", "fact_ids":["F001"]}], "checkins":[{"segment_id":"proof", "text":""}], "segments":[{"id":"proof", "outcome":"Length is 3990 mm."}], "realign_visuals":False})
        check("align review: existing cited line edits combine with cited metadata and explicit checkin removal",
              result.status_code == 200 and store.read_json(did, "script.json")["segments"][0]["checkin"] == ""
              and store.read_json(did, "script.json")["segments"][0]["outcome"] == "Length is 3990 mm.")

        # Reproduce script correction followed by a slide-design edit that marks
        # the deck done while its embedded narration still contains the old draft.
        current_script = store.read_json(did, "script.json")
        current_script["segments"][0].update(topic="dimensions", usp_ids=["reviewed-usp"], deeper=[{"id":"proof-D1", "text":"Old deeper detail.", "fact_ids":[]}])
        current_script["segments"][1]["topic"] = "overview"
        current_script["closing"] = [{"id":"close-L1", "text":"Old closing.", "fact_ids":[]}]
        store.write_json(did, "script.json", current_script)
        callout = {"id":"sl01-c1", "text":"Reviewed label", "fact_ids":["F001"], "placement":"panel", "label_pos":{"x":0.25,"y":0.35}}
        stale_deck = {"slides":[
            {"id":"sl00", "kind":"hero_open", "title":"Product hero", "lines":[], "image_id":None, "callouts":[]},
            {"id":"sl01", "segment_id":"proof", "kind":"proof", "role":"proof", "title":"Reviewed slide title", "image_id":None,
             "callouts":[copy.deepcopy(callout)], "motion":"pan_left", "topics":["old topic"], "usp_ids":["old-usp"], "fact_ids":["FREJECTED"],
             "lines":[{"id":"proof-L1", "text":"Rejected raw 6 airbags claim.", "fact_ids":["FREJECTED"]}],
             "deeper":[{"id":"proof-D1", "text":"Rejected deeper claim.", "fact_ids":["FREJECTED"]}], "checkin":"Rejected old question?"},
            {"id":"sl02", "kind":"closing", "title":"Reviewed closing title", "image_id":None, "callouts":[],
             "lines":[{"id":"close-L1", "text":"Rejected closing.", "fact_ids":[]}]}], "version":1}
        overrides = {"slides":[{"slide_id":"sl01", "title":"Reviewed slide title", "callouts":[copy.deepcopy(callout)]}]}
        store.write_json(did, "deck.json", stale_deck)
        store.write_json(did, "deck-overrides.json", overrides)
        result = api.patch(f"/api/demos/{did}/align/script", json={"lines":[
            {"id":"proof-L1", "text":"Explore the reviewed dimensions.", "fact_ids":[]},
            {"id":"proof-D1", "text":"Here is the reviewed detail.", "fact_ids":[]},
            {"id":"close-L1", "text":"Choose what to explore next.", "fact_ids":[]}],
            "checkins":[{"segment_id":"proof", "text":""}], "segments":[{"id":"proof", "title":"Updated script section", "outcome":"Reviewed fit"}], "realign_visuals":False})
        preview = result.json()["cards"]["deck"]["slides"][1]
        check("align preview: script-edit response uses reviewed narration, citations, deeper text and explicit empty checkin",
              result.status_code == 200 and preview["lines"][0]["text"] == "Explore the reviewed dimensions."
              and preview["lines"][0]["fact_ids"] == [] and preview["fact_ids"] == [] and preview["checkin"] == ""
              and preview["deeper"][0]["text"] == "Here is the reviewed detail.")
        check("align preview: segment metadata refresh preserves reviewed slide title, image, motion and dragged label",
              preview["title"] == "Reviewed slide title" and preview["image_id"] is None and preview["motion"] == "pan_left"
              and preview["callouts"] == [callout] and preview["topics"] == ["dimensions"]
              and preview["usp_ids"] == ["reviewed-usp"] and preview["outcome"] == "Reviewed fit"
              and store.read_json(did, "deck-overrides.json") == overrides)
        result = api.patch(f"/api/demos/{did}/align/deck", json={"slides":[{"slide_id":"sl01", "title":"Final reviewed heading"}]})
        preview_slides = result.json()["cards"]["deck"]["slides"]
        check("align preview: a later deck edit cannot resurrect the raw script in the review response",
              result.status_code == 200 and preview_slides[1]["title"] == "Final reviewed heading"
              and preview_slides[1]["lines"][0]["text"] == "Explore the reviewed dimensions."
              and preview_slides[1]["checkin"] == "" and preview_slides[2]["lines"][0]["text"] == "Choose what to explore next.")
        current_script = store.read_json(did, "script.json")
        current_script["segments"][0]["lines"].append({"id":"unsafe-L1", "text":"Rejected 6 airbags claim.", "fact_ids":[], "unverified":True})
        store.write_json(did, "script.json", current_script)
        deck_bytes = store.path(did, "deck.json").read_bytes()
        override_bytes = store.path(did, "deck-overrides.json").read_bytes()
        cards = align.cards(did)
        check("align preview: reading current narration drops unverified lines without rewriting design artifacts",
              [line["id"] for line in cards["deck"]["slides"][1]["lines"]] == ["proof-L1"]
              and store.path(did, "deck.json").read_bytes() == deck_bytes and store.path(did, "deck-overrides.json").read_bytes() == override_bytes)
        built = bundle.build(did, lambda _message:None)
        check("align preview: bundle and review agree on current text, citations, empty questions and rejected-line filtering",
              built["slides"][1]["lines"][0]["text"] == cards["deck"]["slides"][1]["lines"][0]["text"]
              and built["slides"][1]["lines"][0]["fact_ids"] == [] and built["slides"][1]["fact_ids"] == []
              and built["slides"][1]["checkin"]["text"] == "" and len(built["slides"][1]["lines"]) == 1
              and built["slides"][1]["title"] == "Final reviewed heading" and built["slides"][1]["callouts"] == cards["deck"]["slides"][1]["callouts"])
        check("align review: no model, speech or outbound network calls", not any(mock.called for mock in blocked))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    rows = []
    def check(name, ok, detail=""):
        rows.append(bool(ok)); print(("PASS " if ok else "FAIL ") + name + (" — " + detail if detail else ""))
    run(check)
    print(f"Align review contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)
