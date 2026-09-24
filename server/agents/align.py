"""The Align agent — reads the four cards and the user's message; returns structured actions.

The agent classifies and explains; the orchestrator executes. Keeping those apart is what
makes every run auditable and every stage re-runnable.
"""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from .bundle import media_url
from .qa import classify
from . import voice as voice_agent
from . import deck as deck_agent
from . import coach, faq, narration
from .visuals import part_boxes as visual_parts

CARD_ORDER = ["visuals", "facts", "script", "faq", "persona", "ctas"]
CARD_TITLES = {"visuals": "Visuals", "facts": "Facts", "script": "Script", "faq": "Asked and answered", "persona": "Persona & voice", "ctas": "Calls to action"}

ALIGN_SYSTEM = """You are the alignment agent inside Demo Studio. A brand user is reviewing what the pipeline produced
for their product demo, in six cards: Visuals (video shots + images the demo will use, and visual gaps),
Facts (the fact registry with citations, and open unknowns), Pitch (decision frame, takeaway, primary outcome, USPs,
standard opening + proof blocks, advance, when-not-to-recommend — edits here are revise('plan', …)), Persona & voice
(who the guide is, how it sounds, a sample audio), Calls to action (buttons shown in the demo). They approve each card, or say what is wrong.

You return ONE reply for the user and a list of ACTIONS for the orchestrator. Actions:
- approve(card) — ONLY when the user clearly approves that card ("looks good", "approve", "yes go ahead"). Never approve on your own.
- revise(stage, instruction) — stage is 'understand' (re-read sources: wrong/missing facts, brand tone, visual tagging),
  'coach' (story order, coverage, winning points and evidence gaps), 'plan' (evidence mapping, pictures, segments, persona,
  intake, CTA proposals) or 'author' (script wording). Write the instruction as a precise
  brief for that stage — include the user's exact words and what must change. Prefer edit_fact for a single wrong value.
- edit_fact(fact_id, fact_value[, fact_claim, fact_conditions, fact_truth, fact_source]) / remove_fact(fact_id) — direct corrections or rejection in either product F facts or competitor C facts. Optional fields change only when the user explicitly provides a correction. fact_source is the citation {{ref, locator, quote}}; ref must name an existing source. Keep competitor facts under their own competitor source. Never turn manufacturer-stated figures into certified test results without explicit evidence.
- set_ctas(ctas) — the FULL new list when the user adds/changes/removes buttons (ids: short slugs; kinds: book|reserve|buy|contact|trial|link|custom).
- set_voice(voice_name, persona_description, tone) — voice_name one of Sulafat, Aoede, Leda, Despina, Kore, Achernar, Zephyr; fill only what changes.
- request_upload(upload_kind, reason) — when the right fix is more material (a missing image, the spec sheet).
- resolve_unknown(unknown_id) — when the user says an unknown is irrelevant or now answered (pair with edit_fact/revise as needed).
- build() — only when all six cards are approved AND the user asks to build/proceed/finish.
- The SCRIPT card is the full demo script, batch by batch (≤ 20 s each) mapped to seconds with the picture on screen per line; revise stage 'author' to change the words. Each batch is one SLIDE (deck.json: picture, ≤ 6-word title, ≤ 3 cited callouts); revise stage 'deck' to change pictures, titles or callouts without rewriting the script. The Asked and answered card contains uploaded FAQ questions, answers to real customer questions, and unanswered customer questions with ask counts. Uploaded questions are answered at build; no guessed questions are generated. Rejected answers are never served. Empty cards are approved automatically. Rehearsal is available only on demand in Rehearse.
- answer — a question that changes nothing.
Rules: never invent product facts yourself — route corrections through edit_fact/revise. If the user attached files,
the orchestrator has ALREADY added them as sources; if they are meant to fix facts or visuals, emit revise('understand', …)
explaining what to look for in the new files. Keep the reply to 1-4 plain sentences: what you did / will do, or what you need.
Current card under review: {current}. Approvals: {approvals}. Stage status: {stages}.

CARDS:
{cards}
"""


