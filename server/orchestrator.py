"""Stage graph + invalidation + background runs + align-action execution.

Stages run in worker threads (the SDKs are synchronous); progress streams through events.py.
"""
from __future__ import annotations

import threading
import time
import traceback

from . import events, media, store, usage, runlog
from .agents import align, author, bundle, faq, plan, rehearsal, understand, voice
from .store import STAGES

DOWNSTREAM = {
    "understand": ["plan", "author", "faq", "voice", "rehearsal", "bundle"],
    "plan": ["author", "voice", "rehearsal", "bundle"],
    "author": ["voice", "rehearsal", "bundle"],
    "faq": ["voice", "rehearsal", "bundle"],
    "voice": ["bundle"],
    "rehearsal": ["bundle"],
    "bundle": [],
}

def is_running(demo_id: str) -> bool:
    from . import graph
    return graph.is_running(demo_id)


def emit_for(demo_id: str, stage: str | None = None):
    def emit(message: str):
        events.publish(demo_id, "progress", stage=stage, message=message)
    return emit


def set_stage(demo_id: str, stage: str, status: str, error: str | None = None, message: str = "") -> None:
    def fn(d):
        prev = d["stages"].get(stage, {})
        started = time.time() if status == "running" else prev.get("started_at")
        d["stages"][stage] = {"status": status, "updated_at": time.time(), "error": error, "message": message, "started_at": started,
                              "seconds": round(time.time() - started, 1) if started and status in ("done", "error") else prev.get("seconds")}
        if status == "running":
            d["running"] = stage
        elif d.get("running") == stage:
            d["running"] = None
    store.update(demo_id, fn)
    events.publish(demo_id, "stage", stage=stage, status=status, error=error)


def invalidate(demo_id: str, stage: str) -> None:
    def fn(d):
        for s in DOWNSTREAM[stage]:
            if d["stages"][s]["status"] == "done":
                d["stages"][s]["status"] = "stale"
    store.update(demo_id, fn)


def _run_stage(demo_id: str, stage: str, instruction: str = "") -> object:
    usage.current_demo.set(demo_id)
    usage.current_stage.set(stage)
    set_stage(demo_id, stage, "running")
    emit = emit_for(demo_id, stage)
    try:
        if stage == "understand":
            out = understand.run(demo_id, emit, instruction)
        elif stage == "plan":
            out = plan.run(demo_id, emit, instruction)
        elif stage == "author":
            out = author.run(demo_id, emit, instruction)
        elif stage == "faq":
            out = faq.run(demo_id, emit)
        elif stage == "voice":
            out = voice.render_script(demo_id, emit)
        elif stage == "rehearsal":
            out = rehearsal.run(demo_id, emit)
        elif stage == "bundle":
            out = bundle.build(demo_id, emit)
        else:
            raise ValueError(stage)
        set_stage(demo_id, stage, "done")
        invalidate(demo_id, stage)
        st = store.load(demo_id)["stages"].get(stage, {})
        runlog.stage_report(demo_id, stage, seconds=st.get("seconds"), started_at=st.get("started_at"), instruction=instruction)
        return out
    except Exception as e:
        store.log(demo_id, f"error-{stage}", {"error": str(e), "trace": traceback.format_exc()})
        set_stage(demo_id, stage, "error", error=str(e)[:400])
        runlog.stage_failed(demo_id, stage, str(e)[:2000])
        raise


def _set_status(demo_id: str, status: str) -> None:
    store.update(demo_id, lambda d: d.__setitem__("status", status))
    events.publish(demo_id, "status", status=status)


def _append_conversation(demo_id: str, role: str, text: str, **extra) -> dict:
    conv = store.read_json(demo_id, "conversation.json", []) or []
    msg = {"role": role, "text": text, "t": time.time(), **extra}
    conv.append(msg)
    store.write_json(demo_id, "conversation.json", conv)
    events.publish(demo_id, "message", message=msg)
    return msg


# ---------- phases ----------

def _persona_sample(demo_id: str) -> None:
    p = store.read_json(demo_id, "plan.json")
    if not p:
        return
    emit = emit_for(demo_id, "plan")
    try:
        demo = store.load(demo_id)
        if voice.provider_for(demo) == "gemini" and p["voice"].get("suggested_voice") in voice.GEMINI_VOICES and not demo["settings"].get("voice_locked"):
            store.update(demo_id, lambda d: d["settings"].__setitem__("voice_name", p["voice"]["suggested_voice"]))
        try:
            m = media.generate_mascot(demo_id, p.get("voice"), emit)
            if m:
                store.update(demo_id, lambda d: d.__setitem__("mascot", m))
        except Exception as e:
            emit(f"Mascot skipped ({str(e)[:60]}).")
        emit("Recording a voice sample…")
        rel = voice.sample(demo_id, p["voice"]["sample_line"])
        p["voice_sample_audio"] = rel
        store.write_json(demo_id, "plan.json", p)
    except Exception as e:
        emit(f"Voice sample skipped: {str(e)[:120]}")


# ---------- align: message → actions → effects ----------

