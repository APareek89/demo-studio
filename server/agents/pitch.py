"""Runtime pitch planner — after the standard intro, personalise the route through the
approved proof blocks for THIS buyer (P02/P03/P05/P07), with grounded one-line bridges."""
from __future__ import annotations

import json
import re

from .. import schemas, store
from ..llm import runtime
from .author import CLAIMISH, NUMBERISH
from .principles import CUSTOMER_STATES, PRINCIPLES, audience_instruction, language_instruction

PITCH_SYSTEM = """You are {persona_name}, the voice guide in a live demo of {product_name}. An approved standard opening
will play after the opening film. Plan the personalised route that follows it for THIS buyer.

{principles}

{states}

Your output:
- customer_state: from what they said (their name/purpose answer, and the follow-up answer if present).
- decision_frame: the ACKNOWLEDGEMENT, 1-2 spoken sentences that restate THIS buyer's need in their OWN words and promise
  the order ("Got it, Anand: easy in city traffic, and comfortable on the long drives. Cabin first, then the drive, then
  what's standard."). It plays right after the overview. Warm, specific, zero specs. If they gave no signal, say honestly
  that you'll give the balanced tour and they can steer at any pause. Keep this framing positive: never promise a section
  about gaps, unknowns, or "what I can't tell you"; written terms and open questions belong in the establish block.
- follow_up_question: ONE question (P03: for a stated want, what it must accomplish and under what conditions; for a
  stated need, confirm it and its stakes; for unknown, "walk me through a normal day"). Empty on a refine call.
- route: from the LIBRARY below — the buyer's strongest signal FIRST (a comfort need starts at the cabin, a performance
  want at the drive), then 1-2 supporting blocks, then the single features block, then establish last. Never more than 3 proof blocks: the whole demo must stay near three minutes; everything else
  is for questions. Each step may carry ONE bridge sentence that ties the block to this buyer's situation using their nouns
  and numbers. A bridge that states a figure must cite fact ids from the REGISTRY; otherwise leave the bridge empty.
  Never put intro/outcome segments in the route (they already played).
- skipped: segments left out, with the reason.
- usp_order: which USPs get covered, in order (every route step's usps).
- custom_batches: when the buyer said something specific, 2-3 batches of ≤ 38 words each, ONE idea per batch, each shaped
  as: their words → one outcome → one cited proof → what it changes for them. ("For the long drives you mentioned, Smart
  Cruise with Stop and Go holds your distance on the highway…"). Each names the picture that literally shows that idea
  (visual_ref) and cites fact ids for every figure. Prefer exactly ONE fact per batch; combine facts only when they are the
  same visible feature. Never invent an operating consequence (for example, number of downshifts) that the registry does
  not state. A reasonable inference must be introduced as "That suggests…". Never a spec list. Empty when the buyer gave
  nothing specific.
- advance: the closing advance for this buyer (P10), naming one CTA label; advance_cta = its id.
{audience}
{language}

CUSTOMER SAID: {profile}

LIBRARY (proof + establish segments):
{library}

USPS: {usps}
CTAS: {ctas}
PLAN DEFAULTS: primary_outcome={primary}; supporting={supporting}; advance="{advance}"; do_not_recommend_if="{dnr}"

FACT REGISTRY:
{facts}"""


