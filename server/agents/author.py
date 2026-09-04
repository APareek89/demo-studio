"""Stage 3 — Author.  Claude writes the segment script; code enforces 'no citation, no claim'
and the pacing rules (standard intro ≤ 2 min, proof blocks ≤ ~150 words)."""
from __future__ import annotations

import json
import re

from .. import schemas, store
from ..llm import claude
from . import visuals
from .principles import PITCH_SHAPE, PRINCIPLES, PROOF_BLOCK, SIGNPOSTS, audience_instruction, language_instruction

AUTHOR_SYSTEM = """You write the spoken script for a product demo delivered by a voice guide. The customer can
interrupt at any moment, so every line must stand alone and every segment must stand alone (no "as I said").

{principles}

{proof_block}

Hard rules:
1. GROUNDING. Every sentence that states a specification, number, price, offer, policy or capability MUST cite
   the fact ids it relies on in fact_ids and must not go beyond what those facts say. A line with a number and no
   fact id will be rejected by a validator. Name the kind of truth (P09): "certified under the IDC cycle",
   "an estimate assuming…", "the written warranty says…".
2. HONESTY. Where the registry is silent, say so in the persona's voice ("the spec sheet doesn't list X, so I won't
   guess — the team can confirm"). Never paper over a gap with a plausible number.
3. VISUALS. Every line binds to one visual: a video shot id (the player seeks to that range) or an image id.
   Choose the visual that literally shows what the line says. 'focus' is a 2-5 word label shown on screen.
4. SHAPE — the whole narration is a 3-minute pitch; the budgets are hard limits checked by a validator:
   - intro: 2-3 lines, step=frame, ≤ 50 words. Opens with a signpost. No features, no numbers except the one that frames the decision.
   - outcome: 2-3 lines, ≤ 55 words — the end state in the buyer's routine ("for a fifteen-kilometre commute that's about a
     week between charges, on the certified figure"), best visual. No check-in on intro/outcome.
   - proof: 3-4 lines, ≤ 55 words — signpost → pain point → the feature that removes it → what it means daily; CONFIRM question in `checkin`.
     A 2-3 line `deeper` layer holds the technical detail (this is where specifications and conditions go).
   - features: 4-6 lines, ≤ 100 words — signpost, then one sentence per feature, no numbers unless decisive; the last line invites questions; checkin = "anything there you'd like me to open up?"
   - establish: 2-3 lines, ≤ 40 words — the honest condition, the written terms in one line, support in one line.
   - closing: 2 lines, ≤ 40 words, step=advance — the next step naming the CTA label; then the offer to answer anything.
   Signposts to use (in the persona's voice, varied): {signposts}
   Use card='contrast' on the line that puts today next to after (P08), 'price' only if the block is about price, 'facts' at most once, 'summary' in the closing. A card shows at most 3 rows.
5. VOICE. Follow the persona and tone exactly. Spoken, not written: contractions, short clauses, numbers as words
   where natural. No markdown, no bullet points, no emojis. Concrete nouns (P07); no "smart/convenient/economical".
   No monologue: never more than two facts in a row without translating what they mean for this person.
6. intake_q1 / intake_q2: the two spoken intake questions from the plan, polished in the persona's voice.
{audience}
{language}"""


NUMBERISH = re.compile(r"(\d[\d,\.]*\s*(%|km|kwh|kw|kg|hrs?|hours?|mins?|minutes?|years?|months?|days?|litres?|liters?|gb|mb|tb|mah|w\b|v\b|cc\b|mm|cm|inch|inches|₹|rs\.?|rupees|usd|\$|€)|₹\s*\d|\$\s*\d|\d{2,})", re.I)
CLAIMISH = re.compile(r"\b(warrant|guarantee|certified|rated|fastest|longest|best[- ]in[- ]class|free|discount|offer|included|supports?|compatible|waterproof|ip6\d)\b", re.I)
LIMITS = {"intro": 55, "outcome": 60, "proof": 60, "features": 110, "establish": 45}
CLOSING_LIMIT = 45
ROUTE_LIMIT = 480  # ≈ 3 minutes at ~150 wpm: intro + outcome + best 3 proof + features + establish + closing
JARGON = re.compile(r"\b(IDC|kWh|kW|amp|15A|5A|torque|Nm|IP6\d|TFT|RPM|ABS|CBS|Li-ion|BMS|regen)\b")


def words(t: str) -> int:
    return len(re.findall(r"\S+", t or ""))


