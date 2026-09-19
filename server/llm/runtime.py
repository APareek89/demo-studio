"""Runtime model calls — the customer is waiting.

Providers are tried in RUNTIME_PROVIDERS order (default gemini, claude, runware), with bounded attempts.
When every provider fails the caller declines and offers a callback: never a guess, never a silent wait.
Build-time stages keep their own path (claude.structured with its full retries and fallback)."""
from __future__ import annotations

import time
from typing import TypeVar

from pydantic import BaseModel

from .. import config, usage
from . import claude, gemini, mock, runware

T = TypeVar("T", bound=BaseModel)


def structured(system: str, content: str, schema: type[T], *, history: list[dict] | None = None,
               max_tokens: int = 1500, thinking_level: str | None = None,
               timeout_budget_s: float | None = None) -> T:
    if config.MOCK_LLM:
        out = mock.fake(schema)
        usage.trace("runtime", "mock", latency_ms=5, system=system, user=content, response=out.model_dump_json()[:4000])
        return out
    errors: list[str] = []
    deadline = time.monotonic() + timeout_budget_s if timeout_budget_s is not None else None
    providers = list(config.RUNTIME_PROVIDERS)
    for index, provider in enumerate(providers):
        t0 = time.time()
        remaining = deadline - time.monotonic() if deadline is not None else config.RUNTIME_TIMEOUT
        if remaining <= (.4 if deadline else 0):
            errors.append("whole-turn deadline reached")
            break
        # One bounded attempt per provider in the conversational graph. Legacy
        # callers retain their contract; fallbacks share, never reset, this clock.
        timeout = min(config.RUNTIME_TIMEOUT, remaining)
        if deadline and index < len(providers) - 1:
            # A stalled primary must not consume the whole conversational clock.
            # Leave useful time for fallback, while never extending this deadline.
            reserve = min(2.0 * (len(providers)-index-1), remaining * .45)
            timeout = min(timeout, 7.0 if index == 0 else timeout, remaining - reserve)
            if timeout < .4:
                continue
        try:
            if provider == "claude":
                selected_model = config.CLAUDE_RUNTIME_MODEL
                result = claude.structured(system, content, schema, max_tokens=max_tokens, history=history,
                                          timeout=timeout, max_retries=0 if deadline else 1, model=selected_model, fallback=False)
            elif provider == "gemini":
                msgs = list(history or []) + [{"role": "user", "content": content}]
                thinking = {"thinking_level": thinking_level} if thinking_level is not None else {}
                selected_model = config.GEMINI_RUNTIME_MODEL
                result = gemini.text_structured(system, claude._fallback_transcript(msgs), schema, max_tokens=max_tokens,
                                               timeout_s=timeout, model=selected_model, tries=1 if deadline else 2, kind="runtime", **thinking)
            elif provider == "runware":
                selected_model = config.RUNWARE_TEXT_MODEL
                result = runware.structured(system, content, schema, history=history, max_tokens=max_tokens,
                                           timeout=timeout, model=selected_model)
            else:
                errors.append(f"{provider}: unknown provider")
                continue
            # Side metadata does not enter the provider schema or its fact fields.
            object.__setattr__(result, "_runtime_provider", provider)
            object.__setattr__(result, "_runtime_model", selected_model)
            return result
        except Exception as e:  # noqa: BLE001 — the next provider gets its turn; the caller declines when all fail
            errors.append(f"{provider}: {str(e)[:120]}")
            usage.trace(f"runtime-{provider}", provider, latency_ms=(time.time() - t0) * 1000, user=content[:2000], error=str(e)[:300])
    raise RuntimeError("all runtime providers failed — " + " | ".join(errors))
