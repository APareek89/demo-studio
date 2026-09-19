"""Narrow checks for explicit relations between separately reviewed assertions.

This does not infer product compatibility. It checks spoken equipment pairing
against literal positive fitment clauses, without using source-table quotations.
Ordinary citation, quantity, polarity and scope guards still run in the caller.
"""
from __future__ import annotations

from decimal import Decimal
import re

from .knowledge import scope_atoms, scope_value, scope_values, variant_projection

_PAIR = re.compile(r"\b(?:(?:is|are|can be)\s+)?(?:pairs?|paired|combines?|combined)\s+with\b", re.I)
_NEGATIVE = re.compile(r"\b(?:no|not|never|without|excludes?|absent|unavailable|unverified|unconfirmed)\b|\b(?:pending|awaiting)\s+confirmation\b", re.I)
_UNCERTAIN = re.compile(r"\b(?:unverified|unconfirmed)\b|\bnot\s+(?:yet\s+)?(?:confirmed|verified|established)\b|\b(?:pending|awaiting)\s+confirmation\b", re.I)
_UNIVERSAL = {"all", "all variants", "all trims"}
_STOP = set("a an the this that these those its it either and or with on in for of to as is are be has have offers offer comes standard available availability selected higher lower trims trim variants variant system systems feature features equipment includes include also depending range model vehicle car".split())
_ALIASES = {"touchscreen": "display", "screen": "display", "screens": "display", "displays": "display", "speakers": "speaker", "seats": "seat", "wheels": "wheel"}


def _eligible(fact: dict) -> bool:
    knowledge = fact.get("knowledge") or {}
    return (fact.get("approved", True) and not knowledge.get("excluded_by_precedence")
            and knowledge.get("conflict_status") not in {"suppressed", "unresolved"})


def _words(text: str) -> set[str]:
    return {_ALIASES.get(word, word) for word in re.findall(r"[a-z]+", text.casefold())
            if word not in _STOP and word not in {"inch", "inches", "cm", "mm"}}


