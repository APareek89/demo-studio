"""Free provider contracts, called from qa_deck after its isolated demo is built.

Every non-mock provider call uses a fake client/transport and synthetic keys.
Socket guards make an accidental request a failing eval, never a paid probe.
"""
from __future__ import annotations

import copy
import json
import math
import os
import runpy
import tempfile
from contextlib import ExitStack
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import httpx


def run(check, demo_id: str) -> None:
    from server import app as app_module
    from server import config, schemas, store, usage
    from server.agents import author, deck, qa, understand
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

        # Resolve config in independent namespaces: never reload the live config module or read .env.
        with tempfile.TemporaryDirectory(prefix="provider-contract-") as temp:
            isolated_env = {"MOCK_LLM": "1", "CLOUD_SYNC": "0", "DEMO_STUDIO_DATA": temp + "/demos",
                            "DEMO_STUDIO_GRAPH_DB": temp + "/graph.sqlite"}

            def isolated(path, values=None):
                with patch.dict(os.environ, {**isolated_env, **(values or {})}, clear=True), \
                        patch("dotenv.load_dotenv", return_value=False):
                    return runpy.run_path(path, run_name="server._provider_contract_isolated")

            eval_config = isolated(config.__file__)
            customer_config = isolated(config.__file__, {"MODEL_TIER": "customer"})
            for tier, resolved, cm, gm, rm in (
                ("eval", eval_config, "claude-haiku-4-5-20251001", "gemini-3.5-flash-lite", "deepseek:v4@flash"),
                ("customer", customer_config, "claude-opus-5", "gemini-3.8-flash", "openai:gpt@5.5"),
            ):
                check(f"providers: {tier} tier resolves every approved text-model role",
                      resolved["MODEL_TIER"] == tier
                      and all(resolved[key] == cm for key in ("CLAUDE_MODEL", "CLAUDE_PLAN_MODEL", "CLAUDE_LITE_MODEL", "CLAUDE_RUNTIME_MODEL"))
                      and resolved["GEMINI_TEXT_MODEL"] == resolved["GEMINI_RUNTIME_MODEL"] == gm
                      and resolved["RUNWARE_TEXT_MODEL"] == rm
                      and resolved["RUNTIME_PROVIDERS"] == ["gemini", "claude", "runware"])
            media_models = {"GEMINI_MODEL": "gemini-3.6-flash", "GEMINI_IMAGE_MODEL": "gemini-3.1-flash-lite-image",
                            "GEMINI_TTS_MODEL": "gemini-3.1-flash-tts-preview"}
            check("providers: changing text tier leaves vision, image and speech defaults unchanged",
                  all(resolved[key] == value for resolved in (eval_config, customer_config) for key, value in media_models.items()))
            overrides = {key: "override-" + key.lower() for key in ("CLAUDE_MODEL", "CLAUDE_PLAN_MODEL", "CLAUDE_LITE_MODEL",
                         "CLAUDE_RUNTIME_MODEL", "GEMINI_TEXT_MODEL", "GEMINI_RUNTIME_MODEL", "GEMINI_MODEL")}
            overridden = isolated(config.__file__, {"MODEL_TIER": "customer", **overrides})
            check("providers: explicit role and media overrides survive customer tier", all(overridden[key] == value for key, value in overrides.items()))
            runware_overrides = {"RUNWARE_TEXT_MODEL": "eval-override", "RUNWARE_TEXT_MODEL_PREMIUM": "customer-override"}
            er = isolated(config.__file__, runware_overrides)
            cr = isolated(config.__file__, {"MODEL_TIER": "customer", **runware_overrides})
            check("providers: Runware eval and premium overrides stay in their own tier",
                  er["RUNWARE_TEXT_MODEL"] == "eval-override" and cr["RUNWARE_TEXT_MODEL"] == "customer-override")
            blanks = isolated(config.__file__, {"CLAUDE_MODEL": " ", "GEMINI_TEXT_MODEL": "", "RUNWARE_TEXT_MODEL": " "})
            check("providers: blank overrides use eval defaults and invalid tier is refused",
                  all(blanks[key] == eval_config[key] for key in ("CLAUDE_MODEL", "GEMINI_TEXT_MODEL", "RUNWARE_TEXT_MODEL"))
                  and bool(failure(lambda: isolated(config.__file__, {"MODEL_TIER": "custmer"}), ValueError)))

            pricing = isolated(usage.__file__)
            cost = pricing["_cost_usd"]
            row = {"kind": "runware-structured", "in": 1000000, "out": 1000000, "chars": 0, "sec": 0,
                   "t": datetime(2026, 9, 18, tzinfo=timezone.utc).timestamp()}
            expected_prices = {"claude-haiku-4-5-20251001": (1.0, 5.0), "claude-opus-5": (5.0, 25.0),
                               "gemini-3.5-flash-lite": (0.30, 2.50), "gemini-3.8-flash": (0.75, 3.75),
                               "deepseek:v4@flash": (0.076, 0.153), "openai:gpt@5.5": (5.0, 30.0),
                               "deepseek-v4-flash": (0.076, 0.153), "openai-gpt-5-5": (5.0, 30.0)}
            check("providers: approved model IDs and Runware aliases use exact token prices",
                  all(math.isclose(cost({**row, "model": model, "out": 0}), expected[0])
                      and math.isclose(cost({**row, "model": model, "in": 0}), expected[1])
                      for model, expected in expected_prices.items()))
            check("providers: native Runware cost overrides estimates including exact zero",
                  cost({**row, "model": "openai:gpt@5.5", "usd": 0}) == 0
                  and cost({**row, "model": "deepseek:v4@flash", "usd": 0.123}) == 0.123)
            cutoff = datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()
            check("providers: Gemini customer promotional price ends at the UTC boundary",
                  cost({**row, "model": "gemini-3.8-flash", "t": cutoff - 1}) == 4.5
                  and cost({**row, "model": "gemini-3.8-flash", "t": cutoff}) == 9.0)

        # Real Gemini text adapter must account for thought tokens as billed output.
        recorded.reset_mock()
        traced.reset_mock()
        gemini_reply = SimpleNamespace(text=answer.model_dump_json(), usage_metadata=SimpleNamespace(
            prompt_token_count=100, candidates_token_count=20, thoughts_token_count=30))
        types = SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs, HttpOptions=lambda **kwargs: kwargs)
        with patch.object(gemini, "_types", return_value=types), \
                patch.object(gemini, "_retry", side_effect=lambda fn, **kwargs: fn()), \
                patch.object(gemini, "client", return_value=SimpleNamespace(models=SimpleNamespace(generate_content=lambda **kwargs: gemini_reply))):
            out = gemini.text_structured("System", "Question", schemas.QAOut)
        check("providers: Gemini text billing includes hidden thought tokens",
              out == answer and recorded.call_args.kwargs.get("output_tokens") == 50
              and traced.call_args.kwargs.get("output_tokens") == 50
              and recorded.call_args.args[1] == config.GEMINI_TEXT_MODEL)

        # Exercise live QA through the dispatcher, adapter and installed SDK config.
        # The response stays short; its envelope and hidden thoughts need their own room.
        budget_answer = schemas.QAOut(answer="The documented capacity is 382 litres.",
                                     fact_ids=["F-contract"], answered=True)
        budget_registry = {"facts": [{"id": "F-contract", "claim": "Capacity", "value": "382 litres",
                                      "approved": True, "source": {"ref": "src-contract"}}]}
        budget_reply = SimpleNamespace(text=budget_answer.model_dump_json(), usage_metadata=SimpleNamespace(
            prompt_token_count=20008, candidates_token_count=180, thoughts_token_count=1600))
        budget_requests = []

        def budget_generate(**kwargs):
            budget_requests.append(kwargs)
            return budget_reply

        recorded.reset_mock()
        traced.reset_mock()
        with patch.object(qa, "_system", return_value=("Approved facts", budget_registry, {})), \
                patch.object(store, "load", return_value={"settings": {}}), \
                patch.object(store, "read_json", return_value={}), \
                patch.object(store, "write_json", side_effect=AssertionError("Budget contract wrote data")), \
                patch.object(gemini, "_hard_quota_until", 0), \
                patch.object(gemini, "client", return_value=SimpleNamespace(models=SimpleNamespace(generate_content=budget_generate))), \
                patch.object(claude, "structured", return_value=budget_answer) as build_call, \
                patch.object(runware, "structured", side_effect=AssertionError("Successful QA fell through")) as later_call:
            live_answer = qa.answer(demo_id, "What is the documented capacity?", voice_it=False, live=True)
            request = budget_requests[0]
            sdk_config = request["config"]
            check("providers: live QA reserves 3000 output tokens in the real Gemini SDK envelope",
                  sdk_config.max_output_tokens == 3000 and sdk_config.response_schema is schemas.QAOut
                  and sdk_config.response_mime_type == "application/json" and sdk_config.thinking_config is None)
            check("providers: complete live QA keeps its approved citation and stops after Gemini",
                  live_answer["answered"] and live_answer["answer"] == budget_answer.answer
                  and live_answer["fact_ids"] == ["F-contract"] and not live_answer["provider_failed"]
                  and len(budget_requests) == 1 and not build_call.called and not later_call.called
                  and request["model"] == config.GEMINI_RUNTIME_MODEL
                  and sdk_config.http_options.timeout == int(config.RUNTIME_TIMEOUT * 1000))
            check("providers: enlarged live envelope still bills candidate and thought tokens",
                  recorded.call_count == 1 and recorded.call_args.args == ("runtime", config.GEMINI_RUNTIME_MODEL)
                  and recorded.call_args.kwargs == {"input_tokens": 20008, "output_tokens": 1780}
                  and traced.call_args.kwargs["output_tokens"] == 1780)
            built_answer = qa.answer(demo_id, "Build-time capacity?", voice_it=False, live=False)
            check("providers: build-time QA keeps its existing 1500-token budget",
                  built_answer["answered"] and build_call.call_count == 1
                  and build_call.call_args.kwargs["max_tokens"] == 1500 and len(budget_requests) == 1)
            runtime.structured("System", "Non-QA runtime caller", schemas.QAOut)
            check("providers: unrelated runtime callers retain the 1500-token default",
                  len(budget_requests) == 2 and budget_requests[1]["config"].max_output_tokens == 1500)

        # PDFs reach the secondary text chain only after source-labelled extraction.
        source = {"id": "src_contract", "kind": "pdf", "role": "product", "name": "official-brochure.pdf", "path": "sources/contract.pdf"}
        document_demo = {"name": "Contract vehicle", "product": {}, "sources": [source]}
        facts = schemas.FactsOut(
            product=schemas.Product(name="Contract vehicle", category="car", summary="A sourced vehicle.", audience="Buyers"),
            facts=[schemas.FactOut(kind="policy", claim="Warranty", value="3 years", confidence=1,
                                  source=schemas.FactSource(ref="src_contract", locator="page 1", quote="Warranty: 3 years"))],
            unknowns=[], brand=schemas.Brand(tone="Direct", voice_style="Warm", dos=[], donts=[], persona_hint="Guide"))
        document_calls, document_tasks = [], []

        def no_claude(**kwargs):
            document_calls.append("claude")
            raise RuntimeError("Claude credit balance is too low")

        def no_gemini(*args, **kwargs):
            document_calls.append("gemini")
            raise RuntimeError("503 Gemini unavailable")

        def document_response(task, timeout):
            document_calls.append("runware")
            document_tasks.append(copy.deepcopy(task))
            return response(task, facts.model_dump_json())

        with patch.object(store, "load", return_value=document_demo), patch.object(store, "read_json", return_value=None), \
                patch.object(store, "write_json"), patch.object(store, "log"), patch.object(store, "update"), \
                patch.object(understand.media, "enhance_images"), patch.object(claude, "pdf_block", return_value=media), \
                patch.object(understand.sources, "source_text", return_value={"name": source["name"], "text": "Warranty: 3 years"}), \
                patch.object(claude, "_client_opts", return_value=SimpleNamespace(messages=SimpleNamespace(parse=no_claude))), \
                patch.object(gemini, "text_structured", side_effect=no_gemini), \
                patch.object(runware, "_post", side_effect=document_response):
            understanding = understand.run(demo_id, lambda message: None)
            sent_text = json.dumps(document_tasks[-1]["messages"])
            check("providers: unavailable PDF reader falls back once with source-labelled extracted text",
                  document_calls == ["claude", "gemini", "runware"] and understanding["facts"][0]["source"]["ref"] == "src_contract"
                  and all(text in sent_text for text in ("SOURCE src_contract", source["name"], "Warranty: 3 years"))
                  and all(text not in sent_text for text in ("DO-NOT-SEND-MEDIA", "base64", "[pdf document]")))
            document_demo["sources"] = [{**source, "kind": "text", "name": "facts.txt"}]
            document_calls.clear()

            def no_runware(task, timeout):
                document_calls.append("runware")
                raise httpx.ConnectError("synthetic unavailable")

            with patch.object(runware, "_post", side_effect=no_runware):
                error = failure(lambda: understand.run(demo_id, lambda message: None))
            check("providers: exhausted source-text chain is not restarted by document recovery",
                  bool(error) and document_calls == ["claude", "gemini", "runware"])

        # Exercise route guards directly; the graph is stubbed so no background work starts.
        with patch.multiple(config, ANTHROPIC_API_KEY="", GEMINI_API_KEY=""), \
                patch.object(app_module, "_demo_or_404", return_value={"sources": [{"kind": "text"}]}) as get_demo, \
                patch.object(app_module.graph, "start_read") as start_read:
            result = app_module.read_sources(demo_id)
            check("providers: Runware key alone permits a text-only source read", result == {"ok": True} and start_read.call_count == 1)
            get_demo.return_value = {"sources": [{"kind": "image"}]}
            error = failure(lambda: app_module.read_sources(demo_id), app_module.HTTPException)
            check("providers: image sources still require Gemini before a read starts",
                  error is not None and error.status_code == 400 and "GEMINI_API_KEY" in error.detail and start_read.call_count == 1)
            get_demo.return_value = {"sources": [{"kind": "text"}]}
            with patch.object(config, "RUNWARE_API_KEY", ""):
                error = failure(lambda: app_module.read_sources(demo_id), app_module.HTTPException)
            check("providers: no model key refuses a real source read before the graph starts",
                  error is not None and error.status_code == 400 and start_read.call_count == 1)

        clock = {"now": 100.0}
        budgets = []

        def timed_repair(task, timeout):
            budgets.append(timeout)
            clock["now"] += 6 if len(budgets) == 1 else 1
            return response(task, "{}" if len(budgets) == 1 else None)

        with patch.object(runware.time, "monotonic", side_effect=lambda: clock["now"]), \
                patch.object(runware, "_post", side_effect=timed_repair):
            out = runware.structured("System", "Question", schemas.QAOut, timeout=10)
        check("providers: JSON repair shares the original timeout budget", out == answer and budgets == [10, 4])

        def duplicated(task, timeout):
            body = response(task).json()
            body["data"].append(copy.deepcopy(body["data"][0]))
            return httpx.Response(200, json=body)

        recorded.reset_mock()
        with patch.object(runware, "_post", side_effect=duplicated) as post:
            error = failure(lambda: runware.structured("System", "Question", schemas.QAOut))
        check("providers: duplicate task results are refused and returned costs remain recorded",
              bool(error) and post.call_count == 1 and recorded.call_count == 2)
        check("providers: no fake-provider contract opened a network socket", not any(guard.called for guard in network))
