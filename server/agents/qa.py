"""Runtime Q&A — the model proposes, the validator disposes ('no citation, no claim').
No web search, no tools: only the registry. Unanswerable, or every provider down → don't guess → offer a salesperson callback."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

from .. import schemas, store, usage
from ..llm import claude, runtime
from . import plain_terms
from .author import CLAIMISH, NUMBERISH
from .principles import EVIDENCE_RULES, audience_instruction, fact_context, language_instruction, policy_relation_conflict

QA_SYSTEM = """You are {persona_name}, the voice guide in a live product demo of {product_name} ({category}).
Reply in 1-3 short spoken sentences in the persona's voice ({tone}). No markdown.
Keep the entire answer within 60 words, including required caveats. A direct single-fact answer can use one sentence.

HARD RULES
- You have NO web search and NO tools. Only the FACT REGISTRY below may be stated as fact. Cite every fact id you
  rely on in fact_ids. Keep stated specifications distinct from certified results, modeled estimates, observations
  and written terms. Official manufacturer specifications are not automatically certified. Give the relevant basis
  when it matters, without a ritual label for ordinary facts.
- If the registry does not answer the question, set answered=false, leave fact_ids empty, and say plainly that you're
  not sure from the material you have and won't guess — never estimate, never compare to other brands, never promise
  discounts, delivery dates or negotiate price. The player will then offer a salesperson callback; do NOT ask for a
  phone number yourself.
- P03: only when the customer's intent is ambiguous enough to change the answer, ask ONE short clarifying_question
  FIRST. In that response, answer is that same question, answered=true, and fact_ids, visual_ref, escalate and cta are
  empty. Wait for their reply before offering an answer. The question contains no product claims, figures or assumed
  customer details. Do not clarify a clear factual question, and never use clarification to avoid declaring a missing fact.
  When history contains the customer's clarification reply, answer the original question using it; do not restart discovery.
- The player listens briefly after an ordinary answer, then continues automatically. Use statements for ordinary answers and brief
  acknowledgments for greetings; do not restart intake or append an offer, discovery or satisfaction question.
  Only clarifying_question may ask a question; when needed, answer must be that identical single question.
- P07: reuse only the customer's actual nouns and numbers from CUSTOMER or their messages. Do not infer a commute,
  budget, location or household from a persona, a prior script or an example. Unknown context remains unknown.
- A buying need or context correction is not a missing product specification. Acknowledge the actual need without
  promising a benefit; discuss an applicable approved fact, or use the existing one-question clarification when the
  buyer's intended help is unclear. Do not turn a goal such as wanting help in traffic into a request for an unlisted
  assistance feature. The decline rules still apply to any actual unsupported specification or guarantee question.
- Answer the current question's product and scope. Resolve references from the conversation, but a previous shortlist or comparison is not a new request to compare.
  Do not add another brand's policy or features unless the current question asks for that comparison.
- For an explicit reference to a selected or chosen demo variant, use DEMO COMPARISON CONTEXT only when it identifies
  one configuration for that named product. An explicit customer variant or correction takes precedence; never infer a buyer selection or preference from these notes.
  These notes identify comparison examples, not factual evidence: product claims still require approved registry facts
  and all their conditions. If the configuration is missing or ambiguous, clarify only when it changes the answer.
- For an explicit comparison, choose one shared dimension relevant to this buyer and state both sides for the same
  named configurations and matching test basis. A second dimension is optional only when both sides have matching
  evidence and the complete answer still fits the word limit. Do not compare unrelated feature lists or infer that
  an unlisted rival feature is absent. If a dimension and its material conditions do not fit,
  omit that dimension; never shorten away its scope. Stop after the focused answer; the player owns the next question.
- Prefer a visual: pick the shot or image id that literally shows what you are talking about.
- If the customer asks to take an action (book, buy, reserve, talk to someone), set cta to the matching id.
- topic: one of {topics}.
- DECLINE RULES: for pricing, discounts, finance/EMI, insurance, product features/specs, availability/delivery,
  warranty/service terms and brand comparisons — if the registry does not state it, decline (answered=false) and let the
  callback happen. Never estimate these categories, even when a "typical" figure feels obvious.
- For warranty, service and offer terms, a headline is not the complete policy. Preserve explicit unknowns in the cited
  conditions. If duration and usage limits are only joined by a slash or bar, report them as advertised limits and say
  their relationship is not supplied; never turn the separator into "or" or "whichever comes first", or invent coverage
  or exclusions. Retain a relationship or coverage rule when the source explicitly states it. Name a missing term only
  in the relevant answer, not as a disclaimer on every response.
{competitors}
{audience}
{language}
- Answer in plain words first; mention available technical detail as a statement rather than
  volunteering it or asking another question.
  When the customer asks for a technical quantity, the direct answer includes its value AND unit, with a short gloss.
{evidence}

CUSTOMER: {profile}

DEMO COMPARISON CONTEXT (reviewed examples, not buyer selections or factual evidence):
{demo_context}

CALLS TO ACTION: {ctas}

FACT REGISTRY:
{facts}

