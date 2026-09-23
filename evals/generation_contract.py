"""Free generation-input and approval contracts, with provider/network calls blocked.

These exercise real stage assembly and deterministic filters with proposed model
outputs. They do NOT test whether a model follows the evidence instructions;
fixtures/generation_grounding.json supplies adversarial cases for real review.
"""
from __future__ import annotations

import copy
import json
import hashlib
import shutil
import sys
import tempfile
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check, demo_id: str = "generation-fixture") -> None:
    from server import config, media, schemas, sources, store
    from server.agents import author, deck, plan, principles, qa, understand, visuals, voice
    from server.llm import mock

    source = {"ref": "src-product", "locator": "page 4 / diesel column / footnote †",
              "quote": 'Peak torque: "250 Nm"\nDiesel automatic only†'}
    fact = {"id": "F001", "kind": "spec", "claim": "Diesel automatic peak torque", "value": "250 Nm",
            "conditions": "Diesel automatic only; source lists peak output, not acceleration",
            "truth": "stated", "source": source, "confidence": 1, "approved": True}
    rejected = {**copy.deepcopy(fact), "id": "F002", "claim": "REJECTED PRODUCT CLAIM", "approved": False,
                "source": {"ref": "src-product", "locator": "rejected-locator", "quote": "REJECTED QUOTE"}}
    legacy = {"id": "F003", "kind": "feature", "claim": "Headlamp", "value": "LED", "source": {"ref": "src-product"}}
    product = {"name": "Fixture car", "category": "Car", "summary": "A product fixture.", "audience": "Buyers"}
    brand = {"tone": "Warm and direct", "voice_style": "Calm", "dos": [], "donts": [], "persona_hint": "A guide"}
    und = {"product": product, "brand": brand, "facts": [fact, rejected, legacy], "unknowns": [], "images": [], "shots": [], "competitors": []}
    demo = {"id": demo_id, "name": "Generation fixture", "product": product,
            "settings": {"audience": "everyday", "competition": "off"}, "sources": []}
    files = {"understanding.json": und, "plan.json": None, "script.json": None}
    source_rows = [
        {"id": "src-product", "name": "Product table", "kind": "text", "role": "product"},
        {"id": "src-rival", "name": "Rival table", "kind": "text", "role": "competitor"},
    ]
    source_text = {"src-product": "PRODUCT ONLY. Diesel automatic: 250 Nm. ISO volume method does not certify the vehicle.",
                   "src-rival": "RIVAL ONLY. Petrol automatic: 6 speeds. Applies to VX only."}

    with ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=True))
        stack.enter_context(patch.object(store, "load", side_effect=lambda _id: copy.deepcopy(demo)))
        stack.enter_context(patch.object(store, "read_json", side_effect=lambda _id, name: copy.deepcopy(files.get(name))))
        stack.enter_context(patch.object(store, "write_json"))
        stack.enter_context(patch.object(store, "update"))
        stack.enter_context(patch.object(store, "log"))
        stack.enter_context(patch.object(media, "enhance_images"))
        stack.enter_context(patch.object(visuals, "build_map", return_value={}))
        stack.enter_context(patch.object(visuals, "align", side_effect=lambda _id, script, _und, _emit: script))
        stack.enter_context(patch.object(visuals, "for_facts", return_value=None))
        network = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected outbound call")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        providers = [stack.enter_context(patch(name, side_effect=AssertionError("Unexpected provider call")))
                     for name in ("server.llm.gemini.client", "server.llm.runware._post", "server.llm.claude._client_opts")]

        # Exercise both extraction calls; inspect the complete model envelopes,
        # not the source file or a copied prompt assembled by this test.
        demo["sources"] = source_rows
        files["understanding.json"] = None
        extraction_calls = []
        def extract(system, content, schema, **_kwargs):
            extraction_calls.append((schema, system, copy.deepcopy(content)))
            row = schemas.FactOut.model_validate(fact)
            if schema is schemas.FactsOut:
                return schemas.FactsOut(product=schemas.Product(**product), brand=schemas.Brand(**brand), facts=[row], unknowns=[])
            assert schema is schemas.CompetitorsOut
            return schemas.CompetitorsOut(competitors=[schemas.CompetitorOut(name="Rival", facts=[row])])
        with patch.object(sources, "source_text", side_effect=lambda _id, src, **_kwargs: {"name": src["name"], "text": source_text[src["id"]]}), \
                patch.object(understand.claude, "structured", side_effect=extract):
            understand.run(demo_id, lambda _msg: None)
        for schema in (schemas.FactsOut, schemas.CompetitorsOut):
            call = next(row for row in extraction_calls if row[0] is schema)
            check(f"generation: {schema.__name__} receives the same truth and scope instructions", principles.TRUTH_RULES in call[1])
        product_prompt = repr(next(row[2] for row in extraction_calls if row[0] is schemas.FactsOut))
        rival_prompt = next(row[2] for row in extraction_calls if row[0] is schemas.CompetitorsOut)
        check("generation: source applicability stays attached and product/rival extraction stays separate",
              source_text["src-product"] in product_prompt and "RIVAL ONLY" not in product_prompt
              and source_text["src-rival"] in rival_prompt and "PRODUCT ONLY" not in rival_prompt)
        check("generation: old fact rows still default to stated without a schema migration",
              schemas.FactOut.model_validate({k: v for k, v in fact.items() if k != "truth"}).truth == "stated")
        files["understanding.json"] = und
        demo["sources"] = []

        proposed_plan = mock.fake(schemas.Plan)
        for row in proposed_plan.usps + proposed_plan.segments + proposed_plan.concerns:
            row.fact_ids = ["F001", "F002", "F003", "F404"]
        with patch.object(plan.claude, "structured", return_value=proposed_plan) as model:
            planned = plan.run(demo_id, lambda _msg: None)
        plan_system, plan_input = model.call_args.args[:2]
        quote = json.dumps(source["quote"], ensure_ascii=False)
        required = [fact["conditions"], source["ref"], source["locator"], quote, "[spec·stated]", "250 Nm"]
        check("generation: planner receives exact quote, locator, units, truth and applicability",
              all(value in plan_input for value in required))
        check("generation: planner excludes rejected product evidence from current registry input",
              "REJECTED PRODUCT CLAIM" not in plan_input and "REJECTED QUOTE" not in plan_input)
        for key in ("usps", "segments", "concerns"):
            referenced = [x for row in planned[key] for x in row["fact_ids"]]
            check(f"generation: proposed {key} cannot restore rejected or unknown citations",
                  "F001" in referenced and "F003" in referenced and "F002" not in referenced and "F404" not in referenced)
        check("generation: legacy rows with no quote or locator remain usable without invented evidence",
              'F003 [feature·stated] Headlamp: LED (source: src-product; locator: not supplied; quote: "")' in plan_input)
        files["plan.json"] = planned

        # A harmless script and one complete technical deeper answer test that
        # the actual author path retains unit-bearing detail for an everyday user.
        line = {"text": "Take a look at the choices for your drive.", "visual": {"kind": "none"}, "fact_ids": []}
        technical = {"text": "The diesel automatic has peak torque of 250 Nm.", "visual": {"kind": "none"}, "fact_ids": ["F001"]}
        proposed_script = schemas.ScriptOut(segments=[schemas.SegmentOut(id="drive", title="Your drive", role="proof",
            topic="performance", lines=[schemas.LineOut(**line)], checkin="Let’s keep exploring.",
            deeper=[schemas.LineOut(**technical)])], closing=[], intake_q1="Welcome. Shall we explore?", intake_q2="")
        with patch.object(author.claude, "structured", return_value=proposed_script) as model:
            scripted = author.run(demo_id, lambda _msg: None)
        author_system, author_input = model.call_args.args[:2]
        check("generation: author receives original source evidence alongside the plan",
              all(value in author_input for value in required))
        check("generation: planner and author both receive the evidence-to-relevance rules",
              principles.EVIDENCE_RULES in plan_system and principles.EVIDENCE_RULES in author_system)
        check("generation: complete technical quantities survive in deeper detail without a jargon repair",
              model.call_count == 1 and not scripted["issues"]
              and scripted["segments"][0]["deeper"][0]["text"] == technical["text"])
        jargon = copy.deepcopy(scripted)
        jargon["segments"][0]["lines"] = [copy.deepcopy(scripted["segments"][0]["deeper"][0])]
        issues = author.validate(jargon, und)
        check("generation: a jargon repair requests moving the whole quantity, never deleting its unit",
              any("complete technical quantity" in issue and "never keep a number while dropping its unit" in issue for issue in issues))

        def timed_script(count, role="proof"):
            return {"segments": [{"id": "timed", "title": "A useful stop", "role": role,
                                  "lines": [{"text": " ".join(["Look"] * count), "fact_ids": []}],
                                  "deeper": [], "checkin": ""}], "closing": []}
        timing_plan = {"segments": [{"id": "timed", "word_budget": 30, "stop_id": "engine", "fundamental": True}]}
        longer = timed_script(35)
        issues = author.validate(longer, und, timing_plan, demo)
        check("generation: Author enforces the planner allowance plus four words", any("over its budget of 30" in issue for issue in issues) and not any("over its budget" in issue for issue in author.validate(timed_script(34), und, timing_plan, demo)))
        issues = author.validate(timed_script(19), und, timing_plan, demo)
        check("generation: an explicit short allocation gets an advisory join warning", any("warning" in issue and "well under budget; add the join or the moment" in issue for issue in issues))
        check("generation: missing legacy budgets do not invent under-budget warnings", not any("well under budget" in issue for issue in author.validate(timed_script(10), und)))
        ceiling = author.validate(timed_script(47), und, {"segments": [{"id": "timed", "word_budget": 46}]}, demo)
        check("generation: role ceiling remains hard inside the budget tolerance", any("limit 46" in issue for issue in ceiling) and not any("over its budget" in issue for issue in ceiling))
        route = {"segments": [], "closing": [{"text": " ".join(["Look"] * 45), "fact_ids": []}]}
        for index, (role, count) in enumerate([("intro", 40), ("outcome", 40), ("proof", 46), ("proof", 46), ("proof", 46), ("features", 48), ("establish", 44)]):
            segment = timed_script(count, role)["segments"][0]; segment["id"] = f"route-{index}"; route["segments"].append(segment)
        two, four = {"settings": {"pitch_minutes": 2}}, {"settings": {"pitch_minutes": 4}}
        check("generation: route ceiling follows two-minute and four-minute settings", author.route_limit(two) == 268 and author.route_limit(four) == 496 and any("a full route" in issue for issue in author.validate(copy.deepcopy(route), und, {}, two)) and not any("a full route" in issue for issue in author.validate(copy.deepcopy(route), und, {}, four)))
        timing = author.timeline(longer)
        check("generation: timing carries planned duration separately from estimates", longer["segments"][0]["word_budget"] == 30 and longer["segments"][0]["stop_id"] == "engine" and longer["segments"][0]["fundamental"] and longer["segments"][0]["planned_seconds"] == 15.8 and timing["planned_total_seconds"] == 39.5 and not timing["measured"] and not timing["exact"])
        unplanned = timed_script(20)
        check("generation: legacy timing leaves absent planned durations unknown", author.timeline(unplanned)["planned_total_seconds"] is None and unplanned["segments"][0]["planned_seconds"] is None)
        split = timed_script(20)
        split["segments"][0]["lines"] *= 3
        split_plan = {"segments": [{"id": "timed", "word_budget": 44, "stop_id": "engine", "fundamental": True}]}
        author.validate(split, und, split_plan, demo)
        added = author.split_long_batches(split)
        before_recheck = [segment["word_budget"] for segment in split["segments"]]
        author.validate(split, und, split_plan, demo)
        split_timing = author.timeline(split)
        check("generation: split and revalidation preserve one original planned allowance", added == 1 and before_recheck == [29, 15] and [segment["word_budget"] for segment in split["segments"]] == before_recheck and split_timing["planned_total_seconds"] == round(89 / author.WPS, 1) and all(segment["budget_source_id"] == "timed" for segment in split["segments"]))
        measured = timed_script(20)
        measured["segments"][0]["lines"][0]["audio"] = "main.wav"
        measured["segments"][0].update(word_budget=30, checkin="Let’s continue.", checkin_audio="checkin.wav")
        measured["closing"] = [{"text": "Take the next step.", "fact_ids": [], "audio": "closing.wav"}]
        with patch.object(author, "_audio_seconds", side_effect=lambda _did, rel: {"main.wav": 10.0}.get(rel)):
            mixed = author.timeline(measured, "fixture")
        check("generation: any measured main line keeps exact but incomplete checkin and closing stay mixed", mixed["exact"] and not mixed["measured"] and not measured["segments"][0]["measured"])
        with patch.object(author, "_audio_seconds", side_effect=lambda _did, rel: {"main.wav": 10.0, "checkin.wav": 1.0, "closing.wav": 2.0}.get(rel)):
            complete = author.timeline(measured, "fixture")
        check("generation: fully recorded narration checkin and closing are measured", complete["exact"] and complete["measured"] and measured["segments"][0]["measured"] and complete["total_seconds"] == 13.0)

        legacy_root = Path(__file__).resolve().parents[1] / "data/demos/dm_41513908"
        legacy_names = ("script.json", "plan.json", "understanding.json", "demo.json")
        if all((legacy_root / name).is_file() for name in legacy_names):
            before_hashes = {name: hashlib.sha256((legacy_root / name).read_bytes()).hexdigest() for name in legacy_names}
            with tempfile.TemporaryDirectory(prefix="legacy-creta-budget-") as tmp:
                for name in legacy_names:
                    shutil.copy2(legacy_root / name, Path(tmp) / name)
                copies = {name: json.loads((Path(tmp) / name).read_text()) for name in legacy_names}
                legacy_issues = author.validate(copies["script.json"], copies["understanding.json"], copies["plan.json"], copies["demo.json"])
            check("generation: isolated legacy Creta retains its budget validity; only legacy question checkins require new-authoring repair",
                  all("checkin: must be a short closing statement, never a question" in issue for issue in legacy_issues))
            check("generation: legacy Creta source artifacts remain byte-identical", before_hashes == {name: hashlib.sha256((legacy_root / name).read_bytes()).hexdigest() for name in legacy_names})

        slide = {"id": "sl01", "kind": "proof", "title": "Driving choices", "image_id": None,
                 "lines": [{"text": technical["text"], "fact_ids": ["F001"]}]}
        approved = {row["id"]: row for row in und["facts"] if row.get("approved", True)}
        with patch.object(deck.claude, "structured", return_value=deck.DeckOut(titles=[], callouts=[])) as model:
            deck._ask_model(demo, und, planned, [slide], {}, approved)
        deck_system = model.call_args.args[0]
        check("generation: deck receives current quote, locator, units, truth and applicability",
              all(value in deck_system for value in required)
              and "REJECTED PRODUCT CLAIM" not in deck_system and "REJECTED QUOTE" not in deck_system)
        check("generation: deck receives shared evidence rules and permits omission when scope cannot fit",
              principles.EVIDENCE_RULES in deck_system and "omit the callout" in deck_system
              and "neutral specification" in model.call_args.args[2].model_json_schema()["$defs"]["CalloutOut"]["properties"]["text"]["description"])

        for live in (False, True):
            proposed_answer = schemas.QAOut(answer="The diesel automatic's peak torque is 250 Nm, or newton metres.", fact_ids=["F001"], answered=True)
            target = qa.runtime if live else qa.claude
            label = "runtime" if live else "build FAQ"
            with patch.object(target, "structured", return_value=proposed_answer) as model, \
                    patch.object(voice, "render_line", return_value="audio/fixture.wav") as speak:
                reply = qa.answer(demo_id, "What is its torque?", live=live, voice_it=True)
            system = model.call_args.args[0]
            check(f"generation: {label} receives the full product evidence and rules",
                  all(value in system for value in required) and principles.EVIDENCE_RULES in system)
            check(f"generation: {label} excludes rejected product evidence",
                  "REJECTED PRODUCT CLAIM" not in system and "REJECTED QUOTE" not in system)
            check(f"generation: {label} delivers a complete unit-bearing answer unchanged to speech",
                  reply["answered"] and reply["answer"] == proposed_answer.answer
                  and speak.call_args.args[1] == proposed_answer.answer)

        # Test the real QA input envelope, not whether a mocked model obeys it.
        # The explicit-terms control must retain known relationships/exclusions;
        # this rule must not turn every policy answer into an unknown.
        policy_cases = [
            ("unknown relationship", "2 years | 40,000 km",
             "Headline only; relation between the duration and distance limits, exclusions and transferability are not supplied."),
            ("explicit relationship and exclusion", "4 years or 80,000 km, whichever occurs first",
             "Whichever occurs first; commercial use excluded. These are the supplied written terms."),
        ]
        for label, value, conditions in policy_cases:
            policy = {**copy.deepcopy(fact), "id": "F004", "kind": "policy", "truth": "contractual",
                      "claim": "Advertised equipment warranty", "value": value, "conditions": conditions,
                      "source": {"ref": "src-policy", "locator": "policy sheet / warranty panel", "quote": value}}
            files["understanding.json"] = {**copy.deepcopy(und), "facts": [policy]}
            for live in (False, True):
                target = qa.runtime if live else qa.claude
                proposed = schemas.QAOut(answer="I can confirm only the supplied terms.", fact_ids=["F004"], answered=True)
                with patch.object(target, "structured", return_value=proposed) as model:
                    qa.answer(demo_id, "What does the warranty headline establish?", live=live, voice_it=False)
                envelope = model.call_args.args[0]
                check(f"generation: {'runtime' if live else 'build FAQ'} policy envelope retains {label} and headline rule",
                      all(piece in envelope for piece in (value, conditions, json.dumps(value), policy["source"]["locator"],
                          "[policy·contractual]", "a headline is not the complete policy", "Preserve explicit unknowns",
                          "Retain a relationship or coverage rule when the source explicitly states it"))
                      and model.call_args.args[2] is schemas.QAOut)
        files["understanding.json"] = und

        # A greeting or ordinary answer must not invite a second model-owned
        # question before the player's satisfaction check. This verifies prompt
        # delivery for each response mode, not a provider's future compliance.
        turn_cases = [
            ("greeting", "Hello", schemas.QAOut(answer="I'm here with you.", fact_ids=[], answered=True)),
            ("ordinary answer", "What is its torque?", schemas.QAOut(answer="Peak torque is 250 Nm.", fact_ids=["F001"], answered=True)),
            ("clarification", "Does the cheaper one have that?", schemas.QAOut(answer="Which version do you mean?", fact_ids=[], answered=True, clarifying_question="Which version do you mean?")),
        ]
        for label, question, proposed in turn_cases:
            for live in (False, True):
                with patch.object(qa.runtime if live else qa.claude, "structured", return_value=proposed) as model:
                    qa.answer(demo_id, question, live=live, voice_it=False)
                envelope = model.call_args.args[0]
                check(f"generation: {'runtime' if live else 'build FAQ'} {label} envelope assigns questions to one owner",
                      model.call_args.args[1] == question and model.call_args.args[2] is schemas.QAOut
                      and all(rule in envelope for rule in ("The player listens briefly after an ordinary answer", "Use statements for ordinary answers",
                          "Only clarifying_question may ask a question", "answer must be that identical single question",
                          "mention available technical detail as a statement"))
                      and "offer the technical detail rather than volunteering it" not in envelope)

        # A crowded comparison must receive a brevity budget together with both
        # sides' scope and the mandatory caveat; the fixture does not score prose.
        comparison_fact = {**copy.deepcopy(fact), "id": "F007", "claim": "Automatic transmission",
                           "value": "7-speed dual-clutch", "conditions": "Premium petrol trim only; not the diesel variant."}
        rival_fact = {**copy.deepcopy(fact), "id": "C1-001", "claim": "Automatic transmission",
                      "value": "6-speed automatic", "conditions": "GX 1.5 petrol trim only; no relative smoothness claim.",
                      "source": {"ref": "src-rival", "locator": "variant table / GX petrol column", "quote": "6-speed automatic"}}
        files["understanding.json"] = {**copy.deepcopy(und), "facts": [comparison_fact],
            "competitors": [{"name": "Fixture rival", "source_id": "src-rival", "fetched_at": 1704067200,
                             "facts": [rival_fact]}]}
        demo["settings"]["competition"] = "on"
        profile = {"why": "I want an automatic and child-seat practicality."}
        for live in (False, True):
            proposed = schemas.QAOut(answer="These are the two listed automatic choices.", fact_ids=["F007", "C1-001"], answered=True)
            with patch.object(qa.runtime if live else qa.claude, "structured", return_value=proposed) as model:
                qa.answer(demo_id, "How do my selected trims compare?", profile=profile, live=live, voice_it=False)
            envelope = model.call_args.args[0]
            check(f"generation: {'runtime' if live else 'build FAQ'} comparison envelope carries focus, scope and full caveat",
                  all(piece in envelope for piece in ("within 60 words, including required caveats", "A direct single-fact answer can use one sentence",
                      "choose one shared dimension relevant to this buyer", "A second dimension is optional only when both sides",
                      "Do not compare unrelated feature lists", "omit that dimension; never shorten away its scope",
                      comparison_fact["conditions"], rival_fact["conditions"], rival_fact["source"]["locator"], profile["why"],
                      "that is as per their website when we checked — please verify on their site")))

        # Reviewed demo examples identify the referent, not a customer's choice
        # or new fact evidence. Fake outputs prove the actual input/clarification
        # path only; they do not claim a model will follow the precedence rule.
        original_notes = files["plan.json"].get("notes", "")
        example_notes = "Comparison example: Fixture rival GX 1.5 petrol automatic. This is not an inferred buyer selection."
        files["plan.json"]["notes"] = example_notes
        demo["approvals"] = {"script": True}
        selected_question = "What differs from the selected demo variant of Fixture rival?"
        for live in (False, True):
            with patch.object(qa.runtime if live else qa.claude, "structured", return_value=proposed) as model:
                qa.answer(demo_id, selected_question, profile=profile, live=live, voice_it=False)
            envelope = model.call_args.args[0]
            check(f"generation: {'runtime' if live else 'build FAQ'} receives reviewed demo example separately from buyer and fact evidence",
                  example_notes in envelope and "DEMO COMPARISON CONTEXT" in envelope
                  and all(value in envelope for value in (comparison_fact["conditions"], rival_fact["conditions"],
                      rival_fact["source"]["locator"], json.dumps(rival_fact["source"]["quote"])))
                  and model.call_args.args[1] == selected_question
                  and "not buyer selections or factual evidence" in envelope)
        correction = {"why": "I mean Fixture rival LX manual, not the GX automatic example."}
        with patch.object(qa.runtime, "structured", return_value=proposed) as model:
            qa.answer(demo_id, "What about that version?", profile=correction, live=True, voice_it=False)
        envelope = model.call_args.args[0]
        check("generation: explicit buyer variant overrides the demo example without becoming an inferred preference",
              correction["why"] in envelope and example_notes in envelope
              and "explicit customer variant or correction takes precedence" in envelope
              and "never infer a buyer selection or preference from these notes" in envelope)
        clarification = schemas.QAOut(answer="Which version do you mean?", answered=True, fact_ids=[],
                                      clarifying_question="Which version do you mean?")
        for label, notes in (("missing", ""), ("ambiguous", "Comparison examples: Fixture rival GX automatic or LX manual; neither is selected.")):
            files["plan.json"]["notes"] = notes
            with patch.object(qa.runtime, "structured", return_value=clarification) as model:
                reply = qa.answer(demo_id, selected_question, profile=profile, live=True, voice_it=False)
            envelope = model.call_args.args[0]
            check(f"generation: {label} demo configuration retains the existing clarification path",
                  reply["clarifying_question"] == clarification.clarifying_question
                  and "missing or ambiguous" in envelope and "when it changes the answer" in envelope
                  and (notes in envelope if notes else example_notes not in envelope))
        files["plan.json"]["notes"] = example_notes
        for label, competition, approved in (("competition disabled", "off", True), ("script unapproved", "on", False)):
            demo["settings"]["competition"], demo["approvals"]["script"] = competition, approved
            with patch.object(qa.runtime, "structured", return_value=clarification) as model:
                qa.answer(demo_id, selected_question, profile=profile, live=True, voice_it=False)
            check(f"generation: {label} cannot supply an unreviewed comparison example", example_notes not in model.call_args.args[0])
        files["plan.json"]["notes"] = original_notes
        demo["settings"]["competition"] = "on"
        demo.pop("approvals")
        files["understanding.json"]["facts"].append(policy)
        shortlist = {"why": "I am considering Fixture car and Fixture rival."}
        prior = [{"role": "user", "text": "Compare the selected automatic versions."},
                 {"role": "assistant", "text": "Those are the listed transmission choices."}]
        question = "What warranty does Fixture car provide?"
        for live in (False, True):
            proposed = schemas.QAOut(answer="The supplied terms apply to Fixture car.", fact_ids=["F004"], answered=True)
            with patch.object(qa.runtime if live else qa.claude, "structured", return_value=proposed) as model:
                qa.answer(demo_id, question, history=prior, profile=shortlist, live=live, voice_it=False)
            envelope = model.call_args.args[0]
            check(f"generation: {'runtime' if live else 'build FAQ'} current product scope survives a previous comparison",
                  model.call_args.args[1] == question and shortlist["why"] in envelope
                  and any(message["content"] == prior[0]["text"] for message in model.call_args.kwargs["history"])
                  and all(rule in envelope for rule in ("Answer the current question's product and scope",
                      "a previous shortlist or comparison is not a new request to compare",
                      "Do not add another brand's policy or features unless the current question asks for that comparison")))
        files["understanding.json"] = und
        demo["settings"]["competition"] = "off"

        check("generation: all contracts avoid actual provider and network calls",
              not any(call.called for call in providers + network))


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    rows = []
    def check(name, ok, detail=""):
        rows.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + name + (" — " + detail if detail else ""))
    run(check)
    print(f"Generation input/approval contracts: {sum(rows)}/{len(rows)} (model entailment not evaluated)")
    raise SystemExit(0 if all(rows) else 1)
