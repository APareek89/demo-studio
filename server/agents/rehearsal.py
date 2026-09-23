"""Stage 5 — Rehearsal.  Ask the demo what real buyers will ask; measure what it can't answer."""
from __future__ import annotations

import json
import hashlib

from .. import schemas, store
from ..llm import claude
from . import qa
from .principles import PRINCIPLES, SCORECARD

# Describe the mix of likely buyer questions, including gaps in the supplied evidence.
# generate_questions sends this prompt through llm/claude.py:structured for FAQ or rehearsal preparation.
QGEN_SYSTEM = """You generate the questions a real prospective buyer asks during a product demo. Mix: specs and
numbers, price and offers, ownership and support, setup/usage in their situation, comparisons, risks and edge cases,
and 2-3 questions the given sources clearly cannot answer. Short, natural, first person. No duplicates."""


# Hash semantic script, evidence, Plan, FAQ, settings and scoring prompts for review reuse.
# Returns a fingerprint using orchestrator.py:semantic; audio files and timestamps do not force a new review.
def input_hash(demo_id: str) -> str:
    """Audio, timestamps and version counters cannot invalidate a semantic review."""
    from ..orchestrator import semantic
    demo = store.load(demo_id)
    settings = demo.get("settings", {})
    und = store.read_json(demo_id, "understanding.json") or {}
    script = store.read_json(demo_id, "script.json") or {}
    bank = store.read_json(demo_id, "faq.json") or {}
    # Select semantic speech fields while dropping audio paths and incidental timing.
    # orchestrator.py:semantic handles the other review inputs so recordings alone do not invalidate scoring.
    def spoken(line):
        return {key: line.get(key) for key in ("id", "text", "fact_ids", "step", "delivery", "unverified") if key in line}
    script_input = {"intake_q1": script.get("intake_q1"), "closing": [spoken(line) for line in script.get("closing", [])],
                    "runtime_overview": spoken(script.get("runtime_overview") or {}),
                    "segments": [{**{key: segment.get(key) for key in ("id", "title", "role", "topic", "outcome", "usp_ids", "checkin")},
                                  "lines": [spoken(line) for line in segment.get("lines", [])],
                                  "deeper": [spoken(line) for line in segment.get("deeper", [])]} for segment in script.get("segments", [])]}
    # Combine semantic evidence, Plan, script and FAQ with settings and scoring prompts.
    # The resulting hash controls run reuse; qa.py:QA_SYSTEM changes also require a fresh review.
    inputs = {"understanding": semantic({key: und.get(key) for key in ("product", "brand", "facts", "competitors", "unknowns")}),
              "plan": semantic(store.read_json(demo_id, "plan.json") or {}), "script": script_input,
              "faq": semantic({"entries": bank.get("entries", []), "partial": bank.get("partial", False)})}
    inputs["settings"] = {key: settings.get(key) for key in ("language", "audience", "competition", "rehearsal_questions")}
    inputs["prompts"] = {"questions": QGEN_SYSTEM, "score": SCORE_SYSTEM, "criteria": SCORECARD,
                         "qa": qa.QA_SYSTEM, "schema": schemas.Scorecard.model_json_schema()}
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


# Ask for likely buyer questions using the product, persona, concerns and available fact names.
# Returns a bounded list through llm/claude.py:structured; faq.py:run also uses this helper before the Rehearsal stage.
def generate_questions(demo_id: str, n: int = 12, bias: str | None = None) -> list[str]:
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    content = "PRODUCT: " + json.dumps(und.get("product", {})) + "\nCUSTOMER: " + str(plan.get("customer_persona", "")) + "\nCONCERNS: " + json.dumps(plan.get("concerns", [])) + "\nFACT CLAIMS AVAILABLE: " + str([f["claim"] for f in und.get("facts", [])][:80]) + "\nGenerate " + str(n) + " questions."
    try:
        return claude.structured(QGEN_SYSTEM, content, schemas.RehearsalQuestions, max_tokens=4000).questions[:n]
    except Exception as e:
        raise RuntimeError("Question generation failed: " + claude.describe_error(e)) from e


