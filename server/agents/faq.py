"""Uploaded FAQ answers and a snapshot-bound cache of questions customers actually ask."""
from __future__ import annotations

import hashlib
import json
import re
import copy

from .. import store
from . import author, deck, plain_terms, qa

QUESTION_POLICY = "uploaded-and-customer-v1"

# Remove common question words before comparing FAQ wording.
# This supports the legacy match helper; runtime_graph.py:reason separately handles conversational answers.
STOP = set("the a an and or of to in on at for with by from as is are was were be been it its this that these those you your we our they their i me my "
           "do does did can will would could should may might have has had what which who how why when where much many any some there here about please tell "
           "give get got know want need like also just only very really if then than so".split())


# Extract one question from a document line, removing common numbering and Markdown prefixes.
# Returns a question or None for doc_questions; understand.py:extract_text supplies non-text document content.
def question_from_line(line: str) -> str | None:
    """Read both question-only lines and common inline `1. **Question?** Answer` FAQ rows."""
    clean = re.sub(r"^\s*#{1,6}\s*", "", line or "").strip()
    clean = re.sub(r"^\s*(?:q\d*|\d+|[-*•])\s*[\.\):]\s*", "", clean, flags=re.I)
    clean = clean.lstrip("*_ ")
    clean = re.sub(r"^q\s*:\s*", "", clean, flags=re.I)
    m = re.match(r"^(.{7,199}?\?)", clean)
    if not m:
        return None
    q = m.group(1).strip().rstrip("*_ ")
    return q if 8 <= len(q) <= 200 else None


# Turn a question into useful words for the older FAQ matching path.
# Returns a word set for match; the conversational path is separate in runtime_graph.py.
def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9\-\.]*", (text or "").lower()):
        w = w.strip(".")
        if w in STOP or len(w) < 2:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 and not w.endswith("ss") else w)
    return out


# Read FAQ-labelled sources, extract their questions and remove repeated wording.
# Returns question strings; store.py:load locates sources and understand.py:extract_text reads documents.
def doc_questions(demo_id: str) -> list[str]:
    """Lines ending in '?' from uploaded FAQ documents (text/markdown; PDFs via the same extractor the registry uses)."""
    demo = store.load(demo_id)
    qs: list[str] = []
    # Read only FAQ-labelled text or document sources, and skip unreadable files.
    # understand.py:extract_text handles document conversion before question_from_line selects the questions.
    for s in demo.get("sources", []):
        is_faq = s.get("role") == "faq" or "faq" in (s.get("name") or "").lower()
        if not is_faq or s.get("kind") not in ("text", "pdf", "doc"):
            continue
        try:
            if s.get("kind") == "text":
                txt = store.path(demo_id, s["path"]).read_text(errors="replace")
            else:
                from .understand import extract_text  # type: ignore
                txt = extract_text(demo_id, s) or ""
        except Exception:
            continue
        for line in txt.splitlines():
            q = question_from_line(line)
            if q:
                qs.append(q)
    # Remove repeated question text while keeping the first occurrence and its order.
    # The returned list becomes the document portion of run; qa.py:answer supplies each answer later.
    seen, out = set(), []
    for q in qs:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out


