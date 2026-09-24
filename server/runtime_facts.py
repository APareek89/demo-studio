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


_ENGINE = re.compile(r"\b(?:(?:non[- ]turbo|naturally[- ]aspirated|regular|turbo(?:charged)?(?:\s+GDi)?|hybrid)\s+)?(?:petrol|gasoline|diesel)\b", re.I)
_GEARBOX = re.compile(r"\b(?:manual|automatic|dual[- ]clutch(?:\s+automatic)?|IVT|CVT|DCT|(?-i:AT|MT))\b", re.I)
_ENGINE_LINK = re.compile(r"\b(?:for|with|on|has|have|offers?|gets?|uses?|paired|pair|comes?|available)\b|:", re.I)
_COLLECTIVE_PAIR = re.compile(r"\b(?:pair\s+(?:them|these|those)|(?:they|both|each|all|these|those)\b.{0,65}\b(?:with|have|has|offer|offers|get|gets|come|comes|available)|(?:all|both|each)\s+(?:of\s+)?(?:the\s+)?(?:engine|powertrain)s?)\b", re.I)


def _engines(text: str) -> set[str]:
    engines = set()
    for match in _ENGINE.finditer(text):
        value = match[0].casefold().replace("gasoline", "petrol")
        base = "diesel" if value.endswith("diesel") else "petrol"
        prefix = "hybrid " if value.startswith("hybrid") else "turbo " if value.startswith("turbo") else ""
        engines.add(prefix + base)
    return engines


def _gearboxes(text: str) -> set[str]:
    # Everyday "automatic" is a valid generalisation of these named families;
    # a manual or a different named family is not interchangeable with them.
    names = set()
    for match in _GEARBOX.finditer(text):
        value = match[0].casefold()
        if value in {"manual", "automatic"}:
            following = re.match(r"\s+([a-z]+)\b", text[match.end():], re.I)
            if following and following[1].casefold() not in {
                "or", "and", "for", "with", "on", "gearbox", "gearboxes", "transmission", "transmissions",
                "version", "versions", "variant", "variants", "option", "options", "choice", "choices",
                "is", "are", "was", "can", "only", "depending", "available", "offered",
            }:
                continue  # Adjectives in "automatic climate control"/"manual seats" are not gearboxes.
        name = "manual" if value in {"manual", "mt"} else "dct" if value.startswith("dual") else value
        names.add(name)
        if name in {"ivt", "cvt", "dct", "at"}:
            names.add("automatic")
    return names


def _engine_clauses(text: str):
    # Preserve decimal engine sizes. A repeated named subject or a separately
    # qualified gearbox option starts its own clause, not a shared option list.
    boundary = r"[,;!?]|\.(?=\s|$)|\b(?:while|whereas|but)\b|\band\b(?=\s+(?:the\s+)?(?:turbo\s+)?(?:petrol|diesel)\s+(?:has|offers?|gets?|comes?))|\band\b(?=\s+(?:a\s+|an\s+)?(?:\d+[- ]speed\s+)?(?:dual[- ]clutch|IVT|CVT|DCT|manual|automatic)\b[^,;.!?]*\b(?:for|with)\b)"
    start = 0
    for match in re.finditer(boundary, text, re.I):
        yield start, text[start:match.start()]
        start = match.end()
    yield start, text[start:]


