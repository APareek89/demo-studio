"""Stage graph + invalidation + background runs + align-action execution.

Stages run in worker threads (the SDKs are synchronous); progress streams through events.py.
"""
from __future__ import annotations

import threading
import time
import traceback
import re

from . import cloud, events, media, store, usage, runlog
from .agents import align, author, bundle, coach, deck, faq, narration, plan, rehearsal, understand, voice
from .store import STAGES

# Declare which outputs depend on a changed stage so reuse never assumes they are current.
# Input: the name of the changed stage. Output: the stage names invalidate() marks stale.
# Linked: server/graph.py node wrappers reuse only appropriate completed work; Deck changes need no new voice.
DOWNSTREAM = {
    "understand": ["coach", "plan", "author", "deck", "faq", "voice", "rehearsal", "bundle"],
    "coach": ["plan", "author", "deck", "voice", "rehearsal", "bundle"],
    "plan": ["author", "deck", "voice", "rehearsal", "bundle"],
    "author": ["deck", "voice", "rehearsal", "bundle"],
    "deck": ["bundle"],  # audio is keyed by script text; a slide change only needs re-bundling
    "faq": ["voice", "rehearsal", "bundle"],
    "voice": ["bundle"],
    "rehearsal": [],  # on-demand diagnostics do not change the published demo
    "bundle": [],
}

# Ask the build graph whether this demo already has an active worker.
# Input: demo ID. Output: true or false; this module does not maintain a second worker list.
# Linked: server/graph.py:is_running is the source of worker state.
def is_running(demo_id: str) -> bool:
    from . import graph
    return graph.is_running(demo_id)


# Create a progress reporter bound to one demo and optional stage.
# Input: demo ID/stage. Output: an emit(message) callback for agent functions.
# Linked: server/agents/plan.py:run and other stage functions receive this callback from _run_stage.
def emit_for(demo_id: str, stage: str | None = None):
    # Save useful progress history and send each message to connected Studio clients.
    # Input: an agent progress message. Output: updated stage notes and a progress event.
    # Linked: server/store.py:update persists notes; server/events.py:publish sends the UI event.
    def emit(message: str):
        if stage:
            # Keep the latest progress entries and a short list of warning-like messages.
            # Input: mutable demo record and captured message. Output: changed stage metadata in that record.
            # Linked: server/store.py:update saves this callback result under the per-demo write lock.
            def retain(d):
                state = d["stages"].setdefault(stage, {})
                entry = {"t": time.time(), "message": str(message)}
                state["message"] = str(message)
                state["progress"] = (state.get("progress", []) + [entry])[-40:]
                if re.search(r"\b(warning|skipped|unavailable|missing|failed|error|fallback|held back|timed captions)\b", str(message), re.I):
                    state["warnings"] = (state.get("warnings", []) + [entry])[-20:]
            store.update(demo_id, retain)
        events.publish(demo_id, "progress", stage=stage, message=message)
    return emit


# Track when a stage starts, finishes or fails and how long it took.
# Input: demo ID, stage and status/error/message. Output: saved stage metadata and a stage event.
# Linked: server/store.py:update and server/events.py:publish keep polling and streaming views aligned.
def set_stage(demo_id: str, stage: str, status: str, error: str | None = None, message: str = "") -> None:
    # Update one stage record while retaining its earlier timing information when appropriate.
    # Input: mutable demo record. Output: stage state plus the current running-stage marker.
    # Linked: server/store.py:update calls this callback while holding the demo lock.
    def fn(d):
        prev = d["stages"].get(stage, {})
        started = time.time() if status == "running" else prev.get("started_at")
        d["stages"][stage] = {**prev, "status": status, "updated_at": time.time(), "error": error, "message": message or ("" if status == "running" else prev.get("message", "")), "started_at": started,
                              "seconds": round(time.time() - started, 1) if started and status in ("done", "error") else prev.get("seconds")}
        if status == "running":
            d["stages"][stage].update(progress=[], warnings=[])
            d["running"] = stage
        elif d.get("running") == stage:
            d["running"] = None
    store.update(demo_id, fn)
    events.publish(demo_id, "stage", stage=stage, status=status, error=error)


# Mark completed dependent stages stale when an upstream result changes.
# Input: demo ID and changed stage. Output: updated status only; artifacts are not regenerated here.
# Linked: server/graph.py nodes consult these states before reusing work.
def invalidate(demo_id: str, stage: str) -> None:
    # Apply the dependency list to a demo record without deleting previous outputs.
    # Input: mutable demo record and captured stage. Output: downstream done states become stale.
    # Linked: server/store.py:update persists the state; server/graph.py chooses when to rerun it.
    def fn(d):
        for s in DOWNSTREAM[stage]:
            if d["stages"][s]["status"] == "done":
                d["stages"][s]["status"] = "stale"
    store.update(demo_id, fn)


