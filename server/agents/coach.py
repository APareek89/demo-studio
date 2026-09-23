"""Sales Coach: turn approved evidence into the reviewed category story spine."""
from __future__ import annotations

import copy
import hashlib
import json
import re

from .. import config, schemas, store
from ..llm import claude
from . import author, faq, playbooks, visuals
from .principles import fact_context

COACH_SYSTEM = """You are a sales trainer for {category}. You have trained showroom staff on this product class. Decide what a good
salesperson covers, in what order, for THIS product, using only the APPROVED FACT REGISTRY below. You do not write
dialogue. You write the playbook the planner must follow.

RULES
- Follow CATEGORY LIBRARY ORDER as the spine. Keep every stop whose evidence exists. A stop the registry cannot support
  stays in the list with must_cover=false and a gap naming exactly what is missing (e.g. "ground clearance figure").
- The first stop must be a fundamental. Delighters (sunroof, ventilated seats, audio, ambient lighting) never come before
  the fundamentals are covered.
- Each stop lists the registry ids that support it and the picture ids that literally show it. A cabin photo does not
  show an engine. If no picture shows a stop, leave picture_ids empty; do not invent one.
- usps: EXACTLY THREE. Choose each by asking what a buyer would tell a friend that evening, then check the registry
  supports it. At least two USPs must sit on fundamental stops. Names are promises in the buyer's language, 3-8 words,
  with NO digits, units, model codes or parts lists.
Never build a USP or a narration line on a company or market statistic: units sold, monthly or annual
sales figures, customer totals, market share, sales rank, years on sale, or award counts. These are the
brand's numbers, not the buyer's experience; they date within weeks and no one buys because of a units
figure. A derived reputational line is allowed ONCE, in the intro, with no figure and no rank — "one of
the cars you see most on Indian roads" — still citing the fact id it rests on.
You choose what the demo is emotionally about, not only what it proves: decide the one moment in owning
this product that the whole tour walks toward, and make the lead fundamental stop the one closest to it, and place the delighter that serves it right after the fundamentals. The
author can make any stop sound warm; it cannot rescue a tour that opens on dimensions.
- objections: the 3-6 doubts a buyer in this category raises (price, running cost, service, resale, size, safety).
  Mark each supported (with ids) or unknown. Never invent a response.
- evidence_gaps: what the category playbook needs that the registry lacks, with the source that would supply it
  (spec sheet page, brochure table, official website section, a photo of the engine bay or side profile).
- Plain, everyday words everywhere. No engineering vocabulary in labels or names.
Return JSON matching the schema exactly.
"""

KINDS = {"fundamental", "differentiator", "delighter", "hygiene", "ownership"}
_USP_UNITS = re.compile(r"\b(?:cc|hp|bhp|kw|kwh|mm|cm|km|kg|nm|litres?|liters?|dct|iv[t]|mpfi)\b", re.I)


def _unsafe_usp_name(name: str) -> bool:
    return bool(author.NUMBERISH.search(name) or re.search(r"\d", name) or _USP_UNITS.search(name) or not 3 <= len(name.split()) <= 8)


def _unique(values: list) -> list:
    return list(dict.fromkeys(values))


def _allowed_understanding(und: dict, demo: dict) -> dict:
    allowed = copy.deepcopy(und)
    for key in ("images", "shots"):
        allowed[key] = [row for row in und.get(key, []) if store.visual_allowed(demo, row.get("source_id", ""))]
    return allowed


