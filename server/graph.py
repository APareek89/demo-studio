"""The demo-building workflow as ONE LangGraph graph.

    START ─▶ router ─▶ understand ─▶ plan ─▶ author ─▶ deck ─▶ faq ─▶ align_enter ─▶ align_wait ◀─┐ (interrupt: waits for you)
                 │                                                                   │  message / approve / revise ─┘
                 │                                                                   └─ build ─▶ voice ─▶ rehearsal ─▶ bundle ─▶ finish ─▶ END
                 ├─ build  ─▶ author (skips when done) ─▶ deck (skips when done) ─▶ faq …
                 └─ revise ─▶ understand | plan | author | deck | faq (then back to align_wait, or on to the build chain when rebuilding)

Every node is one of the existing stage functions (server/agents/*) wrapped by orchestrator._run_stage, which keeps
the stage bookkeeping, tracing and the run log. State is checkpointed in data/graph.sqlite after every node, so a
demo can be resumed from where it stopped, and the whole workflow can be drawn (docs/mermaid/00-workflow.mmd) or
stepped through in LangGraph Studio (`langgraph dev`, see langgraph.json)."""
from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from typing import Optional, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from . import cloud, config, events, runlog, store
from . import orchestrator as orch
from .agents import align


class DemoState(TypedDict, total=False):
    demo_id: str
    entry: str            # read | build | revise | message
    instruction: str      # for understand / plan / author when revising
    revise_stage: str     # understand | plan | author
    rebuild: bool         # revise and then run the build chain
    prev_ready: bool      # the demo was ready before this revision → rebuild after
    pending: Optional[dict]  # a user command carried in with the input (message/build/revise) instead of via interrupt


# ---------- nodes ----------

def router(state: DemoState) -> Command:
    e = state.get("entry", "read")
    if e == "read":
        return Command(goto="understand")
    if e == "build":
        return Command(goto="author")
    if e == "revise":
        return Command(goto=state.get("revise_stage") or "author")
    return Command(goto="align_wait")


def understand(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "reading")
    if state.get("entry") == "read":
        runlog.event(d, "READ started" + (f" · instruction: {state.get('instruction')}" if state.get("instruction") else ""), "Configure Demo: understand the sources, then plan the pitch.")
        st = store.load(d)["stages"]
        if not state.get("instruction") and st["understand"]["status"] == "done" and store.read_json(d, "understanding.json"):
            events.publish(d, "progress", stage="understand", message="Sources already read — reusing the registry and visuals.")
            return {}
    orch._run_stage(d, "understand", state.get("instruction", "") if state.get("entry") in ("read", "revise") else "")
    if state.get("entry") == "revise":
        # New source material can change any downstream card. Never leave a stale
        # approval green and accidentally expose Build before the new alignment pass.
        store.update(d, lambda x: x["approvals"].update({card: False for card in store.CARDS}))
    return {}


def plan(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "reading")
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "plan" else ""
    orch._run_stage(d, "plan", instr)
    orch._persona_sample(d)
    return {}


def align_enter(state: DemoState) -> dict:
    """Back to the human: status align, opening message on a fresh read, run-log marker."""
    d = state["demo_id"]
    orch._set_status(d, "align")
    if state.get("entry") == "read":
        text = align.opening_message(d)
        orch._append_conversation(d, "agent", text)
        runlog.event(d, "Agent opening message", text)
        runlog.phase_done(d, "read")
        events.publish(d, "phase_done", phase="read")
    else:
        runlog.phase_done(d, "revise")
        events.publish(d, "phase_done", phase="revise")
    return {}


def align_wait(state: DemoState) -> Command:
    """The human checkpoint. Waits (interrupt) for a chat message, a build request or a revision; acts on it; routes."""
    d = state["demo_id"]
    cmd = state.get("pending") or interrupt({"demo_id": d, "status": store.load(d)["status"], "approvals": store.load(d)["approvals"]})
    update = {"pending": None, "instruction": "", "rebuild": False}
    kind = (cmd or {}).get("type")
    if kind == "message":
        reply, actions, notes, requests = orch.respond(d, cmd.get("message", ""), cmd.get("attachments") or [], cmd.get("context", "align"))
        events.publish(d, "align_reply", req_id=cmd.get("req_id"), reply=reply, actions=actions, notes=notes)
        if requests.get("revise"):
            stage, instr = requests["revise"]
            rebuild = cmd.get("context") == "rehearse" or store.load(d)["status"] == "ready"
            return Command(goto=stage, update={**update, "entry": "revise", "revise_stage": stage, "instruction": instr, "rebuild": rebuild, "prev_ready": store.load(d)["status"] == "ready"})
        if requests.get("build"):
            return Command(goto="author", update={**update, "entry": "build"})
        return Command(goto="align_wait", update=update)
    if kind == "build":
        if all(store.load(d)["approvals"].values()):
            return Command(goto="author", update={**update, "entry": "build"})
        events.publish(d, "phase_error", phase="build", error="Approve all six cards before building")
        return Command(goto="align_wait", update=update)
    if kind == "revise":
        stage = cmd.get("stage") or "author"
        return Command(goto=stage, update={**update, "entry": "revise", "revise_stage": stage, "instruction": cmd.get("instruction", ""), "rebuild": bool(cmd.get("rebuild")), "prev_ready": store.load(d)["status"] == "ready"})
    return Command(goto="align_wait", update=update)


