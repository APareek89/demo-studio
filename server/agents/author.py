"""Stage 3 — Author. Claude writes grounded, conversational batches of at most twenty seconds."""
from __future__ import annotations

import json
import re

from .. import schemas, store
from ..llm import claude
from . import speech_style, visuals
from .principles import PITCH_SHAPE, PRINCIPLES, PROOF_BLOCK, SIGNPOSTS, audience_instruction, fact_context, language_instruction

AUTHOR_SYSTEM = """You write the spoken script for a product demo delivered by a voice guide. The customer can interrupt at any
moment, so every line and every segment must stand alone (no "as I said").

{principles}

{proof_block}

Hard rules:
1. GROUNDING (G2). Every sentence stating a spec, number, price, offer, policy or capability cites its fact ids in
   fact_ids and never goes beyond them. A figure without a fact id is rejected by a validator; an existing id does not
   prove an added benefit. Keep truth kinds distinct (G4): ordinary stated specifications stay stated; reserve
   certification language for explicit certified results with their basis. Name estimates, marketing and written
   terms where relevant, without a ritual evidence label on every line.
2. HONESTY. Where the registry is silent, say so in the persona's voice and say where it gets settled ("boot litres
   aren't in this brochure — one to check in person"). The establish segment DECLARES the top open questions; never
   paper over a gap.
3. VISUALS (G5). Every line binds to the visual that literally shows what it says (shot id or image id); 'focus' is a
   2-5 word on-screen label. When the subject changes, the picture changes.
4. THE FLOW AND ITS BUDGETS (hard limits, validator-checked; one segment = one ≤20-second batch):
   Aim for one natural ten-to-twenty-second thought, usually 19-38 words across the batch. Do not pad a short useful line,
   write sentence fragments, or recite a list. This reusable script knows no individual customer: never assign them a
   commute distance, budget, location or household. Plans, personas and earlier scripts are not customer testimony.
   - intake_q1 = the greeting + ONE context choice from the plan, polished: warm, names brand and product, easy to decline.
     This is the only intake question. Return intake_q2 as an empty string for schema compatibility.
   - intro (1-2 segments, ≤ 38 words each): the quick overview — who it's for and the supported experience or choice. NO greeting,
     no self-introduction (already done in intake), no spec list, no decision frame.
   - outcome (≤ 38 words): the three things to remember — the plan's three USPs, plainly; the customer can steer the order.
     Say this as an invitation, not another intake question.
   - proof (4-6 segments, ≤ 38 words each): NOTICE one thing → the picture SHOWS it → RELEVANCE: the choice it informs
     or a useful fit-check. Explain a customer benefit only when the cited evidence establishes it; a specification
     need not become a promised performance, safety or practical outcome →
     CHECK: one short question in `checkin` (never two). Technical detail goes to 2-3 `deeper` lines.
   - features (≤ 40 words): one sentence per feature, no numbers unless decisive; invite questions in `checkin`.
   - establish (≤ 36 words): variant + written terms in one line each, then the top open questions declared honestly.
   - closing (2 lines, ≤ 45 words total): FIT SUMMARY — "the strongest fit is … and the one thing we should still verify
     is …" (the plan's decision_frame, in everyday nouns) — then the next step naming the CTA label.
   Signposts, varied, in the persona's voice: {signposts}
   card='contrast' where today meets after; 'price' only in a price block; 'facts' at most once; 'summary' in the closing.
   Every real question goes in `checkin`, where the player explicitly waits for an answer. Narration and closing lines
   contain no questions. Do not duplicate a checkin in a line. `step=confirm` is retained only for old script compatibility.
5. VOICE (G1). Spoken, not written: contractions, short clauses, numbers as words where natural, no markdown. Concrete
   nouns; no "smart/convenient/economical". Never more than two facts in a row without their supported relevance.
6. MAKE THE PRODUCT WORTH EXPLORING. Lead with the strongest supported reason to care, then show the actual feature.
   Choose a vivid, concrete observation over generic praise. A good opening makes the buyer want to see the cabin or
   try a feature; it does not recite the vehicle's dimensions or say every feature is exciting. Show standout features
   early; keep technical mechanics for a requested deeper answer. A transmission type alone never proves smooth,
   imperceptible or jerk-free shifts. A safety feature never promises that an accident cannot happen.
7. DELIVERY. Be a helpful, cheerful, attentive guide: gentle enthusiasm, a reassuring cadence for limitations, no
   theatrical excitement, repeated superlatives or forced fillers. Use punctuation for natural pauses. Set each line's
   delivery metadata to tone warm/upbeat/calm/reassuring and optional pace 0.9–1.08. Never put [emotion] or SSML in text.
   Write overview as a separate, self-contained 23–28 word thought for Explore's 10–15 second introduction: a compelling
   supported feature/benefit first, with its variant qualification and citations. No greeting, question or dimensions.
   Do not duplicate overview verbatim in the regular segments; it is an alternative opening while the route is planned.
{audience}
{language}"""


