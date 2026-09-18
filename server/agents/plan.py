"""Stage 2 — Plan.  Claude decides what the demo should be: decision frame, takeaway, USPs,
the standard intro + outcome-first opening, proof blocks, establish, advance."""
from __future__ import annotations

import json

from .. import config, schemas, store
from . import visuals
from ..llm import claude
from .principles import CUSTOMER_STATES, PITCH_SHAPE, PRINCIPLES, PROOF_BLOCK, audience_instruction, language_instruction

PLAN_SYSTEM = """You are the product-demo planner. You turn a fact registry and a set of visuals into the plan for a
voice-led, interruptible demo a prospective buyer watches on the brand's website. It must feel like a good human
salesperson: greet, offer a choice, overview before detail, then guided discovery — not a spec tour and not an interrogation.

{principles}

{states}

{shape}

{audience}

Produce exactly this:
- intake.q1 = the GREETING + one context choice, in one breath: warm, names the brand and the product, then ONE low-pressure
  question that is easy to decline ("…or shall we just get started?"). ONE question only — never name + something else stacked.
- intake.q2 = empty. There is no second discovery question after intake.
- customer_persona is a general audience description, not a real customer's circumstances. Do not supply a fictional
  distance, budget, family or location for the author to repeat. Unknown personal context stays unknown.
- usps: EXACTLY THREE, each tied to fact ids — one about the daily EXPERIENCE (comfort/cabin/ease), one about PERFORMANCE or
  productivity, one about CONFIDENCE or ownership (safety, warranty, service). These three are the demo's spine.
- decision_frame: written in a buyer's everyday nouns, for the FIT SUMMARY at the END of the demo (never the opening):
  "the strongest fit is … and the thing still to verify is …". takeaway: one memorable plain-language sentence.
- primary_outcome + ≤2 supporting_outcomes: customer end states, not features.
- segments, tagged by role, in this order:
  1-2 × role=intro — the QUICK OVERVIEW (step 2 of the flow): who it's for, the experience, the promise. ≤ 38 words each.
     No spec lists, no decision framing, NO greeting (the greeting lives in intake.q1).
  1 × role=outcome — THREE THINGS TO REMEMBER: the three USPs in one breath; say the buyer can steer, without another question.
  4-6 × role=proof — GUIDED DISCOVERY in the natural order for this product category (what a person first sees or touches →
     what they live with daily → practicality → the core performance moment → trust/safety). One area per segment. The
     runtime plays the buyer's strongest signal first, so each must stand alone.
  1 × role=features — a few more things, one sentence each.
  1 × role=establish — variant + written terms + the TOP 2-3 OPEN QUESTIONS from the unknowns list, declared honestly with
     where each gets settled (test drive / dealer / a document the owner can upload).
- state_questions: optional questions for responding to an unclear customer request; not an automatic discovery sequence.
- advance: the next action naming a CTA label — chosen to resolve the biggest remaining uncertainty. do_not_recommend_if: honest.
- Segments may only use facts that exist; a concern with no facts is planned as an honest gap, never invented.
- Every segment needs a visual that shows its subject (shots quality ≥3 preferred, else images); missing → visual_gaps.
- CTAs: 2-3 fitting the product; one primary; the advance references one.
- Voice: a persona matching the brand — warm, direct, honest. Voices: Sulafat (warm), Aoede (breezy), Leda (youthful),
  Despina (smooth), Kore (firm), Achernar (soft), Zephyr (bright).
{language}
Return exactly the schema."""


def _verified_plan(demo_id: str, demo: dict) -> schemas.Plan | None:
    """Load a human-reviewed plan bundle when both reasoning providers are unavailable."""
    manifests = [s for s in demo.get("sources", []) if s.get("kind") == "text"
                 and s.get("name", "").lower() == "verified-plan.json.md"]
    if not manifests:
        return None
    raw = store.path(demo_id, manifests[-1]["path"]).read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return schemas.Plan.model_validate_json(raw)


def run(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        raise RuntimeError("Nothing to plan from — read the sources first")
    prev = store.read_json(demo_id, "plan.json")
    demo = store.load(demo_id)
    emit("Planning the pitch: decision frame, outcome, proof blocks…")
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}·{f.get('truth','stated')}] {f['claim']}: {f['value']}" + (f" ({f['conditions']})" if f.get("conditions") else "") for f in und["facts"] if f.get("approved", True))
    vshots = [s for s in und["shots"] if store.visual_allowed(demo, s["source_id"])]
    vimgs = [i for i in und["images"] if store.visual_allowed(demo, i["source_id"])]
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in vshots)
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(visuals.part_names(i))} · {i['description']}" for i in vimgs)
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
        content += f"\nPREVIOUS PLAN (keep what still works; remove unsupported personal assumptions; it is not evidence of customer context):\n{json.dumps(prev)[:24000]}\n"
    if instruction:
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    sys = PLAN_SYSTEM.format(principles=PRINCIPLES, states=CUSTOMER_STATES, shape=PITCH_SHAPE, audience=audience_instruction(demo.get("settings", {}).get("audience", "everyday")), language=language_instruction(demo.get("settings", {}).get("language", "en-IN")))
    try:
        plan = claude.structured(sys, content, schemas.Plan, max_tokens=20000, model=config.CLAUDE_PLAN_MODEL)
    except Exception as e:
        manifest = _verified_plan(demo_id, demo) if claude._provider_unavailable(e) else None
        if not manifest:
            raise RuntimeError(f"Planning failed: {claude.describe_error(e)}") from e
        emit("Reasoning providers unavailable — using the explicit verified plan…")
        plan = manifest

    fact_ids = {f["id"] for f in und["facts"]}
    vis_ids = {s["id"] for s in vshots} | {i["id"] for i in vimgs}
    p = plan.model_dump()
    p["intake"]["q2"] = ""
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
    if "features" not in roles and p["segments"]:
        # guarantee the "a few more things" block exists
        p["segments"].append({"id": "more-features", "title": "A few more things", "role": "features", "goal": "three to five other features, one sentence each, then invite questions", "outcome": "", "topic": "features", "fact_ids": [], "usp_ids": [], "visual_refs": [], "priority_topic": False})
    order = {"intro": 0, "outcome": 1, "proof": 2, "features": 3, "establish": 4}
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
