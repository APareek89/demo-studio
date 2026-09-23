"""Actual graph + live socket ownership, with blocked providers and memory storage."""
import asyncio
import copy
import json
import socket
import sys
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import runtime_graph as graph, runtime_live, runtime_state, store

passed = []
def check(name, value):
    assert value, name
    passed.append(name)
    print("PASS", name)

class Socket:
    headers = {}
    query_params = {"session_id": "s_explore_race"}
    def __init__(self): self.queue, self.sent = asyncio.Queue(), []
    async def accept(self): pass
    async def receive_text(self): return await self.queue.get()
    async def send_json(self, event): self.sent.append(event)
    async def close(self, **kwargs): pass
    async def put(self, **event):
        await self.queue.put(json.dumps(event))
        for _ in range(12): await asyncio.sleep(0)

class Delivery:
    instances = []
    def __init__(self, *args):
        self.cancelled, self.registered = 0, []
        self.instances.append(self)
    async def cancel(self): self.cancelled += 1
    def register(self, value): self.registered.append(value)

class Adapter:
    instances = []
    def __init__(self, **kwargs):
        self.queue = asyncio.Queue()
        self.instances.append(self)
    async def __aenter__(self): return self
    async def aclose(self): pass
    async def events(self):
        while True: yield await self.queue.get()

async def until(predicate):
    for _ in range(1000):
        if predicate(): return
        await asyncio.sleep(.001)
    raise AssertionError("Expected local event did not occur")