def _verified_script(demo_id: str, demo: dict) -> schemas.ScriptOut | None:
    """Load a human-reviewed script bundle when both reasoning providers are unavailable."""
    manifests = [s for s in demo.get("sources", []) if s.get("kind") == "text"
                 and s.get("name", "").lower() == "verified-script.json.md"]
    if not manifests:
        return None
    raw = store.path(demo_id, manifests[-1]["path"]).read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return schemas.ScriptOut.model_validate_json(raw)


NUMBERISH = re.compile(r"(\d[\d,\.]*\s*(%|km|kwh|kw|kg|hrs?|hours?|mins?|minutes?|years?|months?|days?|litres?|liters?|gb|mb|tb|mah|w\b|v\b|cc\b|mm|cm|inch|inches|₹|rs\.?|rupees|usd|\$|€)|₹\s*\d|\$\s*\d|\d{2,}|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)(?:\s+|-)?(?:airbags?|stars?|seats?|seaters?|speakers?|colou?r options?|apps?|variants?|years?|months?)\b)", re.I)
CLAIMISH = re.compile(r"\b(warrant|guarantee|certified|rated|fastest|longest|best[- ]in[- ]class|free|discount|offer|included|supports?|compatible|waterproof|ip6\d)\b", re.I)
LIMITS = {"intro": 38, "outcome": 38, "proof": 38, "features": 40, "establish": 36}  # ≤ 20 s per batch at the measured ~1.9 words/s of the recorded voice
WPS = 1.9  # spoken words per second, measured on Sarvam bulbul (Creta run 2026-09-04: 446 words → 240 s); replaced by real audio durations after voicing
CLOSING_LIMIT = 45
ROUTE_LIMIT = 360  # ≈ 3 minutes at the measured ~1.9 words/s: intro + outcome + best 3 proof + features + establish + closing
JARGON = re.compile(r"\b(IDC|kWh|kW|amp|15A|5A|torque|Nm|newton[ -]?met(?:re|er)s?|r/min|RPM|Level\s*[12]|IP6\d|TFT|ABS|CBS|Li-ion|BMS|regen|DCT|IVT|CVT|ADAS|GDi|PS|BHP)\b")
_SHIFT_PROMISE = re.compile(r"\b(?:imperceptible|seamless|jerk[- ]free)\s+(?:gear\s*)?(?:shifts?|changes?)\b|\b(?:won't|will not|cannot|can't)\s+(?:even\s+)?feel\s+(?:the\s+)?(?:gear\s*)?(?:shifts?|changes?)\b", re.I)


def words(t: str) -> int:
    return len(re.findall(r"\S+", t or ""))


def ungrounded(text: str, fact_ids: list[str] | None, allowed: set[str]) -> tuple[list[str], bool]:
    """The one rule every spoken or shown line obeys — script lines, runtime bridges, custom batches, slide callouts:
    keep only the fact ids that exist; if none are left and the text states a figure or claim, it is ungrounded."""
    valid = [x for x in (fact_ids or []) if x in allowed]
    return valid, bool(not valid and (NUMBERISH.search(text or "") or CLAIMISH.search(text or "")))


