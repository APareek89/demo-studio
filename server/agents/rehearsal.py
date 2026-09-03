"""Stage 5 — Rehearsal.  Ask the demo what real buyers will ask; measure what it can't answer."""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from . import qa

QGEN_SYSTEM = """You generate the questions a real prospective buyer asks during a product demo. Mix: specs and
numbers, price and offers, ownership and support, setup/usage in their situation, comparisons, risks and edge cases,
and 2-3 questions the given sources clearly cannot answer. Short, natural, first person. No duplicates."""


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
    store.write_json(demo_id, "rehearsal.json", out)
    store.log(demo_id, "rehearsal", {"coverage": out["coverage"], "gaps": gaps})
    emit(f"Rehearsal: answered {answered}/{len(results)} from the sources; {len(gaps)} gap{'s' if len(gaps) != 1 else ''} added to the list.")
    return out
