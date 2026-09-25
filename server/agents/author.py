"""Author stage: write grounded, conversational batches within the reviewed word budgets."""
from __future__ import annotations

import json
import re

from .. import schemas, store
from ..llm import claude
from . import plain_terms, speech_style, visuals
from .principles import AUTHOR_CRAFT, PRINCIPLES, SIGNPOSTS, TRANSLATION_LADDER, audience_instruction, fact_context, language_instruction

# Brief the writer on grounded dialogue, per-line visuals and non-question closing statements.
# server/schemas.py:ScriptOut describes the result; visuals.py:align separately audits image coverage afterward.
AUTHOR_SYSTEM = """You are writing what a helpful human guide actually says to one visitor while showing a product.
The visitor should hear a person addressing them, not an announcer describing a catalogue. Use active, direct
spoken sentences: let I/we/you occur naturally as the guide points out, explains or compares a supported detail.
This is the voice of the whole tour, not a mandatory pronoun in every line or a prefix to add to a formal sentence.
Let some thoughts begin with a brief personal invitation to notice the current feature and others explain what
the visitor can see or do. Write fresh dialogue for this product; do not rotate stock transition strings.
Read it aloud to one person. If it sounds like brochure copy, rewrite the sentence itself rather than adding a
friendly opener to it. A polished brand voice still speaks plainly and personally; avoid detached descriptions,
formal noun phrases and runs of sentences beginning with an -ing clause. One or two short connected sentences
can carry a complete batch. Facts, qualifications, selected duration and the reviewed plan remain binding.

Write it as ONE continuous talk in the plan's order, each part carrying the thought of the part before it. The
Planner supplies an outline, not proof: its adjectives, benefit labels and suggested sentences are untrusted
editorial context. Re-check every capability or felt outcome against the actual cited fact, even when a Planner
goal asks for it. Engine output does not establish effortless driving; all-wheel drive does not establish a
composed or comfortable ride. An assistance feature still needs its supervision and eligibility conditions in
the same spoken thought. Never hide a material prerequisite in deeper detail to make the main claim fit: drop
that claim instead if its complete qualification cannot fit the planned batch. Do not inherit the outline's
brochure wording. The conversational contract above governs how you turn every outline into spoken words.

CONTINUITY AND STANDING ALONE ARE DIFFERENT THINGS. What breaks when a segment plays out of order is a
REFERENCE — "as I said", "that engine we just looked at", "the second of the three". What does not
break is a CONNECTION — the next thing being about a subject the buyer has just arrived at, in the same
voice, in a sentence that carries the thought on. Never reference. Always connect.
- INSIDE a prepared story stop, consecutive complete lines become separate delivery batches. Each line names its
  subject and finishes its own thought, so it works after an interruption; its ending carries a subject into the
  next line. Connect the ideas without a pronoun needing a previous batch or a repeated topic announcement.
  Short legacy lines that remain inside one delivery batch may share a subject naturally.
- ACROSS segments, only the proof segments can be reordered. The default guided tour plays enough supported
  proof stops to provide the selected demo duration of narration, excluding film and customer Q&A. Those stops must
  open cold — no naming, numbering or pointing back at another segment — but "cold" does not mean
  "abrupt": address the visitor about this stop's own subject or invite them to notice its visible feature.
  The sentence must make sense wherever it lands; it does not need a formal scene-setting preface.
- THE OTHER JOINTS ARE FIXED and you should write them as real joins. intro → outcome → (proof run) →
  features → establish → closing always play in that order. Write those joins as though one person is
still talking, because they are.

GUIDELINES — make each batch a useful piece of conversation
- Speak to one visitor as a person showing them the product, not as a brochure being read aloud. Use direct,
  natural sentences, contractions and occasional first-person guidance. A courteous or precise brand voice can
  still say "let me show you"; it does not require formal catalogue language or reciting every technical quantity.
  Let the chosen audience decide the depth of explanation, not whether the guide sounds human.
- At a useful change of subject, write a short, context-specific invitation to notice the actual feature, then
  explain its sourced function or choice in the same thought. "Now let me show you how the rear seats are arranged"
  and "If we look at the gear selector, ..." illustrate this register only: write fresh words for the supplied
  product and only refer to a part the assigned picture really shows. These are occasional spoken joins, not
  mandatory openers, a phrase list to rotate, a new question or an instruction to wait for an answer.
  Most lines can simply develop the observation. Alternate direct observations, explanations and brief guidance;
  do not begin a run of sentences with "Managing", "Providing", "Supporting" or other interchangeable -ing clauses.
- Open the intro's first sentence with a supported product fact or positioning. Use the one source-backed
  reputational line only if the plan supplies support; otherwise start with the product fact. Intake already greeted.
- Write each main delivery batch as one complete 26–33-word line. Within a three-minute compact-SUV plan, powertrain
  has three such lines and each other stop has at most two across the plan; follow the Planner's distinct evidence
  allocation. Continuation lines develop the thought, but vary their first words and grammatical openings too.
  The separate Explore overview stays 23–28 words with no digits; final closing stays at most two statements and
  45 words total. These two shorter formats are not main delivery batches.
- Use the distinct first-fundamental detail reserved for the Explore overview only there on the guided path.
  Later proof lines develop the other assigned evidence. Rephrasing that overview claim cannot count as new content.
- Explain one sourced function or choice in words you would use with the visitor beside you, then give the next
  thought a natural subject. An ordinary action can make a fact useful: arranging bags beside passengers, setting
  a temperature or matching a quote to equipment. Express the action as something the person can do, rather
  than opening every sentence with an impersonal participle. Do not force every feature into an invented scenario.
  For an appearance-only feature, talk about its visible finish or style without inventing a performance benefit.
  Read the thought as speech before checking its word count. A picture description or a generic buying phrase
  attached to a catalogue sentence is not enough; the actual explanation should sound personal and direct.
- Prefer that concrete connection to a list of equipment. State a demonstrated benefit only when the cited source
  establishes it; otherwise explain the sourced function or buying choice. Manufacturer descriptions remain
  attributed claims. "Never feels strained", a cooling time, or comparative ride comfort needs its own evidence.
- Keep the named starting trim or exact trim set in the same batch as a gated feature, along with material engine,
  gearbox, paid-option or adapter restrictions. "Selected variants", "equipped trims" and "depending on the variant"
  leave the buyer's question unanswered. Omit a less useful feature when its real conditions will not fit.
- Introduce an option at its first supported trim, or its exact non-continuous set, before illustrating a higher
  trim's combination. Keep an exception beside any statement it qualifies; the complete matrix remains deeper.
  When space is tight, first availability and material restrictions outrank a higher-trim example in the plan;
  move that example deeper. Treat the plan's suggested wording as guidance, keeping these speech rules intact.
  A restriction on one duration or package stays attached to that duration or package; shortening the sentence
  must not turn a limited eligibility rule into a rule for every warranty, offer or version.
- End each main batch on the next relevant subject, not a bare specification. Read it aloud without the picture,
  then after a customer interruption: it should still name its subject and make sense. Handoffs are short connecting
  thoughts, not stock "moving on" announcements, repeated promises or invented outcomes.
  Check the ending against the next subject in the plan: repeating this batch's own equipment or availability does
  not create that join. The last main batch turns toward the closing choice and next action.
- Make the join a reason the next subject matters to the current choice. Matching a quote to included cabin
  equipment is a useful connection. A brief invitation to look is useful when it immediately identifies the
  pictured feature and develops its sourced detail; an empty announcement that another item awaits is not.
  Vary sentence rhythm and grammatical openings: swapping "Choosing" for "Considering" does not change the shape.
  A line may contain two short connected sentences rather than one formal sentence stretched to its word budget.
- Keep segment checkins empty when the plan reserves its two statements for the final close. The close summarizes
  the supported choices and names the actual next action; it does not choose a customer's preferred trim for them.
- Audit the full main path before returning it: varied first words and constructions, exact trim scope, no repeated
  evidence, no unsupported figures, each pictured subject literally present. A price or policy can use visual none;
  an unrelated car picture is not proof. Meet the plan's full supported-word target without padding or slowing speech.
  When contrasting physically different options, show only the pictured option in that batch or choose visual
  none for the comparison. A manual control cannot illustrate an automatic-only choice; an alloy cannot illustrate
  a steel wheel. Topic similarity alone is insufficient, including in alternative openings and deeper detail.
- Check citations clause by clause, including openings and handoffs: a transition that mentions another product
  capability needs that capability's own assigned fact IDs too. The paragraph's main fact cannot support its bridge.
  In deeper detail, preserve whether a counted component is included: a system "with" a part is not that count
  "and" an extra part. Keep the source's complete quantity, membership and conditions together.

{principles}

{author_craft}

Hard rules:
1. GROUNDING (G2). Every sentence stating a spec, number, price, offer, policy or capability cites its fact ids in
   fact_ids and never goes beyond them. A figure without a fact id is rejected by a validator; an existing id does not
   prove an added benefit. Keep truth kinds distinct (G4): ordinary stated specifications stay stated; reserve
   certification language for explicit certified results with their basis. Name estimates, marketing and written
   terms where relevant, without a ritual evidence label on every line.
2. HONESTY. Where the supplied facts do not settle a relevant question, state your verification limit in the persona's
   voice and name the right next step. Say "I can't confirm the boot-capacity figure from these details" rather than
   claiming a whole brochure omits it. A visit can check personal fit, not establish an undocumented specification or
   policy. Use the plan's establish segment for remaining questions; never paper over a gap.
3. VISUALS (G5). Every line binds to the visual that literally shows what it says (shot id or image id); 'focus' is a
   2-5 word on-screen label. When the subject changes, the picture changes.
4. THE PLAN IS SETTLED. Write one segment for each segment in PLAN.segments, in the order given, keeping
   its id, role and title exactly. Do not add, drop, merge, split, reorder or rename a segment, and do
   not decide what the demo covers — that decision is made. Speak only the facts the plan assigned to
   that segment; anything else it cites belongs in `deeper`. The suggested batch wording and spoken/deeper split
   do not override evidence or visual grounding. If that wording mixes unrelated pictured subjects, keep one
   already assigned literal subject in the batch and move the other assigned detail to deeper. Preserve every
   material condition of the claim you keep; current approved facts outrank a shorter or conflicting outline.
   Develop distinct assigned detail across the remaining batches to fulfill the unchanged whole-stop budget and
   narration target, using direct, varied dialogue. Do not create a new stop, borrow unassigned evidence or fill
   the space with repeated claims. Put a one-line closing statement only where the plan asks for one; never a question. For a prepared plan, one segment is one reviewed story stop: its word_budget can cover several short delivery batches. Write complete cited lines within that whole-stop allowance; the delivery splitter groups those lines afterward. The budget exists to
   keep the thought clear, not to compress thoughts — a segment under its word_budget that flows beats one at the ceiling that is crammed. Your judgement is about WORDS: what to say first inside the segment, how long a sentence
   runs, which everyday noun carries the idea, how one segment hands over to the next.
   PLAN.customer_persona is the planner's note about who the product suits. It is not a person in the
   room. This script is written before any customer arrives and must be excellent with none: never assign
   the listener a commute, budget, city, household or job, and never hedge around them either — no
   "depending on your routine", no "if that matters to you". "You" is fine for what the product does for
   anyone: "you'd notice it the first hot afternoon", never "on your Bengaluru commute".
   Each main delivery batch is one natural 26–33-word thought; each complete line must fit the role ceiling. In a prepared plan, use the segment's whole-stop word_budget for several distinct supported thoughts. PLAN.narration_preparation.target_words is the minimum across overview, all proof/features/establish narration and closing, excluding intro/outcome alternatives, deeper-only lines, questions and repeated claims. Use distinct detail from the assigned approved facts to meet it; if those facts cannot support it, state the evidence gap. Do not change the voice speed. In a legacy plan without that preparation field, the role ceiling applies to the whole segment. Padding means
   filler adjectives, restating the obvious, and repeating what was just said — cut those first. A
   joining clause is NOT padding; it is what makes this one piece of speech instead of a stack of
   captions. When the budget is tight, drop the least decisive fact and keep the remaining sentences
   whole and joined.
   OPENINGS. Avoid stock signposts, topic labels and bare specifications. A natural transition is allowed when
   it names this segment's own subject and leads straight into useful sourced detail. Open on the thing itself,
   on the moment it matters, or with a brief personal invitation to notice it. Each opening must make sense after
   an interruption, without "as we saw" or a numbered sequence. Vary constructions across the conversation;
   occasional repeated ordinary first words are fine. Do not force synonym changes into the same stiff template.
   The list below gives optional subjects, not required opening constructions or phrases to speak verbatim.
   Use them only within the direct spoken register above; do not turn them into a rotation of scene-setting
   prefaces: {signposts}
   Bad, because it is a label: "Next: cabin and comfort." Bad, because it assumes an order: "As we saw
   outside —". Bad, because it is a catalogue entry: "Selected variants offer ventilated front seats."
   Where segments run in the planned order, end each one on a clause that lands the thought and turns
   towards the next, never on a specification.
5. VOICE (G1). Spoken, not written: contractions, short clauses, numbers as words where natural, no markdown.
   Concrete nouns; no "smart/convenient/economical/premium/seamless". Relevance is not a garnish on a
   fact — it is the sentence, and the fact is the evidence inside it. Write what the thing does for the
   buyer, then the feature or figure that proves it, not the other way round. A line that is only a
   specification belongs in `deeper`. No segment may contain two consecutive sentences that are both
   specifications, and no fact may carry the narrative twice: a number that led one segment is not
   repeated in another.

{ladder}

   A FIT-CHECK IS A LAST RESORT, NOT A RELEVANCE BEAT. "Try it on a test drive", "check it when you sit
   in the car", "decide whether it matters to you" — these say nothing and cost the buyer the segment.
   Use a fit-check only where the evidence genuinely cannot support any rung of the ladder, and at most
   ONCE in the whole script. Never end consecutive segments on one. Where you would have written a
   fit-check, write R1 instead: describe what the picture shows.
6. MAKE THE PRODUCT WORTH EXPLORING. Lead with the strongest supported reason to care, then show the actual feature.
   Choose a vivid, concrete observation over generic praise. It does not recite the vehicle's dimensions or say every feature is exciting. A transmission type alone never proves smooth,
   imperceptible or jerk-free shifts. A safety feature never promises that an accident cannot happen.
   Do not make "four-cylinder", "quad-beam", "dual-clutch" or dimensions the everyday opening or a headline benefit.
   Do not replace those with unsupported praise such as "responsive turbo", "assured stopping performance", "diesel
   pulling power" or "extra pep". Equipment describes equipment; a felt result needs its own evidence.
   When reviewed facts pair petrol with manual or automatic and turbo with automatic
   only, NEVER compress that into "each engine offers manual or automatic". Say "Gearbox choices depend on the engine"
   and retain the exact pairings in deeper detail. No universal "each/all" unless every cited scope supports it.
   A check-in is one short closing statement for the stop, never a question. Narration continues immediately after it;
   it does not ask for readiness, a preference or permission. Leave it empty unless the plan asks for a closing statement.
   Do not ask again for context the customer already supplied. The intake's open context question is a separate flow.
7. DELIVERY. Be a helpful, cheerful, attentive guide: gentle enthusiasm, a reassuring cadence for limitations, no
   theatrical excitement, repeated superlatives or forced fillers. Use punctuation for natural pauses. Set each line's
   delivery metadata to tone warm/upbeat/calm/reassuring; keep pace at 1.0 for a naturally timed guided script.
   Choose occasional meaningful moments for more expressive delivery: a distinctive supported feature worth
   noticing, or a useful contrast the evidence establishes. On those lines only, set optional delivery.expressiveness
   to 0.7–0.8; omit it on most lines. At most one in four main lines may use it, and fewer is fine: this is not a quota,
   an alternating pattern or a rule to mark every number. Let the meaning choose the moment. The provider uses this
   to vary expression; it is not a direct pitch or loudness control and cannot guarantee emphasis on a chosen word.
   Keep limitations, prices and policy conditions calm and clear. Never add a claim, repeated word, filler or slower
   pace to manufacture drama or reach the duration. Never put [emotion], SSML, ALL-CAPS cues or a delivery instruction
   in spoken text; exact words and punctuation remain the script the customer sees and hears.
   Write overview as a separate, self-contained 23–28 word thought for Explore's 10–15 second introduction: begin with
   the first supported fundamental in the playbook, as mapped to PLAN.segments, in everyday words with its variant
   qualification and citations. No greeting, question, decision frame, digits or dimensions. Delighters come later.
   Do not duplicate overview verbatim in the regular segments; it is an alternative opening while the route is planned.
{audience}
{language}

FINAL SELF-REVIEW — apply to the complete response before returning it
- Read every claim against its own fact_ids, including deeper answers. An exhaustive exclusion across engine,
  trim or offer choices needs the evidence for every choice it rules out, not just two rows of a larger matrix.
- Review each visual against the whole line. A dashboard may show its displays but cannot show a connected-service
  entitlement or subscription period. Keep such mixed evidence lines nonvisual, or separate the pictured subject.
- Read the main path aloud in the guide's voice: does it sound like someone showing one visitor the product, or
  a sequence of catalogue captions? Replace repeated formal -ing openings and long technical lists with varied,
  direct spoken thoughts. Keep occasional personal guidance specific to the pictured subject, with no greeting
  reset, invented customer preference or unsupported benefit. Keep the handoff connected to the next actual subject.
- Check first availability, scope restrictions, distinct evidence and all word budgets again after those edits.
  Return the script only; this review is preparation, not extra narration or an added schema field."""


