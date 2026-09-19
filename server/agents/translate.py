"""Multi-language pass — translate the approved script into each extra language chosen at configuration.
Ids, fact ids, visuals and cards are preserved; only spoken text changes. Output: script.<lang>.json."""
from __future__ import annotations

import copy
import json
import re

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
    overview: TLine | None = None


_DIGIT_MAP = {ord(c): str(i) for digits in ("०१२३४५६७८९", "০১২৩৪৫৬৭৮৯", "௦௧௨௩௪௫௬௭௮௯", "౦౧౨౩౪౫౬౭౮౯", "೦೧೨೩೪೫೬೭೮೯", "൦൧൨൩൪൫൬൭൮൯", "૦૧૨૩૪૫૬૭૮૯", "੦੧੨੩੪੫੬੭੮੯") for i, c in enumerate(digits)}


def _numbers(text: str) -> list[str]:
    """Digit groups in a line, with Indian-script numerals normalised and thousands separators removed."""
    import re
    t = (text or "").translate(_DIGIT_MAP)
    t = re.sub(r"(?<=\d)[,\s](?=\d{2,3}\b)", "", t)
    return sorted(re.findall(r"\d+(?:\.\d+)?", t))


def _keeps_numbers(src: str, dst: str) -> bool:
    return _numbers(src) == _numbers(dst)


def script_path(lang: str) -> str:
    return f"script.{lang}.json"


def translate(demo_id: str, lang: str, emit) -> dict:
    """Returns the translated script (also written to script.<lang>.json). Reuses a previous translation when the
    source script hasn't changed since."""
    script = store.read_json(demo_id, "script.json") or {}
    if not script:
        raise RuntimeError("No script to translate")
    from ..orchestrator import semantic
    key = store.digest(json.dumps({"s": semantic(script.get("segments")), "c": semantic(script.get("closing")),
                                  "q": [script.get("intake_q1"), script.get("intake_q2")],
                                  "overview": semantic(script.get("runtime_overview")), "prompt": TRANSLATE_SYSTEM}, sort_keys=True))
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
    overview = out.get("runtime_overview")
    if overview:
        for field in ("audio", "duration_seconds", "duration_exact", "duration_in_range"):
            overview.pop(field, None)
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
        if overview:
            overview["text"] = tag + overview["text"]
        store.write_json(demo_id, script_path(lang), out)
        return out
    demo = store.load(demo_id)
    product = (store.read_json(demo_id, "understanding.json") or {}).get("product", {}).get("name") or demo["name"]
    payload = {"segments": [{"id": s["id"], "title": s["title"], "lines": [{"id": l["id"], "text": l["text"]} for l in s["lines"]], "checkin": s.get("checkin", ""),
                             "deeper": [{"id": l["id"], "text": l["text"]} for l in s.get("deeper", [])]} for s in out["segments"]],
               "closing": [{"id": l["id"], "text": l["text"]} for l in out.get("closing", [])], "intake_q1": out["intake_q1"], "intake_q2": out["intake_q2"]}
    if overview:
        payload["overview"] = {"id": overview["id"], "text": overview["text"]}
    emit(f"Translating the script into {LANGUAGES.get(lang, lang)}…")
    prev_stage = usage.current_stage.get()
    usage.current_stage.set("translate")
    try:
        t = claude.structured(TRANSLATE_SYSTEM.format(product=product, language=language_instruction(lang)), json.dumps(payload, ensure_ascii=False), TScript, max_tokens=16000, soft=True, effort="low", timeout=240.0, model=config.CLAUDE_LITE_MODEL)
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
    if overview and t.overview and t.overview.id == overview["id"]:
        tmap[t.overview.id] = t.overview.text
    missing = 0
    kept = 0  # lines whose translation changed a figure — kept in the source language (no citation, no claim)

    def take(ln: dict) -> None:
        nonlocal missing, kept
        t = tmap.get(ln["id"])
        if not t:
            missing += 1
            return
        if not _keeps_numbers(ln["text"], t):
            kept += 1
            ln["kept_source"] = True
            return
        ln["text"] = t

    for seg in out["segments"]:
        seg["title"] = tmap.get(f"title:{seg['id']}") or seg["title"]
        if seg.get("checkin"):
            seg["checkin"] = tmap[f"checkin:{seg['id']}"] if _keeps_numbers(seg["checkin"], tmap.get(f"checkin:{seg['id']}") or "") and tmap.get(f"checkin:{seg['id']}") else seg["checkin"]
        for ln in seg["lines"] + seg.get("deeper", []):
            take(ln)
    for ln in out.get("closing", []):
        take(ln)
    if overview:
        translated = tmap.get(overview["id"], "")
        units = re.compile(r"\b(?:kWh|kW|km|mm|cm|kg|Nm|PS|BHP|cc|IDC|ISO|VDA)\b", re.I)
        # Overview must not silently fall back to main-language speech or drop
        # a technical unit while preserving its bare number.
        if translated and _keeps_numbers(overview["text"], translated) and sorted(x.casefold() for x in units.findall(overview["text"])) == sorted(x.casefold() for x in units.findall(translated)):
            overview["text"] = translated
        else:
            overview["unverified"] = True
            overview["translation_issue"] = "Overview translation missing or changed a quantity/unit; review before recording."
            emit(overview["translation_issue"])
    if kept:
        emit(f"{kept} line(s) kept in the main language: the translation changed a number, and only registry figures may be spoken.")
    out["intake_q1"], out["intake_q2"] = t.intake_q1 or out["intake_q1"], t.intake_q2 or out["intake_q2"]
    if missing:
        emit(f"{missing} line(s) came back untranslated — kept in the main language.")
    store.write_json(demo_id, script_path(lang), out)
    store.log(demo_id, "translate", {"language": lang, "missing": missing, "kept_source": kept})
    return out