def validate(script: dict, und: dict, audience: str = "everyday") -> list[str]:
    fact_ids = {f["id"] for f in und["facts"]}
    vis = {s["id"]: "shot" for s in und["shots"] if s.get("_allowed", True)} | {i["id"]: "image" for i in und["images"] if i.get("_allowed", True)}
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
        total = sum(words(l["text"]) for l in seg["lines"])
        lim = LIMITS.get(seg.get("role", "proof"), 165)
        if total > lim:
            issues.append(f"{seg['id']} ({seg.get('role')}): {total} words, limit {lim} — shorten (P06)")
        if seg.get("role") in ("proof", "features") and not (seg.get("checkin") or "").strip():
            issues.append(f"{seg['id']}: {seg.get('role')} block needs a CONFIRM question in checkin (P06)")
        if audience == "everyday":
            for l in seg["lines"]:
                m = JARGON.search(l["text"])
                if m:
                    issues.append(f"{seg['id']}: jargon '{m.group(0)}' in the main narration — say it plainly (technical detail belongs in deeper)")
                    break
    intro_words = sum(words(l["text"]) for s in script["segments"] if s.get("role") in ("intro", "outcome") for l in s["lines"])
    if intro_words > 115:
        issues.append(f"opening (intro + outcome) is {intro_words} words; keep it under 115 (~45 s)")
    for n, ln in enumerate(script.get("closing", []), 1):
        check(ln, f"closing {n}")
    closing_words = sum(words(l["text"]) for l in script.get("closing", []))
    if closing_words > CLOSING_LIMIT:
        issues.append(f"closing is {closing_words} words, limit {CLOSING_LIMIT}")
    by_role = {}
    for s in script["segments"]:
        by_role.setdefault(s.get("role", "proof"), []).append(sum(words(l["text"]) for l in s["lines"]))
    route = sum(by_role.get("intro", [0])) + sum(by_role.get("outcome", [0])) + sum(sorted(by_role.get("proof", []), reverse=True)[:3]) + sum(by_role.get("features", [0])) + sum(by_role.get("establish", [0])) + closing_words
    if route > ROUTE_LIMIT:
        issues.append(f"a full route would run {route} words (~{route/150:.1f} min); keep it under {ROUTE_LIMIT} (3 minutes) — cut, don't compress")
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
    demo = store.load(demo_id)
    for s in und["shots"]:
        s["_allowed"] = store.visual_allowed(demo, s["source_id"])
    for i in und["images"]:
        i["_allowed"] = store.visual_allowed(demo, i["source_id"])
    prev = store.read_json(demo_id, "script.json")
    emit("Writing the script…")
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}·{f.get('truth','stated')}] {f['claim']}: {f['value']}" + (f" (condition: {f['conditions']})" if f.get("conditions") else "") for f in und["facts"] if f.get("approved", True))
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in und["shots"] if s.get("_allowed", True))
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(i['parts'])} · {i['description']}" for i in und["images"] if i.get("_allowed", True))
    plan_view = {k: plan.get(k) for k in ("customer_persona", "decision_frame", "takeaway", "primary_outcome", "supporting_outcomes", "concerns", "usps", "segments", "ctas", "voice", "intake", "do_not_recommend_if", "advance")}
    content = f"""PRODUCT: {json.dumps(und['product'])}
BRAND: {json.dumps(und['brand'])}
PLAN: {json.dumps(plan_view)}

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
    audience = demo.get("settings", {}).get("audience", "everyday")
    sys = AUTHOR_SYSTEM.format(principles=PRINCIPLES + "\n\n" + PITCH_SHAPE, proof_block=PROOF_BLOCK, signposts=" | ".join(SIGNPOSTS), audience=audience_instruction(audience), language=language_instruction(demo.get("settings", {}).get("language", "en-IN")))
    try:
        out = claude.structured(sys, content, schemas.ScriptOut, max_tokens=40000)
    except Exception as e:
        raise RuntimeError(f"Script writing failed: {claude.describe_error(e)}") from e
    script = out.model_dump()
    issues = validate(script, und, audience)
    if issues:
        emit(f"Validator flagged {len(issues)} issue{'s' if len(issues) != 1 else ''} — asking for a grounded rewrite…")
        fix = content + "\n\nYOUR DRAFT:\n" + json.dumps({"segments": script["segments"], "closing": script["closing"], "intake_q1": script["intake_q1"], "intake_q2": script["intake_q2"]})[:60000]
        fix += "\n\nVALIDATOR ISSUES — fix every one: cite the correct fact ids, or rewrite the line so it makes no unsupported claim (state the gap honestly); shorten where told. Return the full script.\n" + "\n".join("- " + i for i in issues)
        try:
            out2 = claude.structured(sys, fix, schemas.ScriptOut, max_tokens=40000)
            script = out2.model_dump()
            issues = validate(script, und, audience)
        except Exception:
            pass
    _assign_ids(script)
    script["issues"] = issues
    script["version"] = (prev.get("version", 0) + 1) if prev else 1
    script["intake_audio"] = {}
    schemas.Script.model_validate(script)
    script = visuals.align(demo_id, script, und, emit)
    store.write_json(demo_id, "script.json", script)
    n_lines = sum(len(s["lines"]) for s in script["segments"])
    unverified = sum(1 for s in script["segments"] for l in s["lines"] if l.get("unverified"))
    store.log(demo_id, "author", {"segments": len(script["segments"]), "lines": n_lines, "issues": issues})
    emit(f"Script: {len(script['segments'])} segments, {n_lines} lines" + (f", {unverified} held back as unverified; {len(issues)} note(s) on the Facts card." if issues else ", all lines grounded and within pacing limits."))
    return script