def unsupported_powertrain_pairing(text: str, cited_facts: list[dict], previous_claim: dict | None = None) -> bool:
    """Check explicit collective engine/gearbox choices against literal mappings.

    This bounded relation check does not infer compatibility from two independent
    availability lists. It addresses the loss of engine boundaries in "pair them
    with a manual or automatic". The preceding accepted row supplies antecedent
    names only; this row's eligible citations must supply each actual mapping.
    """
    supported: dict[str, set[str]] = {}
    for fact in cited_facts:
        if not _eligible(fact):
            continue
        claim = str(fact.get("claim", ""))
        claim_engines = _engines(claim) if re.search(r"\b(?:transmissions?|gearboxes?)\b", claim, re.I) and not _NEGATIVE.search(claim) else set()
        for _, clause in _engine_clauses(str(fact.get("value", ""))):
            engines, gearboxes = _engines(clause), _gearboxes(clause)
            # A granular reviewed assertion can name its engine in the claim
            # ("petrol transmission options") and list gearboxes in the value.
            own_identity = not engines and len(claim_engines) == 1
            if own_identity:
                engines = claim_engines
            if engines and gearboxes and (own_identity or _ENGINE_LINK.search(clause)) and not _NEGATIVE.search(clause):
                for engine in engines:
                    supported.setdefault(engine, set()).update(gearboxes)
    for start, clause in _engine_clauses(text):
        gearboxes = _gearboxes(clause)
        if not gearboxes or _NEGATIVE.search(clause) or not _ENGINE_LINK.search(clause):
            continue
        engines = _engines(clause)
        prefix = re.split(r"[;!?]|\.(?=\s|$)", text[:start])[-1]
        if engines and _engines(prefix) and not _gearboxes(prefix) and not _NEGATIVE.search(prefix):
            # Oxford-comma engine enumeration still owns one shared predicate.
            engines |= _engines(prefix)
        if _COLLECTIVE_PAIR.search(clause) and not engines:
            if re.search(r"\ball\s+(?:(?:the|three|3)\s+)?(?:engine|powertrain)s?\b", clause, re.I):
                engines = set(supported)
            else:
                engines = _engines(text[:start]) or _engines(str((previous_claim or {}).get("text", "")))
        # Single-engine assertions remain under existing scope/quantity guards.
        # Bare separate inventories have no explicit engine→gearbox relation.
        if len(engines) > 1 and any(not gearboxes <= supported.get(engine, set()) for engine in engines):
            return True
    return False


def transmission_condition_dependencies(text: str, cited: list[dict], registry: list[dict],
                                        requested: dict | None = None) -> list[dict]:
    """Carry explicit same-feature gearbox requirements, not additional offerings.

    The caller supplies the pinned registry, or condition records derived from
    it before retrieval truncation. A broad duplicate cannot erase the narrow
    assertion's literal requirement. Source quotes and table order are not used.
    """
    requested = requested or {}
    stop = {"a", "an", "the", "with", "and", "of", "availability", "feature", "features", "system"}

    def words(value):
        return [w for w in re.findall(r"[a-z0-9]+", str(value).casefold()) if w not in stop]

    def contains(value, feature):
        tokens = words(value)
        return any(tokens[i:i + len(feature)] == feature for i in range(len(tokens) - len(feature) + 1))

    def eligible(fact):
        return _eligible(fact) and fact.get("provenance") not in {"calculation", "live_web"}

    def compatible(donor, base):
        a, b = donor.get("scope") or {}, base.get("scope") or {}
        model = scope_value(a.get("model", ""), "model")
        if not model or scope_value(b.get("model", ""), "model") != model:
            return False
        # Transmission is the requirement being checked, not a reason to hide
        # it from a customer asking about a manual version of the same feature.
        for key in ("model", "market", "variant", "model_year", "generation", "powertrain", "effective_from", "effective_to"):
            values = [scope_values(scope[key], key) for scope in (a, b, requested) if scope.get(key)]
            if key == "variant":
                values = [v for v in values if not v & _UNIVERSAL]
            if values and not set.intersection(*values):
                return False
            if key in {"model_year", "generation", "effective_from", "effective_to"} and a.get(key) and not (b.get(key) or requested.get(key)):
                return False
        return True

    dependencies = []
    for donor in registry:
        if not eligible(donor):
            continue
        condition = str(donor.get("conditions", ""))
        if not re.fullmatch(r"(?:IVT|AT|DCT|CVT|MT)(?:\s*[,/]\s*(?:IVT|AT|DCT|CVT|MT))*\s+transmissions?\s+only[.]?", condition, re.I):
            continue
        feature = words(donor.get("claim", ""))
        if len(set(feature)) < 2 or _NEGATIVE.search(str(donor.get("value", ""))) or not contains(text, feature):
            continue
        for base in cited:
            if not eligible(base) or not compatible(donor, base):
                continue
            # The duplicate must actually assert this feature. A locator or an
            # unrelated word elsewhere in a suite cannot supply its identity.
            assertions = re.split(r"[;!?]|\.(?:\s|$)", str(base.get("value", "")))
            if any(contains(clause, feature) and not _NEGATIVE.search(clause) for clause in assertions):
                dependencies.append(donor)
                break
    return list({fact["id"]: fact for fact in dependencies}.values())


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