# ---------- the deck's on-screen text (titles, callouts) per extra language ----------

class TCallout(BaseModel):
    id: str
    text: str


class TSlide(BaseModel):
    id: str
    title: str
    callouts: list[TCallout] = Field(default_factory=list)


class TDeck(BaseModel):
    slides: list[TSlide]


def deck_path(lang: str) -> str:
    return f"deck.{lang}.json"


def translate_deck(demo_id: str, lang: str, emit) -> dict | None:
    """Slide titles and callout text in the extra language → deck.<lang>.json (an overlay by id; positions and pictures
    never change with language). A callout whose translation changes a figure keeps the source text."""
    deck = store.read_json(demo_id, "deck.json") or {}
    if not deck.get("slides"):
        return None
    payload = {"slides": [{"id": s["id"], "title": s.get("title", ""), "callouts": [{"id": c["id"], "text": c["text"]} for c in s.get("callouts", [])]} for s in deck["slides"]]}
    key = store.digest(json.dumps(payload, sort_keys=True))
    prev = store.read_json(demo_id, deck_path(lang))
    if prev and prev.get("source_digest") == key:
        return prev
    if config.MOCK_LLM:
        out = {"source_digest": key, "slides": [{"id": s["id"], "title": f"[{lang}] " + s["title"], "callouts": [{"id": c["id"], "text": f"[{lang}] " + c["text"]} for c in s["callouts"]]} for s in payload["slides"]]}
        store.write_json(demo_id, deck_path(lang), out)
        return out
    demo = store.load(demo_id)
    product = (store.read_json(demo_id, "understanding.json") or {}).get("product", {}).get("name") or demo["name"]
    emit(f"Translating slide titles and callouts into {LANGUAGES.get(lang, lang)}…")
    prev_stage = usage.current_stage.get()
    usage.current_stage.set("translate")
    try:
        t = claude.structured(TRANSLATE_SYSTEM.format(product=product, language=language_instruction(lang)) + " Titles stay ≤ 6 words and callouts ≤ 8 words.",
                              json.dumps(payload, ensure_ascii=False), TDeck, max_tokens=8000, soft=True, effort="low", timeout=180.0, model=config.CLAUDE_LITE_MODEL)
    finally:
        usage.current_stage.set(prev_stage)
    tmap = {s.id: s for s in t.slides}
    kept = 0
    slides = []
    for s in payload["slides"]:
        ts = tmap.get(s["id"])
        cmap = {c.id: c.text for c in (ts.callouts if ts else [])}
        cs = []
        for c in s["callouts"]:
            tt = cmap.get(c["id"], "")
            if tt and _keeps_numbers(c["text"], tt):
                cs.append({"id": c["id"], "text": tt})
            else:
                kept += bool(tt)
                cs.append({"id": c["id"], "text": c["text"]})
        slides.append({"id": s["id"], "title": (ts.title if ts and ts.title.strip() else s["title"]), "callouts": cs})
    if kept:
        emit(f"{kept} callout(s) kept in the main language: the translation changed a number.")
    out = {"source_digest": key, "slides": slides}
    store.write_json(demo_id, deck_path(lang), out)
    return out
