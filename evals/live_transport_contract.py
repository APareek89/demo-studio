"""Free behavioral checks of the actual live route's capture ownership.
No socket network, provider call or production storage is used.
"""
import asyncio
from contextlib import ExitStack
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory(prefix="live-transport-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=scratch.name, DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import runtime_live, runtime_state

passed = []
def check(name, value):
    assert value, name
    passed.append(name)
    print("PASS", name)

class Socket:
    headers = {}
    query_params = {"session_id": "s_capture_test"}
    def __init__(self): self.queue, self.sent = asyncio.Queue(), []
    async def accept(self): pass
    async def receive_text(self): return await self.queue.get()
    async def send_json(self, event): self.sent.append(event)
    async def close(self, **kwargs): pass
    async def put(self, **event): await self.queue.put(json.dumps(event)); await settle()

class Adapter:
    instances = []
    def __init__(self, **kwargs):
        self.queue, self.audio, self.closed = asyncio.Queue(), [], False
        self.instances.append(self)
    async def __aenter__(self): return self
    async def aclose(self): self.closed = True
    async def send_audio(self, audio): self.audio.append(audio)
    async def events(self):
        while True:
            event = await self.queue.get()
            if event is None: return
            yield event

class Delivery:
    spoken = []
    cancellations = 0
    def __init__(self, demo_id, send): self.send = send
    async def cancel(self): Delivery.cancellations += 1
    def register(self, plan): pass
    async def speak(self, text, utterance_id, turn_id, language):
        self.spoken.append(text)
        await self.send({"type":"audio.chunk", "utterance_id":utterance_id, "turn_id":turn_id, "audio":"AAA=", "seq":0})
        await self.send({"type":"audio.end", "utterance_id":utterance_id, "turn_id":turn_id})

turn_bodies = []
async def fake_turn(demo_id, body):
    turn_bodies.append(dict(body))
    control = runtime_state.claim_turn(demo_id, body["session_id"], body["turn_id"])
    runtime_state.checkpoint({**body,"demo_id":demo_id,"control":control}, "accepted")
    return {"delivery":{"utterance_id":"u_"+body["turn_id"]},"result":{"answer":"Reviewed answer", "answered":True}}

async def settle():
    for _ in range(8): await asyncio.sleep(0)

async def main():
    socket = Socket()
    with patch.object(runtime_live.store, "exists", return_value=True), patch.object(runtime_live, "DeliveryCoordinator", Delivery), patch.object(runtime_live, "cancel_turn") as cancelled, patch.object(runtime_live, "run_turn", fake_turn), patch("server.llm.sarvam_stream.RealtimeSTT", Adapter), patch.object(runtime_live.usage, "trace"):
        task = asyncio.create_task(runtime_live.live(socket, "dm_test0001"))
        await socket.put(type="session.start", mic=False, input_mode="text")
        check("text session opens no provider", not Adapter.instances)
        check("session readiness reports selected text input mode", socket.sent[-1]["type"]=="session.ready" and socket.sent[-1]["input_mode"]=="text")
        await socket.put(type="mic.set", enabled=False, input_generation=0, input_mode="text")
        await socket.put(type="turn.ask", turn_id="text_first", question="A typed question", input_mode="voice")
        check("text mode owns runtime request metadata despite conflicting client payload", turn_bodies[-1]["input_mode"]=="text")
        check("text mode reaches the real isolated session checkpoint", runtime_state.previous_state("dm_test0001","s_capture_test").get("input_mode")=="text")
        await socket.put(type="delivery.speak", turn_id="text_first", text="Spoken in text mode", utterance_id="text_speech")
        check("text mode streams output while no STT adapter exists", not Adapter.instances and Delivery.spoken==["Spoken in text mode"] and socket.sent[-1]["type"]=="audio.end")
        await socket.put(type="mic.set", enabled=True, input_generation=1)
        first = Adapter.instances[-1]
        check("mic readiness belongs to the requested capture", socket.sent[-1]["type"] == "mic.ready" and socket.sent[-1]["input_generation"] == 1 and socket.sent[-1]["input_mode"]=="voice")
        for index in range(3):
            await socket.put(type="turn.ask", turn_id=f"voice_{index}", question=f"Voice question {index}")
        check("one voice adapter survives three independent runtime turns", len(Adapter.instances)==1 and not first.closed and all(body["input_mode"]=="voice" for body in turn_bodies[-3:]))
        check("voice selection persists in the actual latest checkpoint", runtime_state.previous_state("dm_test0001","s_capture_test").get("input_mode")=="voice")
        before_cancel = cancelled.call_count
        before_delivery = Delivery.cancellations
        for event in ({"type":"input.speech_start","input_id":"impact"}, {"type":"input.speech_end","input_id":"impact"},
                      {"type":"transcript.partial","input_id":"impact","text":"[noise]"}, {"type":"transcript.final","input_id":"impact","text":"..."}):
            await first.queue.put(event)
        await settle()
        check("raw VAD and noise-only transcripts never cancel server delivery or planning",cancelled.call_count == before_cancel)
        await first.queue.put({"type":"transcript.partial","input_id":"real","text":"Warranty"}); await settle()
        check("meaningful partial is forwarded without cancelling server planning or output",cancelled.call_count == before_cancel and Delivery.cancellations == before_delivery and socket.sent[-1]["text"] == "Warranty")
        await first.queue.put({"type":"input.speech_start","input_id":"real"})
        await first.queue.put({"type":"transcript.partial","input_id":"real","text":"Warranty coverage"})
        await first.queue.put({"type":"transcript.final","input_id":"real","text":"Warranty coverage?"})
        await first.queue.put({"type":"transcript.final","input_id":"real","text":"Warranty coverage?"}); await settle()
        check("final and duplicated recognition events alone never take server turn ownership",cancelled.call_count == before_cancel and Delivery.cancellations == before_delivery)
        await first.queue.put({"type":"transcript.final","input_id":"short","text":"हाँ"}); await settle()
        check("short multilingual final waits for the player's qualified interrupt command",cancelled.call_count == before_cancel and Delivery.cancellations == before_delivery and socket.sent[-1]["text"] == "हाँ")
        await socket.put(type="turn.interrupt",turn_id="manual_interrupt",preserve_planning=True)
        check("explicit interruption still cancels immediately without speech evidence",cancelled.call_count == before_cancel + 1 and Delivery.cancellations == before_delivery + 1 and cancelled.call_args.kwargs == {"preserve_planning":True} and socket.sent[-1]["type"] == "turn.cancelled")
        before_fragment = cancelled.call_count
        for event in ({"type":"transcript.partial","input_id":"fragment","text":"It’s"},
                      {"type":"transcript.final","input_id":"fragment","text":"[noise]"},
                      {"type":"transcript.final","input_id":"tv","text":"Breaking news on television"}):
            await first.queue.put(event)
        await settle()
        check("fragment then noise and unrelated TV finals remain observational on server",cancelled.call_count == before_fragment and socket.sent[-1]["text"] == "Breaking news on television")
        finals_before = len([event for event in socket.sent if event.get("type") == "transcript.final"])
        await first.queue.put({"type":"transcript.final","text":"yes"})
        await first.queue.put({"type":"transcript.final","text":"yes"}); await settle()
        check("server preserves repeated unowned yes finals for client qualification",len([event for event in socket.sent if event.get("type") == "transcript.final"]) == finals_before + 2 and cancelled.call_count == before_fragment)
        await first.queue.put({"type": "transcript.final", "text": "First answer", "input_id": "1"}); await settle()
        check("transcript carries adapter capture generation", socket.sent[-1]["input_generation"] == 1 and socket.sent[-1]["text"] == "First answer")
        await socket.put(type="mic.set", enabled=False, input_generation=1)
        await socket.put(type="turn.ask", turn_id="text_after_off", question="Typed after switching off")
        check("explicit microphone off records text mode for following turns", first.closed and turn_bodies[-1]["input_mode"]=="text" and runtime_state.previous_state("dm_test0001","s_capture_test").get("input_mode")=="text")
        await socket.put(type="mic.set", enabled=True, input_generation=2)
        second = Adapter.instances[-1]
        check("unmute closes previous adapter and creates a new one", first.closed and second is not first and not second.closed)
        await socket.put(type="mic.set", enabled=False, input_generation=1)
        await socket.put(type="audio.input", audio="old", input_generation=1)
        await socket.put(type="audio.input", audio="unowned")
        await socket.put(type="audio.input", audio="new", input_generation=2)
        check("old mute and queued PCM cannot affect new capture", not second.closed and second.audio == ["new"])
        await socket.put(type="turn.ask", turn_id="voice_after_stale_off", question="Current voice question")
        check("obsolete microphone off cannot relabel the current voice session", turn_bodies[-1]["input_mode"]=="voice")
        await socket.put(type="mic.set", enabled=True, input_generation=1)
        check("older enable cannot replace current adapter", len(Adapter.instances) == 2)
        await second.queue.put({"type": "transcript.final", "text": "New answer", "input_id": "1"}); await settle()
        check("new adapter final belongs to current generation", socket.sent[-1]["input_generation"] == 2 and socket.sent[-1]["text"] == "New answer")
        await second.queue.put(None); await settle()
        check("normal provider end reports owned failure and releases adapter", second.closed and socket.sent[-1]["code"] == "microphone_stream" and socket.sent[-1]["input_generation"] == 2)
        await socket.put(type="turn.ask", turn_id="after_failure", question="Typed after capture failure")
        check("capture failure falls back to text metadata without closing transport", turn_bodies[-1]["input_mode"]=="text" and socket.sent[-1]["type"]=="turn.result")
        await socket.put(type="mic.set", enabled=True, input_generation=3)
        await socket.put(type="turn.ask", turn_id="last_voice", question="Last voice turn")
        await socket.put(type="session.end")
        await task
        check("session teardown does not relabel the completed voice checkpoint", runtime_state.previous_state("dm_test0001","s_capture_test").get("input_mode")=="voice" and Adapter.instances[-1].closed)

with ExitStack() as blocked:
    for target in ("socket.create_connection", "socket.getaddrinfo", "socket.socket.connect", "socket.socket.connect_ex", "socket.socket.sendto"):
        blocked.enter_context(patch(target, side_effect=AssertionError("Sockets blocked")))
    asyncio.run(main())
print(f"Live transport: {len(passed)}/{len(passed)} passed")
scratch.cleanup()
