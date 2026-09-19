"""Runtime model calls — the customer is waiting.

Providers are tried in RUNTIME_PROVIDERS order (default gemini, claude, runware), with bounded attempts.
When every provider fails the caller declines and offers a callback: never a guess, never a silent wait.
Build-time stages keep their own path (claude.structured with its full retries and fallback)."""
from __future__ import annotations

import hashlib
import os
import threading
import time
from typing import TypeVar

from pydantic import BaseModel

from .. import config, usage
from . import claude, gemini, mock, runware

T = TypeVar("T", bound=BaseModel)
_CREDIT_COOLDOWN_S = 60.0
_credit_cooldowns: dict[bytes, float] = {}
_credit_lock = threading.Lock()


def _claude_identity(model: str) -> bytes:
    # The cached SDK client can still hold the effective key after configuration
    # changes. Hash its actual credential and endpoint; never retain/log the key.
    cached = claude._client
    key = getattr(cached, "api_key", config.ANTHROPIC_API_KEY)
    endpoint = str(getattr(cached, "base_url", None) or os.getenv("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip("/")
    return hashlib.sha256(f"claude\0{model}\0{key}\0{endpoint}".encode()).digest()


def _explicit_credit_failure(error: Exception) -> bool:
    # Only the observed non-retryable Anthropic response. Timeouts, 429s,
    # authentication errors and unrelated 400s must not poison the next turn.
    if not isinstance(error, claude.anthropic.BadRequestError) or error.status_code != 400:
        return False
    body = error.body
    detail = body.get("error") if isinstance(body, dict) else None
    return (isinstance(detail, dict) and detail.get("type") == "invalid_request_error"
            and str(detail.get("message", "")).casefold().startswith("your credit balance is too low to access the anthropic api."))


def _credit_wait(identity: bytes) -> float:
    now = time.monotonic()
    with _credit_lock:
        for expired in [key for key, until in _credit_cooldowns.items() if until <= now]:
            del _credit_cooldowns[expired]
        return max(0.0, _credit_cooldowns.get(identity, now) - now)


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
        credit_identity = None
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
                if deadline is not None:
                    credit_identity = _claude_identity(selected_model)
                    wait = _credit_wait(credit_identity)
                    if wait:
                        reason = f"Skipped: explicit insufficient-credit response; process cooldown has {wait:.1f}s remaining"
                        errors.append(f"claude: {reason}")
                        usage.trace("runtime-claude-skipped", selected_model, latency_ms=0, error=reason, usd=0)
                        continue
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
            if credit_identity is not None and _explicit_credit_failure(e):
                with _credit_lock:
                    _credit_cooldowns[credit_identity] = time.monotonic() + _CREDIT_COOLDOWN_S
            errors.append(f"{provider}: {str(e)[:120]}")
            usage.trace(f"runtime-{provider}", provider, latency_ms=(time.time() - t0) * 1000, user=content[:2000], error=str(e)[:300])
    raise RuntimeError("all runtime providers failed — " + " | ".join(errors))
