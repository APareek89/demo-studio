"""Reject the observed policy contradiction before speech; no live data/network."""
from __future__ import annotations

import copy
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check):
    from server import schemas, store
    from server.agents import qa, voice

    fact = {"id": "F027", "kind": "policy", "truth": "contractual", "approved": True,
            "claim": "Basic warranty headline", "value": "3 years | 100000 km",
            "conditions": "The relationship between the time and distance limits is not supplied. Full terms are not provided.",
            "source": {"source_id": "s1", "locator": "warranty badge", "quote": "3 years | 100000 km"}}
    und = {"product": {"name": "Fixture"}, "facts": [fact], "competitors": [], "images": [], "shots": []}
    plan = {"segments": [], "ctas": []}
    bad = "The advertised basic warranty is 3 years or 100 000 km, though the materials do not specify the relationship between time and distance or whether whichever comes first applies."
    proposed = schemas.QAOut(answer=bad, fact_ids=["F027"], answered=True, visual_ref="", escalate="", topic="ownership", cta="book-test-drive", clarifying_question="")
    spoken = []

    def speak(_id, text, **kwargs):
        spoken.append(text)
        return "audio/fixture.wav"

    with ExitStack() as stack:
        stack.enter_context(patch.object(store, "read_json", side_effect=lambda _id, name: copy.deepcopy(und if name == "understanding.json" else plan)))
        stack.enter_context(patch.object(store, "load", return_value={"settings": {"competition": "on", "language": "en-IN"}, "approvals": {"script": True}}))
        stack.enter_context(patch.object(store, "write_json", side_effect=AssertionError("No store mutation")))
        stack.enter_context(patch.object(qa, "_record_unknown"))
        stack.enter_context(patch.object(qa, "_clear_runtime_unknown"))
        stack.enter_context(patch.object(qa.runtime, "structured", side_effect=lambda *a, **kw: proposed.model_copy(deep=True)))
        stack.enter_context(patch.object(voice, "render_line", side_effect=speak))
        for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(name, side_effect=AssertionError("Network forbidden")))

        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: actual contradictory or-plus-unknown answer is declined", not result["answered"] and result["answer"] == qa.DONT_GUESS)
        check("policy: invalid meaning has no citations, CTA or proposed visual", result["fact_ids"] == [] and result["cta"] == "" and result["visual"] is None)
        check("policy: only the existing safe decline reaches speech", spoken == [qa.DONT_GUESS])
        check("policy: semantic rejection offers callback without inventing a provider outage", result["offer_callback"] and not result["provider_failed"])

        proposed.cta = ""
        proposed.answer = "The warranty headline lists 3 years and 100000 km. Their relationship is not supplied."
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: advertised limits with an explicit unknown remain usable", result["answered"] and result["answer"] == proposed.answer)

        proposed.answer = "The material does not state whether whichever comes first applies."
        result = qa.answer("fixture", "Which limit applies first?", live=True)
        check("policy: a negated relationship is not an assertion", result["answered"] and result["answer"] == proposed.answer)

        proposed.answer = "The warranty is 3 years or 100000 km, whichever comes first."
        fact["conditions"] = "3 years or 100000 km, whichever comes first."
        fact["source"]["quote"] = fact["conditions"]
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: a source that explicitly states the relationship retains it", result["answered"] and result["answer"] == proposed.answer)

        fact["conditions"] = "See the source badge."
        fact["source"]["quote"] = "3 years | 100000 km. The relationship between the limits is unknown."
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: a source-quote-only explicit unknown also rejects the assertion", not result["answered"] and result["answer"] == qa.DONT_GUESS)

        proposed.answer = "The limit is 100000 km or 3 years."
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: reversed distance/time order cannot bypass the guard", not result["answered"])

        proposed.answer = "The headline is three years or one hundred thousand kilometres."
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: spoken quantities cannot bypass the relation guard", not result["answered"])

        proposed.answer = "Exclusions are not supplied, and the warranty is 3 years or 100000 km."
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: unrelated earlier uncertainty cannot excuse an assertion", not result["answered"])

        proposed.answer = "The material does not state whether the warranty is 3 years or 100000 km."
        result = qa.answer("fixture", "What are the warranty limits?", live=True)
        check("policy: uncertainty attached to the actual limits remains usable", result["answered"])


if __name__ == "__main__":
    results = []
    def check(name, ok):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    run(check)
    print(f"QA policy contracts: {sum(results)}/{len(results)} (fake providers; network blocked)")
    raise SystemExit(0 if all(results) else 1)