def validate(script: dict, und: dict, audience: str = "everyday") -> list[str]:
    # A human rejection in Align is a hard boundary: rejected facts must not
    # survive as citations merely because they still exist in the registry.
    fact_ids = {f["id"] for f in und["facts"] if f.get("approved", True)}
    vis = {s["id"]: "shot" for s in und["shots"] if s.get("_allowed", True)} | {i["id"]: "image" for i in und["images"] if i.get("_allowed", True)}
    issues: list[str] = []

    def check(line: dict, where: str):
        prepared = speech_style.prepare(line.get("text", ""), line.get("delivery"))
        if prepared["plain_text"] != line.get("text", "").strip():
            issues.append(f"{where}: removed unsupported delivery markup; keep delivery metadata separate from spoken words")
            line["text"] = prepared["plain_text"]
        if line.get("delivery"):
            line["delivery"] = speech_style.normalize(line["delivery"])
        line["fact_ids"], bad = ungrounded(line.get("text", ""), line.get("fact_ids"), fact_ids)
        cited = [f for f in und["facts"] if f["id"] in line["fact_ids"]]
        evidence = " ".join(str(f.get(k, "")) for f in cited for k in ("claim", "value", "conditions")) + " " + " ".join(str((f.get("source") or {}).get("quote", "")) for f in cited)
        if _SHIFT_PROMISE.search(line.get("text", "")) and not _SHIFT_PROMISE.search(evidence):
            issues.append(f"{where}: transmission evidence does not establish an imperceptible or seamless shift outcome")
            bad = True
        v = line.get("visual") or {"kind": "none", "ref": "", "focus": ""}
        if v.get("ref") and v["ref"] not in vis:
            issues.append(f"{where}: visual '{v['ref']}' does not exist")
            v["ref"], v["kind"] = "", "none"
        elif v.get("ref"):
            v["kind"] = vis[v["ref"]]
        line["visual"] = v
        if bad:
            if not line["fact_ids"]:
                issues.append(f"{where}: states a figure or claim without a fact id — “{line.get('text', '')[:90]}”")
            line["unverified"] = True
        else:
            line["unverified"] = False

    for seg in script["segments"]:
        checkin = (seg.get("checkin") or "").strip()
        # Checkins have no citation field. Moving a claim out of a line cannot
        # exempt it from grounding: a question-only turn must remain claim-free.
        if NUMBERISH.search(checkin) or CLAIMISH.search(checkin):
            issues.append(f"{seg['id']}: checkin contains a figure or claim without citations — ask only about relevance, and keep cited facts in narration")
            seg["checkin"], seg["checkin_audio"] = "", None
        for n, ln in enumerate(seg["lines"], 1):
            check(ln, f"{seg['id']} line {n}")
            if re.search(r"[?？]", ln.get("text", "")) or ln.get("step") == "confirm":
                issues.append(f"{seg['id']} line {n}: move the question to checkin so the player explicitly waits; narration must not ask it again")
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
                    issues.append(f"{seg['id']}: jargon '{m.group(0)}' in the main narration — move the complete technical quantity to deeper; never keep a number while dropping its unit")
                    break
    intro_words = sum(words(l["text"]) for s in script["segments"] if s.get("role") in ("intro", "outcome") for l in s["lines"])
    if intro_words > 115:
        issues.append(f"opening (intro + outcome) is {intro_words} words; keep it under 115 (~45 s)")
    for n, ln in enumerate(script.get("closing", []), 1):
        check(ln, f"closing {n}")
        if re.search(r"[?？]", ln.get("text", "")) or ln.get("step") == "confirm":
            issues.append(f"closing line {n}: a question needs an explicit checkin; close with the next action instead")
    closing_words = sum(words(l["text"]) for l in script.get("closing", []))
    if closing_words > CLOSING_LIMIT:
        issues.append(f"closing is {closing_words} words, limit {CLOSING_LIMIT}")
    by_role = {}
    for s in script["segments"]:
        by_role.setdefault(s.get("role", "proof"), []).append(sum(words(l["text"]) for l in s["lines"]))
    route = sum(by_role.get("intro", [0])) + sum(by_role.get("outcome", [0])) + sum(sorted(by_role.get("proof", []), reverse=True)[:3]) + sum(by_role.get("features", [0])) + sum(by_role.get("establish", [0])) + closing_words
    if route > ROUTE_LIMIT:
        issues.append(f"a full route would run {route} words (~{route/150:.1f} min); keep it under {ROUTE_LIMIT} (3 minutes) — cut, don't compress")
    overview = script.get("overview") or script.get("runtime_overview")
    if overview:
        check(overview, "Explore overview")
        if not 23 <= words(overview.get("text", "")) <= 28:
            issues.append("Explore overview: use 23–28 words for the 10–15 second opening")
        if not overview.get("fact_ids") or re.search(r"[?？]", overview.get("text", "")):
            issues.append("Explore overview needs cited evidence and must not ask a question")
            overview["unverified"] = True
        if audience == "everyday" and JARGON.search(overview.get("text", "")):
            issues.append("Explore overview: move technical jargon to deeper detail")
    return issues


