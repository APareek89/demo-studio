"""Multi-language pass — translate the approved script into each extra language chosen at configuration.
Ids, fact ids, visuals and cards are preserved; only spoken text changes. Output: script.<lang>.json."""
from __future__ import annotations

import copy
import json

from pydantic import BaseModel, Field

from .. import config, store, usage
from ..llm import claude
from .principles import LANGUAGES, language_instruction

TRANSLATE_SYSTEM = """You translate a spoken sales-demo script for {product}. {language}
Rules: keep every id exactly; translate meaning, not words — spoken register, short clauses, the way a good salesperson in that
language actually talks. Product names, model names, prices, units and numbers stay exactly as written. Keep the same number of
lines. Do not add or remove facts. Return the translated lines only."""


class TLine(BaseModel):
    id: str
    text: str


class TSegment(BaseModel):
    id: str
    title: str
    lines: list[TLine]
    checkin: str = ""
    deeper: list[TLine] = Field(default_factory=list)


class TScript(BaseModel):
    segments: list[TSegment]
    closing: list[TLine]
    intake_q1: str
    intake_q2: str


def script_path(lang: str) -> str:
    return f"script.{lang}.json"


def translate(demo_id: str, lang: str, emit) -> dict:
    """Returns the translated script (also written to script.<lang>.json). Reuses a previous translation when the
    source script hasn't changed since."""
    script = store.read_json(demo_id, "script.json") or {}
    if not script:
        raise RuntimeError("No script to translate")
    key = store.digest(json.dumps({"s": script.get("segments"), "c": script.get("closing"), "q": [script.get("intake_q1"), script.get("intake_q2")]}, sort_keys=True))
    prev = store.read_json(demo_id, script_path(lang))
    if prev and prev.get("source_digest") == key:
        emit(f"{LANGUAGES.get(lang, lang)}: translation up to date.")
        return prev
    out = copy.deepcopy(script)
    out["language"] = lang
    out["source_digest"] = key
    for seg in out["segments"]:
        for ln in seg["lines"] + seg.get("deeper", []):
            ln.pop("audio", None)
        seg.pop("checkin_audio", None)
    for ln in out.get("closing", []):
        ln.pop("audio", None)
    out.pop("intake_audio", None)
    if config.MOCK_LLM:
        tag = f"[{lang}] "
        for seg in out["segments"]:
            for ln in seg["lines"] + seg.get("deeper", []):
                ln["text"] = tag + ln["text"]
            if seg.get("checkin"):
                seg["checkin"] = tag + seg["checkin"]
        for ln in out.get("closing", []):
            ln["text"] = tag + ln["text"]
        out["intake_q1"], out["intake_q2"] = tag + out["intake_q1"], tag + out["intake_q2"]
        store.write_json(demo_id, script_path(lang), out)
        return out
    demo = store.load(demo_id)
    product = (store.read_json(demo_id, "understanding.json") or {}).get("product", {}).get("name") or demo["name"]
    payload = {"segments": [{"id": s["id"], "title": s["title"], "lines": [{"id": l["id"], "text": l["text"]} for l in s["lines"]], "checkin": s.get("checkin", ""),
                             "deeper": [{"id": l["id"], "text": l["text"]} for l in s.get("deeper", [])]} for s in out["segments"]],
               "closing": [{"id": l["id"], "text": l["text"]} for l in out.get("closing", [])], "intake_q1": out["intake_q1"], "intake_q2": out["intake_q2"]}
    emit(f"Translating the script into {LANGUAGES.get(lang, lang)}…")
    prev_stage = usage.current_stage.get()
    usage.current_stage.set("translate")
    try:
        t = claude.structured(TRANSLATE_SYSTEM.format(product=product, language=language_instruction(lang)), json.dumps(payload, ensure_ascii=False), TScript, max_tokens=16000, soft=True, effort="low", timeout=240.0)
    finally:
        usage.current_stage.set(prev_stage)
    tmap = {}
    for seg in t.segments:
        for l in seg.lines + seg.deeper:
            tmap[l.id] = l.text
        tmap[f"checkin:{seg.id}"] = seg.checkin
        tmap[f"title:{seg.id}"] = seg.title
    for l in t.closing:
        tmap[l.id] = l.text
    missing = 0
    for seg in out["segments"]:
        seg["title"] = tmap.get(f"title:{seg['id']}") or seg["title"]
        if seg.get("checkin"):
            seg["checkin"] = tmap.get(f"checkin:{seg['id']}") or seg["checkin"]
        for ln in seg["lines"] + seg.get("deeper", []):
            if tmap.get(ln["id"]):
                ln["text"] = tmap[ln["id"]]
            else:
                missing += 1
    for ln in out.get("closing", []):
        if tmap.get(ln["id"]):
            ln["text"] = tmap[ln["id"]]
        else:
            missing += 1
    out["intake_q1"], out["intake_q2"] = t.intake_q1 or out["intake_q1"], t.intake_q2 or out["intake_q2"]
    if missing:
        emit(f"{missing} line(s) came back untranslated — kept in the main language.")
    store.write_json(demo_id, script_path(lang), out)
    store.log(demo_id, "translate", {"language": lang, "missing": missing})
    return out
