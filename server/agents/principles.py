"""Evidence-based sales principles (condensed from the playbook in
Codex/2026-09-03/wh/outputs/evidence_based_sales_pitch_demo_playbook.json).
These are injected into the plan, author, pitch and Q&A prompts, and drive the demo scorecard."""

import json
import re


_POLICY_RELATION_TOPIC = re.compile(r"\b(?:relationship|which(?:ever)?[^.;]{0,35}(?:first|earlier)|(?:duration|time)[^.;]{0,35}(?:distance|usage)|limits?[^.;]{0,35}(?:appl|first|earlier))\b", re.I)
_POLICY_RELATION_UNKNOWN = re.compile(r"\b(?:unknown|unstated|unspecified|undetermined)\b|\bnot\s+(?:provided|supplied|stated|specified|detailed|established|known|clear)\b|\b(?:does|do)\s+not\s+(?:state|specify|detail|explain|provide)\b", re.I)
_POLICY_RELATION = re.compile(r"\bwhichever\s+(?:(?:occurs|comes|happens|is|applies)\s+)?(?:first|earlier)\b|\b(?:years?|months?|days?|hours?)\b[^.!?;]{0,35}\bor\b[^.!?;]{0,65}\b(?:km|kilometres?|kilometers?|miles?|cycles?)\b|\b(?:km|kilometres?|kilometers?|miles?|cycles?)\b[^.!?;]{0,35}\bor\b[^.!?;]{0,45}\b(?:years?|months?|days?|hours?)\b", re.I)


def policy_relation_conflict(text: str, facts: list[dict]) -> bool:
    """Reject an asserted policy relation when cited evidence explicitly leaves it unknown.

    This English lexical guard addresses an observed contradiction, not general
    entailment. An earlier assertion is not excused by a later unknown disclaimer.
    A sentence that only says the relation is not supplied remains usable.
    """
    unknown = False
    for fact in facts:
        if fact.get("kind") != "policy" and fact.get("truth") != "contractual":
            continue
        evidence = str(fact.get("conditions") or "") + ";" + str((fact.get("source") or {}).get("quote") or "")
        if any(_POLICY_RELATION_TOPIC.search(c) and _POLICY_RELATION_UNKNOWN.search(c)
               for c in re.split(r"[.;\n]", evidence)):
            unknown = True
            break
    if not unknown:
        return False
    for clause in re.split(r"[.!?;\n]|\b(?:though|although|however|but)\b", text):
        for match in _POLICY_RELATION.finditer(clause):
            # Only a preceding explicit uncertainty can negate this particular
            # relation; never let a later caveat erase an affirmative first claim.
            prefix = clause[:match.start()]
            # Uncertainty about unrelated exclusions/terms does not negate a
            # later affirmative relation in the same sentence.
            attached_unknown = re.search(
                "(?:" + _POLICY_RELATION_UNKNOWN.pattern + r")\s+(?:if|whether)\b[^,;]{0,120}$",
                prefix, re.I)
            if not attached_unknown:
                return True
    return False

TRUTH_RULES = """EVIDENCE CLASSIFICATION AND SCOPE
- Default manufacturer-stated specifications and features to stated. An official source, high confidence, or a named
  measurement method (including ISO/VDA) does not by itself make a specification certified. Use certified only when
  the source explicitly reports a certification or a named test/rating result; retain its test basis and scope.
  Attribute a manufacturer's reported result to that source; do not imply you independently verified it.
- Use modeled only for a source's estimate with its assumptions, observed for a reported measurement in use,
  contractual for written terms, and stated for other source statements. Marketing language remains a claim,
  never a measured result. Classification describes the evidence, not your confidence in the product.
- Preserve exact quantities, units, currency, test basis, and all stated applicability: model generation, trim,
  engine, fuel or operating mode, transmission, market, date and offer restrictions. Keep different engines and
  fuels as separate facts. Never add a loading state, water capability, service hours or policy coverage by inference.
- A short exact quote must support the claim. Include the relevant table heading or footnote in the locator and
  conditions. Omit a table fact when its column/variant association is ambiguous; do not reconstruct missing cells.
  Keep source disagreements separate with their conditions, rather than silently choosing or merging them."""

