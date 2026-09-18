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


def structured(system: str, content: str, schema: type[T], *, history: list[dict] | None = None, max_tokens: int = 1500) -> T:
    if config.MOCK_LLM:
        out = mock.fake(schema)
        usage.trace("runtime", "mock", latency_ms=5, system=system, user=content, response=out.model_dump_json()[:4000])
        return out
    errors: list[str] = []
    for provider in config.RUNTIME_PROVIDERS:
        t0 = time.time()
        try:
            if provider == "claude":
                return claude.structured(system, content, schema, max_tokens=max_tokens, history=history,
                                         timeout=config.RUNTIME_TIMEOUT, max_retries=1, model=config.CLAUDE_RUNTIME_MODEL, fallback=False)
            if provider == "gemini":
                msgs = list(history or []) + [{"role": "user", "content": content}]
                return gemini.text_structured(system, claude._fallback_transcript(msgs), schema, max_tokens=max_tokens,
                                              timeout_s=config.RUNTIME_TIMEOUT, model=config.GEMINI_RUNTIME_MODEL, tries=2, kind="runtime")
            if provider == "runware":
                return runware.structured(system, content, schema, history=history, max_tokens=max_tokens,
                                          timeout=config.RUNTIME_TIMEOUT, model=config.RUNWARE_TEXT_MODEL)
            errors.append(f"{provider}: unknown provider")
        except Exception as e:  # noqa: BLE001 — the next provider gets its turn; the caller declines when all fail
            errors.append(f"{provider}: {str(e)[:120]}")
            usage.trace(f"runtime-{provider}", provider, latency_ms=(time.time() - t0) * 1000, user=content[:2000], error=str(e)[:300])
    raise RuntimeError("all runtime providers failed — " + " | ".join(errors))
