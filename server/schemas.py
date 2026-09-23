"""Pydantic schemas shared by the agents. These are the contracts between stages —
every stage's output is data the next stage consumes, so they are strict on purpose."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# ---------- Understand (Gemini: visuals) ----------

# Describe one visible interval in a video before the app assigns its identity.
# Input: model-reported start/end, subject, description and quality. Output: a validated shot record.
# Linked: server/agents/understand.py:run asks the vision model for ShotsOut containing these records.
class ShotG(BaseModel):
    start: float = Field(description="start time in seconds")
    end: float = Field(description="end time in seconds")
    description: str = Field(description="what is visible, one sentence")
    part: str = Field(description="which part of the product is shown, e.g. 'front', 'display', 'charging port', 'whole product'")
    feature: str = Field(description="the feature or benefit this footage could demonstrate, or 'none'")
    quality: int = Field(description="1-5 usability as demo footage: 5 = clear, well lit, product fills frame")
    on_screen_text: str = Field(default="", description="any text overlay visible, else empty")


# Collect the vision model result for one video.
# Input: shot records and an overall summary. Output: the validated response used to index the video.
# Linked: server/agents/understand.py:run assigns shot IDs and stores the summary.
class ShotsOut(BaseModel):
    shots: list[ShotG]
    summary: str = Field(description="one paragraph: what the video shows overall and its style")


# Describe one visible product part and where it is located in an image.
# Input: part name, 0–1000 bounding box and confidence. Output: a validated model part record.
# Linked: server/agents/understand.py:_part converts its coordinates for server/agents/deck.py:place_callouts.
class PartG(BaseModel):
    name: str = Field(description="one distinct product part that is visible, e.g. 'headlamp', 'touchscreen', 'boot', 'alloy wheel', 'charging port'")
    box_2d: list[int] = Field(description="tight bounding box [ymin, xmin, ymax, xmax] on a 0-1000 grid of this image")
    confidence: float = Field(description="0-1: how sure you are that this part is visible and the box is tight around it")


# Describe the pixels of one supplied image, before giving it a persistent image ID.
# Input: batch index, visible parts, angle and quality. Output: a validated vision description.
# Linked: server/agents/understand.py:run associates this batch index with the original uploaded source.
class ImageG(BaseModel):
    index: int = Field(description="0-based index of the image in the order given")
    description: str
    angle: str = Field(description="e.g. front, rear, left side, three-quarter, detail, lifestyle, screenshot")
    parts: list[PartG] = Field(description="every distinct product part visible, each with its box; empty for lifestyle or abstract images")
    quality: int = Field(description="1-5 usability as demo visual")
    full_product: bool = Field(default=False, description="true only when the whole product is in frame (a hero-style view); false for a detail, crop or interior")


# Collect image descriptions from one vision-model batch.
# Input: a list of ImageG records. Output: the validated image-tagging response.
# Linked: server/agents/understand.py:run uses this response to create understanding.images.
class ImagesOut(BaseModel):
    images: list[ImageG]


# ---------- Understand (Claude: facts + brand) ----------

# Keep the location and exact wording that support a factual claim.
# Input: source ID, page/time locator and quote. Output: a validated evidence reference.
# Linked: server/agents/understand.py:run extracts it; server/store.py:edit_fact validates later corrections.
class FactSource(BaseModel):
    ref: str = Field(description="source id, e.g. src_ab12cd")
    locator: str = Field(default="", description="page number, section heading, or URL fragment")
    quote: str = Field(default="", description="short exact quote from the source that supports the claim")


# Define a product assertion before the app assigns a stable fact ID.
# Input: claim, value, kind, conditions, source and truth category. Output: structured extracted evidence.
# Linked: server/agents/understand.py:run passes these assertions to server/knowledge.py:reconcile.
class FactOut(BaseModel):
    kind: Literal["spec", "price", "offer", "policy", "feature", "claim", "availability", "other"]
    claim: str = Field(description="what the fact is about, short label, e.g. 'Battery warranty'")
    value: str = Field(description="the fact itself, exactly as the source states it, with units")
    source: FactSource
    confidence: float = Field(description="0-1: how directly the source states this")
    conditions: str = Field(default="", description="all stated applicability: generation, trim, engine/fuel/mode, transmission, market/date, measurement/test basis, price basis and offer restrictions; do not infer missing conditions")
    scope: dict[str, str] = Field(default_factory=dict, description="Only explicitly stated applicability: model, generation, model_year, market, variant, powertrain, transmission, test_basis, price_basis, effective_from, effective_to. Missing means unknown; do not infer. Dates ISO YYYY-MM-DD when stated.")
    truth: Literal["certified", "modeled", "observed", "contractual", "stated"] = Field(default="stated", description="stated = ordinary source specifications/features; certified = explicitly reported certification or named test/rating result, retaining basis and scope (an official source or measurement method alone is insufficient); modeled = source estimate with assumptions; observed = reported measurement in use; contractual = written terms")


# Record a customer question the supplied evidence cannot answer.
# Input: question, reason, category and suggested document. Output: a structured knowledge gap.
# Linked: server/agents/understand.py:run stores these gaps for server/agents/plan.py:run.
class UnknownOut(BaseModel):
    question: str = Field(description="a question a real customer would ask that the sources do not answer")
    why_customers_ask: str = Field(default="")
    category: Literal["pricing", "finance", "insurance", "warranty_service", "features", "availability", "comparison", "usage", "other"] = Field(default="other")
    suggested_document: str = Field(default="", description="the document the brand should upload to answer it, e.g. 'EMI schedule / bank tie-up sheet', 'insurance partner terms', 'spec sheet PDF', 'FAQ page'")


# Describe the brand speaking style and its content boundaries.
# Input: tone, voice style, allowed/disallowed behaviors and persona hint. Output: a brand brief.
# Linked: server/agents/plan.py:run and server/agents/author.py:run include this brief in their prompts.
class Brand(BaseModel):
    tone: str = Field(description="how the brand speaks, 1 sentence")
    voice_style: str = Field(description="how a spoken guide should sound, 1 sentence")
    dos: list[str]
    donts: list[str]
    persona_hint: str = Field(description="who the guide persona should be, 1 sentence")


# Identify the product and its general audience without writing the demo yet.
# Input: name, category, factual summary and audience. Output: a validated product description.
# Linked: server/agents/understand.py:run stores it; server/agents/plan.py:run uses it to frame the story.
class Product(BaseModel):
    name: str
    category: str = Field(description="e.g. electric scooter, laptop, SaaS analytics tool")
    summary: str = Field(description="2 sentences, factual")
    audience: str = Field(description="who buys this, 1 sentence")


# Group a document-reading result into product facts, open questions and brand context.
# Input: structured output from a fact-reading model call. Output: a validated extraction batch.
# Linked: server/agents/understand.py:run merges batches and reconciles their assertion identities.
class FactsOut(BaseModel):
    product: Product
    facts: list[FactOut]
    unknowns: list[UnknownOut]
    brand: Brand


# Keep one competitor product and its sourced assertions together.
# Input: competitor name and facts. Output: one validated competitor group, separate from own-product facts.
# Linked: server/agents/understand.py:run attaches the owning competitor source when saving these records.
class CompetitorOut(BaseModel):
    name: str = Field(description="competitor product name as the site calls it")
    facts: list[FactOut] = Field(description="only figures stated on that official page, with quotes")


# Collect competitor groups returned by the competitor document reader.
# Input: a list of CompetitorOut records. Output: the validated competitor extraction response.
# Linked: server/agents/understand.py:run writes the groups under understanding.competitors.
class CompetitorsOut(BaseModel):
    competitors: list[CompetitorOut]


# ---------- stored understanding (ids assigned by code) ----------

# Add app-owned identity to a video interval described by the vision model.
# Input: ShotG fields plus shot ID and source ID. Output: the stored shot shape.
# Linked: server/agents/bundle.py:build resolves the source and time range into a playable media reference.
class Shot(ShotG):
    id: str
    source_id: str


# Store the identified image and its visible-part descriptions/boxes.
# Input: image ID, source ID, description, angle, parts and quality. Output: an image catalogue record.
# Linked: server/agents/plan.py:run chooses IDs; server/agents/deck.py:build uses tags to select slide images.
class ImageInfo(BaseModel):
    id: str
    source_id: str
    description: str
    angle: str
    parts: list[Any]  # slides-v1: [{name, box:{x,y,w,h} in 0-1, confidence}]; older demos: plain names
    quality: int
    full_product: bool = False


# Add approval, editing and knowledge metadata to an extracted assertion.
# Input: FactOut fields plus ID/review metadata. Output: the stored fact shape.
# Linked: server/store.py:edit_fact validates candidates; server/agents/bundle.py:build filters approved facts.
class Fact(FactOut):
    id: str
    approved: bool = True
    edited: bool = False
    knowledge: dict[str, Any] = Field(default_factory=dict)


# Add app-owned identity and resolution status to a missing-information question.
# Input: UnknownOut fields plus ID, status and origin. Output: the saved gap record.
# Linked: server/orchestrator.py:apply_actions can mark a reviewed unknown resolved.
class Unknown(UnknownOut):
    id: str
    status: Literal["open", "resolved", "dismissed"] = "open"
    origin: str = "extraction"


# Define the main knowledge and media catalogue shared by later build steps.
# Input: product, facts, images/shots, unknowns, brand and competitor groups. Output: validated understanding data.
# Linked: server/agents/understand.py:run writes it; server/agents/plan.py:run and author.py:run read it.
class Understanding(BaseModel):
    product: Product
    shots: list[Shot] = []
    images: list[ImageInfo] = []
    facts: list[Fact] = []
    unknowns: list[Unknown] = []
    brand: Brand
    video_summaries: dict[str, str] = {}
    competitors: list[dict] = []
    knowledge: dict[str, Any] = Field(default_factory=dict)


# ---------- Plan (Claude) ----------

# Describe a likely buyer concern and the evidence relevant to it.
# Input: concern fields and related fact IDs. Output: one structured concern in the plan.
# Linked: server/agents/plan.py:run creates it; server/agents/author.py:run receives the planned concerns.
class Concern(BaseModel):
    topic: str = Field(description="short topic key, e.g. range, price, setup, security")
    why: str = Field(description="why a buyer of this product worries about it")
    fact_ids: list[str] = Field(description="facts that address it (may be empty)")


# Describe one supported reason for a buyer to explore the product.
# Input: selling-point identity, wording and cited facts. Output: a structured value point in the plan.
# Linked: server/agents/plan.py:run selects these; server/agents/author.py:run turns them into speech.
class USP(BaseModel):
    id: str = Field(description="short slug, e.g. 'usp-warranty'")
    name: str = Field(description="the differentiated value, 3-8 words")
    why_it_matters: str = Field(description="one concrete sentence of supported relevance; a choice or fit-check is valid when the source does not demonstrate a customer outcome")
    fact_ids: list[str] = Field(description="approved facts supporting the stated value and scope; no invented benefit or comparison; with no facts, describe the unresolved choice rather than asserting a product advantage")


# Represent an optional clarification suggestion for a customer state.
# Input: state/question fields. Output: a suggestion, not an instruction to ask every question automatically.
# Linked: server/agents/plan.py:run writes these suggestions; the player owns actual conversation waits.
class StateQuestion(BaseModel):
    state: Literal["unknown", "stated_want", "stated_need"]
    question: str = Field(description="optional clarification for an unclear customer request; never an automatic second intake question")


# Describe one story stop before its final spoken sentences exist.
# Input: role, goal, facts, topic and ordered visual_refs. Output: the planned segment contract.
# Linked: server/agents/plan.py:run writes it; server/agents/author.py:run uses it as the writing brief.
class SegmentPlan(BaseModel):
    id: str = Field(description="short slug id, e.g. 'range'")
    title: str
    role: Literal["intro", "outcome", "proof", "features", "establish"] = Field(description="intro = brief overview, no decision frame; outcome = three things to remember; proof = guided discovery; features = one 'a few more things' block; establish = assumptions, terms and open questions")
    goal: str = Field(description="what the customer should believe or understand after this segment")
    outcome: str = Field(description="supported customer result or decision/fit-check explored, 3-8 words; no promised outcome inferred from a specification (empty for intro)")
    topic: str
    fact_ids: list[str]
    usp_ids: list[str] = Field(default_factory=list, description="USPs this segment covers")
    visual_refs: list[str] = Field(description="shot or image ids to use, best first")
    priority_topic: bool = Field(description="true if this addresses one of the top concerns")


# Define a buyer action such as a test-drive request, contact or verified link.
# Input: ID, label, kind, URL and display intent. Output: one structured call to action.
# Linked: server/agents/plan.py:_ground_action_ctas checks links; server/agents/bundle.py:build publishes CTAs.
class CTA(BaseModel):
    id: str
    label: str = Field(description="button text, 2-4 words")
    kind: Literal["book", "reserve", "buy", "contact", "trial", "link", "custom"]
    url: str = Field(default="")
    primary: bool = False
    when: str = Field(default="always", description="when to show it: always | after_price | end")


# Describe the guide persona and a short sample line for review.
# Input: persona identity/description, tone, suggested voice and language. Output: the voice brief in Plan.
# Linked: server/orchestrator.py:_persona_sample prepares previews; server/agents/voice.py renders selected speech.
class VoiceBrief(BaseModel):
    persona_name: str
    persona_description: str = Field(description="2 sentences: who the guide is, how they behave")
    tone: str = Field(description="1 sentence")
    sample_line: str = Field(description="one natural greeting line in the persona's voice, ~25 words")
    suggested_voice: str = Field(description="one of: Sulafat, Aoede, Leda, Despina, Kore, Achernar, Zephyr")
    language: str = "en-IN"


# Explain which useful picture is missing and what the human could upload.
# Input: missing subject, reason and concrete suggestion. Output: one gap in the plan.
# Linked: server/agents/plan.py:run reports gaps instead of inventing unavailable source images.
class VisualGap(BaseModel):
    what: str = Field(description="what visual is missing, e.g. 'the charging port'")
    why: str
    suggestion: str = Field(description="what to upload, concretely")


# Define a suggested focus topic the customer can select.
# Input: topic key and visible label. Output: one selectable intake choice.
# Linked: server/agents/bundle.py:build publishes Plan intake chips for web/player/player.js.
class IntakeChip(BaseModel):
    key: str
    label: str


# Define the opening context question and suggested focus choices.
# Input: one useful question, legacy second-question field and chips. Output: planned intake content.
# Linked: server/agents/plan.py:run clears q2; server/agents/author.py:run writes the final spoken intake.
class Intake(BaseModel):
    q1: str = Field(description="warm brand/product greeting plus ONE useful context question, easy to decline; do not also ask for a name")
    q2: str = Field(description="empty string; retained for older bundles, never a second intake question")
    chips: list[IntakeChip] = Field(description="4-7 focus topics the customer might pick, matching segment topics")


# Define the Coach's category story, its approved support and missing evidence.
# The Planner maps these reviewed stops to segments; the Author writes speech.
class PlaybookStop(BaseModel):
    id: str = Field(description="slug, e.g. 'powertrain'")
    label: str = Field(description="2-6 everyday words, the thing itself, no numbers")
    kind: Literal["fundamental", "differentiator", "delighter", "hygiene", "ownership"]
    why_here: str = Field(description="one sentence: why a trained salesperson covers this at this point")
    fact_ids: list[str] = Field(description="approved registry ids that support this stop")
    picture_ids: list[str] = Field(default_factory=list, description="image/shot ids that literally show this stop")
    must_cover: bool = True
    gaps: list[str] = Field(default_factory=list, description="what the library expects here that the registry lacks")


class PlaybookUSP(BaseModel):
    id: str
    name: str = Field(description="3-8 everyday words, a promise in the buyer's language, no digits, units or model codes")
    fact_ids: list[str]
    stop_id: str


class PlaybookObjection(BaseModel):
    objection: str
    fact_ids: list[str] = Field(default_factory=list)
    status: Literal["supported", "unknown"]


class EvidenceGap(BaseModel):
    what: str
    why_it_matters: str
    suggested_source: str


class Playbook(BaseModel):
    category: str
    category_source: Literal["library", "inferred"]
    stops: list[PlaybookStop]
    usps: list[PlaybookUSP] = Field(description="exactly three")
    objections: list[PlaybookObjection] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    notes: str = ""


# Define the complete story brief, chosen evidence/images and reviewable buyer actions.
# Input: structured Planner response. Output: a validated Plan, before its post-processing and save.
# Linked: server/agents/plan.py:run saves plan.json; server/agents/author.py:run receives its editorial intent.
class Plan(BaseModel):
    customer_persona: str = Field(description="general intended audience, 2 sentences; no invented individual distance, budget, location or household")
    decision_frame: str = Field(description="fit summary at the END: the strongest supported fit and what remains to verify; not an opening decision frame")
    takeaway: str = Field(description="the ONE sentence the buyer should be able to repeat after the demo")
    primary_outcome: str = Field(description="one supported customer result or buying decision the demo explores; do not invent a performance or safety guarantee")
    supporting_outcomes: list[str] = Field(description="at most two")
    concerns: list[Concern]
    usps: list[USP] = Field(description="exactly three differentiated value points, each tied to facts")
    segments: list[SegmentPlan]
    ctas: list[CTA]
    voice: VoiceBrief
    visual_gaps: list[VisualGap]
    intake: Intake
    state_questions: list[StateQuestion] = Field(description="optional clarification suggestions, not an automatic discovery sequence")
    do_not_recommend_if: str = Field(description="P09: the honest condition under which the guide would not recommend this product, 1 sentence")
    advance: str = Field(description="P10: the next buyer action that resolves the largest remaining uncertainty, with an owner and trigger — references one CTA by label")
    notes: str = Field(default="", description="anything the planner wants the human to know")


# ---------- Author (Claude) ----------

# Attach a visual identity and attention cue to a spoken line.
# Input: image/shot/none, reference ID and focus label. Output: a line visual reference, not a media URL.
# Linked: server/agents/author.py:run assigns it; server/agents/bundle.py:build resolves source paths later.
class Visual(BaseModel):
    kind: Literal["shot", "image", "none"]
    ref: str = Field(default="", description="shot or image id")
    focus: str = Field(default="", description="what to draw the eye to, 2-5 words, shown as a label")


# Define one spoken thought with evidence, visual choice and subtle delivery guidance.
# Input: text, step, visual, fact IDs, card and delivery. Output: a model-authored line without app/audio IDs.
# Linked: server/agents/author.py:validate checks lines; server/agents/voice.py later records approved text.
class LineOut(BaseModel):
    text: str = Field(description="one natural spoken thought, 1-2 short sentences; the whole batch fits 10-20 seconds, no padding, lists or questions")
    step: Literal["frame", "say", "show", "translate", "confirm", "establish", "advance", "other"] = Field(default="other", description="proof-block step; confirm is legacy compatibility only, new questions go in SegmentOut.checkin")
    visual: Visual
    fact_ids: list[str] = Field(description="every fact this line relies on; empty only for pure transition/opinion lines")
    card: Literal["none", "facts", "price", "summary", "contrast"] = "none"
    delivery: dict[str, Any] = Field(default_factory=dict, description="Subtle delivery metadata only: tone warm/upbeat/calm/reassuring, optional pace 0.9–1.08. Never put emotion tags or SSML in text.")


# Group a short narration batch with its optional check-in and deeper explanation.
# Input: segment identity/role/topic, lines, check-in and deeper lines. Output: one authored story segment.
# Linked: server/agents/author.py:run checks pacing and question placement before saving it.
class SegmentOut(BaseModel):
    id: str
    title: str
    role: Literal["intro", "outcome", "proof", "features", "establish"]
    topic: str
    outcome: str = ""
    usp_ids: list[str] = Field(default_factory=list)
    lines: list[LineOut]
    checkin: str = Field(description="Optional ONE short confirmation of enough detail or readiness, with an explicit wait: yes continues, no opens more detail. Example: 'Is that enough detail for now?' Never opt into more detail or ask an open/either-or question. No claims or assumed customer details. Leave empty when narration should continue; empty for intro/outcome. Not required after every proof/features section.")
    deeper: list[LineOut] = Field(description="2-3 lines for 'tell me more', grounded")


# Collect the Author model response before app IDs, timing and audio are attached.
# Input: overview, segments, closing and intake words. Output: the validated draft response shape.
# Linked: server/agents/author.py:_assign_ids names lines and moves overview into runtime_overview.
class ScriptOut(BaseModel):
    overview: Optional[LineOut] = Field(default=None, description="Standalone 23–28 word, 10–15 second opening for Explore while its route is planned. Lead with sourced standout features and their supported relevance, retain variant qualifiers, cite facts. No greeting/question/spec list; not a segment.")
    segments: list[SegmentOut]
    closing: list[LineOut] = Field(description="two lines, at most 45 words total: fit summary then next step naming the CTA; statements, no questions")
    intake_q1: str = Field(description="warm greeting plus ONE useful context question; no name request stacked with it")
    intake_q2: str = Field(description="empty string; no second intake")


# Add stable app identity, verification status and optional recording to an authored line.
# Input: LineOut fields plus ID/unverified/audio. Output: the stored line shape.
# Linked: server/agents/voice.py:render_script fills audio; server/agents/bundle.py:build joins by line ID.
class Line(LineOut):
    id: str
    unverified: bool = False
    audio: Optional[str] = None


# Define a stored narration segment after IDs and review flags are assigned.
# Input: segment details, saved lines, check-in/audio and deeper material. Output: the stored segment shape.
# Linked: server/agents/deck.py:build makes its slide; server/agents/voice.py:render_script records its speech.
class Segment(BaseModel):
    id: str
    title: str
    role: Literal["intro", "outcome", "proof", "features", "establish"] = "proof"
    topic: str
    outcome: str = ""
    usp_ids: list[str] = []
    lines: list[Line]
    checkin: str = ""
    checkin_audio: Optional[str] = None
    deeper: list[Line] = []


# Check the core saved script shape, including review issues and recording links.
# Input: segments, closing, intake/audio, issues and version. Output: a validated script model.
# Linked: server/agents/author.py:run checks this shape but saves the original dictionary with extra runtime fields.
class Script(BaseModel):
    segments: list[Segment]
    closing: list[Line]
    intake_q1: str
    intake_q2: str
    intake_audio: dict[str, Optional[str]] = {}
    issues: list[str] = []
    version: int = 1


# ---------- Deck (one script segment = one slide) ----------

# Describe one short on-screen label and when it should appear.
# Input: text, citations, part/placement coordinates and reveal_on_line. Output: a slide callout record.
# Linked: server/agents/deck.py:place_callouts chooses overlay/panel; web/slide.js reveals labels during narration.
class Callout(BaseModel):
    id: str
    text: str
    fact_ids: list[str] = []
    part: str = ""
    placement: Literal["overlay", "panel"] = "panel"
    anchor: Optional[dict] = None      # {x, y} in 0-1: the part's centre
    label_pos: Optional[dict] = None   # {x, y} in 0-1: the chip's top-left, outside the part box
    part_box: Optional[dict] = None    # {x, y, w, h} in 0-1
    reveal_on_line: int = 0
    confidence: float = 0.0


# Define one slide with its picture, narration, evidence and interaction details.
# Input: slide/segment IDs, image_id, lines, callouts and check-in/deeper data. Output: stored slide structure.
# Linked: server/agents/deck.py:build creates it; server/agents/bundle.py:build attaches URLs and recordings.
class Slide(BaseModel):
    id: str
    segment_id: Optional[str] = None
    kind: Literal["hero_open", "intro", "outcome", "proof", "features", "establish", "closing", "hero_close"]
    title: str
    topics: list[str] = []
    fact_ids: list[str] = []
    image_id: Optional[str] = None
    image_reason: str = ""
    motion: Literal["zoom_in", "pan_left", "none"] = "zoom_in"
    callouts: list[Callout] = []
    lines: list[dict] = []       # {id, text, fact_ids, step}; audio joins at bundle time by id
    checkin: str = ""
    deeper: list[dict] = []
    usp_ids: list[str] = []
    priority: bool = False
    role: str = "proof"


# Collect the slides and record which script/version produced them.
# Input: hero media, slide list, versions, method and issues. Output: a validated deck artifact.
# Linked: server/agents/deck.py:build saves deck.json; server/agents/bundle.py:build publishes its structure.
class Deck(BaseModel):
    hero_image: Optional[str] = None
    intro_video: Optional[str] = None
    slides: list[Slide]
    version: int = 1
    script_version: Optional[int] = None
    method: str = ""
    issues: list[str] = []


# ---------- Runtime: pitch planner ----------

# Describe one selected step in a personalized demo route.
# Input: selected segment and routing guidance. Output: one step proposed by the pitch planner.
# Linked: server/agents/pitch.py:plan_pitch creates routes; web/player/player.js maps them to reviewed slides.
class RouteStep(BaseModel):
    segment_id: str = Field(description="a segment id from the library (proof, features or establish only)")
    bridge: str = Field(default="", description="ONE personalised sentence spoken before the segment, in the buyer's own nouns and numbers (P07); empty if nothing personal to add")
    bridge_fact_ids: list[str] = Field(default_factory=list, description="facts the bridge relies on; a bridge with a number and no fact id will be dropped")


# Keep the older personalized proof-batch response shape available.
# Input: spoken text, citations and a visual reference. Output: a legacy batch; current live-route prompts request none.
# Linked: server/agents/pitch.py:plan_pitch uses PitchPlan; current personalized speech uses selected segments.
class CustomBatch(BaseModel):
    text: str = Field(description="one natural spoken thought for THIS buyer, ≤38 words (about 20 seconds), no questions; personal context only from their words, product figures cite fact ids")
    fact_ids: list[str] = Field(default_factory=list)
    visual_ref: str = Field(default="", description="the image or shot id that shows what this batch talks about")


# Propose contextual delivery for a selected reviewed segment.
# Input: segment identity, customer quote and replacement lines. Output: a proposed personalized segment.
# Linked: server/agents/pitch.py:plan_pitch validates replacements before web/player/player.js uses them.
class PersonalizedSegment(BaseModel):
    segment_id: str
    customer_quote: str = Field(default="", description="At most eight consecutive words copied exactly from this customer's why/followup, selecting the need relevant to this segment; no invented context")
    lines: list[LineOut] = Field(default_factory=list, description="Compose a focused replacement using complete reviewed factual lines from this segment's main/deeper speech. Preserve exact factual wording and all fact_ids; reorder/select for this customer's need. No new factual paraphrase or appended repeat.")


# Describe a customer-specific route and any reviewed-line personalization.
# Input: pitch model response with route, rationale, buyer action and replacements. Output: a validated proposal.
# Linked: server/agents/pitch.py:plan_pitch checks it; server/runtime_graph.py:explore requests it during a demo.
class PitchPlan(BaseModel):
    customer_state: Literal["unknown", "stated_want", "stated_need"]
    decision_frame: str = Field(description="Brief acknowledgement metadata, at most twelve words, using this buyer's actual words; no specs, assumed details or question. Live Explore does not narrate it after the overview.")
    follow_up_question: str = Field(description="always empty; the buyer already had one intake question")
    primary_outcome: str
    focus_topics: list[str] = Field(description="segment topics this buyer cares about, from their words (any language)")
    route: list[RouteStep] = Field(description="ordered proof/establish segments: primary outcome first, ≤2 supporting, then establish; 3-6 steps")
    skipped: list[str] = Field(default_factory=list, description="segment ids deliberately left out and why, as 'id: reason'")
    usp_order: list[str] = Field(default_factory=list, description="usp ids in the order they will be covered")
    advance: str = Field(description="the closing advance for this buyer (P10), naming the CTA label")
    advance_cta: str = Field(default="", description="cta id")
    custom_batches: list[CustomBatch] = Field(default_factory=list, description="Legacy recorded-delivery proof batches only. For LIVE ROUTE DELIVERY always return []; the selected slide speech is personalized in place.")
    personalized_segments: list[PersonalizedSegment] = Field(default_factory=list, description="For LIVE ROUTE DELIVERY with customer context, provide a reviewed-line replacement for each selected unseen route segment. Only the first segment may have a short verbatim customer_quote. Preserve factual sentences and citations exactly; invalid or omitted replacements use explicitly marked reviewed-route fallback speech.")
    do_not_recommend_if: str = Field(default="")


# ---------- Runtime Q&A ----------

# Define the answer/clarification shape used by the legacy QA adapter.
# Input: response text, citations, visual reference, topic and follow-up fields. Output: a structured QA proposal.
# Linked: server/agents/qa.py:answer validates it; server/agents/faq.py:run uses that adapter to prepare answers.
class QAOut(BaseModel):
    answer: str = Field(description="1-3 short spoken sentences; when clarification is needed, only the clarifying question, no product answer yet")
    fact_ids: list[str] = Field(description="facts used; MUST be empty if the sources do not answer the question")
    visual_ref: str = Field(default="", description="shot or image id that best shows it, or empty")
    escalate: str = Field(default="", description="what a human should follow up on, or empty")
    topic: str = ""
    cta: str = Field(default="", description="cta id if the customer is asking to take that action, else empty")
    answered: bool = Field(description="true for a fully supported answer or a question-only clarification turn; false for an unsupported factual answer")
    clarifying_question: str = Field(default="", description="ONE short question only when ambiguous intent changes the answer; no claims, figures or assumed personal details; answer it before giving product facts; otherwise empty")


# Collect likely customer questions generated from product and plan context.
# Input: model-written question list. Output: validated question strings.
# Linked: server/agents/rehearsal.py:generate_questions also supplies questions to server/agents/faq.py:run.
class RehearsalQuestions(BaseModel):
    questions: list[str] = Field(description="questions a real prospective buyer would ask, varied: specs, price, comparisons, ownership, edge cases")


# Describe one criterion in the build-time script review.
# Input: criterion, score and explanation. Output: a structured review item, not a live-session KPI.
# Linked: server/agents/rehearsal.py:score_script asks for these items as part of Scorecard.
class ScoreItem(BaseModel):
    criterion: str
    score: int = Field(description="0 absent, 1 partial, 2 clear and evidenced")
    note: str = Field(description="one line: why, quoting the script where useful")


# Group the script-review criteria, total and suggested improvements.
# Input: model review items, total and weakest areas. Output: the structured build-time scorecard.
# Linked: server/agents/rehearsal.py:score_script returns it for rehearsal.json; it does not measure human speech.
class Scorecard(BaseModel):
    scores: list[ScoreItem] = Field(description="exactly the 10 criteria in the given order")
    total: int
    weakest: list[str] = Field(description="the 2-3 criteria to fix first, with a concrete suggestion each")


# ---------- Align agent ----------

# Describe one proposed edit, approval or request from the review conversation.
# Input: action type and its relevant fields. Output: a structured action; validation/execution happens later.
# Linked: server/agents/align.py:respond proposes it; server/orchestrator.py:apply_actions applies supported actions.
class AlignAction(BaseModel):
    type: Literal["revise", "approve", "request_upload", "set_ctas", "set_voice", "edit_fact", "remove_fact", "build", "answer", "resolve_unknown"]
    stage: Optional[Literal["understand", "coach", "plan", "author", "deck", "faq"]] = Field(default=None, description="for revise")
    card: Optional[Literal["visuals", "facts", "script", "faq", "persona", "ctas"]] = Field(default=None, description="for approve")
    instruction: str = Field(default="", description="for revise: precise instruction to the stage")
    ctas: list[CTA] = Field(default_factory=list, description="for set_ctas: the full new list")
    voice_name: str = Field(default="", description="for set_voice")
    persona_description: str = Field(default="", description="for set_voice")
    tone: str = Field(default="", description="for set_voice")
    fact_id: str = Field(default="", description="for edit_fact / remove_fact")
    fact_value: str = Field(default="", description="for edit_fact: the corrected value")
    fact_claim: str = Field(default="", description="for edit_fact: corrected label, optional")
    fact_conditions: Optional[str] = Field(default=None, description="for edit_fact: corrected applicability conditions; null means unchanged")
    fact_truth: Optional[Literal["certified", "modeled", "observed", "contractual", "stated"]] = Field(default=None, description="for edit_fact: corrected truth type; null means unchanged")
    fact_source: Optional[FactSource] = Field(default=None, description="for edit_fact: corrected source id, locator and exact quote; null means unchanged")
    unknown_id: str = Field(default="", description="for resolve_unknown")
    upload_kind: str = Field(default="", description="for request_upload: image | video | document")
    reason: str = Field(default="", description="for request_upload")


# Keep the review agent reply separate from the changes it proposes.
# Input: reply text and action list. Output: the validated review response.
# Linked: server/agents/align.py:respond returns this; server/orchestrator.py:respond records and applies it.
class AlignOut(BaseModel):
    reply: str = Field(description="what to say to the user, plain text, 1-4 sentences, no markdown")
    actions: list[AlignAction] = Field(description="zero or more actions; use 'answer' alone when nothing should change")