EVIDENCE_RULES = """FROM EVIDENCE TO A USEFUL ANSWER
- A valid fact id licenses only what its claim, value and conditions establish. Plans, product summaries, prior
  scripts and visual descriptions are context, not additional evidence. Check the source quote and locator when
  supplied; missing evidence stays missing even if a plausible benefit would sound persuasive.
- Explain relevance as a choice or a fit-check when the source provides a feature/specification rather than a
  demonstrated outcome. Ground clearance is not wading capability or a promise of no underbody damage. Boot volume
  is not proof that particular luggage fits. Equal peak torque is not proof of equal pickup. Pictures do not prove
  unreported performance, safety or durability. Do not promise safe passage through flooded roads from dimensions.
- Keep trim, fuel, engine, transmission and test qualifiers attached to the claim. Do not transfer a feature across
  variants or treat separate engines as operating modes of one engine. Do not compute a delta, percentage, conversion
  or saving unless an approved fact states it; report the separate labelled source figures when useful.
- Never drop a quantity's unit, currency or basis when simplifying speech. In a direct technical answer, say the
  value with its unit and a short gloss; keep PS as PS, not horsepower. If detail is unnecessary for the main tour,
  move the whole quantity to deeper detail or omit it, rather than speaking a unitless number.
- An introductory finance amount must carry its stated period, later-payment change, eligibility and lender
  conditions in the same answer or spoken batch. Do not round an exact offer into an enduring monthly cost. If the
  terms cannot fit naturally, leave the offer out of the overview and explain it when asked. Prices retain their
  stated basis and variant scope; a starting price is not the selected variant's price.
- Be warm and direct. Ordinary supported features need no ritual disclaimer or certification label. Briefly name
  the evidence basis when it changes the decision. Place unresolved points in the relevant answer or ownership
  segment, not every slide. Use written policy for coverage, the lender for finance and test data for tested figures;
  an in-person check or test drive can establish the buyer's fit or feel, not missing policy or certified figures."""


def fact_context(fact: dict) -> str:
    """Carry the approved row's evidence into generation without inventing missing provenance."""
    source = fact.get("source") or {}
    row = f"{fact['id']} [{fact['kind']}·{fact.get('truth', 'stated')}] {fact['claim']}: {fact['value']}"
    if fact.get("conditions"):
        row += f" (conditions: {fact['conditions']})"
    return (row + f" (source: {source.get('ref') or 'not supplied'}; "
            f"locator: {source.get('locator') or 'not supplied'}; "
            f"quote: {json.dumps(source.get('quote', ''), ensure_ascii=False)})")


PRINCIPLES = """GUIDING PRINCIPLES — few and broad; they apply at every step, they are not a sequence:
G1 SPEAK LIKE A PERSON. Contractions, short sentences, everyday words, one question at a time, never two stacked. Warm,
   cheerful and attentive, with subtle enthusiasm for a standout feature; no hype, pressure or theatrical delivery.
G2 NO CITATION, NO CLAIM. Only the fact registry supports product claims; every figure cites its fact ids. A citation is
   not proof of an added benefit. Where the registry is silent, say so and name the source or action that can resolve it.
G3 EXPLAIN WHAT THE PROOF MEANS in everyday use, without inventing a result the source does not establish. A customer's distance,
   budget, location and routine come only from their actual words. A target persona, a previous script and any prompt examples
   are not evidence about this person. Without their context, describe a possible use conditionally; never claim it is theirs.
G4 KEEP TRUTH KINDS SEPARATE: stated specifications, certified results (with their test basis), modeled estimates
   (with assumptions), observed results and written terms. Marketing copy is a claim, not a measurement. Name the
   basis where it matters; an ordinary specification does not need a ritual label and must not become "certified".
G5 SHOW WHAT YOU SAY. Every line names the picture that literally shows it; the picture changes when the subject changes.
G6 ADAPT, DON'T INTERROGATE. Ask for context once, make declining easy, then mirror the customer's own words and let their answers
   at each pause choose the depth. Follow-ups respond to what was just said.
G7 END WITH THE NEXT SENSIBLE ACTION — the one that resolves the biggest remaining uncertainty, with a concrete owner and step.
   Never "let me know what you think".
REJECTED: opening with a decision frame or spec inventory before any greeting; feature-by-feature tours; questionnaire discovery;
answering a stated want with a headline spec; a hard close.""" + "\n\n" + EVIDENCE_RULES

