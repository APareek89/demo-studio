"""Per-demo usage accounting → cost estimate. Every model/speech call records tokens or characters;
the Playground shows totals by stage with the price assumptions spelled out."""
from __future__ import annotations

import contextvars
import json
import os
import time

from . import store

current_demo: contextvars.ContextVar[str | None] = contextvars.ContextVar("current_demo", default=None)
current_stage: contextvars.ContextVar[str] = contextvars.ContextVar("current_stage", default="runtime")

# USD per 1M tokens unless noted. Override any of these in .env; they are assumptions, shown as such.
PRICES = {
    "claude-opus-5": {"in": float(os.getenv("PRICE_CLAUDE_IN", "5.0")), "out": float(os.getenv("PRICE_CLAUDE_OUT", "25.0")), "note": "Anthropic list price"},
    "gemini-3.6-flash": {"in": float(os.getenv("PRICE_GEMINI_IN", "0.30")), "out": float(os.getenv("PRICE_GEMINI_OUT", "2.50")), "note": "assumed — set PRICE_GEMINI_IN/OUT"},
    "gemini-tts": {"in": float(os.getenv("PRICE_GEMINI_TTS_IN", "0.50")), "out": float(os.getenv("PRICE_GEMINI_TTS_OUT", "10.0")), "note": "assumed — set PRICE_GEMINI_TTS_IN/OUT"},
    "sarvam-tts": {"per_1k_chars_inr": float(os.getenv("PRICE_SARVAM_TTS_INR_1K", "1.5")), "note": "assumed ₹/1k chars — set PRICE_SARVAM_TTS_INR_1K"},
    "sarvam-stt": {"per_min_inr": float(os.getenv("PRICE_SARVAM_STT_INR_MIN", "0.5")), "note": "assumed ₹/min — set PRICE_SARVAM_STT_INR_MIN"},
}
FX_INR = float(os.getenv("FX_INR", "84"))


def record(kind: str, model: str, *, input_tokens: int = 0, output_tokens: int = 0, chars: int = 0, seconds: float = 0.0, demo_id: str | None = None, stage: str | None = None) -> None:
    demo_id = demo_id or current_demo.get()
    if not demo_id or not store.exists(demo_id):
        return
    row = {"t": time.time(), "stage": stage or current_stage.get(), "kind": kind, "model": model,
           "in": int(input_tokens or 0), "out": int(output_tokens or 0), "chars": int(chars or 0), "sec": round(float(seconds or 0), 2)}
    p = store.path(demo_id, "usage.jsonl")
    try:
        with p.open("a") as f:
            f.write(json.dumps(row) + "\n")
    except Exception:
        pass


def _cost_usd(row: dict) -> float:
    m = row["model"]
    if m.startswith("claude"):
        pr = PRICES["claude-opus-5"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if row["kind"] == "gemini-tts":
        pr = PRICES["gemini-tts"]
        return row["in"] / 1e6 * pr["in"] + row["out"] / 1e6 * pr["out"]
    if m.startswith("gemini"):
        pr = PRICES["gemini-3.6-flash"]
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