def validate(pb: dict, und: dict) -> list[str]:
    """Sanitize evidence identities and unsafe labels, retaining every diagnostic for Align."""
    issues = []
    fact_ids = {f["id"] for f in und.get("facts", []) if f.get("approved", True)}
    pictures = {p["id"] for key in ("images", "shots") for p in und.get(key, [])}
    stops = pb.get("stops", [])
    stop_ids = [stop.get("id") for stop in stops]
    if len(set(stop_ids)) != len(stop_ids):
        raise ValueError("Duplicate playbook stop IDs are not allowed")
    if not stops:
        raise ValueError("A playbook needs a fundamental stop")
    for stop in stops:
        if stop.get("kind") not in KINDS:
            raise ValueError(f"Invalid kind for playbook stop {stop.get('id')}")
        old_facts, old_pictures = stop.get("fact_ids", []), stop.get("picture_ids", [])
        stop["fact_ids"] = _unique([fid for fid in old_facts if fid in fact_ids])
        stop["picture_ids"] = _unique([ref for ref in old_pictures if ref in pictures])
        if old_facts != stop["fact_ids"]:
            issues.append(f"{stop['id']}: removed unapproved or duplicate fact IDs")
        if old_pictures != stop["picture_ids"]:
            issues.append(f"{stop['id']}: removed unavailable or duplicate picture IDs")
        gaps = stop.setdefault("gaps", [])
        if not stop["fact_ids"]:
            if stop.get("must_cover", True):
                issues.append(f"{stop['id']}: no approved facts; stop retained as an evidence gap")
            stop["must_cover"] = False
            gap = f"Approved evidence for {stop['label'].lower()}"
            if not gaps:
                gaps.append(gap)
        if stop.get("must_cover") and not stop["picture_ids"]:
            if not any(re.search(r"picture|photo|image|visual", gap, re.I) for gap in gaps):
                gaps.append(f"Picture showing {stop['label'].lower()}")
                issues.append(f"{stop['id']}: no literal picture; picture gap recorded")
    if stops[0].get("kind") != "fundamental":
        first = next((stop for stop in stops if stop.get("kind") == "fundamental"), None)
        if first is None:
            raise ValueError("A playbook needs a fundamental stop")
        stops.remove(first)
        stops.insert(0, first)
        issues.append("Moved the first fundamental to the opening stop")
    # A drag/relabel may put another fundamental after a delighter. Preserve the
    # reviewed relative order while keeping the category fundamentals first.
    last_fundamental = max(i for i, stop in enumerate(stops) if stop["kind"] == "fundamental")
    early_delighters = [stop for stop in stops[:last_fundamental] if stop["kind"] == "delighter"]
    if early_delighters:
        stops[:] = [stop for stop in stops if stop not in early_delighters]
        after = max(i for i, stop in enumerate(stops) if stop["kind"] == "fundamental") + 1
        stops[after:after] = early_delighters
        issues.append("Moved delighters after the fundamentals")
    usps = pb.get("usps", [])
    if len(usps) != 3:
        issues.append(f"Playbook needs exactly three USPs; received {len(usps)}")
    stop_by_id = {stop["id"]: stop for stop in stops}
    for usp in usps:
        stop = stop_by_id.get(usp.get("stop_id"), {})
        allowed = set(stop.get("fact_ids", [])) & fact_ids
        old = usp.get("fact_ids", [])
        usp["fact_ids"] = _unique([fid for fid in old if fid in allowed])
        if old != usp["fact_ids"]:
            issues.append(f"{usp.get('id')}: removed facts outside its approved stop")
        if not usp["fact_ids"]:
            issues.append(f"{usp.get('id')}: USP needs approved supporting evidence")
        name = usp.get("name", "")
        if _unsafe_usp_name(name):
            issues.append(f"{usp.get('id')}: rejected USP name; use three to eight everyday words without figures, units or model codes")
    if sum(bool(u.get("fact_ids")) and stop_by_id.get(u.get("stop_id"), {}).get("kind") == "fundamental" for u in usps) < 2:
        issues.append("At least two supported USPs must sit on fundamental stops")
    for objection in pb.get("objections", []):
        objection["fact_ids"] = _unique([fid for fid in objection.get("fact_ids", []) if fid in fact_ids])
        objection["status"] = "supported" if objection["fact_ids"] else "unknown"
    library_key, _ = playbooks.match((und.get("product") or {}).get("category", ""))
    pb["category_source"] = "inferred" if library_key == "_generic" else "library"
    return issues


