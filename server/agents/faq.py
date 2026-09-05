"""FAQ bank — the questions customers actually ask, answered at build time from the registry and voiced in the
persona's voice, so a known question is answered instantly at runtime with no model call and no voice change.

Questions come from two places: any uploaded FAQ document (role 'faq', or a document whose name contains 'faq';
every line ending in '?' is taken), and generated likely questions (rehearsal.generate_questions) to fill up to
settings.faq_questions (default 20). Every answer goes through qa.answer, so "no citation, no claim" holds; a question
the sources cannot answer is kept with its decline-and-callback answer, which is also instant at runtime.

Runtime: match(demo_id, question) returns the bank entry when the customer's wording clearly means the same question."""
from __future__ import annotations

import hashlib
import json
import re

from .. import store
from . import qa, rehearsal

STOP = set("the a an and or of to in on at for with by from as is are was were be been it its this that these those you your we our they their i me my "
           "do does did can will would could should may might have has had what which who how why when where much many any some there here about please tell "
           "give get got know want need like also just only very really if then than so".split())


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


def _tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9][a-z0-9\-\.]*", (text or "").lower()):
        w = w.strip(".")
        if w in STOP or len(w) < 2:
            continue
        out.add(w[:-1] if w.endswith("s") and len(w) > 4 and not w.endswith("ss") else w)
    return out


def doc_questions(demo_id: str) -> list[str]:
    """Lines ending in '?' from uploaded FAQ documents (text/markdown; PDFs via the same extractor the registry uses)."""
    demo = store.load(demo_id)
    qs: list[str] = []
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
    seen, out = set(), []
    for q in qs:
        k = q.lower()
        if k not in seen:
            seen.add(k)
            out.append(q)
    return out


def _registry_hash(demo_id: str) -> str:
    und = store.read_json(demo_id, "understanding.json") or {}
    rows = [(f.get("id"), f.get("claim"), f.get("value"), f.get("conditions"), f.get("approved", True)) for f in und.get("facts", [])]
    rows += [(f.get("id"), f.get("claim"), f.get("value"), f.get("conditions"), True) for c in und.get("competitors", []) for f in c.get("facts", [])]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:20]


def run(demo_id: str, emit, force: bool = False) -> dict:
    demo = store.load(demo_id)
    n = int(demo.get("settings", {}).get("faq_questions", 20) or 20)
    docs = doc_questions(demo_id)
    emit(f"FAQ bank: {len(docs)} question(s) from your FAQ document" + (f", generating {max(0, n - len(docs))} more" if n > len(docs) else "") + "…")
    generated = rehearsal.generate_questions(demo_id, max(0, n - len(docs)), bias="answerable") if n > len(docs) else []
    questions = [(q, "document") for q in docs] + [(q, "generated") for q in generated]
    registry_hash = _registry_hash(demo_id)
    previous = store.read_json(demo_id, "faq.json") or {}
    reusable = {e.get("question"): e for e in previous.get("entries", [])} if not force and previous.get("registry_hash") == registry_hash else {}
    entries = []
    for i, (q, origin) in enumerate(questions, 1):
        emit(f"FAQ {i}/{len(questions)}: “{q[:70]}”")
        if q in reusable and not reusable[q].get("error"):
            entries.append({**reusable[q], "id": f"Q{i:02d}", "origin": origin})
            continue
        try:
            r = qa.answer(demo_id, q, [], None, voice_it=False)
            entries.append({"id": f"Q{i:02d}", "question": q, "origin": origin, "answer": r["answer"], "fact_ids": r["fact_ids"], "answered": r["answered"],
                            "visual": r.get("visual"), "offer_callback": r.get("offer_callback", False), "clarifying_question": r.get("clarifying_question", ""), "audio": None})
        except Exception as e:
            entries.append({"id": f"Q{i:02d}", "question": q, "origin": origin, "answer": "", "fact_ids": [], "answered": False, "visual": None, "offer_callback": True, "clarifying_question": "", "audio": None, "error": str(e)[:160]})
        store.write_json(demo_id, "faq.json", {"entries": entries, "answered": sum(1 for e in entries if e["answered"]), "total": len(questions), "registry_hash": registry_hash, "partial": len(entries) < len(questions)})
    out = {"entries": entries, "answered": sum(1 for e in entries if e["answered"]), "total": len(entries), "registry_hash": registry_hash, "partial": False}
    store.write_json(demo_id, "faq.json", out)
    store.log(demo_id, "faq", {"answered": out["answered"], "total": out["total"], "from_document": len(docs), "questions": [e["question"] for e in entries]})
    emit(f"FAQ bank ready: {out['answered']}/{out['total']} answered from the sources; the rest decline and offer a callback — all instant at runtime.")
    return out


def match(demo_id: str, question: str) -> dict | None:
    """The bank entry whose question clearly means the same as the customer's, else None."""
    bank = store.read_json(demo_id, "faq.json") or {}
    qt = _tokens(question)
    if not qt:
        return None
    best, best_score = None, 0.0
    for e in bank.get("entries", []):
        et = _tokens(e["question"])
        if not et:
            continue
        inter = len(qt & et)
        if not inter:
            continue
        jaccard = inter / len(qt | et)
        cover_q = inter / len(qt)   # how much of what the customer said is in the bank question
        cover_e = inter / len(et)   # how much of the bank question the customer covered
        ok = jaccard >= 0.6 or (cover_q >= 0.75 and cover_e >= 0.2)
        score = jaccard + cover_q
        if ok and score > best_score:
            best, best_score = e, score
    return best
