"""Per-demo usage accounting → cost estimate. Every model/speech call records tokens or characters;
the Playground shows totals by stage with the price assumptions spelled out."""
from __future__ import annotations

import contextvars
import json
import os
import re
import time
from datetime import datetime, timezone

from . import store, config

current_demo: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_demo", default=None)
current_stage: contextvars.ContextVar[str] = contextvars.ContextVar("current_stage", default="runtime")


def redact(text: str) -> str:
    value = str(text or "")
    for name in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "RUNWARE_API_KEY", "SARVAM_API_KEY", "GCLOUD_TTS_API_KEY"):
        secret = getattr(config,name,"")
        if secret: value=value.replace(secret,"[redacted]")
    return value

# USD per 1M tokens unless noted. Override any of these in .env; they are assumptions, shown as such.
PRICES = {
    "claude-opus-5": {"in": float(os.getenv("PRICE_CLAUDE_IN", "5.0")), "out": float(os.getenv("PRICE_CLAUDE_OUT", "25.0")), "note": "Anthropic list price"},
    "claude-sonnet-5": {"in": float(os.getenv("PRICE_SONNET_IN", "3.0")), "out": float(os.getenv("PRICE_SONNET_OUT", "15.0")), "note": "assumed — set PRICE_SONNET_IN/OUT"},
    "claude-haiku-4-5": {"in": float(os.getenv("PRICE_HAIKU_IN", "1.0")), "out": float(os.getenv("PRICE_HAIKU_OUT", "5.0")), "note": "Anthropic list price"},
    "gemini-lite": {"in": float(os.getenv("PRICE_GEMINI_LITE_IN", "0.10")), "out": float(os.getenv("PRICE_GEMINI_LITE_OUT", "0.40")), "note": "assumed — set PRICE_GEMINI_LITE_IN/OUT"},
    "gemini-image": {"per_image": float(os.getenv("PRICE_GEMINI_IMAGE", "0.02")), "note": "assumed $/generated image — set PRICE_GEMINI_IMAGE"},
    "gemini-3.6-flash": {"in": float(os.getenv("PRICE_GEMINI_IN", "0.30")), "out": float(os.getenv("PRICE_GEMINI_OUT", "2.50")), "note": "assumed — set PRICE_GEMINI_IN/OUT"},
    "gemini-3.5-flash-lite": {"in": float(os.getenv("PRICE_GEMINI_TEXT_EVAL_IN", "0.30")), "out": float(os.getenv("PRICE_GEMINI_TEXT_EVAL_OUT", "2.50")), "note": "Google standard paid text price; output includes thinking"},
    "gemini-3.8-flash": {"in": float(os.getenv("PRICE_GEMINI_TEXT_CUSTOMER_IN", "0.75")), "out": float(os.getenv("PRICE_GEMINI_TEXT_CUSTOMER_OUT", "3.75")),
                         "standard_in": float(os.getenv("PRICE_GEMINI_TEXT_CUSTOMER_STANDARD_IN", "1.50")), "standard_out": float(os.getenv("PRICE_GEMINI_TEXT_CUSTOMER_STANDARD_OUT", "7.50")),
                         "note": "Google introductory price through 2026-12-31 UTC; standard rates from 2027-01-01; selected by call timestamp, output includes thinking"},
    "deepseek:v4@flash": {"in": float(os.getenv("PRICE_RUNWARE_DEEPSEEK_IN", "0.076")), "out": float(os.getenv("PRICE_RUNWARE_DEEPSEEK_OUT", "0.153")), "note": "Runware uncached list price; returned USD cost takes precedence"},
    "openai:gpt@5.5": {"in": float(os.getenv("PRICE_RUNWARE_GPT55_IN", "5.0")), "out": float(os.getenv("PRICE_RUNWARE_GPT55_OUT", "30.0")), "note": "Runware uncached list price; returned USD cost takes precedence"},
    "gemini-tts": {"in": float(os.getenv("PRICE_GEMINI_TTS_IN", "0.50")), "out": float(os.getenv("PRICE_GEMINI_TTS_OUT", "10.0")), "note": "assumed — set PRICE_GEMINI_TTS_IN/OUT"},
    "sarvam-tts": {"per_1k_chars_inr": float(os.getenv("PRICE_SARVAM_TTS_INR_1K", "1.5")), "note": "assumed ₹/1k chars — set PRICE_SARVAM_TTS_INR_1K"},
    "sarvam-stt": {"per_min_inr": float(os.getenv("PRICE_SARVAM_STT_INR_MIN", "0.5")), "note": "assumed ₹/min — set PRICE_SARVAM_STT_INR_MIN"},
}
_RUNWARE_MODELS = {"deepseek:v4@flash": "deepseek:v4@flash", "deepseek-v4-flash": "deepseek:v4@flash",
                   "openai:gpt@5.5": "openai:gpt@5.5", "openai-gpt-5-5": "openai:gpt@5.5"}
