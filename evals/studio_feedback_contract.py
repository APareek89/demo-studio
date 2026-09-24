"""Actual Studio navigation and Rehearse chat with isolated API/player boundaries."""
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
<link rel="stylesheet" href="/web/styles.css"><link rel="stylesheet" href="/web/design-system.css"><link rel="stylesheet" href="/web/studio-ui.css"><link rel="stylesheet" href="/web/player-ui.css">
<header class="top"><a class="brand" href="#/home">DemoStudio</a><nav class="tabs" id="tabs"><a data-tab="home" href="#/home">Home</a><a data-tab="demos" href="#/demos">My demos</a><a data-tab="studio" href="#/studio">Studio</a><a data-tab="playground" href="#/playground">Playground</a><a data-tab="observability" href="#/observability">Observability</a></nav><div id="health"></div></header>
<main id="main"></main><div id="toasts" class="toasts"></div>
<script type="module">
window.fetch=()=>Promise.reject(new Error('Unexpected network request'));
window.calls=[];window.players=[];window.subscriptions=[];window.created=0;window.feedback=[];window.formPending=[];window.creations=[];
const saved={id:'dm_12345678',name:'Saved product',product:{name:'Saved product',url:'https://maker.example/product'},sources:[{id:'src_old',name:'reviewed.txt',kind:'document',role:'product',size:10}],status:'ready',version:2,approvals:{},settings:{pitch_minutes:3,languages:['en-IN']},stages:{}};
window.saved=structuredClone(saved);window.states=new Map([[saved.id,{demo:saved,cards:null,conversation:[],sessions:[],leads:[],running:false,bundle_ready:true}]]);
window.emit=(type,event)=>subscriptions.filter(s=>!s.closed).forEach(s=>s.fn(type,event));
const {api}=await import('/web/api.js');
api.get=async path=>{calls.push({method:'GET',path});
 if(path==='/api/health')return {};
 if(path==='/api/demos')return [...states.values()].map(s=>structuredClone(s.demo));
 if(path.startsWith('/api/voices'))return {voices:[{id:'priya',label:'Priya'}],current:'priya',provider:'sarvam',chain:['sarvam'],stt:'sarvam',setting_key:'voice_name'};
 if(path.endsWith('/readiness'))return {};
 const id=path.split('/')[3];if(window.failRefresh&&path==='/api/demos/dm_12345678'){window.failRefresh=false;throw new Error('Fixture refresh unavailable');}if(path.endsWith('/bundle'))return {name:states.get(id)?.demo.name||'Fixture',slides:[],runtime:{}};
 if(!states.has(id))throw new Error('Unknown fixture path '+path);return structuredClone(states.get(id));};
api.post=async(path,body)=>{calls.push({method:'POST',path,body});
 if(path==='/api/demos'){if(window.holdCreate)await new Promise(resolve=>creations.push(resolve));created++;const demo={...structuredClone(saved),id:'dm_new0000'+created,name:'Untitled demo',product:{name:'Untitled demo',url:''},sources:[],status:'sources',version:0};states.set(demo.id,{demo,cards:null,conversation:[],running:false,bundle_ready:false});return structuredClone(demo);}
 return {};};
api.patch=async(path,body)=>{calls.push({method:'PATCH',path,body});const state=states.get(path.split('/')[3]);if(!state)throw new Error('Unknown patch');for(const[k,v]of Object.entries(body))state.demo[k]=typeof v==='object'?{...state.demo[k],...v}:v;return structuredClone(state.demo);};
api.form=async(path,body)=>{const row={method:'FORM',path,message:body.get('message'),context:body.get('context'),files:await Promise.all(body.getAll('files').map(async f=>({name:f.name,text:await f.text()})))};calls.push(row);
 if(window.holdFeedback)return new Promise(resolve=>formPending.push(()=>resolve({reply:'Stale reply'})));
 if(window.failFeedback){window.failFeedback=false;throw new Error('Fixture upload unavailable');}
 const state=states.get(path.split('/')[3]);
 if(path.endsWith('/sources')){const added=row.files.map((f,i)=>({id:'new'+i,name:f.name,kind:'document',role:body.get('role')}));state.demo.sources.push(...added);return{sources:structuredClone(state.demo.sources),added};}
 const t=Date.now()/1000;state.conversation.push({role:'user',text:row.message,t,attachments:row.files},{role:'agent',text:'Review the changed cards in Align.',t:t+.001});feedback.push(row);if(window.replyBeforeRefresh){window.replyBeforeRefresh=false;emit('message',{message:state.conversation.at(-1)});window.failRefresh=true;}return {reply:'Review the changed cards in Align.'};};
