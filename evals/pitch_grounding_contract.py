"""Free real-pitch-path regressions for generated policy and benefit additions."""
from __future__ import annotations

import copy
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    from server import config, schemas, store
    from server.agents import pitch, visuals, voice

    warranty = {"id": "F027", "kind": "policy", "truth": "contractual", "claim": "Advertised basic warranty",
                "value": "3 years | 100 000 km", "approved": True,
                "conditions": "Advertised basic warranty headline; specific terms, exclusions, transferability, or 'whichever occurs first' qualification not detailed in source badge.",
                "source": {"ref": "brochure", "locator": "page 40 / warranty badge", "quote": "3 years | 100 000 km"}}
    mount = {"id": "F004", "kind": "feature", "truth": "stated", "claim": "Standard child seat mounts", "value": "ISOFIX standard",
             "conditions": "Standard across variants; attachment-point count and universal compatibility not stated.",
             "approved": True, "source": {"ref": "brochure", "locator": "page 11 / equipment footnote", "quote": "ISOFIX*"}}
    und = {"product": {"name": "Fixture car"}, "facts": [warranty, mount], "images": [], "shots": []}
    boot = {"id": "F014", "kind": "spec", "truth": "stated", "claim": "Boot space", "value": "382 L petrol/diesel; 321 L CNG",
            "approved": True, "conditions": "Brochure measurement basis: ISO V215. Volume does not establish stroller fit.",
            "source": {"ref": "brochure", "locator": "page 40 / measurement footnote", "quote": "Boot Space (L) 382 321"}}
    und["facts"].append(boot)
    script = {"segments": [
        {"id": "safety", "role": "proof", "title": "Child seat mounting", "topic": "safety",
         "lines": [{"id": "l1", "text": "ISOFIX mounts are standard.", "fact_ids": ["F004"]}]},
        {"id": "ownership", "role": "establish", "title": "Written terms", "topic": "ownership",
         "lines": [{"id": "l2", "text": "The written headline leaves the limits' relationship unstated.", "fact_ids": ["F027"]}]}]}
    # These positive examples are deliberately reviewed proof, not newly
    # generated paraphrases. Their exact wording/citations remain the boundary.
    reviewed = [
        ("The advertised limits are 3 years and 100 000 km; their relationship is not supplied.", ["F027"]),
        ("For your child seat, the brochure lists ISOFIX mounts as standard; bring the seat to check its fit in person.", ["F004"]),
        ("The listed boot is 382 litres for petrol and diesel, and 321 litres for CNG, measured using ISO V215; check your stroller in person.", ["F014"]),
        ("The petrol boot is listed at 382 litres measured using ISO V215.", ["F014"]),
        ("The written warranty lasts 3 years or 100 000 km, whichever occurs first.", ["F027"]),
        ("The documented assessment describes installation as straightforward.", ["F004"]),
        ("The brochure lists ISOFIX mounts as standard.", ["F004"]),
    ]
    script["segments"][0]["deeper"] = [
        {"id": f"reviewed-{i}", "text": text, "fact_ids": ids, "unverified": False}
        for i, (text, ids) in enumerate(reviewed)
    ]
    demo = {"settings": {"language": "en-IN"}, "approvals": {"script": True}}
    plan = {"voice": {}, "ctas": [], "segments": []}
    files = {"understanding.json": und, "script.json": script, "plan.json": plan,
             "deck.json": {"slides": [{"id": "sl-safety", "segment_id": "safety"}, {"id": "sl-ownership", "segment_id": "ownership"}]}}
    profile = {"why": "I drive five to ten kilometres in the city and use a child seat and stroller."}
    proposed = schemas.PitchPlan(customer_state="stated_need", decision_frame="We will look at child-seat mounting and written ownership terms.",
                                 follow_up_question="", primary_outcome="Review your stated needs.", focus_topics=["safety"],
                                 route=[schemas.RouteStep(segment_id="safety"), schemas.RouteStep(segment_id="ownership")],
                                 advance="Bring your child seat for an in-person fit check.")
    spoken = []
    with ExitStack() as stack:
        stack.enter_context(patch.object(config, "MOCK_LLM", True))
        stack.enter_context(patch.object(store, "read_json", side_effect=lambda _id, name: copy.deepcopy(files.get(name))))
        stack.enter_context(patch.object(store, "load", side_effect=lambda _id: copy.deepcopy(demo)))
        stack.enter_context(patch.object(store, "log"))
        writes = stack.enter_context(patch.object(store, "write_json", side_effect=AssertionError("No source or script writes")))
        stack.enter_context(patch.object(voice, "provider_for", return_value="sarvam"))
        stack.enter_context(patch.object(voice, "render_line", side_effect=lambda _id, text, **kw: spoken.append(text) or "fake.wav"))
        stack.enter_context(patch.object(visuals, "for_facts", return_value=None))
        stack.enter_context(patch.object(visuals, "for_text_and_facts", return_value=None))
        blocked = [stack.enter_context(patch(name, side_effect=AssertionError("No provider/network calls"))) for name in
                   ("socket.socket.connect", "socket.create_connection", "server.llm.gemini.client", "server.llm.runware._post", "server.llm.claude._client_opts")]

        def generate(text, ids, *, bridge=False, route_index=0):
            item = proposed.model_copy(deep=True)
            if bridge:
                item.route[route_index].bridge, item.route[route_index].bridge_fact_ids = text, ids
            else:
                item.custom_batches = [schemas.CustomBatch(text=text, fact_ids=ids)]
            spoken.clear()
            with patch.object(pitch.runtime, "structured", return_value=item) as model:
                result = pitch.plan_pitch("pitch-fixture", profile, refine=True)
            return result, model.call_args, list(spoken)

        bad_policy = "For your daily five to ten kilometre city routine, the basic warranty covers 3 years or 100 000 km to keep early ownership predictable."
        result, call, audio = generate(bad_policy, ["F027"])
        check("pitch: observed unsupported warranty relation is dropped before speech", not result["custom_batches"] and bad_policy not in audio)
        check("pitch: rejecting custom proof preserves the reviewed safety/ownership route",
              [x["segment_id"] for x in result["route"]] == ["safety", "ownership"] and result["route"][-1]["slide_id"] == "sl-ownership")
        bad_bridge = "For your child seat, standard mounting points keep installation straightforward."
        result, _, audio = generate(bad_bridge, [], bridge=True)
        check("pitch: observed uncited installation bridge is dropped before speech", not result["route"][0]["bridge"] and result["route"][0].get("bridge_dropped") == bad_bridge and bad_bridge not in audio)
        result, _, audio = generate(bad_bridge, ["F004"], bridge=True)
        check("pitch: an equipment citation alone cannot license an installation benefit", not result["route"][0]["bridge"] and bad_bridge not in audio)
        for text in (
            "The rear mounting points sit under a removable panel.",
            "The cabin surface feels velvety to the touch.",
            "Next: Child seat mounting. The anchors sit beneath a panel.",
        ):
            result, _, audio = generate(text, [], bridge=True)
            check(f"pitch: uncited free product prose never reaches bridge speech: {text}",
                  not result["route"][0]["bridge"] and result["route"][0].get("bridge_dropped") == text and text not in audio)
        wrong_route = "Next: Written terms."
        result, _, audio = generate(wrong_route, [], bridge=True)
        check("pitch: a neutral cue cannot be attached to the wrong route segment",
              not result["route"][0]["bridge"] and wrong_route not in audio)
        child_batch = "To secure your child seat properly across your city drives, ISOFIX mounts come standard across all variants."
        result, _, audio = generate(child_batch, ["F004"])
        check("pitch: equipment-only proof does not license properly secured child-seat outcome", not result["custom_batches"] and child_batch not in audio)

        for text in (
            "For your child seat, ISOFIX child seat mounts come standard across all variants, providing built-in mounting points in the rear cabin.",
            "ISOFIX mounts are standard and made from titanium.",
            "ISOFIX mounts are standard. They are hidden beneath a removable panel.",
        ):
            for bridge in (False, True):
                result, _, audio = generate(text, ["F004"], bridge=bridge)
                check(f"pitch: unreviewed property detail never reaches {'bridge' if bridge else 'batch'} speech: {text}",
                      (not result["route"][0]["bridge"] if bridge else not result["custom_batches"]) and text not in audio)

        main_proof = "ISOFIX mounts are standard."
        for bridge in (False, True):
            result, _, audio = generate(main_proof, ["F004"], bridge=bridge)
            main_text = [line["text"] for segment in script["segments"]
                         if segment["id"] in {step["segment_id"] for step in result["route"]}
                         for line in segment["lines"]]
            check(f"pitch: main-route proof is not repeated in an optional {'bridge' if bridge else 'batch'}",
                  (not result["route"][0]["bridge"] if bridge else not result["custom_batches"])
                  and (audio + main_text).count(main_proof) == 1)
        trusted = "The brochure lists ISOFIX mounts as standard."
        result, _, audio = generate(trusted, ["F004"])
        check("pitch: exact reviewed proof remains available for the selected buyer need",
              bool(result["custom_batches"]) and result["custom_batches"][0]["text"] == trusted and trusted in audio)
        result, _, audio = generate(trusted, ["F027"])
        check("pitch: reviewed text cannot be relabelled with different fact ids", not result["custom_batches"] and trusted not in audio)
        result, _, audio = generate(trusted, ["F004", "MISSING"])
        check("pitch: invalid model citations are not silently stripped into a trusted proof", not result["custom_batches"] and trusted not in audio)
        script["segments"][0]["deeper"][-1]["unverified"] = True
        result, _, audio = generate(trusted, ["F004"])
        check("pitch: an unverified script line cannot authorize new speech", not result["custom_batches"] and trusted not in audio)
        script["segments"][0]["deeper"][-1]["unverified"] = False
        original_line = copy.deepcopy(script["segments"][0]["deeper"][-1])
        script["segments"][0]["deeper"][-1]["fact_ids"] = ["MISSING"]
        result, _, audio = generate(trusted, ["F004"])
        check("pitch: a script line with unsupported citations supplies no reviewed proof", not result["custom_batches"] and trusted not in audio)
        bad_reviewed = "ISOFIX mounts make installation straightforward."
        script["segments"][0]["deeper"][-1] = {**original_line, "text": bad_reviewed}
        result, _, audio = generate(bad_reviewed, ["F004"])
        check("pitch: existing source-condition safeguards still apply to reviewed proof", not result["custom_batches"] and bad_reviewed not in audio)
        script["segments"][0]["deeper"][-1] = original_line
        demo["approvals"]["script"] = False
        result, _, audio = generate(trusted, ["F004"])
        check("pitch: unapproved script supplies no custom proof while the route remains",
              not result["custom_batches"] and len(result["route"]) == 2 and trusted not in audio)
        demo["approvals"]["script"] = True
        no_proof = "The source lists ISOFIX as standard equipment."
        result, _, audio = generate(no_proof, ["F004"])
        check("pitch: no exact reviewed proof omits only the optional batch",
              not result["custom_batches"] and len(result["route"]) == 2 and no_proof not in audio)

        for wording in ("The warranty lasts 3 years or 100 000 km.", "The warranty lasts 3 years and 100 000 km, whichever occurs first."):
            for bridge in (False, True):
                result, _, audio = generate(wording, ["F027"], bridge=bridge)
                check(f"pitch: unknown relation rejects {'bridge' if bridge else 'batch'} {wording}",
                      (not result["route"][0]["bridge"] if bridge else not result["custom_batches"]) and wording not in audio)

        safe_policy = "The advertised limits are 3 years and 100 000 km; their relationship is not supplied."
        result, _, audio = generate(safe_policy, ["F027"])
        check("pitch: unknown relationship can be stated honestly without inventing one", result["custom_batches"][0]["text"] == safe_policy and safe_policy in audio)
        safe_mount = "For your child seat, the brochure lists ISOFIX mounts as standard; bring the seat to check its fit in person."
        result, _, audio = generate(safe_mount, ["F004"])
        check("pitch: plain equipment and a proposed personal fit check survive", result["custom_batches"][0]["text"] == safe_mount and safe_mount in audio)
        neutral = "Next: Child seat mounting."
        result, neutral_call, audio = generate(neutral, [], bridge=True)
        check("pitch: the exact route-owned neutral cue needs no fabricated product claim", result["route"][0]["bridge"] == neutral and neutral in audio)
        check("pitch: prompt supplies exact neutral cues by route and forbids other uncited prose",
              '"safety": "' + neutral + '"' in neutral_call.args[0]
              and '"ownership": "' + wrong_route + '"' in neutral_call.args[0]
              and "NEUTRAL ROUTE CUES" in neutral_call.args[0]
              and "no other uncited prose" in neutral_call.args[0])
        demo["approvals"]["script"] = False
        result, _, audio = generate(neutral, [], bridge=True)
        check("pitch: an unreviewed title cannot authorize a neutral spoken cue",
              not result["route"][0]["bridge"] and neutral not in audio)
        demo["approvals"]["script"] = True

        bare_volume = "For your stroller, the listed boot is 382 litres for petrol and diesel, and 321 litres for CNG."
        result, _, audio = generate(bare_volume, ["F014"])
        check("pitch: a stated volume cannot lose its explicit measurement basis", not result["custom_batches"] and bare_volume not in audio)
        qualified_volume = "The listed boot is 382 litres for petrol and diesel, and 321 litres for CNG, measured using ISO V215; check your stroller in person."
        result, _, audio = generate(qualified_volume, ["F014"])
        check("pitch: complete volume scope and measurement basis survive", result["custom_batches"][0]["text"] == qualified_volume and qualified_volume in audio)
        result, _, audio = generate(wrong_route, [], bridge=True, route_index=1)
        check("pitch: the next reviewed route title supplies its own neutral cue",
              result["route"][1]["bridge"] == wrong_route and wrong_route in audio)
        quote_basis = copy.deepcopy(boot)
        quote_basis["value"], quote_basis["conditions"] = "382 L", "Petrol only."
        quote_basis["source"]["quote"] = "Boot volume 382 L, ISO V215."
        files["understanding.json"]["facts"][2] = quote_basis
        bare_quote = "The petrol boot is listed at 382 litres."
        result, _, audio = generate(bare_quote, ["F014"])
        check("pitch: a measurement basis stated only in the quote cannot be omitted", not result["custom_batches"] and bare_quote not in audio)
        full_quote = "The petrol boot is listed at 382 litres measured using ISO V215."
        result, _, audio = generate(full_quote, ["F014"])
        check("pitch: a quoted measurement code is approved numeric evidence", bool(result["custom_batches"]) and result["custom_batches"][0]["text"] == full_quote and full_quote in audio)
        files["understanding.json"]["facts"][2] = boot

        documented = copy.deepcopy(warranty)
        documented["value"] = "3 years or 100 000 km, whichever occurs first"
        documented["conditions"] = "Whichever occurs first applies; exclusions are not supplied."
        documented["source"]["quote"] = documented["value"]
        files["understanding.json"]["facts"][0] = documented
        known = "The written warranty lasts 3 years or 100 000 km, whichever occurs first."
        result, _, audio = generate(known, ["F027"])
        check("pitch: explicitly documented relation survives despite unrelated missing exclusions", result["custom_batches"][0]["text"] == known and known in audio)

        documented_mount = copy.deepcopy(mount)
        documented_mount["source"]["quote"] = "The assessed installation was straightforward."
        files["understanding.json"]["facts"][1] = documented_mount
        result, _, audio = generate("The documented assessment describes installation as straightforward.", ["F004"])
        check("pitch: an explicitly stated installation assessment is not blanket-blocked", bool(result["custom_batches"]) and len(audio) >= 1)

        envelope = call.args[0]
        check("pitch: full evidence and scope-before-benefit rules reach the real prompt",
              warranty["source"]["quote"] in envelope and warranty["source"]["locator"] in envelope
              and warranty["conditions"] in envelope and "reasonable inference" not in envelope.lower()
              and "all material conditions" in envelope and "installation" in envelope
              and "relationship" in envelope and "not evidence" in envelope)
        check("pitch: the prompt exposes reviewed proof and limits factual wording to it",
              "REVIEWED SPOKEN PROOF" in envelope and trusted in envelope
              and "exact text and the complete fact_ids" in envelope)
        selection = proposed.model_copy(deep=True)
        selection.custom_batches = [schemas.CustomBatch(text=safe_mount, fact_ids=["F004"]),
                                    schemas.CustomBatch(text=qualified_volume, fact_ids=["F014"])]
        spoken.clear()
        before_profile = copy.deepcopy(profile)
        with patch.object(pitch.runtime, "structured", return_value=selection):
            selected = pitch.plan_pitch("pitch-fixture", profile)
        check("pitch: reviewed factual reuse keeps selected need-led proof order and customer context",
              [item["text"] for item in selected["custom_batches"]] == [safe_mount, qualified_volume]
              and [item["fact_ids"] for item in selected["custom_batches"]] == [["F004"], ["F014"]]
              and selected["decision_frame"] == selection.decision_frame and profile == before_profile)
        hinted = {"focus": ["safety is the main priority"]}
        with patch.object(pitch.runtime, "structured", return_value=selection.model_copy(deep=True)) as model:
            hint_only = pitch.plan_pitch("pitch-fixture", hinted)
        raw_customer = model.call_args.args[0].split("CUSTOMER SAID:", 1)[1].split("COMPUTED ROUTING HINTS", 1)[0]
        check("pitch: computed focus alone cannot create stated need or attributed preference",
              hint_only["customer_state"] == "unknown" and not hint_only["custom_batches"]
              and "safety is the main priority" not in raw_customer
              and "never evidence" in model.call_args.args[0])
        check("pitch: tests made no provider/network calls or source/script writes", not writes.called and not any(x.called for x in blocked))


if __name__ == "__main__":
    rows = []
    def check(name, passed):
        rows.append(bool(passed))
        print(f"{'PASS' if passed else 'FAIL'} {name}")
    run(check)
    print(f"Pitch grounding contracts: {sum(rows)}/{len(rows)}")
    raise SystemExit(0 if all(rows) else 1)