def plan_pitch(demo_id: str, profile: dict, refine: bool = False) -> dict:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    script = store.read_json(demo_id, "script.json") or {}
    demo = store.load(demo_id)
    voice = plan.get("voice", {})
    segs = [s for s in script.get("segments", []) if s.get("role") in ("proof", "features", "establish") and any(not l.get("unverified") for l in s["lines"])]
    plan_by_id = {s["id"]: s for s in plan.get("segments", [])}
    library = "\n".join(f"{s['id']} [{s['role']}] {s['title']} — outcome: {s.get('outcome') or plan_by_id.get(s['id'], {}).get('outcome','')} — topic {s['topic']} — usps {s.get('usp_ids') or plan_by_id.get(s['id'], {}).get('usp_ids', [])} — facts {sorted({f for l in s['lines'] for f in l.get('fact_ids', [])})}" for s in segs) or "(no proof blocks)"
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}·{f.get('truth','stated')}] {f['claim']}: {f['value']}" + (f" ({f['conditions']})" if f.get("conditions") else "") for f in facts) or "(empty)"
    sys = PITCH_SYSTEM.format(
        persona_name=voice.get("persona_name", "the guide"), product_name=und.get("product", {}).get("name", "the product"),
        principles=PRINCIPLES, states=CUSTOMER_STATES, audience=audience_instruction(demo.get("settings", {}).get("audience", "everyday")), language=language_instruction((profile or {}).get("language") or demo.get("settings", {}).get("language", "en-IN")),
        profile=json.dumps(profile), library=library, usps=json.dumps(plan.get("usps", [])),
        ctas=json.dumps([{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in plan.get("ctas", [])]),
        primary=plan.get("primary_outcome", ""), supporting=plan.get("supporting_outcomes", []), advance=plan.get("advance", ""), dnr=plan.get("do_not_recommend_if", ""), facts=facts_txt,
    )
    ask = "Plan the route now." + (" This is a REFINE call: the follow-up has been answered — leave follow_up_question empty and finalise the route." if refine else "")
    try:
        # runtime providers in order, short timeout each: the plan must land while the standard opening plays
        out = runtime.structured(sys, ask, schemas.PitchPlan, max_tokens=3000)
    except Exception as e:
        raise RuntimeError(str(e)[:300]) from e
    p = out.model_dump()
    # The live demo asks exactly one intake question. Refine calls must not create
    # or voice a second runtime question, even if a model returns one anyway.
    if refine:
        p["follow_up_question"] = ""
    if re.search(r"\b(can't|cannot|can’t|don't know|do not know|honestly can't|honestly cannot)\b", p.get("decision_frame", ""), re.I):
        first = re.split(r"(?<=[.!?])\s+", p["decision_frame"].strip(), maxsplit=1)[0]
        p["decision_frame"] = first + " I'll start with what matters most, then cover the everyday fit, what's standard, and what's in writing."
    # ---- validate: segment ids exist; bridges obey no-citation-no-claim; establish last
    seg_ids = {s["id"] for s in segs}
    fact_ids = {f["id"] for f in facts}
    route, seen = [], set()
    for st in p["route"]:
        if st["segment_id"] not in seg_ids or st["segment_id"] in seen:
            continue
        seen.add(st["segment_id"])
        st["bridge_fact_ids"] = [x for x in st.get("bridge_fact_ids", []) if x in fact_ids]
        b = (st.get("bridge") or "").strip()
        if b and not st["bridge_fact_ids"] and (NUMBERISH.search(b) or CLAIMISH.search(b)):
            st["bridge"] = ""  # dropped: a figure without a citation
            st["bridge_dropped"] = b
        route.append(st)
    establish = [s["id"] for s in segs if s["role"] == "establish"]
    features = [s["id"] for s in segs if s["role"] == "features"]
    # custom batches: grounded, pictured, voiced server-side (same voice as the demo — never the browser's)
    from . import visuals as _vis
    from . import voice as _voice
    vis_ids = {x["id"] for x in und.get("images", [])} | {x["id"] for x in und.get("shots", [])}
    batches = []
    for b in (p.get("custom_batches") or [])[:3]:
        b["fact_ids"] = [x for x in b.get("fact_ids", []) if x in fact_ids]
        txt = (b.get("text") or "").strip()
        if not txt or (not b["fact_ids"] and (NUMBERISH.search(txt) or CLAIMISH.search(txt))):
            continue
        if b.get("visual_ref") not in vis_ids:
            b["visual_ref"] = _vis.for_facts(und, b["fact_ids"]) or ""
        b["visual_ref"] = _vis.for_text_and_facts(demo_id, und, txt, b["fact_ids"], b.get("visual_ref") or "") or ""
        b["words"] = len(txt.split())
        batches.append(b)
    to_voice = [(b, "audio", b["text"]) for b in batches] + [(st, "bridge_audio", st["bridge"]) for st in p["route"] if st.get("bridge")]
    if p.get("decision_frame"):
        to_voice.append((p, "decision_frame_audio", p["decision_frame"]))
    if p.get("follow_up_question"):
        to_voice.append((p, "follow_up_audio", p["follow_up_question"]))
    if p.get("advance"):
        to_voice.append((p, "advance_audio", p["advance"]))
    if to_voice and _voice.provider_for(demo) != "browser":
        import contextvars as _cv
        from concurrent.futures import ThreadPoolExecutor as _TPE
        with _TPE(max_workers=4) as pool:
            futs = {pool.submit(_cv.copy_context().run, _voice.render_line, demo_id, text, strict=True): (obj, key) for obj, key, text in to_voice}
            for fut in futs:
                obj, key = futs[fut]
                try:
                    rel = fut.result()
                    obj[key] = f"/media/{demo_id}/{rel}" if rel else None
                except Exception:
                    obj[key] = None
    for b in batches:
        v = next((x for x in und.get("images", []) + und.get("shots", []) if x["id"] == b.get("visual_ref")), None)
        b["visual"] = {"kind": "image" if b.get("visual_ref", "").startswith("im") else "shot", "ref": b.get("visual_ref"), "source_id": v.get("source_id") if v else None, "start": v.get("start") if v else None, "end": v.get("end") if v else None, "description": v.get("description", "") if v else ""} if v else None
        b["visual"] = b["visual"] or {"kind": "none"}
    p["custom_batches"] = batches
    proofs = [r for r in route if r["segment_id"] not in establish and r["segment_id"] not in features][:3]
    feat = [r for r in route if r["segment_id"] in features][:1] or ([{"segment_id": features[0], "bridge": "", "bridge_fact_ids": []}] if features else [])
    est = [r for r in route if r["segment_id"] in establish][:1] or ([{"segment_id": establish[0], "bridge": "", "bridge_fact_ids": []}] if establish else [])
    route = proofs + feat + est
    if not proofs:  # fallback: plan order, first 3 proof blocks
        route = [{"segment_id": s["id"], "bridge": "", "bridge_fact_ids": []} for s in segs if s["role"] == "proof"][:3] + feat + est
    p["route"] = route
    ctas = {c["id"]: c for c in plan.get("ctas", [])}
    if p.get("advance_cta") not in ctas:
        prim = next((c for c in ctas.values() if c.get("primary")), next(iter(ctas.values()), None))
        p["advance_cta"] = prim["id"] if prim else ""
    store.log(demo_id, "pitch", {"state": p["customer_state"], "route": [r["segment_id"] for r in p["route"]], "profile": profile})
    return p