_NON_SEMANTIC = {"audio", "checkin_audio", "intake_audio", "voice_sample_audio", "voice_provider", "voice_name", "voice_input_hash",
                 "voice_failures", "version", "updated_at", "created_at", "t", "timeline",
                 "narration_preparation",
                 "duration_seconds", "duration_exact", "duration_in_range", "exact", "spoken", "checkin_start", "checkin_duration"}


# Remove recording and bookkeeping fields before deciding whether review content changed.
# Input: nested artifact data. Output: a comparable copy containing the review-relevant content.
# Linked: server/agents/voice.py adds audio/timing; those additions alone should not revoke content approval.
def semantic(value):
    """Keep approval content while excluding recording/version bookkeeping."""
    if isinstance(value, dict):
        ignored = _NON_SEMANTIC | ({"start", "duration"} if "text" in value or "lines" in value else set())
        return {k: semantic(v) for k, v in value.items() if k not in ignored}
    if isinstance(value, list):
        return [semantic(v) for v in value]
    return value


# Decide which review cards need approval again after a stage rewrites an artifact.
# Input: stage name and before/after JSON. Output: a set of affected card names.
# Linked: server/store.py:CARDS defines the review cards used by server/graph.py:align_wait.
def changed_cards(stage: str, before: dict | None, after: dict | None) -> set[str]:
    before, after = semantic(before or {}), semantic(after or {})
    if stage == "faq":
        # Repeat asks are usage counts, not newly reviewed answer content.
        for bank in (before, after):
            for entry in bank.get("entries", []):
                entry.pop("asked_count", None)
    if before == after:
        return set()
    if stage == "understand":
        factual = ("facts", "competitors", "unknowns", "product", "brand")
        return set(store.CARDS) if any(before.get(k) != after.get(k) for k in factual) else {"visuals", "script"}
    if stage == "coach":
        return {"script", "visuals"} if any(before.get(k) != after.get(k) for k in ("stops", "usps", "evidence_gaps", "issues")) else set()
    if stage == "plan":
        cards = set()
        if before.get("voice") != after.get("voice"):
            cards.add("persona")
        if before.get("ctas") != after.get("ctas"):
            cards.add("ctas")
        if {k: v for k, v in before.items() if k not in ("voice", "ctas")} != {k: v for k, v in after.items() if k not in ("voice", "ctas")}:
            cards.update(("script", "visuals"))
        return cards
    return {"author": {"script", "visuals"}, "deck": {"visuals"}, "faq": {"faq"}}.get(stage, set())


def approve_empty_faq(demo_id: str) -> bool:
    """An empty review card must not block Build, including a reused Read."""
    with store._lock(demo_id):
        bank = store.read_json(demo_id, "faq.json") or {}
        und = store.read_json(demo_id, "understanding.json") or {}
        has_questions = bool(faq.current_entries(bank)) or any(
            unknown.get("source") == "customer" and unknown.get("status", "open") == "open"
            for unknown in und.get("unknowns", []))
        if has_questions:
            return False
        demo = store.load(demo_id)
        demo["approvals"]["faq"] = True
        store.save(demo_id, demo)
        return True


