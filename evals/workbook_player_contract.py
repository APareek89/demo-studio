"""Workbook player presentation: real DOM, isolated fixtures and no provider access."""
from pathlib import Path
import json
import mimetypes
import os
import sys
import tempfile
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright
from ui_layout_contract import HTML, ROOT, reference_pixels

_TMP = tempfile.TemporaryDirectory(prefix='workbook-player-')
os.environ.update(MOCK_LLM='1', CLOUD_SYNC='0', STORAGE_BACKEND='local',
                  DEMO_STUDIO_DATA=_TMP.name+'/demos', DEMO_STUDIO_GRAPH_DB=_TMP.name+'/graph.sqlite')
sys.path.insert(0,str(ROOT))
from server.crawl import _render_executable

EXTRA=r'''
let workbookDispose=null;
window.workbookStopEmbedded=()=>{workbookDispose?.();workbookDispose=null;};
window.workbookWelcome=async(theme='marine',missing=false)=>{
 workbookDispose?.();workbookDispose=null;
 player?.destroy();player=null;host.replaceChildren();host.style.cssText='';
 const b={...structuredClone(bundle),visual_theme:theme,media:{hero:missing?'/missing-image.jpg':'/reference-car.jpg',images:[{id:'uploaded',url:'/reference-car.jpg'}]}};
 b.slides[0].image_url=missing?null:'/reference-car.jpg';
 b.intake.q1='Hello and welcome. What matters most to you as you consider this product? Tell me what you would like to explore, or skip to start the demo.';
 player=mountPlayer(host,b,{});await settle();await settle();
};
window.workbookPreview=async()=>{
 player?.destroy();player=null;host.replaceChildren();
 const stage=document.createElement('div');stage.className='pl slide-review-stage';stage.dataset.visualTheme='sage';
 stage.innerHTML='<div class="pl-stage"></div>';host.append(stage);
 view=renderSlide({id:'preview',title:'Reviewed product view',image_url:'/reference-car.jpg',lines:[],callouts:[]},{fit:true,theme:'sage'});
 view.el.classList.add('on');stage.firstChild.append(view.el);await settle();await settle();view.layout();
};
window.workbookEmbedded=async()=>{
 workbookDispose?.();player?.destroy();player=null;host.replaceChildren();host.style.cssText='';
 const b={...structuredClone(bundle),media:{hero:'/reference-car.jpg'}};
 api.get=async path=>path.endsWith('/bundle')?b:structuredClone(state);
 workbookDispose=renderRehearse({demoId:'fixture',area:host,state:structuredClone(state),subscribe(){},setRailStatus(){}});
 await settle();await settle();
};
window.workbookEmbeddedTour=async()=>{
 document.querySelectorAll('.pl-intake').forEach(n=>n.remove());
 const data=structuredClone(approvedData);data.image_url='/reference-car.jpg';
 data.media?.forEach(m=>m.image_url='/reference-car.jpg');
 view=renderSlide(data,{fit:true,theme:'marine'});view.el.classList.add('on');
 document.querySelector('.slide-stack').replaceChildren(view.el);
 await Promise.all([...view.el.querySelectorAll('img')].map(i=>i.complete?Promise.resolve():new Promise(r=>i.addEventListener('load',r,{once:true}))));
 view.setRevealed(99);await settle();view.layout();await settle();
};
window.controlContrast=()=>{
 const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');canvas.width=canvas.height=1;
 const rgb=color=>{ctx.clearRect(0,0,1,1);ctx.fillStyle=color;ctx.fillRect(0,0,1,1);return [...ctx.getImageData(0,0,1,1).data].slice(0,3)};
 const lum=values=>values.map(c=>{c/=255;return c<=.04045?c/12.92:((c+.055)/1.055)**2.4}).reduce((v,c,i)=>v+c*[.2126,.7152,.0722][i],0);
 return ['.pl-reply .btn.primary','.pl-reply .mic.on','.pl-ctas .chip.primary'].map(selector=>{const c=getComputedStyle(document.querySelector(selector)),text=lum(rgb(c.color)),bg=lum(rgb(c.backgroundColor));return {selector,ratio:(Math.max(text,bg)+.05)/(Math.min(text,bg)+.05),color:c.color,background:c.backgroundColor}});
};
'''
PAGE=HTML.replace('window.ready=true;',EXTRA+'\nwindow.ready=true;')
BASE='http://127.0.0.1:8905'

