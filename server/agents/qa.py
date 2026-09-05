"""Runtime Q&A — Claude proposes, the validator disposes ('no citation, no claim').
No web search, no tools: only the registry. Unanswerable → don't guess → offer a salesperson callback."""
from __future__ import annotations

import json
import re
import time

from .. import schemas, store, usage
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

DONT_GUESS = "I'm not sure about that from the material I've been given, so I won't guess. I can offer a salesperson callback, or we can carry on."

LOCAL_STOP = set("a an and are as at be by can current did do does for from have how i in is it me much my of on or our please tell that the their there this to was we what when where which who why will with would you your available offered".split())
_qa_reasoning_unavailable_until = 0.0


def _local_terms(text: str) -> set[str]:
    out = set()
    for raw in re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", (text or "").lower()):
        w = raw[:-1] if raw.endswith("s") and len(raw) > 4 and not raw.endswith("ss") else raw
        if len(w) > 1 and w not in LOCAL_STOP:
            out.add(w)
    return out


def _named_competitor(question: str, facts: list[dict]) -> tuple[str, str] | None:
    """Resolve a named rival from the uploaded comparison registry, not a product-specific list."""
    q = question.lower()
    for fact in facts:
        if not fact.get("approved", True):
            continue
        claim = fact.get("claim") or ""
        match = re.match(
            r"comparison\s*[—–:-]\s*(.+?)\s+(?:starting\s+price|price|seating|seats?|fuel\s+tank|tank|range|warranty|dimensions?|power|torque)\b",
            claim, re.I,
        )
        if not match:
            continue
        label = match.group(1).strip()
        aliases = {label.lower()}
        tokens = re.findall(r"[a-z0-9]+", label.lower())
        if tokens:
            aliases.add(tokens[-1])
        if len(tokens) >= 2:
            aliases.add(" ".join(tokens[-2:]))
        if any(re.search(rf"\b{re.escape(alias)}\b", q) for alias in aliases):
            return label.lower(), label
    return None


