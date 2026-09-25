"""Post-cutover public RTC join/close only. No capture, questions, speech or writes."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path('/Users/macbook/Documents/demo-studio')
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base', default='https://13-202-0-79.sslip.io')
parser.add_argument('--signal', default='wss://rtc.13-202-0-79.sslip.io')
parser.add_argument('--turn-host', default='turn.13-202-0-79.sslip.io')
parser.add_argument('--rtc-host', default='172.31.13.9')
parser.add_argument('--demo', default='dm_29df0418')
parser.add_argument('--output', type=Path, default=ROOT/'output/livekit-production-2026-09-25/public-join')
args = parser.parse_args()
base,signal = urlsplit(args.base),urlsplit(args.signal)
assert base.scheme == 'https' and base.hostname == '13-202-0-79.sslip.io' and base.path in ('','/') and not base.query and not base.fragment and not base.username
assert signal.scheme == 'wss' and signal.hostname == 'rtc.13-202-0-79.sslip.io' and signal.port in (None,443) and signal.path in ('','/') and not signal.query and not signal.fragment and not signal.username
assert args.turn_host == 'turn.13-202-0-79.sslip.io' and args.rtc_host == '172.31.13.9'
assert args.demo == 'dm_29df0418'
args.output.mkdir(parents=True,exist_ok=True)
blocked,errors,sockets,posts,checks = [],[],[],[],[]
def safe(url):
    p=urlsplit(url);return p.scheme+'://'+p.netloc+p.path

def check(name,value):
    assert value,name
    checks.append(name);print('PASS',name,flush=True)

with tempfile.TemporaryDirectory(prefix='livekit-public-join-import-') as tmp:
    os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local',DEMO_STUDIO_DATA=tmp+'/data',DEMO_STUDIO_GRAPH_DB=tmp+'/graph.sqlite')
    from server.crawl import _render_executable
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=_render_executable(pw.chromium),args=['--mute-audio','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE '+base.hostname+', EXCLUDE '+signal.hostname+', EXCLUDE '+args.turn_host])
        context=browser.new_context(viewport={'width':1440,'height':960},service_workers='block')
        context.add_init_script('''(() => {
          window.publicPCs=[];window.captureAttempts=0;
          const PC=RTCPeerConnection;window.RTCPeerConnection=class extends PC {constructor(...args){super(...args);publicPCs.push(this);}};
          navigator.mediaDevices.getUserMedia=async()=>{captureAttempts++;throw new Error('Public no-input smoke forbids capture');};
        })();''')
        def route(r):
            p=urlsplit(r.request.url)
            if p.scheme in ('data','blob'):return r.continue_()
            if p.hostname=='fonts.googleapis.com':return r.fulfill(status=200,content_type='text/css',body='/* offline system fonts */')
            if p.scheme in ('http','https') and p.netloc in (base.netloc,signal.netloc):
                if r.request.method in ('GET','HEAD'):return r.continue_()
                if r.request.method=='POST' and p.netloc==base.netloc and p.path==f'/api/demos/{args.demo}/run/livekit/token':
                    body=r.request.post_data_json
                    assert body.get('session_id','').startswith('lk_public_join_')
                    posts.append(p.path);return r.continue_()
            blocked.append(safe(r.request.url));return r.abort()
        def websocket(ws):
            p=urlsplit(ws.url)
            if p.scheme==signal.scheme and p.netloc==signal.netloc:
                sockets.append(safe(ws.url));return ws.connect_to_server()
            blocked.append(safe(ws.url));ws.close()
        context.route('**/*',route);context.route_web_socket('**/*',websocket)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(args.base+'/?mute=1#/play/'+args.demo)
            page.get_by_role('button',name='Explore with me',exact=True).wait_for(timeout=20000)
            check('actual public publication opens without a transport flag','voice_transport' not in page.url)
            result=page.evaluate('''async demo => {
              const {resolveLiveClientFactory}=await import('/web/player/voice-transport.js');
              const capability=await(await fetch('/api/runtime/transport')).json();
              const bundle=await(await fetch(`/api/demos/${demo}/bundle`)).json();
              const state=window.publicJoinQA={errors:[],controls:[],capability};
              const factory=await resolveLiveClientFactory(bundle,{loadCapability:async()=>capability,search:''});
              if(typeof factory!=='function')throw new Error('Public server did not select LiveKit');
              const client=state.client=factory({url:`/api/demos/${demo}/run/live`,sessionId:'lk_public_join_'+crypto.randomUUID().replaceAll('-',''),onError:e=>state.errors.push(e)});
              const send=client.send.bind(client);
              client.send=(type,data={})=>{
                if(!['session.start','session.end','turn.interrupt','trial.ping'].includes(type)||data.mic===true)throw new Error('Public no-input smoke forbids runtime input');
                state.controls.push({type,mic:data.mic??null});return send(type,data);
              };
              client.setMuted(true);await client.connect();
              return {capability,ready:client.ready,transport:client.transport,mic:client.mic,captureAttempts};
            }''',args.demo)
            check('public capability selects configured hosted LiveKit',result['capability']['transport']=='livekit' and result['capability']['mode']=='hosted' and result['capability']['livekit_available'])
            check('public no-input RTC session becomes ready',result['ready'] and result['transport']=='livekit')
            check('public join keeps microphone disabled and never requests a device',not result['mic'] and result['captureAttempts']==0)
            page.wait_for_function("()=>publicPCs.some(p=>p.connectionState==='connected')",timeout=10000)
            stats=page.evaluate('''async expected => {
              const all=(await Promise.all(publicPCs.map(async p=>[...(await p.getStats()).values()]))).flat();
              const pair=all.find(v=>v.type==='candidate-pair'&&v.state==='succeeded'&&v.nominated);
              const local=all.find(v=>v.id===pair?.localCandidateId),remote=all.find(v=>v.id===pair?.remoteCandidateId);
              let relay;const relayURL=local?.url||'';try{relay=new URL(relayURL.replace(/^turns?:/,'http://'));}catch{}
              return {pairState:pair?.state,localType:local?.candidateType,relayProtocol:local?.relayProtocol||null,
                relayTLS:local?.relayProtocol==='tls'||/^turns:/.test(relayURL),relayPort443:relay?.port==='443',relayExpectedHost:relay?.hostname===expected.turn,
                remoteExpectedHost:(remote?.address||remote?.ip)===expected.rtc,bytesSent:pair?.bytesSent||0,
                microphoneTracks:publicJoinQA.client.socket.room.localParticipant.audioTrackPublications.size};
            }''',{'turn':args.turn_host,'rtc':args.rtc_host})
            check('public data channel uses authenticated TLS relay on443',stats['pairState']=='succeeded' and stats['localType']=='relay' and stats['relayTLS'] and stats['relayPort443'] and stats['relayExpectedHost'] and stats['remoteExpectedHost'] and stats['bytesSent']>0)
            check('public session publishes no microphone track',stats['microphoneTracks']==0)
            page.screenshot(path=str(args.output/'public-bmw-welcome.png'),full_page=False)
            closed=page.evaluate('''async()=>{const socket=publicJoinQA.client.socket;publicJoinQA.client.close();await new Promise(r=>setTimeout(r,300));return{closed:socket.readyState===3,ready:publicJoinQA.client.ready,captureAttempts,controls:publicJoinQA.controls,errors:publicJoinQA.errors};}''')
            check('public join closes without capture, question or speech',closed['closed'] and not closed['ready'] and closed['captureAttempts']==0 and all(c['type'] in ('session.start','session.end','turn.interrupt','trial.ping') for c in closed['controls']))
            check('only one authorized token POST and public signaling were used',len(posts)==1 and sockets and not blocked)
            check('public browser has no uncaught error',not errors and not closed['errors'])
            receipt={'passed':len(checks),'total':len(checks),'checks':checks,'rtc':stats,'controls':closed['controls'],'provider_calls':0,'capture_attempts':0,'microphone_tracks':0,'runtime_questions':0,'production_visit_writes':0,'errors':errors,'blocked':blocked}
            (args.output/'results.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
        except Exception:
            page.screenshot(path=str(args.output/'failure.png'),full_page=False)
            (args.output/'failure.json').write_text(json.dumps({'passed':checks,'errors':errors,'blocked':blocked,'posts':posts,'sockets':sockets},indent=2)+'\n')
            raise
        finally:
            try:page.evaluate('window.publicJoinQA?.client?.close()')
            except Exception:pass
            browser.close()