def _quantities(text: str) -> set[tuple[Decimal, str]]:
    # Preserve adjacent units: an eight-speaker count cannot license an
    # eight-inch display. Quotes are the ordinary printed inch abbreviation.
    values = set()
    for match in re.finditer(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[-–]?\s*(\"|″|inches?\b|[a-z]+\b)?", text, re.I):
        unit = (match[2] or "").casefold()
        unit = "inch" if unit in {'"', '″', 'inch', 'inches'} else _ALIASES.get(unit, unit)
        values.add((Decimal(match[1]), unit))
    return values


def _matches(descriptor: str, assertion: str) -> bool:
    words = _words(descriptor)
    return bool(words) and words <= _words(assertion) and _quantities(descriptor) <= _quantities(assertion)


def _compatible(left: dict, right: dict, requested: dict) -> bool:
    # Missing identity is not evidence that two records describe the same car.
    a, b = left.get("scope") or {}, right.get("scope") or {}
    for key in ("model", "market"):
        if not a.get(key) or not b.get(key) or scope_value(a[key], key) != scope_value(b[key], key):
            return False
    for key in ("model", "market", "generation", "model_year", "powertrain", "transmission", "effective_from", "effective_to"):
        values = [scope_values(scope[key], key) for scope in (a, b, requested) if scope.get(key)]
        if values and not set.intersection(*values):
            return False
    return True


def _variants(fact: dict) -> list[str]:
    values = scope_atoms((fact.get("scope") or {}).get("variant", ""), "variant")
    # No inferred higher/lower trim order or fuzzy name aliases.
    return [v for v in values if scope_value(v, "variant") not in _UNIVERSAL
            and not re.search(r"\b(?:above|below|selected|higher|lower|other)\b", v, re.I)]


def _positive_at(fact: dict, variant: str, descriptor: str = "") -> bool:
    """Match only this variant's positive assertion, never another matrix cell."""
    if _UNCERTAIN.search(str(fact.get("conditions", ""))):
        return False
    projection = variant_projection(fact, {"variant": variant})
    claim = str(fact.get("claim", ""))
    if projection:
        rows = projection["rows"]
        if any(row["polarity"] == "negative" for row in rows):
            return False
        for row in rows:
            assertion = row["assertion"]
            if _NEGATIVE.search(assertion):
                continue
            # A condition 'Available on A' qualifies the value. It cannot
            # make a different value matrix cell applicable to A.
            if re.fullmatch(r"(?:Available|Standard|Applicable)(?:\s+equipment)?", row.get("label", ""), re.I):
                value = str(fact.get("value", ""))
                if ";" in value or re.search(r"\bon\b", value, re.I):
                    continue
                assertion = value + "; " + assertion
            if not descriptor or _matches(descriptor, claim + "; " + assertion):
                return True
        return False
    variants = scope_values((fact.get("scope") or {}).get("variant", ""), "variant")
    assertion = str(fact.get("value", "")) + "; " + str(fact.get("conditions", ""))
    if scope_value(variant, "variant") not in variants and not variants & _UNIVERSAL:
        return False
    if _NEGATIVE.search(assertion):
        return False
    return not descriptor or _matches(descriptor, claim + "; " + assertion)


def _parts(text: str, match: re.Match) -> tuple[str, list[str]]:
    left = re.split(r"[.;!?](?:\s|$)", text[:match.start()])[-1].strip()
    # Drop an introductory qualifier, not the subject of the relation.
    left = re.sub(r"^.*?,\s*(?=(?:it|this|that|the|an?|these|those)\b)", "", left, flags=re.I)
    left = re.sub(r"\s+(?:is|are|can be)$", "", left, flags=re.I).strip()
    right = re.split(r",?\s+\b(?:while|whereas|but)\b|[.;!?](?:\s|$)", text[match.end():], maxsplit=1, flags=re.I)[0]
    # Each alternative needs its own co-fitment proof. One supported size must
    # not license another size through a union of the cited assertion's numbers.
    objects = [re.sub(r"^\s*(?:either|both)\s+", "", v, flags=re.I).strip(" ,.")
               for v in re.split(r"\s+(?:or|and)\s+", right) if v.strip(" ,.")]
    return left, objects


def _direct_pair(left: str, right: str, facts: list[dict]) -> bool:
    for fact in facts:
        for assertion in re.split(r"[;\n]", str(fact.get("value", ""))):
            for match in _PAIR.finditer(assertion):
                a, objects = _parts(assertion, match)
                if not _NEGATIVE.search(assertion) and _matches(left, a) and any(_matches(right, b) for b in objects):
                    return True
    return False


def unsupported_equipment_pairing(text: str, cited_facts: list[dict],
                                  previous_claim: dict | None = None,
                                  requested_scope: dict | None = None) -> bool:
    """Whether an explicit affirmative equipment pairing lacks reviewed support.

    ``previous_claim`` is the caller's immediately preceding accepted factual
    row: ``{"text": ..., "facts": [trusted facts]}``. It must never contain a
    rejected model row. An unresolved pronoun or unknown fitment fails closed.
    A separate range/feature list without a pairing verb is unaffected.
    """
    facts = [f for f in cited_facts if _eligible(f)]
    requested = requested_scope or {}
    for match in _PAIR.finditer(text):
        left, objects = _parts(text, match)
        # This guard never treats negative fitment as evidence of a pairing.
        # Existing polarity checks own negative assertions themselves.
        if _NEGATIVE.search(left):
            continue
        pronoun = bool(re.fullmatch(r"(?:it|this|that|they|these|those)(?:\s+(?:system|feature|equipment))?", left, re.I))
        if pronoun:
            prior = previous_claim or {}
            subjects = [f for f in prior.get("facts", []) if _eligible(f)]
            if not prior.get("text") or not subjects or _NEGATIVE.search(str(prior["text"])):
                return True
        else:
            subjects = [f for f in facts if _matches(left, str(f.get("claim", "")) + "; " + str(f.get("value", "")))]
        if not objects or not subjects:
            return True
        for descriptor in objects:
            if not pronoun and _direct_pair(left, descriptor, facts):
                continue
            # Every plausible immediate antecedent must support the relation.
            # This refuses ambiguous pronouns instead of choosing a convenient
            # fact from a previously spoken multi-feature sentence.
            for subject in subjects:
                variants = _variants(subject)
                if requested.get("variant"):
                    wanted = scope_values(requested["variant"], "variant")
                    variants = [v for v in variants if scope_value(v, "variant") in wanted]
                if not variants or not any(
                    _positive_at(subject, variant)
                    and any(_compatible(subject, obj, requested) and _positive_at(obj, variant, descriptor) for obj in facts)
                    for variant in variants
                ):
                    return True
    return False
