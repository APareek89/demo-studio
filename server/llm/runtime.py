"""Runtime model calls — the customer is waiting.

Providers are tried in RUNTIME_PROVIDERS order (default gemini, claude, runware), with bounded attempts.
When every provider fails the caller declines and offers a callback: never a guess, never a silent wait.
Build-time stages keep their own path (claude.structured with its full retries and fallback)."""
from __future__ import annotations

import hashlib
import contextvars
import copy
import json
import math
import uuid
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


def _sequential(system: str, content: str, schema: type[T], *, history: list[dict] | None = None,
               max_tokens: int = 1500, thinking_level: str | None = None,
               timeout_budget_s: float | None = None, cancel_event=None) -> T:
    if config.MOCK_LLM:
        out = mock.fake(schema)
        usage.trace("runtime", "mock", latency_ms=5, system=system, user=content, response=out.model_dump_json()[:4000])
        return out
    errors: list[str] = []
    deadline = time.monotonic() + timeout_budget_s if timeout_budget_s is not None else None
    providers = list(config.RUNTIME_PROVIDERS)
    for index, provider in enumerate(providers):
        if cancel_event is not None and cancel_event.is_set():
            raise InterruptedError("Runtime turn cancelled")
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
                                           timeout=timeout, model=selected_model, **({"stop_event":cancel_event} if cancel_event is not None else {}))
            else:
                errors.append(f"{provider}: unknown provider")
                continue
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("Runtime turn cancelled")
            # Side metadata does not enter the provider schema or its fact fields.
            object.__setattr__(result, "_runtime_provider", provider)
            object.__setattr__(result, "_runtime_model", selected_model)
            return result
        except InterruptedError:
            raise
        except Exception as e:  # noqa: BLE001 — the next provider gets its turn; the caller declines when all fail
            if credit_identity is not None and _explicit_credit_failure(e):
                with _credit_lock:
                    _credit_cooldowns[credit_identity] = time.monotonic() + _CREDIT_COOLDOWN_S
            errors.append(f"{provider}: {str(e)[:120]}")
            usage.trace(f"runtime-{provider}", provider, latency_ms=(time.time() - t0) * 1000, user=content[:2000], error=str(e)[:300])
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("Runtime turn cancelled")
    raise RuntimeError("all runtime providers failed — " + " | ".join(errors))


_HEDGE_DELAY_S = config.RUNTIME_HEDGE_DELAY_S
_PRIMARY_CAP_S = 7.0
_MIN_ATTEMPT_S = .4


class _StopToken:
    """One local winner/deadline and an optional external turn cancellation."""
    def __init__(self, deadline, retired, external):
        self.deadline, self.retired, self.external = deadline, retired, external

    def is_set(self):
        return (self.retired.is_set() or time.monotonic() >= self.deadline
                or (self.external is not None and self.external.is_set()))


