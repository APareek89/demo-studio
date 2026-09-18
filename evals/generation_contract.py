"""Free generation-input and approval contracts, with provider/network calls blocked.

These exercise real stage assembly and deterministic filters with proposed model
outputs. They do NOT test whether a model follows the evidence instructions;
fixtures/generation_grounding.json supplies adversarial cases for real review.
"""
from __future__ import annotations

import copy
import json
import sys
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
        with patch.object(sources, "source_text", side_effect=lambda _id, src: {"name": src["name"], "text": source_text[src["id"]]}), \
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
            topic="performance", lines=[schemas.LineOut(**line)], checkin="What would you like to explore?",
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
                      and all(rule in envelope for rule in ("The player owns the satisfaction check", "Use statements for ordinary answers",
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