# Read an explicitly supplied reviewed script when the stage's reasoning providers are unavailable.
# server/schemas.py:ScriptOut validates its structure; the normal checks still run on the returned draft.
def _verified_script(demo_id: str, demo: dict) -> schemas.ScriptOut | None:
    """Load a human-reviewed script bundle when both reasoning providers are unavailable."""
    manifests = [s for s in demo.get("sources", []) if s.get("kind") == "text"
                 and s.get("name", "").lower() == "verified-script.json.md"]
    if not manifests:
        return None
    raw = store.path(demo_id, manifests[-1]["path"]).read_text(encoding="utf-8").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return schemas.ScriptOut.model_validate_json(raw)


# Recognize common figures/claims so uncited lines can be flagged; these patterns are not full entailment tests.
# The shared ungrounded check is also used by server/agents/deck.py:clean_callouts for on-screen text.
NUMBERISH = re.compile(r"(\d[\d,\.]*\s*(%|km|kwh|kw|kg|hrs?|hours?|mins?|minutes?|years?|months?|days?|litres?|liters?|gb|mb|tb|mah|w\b|v\b|cc\b|mm|cm|inch|inches|₹|rs\.?|rupees|usd|\$|€)|₹\s*\d|\$\s*\d|\d{2,}|\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)(?:\s+|-)?(?:airbags?|stars?|seats?|seaters?|speakers?|colou?r options?|apps?|variants?|years?|months?)\b)", re.I)
CLAIMISH = re.compile(r"\b(warrant|guarantee|certified|rated|fastest|longest|best[- ]in[- ]class|free|discount|offer|included|supports?|compatible|waterproof|ip6\d)\b", re.I)
# Set word budgets and an estimated speaking speed before real audio durations are available.
# server/agents/voice.py:render_script later calls timeline with recorded audio; estimates are not playback guarantees.
LIMITS = {"intro": 46, "outcome": 46, "proof": 46, "features": 48, "establish": 44}  # Room for natural joins; the planner allocates within these ceilings.
WPS = 1.9  # spoken words per second, measured on Sarvam bulbul (Creta run 2026-09-04: 446 words → 240 s); replaced by real audio durations after voicing
CLOSING_LIMIT = 45
def route_limit(demo: dict | None = None, plan: dict | None = None) -> int:
    """Derive the route ceiling from the selected duration, with room for joins."""
    preparation = (plan or {}).get("narration_preparation") or {}
    if preparation.get("version") == 1 and preparation.get("target_words"):
        return int(preparation["target_words"]) + 40
    from .narration import minimum_seconds
    minutes = minimum_seconds(demo) / 60
    return round(minutes * 60 * WPS) + 40