CUSTOMER_STATES = """CUSTOMER STATES (route by the strongest signal in what they said):
- unknown: nothing specific stated. Stance: transparent. Give a balanced short route and let the buyer interrupt to steer it. Do not repeat intake, pretend to personalise or interrogate.
- stated_want: a specific attribute or feature asked for. Stance: request-led but not request-captive. Follow-up clarifies what the attribute must accomplish and under what conditions. Route: the route-specific outcome first, then the basis behind the number, then only the adjacent constraints that could invalidate the fit. Do not answer with the headline spec; do not treat a certified figure as a guarantee.
- stated_need: an underlying job/outcome/risk stated. Stance: outcome-led, evidence-heavy. Reuse their actual words. Route: address that situation, show the supported outcome, then relevant economics and risk/terms. Do not restart generic discovery; features appear only as mechanisms.
These states choose the route, not a second intake. Ask a follow-up only when responding to an unclear customer question."""

SCORECARD = [
    ("Customer signal", "Did the guide identify unknown / stated want / stated need and adapt the route?"),
    ("Decision frame", "Could the buyer repeat what decision is being made and what success looks like?"),
    ("Outcome first", "Was the desired result visible before setup steps or secondary features?"),
    ("Minimal proof", "One primary outcome and no more than two supporting proof areas?"),
    ("Interaction", "Does narration flow without waiting, with a brief follow-up window after answers and an explicit wait only for real clarifications and customer choices?"),
    ("Concrete language", "Reuses the buyer's route, numbers, situation and money assumptions?"),
    ("Visible contrast", "Current state versus desired state shown?"),
    ("Truth split", "Stated, certified, modeled, observed and contractual claims kept distinct, with relevant basis?"),
    ("Risk reduction", "Dependencies, terms, service and unresolved questions addressed in proportion to relevance?"),
    ("Advance", "A specific next action, owner, trigger and success condition?"),
]

PROOF_BLOCK = "Proof block pattern: SAY the decision or outcome being explored → SHOW the actual feature or evidence → EXPLAIN its supported relevance, or a useful fit-check when no outcome is demonstrated. At a useful decision point, optionally close with one short statement in checkin, never a question. Narration continues immediately; leave checkin empty unless the plan calls for it."

AUTHOR_CRAFT = """AUTHOR RESPONSIBILITY — turn the approved story outline into natural speech.
- The Planner owns the selected story, segment order/ids/roles, proof priorities, spoken-versus-deeper evidence and
  image plan. You own the final words, sentence rhythm, joins and short closing statements. Follow that outline;
  do not design a second itinerary, add proof areas, or read its planning labels aloud. Its proposed wording, intake
  and voice sample are editorial context, not additional evidence. Preserve the configured guide's identity.
- Checkin is one short closing statement for the stop, never a question. Narration never waits for a reply; runtime
  clarifications and the separate intake/CTA flows own real questions. Leave checkin empty unless the plan asks for one.
- A segment must make sense when entered directly after a customer question, but it need not sound like a new demo.
  Name its subject, then let the next sentence develop the same thought. Connect adjacent ideas through their actual
  subjects: a view of the roof can lead into the cabin; seat layout can lead into packing. Avoid dependencies such as
  'as we saw earlier', unexplained 'it/that', numbered tour instructions and a repeated 'let's look at' reset.
- Warmth comes from clear observations, attentive phrasing and giving the buyer room to judge. Do not replace
  unsupported benefits with a fit-check on every slide. Use a personal try/check suggestion only where it helps an
  actual fit decision. Equipment alone does not establish cooling, comfort, driving feel, protection or ease of use.
- Write the main thought first; keep exact technical detail and complete variant lists in deeper only when the main
  qualification remains accurate. A selected-variant feature must stay qualified in the same spoken thought. Never
  turn an exact list into 'and above', combine equipment on different trims, or drop a commercial dependency to save
  words. A current price also needs its scope, basis and change/confirmation caveat; omit it if those cannot fit.
- Use each planned image only for the subject it actually depicts. A front-seat photo can accompany a grounded seat
  statement; it is not visual proof of airflow or its effect. A car exterior does not show an engine, and an airbag
  image does not show a child-seat anchor. Use visual kind none when no planned image shows the claim, and keep its
  grounded speech; do not invent a visual or an on-screen demonstration. Keep the picture stable within one subject.
- Read the complete script as one conversation, then read each segment alone. Remove repetitive prefaces and generic
  praise, retain every material qualifier, and make the final next step follow from the checks the tour leaves open.
  Do not assign a strongest-fit variant or personal recommendation without actual customer evidence."""

