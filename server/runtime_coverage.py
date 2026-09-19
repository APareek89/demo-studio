"""Coverage claims that cannot be established by selected source passages.

This is a conservative text guard, not an entailment engine. Runtime retrieval
and source lookup return subsets; even a successful fetch with no warnings does
not prove a page-wide negative or an exhaustive reading. Apply this before web
attribution. A match licenses only the fixed own-verification limitation below,
never the original text or its citations. Product absence and commercial terms
still belong to normal assertion validation.
"""
from __future__ import annotations

import re


_SOURCE = r"(?:web\s*pages?|websites?|sites?|pages?|sources?|records?|documents?|brochures?|manuals?|materials?|evidence)"
_REPORT = r"(?:states?|shows?|mentions?|lists?|includes?|covers?|contains?|provides?|specif(?:y|ies)|details?|documents?|publish(?:es)?|discloses?|reports?)"
_REPORTED = r"(?:stated|shown|mentioned|listed|covered|included|provided|specified|detailed|documented|published|disclosed|reported)"
_ADVERBS = r"(?:(?:explicitly|currently|actually|anywhere|ever|still|itself|themselves)\s+){0,3}"
_DESTINATION = r"(?:here|there|anywhere|(?:in|on|by|from|within)\s+[^.!?;]{0,90}\b" + _SOURCE + r"\b)"

# Bind the reporting predicate to the source subject. A reference to a page
# earlier in a product sentence must not turn 'the E trim does not include ADAS'
# into a statement about the page's coverage.
_ACTIVE_ABSENCE = re.compile(
    r"\b" + _SOURCE + r"\s+" + _ADVERBS
    + r"(?:does not|do not|doesn't|don't|did not|didn't|never|has not|have not|hasn't|haven't)\s+"
    + _ADVERBS + r"(?:" + _REPORT + r"|" + _REPORTED + r")\b", re.I)
# A directly coordinated 'page lists ..., but it does not mention ...' keeps
# the page as its subject. Do not infer that ownership across sentences,
# embedded clauses or a possible intervening singular product referent.
_COORDINATED_SOURCE_ABSENCE = re.compile(
    r"\b" + _SOURCE + r"\s+" + _ADVERBS + _REPORT
    + r"\b(?P<object>[^.!?;]{0,180}?)\s*,?\s+(?:but|and|yet)\s+it\s+"
    + _ADVERBS + r"(?:does not|doesn't|did not|didn't|never|has not|hasn't)\s+"
    + _ADVERBS + r"(?P<negative_report>" + _REPORT + r"|" + _REPORTED + r")\b", re.I)
_EMBEDDED_SOURCE_CLAUSE = re.compile(
    r"\b(?:that|which|who|where|when|while|because|although|but)\b", re.I)
_POSSIBLE_PRODUCT_REFERENT = re.compile(
    r"\b(?:product|service|item|plan|package|policy|warranty|vehicle|car|trim|variant|model|feature)\b", re.I)
_BARE_NAMED_REFERENT = re.compile(
    r"\s*(?:[Tt]he\s+)?[A-Z][A-Za-z0-9()_-]*(?:\s+[A-Z][A-Za-z0-9()_-]*){0,2}\s*,?\s*")
_PRODUCT_OR_REPORTING_PREDICATE = re.compile(
    r"(?:includes?|included|covers?|covered|contains?|provides?|provided)", re.I)
_PASSIVE_ABSENCE = re.compile(
    r"\b(?:not|never|isn't|aren't|wasn't|weren't)\s+" + _ADVERBS + _REPORTED
    + r"\s+" + _DESTINATION + r"\b", re.I)
_MISSING_FROM = re.compile(
    r"\b(?:missing|absent|omitted)\s+(?:from|in|on)\s+[^.!?;]{0,90}\b" + _SOURCE + r"\b", re.I)
_NEGATIVE_SOURCE = re.compile(
    r"\b" + _SOURCE + r"\s+(?:(?:itself|currently|still)\s+)?"
    r"(?:omits?\b|lacks?\b|(?:is|are|remains?)\s+silent\s+(?:on|about)\b|"
    r"(?:has|have|contains?|provides?|gives?|makes?)\s+(?:no\s+(?:mention|reference|information|details|record)|nothing)\b)", re.I)
_NO_SOURCE = re.compile(r"\b(?:no|none of (?:the|these|those))\s+" + _SOURCE + r"\b", re.I)
_NO_MENTION = re.compile(
    r"\b(?:no\s+(?:mention|reference|information|details|specifications|record|evidence)|nothing)\b"
    r"[^.!?;]{0,120}\b" + _DESTINATION + r"\b", re.I)
_ONLY_CONTENT = re.compile(
    r"\b" + _SOURCE + r"\s+(?:(?:itself|currently)\s+)?(?:only\s+" + _REPORT
    + r"|" + _REPORT + r"\s+only)\b", re.I)
# 'Not available on E' is fitment, not document coverage. Availability absence
# belongs here only when explicitly located in/from records or source material;
# deictic 'there' alone could refer to a car or trim and is left to normal guards.
_UNAVAILABLE_IN_SOURCE = re.compile(
    r"\b(?:(?:not|isn't|aren't|wasn't|weren't)\s+available|unavailable)\s+"
    r"(?:in|from)\s+[^.!?;]{0,90}\b" + _SOURCE + r"\b", re.I)