def _local_grounded_answer(question: str, und: dict, plan: dict) -> schemas.QAOut:
    """Conservative exact-registry fallback when both reasoning providers are unavailable."""
    q = question.lower()
    qterms = _local_terms(question)
    expansions = {
        "dimension": {"length", "width", "height", "wheelbase"},
        "gearbox": {"transmission", "automatic", "manual", "dsg"},
        "mileage": {"fuel", "efficiency"},
        "airbag": {"airbag"},
        "screen": {"screen", "cockpit", "infotainment"},
        "warranty": {"warranty"},
    }
    for term in list(qterms):
        qterms |= expansions.get(term, set())
    official_only = any(x in q for x in ("official", "exact", "today", "current on-road", "current on road"))
    asks_synthetic = any(x in q for x in ("synthetic", "illustrative", "illustration", "estimate", "example"))
    hard_unknown = (
        (any(x in q for x in ("crash rating", "safety rating", "global ncap", "bharat ncap", "five-star", "five star"))) or
        ("crash" in q and any(x in q for x in ("rating", "score", "tested"))) or
        ("ground clearance" in q) or
        (any(x in q for x in ("real-world", "real world", "definitely", "guarantee")) and any(x in q for x in ("mileage", "efficiency", "delivery"))) or
        (any(x in q for x in ("discount", "exchange bonus", "waiting period"))) or
        (any(x in q for x in ("on-road", "on road")) and not asks_synthetic)
    )
    approved = [f for f in und.get("facts", []) if f.get("approved", True)]
    for comp in und.get("competitors", []):
        label = (comp.get("name") or "Competitor").strip()
        for fact in comp.get("facts", []):
            if fact.get("approved", True):
                approved.append({**fact, "claim": f"Comparison — {label} {fact.get('claim', '')}".strip()})
    competitor = _named_competitor(question, approved)
    named_competitor = competitor[0] if competitor else None
    if named_competitor and any(x in q for x in ("price", "cost", "start", "cheap", "expensive")):
        own = next((f for f in approved if (f.get("claim") or "").lower() == "starting price"), None)
        if not own:
            # Some official configurators publish one price per named variant
            # instead of a single "starting price" field. Use the first
            # registry row verbatim; do not infer or label it as the cheapest.
            own = next((f for f in approved if (f.get("claim") or "").lower().endswith("ex-showroom price")), None)
        competitor_fact = next((f for f in approved if named_competitor in (f.get("claim") or "").lower()
                                and "comparison" in (f.get("claim") or "").lower()
                                and "price" in (f.get("claim") or "").lower()), None)
        rule = next((f for f in approved if (f.get("claim") or "").lower() == "comparison response rule"), None)
        if own and competitor_fact:
            product = (und.get("product") or {}).get("name") or "This product"
            label = competitor[1]
            reviewed = re.search(r"reviewed\s+([0-9-]+)", competitor_fact.get("conditions") or "", re.I)
            review_note = f", reviewed {reviewed.group(1)}" if reviewed else ""
            own_label = (own.get("claim") or "price").replace(" ex-showroom price", "", 1)
            own_text = f"The {product} page lists {own['value']}"
            if own_label.lower() not in ("starting price", "price"):
                own_text += f" for {own_label}"
            answer = (f"{own_text}. {label}'s official price page{review_note} lists "
                      f"{competitor_fact['value']}. Current trims, prices and stock need dealer verification.")
            fact_ids = [own["id"], competitor_fact["id"]] + ([rule["id"]] if rule else [])
            return schemas.QAOut(answer=answer, fact_ids=fact_ids, visual_ref="", escalate="", topic=classify(question)[0], cta="", answered=True, clarifying_question="")
    if named_competitor and any(x in q for x in ("seat", "seating")):
        own = next((f for f in approved if (f.get("claim") or "").lower() == "seating capacity"), None)
        competitor_fact = next((f for f in approved if named_competitor in (f.get("claim") or "").lower()
                                and "comparison" in (f.get("claim") or "").lower()
                                and any(x in (f.get("claim") or "").lower() for x in ("seat", "seating"))), None)
        rule = next((f for f in approved if (f.get("claim") or "").lower() == "comparison response rule"), None)
        if own and competitor_fact:
            product = (und.get("product") or {}).get("name") or "This product"
            answer = (f"The {product} is listed as {own['value']}. {competitor[1]} is listed as {competitor_fact['value']}. "
                      "Exact variants and current availability still need verification.")
            fact_ids = [own["id"], competitor_fact["id"]] + ([rule["id"]] if rule else [])
            return schemas.QAOut(answer=answer, fact_ids=fact_ids, visual_ref="", escalate="", topic=classify(question)[0], cta="", answered=True, clarifying_question="")

    # Resolve high-value compound intents before fuzzy overlap. Words such as
    # "seat" and "driver" occur in several unrelated feature labels.
    fact_by_claim = {(f.get("claim") or "").lower(): f for f in approved
                     if not (f.get("claim") or "").lower().startswith("comparison")}
    topic, _ = classify(question)

    def exact(claims: list[str], answer: str) -> schemas.QAOut | None:
        chosen = [fact_by_claim[c] for c in claims if c in fact_by_claim]
        if len(chosen) != len(claims):
            return None
        return schemas.QAOut(answer=answer, fact_ids=[f["id"] for f in chosen], visual_ref="", escalate="", topic=topic, cta="", answered=True, clarifying_question="")

    def exact_rows(claims: list[str], *, include_conditions: bool = False) -> schemas.QAOut | None:
        """Render a narrow, ordered set of exact facts without fuzzy extras."""
        chosen = [fact_by_claim[c] for c in claims if c in fact_by_claim]
        if len(chosen) != len(claims):
            return None
        answer = "From the supplied material: " + "; ".join(
            f"{f.get('claim')}: {f.get('value')}" for f in chosen
        ) + "."
        if include_conditions:
            conditions = []
            for f in chosen:
                condition = (f.get("conditions") or "").strip().rstrip(".")
                if condition and condition not in conditions:
                    conditions.append(condition)
            if conditions:
                answer += " " + "; ".join(conditions) + "."
        return schemas.QAOut(answer=answer, fact_ids=[f["id"] for f in chosen], visual_ref="", escalate="", topic=topic, cta="", answered=True, clarifying_question="")

    if any(x in q for x in ("real-world mileage", "real world mileage")) or ("mileage" in q and "definitely" in q):
        return schemas.QAOut(answer=DONT_GUESS, fact_ids=[], visual_ref="", escalate=question, topic=topic, cta="", answered=False, clarifying_question="")
    if "emi" in q and any(x in q for x in ("guarantee", "guaranteed", "promise")):
        f = fact_by_claim.get("official flexi-scheme starting emi")
        if f:
            condition = f.get("conditions", "").rstrip(".")
            condition = condition[:1].lower() + condition[1:] if condition else "the financier sets the final terms"
            answer = f"No. The page shows {f['value']} as a starting Flexi EMI, but {condition}"
            return schemas.QAOut(answer=answer + ".", fact_ids=[f["id"]], visual_ref="", escalate="", topic=topic, cta="", answered=True, clarifying_question="")
        synthetic = next((f for f in approved if (f.get("claim") or "").lower().startswith("synthetic emi illustration")), None)
        if synthetic:
            return schemas.QAOut(
                answer="No. The EMI figures in this demo are synthetic illustrations, not finance offers; lender approval and final terms still apply.",
                fact_ids=[synthetic["id"]], visual_ref="", escalate="", topic=topic, cta="", answered=True, clarifying_question="",
            )
    if "how many" in q and any(x in q for x in ("people", "seat")):
        f = fact_by_claim.get("seating capacity")
        if f:
            product = (und.get("product") or {}).get("name") or "This product"
            return exact(["seating capacity"], f"The {product} is described as {f['value'].lower()}.")
    if "price" in q and "premium plus" in q and "technology" in q:
        result = exact_rows(["premium plus ex-showroom price", "technology ex-showroom price"], include_conditions=True)
        if result:
            return result
    if "accelerat" in q and "top speed" in q:
        result = exact_rows(["acceleration", "top speed"])
        if result:
            return result
    if "quattro" in q:
        result = exact_rows(["fully variable quattro"], include_conditions=True)
        if result:
            return result
    if "drive select" in q:
        result = exact_rows(["audi drive select"])
        if result:
            return result
    if "dimension" in q and "wheelbase" in q:
        result = exact_rows(["dimensions", "wheelbase"])
        if result:
            return result
    if "climate control" in q:
        result = exact_rows(["climate control"])
        if result:
            return result
    if "ambient" in q and any(x in q for x in ("colour", "color", "light")):
        result = exact_rows(["contour ambient lighting"])
        if result:
            return result
    if "virtual cockpit" in q:
        result = exact_rows(["audi virtual cockpit plus"])
        if result:
            return result
    feature_intents = (
        (("mmi", "touch"), ["mmi navigation plus with mmi touch"]),
        (("bang", "olufsen"), ["bang & olufsen 3d premium sound system"]),
        (("phone box",), ["audi phone box"]),
        (("driver memory",), ["power front seats with driver memory"]),
        (("damper control",), ["suspension with damper control"]),
        (("park assist",), ["360-degree cameras with park assist"]),
        (("sensor-controlled boot",), ["sensor-controlled boot-lid operation", "comfort key"]),
        (("comfort key",), ["comfort key", "sensor-controlled boot-lid operation"]),
    )
    for needles, claims in feature_intents:
        if all(needle in q for needle in needles):
            result = exact_rows(claims, include_conditions=True)
            if result:
                return result
    if ("exterior" in q and "interior" in q) and any(x in q for x in ("colour", "color")):
        result = exact_rows(["exterior colour options", "interior colour options"], include_conditions=True)
        if result:
            return result
    if "test drive" in q:
        result = exact_rows(["official test-drive booking"])
        if result:
            return result
    if "picture" in q and any(x in q for x in ("prove", "equipment", "fitted", "spec")):
        f = fact_by_claim.get("representation disclaimer")
        if f:
            return exact(["representation disclaimer"], f"No. {f['value']}; {f.get('conditions', '').rstrip('.').lower()}.")
    if "ground clearance" in q:
        f = fact_by_claim.get("ground clearance") or fact_by_claim.get("official ground clearance")
        if f:
            return exact_rows([(f.get("claim") or "").lower()], include_conditions=True)
        return schemas.QAOut(answer=DONT_GUESS, fact_ids=[], visual_ref="", escalate=question, topic=topic, cta="", answered=False, clarifying_question="")
    asks_driver_assistance = any(x in q for x in ("adas", "driver-assistance", "driver assistance", "driver assistance system"))
    if asks_driver_assistance:
        selected = [f for f in approved if re.search(
            r"adas|driver[- ]assistance|adaptive cruise", (f.get("claim") or "").lower()
        )]
        if selected:
            answer = "From the supplied material: " + "; ".join(
                f"{f.get('claim')}: {f.get('value')}" for f in selected[:3]
            ) + "."
            return schemas.QAOut(answer=answer, fact_ids=[f["id"] for f in selected[:3]], visual_ref="", escalate="", topic=topic, cta="", answered=True, clarifying_question="")
        return schemas.QAOut(answer=DONT_GUESS, fact_ids=[], visual_ref="", escalate=question, topic=topic, cta="", answered=False, clarifying_question="")
    if "transmission" in q and any(x in q for x in ("diesel", "petrol")):
        manual, auto = fact_by_claim.get("manual transmission"), fact_by_claim.get("automatic transmission")
        if manual and auto:
            answer = (f"The brochure lists {manual['value']} and {auto['value']}. "
                      "Use its powertrain matrix to confirm the exact fuel-and-variant combination.")
            return exact(["manual transmission", "automatic transmission"], answer)
    if "diesel" in q and "power" in q and "torque" in q:
        power, torque = fact_by_claim.get("diesel maximum power"), fact_by_claim.get("diesel maximum torque")
        if power and torque:
            return exact(["diesel maximum power", "diesel maximum torque"], f"The diesel is listed at {power['value']} and {torque['value']}.")
    if any(x in q for x in ("crash rating", "safety rating", "bharat ncap", "five-star", "five star")):
        f = fact_by_claim.get("bharat ncap safety rating")
        if f:
            suffix = " The source pack does not settle the exact protocol year or variant scope, so verify that if it changes your decision." if "variant" in q or "apply" in q else ""
            return exact(["bharat ncap safety rating"], f"The brochure states a {f['value']}.{suffix}")
    if "global ncap" in q and any(x in q for x in ("apply", "variant", "scope")):
        f = fact_by_claim.get("global ncap applicability")
        if f:
            return exact(["global ncap applicability"], f"The supplied material says the Global NCAP result {f['value'].lower()}. That is not every current variant, so verify the exact car before relying on it.")
    if "adas" in q:
        avail, cruise = fact_by_claim.get("adas level 2+ availability"), fact_by_claim.get("adaptive cruise control")
        if avail and cruise:
            availability = avail["value"]
            availability = availability[len("Available on "):] if availability.lower().startswith("available on ") else availability
            answer = (f"Level 2+ is listed for {availability}; adaptive cruise is {cruise['value'].lower()}. "
                      "It assists the driver and does not replace attention.")
            return exact(["adas level 2+ availability", "adaptive cruise control"], answer)
    if "front seats" in q and "powered" in q:
        driver, passenger = fact_by_claim.get("powered driver seat"), fact_by_claim.get("powered co-driver seat")
        if driver and passenger:
            return exact(["powered driver seat", "powered co-driver seat"], f"Yes. The driver seat is listed as {driver['value']}, and the co-driver seat as {passenger['value']}.")
    if "variant" in q and any(x in q for x in ("cheapest", "lowest-priced", "lowest priced", "entry-level", "entry level")):
        count = fact_by_claim.get("variant count") or fact_by_claim.get("variant line-up")
        variant_prices = [f for f in approved if (f.get("claim") or "").lower().endswith("ex-showroom price")]
        if count and len(variant_prices) >= 2:
            answer = (f"The configurator lists {count['value']}. " + " ".join(
                f"{f.get('claim')}: {f.get('value')}." for f in variant_prices
            ) + " I won't turn those reviewed figures into a permanent 'cheapest' label; confirm the current quote with the dealer.")
            return schemas.QAOut(answer=answer, fact_ids=[count["id"]] + [f["id"] for f in variant_prices], visual_ref="", escalate="", topic=topic, cta="", answered=True, clarifying_question="")
        named = next((f for f in approved if any(x in (f.get("claim") or "").lower()
                     for x in ("cheapest variant", "lowest-priced variant", "lowest priced variant", "entry variant"))), None)
        if not named:
            return schemas.QAOut(answer=DONT_GUESS, fact_ids=[], visual_ref="", escalate=question, topic=topic, cta="", answered=False, clarifying_question="")
    candidates = []
    for f in und.get("facts", []):
        if not f.get("approved", True):
            continue
        claim = (f.get("claim") or "").lower()
        value = (f.get("value") or "").lower()
        conditions = (f.get("conditions") or "").lower()
        if claim.startswith("comparison") and not named_competitor:
            continue
        if named_competitor and named_competitor not in (claim + " " + value):
            continue
        if official_only and any(x in (claim + " " + conditions) for x in ("synthetic", "illustrative", "not an official")):
            continue
        if any(x in (claim + " " + conditions) for x in ("synthetic", "unverified", "not stated in the official")) and not any(x in q for x in ("synthetic", "illustrative", "illustration", "estimate", "example")):
            continue
        cterms, vterms = _local_terms(claim), _local_terms(value)
        overlap = qterms & cterms
        score = 3 * len(overlap) + len(qterms & vterms)
        if any(n in qterms and n in cterms | vterms for n in ("1.0", "1.5")):
            score += 3
        if "engine" in q and any(x in q for x in ("available", "offered", "options")) and any(x in claim for x in ("engine type", "1.5l tsi engine", "engine options")):
            score += 5
        if "dimension" in q and claim in ("length", "width", "height", "wheelbase"):
            score += 5
        if "automatic" in q and any(x in q for x in ("gearbox", "transmission")) and "transmission" in claim and any(x in value for x in ("automatic", "dsg")):
            score += 4
        if score:
            candidates.append((score, f))
    if hard_unknown:
        required = ("rating", "ncap", "five-star") if any(x in q for x in ("rating", "ncap", "five-star", "five star")) else tuple(qterms)
        candidates = [(s, f) for s, f in candidates if any(x in _local_terms((f.get("claim") or "") + " " + (f.get("value") or "")) for x in required)]
    if official_only and any(x in q for x in ("on-road", "on road")):
        candidates = [(s, f) for s, f in candidates if any(x in (f.get("claim") or "").lower() for x in ("on-road", "on road"))]
    intent_rx = None
    max_facts = 3
    engine_choice = all(x in q for x in ("1.0", "1.5")) and any(x in q for x in ("between", "decide", "choose", "difference"))
    finance_case = re.search(r"(?:illustration|scenario)\s+([a-z])\b", q, re.I)
    if finance_case:
        intent_rx, max_facts = rf"synthetic emi illustration {finance_case.group(1)}$", 1
    elif official_only and any(x in q for x in ("on-road", "on road")):
        intent_rx = r"on-road|on road"
    elif re.search(r"starting(?:\s+ex-showroom)?\s+price", q):
        intent_rx, max_facts = r"^starting price$", 1
    elif "seating" in q or ("seat" in q and "powered" not in q):
        intent_rx, max_facts = r"^seating capacity$", 1
    elif "transmission" in q and any(x in q for x in ("diesel", "petrol")):
        intent_rx, max_facts = r"^(manual|automatic) transmission$", 2
    elif "fuel type" in q:
        intent_rx = r"^fuel type$"
    elif "fuel-tank" in q or "fuel tank" in q:
        intent_rx = r"fuel tank capacity"
    elif "boot" in q:
        intent_rx, max_facts = r"^boot space$", 1
    elif "dimension" in q:
        intent_rx, max_facts = r"^(length|width|height|wheelbase)$", 4
    elif "turning radius" in q:
        intent_rx = r"turning radius"
    elif "airbag" in q:
        intent_rx = r"airbag"
    elif "adas" in q:
        intent_rx, max_facts = r"adas level 2\+ availability|adaptive cruise control", 2
    elif "safety equipment" in q:
        intent_rx = r"electronic safety|parking sensor|reversing camera|child seat"
    elif "sunroof" in q:
        intent_rx = r"sunroof"
    elif "powered tailgate" in q:
        intent_rx, max_facts = r"^powered tailgate$", 1
    elif "test drive" in q:
        intent_rx, max_facts = r"^test-drive booking$", 1
    elif "sun blind" in q:
        intent_rx, max_facts = r"^rear sun blinds$", 1
    elif "colour" in q or "color" in q:
        intent_rx, max_facts = r"(?:^| )colou?r options$", 2
    elif "ventilated" in q or "electric front seat" in q:
        intent_rx = r"front seats.*electric.*ventilated"
    elif "wireless" in q:
        intent_rx = r"smartphone connectivity|phone box|wireless charging"
    elif "screen" in q or "cockpit" in q or "infotainment display" in q:
        intent_rx, max_facts = r"infotainment display|screen sizes|cockpit sizes|virtual cockpit", 1
    elif "variant" in q:
        intent_rx, max_facts = r"^variant (?:line-up|count)$", 1
    elif "warranty" in q or "service package" in q:
        intent_rx, max_facts = r"(?:standard|vehicle) warranty|roadside assistance|free services", 3
    elif "power" in q and any(x in q for x in ("1.0", "1.5")):
        intent_rx = r"max power"
        wanted_engine = "1.0" if "1.0" in q else "1.5"
        candidates = [(s, f) for s, f in candidates if wanted_engine in ((f.get("claim") or "") + " " + (f.get("value") or ""))]
    elif "manual transmission" in q:
        intent_rx = r"transmission"
        candidates = [(s, f) for s, f in candidates if "manual" in ((f.get("claim") or "") + " " + (f.get("value") or "")).lower()]
    elif "automatic" in q and any(x in q for x in ("gearbox", "transmission")):
        intent_rx = r"transmission"
        candidates = [(s, f) for s, f in candidates if any(x in ((f.get("claim") or "") + " " + (f.get("value") or "")).lower() for x in ("automatic", "dsg"))]
    elif engine_choice:
        intent_rx, max_facts = r"max power|transmission|fuel efficiency", 7
    elif "engine" in q and any(x in q for x in ("available", "offered", "options")):
        intent_rx = r"engine options|engine type|^1\.5l tsi engine$"
    elif "fuel-efficiency" in q or "fuel efficiency" in q or "mileage" in q:
        intent_rx = r"fuel efficiency"
    if intent_rx:
        narrowed = [(s, f) for s, f in candidates if re.search(intent_rx, (f.get("claim") or "").lower())]
        candidates = narrowed
    universal_scope = (
        "standard" in q or "every variant" in q or "all variants" in q or
        "across variants" in q or "across the range" in q
    )
    if universal_scope:
        scope_rx = re.compile(r"\bstandard\b|all variants|every variant|applies across|available on|variant only|from .+ onwards|excluding", re.I)
        candidates = [(s, f) for s, f in candidates if scope_rx.search(" ".join((f.get("value") or "", f.get("conditions") or "")))]
    if any(x in q for x in ("on-road", "on road")) and not asks_synthetic:
        candidates = []
    candidates.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    top = [f for score, f in candidates if score >= 3][:max_facts]
    topic, _ = classify(question)
    cta = ""
    if any(x in q for x in ("book", "test drive", "dealer quote", "buy online")):
        wanted = "book" if "test drive" in q or "book" in q else "contact"
        cta = next((c.get("id", "") for c in plan.get("ctas", []) if c.get("kind") == wanted), "")
    if not top:
        return schemas.QAOut(answer=DONT_GUESS, fact_ids=[], visual_ref="", escalate=question, topic=topic, cta=cta, answered=False, clarifying_question="")
    if engine_choice:
        by_claim = {(f.get("claim") or "").lower(): f for f in top}
        p10 = next((f for k, f in by_claim.items() if "1.0" in k and "max power" in k), None)
        t10 = next((f for k, f in by_claim.items() if "1.0" in k and "transmission" in k), None)
        p15 = next((f for k, f in by_claim.items() if "1.5" in k and "max power" in k), None)
        t15 = next((f for k, f in by_claim.items() if "1.5" in k and "transmission" in k), None)
        fuels = [f for f in top if "fuel efficiency" in (f.get("claim") or "").lower()]
        if all((p10, t10, p15, t15)):
            short = lambda f: str(f.get("value", "")).split("@")[0].strip()
            answer = (f"The one-litre is {short(p10)}, with {t10['value']}. "
                      f"The one-point-five is {short(p15)}, with {t15['value']}. "
                      f"Published efficiency is {', '.join(str(f['value']) for f in fuels)} for the listed transmissions; actual use varies.")
            return schemas.QAOut(answer=answer, fact_ids=[f["id"] for f in top], visual_ref="", escalate="", topic=topic, cta=cta, answered=True, clarifying_question="")
    rows = [f"{f.get('claim')}: {f.get('value')}" for f in top]
    answer = "From the supplied material: " + "; ".join(rows) + "."
    caveat = next((f.get("conditions", "") for f in top if f.get("conditions") and (
        "synthetic" in (f.get("claim") or "").lower() or
        "variant" in q or universal_scope or
        any(x in f.get("conditions", "").lower() for x in ("synthetic", "illustrative", "not an official", "ex-showroom", "verify", "does not print", "not a finance offer"))
    )), "")
    if caveat:
        answer += " " + caveat.rstrip(".") + "."
    return schemas.QAOut(answer=answer, fact_ids=[f["id"] for f in top], visual_ref="", escalate="", topic=topic, cta=cta, answered=True, clarifying_question="")


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
    global _qa_reasoning_unavailable_until
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
    try:
        if time.monotonic() < _qa_reasoning_unavailable_until:
            raise RuntimeError("reasoning providers temporarily unavailable")
        out = claude.structured(sys, question, schemas.QAOut, max_tokens=1500, history=msgs)
    except Exception:
        # Avoid retrying two known-unavailable paid providers for every FAQ
        # question. Exact registry matching remains available and auditable.
        _qa_reasoning_unavailable_until = time.monotonic() + 600
        out = _local_grounded_answer(question, und, plan)
        usage.trace("local-grounded-fallback", "registry-match-v1", latency_ms=(time.monotonic() - started) * 1000,
                    user=question, response=out.model_dump_json(), system="Both configured reasoning providers were unavailable; exact approved registry facts only.")

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
    elif answered:
        _clear_runtime_unknown(demo_id, question)
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
    qterms = _local_terms(q)
    # Do not duplicate a source-extraction gap merely because the runtime
    # phrased it more specifically (for example, "definitely" or a city).
    covered = False
    for u in und.get("unknowns", []):
        if u.get("origin") == "runtime":
            continue
        uterms = _local_terms(u.get("question", ""))
        if uterms and len(qterms & uterms) / len(uterms) >= 0.75:
            covered = True
            break
    if covered:
        before = len(und.get("unknowns", []))
        und["unknowns"] = [u for u in und.get("unknowns", []) if not (
            u.get("origin") == "runtime" and u.get("question", "").strip().lower() == q.lower()
        )]
        if len(und["unknowns"]) != before:
            store.write_json(demo_id, "understanding.json", und)
        return
    for u in und.get("unknowns", []):
        if u.get("question", "").strip().lower() == q.lower():
            return
    cat, doc = classify(q)
    und.setdefault("unknowns", []).append({"id": f"U{len(und['unknowns'])+1:02d}", "question": q, "why_customers_ask": "asked during a demo", "status": "open", "origin": "runtime", "category": cat, "suggested_document": doc})
    store.write_json(demo_id, "understanding.json", und)


def _clear_runtime_unknown(demo_id: str, question: str) -> None:
    """Remove a stale runtime gap once the registry can answer it."""
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        return
    q = question.strip().lower()
    current = und.get("unknowns", [])
    kept = [u for u in current if not (
        u.get("origin") == "runtime" and u.get("question", "").strip().lower() == q
    )]
    if len(kept) != len(current):
        und["unknowns"] = kept
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
