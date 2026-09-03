"""Runtime Q&A — Claude proposes, the validator disposes ('no citation, no claim')."""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from .author import CLAIMISH, NUMBERISH

QA_SYSTEM = """You are {persona_name}, the voice guide in a live product demo of {product_name} ({category}).
Reply in 1-3 short spoken sentences in the persona's voice ({tone}). No markdown.

HARD RULES
- Only the FACT REGISTRY below may be stated as fact. Cite every fact id you rely on in fact_ids.
- If the registry does not answer the question, set answered=false, leave fact_ids empty, say plainly that the
  sources don't state it and that a person from the brand will confirm — never estimate, never compare to other
  brands, never promise discounts, delivery dates or negotiate price.
- Lab/certified figures must be named as such with their condition.
- Prefer a visual: pick the shot or image id that literally shows what you are talking about.
- If the customer asks to take an action (book, buy, reserve, talk to someone), set cta to the matching id.
- topic: one of {topics}.

CUSTOMER: {profile}

CALLS TO ACTION: {ctas}

FACT REGISTRY:
{facts}

VISUALS:
{visuals}
"""

DONT_GUESS = "I don't want to guess on that — it isn't in the material I've been given. I'll note it so someone from the team can confirm it for you. Is there anything else I can show you meanwhile?"


def _system(demo_id: str, profile: dict | None) -> tuple[str, dict, dict]:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    voice = plan.get("voice", {})
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}] {f['claim']}: {f['value']}" + (f" (condition: {f['conditions']})" if f.get("conditions") else "") for f in facts) or "(empty)"
    vis_txt = "\n".join([f"{s['id']} shot {s['start']:.0f}-{s['end']:.0f}s · {s['part']} · {s['description']}" for s in und.get("shots", [])] + [f"{i['id']} image · {i['angle']} · {i['description']}" for i in und.get("images", [])]) or "(none)"
    topics = sorted({s.get("topic", "") for s in plan.get("segments", [])} | {"other"})
    sys = QA_SYSTEM.format(
        persona_name=voice.get("persona_name", "Maya"), product_name=und.get("product", {}).get("name", "the product"),
        category=und.get("product", {}).get("category", ""), tone=voice.get("tone", "warm, direct, honest"),
        topics=", ".join(t for t in topics if t), profile=json.dumps(profile or {"note": "unknown"}),
        ctas=json.dumps([{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in plan.get("ctas", [])]),
        facts=facts_txt, visuals=vis_txt,
    )
    return sys, und, plan


def answer(demo_id: str, question: str, history: list[dict] | None = None, profile: dict | None = None) -> dict:
    sys, und, plan = _system(demo_id, profile)
    msgs: list[dict] = []
    for h in (history or [])[-8:]:
        role = "user" if h.get("role") == "user" else "assistant"
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + h.get("text", "")
        else:
            msgs.append({"role": role, "content": h.get("text", "")})
    if msgs and msgs[0]["role"] != "user":
        msgs.insert(0, {"role": "user", "content": "(demo in progress)"})
    if msgs and msgs[-1]["role"] == "user":
        msgs.append({"role": "assistant", "content": "(listening)"})
    try:
        out = claude.structured(sys, question, schemas.QAOut, max_tokens=1500, history=msgs)
    except Exception as e:
        raise RuntimeError(claude.describe_error(e)) from e

    fact_ids = {f["id"] for f in und.get("facts", []) if f.get("approved", True)}
    valid = [x for x in out.fact_ids if x in fact_ids]
    text = out.answer.strip()
    escalate = out.escalate.strip()
    answered = bool(out.answered) and (bool(valid) or not (NUMBERISH.search(text) or CLAIMISH.search(text)))
    if (NUMBERISH.search(text) or CLAIMISH.search(text)) and not valid:
        answered = False
    if not answered and not out.cta:
        text = DONT_GUESS if not valid else text
        escalate = escalate or question
        _record_unknown(demo_id, question)
    vis = None
    if out.visual_ref:
        for s in und.get("shots", []):
            if s["id"] == out.visual_ref:
                vis = {"kind": "shot", "ref": s["id"], "start": s["start"], "end": s["end"], "source_id": s["source_id"]}
        for i in und.get("images", []):
            if i["id"] == out.visual_ref:
                vis = {"kind": "image", "ref": i["id"], "source_id": i["source_id"]}
    facts = [f for f in und.get("facts", []) if f["id"] in valid]
    return {"answer": text, "fact_ids": valid, "facts": [{"id": f["id"], "claim": f["claim"], "value": f["value"], "source": f["source"]} for f in facts],
            "visual": vis, "escalate": escalate, "topic": out.topic, "cta": out.cta, "answered": answered}


def _record_unknown(demo_id: str, question: str) -> None:
    def fn(d):
        pass
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        return
    q = question.strip()
    for u in und.get("unknowns", []):
        if u["question"].strip().lower() == q.lower():
            return
    und.setdefault("unknowns", []).append({"id": f"U{len(und['unknowns'])+1:02d}", "question": q, "why_customers_ask": "asked during a demo", "status": "open", "origin": "runtime"})
    store.write_json(demo_id, "understanding.json", und)
