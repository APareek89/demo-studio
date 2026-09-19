"""Conservative universal-fitment checks for cited live feature tables.

This reads the table already captured by lookup. It does not ingest sources,
create product assertions, infer trim order, or expand a partial row's scope.
"""
from __future__ import annotations

import re


_UNIVERSAL = re.compile(
    r"\b(?:all|every|each)\s+(?:(?:the|current)\s+)?(?:trims?|variants?|versions?|models?)\b"
    r"|\b(?:across|throughout)\s+(?:(?:the|its|this|entire|whole|complete|full)\s+)*"
    r"(?:line[- ]?up|range)\b", re.I)
_NEGATIVE = re.compile(r"\b(?:not|never|without|lacks?|absent|unavailable)\b|\b(?:doesn't|don't|isn't|aren't)\b", re.I)
_STATUS = re.compile(
    r"(?:[A-Z]{1,2}[*†‡]*|[-–—?✓✔●]|yes|no|standard|included|available|optional|"
    r"not available|unknown|pending|tbd|n/?a)[.]?", re.I)
_S_LEGEND = re.compile(r"(?:^|[;\n])\s*S\s*[:=–-]\s*standard[.]?\s*(?=$|[;\n])", re.I)
_LEGEND_ITEM = re.compile(r"(?:S\s*[:=–-]\s*standard|O\s*[:=–-]\s*optional|[-–—]\s*[:=]\s*not available)[.]?", re.I)
_STOP = set((
    "a an the this that it its these those and or with on in for of to as is are be "
    "has have gets get comes come standard available availability included includes include "
    "offers offer provides provide equipped fitted also both all every each across throughout "
    "trim trims variant variants version versions model models lineup range entire whole full "
    "current comfort convenience amenities equipment feature features listed highlights lists"
).split())
_ALIASES = {
    "centre": "center", "charger": "charge", "chargers": "charge", "charging": "charge",
    "vents": "vent", "armrests": "armrest", "holders": "holder", "seats": "seat",
    "windows": "window", "wheels": "wheel", "screens": "display", "screen": "display",
    "touchscreen": "display", "displays": "display", "ventilated": "ventilation",
}
_REPORTING_LEAD = re.compile(
    r"^(?:it|(?:the|this|that)\s+(?:page|website|table|brochure|car|vehicle|model)|"
    r"(?:the\s+)?(?-i:[A-Z][A-Za-z0-9-]*(?:\s+[A-Z][A-Za-z0-9-]*){0,3})"
    r"(?:\s+(?:features?|specification)\s+page)?)\s+(?:also\s+)?"
    r"(?:highlights?|lists?|shows?|notes?|offers?|includes?|provides?|has|have|gets?|"
    r"comes?\s+with|(?:is|are)\s+equipped\s+with)\s+", re.I)


def _words(text: str) -> set[str]:
    # Literal feature descriptors retain front/rear, numbers and other modifiers.
    # Broad feature keys alone would let one wireless-charger row fund another.
    text = re.sub(r"\bair[- ]conditioning\b", "ac", text, flags=re.I)
    text = re.sub(r"\bfront row\b", "front", text, flags=re.I)
    text = re.sub(r"\bsmartphone\b(?=\s+wireless)|(?<=wireless )\bsmartphone\b", "", text, flags=re.I)
    return {_ALIASES.get(word, word) for word in re.findall(r"\d+(?:\.\d+)?|[a-z]+", text.casefold())
            if word not in _STOP}


def _descriptors(clause: str) -> list[set[str]]:
    text = re.sub(r"^\s*according to\s+[^,;]+,\s*", "", clause, flags=re.I)
    text = _UNIVERSAL.sub(" ", text).strip(" ,.")
    # Discard a reporting/vehicle subject, never a feature qualifier at the end
    # of a coordinated list. Unknown words in the remaining list must be proved.
    text = _REPORTING_LEAD.sub("", text, count=1)
    # Each coordinated feature needs one own-row proof. Pooling words across
    # items would swap front/rear modifiers between a charger and an air vent.
    return [_words(item) for item in re.split(r"\s*,\s*(?:and\s+)?|\s+and\s+", text)
            if item.strip()]


