"""Free provider contracts, called from qa_deck after its isolated demo is built.

Every non-mock provider call uses a fake client/transport and synthetic keys.
Socket guards make an accidental request a failing eval, never a paid probe.
"""
from __future__ import annotations

import copy
import json
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

import httpx


def run(check, demo_id: str) -> None:
    from server import config, schemas, usage
    from server.agents import author, deck, qa
    from server.llm import claude, gemini, runware, runtime

    answer = schemas.QAOut(answer="The approved material can help.", fact_ids=[], answered=True)
    secret = "contract-runware-key-not-real"
    history = [{"role": "user", "content": "Earlier question"},
               {"role": "assistant", "content": [{"type": "text", "text": "Earlier reply"}]}]
    saved_history = copy.deepcopy(history)

    def response(task, text=None, *, changes=None, status=200, body_changes=None):
        row = {"taskType": "textInference", "taskUUID": task["taskUUID"], "model": task["model"],
               "text": answer.model_dump_json() if text is None else text, "finishReason": "stop",
               "usage": {"promptTokens": 100, "completionTokens": 20}, "cost": 0.012}
        row.update(changes or {})
        body = {"data": [row]}
        body.update(body_changes or {})
        return httpx.Response(status, json=body, request=httpx.Request("POST", runware.ENDPOINT))

    def failure(call, expected=RuntimeError):
        try:
            call()
        except expected as error:
            return error
        return None

    with ExitStack() as stack:
        stack.enter_context(patch.multiple(config, MOCK_LLM=False, ANTHROPIC_API_KEY="contract-claude-key-not-real",
                                          GEMINI_API_KEY="contract-gemini-key-not-real", RUNWARE_API_KEY=secret,
                                          RUNTIME_PROVIDERS=["gemini", "claude", "runware"],
                                          CLAUDE_RUNTIME_MODEL="claude-runtime-contract",
                                          GEMINI_RUNTIME_MODEL="gemini-runtime-contract",
                                          RUNWARE_TEXT_MODEL="deepseek:v4@flash"))
        network = [stack.enter_context(patch(name, side_effect=AssertionError("Provider eval attempted a network connection")))
                   for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex")]
        traced = stack.enter_context(patch.object(usage, "trace"))
        recorded = stack.enter_context(patch.object(usage, "record"))

        # Exercise the real dispatcher and the real Claude/Runware adapters.
        calls, sent, claude_requests, gemini_requests = [], [], [], []
        succeed = {"provider": "runware"}

        def fake_gemini(*args, **kwargs):
            calls.append("gemini")
            gemini_requests.append((args, kwargs))
            if succeed["provider"] == "gemini":
                return answer
            raise RuntimeError("503 Gemini unavailable")

        def fake_claude(**kwargs):
            calls.append("claude")
            claude_requests.append(kwargs)
            if succeed["provider"] == "claude":
                return SimpleNamespace(parsed_output=answer, stop_reason="end_turn", content=[], usage=None)
            raise RuntimeError("Claude credit balance is too low")

        def fake_runware(task, timeout):
            calls.append("runware")
            sent.append(copy.deepcopy(task))
            if succeed["provider"] == "none":
                raise httpx.ConnectError("synthetic unavailable")
            return response(task)

        client = SimpleNamespace(messages=SimpleNamespace(parse=fake_claude))
        with patch.object(gemini, "text_structured", side_effect=fake_gemini), \
                patch.object(claude, "_client_opts", return_value=client), \
                patch.object(runware, "_post", side_effect=fake_runware), \
                patch.object(claude, "structured", wraps=claude.structured) as claude_dispatch:
            out = runtime.structured("System", "Current question", schemas.QAOut, history=history)
            check("providers: runtime really traverses Gemini → Claude → Runware once", out == answer and calls == ["gemini", "claude", "runware"])
            check("providers: runtime passes role models and disables Claude's nested fallback",
                  claude_dispatch.call_args.kwargs.get("fallback") is False
                  and claude_requests[-1]["model"] == "claude-runtime-contract"
                  and gemini_requests[-1][1]["model"] == "gemini-runtime-contract"
                  and sent[-1]["model"] == "deepseek:v4@flash")
            check("providers: Runware preserves history roles and leaves caller history unchanged",
                  sent[-1]["messages"] == [{"role": "user", "content": "Earlier question"},
                                            {"role": "assistant", "content": "Earlier reply"},
                                            {"role": "user", "content": "Current question"}]
                  and history == saved_history)
            for provider, expected in (("gemini", ["gemini"]), ("claude", ["gemini", "claude"])):
                calls.clear()
                succeed["provider"] = provider
                out = runtime.structured("System", "Question", schemas.QAOut)
                check(f"providers: {provider} runtime success stops later providers", out == answer and calls == expected)
            calls.clear()
            succeed["provider"] = "runware"
            with patch.object(config, "GEMINI_API_KEY", ""):
                out = claude.structured("System", "Build question", schemas.QAOut)
            check("providers: build reaches Runware even without a Gemini key", out == answer and calls == ["claude", "gemini", "runware"])
            calls.clear()
            succeed["provider"] = "none"
            results = [qa.answer(demo_id, "Contract test unsupported price", voice_it=False, live=True) for _ in range(2)]
            check("providers: all down declines with callback on two independent traversals",
                  calls == ["gemini", "claude", "runware"] * 2
                  and all(not r["answered"] and r["offer_callback"] and not r["fact_ids"] and "won't guess" in r["answer"] for r in results))

        # A provider grammar rejection must not silently switch the selected tier/model.
        grammar_error = claude.anthropic.BadRequestError(
            "Structured-output grammar is too large",
            response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages")),
            body={"error": {"type": "invalid_request_error", "message": "grammar is too large"}},
        )

        def reject_grammar(**kwargs):
            raise grammar_error

        with patch.object(claude, "_client_opts", return_value=SimpleNamespace(messages=SimpleNamespace(parse=reject_grammar))), \
                patch.object(claude, "_soft_structured", return_value=answer) as soft:
            out = claude.structured("System", "Question", schemas.QAOut, model="claude-contract-explicit",
                                    timeout=9.0, effort="low", max_retries=1)
            check("providers: Claude grammar retry preserves model, timeout, effort and retries",
                  out == answer and soft.call_count == 1
                  and soft.call_args.kwargs == {"model": "claude-contract-explicit", "timeout": 9.0,
                                               "effort": "low", "max_retries": 1})

        # MOCK_LLM must short-circuit provider construction, not merely return a mock label.
        with patch.object(config, "MOCK_LLM", True), \
                patch.object(claude, "_client_opts", side_effect=AssertionError("Claude opened in mock mode")) as cl, \
                patch.object(gemini, "client", side_effect=AssertionError("Gemini opened in mock mode")) as ge, \
                patch.object(runware, "_post", side_effect=AssertionError("Runware opened in mock mode")) as rw:
            mocked = [runtime.structured("System", "Question", schemas.QAOut),
                      claude.structured("System", "Question", schemas.QAOut),
                      runware.structured("System", "Question", schemas.QAOut)]
            check("providers: mock runtime/build/direct Runware never open providers", all(isinstance(x, schemas.QAOut) for x in mocked) and not (cl.called or ge.called or rw.called))

        media = {"type": "document", "source": {"type": "base64", "data": "DO-NOT-SEND-MEDIA"}}
        with patch.object(runware, "_post") as post:
            bad_content = failure(lambda: runware.structured("System", [media], schemas.QAOut))
            bad_history = failure(lambda: runware.structured("System", "Question", schemas.QAOut, history=[{"role": "user", "content": [media]}]))
            bad_build = failure(lambda: claude.text_fallback("System", [{"role": "user", "content": [media]}], schemas.QAOut), ValueError)
            check("providers: current/history media and build fallback reject before transport", all((bad_content, bad_history, bad_build)) and not post.called)

        # Invalid schema output is billable and repair is bounded to one extra request.
        recorded.reset_mock()
        traced.reset_mock()
        repaired = []

        def repair(task, timeout):
            repaired.append(copy.deepcopy(task))
            return response(task, "{broken JSON" if len(repaired) == 1 else None)

        with patch.object(runware, "_post", side_effect=repair):
            out = runware.structured("System", "Question", schemas.QAOut)
        check("providers: one JSON repair returns a validated application schema", out == answer and len(repaired) == 2 and len(repaired[1]["messages"]) == 3)
        check("providers: invalid and repaired billable replies both record cost and trace",
              recorded.call_count == 2 and traced.call_count == 2
              and all(c.kwargs.get("usd") == 0.012 and c.kwargs.get("input_tokens") == 100 for c in recorded.call_args_list)
              and bool(traced.call_args_list[0].kwargs.get("error")) and not traced.call_args_list[1].kwargs.get("error"))
        with patch.object(runware, "_post", side_effect=lambda task, timeout: response(task, "{}")) as post:
            error = failure(lambda: runware.structured("System", "Question", schemas.QAOut))
            check("providers: two schema-invalid replies stop after one repair", bool(error) and post.call_count == 2)

        for name, changes, body_changes, status in (
            ("wrong task UUID", {"taskUUID": "unrelated"}, None, 200),
            ("truncated answer", {"finishReason": "length"}, None, 200),
            ("refused answer", {"refusal": "declined"}, None, 200),
            ("HTTP error", None, None, 503),
            ("task error envelope", None, {"errors": [{"message": "rejected"}]}, 200),
        ):
            with patch.object(runware, "_post", side_effect=lambda task, timeout, ch=changes, bc=body_changes, st=status: response(task, changes=ch, body_changes=bc, status=st)) as post:
                error = failure(lambda: runware.structured("System", "Question", schemas.QAOut))
                check(f"providers: {name} fails closed without a JSON repair", bool(error) and post.call_count == 1)

        traced.reset_mock()
        with patch.object(runware, "_post", side_effect=lambda task, timeout: response(task, secret, status=401, body_changes={"errors": [{"message": secret}]})):
            error = failure(lambda: runware.structured("System " + secret, "Question " + secret, schemas.QAOut))
        check("providers: credentials never enter Runware traces or raised diagnostics",
              bool(error) and secret not in str(error) and secret not in str(traced.call_args_list))

        # A schema-valid provider result still has to pass the existing grounding consumers.
        uncited = schemas.QAOut(answer="It travels 999 km.", fact_ids=[], answered=True)
        with patch.object(runware, "_post", side_effect=lambda task, timeout: response(task, uncited.model_dump_json())):
            parsed = runware.structured("System", "Question", schemas.QAOut)
        valid, bad = author.ungrounded(parsed.answer, parsed.fact_ids, {"F001"})
        cleaned = deck.clean_callouts([{"text": parsed.answer, "fact_ids": parsed.fact_ids}], {"lines": [{"id": "line"}]}, {"F001"}, None)
        check("providers: valid Runware JSON cannot smuggle an uncited figure into callouts", bad and not valid and cleaned == [])
        with patch.object(config, "RUNTIME_PROVIDERS", ["runware"]), \
                patch.object(runware, "_post", side_effect=lambda task, timeout: response(task, uncited.model_dump_json())):
            out = qa.answer(demo_id, "Contract test unsupported range", voice_it=False, live=True)
        check("providers: runtime drops Runware's uncited figure and offers callback", not out["answered"] and not out["fact_ids"] and out["offer_callback"] and "999" not in out["answer"])
        check("providers: no fake-provider contract opened a network socket", not any(guard.called for guard in network))