api.subscribe=(id,fn)=>{const s={id,fn,closed:false};subscriptions.push(s);return()=>s.closed=true;};
await import('/web/app.js');window.ready=true;
</script>'''
# Use the actual nav markup so compact-layout checks include branding and Workspace.
_shell = (ROOT / 'web/index.html').read_text()
_header = _shell[_shell.index('<header class="top">'):_shell.index('</header>') + len('</header>')]
HTML = HTML[:HTML.index('<header class="top">')] + _header + HTML[HTML.index('</header>') + len('</header>'):]
PLAYER = r'''export function mountPlayer(host,bundle,api){const entry={closed:false,pauseCalls:0};window.players.push(entry);host.innerHTML='<div class="fixture-demo" style="width:100%;height:100%;background:#fff">Reviewed demo preview</div>';return {destroy(){entry.closed=true},pause(){entry.pauseCalls++},context(){return {slide_id:'reviewed-slide',line:1}},restart(){}};}'''


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == '/': data, mime = HTML.encode(), 'text/html'
        elif path == '/web/player/player.js': data, mime = PLAYER.encode(), 'text/javascript'
        elif path.startswith('/web/'):
            file = (ROOT / path.lstrip('/')).resolve()
            if not file.is_relative_to(ROOT/'web') or not file.is_file(): self.send_error(404); return
            data, mime = file.read_bytes(), mimetypes.guess_type(file.name)[0]
        else: self.send_error(404); return
        self.send_response(200); self.send_header('Content-Type', mime or 'application/octet-stream')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'")
        self.end_headers(); self.wfile.write(data)


def main():
    with tempfile.TemporaryDirectory(prefix='studio-feedback-contract-') as tmp:
        os.environ.update(MOCK_LLM='1', CLOUD_SYNC='0', STORAGE_BACKEND='local', DEMO_STUDIO_DATA=tmp+'/data', DEMO_STUDIO_GRAPH_DB=tmp+'/graph.sqlite')
        sys.path.insert(0, str(ROOT))
        from server.crawl import _render_executable
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        passed=[];errors=[];outbound=[]
        def check(name, value):
            assert value, name
            passed.append(name);print('PASS',name,flush=True)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=_render_executable(pw.chromium),chromium_sandbox=True,headless=True,args=['--mute-audio','--disable-background-networking'])
                context=browser.new_context(viewport={'width':1440,'height':1000});base=f'http://127.0.0.1:{server.server_port}'
                def guard(route):
                    if route.request.url.startswith(base+'/') and route.request.method=='GET': route.continue_()
                    else: outbound.append(route.request.url);route.abort()
                context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(base+'/#/studio');page.wait_for_selector('#source-product-name');page.wait_for_function('window.ready')
                check('Studio nav starts blank without fetching an existing demo or creating a record',page.locator('#source-product-name').input_value()=='' and page.locator('#source-product-url').input_value()=='' and page.evaluate("created===0 && !calls.some(c=>c.path==='/api/demos'||/null|undefined/.test(c.path))"))
                page.locator('#tabs a[data-tab=studio]').click();page.wait_for_selector('#source-product-name')
                check('repeated direct Studio nav stays empty with no draft records',page.evaluate('created===0') and page.locator('#source-product-name').input_value()=='')
                page.locator('#source-product-name').fill('New product');page.locator('#source-product-url').click()
                page.wait_for_function("created===1 && location.hash.includes('dm_new00001') && states.get('dm_new00001').demo.product.name==='New product'")
                check('first meaningful save lazily creates one ID and adopts its explicit Sources URL',page.locator('#source-product-name').input_value()=='New product')
                page.locator('input[type=file][aria-label="Catalogue, spec sheet, price list"]').set_input_files({'name':'new.txt','mimeType':'text/plain','buffer':b'New source'})
                page.wait_for_function("states.get('dm_new00001').demo.sources.length===1")
                check('upload reuses the lazy ID and keeps prior saved demo untouched',page.evaluate("created===1 && JSON.stringify(states.get(saved.id).demo)===JSON.stringify(saved)"))
                page.locator('#tabs a[data-tab=studio]').click();page.wait_for_selector('#source-product-name')
                check('Studio nav from a saved workspace returns to a blank unsaved form',page.locator('#source-product-name').input_value()=='' and page.evaluate('created===1'))
                page.evaluate("location.hash='#/studio/dm_12345678/sources'");page.wait_for_function("document.querySelector('#source-product-name')?.value==='Saved product'")
                check('explicit demo URL preserves saved name, URL and source library',page.locator('#source-product-url').input_value()=='https://maker.example/product' and page.get_by_text('reviewed.txt',exact=True).count()==1)
                page.evaluate("location.hash='#/demos'");page.get_by_role('link',name='Open studio',exact=True).first.click()
                page.wait_for_selector('.rehearse-feedback')
                check('My demos Open Studio still opens its existing demo',page.evaluate("location.hash==='#/studio/dm_12345678/rehearse' && created===1"))
                check('Rehearse contains only chat and preview beside unchanged steps rail',page.locator('.rail .step').count()==4 and page.locator('.rehearse-page-head,.rehearse .rpanel,.rehearse .readiness-panel').count()==0 and page.locator('.rehearse-feedback').count()==1 and page.locator('.player-host').count()==1)
                check('feedback occupies the full preview height',page.evaluate("(()=>{const a=document.querySelector('.rehearse-feedback').getBoundingClientRect(),b=document.querySelector('.player-host').getBoundingClientRect();return Math.abs(a.top-b.top)<1&&Math.abs(a.height-b.height)<1&&b.bottom<=innerHeight+1})()"))
                read_count=page.evaluate("calls.filter(c=>c.path.endsWith('/readiness')).length")
                page.get_by_role('textbox',name='Demo feedback',exact=True).fill('Explain this earlier')
                page.locator('input[aria-label="Feedback attachments"]').set_input_files({'name':'proof.txt','mimeType':'text/plain','buffer':b'Reviewed support'})
                page.get_by_role('button',name='Send',exact=True).click();page.wait_for_function('feedback.length===1')
                page.get_by_text('Review the changed cards in Align.',exact=True).wait_for()
                check('feedback sends attachment bytes and player context through existing human-review workflow',page.evaluate("feedback[0].context==='rehearse'&&feedback[0].files[0].text==='Reviewed support'&&feedback[0].message.includes('reviewed-slide')&&!calls.some(c=>c.path.endsWith('/build'))"))
                check('successful feedback clears composer and deduplicates persisted messages',page.get_by_role('textbox',name='Demo feedback',exact=True).input_value()=='' and page.locator('.attach').inner_text()=='' and page.get_by_text('Review the changed cards in Align.',exact=True).count()==1)
                page.evaluate("emit('status',{status:'reading'});emit('progress',{stage:'understand',message:'Reading attached evidence'})")
                check('source progress pauses preview and prevents overlapping requests',page.locator('.feedback-progress').inner_text()=='understand · Reading attached evidence' and page.get_by_role('button',name='Send',exact=True).is_disabled() and page.evaluate('players.at(-1).pauseCalls===1'))
                page.evaluate("emit('phase_done',{phase:'revise'})");page.get_by_role('button',name='Send',exact=True).wait_for(state='visible')
                check('revision completion directs review without starting Build', 'Review the affected cards' in page.locator('.feedback-progress').inner_text() and page.evaluate("!calls.some(c=>c.path.endsWith('/build'))"))
                page.get_by_role('textbox',name='Demo feedback',exact=True).fill('Keep this retry')
                page.locator('input[aria-label="Feedback attachments"]').set_input_files({'name':'retry.txt','mimeType':'text/plain','buffer':b'Retry evidence'})
                page.evaluate('window.failFeedback=true');page.get_by_role('button',name='Send',exact=True).click();page.locator('.feedback-progress.error').wait_for()
                check('failed feedback keeps text/files and exposes a retryable error',page.get_by_role('textbox',name='Demo feedback',exact=True).input_value()=='Keep this retry' and 'retry.txt' in page.locator('.attach').inner_text() and not page.get_by_role('button',name='Send',exact=True).is_disabled())
                page.get_by_role('button',name='Send',exact=True).click();page.wait_for_function('feedback.length===2')
                check('retry sends preserved material once without approvals or publication',page.evaluate("feedback[1].files[0].text==='Retry evidence'&&!calls.some(c=>/approve|build/.test(c.path))"))
                before_reply=page.get_by_text('Review the changed cards in Align.',exact=True).count()
                page.evaluate('window.replyBeforeRefresh=true')
                page.get_by_role('textbox',name='Demo feedback',exact=True).fill('One more change')
                page.get_by_role('button',name='Send',exact=True).click();page.wait_for_function('feedback.length===3')
                page.wait_for_function("!document.querySelector('.rehearse-feedback .dock .btn.primary').disabled")
                check('SSE reply stays single when the following conversation refresh fails',page.get_by_text('Review the changed cards in Align.',exact=True).count()==before_reply+1)
                page.get_by_role('button',name='Run rehearsal',exact=True).click();page.wait_for_function("calls.some(c=>c.path.endsWith('/rehearsal'))")
                page.evaluate("states.get(saved.id).rehearsal={coverage:.5,questions:['A','B'],gaps:['Warranty'],scorecard:{total:16,weakest:['Clearer opening']}};emit('phase_done',{phase:'rehearsal'})")
                page.get_by_text('Rehearsal complete: 50%',exact=False).wait_for()
                check('on-demand rehearsal remains an explicit action with results in chat',page.locator('.rehearsal-action').count()==0 and 'Script score: 16/20.' in page.locator('.thread').inner_text())
                check('Rehearse never invokes provider readiness checks',page.evaluate("calls.filter(c=>c.path.endsWith('/readiness')).length")==read_count and page.evaluate("!calls.some(c=>c.path.includes('readiness/check'))"))
                page.get_by_role('textbox',name='Demo feedback',exact=True).fill('Late feedback');page.evaluate('window.holdFeedback=true');page.get_by_role('button',name='Send',exact=True).click();page.wait_for_function('formPending.length===1')
                page.locator('#tabs a[data-tab=studio]').click();page.wait_for_selector('#source-product-name');page.evaluate('formPending.splice(0).forEach(fn=>fn())');page.wait_for_timeout(50)
                check('navigation destroys preview/subscription and ignores late feedback completion',page.evaluate("players.at(-1).closed&&subscriptions.every(s=>s.closed)&&location.hash==='#/studio'") and page.get_by_text('Stale reply',exact=True).count()==0)
                page.locator('#source-duration').select_option('5')
                page.wait_for_function("created===2 && states.get('dm_new00002').demo.settings.pitch_minutes===5")
                check('duration preference also lazily saves exactly one draft',page.evaluate("location.hash==='#/studio/dm_new00002/sources'"))
                page.locator('#tabs a[data-tab=studio]').click();page.wait_for_selector('#source-product-name')
                page.wait_for_function("document.querySelector('#source-duration')?.value==='3'")
                page.evaluate('window.holdCreate=true')
                page.locator('#source-product-name').fill('Abandoned field');page.locator('#source-product-url').click();page.wait_for_function('creations.length===1')
                page.evaluate("location.hash='#/studio/dm_12345678/rehearse'");page.wait_for_selector('.rehearse-feedback')
                page.evaluate('window.holdCreate=false;creations.splice(0).forEach(fn=>fn())');page.wait_for_timeout(50)
                check('late lazy creation cannot replace a newer route or alter an existing demo',page.evaluate("location.hash==='#/studio/dm_12345678/rehearse'&&JSON.stringify(states.get(saved.id).demo)===JSON.stringify(saved)"))
                screenshots=Path(tempfile.mkdtemp(prefix='studio-feedback-ui-'))
                for width,height in [(1440,1000),(1366,768),(390,844)]:
                    page.set_viewport_size({'width':width,'height':height});page.wait_for_timeout(60)
                    check(f'compact navigation and embedded regions stay in {width}×{height} viewport',page.evaluate("""(()=>{const header=document.querySelector('.top').getBoundingClientRect(),host=document.querySelector('.player-host').getBoundingClientRect(),chat=document.querySelector('.rehearse-feedback').getBoundingClientRect();return Math.abs(header.height-45.6)<1&&host.height>0&&host.bottom<=innerHeight+1&&chat.bottom<=innerHeight+1&&Math.max(host.right,chat.right)<=innerWidth+1&&document.documentElement.scrollWidth<=innerWidth+1})()"""))
                    print('GEOMETRY',width,page.evaluate("JSON.stringify([...document.querySelectorAll('.rehearse-feedback,.rehearse-feedback .align-agent-header,.rehearse-feedback .dock,.rehearse-feedback textarea,.rehearse-feedback .dock .btn')].map(e=>({class:e.className,tag:e.tagName,text:e.textContent.slice(0,25),rect:e.getBoundingClientRect().toJSON()})))"),flush=True)
                    check(f'feedback header, composer, attachment and send stay visible at {width}px',page.evaluate("""(()=>{const chat=document.querySelector('.rehearse-feedback').getBoundingClientRect();return [...document.querySelectorAll('.rehearse-feedback .align-agent-header,.rehearse-feedback textarea,.rehearse-feedback .dock .box>.btn')].every(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=chat.top-1&&r.bottom<=Math.min(chat.bottom,innerHeight)+1&&r.left>=chat.left-1&&r.right<=chat.right+1})})()"""))
                    page.screenshot(path=str(screenshots/f'studio-{width}.png'))
                page.locator('#tabs a[data-tab=observability]').scroll_into_view_if_needed()
                check('compact mobile nav preserves reachable final route',page.locator('#tabs a[data-tab=observability]').bounding_box()['x']>=0)
                print('SCREENSHOTS',screenshots,flush=True)
                check('no page errors or external requests',not errors and not outbound)
                browser.close()
        finally: server.shutdown()
        print(f'Studio feedback contracts: {len(passed)}/{len(passed)}');print('OUTBOUND_ATTEMPTS',len(outbound))

if __name__=='__main__': main()