def _vis_url(demo_id: str, und: dict, src_by_id: dict, ref: str | None) -> str | None:
    if not ref:
        return None
    for i in und.get("images", []):
        if i["id"] == ref:
            src = src_by_id.get(i["source_id"], {})
            return media_url(demo_id, src.get("play") or src.get("path"))
    for sh in und.get("shots", []):
        if sh["id"] == ref:
            src = src_by_id.get(sh["source_id"], {})
            return media_url(demo_id, src.get("play") or src.get("path")) + f"#t={sh.get('start', 0):.1f}"
    return None


def _last_visuals(demo_id: str) -> dict | None:
    try:
        files = sorted(store.path(demo_id, "logs").glob("*-visuals.json"))
        return json.loads(files[-1].read_text()) if files else None
    except Exception:
        return None


def cards(demo_id: str) -> dict:
    demo = store.load(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    playbook = store.read_json(demo_id, "playbook.json") or {}
    if playbook:
        playbook = coach.apply_overrides(playbook, demo_id)
    script = store.read_json(demo_id, "script.json") or {}
    visual_audit = store.read_json(demo_id, "visual-audit.json") or {}
    deck = store.read_json(demo_id, "deck.json") or {}
    reh = store.read_json(demo_id, "rehearsal.json") or {}
    bank = store.read_json(demo_id, "faq.json") or {}
    active_answers = faq.current_entries(bank)
    customer_unknowns = [unknown for unknown in und.get("unknowns", []) if unknown.get("source") == "customer" and unknown.get("status", "open") == "open"]
    src_by_id = {s["id"]: s for s in demo["sources"]}
    audit_images = {x.get("visual"): x for x in visual_audit.get("images", [])}
    audit_lines = {x.get("line_id"): x for x in visual_audit.get("lines", [])}
    shots = [{**s, "url": media_url(demo_id, src_by_id.get(s["source_id"], {}).get("path"))} for s in und.get("shots", [])]
    images = [{**i, "url": media_url(demo_id, src_by_id.get(i["source_id"], {}).get("play") or src_by_id.get(i["source_id"], {}).get("path")), "original_url": media_url(demo_id, src_by_id.get(i["source_id"], {}).get("path")), "enhanced": src_by_id.get(i["source_id"], {}).get("enhanced"), "audit": audit_images.get(i["id"])} for i in und.get("images", [])]
    voice = plan.get("voice", {})
    actual_provider = voice_agent.provider_for(demo)
    allowed_facts = {fact["id"] for fact in und.get("facts", []) if fact.get("approved", True)}
    _, narration_minimum = narration.default_route(script, demo_id=demo_id, allowed_fact_ids=allowed_facts)
    # Publication checks every recorded language. Show the limiting recording
    # here too, so an alternate-language deficit has an actionable review card.
    settings = demo.get("settings", {})
    main_language = settings.get("language", "en-IN")
    recorded_current = bool(script.get("voice_input_hash")) and script["voice_input_hash"] == voice_agent.input_hash(demo_id)
    for language in (settings.get("languages", []) or []) if recorded_current else []:
        if language == main_language:
            continue
        translated = store.read_json(demo_id, f"script.{language}.json")
        if not translated:
            continue
        _, candidate = narration.default_route(translated, demo_id=demo_id, allowed_fact_ids=allowed_facts)
        current_key = (narration_minimum["sufficient"] and narration_minimum["measured"], narration_minimum["seconds"])
        candidate_key = (candidate["sufficient"] and candidate["measured"], candidate["seconds"])
        if candidate_key < current_key:
            narration_minimum = {**candidate, "language": language}
    preparation = plan.get("narration_preparation") or {}
    target = preparation.get("target_words")
    if isinstance(target, int) and not isinstance(target, bool) and target > 0:
        # Include every eligible continuation, not only the first route that
        # reaches the old estimated minimum. Recorded publication stays final.
        draft = narration.preparation_report(script, allowed_fact_ids=allowed_facts)
        narration_minimum["preparation"] = {"target_words": target, "words": draft["words"],
                                              "sufficient": draft["words"] >= target}
    return {
        "product": und.get("product", {"name": demo["name"]}),
        "visuals": {"shots": shots, "images": images, "gaps": plan.get("visual_gaps", []), "video_summaries": und.get("video_summaries", {}),
                    "visual_theme": demo.get("settings", {}).get("visual_theme", "marine"),
                    "audit": {"method": visual_audit.get("method"), "model": visual_audit.get("model"), "line_count": len(visual_audit.get("lines", [])), "image_count": len(visual_audit.get("images", [])), "missing_line_count": sum(1 for x in visual_audit.get("lines", []) if x.get("missing_features"))},
                    "segments": [{"id": s["id"], "title": s["title"], "visual_refs": s["visual_refs"]} for s in plan.get("segments", [])]},
        "facts": {"facts": [{**fact, "applicability": fact.get("scope", {}), "scope": "competitor" if owner is not None else "product",
                              "competitor_name": owner.get("name", "") if owner is not None else "",
                              "competitor_source_id": owner.get("source_id", "") if owner is not None else ""}
                             for fact, owner in store.fact_entries(und)], "unknowns": [({**u, "category": classify(u["question"])[0], "suggested_document": classify(u["question"])[1]} if not u.get("category") or u.get("category") == "other" and not u.get("suggested_document") else u) for u in und.get("unknowns", [])], "sources": demo["sources"],
                  "gaps": reh.get("gaps", []), "script_issues": script.get("issues", []),
                  "coverage": und.get("knowledge", {}).get("coverage", {}), "conflicts": und.get("knowledge", {}).get("conflicts", []),
                  "diff": und.get("knowledge", {}).get("diff", {})},
        "persona": {**voice, "sample_audio": media_url(demo_id, plan.get("voice_sample_audio")), "brand": und.get("brand", {}),
                    "provider": actual_provider, "voice_name": voice_agent.voice_name_for(demo, actual_provider)},
        "ctas": plan.get("ctas", []),
        "script": {k: plan.get(k) for k in ("decision_frame", "takeaway", "primary_outcome", "supporting_outcomes", "usps", "advance", "do_not_recommend_if", "state_questions", "customer_persona")} | {
            "playbook": {"stops": playbook.get("stops", []), "usps": playbook.get("usps", []),
                         "gaps": playbook.get("evidence_gaps", []), "issues": playbook.get("issues", [])},
            "language": demo.get("settings", {}).get("language", "en-IN"), "scorecard": reh.get("scorecard"), "timeline": script.get("timeline"),
            "pitch_minutes": demo.get("settings", {}).get("pitch_minutes", 3), "total_words": plan.get("total_words"),
            "narration_minimum": narration_minimum,
            "written_at": (store.path(demo_id, "script.json").stat().st_mtime if store.path(demo_id, "script.json").exists() else None), "version": demo.get("version", 0),
            "intake": {"q1": script.get("intake_q1", ""), "q2": script.get("intake_q2", "")},
            "runtime_overview": ({**script["runtime_overview"], "visual": (script["runtime_overview"].get("visual") or {}).get("ref")} if script.get("runtime_overview") else None),
            "segments": [{"id": s["id"], "title": s["title"], "role": s.get("role", "proof"), "topic": s.get("topic", ""), "outcome": s.get("outcome", ""), "usp_ids": s.get("usp_ids", []), "start": s.get("start"), "duration": s.get("duration"), "spoken": s.get("spoken"), "word_budget": s.get("word_budget"), "planned_seconds": s.get("planned_seconds"), "measured": bool(s.get("measured")), "narration_measured": any(not l.get("unverified") for l in s.get("lines", [])) and all(l.get("exact") for l in s.get("lines", []) if not l.get("unverified")), "exact": any(l.get("exact") for l in s.get("lines", [])), "checkin_duration": s.get("checkin_duration"), "checkin": s.get("checkin", ""),
                          "lines": [{"id": l["id"], "text": l["text"], "fact_ids": l.get("fact_ids", []), "visual": (l.get("visual") or {}).get("ref"), "visual_url": _vis_url(demo_id, und, src_by_id, (l.get("visual") or {}).get("ref")), "card": l.get("card", "none"), "start": l.get("start"), "duration": l.get("duration"), "exact": bool(l.get("exact")), "unverified": bool(l.get("unverified")), "visual_audit": audit_lines.get(l["id"])} for l in s.get("lines", [])],
                          "deeper": [{"id": l["id"], "text": l["text"], "fact_ids": l.get("fact_ids", [])} for l in s.get("deeper", [])]} for s in script.get("segments", [])],
            "closing": [{"id": l["id"], "text": l["text"], "fact_ids": l.get("fact_ids", []), "visual": (l.get("visual") or {}).get("ref"), "visual_url": _vis_url(demo_id, und, src_by_id, (l.get("visual") or {}).get("ref")), "visual_audit": audit_lines.get(l["id"]), "start": l.get("start"), "duration": l.get("duration")} for l in script.get("closing", [])],
            "issues": script.get("issues", []), "visual_audit": script.get("visual_audit", {}), "visual_changes": visual_audit.get("changes", (_last_visuals(demo_id) or {}).get("changes", []))},
        "deck": {"version": deck.get("version"), "method": deck.get("method"), "hero_image": deck.get("hero_image"),
                 "written_at": (store.path(demo_id, "deck.json").stat().st_mtime if store.path(demo_id, "deck.json").exists() else None),
                 "images": [{"id": i["id"], "url": media_url(demo_id, src_by_id.get(i["source_id"], {}).get("play") or src_by_id.get(i["source_id"], {}).get("path")), "angle": i.get("angle", ""), "description": i.get("description", ""), "parts": visual_parts(i), "full_product": bool(i.get("full_product"))} for i in und.get("images", []) if store.visual_allowed(demo, i["source_id"])],
                 "slides": [{**s, "image_url": _vis_url(demo_id, und, src_by_id, s.get("image_id")),
                             "media": [{**m, "image_url": _vis_url(demo_id, und, src_by_id, m.get("image_id")),
                                        "image_parts": visual_parts(next((image for image in und.get("images", []) if image["id"] == m.get("image_id")), {}))}
                                       for m in s.get("media", [])]} for s in deck_agent.slides_with_script(deck.get("slides", []), script)]},
        "faq": {"entries": [{**e, "audio": media_url(demo_id, e.get("audio"))} for e in bank.get("entries", []) if e in active_answers or e.get("rejected")],
                "answered": sum(bool(e.get("answered")) for e in active_answers), "total": len(active_answers),
                "customer_unknowns": customer_unknowns, "customer_unknown_count": len(customer_unknowns),
                "empty_note": "No questions yet; this card fills from customer questions" if not active_answers and not customer_unknowns else ""},
        "plan": {"customer_persona": plan.get("customer_persona", ""), "concerns": plan.get("concerns", []), "segments": plan.get("segments", []), "intake": plan.get("intake", {}), "notes": plan.get("notes", "")},
        "approvals": demo.get("approvals", {}),
        "stages": demo.get("stages", {}),
        "status": demo.get("status"),
        "version": demo.get("version", 0),
    }


def current_card(demo: dict) -> str | None:
    for c in CARD_ORDER:
        if not demo.get("approvals", {}).get(c):
            return c
    return None


def _cards_text(c: dict) -> str:
    v, f, p = c["visuals"], c["facts"], c["persona"]
    lines = [
        f"PRODUCT: {json.dumps(c['product'])}",
        f"VISUALS: {len(v['shots'])} shots, {len(v['images'])} images. Gaps: {json.dumps(v['gaps'])}",
        f"VISUAL PROOF AUDIT: {json.dumps(v.get('audit', {}))}",
        "  shots: " + "; ".join(f"{s['id']} {s['start']:.0f}-{s['end']:.0f}s q{s['quality']} {s['part']}: {s['description'][:60]}" for s in v["shots"][:40]),
        "  images: " + "; ".join(f"{i['id']} q{i['quality']} {i['angle']}: {i['description'][:60]}" for i in v["images"][:30]),
        f"FACTS ({len(f['facts'])}): " + "; ".join(json.dumps({key: x.get(key) for key in ("id", "scope", "applicability", "competitor_name", "kind", "claim", "value", "conditions", "truth", "approved", "source")}, ensure_ascii=False) for x in f["facts"]),
        f"UNKNOWNS: " + "; ".join(f"{u['id']} {u['question']} ({u['status']})" for u in f["unknowns"][:40]),
        f"SOURCES: " + "; ".join(f"{s['id']} {s['kind']} {s['name']} role={s.get('role')}" for s in f["sources"]),
        f"PERSONA & VOICE: {json.dumps({k: p.get(k) for k in ('persona_name', 'persona_description', 'tone', 'suggested_voice', 'sample_line')})} provider={p.get('provider')} voice={p.get('voice_name')}",
        f"CTAS: {json.dumps(c['ctas'])}",
        f"SALES PLAYBOOK: {json.dumps(c['script'].get('playbook', {}), ensure_ascii=False)}",
        f"SCRIPT: {json.dumps({k: c['script'].get(k) for k in ('decision_frame','takeaway','primary_outcome','supporting_outcomes','advance','do_not_recommend_if')})} usps={[u['name'] for u in (c['script'].get('usps') or [])]} batches={[(s['id'], s['role'], s.get('duration')) for s in c['script']['segments']]} total_seconds={(c['script'].get('timeline') or {}).get('total_seconds')} language={c['script'].get('language')}",
        f"DECK: v{c['deck'].get('version')} · {len(c['deck'].get('slides', []))} slides · callouts by {c['deck'].get('method')} · " + "; ".join(f"{s['id']} {s['kind']} '{s.get('title', '')}' pic {s.get('image_id') or '—'} callouts {len(s.get('callouts', []))}" for s in c['deck'].get('slides', [])[:20]),
        f"ASKED AND ANSWERED: {c['faq'].get('answered')}/{c['faq'].get('total')} answered; questions={[e['question'][:60] for e in c['faq'].get('entries', [])][:20]}; customer unknowns={json.dumps(c['faq'].get('customer_unknowns', []))}",
        f"PLAN: persona={c['plan']['customer_persona']} segments={[s['id'] for s in c['plan']['segments']]} concerns={[x['topic'] for x in c['plan']['concerns']]}",
    ]
    if f.get("gaps"):
        lines.append("REHEARSAL GAPS: " + "; ".join(f["gaps"][:20]))
    if f.get("script_issues"):
        lines.append("SCRIPT ISSUES: " + "; ".join(f["script_issues"][:10]))
    return "\n".join(lines)


def respond(demo_id: str, message: str, attachments: list[dict], history: list[dict], context: str = "align") -> schemas.AlignOut:
    demo = store.load(demo_id)
    c = cards(demo_id)
    cur = current_card(demo) or "none (all approved)"
    sys = ALIGN_SYSTEM.format(current=cur, approvals=json.dumps(demo["approvals"]), stages=json.dumps({k: v["status"] for k, v in demo["stages"].items()}), cards=_cards_text(c))
    if context == "rehearse":
        sys += "\nCONTEXT: the user is in Rehearse, watching the built demo. Feedback about wording, order, pacing, what the guide says → revise('author', …). Wrong facts → edit_fact or revise('understand', …). Missing sections/CTAs → revise('plan', …) or set_ctas. After a revise the orchestrator rebuilds automatically."
    msgs = []
    for h in history[-12:]:
        role = "user" if h["role"] == "user" else "assistant"
        txt = h.get("text", "")
        if msgs and msgs[-1]["role"] == role:
            msgs[-1]["content"] += "\n" + txt
        else:
            msgs.append({"role": role, "content": txt})
    if msgs and msgs[0]["role"] != "user":
        msgs.insert(0, {"role": "user", "content": "(session started)"})
    if msgs and msgs[-1]["role"] == "user":
        msgs.append({"role": "assistant", "content": "(noted)"})
    content = message.strip() or "(no text)"
    if attachments:
        content += "\n\nATTACHED (already added as sources): " + "; ".join(f"{a['id']} {a['kind']} {a['name']}" for a in attachments)
    try:
        return claude.structured(sys, content, schemas.AlignOut, max_tokens=4000, history=msgs)
    except Exception as e:
        raise RuntimeError(claude.describe_error(e)) from e


OPENING_SYSTEM = """You are the alignment agent in Demo Studio, greeting a brand user who has just had their product
sources read. Write 3-5 plain sentences (no markdown, no lists): what you found (counts of shots, images, facts, open
questions), what stands out or is missing (visual gaps, thin registry), and ask them to review the first card —
{card} — and either approve it or tell you what's wrong. Warm, specific, brief."""


def opening_message(demo_id: str) -> str:
    demo = store.load(demo_id)
    c = cards(demo_id)
    cur = current_card(demo) or "visuals"
    try:
        return claude.text(OPENING_SYSTEM.format(card=CARD_TITLES[cur]), _cards_text(c), max_tokens=600)
    except Exception:
        v, f = c["visuals"], c["facts"]
        return (f"I've read your sources: {len(v['shots'])} usable video shots, {len(v['images'])} images, {len(f['facts'])} facts with citations, "
                f"and {len([u for u in f['unknowns'] if u['status']=='open'])} questions the sources don't answer. "
                f"Start with the {CARD_TITLES[cur]} card — approve it, or tell me what's wrong.")


def card_prompt(demo_id: str, card: str) -> str:
    c = cards(demo_id)
    if card == "facts":
        f = c["facts"]
        return f"Next, the Facts card: {len(f['facts'])} facts, each with a source. Check the ones that matter most — prices, warranty, headline specs. Tell me any that are wrong and I'll fix the registry; {len([u for u in f['unknowns'] if u['status']=='open'])} open questions are listed too — upload material for any you want covered."
    if card == "script":
        pt = c["script"]
        tl = pt.get("timeline") or {}
        return f"Next, the Script card — every batch the guide will say, mapped to seconds ({tl.get('total_seconds', 0):.0f} s in {len(pt.get('segments', []))} batches) with the picture on screen for each line. Decision frame: “{pt.get('decision_frame','')}” Takeaway: “{pt.get('takeaway','')}” with {len(pt.get('usps') or [])} USPs, and closes on: “{pt.get('advance','')}”. Approve, or tell me what the pitch should lead with, drop, or promise differently."
    if card == "persona":
        p = c["persona"]
        return f"Next, Persona & voice: the guide is “{p.get('persona_name','')}” — {p.get('tone','')} There's a sample line to listen to. Approve, or tell me how it should sound (warmer, more formal, a different voice)."
    if card == "ctas":
        return "Last card: the calls to action shown during the demo — " + ", ".join(f"“{x['label']}”" for x in c["ctas"]) + ". Confirm these, or tell me the buttons and links you want."
    if card == "faq":
        f = c["faq"]
        return f.get("empty_note") or f"Next, Asked and answered: {f.get('answered', 0)} sourced answers and {f.get('customer_unknown_count', 0)} unanswered customer questions. Review, edit or reject the saved answers, or upload evidence for the unknowns."
    return "All six cards are approved. Say “build the demo” and I'll record the narration, uploaded FAQ answers and filler lines, then open the playground. Rehearsal is available there on demand."
