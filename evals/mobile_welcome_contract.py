#!/usr/bin/env python3
"""Real BMW welcome/intake geometry in Chromium and WebKit; static mock APIs/audio only."""
import argparse,json,threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from gallery_continuity_browser import ContinuityHandler
from gallery_template_browser import ROOT

CHECK=r'''e=>{const r=e.getBoundingClientRect(),h=visualViewport.height+visualViewport.offsetTop,p=e.closest('.inner').getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {label:e.getAttribute('aria-label')||e.textContent,visible:r.top>=p.top-1&&r.bottom<=p.bottom+1&&r.top>=0&&r.bottom<=h+1&&r.left>=0&&r.right<=innerWidth+1,hit:hit===e||e.contains(hit),rect:{top:r.top,bottom:r.bottom,height:r.height},inner:{top:p.top,bottom:p.bottom}}}'''

def main():
 from playwright.sync_api import sync_playwright
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ROOT/'output/mobile-welcome-2026-09-26/current');p.add_argument('--revision');p.add_argument('--bmw',type=Path,default=Path('/tmp/demo-livekit-trial-20260925/review/data/dm_29df0418'));a=p.parse_args();assert (a.bmw/'bundle.json').is_file();a.output.mkdir(parents=True,exist_ok=True)
 s=ThreadingHTTPServer(('127.0.0.1',8936),ContinuityHandler);s.revision=a.revision;s.creta=None;s.bmw=a.bmw.resolve();threading.Thread(target=s.serve_forever,daemon=True).start();base='http://127.0.0.1:8936';rows=[];errors=[];blocked=[]
 def check(n,v,detail=None):
  rows.append({'name':n,'passed':bool(v),'detail':detail});print(('PASS ' if v else 'FAIL ')+n,flush=True)
 try:
  with sync_playwright() as pw:
   for name in ['chromium','webkit']:
    b=getattr(pw,name).launch(headless=True,**({'executable_path':'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome','args':['--mute-audio']} if name=='chromium' else {}))
    try:
     for label,w,h in [('portrait',390,844),('landscape',844,390),('short-landscape',844,320),('small-landscape',568,320),('desktop',1440,960),('keyboard',390,844)]:
      c=b.new_context(viewport={'width':w,'height':h},is_mobile=True,has_touch=True,reduced_motion='reduce');c.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base+'/') and r.request.method=='GET' else (blocked.append(r.request.url),r.abort())[-1]);c.route_web_socket('**/*',lambda ws:ws.close());q=c.new_page();q.on('pageerror',lambda e:errors.append(str(e)));q.goto(base);q.wait_for_function('()=>window.galleryQA?.ready');q.evaluate("async()=>galleryQA.setup(await(await fetch('/fixtures/bmw.json')).json())");q.wait_for_function("()=>document.querySelector('.pl-hero-backdrop').complete&&document.querySelector('.pl-hero-backdrop').naturalWidth>0");prefix=name+' '+label
      controls=q.locator('.pl-welcome .actions button,.pl-welcome input[role=switch]');initial=[controls.nth(i).evaluate(CHECK) for i in range(controls.count())];check(prefix+' shows both start buttons and voice toggle',len(initial)==3 and all(r['visible'] and r['hit'] for r in initial),initial)
      check(prefix+' retains the published BMW title and backdrop',q.locator('.pl-welcome h1').inner_text()==q.evaluate('galleryQA.bundle().product.name') and q.locator('.pl-hero-backdrop').evaluate('e=>e.complete&&e.naturalWidth>0'))
      voice=q.get_by_role('switch',name='Voice mode',exact=True);voice.check();on=voice.is_checked();voice.uncheck();check(prefix+' voice toggle is operable without capture',on and not voice.is_checked() and q.evaluate('window.microphoneAttempts===0'))
      q.screenshot(path=str(a.output/(name+'-'+label+'-welcome.png')))
      q.get_by_role('button',name='Explore with me',exact=True).tap();q.wait_for_function("()=>document.querySelector('.pl-intake:not(.pl-welcome)').classList.contains('open')")
      if label=='keyboard':
       q.get_by_role('textbox',name='Your answer',exact=True).tap();q.evaluate("Object.defineProperty(visualViewport,'height',{configurable:true,get:()=>320});visualViewport.dispatchEvent(new Event('resize'))")
      q.evaluate('async()=>{for(let i=0;i<5;i++)await new Promise(r=>requestAnimationFrame(r))}')
      intake=q.locator('.pl-intake.open .fallback input,.pl-intake.open .fallback button,.pl-intake.open .actions button');reachable=[]
      for i in range(intake.count()):
       el=intake.nth(i);el.scroll_into_view_if_needed();reachable.append(el.evaluate(CHECK))
      check(prefix+' intake fields send microphone and skip remain reachable',len(reachable)==5 and all(r['visible'] and r['hit'] for r in reachable),reachable)
      q.screenshot(path=str(a.output/(name+'-'+label+'-intake.png')))
      if label=='keyboard':q.evaluate("delete visualViewport.height;document.activeElement?.blur();visualViewport.dispatchEvent(new Event('resize'))")
      q.get_by_role('button',name='Skip, start the demo',exact=True).tap();q.wait_for_function("()=>!document.querySelector('.pl-intake:not(.pl-welcome)').classList.contains('open')&&galleryQA.state().active.length===1")
      check(prefix+' skip starts one approved narration without page overflow',q.evaluate('()=>galleryQA.state().maxActive===1&&window.microphoneAttempts===0&&document.documentElement.scrollWidth<=innerWidth&&galleryQA.state().unchanged'))
      q.evaluate('galleryQA.destroy()');c.close()
     # An unusually long product name may scroll internally; its controls remain usable.
     c=b.new_context(viewport={'width':844,'height':320},is_mobile=True,has_touch=True,reduced_motion='reduce');c.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base+'/') and r.request.method=='GET' else (blocked.append(r.request.url),r.abort())[-1]);c.route_web_socket('**/*',lambda ws:ws.close());q=c.new_page();q.on('pageerror',lambda e:errors.append(str(e)));q.goto(base);q.wait_for_function('()=>window.galleryQA?.ready');q.evaluate("async()=>{const b=await(await fetch('/fixtures/bmw.json')).json();b.product.name+=' — '+('Extended customer product description '.repeat(12));return galleryQA.setup(b)}")
     check(name+' long welcome keeps internal scrolling',q.locator('.pl-welcome .inner').evaluate('e=>e.scrollHeight>e.clientHeight&&getComputedStyle(e).overflowY==="auto"'))
     browse=q.get_by_role('button',name='Browse at my pace',exact=True);browse.scroll_into_view_if_needed();v=browse.evaluate(CHECK);browse.tap();q.wait_for_function('()=>galleryQA.state().active.length===1');check(name+' long welcome still starts from the reachable browse button',v['visible'] and v['hit'] and q.evaluate('window.microphoneAttempts===0'));q.evaluate('galleryQA.destroy()');c.close()
    finally:b.close()
  check('no script errors',not errors,errors);check('no external requests or providers',not blocked,blocked)
 finally:
  s.shutdown();s.server_close();result={'passed':sum(r['passed'] for r in rows),'total':len(rows),'checks':rows,'errors':errors,'blocked':blocked,'provider_calls':0,'physical_microphone':False,'physical_keyboard':False,'revision':a.revision};(a.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
 print('Mobile welcome:',result['passed'],'/',result['total']);return 0 if result['passed']==result['total'] else 1
if __name__=='__main__':raise SystemExit(main())
