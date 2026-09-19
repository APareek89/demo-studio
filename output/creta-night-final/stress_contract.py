"""Free guard/transport checks. Fake upstream; no provider or physical socket."""
import asyncio, importlib.util, json, socket, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient

attempts=[]
def blocked(*a,**kw):attempts.append(True);raise AssertionError('No outbound sockets in stress contracts')
socket.socket.connect=blocked;socket.socket.connect_ex=blocked;socket.create_connection=blocked
spec=importlib.util.spec_from_file_location('stress_server',Path(__file__).with_name('stress_server.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class FakeResponse:
    status_code=200
    def __init__(self,value):self.value=value;self.content=json.dumps(value).encode()
    def json(self):return self.value
    def raise_for_status(self):return self
class FakeHttp:
    calls=[]
    def __init__(self,*a,**kw):pass
    async def __aenter__(self):return self
    async def __aexit__(self,*a):pass
    async def request(self,method,path,**kw):
        self.calls.append((method,path,kw))
        return FakeResponse({'total_usd':16.3976} if path.endswith('/usage') else {'ok':True,'answer':'Captured fake HTTP graph result'})

class Guards(unittest.TestCase):
    def test_start_and_binding_are_durable(self):
        with tempfile.TemporaryDirectory() as d:
            r=m.RunGuard(d,True)
            with self.assertRaises(HTTPException):asyncio.run(r.accept('qa',16.3976))
            r.data['started']=True;r.bind('one')
            asyncio.run(r.accept('qa',16.3976))
            resumed=m.RunGuard(d,True);self.assertEqual(resumed.data['qa'],1)
            with self.assertRaises(HTTPException):resumed.bind('two')
            with self.assertRaises(RuntimeError):m.RunGuard(d,False)
    def test_hard_request_and_dollar_stops(self):
        with tempfile.TemporaryDirectory() as d:
            r=m.RunGuard(d,True);r.data['started']=True
            for _ in range(16):asyncio.run(r.accept('qa',16.3976))
            with self.assertRaises(HTTPException):asyncio.run(r.accept('qa',16.3976))
            for _ in range(2):asyncio.run(r.accept('pitch',16.3976))
            with self.assertRaises(HTTPException):asyncio.run(r.accept('pitch',16.3976))
            asyncio.run(r.accept('summary',16.3976))
            with self.assertRaises(HTTPException):asyncio.run(r.accept('summary',16.3976))
        with tempfile.TemporaryDirectory() as d:
            r=m.RunGuard(d,True);r.data['started']=True
            with self.assertRaises(HTTPException):asyncio.run(r.accept('qa',19.8977))
            self.assertEqual(r.data['qa'],0)
    def test_http_disallows_voice_leads_and_other_mutations(self):
        with tempfile.TemporaryDirectory() as d, TestClient(m.create_app(directory=d)) as client:
            for suffix in ('run/tts','run/stt','run/lead','build','read'):
                self.assertEqual(client.post(f'/api/demos/{m.DEMO}/{suffix}',json={}).status_code,403)
            self.assertEqual(client.post('/stress/start',json={}).status_code,200)
            self.assertEqual(client.post('/stress/start',json={}).status_code,409)
    def test_root_command_is_explicit_and_single_use(self):
        with tempfile.TemporaryDirectory() as d, TestClient(m.create_app(directory=d)) as client:
            self.assertFalse(client.get('/stress/config').json()['run'].get('command_requested',False))
            self.assertEqual(client.post('/stress/command/start',json={}).status_code,200)
            self.assertFalse(client.get('/stress/config').json()['run']['started'])
            self.assertEqual(client.post('/stress/command/start',json={}).status_code,409)
            self.assertEqual(client.post('/stress/start',json={}).status_code,200)
    def test_http_live_fallback_forces_no_voice_and_graph(self):
        FakeHttp.calls=[]
        with tempfile.TemporaryDirectory() as d, patch.object(m.httpx,'AsyncClient',FakeHttp), TestClient(m.create_app(live=True,directory=d)) as client:
            self.assertEqual(client.post('/stress/start',json={}).status_code,200)
            for suffix in ('run/qa','run/pitch'):
                self.assertEqual(client.post(f'/api/demos/{m.DEMO}/{suffix}',json={'session_id':'one','question':'Test','voice_it':True}).status_code,200)
            forwarded=[row for row in FakeHttp.calls if row[0]=='POST']
            self.assertEqual(len(forwarded),2)
            self.assertTrue(all(row[2]['json']['voice_it'] is False and row[2]['json']['runtime_version']==1 for row in forwarded))
    def test_one_frozen_summary_and_session(self):
        with tempfile.TemporaryDirectory() as d, TestClient(m.create_app(directory=d)) as client:
            client.post('/stress/start',json={});body={'id':'one','ended':True,'profile':{'name':m.NAME},'questions':['Test?'],'leads':[]}
            path=f'/api/demos/{m.DEMO}/run/session'
            self.assertEqual(client.post(path,json=body).status_code,200)
            self.assertEqual(client.post(path,json=body).status_code,200)
            self.assertEqual(client.post(path,json={**body,'questions':['Changed?']}).status_code,409)
            self.assertEqual(client.post(path,json={**body,'id':'two'}).status_code,409)
            self.assertEqual(client.get(f'/api/demos/{m.DEMO}/sessions/one').json()['summary']['model'],'offline_synthetic_fixture')
            self.assertEqual(json.loads((Path(d)/'stress-budget.json').read_text())['summary'],1)
    def test_failed_upstream_save_stays_failed_on_duplicate_without_retry(self):
        class FailedHttp(FakeHttp):
            calls=[]
            async def request(self,method,path,**kw):
                if method=='POST':self.calls.append((method,path,kw));raise RuntimeError('Fake upstream unavailable')
                return FakeResponse({'total_usd':16.3976})
        with tempfile.TemporaryDirectory() as d, patch.object(m.httpx,'AsyncClient',FailedHttp), TestClient(m.create_app(live=True,directory=d)) as client:
            client.post('/stress/start',json={});body={'id':'one','ended':True,'profile':{'name':m.NAME},'leads':[]}
            path=f'/api/demos/{m.DEMO}/run/session'
            self.assertEqual(client.post(path,json=body).status_code,502)
            self.assertEqual(client.post(path,json=body).status_code,502)
            self.assertEqual(len(FailedHttp.calls),1)
            saved=json.loads((Path(d)/'stress-budget.json').read_text());self.assertEqual(saved['summary'],1);self.assertNotIn('save_response',saved)
    def test_authoritative_save_excludes_synthetic_audio_and_interruption_kpis(self):
        from server import runtime_metrics
        from types import SimpleNamespace
        body={'id':'one','ended':True,'profile':{},'leads':[],
            'interruptions':[{'detected_at':1000,'stopped_at':1020,'phase':'answer','detection_source':'synthetic'}],
            'turns':[{'question':'Test?','answered':True,'response_kind':'answer',
                'voice_ended':2000,'stt_done':2050,'qa_done':2400,'speech_detected':1900,
                'endpoint_received_at':2050,'server_endpoint_received_at':2040,
                'ack_audio':2100,'answer_audio':2500,'delivery_done':3000}]}
        original=json.loads(json.dumps(body));FakeHttp.calls=[]
        with tempfile.TemporaryDirectory() as d, patch.object(m.httpx,'AsyncClient',FakeHttp), TestClient(m.create_app(live=True,directory=d)) as client:
            client.post('/stress/start',json={})
            path=f'/api/demos/{m.DEMO}/run/session'
            self.assertEqual(client.post(path,json=body).status_code,200)
            self.assertEqual(client.post(path,json=body).status_code,200)
            forwarded=[r[2]['json'] for r in FakeHttp.calls if r[0]=='POST']
            self.assertEqual(len(forwarded),1);saved=forwarded[0]
            self.assertEqual(saved,json.loads((Path(d)/'stress-submitted-session.json').read_text()))
        self.assertEqual(body,original)
        self.assertEqual(saved['evaluation']['synthetic_interruptions'],original['interruptions'])
        self.assertEqual(len(saved['interruptions']),1)
        self.assertEqual(saved['interruptions'][0]['phase'],'answer')
        self.assertEqual(saved['turns'][0]['qa_done'],2400)
        self.assertEqual(saved['turns'][0]['synthetic_delivery_timestamps']['answer_audio'],2500)
        self.assertIsNone(saved['turns'][0]['stt_done'])
        self.assertEqual(m.sanitize_caption_session(saved,live=True),saved)
        def aggregate(record):
            with patch.object(runtime_metrics.storage,'backend',return_value=SimpleNamespace(iter_sessions=lambda _: [record])):
                return runtime_metrics.aggregate('fixture')
        before=aggregate(original);after=aggregate(saved)
        self.assertEqual(before['interruption']['n'],1);self.assertEqual(before['cohorts'][0]['complete_timings'],1)
        self.assertEqual(after['sessions'],1);self.assertEqual(after['cohorts'][0]['turns'],1)
        self.assertEqual(after['interruption']['n'],0);self.assertIsNone(after['interruption']['p50_ms'])
        self.assertEqual(after['cohorts'][0]['complete_timings'],0)
        self.assertEqual(after['cohorts'][0]['measured_responses'],0)
        self.assertEqual(after['cohorts'][0]['useful_answer_timings'],0)
    def test_synthetic_socket_never_uses_stt_or_tts(self):
        with tempfile.TemporaryDirectory() as d, patch.object(m.websockets,'connect',side_effect=AssertionError('Offline upstream forbidden')), TestClient(m.create_app(directory=d)) as client:
            client.post('/stress/start',json={})
            with client.websocket_connect(f'/api/demos/{m.DEMO}/run/live?session_id=one') as ws:
                def send(kind,**extra):ws.send_json({'type':kind,'session_id':'one','turn_id':'t1',**extra})
                send('session.start',mic=True);self.assertEqual(ws.receive_json()['type'],'session.ready')
                send('mic.set',enabled=True,input_generation=1);self.assertEqual(ws.receive_json()['type'],'mic.ready')
                send('audio.input',audio='AA==',input_generation=1)
                send('delivery.speak',utterance_id='u1',text='Synthetic caption')
                chunk=ws.receive_json();self.assertEqual(chunk['type'],'audio.chunk');self.assertTrue(chunk['synthetic'])
                self.assertEqual(ws.receive_json()['type'],'audio.end')
                send('session.end')
    def test_live_socket_forces_mic_false_and_blocks_voice_before_upstream(self):
        class Upstream:
            def __init__(self):self.messages=[];self.q=asyncio.Queue()
            async def send(self,raw):
                data=json.loads(raw);self.messages.append(data)
                if data['type']=='session.start':await self.q.put(json.dumps({'type':'session.ready'}))
                if data['type']=='turn.ask':await self.q.put(json.dumps({'type':'turn.result','turn_id':'t1','utterance_id':'answer1','answer':{'answer':'Fake real-lane adapter result','answered':True}}))
            def __aiter__(self):return self
            async def __anext__(self):
                item=await self.q.get()
                if item is None:raise StopAsyncIteration
                return item
            async def close(self):await self.q.put(None)
        upstream=Upstream();connect_args=[]
        async def connect(url,**kw):connect_args.append((url,kw));return upstream
        with tempfile.TemporaryDirectory() as d, patch.object(m.httpx,'AsyncClient',FakeHttp), patch.object(m.websockets,'connect',side_effect=connect), TestClient(m.create_app(live=True,directory=d)) as client:
            client.post('/stress/start',json={})
            with client.websocket_connect(f'/api/demos/{m.DEMO}/run/live?session_id=one') as ws:
                def send(kind,**extra):ws.send_json({'type':kind,'session_id':'one','turn_id':'t1',**extra})
                send('session.start',mic=True);self.assertEqual(ws.receive_json()['type'],'session.ready')
                send('mic.set',enabled=True,input_generation=1);self.assertEqual(ws.receive_json()['type'],'mic.ready')
                send('audio.input',audio='AA==',input_generation=1)
                send('turn.ask',question='Test',voice_it=True);self.assertEqual(ws.receive_json()['type'],'turn.result')
                send('delivery.request',utterance_id='answer1');self.assertTrue(ws.receive_json()['synthetic'])
                send('delivery.cancel',utterance_id='answer1');send('session.end')
            self.assertEqual(connect_args[0][1]['origin'],'http://127.0.0.1:8896')
            self.assertEqual([x['type'] for x in upstream.messages],['session.start','turn.ask','session.end'])
            self.assertIs(upstream.messages[0]['mic'],False)
            self.assertIs(upstream.messages[1]['voice_it'],False)
            self.assertEqual(upstream.messages[1]['profile']['name'],m.NAME)

if __name__=='__main__':
    try:unittest.main()
    finally:print('OUTBOUND_SOCKET_ATTEMPTS='+str(len(attempts)))