def _carry_plan_metadata(script: dict, plan: dict | None) -> None:
    """Carry the settled plan's timing and story identity through recording and splitting."""
    by_id = {segment["id"]: segment for segment in (plan or {}).get("segments", [])}
    groups = {}
    for segment in script.get("segments", []):
        source = segment.get("budget_source_id") or segment.get("id")
        groups.setdefault(source, []).append(segment)
    for source, segments in groups.items():
        planned = by_id.get(source)
        if not planned:
            continue
        for segment in segments:
            for key in ("stop_id", "fundamental", "word_budget"):
                if key in planned:
                    segment[key] = planned[key]
        if len(segments) > 1 and isinstance(planned.get("word_budget"), int) and planned["word_budget"] > 0:
            weights = [sum(words(line.get("text", "")) for line in segment.get("lines", []) if not line.get("unverified")) for segment in segments]
            for segment, budget in zip(segments, _allocate_words(planned["word_budget"], weights)):
                segment["word_budget"] = budget


def _allocate_words(total: int, weights: list[int]) -> list[int]:
    """Share one stop's integer word allowance without increasing its total."""
    weights = weights if sum(weights) else [1 for _ in weights]
    raw = [total * weight / sum(weights) for weight in weights]
    allocations = [int(value) for value in raw]
    for index in sorted(range(len(raw)), key=lambda i: raw[i] - allocations[i], reverse=True)[:total - sum(allocations)]:
        allocations[index] += 1
    return allocations

