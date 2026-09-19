"""Immutable evidence identities, explicit conflict policy, and local hybrid retrieval.

The retrieval index ranks evidence; it never creates or changes a fact. Snapshots
pin citation meanings even when a later Align edit or Read changes the registry.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import store

SCOPE_KEYS = {"model", "generation", "model_year", "market", "variant", "powertrain", "transmission", "test_basis", "price_basis", "effective_from", "effective_to"}
# Fixed local concepts improve recall without an embedding service or learned claims.
CONCEPTS = (
    {"boot", "luggage", "cargo", "suitcase", "storage"}, {"family", "child", "children", "isofix", "seats", "seating"},
    {"safety", "airbag", "airbags", "braking", "adas", "collision"}, {"warranty", "guarantee", "coverage"},
    {"mileage", "economy", "consumption", "efficiency", "kmpl"}, {"price", "cost", "rupees", "inr", "lakh"},
    {"engine", "power", "torque", "performance"}, {"automatic", "transmission", "dct", "cvt", "gearbox"},
    {"screen", "display", "infotainment", "carplay", "android"}, {"space", "room", "headroom", "legroom", "comfort"},
)


def _hash(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _norm(value) -> str:
    return " ".join(str(value or "").casefold().split())


def _scope(fact) -> dict:
    return {k: _norm(v) for k, v in (fact.get("scope") or {}).items() if k in SCOPE_KEYS and _norm(v)}


_MODEL_BRANDS = r"^(?:hyundai|kia|tata|maruti(?: suzuki)?|suzuki|toyota|honda|mahindra|volkswagen|skoda|renault|nissan|audi|bmw|mg|mercedes(?: benz)?) "


def scope_value(value, key: str) -> str:
    text = " ".join(re.findall(r"[a-z0-9]+", str(value).casefold()))
    return re.sub(_MODEL_BRANDS, "", text) if key == "model" else text


def scope_atoms(value, key: str) -> list[str]:
    """Split explicit variant enumerations only; 'SX and above' stays opaque."""
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [part.strip() for item in values if item is not None
            for part in (re.split(r"[,;]", str(item)) if key == "variant" else [str(item)]) if part.strip()]


def scope_values(value, key: str) -> set[str]:
    return {scope_value(v, key) for v in scope_atoms(value, key)}


def _powertrain_match(actual: str, requested: str) -> bool:
    """Match a requested engine family without equating different capacities.

    This affects retrieval applicability only; it never changes fact identities
    or declares differently qualified assertions to be the same evidence.
    """
    def parts(value):
        words = set(scope_value(value, "powertrain").split())
        family = "diesel" if "diesel" in words else "turbo petrol" if {"turbo","petrol"} <= words else "naturally aspirated petrol" if "petrol" in words and ("mpi" in words or {"naturally","aspirated"} <= words) else ""
        capacity = re.search(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[- ]?\s*(?:litres?|liters?|l)\b",str(value),re.I)
        return family, float(capacity[1]) if capacity else None, words
    family, capacity, words = parts(actual)
    requested_family, requested_capacity, requested_words = parts(requested)
    if not family or family != requested_family:
        return False
    if requested_capacity is not None and capacity != requested_capacity:
        return False
    if requested_capacity is None and scope_value(requested,"powertrain") not in {"diesel","turbo petrol","naturally aspirated petrol"}:
        return False
    technology = requested_words & {"gdi","crdi","mpi","u2","tsi","tdi"}
    return technology <= words


def variant_projection(fact: dict, requested: dict | None) -> dict | None:
    """Project explicit reviewed variant clauses without inventing trim order.

    Missing structured scope is not an all-trim claim. Only literal enumerations
    in the approved assertion itself can supply this narrow runtime view; broad
    source tables and relative descriptions such as 'SX and above' cannot.
    """
    if not fact.get("approved",True):
        return None
    wanted = scope_values((requested or {}).get("variant",""),"variant") - {"all","all variants","all trims"}
    if not wanted:
        return None
    def names(text):
        if re.search(r"\b(?:above|below|upwards|onwards|higher|lower|selected|certain|other|all|every)\b",text,re.I):
            return []
        text=re.sub(r"\s+(?:variants?|trims?)\s*$","",text.strip(),flags=re.I)
        values=[v.strip() for v in re.split(r",|\s+(?:and|&)\s+",text) if v.strip()]
        if not values or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9() -]{0,45}",v) for v in values):
            return []
        return values
    clauses=[]
    for field in ("value","conditions"):
        clauses += [v.strip() for v in re.split(r"[;\n]",str(fact.get(field,""))) if v.strip()]
    rows=[]
    for clause in clauses:
        negative=re.fullmatch(r"(?:Excludes?|Not (?:available|offered|included) (?:on|in|for))\s+(.+?)[.]?",clause,re.I)
        no_feature=re.fullmatch(r"(.+?)\s+(?:variant|trim)\s+has no\s+.+?[.]?",clause,re.I)
        positive=re.fullmatch(r"(.+?)\s+on\s+(.+?)[.]?",clause,re.I)
        polarity, variants = "", []
        if negative or no_feature:
            polarity="negative";variants=names((negative or no_feature)[1])
        elif positive and not re.search(r"\b(?:no|not|excludes?)\b",positive[1],re.I):
            polarity="positive";variants=names(positive[2])
        if variants:
            matched=[v for v in variants if scope_value(v,"variant") in wanted]
            if matched:
                rows.append({"polarity":polarity,"variants":matched,"assertion":clause,
                             "label":positive[1] if polarity=="positive" else str(fact.get("claim",""))})
    if not rows:
        return None
    return {"kind":"explicit_variant_clauses","rows":rows,"requested_variants":scope_atoms((requested or {}).get("variant",""),"variant")}


def scope_matches(fact: dict, requested: dict | None) -> bool:
    """A comparison may request a list of canonical alternatives per dimension."""
    applicability = fact.get("scope") or {}
    for key, value in (requested or {}).items():
        if key not in SCOPE_KEYS:
            continue
        wanted = scope_values(value, key)
        if not wanted:
            continue
        actual = scope_values(applicability.get(key, ""), key)
        if key == "variant" and actual & {"all", "all variants", "all trims"}:
            continue
        if key == "powertrain" and any(_powertrain_match(a,w) for a in scope_atoms(applicability.get(key,""),key) for w in scope_atoms(value,key)):
            continue
        if key == "transmission" and wanted == {"automatic"} and re.search(r"\b(?:automatic|IVT|CVT|DCT|AT)\b",str(applicability.get(key,"")),re.I):
            continue
        if not actual & wanted:
            return False
    return True


def _identity(fact) -> str:
    # Confidence/approval are review state. Value, qualifiers and exact evidence are meaning.
    return _hash({k: fact.get(k, {} if k in {"source", "scope"} else "") for k in
                  ("kind", "claim", "value", "conditions", "truth", "source", "scope")})


def _slot(fact) -> tuple:
    return (_norm(fact.get("claim")), json.dumps(_scope(fact), sort_keys=True), _norm(fact.get("conditions")))


def _same_scope(a: dict, b: dict) -> bool:
    """Unknown qualifiers are not universal applicability or an established match."""
    x, y = _scope(a), _scope(b)
    # Both sources must explicitly establish the car, year/generation, market, and trim.
    required = {"model", "market", "variant"}
    if not required <= x.keys() or not required <= y.keys():
        return False
    if not ((x.get("model_year") and y.get("model_year")) or (x.get("generation") and y.get("generation"))):
        return False
    if x != y or _norm(a.get("conditions")) != _norm(b.get("conditions")):
        return False
    if a.get("kind") in {"price", "offer", "policy", "availability"}:
        if not x.get("effective_from") or not x.get("effective_to"):
            return False
        if x["effective_to"] < datetime.now(timezone.utc).date().isoformat():
            return False
    return True


def _uploaded_document(src: dict) -> bool:
    return src.get("kind") in {"pdf", "doc", "text"} and src.get("origin", "uploaded") == "uploaded" and not src.get("crawl_parent")


def _evidence_anchor(fact: dict) -> dict:
    return {"source": fact.get("source", {}), "scope": _scope(fact), "conditions": _norm(fact.get("conditions"))}


def copy_on_edit(demo_id: str, previous_fact: dict, candidate: dict, *, competitor: bool = False) -> dict:
    """Version a fully validated human edit. Caller holds the demo write lock.

    This writes only the immutable registry snapshot and identity ledger. The caller
    replaces the current row and invalidates dependent drafts/approvals atomically.
    """
    result = copy.deepcopy(candidate)
    if _identity(previous_fact) == _identity(result):
        result["id"] = previous_fact["id"]
        return result
    current = store.read_json(demo_id, "understanding.json") or {}
    if current:
        _save_snapshot(demo_id, current)
    ledger = store.read_json(demo_id, "knowledge/identities.json") or {"version": 1, "next_product": 1, "next_competitor": 1, "ids": {}}
    for fact, owner in [*store.fact_entries(current), (previous_fact, {} if competitor else None)]:
        fid = fact.get("id")
        if not fid:
            continue
        ledger["ids"].setdefault(fid, {"identity": _identity(fact), "first_seen": store.now(), "role": "competitor" if owner is not None else "product", "assertion": copy.deepcopy(fact)})
        match = re.fullmatch(r"([FC])(\d+)(?:-\d+)?", fid)
        if match:
            key = "next_product" if match[1] == "F" else "next_competitor"
            ledger[key] = max(ledger[key], int(match[2]) + 1)
    counter, prefix = ("next_competitor", "C") if competitor else ("next_product", "F")
    while True:
        fid = f"{prefix}{ledger[counter]:03d}"
        ledger[counter] += 1
        if fid not in ledger["ids"]:
            break
    old_meta = previous_fact.get("knowledge", {})
    src = next((s for s in store.load(demo_id).get("sources", []) if s["id"] == result.get("source", {}).get("ref")), {})
    result.update(id=fid, edited=True)
    meta = result.setdefault("knowledge", {})
    meta.update(previous_id=previous_fact["id"], supersedes=[previous_fact["id"]],
                override_of=old_meta.get("override_of") or _identity(previous_fact),
                override_evidence=copy.deepcopy(old_meta.get("override_evidence") or _evidence_anchor(previous_fact)),
                assertion_hash=_identity(result), source_revision=src.get("revision", ""),
                evidence_path=src.get("evidence_path", ""), extraction_version=src.get("extraction_version", 1),
                source_url=src.get("final_url") or src.get("url", ""), fetched_at=src.get("fetched_at", ""),
                origin=src.get("origin", "uploaded" if _uploaded_document(src) else "website"),
                evidence_id="ev_" + _hash({"source": result.get("source", {}), "revision": src.get("revision", ""), "scope": _scope(result)})[:24])
    # A former conflict decision cannot automatically apply to a changed assertion.
    for key in ("excluded_by_precedence", "human_resolution", "review_required"):
        meta.pop(key, None)
    ledger["ids"][fid] = {"identity": _identity(result), "first_seen": store.now(), "role": "competitor" if competitor else "product", "assertion": copy.deepcopy(result), "supersedes": previous_fact["id"]}
    store.write_json(demo_id, "knowledge/identities.json", ledger)
    return result


def reconcile(demo_id: str, understanding: dict, previous: dict | None = None) -> dict:
    """Assign never-reused IDs and preserve reviewed corrections on identical evidence.

    An identity ledger survives row removal. Reordering sources or model output cannot
    retarget an old citation. Changed assertions get new IDs and require fact review.
    """
    und, previous = copy.deepcopy(understanding), previous or {}
    demo = store.load(demo_id)
    sources = {s["id"]: s for s in demo.get("sources", [])}
    ledger = store.read_json(demo_id, "knowledge/identities.json") or {"version": 1, "next_product": 1, "next_competitor": 1, "ids": {}}
    old_rows = list(store.fact_entries(previous))
    for old, owner in old_rows:
        fid = old.get("id")
        if not fid:
            continue
        ledger["ids"].setdefault(fid, {"identity": _identity(old), "first_seen": store.now(), "role": "competitor" if owner else "product"})
        match = re.fullmatch(r"F(\d+)", fid)
        if match:
            ledger["next_product"] = max(ledger["next_product"], int(match[1]) + 1)
        match = re.fullmatch(r"C(\d+)(?:-(\d+))?", fid)
        if match:
            ledger["next_competitor"] = max(ledger["next_competitor"], int(match[1]) + 1)
    old_exact, old_slots = defaultdict(list), defaultdict(list)
    for old, owner in old_rows:
        role = "competitor" if owner else "product"
        old_exact[(role, _identity(old))].append(old)
        old_slots[(role, _slot(old))].append(old)
    used_ids, added, changed, kept, conflicts = set(), [], [], [], []
    for fact, owner in store.fact_entries(und):
        role = "competitor" if owner else "product"
        fact["scope"] = {k: v for k, v in fact.get("scope", {}).items() if k in SCOPE_KEYS and v}
        src = sources.get(fact.get("source", {}).get("ref"), {})
        fact.setdefault("knowledge", {})["source_revision"] = src.get("revision", "")
        fingerprint = _identity(fact)
        exact = next((f for f in old_exact[(role, fingerprint)] if f["id"] not in used_ids and ledger["ids"][f["id"]]["identity"] == fingerprint), None)
        prior = old_slots.get((role, _slot(fact)), [])
        # An edited row is retained only when the underlying quoted evidence is unchanged.
        edited = next((f for f, old_owner in old_rows if bool(owner) == bool(old_owner) and f.get("edited") and f["id"] not in used_ids
                       and ((f.get("knowledge", {}).get("override_of") == fingerprint)
                            or (f.get("knowledge", {}).get("override_evidence") == _evidence_anchor(fact))
                            or (f in prior and f.get("source") == fact.get("source")))), None)
        if exact or edited:
            old = exact or edited
            if edited and not exact:
                proposal = copy.deepcopy(fact)
                fact.clear()
                fact.update(copy.deepcopy(old))
                conflicts.append({"id": "conf_" + _hash([old["id"], _identity(proposal)])[:16], "fact_ids": [old["id"]],
                                  "status": "reviewed_override_preserved", "resolution": "human_edit", "proposed": proposal,
                                  "reason": "Human correction retained because its source quote and applicability are unchanged."})
                fingerprint = _identity(fact)
            fact.update(id=old["id"], approved=old.get("approved", True), edited=old.get("edited", False))
            kept.append(fact["id"])
        else:
            counter = "next_competitor" if owner else "next_product"
            prefix = "C" if owner else "F"
            while True:
                fid = f"{prefix}{ledger[counter]:03d}"
                ledger[counter] += 1
                if fid not in ledger["ids"] and fid not in used_ids:
                    break
            fact.update(id=fid, approved=not bool(prior), edited=False)
            if prior:
                fact.setdefault("knowledge", {})["supersedes"] = [f["id"] for f in prior]
                changed.append({"id": fid, "previous_ids": [f["id"] for f in prior]})
            else:
                added.append(fid)
        used_ids.add(fact["id"])
        quote = fact.get("source", {})
        evidence_id = "ev_" + _hash({"source": quote, "revision": src.get("revision", ""), "scope": _scope(fact)})[:24]
        fact.setdefault("knowledge", {}).update({"assertion_hash": fingerprint, "evidence_id": evidence_id,
            "source_revision": src.get("revision", ""), "evidence_path": src.get("evidence_path", ""), "extraction_version": src.get("extraction_version", 1), "origin": src.get("origin", "uploaded" if _uploaded_document(src) else "website"),
            "source_url": src.get("final_url") or src.get("url", ""), "fetched_at": src.get("fetched_at", "")})
        ledger["ids"].setdefault(fact["id"], {"identity": fingerprint, "first_seen": store.now(), "role": role})
    # A changed extractor label must not silently erase an existing reviewed correction.
    for old, old_owner in old_rows:
        if not old.get("edited") or old["id"] in used_ids:
            continue
        src = sources.get(old.get("source", {}).get("ref"), {})
        same_evidence_proposal = any(new.get("source") == old.get("source") and _scope(new) == _scope(old)
                                     and _norm(new.get("conditions")) == _norm(old.get("conditions")) for new, _ in store.fact_entries(und))
        unchanged_source = bool(src) and src.get("crawl_active", True) and (same_evidence_proposal or src.get("revision", "") == old.get("knowledge", {}).get("source_revision", ""))
        conflicts.append({"id": "conf_" + _hash(["reviewed", old["id"], src.get("revision", "")])[:16], "fact_ids": [old["id"]],
                          "status": "reviewed_override_preserved" if unchanged_source else "unresolved",
                          "resolution": "human_edit" if unchanged_source else "requires_review", "previous_fact": old,
                          "reason": "Human correction retained on unchanged source evidence." if unchanged_source else "The source behind a human correction changed or was removed; review is required."})
        if unchanged_source:
            retained = copy.deepcopy(old)
            if old_owner:
                owner = next((c for c in und.get("competitors", []) if c.get("source_id") == old_owner.get("source_id") and c.get("name") == old_owner.get("name")), None)
                if owner is None:
                    owner = {**old_owner, "facts": []}
                    und.setdefault("competitors", []).append(owner)
                owner["facts"].append(retained)
            else:
                und["facts"].append(retained)
            used_ids.add(old["id"])
            kept.append(old["id"])
    rows = list(store.fact_entries(und))
    # Enforce exact evidence on newly extracted, persisted sources. Legacy rows retain
    # compatibility until they are re-read; mock fixtures intentionally have no quotes.
    from . import config
    if not config.MOCK_LLM:
        for fact, _ in rows:
            src = sources.get(fact.get("source", {}).get("ref"), {})
            if src.get("crawl_cached"):
                fact["approved"] = False
                fact.setdefault("knowledge", {})["review_required"] = "Earlier source revision was not fetched this read; review freshness."
            if not src.get("evidence_path"):
                continue
            extraction = store.read_json(demo_id, src["evidence_path"]) or {}
            quote = _norm(fact.get("source", {}).get("quote"))
            if not quote or quote not in _norm(extraction.get("text")) or not fact.get("source", {}).get("locator"):
                fact["approved"] = False
                fact.setdefault("knowledge", {})["review_required"] = "Citation quote/locator was not verified against this source revision."
    rows = list(store.fact_entries(und))
    for i, (a, owner_a) in enumerate(rows):
        for b, owner_b in rows[i + 1:]:
            if bool(owner_a) != bool(owner_b) or (owner_a and _norm(owner_a.get("name")) != _norm(owner_b.get("name"))):
                continue
            if a.get("knowledge", {}).get("review_required") or b.get("knowledge", {}).get("review_required"):
                continue
            if _norm(a.get("claim")) != _norm(b.get("claim")) or _norm(a.get("value")) == _norm(b.get("value")) or not _same_scope(a, b):
                continue
            sa, sb = sources.get(a.get("source", {}).get("ref"), {}), sources.get(b.get("source", {}).get("ref"), {})
            da, db = _uploaded_document(sa), _uploaded_document(sb)
            previous_decision = next((c for c in previous.get("knowledge", {}).get("conflicts", [])
                                      if c.get("resolution") == "human_review" and set(c.get("fact_ids", [])) == {a["id"], b["id"]}
                                      and c.get("preferred_fact_id") in {a["id"], b["id"]}), None)
            preferred = (a if previous_decision["preferred_fact_id"] == a["id"] else b) if previous_decision else (a if da and not db else b if db and not da else None)
            if preferred:
                loser = b if preferred is a else a
                loser["approved"] = False
                loser.setdefault("knowledge", {})["excluded_by_precedence"] = preferred["id"]
                preferred.setdefault("knowledge", {}).pop("excluded_by_precedence", None)
                preferred["approved"] = True if previous_decision else preferred.get("approved", True)
                resolution, status = ("human_review" if previous_decision else "uploaded_document"), "resolved"
            else:
                a["approved"] = b["approved"] = False
                resolution, status = "requires_review", "unresolved"
            conflicts.append({"id": "conf_" + _hash(sorted([a["id"], b["id"]]))[:16], "fact_ids": [a["id"], b["id"]],
                              "preferred_fact_id": preferred["id"] if preferred else None, "status": status, "resolution": resolution,
                              "scope": _scope(a), "reason": "Preserved the explicit human decision for unchanged assertions." if previous_decision else "Conflicting exact values with matching explicit applicability.",
                              **({k: previous_decision[k] for k in ("reviewed_at", "review_note") if k in previous_decision} if previous_decision else {})})
    removed = [f["id"] for f, _ in old_rows if f["id"] not in used_ids]
    und["knowledge"] = {"version": 1, "conflicts": conflicts, "decisions": previous.get("knowledge", {}).get("decisions", []), "coverage": store.read_json(demo_id, "knowledge/coverage.json") or {},
                        "diff": {"added": added, "changed": changed, "removed": removed, "unchanged": kept}, "reconciled_at": store.now()}
    store.write_json(demo_id, "knowledge/identities.json", ledger)
    # Keep the old complete registry before the caller replaces understanding.json.
    if previous:
        _save_snapshot(demo_id, previous)
    return und


def resolve_conflict(demo_id: str, conflict_id: str, preferred_fact_id: str, *, note: str = "") -> dict:
    """Persist an explicit human winner; caller invalidates downstream stages/approvals.

    Sources, quotes and immutable historical snapshots remain intact. Selecting an
    assertion for the current draft does not change already published demos.
    """
    if not isinstance(note, str) or len(note) > 2000:
        raise ValueError("Review note must be text up to 2000 characters")
    with store._lock(demo_id):
        und = store.read_json(demo_id, "understanding.json") or {}
        conflict = next((c for c in und.get("knowledge", {}).get("conflicts", []) if c.get("id") == conflict_id), None)
        if not conflict:
            raise KeyError("Evidence conflict not found")
        ids = conflict.get("fact_ids", [])
        if preferred_fact_id not in ids or len(ids) < 2:
            raise ValueError("Choose one of the current assertions in this conflict")
        facts = {f["id"]: f for f, _ in store.fact_entries(und)}
        if any(fid not in facts for fid in ids):
            raise ValueError("This conflict refers to earlier evidence; re-read before resolving it")
        winner = facts[preferred_fact_id]
        if not all(winner.get("source", {}).get(k) for k in ("ref", "locator", "quote")):
            raise ValueError("The chosen assertion needs a source, exact quote and locator")
        _save_snapshot(demo_id, und)
        before = copy.deepcopy(conflict)
        for fid in ids:
            row = facts[fid]
            row["approved"] = fid == preferred_fact_id
            row.setdefault("knowledge", {})["human_resolution"] = conflict_id
            if fid == preferred_fact_id:
                row["knowledge"].pop("excluded_by_precedence", None)
                row["knowledge"].pop("review_required", None)
            else:
                row["knowledge"]["excluded_by_precedence"] = preferred_fact_id
        conflict.update(status="resolved", resolution="human_review", preferred_fact_id=preferred_fact_id,
                        reviewed_at=store.now(), review_note=note.strip(), reason="A reviewer explicitly selected the applicable supported assertion.")
        und.setdefault("knowledge", {}).setdefault("decisions", []).append({"conflict_id": conflict_id,
            "preferred_fact_id": preferred_fact_id, "note": note.strip(), "at": store.now(), "previous": before})
        store.write_json(demo_id, "understanding.json", und)
    return {"understanding": und, "conflict": conflict, "changed_fact_ids": list(ids), "requires_approval": True}


def _snapshot_sources(demo_id: str, und: dict) -> list[dict]:
    fields = ("id", "name", "kind", "url", "path", "origin", "revision", "evidence_path", "final_url", "fetched_at", "extraction_version", "duplicate_of")
    records = {s["id"]: {k: s[k] for k in fields if k in s} for s in store.load(demo_id).get("sources", [])}
    for fact, _ in store.fact_entries(und):
        ref, meta = fact.get("source", {}).get("ref"), fact.get("knowledge", {})
        if not ref:
            continue
        source = records.setdefault(ref, {"id": ref})
        revision = meta.get("source_revision")
        if revision:
            source.update(revision=revision, evidence_path=meta.get("evidence_path") or f"knowledge/sources/{ref}/{revision}.json")
        if meta.get("source_url"):
            source["url"] = source["final_url"] = meta["source_url"]
        if meta.get("fetched_at"):
            source["fetched_at"] = meta["fetched_at"]
    return list(records.values())


def _save_snapshot(demo_id: str, und: dict) -> dict:
    body = {"version": 1, "product": und.get("product", {}), "facts": und.get("facts", []), "competitors": und.get("competitors", []),
            "conflicts": und.get("knowledge", {}).get("conflicts", []), "coverage": und.get("knowledge", {}).get("coverage", {}),
            "sources": _snapshot_sources(demo_id, und)}
    sid = "kb_" + _hash(body)[:24]
    filename = f"knowledge/snapshots/{sid}.json"
    prior = store.read_json(demo_id, filename)
    if prior:
        return prior
    record = {"id": sid, "created_at": store.now(), **body}
    store.write_json(demo_id, filename, record)
    _write_index(demo_id, record)
    return record


def snapshot(demo_id: str, *, publish: bool = False) -> dict:
    demo = store.load(demo_id)
    if publish and not all(demo.get("approvals", {}).get(card, False) for card in store.CARDS):
        raise ValueError("All six Align cards must be approved before publishing a knowledge snapshot")
    und = store.read_json(demo_id, "understanding.json") or {}
    if not und:
        raise ValueError("No understanding registry exists")
    result = _save_snapshot(demo_id, und)
    if publish:
        store.write_json(demo_id, "knowledge/published.json", {"id": result["id"], "published_at": store.now()})
    return result


def _features(text: str) -> Counter:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    bag = Counter(words)
    for i, concept in enumerate(CONCEPTS):
        if concept.intersection(words):
            bag[f"concept:{i}"] += 2
    # Character features recover singular/plural and minor spelling variation locally.
    for word in set(words):
        if len(word) >= 5:
            for j in range(len(word) - 2):
                bag["tri:" + word[j:j+3]] += 0.15
    return bag


def _write_index(demo_id: str, snap: dict) -> dict:
    docs = []
    for fact, owner in store.fact_entries(snap):
        text = " ".join(str(fact.get(k, "")) for k in ("claim", "value", "conditions")) + " " + json.dumps(fact.get("scope", {}))
        docs.append({"id": fact["id"], "owner": owner.get("name", "") if owner else "", "features": dict(_features(text)), "length": len(text.split())})
    index = {"version": 1, "snapshot_id": snap["id"], "method": "BM25 + fixed concept/character cosine", "documents": docs}
    store.write_json(demo_id, f"knowledge/index/{snap['id']}.json", index)
    return index


def retrieve(demo_id: str, query: str, *, snapshot_id: str | None = None, scope: dict | None = None,
             competition: bool = False, limit: int = 8) -> dict:
    if snapshot_id:
        if not re.fullmatch(r"kb_[a-f0-9]{24}", snapshot_id):
            raise ValueError("Invalid knowledge snapshot id")
        snap = store.read_json(demo_id, f"knowledge/snapshots/{snapshot_id}.json")
        if not snap:
            raise ValueError("Knowledge snapshot not found")
    else:
        published = store.read_json(demo_id, "knowledge/published.json") or {}
        snap = store.read_json(demo_id, f"knowledge/snapshots/{published['id']}.json") if published else None
        snap = snap or snapshot(demo_id)
    index = store.read_json(demo_id, f"knowledge/index/{snap['id']}.json") or _write_index(demo_id, snap)
    docs, q = index["documents"], _features(query)
    df = Counter(t for doc in docs for t in doc["features"])
    avg = sum(doc["length"] for doc in docs) / max(1, len(docs)) or 1
    ranking = {}
    for doc in docs:
        features, score = doc["features"], 0.0
        for term, weight in q.items():
            tf = features.get(term, 0)
            if not tf:
                continue
            idf = math.log(1 + (len(docs) - df[term] + .5) / (df[term] + .5))
            score += weight * idf * (tf * 2.2 / (tf + 1.2 * (.25 + .75 * doc["length"] / avg)))
        dot = sum(v * features.get(k, 0) for k, v in q.items())
        norm = math.sqrt(sum(v*v for v in q.values()) * sum(v*v for v in features.values())) or 1
        ranking[(doc["id"], doc["owner"])] = score + dot / norm
    evidence = []
    requested = {k: v for k, v in (scope or {}).items() if k in SCOPE_KEYS and v}
    for fact, owner in store.fact_entries(snap):
        if not fact.get("approved", True) or fact.get("knowledge", {}).get("excluded_by_precedence") or (owner and not competition):
            continue
        applicability = _scope(fact)
        projection = variant_projection(fact, requested)
        # Preserve negative applicability and explicit per-trim assertion clauses
        # without broadening any other scope dimension or changing the registry.
        if not scope_matches(fact, requested):
            if not projection or not scope_matches(fact,{k:v for k,v in requested.items() if k!="variant"}):
                continue
        today = datetime.now(timezone.utc).date().isoformat()
        if (applicability.get("effective_to") and applicability["effective_to"] < today) or (applicability.get("effective_from") and applicability["effective_from"] > today):
            continue
        score = ranking.get((fact["id"], owner.get("name", "") if owner else ""), 0)
        if score <= 0:
            continue
        wanted_variants = scope_values(requested.get("variant", ""), "variant")
        fact_variants = scope_values(fact.get("scope", {}).get("variant", ""), "variant")
        if wanted_variants and fact_variants & wanted_variants and not fact_variants & {"all","all variants","all trims"}:
            # Named configuration details should not be crowded out by repeated
            # all-trim assertions. This changes rank, never evidence eligibility.
            score *= 1.2
        item = {**copy.deepcopy(fact), "score": round(score, 5), "entity": owner.get("name") if owner else snap.get("product", {}).get("name"),
                "competition": bool(owner), "snapshot_id": snap["id"]}
        if projection:
            item["applicability_projection"] = projection
        source = next((s for s in snap.get("sources", []) if s["id"] == fact.get("source", {}).get("ref")), {})
        item["source_metadata"] = source
        if source.get("evidence_path"):
            extraction = store.read_json(demo_id, source["evidence_path"]) or {}
            quote = _norm(fact.get("source", {}).get("quote"))
            locator = fact.get("source", {}).get("locator", "")
            matching = [s for s in extraction.get("sections", []) if (quote and quote in _norm(s.get("text"))) or (locator and locator == s.get("locator"))]
            item["context"] = matching[:2]
        evidence.append(item)
    evidence.sort(key=lambda row: (-row["score"], row["id"]))
    unique, seen = [], set()
    for row in evidence:
        key = (_norm(row.get("claim")), _norm(row.get("value")), _norm(row.get("conditions")), json.dumps(row.get("scope",{}),sort_keys=True), row.get("entity"))
        if key not in seen:
            unique.append(row); seen.add(key)
    return {"snapshot_id": snap["id"], "evidence": unique[:max(1, min(30, limit))], "conflicts": snap.get("conflicts", []),
            "coverage": snap.get("coverage", {}), "method": index["method"]}
