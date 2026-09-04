"""Stage 5 — Rehearsal.  Ask the demo what real buyers will ask; measure what it can't answer."""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from . import qa
from .principles import PRINCIPLES, SCORECARD

QGEN_SYSTEM = """You generate the questions a real prospective buyer asks during a product demo. Mix: specs and
numbers, price and offers, ownership and support, setup/usage in their situation, comparisons, risks and edge cases,
and 2-3 questions the given sources clearly cannot answer. Short, natural, first person. No duplicates."""


def generate_questions(demo_id: str, n: int = 12) -> list[str]:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    content = "PRODUCT: " + json.dumps(und.get("product", {})) + "\nCUSTOMER: " + str(plan.get("customer_persona", "")) + "\nCONCERNS: " + json.dumps(plan.get("concerns", [])) + "\nFACT CLAIMS AVAILABLE: " + str([f["claim"] for f in und.get("facts", [])][:80]) + "\nGenerate " + str(n) + " questions."
    try:
        return claude.structured(QGEN_SYSTEM, content, schemas.RehearsalQuestions, max_tokens=4000).questions[:n]
    except Exception as e:
        raise RuntimeError("Question generation failed: " + claude.describe_error(e)) from e


def run(demo_id: str, emit) -> dict:
    demo = store.load(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    n = int(demo.get("settings", {}).get("rehearsal_questions", 12) or 12)
    if n <= 0:
        emit("Rehearsal skipped (0 questions configured).")
        out = {"questions": [], "coverage": None, "gaps": [], "skipped": True}
        store.write_json(demo_id, "rehearsal.json", out)
        return out
    bank = store.read_json(demo_id, "faq.json") or {}
    if bank.get("entries"):
        results = [{"question": e["question"], "answered": e["answered"], "fact_ids": e["fact_ids"], "answer": e["answer"], "escalate": ""} for e in bank["entries"]]
        answered = sum(1 for r in results if r["answered"])
        gaps = [r["question"] for r in results if not r["answered"]]
        out = {"questions": results, "coverage": round(answered / max(1, len(results)), 2), "gaps": gaps, "skipped": False, "from_bank": True}
        emit(f"Rehearsal uses the FAQ bank: {answered}/{len(results)} answered from the sources — scoring the script…")
        out["scorecard"] = score_script(demo_id, emit)
        store.write_json(demo_id, "rehearsal.json", out)
        store.log(demo_id, "rehearsal", {"coverage": out["coverage"], "gaps": gaps, "from_bank": True})
        return out
    emit(f"Rehearsing: generating {n} likely customer questions…")
    content = f"PRODUCT: {json.dumps(und.get('product', {}))}\nCUSTOMER: {plan.get('customer_persona','')}\nCONCERNS: {json.dumps(plan.get('concerns', []))}\nFACT CLAIMS AVAILABLE: {[f['claim'] for f in und.get('facts', [])][:80]}\nGenerate {n} questions."
    try:
        qs = claude.structured(QGEN_SYSTEM, content, schemas.RehearsalQuestions, max_tokens=4000).questions[:n]
    except Exception as e:
        raise RuntimeError(f"Rehearsal question generation failed: {claude.describe_error(e)}") from e
    results = []
    for i, q in enumerate(qs, 1):
        emit(f"Rehearsal {i}/{len(qs)}: “{q[:70]}”")
        try:
            r = qa.answer(demo_id, q, [], None)
            results.append({"question": q, "answered": r["answered"], "fact_ids": r["fact_ids"], "answer": r["answer"], "escalate": r["escalate"]})
        except Exception as e:
            results.append({"question": q, "answered": False, "fact_ids": [], "answer": "", "escalate": f"error: {e}"})
    answered = sum(1 for r in results if r["answered"])
    gaps = [r["question"] for r in results if not r["answered"]]
    out = {"questions": results, "coverage": round(answered / max(1, len(results)), 2), "gaps": gaps, "skipped": False}
    out["scorecard"] = score_script(demo_id, emit)
    store.write_json(demo_id, "rehearsal.json", out)
    store.log(demo_id, "rehearsal", {"coverage": out["coverage"], "gaps": gaps})
    emit(f"Rehearsal: answered {answered}/{len(results)} from the sources; {len(gaps)} gap{'s' if len(gaps) != 1 else ''} added to the list.")
    return out


SCORE_SYSTEM = """JUDGING NOTE: the script deliberately has ONE short "more features" block (3–5 one-line items, ≤110 words) after the proof blocks — that is the product's demo shape, not a feature inventory. Do not penalise "Minimal proof" for its existence; penalise only proof blocks beyond one primary + two supporting, or feature items that carry numbers/claims.
You are a demanding sales-demo coach. Score the SCRIPT below on the 10 criteria (0 absent, 1 partial,
2 clear and evidenced), quoting the script in your notes. Be strict: a first demo should score ≥16/20 with no zero on
customer signal, outcome first, truth split, or advance. The runtime personalises the route per buyer (customer signal and
concrete language are partly delivered at runtime) — score what the SCRIPT itself enables. Then name the 2-3 weakest
criteria with one concrete rewrite suggestion each.

""" + PRINCIPLES


def score_script(demo_id: str, emit) -> dict | None:
    script = store.read_json(demo_id, "script.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    if not script.get("segments"):
        return None
    emit("Scoring the demo against the playbook…")
    crit = "\n".join(f"{i+1}. {c}: {t}" for i, (c, t) in enumerate(SCORECARD))
    content = f"CRITERIA:\n{crit}\n\nPLAN: {json.dumps({k: plan.get(k) for k in ('decision_frame','takeaway','primary_outcome','supporting_outcomes','advance','do_not_recommend_if','state_questions')})}\n\nSCRIPT: {json.dumps({'segments': script['segments'], 'closing': script['closing'], 'intake_q1': script.get('intake_q1')})[:50000]}"
    try:
        sc = claude.structured(SCORE_SYSTEM, content, schemas.Scorecard, max_tokens=3000).model_dump()
        sc["total"] = sum(max(0, min(2, s["score"])) for s in sc["scores"])
        emit(f"Demo scorecard: {sc['total']}/20 — weakest: {'; '.join(w[:60] for w in sc['weakest'][:2])}")
        return sc
    except Exception as e:
        emit(f"Scorecard skipped: {str(e)[:100]}")
        return None