# Flag technical register and unsupported shift promises without inventing replacement benefits.
# Check-ins are closing statements; real runtime clarifications own the waiting interaction.
JARGON = re.compile(r"\b(IDC|kWh|kW|amp|15A|5A|torque|Nm|newton[ -]?met(?:re|er)s?|r/min|RPM|Level\s*[12]|IP6\d|TFT|ABS|CBS|Li-ion|BMS|regen|DCT|IVT|CVT|ADAS|GDi|PS|BHP|\d[\d,.]*\s*(?i:mm|millimet(?:re|er)s?)|(?i:mm|millimet(?:re|er)s?|length|four[ -]cylinder|4[ -]cylinder|quad[ -]beam|parametric|dual[ -]clutch))\b")
# Extend the warning-only narration check without changing its existing matches.
JARGON = re.compile(JARGON.pattern + r"|\b(?i:" + "|".join(re.escape(term) for term in sorted(plain_terms.JARGON, key=len, reverse=True)) + r")\b")
_SHIFT_PROMISE = re.compile(r"\b(?:imperceptible|seamless|jerk[- ]free)\s+(?:gear\s*)?(?:shifts?|changes?)\b|\b(?:won't|will not|cannot|can't)\s+(?:even\s+)?feel\s+(?:the\s+)?(?:gear\s*)?(?:shifts?|changes?)\b", re.I)


# Count whitespace-separated words for draft budgets and estimated durations.
# server/agents/deck.py uses this helper for compact titles and labels; no model call is involved.
def words(t: str) -> int:
    return len(re.findall(r"\S+", t or ""))


# Filter citations against the allowed IDs and flag recognizable claims when no valid citation remains.
# Returns the retained IDs plus a warning flag; server/agents/deck.py:clean_callouts reuses this minimum check.
def ungrounded(text: str, fact_ids: list[str] | None, allowed: set[str]) -> tuple[list[str], bool]:
    """The one rule every spoken or shown line obeys — script lines, runtime bridges, custom batches, slide callouts:
    keep only the fact ids that exist; if none are left and the text states a figure or claim, it is ungrounded."""
    valid = [x for x in (fact_ids or []) if x in allowed]
    return valid, bool(not valid and (NUMBERISH.search(text or "") or CLAIMISH.search(text or "")))