_GEMINI_38_STANDARD_FROM = datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()
FX_INR = float(os.getenv("FX_INR", "84"))
TRACE_CAPTURE = os.getenv("TRACE_CAPTURE", "full").strip().lower()  # full | meta (meta = lengths only, no prompt text)
TRACE_MAX_CHARS = int(os.getenv("TRACE_MAX_CHARS", "400000"))  # full prompts and responses by default
_PHONE = re.compile(r"(?<!\d)[6-9]\d(?:[\s-]?\d){8}(?!\d)")  # 10-digit Indian mobiles, with or without spaces/dashes
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")


def _redact(text: str, limit: int | None = None) -> str:
    limit = limit or TRACE_MAX_CHARS
    t = (text or "")[:limit]
    return _EMAIL.sub("[email]", _PHONE.sub("[phone]", t))



def record(kind: str, model: str, *, input_tokens: int = 0, output_tokens: int = 0, chars: int = 0, seconds: float = 0.0, usd: float | None = None, demo_id: str | None = None, stage: str | None = None) -> None:
    demo_id = demo_id or current_demo.get()
    if not demo_id or not store.exists(demo_id):
        return
    row = {"t": time.time(), "stage": stage or current_stage.get(), "kind": kind, "model": model,
           "in": int(input_tokens or 0), "out": int(output_tokens or 0), "chars": int(chars or 0), "sec": round(float(seconds or 0), 2)}
    if usd is not None:
        row["usd"] = round(float(usd), 6)
    elif _unpriced_runware(row):
        row["cost_note"] = "Runware cost unavailable: model has no configured price and response supplied no USD cost"
    p = store.path(demo_id, "usage.jsonl")
    try:
        with p.open("a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def trace(kind: str, model: str, *, latency_ms: float, system: str = "", user: str = "", response: str = "", error: str = "",
          input_tokens: int = 0, output_tokens: int = 0, chars: int = 0, usd: float | None = None, demo_id: str | None = None, stage: str | None = None) -> None:
    """Observability row: what was sent, what came back, how long, what it cost."""
    demo_id = demo_id or current_demo.get()
    if not demo_id or not store.exists(demo_id):
        return
    system,user,response,error = (redact(v) for v in (system,user,response,error))
    row = {"t": time.time(), "stage": stage or current_stage.get(), "kind": kind, "model": model, "latency_ms": round(latency_ms),
           "in": int(input_tokens or 0), "out": int(output_tokens or 0), "chars": int(chars or 0),
           "system": (system or "")[:TRACE_MAX_CHARS] if TRACE_CAPTURE == "full" else f"[{len(system or '')} chars]",
           "user": _redact(user) if TRACE_CAPTURE == "full" else f"[{len(user or '')} chars]",
           "response": _redact(response) if TRACE_CAPTURE == "full" else f"[{len(response or '')} chars]", "error": (error or "")[:400]}
    row["usd"] = round(float(usd), 5) if usd is not None else round(_cost_usd({**row, "sec": 0}), 5)
    if usd is None and _unpriced_runware(row):
        # Existing trace consumers expect numeric USD; make an unavailable estimate an explicit error,
        # rather than presenting an unknown override as a successful free call.
        row["error"] = (row["error"] + "; " if row["error"] else "") + "Runware cost unavailable: no configured model price or returned USD cost"
    try:
        with store.path(demo_id, "trace.jsonl").open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass


def traces(demo_id: str, limit: int = 300) -> list[dict]:
    p = store.path(demo_id, "trace.jsonl")
    if not p.exists():
        return []
    rows = []
    for line in p.read_text().splitlines()[-limit:]:
        try:
            rows.append(json.loads(line))
        except Exception:
            pass
    return rows


def _unpriced_runware(row: dict) -> bool:
    return row.get("kind", "").startswith("runware") and row.get("model") != "mock" and row.get("model") not in _RUNWARE_MODELS


def _cost_usd(row: dict) -> float:
    if row.get("usd") is not None:
        return float(row["usd"])
    m = row["model"]
    if m in _RUNWARE_MODELS:
        pr = PRICES[_RUNWARE_MODELS[m]]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if m.startswith("claude"):
        pr = PRICES["claude-haiku-4-5"] if "haiku" in m else PRICES["claude-sonnet-5"] if "sonnet" in m else PRICES["claude-opus-5"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if row["kind"] == "gemini-image":
        return PRICES["gemini-image"]["per_image"]
    if row["kind"] == "gemini-tts":
        pr = PRICES["gemini-tts"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if m.startswith("gemini"):
        if m == "gemini-3.8-flash":
            pr = PRICES[m]
            prefix = "standard_" if row.get("t", time.time()) >= _GEMINI_38_STANDARD_FROM else ""
            return row["in"] / 1e6 * pr[prefix + "in"] + row["out"] / 1e6 * pr[prefix + "out"]
        if m == "gemini-3.5-flash-lite":
            pr = PRICES[m]
            return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
        pr = PRICES["gemini-lite"] if "lite" in m else PRICES["gemini-3.6-flash"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if row["kind"] == "sarvam-tts":
        return row["chars"] / 1000 * PRICES["sarvam-tts"]["per_1k_chars_inr"] / FX_INR
    if row["kind"] == "sarvam-stt":
        return row["sec"] / 60 * PRICES["sarvam-stt"]["per_min_inr"] / FX_INR
    return 0.0


def summary(demo_id: str) -> dict:
    p = store.path(demo_id, "usage.jsonl")
    rows = []
    if p.exists():
        for line in p.read_text().splitlines():
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    by_stage: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    total = 0.0
    for r in rows:
        c = _cost_usd(r)
        total += c
        s = by_stage.setdefault(r["stage"], {"calls": 0, "in": 0, "out": 0, "chars": 0, "sec": 0.0, "usd": 0.0})
        s["calls"] += 1; s["in"] += r["in"]; s["out"] += r["out"]; s["chars"] += r["chars"]; s["sec"] += r["sec"]; s["usd"] += c
        m = by_model.setdefault(r["model"], {"calls": 0, "in": 0, "out": 0, "chars": 0, "sec": 0.0, "usd": 0.0})
        m["calls"] += 1; m["in"] += r["in"]; m["out"] += r["out"]; m["chars"] += r["chars"]; m["sec"] += r["sec"]; m["usd"] += c
    runtime = by_stage.get("runtime", {})
    sessions = len(list(store.path(demo_id, "sessions").glob("*.json"))) if store.path(demo_id, "sessions").exists() else 0
    return {"rows": len(rows), "total_usd": round(total, 4), "total_inr": round(total * FX_INR, 2), "fx_inr": FX_INR,
            "by_stage": {k: {**v, "usd": round(v["usd"], 4)} for k, v in by_stage.items()},
            "by_model": {k: {**v, "usd": round(v["usd"], 4)} for k, v in by_model.items()},
            "per_session_usd": round(runtime.get("usd", 0.0) / sessions, 4) if sessions else None, "sessions": sessions,
            "prices": PRICES}
