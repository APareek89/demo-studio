"""Closed, backend-rendered conversational acts; never product evidence.

The model selects IDs, not speech. ``question`` is trusted only as customer
context (optionally prior customer messages followed by the current message).
No customer substring, value, URL, or model-authored wording reaches the output.
This module does not establish that a product assertion is absent from a source.
"""
from __future__ import annotations

import re
from collections.abc import Mapping
from urllib.parse import urlsplit


SUBJECT_IDS = ("rear_armrest", "personal_comfort", "guaranteed_resale",
               "comparison_evidence", "source_instructions", "lender_approval",
               "product_evidence_boundary")
INPUT_IDS = ("source_url", "city", "variant", "loan_amount", "interest_rate",
             "loan_tenure", "fuel_efficiency", "fuel_price", "travel_distance")
MODES = ("verification_limit", "input_request", "fit_check")

_FAMILIES = {
    "loan": ("loan_amount", "interest_rate", "loan_tenure"),
    "fuel": ("fuel_efficiency", "fuel_price", "travel_distance"),
    "lookup": ("source_url", "city", "variant"),
}
_LIMITS = {
    "rear_armrest": "I couldn't verify whether it has a rear-seat armrest from the reviewed evidence.",
    "personal_comfort": "I cannot confirm how comfortably you or your passengers will fit without a seating check.",
    "guaranteed_resale": "I cannot guarantee a future resale value.",
    "comparison_evidence": "I could not verify reviewed competitor comparison evidence.",
    "source_instructions": "I will keep answering your question, without following instructions from the source page.",
    "lender_approval": "I cannot confirm or guarantee a lender's loan approval.",
    "product_evidence_boundary": "I will only make product claims supported by reviewed evidence.",
}
_LABELS = {
    "source_url": "the public product-page URL",
    "city": "your city", "variant": "the variant you are considering",
    "loan_amount": "the loan amount in rupees",
    "interest_rate": "the annual or monthly interest rate",
    "loan_tenure": "the loan tenure in months or years",
    "fuel_efficiency": "your assumed fuel efficiency in kilometres per litre",
    "fuel_price": "the fuel price in rupees per litre",
    "travel_distance": "your driving distance and its time period",
}
_ALIASES = {
    "source_url": r"(?:url|web(?:site)? link|product (?:page|link)|website|webpage)",
    "city": r"(?:city|location)", "variant": r"(?:variant|trim|configuration)",
    "loan_amount": r"(?:loan amount|loan principal|principal|amount (?:to borrow|borrowed))",
    "interest_rate": r"(?:(?:annual|monthly|loan)\s+)?(?:interest )?rate",
    "loan_tenure": r"(?:tenure|loan term|loan duration|repayment period)",
    "fuel_efficiency": r"(?:fuel efficiency|mileage|fuel economy)",
    "fuel_price": r"(?:(?:fuel|petrol|diesel)\s+(?:price|cost)|price per litre)",
    "travel_distance": r"(?:(?:driving|travel|monthly|yearly)\s+distance|distance)",
}

# Values are detected only to avoid asking for an already-supplied input. They
# are never evaluated, converted, or passed to a calculator by this helper.
_SMALL = r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty)"
_Q = rf"(?:\d+(?:,\d{{2,3}})*(?:\.\d+)?|{_SMALL}(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?)"
_SCALE = r"(?:lakh(?:s)?|lac(?:s)?|crore(?:s)?|thousand|million)"
_MONEY = rf"(?:(?:₹|inr\s*|rs\.?\s*){_Q}(?:\s*{_SCALE})?|{_Q}\s*{_SCALE}(?:\s*(?:rupees?|inr))?|{_Q}\s*(?:rupees?|inr))"
_PCT = rf"{_Q}\s*(?:%|per\s*cent)"
_BASIS = r"(?:annual|annually|yearly|monthly|per\s+(?:annum|year|month)|p\.?a\.?(?=\s|$))"
_PER = r"(?:/|per\s+|each\s+|every\s+|a\s+)"
_EFF = rf"{_Q}\s*(?:km\s*(?:/|per\s+)\s*(?:l|litres?|liters?)\b|kmpl\b|kilomet(?:re|er)s?\s+per\s+lit(?:re|er))"
_PRICE = rf"{_MONEY}\s*(?:/|per\s+)\s*(?:l\b|litres?\b|liters?\b)"
_DIST = rf"{_Q}\s*(?:km|kilometres?|kilometers?)\s*{_PER}(?:month|year|week|day)\b"
_TERM = rf"{_Q}\s*(?:months?|years?)\b"
_NEGATIVE = re.compile(r"\b(?:not|no|never|unknown|undecided|unsure|unconfirmed|unavailable|haven't|hasn't|don't|doesn't|isn't|aren't|ignore|discard|changed|change)\b", re.I)