# Check and normalize a draft in place, returning issues for the writer's repair pass.
# Uses approved understanding facts and allowed visuals; server/agents/bundle.py:build omits unverified main lines.
def validate(script: dict, und: dict, plan: dict | str | None = None, demo: dict | None = None,
             audience: str | None = None) -> list[str]:
    # Older callers pass the audience as argument three. Keep that contract while
    # new authoring runs pass the actual plan and demo for typed timing checks.
    if isinstance(plan, str):
        audience, plan = plan, None
    audience = audience or (demo or {}).get("settings", {}).get("audience", "everyday")
    _carry_plan_metadata(script, plan)
    preparation = (plan or {}).get("narration_preparation") or {}
    prepared_tour = preparation.get("version") == 1 and bool(preparation.get("target_words"))
    # A human rejection in Align is a hard boundary: rejected facts must not
    # survive as citations merely because they still exist in the registry.
    fact_ids = {f["id"] for f in und["facts"] if f.get("approved", True)}
    vis = {s["id"]: "shot" for s in und["shots"] if s.get("_allowed", True)} | {i["id"]: "image" for i in und["images"] if i.get("_allowed", True)}
    issues: list[str] = []

    # Add a readable editorial warning when main narration is too technical for the everyday audience.
    # The warning informs the rewrite prompt; it does not remove a sourced quantity or its unit itself.
    def register_warning(text: str, where: str):
        # Editorial warning only: never suppress a sourced line, strip its unit,
        # or police a requested technical/deeper answer.
        if audience == "everyday":
            m = JARGON.search(text or "")
            if m:
                issues.append(f"{where}: everyday register warning — jargon '{m.group(0)}' in the main narration; move the complete technical quantity to deeper unless explicitly requested, never keep a number while dropping its unit")

    # Normalize one line's delivery, citations and visual ID, then mark detected unsupported claims.
    # server/agents/speech_style.py:prepare cleans speech markup; pixel coverage is checked later by visuals.py:align.
    def check(line: dict, where: str):
        prepared = speech_style.prepare(line.get("text", ""), line.get("delivery"))
        if prepared["plain_text"] != line.get("text", "").strip():
            issues.append(f"{where}: removed unsupported delivery markup; keep delivery metadata separate from spoken words")
            line["text"] = prepared["plain_text"]
        if line.get("delivery"):
            line["delivery"] = speech_style.normalize(line["delivery"])
        line["fact_ids"], bad = ungrounded(line.get("text", ""), line.get("fact_ids"), fact_ids)
        cited = [f for f in und["facts"] if f["id"] in line["fact_ids"]]
        evidence = " ".join(str(f.get(k, "")) for f in cited for k in ("claim", "value", "conditions")) + " " + " ".join(str((f.get("source") or {}).get("quote", "")) for f in cited)
        if _SHIFT_PROMISE.search(line.get("text", "")) and not _SHIFT_PROMISE.search(evidence):
            issues.append(f"{where}: transmission evidence does not establish an imperceptible or seamless shift outcome")
            bad = True
        # Verify that the chosen image/shot exists and derive its correct kind from the catalogue.
        # A valid ID only establishes identity here, not that the picture proves the spoken feature.
        v = line.get("visual") or {"kind": "none", "ref": "", "focus": ""}
        if v.get("ref") and v["ref"] not in vis:
            issues.append(f"{where}: visual '{v['ref']}' does not exist")
            v["ref"], v["kind"] = "", "none"
        elif v.get("ref"):
            v["kind"] = vis[v["ref"]]
        line["visual"] = v
        if bad:
            if not line["fact_ids"]:
                issues.append(f"{where}: states a figure or claim without a fact id — “{line.get('text', '')[:90]}”")
            line["unverified"] = True
        else:
            line["unverified"] = False

    # Validate main and deeper lines, and keep uncited claims out of the separate check-in field.
    # Only runtime clarifications wait; authored check-ins cannot request a reply.
    for seg in script["segments"]:
        checkin = (seg.get("checkin") or "").strip()
        register_warning(checkin, f"{seg['id']} checkin")
        if re.search(r"[?？]", checkin):
            issues.append(f"{seg['id']} checkin: must be a short closing statement, never a question")
            # Preserve reviewed legacy words/audio. New drafts repair this issue;
            # runtime skips a legacy question without rewriting its source.
        # Checkins have no citation field. Moving a claim out of a line cannot
        # exempt it from grounding: a closing statement must remain claim-free.
        if NUMBERISH.search(checkin) or CLAIMISH.search(checkin):
            issues.append(f"{seg['id']}: checkin contains a figure or claim without citations — use a claim-free closing statement and keep cited facts in narration")
            seg["checkin"], seg["checkin_audio"] = "", None
        for n, ln in enumerate(seg["lines"], 1):
            check(ln, f"{seg['id']} line {n}")
            if re.search(r"[?？]", ln.get("text", "")) or ln.get("step") == "confirm":
                issues.append(f"{seg['id']} line {n}: narration must use statements, never a question; only runtime clarifications wait for a reply")
        for n, ln in enumerate(seg.get("deeper", []), 1):
            check(ln, f"{seg['id']} deeper {n}")
        total = sum(words(l["text"]) for l in seg["lines"])
        lim = LIMITS.get(seg.get("role", "proof"), 165)
        explicit_budget = seg.get("word_budget")
        explicit_budget = explicit_budget if isinstance(explicit_budget, int) and not isinstance(explicit_budget, bool) and explicit_budget > 0 else None
        budget = explicit_budget or lim
        if total > budget + 4:
            issues.append(f"{seg['id']} ({seg.get('role')}): {total} words, over its budget of {budget} — cut a whole idea, keeping the joins")
        if explicit_budget and total < budget - 10:
            issues.append(f"{seg['id']} ({seg.get('role')}): warning — well under budget; add the join or the moment ({total} words, budget {budget})")
        if prepared_tour and seg.get("role") in {"proof", "features", "establish"} and not seg.get("budget_source_id"):
            for n, line in enumerate(seg["lines"], 1):
                if words(line.get("text", "")) > lim:
                    issues.append(f"{seg['id']} line {n}: complete thought exceeds the {lim}-word delivery ceiling — use separate complete cited lines, never fragments")
        elif total > lim:
            issues.append(f"{seg['id']} ({seg.get('role')}): {total} words, limit {lim} — shorten (P06)")
        for n, line in enumerate(seg["lines"], 1):
            register_warning(line.get("text", ""), f"{seg['id']} line {n}")
    # Check opening, closing and a representative route against their word budgets.
    # These draft totals guide repair; server/agents/voice.py:render_script later supplies actual recording durations.
    intro_words = sum(words(l["text"]) for s in script["segments"] if s.get("role") in ("intro", "outcome") for l in s["lines"])
    if intro_words > 115:
        issues.append(f"opening (intro + outcome) is {intro_words} words; keep it under 115 (~45 s)")
    for n, ln in enumerate(script.get("closing", []), 1):
        check(ln, f"closing {n}")
        register_warning(ln.get("text", ""), f"closing {n}")
        if re.search(r"[?？]", ln.get("text", "")) or ln.get("step") == "confirm":
            issues.append(f"closing line {n}: close with a next-action statement; the separate CTA choice waits for the customer")
    closing_words = sum(words(l["text"]) for l in script.get("closing", []))
    if closing_words > CLOSING_LIMIT:
        issues.append(f"closing is {closing_words} words, limit {CLOSING_LIMIT}")
    by_role = {}
    for s in script["segments"]:
        by_role.setdefault(s.get("role", "proof"), []).append(sum(words(l["text"]) for l in s["lines"]))
    route = sum(by_role.get("intro", [0])) + sum(by_role.get("outcome", [0])) + sum(sorted(by_role.get("proof", []), reverse=True)[:3]) + sum(by_role.get("features", [0])) + sum(by_role.get("establish", [0])) + closing_words
    if isinstance(plan, dict) and plan.get("guided_minimum_seconds") and demo is not None:
        from . import narration
        _, guided = narration.default_route(script, allowed_fact_ids=fact_ids, minimum_seconds=narration.minimum_seconds(demo))
        route = guided["words"]
    limit = route_limit(demo, plan)
    if route > limit:
        issues.append(f"a full route would run {route} words (~{route / WPS / 60:.1f} min); keep it under {limit} for the selected demo length — cut, don't compress")
    # Validate the separate Explore opening as cited, question-free narration with its own word budget.
    # server/agents/bundle.py:build publishes it under runtime.overview for concurrent opening playback/planning.
    overview = script.get("overview") or script.get("runtime_overview")
    if overview:
        check(overview, "Explore overview")
        if not 23 <= words(overview.get("text", "")) <= 28:
            issues.append("Explore overview: use 23–28 words for the 10–15 second opening")
        if not overview.get("fact_ids") or re.search(r"[?？]", overview.get("text", "")):
            issues.append("Explore overview needs cited evidence and must not ask a question")
            overview["unverified"] = True
        register_warning(overview.get("text", ""), "Explore overview")
    if isinstance(plan, dict) and plan.get("guided_minimum_seconds") and demo is not None:
        from . import narration
        _, guided = narration.default_route(script, allowed_fact_ids=fact_ids, minimum_seconds=narration.minimum_seconds(demo))
        script["narration_minimum"] = guided
        if prepared_tour:
            script["narration_preparation"] = {**(script.get("narration_preparation") or {}), **preparation}
            eligible = narration.preparation_report(script, allowed_fact_ids=fact_ids, minimum_seconds=narration.minimum_seconds(demo))
            target = int(preparation["target_words"])
            script["narration_preparation"].update(status="incomplete" if eligible["words"] < target else "ready",
                                                  words=eligible["words"], missing_words=max(0, target - eligible["words"]))
            if eligible["words"] < target:
                issues.append(f"GLOBAL NARRATION TARGET: {eligible['words']} distinct supported words, minimum {target}. Add {target - eligible['words']} words of distinct supported detail from assigned approved facts to underused story stops, within their whole-stop budgets. Add complete cited lines, each within its delivery ceiling. Preserve good existing lines; never repeat claims, pad, slow the voice, or count deeper-only material. If the evidence is insufficient, keep the gap explicit.")
            if eligible["words"] > limit:
                issues.append(f"GLOBAL NARRATION TARGET: {eligible['words']} words exceeds the {limit}-word route ceiling; remove a whole less useful idea without losing the minimum {target} words")
        elif not guided["sufficient"]:
            issues.append(narration.deficit_message(guided))
    return issues


