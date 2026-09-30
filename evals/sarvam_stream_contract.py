"""Free streaming protocol/cancellation checks, with every network connection faked."""
import asyncio
import base64
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.llm import sarvam_stream as stream


class Socket:
    def __init__(self, events):
        self.events = iter(events)
        self.sent = []
        self.closed = False

    async def send(self, raw):
        self.sent.append(json.loads(raw))

    async def recv(self):
        return json.dumps(next(self.events))

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return json.dumps(next(self.events))
        except StopIteration:
            raise StopAsyncIteration

    async def close(self):
        self.closed = True


class Connection:
    def __init__(self, socket):
        self.socket = socket

    def __await__(self):
        async def value():
            return self.socket
        return value().__await__()

    async def __aenter__(self):
        return self.socket

    async def __aexit__(self, *_):
        await self.socket.close()


async def main():
    checks = []
    def check(name, ok):
        checks.append(bool(ok))
        print(("PASS " if ok else "FAIL ") + name)
    pcm = base64.b64encode(b"\0\0" * 100).decode()
    events = [{"event": "vad.speech_start"}, {"event": "transcript.partial", "text": "boot"},
              {"event": "vad.speech_end"}, {"event": "transcript.final", "text": "boot space", "start_s": 0.1, "end_s": 0.7},
              {"event": "session.end", "audio_duration_s": 1.2}]
    socket = Socket(events)
    with patch.object(stream.config, "MOCK_LLM", False), patch.object(stream.config, "SARVAM_API_KEY", "fake-contract-key"), \
         patch.object(stream.usage, "record") as record, patch.object(stream.usage, "trace"), \
         patch.object(stream.websockets, "connect", return_value=Connection(socket)) as connect:
        async with stream.RealtimeSTT("en-IN") as stt:
            await stt.send_audio(pcm)
            received = [event async for event in stt.events()]
        check("realtime endpoint and PCM format selected", "/speech-to-text-realtime/ws?" in connect.call_args.args[0] and "encoding=linear16" in connect.call_args.args[0])
        check("STT passes bounded base64 PCM without WAV header", socket.sent[0] == {"event": "audio_input", "audio": pcm})
        check("VAD and transcript events normalize in order", [e["type"] for e in received] == ["input.speech_start", "transcript.partial", "input.speech_end", "transcript.final"])
        check("partial/final share input identity", len({e["input_id"] for e in received}) == 1)
        check("provider billing duration wins over sent estimate", record.call_args.kwargs["seconds"] == 1.2)
        check("STT close is explicit and releases socket", socket.closed and socket.sent[-1] == {"event": "end"})
    socket = Socket([{"event": "transcript.final", "text": "yes"}, {"event": "vad.speech_start"}, {"event": "transcript.final", "text": "yes"}, {"event": "transcript.final", "text": "yes"}])
    with patch.object(stream.config, "MOCK_LLM", False), patch.object(stream.config, "SARVAM_API_KEY", "fake-contract-key"), \
         patch.object(stream.usage, "record"), patch.object(stream.usage, "trace"), \
         patch.object(stream.websockets, "connect", return_value=Connection(socket)):
        async with stream.RealtimeSTT() as stt:
            finals = [event async for event in stt.events() if event["type"] == "transcript.final"]
        check("missing VAD identity cannot permanently dedupe repeated customer words", "input_id" not in finals[0] and finals[1]["input_id"] == "1" and "input_id" not in finals[2])
    socket = Socket([])
    with patch.object(stream.config, "MOCK_LLM", False), patch.object(stream.config, "SARVAM_API_KEY", "fake-contract-key"), \
         patch.object(stream.usage, "record") as record, patch.object(stream.usage, "trace"), \
         patch.object(stream.websockets, "connect", return_value=Connection(socket)):
        async with stream.RealtimeSTT() as stt:
            await stt.send_audio(base64.b64encode(bytes(32000)).decode())
        frames = [base64.b64decode(e["audio"]) for e in socket.sent if e.get("event") == "audio_input"]
        check("one-second caller PCM is split below provider fast-mode frame cap", len(frames) == 10 and all(len(f) == 3200 for f in frames))
        check("split PCM preserves exactly the submitted duration", b"".join(frames) == bytes(32000) and record.call_args.kwargs["seconds"] == 1)
    for cancel in (False, True):
        socket = Socket([{"type": "audio", "data": {"audio": pcm}}, {"type": "event", "data": {"event_type": "final"}}])
        with patch.object(stream.config, "MOCK_LLM", False), patch.object(stream.config, "SARVAM_API_KEY", "fake-contract-key"), \
             patch.object(stream.usage, "record") as record, patch.object(stream.usage, "trace"), \
             patch.object(stream.websockets, "connect", return_value=Connection(socket)):
            generator = stream.stream_tts("Reviewed answer", speaker="priya")
            first = await anext(generator)
            if cancel:
                await generator.aclose()
            else:
                remainder = [event async for event in generator]
                check("provider final terminates TTS without silence timer", remainder == [])
            check(f"TTS {'cancel' if cancel else 'complete'} closes socket", socket.closed)
            check(f"TTS {'cancel' if cancel else 'complete'} retains selected voice and raw PCM", socket.sent[0]["data"]["speaker"] == "priya" and socket.sent[0]["data"]["output_audio_codec"] == "linear16" and first["sample_rate"] == 24000)
            check(f"TTS {'cancel' if cancel else 'complete'} explicitly requests 128k without changing PCM bytes", socket.sent[0]["data"]["output_audio_bitrate"] == "128k" and first["audio"] == pcm and first["format"] == "pcm_s16le")
            check(f"TTS {'cancel' if cancel else 'complete'} accounts submitted characters", record.call_args.kwargs["chars"] == len("Reviewed answer"))
    with patch.object(stream.config, "MOCK_LLM", True), patch.object(stream.websockets, "connect", side_effect=AssertionError("network forbidden")) as connect:
        chunks = [event async for event in stream.stream_tts("Mock answer")]
        async with stream.RealtimeSTT() as stt:
            await stt.send_audio(pcm)
        check("mock mode never opens provider connection", len(chunks) == 3 and not connect.called)
    print(f"Sarvam streaming: {sum(checks)}/{len(checks)} passed")
    return all(checks)


if __name__ == "__main__":
    raise SystemExit(0 if asyncio.run(main()) else 1)
