"""Actual SPA/player teardown with mocked APIs/voice, muted Chromium and no external requests."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import mimetypes
import os
import sys
import tempfile
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
HTML = r'''<!doctype html><meta charset="utf-8">
<link rel="stylesheet" href="/web/styles.css"><link rel="stylesheet" href="/web/player-ui.css">
<style>#tabs{position:relative;z-index:10000;background:white;min-height:40px}#main{height:calc(100vh - 40px)}.play-page{position:fixed!important;inset:40px 0 0!important}</style>
<div id="health"></div><nav id="tabs"><a data-tab="home" href="#/home">Home</a><a data-tab="studio" href="#/studio/dm_12345678/align">Align</a></nav>
<main id="main"></main><div id="toasts"></div>
<script type="module">
window.fetch=()=>Promise.reject(new Error('Unexpected network request'));
window.clients=[];window.preloadLoads=0;window.posts=[];window.subscriptions=[];window.held=[];window.savedVisits=new Map();window.questions=[];
window.Audio=function(url){const el=document.createElement('audio');if(url)el.src=url;el.load=()=>{if(el.getAttribute('src'))window.preloadLoads++;};return el;};
const {api}=await import('/web/api.js');
const bundle={name:'Navigation fixture',version:1,language:'en-IN',product:{name:'Fixture'},voice:{provider:'sarvam'},runtime:{version:1,continuous_voice:true},intake:{q1:'What matters to you?'},slides:[{id:'hero',kind:'hero_open',title:'Fixture',lines:[]}],facts:[],ctas:[],fillers:{welcome:{text:'Welcome',audio:'/fixture.wav'}}};
const state={demo:{id:'dm_12345678',name:'Fixture',status:'ready',approvals:{},settings:{},stages:{}},cards:null,conversation:[],sessions:[],leads:[],bundle_ready:true,running:false};
window.fixtureBundle=bundle;
api.get=async path=>{
 if(window.holdBundles&&path.endsWith('/bundle'))return new Promise((resolve,reject)=>held.push({resolve,reject}));
 if(path.endsWith('/bundle'))return structuredClone(bundle);
 if(path==='/api/demos')return [];
 if(path==='/api/runtime/transport'){
   if(window.holdCapability)return new Promise(resolve=>{window.releaseCapability=()=>{window.holdCapability=false;resolve(window.transportCapability);};});
   return window.transportCapability||{transport:'websocket',livekit_enabled:false,livekit_available:false,mode:'disabled'};
 }
 if(path==='/api/health'||path.endsWith('/readiness'))return {};
 return structuredClone(state);
};
api.post=async(path,body,options={})=>{posts.push({path,body:structuredClone(body)});
 if(path.endsWith('/run/qa'))return new Promise(resolve=>{const q={resolve,aborted:false};questions.push(q);options.signal?.addEventListener('abort',()=>{q.aborted=true;});});
 if(path.endsWith('/run/session')){if(window.failSave){window.failSave=false;throw new Error('Mock save unavailable');}if(window.deferSave){window.deferSave=false;return new Promise((resolve,reject)=>{window.rejectSave=reject;});}savedVisits.set(body.id,structuredClone(body));}return {};};api.patch=async()=>({});
api.subscribe=(id,fn)=>{const sub={closed:false,fn};subscriptions.push(sub);return()=>{sub.closed=true;};};
window.releaseBundles=()=>{window.holdBundles=false;for(const p of held.splice(0))p.resolve(structuredClone(bundle));};
window.rejectBundles=()=>{window.holdBundles=false;for(const p of held.splice(0))p.reject(new Error('Stale fixture error'));};
window.activate=()=>Object.assign(clients.at(-1),{mic:true,ready:true,socketOpen:true,playing:true});
document.documentElement.requestFullscreen=()=>Promise.resolve();
await import('/web/app.js');window.ready=true;
</script>'''
VOICE = r'''export { meaningfulTranscript } from '/web/player/live-voice-actual.js';
export class LiveVoiceClient {
 constructor(options){this.options=options;this.mic=false;this.closed=false;this.closeCalls=0;window.clients.push(this);}
 setMuted(){} unlockOutput(){return Promise.resolve();} connect(){this.ready=true;this.socketOpen=true;return Promise.resolve();}
 setMicEnabled(value){this.mic=value;return Promise.resolve(value);} startCapture(){this.mic=true;return Promise.resolve(true);}
 stopCapture(){this.mic=false;} interrupt(){this.playing=false;} close(){this.closeCalls++;this.closed=true;this.mic=false;this.ready=false;this.socketOpen=false;this.playing=false;}
 endSpeechHold(){return false;}
}'''
LIVEKIT = r'''import {LiveVoiceClient} from '/web/player/live-voice.js';
export class LiveKitVoiceClient extends LiveVoiceClient {
 constructor(options){super(options);this.transport='livekit';}
}'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/':
            data, mime = HTML.encode(), 'text/html'
        elif path == '/web/player/live-voice.js':
            data, mime = VOICE.encode(), 'text/javascript'
        elif path == '/web/player/live-voice-actual.js':
            data, mime = (ROOT / 'web/player/live-voice.js').read_bytes(), 'text/javascript'
        elif path == '/web/player/livekit-voice.js':
            data, mime = LIVEKIT.encode(), 'text/javascript'
        elif path.startswith('/web/'):
            file = (ROOT / path.lstrip('/')).resolve()
            if not file.is_relative_to(ROOT / 'web') or not file.is_file():
                self.send_error(404); return
            data, mime = file.read_bytes(), mimetypes.guess_type(file.name)[0]
        else:
            self.send_error(404); return
        self.send_response(200)
        self.send_header('Content-Type', mime or 'application/octet-stream')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; media-src 'none'")
        self.end_headers(); self.wfile.write(data)


def main():
    isolated = tempfile.TemporaryDirectory(prefix='player-navigation-contract-')
    os.environ.update(MOCK_LLM='1', CLOUD_SYNC='0', STORAGE_BACKEND='local', DEMO_STUDIO_DATA=isolated.name+'/demos', DEMO_STUDIO_GRAPH_DB=isolated.name+'/graph.sqlite')
    sys.path.insert(0, str(ROOT))
    from server.crawl import _render_executable
    passed, errors, rejected = [], [], []
    def check(name, ok):
        assert ok, name
        passed.append(name)
        print('PASS', name, flush=True)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=_render_executable(pw.chromium), chromium_sandbox=True, headless=True, args=['--mute-audio', '--disable-background-networking'])
            context = browser.new_context(viewport={'width':1440,'height':1000})
            def guard(route):
                if route.request.url.startswith(base + '/') and route.request.method == 'GET': route.continue_()
                else: rejected.append(route.request.url); route.abort()
            context.route('**/*', guard)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base + '/?mute=1#/home')
            page.wait_for_function('window.ready')

            def play(rehearse=False):
                before = page.evaluate('clients.length')
                page.evaluate("location.hash=" + repr('#/studio/dm_12345678/rehearse' if rehearse else '#/play/dm_12345678'))
                page.wait_for_function(f'clients.length>{before} && !!document.querySelector(".pl-welcome")')
                page.evaluate('activate()')
                return before

            def closed(index):
                page.wait_for_function(f'clients[{index}].closed')
                return page.evaluate(f'!clients[{index}].mic && !clients[{index}].socketOpen && !clients[{index}].playing && clients[{index}].closeCalls===1')

            old = play(); page.get_by_role('link', name='Home', exact=True).click()
            check('top Home disposes standalone capture, output and socket once', closed(old))
            old = play(); page.locator('#tabs').get_by_role('link', name='Align', exact=True).click()
            check('Align navigation disposes standalone player', closed(old))
            old = play(); page.evaluate('history.back()')
            check('browser Back disposes standalone player', closed(old))
            old = play(True); page.locator('#tabs').get_by_role('link', name='Align', exact=True).click()
            check('Rehearse to Align disposes embedded player and SSE', closed(old) and page.evaluate('subscriptions.slice(0,-1).every(s=>s.closed)'))
            old = play(True); page.get_by_role('button', name='Full screen', exact=True).click()
            page.wait_for_function(f'clients.length>{old+1}')
            check('Rehearse fullscreen closes old transport before new player', closed(old) and page.evaluate('clients.filter(c=>!c.closed).length===1'))

            # Leave before standalone and embedded bundle reads complete. Both
            # successful and failed stale responses must leave the current view alone.
            for rehearse in (False, True):
                page.get_by_role('link', name='Home', exact=True).click()
                page.wait_for_function('location.hash==="#/home" && !document.querySelector(".pl-welcome")')
                count = page.evaluate('clients.length')
                page.evaluate('window.holdBundles=true')
                page.evaluate("location.hash=" + repr('#/studio/dm_12345678/rehearse' if rehearse else '#/play/dm_12345678'))
                page.wait_for_function('held.length>=1')
                page.get_by_role('link', name='Home', exact=True).click()
                page.evaluate('releaseBundles()')
                page.wait_for_timeout(50)
                check(f'{"Rehearse" if rehearse else "standalone"} delayed bundle cannot mount after route leaves', page.evaluate(f'clients.length==={count} && location.hash==="#/home" && !document.querySelector(".pl-welcome")'))
            page.evaluate('window.holdBundles=true;location.hash="#/play/dm_12345678"')
            page.wait_for_function('held.length>=1')
            page.get_by_role('link', name='Home', exact=True).click(); page.evaluate('rejectBundles()')
            page.wait_for_timeout(50)
            check('stale bundle error cannot redirect or toast on the new screen', page.evaluate('location.hash==="#/home" && !document.querySelector(".toast")'))

            check('destroy cancels delayed preloads and is idempotent', page.evaluate('''async()=>{
              const {mountPlayer}=await import('/web/player/player.js');const host=document.createElement('div');document.body.append(host);
              const start=preloadLoads;const p=mountPlayer(host,structuredClone(fixtureBundle),{});p.destroy();p.destroy();
              await new Promise(r=>setTimeout(r,220));host.remove();return preloadLoads===start;
            }'''))
            check('all departed transports are closed', page.evaluate('clients.every(c=>c.closed)'))
            check('no paid runtime API was requested', page.evaluate('posts.length===0'))
            play(); page.evaluate('window.failSave=true')
            page.get_by_role('button', name='Stop and see the summary', exact=True).click()
            page.wait_for_function('document.querySelector(".session-save-status")?.textContent.includes("Couldn\'t save")')
            check('failed visit save remains visible beside the completed recap', page.locator('.pl-handoff.open').count() == 1 and page.get_by_role('button', name='Retry save', exact=True).is_visible())
            page.get_by_role('button', name='Retry save', exact=True).click()
            page.wait_for_function('document.querySelector(".session-save-status")?.textContent.includes("Visit saved.")')
            check('retry saves one visit using the same immutable record and ID', page.evaluate('savedVisits.size===1 && posts.length===2 && JSON.stringify(posts[0].body)===JSON.stringify(posts[1].body)'))
            page.get_by_role('button', name='Done', exact=True).click()
            check('Done does not repeat an already successful save', page.evaluate('posts.length===2'))
            page.get_by_role('link', name='Home', exact=True).click()
            play()
            page.get_by_role('button', name='Stop and see the summary', exact=True).click()
            page.wait_for_function('document.querySelector(".session-save-status")?.textContent.includes("Visit saved.")')
            page.get_by_role('button', name='Request dealership follow-up', exact=True).click()
            page.locator('.lead-card input[aria-label="Your name"]').fill('Revision fixture')
            page.locator('.lead-card input[aria-label="10-digit mobile number"]').fill('9876543210')
            page.get_by_role('button', name='Request a callback', exact=True).click()
            page.wait_for_function('!document.querySelector(".pl-lead.open")')
            page.get_by_role('button', name='Done', exact=True).click()
            page.wait_for_function('[...savedVisits.values()].some(s=>s.profile?.name==="Revision fixture" && s.leads?.length===1)')
            check('recap lead then Done saves changed name, lead and escalation under the same visit ID', page.evaluate('''()=>{
              const reports=posts.filter(p=>p.path.endsWith('/run/session'));const latest=reports.at(-1).body;
              const revisions=reports.filter(p=>p.body.id===latest.id);
              return revisions.length===2 && revisions[0].body.leads.length===0 && latest.profile.name==='Revision fixture' && latest.leads[0].phone==='9876543210' && latest.escalations.some(s=>s.includes('9876543210'));
            }'''))
            page.get_by_role('link', name='Home', exact=True).click()
            play(); page.evaluate('window.deferSave=true')
            page.get_by_role('button', name='Stop and see the summary', exact=True).click()
            page.wait_for_function('typeof window.rejectSave==="function"')
            pending_count = page.evaluate('posts.length')
            page.get_by_role('button', name='Done', exact=True).click()
            page.evaluate('rejectSave(new Error("Late mock save failure"))')
            page.wait_for_function('document.querySelector(".toast")?.textContent.includes("Couldn\'t save this visit")')
            check('late save failure after Done is visible without reopening or blocking the recap', page.locator('.pl-handoff.open').count() == 0 and page.evaluate(f'posts.length==={pending_count}'))
            page.get_by_role('link', name='Home', exact=True).click()
            play(); page.evaluate('clients.at(-1).ready=false;document.querySelector(".pl-welcome").remove()')
            page.locator('.pl-reply input').fill('How much space is there?')
            page.locator('.pl-reply').evaluate('form=>form.requestSubmit()')
            page.wait_for_function('questions.length===1')
            page.get_by_role('link', name='Home', exact=True).click()
            page.wait_for_function('questions[0].aborted')
            page.wait_for_function('posts.some(p=>p.path.endsWith("/run/session")&&p.body.transcript?.some(t=>t.text==="How much space is there?"))')
            check('navigation saves one active transcript using its original ID without ending it', page.evaluate('''()=>{
              const question=posts.find(p=>p.path.endsWith('/run/qa')&&p.body.question==='How much space is there?');
              const reports=posts.filter(p=>p.path.endsWith('/run/session')&&p.body.id===question.body.session_id);
              return reports.length===1 && reports[0].body.ended===false && reports[0].body.transcript.some(t=>t.role==='user'&&t.text===question.body.question);
            }'''))
            page.evaluate('questions[0].resolve({answered:true,answer:"Obsolete answer"})')
            check('navigation aborts the HTTP question and ignores a late answer', page.locator('.pl').count() == 0)
            play(); page.evaluate('clients.at(-1).ready=false;document.querySelector(".pl-welcome").remove()')
            page.locator('.pl-reply input').fill('What is the warranty?')
            page.locator('.pl-reply').evaluate('form=>form.requestSubmit()')
            page.wait_for_function('questions.length===2')
            page.wait_for_function('questions[1].aborted', timeout=18000)
            page.wait_for_function('document.querySelector(".pl-cap .txt")?.textContent.includes("couldn\'t reach my notes")')
            check('HTTP fallback times out and uses the existing honest failure caption', page.locator('.pl-cap .txt').text_content().startswith("I couldn't reach my notes"))
            page.evaluate('questions[1].resolve({answered:true,answer:"Obsolete timeout answer"})')
            page.wait_for_timeout(30)
            check('late timed-out HTTP answer cannot replace the failure caption', 'Obsolete' not in page.locator('.pl-cap .txt').text_content())
            page.get_by_role('link', name='Home', exact=True).click()
            page.evaluate("window.transportCapability={transport:'livekit',livekit_enabled:true,livekit_available:true,mode:'hosted'}")
            for rehearse in (False, True):
                old = play(rehearse)
                check(f'{"Rehearse" if rehearse else "public player"} normal URL uses server-selected LiveKit', page.evaluate(f'clients[{old}].transport==="livekit" && !location.search.includes("voice_transport")'))
                page.get_by_role('link', name='Home', exact=True).click()
                check(f'{"Rehearse" if rehearse else "public player"} closes its selected LiveKit client on navigation', closed(old))
            for rehearse in (False, True):
                count = page.evaluate('clients.length')
                page.evaluate('window.holdCapability=true')
                page.evaluate("location.hash=" + repr('#/studio/dm_12345678/rehearse' if rehearse else '#/play/dm_12345678'))
                page.wait_for_function('typeof window.releaseCapability==="function"')
                page.get_by_role('link', name='Home', exact=True).click()
                page.evaluate('releaseCapability();delete window.releaseCapability')
                page.wait_for_timeout(50)
                check(f'{"Rehearse" if rehearse else "public player"} stale capability cannot open capture after navigation', page.evaluate(f'clients.length==={count} && !document.querySelector(".pl-welcome")'))
            page.evaluate("window.transportCapability={transport:'websocket',livekit_enabled:false,livekit_available:false,mode:'disabled'}")
            play(True); page.evaluate('clients.at(-1).ready=false;document.querySelector(".pl-welcome").remove()')
            page.locator('.pl-reply input').fill('Keep this rehearsal question.')
            page.locator('.pl-reply').evaluate('form=>form.requestSubmit()')
            page.wait_for_function('questions.length===3')
            page.get_by_role('link', name='Home', exact=True).click()
            page.wait_for_function('posts.some(p=>p.path.endsWith("/run/session")&&p.body.transcript?.some(t=>t.text==="Keep this rehearsal question."))')
            check('Rehearse teardown also saves its active transcript once without marking it ended', page.evaluate('''()=>{
              const question=posts.find(p=>p.path.endsWith('/run/qa')&&p.body.question==='Keep this rehearsal question.');
              const reports=posts.filter(p=>p.path.endsWith('/run/session')&&p.body.id===question.body.session_id);
              return reports.length===1 && reports[0].body.ended===false && questions[2].aborted;
            }'''))
            check('no browser exceptions or outbound requests', not errors and not rejected)
            browser.close()
        print(f'Player navigation contracts: {len(passed)}/{len(passed)}; OUTBOUND_ATTEMPTS {len(rejected)}', flush=True)
    finally:
        server.shutdown(); server.server_close()
        isolated.cleanup()
    if errors:
        raise AssertionError(errors)


if __name__ == '__main__':
    main()
