"""Session summary — one lite call at the end of a session, from the TRUE transcript (what the customer actually heard).
The record's own facts (questions, slides visited, leads, CTA) are copied by code; the model only writes what needs
reading: context, what they cared about, objections and whether they were resolved, the unanswered questions, and one
opening line for the sales call. Runs on the runtime providers (Gemini first, Claude fallback); mock mode never calls out."""
from __future__ import annotations

import json
import time

from pydantic import BaseModel, Field

from .. import config, store
from ..llm import mock, runtime

SUMMARY_SYSTEM = """You summarise a finished voice-led product demo of {product} for the salesperson who will follow up.
Use ONLY the transcript and record given — never invent a detail, a number or a name; leave a field empty when the material does not say.
Plain words, no markdown. Lines marked interrupted were cut off by the customer: only the words shown were heard.
Write for a busy salesperson: what this person is deciding, what they cared about, what worried them and whether the guide settled it,
what could not be answered from the sources, and ONE natural opening line for the call — in the customer's own words where possible.
Keep unresolved requests unanswered. Do not imply that the salesperson already has missing answers, quotes, approvals or finance terms;
when questions remain open, invite a discussion of those questions without promising that their details are ready."""


class Objection(BaseModel):
    text: str
    resolved: bool = False


class SessionSummary(BaseModel):
    customer_name: str = ""
    context: str = Field(description="who they are and what they are deciding, one or two sentences")
    cared_about: list[str] = Field(default_factory=list, description="the two to four things that mattered to them")
    objections: list[Objection] = Field(default_factory=list)
    unanswered: list[str] = Field(default_factory=list, description="questions the guide could not answer from the sources")
    opening_line: str = Field(description="one suggested opening line for the sales call")


def _payload(demo_id: str, session: dict) -> dict:
    deck = store.read_json(demo_id, "deck.json") or {}
    titles = {s["id"]: s.get("title", "") for s in deck.get("slides", [])}
    return {"profile": session.get("profile"), "customer_state": session.get("customer_state"), "minutes": session.get("minutes"), "cta": session.get("cta"),
            "questions": session.get("questions", []), "escalations": session.get("escalations", []), "resolved": session.get("resolved", []), "unresolved": session.get("unresolved", []),
            "slides_visited": [{"slide": titles.get(v.get("slide_id"), v.get("slide_id")), "seconds": v.get("seconds")} for v in session.get("slides_visited", [])],
            "transcript": [{"role": t.get("role"), "text": t.get("text"), **({"interrupted": True} if t.get("interrupted") else {})} for t in session.get("transcript", [])][-60:]}


def summarize(demo_id: str, session: dict) -> dict:
    """The summary dict stored on the session: model fields + the record's own facts, with the model that wrote it."""
    und = store.read_json(demo_id, "understanding.json") or {}
    product = (und.get("product") or {}).get("name") or store.load(demo_id).get("name", "the product")
    payload = _payload(demo_id, session)
    model = "mock"
    if config.MOCK_LLM:
        out = mock.fake(SessionSummary)
        out.customer_name = (session.get("profile") or {}).get("name", "") or out.customer_name
    else:
        out = runtime.structured(SUMMARY_SYSTEM.format(product=product), json.dumps(payload, ensure_ascii=False), SessionSummary,
                                 max_tokens=1200, thinking_level="low")
        model = "runtime"
    escalations = [e for e in session.get("escalations", []) if not str(e).startswith("callback requested")]
    # A proposed sales opener is not evidence that missing answers were obtained.
    # Preserve the summary's other fields and never rewrite the session's status.
    if session.get("unresolved") or escalations or out.unanswered:
        out.opening_line = "I'd like to discuss the questions left open in your demo."
    profile = session.get("profile") or {}
    seconds = {}
    for v in session.get("slides_visited", []):
        seconds[v.get("slide_id")] = round(seconds.get(v.get("slide_id"), 0) + float(v.get("seconds") or 0), 1)
    titles = {s["id"]: s.get("title", "") for s in (store.read_json(demo_id, "deck.json") or {}).get("slides", [])}
    return {**out.model_dump(), "customer_name": out.customer_name or profile.get("name", ""), "questions_asked": list(session.get("questions", [])),
            "unanswered": out.unanswered or escalations,
            "slides_visited": [{"slide_id": k, "title": titles.get(k, k), "seconds": v} for k, v in seconds.items()],
            "cta_result": session.get("cta") or "", "leads": [{"phone": l.get("phone"), "question": l.get("question")} for l in session.get("leads", [])],
            "minutes": session.get("minutes"), "model": model, "generated_at": time.time(), "transcript_lines": len(session.get("transcript", []))}