_EXHAUSTIVE_CHECK = re.compile(
    r"\b(?:checked|read|reviewed|searched|examined|scanned)\s+"
    r"(?:(?:the|this|that|your|provided|supplied|linked)\s+){0,2}"
    r"(?:(?:entire|whole)\s+" + _SOURCE + r"|(?:all|every)\s+(?:sections?|parts?|contents?)\s+of\s+(?:the\s+)?" + _SOURCE + r")\b"
    r"|\b(?:entire|whole)\s+" + _SOURCE + r"\s+(?:was|were|has been|have been)\s+(?:checked|read|reviewed|searched|examined|scanned)\b", re.I)
_GLOBAL_ORIGIN = re.compile(
    r"\b(?:all|every)\s+(?:the\s+)?(?:details?|information|data|specifications?|descriptions?|content)\b"
    r"[^.;!?]{0,85}\b(?:come|comes|came|originate|originates|sourced|taken|obtained)\s+"
    r"(?:directly\s+)?from\b", re.I)

_PATTERNS = (_ACTIVE_ABSENCE, _PASSIVE_ABSENCE, _MISSING_FROM,
             _NEGATIVE_SOURCE, _NO_SOURCE, _NO_MENTION, _ONLY_CONTENT,
             _UNAVAILABLE_IN_SOURCE, _EXHAUSTIVE_CHECK, _GLOBAL_ORIGIN)

# Optional precision for uncited interaction limits only. Each subject slot is
# a requested attribute, not a value, fitment condition or finite product claim.
# Unknown/compound subjects fall back to the generic limit instead of silently
# dropping an unrecognised part. No raw captured clause is returned as speech.
_PASSIVE_SUBJECT = re.compile(
    r"(?:However,\s*)?(?P<subject>.+?)\s+(?:is|are|was|were)\s+"
    r"(?:not|never)\s+" + _ADVERBS + _REPORTED + r"\s+" + _DESTINATION + r"[.]?", re.I)
_BOOT_ATTRIBUTE = re.compile(
    r"(?:(?:the|its)\s+)?(?P<exact>exact\s+)?(?:boot|luggage|cargo)\s+"
    r"(?:capacity|volume)(?:\s+in\s+(?P<unit>litres|liters))?", re.I)
_SEAT_BASIS = re.compile(
    r"(?:(?:the|its)\s+)?seat configuration"
    r"(?:\s+(?:it was measured (?:under|with)|used for (?:the|that) measurement))?", re.I)
_SIMPLE_ATTRIBUTE = re.compile(
    r"(?:(?:the|its)\s+)?(?:(?:exact|specific)\s+)?"
    r"(?P<attribute>(?:standard\s+|extended\s+)?warranty (?:duration|terms)|tyre size|tire size|measurement basis)", re.I)


def _attribute_limit(text: str) -> str:
    match = _PASSIVE_SUBJECT.fullmatch(text)
    if not match:
        return ""
    parts = re.split(r"\s+(?:and|or)\s+|\s*,\s*(?:(?:and|or)\s+)?", match["subject"])
    if not 1 <= len(parts) <= 3:
        return ""
    attributes = []
    for part in parts:
        if attribute := _BOOT_ATTRIBUTE.fullmatch(part):
            name = ("the exact" if attribute["exact"] else "the") + " boot capacity"
            if attribute["unit"]:
                name += " in litres"
        elif _SEAT_BASIS.fullmatch(part):
            name = "the seat configuration used for the measurement"
        elif attribute := _SIMPLE_ATTRIBUTE.fullmatch(part):
            name = "the " + attribute["attribute"].lower().replace("tire", "tyre")
        else:
            return ""
        attributes.append(name)
    return "I couldn't verify " + " or ".join(dict.fromkeys(attributes)) + " from the retrieved evidence."


def unsupported_coverage_claim(text: str) -> bool:
    """Whether text asserts source coverage beyond selected retrieved passages.

    This adds deictic/passive, explicit omission and exhaustive-reading forms to
    the graph's existing coverage guard. No evidence or warning-list flag can
    bypass it: current runtime evidence carries no complete-coverage proof.
    False does not license a sentence; ordinary grounding must still run.
    """
    if not isinstance(text, str):
        return False
    plain = " ".join(text.replace("’", "'").split())
    return (any(pattern.search(plain) for pattern in _PATTERNS)
            or any(not _EMBEDDED_SOURCE_CLAUSE.search(match["object"])
                   # Bare names can own fitment ('SX ... it does not include').
                   # Capitalized headings cannot bypass reporting-only absence
                   # ('Highlights ... it does not detail warranty terms').
                   and not (_PRODUCT_OR_REPORTING_PREDICATE.fullmatch(match["negative_report"])
                            and (_POSSIBLE_PRODUCT_REFERENT.search(match["object"])
                                 or _BARE_NAMED_REFERENT.fullmatch(match["object"])))
                   for match in _COORDINATED_SOURCE_ABSENCE.finditer(plain)))


def coverage_limitation(text: str, *, precise: bool = False) -> str:
    """Discard the unsafe sentence, including any asserted successful checking.

    Enable ``precise`` only for uncited context/limitation rows. It recognizes a
    closed set of attribute slots; it must not rewrite a cited fact's conditions.
    """
    if not unsupported_coverage_claim(text):
        return ""
    if precise:
        plain = " ".join(text.replace("’", "'").split())
        if limitation := _attribute_limit(plain):
            return limitation
    return "I couldn't verify that from the retrieved evidence."
