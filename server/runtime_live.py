"""Private per-session live transport. Build SSE never carries customer turns."""
from __future__ import annotations

import asyncio
import json
import re
import time
from urllib.parse import urlsplit

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from . import store, usage
from .runtime_delivery import DeliveryCoordinator
from .runtime_graph import run_turn
from .runtime_state import cancel_turn, safe_id

router = APIRouter()


@router.websocket("/api/demos/{demo_id}/run/live")
async def live(websocket: WebSocket, demo_id: str):
    if not store.exists(demo_id):
        await websocket.close(code=1008); return
    origin = websocket.headers.get("origin")
    if origin and urlsplit(origin).netloc != websocket.headers.get("host"):
        await websocket.close(code=1008); return
    await websocket.accept()
    session_id = safe_id(websocket.query_params.get("session_id") or "s_"+str(time.time_ns()))
    send_lock = asyncio.Lock()
    current_turn, language, input_mode = "", "en-IN", "text"
    stt, stt_task, turn_task = None,None,None
    input_generation = 0
    closed = False

    async def send(event):
        if not closed:
            async with send_lock:
                await websocket.send_json({"session_id":session_id,"server_time":time.time(),**event})

    delivery = DeliveryCoordinator(demo_id,send)

    async def stop_turn(*, preserve_planning=False):
        nonlocal turn_task
        cancel_turn(demo_id,session_id,preserve_planning=preserve_planning)
        await delivery.cancel()
        if turn_task:
            turn_task.cancel()
            try: await turn_task
            except (asyncio.CancelledError,Exception): pass
            turn_task=None

    async def stop_mic():
        nonlocal stt,stt_task
        if stt_task:
            stt_task.cancel()
            try: await stt_task
            except (asyncio.CancelledError,Exception): pass
            stt_task=None
        if stt:
            await stt.aclose()
            stt=None

    async def consume_stt(adapter, generation):
        nonlocal stt,stt_task,input_mode
        try:
            async for event in adapter.events():
                if adapter is not stt or generation != input_generation:
                    return
                if event.get("type")=="input.speech_start":
                    # Speech onset stops sound immediately. Only the completed
                    # customer turn can supersede a concurrent Explore plan.
                    await stop_turn(preserve_planning=True)
                if event.get("type")=="error":
                    await send({"type":"error","code":"microphone_stream","message":"Voice input disconnected. Retry the microphone or type your answer.","is_fatal":True,"input_generation":generation})
                    return
                await send({**event,"input_generation":generation})
            if not closed and adapter is stt and generation == input_generation:
                await send({"type":"error","code":"microphone_stream","message":"Voice input ended. Retry the microphone or type your answer.","is_fatal":True,"input_generation":generation})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await send({"type":"error","code":"microphone_stream","message":"Voice connection stopped. Retry the microphone or type your answer.","is_fatal":True,"input_generation":generation})
            usage.trace("runtime-stt-error","sarvam",latency_ms=0,error=type(exc).__name__)
        finally:
            if stt is adapter:
                stt=None
                if not closed: input_mode="text"
            if stt_task is asyncio.current_task(): stt_task=None
            await adapter.aclose()

    async def start_mic(generation):
        nonlocal stt,stt_task,input_generation,input_mode
        if generation <= input_generation:
            if generation == input_generation and stt:
                await send({"type":"mic.ready","input_generation":generation,"input_mode":"voice"})
            return
        await stop_mic()
        input_generation = generation
        from .llm.sarvam_stream import RealtimeSTT
        candidate = RealtimeSTT(language=language)
        try:
            await asyncio.wait_for(candidate.__aenter__(),timeout=8)
            stt = candidate
            input_mode = "voice"
            stt_task = asyncio.create_task(consume_stt(candidate,generation))
            await send({"type":"mic.ready","input_generation":generation,"input_mode":"voice"})
        except Exception as exc:
            input_mode = "text"
            await candidate.aclose()
            await send({"type":"error","code":"microphone_unavailable","message":"I couldn't connect voice input. You can retry or type your answer.","input_generation":generation})
            usage.trace("runtime-stt-connect","sarvam",latency_ms=0,error=type(exc).__name__)

    async def answer(body: dict):
        tid = body["turn_id"]
        try:
            final = await run_turn(demo_id,{**body,"session_id":session_id})
            if tid!=current_turn: return
            delivery.register(final["delivery"])
            await send({"type":"turn.result","turn_id":tid,"utterance_id":final["delivery"]["utterance_id"],"answer":final["result"]})
        except (asyncio.CancelledError,InterruptedError):
            pass
        except Exception as exc:
            if tid==current_turn:
                await send({"type":"error","turn_id":tid,"code":"turn_failed","message":"I couldn't finish that answer. Please try again."})
            usage.trace("runtime-live-error","code",latency_ms=0,error=type(exc).__name__)

    usage.current_demo.set(demo_id)
    usage.current_stage.set("runtime")
    try:
        while True:
            raw = await websocket.receive_text()
            if len(raw)>100_000:
                await websocket.close(code=1009); break
            try: message=json.loads(raw)
            except ValueError:
                await send({"type":"error","code":"bad_message","message":"Invalid live message."}); continue
            kind=message.get("type")
            if kind=="session.start":
                requested=message.get("session_id")
                if requested and not current_turn: session_id=safe_id(requested)
                language=str(message.get("language") or "en-IN")[:20]
                input_mode = message.get("input_mode") if message.get("input_mode") in ("voice","text") else "voice" if message.get("mic") is True else "text"
                await send({"type":"session.ready","runtime_version":1,"microphone":False,"input_mode":input_mode})
                if message.get("mic") is True: await start_mic(1)
            elif kind=="mic.set":
                generation=message.get("input_generation")
                if type(generation) is not int or generation < 0: continue
                if message.get("enabled") is True:
                    if generation > 0: await start_mic(generation)
                elif message.get("enabled") is False and generation == input_generation:
                    await stop_mic()
                    input_mode = "text"
            elif kind=="audio.input":
                data=message.get("audio","")
                if stt and message.get("input_generation") == input_generation and isinstance(data,str) and len(data)<=90_000:
                    try: await stt.send_audio(data)
                    except Exception: await stop_mic(); await send({"type":"error","code":"microphone_stream","message":"Voice input disconnected. Please retry or type.","input_generation":input_generation})
            elif kind=="turn.interrupt":
                await stop_turn(preserve_planning=message.get("preserve_planning") is True)
                current_turn=safe_id(message.get("turn_id") or "t_"+str(time.time_ns()),"t")
                await send({"type":"turn.cancelled","turn_id":current_turn})
            elif kind=="turn.ask":
                await stop_turn(preserve_planning=True)
                current_turn=safe_id(message.get("turn_id") or "t_"+str(time.time_ns()),"t")
                message["turn_id"]=current_turn
                message["input_mode"]=input_mode
                turn_task=asyncio.create_task(answer(message))
            elif kind=="delivery.request":
                if message.get("turn_id")==current_turn:
                    await delivery.request(str(message.get("utterance_id","")),current_turn)
            elif kind=="delivery.cancel":
                await delivery.cancel_utterance(str(message.get("turn_id","")),str(message.get("utterance_id","")))
            elif kind=="delivery.speak":
                text=str(message.get("text") or "").strip()
                if text and len(text)<=2000:
                    # Same endpoint capability as existing /run/tts; output voice
                    # is selected by this demo, not by arbitrary client settings.
                    tid=str(message.get("turn_id") or current_turn)
                    if not current_turn or tid==current_turn:
                        await delivery.speak(text,safe_id(message.get("utterance_id") or str(time.time_ns()),"u"),tid,language)
            elif kind in ("delivery.start","delivery.end"):
                # A delivery receipt is observational only; it never answers a
                # question or advances a graph based on elapsed time.
                usage.trace("runtime-"+kind,"browser",latency_ms=0,response=json.dumps({k:message.get(k) for k in ("turn_id","utterance_id","completed","client_time")}))
            elif kind=="session.end":
                break
    except WebSocketDisconnect:
        pass
    finally:
        closed=True
        await stop_turn()
        await stop_mic()