def main():
    output=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/demo-workbook-player-qa')
    output.mkdir(parents=True,exist_ok=True)
    results=[];errors=[];rejected=[]
    def check(label,good):
        results.append({'check':label,'pass':bool(good)})
        print(('PASS ' if good else 'FAIL ')+label,flush=True)
        if not good: raise AssertionError(label)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=_render_executable(pw.chromium),chromium_sandbox=True,headless=True,args=['--mute-audio','--disable-background-networking'])
        context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce')
        def serve(route):
            url=route.request.url;path=urlsplit(url).path
            if not url.startswith(BASE+'/') or route.request.method!='GET':
                rejected.append(url);route.abort();return
            if path=='/':route.fulfill(body=PAGE,content_type='text/html');return
            if path=='/missing-image.jpg':route.fulfill(status=404,body='');return
            if path=='/reference-car.jpg':
                body,mime=reference_pixels();route.fulfill(body=body,content_type=mime);return
            file=(ROOT/path.lstrip('/')).resolve()
            if file.is_relative_to(ROOT/'web') and file.is_file():route.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(file.name)[0] or 'text/plain');return
            rejected.append(url);route.abort()
        context.route('**/*',serve)
        page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(BASE+'/?mute=1');page.wait_for_function('window.ready')
        for width,height in [(1440,900),(1366,768),(850,650),(390,844),(844,390),(390,400)]:
            page.set_viewport_size({'width':width,'height':height});page.evaluate('workbookWelcome()')
            page.wait_for_function("document.querySelector('.pl-hero-backdrop').naturalWidth>0")
            check(f'{width}x{height} welcome stays inside viewport',page.evaluate("(()=>{const r=document.querySelector('.pl').getBoundingClientRect();return r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1&&document.documentElement.scrollWidth<=innerWidth})()"))
            check(f'{width}x{height} hero fills below-header area without distortion',page.evaluate("(()=>{const s=document.querySelector('.pl-stage').getBoundingClientRect(),i=document.querySelector('.pl-hero-backdrop'),r=i.getBoundingClientRect(),c=getComputedStyle(i);return Math.abs(r.width-s.width)<1&&Math.abs(r.height-s.height)<1&&c.objectFit==='cover'&&c.objectPosition==='50% 50%'})()"))
            check(f'{width}x{height} welcome has no lower dock and accessible start actions',page.evaluate("getComputedStyle(document.querySelector('.pl-dock')).display==='none'&&getComputedStyle(document.querySelector('.pl-action-bar')).display==='none'&&[...document.querySelectorAll('.pl-welcome button')].every(n=>n.closest('.inner').scrollHeight>=n.offsetHeight)"))
            page.screenshot(path=str(output/f'welcome-{width}x{height}.png'))
            page.get_by_role('button',name='Explore with me',exact=True).click()
            check(f'{width}x{height} intake owns the same full hero area and no lower panel',page.evaluate("!!document.querySelector('.pl-intake:not(.pl-welcome).open')&&getComputedStyle(document.querySelector('.pl-dock')).display==='none'&&getComputedStyle(document.querySelector('.pl-action-bar')).display==='none'&&getComputedStyle(document.querySelector('.pl-intake .inner')).backgroundColor==='rgba(0, 0, 0, 0)'"))
            for label in ['Your answer','Websites I can check (optional)','Skip, start the demo']:
                locator=page.get_by_role('button',name=label,exact=True) if label.startswith('Skip') else page.get_by_label(label,exact=True)
                locator.scroll_into_view_if_needed();box=locator.bounding_box()
                check(f'{width}x{height} intake control remains reachable: {label}',bool(box) and box['x']>=0 and box['x']+box['width']<=width+1 and box['y']>=0 and box['y']+box['height']<=height+1)
            page.screenshot(path=str(output/f'intake-{width}x{height}.png'))
            page.get_by_role('button',name='Skip, start the demo',exact=True).click()
            page.wait_for_function("!document.querySelector('.pl-intake.open')")
            check(f'{width}x{height} closing intake preserves a reserved action footer',page.evaluate("(()=>{const r=s=>document.querySelector(s).getBoundingClientRect(),p=r('.pl'),d=r('.pl-dock'),a=r('.pl-action-bar');return a.height>0&&d.bottom<=a.top+1&&a.bottom<=p.bottom+1})()"))
            page.evaluate("approvedLayout('marine',true)")
            check(f'{width}x{height} slide is white, borderless with half-size heading',page.evaluate("(()=>{const c=s=>getComputedStyle(document.querySelector(s));return c('.pl').backgroundColor==='rgb(255, 255, 255)'&&c('.pl-top').borderBottomWidth==='0px'&&c('.sample-layout').backgroundColor==='rgb(255, 255, 255)'&&parseFloat(c('.slide-title').fontSize)<=17&&c('.pl-dock').borderTopWidth==='0px'})()"))
            check(f'{width}x{height} actual tour header remains fully in the viewport',page.evaluate("(()=>{const h=document.querySelector('.pl-top').getBoundingClientRect();return h.top>=0&&h.bottom<=innerHeight&&h.height>=49})()"))
            check(f'{width}x{height} two supplied pictures remain left and right with native proportions',page.evaluate("(()=>{const ps=[...document.querySelectorAll('.slide-pic')],r=ps.map(n=>n.getBoundingClientRect());return r.length===2&&r[0].right<=r[1].left&&Math.abs(r[0].top-r[1].top)<1&&ps.every((n,i)=>Math.abs(r[i].width/r[i].height-n.querySelector('img').naturalWidth/n.querySelector('img').naturalHeight)<.03)})()"))
            check(f'{width}x{height} labels stay bounded, clear and attached to reviewed image coordinates',page.evaluate("(()=>{const g=labelGeometry();return g.bounded&&g.clear&&g.represented&&g.ownership&&JSON.stringify(approvedData)===approvedSaved})()"))
            portrait=width<=720 and height>width
            check(f'{width}x{height} portrait guidance is truthful and nonblocking',page.evaluate("getComputedStyle(document.querySelector('.pl-orientation-hint')).display!=='none'")==portrait)
            page.screenshot(path=str(output/f'slide-{width}x{height}.png'))
            page.evaluate('stress()')
            check(f'{width}x{height} transient conversation and CTA retain slide geometry',page.evaluate("(()=>{const r=s=>document.querySelector(s).getBoundingClientRect(),p=r('.pl'),s=r('.slide-stack'),d=r('.pl-dock'),c=r('.pl-action-bar');return s.bottom<=d.top+1&&d.bottom<=c.top+1&&c.bottom<=p.bottom+1&&['.pl-controls .mic','.pl-reply input'].every(q=>{const x=r(q);return x.top>=d.top-1&&x.bottom<=d.bottom+1&&x.left>=0&&x.right<=innerWidth+1})})()"))
            page.screenshot(path=str(output/f'conversation-{width}x{height}.png'))
        page.set_viewport_size({'width':1440,'height':900})
        page.evaluate("workbookWelcome('sage',true)");page.wait_for_function("document.querySelector('.pl-hero-backdrop').naturalWidth>0")
        check('failed or absent hero falls back to an uploaded image',page.locator('.pl-hero-backdrop').get_attribute('src')=='/reference-car.jpg')
        check('selected palette controls text and dark button background',page.evaluate("(()=>{const p=document.querySelector('.pl'),c=getComputedStyle(p),ink=c.getPropertyValue('--theme-deep').trim(),title=getComputedStyle(document.querySelector('.pl-welcome h1')).color,btn=getComputedStyle(document.querySelector('.pl-welcome .btn.primary'));return title==='rgb(25, 59, 51)'&&btn.backgroundColor===title&&btn.color==='rgb(255, 255, 255)'})()"))
        page.evaluate('workbookPreview()')
        check('shared Align/Rehearse slide preview uses the same white template',page.evaluate("getComputedStyle(document.querySelector('.sample-layout')).backgroundColor==='rgb(255, 255, 255)'&&getComputedStyle(document.querySelector('.slide-title')).color==='rgb(25, 59, 51)'"))
        for width,height in [(1366,768),(844,390),(390,844)]:
            page.set_viewport_size({'width':width,'height':height});page.evaluate('workbookEmbedded()')
            page.wait_for_selector('.rehearse-workspace .pl')
            check(f'{width}x{height} actual Rehearse player and feedback stay inside the viewport',page.evaluate("[...document.querySelectorAll('.rehearse-workspace>.player-host,.rehearse-feedback,.rehearse-workspace .pl')].every(n=>{const r=n.getBoundingClientRect();return r.width>0&&r.height>0&&r.left>=0&&r.right<=innerWidth+1&&r.top>=0&&r.bottom<=innerHeight+1})"))
            check(f'{width}x{height} embedded welcome uses the same full-area hero and white header',page.evaluate("getComputedStyle(document.querySelector('.pl-top')).backgroundColor==='rgb(255, 255, 255)'&&getComputedStyle(document.querySelector('.pl-dock')).display==='none'&&document.querySelector('.pl-hero-backdrop').getAttribute('src')==='/reference-car.jpg'"))
            page.screenshot(path=str(output/f'rehearse-{width}x{height}.png'))
            page.evaluate('workbookEmbeddedTour()')
            check(f'{width}x{height} embedded actual slide and composer share the bounded player',page.evaluate("(()=>{const r=s=>document.querySelector(s).getBoundingClientRect(),p=r('.pl'),s=r('.slide-stack'),d=r('.pl-dock'),a=r('.pl-action-bar');return s.width===p.width&&s.height>0&&s.bottom<=d.top+1&&d.bottom<=a.top+1&&a.bottom<=p.bottom+1&&r('.pl-reply').bottom<=d.bottom+1})()"))
            page.screenshot(path=str(output/f'rehearse-tour-{width}x{height}.png'))
        contrast={}
        for theme in ['marine','sage','graphite']:
            page.evaluate('workbookStopEmbedded()')
            page.set_viewport_size({'width':1366,'height':768});page.evaluate(f"approvedLayout('{theme}')")
            page.evaluate("document.querySelector('.pl-controls .mic').classList.add('on');document.querySelector('.pl-ctas').innerHTML='<button class=\"chip primary\">Contact</button>'")
            contrast[theme]=page.evaluate('controlContrast()')
            check(f'{theme} active microphone, Send and dark CTA text contrast reaches4.5',all(row['ratio']>=4.5 for row in contrast[theme]))
        (output/'control-contrast.json').write_text(json.dumps(contrast,indent=2))
        check('no browser exceptions',not errors)
        check('no external requests or mutations',not rejected)
        browser.close()
    (output/'results.json').write_text(json.dumps({'passed':len(results),'total':len(results),'external_requests':rejected,'page_errors':errors,'checks':results},indent=2))
    print(f'Workbook player: {len(results)}/{len(results)}; external requests0; page errors0')

if __name__=='__main__':main()