def author(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "building" if state.get("entry") == "build" or (state.get("entry") == "revise" and (state.get("rebuild") or state.get("prev_ready"))) else "reading")
    if state.get("entry") == "build":
        runlog.event(d, "BUILD started", "All six cards approved. Voice (narration + FAQ answers + fillers) → rehearsal → bundle.")
        if store.load(d)["stages"]["author"]["status"] == "done":
            return {}
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "author" else ""
    orch._run_stage(d, "author", instr)
    return {}


def deck(state: DemoState) -> dict:
    d = state["demo_id"]
    if state.get("entry") == "build" and store.load(d)["stages"]["deck"]["status"] == "done":
        return {}
    orch._set_status(d, "building" if state.get("entry") == "build" or (state.get("entry") == "revise" and (state.get("rebuild") or state.get("prev_ready"))) else "reading")
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "deck" else ""
    orch._run_stage(d, "deck", instr)
    return {}


def voice(state: DemoState) -> dict:
    orch._set_status(state["demo_id"], "building")
    orch._run_stage(state["demo_id"], "voice", "")
    return {}


def rehearsal(state: DemoState) -> dict:
    orch._run_stage(state["demo_id"], "rehearsal", "")
    return {}


def bundle(state: DemoState) -> dict:
    orch._run_stage(state["demo_id"], "bundle", "")
    return {}


def finish(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "ready")
    runlog.phase_done(d, "build")
    cloud.sync_demo_async(d)
    events.publish(d, "phase_done", phase="build")
    return {}


# ---------- routing ----------

def after_plan(state: DemoState) -> str:
    return "author"  # the script is part of Align now: plan → author → faq → align


def after_author(state: DemoState) -> str:
    if state.get("entry") == "build" or (state.get("entry") == "revise" and (state.get("rebuild") or state.get("prev_ready"))):
        d = state["demo_id"]
        return "voice" if store.load(d)["stages"]["faq"]["status"] == "done" else "faq"  # a stale bank re-answers before voicing
    return "faq"


def faq(state: DemoState) -> dict:
    d = state["demo_id"]
    explicit_retry = state.get("entry") == "revise" and state.get("revise_stage") == "faq"
    if store.load(d)["stages"]["faq"]["status"] == "done" and not explicit_retry:
        return {}
    orch._set_status(d, "building" if state.get("entry") == "build" or (state.get("entry") == "revise" and (state.get("rebuild") or state.get("prev_ready"))) else "reading")
    orch._run_stage(d, "faq", state.get("instruction", "") if explicit_retry else "")
    return {}


def after_voice(state: DemoState) -> str:
    return "bundle" if state.get("entry") == "revise" else "rehearsal"


def build_graph() -> StateGraph:
    g = StateGraph(DemoState)
    g.add_node("router", router, destinations=("understand", "author", "plan", "deck", "faq", "align_wait"))
    g.add_node("understand", understand)
    g.add_node("plan", plan)
    g.add_node("align_enter", align_enter)
    g.add_node("align_wait", align_wait, destinations=("align_wait", "understand", "plan", "author", "deck", "faq"))
    g.add_node("author", author)
    g.add_node("deck", deck)
    g.add_node("faq", faq)
    g.add_node("voice", voice)
    g.add_node("rehearsal", rehearsal)
    g.add_node("bundle", bundle)
    g.add_node("finish", finish)
    g.add_edge(START, "router")
    g.add_edge("understand", "plan")
    g.add_conditional_edges("plan", after_plan, {"author": "author"})
    g.add_edge("align_enter", "align_wait")
    g.add_edge("author", "deck")
    g.add_conditional_edges("deck", after_author, {"voice": "voice", "faq": "faq"})
    g.add_conditional_edges("faq", lambda st: "voice" if st.get("entry") == "build" or (st.get("entry") == "revise" and (st.get("rebuild") or st.get("prev_ready"))) else "align_enter", {"voice": "voice", "align_enter": "align_enter"})
    g.add_conditional_edges("voice", after_voice, {"rehearsal": "rehearsal", "bundle": "bundle"})
    g.add_edge("rehearsal", "bundle")
    g.add_edge("bundle", "finish")
    g.add_edge("finish", END)
    return g


