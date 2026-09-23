"""The demo-building workflow as ONE LangGraph graph.

    START ─▶ router ─▶ understand ─▶ coach ─▶ plan ─▶ author ─▶ deck ─▶ faq ─▶ align_enter ─▶ align_wait ◀─┐ (interrupt: waits for you)
                 │                                                                   │  message / approve / revise ─┘
                 │                                                                   └─ build ─▶ voice ─▶ bundle ─▶ finish ─▶ END
                 ├─ build  ─▶ author (skips when done) ─▶ deck (skips when done) ─▶ faq …
                 └─ revise ─▶ understand | coach | plan | author | deck | faq (then back to align_wait)

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


# Carry instructions about which build step should run; large artifacts stay in JSON files.
# Input: demo ID, action and revision details. Output: the small state shared by graph nodes.
# Linked: server/orchestrator.py:_run_stage runs agents; server/store.py:read_json loads their saved outputs.
class DemoState(TypedDict, total=False):
    demo_id: str
    entry: str            # read | build | revise | message
    instruction: str      # for understand / coach / plan / author when revising
    revise_stage: str     # understand | coach | plan | author
    rebuild: bool         # revise and then run the build chain
    prev_ready: bool      # the demo was ready before this revision → rebuild after
    pending: Optional[dict]  # a user command carried in with the input (message/build/revise) instead of via interrupt


# ---------- nodes ----------

# Choose the first node for a read, build, revision or review message.
# Input: DemoState.entry and revise_stage. Output: a Command naming the next node.
# Linked: server/app.py:read_sources and build enter this graph through start_read/start_build.
def router(state: DemoState) -> Command:
    e = state.get("entry", "read")
    if e == "read":
        return Command(goto="understand")
    if e == "build":
        return Command(goto="author")
    if e == "revise":
        return Command(goto=state.get("revise_stage") or "author")
    return Command(goto="align_wait")


# Read source material unless a completed, unchanged understanding can be reused.
# Input: demo ID and optional instruction. Output: saved understanding.json; the node itself returns no state changes.
# Linked: server/orchestrator.py:_run_stage calls server/agents/understand.py:run.
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
    return {}


# Prepare the category playbook using only approved evidence.
# Input: demo ID and any Coach revision. Output: playbook.json, reused when its inputs are unchanged.
# Linked: server/agents/coach.py owns mapping, validation and caching.
def coach(state: DemoState) -> dict:
    """Map approved evidence to the category playbook before planning."""
    d = state["demo_id"]
    orch._set_status(d, "reading")
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "coach" else ""
    orch._run_stage(d, "coach", instr)
    return {}


# Create the story outline, then prepare the persona preview for review.
# Input: demo ID and any Plan revision. Output: plan.json and, when available, sample voice/mascot assets.
# Linked: server/orchestrator.py:_run_stage and _persona_sample call the Planner and media helpers.
def plan(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "reading")
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "plan" else ""
    orch._run_stage(d, "plan", instr)
    orch._persona_sample(d)
    return {}


# Tell the user that draft content is ready for review and mark this phase complete.
# Input: demo ID and entry action. Output: align status, a saved opening message on Read, and UI events.
# Linked: server/agents/align.py:opening_message and server/events.py:publish supply the review handoff.
def align_enter(state: DemoState) -> dict:
    """Back to the human: status align, opening message on a fresh read, run-log marker."""
    d = state["demo_id"]
    orch._set_status(d, "align")
    if state.get("entry") == "read":
        orch.approve_empty_faq(d)
        text = align.opening_message(d)
        orch._append_conversation(d, "agent", text)
        runlog.event(d, "Agent opening message", text)
        runlog.phase_done(d, "read")
        events.publish(d, "phase_done", phase="read")
    else:
        runlog.phase_done(d, "revise")
        events.publish(d, "phase_done", phase="revise")
    return {}


# Pause the graph until the user reviews, requests a revision or asks to build.
# Input: a pending/resumed command and saved approvals. Output: updated routing state and the next node.
# Linked: server/orchestrator.py:respond applies review actions; server/store.py:load checks approvals.
def align_wait(state: DemoState) -> Command:
    """The human checkpoint. Waits (interrupt) for a chat message, a build request or a revision; acts on it; routes."""
    d = state["demo_id"]
    cmd = state.get("pending") or interrupt({"demo_id": d, "status": store.load(d)["status"], "approvals": store.load(d)["approvals"]})
    update = {"pending": None, "instruction": "", "rebuild": False}
    kind = (cmd or {}).get("type")
    # Process a review message before deciding whether to stay paused or revise/build.
    # Input: message text and attachments. Output: a reply event plus any requested route change.
    # Linked: server/orchestrator.py:respond returns the actions and build/revision requests.
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
    # Check saved human approvals again at the review checkpoint.
    # Input: Build command and demo approvals. Output: Author reuse/build route or a review error event.
    # Linked: server/store.py:load reads the same approval flags used by server/app.py:build.
    if kind == "build":
        if all(store.load(d)["approvals"].values()):
            return Command(goto="author", update={**update, "entry": "build"})
        events.publish(d, "phase_error", phase="build", error="Approve all six cards before building")
        return Command(goto="align_wait", update=update)
    if kind == "revise":
        stage = cmd.get("stage") or "author"
        return Command(goto=stage, update={**update, "entry": "revise", "revise_stage": stage, "instruction": cmd.get("instruction", ""), "rebuild": bool(cmd.get("rebuild")), "prev_ready": store.load(d)["status"] == "ready"})
    return Command(goto="align_wait", update=update)


# Write the spoken script, or reuse a completed script when the user builds approved content.
# Input: demo ID and any Author revision. Output: script.json; an unchanged build skips generation.
# Linked: server/orchestrator.py:_run_stage calls server/agents/author.py:run.
def author(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "building" if state.get("entry") == "build" else "reading")
    if state.get("entry") == "build":
        runlog.event(d, "BUILD started", "All six cards approved. Voice (narration + uploaded FAQ answers + fillers) → bundle. Rehearsal is available on demand.")
        if store.load(d)["stages"]["author"]["status"] == "done":
            return {}
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "author" else ""
    orch._run_stage(d, "author", instr)
    return {}


# Create slides from the script, keeping completed slides during an unchanged build.
# Input: demo ID and any Deck instruction. Output: deck.json or reuse of the existing deck.
# Linked: server/orchestrator.py:_run_stage calls server/agents/deck.py:build.
def deck(state: DemoState) -> dict:
    d = state["demo_id"]
    if state.get("entry") == "build" and store.load(d)["stages"]["deck"]["status"] == "done":
        return {}
    orch._set_status(d, "building" if state.get("entry") == "build" else "reading")
    instr = state.get("instruction", "") if state.get("entry") == "revise" and state.get("revise_stage") == "deck" else ""
    orch._run_stage(d, "deck", instr)
    return {}


# Record speech only when the saved voice inputs are new or incomplete.
# Input: script, voice settings and their hash. Output: audio files and audio links in saved artifacts.
# Linked: server/agents/voice.py:input_hash and render_script provide reuse and recording.
def voice(state: DemoState) -> dict:
    orch._set_status(state["demo_id"], "building")
    if (store.load(state["demo_id"])["stages"]["voice"]["status"] == "done"
            and (store.read_json(state["demo_id"], "script.json") or {}).get("voice_input_hash") == orch.voice.input_hash(state["demo_id"])):
        return {}  # A visual-only revision does not re-record approved speech.
    orch._run_stage(state["demo_id"], "voice", "")
    return {}


# Assemble the reviewed content and recordings into the published player package.
# Input: demo ID. Output: bundle.json with resolved media URLs and a pinned knowledge snapshot.
# Linked: server/orchestrator.py:_run_stage calls server/agents/bundle.py:build.
def bundle(state: DemoState) -> dict:
    orch._run_stage(state["demo_id"], "bundle", "")
    return {}


# Mark a successfully published demo ready and tell the UI that Build finished.
# Input: demo ID. Output: ready status, a completion event and an optional cloud-sync request.
# Linked: server/runlog.py:phase_done, server/events.py:publish and server/cloud.py:sync_demo_async.
def finish(state: DemoState) -> dict:
    d = state["demo_id"]
    orch._set_status(d, "ready")
    runlog.phase_done(d, "build")
    cloud.sync_demo_async(d)
    events.publish(d, "phase_done", phase="build")
    return {}


# ---------- routing ----------

# Continue from the story outline to the spoken script.
# Input: graph state. Output: the Author node name.
# Linked: server/agents/author.py:run consumes the plan saved by server/agents/plan.py:run.
def after_plan(state: DemoState) -> str:
    return "author"  # the script is part of Align now: plan → author → deck → faq → align


# Choose the next stage after Deck; the helper name predates the Deck node.
# Input: build mode, approvals and FAQ completion. Output: voice for a ready bank, otherwise faq.
# Linked: server/store.py:load supplies stage status; build_graph wires this helper after deck.
def after_author(state: DemoState) -> str:
    if state.get("entry") == "build" and all(store.load(state["demo_id"])["approvals"].values()):
        d = state["demo_id"]
        return "voice" if _faq_current(d) else "faq"
    return "faq"


def _faq_current(demo_id: str) -> bool:
    """Legacy guessed-question banks reconcile once before current reuse."""
    return (store.load(demo_id)["stages"]["faq"]["status"] == "done"
            and (store.read_json(demo_id, "faq.json") or {}).get("question_policy") == orch.faq.QUESTION_POLICY)


# Prepare likely questions and answers, reusing a completed bank unless explicitly retried.
# Input: demo ID and FAQ retry instruction. Output: faq.json, with answers and related slide IDs.
# Linked: server/orchestrator.py:_run_stage calls server/agents/faq.py:run.
def faq(state: DemoState) -> dict:
    d = state["demo_id"]
    explicit_retry = state.get("entry") == "revise" and state.get("revise_stage") == "faq"
    if _faq_current(d) and not explicit_retry:
        return {}
    orch._set_status(d, "building" if state.get("entry") == "build" else "reading")
    orch._run_stage(d, "faq", state.get("instruction", "") if explicit_retry else "")
    return {}


# Publish voiced content; optional rehearsal is a separate explicit action.
def after_voice(state: DemoState) -> str:
    return "bundle"


# Choose between publishing approved content and returning draft content for human review.
# Input: entry action and all saved approvals. Output: voice or align_enter.
# Linked: server/store.py:load reads the approvals maintained by server/orchestrator.py:apply_actions.
def after_faq(state: DemoState) -> str:
    return "voice" if state.get("entry") == "build" and all(store.load(state["demo_id"])["approvals"].values()) else "align_enter"


# Register each node and connect the actual read, review and build routes.
# Input: DemoState and node functions. Output: an uncompiled StateGraph; helpers decide conditional routes.
# Linked: node wrappers delegate to server/orchestrator.py:_run_stage rather than carrying artifacts in state.
def build_graph() -> StateGraph:
    g = StateGraph(DemoState)
    g.add_node("router", router, destinations=("understand", "coach", "author", "plan", "deck", "faq", "align_wait"))
    g.add_node("understand", understand)
    g.add_node("coach", coach)
    g.add_node("plan", plan)
    g.add_node("align_enter", align_enter)
    g.add_node("align_wait", align_wait, destinations=("align_wait", "understand", "coach", "plan", "author", "deck", "faq"))
    g.add_node("author", author)
    g.add_node("deck", deck)
    g.add_node("faq", faq)
    g.add_node("voice", voice)
    g.add_node("bundle", bundle)
    g.add_node("finish", finish)
    g.add_edge(START, "router")
    g.add_edge("understand", "coach")
    g.add_edge("coach", "plan")
    g.add_conditional_edges("plan", after_plan, {"author": "author"})
    g.add_edge("align_enter", "align_wait")
    g.add_edge("author", "deck")
    g.add_conditional_edges("deck", after_author, {"voice": "voice", "faq": "faq"})
    g.add_conditional_edges("faq", after_faq, {"voice": "voice", "align_enter": "align_enter"})
    g.add_conditional_edges("voice", after_voice, {"bundle": "bundle"})
    g.add_edge("bundle", "finish")
    g.add_edge("finish", END)
    return g


# ---------- runtime: one compiled graph, one sqlite checkpointer, one thread per running demo ----------

# Keep graph checkpoints in SQLite and compile the workflow once when this module loads.
# Input: server/config.py:GRAPH_DB. Output: the compiled graph and per-process worker registry.
# Linked: server/store.py keeps plan/script/media separately; checkpoints track graph progress, not those file contents.
_conn = sqlite3.connect(str(config.GRAPH_DB), check_same_thread=False)
checkpointer = SqliteSaver(_conn)
graph = build_graph().compile(checkpointer=checkpointer)
_threads: dict[str, threading.Thread] = {}
_lock = threading.Lock()


# Give LangGraph the stable checkpoint identity for this demo.
# Input: demo ID. Output: a configurable thread_id dictionary.
# Linked: server/store.py:demo_dir uses the same demo identity for the separate artifact files.
def _cfg(demo_id: str) -> dict:
    return {"configurable": {"thread_id": demo_id}}


# Check whether this process still has a live build worker for the demo.
# Input: demo ID. Output: true or false; this is process-local worker state.
# Linked: server/orchestrator.py:is_running and server/app.py use it to avoid overlapping work.
def is_running(demo_id: str) -> bool:
    t = _threads.get(demo_id)
    return bool(t and t.is_alive())


# Check whether a saved graph checkpoint is paused at human review.
# Input: demo ID. Output: true when Align has an outstanding interrupt, otherwise false.
# Linked: server/app.py:workflow reports waiting demos; _submit() uses this to resume a paused build.
def is_waiting(demo_id: str) -> bool:
    """True when the graph is parked at the Align checkpoint for this demo."""
    try:
        st = graph.get_state(_cfg(demo_id))
        return bool(st.next) and "align_wait" in st.next and any(getattr(t, "interrupts", None) for t in st.tasks)
    except Exception:
        return False


# Invoke the graph and make uncaught build failures visible to the user.
# Input: demo ID, initial/resume payload and phase. Output: node side effects or saved error status/logs.
# Linked: server/orchestrator.py:_set_status, server/events.py:publish and server/store.py:log record failure.
def _run(demo_id: str, payload, phase: str) -> None:
    try:
        graph.invoke(payload, _cfg(demo_id))
    except Exception as e:
        orch._set_status(demo_id, "error")
        events.publish(demo_id, "phase_error", phase=phase, error=str(e)[:400])
        store.log(demo_id, "error-graph", {"phase": phase, "error": str(e)})


# Start one background graph worker, refusing a second worker for the same demo.
# Input: demo ID, payload and phase. Output: a running thread registered for that demo.
# Linked: server/app.py read/build/revise routes return while server/events.py streams progress.
def _spawn(demo_id: str, payload, phase: str) -> None:
    with _lock:
        if is_running(demo_id):
            raise RuntimeError("This demo is already being processed — wait for it to finish")
        t = threading.Thread(target=_run, args=(demo_id, payload, phase), daemon=True, name=f"graph-{demo_id}")
        _threads[demo_id] = t
        t.start()


# Resume the paused review checkpoint when possible, otherwise start a fresh graph entry.
# Input: command plus fresh-run state. Output: a spawned graph worker with the appropriate payload.
# Linked: server/orchestrator.py:apply_actions requests revisions/builds through the public entry helpers.
def _submit(demo_id: str, cmd: dict, fresh: dict, phase: str) -> None:
    """Deliver a command: resume the parked checkpoint when there is one, otherwise start a new run."""
    if is_waiting(demo_id):
        _spawn(demo_id, Command(resume=cmd), phase)
    else:
        _spawn(demo_id, {"demo_id": demo_id, **fresh}, phase)


# Start source understanding and draft creation, showing reading status immediately.
# Input: demo ID and optional instruction. Output: a background Read run starting at Understand.
# Linked: server/app.py:read_sources calls this; server/orchestrator.py:_set_status updates demo.json.
def start_read(demo_id: str, instruction: str = "") -> None:
    orch._set_status(demo_id, "reading")  # synchronous, so the UI and any poller see it before the thread starts
    _spawn(demo_id, {"demo_id": demo_id, "entry": "read", "instruction": instruction, "pending": None}, "read")


# Require all six approvals and an idle worker before accepting Build.
# Input: demo ID. Output: a resumed/new build run, or a clear refusal.
# Linked: server/app.py:build and server/orchestrator.py:apply_actions call this entry point.
def start_build(demo_id: str) -> None:
    if not all(store.load(demo_id)["approvals"].values()):
        raise RuntimeError("Approve all six cards before building")
    if is_running(demo_id):
        raise RuntimeError("This demo is already being processed — wait for it to finish")
    orch._set_status(demo_id, "building")
    _submit(demo_id, {"type": "build"}, {"entry": "build", "pending": None}, "build")


def _run_rehearsal(demo_id: str) -> None:
    """Review on request without replacing the build checkpoint or published status."""
    try:
        orch._run_stage(demo_id, "rehearsal", "")
        runlog.phase_done(demo_id, "rehearsal")
        events.publish(demo_id, "phase_done", phase="rehearsal")
    except Exception as exc:
        events.publish(demo_id, "phase_error", phase="rehearsal", error=str(exc)[:400])
        store.log(demo_id, "error-rehearsal", {"error": str(exc)})


def start_rehearsal(demo_id: str) -> None:
    """Serialize an explicit rehearsal with Read/Build without resuming their graph."""
    with _lock:
        if is_running(demo_id):
            raise RuntimeError("This demo is already being processed — wait for it to finish")
        if not (store.read_json(demo_id, "script.json") or {}).get("segments"):
            raise RuntimeError("Prepare a script before rehearsing")
        worker = threading.Thread(target=_run_rehearsal, args=(demo_id,), daemon=True, name=f"rehearsal-{demo_id}")
        _threads[demo_id] = worker
        worker.start()


# Send a requested stage revision back through the human review workflow.
# Input: demo ID, stage, instruction and rebuild flag. Output: a revision command and reading status.
# Linked: server/app.py:revise and server/orchestrator.py:apply_actions supply the revision request.
def start_revise(demo_id: str, stage: str, instruction: str, rebuild: bool = False) -> None:
    if is_running(demo_id):
        raise RuntimeError("This demo is already being processed — wait for it to finish")
    prev_ready = store.load(demo_id)["status"] == "ready"  # read BEFORE the status flips, or a ready demo never rebuilds
    orch._set_status(demo_id, "reading")  # Every revision returns through human Align, even from Ready.
    _submit(demo_id, {"type": "revise", "stage": stage, "instruction": instruction, "rebuild": rebuild},
            {"entry": "revise", "revise_stage": stage, "instruction": instruction, "rebuild": rebuild, "prev_ready": prev_ready, "pending": None}, "revise")


# Submit one review conversation turn and wait for its matching reply event.
# Input: message, attachments and review context. Output: reply/actions/notes, or a timeout/error.
# Linked: server/orchestrator.py:respond generates the reply; server/events.py:since returns its event.
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


# Describe the compiled graph as Mermaid text for the workflow viewer.
# Input: the compiled graph. Output: diagram source, not a new build run.
# Linked: server/app.py:workflow exposes this representation to the UI.
def mermaid() -> str:
    return graph.get_graph().draw_mermaid()
