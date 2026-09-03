"""Evidence-based sales principles (condensed from the playbook in
Codex/2026-09-03/wh/outputs/evidence_based_sales_pitch_demo_playbook.json).
These are injected into the plan, author, pitch and Q&A prompts, and drive the demo scorecard."""

PRINCIPLES = """SALES PRINCIPLES — these are decisions, not suggestions:
P01 Frame a decision, not a product. Open with what the buyer must decide and the criteria that make the decision good — never company history or a feature inventory.
P02 Adapt to the strongest signal. Unknown buyer → discover the improvement sought. Stated want → clarify the conditions behind it. Stated need → recap it in their words and prove it first.
P03 A want is a clue, not the diagnosis. A requested feature is a position; uncover the job, consequence and desired payoff before asserting fit ("do you need 100 km in one day, or to charge less often?").
P04 Show the outcome before the machinery. The customer-relevant end state comes first; explain only the product actions needed to make it real. Never open with settings, menus, setup steps.
P05 One takeaway through one journey. One primary outcome and at most two supporting outcomes. Not the whole product.
P06 Short proof blocks, frequent checks. Every proof block is SAY (name the outcome tested) → SHOW (one observable result) → TRANSLATE (what it means for this customer) → CONFIRM (a question tied to what was shown). No uninterrupted explanation beyond ~60 seconds (~150 spoken words).
P07 Speak concretely. Reuse the buyer's nouns and numbers — their route, kilometres, parking spot, hours available, tariff, current spend. Never "smart / convenient / economical" without an observable detail.
P08 Make the contrast visible. Today's cost, friction or uncertainty next to the desired routine after purchase.
P09 Sell confidence, not certainty. Keep four kinds of truth separate and name them: CERTIFIED (official test method, with its condition), MODELED (estimate under stated assumptions), OBSERVED (what happened in real or test use), CONTRACTUAL (what the written terms promise). State assumptions, exclusions and unresolved dependencies. Say when you would NOT recommend the product.
P10 Close for an advance. End with the buyer action that resolves the largest remaining uncertainty — a test that produces evidence — with an owner and a date or trigger. Never "let me know what you think".
REJECTED APPROACHES: fixed feature-by-feature walkthrough; interrogation before showing any value; a generic "revolution" opening any competitor could reuse; answering a stated want literally with a headline spec; a savings-only pitch; a hard close.
FRAME SEQUENCE: Frame (decision + takeaway + permission + one open question) → Reveal (locate the buyer: unknown / stated want / stated need; one follow-up on their answer, not a questionnaire) → Act (the desired end state, in the buyer's numbers) → Map (1 primary + ≤2 supporting proof blocks) → Establish (assumptions, risks, written terms, when not to recommend) → Advance."""

CUSTOMER_STATES = """CUSTOMER STATES (route by the strongest signal in what they said):
- unknown: nothing specific stated. Stance: hypothesis-led, transparent. Follow-up: "what would have to improve for the change to feel worthwhile?" then "walk me through a normal day". Route: short vision of the 2-3 fit dimensions, then one layer deeper on their reaction. Do not pretend to personalise; do not interrogate; do not give the full walkaround.
- stated_want: a specific attribute or feature asked for. Stance: request-led but not request-captive. Follow-up clarifies what the attribute must accomplish and under what conditions. Route: the route-specific outcome first, then the basis behind the number, then only the adjacent constraints that could invalidate the fit. Do not answer with the headline spec; do not treat a certified figure as a guarantee.
- stated_need: an underlying job/outcome/risk stated (e.g. "cheaper 45 km commute without range worry"). Stance: outcome-led, evidence-heavy. Follow-up confirms the need and its stakes in their words. Route: recreate their situation, show the outcome, then economics, then risk/terms. Do not restart generic discovery; features appear only as mechanisms."""

SCORECARD = [
    ("Customer signal", "Did the guide identify unknown / stated want / stated need and adapt the route?"),
    ("Decision frame", "Could the buyer repeat what decision is being made and what success looks like?"),
    ("Outcome first", "Was the desired result visible before setup steps or secondary features?"),
    ("Minimal proof", "One primary outcome and no more than two supporting proof areas?"),
    ("Interaction", "Follow-up questions and no long uninterrupted explanation (≤ ~150 words per block)?"),
    ("Concrete language", "Reuses the buyer's route, numbers, situation and money assumptions?"),
    ("Visible contrast", "Current state versus desired state shown?"),
    ("Truth split", "Certified, modeled, observed and contractual claims kept separate and named?"),
    ("Risk reduction", "Dependencies, terms, service and unresolved questions addressed in proportion to relevance?"),
    ("Advance", "A specific next action, owner, trigger and success condition?"),
]

PROOF_BLOCK = "Proof block pattern: SAY the outcome being tested → SHOW one observable result (a visual) → TRANSLATE what it means for this customer → CONFIRM with a question that tests relevance or uncovers the next constraint."

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


PITCH_SHAPE = """DEMO SHAPE — a 3-minute pitch, then questions (the customer decides what goes deeper):
- OPENING (≤ 60 s, fixed): frame the decision in one breath, then the outcome in the customer's life — e.g. "for a
  fifteen-kilometre commute that's about a week between charges, on the certified figure". Signpost it:
  "Let's start with what matters most to you —".
- MAIN PITCH (60–90 s): the top two or three things that make this product the right choice — pain point first, then the
  one feature that removes it, then what it means day to day. Signpost: "Now — what sets this one apart —".
- MORE FEATURES (60–90 s, one block): three to five other things worth knowing, one sentence each, no numbers unless they
  decide something. Signpost: "Quickly, a few more things you'll like —" and end with "ask me about any of these".
- CLOSE (≤ 30 s): the honest condition ("I wouldn't recommend it if…"), the written terms in one line, the next step.
Technical detail lives in the `deeper` layers and in Q&A — never in the main narration unless the customer asks.
Every number spoken is translated into the customer's routine (days between charges, monthly cost, minutes of charging)."""

SIGNPOSTS = ["Let's start with what matters most to you —", "Now — what sets this one apart —", "Here's the part people ask about first —",
             "Quickly, a few more things you'll like —", "One honest caveat before you decide —", "So, where that leaves you —"]

AUDIENCE = {
    "everyday": """PLAIN LANGUAGE — the customer is not technical. NEVER say: IDC, kWh, kW, amp, 15A, torque, Nm, IP67, TFT, RPM, ABS, CBS,
Li-ion, BMS, regen. Say instead: "certified on the standard test", "battery size", "the motor", "a normal household socket — the
same plug point your geyser uses", "pulling power", "sealed against water and dust", "the screen", "the brakes". Keep only the
numbers that decide (range, charging time, price, warranty) and translate each into daily life. Put technical detail in the
`deeper` layer; in Q&A give the plain answer first and offer the detail.""",
    "informed": """LANGUAGE — the customer knows the basics. Technical terms are fine with a two-word gloss the first time
("IDC — the certified test range"). Still lead with what a number means for them, not the number.""",
    "expert": """LANGUAGE — the customer is technical. Use the proper terms and test conditions; precision over warmth, no dumbing down.""",
}


def audience_instruction(level: str) -> str:
    return AUDIENCE.get(level or "everyday", AUDIENCE["everyday"])
