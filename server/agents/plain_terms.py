"""Reviewed neutral renderings for everyday speech; evidence validation runs first."""
from __future__ import annotations

import re

COMMON_TERMS = {"cc", "hp", "bhp", "ps", "turbo", "turbo petrol", "diesel", "petrol", "hybrid", "automatic", "manual",
    "dual clutch", "dual-clutch", "airbag", "airbags", "abs", "sunroof", "panoramic sunroof", "touchscreen", "cruise control",
    "parking sensors", "reverse camera", "alloy wheels", "alloys", "km/l", "kmpl", "litre", "litres", "seater", "boot",
    "ground clearance", "suspension", "wheelbase", "torque", "gearbox", "ev", "battery", "range", "fast charging"}

# Neutral plain renderings. No benefit words. Reviewed by a human before release.
JARGON = {
    "mcpherson strut": "strut-type front suspension",
    "macpherson strut": "strut-type front suspension",
    "coupled torsion beam axle": "a simple rear suspension setup",
    "coupled torsion beam": "a simple rear suspension setup",
    "torsion beam": "a simple rear suspension setup",
    "multi-link": "independent rear suspension",
    "coil spring": "coil springs",
    "gdi": "direct-injection petrol engine",
    "mpi": "petrol engine",
    "crdi": "diesel engine",
    "ivt": "automatic gearbox",
    "dct": "dual-clutch automatic",
    "7-speed dct": "seven-speed dual-clutch automatic",
    "adas": "driver-assistance features",
    "level 2 adas": "advanced driver-assistance features",
    "smartsense": "Hyundai's driver-assistance package",
    "esc": "electronic stability control",
    "vsm": "stability management",
    "hac": "hill-start assist",
    "tpms": "tyre-pressure warning",
    "epb": "electronic parking brake",
    "isofix": "child-seat mounts",
    "nvh": "noise and vibration",
    "kerb weight": "weight",
    "parametric grille": "front grille",
    "quad-beam": "four-lamp",
}
TECHNICAL_REQUEST = re.compile(r"\b(technical|spec|specification|exact type|which type|what type of|engineering|details? of the (engine|suspension|gearbox))\b", re.I)


def _phrase(term: str) -> str:
    # Word boundaries also keep short codes out of unrelated words.
    return r"(?<!\w)" + re.escape(term) + r"(?!\w)"


def find_jargon(text: str) -> list[str]:
    """Return matched blocklist keys, longest first, without matching word fragments."""
    return [term for term in sorted(JARGON, key=len, reverse=True)
            if re.search(_phrase(term), text or "", re.I)]


def substitute(text: str) -> tuple[str, list]:
    """Replace original longest phrases in one pass; never reprocess replacements."""
    terms = sorted((term for term, replacement in JARGON.items() if replacement), key=len, reverse=True)
    if not terms:
        return text, []
    pattern = re.compile("|".join(_phrase(term) for term in terms), re.I)
    substitutions, chunks, cursor = [], [], 0
    for match in pattern.finditer(text):
        if match.start() < cursor:
            continue
        term = match.group(0).lower()
        replacement = JARGON[term]
        substitutions.append((term, replacement))
        prefix = text[cursor:match.start()]
        # A reviewed phrase may already contain the article or category noun
        # beside the original term. Remove only that boundary duplication.
        if replacement.startswith("a "):
            article = re.search(r"\b(a|an)\s+$", prefix, re.I)
            if article:
                prefix = prefix[:article.start()]
                if article.group(1)[:1].isupper():
                    replacement = replacement[:1].upper() + replacement[1:]
        cursor = match.end()
        if replacement.endswith("suspension"):
            repeated = re.match(r"\s+" + (r"(?:front\s+)?" if replacement.endswith("front suspension") else r"(?:rear\s+)?") + r"suspension\b", text[cursor:], re.I)
            if repeated:
                cursor += repeated.end()
        chunks.extend((prefix, replacement))
    chunks.append(text[cursor:])
    return "".join(chunks), substitutions


def allowed(term: str) -> bool:
    return (term or "").strip().lower() in COMMON_TERMS
