"""Runware's native text API: JSON output, local validation, one repair attempt.

The endpoint and bearer token stay server-side. No provider/network retries are
hidden here: a failed provider yields to the caller's existing fallback policy.
"""
from __future__ import annotations

import math
import time
import uuid
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from .. import config, usage
from . import mock

T = TypeVar("T", bound=BaseModel)
ENDPOINT = "https://api.runware.ai/v1"
KIND = "runware-structured"
DEFAULT_TIMEOUT = 120.0
_MODEL_ALIASES = (
    {"deepseek:v4@flash", "deepseek-v4-flash"},
    {"openai:gpt@5.5", "openai-gpt-5-5"},
)


class RunwareError(RuntimeError):
    """A safe diagnostic that never includes provider bodies or credentials."""


def _redact(text: str) -> str:
    if not isinstance(text, str):
        return "[invalid text]"
    key = config.RUNWARE_API_KEY
    return text.replace(key, "[redacted]") if key else text


def _text(content: str | list[dict]) -> str:
    if isinstance(content, str):
        text = content
    elif isinstance(content, list) and all(
        isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str)
        for block in content
    ):
        text = "\n".join(block["text"] for block in content)
    else:
        raise RunwareError("Runware text fallback accepts text only; media must use the original provider")
    if not text.strip():
        raise RunwareError("Runware requires a non-empty text message")
    return text


def _messages(content: str | list[dict], history: list[dict] | None) -> list[dict]:
    messages = []
    if history is not None and not isinstance(history, list):
        raise RunwareError("Runware history must contain text chat messages")
    for message in history or []:
        if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
            raise RunwareError("Runware history supports user and assistant messages only")
        messages.append({"role": message["role"], "content": _text(message.get("content"))})
    messages.append({"role": "user", "content": _text(content)})
    return messages


def _post(task: dict, timeout: float) -> httpx.Response:
    """Transport seam for free evals (replace this or use httpx.MockTransport)."""
    with httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False) as client:
        return client.post(ENDPOINT, headers={"Authorization": "Bearer " + config.RUNWARE_API_KEY}, json=[task])


