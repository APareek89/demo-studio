"""Closed conversational acts, separate from product assertions and calculations.

Only the recognised act and its known input slots reach the returned speech.
The caller must use this for uncited interaction text, never cited fact rows.
"""
from __future__ import annotations

import re


_INPUT_NAMES = {
    "loan amount": "loan amount", "principal": "principal",
    "interest rate": "interest rate", "loan term": "loan term", "tenure": "tenure",
    "distance": "distance", "driving distance": "distance", "typical driving distance": "distance",
    "fuel efficiency": "fuel efficiency", "expected fuel efficiency": "fuel efficiency",
    "fuel efficiency figure": "fuel efficiency",
    "fuel price": "fuel price", "local fuel price": "fuel price",
}
_QUANTITY = re.compile(r"\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                       r"hundred|thousand|million|lakh|crore|percent)\b", re.I)
_NO_ASSUMPTION = re.compile(
    r"(?:Understood,\s*)?I\s+(?:will not|won't)\s+"
    r"(?:guess|assume|estimate)(?:\s+(?:or|and)\s+(?:guess|assume|estimate)){0,2}\s+"
    r"(?P<inputs>.+?)[.!]?", re.I)
_REQUEST_INPUTS = re.compile(
    r"(?:Whenever (?:you would|you'd) like to (?:check|calculate|estimate) "
    r"(?:running costs?|fuel costs?|it),\s*)?"
    r"(?:please\s+)?(?:just\s+)?(?:share|provide|tell me|let me know)\s+"
    r"(?P<inputs>.+?)"
    r"(?:,\s+and we can (?:calculate|estimate) (?:it|them)(?: directly)?)?[.!]?", re.I)
_KEEP_FOCUS = re.compile(
    r"No,\s+(?:that|it)\s+(?:will not|won't|does not|doesn't) change my "
    r"(?:answer|focus|response)(?: at all)?[.!]?", re.I)
_HELP = re.compile(
    r"(?:I am|I'm) here to (?:assist|help) you(?: directly)? with your questions"
    r"(?: about (?P<topic>.+?))?[.!]?", re.I)


def _inputs(text: str) -> list[str]:
    """Parse a list of slot names, never supplied values or an open noun phrase."""
    if re.search(r"\band\b", text, re.I) and re.search(r"\bor\b", text, re.I):
        return []  # Mixed alternatives require more context than this act carries.
    text = re.sub(r",\s*(?:and|or)\s+", ",", text, flags=re.I)
    parts = re.split(r"\s*,\s*|\s+(?:and|or)\s+", text)
    if not 1 <= len(parts) <= 8:
        return []
    names = []
    for part in parts:
        part = re.sub(r"^(?:your|the|a|an)\s+", "", part.strip(), flags=re.I).casefold()
        if part not in _INPUT_NAMES:
            return []
        names.append(_INPUT_NAMES[part])
    return list(dict.fromkeys(names))


def _list(names: list[str], original: str) -> str:
    conjunction = "or" if re.search(r"\bor\b", original, re.I) else "and"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return (" " + conjunction + " ").join(names)
    return ", ".join(names[:-1]) + ", " + conjunction + " " + names[-1]


def _topic_name(text: str) -> bool:
    # A product name may explain the help act but is deliberately not rendered.
    # Restrict it to a short name, not a clause or a claim about that product.
    words = re.sub(r"^(?:the|this)\s+", "", text, flags=re.I).split()
    return bool(words and len(words) <= 5 and all(
        re.fullmatch(r"[A-Z][A-Za-z-]*", word) is not None
        and word.casefold() not in {"has", "have", "is", "are", "will", "can", "comes", "offers", "includes"}
        for word in words))


def assistant_behavior(text: str) -> str:
    """Return canonical speech for one recognised assistant/input act, else ''."""
    if not isinstance(text, str) or len(text) > 500:
        return ""
    plain = " ".join(text.strip().replace("’", "'").split())
    if not plain or _QUANTITY.search(plain):
        return ""
    match = _NO_ASSUMPTION.fullmatch(plain)
    if match and (names := _inputs(match["inputs"])):
        return "I will not guess your " + _list(names, match["inputs"]) + "."
    match = _REQUEST_INPUTS.fullmatch(plain)
    if match and (names := _inputs(match["inputs"])):
        return "Please share your " + _list(names, match["inputs"]) + "."
    if _KEEP_FOCUS.fullmatch(plain):
        return "No, that will not change my answer."
    match = _HELP.fullmatch(plain)
    if match and (not match["topic"] or _topic_name(match["topic"])):
        return "I am here to help you with your questions."
    return ""
