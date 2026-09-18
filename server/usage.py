"""Per-demo usage accounting → cost estimate. Every model/speech call records tokens or characters;
the Playground shows totals by stage with the price assumptions spelled out."""
from __future__ import annotations

import contextvars
import json
import os
import re
import time

from . import store

current_demo: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_demo", default=None)
current_stage: contextvars.ContextVar[str] = contextvars.ContextVar("current_stage", default="runtime")

# USD per 1M tokens unless noted. Override any of these in .env; they are assumptions, shown as such.
PRICES = {
    "claude-opus-5": {"in": float(os.getenv("PRICE_CLAUDE_IN", "5.0")), "out": float(os.getenv("PRICE_CLAUDE_OUT", "25.0")), "note": "Anthropic list price"},
    "claude-sonnet-5": {"in": float(os.getenv("PRICE_SONNET_IN", "3.0")), "out": float(os.getenv("PRICE_SONNET_OUT", "15.0")), "note": "assumed — set PRICE_SONNET_IN/OUT"},
    "claude-haiku-4-5": {"in": float(os.getenv("PRICE_HAIKU_IN", "1.0")), "out": float(os.getenv("PRICE_HAIKU_OUT", "5.0")), "note": "Anthropic list price"},
    "gemini-lite": {"in": float(os.getenv("PRICE_GEMINI_LITE_IN", "0.10")), "out": float(os.getenv("PRICE_GEMINI_LITE_OUT", "0.40")), "note": "assumed — set PRICE_GEMINI_LITE_IN/OUT"},
    "gemini-image": {"per_image": float(os.getenv("PRICE_GEMINI_IMAGE", "0.02")), "note": "assumed $/generated image — set PRICE_GEMINI_IMAGE"},
    "gemini-3.6-flash": {"in": float(os.getenv("PRICE_GEMINI_IN", "0.30")), "out": float(os.getenv("PRICE_GEMINI_OUT", "2.50")), "note": "assumed — set PRICE_GEMINI_IN/OUT"},
    "gemini-tts": {"in": float(os.getenv("PRICE_GEMINI_TTS_IN", "0.50")), "out": float(os.getenv("PRICE_GEMINI_TTS_OUT", "10.0")), "note": "assumed — set PRICE_GEMINI_TTS_IN/OUT"},
    "sarvam-tts": {"per_1k_chars_inr": float(os.getenv("PRICE_SARVAM_TTS_INR_1K", "1.5")), "note": "assumed ₹/1k chars — set PRICE_SARVAM_TTS_INR_1K"},
    "sarvam-stt": {"per_min_inr": float(os.getenv("PRICE_SARVAM_STT_INR_MIN", "0.5")), "note": "assumed ₹/min — set PRICE_SARVAM_STT_INR_MIN"},
}
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
    row = {"t": time.time(), "stage": stage or current_stage.get(), "kind": kind, "model": model, "latency_ms": round(latency_ms),
           "in": int(input_tokens or 0), "out": int(output_tokens or 0), "chars": int(chars or 0),
           "system": (system or "")[:TRACE_MAX_CHARS] if TRACE_CAPTURE == "full" else f"[{len(system or '')} chars]",
           "user": _redact(user) if TRACE_CAPTURE == "full" else f"[{len(user or '')} chars]",
           "response": _redact(response) if TRACE_CAPTURE == "full" else f"[{len(response or '')} chars]", "error": (error or "")[:400]}
    row["usd"] = round(float(usd), 5) if usd is not None else round(_cost_usd({**row, "sec": 0}), 5)
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


def _cost_usd(row: dict) -> float:
    if row.get("usd") is not None:
        return float(row["usd"])
    m = row["model"]
    if m.startswith("claude"):
        pr = PRICES["claude-haiku-4-5"] if "haiku" in m else PRICES["claude-sonnet-5"] if "sonnet" in m else PRICES["claude-opus-5"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if row["kind"] == "gemini-image":
        return PRICES["gemini-image"]["per_image"]
    if row["kind"] == "gemini-tts":
        pr = PRICES["gemini-tts"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if m.startswith("gemini"):
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
