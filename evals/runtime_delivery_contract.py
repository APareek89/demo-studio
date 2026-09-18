"""Free same-event-loop API checks for reviewed routing and responsive media delivery."""
from __future__ import annotations

import asyncio
import copy
import os
import sys
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch


def run(check, _demo_id=None):
    with tempfile.TemporaryDirectory(prefix="runtime-delivery-") as tmp, ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, {"MOCK_LLM":"1", "CLOUD_SYNC":"0", "STORAGE_BACKEND":"local",
                                                  "DEMO_STUDIO_DATA":str(Path(tmp)/"demos"), "DEMO_STUDIO_GRAPH_DB":str(Path(tmp)/"graph.sqlite")}))
        import httpx
        from server import cloud, config, schemas, store, usage
        from server.agents import deck, pitch, qa, voice
        from server.app import app
        from server.llm import sarvam
        stack.enter_context(patch.multiple(config, MOCK_LLM=True, DATA_DIR=Path(tmp)/"demos", GRAPH_DB=Path(tmp)/"graph.sqlite"))
        stack.enter_context(patch.object(cloud,"enabled",return_value=False))
        blocked=[stack.enter_context(patch(name,side_effect=AssertionError("Unexpected provider/network call")))
                 for name in ("socket.create_connection","socket.socket.connect","socket.socket.connect_ex",
                              "server.llm.gemini.client","server.llm.runware._post","server.llm.claude._client_opts")]
        demo=store.new_demo("Runtime delivery fixture");did=demo["id"]
        source=store.add_text_source(did,"Product brochure","Boot 382 L; front-seat ventilation.","product")
        def fact(fid,value):
            return schemas.Fact(id=fid,kind="spec",claim=value,value=value,confidence=1,
                                source=schemas.FactSource(ref=source["id"],quote=value)).model_dump()
        store.write_json(did,"understanding.json",{"facts":[fact("F014","Boot 382 L"),fact("F020","Front-seat ventilation")],"competitors":[],"unknowns":[],"images":[],"shots":[]})
        raw_slides=[{"id":"sl02","segment_id":"cabin","kind":"proof","title":"Cabin","lines":[{"text":"Front ventilation.","fact_ids":["F020"]}],"fact_ids":["F020"],"deeper":[{"text":"An old boot statement.","fact_ids":["F014"]}],"callouts":[]},
                    {"id":"sl05","segment_id":"boot","kind":"proof","title":"Boot","lines":[{"text":"Old boot copy.","fact_ids":[]}],"fact_ids":[],"deeper":[],"callouts":[{"id":"boot-volume","text":"382 L","fact_ids":["F014"]}]}]
        script={"segments":[{"id":"cabin","title":"Cabin","topic":"cabin","role":"proof","lines":[{"id":"cabin-L1","text":"Front-seat ventilation.","fact_ids":["F020"]}],"deeper":[]},
                            {"id":"boot","title":"Boot","topic":"boot","role":"proof","lines":[{"id":"boot-L1","text":"The boot is listed at 382 L.","fact_ids":["F014"]}],"deeper":[]}],"closing":[]}
        store.write_json(did,"deck.json",{"slides":raw_slides});store.write_json(did,"script.json",script)
        question="How much boot space is listed?";answer="The boot is listed at 382 L."
        store.write_json(did,"faq.json",{"entries":[{"id":"Q01","question":question,"answer":answer,"fact_ids":["F014"],"answered":True,"audio":"audio/ack.wav","slide_id":"sl02"}]})
        audio=store.path(did,"audio/ack.wav");audio.parent.mkdir(exist_ok=True);media_bytes=b"recorded acknowledgement fixture";audio.write_bytes(media_bytes)
        originals={name:store.path(did,name).read_bytes() for name in ("deck.json","script.json")}
        check("runtime delivery: fixture reproduces old raw-deck stay versus reviewed-script jump",
              deck.route_for(raw_slides,"sl02",["F014"],question)["route"]=="stay"
              and deck.route_for(deck.slides_with_script(raw_slides,script),"sl02",["F014"],question)["slide_id"]=="sl05")
        def qa_result():return {"answer":answer,"fact_ids":["F014"],"answered":True,"audio":None,"facts":[],"visual":None,"offer_callback":False,"clarifying_question":""}

        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url="http://test") as client:
                with patch.object(qa,"answer",side_effect=AssertionError("Known question must stay in bank")) as model:
                    response=await client.post(f"/api/demos/{did}/run/qa",json={"question":question,"slide_id":"sl02"});result=response.json()
                    check("runtime delivery: actual bank route jumps from stale cabin copy to current boot slide",response.status_code==200 and result["from_bank"] and result["route"]=="jump" and result["slide_id"]=="sl05" and result["callout_id"]=="boot-volume" and not model.called)
                    response=await client.post(f"/api/demos/{did}/run/qa",json={"question":question,"slide_id":"sl05"})
                    check("runtime delivery: bank stays only when current reviewed slide carries the answer",response.status_code==200 and response.json()["route"]=="stay" and response.json()["slide_id"]=="sl05")
                with patch.object(qa,"answer",return_value=qa_result()):
                    response=await client.post(f"/api/demos/{did}/run/qa",json={"question":question,"slide_id":"sl02","skip_bank":True})
                    check("runtime delivery: actual model route uses the same reviewed-script hydration",response.status_code==200 and not response.json()["from_bank"] and response.json()["route"]=="jump" and response.json()["slide_id"]=="sl05")
                with patch.object(qa,"answer",return_value={**qa_result(),"answered":False,"fact_ids":[],"offer_callback":True}):
                    response=await client.post(f"/api/demos/{did}/run/qa",json={"question":"Something unknown?","slide_id":"sl02","skip_bank":True})
                    check("runtime delivery: unknown answer retains the current slide",response.status_code==200 and response.json()["route"]=="none" and response.json()["slide_id"]=="sl02")
                check("runtime delivery: routing reads current script without mutating saved slide design",all(store.path(did,name).read_bytes()==data for name,data in originals.items()))

                loop_thread=threading.get_ident()
                cases=[("pitch",pitch,"plan_pitch",{"json":{"profile":{"why":"Room for family"},"refine":True}},{"route":[],"decision_frame":"Let's look."}),
                       ("qa",qa,"answer",{"json":{"question":question,"slide_id":"sl02","skip_bank":True}},qa_result()),
                       ("tts",voice,"render_line",{"json":{"text":"Let me check that.","language":"hi-IN"}},"audio/ack.wav"),
                       ("stt",sarvam,"stt",{"files":{"file":("input.wav",b"a"*1024,"audio/wav")},"data":{"language":"hi-IN"}},"Boot space, please.")]
                for endpoint,module,function,request_args,output in cases:
                    started=threading.Event();release=threading.Event();finished=threading.Event();capture={}
                    def slow(*args,**kwargs):
                        capture.update(thread=threading.get_ident(),demo=usage.current_demo.get(),stage=usage.current_stage.get(),args=args,kwargs=kwargs)
                        started.set();release.wait(3);finished.set();return copy.deepcopy(output)
                    # A watchdog releases even the old blocking implementation so the negative regression cannot hang.
                    watchdog=threading.Timer(2,release.set);watchdog.daemon=True;watchdog.start()
                    with patch.object(module,function,side_effect=slow):
                        pending=asyncio.create_task(client.post(f"/api/demos/{did}/run/{endpoint}",**request_args))
                        try:
                            entered=await asyncio.to_thread(started.wait,3)
                            responses=await asyncio.wait_for(asyncio.gather(client.get(f"/media/{did}/audio/ack.wav"),client.get("/api/health")),1)
                            delivered_while_pending=not finished.is_set() and not release.is_set()
                        finally:
                            release.set();watchdog.cancel()
                            response=await pending
                    check(f"runtime delivery: {endpoint} allows cached media and health on the same ASGI loop while provider waits",entered and delivered_while_pending and responses[0].status_code==200 and responses[0].content==media_bytes and responses[1].status_code==200)
                    check(f"runtime delivery: {endpoint} offloads provider and preserves tracing context",capture.get("thread")!=loop_thread and capture.get("demo")==did and capture.get("stage")=="runtime")
                    check(f"runtime delivery: {endpoint} response remains successful",response.status_code==200)
                    if endpoint=="tts":check("runtime delivery: TTS retains chosen-voice strictness and language",capture["kwargs"]=={"lang":"hi-IN","strict":True})
                    if endpoint=="qa":check("runtime delivery: QA retains live-provider behavior",capture["kwargs"].get("live") is True)
                    if endpoint=="pitch":check("runtime delivery: pitch retains profile and refinement",capture["args"]==(did,{"why":"Room for family"},True))
                    if endpoint=="stt":check("runtime delivery: STT retains uploaded content and language",capture["args"]==(b"a"*1024,"input.wav","hi-IN","audio/wav"))
                    with patch.object(module,function,side_effect=RuntimeError("fake provider unavailable")):
                        response=await client.post(f"/api/demos/{did}/run/{endpoint}",**request_args)
                    check(f"runtime delivery: {endpoint} preserves explicit HTTP502 on provider failure",response.status_code==502 and bool(response.json().get("detail")))
                check("runtime delivery: all checks used fake providers and no outbound connection",all(not mock.called for mock in blocked))
        asyncio.run(exercise())


if __name__=="__main__":
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]));results=[]
    def check(label,ok):results.append(bool(ok));print(("PASS " if ok else "FAIL ")+label)
    run(check)
    print(f"Runtime delivery: {sum(results)}/{len(results)} passed")
    raise SystemExit(0 if all(results) else 1)