# Run the agent behind one stage and record its outcome and downstream staleness.
# Input: demo ID, stage and instruction. Output: agent return value plus saved artifacts/status/events.
# Linked: server/agents/* stage functions do the work; server/graph.py calls this shared wrapper.
def _run_stage(demo_id: str, stage: str, instruction: str = "") -> object:
    usage.current_demo.set(demo_id)
    usage.current_stage.set(stage)
    set_stage(demo_id, stage, "running")
    emit = emit_for(demo_id, stage)
    # Capture the old review artifact before a stage rewrites it.
    # Input: stage name. Output: its previous JSON for changed_cards(), when the stage has a review file.
    # Linked: server/store.py:read_json retrieves the agent output rather than LangGraph checkpoint state.
    output_file = {"understand": "understanding.json", "coach": "playbook.json", "plan": "plan.json", "author": "script.json", "deck": "deck.json", "faq": "faq.json"}.get(stage)
    previous = store.read_json(demo_id, output_file) if output_file else None
    try:
        # Dispatch to the actual implementation; graph nodes do not contain the product-generation logic.
        # Input: stage and revision instruction. Output: the result returned by the corresponding agent.
        # Linked: server/agents/understand.py:run through server/agents/bundle.py:build implement these branches.
        if stage == "understand":
            out = understand.run(demo_id, emit, instruction)
        elif stage == "coach":
            out = coach.run(demo_id, emit, instruction)
        elif stage == "plan":
            out = plan.run(demo_id, emit, instruction)
        elif stage == "author":
            out = author.run(demo_id, emit, instruction)
        elif stage == "deck":
            out = deck.build(demo_id, emit, instruction)
        elif stage == "faq":
            out = faq.run(demo_id, emit, force=bool(instruction))
        elif stage == "voice":
            out = voice.render_script(demo_id, emit)
        elif stage == "rehearsal":
            out = rehearsal.run(demo_id, emit)
        elif stage == "bundle":
            out = bundle.build(demo_id, emit)
        else:
            raise ValueError(stage)
        # Reconcile approvals and mark the successful stage complete before notifying dependent stages.
        # Input: old/new artifacts and stage result. Output: updated review flags, status, timing and logs.
        # Linked: server/runlog.py:stage_report records details; server/cloud.py helpers optionally mirror the result.
        cards = changed_cards(stage, previous, store.read_json(demo_id, output_file)) if output_file else set()
        if cards:
            store.update(demo_id, lambda d: d["approvals"].update({card: False for card in cards}))
        if stage == "faq" and approve_empty_faq(demo_id):
            emit("No questions yet; this card fills from customer questions")
        preparation = narration.preparation_status(demo_id) if stage == "author" else None
        incomplete = preparation and preparation["status"] in {"incomplete", "needs_sources"}
        if incomplete:
            store.update(demo_id, lambda d: d["approvals"].__setitem__("script", False))
            set_stage(demo_id, stage, "pending", message=preparation["reason"])
            emit(preparation["reason"])
        else:
            set_stage(demo_id, stage, "done")
        invalidate(demo_id, stage)
        st = store.load(demo_id)["stages"].get(stage, {})
        runlog.stage_report(demo_id, stage, seconds=st.get("seconds"), started_at=st.get("started_at"), instruction=instruction)
        cloud.put_event(demo_id, "stage_pending" if incomplete else "stage_done", {"stage": stage, "seconds": st.get("seconds"), "cost_usd": usage.summary(demo_id).get("by_stage", {}).get(stage, {}).get("usd")})
        cloud.sync_demo_async(demo_id)
        return out
    except Exception as e:
        if isinstance(e, (bundle.ApprovalRequired, narration.NarrationTooShort)):
            set_stage(demo_id, stage, "pending", message=str(e))
            raise
        store.log(demo_id, f"error-{stage}", {"error": str(e), "trace": traceback.format_exc()})
        set_stage(demo_id, stage, "error", error=str(e)[:400])
        runlog.stage_failed(demo_id, stage, str(e)[:2000])
        raise


# Update the overall demo status and notify the UI.
# Input: demo ID and status text. Output: changed demo.json and a status event.
# Linked: server/store.py:update saves it; server/events.py:publish announces it.
def _set_status(demo_id: str, status: str) -> None:
    store.update(demo_id, lambda d: d.__setitem__("status", status))
    events.publish(demo_id, "status", status=status)


# Append one review-chat message with optional structured details.
# Input: demo ID, role, text and extra fields. Output: the saved message and a UI message event.
# Linked: server/store.py:write_json stores conversation.json; server/agents/align.py supplies review replies.
def _append_conversation(demo_id: str, role: str, text: str, **extra) -> dict:
    conv = store.read_json(demo_id, "conversation.json", []) or []
    msg = {"role": role, "text": text, "t": time.time(), **extra}
    conv.append(msg)
    store.write_json(demo_id, "conversation.json", conv)
    events.publish(demo_id, "message", message=msg)
    return msg


# ---------- phases ----------

# Prepare a mascot and short voice preview for the selected persona when providers are available.
# Input: plan.json and demo voice settings. Output: mascot metadata and voice_sample_audio when successful.
# Linked: server/media.py:generate_mascot and server/agents/voice.py:sample create the preview assets.
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

