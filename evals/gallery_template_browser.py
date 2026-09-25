#!/usr/bin/env python3
"""Free, muted actual-player acceptance for the central gallery template.

The loopback-only server serves static files and an optional already-published
CRETA fixture read-only. Audio/API are deterministic local fakes. All other
network and WebSocket requests are blocked. No app server or provider is used.
"""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import subprocess
import threading
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CRETA = Path('/tmp/demo-runtime-final-20260924/data/dm_7bbf10d0')

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        target = None
        if path in ('/', '/gallery_template_contract.html'):
            target = ROOT / 'evals/gallery_template_contract.html'
        elif path == '/player_contract.html':
            target = ROOT / 'evals/player_contract.html'
        elif path.startswith('/web/'):
            target = (ROOT / path[1:]).resolve()
            if not target.is_relative_to(ROOT / 'web'):
                target = None
        elif path == '/fixtures/creta.json' and self.server.creta:
            target = self.server.creta / 'bundle.json'
        elif path.startswith('/media/dm_7bbf10d0/') and self.server.creta:
            target = (self.server.creta / path.removeprefix('/media/dm_7bbf10d0/')).resolve()
            if not target.is_relative_to(self.server.creta):
                target = None
        if target is None or not target.is_file():
            self.send_error(404)
            return
        if (path.startswith('/web/') or path == '/player_contract.html') and self.server.revision:
            data = subprocess.check_output(['git', 'show', self.server.revision + ':' + ('evals/player_contract.html' if path == '/player_contract.html' else path[1:])], cwd=ROOT)
        else:
            data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; media-src 'none'; font-src 'self'")
        self.end_headers()
        self.wfile.write(data)

def serve(revision=None, creta=None):
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.revision, server.creta = revision, creta.resolve() if creta else None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, 'http://127.0.0.1:' + str(server.server_port)