def mock_playbook(und: dict, entry: dict) -> dict:
    """Stable no-call fixture using only keyword matches against approved fact claims."""
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    image_map = und.get("image_map") or {}
    stops, gaps = [], []
    for row in entry["order"]:
        ids = [f["id"] for f in facts if any(word in f.get("claim", "").lower() for word in row["covers"])]
        missing = f"Approved evidence for {row['label'].lower()}: {', '.join(row['covers'])}"
        stop = {key: row[key] for key in ("id", "label", "kind")}
        stop.update(why_here="Cover this category topic before moving to the next part of the story.", fact_ids=ids,
                    picture_ids=_unique([ref for fid in ids for ref in image_map.get(fid, [])]),
                    must_cover=bool(ids), gaps=[] if ids else [missing])
        stops.append(stop)
        if not ids:
            gaps.append({"what": missing, "why_it_matters": "The buyer needs this topic to assess the product.",
                         "suggested_source": "Official specification sheet or brochure table"})
    supported = [stop for stop in stops if stop["fact_ids"]]
    selected = supported[:3] or stops[:3]
    usps = [{"id": f"usp-{i + 1}", "name": f"Explore {stop['label'].lower()} choices", "fact_ids": stop["fact_ids"][:], "stop_id": stop["id"]}
            for i, stop in enumerate((selected * 3)[:3])]
    objections = []
    for concern in ("price", "running cost", "service", "resale", "size", "safety"):
        ids = [f["id"] for f in facts if concern in f.get("claim", "").lower()]
        objections.append({"objection": f"What should I know about {concern}?", "fact_ids": ids, "status": "supported" if ids else "unknown"})
    category = (und.get("product") or {}).get("category", "")
    return {"category": category, "category_source": "inferred" if playbooks.match(category)[0] == "_generic" else "library",
            "stops": stops, "usps": usps, "objections": objections, "evidence_gaps": gaps,
            "notes": "Deterministic mock playbook for free flow verification; review selling promises before publication."}


def apply_overrides(pb: dict, demo_id: str) -> dict:
    """Apply reviewed order/kinds to a copy; source evidence still decides what is safe."""
    result = copy.deepcopy(pb)
    override = store.read_json(demo_id, "playbook-overrides.json") or {}
    order = override.get("stop_order", [])
    if not isinstance(order, list) or len(set(order)) != len(order):
        raise ValueError("Playbook stop order must contain unique IDs")
    by_id = {stop["id"]: stop for stop in result.get("stops", [])}
    if any(stop_id not in by_id for stop_id in order):
        raise ValueError("Playbook override names an unknown stop")
    result["stops"] = [by_id[stop_id] for stop_id in order] + [stop for stop in result.get("stops", []) if stop["id"] not in order]
    for stop_id, kind in override.get("kinds", {}).items():
        if stop_id not in by_id or kind not in KINDS:
            raise ValueError("Playbook override names an unknown stop or kind")
        by_id[stop_id]["kind"] = kind
    und = _allowed_understanding(store.read_json(demo_id, "understanding.json") or {}, store.load(demo_id))
    result["issues"] = _unique([*result.get("issues", []), *validate(result, und)])
    return result


