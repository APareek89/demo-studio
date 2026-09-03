"""Stage 2 — Plan.  Claude decides what the demo should be: decision frame, takeaway, USPs,
the standard intro + outcome-first opening, proof blocks, establish, advance."""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from .principles import CUSTOMER_STATES, PRINCIPLES, PROOF_BLOCK, language_instruction

PLAN_SYSTEM = """You are the product-demo planner. You turn a fact registry and a set of visuals into the plan for a
voice-led, interruptible demo that a prospective buyer watches on the brand's website. The demo is a
SALES conversation built to close on the next evidence-producing step, not a product tour.

{principles}

{states}

Structure you must produce (this is the standard shape every demo follows):
- decision_frame (P01), takeaway, primary_outcome + ≤2 supporting_outcomes (P05), 3-5 usps tied to facts.
- segments, in this order and with these roles:
  1. role=intro — "Frame": the STANDARD OPENING, always played first, unchanged: the decision frame, the takeaway,
     what the demo will prove, permission to proceed. ~45-60 seconds. No features yet.
  2. role=outcome — "Act": the desired end state shown FIRST (P04), in the buyer's terms, with the best visual.
     Together intro + outcome are the fixed first 1-2 minutes.
  3. 3-6 × role=proof — "Map" blocks, one customer outcome each, each covering ≥1 USP or concern; say/show/translate/confirm.
  4. role=establish — assumptions, written terms (warranty/service/support), the truth split, do_not_recommend_if.
  The runtime planner picks and orders the proof blocks per buyer, so each must stand alone.
- state_questions: the one follow-up question for an unknown buyer, a stated want, a stated need.
- advance (P10): the next action naming a CTA label. do_not_recommend_if (P09).
- A segment may only use facts that exist. If a concern has no facts, plan the segment to say so honestly — never invent.
- Every segment needs a visual (video shots quality ≥3 preferred, else images); missing visuals go to visual_gaps.
- CTAs: 2-3 that fit the product and the brand site; mark one primary; the advance must reference one of them.
- Voice: a persona matching the brand profile — warm, direct, honest, never salesy. Voices: Sulafat (warm), Aoede (breezy),
  Leda (youthful), Despina (smooth), Kore (firm), Achernar (soft), Zephyr (bright).
- intake.q1 = name + ONE open high-yield question (for an unknown buyer this is the "what would have to improve" question).
{language}
Return exactly the schema."""


def run(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        raise RuntimeError("Nothing to plan from — read the sources first")
    prev = store.read_json(demo_id, "plan.json")
    demo = store.load(demo_id)
    emit("Planning the pitch: decision frame, outcome, proof blocks…")
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}·{f.get('truth','stated')}] {f['claim']}: {f['value']}" + (f" ({f['conditions']})" if f.get("conditions") else "") for f in und["facts"] if f.get("approved", True))
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in und["shots"])
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(i['parts'])} · {i['description']}" for i in und["images"])
    unk_txt = "\n".join(f"{u['id']} {u['question']}" for u in und["unknowns"] if u.get("status") == "open")
    content = f"""PRODUCT: {json.dumps(und['product'])}
BRAND PROFILE: {json.dumps(und['brand'])}
PRODUCT URL: {demo.get('product', {}).get('url', '')}

FACT REGISTRY ({len(und['facts'])}):
{facts_txt or '(empty)'}

OPEN UNKNOWNS:
{unk_txt or '(none)'}

VIDEO SHOTS ({len(und['shots'])}):
{shots_txt or '(none)'}

IMAGES ({len(und['images'])}):
{imgs_txt or '(none)'}
"""
    if prev:
        content += f"\nPREVIOUS PLAN (keep what still works; change only what the instruction asks):\n{json.dumps(prev)[:24000]}\n"
    if instruction:
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    sys = PLAN_SYSTEM.format(principles=PRINCIPLES, states=CUSTOMER_STATES, language=language_instruction(demo.get("settings", {}).get("language", "en-IN")))
    try:
        plan = claude.structured(sys, content, schemas.Plan, max_tokens=20000)
    except Exception as e:
        raise RuntimeError(f"Planning failed: {claude.describe_error(e)}") from e

    fact_ids = {f["id"] for f in und["facts"]}
    vis_ids = {s["id"] for s in und["shots"]} | {i["id"] for i in und["images"]}
    p = plan.model_dump()
    usp_ids = {u["id"] for u in p["usps"]}
    for u in p["usps"]:
        u["fact_ids"] = [x for x in u["fact_ids"] if x in fact_ids]
    for seg in p["segments"]:
        seg["fact_ids"] = [x for x in seg["fact_ids"] if x in fact_ids]
        seg["visual_refs"] = [x for x in seg["visual_refs"] if x in vis_ids]
        seg["usp_ids"] = [x for x in seg.get("usp_ids", []) if x in usp_ids]
    for c in p["concerns"]:
        c["fact_ids"] = [x for x in c["fact_ids"] if x in fact_ids]
    # structural guarantees: exactly one intro first, one outcome second, one establish last
    roles = [s["role"] for s in p["segments"]]
    if "intro" not in roles and p["segments"]:
        p["segments"][0]["role"] = "intro"
    if "outcome" not in roles and len(p["segments"]) > 1:
        p["segments"][1]["role"] = "outcome"
    order = {"intro": 0, "outcome": 1, "proof": 2, "establish": 3}
    p["segments"].sort(key=lambda s: order.get(s["role"], 2))
    p["supporting_outcomes"] = p["supporting_outcomes"][:2]
    if prev and instruction:
        low = instruction.lower()
        if "cta" not in low and "button" not in low and "call to action" not in low:
            p["ctas"] = prev.get("ctas", p["ctas"])
        if "voice" not in low and "persona" not in low and "tone" not in low:
            p["voice"] = prev.get("voice", p["voice"])
    if not p["ctas"]:
        p["ctas"] = [{"id": "contact", "label": "Talk to us", "kind": "contact", "url": "", "primary": True, "when": "always"}]
    store.write_json(demo_id, "plan.json", p)
    store.log(demo_id, "plan", {"segments": [(s["id"], s["role"]) for s in p["segments"]], "usps": [u["name"] for u in p["usps"]], "ctas": [c["label"] for c in p["ctas"]]})
    emit(f"Plan: “{p['takeaway'][:80]}” — {len(p['segments'])} segments ({sum(1 for s in p['segments'] if s['role']=='proof')} proof blocks), {len(p['usps'])} USPs, persona “{p['voice']['persona_name']}”.")
    return p
