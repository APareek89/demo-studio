"""Visual alignment — the picture on screen must show what the guide is talking about.

Runs after the script is written. Three passes:
1. Rules (conservative): each line is matched to the catalogue of tagged images/shots by DISTINCTIVE subject words —
   the parts Gemini saw in an image (gear lever, airbag, panoramic roof) versus the words in the line. Words that
   appear in many pictures (front, blue, view, drive) carry no weight. A proposal needs at least one distinctive hit.
2. Model (one cheap Haiku call): sees every line with its current picture and the rules' proposal, and decides —
   keep, take the proposal, or pick another — with a one-line reason. This is where "the line is about the
   gearbox, show the gear close-up" judgement lives.
3. Coverage guardrail: an uploaded picture with a distinctive subject that some line clearly mentions is shown at
   least once.
Every decision is written to logs/<ts>-visuals.json and the run log, so you can see why each picture was chosen."""
from __future__ import annotations

import json
import re

from pydantic import BaseModel, Field

from .. import config, store
from ..llm import claude

STOP = set("the a an and or of to in on at for with by from as is are was were be been it its this that these those you your we our they their he she i me my "
           "so if then than but not no yes can will would could should may might do does did done have has had into onto over under about across after before "
           "one two three four five six seven eight nine ten first second third also just only very more most less least much many any all some every each per "
           "here there where when what which who whom whose how why let's lets get got go going come came make made take took see seen show shown look looked "
           "like want need say said tell told ask asked give gave keep kept turn turned start stop up down out off back again still even now day days week weeks "
           "km kms kilometre kilometres kilometer kilometers hour hours minute minutes rs rupee rupees lakh lakhs percent view shot close closeup image picture "
           "vehicle car scooter bike product model variant brochure page front rear side left right top high low angle detail lifestyle blue red black white "
           "colour color new".split())

# feature-level synonyms only (generic words like front/back/drive are deliberately absent)
SYNONYMS = {"gearbox": ["gear", "shifter", "transmission", "dct", "manual", "automatic", "paddle", "lever"], "gear": ["gearbox", "shifter", "transmission", "dct", "lever"],
            "transmission": ["gearbox", "gear", "dct", "shifter"], "dct": ["gearbox", "gear", "transmission", "automatic"], "shift": ["gearbox", "gear", "shifter", "lever"], "paddle": ["paddle", "shifter"],
            "battery": ["charger", "charging", "pack", "kwh"], "charger": ["charging", "socket", "plug", "battery"], "charging": ["charger", "socket", "plug", "battery"], "range": ["battery"],
            "seat": ["upholstery", "cabin", "interior", "legroom"], "interior": ["cabin", "seat", "dashboard", "console", "upholstery"], "cabin": ["interior", "seat", "dashboard", "upholstery"],
            "display": ["screen", "cluster", "infotainment", "tft", "touchscreen"], "screen": ["display", "cluster", "infotainment", "touchscreen"], "infotainment": ["display", "screen", "touchscreen"],
            "airbag": ["airbags", "curtain"], "safety": ["airbag", "airbags", "adas", "abs", "sensor", "camera"], "adas": ["safety", "sensor", "camera", "cruise"],
            "boot": ["luggage", "storage", "underseat"], "storage": ["boot", "luggage", "underseat"], "luggage": ["boot", "storage"], "underseat": ["boot", "storage"],
            "wheel": ["alloy", "tyre", "rim"], "alloy": ["wheel", "rim"], "tyre": ["wheel"], "roof": ["sunroof", "panoramic"], "sunroof": ["roof", "panoramic"], "panoramic": ["sunroof", "roof"],
            "engine": ["turbo", "motor"], "motor": ["engine", "hub"], "headlamp": ["headlight", "drl", "led"], "headlight": ["headlamp", "drl", "led"], "grille": ["bumper", "fascia"],
            "steering": ["wheel", "paddle"], "exhaust": ["muffler", "tailpipe"], "muffler": ["exhaust"], "mirror": ["orvm"]}


def _stem(w: str) -> str:
    return w[:-1] if w.endswith("s") and len(w) > 4 and not w.endswith("ss") else w


def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z][a-z0-9\-]+", (text or "").lower()):
        if w in STOP or len(w) < 3:
            continue
        out.add(_stem(w))
    return out


def _expand(tokens: set[str]) -> set[str]:
    out = set(tokens)
    for t in tokens:
        for s in SYNONYMS.get(t, []):
            out.add(_stem(s))
    return out