# Hash fact text, conditions, approval states and the competition setting for cache reuse.
# Reads the registry saved by understand.py:run; run uses the hash to decide whether old FAQ answers still apply.
def _registry_hash(demo_id: str, *, snapshot_id: str | None = None) -> str:
    und = _snapshot_registry(demo_id, snapshot_id) if snapshot_id else store.read_json(demo_id, "understanding.json") or {}
    rows = [(f.get("id"), f.get("claim"), f.get("value"), f.get("conditions"), f.get("approved", True)) for f in und.get("facts", [])]
    rows += [(f.get("id"), f.get("claim"), f.get("value"), f.get("conditions"), f.get("approved", True)) for c in und.get("competitors", []) for f in c.get("facts", [])]
    competition = store.load(demo_id).get("settings", {}).get("competition", "off")
    return hashlib.sha256(json.dumps({"facts": rows, "competition": competition}, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def _snapshot_registry(demo_id: str, snapshot_id: str) -> dict:
    if not re.fullmatch(r"kb_[a-f0-9]{24}", snapshot_id):
        raise ValueError("Invalid knowledge snapshot id")
    registry = store.read_json(demo_id, f"knowledge/snapshots/{snapshot_id}.json")
    if not registry or registry.get("id") != snapshot_id:
        raise ValueError("Knowledge snapshot not found")
    return registry


def _context(demo_id: str, snapshot_id: str | None = None, registry_hash: str | None = None) -> tuple[str, str, dict]:
    if snapshot_id is None:
        bundle = store.read_json(demo_id, "bundle.json") or {}
        published = store.read_json(demo_id, "knowledge/published.json") or {}
        snapshot_id = bundle.get("knowledge_snapshot_id") or published.get("id") or ""
        if not snapshot_id and store.read_json(demo_id, "understanding.json"):
            from .. import knowledge
            snapshot_id = knowledge.snapshot(demo_id)["id"]
    registry = _snapshot_registry(demo_id, snapshot_id) if snapshot_id else store.read_json(demo_id, "understanding.json") or {}
    fingerprint = _registry_hash(demo_id, snapshot_id=snapshot_id)
    if registry_hash is not None and registry_hash != fingerprint:
        raise ValueError("FAQ registry hash does not match its snapshot")
    return snapshot_id, fingerprint, registry


def _source(entry: dict) -> str:
    return entry.get("source") or ("document" if entry.get("origin") == "document" else "customer" if entry.get("origin") == "runtime" else "")


def similarity(question: str, other: str) -> float:
    """The same conservative word-overlap rule for answers, tombstones and gaps."""
    qt, et = _tokens(question), _tokens(other)
    if not qt or not et:
        return 2.0 if question.strip().casefold() == other.strip().casefold() and question.strip() else 0.0
    inter = len(qt & et)
    jaccard, cover_q, cover_e = inter / len(qt | et), inter / len(qt), inter / len(et)
    return jaccard + cover_q if jaccard >= .6 or (cover_q >= .75 and cover_e >= .2) else 0.0


def _best(entries: list[dict], question: str) -> dict | None:
    ranked = [(similarity(question, entry.get("question", "")), -i, entry) for i, entry in enumerate(entries)]
    score, _, entry = max(ranked, key=lambda item: item[:2], default=(0, 0, None))
    return entry if score else None


def _approved(registry: dict, competition: bool) -> set[str]:
    return {fact["id"] for fact, owner in store.fact_entries(registry)
            if (owner is None or competition) and fact.get("approved", True)
            and not (fact.get("knowledge") or {}).get("excluded_by_precedence")
            and (fact.get("knowledge") or {}).get("conflict_status") not in {"suppressed", "unresolved"}}


def _eligible(entry: dict, snapshot_id: str, registry_hash: str, allowed: set[str], bank: dict) -> bool:
    return bool(_source(entry) in {"document", "customer"} and not entry.get("rejected") and not entry.get("error")
                and entry.get("answered") and entry.get("answer") and entry.get("fact_ids")
                and not entry.get("clarifying_question") and not entry.get("offer_callback")
                and set(entry["fact_ids"]) <= allowed
                and entry.get("registry_hash", bank.get("registry_hash")) == registry_hash
                and entry.get("snapshot_id", bank.get("snapshot_id", "")) == snapshot_id)


def _visible_to_visit(entry: dict, session_id: str) -> bool:
    from .. import portfolio_auth as auth
    if not auth.enabled():
        return True
    return bool(_source(entry) == "customer" and session_id and entry.get("session_id") == session_id)


def _available_entries(demo_id: str, bank: dict, session_id: str) -> list[dict]:
    from .. import portfolio_auth as auth
    if not auth.enabled():
        return bank.get("entries", [])
    # A draft edit/review is not a publication. Public answers are an exact
    # projection of the pinned bundle; current customer drafts stay visit-bound.
    bundle = store.read_json(demo_id, "bundle.json") or {}
    snapshot_id = bundle.get("knowledge_snapshot_id")
    shared = []
    if snapshot_id:
        try:
            fingerprint = _registry_hash(demo_id, snapshot_id=snapshot_id)
            for entry in bundle.get("faq", []):
                shared.append({**copy.deepcopy(entry), "snapshot_id": snapshot_id,
                               "registry_hash": fingerprint, "reviewed": True})
        except ValueError:
            pass
    return shared + [entry for entry in bank.get("entries", []) if _visible_to_visit(entry, session_id)]


def _save_bank(demo_id: str, bank: dict, *, changed: bool = False) -> None:
    """Caller holds store._lock; count/audio updates do not clear an approval."""
    active = current_entries(bank)
    bank.update(total=len(active), answered=sum(bool(entry.get("answered")) for entry in active),
                partial=any(entry.get("error") for entry in active))
    store.write_json(demo_id, "faq.json", bank)
    if changed:
        demo = store.load(demo_id)
        if demo.get("approvals", {}).get("faq"):
            demo["approvals"]["faq"] = False
            store.save(demo_id, demo)


def current_entries(bank: dict) -> list[dict]:
    """Build only current customer answers; old entries remain for already pinned visits."""
    return [entry for entry in bank.get("entries", []) if not entry.get("rejected") and
            (_source(entry) != "customer" or
             (entry.get("snapshot_id") == bank.get("snapshot_id") and entry.get("registry_hash") == bank.get("registry_hash")))]


def normalize_entry(entry: dict, audience: str, question: str | None = None) -> dict:
    """Apply the register rule to new and cached text; old audio owns old words."""
    entry = dict(entry)
    if entry.get("reviewed") or audience != "everyday" or plain_terms.TECHNICAL_REQUEST.search(entry.get("question", "") if question is None else question):
        return entry
    text = entry.get("answer", "")
    clean, substitutions = plain_terms.substitute(text)
    if substitutions:
        prior = [tuple(pair) for pair in entry.get("plain_language_substitutions", [])]
        entry["plain_language_substitutions"] = prior + [pair for pair in substitutions if tuple(pair) not in prior]
    if clean != text:
        entry["answer"], entry["audio"] = clean, None
        if entry.get("clarifying_question") == text:
            entry["clarifying_question"] = clean
    return entry


def match(demo_id: str, question: str, *, snapshot_id: str | None = None,
          registry_hash: str | None = None, increment: bool = False, expected: dict | None = None,
          session_id: str = "") -> dict | None:
    """Read a compatible answer; count only an actual caller-selected cache hit."""
    with store._lock(demo_id):
        try:
            sid, fingerprint, registry = _context(demo_id, snapshot_id, registry_hash)
        except ValueError:
            return None
        bank = store.read_json(demo_id, "faq.json") or {}
        entries = _available_entries(demo_id, bank, session_id)
        if _best([entry for entry in entries if entry.get("rejected")], question):
            return None
        demo = store.load(demo_id)
        allowed = _approved(registry, demo.get("settings", {}).get("competition") == "on")
        entry = _best([entry for entry in entries if _eligible(entry, sid, fingerprint, allowed, bank)], question)
        if entry is None:
            return None
        if expected is not None and any(entry.get(key) != expected.get(key) for key in ("id", "answer", "fact_ids")):
            return None  # A concurrent human edit must be validated before serving.
        if increment:
            entry["asked_count"] = int(entry.get("asked_count") or 0) + 1
            _save_bank(demo_id, bank)
        return copy.deepcopy(entry)


def cache_answer(demo_id: str, question: str, result: dict, *, snapshot_id: str | None = None,
                 registry_hash: str | None = None, session_id: str = "") -> dict | None:
    """Cache only already-validated, registry-backed answers; never learn a claim."""
    from .. import portfolio_auth as auth
    if auth.enabled() and not session_id:
        return None
    repair = result.get("validation_repair") or {}
    if (not question.strip() or not result.get("answered") or not result.get("answer", "").strip()
            or not result.get("fact_ids") or result.get("clarifying_question") or result.get("cta")
            or result.get("offer_callback") or result.get("provider_failed") or result.get("repair_failed")
            or result.get("reasoning_failed") or result.get("cancelled") or result.get("validation_errors")
            or result.get("tool_results") or repair.get("error") or (repair.get("attempted") and not repair.get("accepted"))
            or re.search(r"\b(?:I|we)\s+(?:won['’]t|will not)\s+guess\b", result.get("answer", ""), re.I)
            or any(fact.get("provenance") in {"live_web", "calculation"} for fact in result.get("facts", []))):
        return None
    with store._lock(demo_id):
        try:
            sid, fingerprint, registry = _context(demo_id, snapshot_id, registry_hash)
        except ValueError:
            return None
        demo = store.load(demo_id)
        allowed = _approved(registry, demo.get("settings", {}).get("competition") == "on")
        ids = list(dict.fromkeys(result["fact_ids"]))
        if set(ids) - allowed:
            return None
        valid, ungrounded = author.ungrounded(result["answer"], ids, allowed)
        if not valid or ungrounded:
            return None
        entry = normalize_entry({"question": question.strip(), "answer": result["answer"].strip(), "fact_ids": ids,
                                 "answered": True, "audio": None, "visual": result.get("visual"),
                                 "offer_callback": False, "clarifying_question": "",
                                 "plain_language_substitutions": result.get("plain_language_substitutions", [])},
                                demo.get("settings", {}).get("audience", "everyday"))
        if (demo.get("settings", {}).get("audience", "everyday") == "everyday"
                and not plain_terms.TECHNICAL_REQUEST.search(question) and plain_terms.find_jargon(entry["answer"])):
            return None
        bank = store.read_json(demo_id, "faq.json") or {"entries": []}
        bank.setdefault("snapshot_id", sid)
        bank.setdefault("registry_hash", fingerprint)
        entries = bank.setdefault("entries", [])
        visible = _available_entries(demo_id, bank, session_id)
        if _best([old for old in visible if old.get("rejected")], question):
            return None
        old = _best([old for old in visible if _eligible(old, sid, fingerprint, allowed, bank)], question)
        changed = old is None
        if old:
            changed = not old.get("reviewed") and any(old.get(key) != entry.get(key) for key in ("answer", "fact_ids"))
            if changed:
                old.update(entry)
            old["asked_count"] = int(old.get("asked_count") or 0) + 1
            entry = old
        else:
            identity = [question.strip().casefold(), sid, fingerprint]
            if auth.enabled():
                identity.append(session_id)
            key = json.dumps(identity, ensure_ascii=False)
            entry.update(id="C" + hashlib.sha256(key.encode()).hexdigest()[:16], source="customer", origin="runtime",
                         asked_count=1, snapshot_id=sid, registry_hash=fingerprint, reviewed=False, session_id=session_id)
            entries.append(entry)
        _save_bank(demo_id, bank, changed=changed)
        return copy.deepcopy(entry)


def update_audio(demo_id: str, entry_id: str, answer: str, audio: str | None) -> bool:
    """Attach a completed exact-text clip without replacing another writer's bank."""
    with store._lock(demo_id):
        bank = store.read_json(demo_id, "faq.json") or {}
        entry = next((row for row in bank.get("entries", []) if row.get("id") == entry_id), None)
        if not entry or entry.get("rejected") or entry.get("answer") != answer:
            return False
        entry["audio"] = audio
        _save_bank(demo_id, bank)
        return True


def review_entry(demo_id: str, entry_id: str, *, action: str, answer: str | None = None,
                 fact_ids: list[str] | None = None, visual: dict | None = None,
                 slide_id: str | None = None, snapshot_id: str | None = None) -> dict:
    """Apply a checked review under the same lock used by runtime cache writes."""
    if action not in {"approve", "edit", "reject"}:
        raise ValueError("FAQ action must be approve, edit or reject")
    with store._lock(demo_id):
        bank = store.read_json(demo_id, "faq.json") or {}
        found = [entry for entry in bank.get("entries", []) if entry.get("id") == entry_id]
        if not found:
            raise KeyError("FAQ question not found")
        if len(found) != 1:
            raise ValueError("FAQ question id is ambiguous")
        entry = found[0]
        before = copy.deepcopy(entry)
        if action == "reject":
            entry.update(rejected=True, reviewed=True, audio=None)
        else:
            if entry.get("rejected"):
                raise ValueError("Rejected FAQ entries remain rejected")
            sid = snapshot_id if snapshot_id is not None else entry.get("snapshot_id", bank.get("snapshot_id", ""))
            fingerprint = None if snapshot_id is not None else entry.get("registry_hash", bank.get("registry_hash"))
            sid, fingerprint, registry = _context(demo_id, sid, fingerprint)
            demo = store.load(demo_id)
            allowed = _approved(registry, demo.get("settings", {}).get("competition") == "on")
            text = answer.strip() if isinstance(answer, str) else entry.get("answer", "")
            ids = fact_ids if fact_ids is not None else entry.get("fact_ids", [])
            if not isinstance(ids, list) or any(not isinstance(fid, str) for fid in ids) or len(ids) != len(set(ids)):
                raise ValueError("fact_ids must contain distinct approved fact ids")
            valid, ungrounded = author.ungrounded(text, ids, allowed)
            if not text or not 1 <= len(text) <= 2000 or set(ids) - allowed or not valid or ungrounded:
                raise ValueError("A reviewed answer needs approved supporting facts")
            if action == "edit":
                entry.update(answer=text, fact_ids=valid, audio=None, answered=True, visual=visual, slide_id=slide_id,
                             offer_callback=False, clarifying_question="", plain_language_substitutions=[],
                             snapshot_id=sid, registry_hash=fingerprint)
                entry.pop("error", None)
            entry["reviewed"] = True
        content = lambda row: {key: value for key, value in row.items() if key not in {"audio", "asked_count"}}
        _save_bank(demo_id, bank, changed=content(entry) != content(before))
        return copy.deepcopy(entry)


def record_unknown(demo_id: str, question: str, *, session_id: str = "") -> dict | None:
    """Count a customer evidence gap; this never inserts or edits a fact."""
    question = question.strip()
    if not question:
        return None
    with store._lock(demo_id):
        und = store.read_json(demo_id, "understanding.json") or {}
        if not und:
            return None
        unknowns = und.setdefault("unknowns", [])
        unknown = _best(unknowns, question)
        changed = unknown is None or unknown.get("source") != "customer"
        if unknown is None:
            suffixes = [int(match[1]) for row in unknowns if (match := re.fullmatch(r"U(\d+)", str(row.get("id", ""))))]
            category, document = qa.classify(question)
            unknown = {"id": f"U{max(suffixes, default=0) + 1:02d}", "question": question,
                       "why_customers_ask": "asked during a demo", "status": "open", "origin": "runtime",
                       "category": category, "suggested_document": document}
            unknowns.append(unknown)
        unknown.update(source="customer", asked_count=int(unknown.get("asked_count") or 0) + 1, session_id=session_id)
        store.write_json(demo_id, "understanding.json", und)
        if changed:
            demo = store.load(demo_id)
            if demo.get("approvals", {}).get("faq"):
                demo["approvals"]["faq"] = False
                store.save(demo_id, demo)
        return copy.deepcopy(unknown)


def clear_unknown(demo_id: str, question: str) -> None:
    """Resolve a now-answerable customer gap while preserving its observed count."""
    with store._lock(demo_id):
        und = store.read_json(demo_id, "understanding.json") or {}
        current = und.get("unknowns", [])
        changed = False
        kept = []
        for unknown in current:
            if unknown.get("origin") == "runtime" and similarity(question, unknown.get("question", "")):
                changed = True
                if unknown.get("source") == "customer":
                    unknown["status"] = "resolved"
                    kept.append(unknown)
            else:
                kept.append(unknown)
        if changed:
            und["unknowns"] = kept
            store.write_json(demo_id, "understanding.json", und)


def run(demo_id: str, emit, force: bool = False) -> dict:
    """Answer uploaded FAQ questions only, merging around concurrent customer writes."""
    from .. import knowledge
    demo = store.load(demo_id)
    docs = doc_questions(demo_id)
    registry_hash = _registry_hash(demo_id)
    # The same unchanged registry will receive this identity when published.
    snapshot_id = knowledge.snapshot(demo_id)["id"] if store.read_json(demo_id, "understanding.json") else ""
    emit(f"FAQ bank: {len(docs)} question(s) from your FAQ document…")
    with store._lock(demo_id):
        previous = store.read_json(demo_id, "faq.json") or {}
        baseline = copy.deepcopy(previous.get("entries", []))
    entries = []
    audience = demo.get("settings", {}).get("audience", "everyday")
    tombstones = [entry for entry in baseline if entry.get("rejected")]
    reusable = {entry.get("question"): entry for entry in baseline
                if entry.get("registry_hash", previous.get("registry_hash")) == registry_hash
                and entry.get("snapshot_id", previous.get("snapshot_id", snapshot_id)) == snapshot_id}
    used_ids = {entry.get("id") for entry in baseline}
    def next_id():
        number = 1
        while f"Q{number:02d}" in used_ids:
            number += 1
        value = f"Q{number:02d}"
        used_ids.add(value)
        return value
    for index, question in enumerate(docs, 1):
        if _best(tombstones, question):
            continue
        old = reusable.get(question)
        if old and not old.get("error") and (not force or old.get("reviewed")):
            entry = copy.deepcopy(old)
        else:
            emit(f"FAQ {index}/{len(docs)}: “{question[:70]}”")
            try:
                result = qa.answer(demo_id, question, [], None, voice_it=False, learn=False)
                if result.get("provider_failed"):
                    raise RuntimeError("providers down at build — run the FAQ stage again")
                entry = {"id": old.get("id") if old else next_id(), "question": question,
                         **{key: result.get(key) for key in ("answer", "fact_ids", "answered", "visual", "offer_callback", "clarifying_question")},
                         "audio": None, "plain_language_substitutions": result.get("plain_language_substitutions", [])}
            except Exception as exc:
                entry = {"id": old.get("id") if old else next_id(), "question": question, "answer": "", "fact_ids": [],
                         "answered": False, "visual": None, "offer_callback": True, "clarifying_question": "", "audio": None,
                         "error": str(exc)[:160]}
        entry.update(source="document", origin="document", registry_hash=registry_hash, snapshot_id=snapshot_id)
        entry.setdefault("asked_count", 0)
        entry.setdefault("reviewed", False)
        entries.append(normalize_entry(entry, audience))
    slides = (store.read_json(demo_id, "deck.json") or {}).get("slides", [])
    for entry in entries:
        entry["slide_id"] = deck.slide_for(slides, entry.get("fact_ids"), entry["question"])[0] if slides else None
    with store._lock(demo_id):
        bank = store.read_json(demo_id, "faq.json") or {}
        latest = bank.get("entries", [])
        # Runtime counts, rejection and exact human edits win over the snapshot
        # read before slow QA calls; customer entries never come from generation.
        latest_by_id = {entry.get("id"): entry for entry in latest}
        baseline_by_id = {entry.get("id"): entry for entry in baseline}
        merged = []
        for entry in entries:
            newer = latest_by_id.get(entry["id"])
            if newer and newer != baseline_by_id.get(entry["id"]):
                if newer.get("reviewed") or newer.get("rejected"):
                    entry = newer
                else:
                    entry["asked_count"] = newer.get("asked_count", entry.get("asked_count", 0))
            if not _best([row for row in latest if row.get("rejected")], entry["question"]):
                merged.append(entry)
        ids = {entry["id"] for entry in merged}
        merged += [entry for entry in latest if entry.get("id") not in ids and
                   (entry.get("rejected") or _source(entry) == "customer")]
        changed = [{k: v for k, v in entry.items() if k not in {"asked_count", "audio"}} for entry in merged] != [
            {k: v for k, v in entry.items() if k not in {"asked_count", "audio"}} for entry in latest]
        bank.update(entries=merged, registry_hash=registry_hash, snapshot_id=snapshot_id, question_policy=QUESTION_POLICY)
        _save_bank(demo_id, bank, changed=changed)
        out = copy.deepcopy(bank)
    store.log(demo_id, "faq", {"answered": out["answered"], "total": out["total"], "from_document": len(docs), "questions": [e["question"] for e in entries]})
    emit(f"FAQ bank ready: {out['answered']}/{out['total']} answered from the sources.")
    return out
