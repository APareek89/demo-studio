"""Stage graph + invalidation + background runs + align-action execution.

Stages run in worker threads (the SDKs are synchronous); progress streams through events.py.
"""
from __future__ import annotations

import threading
import time
import traceback

from . import events, store, usage
from .agents import align, author, bundle, plan, rehearsal, understand, voice
from .store import STAGES

DOWNSTREAM = {
    "understand": ["plan", "author", "voice", "rehearsal", "bundle"],
    "plan": ["author", "voice", "rehearsal", "bundle"],
    "author": ["voice", "rehearsal", "bundle"],
    "voice": ["bundle"],
    "rehearsal": ["bundle"],
    "bundle": [],
}
_threads: dict[str, threading.Thread] = {}


def is_running(demo_id: str) -> bool:
    t = _threads.get(demo_id)
    return bool(t and t.is_alive())


def emit_for(demo_id: str, stage: str | None = None):
    def emit(message: str):
        events.publish(demo_id, "progress", stage=stage, message=message)
    return emit


def set_stage(demo_id: str, stage: str, status: str, error: str | None = None, message: str = "") -> None:
    def fn(d):
        d["stages"][stage] = {"status": status, "updated_at": time.time(), "error": error, "message": message}
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
        return out
    except Exception as e:
        store.log(demo_id, f"error-{stage}", {"error": str(e), "trace": traceback.format_exc()})
        set_stage(demo_id, stage, "error", error=str(e)[:400])
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


def _spawn(demo_id: str, target, *args) -> None:
    if is_running(demo_id):
        raise RuntimeError("This demo is already being processed — wait for it to finish")
    t = threading.Thread(target=target, args=(demo_id, *args), daemon=True)
    _threads[demo_id] = t
    t.start()


# ---------- phases ----------

def _read(demo_id: str, instruction: str = "") -> None:
    try:
        _set_status(demo_id, "reading")
        st = store.load(demo_id)["stages"]
        if instruction or st["understand"]["status"] != "done" or not store.read_json(demo_id, "understanding.json"):
            _run_stage(demo_id, "understand", instruction)
        else:
            events.publish(demo_id, "progress", stage="understand", message="Sources already read — reusing the registry and visuals.")
        _run_stage(demo_id, "plan", "")
        _persona_sample(demo_id)
        _set_status(demo_id, "align")
        text = align.opening_message(demo_id)
        _append_conversation(demo_id, "agent", text)
        events.publish(demo_id, "phase_done", phase="read")
    except Exception as e:
        _set_status(demo_id, "error")
        events.publish(demo_id, "phase_error", phase="read", error=str(e)[:400])


def _persona_sample(demo_id: str) -> None:
    p = store.read_json(demo_id, "plan.json")
    if not p:
        return
    emit = emit_for(demo_id, "plan")
    try:
        demo = store.load(demo_id)
        if voice.provider_for(demo) == "gemini" and p["voice"].get("suggested_voice") in voice.GEMINI_VOICES and not demo["settings"].get("voice_locked"):
            store.update(demo_id, lambda d: d["settings"].__setitem__("voice_name", p["voice"]["suggested_voice"]))
        emit("Recording a voice sample…")
        rel = voice.sample(demo_id, p["voice"]["sample_line"])
        p["voice_sample_audio"] = rel
        store.write_json(demo_id, "plan.json", p)
    except Exception as e:
        emit(f"Voice sample skipped: {str(e)[:120]}")


def _build(demo_id: str) -> None:
    try:
        _set_status(demo_id, "building")
        st = store.load(demo_id)["stages"]
        if st["author"]["status"] != "done":
            _run_stage(demo_id, "author", "")
        _run_stage(demo_id, "voice", "")
        _run_stage(demo_id, "rehearsal", "")
        _run_stage(demo_id, "bundle", "")
        _set_status(demo_id, "ready")
        events.publish(demo_id, "phase_done", phase="build")
    except Exception as e:
        _set_status(demo_id, "error")
        events.publish(demo_id, "phase_error", phase="build", error=str(e)[:400])