def _normal(text: str) -> str:
    return text.replace("’", "'").replace("–", "-").replace("—", "-")


def _clauses(text: str):
    # Decimal points are not sentence boundaries. Lines preserve the ordering
    # of server-supplied customer history and subsequent explicit corrections.
    for match in re.finditer(r"[^;!?\n]+(?:[!?;\n]|$)", text):
        clause = match.group()
        for part in re.finditer(r"(?:\d\.\d|[^.])+(?:\.(?!\d)|$)", clause):
            yield match.start() + part.start(), part.group()


def _source_instruction_boundary(text: str) -> bool:
    """Source-authored assistant overrides, not ordinary product instructions."""
    source = r"(?:web\s?page|website|source(?:\s+(?:page|material))?|document|manual|brochure)"
    actor = rf"\b{source}\b[^.!?\n]{{0,60}}\b(?:says?|tells?|asks?|instructs?|orders?|directs?)\b|\b(?:instructions|prompt)\b[^.!?\n]{{0,30}}\b(?:in|on|from)\s+(?:(?:a|the|this|that)\s+)?{source}\b"
    target = r"(?:the\s+)?(?:customer|user)|(?:your|system|private|hidden|previous|developer)\s+(?:instructions|prompt|rules)|(?:my|your|the)\s+(?:question|answer)"
    operation = rf"\b(?:ignore|override|reveal|disclose)\b[^.!?\n]{{0,45}}\b(?:{target})\b"
    return any(re.search(actor, clause, re.I) and re.search(operation, clause, re.I)
               for clause in re.split(r"[.!?\n]", text))


def _product_evidence_boundary(text: str) -> bool:
    """Explicit evidence-bypass requests, never ordinary feature/manual queries.

    Detection licenses only our fixed operating action; it never licenses the
    requested claim, copies its topic, or establishes a product fact. A question
    about refusing the same act gets the same polarity-independent action.
    """
    product = r"\b(?:products?|vehicles?|cars?|models?|variants?|trims?|features?|equipment|specifications?|adas)\b"
    disregard = r"\b(?:ignore|override|disregard)\s+(?:(?:your|the|all|our|reviewed|verified)\s+){0,3}(?:sources?|evidence|records)\b"
    speech = r"\b(?:say|claim|tell|state|pretend|assert)\b"
    fabricate = r"\b(?:invent|fabricate|make\s+up)\b[^.!?\n]{0,60}\b(?:claims?|facts?|evidence|specifications?|features?|equipment)\b"
    return any(re.search(product, clause, re.I) and (
        (re.search(disregard, clause, re.I) and re.search(speech, clause, re.I))
        or re.search(fabricate, clause, re.I))
        for clause in re.split(r"[.!?\n]", text))


def _lender_approval_request(text: str) -> bool:
    """A request about the lending decision, not approval fees or an EMI input."""
    if not re.search(r"\b(?:loan|financing|credit application)\b", text, re.I):
        return False
    determiner = r"(?:(?:my|our|the|this|that|a|any|your|lender's|bank's)\s+)?"
    approval = r"approval\b(?!\s+(?:(?:processing|application)\s+)?(?:fees?|costs?|charges?)\b)"
    decision = (
        rf"\b(?:confirm|guarantee|predict|determine)\s+{determiner}(?:(?:loan|financing)\s+)?{approval}"
        rf"|\b(?:confirm|guarantee|predict|determine)\s+(?:that\s+)?{determiner}(?:bank|lender)\s+(?:will|can|would)\s+(?:approve|sanction)\b"
        rf"|\b(?:will|can|could|would)\s+{determiner}(?:bank|lender)\s+(?:(?:definitely|certainly)\s+)?(?:approve|sanction)\b"
        rf"|\b(?:is|was|has|will|can|could|would)\s+{determiner}(?:loan|financing|credit application)\s+(?:(?:been|be)\s+)?(?:approved|sanctioned)\b"
        rf"|\b(?:will|is|can|could|would)\s+{determiner}(?:loan|financing)\s+approval\s+(?:be\s+)?(?:guaranteed|confirmed)\b"
    )
    return bool(re.search(decision, text, re.I))


