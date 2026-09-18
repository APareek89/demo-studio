"""Free summary-opener regression; synthetic records, fake models, no network."""
from __future__ import annotations

import copy
import json
import sys
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def run(check) -> None:
    from server import config, store
    from server.agents import summary

    # The actual C failure, kept as a proposed model result rather than a live
    # session dependency. No test rewrites the preserved customer evidence.
    bad = "You mentioned that you mainly want help with stop-and-go traffic, and I have those details ready along with the exact Mumbai on-road price and EMI numbers."
    neutral = "I'd like to discuss the questions left open in your demo."
    supplied = summary.SessionSummary(
        context="Considering a family car for city use.",
        cared_about=["Stop-and-go traffic", "Exact local price", "Finance terms"],
        objections=[summary.Objection(text="Needs a complete quote", resolved=False)],
        unanswered=["Exact Mumbai on-road price", "Bank-guaranteed five-year EMI"],
        opening_line=bad,
    )
    record = {
        "profile": {"name": "", "why": "", "focus": []},
        "questions": ["What is the exact on-road price in Mumbai today, including every charge?"],
        "unresolved": ["ownership"],
        "escalations": ["Exact Mumbai on-road price including local charges"],
        "resolved": [], "minutes": 2.4, "leads": [], "slides_visited": [],
        "transcript": [{"role": "agent", "text": "I don't have that answer in the approved information."}],
    }
    calls = []

    def fake(system, content, schema, **kwargs):
        calls.append((system, json.loads(content), kwargs))
        return supplied.model_copy(deep=True)

    with ExitStack() as stack:
        stack.enter_context(patch.object(config, "MOCK_LLM", False))
        stack.enter_context(patch.object(store, "read_json", side_effect=lambda _id, name:
            {"product": {"name": "Fixture car"}} if name == "understanding.json" else {"slides": []}))
        stack.enter_context(patch.object(store, "load", side_effect=AssertionError("Unexpected store load")))
        stack.enter_context(patch.object(store, "write_json", side_effect=AssertionError("Unexpected store write")))
        runtime = stack.enter_context(patch.object(summary.runtime, "structured", side_effect=fake))
        for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(name, side_effect=AssertionError("Network forbidden")))

        before = copy.deepcopy(record)
        out = summary.summarize("summary-fixture", record)
        check("summary: actual C readiness promise becomes a neutral invitation", out["opening_line"] == neutral)
        check("summary: context, interests and objections survive the opener guard", all(
            out[k] == supplied.model_dump()[k] for k in ("context", "cared_about", "objections")))
        check("summary: unanswered questions and input status are preserved",
              out["unanswered"] == supplied.unanswered and record == before)
        system, payload, kwargs = calls[-1]
        check("summary: provider gets explicit open-question limits and the real unresolved record",
              "Do not imply" in system and "already has" in system
              and payload["unresolved"] == ["ownership"]
              and payload["escalations"] == record["escalations"]
              and kwargs["max_tokens"] == 1200)

        supplied.unanswered = []
        for field in ("unresolved", "escalations"):
            isolated = {**record, "unresolved": [], "escalations": []}
            isolated[field] = ["Still needs a local quote"]
            result = summary.summarize("summary-fixture", isolated)
            check(f"summary: recorded {field} alone prevents a readiness promise", result["opening_line"] == neutral)

        clean = {**record, "unresolved": [], "escalations": [], "resolved": ["ownership"]}
        supplied.unanswered = ["Which charges are included?"]
        check("summary: model unanswered alone prevents a readiness promise",
              summary.summarize("summary-fixture", clean)["opening_line"] == neutral)

        supplied.unanswered = []
        supplied.opening_line = "You mentioned wanting to see the rear seat in person."
        check("summary: a resolved session retains its specific supported opener",
              summary.summarize("summary-fixture", clean)["opening_line"] == supplied.opening_line)
        callback = {**clean, "escalations": ['callback requested on 0000000000: "test drive"']}
        check("summary: callback bookkeeping alone does not invent an unanswered question",
              summary.summarize("summary-fixture", callback)["opening_line"] == supplied.opening_line)

        with patch.object(config, "MOCK_LLM", True), patch.object(summary.mock, "fake", return_value=supplied.model_copy(deep=True)):
            count = runtime.call_count
            result = summary.summarize("summary-fixture", record)
            check("summary: mock path applies the guard without a provider call",
                  result["opening_line"] == neutral and result["model"] == "mock" and runtime.call_count == count)


if __name__ == "__main__":
    results = []
    def check(name, ok):
        results.append(bool(ok))
        print(f"{'PASS' if ok else 'FAIL'} {name}")
    run(check)
    print(f"Summary contracts: {sum(results)}/{len(results)} (no network or paid calls)")
    raise SystemExit(0 if all(results) else 1)