async def main():
    # Valid pinned registry and reviewed settings keep this test on the real
    # pre-graph cache/delivery path while the planner and socket are controlled.
    snapshot_id = "kb_" + "a" * 24
    demo = {"id": "dm_fea00001", "settings": {"audience": "everyday", "language": "en-IN", "competition": "off"}}
    files = {"demo.json": demo, "bundle.json": {"version": 2, "knowledge_snapshot_id": snapshot_id},
             f"knowledge/snapshots/{snapshot_id}.json": {"id": snapshot_id, "facts": [], "competitors": []}}
    starts, finishes = {}, {}
    qa_started, qa_release = asyncio.Event(), asyncio.Event()
    def plan(_demo, profile, *_args, **_kwargs):
        name = profile["why"]
        starts[name] = True
        if not finishes[name].wait(3): raise AssertionError("Fixture release missing")
        return {"route": [{"segment_id": name}], "decision_frame": name}
    async def retrieve(_state): return {"evidence": [], "requested_scope": {}}
    async def reason(state):
        if state.get("question") == "hold":
            qa_started.set()
            await qa_release.wait()
        return {"decision": {"action": "answer", "answered": True, "sentences": [{"kind": "context", "text": "Let's check that together.", "fact_ids": []}]}}
    def blocked(*_a, **_kw): raise AssertionError("No outbound calls")
    with ExitStack() as stack:
        for name in ("create_connection",): stack.enter_context(patch.object(socket, name, blocked))
        for name in ("connect", "connect_ex"): stack.enter_context(patch.object(socket.socket, name, blocked))
        stack.enter_context(patch.object(store, "exists", return_value=True))
        stack.enter_context(patch.object(store, "load", side_effect=lambda _d: copy.deepcopy(demo)))
        stack.enter_context(patch.object(store, "read_json", side_effect=lambda _d, name: copy.deepcopy(files.get(name))))
        stack.enter_context(patch.object(store, "write_json", side_effect=lambda _d, name, value: files.__setitem__(name, copy.deepcopy(value))))
        stack.enter_context(patch.object(graph.pitch, "plan_pitch", side_effect=plan))
        stack.enter_context(patch.object(graph, "retrieve", retrieve))
        stack.enter_context(patch.object(graph, "reason", reason))
        stack.enter_context(patch.object(graph, "graph", graph.build_graph().compile()))
        stack.enter_context(patch.object(graph.usage, "trace"))
        stack.enter_context(patch.object(runtime_live, "DeliveryCoordinator", Delivery))
        stack.enter_context(patch("server.llm.sarvam_stream.RealtimeSTT", Adapter))
        ws = Socket()
        live = asyncio.create_task(runtime_live.live(ws, "dm_fea00001"))
        await ws.put(type="session.start", mic=False)
        async def start(name):
            finishes[name] = threading.Event()
            task = asyncio.create_task(graph.run_turn("dm_fea00001", {"session_id": "s_explore_race", "turn_id": name, "profile": {"why": name}}, kind="explore"))
            await until(lambda: starts.get(name))
            return task
        async def cancelled(task):
            try: await task
            except InterruptedError: return True
            return False

        pending = await start("overview_plan")
        await ws.put(type="turn.interrupt", turn_id="pause", preserve_planning=True)
        control = runtime_state._planning[("dm_fea00001", "s_explore_race")][1]
        check("media-only pause preserves actual in-flight HTTP Explore", not control.cancelled.is_set() and Delivery.instances[-1].cancelled > 0)
        finishes["overview_plan"].set()
        completed = await pending
        check("preserved planner completes its own checkpoint without starting WS narration", completed["result"]["route"][0]["segment_id"] == "overview_plan" and files["runtime/s_explore_race.json"]["phase"] == "ready_to_deliver" and not Delivery.instances[-1].registered and not any(e["type"] == "turn.result" for e in ws.sent))

        pending = await start("provider_onset")
        await ws.put(type="mic.set", enabled=True, input_generation=1)
        await Adapter.instances[-1].queue.put({"type": "input.speech_start"})
        await until(lambda: any(e["type"] == "input.speech_start" for e in ws.sent))
        control = runtime_state._planning[("dm_fea00001", "s_explore_race")][1]
        check("actual STT onset preserves Explore before any browser preservation flag arrives", not control.cancelled.is_set())
        finishes["provider_onset"].set()
        await pending
        await ws.put(type="mic.set", enabled=False, input_generation=1)

        older = await start("old_context")
        newer = await start("refined_context")
        finishes["old_context"].set()
        check("new Explore or refine cancels older context before publication", await cancelled(older) and files["runtime/s_explore_race.json"]["turn_id"] == "refined_context")
        finishes["refined_context"].set()
        await newer

        pending = await start("before_qa")
        await ws.put(type="turn.ask", turn_id="question", question="What should we check?")
        await until(lambda: any(e.get("turn_id") == "question" and e["type"] == "turn.result" for e in ws.sent))
        qa_checkpoint = copy.deepcopy(files["runtime/s_explore_race.json"])
        finishes["before_qa"].set()
        retained_plan = await pending
        check("actual WS question preserves pending personalized route without overwriting its checkpoint", retained_plan["result"]["route"][0]["segment_id"] == "before_qa" and files["runtime/s_explore_race.json"] == qa_checkpoint and qa_checkpoint["turn_id"] == "question")
        check("late planning completion cannot register speech during the customer wait", len(Delivery.instances[-1].registered) == 1 and Delivery.instances[-1].registered[0]["turn_id"] == "question")

        await ws.put(type="turn.ask", turn_id="held_qa", question="hold")
        await qa_started.wait()
        qa_control = runtime_state._owners[("dm_fea00001", "s_explore_race")][1]
        await ws.put(type="turn.interrupt", turn_id="pause_qa", preserve_planning=True)
        qa_release.set()
        check("preservation flag never keeps a QA turn alive", qa_control.cancelled.is_set() and not any(e.get("turn_id") == "held_qa" and e["type"] == "turn.result" for e in ws.sent))

        pending = await start("explicit_stop")
        await ws.put(type="turn.interrupt", turn_id="stop")
        finishes["explicit_stop"].set()
        check("ordinary Stop cancels pending planning", await cancelled(pending))

        pending = await start("close_session")
        await ws.put(type="session.end")
        await live
        finishes["close_session"].set()
        check("session close cancels pending planning and cannot publish it", await cancelled(pending) and files["runtime/s_explore_race.json"]["phase"] == "accepted")

asyncio.run(main())
print(f"Explore cancellation: {len(passed)}/{len(passed)} passed")