def main():
    from playwright.sync_api import sync_playwright
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'output/playwright/gallery-production-2026-09-25')
    parser.add_argument('--baseline-revision',default='eacbb57')
    parser.add_argument('--creta',type=Path,default=DEFAULT_CRETA)
    parser.add_argument('--baseline-only',action='store_true')
    parser.add_argument('--prepare-click-only','--targeted-only',action='store_true',help='Focused browser regressions for preparation clicks and a long caption rail.')
    parser.add_argument('--reuse-baseline',action='store_true',help='Reuse this output directory baseline receipt during an implementation iteration.')
    parser.add_argument('--skip-legacy',action='store_true',help='Run the new gallery contract only; retain independent legacy receipts.')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    rows=[];errors=[];blocked=[];asset_errors=[]
    def check(name,value,detail=None):
        row={'name':name,'passed':bool(value)}
        if detail is not None:row['detail']=detail
        rows.append(row)
        print(('PASS ' if value else 'FAIL ')+name,flush=True)
    servers=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--mute-audio'])
        def page_for(base,width=1440,height=960):
            context=browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce')
            def route(r):
                if r.request.url.startswith(base+'/') and r.request.method=='GET':return r.continue_()
                blocked.append(r.request.url);return r.abort()
            context.route('**/*',route);context.route_web_socket('**/*',lambda w:w.close())
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.on('response',lambda r:asset_errors.append({'status':r.status,'url':r.url}) if '/media/' in r.url and r.status>=400 else None)
            return page
        def setup(page,base):
            page.goto(base+'/');page.wait_for_function('() => window.galleryQA?.ready')
        def click(page,text):page.evaluate('(s)=>galleryQA.click(s)',text)
        def state(page):return page.evaluate('galleryQA.state()')
        def active(page,src=None):
            page.wait_for_function('(src)=>galleryQA.state().active.some(a=>!src||a.src===src)',arg=src,timeout=15000)
        def current_surface(page):return page.locator('.slide.on .gallery-surface')
        def bounded(page):return page.evaluate("""()=>{const s=document.querySelector('.slide.on'),g=s?.querySelector('.gallery-surface');if(!g)return true;const r=g.getBoundingClientRect(),p=s.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1&&r.top>=p.top-1&&r.bottom<=p.bottom+1&&[...g.querySelectorAll('.gallery-tag')].every(e=>{const b=e.getBoundingClientRect();return b.left>=r.left-1&&b.right<=r.right+1;});}""")
        def prepare_click_attempt(page,label):
            controls=page.locator('.slide.on .gallery-tag,.slide.on .gallery-secondary')
            check(label+' locks every picture/tag control during preparation',controls.count()>=3 and controls.evaluate_all('(nodes)=>nodes.every(e=>e.disabled)'))
            before=state(page)
            controls.evaluate_all("(nodes)=>nodes.forEach(e=>{e.click();e.dispatchEvent(new MouseEvent('click',{bubbles:true}));})")
            check(label+' ignores native and dispatched preparation clicks',not state(page)['active'] and len(state(page)['played'])==len(before['played']))
            active(page)
            after=state(page)
            check(label+' releases the original line once after attempted clicks',len(after['active'])==1 and len(after['played'])==len(before['played'])+1 and after['maxActive']==1 and current_surface(page).get_attribute('data-state')=='ready')
            check(label+' unlocks picture/tag controls when ready',controls.evaluate_all('(nodes)=>nodes.every(e=>!e.disabled)'))
        if args.prepare_click_only:
            server,base=serve();page=page_for(base);setup(page,base);page.emulate_media(reduced_motion='no-preference')
            page.evaluate("()=>{const b=galleryQA.synthetic();b.slides[1].media[1].from_line=0;b.slides[1].callouts[1].reveal_on_line=0;return galleryQA.setup(b);}")
            click(page,'Browse at my pace');page.wait_for_function("()=>['walking','straightening','entering','focusing'].includes(document.querySelector('.slide.on .gallery-surface')?.dataset.state)")
            prepare_click_attempt(page,'Two-photo source')
            check('Preparation click attempts retain exact approved audio and caption',state(page)['active'][0]['text']=='Approved first image detail.' and state(page)['caption']=='Approved first image detail.')
            check('Preparation click check uses no external requests or script errors',not blocked and not errors)
            page.emulate_media(reduced_motion='reduce')
            page.evaluate("""()=>{const b=galleryQA.synthetic(),s=b.slides[1];s.media=s.media.slice(0,1);s.lines=s.lines.slice(0,1);s.callouts=Array.from({length:8},(_,i)=>({id:'long-'+i,image_id:'front',text:'Reviewed feature '+(i+1)+' with its complete original source condition retained in this descriptive caption.',fact_ids:['F1'],placement:'overlay',anchor:{x:.5,y:.2},label_pos:{x:.1,y:.1},reveal_on_line:i===7?0:-1}));return galleryQA.setup(b);}""")
            click(page,'Browse at my pace');active(page)
            long=page.evaluate("""()=>{const c=document.querySelector('.slide.on .gallery-captions'),t=c.querySelector('[data-id=long-7]'),a=c.getBoundingClientRect(),b=t.getBoundingClientRect(),p=document.querySelector('.slide.on .gallery-pointer');return {overflow:c.scrollHeight>c.clientHeight,top:c.scrollTop,visible:b.top>=a.top-1&&b.bottom<=a.bottom+1,opacity:getComputedStyle(p).opacity,path:p.querySelector('path').getAttribute('d')};}""")
            check('Long caption rail scrolls the current reviewed tag fully into view',long['overflow'] and long['top']>0 and long['visible'],long)
            check('Current long-caption anchor has a visible source pointer',long['opacity']=='1' and bool(long['path']))
            before=state(page)
            page.locator('.slide.on .gallery-captions').evaluate("e=>{e.scrollTop=Math.max(0,e.scrollTop-16);e.dispatchEvent(new Event('scroll'));}")
            moved=page.locator('.slide.on .gallery-pointer path').get_attribute('d')
            check('Local caption scroll redraws the pointer endpoint',moved!=long['path'])
            page.locator('.slide.on .gallery-captions').evaluate("e=>{e.scrollTop=0;e.dispatchEvent(new Event('scroll'));}")
            check('Scrolling the selected tag out of view hides its pointer',page.locator('.slide.on .gallery-pointer').evaluate("e=>getComputedStyle(e).opacity==='0'"))
            check('Caption scrolling preserves top navigation and dock geometry',state(page)['geometry']==before['geometry'])
            check('Caption scrolling preserves the active audio and route',state(page)['active']==before['active'] and state(page)['context']==before['context'] and len(state(page)['played'])==len(before['played']))
            browser.close();server.shutdown()
            (args.output/'prepare-click-browser.json').write_text(json.dumps({'passed':sum(r['passed'] for r in rows),'total':len(rows),'checks':rows,'errors':errors,'blocked':blocked,'provider_calls':0,'scope':'Actual mounted player and browser DOM, simulated audio, muted, blocked network'},indent=2)+'\n')
            return 0 if all(r['passed'] for r in rows) else 1
        baseline_server,baseline_url=serve(args.baseline_revision,args.creta if args.creta.exists() else None);servers.append(baseline_server)
        if args.reuse_baseline:
            baseline=json.loads((args.output/'shell-baseline.json').read_text())['geometry']
        else:
            baseline={}
            for width,height in [(1440,960),(390,844)]:
                page=page_for(baseline_url,width,height);setup(page,baseline_url);click(page,'Browse at my pace');active(page)
                page.wait_for_timeout(800);baseline[str(width)]=state(page)['geometry'];page.screenshot(path=str(args.output/f'baseline-{width}.png'),animations='disabled');page.context.close()
            (args.output/'shell-baseline.json').write_text(json.dumps({'revision':args.baseline_revision,'geometry':baseline},indent=2)+'\n')
            legacy=page_for(baseline_url);legacy.goto(baseline_url+'/player_contract.html');legacy.get_by_role('button',name='Run checks',exact=True).click();legacy.wait_for_function('() => !!window.playerContractReport',timeout=60000)
            old=legacy.evaluate('window.playerContractReport');(args.output/'player-browser-baseline.json').write_text(json.dumps(old,indent=2)+'\n');print('Legacy baseline',old['passed'],old['total'],flush=True);legacy.context.close()
        if not args.baseline_only:
            server,base=serve(creta=args.creta if args.creta.exists() else None);servers.append(server)
            for width,height in [(1440,960),(390,844)]:
                page=page_for(base,width,height);setup(page,base)
                check(f'{width}px hero remains native',page.locator('.slide.on.gallery-slide').count()==0 and page.locator('.slide.on .slide-pic img').count()==1)
                click(page,'Browse at my pace');active(page);page.wait_for_timeout(800)
                check(f'{width}px gallery default mounted',current_surface(page).count()==1)
                check(f'{width}px shell geometry and type unchanged from baseline',state(page)['geometry']==baseline[str(width)],{'before':baseline[str(width)],'after':state(page)['geometry']})
                page.screenshot(path=str(args.output/f'gallery-{width}-line0.png'),animations='disabled')
                for i in range(3):
                    if i:page.evaluate('galleryQA.finish()');active(page)
                    s=state(page);line=page.evaluate('(i)=>galleryQA.bundle().slides[1].lines[i]',i)
                    check(f'{width}px line {i} retains exact audio, caption and checkpoint',s['active'][0]['src']==line['audio'] and s['caption']==line['text'] and s['context']['line_index']==i)
                    check(f'{width}px line {i} audio begins after gallery ready',s['played'][-1]['phase']=='ready',s['played'][-1])
                    surface=current_surface(page);expected='front' if i==0 else 'cabin'
                    check(f'{width}px line {i} uses mapped image',surface.get_attribute('data-image-id')==expected)
                    shown=page.locator('.slide.on .gallery-tag:visible').all_text_contents()
                    expectedtag=['Front feature','Cabin feature','Supported source caption'][i]
                    check(f'{width}px line {i} shows exact reviewed tag',any(expectedtag in x for x in shown),shown)
                    if i==2:check(f'{width}px source caption gets no invented pointer',page.locator('.slide.on .gallery-pointer').evaluate_all('(nodes)=>nodes.every(e=>getComputedStyle(e).opacity==="0"||getComputedStyle(e).display==="none")'))
                    check(f'{width}px line {i} viewport remains bounded',bounded(page))
                check(f'{width}px approved bundle remains byte-equivalent',state(page)['unchanged'])
                page.evaluate('galleryQA.finish()');active(page)
                check(f'{width}px explicit media-empty stays native text-only',state(page)['context']['slide']=='text' and page.locator('.slide.on.slide-text-only').count()==1 and page.locator('.slide.on .gallery-surface').count()==0 and page.locator('.slide.on img').count()==0)
                click(page,'Unanchored illustration');active(page);check(f'{width}px illustration caption has no pointer',page.locator('.slide.on .gallery-pointer').evaluate_all('(nodes)=>nodes.every(e=>getComputedStyle(e).opacity==="0"||getComputedStyle(e).display==="none")') and 'Cited illustrated fact' in page.locator('.slide.on').inner_text())
                page.context.close()
            page=page_for(base);setup(page,base);page.emulate_media(reduced_motion='no-preference');click(page,'Browse at my pace')
            page.wait_for_function("() => ['walking','straightening','entering','focusing'].includes(document.querySelector('.slide.on .gallery-surface')?.dataset.state)")
            check('Narration waits during visual entrance',not state(page)['active'])
            click(page,'Pause / resume');paused=page.locator('.slide.on .gallery-camera').evaluate('(e)=>getComputedStyle(e).transform');page.wait_for_timeout(800)
            check('Pause during move freezes camera and cancels stale audio',paused==page.locator('.slide.on .gallery-camera').evaluate('(e)=>getComputedStyle(e).transform') and not state(page)['active'])
            click(page,'Pause / resume');active(page);check('Resume starts the exact interrupted line once',state(page)['context']['line_index']==0 and state(page)['maxActive']==1)
            page.evaluate("galleryQA.question('What is supported?')");page.wait_for_function('() => galleryQA.state().qa.length===1');page.wait_for_function("() => [...document.querySelectorAll('.pl-chips button')].some(b=>b.textContent==='Continue demo')")
            check('Question retains original line checkpoint',state(page)['qa'][0].get('cursor',{}).get('line')==0,state(page)['qa'][0])
            click(page,'Continue demo');active(page);check('Return restores exact approved line and one voice',state(page)['context']['slide']=='pair' and state(page)['context']['line_index']==0 and state(page)['maxActive']==1)
            # Two rapid navigation intents: old preparation may never restart over newest state.
            click(page,'Unanchored illustration');click(page,'Reviewed terms');active(page);page.wait_for_timeout(1800)
            check('Rapid jump leaves only newest slide and audio',state(page)['context']['slide']=='text' and len(state(page)['active'])==1 and state(page)['active'][0]['text']=='Approved terms remain exactly as written.')
            click(page,'Two reviewed pictures');page.wait_for_function("() => document.querySelector('.slide.on .gallery-surface')?.dataset.state!=='ready'")
            click(page,'Stop and see the summary');page.wait_for_timeout(1800)
            check('Stop during move prevents delayed narration',not state(page)['active'] and page.locator('.pl-handoff.open').count()==1)
            click(page,'Restart');click(page,'Skip, start the demo');active(page)
            check('Restart creates clean first line ownership',state(page)['context']['slide']=='pair' and state(page)['context']['line_index']==0 and state(page)['maxActive']==1)
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(500)
            check('Resize during narration preserves active line and viewport',state(page)['context']['line_index']==0 and len(state(page)['active'])==1 and bounded(page))
            click(page,'Unanchored illustration');page.set_viewport_size({'width':1440,'height':960});active(page)
            check('Resize during move releases preparation without hanging',state(page)['context']['slide']=='untrusted' and len(state(page)['active'])==1)
            page.emulate_media(reduced_motion='reduce');click(page,'Two reviewed pictures');active(page)
            check('Reduced motion settles without a running camera animation',not any(a['state']=='running' and a['target'] in ['gallery-camera','gallery-world','gallery-focus','gallery-frame'] for a in state(page)['animations']),state(page)['animations'])
            page.context.close()
            if args.creta.exists():
                for width,height in [(1440,960),(390,844)]:
                    page=page_for(base,width,height);setup(page,base);page.evaluate('galleryQA.loadCreta()');click(page,'Browse at my pace');active(page)
                    # Browse preserves the real opening before it builds progress.
                    # Exercise those held approved clips, then inspect the route.
                    opening_count=0
                    while not state(page)['context']['route'] and opening_count<12:
                        st=state(page);item=st['active'][0]
                        check(f'CRETA {width}px opening clip {opening_count} exact caption',st['caption']==item['text'] and item['src'].startswith('/media/dm_7bbf10d0/audio/'))
                        check(f'CRETA {width}px opening clip {opening_count} stays central',bounded(page))
                        check(f'CRETA {width}px opening clip {opening_count} actual photo loaded',page.locator('.slide.on .gallery-image').evaluate_all('(images)=>images.length>0&&images.every(i=>i.complete&&i.naturalWidth>0)'))
                        page.evaluate('galleryQA.finish()');active(page);opening_count+=1
                    route=page.evaluate("galleryQA.bundle().slides.filter(s=>galleryQA.state().context.route.includes(s.id)&&s.lines?.length).map(s=>({id:s.id,title:s.title,lines:s.lines,media:s.media,callouts:s.callouts}))")
                    check(f'CRETA {width}px representative published route is nonempty',len(route)>=12)
                    for slide in route:
                        if state(page)['context']['slide']!=slide['id']:click(page,slide['title']);active(page)
                        for i,line in enumerate(slide['lines']):
                            if i:page.evaluate('galleryQA.finish()');active(page)
                            st=state(page);check(f'CRETA {width}px {slide["id"]} line {i} exact audio and caption',st['active'][0]['src']==line['audio'] and st['caption']==line['text'])
                            check(f'CRETA {width}px {slide["id"]} line {i} actual photo loaded',page.locator('.slide.on .gallery-image').evaluate_all('(images)=>images.length>0&&images.every(i=>i.complete&&i.naturalWidth>0)'))
                            check(f'CRETA {width}px {slide["id"]} line {i} stays inside central stage',bounded(page))
                            check(f'CRETA {width}px {slide["id"]} line {i} no fabricated pointer',page.locator('.slide.on .gallery-pointer').evaluate_all('(nodes)=>nodes.every(e=>getComputedStyle(e).opacity===\"0\"||getComputedStyle(e).display===\"none\")') or any(c.get('placement')=='overlay' and c.get('anchor') and not next((m.get('proxy') for m in slide.get('media',[]) if m.get('image_id')==c.get('image_id')),False) for c in slide.get('callouts',[])))
                            if len(slide.get('media',[]))==2:
                                eligible=[m for m in slide['media'] if m.get('from_line',0)<=i]
                                latest=max(m.get('from_line',0) for m in eligible)
                                simultaneous=[m for m in eligible if m.get('from_line',0)==latest]
                                check(f'CRETA {width}px {slide["id"]} line {i} correct reviewed photo',current_surface(page).get_attribute('data-image-id') in [m['image_id'] for m in simultaneous])
                                if len(simultaneous)==2:
                                    page.wait_for_function("()=>[...document.querySelectorAll('.slide.on .gallery-secondary-image')].some(i=>i.complete&&i.naturalWidth>0)")
                                    sources=page.locator('.slide.on .gallery-image,.slide.on .gallery-secondary-image').evaluate_all('(images)=>images.filter(i=>i.complete&&i.naturalWidth>0).map(i=>i.getAttribute(\"src\"))')
                                    check(f'CRETA {width}px {slide["id"]} simultaneous pictures both loaded',all(m['image_url'] in sources for m in simultaneous),sources)
                            for c in slide.get('callouts',[]):
                                if c.get('reveal_on_line',0)==i:
                                    check(f'CRETA {width}px {slide["id"]} callout {c["id"]} exact source text',c['text'] in page.locator('.slide.on .gallery-captions').inner_text())
                                    if len(slide.get('media',[]))==2:
                                        before_click=state(page);page.locator('.slide.on .gallery-tag[data-id="'+c['id']+'"]').click()
                                        page.wait_for_function('(owner)=>document.querySelector(\".slide.on .gallery-surface\")?.dataset.imageId===owner',arg=c['image_id'])
                                        page.wait_for_function('()=>document.querySelector(\".slide.on .gallery-image\")?.naturalWidth>0')
                                        after_click=state(page)
                                        expected_url=next(m['image_url'] for m in slide['media'] if m['image_id']==c['image_id'])
                                        check(f'CRETA {width}px {slide["id"]} callout {c["id"]} focuses exact source without replay',page.locator('.slide.on .gallery-image').get_attribute('src')==expected_url and after_click['active']==before_click['active'] and len(after_click['played'])==len(before_click['played']))
                        check(f'CRETA {width}px {slide["id"]} bundle not mutated',st['unchanged'])
                    page.emulate_media(reduced_motion='no-preference');click(page,'Wheel finishes by trim')
                    page.wait_for_function("()=>['walking','straightening','entering','focusing'].includes(document.querySelector('.slide.on .gallery-surface')?.dataset.state)")
                    page.wait_for_function("()=>Number(getComputedStyle(document.querySelector('.slide.on')).opacity)>=.98")
                    page.screenshot(path=str(args.output/f'creta-gallery-entry-{width}.png'))
                    prepare_click_attempt(page,f'CRETA {width}px two-photo source')
                    active(page);page.wait_for_function("()=>document.querySelector('.slide.on .gallery-image')?.naturalWidth>0")
                    check(f'CRETA {width}px final image and reviewed tags are loaded',page.locator('.slide.on .gallery-image').evaluate('(i)=>i.complete&&i.naturalWidth>0') and page.locator('.slide.on .gallery-tag').count()==3)
                    check(f'CRETA {width}px no microphone access',page.evaluate('window.microphoneAttempts===0'))
                    page.screenshot(path=str(args.output/f'creta-focused-{width}.png'),animations='disabled');page.context.close()
            if not args.skip_legacy:
                legacy=page_for(base);legacy.goto(base+'/player_contract.html');legacy.get_by_role('button',name='Run checks',exact=True).click();legacy.wait_for_function('() => !!window.playerContractReport',timeout=60000)
                current=legacy.evaluate('window.playerContractReport');(args.output/'player-browser-current.json').write_text(json.dumps(current,indent=2)+'\n');print('Legacy current',current['passed'],current['total'],flush=True);legacy.context.close()
        browser.close()
    for server in servers:server.shutdown()
    check('No browser script errors, failed source images or external requests',not errors and not blocked and not asset_errors,{'errors':errors,'blocked':blocked,'asset_errors':asset_errors})
    receipt={'passed':sum(r['passed'] for r in rows),'total':len(rows),'checks':rows,'errors':errors,'blocked':blocked,'asset_errors':asset_errors,'baseline_revision':args.baseline_revision,'scope':'Actual mountPlayer, isolated muted browser, approved local fixture bytes; fake audio/API, no acoustic claim','provider_calls':0}
    (args.output/'gallery-browser.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return 0 if all(r['passed'] for r in rows) else 1

if __name__=='__main__':raise SystemExit(main())