def apply_actions(demo_id: str, actions: list[dict], attachments: list[dict], context: str, requests: dict | None = None) -> list[str]:
    """Execute the align agent's structured actions. Build / revise are *requests*: collected into `requests` when the
    graph is driving (it routes them), or handed to the graph when called from a plain API route."""
    notes: list[str] = []
    own = requests is None
    requests = requests if requests is not None else {}
    demo = store.load(demo_id)
    revise_stage, revise_instr = None, []
    for a in actions:
        t = a["type"]
        if t == "approve" and a.get("card"):
            store.update(demo_id, lambda d, c=a["card"]: d["approvals"].__setitem__(c, True))
            notes.append(f"approved {a['card']}")
            runlog.event(demo_id, f"Card approved: {a['card']}")
            nxt = align.current_card(store.load(demo_id))
            _append_conversation(demo_id, "agent", align.card_prompt(demo_id, nxt) if nxt else align.card_prompt(demo_id, "done"), system=True)
        elif t == "edit_fact" and a.get("fact_id"):
            und = store.read_json(demo_id, "understanding.json") or {}
            for f in und.get("facts", []):
                if f["id"] == a["fact_id"]:
                    f["value"] = a.get("fact_value") or f["value"]
                    if a.get("fact_claim"):
                        f["claim"] = a["fact_claim"]
                    f["edited"] = True
                    f["source"] = {**f.get("source", {}), "locator": (f.get("source", {}).get("locator", "") + " · edited by user").strip(" ·")}
                    notes.append(f"edited {f['id']}")
            store.write_json(demo_id, "understanding.json", und)
            invalidate(demo_id, "understand")
        elif t == "remove_fact" and a.get("fact_id"):
            und = store.read_json(demo_id, "understanding.json") or {}
            for f in und.get("facts", []):
                if f["id"] == a["fact_id"]:
                    f["approved"] = False
                    notes.append(f"removed {f['id']}")
            store.write_json(demo_id, "understanding.json", und)
            invalidate(demo_id, "understand")
        elif t == "resolve_unknown" and a.get("unknown_id"):
            und = store.read_json(demo_id, "understanding.json") or {}
            for u in und.get("unknowns", []):
                if u["id"] == a["unknown_id"]:
                    u["status"] = "resolved"
                    notes.append(f"resolved {u['id']}")
            store.write_json(demo_id, "understanding.json", und)
        elif t == "set_ctas":
            p = store.read_json(demo_id, "plan.json") or {}
            if a.get("ctas"):
                p["ctas"] = a["ctas"]
                store.write_json(demo_id, "plan.json", p)
                invalidate(demo_id, "plan")
                notes.append(f"ctas set ({len(a['ctas'])})")
        elif t == "set_voice":
            p = store.read_json(demo_id, "plan.json") or {}
            v = p.setdefault("voice", {})
            if a.get("persona_description"):
                v["persona_description"] = a["persona_description"]
            if a.get("tone"):
                v["tone"] = a["tone"]
            if a.get("voice_name"):
                v["suggested_voice"] = a["voice_name"]
                store.update(demo_id, lambda d, n=a["voice_name"]: (d["settings"].__setitem__("voice_name", n), d["settings"].__setitem__("voice_locked", True)))
            store.write_json(demo_id, "plan.json", p)
            invalidate(demo_id, "plan")
            try:
                rel = voice.sample(demo_id, v.get("sample_line", "Hello, I'm your guide for today."))
                p["voice_sample_audio"] = rel
                store.write_json(demo_id, "plan.json", p)
            except Exception as e:
                notes.append(f"sample failed: {str(e)[:80]}")
            notes.append("voice updated")
        elif t == "request_upload":
            notes.append(f"upload requested: {a.get('upload_kind')} — {a.get('reason')}")
        elif t == "revise" and a.get("stage"):
            order = {"understand": 0, "plan": 1, "author": 2, "faq": 3}
            if revise_stage is None or order[a["stage"]] < order[revise_stage]:
                revise_stage = a["stage"]
            revise_instr.append(a.get("instruction", ""))
        elif t == "build":
            if all(store.load(demo_id)["approvals"].values()):
                requests["build"] = True
                notes.append("build requested")
            else:
                notes.append("build refused: cards not all approved")
    if attachments and revise_stage is None and context == "align":
        revise_stage, revise_instr = "understand", ["New sources were added: " + ", ".join(a["name"] for a in attachments) + ". Incorporate them into the registry and visuals."]
    if revise_stage:
        requests["revise"] = (revise_stage, "\n".join(x for x in revise_instr if x))
        notes.append(f"revising {revise_stage}")
    if own and (requests.get("build") or requests.get("revise")):
        from . import graph
        try:
            if requests.get("revise"):
                stage, instr = requests["revise"]
                graph.start_revise(demo_id, stage, instr, rebuild=(context == "rehearse"))
            elif requests.get("build"):
                graph.start_build(demo_id)
        except RuntimeError as e:
            notes.append(str(e))
    return notes


def respond(demo_id: str, message: str, attachments: list[dict], context: str = "align") -> tuple[str, list[dict], list[str], dict]:
    """One alignment turn: record the user message, ask the align agent, execute its actions, record the reply.
    Returns (reply, actions, notes, requests) — the graph routes on `requests`."""
    usage.current_demo.set(demo_id)
    usage.current_stage.set("align")
    history = store.read_json(demo_id, "conversation.json", []) or []
    _append_conversation(demo_id, "user", message, attachments=[{"id": a["id"], "name": a["name"], "kind": a["kind"]} for a in attachments])
    out = align.respond(demo_id, message, attachments, history, context)
    actions = [a.model_dump() for a in out.actions]
    requests: dict = {}
    notes = apply_actions(demo_id, actions, attachments, context, requests)
    reply = out.reply.strip()
    _append_conversation(demo_id, "agent", reply, actions=actions, notes=notes)
    runlog.chat(demo_id, context, message, reply, actions, attachments)
    return reply, actions, notes, requests