# Read a stored WAV's frame count and sample rate to return its duration, or None if unavailable.
# server/store.py:path resolves the audio written by server/agents/voice.py:render_script; no audio is played here.
def _audio_seconds(demo_id: str | None, rel: str | None) -> float | None:
    if not demo_id or not rel:
        return None
    try:
        import wave
        with wave.open(str(store.path(demo_id, rel)), "rb") as w:
            return round(w.getnframes() / float(w.getframerate() or 1), 2)
    except Exception:
        return None


# Add starts and durations to narration/check-ins and return a script-level timing summary.
# server/agents/voice.py:render_script can refresh word-based estimates with WAV durations before bundle.py:build reads them.
def timeline(script: dict, demo_id: str | None = None) -> dict:
    """Per-line start/duration in seconds (estimated from words, exact from the audio when it exists) and per-batch totals.
    Stored on the script so the Align page and the bundle can show 'at 0:42 the guide says … and shows im04'."""
    if demo_id:
        # Direct edits and older draft scripts may predate metadata carry-over.
        # Recover only absent allowances; already split batches keep their shares.
        missing = [segment for segment in script.get("segments", []) if not segment.get("word_budget")]
        if missing:
            _carry_plan_metadata({"segments": missing}, store.read_json(demo_id, "plan.json") or {})
    t = 0.0
    batches = []
    all_measured = []
    planned_budgets = []
    # Accumulate main narration and check-in audio in order; unverified main lines do not consume time.
    # This is a content timeline, not the customer's runtime wall clock or their answer-wait duration.
    for seg in script.get("segments", []):
        b0 = t
        segment_measured = []
        budget = seg.get("word_budget")
        budget = budget if isinstance(budget, int) and not isinstance(budget, bool) and budget > 0 else None
        planned_budgets.append(budget)
        seg["planned_seconds"] = round(budget / WPS, 1) if budget else None
        for ln in seg.get("lines", []):
            if ln.get("unverified"):
                continue
            actual = _audio_seconds(demo_id, ln.get("audio"))
            dur = actual or round(max(1.0, words(ln.get("text", "")) / WPS), 1)
            ln["start"], ln["duration"], ln["exact"] = round(t, 1), dur, bool(actual)
            segment_measured.append(bool(actual))
            t += dur
        spoken = round(t - b0, 1)  # the batch itself: what the guide says before the pause point
        if seg.get("checkin"):
            actual = _audio_seconds(demo_id, seg.get("checkin_audio"))
            dur = actual or round(max(1.0, words(seg["checkin"]) / WPS), 1)
            segment_measured.append(bool(actual))
            seg["checkin_start"], seg["checkin_duration"] = round(t, 1), dur
            t += dur
        seg["start"], seg["duration"], seg["spoken"] = round(b0, 1), round(t - b0, 1), spoken
        seg["measured"] = bool(segment_measured) and all(segment_measured)
        all_measured.extend(segment_measured)
        batches.append({"id": seg["id"], "title": seg.get("title"), "role": seg.get("role"), "start": round(b0, 1), "duration": round(t - b0, 1), "spoken": spoken, "checkin": round(t - b0 - spoken, 1), "over_20s": spoken > 20.5,
                        "planned_seconds": seg["planned_seconds"], "measured": seg["measured"]})
    # Append closing durations, then record total/batch timings back onto the script.
    # The existing exact flag means some main-line audio was measured, not that every duration is measured.
    for ln in script.get("closing", []):
        actual = _audio_seconds(demo_id, ln.get("audio"))
        dur = actual or round(max(1.0, words(ln.get("text", "")) / WPS), 1)
        ln["start"], ln["duration"], ln["exact"] = round(t, 1), dur, bool(actual)
        all_measured.append(bool(actual))
        t += dur
    planned_total = round((sum(planned_budgets) + CLOSING_LIMIT) / WPS, 1) if planned_budgets and all(budget is not None for budget in planned_budgets) else None
    script["timeline"] = {"total_seconds": round(t, 1), "batches": batches, "exact": any(l.get("exact") for s in script.get("segments", []) for l in s.get("lines", [])),
                          "planned_total_seconds": planned_total, "measured": bool(all_measured) and all(all_measured)}
    return script["timeline"]


