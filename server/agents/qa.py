"""Runtime Q&A — Claude proposes, the validator disposes ('no citation, no claim').
No web search, no tools: only the registry. Unanswerable → don't guess → offer a salesperson callback."""
from __future__ import annotations

import json
import re
import time

from .. import schemas, store
from ..llm import claude
from .author import CLAIMISH, NUMBERISH
from .principles import audience_instruction, language_instruction

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
- DECLINE RULES: for pricing, discounts, finance/EMI, insurance, product features/specs, availability/delivery,
  warranty/service terms and brand comparisons — if the registry does not state it, decline (answered=false) and let the
  callback happen. Never estimate these categories, even when a "typical" figure feels obvious.
{competitors}
{audience}
{language}
- Answer in plain words first, in one or two sentences; offer the technical detail rather than volunteering it.

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
    comp_txt = ""
    if demo.get("settings", {}).get("competition") == "on" and und.get("competitors"):
        rows = []
        for c in und["competitors"]:
            for f in c["facts"]:
                rows.append(f"{f['id']} [{c['name']} · {f['kind']}] {f['claim']}: {f['value']} (source {c['url']})")
        comp_txt = ("- COMPARISONS ARE ALLOWED ONLY against this COMPETITOR REGISTRY (figures from their official pages, as read on "
                    "the date shown). Cite the C-fact ids, compare like with like (same test condition), and END every comparative "
                    "statement with: 'that is as per their website when we checked — please verify on their site'.\nCOMPETITOR REGISTRY:\n" + "\n".join(rows))
    sys = QA_SYSTEM.format(
        persona_name=voice.get("persona_name", "Maya"), product_name=und.get("product", {}).get("name", "the product"),
        category=und.get("product", {}).get("category", ""), tone=voice.get("tone", "warm, direct, honest"),
        topics=", ".join(t for t in topics if t), profile=json.dumps(profile or {"note": "unknown"}),
        ctas=json.dumps([{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in plan.get("ctas", [])]),
        facts=facts_txt, visuals=vis_txt, language=language_instruction((profile or {}).get("language") or demo.get("settings", {}).get("language", "en-IN")), competitors=comp_txt, audience=audience_instruction(demo.get("settings", {}).get("audience", "everyday")),
    )
    return sys, und, plan


def answer(demo_id: str, question: str, history: list[dict] | None = None, profile: dict | None = None, voice_it: bool = True) -> dict:
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
    if store.load(demo_id).get("settings", {}).get("competition") == "on":
        fact_ids |= {f["id"] for c in und.get("competitors", []) for f in c["facts"]}
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
    facts = [f for f in und.get("facts", []) if f["id"] in valid] + [f for c in und.get("competitors", []) for f in c["facts"] if f["id"] in valid]
    if vis is None and valid:
        from . import visuals as _vis
        ref = _vis.for_facts(und, valid)
        if ref:
            vis = {"kind": "image" if ref.startswith("im") else "shot", "ref": ref, "source_id": next((x.get("source_id") for x in und.get("images", []) + und.get("shots", []) if x["id"] == ref), None)}
    audio = None
    if voice_it and text:
        try:
            from . import voice as _voice
            rel = _voice.render_line(demo_id, text, strict=True)
            audio = f"/media/{demo_id}/{rel}" if rel else None
        except Exception:
            audio = None
    return {"audio": audio, "answer": text, "fact_ids": valid, "facts": [{"id": f["id"], "claim": f["claim"], "value": f["value"], "source": f["source"], "truth": f.get("truth", "stated")} for f in facts],
            "visual": vis, "escalate": escalate, "topic": out.topic, "cta": out.cta, "answered": answered,
            "clarifying_question": (out.clarifying_question or "").strip() if answered else "", "offer_callback": offer_callback}


CATEGORY_RULES = [
    (re.compile(r"\b(emi|loan|financ|down.?payment|interest|instal)", re.I), "finance", "EMI schedule / bank tie-up sheet"),
    (re.compile(r"\binsur", re.I), "insurance", "insurance partner terms and premium sheet"),
    (re.compile(r"\b(price|cost|discount|offer|on.?road|ex.?showroom|cheaper|rate)\b", re.I), "pricing", "state-wise on-road price list / current offers sheet"),
    (re.compile(r"\b(warrant|service|guarantee|maintenance|repair|dealer)", re.I), "warranty_service", "warranty terms + service schedule / price list"),
    (re.compile(r"\b(deliver|availab|stock|waiting|colou?r)", re.I), "availability", "availability / delivery timelines by city"),
    (re.compile(r"\b(vs|versus|compare|better than|ather|ola|competitor)", re.I), "comparison", "competitor pages (add as competitor URLs) or a comparison sheet"),
    (re.compile(r"\b(feature|spec|weight|boot|storage|display|app|brake|abs|tyre|seat)", re.I), "features", "spec sheet PDF / owner's manual"),
]


def classify(question: str) -> tuple[str, str]:
    for rx_, cat, doc in CATEGORY_RULES:
        if rx_.search(question):
            return cat, doc
    return "other", "FAQ page"


def _record_unknown(demo_id: str, question: str) -> None:
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        return
    q = question.strip()
    for u in und.get("unknowns", []):
        if u["question"].strip().lower() == q.lower():
            return
    cat, doc = classify(q)
    und.setdefault("unknowns", []).append({"id": f"U{len(und['unknowns'])+1:02d}", "question": q, "why_customers_ask": "asked during a demo", "status": "open", "origin": "runtime", "category": cat, "suggested_document": doc})
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
