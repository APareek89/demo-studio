"""Cancellable, one-utterance-at-a-time speech outside replayable graph nodes."""
from __future__ import annotations

import asyncio
import time

from . import store, usage
from .agents import voice


class DeliveryCoordinator:
    def __init__(self, demo_id: str, send):
        self.demo_id, self.send = demo_id, send
        self.task: asyncio.Task | None = None
        self.generation = 0
        self.delivered: set[str] = set()
        self.pending: dict[str,dict] = {}
        self.active: tuple[str,str] | None = None

    def register(self, plan: dict) -> None:
        self.pending[plan["utterance_id"]] = plan
        if len(self.pending)>32:
            self.pending.pop(next(iter(self.pending)))

    async def cancel(self) -> None:
        self.generation += 1
        if self.task:
            self.task.cancel()
            try: await self.task
            except (asyncio.CancelledError,Exception): pass
            self.task = None
        self.pending.clear()
        self.active = None

    async def cancel_utterance(self, turn_id: str, utterance_id: str) -> None:
        if self.active != (turn_id,utterance_id): return
        self.generation += 1
        if self.task:
            self.task.cancel()
            try: await self.task
            except (asyncio.CancelledError,Exception): pass
            self.task = None
        self.active = None

    async def request(self, utterance_id: str, turn_id: str) -> None:
        plan = self.pending.get(utterance_id)
        if not plan or plan.get("turn_id")!=turn_id or utterance_id in self.delivered:
            return
        # Do not clear a validated pending plan while switching audio owners.
        if self.task:
            self.generation += 1
            self.task.cancel()
            try: await self.task
            except (asyncio.CancelledError,Exception): pass
        self.delivered.add(utterance_id)
        self.active = (turn_id,utterance_id)
        self.task = asyncio.create_task(self._stream(plan,self.generation))

    async def speak(self, text: str, utterance_id: str, turn_id: str, language: str | None = None) -> None:
        self.register({"utterance_id":utterance_id,"turn_id":turn_id,"speech":text[:2000],"language":language})
        await self.request(utterance_id,turn_id)

    async def _stream(self, plan: dict, generation: int) -> None:
        from .llm.sarvam_stream import stream_tts
        from .agents.speech_style import prepare
        demo = store.load(self.demo_id)
        bundle = store.read_json(self.demo_id,"bundle.json") or {}
        selected = bundle.get("voice",{})
        if selected.get("provider") not in (None,"sarvam"):
            await self.send({"type":"error","code":"voice_unavailable","message":"Live streaming requires this demo's selected Sarvam voice; use its recorded voice instead.","turn_id":plan["turn_id"],"utterance_id":plan["utterance_id"]})
            return
        speaker = selected.get("name") or voice.voice_name_for(demo,"sarvam")
        lang = plan.get("language") or demo.get("settings",{}).get("language","en-IN")
        prepared = prepare(plan.get("speech", ""),plan.get("delivery"))
        envelope = {"turn_id":plan["turn_id"],"utterance_id":plan["utterance_id"]}
        seq, started = 0,time.monotonic()
        try:
            await self.send({"type":"audio.start",**envelope,"encoding":"linear16","sample_rate":24000,"seq":seq})
            async for chunk in stream_tts(prepared["text"],speaker=speaker,language=lang,pace=prepared["pace"]):
                if generation != self.generation: return
                seq += 1
                await self.send({"type":"audio.chunk",**envelope,"seq":seq,**chunk})
            if generation==self.generation:
                await self.send({"type":"audio.end",**envelope,"seq":seq+1})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if generation==self.generation:
                await self.send({"type":"error",**envelope,"code":"speech_unavailable","message":"I couldn't play that audio. The answer is available in the captions."})
            usage.trace("runtime-delivery-error","sarvam",latency_ms=(time.monotonic()-started)*1000,error=type(exc).__name__)