# Relative trim labels are opaque reviewed assertions, never sortable names.
# These patterns only identify a spoken threshold; they do not expand one.
_ORDINAL_STOP = r"the|a|an|our|your|my|their|this|that|and|or|above|below|upwards|onwards|upward|onward|up|downwards|downward|down|trim|trims|variant|variants|is|are|has|have|gets|get|comes|come|use|uses|receive|receives|carry|carries|with|without|for|on|in|from|to|while|whereas|but|excluding|except|only|standard|available|offered|includes|include|features|feature"
_ORDINAL_ATOM = rf"(?!(?:{_ORDINAL_STOP})\b)[A-Za-z][A-Za-z0-9]*(?:\([A-Za-z0-9]+\))?"
_ORDINAL_NAME = rf"{_ORDINAL_ATOM}(?:[ -]{_ORDINAL_ATOM}){{0,3}}"
_ORDINAL = re.compile(
    rf"\b(?:(?:starting|beginning)\s+)?(?P<prefix>from|up\s+to)\s+(?:the\s+)?"
    rf"(?P<first>{_ORDINAL_NAME})(?:\s+(?:trim|variant)s?)?"
    rf"(?:(?:\s*,)?\s+(?P<tail>upwards?|onwards?|and\s+(?:above|up|higher)|and\s+(?:below|down|lower)))?"
    rf"|(?<![\w(])(?P<last>{_ORDINAL_NAME})(?:\s+(?:trim|variant)s?)?(?:\s*,)?\s+"
    rf"(?P<suffix>and\s+(?:above|up|higher|below|down|lower)|upwards?|onwards?|downwards?)\b",
    re.I,
)
_FITMENT = re.compile(r"\b(?:available|standard|offered|fitted|equipped|get|gets|include|includes|feature|features)\b", re.I)
_ORDINAL_WORD_STOP = set((
    "standard available offered fitted equipped gets get comes come includes included provides provide use uses receive receives carry carries model models "
    "starting beginning upwards upwards onward onwards above below up down higher lower "
    "trim trims variant variants the a an from at for on in to of is are with and or "
    "only also all across as by there it this that will can be depending feature features yes smart over "
    "option options fitment equipment availability not no never without unavailable absent excludes exclude"
).split())
_NUMBER_WORDS = r"zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand"


def _ordinal_number_text(text: str) -> str:
    # Reuse the runtime's explicit number parser, not trim order arithmetic.
    from .agents.pitch import _numbers
    def replace(match):
        values = _numbers(match[0])
        return next(iter(values)) if len(values) == 1 else match[0]
    text = re.sub(rf"\b(?:{_NUMBER_WORDS})(?:[ -]+(?:{_NUMBER_WORDS}))*\b", replace, text, flags=re.I)
    return re.sub(r"(?<=\d)\+(?=\s)", "", text)


def _ordinal_clauses(text: str, facts: list[dict] | None = None) -> list[str]:
    # Do not split decimals or a comma-separated trim enumeration. Independent
    # clauses are separate proof units; ambiguous unsplit multi-threshold prose
    # is refused below rather than borrowing a convenient neighbouring feature.
    clauses = [v.strip() for v in re.split(
        r"[;\n]|[.!?](?:\s|$)|,?\s+\b(?:while|whereas|but)\b|,\s+and\s+(?!(?:above|up|higher|below|down|lower)\b)", text, flags=re.I
    ) if v.strip()]
    result = []
    for clause in clauses:
        records = _ordinal_records(clause, facts)
        if len(records) > 1:
            start, end = records[0]["span"][1], records[1]["span"][0]
            join = re.search(r"\band\b", clause[start:end], re.I)
            if join:
                boundary = start + join.start()
                result.extend(_ordinal_clauses(clause[:boundary], facts))
                result.extend(_ordinal_clauses(clause[boundary + len(join[0]):], facts))
                continue
        result.append(clause)
    return result