def run(demo_id: str, emit, instruction: str = "") -> dict:
    und = store.read_json(demo_id, "understanding.json")
    if not und:
        raise RuntimeError("Nothing to coach from — read the sources first")
    demo = store.load(demo_id)
    und = _allowed_understanding(und, demo)
    previous = store.read_json(demo_id, "playbook.json") or {}
    registry_hash = faq._registry_hash(demo_id)
    audience = demo.get("settings", {}).get("audience", "everyday")
    product = und.get("product") or {}
    category = product.get("category", "")
    library_key, entry = playbooks.match(category)
    # The FAQ hash covers claim meaning; Coach also consumes category, source
    # provenance, unknowns and picture eligibility/tags. Changes to any of those
    # must not reuse a stale story merely because the claim text stayed equal.
    input_hash = hashlib.sha256(json.dumps({key: und.get(key) for key in
        ("product", "facts", "images", "shots", "image_map", "unknowns")}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:20]
    if (not instruction and previous and previous.get("registry_hash") == registry_hash
            and previous.get("library_version") == playbooks.VERSION and previous.get("audience") == audience
            and previous.get("library_key") == library_key and previous.get("category") == category
            and previous.get("input_hash") == input_hash):
        emit("Playbook unchanged — reused")
        return previous
    emit("Preparing the sales playbook: fundamentals, selling points and evidence gaps…")
    facts = [f for f in und.get("facts", []) if f.get("approved", True)]
    allowed_pictures = {row["id"] for key in ("images", "shots") for row in und.get(key, [])}
    rows = []
    for fact in facts:
        row = fact_context(fact)
        pictures = [ref for ref in (und.get("image_map") or {}).get(fact["id"], []) if ref in allowed_pictures]
        if pictures:
            row += f" (pictures: {', '.join(pictures)})"
        if fact.get("origin"):
            row += f" (origin: {fact['origin']})"
        rows.append(row)
    facts_txt = "\n".join(rows) or "(empty)"
    shots_txt = "\n".join(f"{s['id']} {s['start']:.1f}-{s['end']:.1f}s q{s['quality']} · {s['part']} · {s['feature']} · {s['description']}" for s in und.get("shots", [])) or "(none)"
    imgs_txt = "\n".join(f"{i['id']} q{i['quality']} · {i['angle']} · {', '.join(visuals.part_names(i))} · {i['description']}" for i in und.get("images", [])) or "(none)"
    unknowns = "\n".join(f"{u['id']} {u['question']}" for u in und.get("unknowns", []) if u.get("status") == "open") or "(none)"
    content = f"""PRODUCT: {json.dumps(product)}
CATEGORY LIBRARY ORDER (version {playbooks.VERSION}): {json.dumps(entry['order'])}
AUDIENCE: {audience}

APPROVED FACT REGISTRY ({len(facts)}):
{facts_txt}

OPEN UNKNOWNS:
{unknowns}

VIDEO SHOTS ({len(und.get('shots', []))}):
{shots_txt}

IMAGES ({len(und.get('images', []))}):
{imgs_txt}
"""
    if instruction:
        if previous:
            content += f"\nPREVIOUS PLAYBOOK:\n{json.dumps(previous)}\n"
        content += f"\nREVISION INSTRUCTION FROM THE USER — follow it precisely:\n{instruction}\n"
    if config.MOCK_LLM:
        pb = mock_playbook(und, entry)
    else:
        pb = claude.structured(COACH_SYSTEM.format(category=category), content, schemas.Playbook, max_tokens=12000).model_dump()
    pb["issues"] = validate(pb, und)
    if len(pb.get("usps", [])) != 3 or any(_unsafe_usp_name(usp.get("name", "")) for usp in pb.get("usps", [])):
        raise ValueError("Playbook requires exactly three USPs with safe everyday names: " + "; ".join(pb["issues"]))
    pb.update(library_version=playbooks.VERSION, library_key=library_key, registry_hash=registry_hash, audience=audience, input_hash=input_hash)
    pb = apply_overrides(pb, demo_id)
    schemas.Playbook.model_validate(pb)
    # The previous successful artifact stays intact until every check has passed.
    store.write_json(demo_id, "playbook.json", pb)
    store.log(demo_id, "coach", {"stops": [stop["id"] for stop in pb["stops"]], "issues": pb["issues"], "library_key": library_key})
    emit(f"Sales playbook ready: {len(pb['stops'])} story stops, {len(pb['usps'])} selling points, {len(pb['evidence_gaps'])} evidence gaps.")
    return pb