def _number(value) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        number = float(value)
    except (OverflowError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _metrics(result: dict) -> tuple[int, int, float | None]:
    counts = result.get("usage")
    counts = counts if isinstance(counts, dict) else {}
    inp = _number(counts.get("promptTokens"))
    out = _number(counts.get("completionTokens"))
    return int(inp or 0), int(out or 0), _number(result.get("cost"))


def _same_model(chosen: str, returned) -> bool:
    return isinstance(returned, str) and (chosen == returned or any(
        chosen in aliases and returned in aliases for aliases in _MODEL_ALIASES
    ))


def _api_error(body: dict, status: int = 200) -> str:
    # Only documented, allowlisted codes become diagnostics. Provider messages
    # can echo request data; never put them (or arbitrary code strings) in logs.
    known = {
        "invalidApiKey": "Runware invalidApiKey: check RUNWARE_API_KEY in .env",
        "timeoutProvider": "Runware timeoutProvider: the model provider timed out",
        "providerRateLimitExceeded": "Runware providerRateLimitExceeded: the model provider is rate limited",
    }
    errors = body.get("errors") or body.get("error") or []
    if isinstance(errors, dict):
        errors = [errors]
    if isinstance(errors, list):
        for error in errors:
            code = error.get("code") if isinstance(error, dict) else None
            if isinstance(code, str) and code in known:
                return known[code]
    statuses = {401: "invalid API key", 402: "insufficient account balance; top up Runware",
                403: "API key lacks permission", 429: "rate limit exceeded", 503: "service unavailable"}
    if status < 200 or status >= 300:
        return f"Runware HTTP error {status}" + (f": {statuses[status]}" if status in statuses else "")
    return "Runware API reported a task error"


def _diagnostic(error: Exception) -> str:
    if isinstance(error, RunwareError):
        return str(error)
    if isinstance(error, httpx.TimeoutException):
        return "Runware request timed out"
    if isinstance(error, httpx.RequestError):
        return "Could not reach the Runware API"
    if isinstance(error, ValidationError):
        return "Runware returned JSON that failed schema validation"
    return "Runware structured request failed"


def _trace(model: str, started: float, system: str, user: str, response: str = "", error: str = "",
           inp: int = 0, out: int = 0, cost: float | None = None) -> None:
    usage.trace(KIND, _redact(model), latency_ms=(time.monotonic() - started) * 1000,
                system=_redact(system), user=_redact(user), response=_redact(response), error=_redact(error),
                input_tokens=inp, output_tokens=out, usd=cost)


def structured(system: str, content: list[dict] | str, schema: type[T], *, history: list[dict] | None = None,
               max_tokens: int = 1500, timeout: float | None = None, model: str | None = None, stop_event=None) -> T:
    """Return only a Pydantic-valid result; the consumers retain grounding checks.

Timeout supplies a shared remaining budget to HTTPX's network-phase timeouts
and prevents starting a repair after the deadline. This synchronous transport
does not promise hard wall-clock cancellation of a trickling response.
Runware accepts a JSON-schema envelope. strict=False avoids imposing an
undocumented constrained-decoding subset on the application's Pydantic schemas;
JSON mode and local validation are always required.
    """
    chosen = model or config.RUNWARE_TEXT_MODEL
    started = time.monotonic()
    user = ""
    try:
        if not isinstance(system, str):
            raise RunwareError("Runware system instructions must be text")
        messages = _messages(content, history)
        user = messages[-1]["content"]
        if config.MOCK_LLM:
            result = mock.fake(schema)
            _trace("mock", started, system, user, result.model_dump_json())
            return result
        if not config.RUNWARE_API_KEY:
            raise RunwareError("RUNWARE_API_KEY is not set in .env")
        if not isinstance(chosen, str) or not chosen.strip():
            raise RunwareError("Runware text model is not configured")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or max_tokens < 1:
            raise RunwareError("Runware max_tokens must be a positive integer")
        budget = DEFAULT_TIMEOUT if timeout is None else float(timeout)
        if not math.isfinite(budget) or budget <= 0:
            raise RunwareError("Runware timeout must be a positive finite number")
        deadline = started + budget
        json_schema = {"name": "response", "schema": schema.model_json_schema(), "strict": False}
    except Exception as error:
        safe = _diagnostic(error)
        _trace(chosen, started, system if isinstance(system, str) else "", user, error=safe)
        raise RunwareError(safe) from None

    for attempt in range(2):
        if stop_event is not None and stop_event.is_set():
            raise RunwareError("Runware request cancelled before generation")
        attempt_started = time.monotonic()
        text = ""
        inp = out = 0
        cost = None
        failure = ""
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RunwareError("Runware request timed out")
            task_id = str(uuid.uuid4())
            settings = {"maxTokens": max_tokens}
            if system:
                settings["systemPrompt"] = system
            task = {"taskType": "textInference", "taskUUID": task_id, "model": chosen,
                    "deliveryMethod": "sync", "outputFormat": "JSON", "jsonSchema": json_schema,
                    "messages": messages, "settings": settings, "includeCost": True, "includeUsage": True}
            response = _post(task, remaining)
            try:
                body = response.json()
            except ValueError:
                if response.status_code < 200 or response.status_code >= 300:
                    raise RunwareError(_api_error({}, response.status_code)) from None
                raise RunwareError("Runware returned an invalid API response") from None
            data = body.get("data") if isinstance(body, dict) else None
            matched = [item for item in data if isinstance(item, dict) and item.get("taskUUID") == task_id] if isinstance(data, list) else []
            # Account for returned generations before rejecting bad JSON, truncation,
            # or an API envelope that mixes this task with an error/unrelated task.
            for item in matched:
                item_in, item_out, item_cost = _metrics(item)
                usage.record(KIND, _redact(chosen), input_tokens=item_in, output_tokens=item_out, usd=item_cost)
            if len(matched) == 1:
                result = matched[0]
                inp, out, cost = _metrics(result)
                text = result.get("text") if isinstance(result.get("text"), str) else ""
            # Returned generations remain billable/observable even when this
            # lane lost while HTTP was in flight. Never publish or repair them.
            if stop_event is not None and stop_event.is_set():
                raise RunwareError("Runware result ignored after cancellation")
            if response.status_code < 200 or response.status_code >= 300:
                raise RunwareError(_api_error(body if isinstance(body, dict) else {}, response.status_code))
            if not isinstance(body, dict) or body.get("errors") or body.get("error"):
                raise RunwareError(_api_error(body if isinstance(body, dict) else {}))
            if not isinstance(data, list) or len(data) != 1 or len(matched) != 1:
                raise RunwareError("Runware returned no unique matching task")
            if result.get("taskType") != "textInference" or not _same_model(chosen, result.get("model", chosen)):
                raise RunwareError("Runware returned an unrelated task")
            if result.get("error") or result.get("errors"):
                raise RunwareError(_api_error(result))
            if result.get("refusal"):
                raise RunwareError("Runware rejected the text request")
            if result.get("finishReason") != "stop":
                raise RunwareError("Runware returned an incomplete or refused answer")
            if not text.strip():
                raise RunwareError("Runware returned no text")
            if time.monotonic() >= deadline:
                raise RunwareError("Runware request timed out")
            try:
                return schema.model_validate_json(text)
            except ValidationError:
                failure = "Runware returned JSON that failed schema validation"
                if attempt:
                    raise RunwareError(failure) from None
                # The schema is already supplied with the request. Do not expose
                # validation internals or copy credentials into a repair prompt.
                messages = messages + [{"role": "assistant", "content": _redact(text)[:120000]},
                                       {"role": "user", "content": "That response failed JSON/schema validation. Return only one corrected JSON object matching the supplied schema."}]
        except Exception as error:
            failure = _diagnostic(error)
            raise RunwareError(failure) from None
        finally:
            _trace(chosen, attempt_started, system, user, text, failure, inp, out, cost)
    raise RunwareError("Runware returned no validated answer")
