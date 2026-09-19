"""Free behavioral checks of the actual live route's capture ownership.
No socket network, provider call or production storage is used.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory(prefix="live-transport-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=scratch.name)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import runtime_live

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
    def __init__(self, *args): pass
    async def cancel(self): pass

async def settle():
    for _ in range(8): await asyncio.sleep(0)

async def main():
    socket = Socket()
    with patch.object(runtime_live.store, "exists", return_value=True), patch.object(runtime_live, "DeliveryCoordinator", Delivery), patch.object(runtime_live, "cancel_turn"), patch("server.llm.sarvam_stream.RealtimeSTT", Adapter), patch.object(runtime_live.usage, "trace"):
        task = asyncio.create_task(runtime_live.live(socket, "dm_test"))
        await socket.put(type="session.start", mic=False)
        check("text session opens no provider", not Adapter.instances)
        await socket.put(type="mic.set", enabled=True, input_generation=1)
        first = Adapter.instances[-1]
        check("mic readiness belongs to the requested capture", socket.sent[-1]["type"] == "mic.ready" and socket.sent[-1]["input_generation"] == 1)
        await first.queue.put({"type": "transcript.final", "text": "First answer", "input_id": "1"}); await settle()
        check("transcript carries adapter capture generation", socket.sent[-1]["input_generation"] == 1 and socket.sent[-1]["text"] == "First answer")
        await socket.put(type="mic.set", enabled=False, input_generation=1)
        await socket.put(type="mic.set", enabled=True, input_generation=2)
        second = Adapter.instances[-1]
        check("unmute closes previous adapter and creates a new one", first.closed and second is not first and not second.closed)
        await socket.put(type="mic.set", enabled=False, input_generation=1)
        await socket.put(type="audio.input", audio="old", input_generation=1)
        await socket.put(type="audio.input", audio="unowned")
        await socket.put(type="audio.input", audio="new", input_generation=2)
        check("old mute and queued PCM cannot affect new capture", not second.closed and second.audio == ["new"])
        await socket.put(type="mic.set", enabled=True, input_generation=1)
        check("older enable cannot replace current adapter", len(Adapter.instances) == 2)
        await second.queue.put({"type": "transcript.final", "text": "New answer", "input_id": "1"}); await settle()
        check("new adapter final belongs to current generation", socket.sent[-1]["input_generation"] == 2 and socket.sent[-1]["text"] == "New answer")
        await second.queue.put(None); await settle()
        check("normal provider end reports owned failure and releases adapter", second.closed and socket.sent[-1]["code"] == "microphone_stream" and socket.sent[-1]["input_generation"] == 2)
        await socket.put(type="session.end")
        await task

asyncio.run(main())
print(f"Live transport: {len(passed)}/{len(passed)} passed")
scratch.cleanup()
