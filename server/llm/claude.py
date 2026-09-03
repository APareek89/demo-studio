"""Claude — the reasoning/writing model. Structured outputs via Pydantic (messages.parse)."""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

from .. import config
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


def structured(system: str, content: list[dict] | str, schema: type[T], *, max_tokens: int = 16000,
               history: list[dict] | None = None) -> T:
    """One call, validated output. `content` is the user turn (blocks or plain text)."""
    if config.MOCK_LLM:
        return mock.fake(schema)
    msgs = list(history or [])
    msgs.append({"role": "user", "content": content if isinstance(content, list) else [text_block(content)]})
    try:
        resp = client().messages.parse(
            model=config.CLAUDE_MODEL,
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
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    parsed = resp.parsed_output
    if parsed is None:
        raise RuntimeError("Claude returned no structured output")
    return parsed


def _extract_json(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.S).strip()
    s, e = t.find("{"), t.rfind("}")
    return t[s:e + 1] if s >= 0 and e > s else t


def _soft_structured(system: str, msgs: list[dict], schema: type[T], max_tokens: int) -> T:
    sys2 = system + "\n\nOUTPUT FORMAT: return ONLY one JSON object — no markdown fences, no prose before or after — that validates against this JSON schema:\n" + json.dumps(schema.model_json_schema())
    resp = client().messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=sys2, messages=msgs)
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude declined this request")
    text = _extract_json("".join(b.text for b in resp.content if b.type == "text"))
    try:
        return schema.model_validate_json(text)
    except Exception as ve:  # one repair pass with the validation errors
        repair = msgs + [{"role": "assistant", "content": text[:120000]},
                         {"role": "user", "content": f"That JSON failed validation:\n{str(ve)[:3000]}\nReturn the corrected JSON object only."}]
        resp2 = client().messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=sys2, messages=repair)
        text2 = _extract_json("".join(b.text for b in resp2.content if b.type == "text"))
        return schema.model_validate_json(text2)


def text(system: str, content: list[dict] | str, *, max_tokens: int = 4000, history: list[dict] | None = None) -> str:
    if config.MOCK_LLM:
        return "This is a mock reply — set real keys in .env to get the alignment agent."
    msgs = list(history or [])
    msgs.append({"role": "user", "content": content if isinstance(content, list) else [text_block(content)]})
    resp = client().messages.create(model=config.CLAUDE_MODEL, max_tokens=max_tokens, system=system, messages=msgs)
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
