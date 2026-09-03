"""Stage 2 — Plan.  Claude decides what the demo should be, from the registry and visuals."""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude

PLAN_SYSTEM = """You are the product-demo planner. You turn a fact registry and a set of visuals into the plan for a
4-5 minute spoken, interruptible demo that a prospective buyer watches on the brand's website.

Design rules (these are decisions, not suggestions):
- Lead with the buyer's real concerns for this category (e.g. for an EV: range, charging, cost; for SaaS: setup,
  security, pricing). 6-10 segments, each with one goal, the fact ids it will use, and the best visual refs.
- A segment may only use facts that exist. If a concern has no facts, still plan the segment but say so in goal
  ("acknowledge honestly that the sources don't state X") — never plan to invent.
- Every segment needs a visual. Prefer video shots of quality ≥ 3; else images. If nothing shows a feature,
  record it in visual_gaps with a concrete upload suggestion.
- CTAs: propose 2-3 that fit the product and the brand site (book/reserve/buy/contact/trial/link). Mark one primary.
- Voice: a persona that matches the brand profile — warm, direct, honest, never salesy. Suggested voices are
  Gemini TTS names: Sulafat (warm), Aoede (breezy), Leda (youthful), Despina (smooth), Kore (firm), Achernar (soft), Zephyr (bright).
- Intake: two spoken questions in the persona's voice — first asks the customer's name and why they are
  interested; second asks whether there is anything specific to focus on or whether to get going. Chips = the
  segment topics as short labels.
- customer_persona: who is watching and what they are deciding.
Return exactly the schema."""


def run(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        raise RuntimeError("Nothing to plan from — read the sources first")
    prev = store.read_json(demo_id, "plan.json")
    demo = store.load(demo_id)
    emit("Planning the walkthrough…")
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}] {f['claim']}: {f['value']}" + (f" ({f['conditions']})" if f.get("conditions") else "") for f in und["facts"] if f.get("approved", True))
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
        content += f"\nPREVIOUS PLAN (keep what still works; change only what the instruction asks):\n{json.dumps(prev)[:20000]}\n"
    if instruction:
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    try:
        plan = claude.structured(PLAN_SYSTEM, content, schemas.Plan, max_tokens=16000)
    except Exception as e:
        raise RuntimeError(f"Planning failed: {claude.describe_error(e)}") from e

    fact_ids = {f["id"] for f in und["facts"]}
    vis_ids = {s["id"] for s in und["shots"]} | {i["id"] for i in und["images"]}
    p = plan.model_dump()
    for seg in p["segments"]:
        seg["fact_ids"] = [x for x in seg["fact_ids"] if x in fact_ids]
        seg["visual_refs"] = [x for x in seg["visual_refs"] if x in vis_ids]
    for c in p["concerns"]:
        c["fact_ids"] = [x for x in c["fact_ids"] if x in fact_ids]
    # keep human-set CTAs / voice across revisions unless the instruction is about them
    if prev and instruction:
        low = instruction.lower()
        if "cta" not in low and "button" not in low and "call to action" not in low:
            p["ctas"] = prev.get("ctas", p["ctas"])
        if "voice" not in low and "persona" not in low and "tone" not in low:
            p["voice"] = prev.get("voice", p["voice"])
    if not p["ctas"]:
        p["ctas"] = [{"id": "contact", "label": "Talk to us", "kind": "contact", "url": "", "primary": True, "when": "always"}]
    store.write_json(demo_id, "plan.json", p)
    store.log(demo_id, "plan", {"segments": [s["id"] for s in p["segments"]], "ctas": [c["label"] for c in p["ctas"]], "voice": p["voice"]["suggested_voice"]})
    emit(f"Plan: {len(p['segments'])} segments, {len(p['ctas'])} calls to action, persona “{p['voice']['persona_name']}”.")
    return p