def _revise(demo_id: str, stage: str, instruction: str, rebuild: bool) -> None:
    try:
        prev_status = store.load(demo_id)["status"]
        _set_status(demo_id, "reading" if stage in ("understand", "plan") else "building")
        if stage == "understand":
            _run_stage(demo_id, "understand", instruction)
            _run_stage(demo_id, "plan", "")
            store.update(demo_id, lambda d: d["approvals"].update({"visuals": False, "facts": False}))
        elif stage == "plan":
            _run_stage(demo_id, "plan", instruction)
            _persona_sample(demo_id)
        elif stage == "author":
            _run_stage(demo_id, "author", instruction)
        if rebuild or prev_status == "ready":
            if store.load(demo_id)["stages"]["author"]["status"] != "done":
                _run_stage(demo_id, "author", "")
            _run_stage(demo_id, "voice", "")
            _run_stage(demo_id, "bundle", "")
            _set_status(demo_id, "ready")
            events.publish(demo_id, "phase_done", phase="build")
        else:
            _set_status(demo_id, "align")
            events.publish(demo_id, "phase_done", phase="revise")
    except Exception as e:
        _set_status(demo_id, "error")
        events.publish(demo_id, "phase_error", phase="revise", error=str(e)[:400])


def start_read(demo_id: str, instruction: str = "") -> None:
    _spawn(demo_id, _read, instruction)


def start_build(demo_id: str) -> None:
    demo = store.load(demo_id)
    if not all(demo["approvals"].values()):
        raise RuntimeError("Approve all five cards before building")
    _spawn(demo_id, _build)


def start_revise(demo_id: str, stage: str, instruction: str, rebuild: bool = False) -> None:
    _spawn(demo_id, _revise, stage, instruction, rebuild)


# ---------- align: message → actions → effects ----------

def handle_message(demo_id: str, message: str, attachments: list[dict], context: str = "align") -> dict:
    usage.current_demo.set(demo_id)
    usage.current_stage.set("align")
    if is_running(demo_id):
        raise RuntimeError("Still working on the last change — give me a moment")
    history = store.read_json(demo_id, "conversation.json", []) or []
    _append_conversation(demo_id, "user", message, attachments=[{"id": a["id"], "name": a["name"], "kind": a["kind"]} for a in attachments])
    out = align.respond(demo_id, message, attachments, history, context)
    notes = apply_actions(demo_id, [a.model_dump() for a in out.actions], attachments, context)
    reply = out.reply.strip()
    agent_msg = _append_conversation(demo_id, "agent", reply, actions=[a.model_dump() for a in out.actions], notes=notes)
    return {"reply": reply, "actions": [a.model_dump() for a in out.actions], "notes": notes, "message": agent_msg}


def apply_actions(demo_id: str, actions: list[dict], attachments: list[dict], context: str) -> list[str]:
    notes: list[str] = []
    demo = store.load(demo_id)
    revise_stage, revise_instr = None, []
    for a in actions:
        t = a["type"]
        if t == "approve" and a.get("card"):
            store.update(demo_id, lambda d, c=a["card"]: d["approvals"].__setitem__(c, True))
            notes.append(f"approved {a['card']}")
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
            order = {"understand": 0, "plan": 1, "author": 2}
            if revise_stage is None or order[a["stage"]] < order[revise_stage]:
                revise_stage = a["stage"]
            revise_instr.append(a.get("instruction", ""))
        elif t == "build":
            if all(store.load(demo_id)["approvals"].values()):
                try:
                    start_build(demo_id)
                    notes.append("build started")
                except RuntimeError as e:
                    notes.append(str(e))
            else:
                notes.append("build refused: cards not all approved")
    if attachments and revise_stage is None and context == "align":
        revise_stage, revise_instr = "understand", ["New sources were added: " + ", ".join(a["name"] for a in attachments) + ". Incorporate them into the registry and visuals."]
    if revise_stage:
        try:
            start_revise(demo_id, revise_stage, "\n".join(x for x in revise_instr if x), rebuild=(context == "rehearse"))
            notes.append(f"revising {revise_stage}")
        except RuntimeError as e:
            notes.append(str(e))
    return notes
