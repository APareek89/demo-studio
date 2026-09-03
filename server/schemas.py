"""Pydantic schemas shared by the agents. These are the contracts between stages —
every stage's output is data the next stage consumes, so they are strict on purpose."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------- Understand (Gemini: visuals) ----------

class ShotG(BaseModel):
    start: float = Field(description="start time in seconds")
    end: float = Field(description="end time in seconds")
    description: str = Field(description="what is visible, one sentence")
    part: str = Field(description="which part of the product is shown, e.g. 'front', 'display', 'charging port', 'whole product'")
    feature: str = Field(description="the feature or benefit this footage could demonstrate, or 'none'")
    quality: int = Field(description="1-5 usability as demo footage: 5 = clear, well lit, product fills frame")
    on_screen_text: str = Field(default="", description="any text overlay visible, else empty")


class ShotsOut(BaseModel):
    shots: list[ShotG]
    summary: str = Field(description="one paragraph: what the video shows overall and its style")


class ImageG(BaseModel):
    index: int = Field(description="0-based index of the image in the order given")
    description: str
    angle: str = Field(description="e.g. front, rear, left side, three-quarter, detail, lifestyle, screenshot")
    parts: list[str] = Field(description="product parts visible")
    quality: int = Field(description="1-5 usability as demo visual")


class ImagesOut(BaseModel):
    images: list[ImageG]


# ---------- Understand (Claude: facts + brand) ----------

class FactSource(BaseModel):
    ref: str = Field(description="source id, e.g. src_ab12cd")
    locator: str = Field(default="", description="page number, section heading, or URL fragment")
    quote: str = Field(default="", description="short exact quote from the source that supports the claim")


class FactOut(BaseModel):
    kind: Literal["spec", "price", "offer", "policy", "feature", "claim", "availability", "other"]
    claim: str = Field(description="what the fact is about, short label, e.g. 'Battery warranty'")
    value: str = Field(description="the fact itself, exactly as the source states it, with units")
    source: FactSource
    confidence: float = Field(description="0-1: how directly the source states this")
    conditions: str = Field(default="", description="any condition attached, e.g. 'IDC test cycle', 'ex-showroom', 'select cities'")


class UnknownOut(BaseModel):
    question: str = Field(description="a question a real customer would ask that the sources do not answer")
    why_customers_ask: str = Field(default="")


class Brand(BaseModel):
    tone: str = Field(description="how the brand speaks, 1 sentence")
    voice_style: str = Field(description="how a spoken guide should sound, 1 sentence")
    dos: list[str]
    donts: list[str]
    persona_hint: str = Field(description="who the guide persona should be, 1 sentence")


class Product(BaseModel):
    name: str
    category: str = Field(description="e.g. electric scooter, laptop, SaaS analytics tool")
    summary: str = Field(description="2 sentences, factual")
    audience: str = Field(description="who buys this, 1 sentence")


class FactsOut(BaseModel):
    product: Product
    facts: list[FactOut]
    unknowns: list[UnknownOut]
    brand: Brand


# ---------- stored understanding (ids assigned by code) ----------

class Shot(ShotG):
    id: str
    source_id: str


class ImageInfo(BaseModel):
    id: str
    source_id: str
    description: str
    angle: str
    parts: list[str]
    quality: int


class Fact(FactOut):
    id: str
    approved: bool = True
    edited: bool = False


class Unknown(UnknownOut):
    id: str
    status: Literal["open", "resolved", "dismissed"] = "open"
    origin: str = "extraction"


class Understanding(BaseModel):
    product: Product
    shots: list[Shot] = []
    images: list[ImageInfo] = []
    facts: list[Fact] = []
    unknowns: list[Unknown] = []
    brand: Brand
    video_summaries: dict[str, str] = {}


# ---------- Plan (Claude) ----------

class Concern(BaseModel):
    topic: str = Field(description="short topic key, e.g. range, price, setup, security")
    why: str = Field(description="why a buyer of this product worries about it")
    fact_ids: list[str] = Field(description="facts that address it (may be empty)")


class SegmentPlan(BaseModel):
    id: str = Field(description="short slug id, e.g. 'range'")
    title: str
    goal: str = Field(description="what the customer should believe or understand after this segment")
    topic: str
    fact_ids: list[str]
    visual_refs: list[str] = Field(description="shot or image ids to use, best first")
    priority_topic: bool = Field(description="true if this addresses one of the top concerns")


class CTA(BaseModel):
    id: str
    label: str = Field(description="button text, 2-4 words")
    kind: Literal["book", "reserve", "buy", "contact", "trial", "link", "custom"]
    url: str = Field(default="")
    primary: bool = False
    when: str = Field(default="always", description="when to show it: always | after_price | end")


class VoiceBrief(BaseModel):
    persona_name: str
    persona_description: str = Field(description="2 sentences: who the guide is, how they behave")
    tone: str = Field(description="1 sentence")
    sample_line: str = Field(description="one natural greeting line in the persona's voice, ~25 words")
    suggested_voice: str = Field(description="one of: Sulafat, Aoede, Leda, Despina, Kore, Achernar, Zephyr")
    language: str = "en-IN"


class VisualGap(BaseModel):
    what: str = Field(description="what visual is missing, e.g. 'the charging port'")
    why: str
    suggestion: str = Field(description="what to upload, concretely")


class IntakeChip(BaseModel):
    key: str
    label: str


class Intake(BaseModel):
    q1: str = Field(description="first spoken question: name + why interested, in the persona's voice")
    q2: str = Field(description="second spoken question: anything specific to focus on, or get going")
    chips: list[IntakeChip] = Field(description="4-7 focus topics the customer might pick, matching segment topics")


class Plan(BaseModel):
    customer_persona: str = Field(description="who is watching this demo and what they are deciding, 2 sentences")
    concerns: list[Concern]
    segments: list[SegmentPlan]
    ctas: list[CTA]
    voice: VoiceBrief
    visual_gaps: list[VisualGap]
    intake: Intake
    notes: str = Field(default="", description="anything the planner wants the human to know")


# ---------- Author (Claude) ----------

class Visual(BaseModel):
    kind: Literal["shot", "image", "none"]
    ref: str = Field(default="", description="shot or image id")
    focus: str = Field(default="", description="what to draw the eye to, 2-5 words, shown as a label")


class LineOut(BaseModel):
    text: str = Field(description="1-2 spoken sentences, natural, no markdown")
    visual: Visual
    fact_ids: list[str] = Field(description="every fact this line relies on; empty only for pure transition/opinion lines")
    card: Literal["none", "facts", "price", "summary"] = "none"


class SegmentOut(BaseModel):
    id: str
    title: str
    topic: str
    lines: list[LineOut]
    checkin: str = Field(description="the question the guide asks after this segment, or empty for the first segment")
    deeper: list[LineOut] = Field(description="2-3 lines for 'tell me more', grounded")


class ScriptOut(BaseModel):
    segments: list[SegmentOut]
    closing: list[LineOut] = Field(description="2-3 lines that summarise and offer the CTAs")
    intake_q1: str
    intake_q2: str


class Line(LineOut):
    id: str
    unverified: bool = False
    audio: Optional[str] = None


class Segment(BaseModel):
    id: str
    title: str
    topic: str
    lines: list[Line]
    checkin: str = ""
    checkin_audio: Optional[str] = None
    deeper: list[Line] = []


class Script(BaseModel):
    segments: list[Segment]
    closing: list[Line]
    intake_q1: str
    intake_q2: str
    intake_audio: dict[str, Optional[str]] = {}
    issues: list[str] = []
    version: int = 1


# ---------- Runtime Q&A ----------

class QAOut(BaseModel):
    answer: str = Field(description="1-3 spoken sentences")
    fact_ids: list[str] = Field(description="facts used; MUST be empty if the sources do not answer the question")
    visual_ref: str = Field(default="", description="shot or image id that best shows it, or empty")
    escalate: str = Field(default="", description="what a human should follow up on, or empty")
    topic: str = ""
    cta: str = Field(default="", description="cta id if the customer is asking to take that action, else empty")
    answered: bool = Field(description="true only if the answer is fully supported by the cited facts")


class RehearsalQuestions(BaseModel):
    questions: list[str] = Field(description="questions a real prospective buyer would ask, varied: specs, price, comparisons, ownership, edge cases")


# ---------- Align agent ----------

class AlignAction(BaseModel):
    type: Literal["revise", "approve", "request_upload", "set_ctas", "set_voice", "edit_fact", "remove_fact", "build", "answer", "resolve_unknown"]
    stage: Optional[Literal["understand", "plan", "author"]] = Field(default=None, description="for revise")
    card: Optional[Literal["visuals", "facts", "persona", "ctas"]] = Field(default=None, description="for approve")
    instruction: str = Field(default="", description="for revise: precise instruction to the stage")
    ctas: list[CTA] = Field(default_factory=list, description="for set_ctas: the full new list")
    voice_name: str = Field(default="", description="for set_voice")
    persona_description: str = Field(default="", description="for set_voice")
    tone: str = Field(default="", description="for set_voice")
    fact_id: str = Field(default="", description="for edit_fact / remove_fact")
    fact_value: str = Field(default="", description="for edit_fact: the corrected value")
    fact_claim: str = Field(default="", description="for edit_fact: corrected label, optional")
    unknown_id: str = Field(default="", description="for resolve_unknown")
    upload_kind: str = Field(default="", description="for request_upload: image | video | document")
    reason: str = Field(default="", description="for request_upload")


class AlignOut(BaseModel):
    reply: str = Field(description="what to say to the user, plain text, 1-4 sentences, no markdown")
    actions: list[AlignAction] = Field(description="zero or more actions; use 'answer' alone when nothing should change")