def _context(text: str) -> tuple[set[str], set[str]]:
    subjects = set()
    if re.search(r"\b(?:rear(?:[- ]seat)?|back[- ]seat|second[- ]row)\s+(?:(?:centre|center)\s+)?armrest\b", text, re.I):
        subjects.add("rear_armrest")
    if (re.search(r"\b(?:comfort(?:ably|able)?|fit|seating)\b", text, re.I)
            and re.search(r"\b(?:my|our|me|family|passengers?|adults?|heights?|tall|will .* (?:fit|comfortable))\b", text, re.I)):
        subjects.add("personal_comfort")
    if re.search(r"\b(?:resale|residual value|resell)\b", text, re.I):
        subjects.add("guaranteed_resale")
    if (re.search(r"\b(?:competitor|competitors|rival|rivals|competition)\b", text, re.I)
            and re.search(r"\b(?:compar(?:e|ison|isons|ing)|evidence|reviewed|verified|records)\b", text, re.I)):
        subjects.add("comparison_evidence")
    if _source_instruction_boundary(text):
        subjects.add("source_instructions")
    if _lender_approval_request(text):
        subjects.add("lender_approval")
    if _product_evidence_boundary(text):
        subjects.add("product_evidence_boundary")
    inputs = set()
    if re.search(r"\b(?:emi|loan|borrow|repayment|monthly payment)\b", text, re.I):
        inputs.update(_FAMILIES["loan"])
    if re.search(r"\b(?:(?:fuel|petrol|diesel|running)\s+costs?|(?:fuel|petrol|diesel)\s+price|fuel efficiency|fuel economy|mileage)\b", text, re.I):
        inputs.update(_FAMILIES["fuel"])
    if re.search(r"\b(?:url|web(?:site)?|webpage|link|source|competitor|comparison|compare|check online)\b|https?://", text, re.I):
        inputs.add("source_url")
    vehicle_price_context = re.sub(r"\b(?:(?:fuel|petrol|diesel)\s+prices?|price\s+per\s+litre)\b", "", text, flags=re.I)
    if re.search(r"\b(?:price|pricing|on[- ]road|quotation|insurance quote)\b", vehicle_price_context, re.I):
        inputs.update(("city", "variant"))
    return subjects, inputs


def _valid_url(text: str) -> bool:
    for raw in re.findall(r"https?://[^\s<>\"']+", text, re.I):
        try:
            url = urlsplit(raw.rstrip(".,);!?"))
            # This is presence, not permission to fetch. The actual tool still
            # enforces public-host, port, redirect and source-scope restrictions.
            if url.scheme.lower() in {"http", "https"} and url.hostname and not url.username and not url.password:
                return True
        except ValueError:
            pass
    return False


def _focus(text: str) -> tuple[set[str], set[str]]:
    """A previous calculator topic cannot license acts on an unrelated turn."""
    messages = [line.strip() for line in text.splitlines() if line.strip()]
    current = messages[-1] if messages else ""
    subjects, inputs = _context(current)
    if subjects or inputs or len(messages) < 2:
        return subjects, inputs
    # A typed-value/retraction reply can complete the preceding input request.
    # Other topic-free messages do not silently inherit a historic topic.
    previous = next((_context(line) for line in reversed(messages[:-1]) if _context(line)[1]), (set(), set()))
    if any(_value_matches(slot, current, previous[1]) for slot in previous[1]):
        return previous
    if _NEGATIVE.search(current) and any(re.search(_ALIASES[slot], current, re.I) for slot in previous[1]):
        return previous
    return set(), set()


def _matches(pattern: str, clause: str) -> list[re.Match]:
    return list(re.finditer(pattern, clause, re.I))