# Split oversized narration at existing line boundaries, keeping check-in/deeper material on the last piece.
# Returns the added batch count; server/agents/deck.py:build later creates slides from the resulting segments.
def split_long_batches(script: dict, *, strict: bool = False) -> int:
    """A segment whose spoken lines exceed its role ceiling is split at line
    boundaries into '… (cont.)' batches; the check-in and deeper lines stay with the last piece. Returns the number of
    new batches created."""
    out, created = [], 0
    reserved_ids = {segment["id"] for segment in script.get("segments", [])}
    for seg in script.get("segments", []):
        limit = LIMITS.get(seg.get("role", "proof"), 50)
        lines = [l for l in seg.get("lines", []) if not l.get("unverified")]
        if sum(words(l.get("text", "")) for l in lines) <= limit + (0 if strict else 4) or len(lines) < 2:
            out.append(seg)
            continue
        # Group whole verified lines within the role's word budget; never rewrite a sentence to make it fit.
        # A single long line is not split internally, so measured audio length still needs later review.
        chunks, cur, n = [], [], 0
        for l in lines:
            w = words(l.get("text", ""))
            if cur and n + w > limit:
                chunks.append(cur); cur, n = [], 0
            cur.append(l); n += w
        if cur:
            chunks.append(cur)
        held = [l for l in seg.get("lines", []) if l.get("unverified")]
        # One planned stop may need several delivery batches. Divide its budget
        # by spoken word share; copying the full allowance would inflate the plan.
        allocations = None
        if isinstance(seg.get("word_budget"), int) and seg["word_budget"] > 0:
            weights = [sum(words(line.get("text", "")) for line in chunk) for chunk in chunks]
            allocations = _allocate_words(seg["word_budget"], weights)
        for k, ch in enumerate(chunks):
            last = k == len(chunks) - 1
            piece_id = seg["id"]
            if k:
                suffix = k + 1
                while f"{seg['id']}-{suffix}" in reserved_ids:
                    suffix += 1
                piece_id = f"{seg['id']}-{suffix}"
                reserved_ids.add(piece_id)
            piece = {**seg, "id": piece_id, "budget_source_id": seg.get("budget_source_id") or seg["id"], "title": seg["title"] if k == 0 else f"{seg['title']} (cont.)",
                     "lines": ch + (held if last else []), "checkin": seg.get("checkin", "") if last else "", "checkin_audio": seg.get("checkin_audio") if last else None,
                     "deeper": seg.get("deeper", []) if last else []}
            if allocations is not None:
                piece["word_budget"] = allocations[k]
            out.append(piece)
            created += 0 if k == 0 else 1
    script["segments"] = out
    return created


# Give main, deeper, closing and overview lines stable names within this script's segment structure.
# server/agents/bundle.py:build joins deck line IDs back to script text, audio and timing using these names.
def _assign_ids(script: dict) -> None:
    overview = script.pop("overview", None)
    if overview:
        overview["id"] = "runtime-overview"
        script["runtime_overview"] = overview
    for seg in script["segments"]:
        for n, ln in enumerate(seg["lines"], 1):
            ln["id"] = f"{seg['id']}-L{n}"
        for n, ln in enumerate(seg.get("deeper", []), 1):
            ln["id"] = f"{seg['id']}-D{n}"
    for n, ln in enumerate(script.get("closing", []), 1):
        ln["id"] = f"close-L{n}"


