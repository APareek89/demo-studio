"""Claude — the reasoning/writing model. Structured outputs via Pydantic (messages.parse)."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from .. import config, usage
from . import mock

T = TypeVar("T", bound=BaseModel)
_client: anthropic.Anthropic | None = None


def client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        if not config.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY, max_retries=3, timeout=600.0)
    return _client


def image_block(p: Path) -> dict:
    mt = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    if mt not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mt = "image/jpeg"
    return {"type": "image", "source": {"type": "base64", "media_type": mt,
                                        "data": base64.standard_b64encode(p.read_bytes()).decode()}}


def pdf_block(p: Path, title: str = "") -> dict:
    blk = {"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                          "data": base64.standard_b64encode(p.read_bytes()).decode()}}
    if title:
        blk["title"] = title
    return blk


def text_block(text: str) -> dict:
    return {"type": "text", "text": text}


def _blocks_text(content) -> str:
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict):
            if b.get("type") == "text":
                out.append(b.get("text", ""))
            elif b.get("type") == "document":
                out.append("[pdf document]")
            elif b.get("type") == "image":
                out.append("[image]")
    return "\n".join(out)


def _supports_effort(model: str) -> bool:
    return "haiku" not in (model or "")


def _provider_unavailable(e: Exception) -> bool:
    msg = str(e).lower()
    markers = ("credit balance", "billing", "rate limit", "overloaded", "high demand", "api key", "authentication", "connection error", "529", "503")
    return isinstance(e, (anthropic.AuthenticationError, anthropic.RateLimitError, anthropic.APIConnectionError)) or any(m in msg for m in markers)


def _text_only_messages(msgs: list[dict]) -> bool:
    for msg in msgs:
        content = msg.get("content", "")
        if isinstance(content, str):
            continue
        if not isinstance(content, list) or any(not isinstance(b, dict) or b.get("type") != "text" for b in content):
            return False
    return True


def _fallback_transcript(msgs: list[dict]) -> str:
    return "\n\n".join(f"{str(m.get('role', 'user')).upper()}:\n{_blocks_text(m.get('content'))}" for m in msgs)


def _record(resp, kind: str = "claude", *, t0: float | None = None, system: str = "", msgs: list | None = None, error: str = "", model: str | None = None) -> None:
    try:
        u = resp.usage if resp is not None else None
        inp = ((u.input_tokens or 0) + (getattr(u, "cache_read_input_tokens", 0) or 0) + (getattr(u, "cache_creation_input_tokens", 0) or 0)) if u else 0
        outp = (u.output_tokens or 0) if u else 0
        usage.record(kind, model or config.CLAUDE_MODEL, input_tokens=inp, output_tokens=outp)
        resp_text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text") if resp is not None else ""
        last_user = _blocks_text(msgs[-1]["content"]) if msgs else ""
        usage.trace(kind, model or config.CLAUDE_MODEL, latency_ms=(time.time() - t0) * 1000 if t0 else 0, system=system, user=last_user, response=resp_text, error=error, input_tokens=inp, output_tokens=outp)
    except Exception:
        pass


def _client_opts(timeout: float | None = None, max_retries: int | None = None) -> anthropic.Anthropic:
    kw: dict = {}
    if timeout:
        kw["timeout"] = timeout
    if max_retries is not None:
        kw["max_retries"] = max_retries
    return client().with_options(**kw) if kw else client()


def structured(system: str, content: list[dict] | str, schema: type[T], *, max_tokens: int = 16000,
               history: list[dict] | None = None, soft: bool = False, effort: str | None = None, timeout: float | None = None,
               model: str | None = None, fallback: bool = True, max_retries: int | None = None) -> T:
    """One call, validated output. `content` is the user turn (blocks or plain text).
    soft=True skips constrained decoding (plain JSON + validation) — faster and immune to the grammar-size limit.
    fallback=False disables the built-in Gemini fallback (the runtime layer orders providers itself)."""
    if config.MOCK_LLM:
        out = mock.fake(schema)
        usage.trace("claude", "mock", latency_ms=5, system=system, user=(content if isinstance(content, str) else json.dumps(content)[:4000]), response=out.model_dump_json()[:4000])
        return out
    msgs = list(history or [])
    msgs.append({"role": "user", "content": content if isinstance(content, list) else [text_block(content)]})
    try:
        if soft:
            return _soft_structured(system, msgs, schema, max_tokens, effort=effort, timeout=timeout, model=model, max_retries=max_retries)
        t0 = time.time()
        try:
            resp = _client_opts(timeout, max_retries).messages.parse(
                model=model or config.CLAUDE_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=msgs,
                output_format=schema,
            )
        except anthropic.BadRequestError as e:
            # Large schemas (Plan, ScriptOut) can exceed the constrained-decoding grammar limit.
            # Fall back to plain JSON + Pydantic validation with one repair pass.
            if "grammar" in str(e).lower() or "too large" in str(e).lower() or "schema" in str(e).lower():
                return _soft_structured(system, msgs, schema, max_tokens)
            raise
        _record(resp, "claude-structured", model=model, t0=t0, system=system, msgs=msgs)
        if resp.stop_reason == "refusal":
            raise RuntimeError("Claude declined this request")
        parsed = resp.parsed_output
        if parsed is None:
            raise RuntimeError("Claude returned no structured output")
        return parsed
    except Exception as e:
        if fallback and _provider_unavailable(e) and _text_only_messages(msgs) and config.GEMINI_API_KEY:
            from . import gemini
            return gemini.text_structured(system, _fallback_transcript(msgs), schema, max_tokens=max_tokens, fallback_reason=describe_error(e))
        raise


def _extract_json(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    s, e = t.find("{"), t.rfind("}")
    return t[s:e + 1] if s >= 0 and e > s else t


def _soft_structured(system: str, msgs: list[dict], schema: type[T], max_tokens: int, effort: str | None = None, timeout: float | None = None, model: str | None = None, max_retries: int | None = None) -> T:
    model = model or config.CLAUDE_MODEL
    sys2 = system + "\n\nOUTPUT FORMAT: return ONLY one JSON object — no markdown fences, no prose before or after — that validates against this JSON schema:\n" + json.dumps(schema.model_json_schema())
    kw = {"output_config": {"effort": effort}} if effort and _supports_effort(model) else {}
    c = _client_opts(timeout, max_retries)
    t0 = time.time()
    resp = c.messages.create(model=model, max_tokens=max_tokens, system=sys2, messages=msgs, **kw)
    _record(resp, "claude-soft", model=model, t0=t0, system=system, msgs=msgs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    text = _extract_json("".join(b.text for b in resp.content if b.type == "text"))
    try:
        return schema.model_validate_json(text)
    except Exception as ve:  # one repair pass with the validation errors
        repair = msgs + [{"role": "assistant", "content": text[:120000]},
                         {"role": "user", "content": f"That JSON failed validation:\n{str(ve)[:3000]}\nReturn the corrected JSON object only."}]
        t1 = time.time()
        resp2 = c.messages.create(model=model, max_tokens=max_tokens, system=sys2, messages=repair, **kw)
        _record(resp2, "claude-soft-repair", model=model, t0=t1, system=system, msgs=repair)
        text2 = _extract_json("".join(b.text for b in resp2.content if b.type == "text"))
        return schema.model_validate_json(text2)


def text(system: str, content: list[dict] | str, *, max_tokens: int = 4000, history: list[dict] | None = None, model: str | None = None) -> str:
    if config.MOCK_LLM:
        return "This is a mock reply — set real keys in .env to get the alignment agent."
    msgs = list(history or [])
    msgs.append({"role": "user", "content": content if isinstance(content, list) else [text_block(content)]})
    t0 = time.time()
    resp = client().messages.create(model=model or config.CLAUDE_MODEL, max_tokens=max_tokens, system=system, messages=msgs)
    _record(resp, "claude-text", model=model, t0=t0, system=system, msgs=msgs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def describe_error(e: Exception) -> str:
    if isinstance(e, anthropic.AuthenticationError):
        return "Anthropic API key was rejected — check ANTHROPIC_API_KEY in .env"
    if isinstance(e, anthropic.RateLimitError):
        return "Anthropic rate limit hit — wait a minute and retry"
    if isinstance(e, anthropic.APIStatusError):
        return f"Anthropic API error {e.status_code}: {getattr(e, 'message', str(e))[:200]}"
    if isinstance(e, anthropic.APIConnectionError):
        return "Could not reach the Anthropic API — check the network"
    return str(e)[:300]
