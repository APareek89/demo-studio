"""Free customer-facing content contracts; no model, voice or network calls.

qa_deck supplies its check collector. Fixtures deliberately include plausible
but unsafe model output, not just successful responses.
"""
from __future__ import annotations

import copy
from contextlib import ExitStack
from unittest.mock import patch


def run(check, demo_id: str) -> None:
    from server import config, schemas, store
    from server.agents import author, bundle, deck, pitch, qa, voice, visuals

    slide = {"id": "sl01", "title": "Everyday details", "image_id": None,
             "lines": [{"id": "proof-L1", "text": "See the lamp.", "fact_ids": ["F1"]}], "callouts": []}
    long_fact = {"claim": "Charger supplied", "value": "portable new charger that plugs into a suitable household socket"}
    check("customer: fallback callouts omit long facts instead of chopping a sentence",
          deck.derive_callouts(slide, {"F1": long_fact}, None) == [])
    check("customer: a complete short fallback label survives unchanged",
          deck.derive_callouts(slide, {"F1": {"claim": "Headlamp", "value": "LED"}}, None)[0]["text"] == "Headlamp: LED")
    conditional = {"claim": "Storage", "value": "under the seat", "conditions": "only when the optional accessory is not fitted"}
    check("customer: fallback never drops a long applicability condition to fit a label",
          deck.derive_callouts(slide, {"F1": conditional}, None) == [])
    conditional = {"claim": "Storage", "value": "under seat", "conditions": "selected variants"}
    check("customer: short fallback retains its applicability condition",
          "selected variants" in deck.derive_callouts(slide, {"F1": conditional}, None)[0]["text"])
    check("customer: an overlong title is omitted rather than cut mid-thought",
          deck._compact("The written terms that apply only when serviced", 6) == "")
    overridden = copy.deepcopy(slide)
    deck.apply_overrides([overridden], {"slides": [{"slide_id": "sl01", "title": "The written terms that apply only when serviced"}]}, {}, {"F1"})
    check("customer: unsafe title override keeps the existing complete title", overridden["title"] == slide["title"])

    line = {"id": "proof-L1", "text": "What matters most to you?", "step": "say", "fact_ids": [],
            "visual": {"kind": "none", "ref": "", "focus": ""}}
    script = {"intake_q1": "Welcome. What would you like to explore?", "intake_q2": "", "version": 1,
              "segments": [{"id": "proof", "title": "Everyday details", "role": "proof", "topic": "comfort",
                            "lines": [line], "checkin": "Shall we look closer?", "deeper": []}], "closing": []}
    und = {"product": {"name": "Fixture product"}, "facts": [], "shots": [], "images": []}
    issues = author.validate(copy.deepcopy(script), und)
    check("customer: narration cannot hide a question outside the explicit checkin",
          any("checkin" in issue and "question" in issue and "line" in issue for issue in issues))
    unsafe_script = copy.deepcopy(script)
    unsafe_script["segments"][0]["checkin"] = "Does the free 30-year warranty settle that?"
    unsafe_script["segments"][0]["checkin_audio"] = "stale.wav"
    issues = author.validate(unsafe_script, und)
    check("customer: moving an uncited claim into checkin cannot bypass grounding",
          any("checkin contains a figure or claim" in issue for issue in issues)
          and not unsafe_script["segments"][0]["checkin"] and unsafe_script["segments"][0]["checkin_audio"] is None)

    demo = {"name": "Fixture", "settings": {"audience": "everyday"}, "sources": []}
    plan = {"voice": {}, "segments": [], "ctas": []}
    fact = {"id": "F1", "kind": "spec", "claim": "Lamp", "value": "LED", "source": {"ref": "fixture"}, "truth": "stated"}
    und["facts"] = [fact]
    files = {"understanding.json": und, "script.json": script, "plan.json": plan}
    with ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=True))
        stack.enter_context(patch.object(store, "load", return_value=demo))
        stack.enter_context(patch.object(store, "read_json", side_effect=lambda _id, name: copy.deepcopy(files.get(name))))
        stack.enter_context(patch.object(store, "write_json"))
        stack.enter_context(patch.object(store, "update"))
        stack.enter_context(patch.object(store, "log"))
        stack.enter_context(patch.object(voice, "provider_for", return_value="browser"))
        voice_call = stack.enter_context(patch.object(voice, "render_line", side_effect=AssertionError("Unexpected voice call")))
        network = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected network call")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        stack.enter_context(patch.object(visuals, "catalogue", return_value=[]))
        stack.enter_context(patch.object(visuals, "for_facts", return_value=None))
        stack.enter_context(patch.object(visuals, "for_text_and_facts", return_value=None))

        line["step"] = "confirm"
        built = deck.build(demo_id, lambda _msg: None)
        check("customer: deck preserves an old script's explicit confirmation step",
              built["slides"][1]["lines"][0].get("step") == "confirm")
        files["deck.json"] = built
        files["script.hi-IN.json"] = copy.deepcopy(script)
        files["script.hi-IN.json"]["segments"][0]["lines"][0]["text"] = "क्या यह आपके लिए सही है?"
        demo["id"] = demo_id
        demo["settings"]["languages"] = ["en-IN", "hi-IN"]
        assembled = bundle.build(demo_id, lambda _msg: None)
        check("customer: main and translated bundle slides retain explicit question metadata",
              assembled["slides"][1]["lines"][0].get("step") == "confirm"
              and assembled["alt_languages"]["hi-IN"]["slides"][1]["lines"][0].get("step") == "confirm"
              and assembled["segments"][0]["lines"][0].get("step") == "confirm"
              and assembled["alt_languages"]["hi-IN"]["segments"][0]["lines"][0].get("step") == "confirm")

        # An old deck used positional ids before long-label omission. The edit
        # on its second fact must survive; the first fact's edit must not move.
        saved = {name: files.get(name) for name in ("understanding.json", "script.json", "deck.json", "deck-overrides.json")}
        review_und, review_script, review_deck = copy.deepcopy(und), copy.deepcopy(script), copy.deepcopy(built)
        review_und["facts"] = [{**fact, **long_fact}, {**fact, "id": "F2"}]
        review_script["segments"][0]["lines"][0]["fact_ids"] = ["F1", "F2"]
        review_deck["slides"][1]["callouts"] = [{"id": "sl01-c1", "text": "Old charger label", "fact_ids": ["F1"]},
                                                 {"id": "sl01-c2", "text": "Lamp: LED", "fact_ids": ["F2"]}]
        files.update({"understanding.json": review_und, "script.json": review_script, "deck.json": review_deck,
                      "deck-overrides.json": {"slides": [{"slide_id": "sl01", "callouts": [
                          {"id": "sl01-c1", "text": "Charger label from review", "fact_ids": ["F1"]},
                          {"id": "sl01-c2", "text": "LED headlamp", "fact_ids": ["F2"]}]}]}})
        rebuilt = deck.build(demo_id, lambda _msg: None)
        callouts = rebuilt["slides"][1]["callouts"]
        check("customer: omitting a long label preserves the surviving fact's reviewed callout id",
              any(c["id"] == "sl01-c2" and c["fact_ids"] == ["F2"] and c["text"] == "LED headlamp" for c in callouts))
        check("customer: explicit reviewed short copy survives omission of its long generated fallback",
              any(c["id"] == "sl01-c1" and c["fact_ids"] == ["F1"] and c["text"] == "Charger label from review" for c in callouts))
        files["deck.json"] = rebuilt
        review_script["segments"][0]["lines"][0]["fact_ids"] = ["F2"]
        rebuilt = deck.build(demo_id, lambda _msg: None)
        check("customer: a reviewed label is omitted when its citation no longer belongs to the slide",
              all(c["id"] != "sl01-c1" for c in rebuilt["slides"][1]["callouts"]))
        files["deck.json"] = rebuilt
        review_und["facts"].append({**fact, "id": "F3", "claim": "Seat", "value": "fabric"})
        review_script["segments"][0]["lines"][0]["fact_ids"].append("F3")
        rebuilt = deck.build(demo_id, lambda _msg: None)
        callouts = rebuilt["slides"][1]["callouts"]
        check("customer: an orphaned Align edit never attaches to a new fact on a later rebuild",
              all(c["id"] != "sl01-c1" for c in callouts)
              and any(c["fact_ids"] == ["F3"] and c["text"] == "Seat: fabric" for c in callouts))
        files.update(saved)

        mixed = schemas.QAOut(answer="The headlamp is LED.", fact_ids=["F1"], answered=True,
                              clarifying_question="Which part matters most to you?", escalate="Call customer", cta="")
        with patch.object(qa.runtime, "structured", return_value=mixed), \
                patch.object(qa, "_record_unknown") as unknown, patch.object(qa, "_clear_runtime_unknown") as cleared:
            result = qa.answer(demo_id, "Will it suit me?", live=True, voice_it=False)
        check("customer: clarification is spoken alone before an answer",
              result["answer"] == mixed.clarifying_question and result["clarifying_question"] == mixed.clarifying_question)
        check("customer: clarification carries no claim, visual, escalation or callback",
              result["answered"] and not result["fact_ids"] and not result["facts"] and result["visual"] is None
              and not result["escalate"] and not result["offer_callback"] and not unknown.called and not cleared.called)

        clarification_only = mixed.model_copy(update={"answer": "", "fact_ids": [], "answered": False})
        with patch.object(qa.runtime, "structured", return_value=clarification_only):
            result = qa.answer(demo_id, "Will it suit me?", live=True, voice_it=False)
        check("customer: an explicit clarification is not converted into a callback refusal",
              result["answer"] == mixed.clarifying_question and result["answered"] and not result["offer_callback"])

        unsafe = schemas.QAOut(answer="It will save you Rs 5000.", fact_ids=[], answered=True,
                               clarifying_question="With your 30 km commute, shall we continue?")
        with patch.object(qa.runtime, "structured", return_value=unsafe):
            result = qa.answer(demo_id, "What will it cost?", live=True, voice_it=False)
        check("customer: a clarification cannot smuggle uncited figures past grounding",
              not result["answered"] and result["offer_callback"] and not result["clarifying_question"])
        stacked = schemas.QAOut(answer="", fact_ids=[], answered=False,
                                clarifying_question="What is your routine? What matters most?")
        with patch.object(qa.runtime, "structured", return_value=stacked):
            result = qa.answer(demo_id, "Will it suit me?", live=True, voice_it=False)
        check("customer: stacked clarification questions are rejected instead of opening a wait",
              not result["clarifying_question"] and not result["answered"] and result["offer_callback"])
        action = schemas.QAOut(answer="Let's arrange that.", fact_ids=[], answered=True, cta="book",
                               clarifying_question="What matters most?")
        with patch.object(qa.runtime, "structured", return_value=action):
            result = qa.answer(demo_id, "Book a visit.", live=True, voice_it=False)
        check("customer: an explicit CTA does not also create a clarification wait",
              result["cta"] == "book" and result["answer"] == "Let's arrange that."
              and not result["clarifying_question"] and not result["offer_callback"])

        final_answer = schemas.QAOut(answer="The headlamp is LED.", fact_ids=["F1"], answered=True)
        history = [{"role": "user", "text": "Will it suit me?"},
                   {"role": "assistant", "text": "Which part matters most to you?"},
                   {"role": "user", "text": "Night driving."}]
        with patch.object(qa.runtime, "structured", return_value=final_answer) as model:
            result = qa.answer(demo_id, "Will it suit me?", history=history, profile={"followup": "Night driving."}, live=True, voice_it=False)
        check("customer: clarified answer retains the original question and actual reply in model context",
              result["answered"] and result["fact_ids"] == ["F1"] and model.call_args.args[1] == "Will it suit me?"
              and any(row["content"] == "Night driving." for row in model.call_args.kwargs["history"]))

        generated = schemas.PitchPlan(customer_state="stated_need", decision_frame="For your 30 km commute, let's start there.",
                                      follow_up_question="What is your budget?", primary_outcome="Comfort", focus_topics=["comfort"],
                                      route=[schemas.RouteStep(segment_id="proof", bridge="For your 30 km commute.", bridge_fact_ids=["F1"])],
                                      advance="Explore the details.",
                                      custom_batches=[schemas.CustomBatch(text="For your 30 km commute, see the lamp.", fact_ids=["F1"])])
        with patch.object(pitch.runtime, "structured", return_value=generated):
            personal = pitch.plan_pitch(demo_id, {"why": "I travel 5 to 10 km each day."}, refine=False)
            neutral = pitch.plan_pitch(demo_id, {}, refine=False)
        check("customer: route planning never adds a second intake question", personal["follow_up_question"] == "")
        check("customer: acknowledgement cannot invent a different customer distance", "30" not in personal["decision_frame"])
        check("customer: a valid fact id cannot license an unrelated invented customer quantity",
              not personal["custom_batches"] and all(not step.get("bridge") for step in personal["route"]))
        check("customer: a skipped intake cannot produce invented personal batches or bridges",
              neutral["customer_state"] == "unknown" and not neutral["custom_batches"]
              and all(not step.get("bridge") for step in neutral["route"]))
        written = generated.model_copy(deep=True)
        written.decision_frame = "For your thirty-kilometre commute, let's start there."
        written.route[0].bridge = "For your thirty-kilometre commute."
        written.custom_batches[0].text = "For your thirty-kilometre commute, see the lamp."
        with patch.object(pitch.runtime, "structured", return_value=written):
            personal = pitch.plan_pitch(demo_id, {"why": "I travel 5 to 10 km each day."})
        check("customer: spelling an invented customer quantity does not evade the context guard",
              "thirty" not in personal["decision_frame"] and not personal["custom_batches"]
              and all(not step.get("bridge") for step in personal["route"]))
        grounded = generated.model_copy(deep=True)
        grounded.decision_frame = "For your five-to-ten kilometre journey, let's start there."
        grounded.route[0].bridge = "For your five-to-ten kilometre journey, see the lamp."
        grounded.custom_batches[0].text = "For your five-to-ten kilometre journey, see the lamp."
        with patch.object(pitch.runtime, "structured", return_value=grounded):
            personal = pitch.plan_pitch(demo_id, {"why": "I travel 5 to 10 km each day."})
        check("customer: the real customer's quantities survive spoken-number normalization",
              personal["decision_frame"] == grounded.decision_frame and len(personal["custom_batches"]) == 1
              and personal["route"][0]["bridge"] == grounded.route[0].bridge)
        decimal = grounded.model_copy(deep=True)
        decimal.route[0].bridge = "For the journeys you mentioned, this uses a one point two litre engine."
        decimal.custom_batches[0].text = decimal.route[0].bridge
        decimal_und = copy.deepcopy(und)
        decimal_und["facts"] = [{**fact, "claim": "Engine capacity", "value": "1.2 L"}]
        files["understanding.json"] = decimal_und
        with patch.object(pitch.runtime, "structured", return_value=decimal):
            personal = pitch.plan_pitch(demo_id, {"why": "I travel 5 to 10 km each day."})
        check("customer: a cited decimal survives natural spoken rendering",
              len(personal["custom_batches"]) == 1 and personal["custom_batches"][0]["text"] == decimal.custom_batches[0].text
              and personal["route"][0]["bridge"] == decimal.route[0].bridge)
        files["understanding.json"] = und
        check("customer: content contracts made no network or voice calls", not voice_call.called and not any(x.called for x in network))


if __name__ == "__main__":
    rows = []
    run(lambda name, ok, detail="": rows.append((name, bool(ok), detail)), "fixture")
    for name, ok, detail in rows:
        print(("PASS" if ok else "FAIL") + " " + name + (": " + detail if detail else ""))
    print(f"{sum(ok for _, ok, _ in rows)}/{len(rows)} customer contracts passed")
    raise SystemExit(0 if all(ok for _, ok, _ in rows) else 1)