def _value_matches(slot: str, clause: str, active: set[str]) -> list[re.Match]:
    if slot == "loan_amount":
        matches = _matches(rf"\b(?:loan(?: amount| principal)?|principal|borrow(?:ing)?)\s*(?:of|is|:|=|for)?\s*{_MONEY}|{_MONEY}\s+(?:rupee\s+)?loan\b", clause)
        if re.fullmatch(rf"\s*{_MONEY}[.!]?\s*", clause, re.I) and "loan_amount" in active:
            matches += _matches(_MONEY, clause)
        return matches
    if slot == "interest_rate":
        # A bare percent is insufficient: it may be a discount, not interest.
        return _matches(rf"{_PCT}\s*(?:{_BASIS}\s+)?interest\b(?:\s+{_BASIS})?|(?:(?:(?:annual|monthly)\s+)?interest\s+rate|annual\s+rate|monthly\s+rate)\s*(?:of|is|:|=|at)?\s*{_PCT}(?:\s+{_BASIS})?|{_PCT}\s+{_BASIS}", clause)
    if slot == "loan_tenure":
        named = _matches(rf"\b(?:loan term|loan tenure|tenure|repayment period)\s*(?:of|is|:|=|for)?\s*{_TERM}|{_TERM}\s+(?:loan term|tenure)\b", clause)
        if "loan_amount" in active:
            named += _matches(rf"\b(?:over|for)\s+{_TERM}", clause)
            if re.fullmatch(rf"\s*{_TERM}[.!]?\s*", clause, re.I):
                named += _matches(_TERM, clause)
        return named
    if slot == "fuel_efficiency":
        return _matches(_EFF, clause)
    if slot == "fuel_price":
        return _matches(_PRICE, clause)
    if slot == "travel_distance":
        return _matches(_DIST, clause)
    if slot == "city":
        # Explicit city labels accept a bounded name. Unlabelled locations need
        # capitalized proper-name syntax, never 'my city' or a product code.
        return list(re.finditer(r"\b(?:my city is|city\s*[:=])\s*[A-Za-z][A-Za-z-]*(?:\s+[A-Za-z][A-Za-z-]*){0,2}(?=\s*(?:[.,;?!]|$))", clause, re.I)) + list(re.finditer(r"\bin\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}(?=\s*(?:today|for|including|with|[.,;?!]|$))", clause))
    if slot == "variant":
        return _matches(r"\b(?:variant|trim)\s*(?:is|:|=)\s*[A-Za-z][A-Za-z0-9() -]{0,30}(?=\s*(?:[.,;?!]|$))|\b(?:the\s+)?(?:EX|SX|S|E)(?:\(O\))?(?:\s+Premium)?\s+(?:variant|trim)\b", clause) + list(re.finditer(r"\b(?:EX|SX|S|E)(?:\(O\))?(?:\s+Premium)?(?=\s*(?:[.,;?!]|$))", clause))
    return []