def _audio_seconds(demo_id: str | None, rel: str | None) -> float | None:
    if not demo_id or not rel:
        return None
    try:
        import wave
        with wave.open(str(store.path(demo_id, rel)), "rb") as w:
            return round(w.getnframes() / float(w.getframerate() or 1), 2)
    except Exception:
        return None


def timeline(script: dict, demo_id: str | None = None) -> dict:
    """Per-line start/duration in seconds (estimated from words, exact from the audio when it exists) and per-batch totals.
    Stored on the script so the Align page and the bundle can show 'at 0:42 the guide says … and shows im04'."""
    t = 0.0
    batches = []
    for seg in script.get("segments", []):
        b0 = t
        for ln in seg.get("lines", []):
            if ln.get("unverified"):
                continue
            dur = _audio_seconds(demo_id, ln.get("audio")) or round(max(1.0, words(ln.get("text", "")) / WPS), 1)
            ln["start"], ln["duration"], ln["exact"] = round(t, 1), dur, bool(_audio_seconds(demo_id, ln.get("audio")))
            t += dur
        spoken = round(t - b0, 1)  # the batch itself: what the guide says before the pause point
        if seg.get("checkin"):
            dur = _audio_seconds(demo_id, seg.get("checkin_audio")) or round(max(1.0, words(seg["checkin"]) / WPS), 1)
            seg["checkin_start"], seg["checkin_duration"] = round(t, 1), dur
            t += dur
        seg["start"], seg["duration"], seg["spoken"] = round(b0, 1), round(t - b0, 1), spoken
        batches.append({"id": seg["id"], "title": seg.get("title"), "role": seg.get("role"), "start": round(b0, 1), "duration": round(t - b0, 1), "spoken": spoken, "checkin": round(t - b0 - spoken, 1), "over_20s": spoken > 20.5})
    for ln in script.get("closing", []):
        dur = _audio_seconds(demo_id, ln.get("audio")) or round(max(1.0, words(ln.get("text", "")) / WPS), 1)
        ln["start"], ln["duration"] = round(t, 1), dur
        t += dur
    script["timeline"] = {"total_seconds": round(t, 1), "batches": batches, "exact": any(l.get("exact") for s in script.get("segments", []) for l in s.get("lines", []))}
    return script["timeline"]


def split_long_batches(script: dict) -> int:
    """Hard guarantee for the 20-second rule: a segment whose spoken lines exceed its word budget is split at line
    boundaries into '… (cont.)' batches; the check-in and deeper lines stay with the last piece. Returns the number of
    new batches created."""
    out, created = [], 0
    for seg in script.get("segments", []):
        limit = LIMITS.get(seg.get("role", "proof"), 50)
        lines = [l for l in seg.get("lines", []) if not l.get("unverified")]
        if sum(words(l.get("text", "")) for l in lines) <= limit + 4 or len(lines) < 2:
            out.append(seg)
            continue
        chunks, cur, n = [], [], 0
        for l in lines:
            w = words(l.get("text", ""))
            if cur and n + w > limit:
                chunks.append(cur); cur, n = [], 0
            cur.append(l); n += w
        if cur:
            chunks.append(cur)
        held = [l for l in seg.get("lines", []) if l.get("unverified")]
        for k, ch in enumerate(chunks):
            last = k == len(chunks) - 1
            piece = {**seg, "id": seg["id"] if k == 0 else f"{seg['id']}-{k + 1}", "title": seg["title"] if k == 0 else f"{seg['title']} (cont.)",
                     "lines": ch + (held if last else []), "checkin": seg.get("checkin", "") if last else "", "checkin_audio": seg.get("checkin_audio") if last else None,
                     "deeper": seg.get("deeper", []) if last else []}
            out.append(piece)
            created += 0 if k == 0 else 1
    script["segments"] = out
    return created


