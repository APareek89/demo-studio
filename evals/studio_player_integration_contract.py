"""Full app composition: actual header, Studio rail, feedback and player; no live services."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
import mimetypes
import os
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright
from studio_feedback_contract import HTML, ROOT
from ui_layout_contract import reference_pixels

BUNDLE = {
    'name':'Reviewed fixture','product':{'name':'Reviewed fixture'},'visual_theme':'marine','language':'en-IN',
    'voice':{'provider':'sarvam','persona':{'persona_name':'Guide'}},'intake':{'q1':'What matters most to you?'},
    'media':{'hero':'/reference-car.jpg'},'runtime':{},'facts':[{'id':'F1','claim':'Reviewed product details'}],
    'ctas':[],'fillers':{},'segments':[{'id':'proof','role':'proof','fundamental':True}],
    'slides':[
        {'id':'hero','kind':'hero_open','title':'Reviewed fixture','image_url':'/reference-car.jpg','lines':[],'callouts':[]},
        {'id':'proof','segment_id':'proof','kind':'proof','role':'proof','fundamental':True,'title':'Reviewed product details',
         'media':[{'image_id':'A','image_url':'/reference-car.jpg','from_line':0},
                  {'image_id':'B','image_url':'/reference-car.jpg','from_line':1}],
         'lines':[{'id':'line-A','text':'The first reviewed view shows the product.','fact_ids':['F1'],'audio':'/fixture.wav'},
                  {'id':'line-B','text':'This second view follows the same reviewed product.','fact_ids':['F1'],'audio':'/fixture.wav'}],
         'callouts':[{'id':'A','image_id':'A','text':'First reviewed view','anchor':{'x':.27,'y':.73},'label_pos':{'x':.15,'y':.15},'placement':'overlay','reveal_on_line':0,'fact_ids':['F1']},
                     {'id':'B','image_id':'B','text':'Second reviewed view','anchor':{'x':.63,'y':.44},'label_pos':{'x':.65,'y':.15},'placement':'overlay','reveal_on_line':1,'fact_ids':['F1']}]}
    ]}
PAGE = HTML.replace("return {name:states.get(id)?.demo.name||'Fixture',slides:[],runtime:{}}", 'return '+json.dumps(BUNDLE))
PAGE = PAGE.replace("await import('/web/app.js');", r'''
window.micRequests=0;window.audio=[];
Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia(){micRequests++;return Promise.reject(new Error('Microphone forbidden in fixture'));}}});
// Hold actual player narration at its first reviewed audio line. No device or
// network audio is used; the player itself and its DOM remain production code.
window.Audio=function(url){const a=document.createElement('audio');a.play=()=>{a.fixturePlayed=true;queueMicrotask(()=>a.onplaying?.());return Promise.resolve()};a.pause=()=>{};a.load=()=>{};audio.push(a);return a;};
await import('/web/app.js');''')

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_): pass
    def do_GET(self):
        path=urlsplit(self.path).path
        if path=='/':data,mime=PAGE.encode(),'text/html'
        elif path=='/reference-car.jpg':data,mime=reference_pixels()
        elif path.startswith('/web/'):
            file=(ROOT/path.lstrip('/')).resolve()
            if not file.is_relative_to(ROOT/'web') or not file.is_file():self.send_error(404);return
            data,mime=file.read_bytes(),mimetypes.guess_type(file.name)[0]
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',mime or 'application/octet-stream')
        self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; media-src 'none'")
        self.end_headers();self.wfile.write(data)


def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else tempfile.mkdtemp(prefix='studio-player-integrated-'));output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='studio-player-data-') as tmp:
        os.environ.update(MOCK_LLM='1',CLOUD_SYNC='0',STORAGE_BACKEND='local',DEMO_STUDIO_DATA=tmp+'/data',DEMO_STUDIO_GRAPH_DB=tmp+'/graph.sqlite')
        sys.path.insert(0,str(ROOT));from server.crawl import _render_executable
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
        base=f'http://127.0.0.1:{server.server_port}';passed=[];errors=[];outbound=[]
        def check(name,value):
            print(('PASS ' if value else 'FAIL ')+name,flush=True)
            assert value,name
            passed.append(name)
        try:
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path=_render_executable(pw.chromium),chromium_sandbox=True,headless=True,args=['--mute-audio','--disable-background-networking'])
                for width,height in [(844,390),(1366,768),(390,844)]:
                    context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce')
                    def guard(route):
                        if route.request.url.startswith(base+'/') and route.request.method=='GET':route.continue_()
                        else:outbound.append(route.request.url);route.abort()
                    context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
                    page.goto(base+'/?mute=1#/studio/dm_12345678/rehearse');page.wait_for_selector('.rehearse-workspace .pl-welcome');page.wait_for_function("document.querySelector('.pl-hero-backdrop')?.naturalWidth>0")
                    page.screenshot(path=str(output/f'welcome-{width}x{height}.png'))
                    print('GEOMETRY',width,page.evaluate("JSON.stringify([...document.querySelectorAll('body>.top,.studio,.studio>.rail,.stage-area,.rehearse-feedback,.player-host,.player-host>.pl')].map(e=>({class:e.className,rect:e.getBoundingClientRect().toJSON()})))"),flush=True)
                    check(f'{width}x{height} actual header, rail, chat and welcome fit together',page.evaluate("""(()=>{const boxes=[...document.querySelectorAll('body>.top,.studio>.rail,.rehearse-feedback,.player-host,.player-host>.pl')].map(e=>e.getBoundingClientRect());const host=document.querySelector('.player-host').getBoundingClientRect(),p=document.querySelector('.player-host>.pl').getBoundingClientRect();return boxes.length===5&&boxes.every(r=>r.width>0&&r.height>0&&r.left>=-1&&r.top>=-1&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1)&&p.left>=host.left-1&&p.top>=host.top-1&&p.right<=host.right+1&&p.bottom<=host.bottom+1&&document.documentElement.scrollWidth<=innerWidth+1})()"""))
                    def composer_fits():
                        return page.evaluate("""(()=>{const b=document.querySelector('.rehearse-feedback').getBoundingClientRect();return [...document.querySelectorAll('.rehearse-feedback .align-agent-header,.rehearse-feedback textarea,.rehearse-feedback .dock .box>.btn')].every(e=>{const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=b.top-1&&r.bottom<=Math.min(innerHeight,b.bottom)+1&&r.left>=b.left-1&&r.right<=b.right+1})})()""")
                    check(f'{width}x{height} real welcome preserves visible feedback composer and actions',composer_fits())
                    page.screenshot(path=str(output/f'welcome-{width}x{height}.png'))
                    page.get_by_role('button',name='Browse at my pace',exact=True).click()
                    # The outgoing hero remains mounted for the production 700ms
                    # crossfade. Inspect the settled, sole owned slide, not a
                    # transient frame with duplicate headings/pictures.
                    page.wait_for_function("""(()=>{const stack=document.querySelector('.slide-stack'),slides=stack?.querySelectorAll('.slide');if(slides?.length!==1)return false;const slide=slides[0];return slide.classList.contains('on')&&Number(getComputedStyle(slide).opacity)>=.999&&slide.querySelectorAll('.slide-pic').length===2&&[...slide.querySelectorAll('.slide-pic img')].every(i=>i.complete&&i.naturalWidth>0)&&!slide.getAnimations({subtree:true}).some(a=>a.playState==='running'||a.playState==='pending')})()""")
                    page.evaluate("new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))")
                    page.screenshot(path=str(output/f'tour-{width}x{height}.png'))
                    picture_geometry=page.evaluate("""(()=>{const slide=document.querySelector('.slide-stack .slide.on'),stage=slide.getBoundingClientRect();return {stage:stage.toJSON(),chrome:[...slide.querySelectorAll('.slide-heading,.slide-chapter,.slide-title,.slide-foot,.slide-panel')].map(e=>({class:e.className,box:e.getBoundingClientRect().toJSON(),display:getComputedStyle(e).display})),pictures:[...slide.querySelectorAll('.slide-pic')].map(p=>{const img=p.querySelector('img');return {box:p.getBoundingClientRect().toJSON(),image:img.getBoundingClientRect().toJSON(),nativeWidth:img.naturalWidth,nativeHeight:img.naturalHeight,fit:getComputedStyle(img).objectFit}})}})()""")
                    print('SETTLED_PICTURES',width,json.dumps(picture_geometry),flush=True)
                    check(f'{width}x{height} both settled pictures retain native fit and at least 48px visible height',page.evaluate("""(()=>{const slides=document.querySelectorAll('.slide-stack .slide');if(slides.length!==1)return false;const slide=slides[0],stage=slide.getBoundingClientRect(),pics=[...slide.querySelectorAll('.slide-pic')];return pics.length===2&&pics.every(p=>{const img=p.querySelector('img'),r=p.getBoundingClientRect(),ir=img.getBoundingClientRect();return r.height>=48&&ir.height>=48&&r.width>0&&Math.abs(r.width/r.height-img.naturalWidth/img.naturalHeight)<.02&&getComputedStyle(img).objectFit==='contain'&&Math.abs(ir.width-r.width)<2&&Math.abs(ir.height-r.height)<2&&r.left>=stage.left-1&&r.right<=stage.right+1&&r.top>=stage.top-1&&r.bottom<=stage.bottom+1})&&pics[0].getBoundingClientRect().right<=pics[1].getBoundingClientRect().left})()"""))
                    check(f'{width}x{height} actual two-picture tour and player footer remain inside their host',page.evaluate("""(()=>{const p=document.querySelector('.player-host').getBoundingClientRect();return ['.player-host>.pl','.slide.on','.pl-dock','.pl-action-bar','.pl-reply input','.pl-reply button'].every(s=>{const e=document.querySelector(s);if(!e)return false;const r=e.getBoundingClientRect();return r.width>0&&r.height>0&&r.top>=p.top-1&&r.bottom<=p.bottom+1&&r.left>=p.left-1&&r.right<=p.right+1})&&document.querySelectorAll('.slide.on .slide-pic').length===2})()"""))
                    check(f'{width}x{height} tour preserves usable feedback Send and attachment controls',composer_fits())
                    check(f'{width}x{height} no microphone, audible output or provider action',page.evaluate("micRequests===0&&audio.filter(a=>a.fixturePlayed).every(a=>a.muted)&&!calls.some(c=>/run\\/(qa|pitch|tts|stt)|readiness\\/check/.test(c.path))"))
                    context.close()
                check('no browser exceptions or external requests',not errors and not outbound)
                browser.close()
        finally:server.shutdown()
        print(f'Studio player integration contracts: {len(passed)}/{len(passed)}; OUTBOUND_ATTEMPTS {len(outbound)}');print('SCREENSHOTS',output)

if __name__=='__main__':main()