def _supplied(text: str, relevant: set[str]) -> tuple[set[str], bool]:
    state = {slot: False for slot in INPUT_IDS}
    rate_value_only = False
    for _, clause in _clauses(text):
        active = _context(clause)[1] or relevant
        mentions = [(slot, m) for slot in relevant for m in re.finditer(_ALIASES[slot], clause, re.I)]
        retracted = {}
        for negative in _NEGATIVE.finditer(clause):
            nearby = [(min(abs(m.start()-negative.end()), abs(negative.start()-m.end())), slot, m)
                      for slot, m in mentions]
            if nearby:
                distance, target, mention = min(nearby, key=lambda item: item[0])
                if distance <= 35:
                    retracted[target] = max(retracted.get(target, -1), negative.end(), mention.end())
        # A later explicit retraction wins, and a later new value can restore
        # presence. Unrelated negation outside the typed value is not a value.
        for slot in relevant:
            last_value_end = -1
            matches = _value_matches(slot, clause, active)
            for match in matches:
                # Reject a negated candidate or an unknown placeholder. If the
                # customer supplies a corrected value after 'but', keep it.
                left = clause[max(0, match.start()-45):match.start()]
                left = re.split(r",|\b(?:but|instead|actually)\b", left, flags=re.I)[-1]
                if _NEGATIVE.search(left) or _NEGATIVE.search(match.group()):
                    continue
                if slot in {"city", "variant"} and re.search(r"\b(?:unknown|unsure|undecided|not|none|india|hyundai|creta|seltos|my|your|any|which|what)\b", match.group(), re.I):
                    # 'my city is Pune' is a labelled value, not a placeholder.
                    if not (slot == "city" and re.fullmatch(r"my city is [A-Za-z][A-Za-z-]*(?: [A-Za-z][A-Za-z-]*){0,2}", match.group(), re.I) and not re.search(r"\b(?:unknown|unsure|undecided|none|india|not)\b",match.group(),re.I)):
                        continue
                if slot == "interest_rate":
                    local = match.group()
                    annual = bool(re.search(r"\b(?:annual|annually|yearly|annum|per year)\b|\bp\.?a\.?(?:\s|$)", local, re.I))
                    monthly = bool(re.search(r"\b(?:monthly|per month)\b", local, re.I))
                    state[slot] = annual != monthly
                    rate_value_only = not state[slot]
                else:
                    state[slot] = True
                last_value_end = max(last_value_end, match.end())
            if retracted.get(slot, -1) > last_value_end:
                state[slot] = False
                if slot == "interest_rate":rate_value_only = False
    # A real supplied URL should never cause another URL request. Presence does
    # not certify that the site is reachable or safe; lookup owns those checks.
    state["source_url"] = _valid_url(text)
    return {slot for slot, present in state.items() if present}, rate_value_only


def _catalogue(question: str) -> tuple[dict[str, list[str]], bool]:
    if not isinstance(question, str) or not question.strip() or len(question) > 24000:
        return {mode: [] for mode in MODES}, False
    text = _normal(question)
    subjects, inputs = _focus(text)
    supplied, rate_value_only = _supplied(text, inputs)
    return {
        "verification_limit": [x for x in SUBJECT_IDS if x in subjects],
        "input_request": [x for x in INPUT_IDS if x in inputs and x not in supplied],
        "fit_check": ["personal_comfort"] if "personal_comfort" in subjects else [],
    }, rate_value_only


def allowed_act_ids(question: str) -> dict[str, list[str]]:
    """Small context-bound catalogue for the prompt; no raw values or prose."""
    return _catalogue(question)[0]


def render_act(act: Mapping[str, object], *, question: str) -> str:
    """Canonical speech for one valid act, or '' for invalid/irrelevant acts.

    Input IDs are within one family. Already-supplied slots are removed, while
    unknown, irrelevant or mixed-family IDs reject the whole payload. The
    caller must keep acts separate from cited facts and normal evidence guards.
    """
    if not isinstance(act, Mapping) or set(act) != {"mode", "subject_ids", "input_ids"}:
        return ""
    mode, subjects, inputs = act["mode"], act["subject_ids"], act["input_ids"]
    if not isinstance(mode, str) or mode not in MODES:
        return ""
    if not isinstance(subjects, list) or not isinstance(inputs, list):
        return ""
    if any(not isinstance(x, str) for x in [*subjects, *inputs]):
        return ""
    if len(subjects) != len(set(subjects)) or len(inputs) != len(set(inputs)):
        return ""
    catalogue, rate_value_only = _catalogue(question)
    if mode in {"verification_limit", "fit_check"}:
        if inputs or len(subjects) != 1 or subjects[0] not in catalogue[mode]:
            return ""
        return _LIMITS[subjects[0]] if mode == "verification_limit" else "You can check seat comfort together on a test drive."
    if subjects or not 1 <= len(inputs) <= 3:
        return ""
    relevant = _focus(_normal(question))[1] if isinstance(question, str) and len(question) <= 24000 else set()
    if any(x not in relevant for x in inputs) or not any(set(inputs) <= set(family) for family in _FAMILIES.values()):
        return ""
    missing = [x for x in inputs if x in catalogue["input_request"]]
    if not missing:
        return ""
    labels = ["whether your interest rate is annual or monthly" if x == "interest_rate" and rate_value_only else _LABELS[x] for x in missing]
    joined = labels[0] if len(labels) == 1 else " and ".join(labels) if len(labels) == 2 else ", ".join(labels[:-1]) + ", and " + labels[-1]
    return "Could you share " + joined + "?"