def _table_rows(fact: dict) -> list[tuple[set[str], bool]] | None:
    context = fact.get("context") or {}
    rows = context.get("rows")
    if not isinstance(rows, list) or len(rows) < 2 or not isinstance(rows[0], list):
        return None
    header = rows[0]
    if len(header) < 3 or not all(isinstance(cell, str) for cell in header):
        return None
    if not re.fullmatch(r"features?|equipment|items?", header[0].strip(), re.I):
        return None
    names = [" ".join(cell.casefold().split()) for cell in header[1:]]
    if (len(set(names)) != len(names) or any(not name or re.search(r"[?*†‡]|\.{2,}", name)
                                         or not re.search(r"[a-z0-9]", name) for name in names)):
        return None
    count = len(names)
    footnote = str(context.get("footnote", "")).strip()
    standard_s = bool(_S_LEGEND.search(footnote))
    unqualified = all(_LEGEND_ITEM.fullmatch(part.strip())
                      for part in re.split(r"[;\n]", footnote) if part.strip())
    result = []
    for row in rows[1:]:
        if not isinstance(row, list) or len(row) not in {count + 1, count + 2}:
            return None
        if not all(isinstance(cell, str) for cell in row):
            return None
        labels, cells = row[:-count], row[-count:]
        # A second label cell is allowed, but an extra leading status is not a
        # label. This prevents shifting a negative column off the matrix.
        if any(not label.strip() or _STATUS.fullmatch(label.strip()) for label in labels):
            return None
        label = " ".join(labels)
        words = _words(label)
        if not words:
            return None
        positive = unqualified and not re.search(r"[*†‡]", label) and all(
            cell.strip().casefold() in {"standard", "included", "yes"}
            or (standard_s and cell.strip().casefold() == "s") for cell in cells)
        result.append((words, bool(positive)))
    return result


def unsupported_live_table_universal(text: str, cited_facts: list[dict]) -> bool:
    """Reject a universal list unless each named feature has full-column proof.

    Only live tables activate this guard. Ordinary inventory/selected-trim
    descriptions and non-table assertions retain their existing validation.
    A table's positive marks need explicit semantics; bare ``S`` without a
    captured legend, conditional marks, unknown cells and malformed rows cannot
    grant universal fitment. No source text is added to the spoken response.
    """
    tables = [fact for fact in cited_facts if fact.get("provenance") == "live_web"
              and (fact.get("context") or {}).get("kind") == "table"]
    if not tables:
        return False
    for clause in re.split(r"[;.!?](?:\s|$)|,?\s+\b(?:but|while|whereas)\b\s*", text):
        quantified = list(_UNIVERSAL.finditer(clause))
        if not quantified:
            continue
        negated = [bool(re.search(r"\bnot\s+$", clause[:match.start()], re.I)) for match in quantified]
        if any(negated):
            # One standalone 'not all' is not a positive universal. It cannot
            # exempt another coordinated statement about all trims/the range.
            tail = clause[quantified[0].end():]
            if len(quantified) == 1 and negated[0] and not re.search(r",|\b(?:and|or)\b", tail, re.I):
                continue
            return True
        if _NEGATIVE.search(clause):
            return True  # positive cells cannot authorize a universal negative
        descriptors = _descriptors(clause)
        if not descriptors or any(not item for item in descriptors):
            return True
        rows = []
        headers = None
        for fact in tables:
            parsed = _table_rows(fact)
            if parsed is None:
                return True
            named = frozenset(" ".join(cell.casefold().split())
                              for cell in fact["context"]["rows"][0][1:])
            if headers is not None and named != headers:
                return True  # do not merge different trim universes
            headers = named
            rows.extend(parsed)
        for descriptor in descriptors:
            matching = [positive for label, positive in rows if label == descriptor]
            if not matching or not all(matching):
                return True
    return False