def catalogue(demo_id: str, und: dict, demo: dict) -> list[dict]:
    items = []
    for i in und.get("images", []):
        if not store.visual_allowed(demo, i.get("source_id", "")):
            continue
        parts = [p for p in (i.get("parts") or []) if isinstance(p, str)]
        items.append({"ref": i["id"], "kind": "image", "strong": _tokens(" ".join(parts)), "weak": _tokens(i.get("description", "")), "quality": i.get("quality", 3),
                      "label": f"{i['id']} · {i.get('angle', '')} · {i.get('description', '')}", "parts": parts})
    for s in und.get("shots", []):
        if not store.visual_allowed(demo, s.get("source_id", "")):
            continue
        items.append({"ref": s["id"], "kind": "shot", "strong": _tokens(s.get("part", "")), "weak": _tokens(s.get("description", "")), "quality": s.get("quality", 3),
                      "label": f"{s['id']} · {s.get('start', 0):.0f}–{s.get('end', 0):.0f}s · {s.get('part', '')} · {s.get('description', '')}", "parts": [s.get("part", "")]})
    # distinctiveness: a word that shows up in a third or more of the pictures says nothing about which one to pick
    n = max(1, len(items))
    df: dict[str, int] = {}
    for it in items:
        for t in it["strong"] | it["weak"]:
            df[t] = df.get(t, 0) + 1
    for it in items:
        it["distinct"] = {t for t in it["strong"] | it["weak"] if df.get(t, 0) <= max(1, int(0.34 * n))}
    return items


def _score(line_tokens: set[str], item: dict) -> tuple[float, list[str]]:
    hits = []
    score = 0.0
    for t in line_tokens:
        if t in item["strong"] and t in item["distinct"]:
            score += 3.0; hits.append(t)
        elif t in item["weak"] and t in item["distinct"]:
            score += 1.0; hits.append(t)
        elif t in item["strong"]:
            score += 0.3
    return score, sorted(set(hits))


class Assignment(BaseModel):
    line_id: str
    visual: str = Field(description="a ref from the catalogue, 'keep' for the current picture, or 'none' if nothing fits")
    reason: str = Field(description="one short sentence: why this picture matches what is being said")


class VisualsOut(BaseModel):
    assignments: list[Assignment]


MODEL_SYSTEM = """You are the picture editor for a spoken product demo. For every line you get the text, the segment it sits in,
the picture currently assigned, and a rule-based proposal (with the words that matched). The catalogue lists every picture
with what is visible in it. Decide, per line, which picture should be on screen while that line is spoken:
- The thing being talked about wins: a line about the gearbox shows the gear lever, a line about airbags shows the airbag
  cut-away, a line about the roof shows the roof. A generic beauty shot is right for generic lines (greeting, framing, closing).
- Take the proposal when it names the part in the line; keep the current picture when the proposal is weaker than it;
  choose another catalogue picture when both miss. Never pick a picture that contradicts the line (interior shot for
  exterior styling, and so on).
- Variety: avoid more than two consecutive lines on the same picture when a fitting alternative exists.
Return one assignment for EVERY line id you were given. Use only refs from the catalogue."""