# Apply the Align agent choices and collect any requested build or revision.
# Input: actions, attachments and review context. Output: notes plus requested routes and saved edits.
# Linked: server/agents/align.py:respond proposes actions; server/store.py validates edits; server/graph.py routes work.
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
        # Accept a review card and show the next unresolved review topic.
        # Input: the Align action card name. Output: saved approval and the next review prompt.
        # Linked: server/agents/align.py:current_card and card_prompt choose that next prompt.
        if t == "approve" and a.get("card"):
            if a["card"] == "script":
                preparation = narration.preparation_status(demo_id)
                if preparation["status"] in {"incomplete", "needs_sources"}:
                    store.update(demo_id, lambda d: d["approvals"].__setitem__("script", False))
                    notes.append("Script approval paused: " + preparation["reason"])
                    continue
            store.update(demo_id, lambda d, c=a["card"]: d["approvals"].__setitem__(c, True))
            notes.append(f"approved {a['card']}")
            runlog.event(demo_id, f"Card approved: {a['card']}")
            nxt = align.current_card(store.load(demo_id))
            _append_conversation(demo_id, "agent", align.card_prompt(demo_id, nxt) if nxt else align.card_prompt(demo_id, "done"), system=True)
        # Validate a fact correction, then invalidate content that relied on the old assertion.
        # Input: supplied fact edits. Output: a versioned fact or a refusal, plus refreshed review requirements.
        # Linked: server/store.py:edit_fact preserves old assertion meaning; server/graph.py later reruns stale stages.
        elif t == "edit_fact" and a.get("fact_id"):
            edits = {field: a["fact_" + field] for field in ("value", "claim") if a.get("fact_" + field)}
            edits.update({field: a["fact_" + field] for field in ("conditions", "truth", "source", "scope") if a.get("fact_" + field) is not None})
            try:
                corrected = store.edit_fact(demo_id, a["fact_id"], edits)
            except (KeyError, ValueError) as exc:
                notes.append(f"Could not edit {a['fact_id']}: {str(exc)}")
                continue
            if corrected["id"] == a["fact_id"]:
                notes.append(f"unchanged {a['fact_id']}")
                continue
            notes.append(f"edited {a['fact_id']} → {corrected['id']}")
            invalidate(demo_id, "understand")
            set_stage(demo_id, "understand", "done", message="fact correction saved and validated")
            set_stage(demo_id, "faq", "stale", message="fact edited — bank re-answers on the next build")
            store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
        # Exclude a fact from approved content without deleting the historical assertion.
        # Input: fact ID. Output: approval false, stale dependent work and cleared review cards.
        # Linked: server/store.py:set_fact_approval updates the registry read by the author and runtime.
        elif t == "remove_fact" and a.get("fact_id"):
            try:
                store.set_fact_approval(demo_id, a["fact_id"], False)
            except (KeyError, ValueError) as exc:
                notes.append(f"Could not remove {a['fact_id']}: {str(exc)}")
                continue
            notes.append(f"removed {a['fact_id']}")
            invalidate(demo_id, "understand")
            set_stage(demo_id, "understand", "done", message="fact approval reviewed")
            set_stage(demo_id, "faq", "stale", message="fact removed — bank re-answers on the next build")
            store.update(demo_id, lambda d: d["approvals"].update({key: False for key in store.CARDS}))
        elif t == "resolve_unknown" and a.get("unknown_id"):
            und = store.read_json(demo_id, "understanding.json") or {}
            for u in und.get("unknowns", []):
                if u["id"] == a["unknown_id"]:
                    u["status"] = "resolved"
                    notes.append(f"resolved {u['id']}")
            store.write_json(demo_id, "understanding.json", und)
        # Save the requested buyer actions and invalidate affected script/visual review.
        # Input: replacement CTA list. Output: updated plan.json and downstream stale status.
        # Linked: server/agents/bundle.py:build later includes these reviewed calls to action.
        elif t == "set_ctas":
            p = store.read_json(demo_id, "plan.json") or {}
            if a.get("ctas"):
                p["ctas"] = a["ctas"]
                store.write_json(demo_id, "plan.json", p)
                invalidate(demo_id, "plan")
                store.update(demo_id, lambda d: d["approvals"].update(ctas=False, script=False, visuals=False))
                notes.append(f"ctas set ({len(a['ctas'])})")
        # Save persona changes and lock an explicitly selected voice identity.
        # Input: persona/tone/voice fields. Output: revised plan/settings and an attempted sample recording.
        # Linked: server/agents/voice.py:sample generates the preview; failures become notes rather than a silent voice change.
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
            store.update(demo_id, lambda d: d["approvals"].update(persona=False, script=False, visuals=False))
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
            order = {"understand": 0, "coach": 1, "plan": 2, "author": 3, "deck": 4, "faq": 5}
            if revise_stage is None or order[a["stage"]] < order[revise_stage]:
                revise_stage = a["stage"]
            revise_instr.append(a.get("instruction", ""))
        elif t == "build":
            preparation = narration.preparation_status(demo_id)
            if preparation["status"] in {"incomplete", "needs_sources"}:
                notes.append("Build paused: " + preparation["reason"])
            elif all(store.load(demo_id)["approvals"].values()):
                requests["build"] = True
                notes.append("build requested")
            else:
                notes.append("build refused: cards not all approved")
    # Turn newly attached evidence into a source reread when no other revision was selected.
    # Input: attachments, context and accumulated actions. Output: an Understand revision request.
    # Linked: server/graph.py:start_revise sends the new evidence back through the review workflow.
    if attachments and revise_stage is None and context in {"align", "rehearse"}:
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


# Handle one complete human-review chat turn and record what happened.
# Input: demo ID, message, attachments and context. Output: reply, actions, notes and requested routes.
# Linked: server/agents/align.py:respond generates structured choices; server/runlog.py:chat records the turn.
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