# ---------- runtime: one compiled graph, one sqlite checkpointer, one thread per running demo ----------

_conn = sqlite3.connect(str(config.GRAPH_DB), check_same_thread=False)
checkpointer = SqliteSaver(_conn)
graph = build_graph().compile(checkpointer=checkpointer)
_threads: dict[str, threading.Thread] = {}
_lock = threading.Lock()


def _cfg(demo_id: str) -> dict:
    return {"configurable": {"thread_id": demo_id}}


def is_running(demo_id: str) -> bool:
    t = _threads.get(demo_id)
    return bool(t and t.is_alive())


def is_waiting(demo_id: str) -> bool:
    """True when the graph is parked at the Align checkpoint for this demo."""
    try:
        st = graph.get_state(_cfg(demo_id))
        return bool(st.next) and "align_wait" in st.next and any(getattr(t, "interrupts", None) for t in st.tasks)
    except Exception:
        return False


def _run(demo_id: str, payload, phase: str) -> None:
    try:
        graph.invoke(payload, _cfg(demo_id))
    except Exception as e:
        orch._set_status(demo_id, "error")
        events.publish(demo_id, "phase_error", phase=phase, error=str(e)[:400])
        store.log(demo_id, "error-graph", {"phase": phase, "error": str(e)})


def _spawn(demo_id: str, payload, phase: str) -> None:
    with _lock:
        if is_running(demo_id):
            raise RuntimeError("This demo is already being processed — wait for it to finish")
        t = threading.Thread(target=_run, args=(demo_id, payload, phase), daemon=True, name=f"graph-{demo_id}")
        _threads[demo_id] = t
        t.start()


def _submit(demo_id: str, cmd: dict, fresh: dict, phase: str) -> None:
    """Deliver a command: resume the parked checkpoint when there is one, otherwise start a new run."""
    if is_waiting(demo_id):
        _spawn(demo_id, Command(resume=cmd), phase)
    else:
        _spawn(demo_id, {"demo_id": demo_id, **fresh}, phase)


def start_read(demo_id: str, instruction: str = "") -> None:
    orch._set_status(demo_id, "reading")  # synchronous, so the UI and any poller see it before the thread starts
    _spawn(demo_id, {"demo_id": demo_id, "entry": "read", "instruction": instruction, "pending": None}, "read")


def start_build(demo_id: str) -> None:
    if not all(store.load(demo_id)["approvals"].values()):
        raise RuntimeError("Approve all six cards before building")
    if is_running(demo_id):
        raise RuntimeError("This demo is already being processed — wait for it to finish")
    orch._set_status(demo_id, "building")
    _submit(demo_id, {"type": "build"}, {"entry": "build", "pending": None}, "build")


def start_revise(demo_id: str, stage: str, instruction: str, rebuild: bool = False) -> None:
    if is_running(demo_id):
        raise RuntimeError("This demo is already being processed — wait for it to finish")
    prev_ready = store.load(demo_id)["status"] == "ready"  # read BEFORE the status flips, or a ready demo never rebuilds
    orch._set_status(demo_id, "reading" if stage in ("understand", "plan", "deck", "faq") and not rebuild and not prev_ready else "building")
    _submit(demo_id, {"type": "revise", "stage": stage, "instruction": instruction, "rebuild": rebuild},
            {"entry": "revise", "revise_stage": stage, "instruction": instruction, "rebuild": rebuild, "prev_ready": prev_ready, "pending": None}, "revise")


def handle_message(demo_id: str, message: str, attachments: list[dict], context: str = "align", wait: float = 150.0) -> dict:
    """Send a chat message into the workflow and wait for the agent's reply (the run continues in the background
    if the agent decided to revise or build)."""
    if is_running(demo_id):
        raise RuntimeError("Still working on the last change — give me a moment")
    req_id = uuid.uuid4().hex[:10]
    cmd = {"type": "message", "message": message, "attachments": attachments, "context": context, "req_id": req_id}
    since = events.latest_seq(demo_id)
    _submit(demo_id, cmd, {"entry": "message", "pending": cmd}, "align")
    t0 = time.time()
    while time.time() - t0 < wait:
        for ev in events.since(demo_id, since):
            if ev.get("type") == "align_reply" and ev.get("req_id") == req_id:
                return {"reply": ev.get("reply", ""), "actions": ev.get("actions", []), "notes": ev.get("notes", [])}
            if ev.get("type") == "phase_error":
                raise RuntimeError(ev.get("error", "failed"))
        if not is_running(demo_id) and not is_waiting(demo_id):
            break
        time.sleep(0.25)
    raise RuntimeError("The agent did not answer in time — check Observability for the call")


def mermaid() -> str:
    return graph.get_graph().draw_mermaid()
