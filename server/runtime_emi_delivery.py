"""Append audited EMI terms without rewriting already-validated customer speech.

This is a delivery helper, not a claim validator. It never fixes an incorrect
model amount or removes a condition; callers must validate those claims first.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re

from .runtime_tools import _bound_unit

_WORDS = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred thousand lakh lac crore million"
_WORD = r"(?:" + "|".join(_WORDS.split()) + r")"
_QUANTITY = r"(?:\d[\d,]*(?:\.\d+)?(?:\s*(?:lakh|lac|crore|thousand|million)s?)?|" + _WORD + r"(?:[ -]+" + _WORD + r")*)"
_MONEY = r"(?:(?:₹|INR|Rs\.?)\s*)?" + _QUANTITY + r"(?:\s*(?:rupees?|INR|Rs\.?))?"
_BASIS = r"(?:annual(?:ly)?|monthly|yearly|per\s+(?:year|annum|month))"
_RATE = re.compile(r"(?<!\w)(?:" + _QUANTITY + r"\s*(?:%|percent|per cent)\s*" + _BASIS +
                   r"(?:\s+interest(?:\s+rate)?)?|" + _BASIS + r"\s+(?:interest\s+)?rate\s*(?:of\s+)?" + _QUANTITY + r"\s*(?:%|percent|per cent))(?!\w)", re.I)
_PRINCIPAL = re.compile(r"(?<!\w)(?:\b(?:loan|principal)(?:\s+amount)?\s*(?:(?:of|is)\s+|:\s*)?" + _MONEY +
                        r"|" + _MONEY + r"\s+(?:loan|principal)\b|\b(?:payment|EMI)\s+(?:on|for)\s+(?:a\s+)?" + _MONEY + r")(?!\w)", re.I)
_ITEM = r"(?:(?:all|any|applicable|additional|processing|bank|administrative)\s+)*(?:fees?|tax(?:es)?|insurance(?:\s+premiums?)?)"
_ITEMS = _ITEM + r"(?:\s*(?:,\s*(?:(?:and|or)\s+)?|/|\band\b|\bor\b)\s*" + _ITEM + r")*"


def _plain(value) -> str:
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Non-finite audited EMI operand")
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _excluded(text: str) -> set[str]:
    """Only explicit exclusion lists; no borrowing from an inclusion clause."""
    excluded = set()
    for match in re.finditer(r"\b(?:excludes?|excluding|does not include|do not include|not including)\s+(" + _ITEMS + r")", text, re.I):
        if not _estimate_subject(text, match.start()):
            continue
        # 'does not exclude' must not be interpreted as 'exclude'. Nor can
        # 'excludes fees and taxes are included' prove the coordinated list.
        if re.search(r"\b(?:not|never)\s*$", text[max(0, match.start()-15):match.start()], re.I):
            continue
        if re.match(r"\s+(?:is|are|was|were)\b", text[match.end():], re.I):
            continue
        excluded.update("fees" if word.lower().startswith("fee") else "taxes" if word.lower().startswith("tax") else "insurance"
                        for word in re.findall(r"\b(?:fees?|tax(?:es)?|insurance)\b", match[1], re.I))
    for match in re.finditer(r"(?<!\w)(" + _ITEMS + r")\s+(?:are|is)\s+excluded\b", text, re.I):
        if not _estimate_subject(text, match.start()):
            continue
        excluded.update("fees" if word.lower().startswith("fee") else "taxes" if word.lower().startswith("tax") else "insurance"
                        for word in re.findall(r"\b(?:fees?|tax(?:es)?|insurance)\b", match[1], re.I))
    return excluded


def _estimate_subject(text: str, start: int) -> bool:
    prefix = re.split(r"[.;!?]|\b(?:but|while|whereas|and)\b", text[:start], flags=re.I)[-1].strip()
    return (not prefix or bool(re.search(r"\b(?:estimate|calculation|EMI|loan|payment)\b", prefix, re.I))
            or bool(re.fullmatch(r"(?:(?:that|which)\s+)?(?:this|it)(?:\s+is)?", prefix, re.I))
            or bool(re.fullmatch(r"(?:this|it)\s+is\s+an\s+illustrative\s+figure(?:\s+(?:that|which))?", prefix, re.I)))


def _not_lender_quote(text: str) -> bool:
    quote = r"(?:an?\s+)?(?:(?:formal|official|binding)\s+)?lender\s+quotes?\b"
    for match in re.finditer(r"\b(?:not\s+" + quote + r"|does not\s+(?:serve|count|qualify)(?:\s+as)?\s+" + quote +
                             r"|does not\s+constitute\s+" + quote + r"|rather than\s+" + quote + r")", text, re.I):
        prefix = re.split(r"[.;!?]|\b(?:but|while|whereas)\b", text[:match.start()], flags=re.I)[-1].strip()
        if (not prefix or re.search(r"\b(?:estimate|calculation|EMI|loan|payment)\b", prefix, re.I)
                or re.match(r"^(?:this|it)\s+(?:is|does|excludes?)\b", prefix, re.I)
                or re.search(r"\band (?:it|this) is\s*$", prefix, re.I)):
            return True
    return False


def _estimate(text: str) -> bool:
    for match in re.finditer(r"\b(?:illustrative|estimate|estimated)\b", text, re.I):
        before = re.split(r"[.;!?]", text[:match.start()])[-1]
        if not re.search(r"\b(?:not|never|isn't|is not)\s+(?:(?:an?|only|merely)\s+)*$", before, re.I):
            return True
    return False


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else " and ".join(items) if len(items) == 2 else ", ".join(items[:-1]) + ", and " + items[-1]


def append_missing_emi_terms(sentences: list[str], fact: dict) -> list[str]:
    """Return an unchanged copy plus only missing audited EMI qualifications.

    Assumptions use the existing numeric/unit binder. A local explicit rate
    phrase avoids mistaking an unrelated 'monthly payment' for its rate basis.
    Insurance is a required exclusion only when this audited fact excludes it.
    """
    output = list(sentences)
    derivation = fact.get("derivation", {})
    if fact.get("provenance") != "calculation" or fact.get("approved") is False or derivation.get("operation") != "emi":
        return output
    inputs = {item.get("name"): item for item in derivation.get("inputs", [])}
    rates = [key for key in ("annual_rate", "monthly_rate") if key in inputs]
    if len(rates) != 1 or not all(key in inputs for key in ("principal", "tenure")):
        return output
    rate_key = rates[0]
    principal, rate, tenure = (inputs[key] for key in ("principal", rate_key, "tenure"))
    if (str(principal.get("unit", "")).lower() != "inr" or str(rate.get("unit", "")).lower() != "percent"
            or str(tenure.get("unit", "")).lower() not in {"years", "months"}):
        return output
    try:
        p, r, n = (_plain(item["value"]) for item in (principal, rate, tenure))
    except (KeyError, ValueError, InvalidOperation):
        return output
    text = " ".join(output)
    annual = rate_key == "annual_rate"
    basis = "annual" if annual else "monthly"
    principal_present = any(_bound_unit(match.group(), Decimal(p), "inr") for match in _PRINCIPAL.finditer(text))
    rate_spans = [match.group() for match in _RATE.finditer(text)]
    rate_present = any(_bound_unit(span, Decimal(r), "percent", annual=annual, monthly=not annual) for span in rate_spans)
    # Two opposing labels for the same rate are not a confirmed assumption.
    if any(_bound_unit(span, Decimal(r), "percent", annual=not annual, monthly=annual) for span in rate_spans):
        rate_present = False
    tenure_present = _bound_unit(text, Decimal(n), str(tenure["unit"]).lower())
    pieces = []
    if not principal_present:
        pieces.append(f"a loan of {p} rupees")
    if not rate_present:
        pieces.append(("at " if pieces else "") + f"{r}% {basis} interest")
    if not tenure_present:
        pieces.append(("over " if pieces else "a term of ") + f"{n} {tenure['unit']}")
    if pieces:
        output.append("This estimate uses " + " ".join(pieces) + ".")
    required = {"fees", "taxes"} | ({"insurance"} & _excluded(str(fact.get("conditions", ""))))
    missing = [name for name in ("fees", "taxes", "insurance") if name in required - _excluded(text)]
    needs_quote = not _not_lender_quote(text)
    needs_estimate = not _estimate(text)
    if missing:
        output.append("This " + ("illustrative " if needs_estimate else "") + "estimate excludes " + _join(missing)
                      + (" and is not a lender quote." if needs_quote else "."))
    elif needs_quote:
        output.append("This " + ("illustrative estimate " if needs_estimate else "") + "is not a lender quote.")
    elif needs_estimate:
        output.append("This is an illustrative estimate.")
    return output
