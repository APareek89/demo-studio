"""The Align agent — reads the four cards and the user's message; returns structured actions.

The agent classifies and explains; the orchestrator executes. Keeping those apart is what
makes every run auditable and every stage re-runnable.
"""
from __future__ import annotations

import json

from .. import schemas, store
from ..llm import claude
from .bundle import media_url

CARD_ORDER = ["visuals", "facts", "persona", "ctas"]
CARD_TITLES = {"visuals": "Visuals", "facts": "Facts", "persona": "Persona & voice", "ctas": "Calls to action"}

ALIGN_SYSTEM = """You are the alignment agent inside Demo Studio. A brand user is reviewing what the pipeline produced
for their product demo, in four cards: Visuals (video shots + images the demo will use, and visual gaps),
Facts (the fact registry with citations, and open unknowns), Persona & voice (who the guide is, how it sounds,
a sample audio), Calls to action (buttons shown in the demo). They approve each card, or say what is wrong.

You return ONE reply for the user and a list of ACTIONS for the orchestrator. Actions:
- approve(card) — ONLY when the user clearly approves that card ("looks good", "approve", "yes go ahead"). Never approve on your own.
- revise(stage, instruction) — stage is 'understand' (re-read sources: wrong/missing facts, brand tone, visual tagging),
  'plan' (segments, concerns, gaps, persona, intake, CTA proposals) or 'author' (script wording). Write the instruction as a precise
  brief for that stage — include the user's exact words and what must change. Prefer edit_fact for a single wrong value.
- edit_fact(fact_id, fact_value[, fact_claim]) / remove_fact(fact_id) — direct registry edits when the user states the correct value.
- set_ctas(ctas) — the FULL new list when the user adds/changes/removes buttons (ids: short slugs; kinds: book|reserve|buy|contact|trial|link|custom).
- set_voice(voice_name, persona_description, tone) — voice_name one of Sulafat, Aoede, Leda, Despina, Kore, Achernar, Zephyr; fill only what changes.
- request_upload(upload_kind, reason) — when the right fix is more material (a missing image, the spec sheet).
- resolve_unknown(unknown_id) — when the user says an unknown is irrelevant or now answered (pair with edit_fact/revise as needed).
- build() — only when all four cards are approved AND the user asks to build/proceed/finish.
- answer — a question that changes nothing.
Rules: never invent product facts yourself — route corrections through edit_fact/revise. If the user attached files,
the orchestrator has ALREADY added them as sources; if they are meant to fix facts or visuals, emit revise('understand', …)
explaining what to look for in the new files. Keep the reply to 1-4 plain sentences: what you did / will do, or what you need.
Current card under review: {current}. Approvals: {approvals}. Stage status: {stages}.

CARDS:
{cards}
"""


def cards(demo_id: str) -> dict:
    demo = store.load(demo_id)
    und = store.read_json(demo_id, "understanding.json") or {}
    plan = store.read_json(demo_id, "plan.json") or {}
    script = store.read_json(demo_id, "script.json") or {}
    reh = store.read_json(demo_id, "rehearsal.json") or {}
    src_by_id = {s["id"]: s for s in demo["sources"]}
    shots = [{**s, "url": media_url(demo_id, src_by_id.get(s["source_id"], {}).get("path"))} for s in und.get("shots", [])]
    images = [{**i, "url": media_url(demo_id, src_by_id.get(i["source_id"], {}).get("path"))} for i in und.get("images", [])]
    voice = plan.get("voice", {})
    return {
        "product": und.get("product", {"name": demo["name"]}),
        "visuals": {"shots": shots, "images": images, "gaps": plan.get("visual_gaps", []), "video_summaries": und.get("video_summaries", {}),
                    "segments": [{"id": s["id"], "title": s["title"], "visual_refs": s["visual_refs"]} for s in plan.get("segments", [])]},
        "facts": {"facts": und.get("facts", []), "unknowns": und.get("unknowns", []), "sources": demo["sources"],
                  "gaps": reh.get("gaps", []), "script_issues": script.get("issues", [])},
        "persona": {**voice, "sample_audio": media_url(demo_id, plan.get("voice_sample_audio")), "brand": und.get("brand", {}),
                    "provider": demo.get("settings", {}).get("tts_provider"), "voice_name": demo.get("settings", {}).get("voice_name")},
        "ctas": plan.get("ctas", []),
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
        "  shots: " + "; ".join(f"{s['id']} {s['start']:.0f}-{s['end']:.0f}s q{s['quality']} {s['part']}: {s['description'][:60]}" for s in v["shots"][:40]),
        "  images: " + "; ".join(f"{i['id']} q{i['quality']} {i['angle']}: {i['description'][:60]}" for i in v["images"][:30]),
        f"FACTS ({len(f['facts'])}): " + "; ".join(f"{x['id']} [{x['kind']}] {x['claim']}: {x['value']}" for x in f["facts"][:120]),
        f"UNKNOWNS: " + "; ".join(f"{u['id']} {u['question']} ({u['status']})" for u in f["unknowns"][:40]),
        f"SOURCES: " + "; ".join(f"{s['id']} {s['kind']} {s['name']} role={s.get('role')}" for s in f["sources"]),
        f"PERSONA & VOICE: {json.dumps({k: p.get(k) for k in ('persona_name', 'persona_description', 'tone', 'suggested_voice', 'sample_line')})} provider={p.get('provider')} voice={p.get('voice_name')}",
        f"CTAS: {json.dumps(c['ctas'])}",
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
    if card == "persona":
        p = c["persona"]
        return f"Next, Persona & voice: the guide is “{p.get('persona_name','')}” — {p.get('tone','')} There's a sample line to listen to. Approve, or tell me how it should sound (warmer, more formal, a different voice)."
    if card == "ctas":
        return "Last card: the calls to action shown during the demo — " + ", ".join(f"“{x['label']}”" for x in c["ctas"]) + ". Confirm these, or tell me the buttons and links you want."
    return "All four cards are approved. Say “build the demo” and I'll write the script, record the narration, rehearse it against likely customer questions and open the playground."