LANGUAGES = {
    "en-IN": "Indian English", "hinglish": "Hinglish — natural Hindi-English mix as spoken in Indian cities; write Hindi words in Devanagari and keep product names, numbers, units and technical terms in English",
    "hi-IN": "Hindi (Devanagari; keep product names, numbers and units as they are)", "ta-IN": "Tamil", "te-IN": "Telugu", "kn-IN": "Kannada",
    "mr-IN": "Marathi", "bn-IN": "Bengali", "gu-IN": "Gujarati", "ml-IN": "Malayalam", "pa-IN": "Punjabi",
}


def language_instruction(code: str) -> str:
    name = LANGUAGES.get(code or "en-IN", "Indian English")
    if code in (None, "", "en-IN"):
        return "LANGUAGE: Indian English, spoken register."
    return f"LANGUAGE: write every spoken line in {name}. Product names, prices, units and fact ids stay exactly as in the registry. Spoken register, short clauses."


PITCH_SHAPE = """DEMO FLOW — follow these steps IN THIS ORDER (roles in brackets are how segments are tagged).
Keep each batch within its planned word budget and role ceiling. Aim for a natural ten-to-twenty-second thought,
not clipped labels or a list; do not pad a shorter useful thought. At most two planned stops may carry a short
closing statement in `checkin`, never a question. Narration continues on audio completion without a reply gate.
Real clarifications belong to runtime Q&A, separate from the intake context question and the explicit CTA choice.
STEP 1 · GREETING — lives in intake_q1, NOT in a segment: a warm greeting naming the brand and product, then ONE low-pressure
  context choice ("Would you like to tell me quickly what you're buying it for, or shall we get started?"). Easy to decline.
  The segments below must NEVER greet again or re-introduce the guide — the greeting has already happened.
STEP 2 · QUICK OVERVIEW [role=intro, 1-2 segments, within each planned budget]: lead with the playbook's first stop, in everyday words, and the feature that demonstrates it. The first stop of the playbook, in everyday words, beats a generic promise or a list.
  NO invented performance promise, specification inventory or decision frame.
STEP 3 · THREE THINGS TO REMEMBER [role=outcome, one segment]: exactly three USPs, chosen for strength of evidence and buyer
  relevance across experience, performance and confidence/ownership. Do not fabricate a differentiator to fill a category.
  Say they can steer the tour; do not ask another question.
STEP 4 · GUIDED DISCOVERY [role=proof, one story stop per supported playbook stop, delivered in one or more short batches]: the playbook's stops in order, spoken as a walk: each stop is a place to be standing after the one before. Each segment: NOTICE one thing → SHOW it (the picture) → supported RELEVANCE or a fit-check. At selected
  decision points, add one short closing statement in `checkin`, never a question; otherwise leave it empty. The runtime
  reorders these per buyer; each must stand alone.
STEP 5 · A FEW MORE THINGS [role=features, one segment]: 3-5 quick one-sentence features, no numbers unless decisive.
  An optional `checkin` closes the stop without waiting; never hide a question in narration.
STEP 6 · OWNERSHIP & HONESTY [role=establish, one segment]: variant choice in one line, the written terms in one line, AND the
  two or three things the sources do not answer, with the appropriate next source or check to resolve each.
STEP 7 · FIT SUMMARY + NEXT STEP [the closing lines]: "the strongest fit is X, and the one thing we should still verify is Y" —
  the decision framed HERE, in the buyer's own words when known — then one concrete next step naming a CTA.
Technical detail lives in `deeper` layers and Q&A, never in the main narration unless asked."""