def _ordinal_terms(text: str) -> set[str]:
    text = re.sub(r"\balong\s+with\b", "with", text, flags=re.I)
    return {_ALIASES.get(word, word) for word in re.findall(r"[a-z]+", _ordinal_number_text(text).casefold())
            if word not in _ORDINAL_WORD_STOP}


_COUNT_MODIFIER = r"(?!(?:years?|months?|days?|hours?|km|mm|cm|inches?|kw|kwh|ps|nm|cc|kg|litres?|liters?|speakers?|airbags?|seats?|features?|functions?)\b)[a-z]+\s+"


def _multiple_feature_counts(text: str) -> bool:
    counts: dict[str, set[Decimal]] = {}
    for match in re.finditer(rf"(\d+(?:\.\d+)?)\s+(?:{_COUNT_MODIFIER}){{0,2}}(features?|functions?)\b",
                             _ordinal_number_text(text), re.I):
        counts.setdefault(match[2].casefold().rstrip("s"), set()).add(Decimal(match[1]))
    return any(len(values) > 1 for values in counts.values())


def _ordinal_quantities(text: str, *, preserve_modifiers: bool = False) -> set[tuple[Decimal, str]]:
    # In '70 connected features', features is the counted noun, not connected.
    # Modifiers remain in _ordinal_terms: another feature cannot borrow this
    # count merely by placing an arbitrary adjective between number and noun.
    text = _ordinal_number_text(text)
    if preserve_modifiers:
        bound = set()
        def bind(match):
            label = " ".join((match[2] + match[3].rstrip("s")).casefold().split())
            bound.add((Decimal(match[1]), label))
            return " "
        text = re.sub(rf"(\d+(?:\.\d+)?)\s+((?:{_COUNT_MODIFIER}){{0,2}})(features?|functions?)\b", bind, text, flags=re.I)
        return _quantities(text) | bound
    else:
        text = re.sub(rf"(\d+(?:\.\d+)?)\s+(?:{_COUNT_MODIFIER}){{1,2}}(features?|functions?)\b",
                      r"\1 \2", text, flags=re.I)
    return _quantities(text)


def _ordinal_records(clause: str, facts: list[dict] | None = None) -> list[dict]:
    records = []
    for match in _ORDINAL.finditer(clause):
        name = match["first"] or match["last"]
        prefix, tail = match["prefix"] or "", match["tail"] or match["suffix"] or ""
        # A spelled-out quantity cap ('up to seven years') is not a trim range.
        if prefix.casefold().startswith("up") and re.match(
            r"^\d+(?:\.\d+)?\s+(?:years?|months?|days?|hours?|litres?|liters?|km|mm|cm|inches?|airbags?|seats?|speakers?|features?)\b",
            _ordinal_number_text(name), re.I
        ):
            continue
        # A bare 'from' is a trim threshold only in a fitment assertion; ordinary
        # provenance such as 'information from the brochure' is not one.
        if prefix.casefold() == "from" and not tail and not _FITMENT.search(clause[:match.start()]):
            # Initial 'From Nimbus, ...' is a threshold when Nimbus is an
            # explicitly named trim. This only identifies the grammar; a list
            # still cannot license that newly inferred open-ended fitment.
            named = any(scope_value(name, "variant") in scope_values((f.get("scope") or {}).get("variant", ""), "variant")
                        or variant_projection(f, {"variant": name}) for f in (facts or []))
            if not named or not _FITMENT.search(clause[match.end():]):
                continue
        direction = "down" if re.search(r"below|down|lower", tail, re.I) or prefix.casefold().startswith("up") else "up"
        if prefix.casefold() == "from" and direction == "down":
            direction = "contradictory"
        remainder = (clause[:match.start()] + " " + clause[match.end():]).strip(" ,:")
        # An explicit exclusion is additional scope, not another feature. The
        # ordinary scope/polarity guards still validate that exclusion itself.
        pieces = re.split(r",?\s+\b(?:excluding|except)\b", remainder, maxsplit=1, flags=re.I)
        remainder = pieces[0]
        exceptions = re.sub(r"\b(?:the|and|trims?|variants?)\b", "", pieces[1], flags=re.I) if len(pieces) > 1 else ""
        records.append({"name": scope_value(name, "variant"), "direction": direction,
                        "descriptor": remainder, "negative": bool(_NEGATIVE.search(remainder)),
                        "exceptions": scope_value(exceptions, "variant"), "span": match.span()})
    return records


