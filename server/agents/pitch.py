"""Runtime pitch planner — after the standard intro, personalise the route through the
approved proof blocks for THIS buyer (P02/P03/P05/P07), with grounded one-line bridges."""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from .author import CLAIMISH, NUMBERISH
from .principles import CUSTOMER_STATES, PRINCIPLES, audience_instruction, language_instruction

PITCH_SYSTEM = """You are {persona_name}, the voice guide in a live demo of {product_name}. The standard opening
(decision frame + the outcome shown first) has just played. Now plan the rest of THIS buyer's demo.

{principles}

{states}

Your output:
- customer_state: from what they said (their name/purpose answer, and the follow-up answer if present).
- decision_frame: 1-2 spoken sentences recapping THIS buyer's decision in their own words and numbers (P01, P07). It is
  spoken right after the standard opening. If they gave no signal, say honestly that you won't guess and will show the
  2-3 fit dimensions briefly.
- follow_up_question: ONE question (P03: for a stated want, what it must accomplish and under what conditions; for a
  stated need, confirm it and its stakes; for unknown, "walk me through a normal day"). Empty on a refine call.
- route: from the LIBRARY below — the 2-3 proof blocks that matter to THIS buyer (primary first), then the single features
  block, then establish last. Never more than 3 proof blocks: the whole demo must stay near three minutes; everything else
  is for questions. Each step may carry ONE bridge sentence that ties the block to this buyer's situation using their nouns
  and numbers. A bridge that states a figure must cite fact ids from the REGISTRY; otherwise leave the bridge empty.
  Never put intro/outcome segments in the route (they already played).
- skipped: segments left out, with the reason.
- usp_order: which USPs get covered, in order (every route step's usps).
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
        # soft JSON + low effort + hard timeout: the plan must land while the ~2-minute standard opening plays
        out = claude.structured(sys, ask, schemas.PitchPlan, max_tokens=3000, soft=True, effort="low", timeout=50.0)
    except Exception as e:
        raise RuntimeError(claude.describe_error(e)) from e
    p = out.model_dump()
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
    if refine:
        p["follow_up_question"] = ""
    store.log(demo_id, "pitch", {"state": p["customer_state"], "route": [r["segment_id"] for r in p["route"]], "profile": profile})
    return p