# Review the FAQ bank, or generate and answer questions, then save coverage and a script scorecard.
# Writes rehearsal.json via qa.py:answer and score_script; this is build review, not an actual live customer test.
def run(demo_id: str, emit) -> dict:
    fingerprint = input_hash(demo_id)
    # Reuse a completed review only when its semantic fingerprint still matches.
    # store.py:read_json supplies the old scorecard; no model question or scoring request is needed on a match.
    previous = store.read_json(demo_id, "rehearsal.json") or {}
    if previous.get("input_hash") == fingerprint and (previous.get("scorecard") is not None or previous.get("skipped")):
        emit("Rehearsal and scorecard reused: script, evidence, FAQ and review prompts are unchanged.")
        return previous
    demo = store.load(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    n = int(demo.get("settings", {}).get("rehearsal_questions", 12) or 12)
    if n <= 0:
        emit("Rehearsal skipped (0 questions configured).")
        out = {"questions": [], "coverage": None, "gaps": [], "skipped": True, "input_hash": fingerprint}
        store.write_json(demo_id, "rehearsal.json", out)
        return out
    # Prefer already-built FAQ answers as the rehearsal question set and compute their coverage.
    # faq.py:run owns those answers; this branch scores the script without replaying a customer session.
    bank = store.read_json(demo_id, "faq.json") or {}
    if bank.get("entries"):
        results = [{"question": e["question"], "answered": e["answered"], "fact_ids": e["fact_ids"], "answer": e["answer"], "escalate": ""} for e in bank["entries"]]
        answered = sum(1 for r in results if r["answered"])
        gaps = [r["question"] for r in results if not r["answered"]]
        out = {"questions": results, "coverage": round(answered / max(1, len(results)), 2), "gaps": gaps, "skipped": False, "from_bank": True, "input_hash": fingerprint}
        emit(f"Rehearsal uses the FAQ bank: {answered}/{len(results)} answered from the sources — scoring the script…")
        out["scorecard"] = score_script(demo_id, emit)
        store.write_json(demo_id, "rehearsal.json", out)
        store.log(demo_id, "rehearsal", {"coverage": out["coverage"], "gaps": gaps, "from_bank": True})
        return out
    # When no FAQ bank exists, generate questions and answer them one at a time.
    # qa.py:answer supplies each result; failures are kept as unanswered rows rather than hidden.
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
    # Count answered questions and gaps, attach the script scorecard, then save the review.
    # store.py:write_json writes rehearsal.json; bundle.py:build remains the following graph stage.
    answered = sum(1 for r in results if r["answered"])
    gaps = [r["question"] for r in results if not r["answered"]]
    out = {"questions": results, "coverage": round(answered / max(1, len(results)), 2), "gaps": gaps, "skipped": False, "input_hash": fingerprint}
    out["scorecard"] = score_script(demo_id, emit)
    store.write_json(demo_id, "rehearsal.json", out)
    store.log(demo_id, "rehearsal", {"coverage": out["coverage"], "gaps": gaps})
    emit(f"Rehearsal: answered {answered}/{len(results)} from the sources; {len(gaps)} gap{'s' if len(gaps) != 1 else ''} added to the list.")
    return out


# Ask a model coach to score what the saved script enables against the demo playbook.
# score_script uses principles.py:SCORECARD; this prompt score is not an independent live performance measurement.
SCORE_SYSTEM = """JUDGING NOTE: the script deliberately has ONE short "more features" block (3–5 one-line items, ≤110 words) after the proof blocks — that is the product's demo shape, not a feature inventory. Do not penalise "Minimal proof" for its existence; penalise only proof blocks beyond one primary + two supporting, or feature items that carry numbers/claims.
You are a demanding sales-demo coach. Score the SCRIPT below on the 10 criteria (0 absent, 1 partial,
2 clear and evidenced), quoting the script in your notes. Be strict: a first demo should score ≥16/20 with no zero on
customer signal, outcome first, truth split, or advance. The runtime personalises the route per buyer (customer signal and
concrete language are partly delivered at runtime) — score what the SCRIPT itself enables. Then name the 2-3 weakest
criteria with one concrete rewrite suggestion each.

""" + PRINCIPLES


# Give the Plan and spoken script to a model coach using the configured scoring criteria.
# Returns a scorecard or None through llm/claude.py:structured; the score is not measured runtime accuracy or latency.
def score_script(demo_id: str, emit) -> dict | None:
    script = store.read_json(demo_id, "script.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    if not script.get("segments"):
        return None
    emit("Scoring the demo against the playbook…")
    crit = "\n".join(f"{i+1}. {c}: {t}" for i, (c, t) in enumerate(SCORECARD))
    # Send selected Plan context and the saved spoken script to the scoring model.
    # llm/claude.py:structured returns criteria scores; normalize their total and leave None if scoring fails.
    content = f"CRITERIA:\n{crit}\n\nPLAN: {json.dumps({k: plan.get(k) for k in ('decision_frame','takeaway','primary_outcome','supporting_outcomes','advance','do_not_recommend_if','state_questions')})}\n\nSCRIPT: {json.dumps({'segments': script['segments'], 'closing': script['closing'], 'intake_q1': script.get('intake_q1')})[:50000]}"
    try:
        sc = claude.structured(SCORE_SYSTEM, content, schemas.Scorecard, max_tokens=3000).model_dump()
        sc["total"] = sum(max(0, min(2, s["score"])) for s in sc["scores"])
        emit(f"Demo scorecard: {sc['total']}/20 — weakest: {'; '.join(w[:60] for w in sc['weakest'][:2])}")
        return sc
    except Exception as e:
        emit(f"Scorecard skipped: {str(e)[:100]}")
        return None
