"""Reviewed category story orders. This library supplies topics, never product claims."""
from __future__ import annotations

import re

VERSION = "2026-09-23"


def _stop(id: str, label: str, kind: str, *covers: str) -> dict:
    return {"id": id, "label": label, "kind": kind, "covers": list(covers)}


LIBRARY: dict[str, dict] = {
    "compact suv": {
        "aliases": ["compact suv", "mid-size suv", "midsize suv", "suv", "crossover"],
        "order": [
            _stop("powertrain", "Powertrain", "fundamental", "engine", "turbo", "gearbox", "transmission"),
            _stop("stance-and-ride", "Stance and ride", "fundamental", "ground clearance", "suspension", "wheel", "tyre", "tire"),
            _stop("space-and-practicality", "Space and practicality", "fundamental", "seating", "rear seat", "boot", "seat capacity"),
            _stop("safety", "Safety", "fundamental", "airbag", "structure", "driver assistance", "safety"),
            _stop("cabin-and-tech", "Cabin and tech", "differentiator", "screen", "climate", "connected", "touchscreen"),
            _stop("delighters", "Delighters", "delighter", "sunroof", "ventilated seat", "audio", "ambient"),
            _stop("ownership", "Ownership", "ownership", "price", "warranty", "efficiency", "service"),
        ],
    },
    "premium suv": {
        "aliases": ["luxury suv", "premium"],
        "order": [
            _stop("powertrain-and-drive", "Powertrain and drive", "fundamental", "engine", "turbo", "gearbox", "transmission", "drive"),
            _stop("ride-and-refinement", "Ride and refinement", "fundamental", "suspension", "ride", "noise", "wheel", "tyre", "refinement"),
            _stop("safety", "Safety", "fundamental", "airbag", "structure", "driver assistance", "safety"),
            _stop("cabin", "Cabin", "differentiator", "seat", "cabin", "climate", "trim"),
            _stop("tech", "Tech", "delighter", "screen", "connected", "audio", "ambient", "sunroof"),
            _stop("ownership", "Ownership", "ownership", "price", "warranty", "efficiency", "service"),
        ],
    },
    "electric scooter": {
        "aliases": ["ev scooter", "e-scooter", "electric two-wheeler", "scooter"],
        "order": [
            _stop("range", "Range", "fundamental", "range", "distance"),
            _stop("charging", "Charging", "fundamental", "charg", "plug", "socket"),
            _stop("running-cost", "Running cost", "fundamental", "running cost", "electricity", "cost per", "efficiency"),
            _stop("battery-life-and-warranty", "Battery life and warranty", "fundamental", "battery", "warranty", "cycle"),
            _stop("ride-and-practicality", "Ride and practicality", "fundamental", "ride", "seat", "storage", "suspension", "wheel", "brake"),
            _stop("features", "Features", "delighter", "screen", "connected", "feature", "app", "display"),
            _stop("ownership", "Ownership", "ownership", "price", "service", "insurance", "registration"),
        ],
    },
    "_generic": {
        "aliases": [],
        "order": [
            _stop("fundamentals", "Fundamentals", "fundamental", "product", "purpose", "function", "type", "category"),
            _stop("main-job", "Proof of the main job", "fundamental", "performance", "capacity", "output", "power", "speed", "result"),
            _stop("practicality", "Practicality", "fundamental", "size", "space", "weight", "dimension", "storage", "use"),
            _stop("safety-or-reliability", "Safety or reliability", "fundamental", "safe", "safety", "reliable", "reliability", "certif", "durable"),
            _stop("differentiators", "Differentiators", "differentiator", "feature", "choice", "option"),
            _stop("delighters", "Delighters", "delighter", "extra", "comfort", "personal", "design"),
            _stop("ownership", "Ownership", "ownership", "price", "warranty", "service", "cost", "support"),
        ],
    },
}


def _normalise(category: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (category or "").lower()).split())


def match(category: str) -> tuple[str, dict]:
    """Prefer the most specific key/alias so 'premium SUV' cannot match plain 'SUV'."""
    normal = _normalise(category)
    candidates = [(len(alias), key) for key, entry in LIBRARY.items() if key != "_generic"
                  for text in [key, *entry["aliases"]]
                  if (alias := _normalise(text)) and alias in normal]
    key = max(candidates, default=(0, "_generic"))[1]
    return key, LIBRARY[key]