def _assign_ids(script: dict) -> None:
    overview = script.pop("overview", None)
    if overview:
        overview["id"] = "runtime-overview"
        script["runtime_overview"] = overview
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
    facts_txt = "\n".join(fact_context(f) for f in und["facts"] if f.get("approved", True))
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in und["shots"] if s.get("_allowed", True))
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(visuals.part_names(i))} · {i['description']}" for i in und["images"] if i.get("_allowed", True))
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
        content += f"\nPREVIOUS SCRIPT (revise; keep segment ids, but remove any assumed individual customer circumstances):\n{json.dumps({'segments': prev['segments'], 'closing': prev['closing']})[:40000]}\n"
    if instruction:
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    audience = demo.get("settings", {}).get("audience", "everyday")
    sys = AUTHOR_SYSTEM.format(principles=PRINCIPLES + "\n\n" + PITCH_SHAPE, proof_block=PROOF_BLOCK, signposts=" | ".join(SIGNPOSTS), audience=audience_instruction(audience), language=language_instruction(demo.get("settings", {}).get("language", "en-IN")))
    try:
        out = claude.structured(sys, content, schemas.ScriptOut, max_tokens=40000)
    except Exception as e:
        manifest = _verified_script(demo_id, demo) if claude._provider_unavailable(e) else None
        if not manifest:
            raise RuntimeError(f"Script writing failed: {claude.describe_error(e)}") from e
        emit("Reasoning providers unavailable — using the explicit verified script…")
        out = manifest
    script = out.model_dump()
    script["intake_q2"] = ""
    issues = validate(script, und, audience)
    if issues:
        emit(f"Validator flagged {len(issues)} issue{'s' if len(issues) != 1 else ''} — asking for a grounded rewrite…")
        fix = content + "\n\nYOUR DRAFT:\n" + json.dumps({k: script.get(k) for k in ("overview", "segments", "closing", "intake_q1", "intake_q2")})[:60000]
        fix += "\n\nVALIDATOR ISSUES — fix every one: cite the correct fact ids, or rewrite the line so it makes no unsupported claim (state the gap honestly); shorten where told. Return the full script.\n" + "\n".join("- " + i for i in issues)
        try:
            out2 = claude.structured(sys, fix, schemas.ScriptOut, max_tokens=40000)
            script = out2.model_dump()
            script["intake_q2"] = ""
            issues = validate(script, und, audience)
        except Exception:
            pass
    _assign_ids(script)
    script["issues"] = issues
    script["version"] = (prev.get("version", 0) + 1) if prev else 1
    script["intake_audio"] = {}
    schemas.Script.model_validate(script)
    script = visuals.align(demo_id, script, und, emit)
    n_split = split_long_batches(script)
    if n_split:
        emit(f"{n_split} long batch(es) split at line boundaries so every batch stays under 20 seconds.")
    timeline(script)
    store.write_json(demo_id, "script.json", script)
    n_lines = sum(len(s["lines"]) for s in script["segments"])
    unverified = sum(1 for s in script["segments"] for l in s["lines"] if l.get("unverified"))
    store.log(demo_id, "author", {"segments": len(script["segments"]), "lines": n_lines, "issues": issues})
    emit(f"Script: {len(script['segments'])} segments, {n_lines} lines" + (f", {unverified} held back as unverified; {len(issues)} note(s) on the Facts card." if issues else ", all lines grounded and within pacing limits."))
    return script
