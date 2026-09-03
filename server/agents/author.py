"""Stage 3 — Author.  Claude writes the segment script; code enforces 'no citation, no claim'."""
from __future__ import annotations

import json
import re

from .. import schemas, store
from ..llm import claude

AUTHOR_SYSTEM = """You write the spoken script for a product demo delivered by a voice guide. The customer can
interrupt at any moment, so every line must stand alone and every segment must stand alone (no "as I said").

Hard rules:
1. GROUNDING. Every sentence that states a specification, number, price, offer, policy or capability MUST cite
   the fact ids it relies on in fact_ids, and must not go beyond what those facts say. A line with a number and no
   fact id will be rejected by a validator. Certified/lab figures must be named as such, with their condition.
2. HONESTY. Where the registry is silent, say so in the persona's voice ("the spec sheet doesn't list X, so I won't
   guess — the team can confirm"). Never paper over a gap with a plausible number.
3. VISUALS. Every line binds to one visual: a video shot id (the player seeks to that range) or an image id.
   Choose the visual that literally shows what the line says. 'focus' is a 2-5 word label shown on screen.
4. SHAPE. Per segment 3-6 lines of 1-2 sentences; a check-in question in the persona's voice (empty for the first
   welcome segment); a 2-3 line 'deeper' layer for "tell me more". 2-3 closing lines that summarise and offer the
   calls to action by name. intake_q1 / intake_q2 are the two spoken intake questions (from the plan, polished).
5. VOICE. Follow the persona and tone exactly. Indian English if the market is India. Spoken, not written:
   contractions, short clauses, numbers as words where natural. No markdown, no bullet points, no emojis.
6. Use the card field to put a fact table on screen: 'price' for the price/variant segment, 'facts' where several
   specs are listed, 'summary' in the closing, else 'none'."""


NUMBERISH = re.compile(r"(\d[\d,\.]*\s*(%|km|kwh|kw|kg|hrs?|hours?|mins?|minutes?|years?|months?|days?|litres?|liters?|gb|mb|tb|mah|w\b|v\b|cc\b|mm|cm|inch|inches|₹|rs\.?|rupees|usd|\$|€)|₹\s*\d|\$\s*\d|\d{2,})", re.I)
CLAIMISH = re.compile(r"\b(warrant|guarantee|certified|rated|fastest|longest|best[- ]in[- ]class|free|discount|offer|included|supports?|compatible|waterproof|ip6\d)\b", re.I)


def validate(script: dict, und: dict) -> list[str]:
    fact_ids = {f["id"] for f in und["facts"]}
    vis = {s["id"]: "shot" for s in und["shots"]} | {i["id"]: "image" for i in und["images"]}
    issues: list[str] = []

    def check(line: dict, where: str):
        line["fact_ids"] = [x for x in line.get("fact_ids", []) if x in fact_ids]
        v = line.get("visual") or {"kind": "none", "ref": "", "focus": ""}
        if v.get("ref") and v["ref"] not in vis:
            issues.append(f"{where}: visual '{v['ref']}' does not exist")
            v["ref"], v["kind"] = "", "none"
        elif v.get("ref"):
            v["kind"] = vis[v["ref"]]
        line["visual"] = v
        t = line.get("text", "")
        if not line["fact_ids"] and (NUMBERISH.search(t) or CLAIMISH.search(t)):
            issues.append(f"{where}: states a figure or claim without a fact id — “{t[:90]}”")
            line["unverified"] = True
        else:
            line["unverified"] = False

    for seg in script["segments"]:
        for n, ln in enumerate(seg["lines"], 1):
            check(ln, f"{seg['id']} line {n}")
        for n, ln in enumerate(seg.get("deeper", []), 1):
            check(ln, f"{seg['id']} deeper {n}")
    for n, ln in enumerate(script.get("closing", []), 1):
        check(ln, f"closing {n}")
    return issues


def _assign_ids(script: dict) -> None:
    for seg in script["segments"]:
        for n, ln in enumerate(seg["lines"], 1):
            ln["id"] = f"{seg['id']}-L{n}"
        for n, ln in enumerate(seg.get("deeper", []), 1):
            ln["id"] = f"{seg['id']}-D{n}"
    for n, ln in enumerate(script.get("closing", []), 1):
        ln["id"] = f"close-L{n}"


def run(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    plan = store.read_json(demo_id, "plan.json")
    if not (und and plan):
        raise RuntimeError("Plan first, then author")
    prev = store.read_json(demo_id, "script.json")
    emit("Writing the script…")
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}] {f['claim']}: {f['value']}" + (f" (condition: {f['conditions']})" if f.get("conditions") else "") for f in und["facts"] if f.get("approved", True))
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in und["shots"])
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(i['parts'])} · {i['description']}" for i in und["images"])
    content = f"""PRODUCT: {json.dumps(und['product'])}
BRAND: {json.dumps(und['brand'])}
PLAN: {json.dumps({k: plan[k] for k in ('customer_persona', 'concerns', 'segments', 'ctas', 'voice', 'intake')})}

FACT REGISTRY — the only allowed source of facts:
{facts_txt or '(empty — every specification must be declared unknown)'}

VIDEO SHOTS:
{shots_txt or '(none)'}

IMAGES:
{imgs_txt or '(none)'}
"""
    if prev and instruction:
        content += f"\nPREVIOUS SCRIPT (revise; keep segment ids):\n{json.dumps({'segments': prev['segments'], 'closing': prev['closing']})[:40000]}\n"
    if instruction:
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    try:
        out = claude.structured(AUTHOR_SYSTEM, content, schemas.ScriptOut, max_tokens=32000)
    except Exception as e:
        raise RuntimeError(f"Script writing failed: {claude.describe_error(e)}") from e
    script = out.model_dump()
    issues = validate(script, und)
    if issues:
        emit(f"Validator flagged {len(issues)} line{'s' if len(issues) != 1 else ''} — asking for a grounded rewrite…")
        fix = content + "\n\nYOUR DRAFT:\n" + json.dumps({"segments": script["segments"], "closing": script["closing"], "intake_q1": script["intake_q1"], "intake_q2": script["intake_q2"]})[:60000]
        fix += "\n\nVALIDATOR ISSUES — fix every one: either cite the correct fact ids, or rewrite the line so it makes no unsupported claim (state the gap honestly). Return the full script.\n" + "\n".join("- " + i for i in issues)
        try:
            out2 = claude.structured(AUTHOR_SYSTEM, fix, schemas.ScriptOut, max_tokens=32000)
            script = out2.model_dump()
            issues = validate(script, und)
        except Exception:
            pass
    _assign_ids(script)
    script["issues"] = issues
    script["version"] = (prev.get("version", 0) + 1) if prev else 1
    script["intake_audio"] = {}
    schemas.Script.model_validate(script)
    store.write_json(demo_id, "script.json", script)
    n_lines = sum(len(s["lines"]) for s in script["segments"])
    store.log(demo_id, "author", {"segments": len(script["segments"]), "lines": n_lines, "issues": issues})
    emit(f"Script: {len(script['segments'])} segments, {n_lines} lines" + (f", {len(issues)} still unverified (excluded from voice, listed in the gap list)." if issues else ", all lines grounded."))
    return script