def unsupported_ordinal_fitment(text: str, cited_facts: list[dict],
                               requested_scope: dict | None = None) -> bool:
    """Reject fitment thresholds not literally approved for that same feature.

    Exact named lists, relative trim order, source quotes and table provenance
    cannot establish a range. Only the eligible assertion's own value/conditions
    or literal relative variant scope can license the same named boundary,
    direction and feature. The caller must
    still run normal citation, quantity, polarity and applicability validation.
    """
    requested = requested_scope or {}
    proofs = []
    model_words = set().union(*(_ordinal_terms(str((fact.get("scope") or {}).get("model", "")))
                                for fact in cited_facts)) if cited_facts else set()
    for fact in cited_facts:
        if not _eligible(fact):
            continue
        if _UNCERTAIN.search(str(fact.get("value", "")) + "; " + str(fact.get("conditions", ""))):
            continue
        scope = fact.get("scope") or {}
        if any(scope.get(key) and requested.get(key)
               and not (scope_values(scope[key], key) & scope_values(requested[key], key))
               for key in ("model", "market", "model_year", "generation", "powertrain", "transmission")):
            continue
        assertions = [str(fact.get(field, "")) for field in ("value", "conditions")]
        if scope.get("variant") and not _UNCERTAIN.search(str(fact.get("conditions", ""))):
            assertions += scope_atoms(scope["variant"], "variant")
        for assertion in assertions:
            for clause in _ordinal_clauses(assertion, [fact]):
                records = _ordinal_records(clause, [fact])
                if len(records) != 1 or _UNCERTAIN.search(clause):
                    continue
                record = records[0]
                descriptor = record["descriptor"]
                if not _ordinal_terms(descriptor):
                    # 'Available on Aurora and above' qualifies this assertion's
                    # own feature. It does not qualify another cited assertion.
                    descriptor = "; ".join(str(fact.get(key, "")) for key in ("claim", "value", "conditions"))
                    record = {**record, "negative": bool(_NEGATIVE.search(str(fact.get("value", ""))))}
                # Two different counts for the same head cannot exchange
                # their modifiers (70 connected versus 3 safety features).
                bind_modifiers = _multiple_feature_counts(descriptor)
                proofs.append({**record, "terms": _ordinal_terms(descriptor) - model_words,
                               "bind_modifiers": bind_modifiers,
                               "quantities": _ordinal_quantities(descriptor, preserve_modifiers=bind_modifiers)})
    for clause in _ordinal_clauses(text, cited_facts):
        records = _ordinal_records(clause, cited_facts)
        if not records:
            continue
        if len(records) != 1:
            return True
        record = records[0]
        terms = _ordinal_terms(record["descriptor"]) - model_words
        if not terms or not any(
            record["name"] == proof["name"] and record["direction"] == proof["direction"]
            and record["direction"] != "contradictory" and record["negative"] == proof["negative"]
            and record["exceptions"] == proof["exceptions"]
            and terms <= proof["terms"]
            and _ordinal_quantities(record["descriptor"], preserve_modifiers=proof["bind_modifiers"]) <= proof["quantities"]
            for proof in proofs
        ):
            return True
    return False
