"""Opt-in local transport boundaries; no RTC/network/provider or live storage."""
import asyncio
import base64
from contextlib import ExitStack
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
from unittest.mock import patch

scratch = tempfile.TemporaryDirectory(prefix="livekit-trial-contract-")
os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=scratch.name,
                  DEMO_STUDIO_GRAPH_DB=str(Path(scratch.name) / "graph.sqlite"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from starlette.requests import Request
from server import livekit_trial as trial, runtime_live, store

passed = []
def check(name, value):
    assert value, name
    passed.append(name)
    print("PASS", name)

async def settle():
    for _ in range(12):
        await asyncio.sleep(0)

class Room:
    created = []
    fail = False
    def __init__(self):
        self.callbacks, self.packets, self.disconnected = {}, [], False
        self.local_participant = self
        self.created.append(self)
    def on(self, event, callback): self.callbacks[event] = callback
    async def connect(self, url, token, options):
        self.options, self.url = options, url
        if self.fail: raise RuntimeError("do not expose detail")
    async def disconnect(self): self.disconnected = True
    async def publish_data(self, data, **kwargs): self.packets.append((data, kwargs))

class Stream:
    created = []
    def __init__(self, track, **kwargs):
        self.queue, self.kwargs, self.closed = asyncio.Queue(), kwargs, False
        self.created.append(self)
    def __aiter__(self): return self
    async def __anext__(self):
        value = await self.queue.get()
        if value is None: raise StopAsyncIteration
        return NS(frame=NS(data=value))
    async def aclose(self): self.closed = True

class AccessToken:
    created = []
    def __init__(self, key, secret):
        self.key, self.secret = key, secret
        self.created.append(self)
    def with_identity(self, value): self.identity = value; return self
    def with_ttl(self, value): self.ttl = value; return self
    def with_grants(self, value): self.grants = value; return self
    def to_jwt(self): return "test_" + self.identity

RTC = NS(Room=Room, RoomOptions=lambda **kw:NS(**kw), RtcConfiguration=lambda **kw:NS(**kw),
         IceServer=lambda **kw:NS(**kw), AudioStream=Stream, DataPacketKind=NS(KIND_RELIABLE=0),
         TrackSource=NS(SOURCE_MICROPHONE=2), TrackKind=NS(KIND_AUDIO=1))
API = NS(VideoGrants=lambda **kw:NS(**kw), AccessToken=AccessToken)

def request(body=None, *, client="127.0.0.1", origin="http://127.0.0.1:8920", host="127.0.0.1:8920", extra=None):
    headers = {"host":host, **(extra or {})}
    if origin is not None: headers["origin"] = origin
    raw = json.dumps(body if body is not None else {"session_id":"s_trial_test"}).encode()
    async def receive(): return {"type":"http.request", "body":raw}
    return Request({"type":"http", "method":"POST", "scheme":"http", "path":"/trial", "query_string":b"",
                    "client":(client,2345), "server":("127.0.0.1",8920),
                    "headers":[(k.encode(),v.encode()) for k,v in headers.items()]}, receive)

async def error_status(code, function):
    try: await function()
    except HTTPException as error: return error.status_code == code
    return False

def decode(room):
    decoder = trial.Reassembler()
    out = []
    for packet, _ in room.packets:
        value = decoder.feed(packet)
        if value is not None: out.append(value)
    return out

def data(bridge, event, *, owner=None, topic=trial.TOPIC, reliable=0):
    for packet in trial.fragments(event):
        bridge._data(NS(data=packet, topic=topic, participant=NS(identity=owner or bridge.identity), kind=reliable))

def bridge(session="s_private"):
    return trial.TrialBridge("dm_test0001", session, "r_"+session, "viewer", "runtime", RTC)

class Delivery:
    def __init__(self, demo_id, send): self.send = send
    async def cancel(self): pass
    def register(self, plan): self.plan = plan
    async def request(self, utterance, turn):
        await self.send({"type":"audio.chunk", "audio":"AA==", "seq":0, "utterance_id":utterance, "turn_id":turn})
        await self.send({"type":"audio.end", "utterance_id":utterance, "turn_id":turn})

async def main():
    demo = store.new_demo("Isolated LiveKit trial")
    did = demo["id"]
    with patch.dict(os.environ, {"LIVEKIT_TRIAL_ENABLED":"0"}):
        check("default-off endpoint denies before SDK or demo access", await error_status(404, lambda:trial.trial_token(did,request())))
    settings = {"LIVEKIT_TRIAL_ENABLED":"1", "LIVEKIT_URL":"ws://127.0.0.1:7880", "LIVEKIT_API_KEY":"localtest", "LIVEKIT_API_SECRET":"not-a-production-secret-only-for-tests"}
    with patch.dict(os.environ, settings), patch.object(trial,"_sdk",return_value=(API,RTC)):
        check("remote caller cannot spoof forwarded loopback", await error_status(403, lambda:trial.trial_token(did,request(client="203.0.113.5",extra={"x-forwarded-for":"127.0.0.1"}))))
        check("missing, cross-origin and scheme-mismatched origins rejected", all([await error_status(403,lambda origin=origin:trial.trial_token(did,request(origin=origin))) for origin in (None,"http://evil.example","https://127.0.0.1:8920")]))
        check("unpublished demo cannot obtain a room", await error_status(409, lambda:trial.trial_token(did,request())))
        store.update(did,lambda d:d.update(status="ready"))
        snapshot_id="kb_"+"1"*24
        store.write_json(did,"bundle.json",{"runtime":{"version":1},"knowledge_snapshot_id":snapshot_id,"version":1})
        store.write_json(did,f"knowledge/snapshots/{snapshot_id}.json",{"id":snapshot_id,"facts":[]})
        for bad in ("../../escape", "x"*101, None):
            assert await error_status(400,lambda bad=bad:trial.trial_token(did,request({"session_id":bad})))
        check("session identifiers must be path-safe and bounded", True)
        for url in ("wss://cloud.example", "ws://user:pass@127.0.0.1:7880", "ws://127.0.0.1:7880/arbitrary"):
            with patch.dict(os.environ,{"LIVEKIT_URL":url}):
                assert await error_status(503,lambda:trial.trial_token(did,request()))
        check("trial cannot connect to a remote or credential-bearing LiveKit URL", True)
        for stun in ("stun:stun.l.google.com:19302", "stun:127.0.0.1:8896", "turn:127.0.0.1:7882"):
            with patch.dict(os.environ,{"LIVEKIT_TRIAL_STUN_URL":stun}):
                assert await error_status(503,lambda:trial.trial_token(did,request()))
        check("native RTC override rejects external STUN, TURN and protected port", True)
        result = await trial.trial_token(did,request())
        active = trial._bridges[result["room"]]
        viewer, worker = AccessToken.created[-1], AccessToken.created[-2]
        check("viewer gets unique room and exact bound identity without worker token or keys", result["identity"] == viewer.identity and result["agent_identity"] == worker.identity and result["token"] != "test_"+worker.identity and "secret" not in result and viewer.grants.room == result["room"])
        check("two-minute token grants only joined room, microphone, data and subscription", viewer.ttl.total_seconds()==120 and viewer.grants.can_publish_sources==["microphone"] and viewer.grants.room_join and not viewer.grants.can_update_own_metadata and not worker.grants.can_publish and worker.grants.can_publish_data)
        check("server room is joined before token and uses no external ICE servers", active.runtime_task is not None and [server.urls for server in active.room.options.rtc_config.ice_servers]==[["stun:127.0.0.1:7882"]])
        check("duplicate session cannot open a second runtime owner", await error_status(409,lambda:trial.trial_token(did,request())))
        for n in range(3): await trial.trial_token(did,request({"session_id":f"s_cap{n}"}))
        check("four-room capacity bounded before connection", len(trial._bridges)==4 and await error_status(429,lambda:trial.trial_token(did,request({"session_id":"s_over"}))))
        await trial.close_trials()
        check("shutdown closes every room and clears reservations", not trial._bridges and all(room.disconnected for room in Room.created))
        with patch.object(Room,"fail",True):
            check("connection failure is bounded and releases reservation", await error_status(503,lambda:trial.trial_token(did,request())) and not trial._bridges)
        native_join=asyncio.Event()
        async def slow_native_connect(self,url,token,options):
            await native_join.wait()
        with patch.object(Room,"connect",slow_native_connect),patch.object(trial,"CONNECT_SECONDS",.01):
            timed_out=await error_status(503,lambda:trial.trial_token(did,request()))
            pending=next(iter(trial._bridges.values()))
            check("join timeout retains bounded ownership of uncancellable native connection",timed_out and pending.closed and not pending.connect_task.cancelled() and len(trial._bridges)==1)
            native_join.set();await settle()
            check("late native join is disconnected and releases capacity without serving a token",not trial._bridges and pending.room.disconnected and pending.runtime_task is None)
        native_leave=asyncio.Event()
        async def slow_native_disconnect(self):
            await native_leave.wait()
            self.disconnected=True
        result=await trial.trial_token(did,request())
        pending=trial._bridges[result["room"]]
        with patch.object(Room,"disconnect",slow_native_disconnect),patch.object(trial,"DISCONNECT_SECONDS",.01):
            await pending.close()
            check("native disconnect timeout keeps room capacity reserved until completion",pending.closed and len(trial._bridges)==1 and not pending.dispose_task.done() and not pending.dispose_task.cancelled())
            native_leave.set();await pending.dispose_task
            check("native disconnect completion releases capacity without cancellation",not trial._bridges and pending.room.disconnected)

    payload={"type":"turn.result","answer":"画像🙂"*5000}
    packets=trial.fragments(payload)
    parser=trial.Reassembler(); values=[parser.feed(packet) for packet in packets]
    check("UTF-8 multi-packet roundtrip and packet limits", len(packets)>1 and values[-1]==payload and all(len(p)<=12288 for p in packets))
    check("completed replay cannot deliver a duplicate turn", parser.feed(packets[0]) is None)
    for mutation in (lambda f:f.update(part=1), lambda f:f.update(parts=129), lambda f:f.update(payload="%%%"),lambda f:f.update(id="../bad"), lambda f:f.update(v=True)):
        frame=json.loads(packets[0]);mutation(frame)
        try: trial.Reassembler().feed(json.dumps(frame).encode())
        except ValueError: pass
        else: raise AssertionError("invalid fragment accepted")
    check("malformed, oversized, invalid-base64 and reordered fragments rejected", True)
    parser=trial.Reassembler();parser.feed(packets[0],now=0)
    check("incomplete fragments expire within ten seconds",parser.expired(now=11))
    parser=trial.Reassembler()
    for n in range(4):
        frame=json.loads(packets[0]);frame["id"]=f"m{n}";parser.feed(json.dumps(frame).encode())
    try:
        frame["id"]="m5";parser.feed(json.dumps(frame).encode())
    except ValueError: pass
    else: raise AssertionError("inflight limit")
    check("fragment assembly permits only four bounded inflight messages",True)

    b=bridge()
    b._joined(NS(identity="outsider"));await settle()
    check("unbound participant cannot announce a ready session",not b.room.packets and b.ready_task is None)
    b._joined(NS(identity="viewer"));await settle()
    b._joined(NS(identity="viewer"));await settle()
    check("worker coalesces duplicate identity visibility into one readiness task",[e["type"] for e in decode(b.room)]==["trial.ready"] and decode(b.room)[0]["session_id"]==b.session_id)
    await b.close()
    b._joined(NS(identity="viewer"));await settle()
    check("late participant callbacks cannot reannounce a closed trial",len(b.room.packets)==1 and b.closed)

    with patch.object(trial,"READY_RETRY_SECONDS",.005):
        b=bridge();b._joined(NS(identity="viewer"))
        await asyncio.sleep(.04)
        check("readiness retries are bounded and contain no semantic turn",[e["type"] for e in decode(b.room)]==["trial.ready"]*trial.READY_ATTEMPTS and b.incoming.empty())
        await b.close()
        b=bridge();b._joined(NS(identity="viewer"));await settle()
        data(b,{"type":"session.start","session_id":b.session_id,"mic":False})
        count=len(b.room.packets);await asyncio.sleep(.03)
        check("bound session start stops all readiness retries",b.protocol_started and len(b.room.packets)==count and b.incoming.qsize()==1)
        await b.close()

    b=bridge()
    for options in ({"owner":"outsider"},{"topic":"wrong"},{"reliable":1}): data(b,{"type":"session.start"},**options)
    check("unbound participant, wrong topic and lossy controls ignored",b.incoming.empty())
    data(b,{"type":"session.start","session_id":b.session_id,"mic":False})
    check("owner control enters existing JSON protocol unchanged",json.loads(await b.receive_text())=={"type":"session.start","session_id":b.session_id,"mic":False})
    data(b,{"type":"mic.set","enabled":True,"input_generation":1});await b.receive_text()
    pub=NS(name="demo-mic-1",source=2)
    b._track(NS(kind=1),pub,NS(identity="outsider"))
    b._track(NS(kind=1),NS(name="demo-mic-0",source=2),NS(identity="viewer"))
    b._track(NS(kind=1),NS(name="demo-mic-1",source=1),NS(identity="viewer"))
    check("only owner microphone with current generation can be consumed",b.audio_task is None)
    b._track(NS(kind=1),pub,NS(identity="viewer"));await settle()
    stream=Stream.created[-1]
    for _ in range(400): await stream.queue.put(bytes(640))
    await settle()
    check("RTC is 16k mono 20ms and preserves eight-second pre-ready input",stream.kwargs=={"sample_rate":16000,"num_channels":1,"frame_size_ms":20} and len(b.pre_roll)==400 and b.incoming.empty())
    await b.send_json({"type":"mic.ready","input_generation":1})
    check("mic readiness flushes only current generation after track and provider ready",b.active_generation==1 and b.incoming.qsize()==400 and decode(b.room)[-1]["type"]=="mic.ready")
    while not b.incoming.empty(): await b.receive_text()
    data(b,{"type":"mic.set","enabled":False,"input_generation":1});await b.receive_text()
    await b.send_json({"type":"mic.ready","input_generation":1})
    check("mic off prevents stale provider readiness from reopening capture",not b.mic_enabled and b.active_generation==0)
    await b.close()
    check("session teardown closes RTC audio and later packets are ignored",stream.closed and b.closed and not b._put({"type":"turn.ask"}))

    b=bridge()
    first=NS(name="demo-mic-1",source=2)
    b._track(NS(kind=1),first,NS(identity="viewer"))
    check("early RTC track waits boundedly when track event precedes mic.set",len(b.early_tracks)==1 and b.audio_task is None)
    data(b,{"type":"mic.set","enabled":True,"input_generation":1});await b.receive_text();await settle()
    await b.send_json({"type":"mic.ready","input_generation":1})
    check("mic.set recovers already-subscribed matching track",b.track_generation==1 and b.active_generation==1 and not b.early_tracks)
    owned_task=b.audio_task
    duplicate=NS(name="demo-mic-1",source=2)
    b._track(NS(kind=1),duplicate,NS(identity="viewer"))
    b._untrack(NS(kind=1),duplicate,NS(identity="viewer"));await settle()
    check("duplicate named track cannot replace or unpublish current physical capture",b.audio_task is owned_task and not b.closed)
    data(b,{"type":"mic.set","enabled":False,"input_generation":1});await b.receive_text()
    data(b,{"type":"mic.set","enabled":True,"input_generation":2});await b.receive_text()
    second=NS(name="demo-mic-2",source=2)
    b._track(NS(kind=1),second,NS(identity="viewer"));await settle()
    b._untrack(NS(kind=1),first,NS(identity="viewer"));await settle()
    await b.send_json({"type":"mic.ready","input_generation":2})
    check("late generation-one unpublish cannot close generation-two capture",not b.closed and b.mic_enabled and b.active_generation==2 and b.track_generation==2)
    b._untrack(NS(kind=1),second,NS(identity="viewer"));await settle()
    check("unexpected loss of current microphone fails visibly",b.closed)

    b=bridge()
    data(b,{"type":"mic.set","enabled":True,"input_generation":1});await b.receive_text()
    b._track(NS(kind=1),first,NS(identity="viewer"));await settle()
    stream=Stream.created[-1]
    for _ in range(trial.PRE_ROLL_FRAMES+1): await stream.queue.put(bytes(640))
    await settle()
    check("pre-ready overflow closes capture instead of truncating the question",b.closed and stream.closed)

    b=bridge()
    data(b,{"type":"mic.set","enabled":True,"input_generation":1});await b.receive_text()
    b._track(NS(kind=1),first,NS(identity="viewer"));await settle()
    stream=Stream.created[-1]
    await stream.queue.put(None);await settle()
    check("unexpected RTC stream end cannot leave the demo waiting forever",b.closed)

    b=bridge()
    data(b,{"type":"mic.set","enabled":True,"input_generation":1});await b.receive_text()
    with patch.object(RTC,"AudioStream",side_effect=RuntimeError("native input could not open")):
        b._track(NS(kind=1),first,NS(identity="viewer"));await settle()
    check("native audio constructor failure closes the trial without a dead microphone",b.closed)

    for bad in ({"type":"session.start","session_id":"another"},{"type":"audio.input","audio":"AA=="}):
        b=bridge();data(b,bad);await settle();assert b.closed
    check("client cannot change bound session or inject alternate PCM data",True)
    b=bridge()
    for _ in range(trial.INPUT_QUEUE_SIZE+1):b._put({"type":"turn.ask"})
    await settle()
    check("overflow fails session instead of silently losing input",b.closed)

    calls=[]
    async def answer(demo_id,body):
        calls.append((demo_id,body))
        return {"result":{"answered":True,"answer":"Grounded answer"},"delivery":{"utterance_id":"u_trial"}}
    b=bridge()
    with patch.object(runtime_live.store,"exists",return_value=True),patch.object(runtime_live,"DeliveryCoordinator",Delivery),patch.object(runtime_live,"cancel_turn"),patch.object(runtime_live,"run_turn",answer),patch.object(runtime_live.usage,"trace"):
        await b.connect("ws://127.0.0.1:7880","fake")
        data(b,{"type":"session.start","mic":False,"input_mode":"text"});await settle()
        data(b,{"type":"turn.ask","question":"What is reviewed?","turn_id":"t_trial"});await settle()
        data(b,{"type":"delivery.request","turn_id":"t_trial","utterance_id":"u_trial"});await settle()
        out=decode(b.room)
        check("actual runtime_live handles session, validated answer and original delivery protocol",calls and calls[0][1]["session_id"]=="s_private" and [e["type"] for e in out]==["session.ready","turn.result","audio.chunk","audio.end"])
        check("reliable output is ordered and addressed only to bound viewer",all(kw=={"reliable":True,"destination_identities":["viewer"],"topic":trial.TOPIC} for _,kw in b.room.packets))
        data(b,{"type":"trial.ping"});await settle()
        check("keepalive produces pong without another graph call",decode(b.room)[-1]["type"]=="trial.pong" and len(calls)==1)
        data(b,{"type":"session.end"});await settle()
        check("existing session.end tears down room and runtime",b.closed and b.room.disconnected)
    b=bridge();b.started-=trial.VISIT_SECONDS+1
    watch=asyncio.create_task(b._watch());await asyncio.sleep(1.02);await settle()
    check("room lifetime is independently bounded beyond token expiry",b.closed)
    await watch

with ExitStack() as blocked:
    # These many independent protocol cases share a synthetic client address;
    # public rate-limit behavior is exercised separately in the hosted contract.
    blocked.enter_context(patch.object(trial,"TOKEN_ATTEMPT_LIMIT",1000))
    blocked.enter_context(patch.dict(os.environ,{"LIVEKIT_ENABLED":"0"}))
    for target in ("socket.create_connection","socket.getaddrinfo","socket.socket.connect","socket.socket.connect_ex","socket.socket.sendto"):
        blocked.enter_context(patch(target,side_effect=AssertionError("Sockets blocked")))
    asyncio.run(main())
print(f"LiveKit trial: {len(passed)}/{len(passed)} passed")
scratch.cleanup()
