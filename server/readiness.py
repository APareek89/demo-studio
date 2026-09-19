"""Observed provider capabilities. A configured key is not a successful probe."""
from __future__ import annotations

import asyncio
import base64
import time

from pydantic import BaseModel

from . import config, store, usage
from .agents import voice
from .llm import runtime


class Probe(BaseModel):
    ok: bool


def status(demo_id: str) -> dict:
    observed=store.read_json(demo_id,"provider-readiness.json") or {"checks":{},"checked_at":None}
    now=time.time()
    return {**observed,"configured":{"gemini":bool(config.GEMINI_API_KEY),"claude":bool(config.ANTHROPIC_API_KEY),"runware":bool(config.RUNWARE_API_KEY),"sarvam":bool(config.SARVAM_API_KEY)},"stale":not observed.get("checked_at") or now-observed["checked_at"]>86400,"note":"Configured means a key exists; ready requires a successful capability probe. Availability can change after this check."}


async def probe(demo_id: str) -> dict:
    from .llm.sarvam_stream import RealtimeSTT,stream_tts
    demo=store.load(demo_id)
    usage.current_demo.set(demo_id);usage.current_stage.set("preflight")
    checks={}
    started=time.monotonic()
    try:
        result=await asyncio.wait_for(asyncio.to_thread(runtime.structured,"Return ok=true. This is a connectivity check, no product facts.","Check response schema.",Probe,max_tokens=256,timeout_budget_s=10),timeout=10)
        checks["reasoning"]={"ready":bool(result.ok),"ms":round((time.monotonic()-started)*1000)}
    except Exception as exc:
        checks["reasoning"]={"ready":False,"reason":usage.redact(str(exc))[:250] or type(exc).__name__,"ms":round((time.monotonic()-started)*1000)}
    started=time.monotonic()
    try:
        count=0
        async def speech():
            nonlocal count
            async for frame in stream_tts("Welcome. I'm here to help you explore.",speaker=voice.voice_name_for(demo,"sarvam"),language=demo.get("settings",{}).get("language","en-IN")):
                count+=len(base64.b64decode(frame["audio"]))
        await asyncio.wait_for(speech(),timeout=12)
        checks["streaming_speech"]={"ready":count>0,"pcm_bytes":count,"ms":round((time.monotonic()-started)*1000),"voice":voice.voice_name_for(demo,"sarvam")}
    except Exception as exc:
        checks["streaming_speech"]={"ready":False,"reason":usage.redact(str(exc))[:250] or type(exc).__name__,"ms":round((time.monotonic()-started)*1000)}
    # Open and send bounded silence; this checks protocol/account readiness, not
    # transcription accuracy, turn-taking quality or microphone acoustics.
    started=time.monotonic()
    try:
        async def transcription():
            async with RealtimeSTT(language=demo.get("settings",{}).get("language","en-IN")) as stt:
                async def watch():
                    async for event in stt.events():
                        if event.get("type")=="error":
                            raise RuntimeError(f"{event.get('code') or 'transcription_error'}: {event.get('message') or 'Transcription protocol unavailable'}")
                    raise RuntimeError("Transcription connection closed before probe completed")
                watching=asyncio.create_task(watch())
                try:
                    # Pace 100ms PCM frames, just as a capture device would.
                    # Fast mode caps each frame at 16,000 bytes (500ms).
                    frame=base64.b64encode(b"\0"*3200).decode()
                    for _ in range(10):
                        if watching.done(): await watching
                        await stt.send_audio(frame)
                        await asyncio.sleep(0.1)
                    try: await asyncio.wait_for(watching,timeout=0.5)
                    except asyncio.TimeoutError: pass
                finally:
                    watching.cancel()
                    try: await watching
                    except (asyncio.CancelledError,Exception): pass
        await asyncio.wait_for(transcription(),timeout=10)
        checks["streaming_transcription"]={"ready":True,"ms":round((time.monotonic()-started)*1000),"scope":"connection and bounded PCM input only; no acoustic claim"}
    except Exception as exc:
        checks["streaming_transcription"]={"ready":False,"reason":usage.redact(str(exc))[:250] or type(exc).__name__,"ms":round((time.monotonic()-started)*1000)}
    saved={"checked_at":time.time(),"checks":checks,"mock":config.MOCK_LLM,"ready":all(c["ready"] for c in checks.values())}
    store.write_json(demo_id,"provider-readiness.json",saved)
    return status(demo_id)