# Turn the approved registry and planner's outline into script.json with narration and per-line visual references.
# server/graph.py:author invokes this stage; server/agents/deck.py:build consumes its saved segments next.
def run(demo_id: str, emit, instruction: str = "") -> dict:
    from . import narration, plan as planner
    und = store.read_json(demo_id, "understanding.json")
    plan = store.read_json(demo_id, "plan.json")
    if not (und and plan):
        raise RuntimeError("Plan first, then author")
    demo = store.load(demo_id)
    # Drafting owns preparation before human review, including older plans.
    # This retains the settled story and never invokes another Planner model.
    plan = planner.prepare_existing(demo_id)
    for s in und["shots"]:
        s["_allowed"] = store.visual_allowed(demo, s["source_id"])
    for i in und["images"]:
        i["_allowed"] = store.visual_allowed(demo, i["source_id"])
    prev = store.read_json(demo_id, "script.json")
    emit("Writing the script…")
    # Supply the outline plus approved facts and allowed visual descriptions to the writer.
    # Segment choices from server/agents/plan.py:run become per-line visual.ref/focus fields; pixels come later.
    facts_txt = "\n".join(fact_context(f) for f in und["facts"] if f.get("approved", True))
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in und["shots"] if s.get("_allowed", True))
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(visuals.part_names(i))} · {i['description']}" for i in und["images"] if i.get("_allowed", True))
    plan_view = {k: plan.get(k) for k in ("customer_persona", "decision_frame", "takeaway", "primary_outcome", "supporting_outcomes", "concerns", "usps", "segments", "ctas", "voice", "intake", "do_not_recommend_if", "advance", "notes", "total_words", "playbook_version", "guided_minimum_seconds", "guided_opening_words", "narration_preparation")}
    content = f"""PRODUCT: {json.dumps(und['product'])}
BRAND: {json.dumps(und['brand'])}
PLAN: {json.dumps(plan_view)}

FACT REGISTRY — the only allowed source of facts:
{facts_txt or '(empty — every specification must be declared unknown)'}

VIDEO SHOTS:
{shots_txt or '(none)'}

IMAGES:
{imgs_txt or '(none)'}
"""
    # A revision includes prior dialogue and the user's instruction; a fresh author run uses the current plan.
    # server/llm/claude.py:structured returns ScriptOut through the build provider path, with an explicit manifest fallback.
    if prev and instruction:
        content += f"\nPREVIOUS SCRIPT (revise; keep segment ids, but remove any assumed individual customer circumstances):\n{json.dumps({'segments': prev['segments'], 'closing': prev['closing']})[:40000]}\n"
    if instruction:
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    audience = demo.get("settings", {}).get("audience", "everyday")
    sys = AUTHOR_SYSTEM.format(principles=PRINCIPLES, author_craft=AUTHOR_CRAFT, ladder=TRANSLATION_LADDER, signposts=" | ".join(SIGNPOSTS), audience=audience_instruction(audience), language=language_instruction(demo.get("settings", {}).get("language", "en-IN")))
    attempts, preparation_errors = 1, []
    try:
        out = claude.structured(sys, content, schemas.ScriptOut, max_tokens=40000)
    except Exception as e:
        manifest = _verified_script(demo_id, demo) if claude._provider_unavailable(e) else None
        if not manifest:
            raise RuntimeError(f"Script writing failed: {claude.describe_error(e)}") from e
        emit("Reasoning providers unavailable — using the explicit verified script…")
        out = manifest
    script = out.model_dump()
    script["intake_q2"] = ""
    # Keep the general repair, then permit one duration-focused completion.
    # Three drafting calls is the hard limit; provider failures stop retries.
    issues = validate(script, und, plan, demo)
    if issues:
        attempts += 1
        emit(f"Validator flagged {len(issues)} issue{'s' if len(issues) != 1 else ''} — asking for a grounded rewrite…")
        fix = content + "\n\nYOUR DRAFT:\n" + json.dumps({k: script.get(k) for k in ("overview", "segments", "closing", "intake_q1", "intake_q2")})[:60000]
        fix += "\n\n" + """VALIDATOR ISSUES — each names a specific segment or line. Fix every reported issue and return the full script.
Preserve valid meaning, citations, settled stop order and budgets, not defective wording. An unflagged line has
only passed these mechanical checks; it may still sound like a brochure, combine unrelated pictured subjects,
omit a material condition or add an unsupported benefit. Re-read every line against the system's conversational,
qualification and visual rules, and revise its phrasing or evidence selection where needed within its assigned
facts. Keep already sound speech rather than gratuitously rewriting it; do not freeze a bad line merely because
the validator did not name it. A GLOBAL NARRATION TARGET issue also requires adding distinct supported detail to underused planned stops: retain the existing good lines and add complete cited lines from their assigned facts within the whole-stop allowances. This minimum is required, not advisory; deeper-only lines, film, questions and repeated claims do not count. If approved evidence cannot support more detail, leave that gap explicit. For each flagged line, try these in order and stop at the first that
works: (1) add the correct fact id if the registry genuinely supports the claim; (2) drop one rung on
the translation ladder and move the complete quantity to `deeper`; (3) state the gap honestly in the
guide's voice. Delete the thought only as a last resort. Where a segment is over budget, CUT A WHOLE
IDEA, DO NOT COMPRESS A SENTENCE. Issues whose text contains the word "warning" are advisory — fix one
only if the fix makes the line read better; a surviving warning shown to the human reviewer beats a
sentence flattened to satisfy a lexical rule. When every issue is fixed, read the whole script through
once as if speaking it aloud and repair what the fixes left behind: a sentence that no longer follows
the one before it, a subject introduced twice, a join that lost its verb.
""" + "\n".join("- " + i for i in issues)
        try:
            out2 = claude.structured(sys, fix, schemas.ScriptOut, max_tokens=40000)
            candidate = out2.model_dump()
            candidate["intake_q2"] = ""
            candidate_issues = validate(candidate, und, plan, demo)
            script, issues = candidate, candidate_issues
        except Exception as error:
            preparation_errors.append(f"Draft repair failed: {claude.describe_error(error)[:300]}")
    allowed = {fact["id"] for fact in und["facts"] if fact.get("approved", True)}
    target = plan["narration_preparation"]["target_words"]
    available_words = narration.preparation_report(script, allowed_fact_ids=allowed)["words"]
    route_ids, _ = narration.default_route({"segments": plan["segments"]}, include_all_proofs=True)
    selected_stops = [segment for segment in plan["segments"] if segment["id"] in route_ids]
    capacity = narration.OVERVIEW_WORDS + CLOSING_LIMIT + sum(
        segment["word_budget"] for segment in selected_stops)
    assigned_evidence = any(allowed.intersection(segment.get("fact_ids", [])) for segment in selected_stops)
    if available_words < target and not preparation_errors and assigned_evidence and capacity >= target and attempts < 3:
        attempts += 1
        emit("Completing the selected-length draft with distinct supported detail…")
        completion = content + "\n\n" + narration.PREPARATION_INSTRUCTION
        completion += "\n\nCURRENT DRAFT:\n" + json.dumps({k: script.get(k) for k in ("overview", "segments", "closing", "intake_q1", "intake_q2")})[:60000]
        completion += "\n\nVALIDATOR ISSUES:\n" + "\n".join("- " + issue for issue in issues)
        try:
            out3 = claude.structured(sys, completion, schemas.ScriptOut, max_tokens=40000)
            candidate = out3.model_dump()
            candidate["intake_q2"] = ""
            candidate_issues = validate(candidate, und, plan, demo)
            script, issues = candidate, candidate_issues
        except Exception as error:
            preparation_errors.append(f"Narration completion failed: {claude.describe_error(error)[:300]}")
    # Assign line IDs, then audit actual image coverage before splitting batches and estimating their timeline.
    # server/agents/visuals.py:align can change line visuals; deck.py:build later chooses one slide image per segment.
    _assign_ids(script)
    script["issues"] = issues
    script["version"] = (prev.get("version", 0) + 1) if prev else 1
    script["intake_audio"] = {}
    script["narration_preparation"] = {**plan["narration_preparation"], "status": "incomplete",
                                       "attempts": attempts, "errors": preparation_errors}
    schemas.Script.model_validate(script)
    if narration.preparation_status(demo_id, script=script, plan=plan)["status"] == "ready":
        script = visuals.align(demo_id, script, und, emit)
    else:
        # An old audit cannot be reused as proof for an incomplete new draft.
        # Audit the final words only after automatic preparation succeeds.
        script["visual_audit"] = {"method": "pending_narration", "lines": [], "images": []}
        emit("Narration preparation is incomplete — picture auditing will wait for a complete draft.")
    n_split = split_long_batches(script, strict=(plan.get("narration_preparation") or {}).get("version") == 1)
    if n_split:
        emit(f"{n_split} long batch(es) divided at complete lines for clearer pacing.")
    script["narration_preparation"] = narration.preparation_status(demo_id, script=script, plan=plan)
    timeline(script)
    store.write_json(demo_id, "script.json", script)
    n_lines = sum(len(s["lines"]) for s in script["segments"])
    unverified = sum(1 for s in script["segments"] for l in s["lines"] if l.get("unverified"))
    store.log(demo_id, "author", {"segments": len(script["segments"]), "lines": n_lines, "issues": issues,
                                  "narration_preparation": script["narration_preparation"]})
    emit(f"Script: {len(script['segments'])} segments, {n_lines} lines" + (f", {unverified} held back as unverified; {len(issues)} note(s) on the Facts card." if issues else ", all lines grounded and within pacing limits."))
    return script