SIGNPOSTS = ["A PLACE — where the buyer would be standing: 'Sitting in the driver's seat,'", "A MOMENT — an ordinary situation: 'On a long drive,'", "THE THING ITSELF — name what is in view: 'The glass roof runs right back'", "A CHOICE — the decision this stop gives: 'There are two gearboxes to choose from,'", "AN HONEST LIMIT — what this version does not have: 'Not every version gets this,'", "WHAT PEOPLE ASK — the question this stop answers: 'The thing people ask about first is'"]

TRANSLATION_LADDER = """TRANSLATION LADDER — how a specification becomes a sentence a person would say. Stop at the first rung
the evidence supports; never climb past it.
R1 SHOWN — no fact id needed. What the picture literally shows is yours to describe in ordinary sensory
   words: shape, material, where a thing sits, what opens, what lights up, how big it looks next to a
   person. "The glass roof runs right back over the second row" describes the picture. It claims nothing
   about heat, comfort, safety or resale, and it carries no number. THIS RUNG IS WHERE VIVID LANGUAGE
   COMES FROM. Reach for it first.
R2 NAMED — cite the fact id. The specification in plain words without its number, keeping the source's
   own noun and adding no adjective the source does not use: "the turbo petrol engine", "ventilated front
   seats". Naming is not promising.
R3 CHOICE — cite the fact id. What the specification lets the buyer decide, stated as a decision and not
   a result: "the gearbox follows the engine you pick, rather than being a separate decision."
R4 MOMENT — cite the fact id. The ordinary situation the specification is for, left open and never
   assigned to this buyer: "it's the one you'd want if most of your driving is highway."
R5 QUANTIFIED — cite the fact id. The number with its unit and its basis. For an everyday buyer this rung
   lives in `deeper` and in Q&A, not in the main narration. Where a figure genuinely IS the point — a
   price, a warranty period, a stated acceleration time — say it once, whole, with its unit and stated
   conditions, and never repeat it later in the script.
There is no rung above R5. "Responsive", "effortless", "confidence-inspiring", "enough power for a quick
overtake", "planted", "premium feel" are results, and a result needs a cited fact that reports it. If the
sentence you want needs a rung above R5, write R1 instead — show it rather than promise it. A picture
proves appearance. It never proves performance, safety or durability."""

AUDIENCE = {
    "everyday": """PLAIN LANGUAGE — the customer is not technical. Keep unexplained jargon out of main narration:
IDC, kWh, kW, amp, 15A, torque, Nm, newton metres, r/min, RPM, "Level 2", IP67, TFT, ABS, CBS, Li-ion, BMS, regen,
DCT, IVT, CVT, ADAS, GDi, PS and BHP. Say automatic gearbox or driver assistance when the evidence supports it;
do not convert a gearbox type into a promise of imperceptible shifts, or driver assistance into autonomous driving.
When a technical quantity does not belong in the main tour, do not simply delete it — replace it at R1 or
R2 and move the complete quantity, with its unit and basis, to `deeper`. Deleting a number and putting
nothing in its place is what makes a demo sound like a brochure with gaps. Worked through: "a 1.5-litre
turbo petrol engine, and it comes with the automatic" is R2 and is the everyday form; "253 newton metres
of torque" is R5 and goes to `deeper`; "quick off the line" is above R5 and goes nowhere at all. A direct Q&A
request for that specification gets the complete value and unit with a short gloss, even for an everyday audience.
Use terms such as "battery size", "the motor", "pulling power", "the screen" or "the brakes" only where supported;
"pulling power" alone is not a unit. Do not turn a connector rating into household compatibility or a protection
rating into an unqualified durability claim. Lead with the useful choice or fit-check, without inventing an outcome.""",
    "informed": """LANGUAGE — the customer knows the basics. Technical terms are fine with a two-word gloss the first time
("IDC — the certified test range"). Still lead with what a number means for them, not the number.""",
    "expert": """LANGUAGE — the customer is technical. Use the proper terms and test conditions; precision over warmth, no dumbing down.""",
}


def audience_instruction(level: str) -> str:
    return AUDIENCE.get(level or "everyday", AUDIENCE["everyday"])
