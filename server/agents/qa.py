"""Runtime Q&A — Claude proposes, the validator disposes ('no citation, no claim').
No web search, no tools: only the registry. Unanswerable → don't guess → offer a salesperson callback."""
from __future__ import annotations

import json
import re
import time

from .. import schemas, store
from ..llm import claude
from .author import CLAIMISH, NUMBERISH
from .principles import language_instruction

QA_SYSTEM = """You are {persona_name}, the voice guide in a live product demo of {product_name} ({category}).
Reply in 1-3 short spoken sentences in the persona's voice ({tone}). No markdown.

HARD RULES
- You have NO web search and NO tools. Only the FACT REGISTRY below may be stated as fact. Cite every fact id you
  rely on in fact_ids. Name the kind of truth for figures: certified (with its test condition), modeled (with its
  assumption), or the written terms.
- If the registry does not answer the question, set answered=false, leave fact_ids empty, and say plainly that you're
  not sure from the material you have and won't guess — never estimate, never compare to other brands, never promise
  discounts, delivery dates or negotiate price. The player will then offer a salesperson callback; do NOT ask for a
  phone number yourself.
- P03: if the question is a stated want whose real job is unclear (e.g. "does it have 100 km range?"), you may set
  clarifying_question to ONE short question that uncovers the job (e.g. "do you need a hundred kilometres in one day,
  or mainly want to charge less often?") — then answer briefly with the cited fact anyway.
- P07: reuse the customer's own nouns and numbers from CUSTOMER where relevant.
- Prefer a visual: pick the shot or image id that literally shows what you are talking about.
- If the customer asks to take an action (book, buy, reserve, talk to someone), set cta to the matching id.
- topic: one of {topics}.
{language}

CUSTOMER: {profile}

CALLS TO ACTION: {ctas}

FACT REGISTRY:
{facts}

VISUALS:
{visuals}
"""

DONT_GUESS = "I'm not sure about that from the material I've been given, so I won't guess. I can have a salesperson call you about it — if you'd like that, just tell me your number, or we can carry on."


def _system(demo_id: str, profile: dict | None) -> tuple[str, dict, dict]:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    demo = store.load(demo_id)
    voice = plan.get("voice", {})
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    facts_txt = "\n".join(f"{f['id']} [{f['kind']}·{f.get('truth','stated')}] {f['claim']}: {f['value']}" + (f" (condition: {f['conditions']})" if f.get("conditions") else "") for f in facts) or "(empty)"
    vis_txt = "\n".join([f"{s['id']} shot {s['start']:.0f}-{s['end']:.0f}s · {s['part']} · {s['description']}" for s in und.get("shots", [])] + [f"{i['id']} image · {i['angle']} · {i['description']}" for i in und.get("images", [])]) or "(none)"
    topics = sorted({s.get("topic", "") for s in plan.get("segments", [])} | {"other"})
    sys = QA_SYSTEM.format(
        persona_name=voice.get("persona_name", "Maya"), product_name=und.get("product", {}).get("name", "the product"),
        category=und.get("product", {}).get("category", ""), tone=voice.get("tone", "warm, direct, honest"),
        topics=", ".join(t for t in topics if t), profile=json.dumps(profile or {"note": "unknown"}),
        ctas=json.dumps([{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in plan.get("ctas", [])]),
        facts=facts_txt, visuals=vis_txt, language=language_instruction(demo.get("settings", {}).get("language", "en-IN")),
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
    offer_callback = False
    if not answered and not out.cta:
        text = DONT_GUESS if not valid else text
        escalate = escalate or question
        offer_callback = True
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
    return {"answer": text, "fact_ids": valid, "facts": [{"id": f["id"], "claim": f["claim"], "value": f["value"], "source": f["source"], "truth": f.get("truth", "stated")} for f in facts],
            "visual": vis, "escalate": escalate, "topic": out.topic, "cta": out.cta, "answered": answered,
            "clarifying_question": (out.clarifying_question or "").strip() if answered else "", "offer_callback": offer_callback}


def _record_unknown(demo_id: str, question: str) -> None:
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        return
    q = question.strip()
    for u in und.get("unknowns", []):
        if u["question"].strip().lower() == q.lower():
            return
    und.setdefault("unknowns", []).append({"id": f"U{len(und['unknowns'])+1:02d}", "question": q, "why_customers_ask": "asked during a demo", "status": "open", "origin": "runtime"})
    store.write_json(demo_id, "understanding.json", und)


PHONE = re.compile(r"(?:\+?91[\s-]?)?([6-9]\d{9})")


def parse_phone(text: str) -> str | None:
    digits_only = re.sub(r"[^\d+]", "", text.replace(" ", ""))
    m = PHONE.search(digits_only)
    return m.group(1) if m else None


def save_lead(demo_id: str, phone: str, question: str, profile: dict | None, session_id: str | None) -> dict:
    lead = {"id": f"lead_{int(time.time())}", "phone": phone, "question": question, "profile": profile or {}, "session_id": session_id, "created_at": time.time(), "status": "new"}
    store.write_json(demo_id, f"leads/{lead['id']}.json", lead)
    return lead
