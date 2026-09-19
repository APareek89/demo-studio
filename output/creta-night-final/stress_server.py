"""Disposable loopback eval proxy. Default OFFLINE; root alone may start live mode.

No voice provider request is forwarded. Live mode opens only the existing app's
runtime socket/API. A durable one-run gate, single session ID and request/cost
ceilings remain authoritative even if browser automation fails or reloads.
"""
from __future__ import annotations
import argparse, asyncio, base64, hashlib, json, subprocess, time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import uvicorn
import websockets
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
DEMO = "dm_41513908"
NAME = "Creta final stress review — caption only"
OBSERVER = '''  window.__stressSnapshot = () => ({at_ms:Date.now(),context:context(),pitch:S.pitch,playback:{...S.playback},origin:S.conversationOrigin?{...S.conversationOrigin}:null,speaking:S.speaking?{text:S.speaking.text,startedAt:S.speaking.startedAt,recorded:!!S.speaking.audio}:null,waiting:!!S.waiter,activeTurn:S.activeTurn?{...S.activeTurn}:null,session:sessionRecord(),pending:!!live?.pending,mic:!!live?.mic,input_generation:live?.inputGeneration,mic_ready:!!live?.micReady,delivery:live?.delivery?{utteranceId:live.delivery.utteranceId,started:live.delivery.started}:null});
'''

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()

class RunGuard:
    def __init__(self, directory, live=False):
        self.directory=Path(directory);self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/"stress-budget.json";self.live=live
        self.data=json.loads(self.path.read_text()) if self.path.exists() else {"started":False,"mode":"live_caption_only" if live else "offline_synthetic","baseline_usd":16.3976,"qa":0,"pitch":0,"summary":0,"session_id":None,"saved_digest":None}
        if self.data["mode"] != ("live_caption_only" if live else "offline_synthetic"):
            raise RuntimeError("Never mix offline and live artifacts")
        self.lock=asyncio.Lock()
    def write(self):
        temp=self.path.with_suffix('.tmp');temp.write_text(json.dumps(self.data,indent=2));temp.replace(self.path)
    def bind(self,sid):
        if not sid or not isinstance(sid,str):raise HTTPException(400,"Session ID required")
        if self.data["session_id"] not in (None,sid):raise HTTPException(409,"Exactly one session is permitted; restart is forbidden")
        self.data["session_id"]=sid;self.write()
    async def accept(self,kind,usd):
        async with self.lock:
            if not self.data["started"]:raise HTTPException(403,"Root has not pressed Start")
            cap={"qa":16,"pitch":2,"summary":1}[kind]
            if self.data[kind]>=cap:raise HTTPException(429,f"{kind} allowance exhausted; no retry")
            if self.live and usd-self.data["baseline_usd"]>=3.50:raise HTTPException(429,"Paid stop ceiling reached; reserve retained")
            self.data[kind]+=1;self.data["last_usage_usd"]=usd;self.write()