VISUALS:
{visuals}
"""

DONT_GUESS = "I'm not sure about that from the material I've been given, so I won't guess. I can offer a salesperson callback, or we can carry on."

LOCAL_STOP = set("a an and are as at be by can current did do does for from have how i in is it me much my of on or our please tell that the their there this to was we what when where which who why will with would you your available offered".split())


def _local_terms(text: str) -> set[str]:
    out = set()
    for raw in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", (text or "").lower()):
        w = raw[:-1] if raw.endswith("s") and len(raw) > 4 and not raw.endswith("ss") else raw
        if len(w) > 1 and w not in LOCAL_STOP:
            out.add(w)
    return out


def approved_fact_ids(und: dict, competition: bool = False) -> set[str]:
    ids = {f["id"] for f in und.get("facts", []) if f.get("approved", True)}
    if competition:
        ids |= {f["id"] for c in und.get("competitors", []) for f in c.get("facts", []) if f.get("approved", True)}
    return ids


def _system(demo_id: str, profile: dict | None) -> tuple[str, dict, dict]:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    demo = store.load(demo_id)
    voice = plan.get("voice", {})
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    facts_txt = "\n".join(fact_context(f) for f in facts) or "(empty)"
    vis_txt = "\n".join([f"{s['id']} shot {s['start']:.0f}-{s['end']:.0f}s · {s['part']} · {s['description']}" for s in und.get("shots", [])] + [f"{i['id']} image · {i['angle']} · {i['description']}" for i in und.get("images", [])]) or "(none)"
    topics = sorted({s.get("topic", "") for s in plan.get("segments", [])} | {"other"})
    # Existing reviewed plan notes can identify a demo example. Keep them out of
    # CUSTOMER and the registry; they neither select for the buyer nor prove facts.
    demo_context = (plan.get("notes") or "") if (demo.get("settings", {}).get("competition") == "on"
                    and (demo.get("approvals") or {}).get("script") is True) else ""
    comp_txt = ""
    if demo.get("settings", {}).get("competition") == "on" and und.get("competitors"):
        rows = []
        sources_by_id = {s["id"]: s for s in demo.get("sources", [])}
        for c in und["competitors"]:
            source = sources_by_id.get(c.get("source_id"), {})
            try:
                checked = datetime.fromtimestamp(c["fetched_at"], timezone.utc).date().isoformat()
            except (KeyError, TypeError, ValueError, OverflowError, OSError):
                checked = "not recorded"
            for f in c.get("facts", []):
                if not f.get("approved", True):
                    continue
                citation = f.get("source", {})
                rows.append(f"{f['id']} [{c['name']} · {f['kind']} · {f.get('truth', 'stated')}] {f['claim']}: {f['value']}"
                            + (f" (conditions: {f['conditions']})" if f.get("conditions") else "")
                            + f" (source: {source.get('name') or c.get('source_id', '')}; URL: {c.get('url') or source.get('url') or 'not supplied'}; "
                            f"locator: {citation.get('locator') or 'not supplied'}; quote: {json.dumps(citation.get('quote', ''), ensure_ascii=False)}; checked: {checked})")
        comp_txt = ("- COMPARISONS ARE ALLOWED ONLY against this COMPETITOR REGISTRY (facts from the supplied pages/documents, as read on "
                    "the date shown). Conditions and variant/powertrain/transmission qualifiers are mandatory; do not generalize them to another trim. "
                    "A missing matching variant or test basis means the comparison is unknown. Cite the C-fact ids, compare like with like (same test condition), and END every comparative "
                    "statement with: 'that is as per their website when we checked — please verify on their site'.\nCOMPETITOR REGISTRY:\n" + "\n".join(rows))
    sys = QA_SYSTEM.format(
        persona_name=voice.get("persona_name", "Maya"), product_name=und.get("product", {}).get("name", "the product"),
        category=und.get("product", {}).get("category", ""), tone=voice.get("tone", "warm, direct, honest"),
        topics=", ".join(t for t in topics if t), profile=json.dumps(profile or {"note": "unknown"}),
        demo_context=demo_context or "(none supplied)",
        ctas=json.dumps([{"id": c["id"], "label": c["label"], "kind": c["kind"]} for c in plan.get("ctas", [])]),
        facts=facts_txt, visuals=vis_txt, language=language_instruction((profile or {}).get("language") or demo.get("settings", {}).get("language", "en-IN")), competitors=comp_txt, audience=audience_instruction(demo.get("settings", {}).get("audience", "everyday")),
        evidence=EVIDENCE_RULES,
    )
    return sys, und, plan


def answer(demo_id: str, question: str, history: list[dict] | None = None, profile: dict | None = None, voice_it: bool = True, live: bool = False, *, learn: bool = True) -> dict:
    """live=True is the customer waiting (/run/qa, Playground evals): RUNTIME_PROVIDERS in order, RUNTIME_TIMEOUT each, one retry.
    live=False is build time (FAQ bank, rehearsal): the build model with its full retries and fallback.
    Either way, when every provider fails the guide declines and offers a callback — it never guesses."""
    started = time.monotonic()
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
    provider_failed = False
    try:
        if live:
            # Room for reasoning and the complete JSON envelope; spoken answers stay brief.
            out = runtime.structured(sys, question, schemas.QAOut, history=msgs, max_tokens=3000, thinking_level="low")
        else:
            out = claude.structured(sys, question, schemas.QAOut, max_tokens=1500, history=msgs)
    except Exception as e:  # noqa: BLE001
        provider_failed = True  # an outage is not knowledge: callers must not store this decline as "the sources do not say"
        usage.trace("qa-providers-failed", "none", latency_ms=(time.monotonic() - started) * 1000, user=question, error=str(e)[:300],
                    system="Every reasoning provider failed; declining with a callback offer rather than guessing.")
        out = schemas.QAOut(answer=DONT_GUESS, fact_ids=[], visual_ref="", escalate=question, topic=classify(question)[0], cta="", answered=False, clarifying_question="")

    fact_ids = approved_fact_ids(und, store.load(demo_id).get("settings", {}).get("competition") == "on")
    unsupported_citations = set(out.fact_ids) - fact_ids
    # A valid citation cannot lend cover to a rejected competitor fact in the
    # same answer. Decline the whole proposed claim rather than keeping its text.
    valid = [] if unsupported_citations else list(out.fact_ids)
    text = out.answer.strip()
    escalate = out.escalate.strip()
    clarification = (out.clarifying_question or "").strip()
    cta = out.cta
    selected_facts = [f for f in und.get("facts", []) if f["id"] in valid] + [
        f for competitor in und.get("competitors", []) for f in competitor.get("facts", []) if f["id"] in valid]
    policy_conflict = policy_relation_conflict(text, selected_facts)
    if policy_conflict:
        valid = []
    if unsupported_citations or policy_conflict:
        # An action field must not exempt an unsupported claim from the decline
        # path or let that claim reach speech before the action is shown.
        text, clarification, cta = DONT_GUESS, "", ""
    # A clarification is a question-only turn, not a supported product answer.
    # Keep the existing response shape: answered=true makes old players wait
    # rather than opening a callback. Claims cannot hide in this question field.
    if clarification and (cta or len(clarification.split()) > 38
                          or len(re.findall(r"[?？]", clarification)) != 1
                          or not clarification.endswith(("?", "？"))
                          or NUMBERISH.search(clarification) or CLAIMISH.search(clarification)):
        clarification = ""
    if clarification:
        text, valid, escalate = clarification, [], ""
    answered = bool(out.answered) and not unsupported_citations and not policy_conflict and (bool(valid) or not (NUMBERISH.search(text) or CLAIMISH.search(text)))
    if (NUMBERISH.search(text) or CLAIMISH.search(text)) and not valid:
        answered = False
        text, cta = DONT_GUESS, ""
    offer_callback = False
    if clarification:
        answered = True
    elif not answered and not cta:
        text = DONT_GUESS if not valid else text
        escalate = escalate or question
        offer_callback = True
        if learn and not provider_failed:
            _record_unknown(demo_id, question)
    elif answered and learn:
        _clear_runtime_unknown(demo_id, question)
    vis = None
    if out.visual_ref and not clarification and not policy_conflict:
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
    substitutions = []
    if store.load(demo_id).get("settings", {}).get("audience", "everyday") == "everyday" and not plain_terms.TECHNICAL_REQUEST.search(question):
        text, substitutions = plain_terms.substitute(text)
        if clarification:
            clarification = text
    audio = None
    if voice_it and text:
        try:
            from . import voice as _voice
            rel = _voice.render_line(demo_id, text, demo=_voice.runtime_demo(demo_id, (profile or {}).get("language")) if live else None, strict=True)
            audio = f"/media/{demo_id}/{rel}" if rel else None
        except Exception:
            audio = None
    return {"audio": audio, "answer": text, "fact_ids": valid, "facts": [{"id": f["id"], "claim": f["claim"], "value": f["value"], "source": f["source"], "truth": f.get("truth", "stated")} for f in facts],
            "visual": vis, "escalate": escalate, "topic": out.topic, "cta": cta, "answered": answered,
            "clarifying_question": clarification if answered else "", "offer_callback": offer_callback, "provider_failed": provider_failed,
            "plain_language_substitutions": substitutions}


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
    from . import faq
    faq.record_unknown(demo_id, question)


def _clear_runtime_unknown(demo_id: str, question: str) -> None:
    from . import faq
    faq.clear_unknown(demo_id, question)


PHONE = re.compile(r"(?:\+?91[\s-]?)?([6-9]\d{9})")


def parse_phone(text: str) -> str | None:
    digits_only = re.sub(r"[^\d+]", "", text.replace(" ", ""))
    m = PHONE.search(digits_only)
    return m.group(1) if m else None


def save_lead(demo_id: str, phone: str, question: str, profile: dict | None, session_id: str | None) -> dict:
    lead = {"id": f"lead_{int(time.time())}", "phone": phone, "question": question, "profile": profile or {}, "session_id": session_id, "created_at": time.time(), "status": "new"}
    store.write_json(demo_id, f"leads/{lead['id']}.json", lead)
    return lead