def align(demo_id: str, script: dict, und: dict, emit=lambda m: None) -> dict:
    demo = store.load(demo_id)
    cat = catalogue(demo_id, und, demo)
    if not cat:
        return script
    by_ref = {c["ref"]: c for c in cat}
    rows: list[dict] = []  # per line working record
    for seg in script.get("segments", []):
        for ln in seg.get("lines", []) + seg.get("deeper", []):
            lt = _expand(_tokens(ln.get("text", "")))
            cur = (ln.get("visual") or {}).get("ref")
            scored = sorted(((*_score(lt, c), c["ref"]) for c in cat), key=lambda x: -x[0])
            best_score, best_hits, best_ref = scored[0]
            cur_score, cur_hits = _score(lt, by_ref[cur]) if cur in by_ref else (0.0, [])
            proposal = best_ref if best_score >= 3.0 and best_ref != cur and best_score >= cur_score + 3.0 else None
            rows.append({"seg": seg, "ln": ln, "cur": cur, "cur_hits": cur_hits, "proposal": proposal, "hits": best_hits, "score": best_score, "deeper": ln in seg.get("deeper", [])})
    changes: list[dict] = []
    model_notes: list[dict] = []
    decided = False
    if not config.MOCK_LLM:
        try:
            payload = {"catalogue": [{"ref": c["ref"], "kind": c["kind"], "shows": c["label"], "parts": c["parts"]} for c in cat],
                       "lines": [{"line_id": r["ln"]["id"], "segment": f"{r['seg'].get('title')} ({r['seg'].get('topic')})", "text": r["ln"].get("text", ""), "current": r["cur"],
                                  "proposal": r["proposal"], "proposal_matches": r["hits"] if r["proposal"] else []} for r in rows]}
            out = claude.structured(MODEL_SYSTEM, json.dumps(payload, ensure_ascii=False), VisualsOut, max_tokens=6000, soft=True)
            byid = {a.line_id: a for a in out.assignments}
            for r in rows:
                a = byid.get(r["ln"]["id"])
                if not a:
                    continue
                choice = r["cur"] if a.visual in ("keep", "", None) else (None if a.visual == "none" else a.visual)
                if choice and choice not in by_ref:
                    continue
                model_notes.append({"line_id": r["ln"]["id"], "visual": choice or "none", "reason": a.reason[:180]})
                if choice != r["cur"]:
                    changes.append({"line_id": r["ln"]["id"], "from": r["cur"], "to": choice, "pass": "model", "why": a.reason[:180]})
                    r["ln"]["visual"] = {"ref": choice, "focus": (r["ln"].get("visual") or {}).get("focus", "")} if choice else None
            decided = True
        except Exception as e:
            emit(f"Picture editor model skipped ({str(e)[:80]}) — rule proposals applied instead.")
    if not decided:
        for r in rows:
            if r["proposal"] and not r["cur_hits"]:
                changes.append({"line_id": r["ln"]["id"], "from": r["cur"], "to": r["proposal"], "pass": "rules", "why": f"line mentions {', '.join(r['hits'][:4])}; {by_ref[r['proposal']]['label'][:100]}"})
                r["ln"]["visual"] = {"ref": r["proposal"], "focus": (r["ln"].get("visual") or {}).get("focus", "")}
    # coverage guardrail — an uploaded picture with a distinctive subject some line clearly mentions is shown at least once
    used = {(r["ln"].get("visual") or {}).get("ref") for r in rows}
    for c in cat:
        if c["ref"] in used or (c.get("quality") or 3) < 3 or c["kind"] != "image" or not (c["strong"] & c["distinct"]):
            continue
        best = None
        for r in rows:
            if r["deeper"]:
                continue
            sc, hits = _score(_expand(_tokens(r["ln"].get("text", ""))), c)
            if sc >= 3.0 and (best is None or sc > best[0]):
                best = (sc, r, hits)
        if best:
            sc, r, hits = best
            changes.append({"line_id": r["ln"]["id"], "from": (r["ln"].get("visual") or {}).get("ref"), "to": c["ref"], "pass": "coverage", "why": f"uploaded picture of {', '.join(c['parts'][:3]) or c['ref']} was never shown; this line mentions {', '.join(hits[:3])}"})
            r["ln"]["visual"] = {"ref": c["ref"], "focus": (r["ln"].get("visual") or {}).get("focus", "")}
            used.add(c["ref"])
    store.log(demo_id, "visuals", {"changes": changes, "model": model_notes, "catalogue": [c["label"] for c in cat], "unused_after": [c["ref"] for c in cat if c["ref"] not in used],
                                   "proposals": [{"line_id": r["ln"]["id"], "proposal": r["proposal"], "hits": r["hits"]} for r in rows if r["proposal"]]})
    if changes:
        emit(f"Pictures aligned to the words: {len(changes)} line(s) now show the part being described" + (f"; {sum(1 for c in changes if c['pass'] == 'coverage')} uploaded picture(s) rescued from never being shown" if any(c["pass"] == "coverage" for c in changes) else "") + ".")
    else:
        emit("Pictures already match what is said on every line.")
    return script



def build_map(und: dict, demo: dict) -> dict:
    """fact id → best picture refs (distinctive-subject match between the fact's claim/value and what each picture shows).
    Built at configure; used by the author, the runtime batches and the answers so the screen matches the words."""
    cat = catalogue("", und, demo)
    out = {}
    for f in und.get("facts", []):
        lt = _expand(_tokens(f"{f.get('claim', '')} {f.get('value', '')} {f.get('kind', '')}"))
        scored = sorted(((*_score(lt, c), c["ref"]) for c in cat), key=lambda x: -x[0])
        refs = [r for sc, hits, r in scored if sc >= 3.0][:3]
        if refs:
            out[f["id"]] = refs
    return out


def for_facts(und: dict, fact_ids: list[str]) -> str | None:
    m = und.get("image_map") or {}
    for fid in fact_ids or []:
        if m.get(fid):
            return m[fid][0]
    return None