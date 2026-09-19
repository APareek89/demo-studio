"""Cancellable Sarvam realtime adapters; no browser credentials or REST pacing.

Protocol references (checked 2026-09-19):
https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming
https://docs.sarvam.ai/api-reference/text-to-speech/stream
The TTS socket has no clear/cancel command: cancelling closes this utterance's socket.
"""
from __future__ import annotations

import asyncio
import base64
import json
import time
from urllib.parse import urlencode

import websockets

from .. import config, usage
from .sarvam import SPEAKERS, lang_code

RATE = 24000


def _headers():
    if not config.SARVAM_API_KEY:
        raise RuntimeError("Sarvam streaming is unavailable: API key is not configured")
    return {"api-subscription-key": config.SARVAM_API_KEY}


class RealtimeSTT:
    """One continuous PCM16/16k mono input; events never invoke an answer themselves."""

    def __init__(self, language="en-IN"):
        self.language = "or-IN" if lang_code(language) == "od-IN" else lang_code(language)
        self.ws = None
        self.started = time.monotonic()
        self.audio_bytes = 0
        self.billed_seconds = None
        self.input_index = 0
        self.input_open = False
        self.closed = False
        self._recorded = False
        self._mock_closed = asyncio.Event()

    async def __aenter__(self):
        if config.MOCK_LLM:
            return self
        query = urlencode(dict(language_code=self.language, model="saaras:v3-realtime",
                               stream_type="fast", mode="transcribe", endpointing="vad",
                               encoding="linear16", sample_rate=16000, threshold=0.5,
                               silence_duration_ms=700, min_speech_duration_ms=180,
                               return_timestamps="true"))
        self.ws = await websockets.connect("wss://api.sarvam.ai/speech-to-text-realtime/ws?" + query,
                                           additional_headers=_headers(), open_timeout=8,
                                           close_timeout=2, ping_interval=20, max_size=1024 * 1024)
        return self

    async def __aexit__(self, *_):
        await self.aclose()

    async def send_audio(self, audio_b64: str):
        if self.closed:
            return
        raw = base64.b64decode(audio_b64, validate=True)
        if not raw or len(raw) > 64000 or len(raw) % 2:
            raise ValueError("Expected bounded mono PCM16 audio")
        if self.ws is not None:
            # Fast mode rejects frames larger than 16,000 bytes. Browser frames
            # are 20ms; also bound callers such as readiness probes to 100ms.
            for offset in range(0, len(raw), 3200):
                chunk = raw[offset:offset + 3200]
                await self.ws.send(json.dumps({"event": "audio_input", "audio": base64.b64encode(chunk).decode()}))
                self.audio_bytes += len(chunk)
        else:
            self.audio_bytes += len(raw)

    async def events(self):
        if config.MOCK_LLM:
            await self._mock_closed.wait()
            return
        async for raw in self.ws:
            event = json.loads(raw)
            kind = event.get("event")
            if kind == "session.end":
                self.billed_seconds = event.get("audio_duration_s")
                break
            if kind == "vad.speech_start":
                self.input_index += 1
                self.input_open = True
            names = {"vad.speech_start": "input.speech_start", "vad.speech_end": "input.speech_end",
                     "transcript.partial": "transcript.partial", "transcript.final": "transcript.final",
                     "error": "error"}
            if kind in names:
                result = {"type": names[kind]}
                # Do not fabricate one permanent ID when a provider omits VAD
                # and utterance identity: a second "yes" is still a new input.
                identity = event.get("utterance_id") or (str(self.input_index) if self.input_open else None)
                if identity is not None:
                    result["input_id"] = str(identity)
                for key in ("text", "start_s", "end_s", "language", "code", "is_fatal", "message"):
                    if key in event:
                        result[key] = event[key]
                if kind == "vad.speech_end":
                    result["voice_ended"] = int(time.time() * 1000)
                if kind == "transcript.final":
                    self.input_open = False
                yield result

    async def aclose(self):
        if self.closed:
            return
        self.closed = True
        self._mock_closed.set()
        if self.ws is not None:
            try:
                await self.ws.send(json.dumps({"event": "end"}))
            except Exception:
                pass
            await self.ws.close()
        if not self._recorded and not config.MOCK_LLM:
            self._recorded = True
            seconds = self.billed_seconds if isinstance(self.billed_seconds, (float, int)) else self.audio_bytes / 32000
            usage.record("sarvam-stt", "saaras:v3-realtime", seconds=seconds)
            usage.trace("sarvam-stt", "saaras:v3-realtime", latency_ms=(time.monotonic() - self.started) * 1000,
                        response=json.dumps({"audio_seconds": seconds, "billing_basis": "provider" if self.billed_seconds is not None else "sent_pcm_estimate"}))


async def stream_tts(text: str, speaker="priya", language="en-IN", pace=1.0):
    """Yield raw PCM16 base64 chunks. Closing/cancelling the generator closes its socket."""
    text = str(text).strip()
    if not text or len(text) > 2000:
        raise ValueError("Streaming speech must contain 1–2000 characters")
    if speaker not in SPEAKERS:
        raise ValueError("The selected voice is not supported by Sarvam streaming")
    if not 0.5 <= float(pace) <= 2:
        raise ValueError("Unsupported speaking pace")
    if config.MOCK_LLM:
        for _ in range(3):
            await asyncio.sleep(0)
            yield {"audio": base64.b64encode(b"\0" * 2400).decode(), "sample_rate": RATE, "format": "pcm_s16le"}
        return
    started = time.monotonic()
    submitted = False
    completed = False
    error = ""
    try:
        async with websockets.connect("wss://api.sarvam.ai/text-to-speech/ws?model=bulbul:v3&send_completion_event=true",
                                      additional_headers=_headers(), open_timeout=8, close_timeout=2,
                                      ping_interval=20, max_size=4 * 1024 * 1024) as ws:
            await ws.send(json.dumps({"type": "config", "data": {
                "speaker": speaker, "language_code": lang_code(language), "pace": float(pace),
                "speech_sample_rate": RATE, "output_audio_codec": "linear16",
                "min_buffer_size": 30, "max_chunk_length": 160}}))
            await ws.send(json.dumps({"type": "text", "data": {"text": text}}))
            submitted = True
            await ws.send(json.dumps({"type": "flush"}))
            while True:
                event = json.loads(await asyncio.wait_for(ws.recv(), timeout=15))
                data = event.get("data") or {}
                if event.get("type") == "error":
                    raise RuntimeError("Sarvam streaming speech failed: " + str(data.get("message", "provider error"))[:180])
                if event.get("type") == "audio":
                    audio = data.get("audio", "")
                    pcm = base64.b64decode(audio, validate=True)
                    if not pcm or len(pcm) % 2 or pcm[:4] == b"RIFF":
                        raise RuntimeError("Sarvam did not return the requested raw PCM16 format")
                    yield {"audio": audio, "sample_rate": RATE, "format": "pcm_s16le"}
                elif event.get("type") == "event" and data.get("event_type") == "final":
                    completed = True
                    break
    except (asyncio.CancelledError, GeneratorExit):
        error = "cancelled; sent characters remain an estimate of provider billing"
        raise
    except Exception as exc:
        error = str(exc)[:200]
        raise
    finally:
        if submitted:
            usage.record("sarvam-tts", "bulbul:v3", chars=len(text))
        usage.trace("sarvam-tts", "bulbul:v3", latency_ms=(time.monotonic() - started) * 1000,
                    user=text, response="stream complete" if completed else "stream incomplete", error=error, chars=len(text) if submitted else 0)