def create_app(*, live=False, upstream="http://127.0.0.1:8896", directory=None):
    if urlsplit(upstream).hostname not in {"127.0.0.1","localhost"}:raise ValueError("Upstream must be loopback")
    app=FastAPI();run=RunGuard(directory or HERE/("live" if live else "offline"),live);app.state.guard=run
    bundle=json.loads((ROOT/f"data/demos/{DEMO}/bundle.json").read_text())
    cases=json.loads((HERE/"stress_cases.json").read_text())
    events=run.directory/"stress-events.jsonl"
    def log(kind,**fields):
        with events.open('a') as f:f.write(json.dumps({"at_ms":round(time.time()*1000),"kind":kind,**fields},ensure_ascii=False)+"\n")
    async def request(method,path,**kwargs):
        async with httpx.AsyncClient(base_url=upstream,timeout=25) as client:
            return await client.request(method,path,**kwargs)
    async def cost():
        if not live:return run.data["baseline_usd"]
        response=await request("GET",f"/api/demos/{DEMO}/usage");response.raise_for_status()
        usage=response.json();log("budget_observation",usage=usage,counters=run.data)
        return usage["total_usd"]
    async def accept(kind):await run.accept(kind,await cost())

    @app.get("/")
    async def home():return FileResponse(HERE/"stress.html")
    @app.get("/stress_driver.js")
    async def driver():return FileResponse(HERE/"stress_driver.js",media_type="application/javascript")
    @app.get("/stress/config")
    async def configuration():return {"live":live,"cases":cases,"run":run.data,"bundle_version":bundle.get("version"),"bundle_sha256":digest(bundle)}
    @app.post("/stress/command/start")
    async def command_start():
        async with run.lock:
            if run.data['started'] or run.data.get('command_requested'):raise HTTPException(409,"Start was already explicitly requested")
            run.data['command_requested']=True;run.data['command_requested_at']=time.time();run.write()
        return {"ok":True,"action":"The open browser will invoke its same Start handler once"}
    @app.get("/stress/bundle")
    async def get_bundle():return bundle
    @app.post("/stress/start")
    async def start():
        async with run.lock:
            if run.data["started"]:raise HTTPException(409,"This one-session run has already started; no reset")
            if live:
                usd=await cost()
                if usd<run.data['baseline_usd'] or usd-run.data['baseline_usd']>=3.50:raise HTTPException(409,"Baseline or paid allowance no longer valid")
            run.data["started"]=True;run.data['started_at']=time.time();run.write()
            (run.directory/"stress-provenance.json").write_text(json.dumps({"mode":run.data['mode'],"app_code_sha":subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),"bundle_sha256":digest(bundle),"bundle_version":bundle.get('version'),"script_hashes":{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),HERE/'stress_driver.js',ROOT/'web/player/player.js',ROOT/'web/player/live-voice.js',ROOT/'server/runtime_graph.py']},"boundary":cases['boundary'],"baseline_usd":run.data['baseline_usd'],"started_at":run.data['started_at']},indent=2))
        return {"ok":True}
    @app.post("/stress/event")
    async def event(req:Request):
        body=await req.json();log("browser",event=body);return {"ok":True}
    @app.post("/stress/final")
    async def final(req:Request):
        body=await req.json();path=run.directory/"stress-browser-result.json"
        if path.exists():raise HTTPException(409,"Immutable final result already saved")
        path.write_text(json.dumps(body,ensure_ascii=False,indent=2));log("browser_finished",status=body.get('status'));return {"ok":True}
    @app.get("/web/{path:path}")
    async def web(path:str):
        target=(ROOT/'web'/path).resolve()
        if not target.is_relative_to(ROOT/'web') or not target.is_file():raise HTTPException(404)
        if path=='player/player.js':
            source=target.read_text();needle='  return { destroy, restart, pause, context };'
            if source.count(needle)!=1:raise HTTPException(500,"Read-only observer anchor changed")
            return Response(source.replace(needle,OBSERVER+needle),media_type='application/javascript')
        return FileResponse(target)
    @app.get("/media/{path:path}")
    async def media(path:str):
        # Published local media only; no remote asset fetch or generation.
        target=(ROOT/'data/demos'/path).resolve()
        if not target.is_relative_to(ROOT/'data') or not target.is_file():raise HTTPException(404)
        return FileResponse(target)
    @app.api_route("/api/{path:path}",methods=["GET","POST"])
    async def api(path:str,req:Request):
        prefix=f"demos/{DEMO}/";suffix=path.removeprefix(prefix)
        if not path.startswith(prefix):raise HTTPException(403,"Only the selected demo is allowed")
        if req.method=='GET' and (suffix=='usage' or suffix.startswith('sessions/')):
            if not live:
                if suffix=='usage':return {"total_usd":run.data['baseline_usd']}
                p=run.directory/'stress-persisted-session.json'
                if not p.exists():raise HTTPException(404)
                return json.loads(p.read_text())
            response=await request('GET','/api/'+path);return Response(response.content,status_code=response.status_code,media_type='application/json')
        if req.method!='POST' or suffix not in {'run/qa','run/pitch','run/session'}:raise HTTPException(403,"Voice, leads, build and other mutations are blocked")
        body=await req.json();run.bind(body.get('id') if suffix=='run/session' else body.get('session_id'))
        if suffix=='run/session':
            if body.get('leads'):raise HTTPException(403,"No leads in this test")
            if not body.get('ended'):return {"ok":True,"deferred_until_ended":True}
            if run.data['saved_digest']:
                if digest(body)!=run.data['saved_digest']:raise HTTPException(409,"One frozen ended record only")
                if run.data.get('save_failure'):raise HTTPException(502,run.data['save_failure'])
                if run.data.get('save_response'):return run.data['save_response']
                raise HTTPException(409,"The one permitted save is still in progress; no success observed")
            await accept('summary')
            run.data['saved_digest']=digest(body);run.write()
            (run.directory/'stress-submitted-session.json').write_text(json.dumps(body,ensure_ascii=False,indent=2))
            if not live:
                body['summary']={"model":"offline_synthetic_fixture","customer_name":NAME,"context":"Offline harness fixture only; not a live model result.","questions_asked":body.get('questions',[]),"unanswered":body.get('escalations',[])}
                (run.directory/'stress-persisted-session.json').write_text(json.dumps(body,ensure_ascii=False,indent=2));result={"ok":True,"id":body['id']}
            else:
                try:
                    response=await request('POST','/api/'+path,json=body);response.raise_for_status();result=response.json()
                except Exception as exc:
                    run.data['save_failure']='The one upstream session save failed or its result is unknown. No retry was sent; inspect the session readback.';run.write()
                    log('session_save_failure',error=type(exc).__name__)
                    raise HTTPException(502,run.data['save_failure']) from exc
            run.data['save_response']=result;run.write();return result
        await accept('pitch' if suffix=='run/pitch' else 'qa')
        body['voice_it']=False;body['runtime_version']=1
        log("http_request",path=path,body=body)
        if not live:
            if suffix=='run/pitch':
                await asyncio.sleep(.2)
                return {"route":[{"slide_id":s['id'],"segment_id":s.get('segment_id')} for s in bundle['slides'] if s.get('kind')=='proof'],"focus_topics":["comfort"],"personalized_segments":[],"decision_frame":"","custom_batches":[],"evaluation_mode":"offline_synthetic_fixture"}
            return offline_answer(body)
        response=await request('POST','/api/'+path,json=body);log("http_result",path=path,status=response.status_code,body=response.json());return Response(response.content,status_code=response.status_code,media_type='application/json')

    def offline_answer(body):
        question=body.get('question','');history=json.dumps(body.get('history',[])).lower()
        clarify='estimate the EMI' in question and 'nine percent annual' not in history
        return {"answered":not clarify,"answer":"Could you share the interest rate and loan tenure?" if clarify else "Offline synthetic response. This fixture tests waiting, interruptions, and returning to the reviewed route; it is not a new live API answer.","clarifying_question":"Could you share the interest rate and loan tenure?" if clarify else "","fact_ids":[],"facts":[],"route":"stay","topic":"finance" if 'EMI' in question else 'comfort',"evaluation_mode":"offline_synthetic_fixture"}

    @app.websocket(f"/api/demos/{DEMO}/run/live")
    async def socket(ws:WebSocket):
        await ws.accept();sid=ws.query_params.get('session_id');up=None;tasks=set();send_lock=asyncio.Lock();answers={};deliveries={}
        async def send(data):
            async with send_lock:await ws.send_json({"session_id":sid,**data})
        async def synthetic_delivery(data):
            key=data['utterance_id'];text=data.get('text') or answers.get(key,{}).get('answer','');duration=max(1.2,min(24,len(text.split())/2.5))*(1 if live else .04)
            log('synthetic_caption_delivery',utterance_id=key,turn_id=data['turn_id'],text=text,duration_s=duration,not_audio_measurement=True)
            await send({"type":"audio.chunk","turn_id":data['turn_id'],"utterance_id":key,"seq":0,"audio":base64.b64encode(bytes(320)).decode(),"sample_rate":8000,"format":"pcm_s16le","synthetic":True})
            await asyncio.sleep(duration);await send({"type":"audio.end","turn_id":data['turn_id'],"utterance_id":key,"synthetic":True})
        async def upstream_messages():
            async for raw in up:
                value=json.loads(raw)
                if value.get('type')=='turn.result':
                    answers[value.get('utterance_id')]=value.get('answer',{});log('live_turn_result',body=value)
                await send(value)
        async def offline_reply(data):
            await asyncio.sleep(.8 if 'panoramic sunroof vary' in data.get('question','') else .1);value=offline_answer(data);uid='offline_'+data['turn_id'];answers[uid]=value
            await send({"type":"turn.result","turn_id":data['turn_id'],"utterance_id":uid,"answer":value,"synthetic":True})
        try:
            run.bind(sid)
            if not run.data['started']:raise HTTPException(403,"Root has not pressed Start")
            if live:
                url=upstream.replace('http://','ws://').replace('https://','wss://')+f'/api/demos/{DEMO}/run/live?session_id={sid}'
                up=await websockets.connect(url,origin=upstream);tasks.add(asyncio.create_task(upstream_messages()))
            while True:
                data=await ws.receive_json();kind=data.get('type');log('client_message',body={k:v for k,v in data.items() if k!='audio'})
                if data.get('session_id')!=sid:raise HTTPException(409,"Session mismatch")
                if kind=='session.start':
                    data['mic']=False
                    if not live:await send({"type":"session.ready"});continue
                elif kind in {'mic.set','audio.input'}:
                    if kind=='mic.set' and data.get('enabled'):await send({"type":"mic.ready","input_generation":data['input_generation'],"synthetic":True})
                    continue
                elif kind in {'delivery.request','delivery.speak'}:
                    deliveries[data['utterance_id']]=asyncio.create_task(synthetic_delivery(data));tasks.add(deliveries[data['utterance_id']]);continue
                elif kind in {'delivery.cancel','delivery.end','delivery.start'}:
                    if kind=='delivery.cancel' and data.get('utterance_id') in deliveries:deliveries[data['utterance_id']].cancel()
                    continue
                elif kind=='turn.ask':
                    data['voice_it']=False;data['runtime_version']=1
                    data['profile']={**data.get('profile',{}),'name':NAME}
                    await accept('qa')
                    if not live:tasks.add(asyncio.create_task(offline_reply(data)));continue
                elif kind not in {'turn.interrupt','session.end'}:raise HTTPException(403,"Unsupported runtime command")
                if up:await up.send(json.dumps(data))
                if kind=='session.end':break
        except WebSocketDisconnect:pass
        except Exception as exc:
            log('transport_error',error=str(exc));
            try:await send({"type":"error","code":"stress_guard","message":str(exc),"is_fatal":True})
            except Exception:pass
        finally:
            for task in tasks:task.cancel()
            if up:await up.close()
    return app

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--authorized-live',action='store_true');parser.add_argument('--port',type=int,default=8898);parser.add_argument('--upstream',default='http://127.0.0.1:8896');parser.add_argument('--output',type=Path)
    args=parser.parse_args();uvicorn.run(create_app(live=args.authorized_live,upstream=args.upstream,directory=args.output),host='127.0.0.1',port=args.port)