def _hedged(system: str, content: str, schema: type[T], *, history: list[dict] | None,
            max_tokens: int, thinking_level: str | None, timeout_budget_s: float,
            cancel_event=None, trace_context: dict | None = None) -> T:
    """One delayed fallback lane; ignored in-flight work may still incur cost.

    Synchronous transports are not forcibly terminated. Each spawned thread gets
    its own copied Context so returned usage is attributed even after this call
    has selected another result. Only the atomic winner can return to the graph.
    """
    started=time.monotonic();deadline=started+timeout_budget_s
    providers=list(dict.fromkeys(config.RUNTIME_PROVIDERS))
    retired=threading.Event();stop=_StopToken(deadline,retired,cancel_event)
    lock=threading.Condition()
    state={"winner":None,"primary_done":False,"fallback_done":False,"fallback_started":False,"errors":[]}
    call_id="rh_"+uuid.uuid4().hex
    context={k:str(v)[:120] for k,v in (trace_context or {}).items() if k in {"session_id","turn_id","phase"}}

    def trace(event,provider="",**details):
        usage.trace("runtime-hedge",provider or "code",latency_ms=(time.monotonic()-started)*1000,
                    response=json.dumps({"call_id":call_id,"attempt_id":call_id+":"+provider if provider else "",
                                         "event":event,**context,**details}),usd=0)

    def skipped_before_dispatch(provider,reason):
        # 'launch' is preparation intent. Close it explicitly when a later
        # gate retires this lane before the provider adapter has been called.
        trace("skipped_before_dispatch",provider,reason=reason,dispatched=False)
        return None

    def invoke(provider,index):
        # This initial gate avoids preparation for an already-lost lane. The
        # dispatch gate below also covers retirement during tracing/history copy.
        if stop.is_set():return None
        remaining=deadline-time.monotonic()
        if remaining<=_MIN_ATTEMPT_S:return None
        timeout=min(config.RUNTIME_TIMEOUT,remaining)
        if index==0:timeout=min(timeout,_PRIMARY_CAP_S)
        elif index<len(providers)-1:
            timeout=min(timeout,remaining-min(2.0*(len(providers)-index-1),remaining*.45))
        if timeout<_MIN_ATTEMPT_S:return None
        identity=None
        if provider=="claude":
            identity=_claude_identity(config.CLAUDE_RUNTIME_MODEL)
            wait=_credit_wait(identity)
            if wait:
                trace("credit_cooldown_skip",provider,remaining_ms=round(remaining*1000),cooldown_ms=round(wait*1000))
                return None
        if stop.is_set():return None
        trace("launch",provider,timeout_ms=round(timeout*1000),remaining_ms=round(remaining*1000))
        try:
            # Each lane receives independent inputs; an adapter must not mutate
            # the other lane's conversation or shared evidence prompt.
            lane_history=copy.deepcopy(history)
            if provider=="gemini":
                model=config.GEMINI_RUNTIME_MODEL
                extra={"thinking_level":thinking_level} if thinking_level is not None else {}
                adapter=gemini.text_structured
                args=(system,claude._fallback_transcript(list(lane_history or [])+[{"role":"user","content":content}]),schema)
                kwargs=dict(max_tokens=max_tokens,model=model,tries=1,kind="runtime",**extra)
                timeout_key="timeout_s"
            elif provider=="claude":
                model=config.CLAUDE_RUNTIME_MODEL
                adapter=claude.structured;args=(system,content,schema)
                kwargs=dict(max_tokens=max_tokens,history=lane_history,max_retries=0,model=model,fallback=False)
                timeout_key="timeout"
            elif provider=="runware":
                model=config.RUNWARE_TEXT_MODEL
                adapter=runware.structured;args=(system,content,schema)
                kwargs=dict(history=lane_history,max_tokens=max_tokens,model=model,stop_event=stop)
                timeout_key="timeout"
            else:raise RuntimeError("Unknown runtime provider")
            # Logging, deep copy and transcript assembly may yield while another
            # lane wins or this turn expires. Nothing expensive belongs between
            # this last check and the adapter boundary. Once transport starts it
            # may still complete and incur cost; its late result is ignored.
            if stop.is_set():return skipped_before_dispatch(provider,"stop_requested")
            remaining=deadline-time.monotonic()
            timeout=min(timeout,config.RUNTIME_TIMEOUT,remaining)
            if index==0:timeout=min(timeout,_PRIMARY_CAP_S)
            elif index<len(providers)-1:
                timeout=min(timeout,remaining-min(2.0*(len(providers)-index-1),remaining*.45))
            if timeout<_MIN_ATTEMPT_S:return skipped_before_dispatch(provider,"insufficient_budget")
            kwargs[timeout_key]=timeout
            if stop.is_set():return skipped_before_dispatch(provider,"stop_requested")
            result=adapter(*args,**kwargs)
            if not isinstance(result,schema):raise TypeError("Provider did not return the requested structured schema")
            with lock:
                if stop.is_set() or state["winner"] is not None:
                    trace("late_result_ignored",provider)
                    return None
                object.__setattr__(result,"_runtime_provider",provider)
                object.__setattr__(result,"_runtime_model",model)
                object.__setattr__(result,"_runtime_call_id",call_id)
                state["winner"]=result
                retired.set()
                trace("winner",provider)
                lock.notify_all()
            return result
        except Exception as exc:
            if identity is not None and _explicit_credit_failure(exc):
                with _credit_lock:_credit_cooldowns[identity]=time.monotonic()+_CREDIT_COOLDOWN_S
            with lock:
                state["errors"].append(provider+": "+str(exc)[:120])
                trace("late_error_ignored" if stop.is_set() else "attempt_failed",provider,error=usage.redact(str(exc))[:300])
                lock.notify_all()
            return None

    def primary():
        try:invoke(providers[0],0)
        finally:
            with lock:state["primary_done"]=True;lock.notify_all()

    def fallback():
        try:
            for index,provider in enumerate(providers[1:],1):
                if stop.is_set():break
                if invoke(provider,index) is not None:break
        finally:
            with lock:state["fallback_done"]=True;lock.notify_all()

    def launch(target):
        ctx=contextvars.copy_context()
        threading.Thread(target=lambda:ctx.run(target),daemon=True,name=call_id).start()

    if cancel_event is not None and cancel_event.is_set():raise InterruptedError("Runtime turn cancelled")
    trace("start",primary_cap_ms=round(min(_PRIMARY_CAP_S,timeout_budget_s)*1000),hedge_delay_ms=round(_HEDGE_DELAY_S*1000))
    launch(primary)
    try:
        with lock:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    trace("cancelled");raise InterruptedError("Runtime turn cancelled")
                if state["winner"] is not None:return state["winner"]
                remaining=deadline-time.monotonic()
                if remaining<=0:
                    trace("deadline");raise TimeoutError("Runtime whole-call deadline reached")
                due=started+_HEDGE_DELAY_S-time.monotonic()
                if not state["fallback_started"] and (state["primary_done"] or due<=0):
                    state["fallback_started"]=True
                    trace("fallback_lane_start",trigger="primary_finished" if state["primary_done"] else "hedge_delay")
                    launch(fallback)
                if state["primary_done"] and state["fallback_done"]:
                    raise RuntimeError("all runtime providers failed — "+" | ".join(state["errors"]))
                lock.wait(timeout=min(.025,remaining,max(.001,due) if not state["fallback_started"] else .025))
    finally:
        retired.set()


def structured(system: str, content: str, schema: type[T], *, history: list[dict] | None = None,
               max_tokens: int = 1500, thinking_level: str | None = None,
               timeout_budget_s: float | None = None, cancel_event=None,
               trace_context: dict | None = None) -> T:
    """Default sequential dispatch; opt-in bounded race for Gemini-first calls."""
    providers=list(dict.fromkeys(config.RUNTIME_PROVIDERS))
    if (config.RUNTIME_HEDGE_ENABLED and not config.MOCK_LLM and cancel_event is not None and timeout_budget_s is not None
            and math.isfinite(timeout_budget_s) and timeout_budget_s>_HEDGE_DELAY_S+_MIN_ATTEMPT_S
            and len(providers)>1 and providers[0]=="gemini"):
        return _hedged(system,content,schema,history=history,max_tokens=max_tokens,thinking_level=thinking_level,
                       timeout_budget_s=timeout_budget_s,cancel_event=cancel_event,trace_context=trace_context)
    return _sequential(system,content,schema,history=history,max_tokens=max_tokens,thinking_level=thinking_level,
                       timeout_budget_s=timeout_budget_s,cancel_event=cancel_event)
