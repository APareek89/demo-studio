"""WP12 isolated browser evidence: unchanged chrome/Align parity and real-player tour.

The reference animation is deliberately not served here. Only repository harnesses,
static app files and an explicitly supplied isolated MOCK_LLM URL are permitted.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import mimetypes
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def browser_executable():
    candidates = [os.getenv('CHROME_BIN'), '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome']
    return next((p for p in candidates if p and Path(p).is_file()), None)


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def parity(browser, repo, output, baseline=None):
    """Same real renderer fixture for baseline/after; pixels and raw DOM both retained."""
    layout = module_from(repo / 'evals/ui_layout_contract.py', 'wp12_layout_fixture')
    base = 'http://127.0.0.1:8892'
    rejected, errors, rows = [], [], []
    context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    def serve(route):
        path = urlsplit(route.request.url).path
        if not route.request.url.startswith(base + '/') or route.request.method != 'GET':
            rejected.append(route.request.url); route.abort(); return
        if path == '/':
            route.fulfill(body=layout.HTML, content_type='text/html'); return
        if path == '/reference-car.jpg':
            body, mime = layout.reference_pixels(); route.fulfill(body=body, content_type=mime); return
        file = (repo / path.lstrip('/')).resolve()
        if file.is_relative_to(repo / 'web') and file.is_file():
            route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(file.name)[0] or 'text/plain'); return
        rejected.append(route.request.url); route.abort()
    context.route('**/*', serve)
    page = context.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(base + '/?mute=1'); page.wait_for_function('window.ready')
    for width in (1440, 1024, 800):
        page.set_viewport_size({'width': width, 'height': 900})
        page.evaluate("approvedLayout('marine',true)")
        page.evaluate('settle()'); page.evaluate('settle()')
        for selector, name in [('.pl-top', 'top'), ('.pl-dock', 'dock')]:
            target = page.locator(selector)
            file = output / f'{name}-{width}.png'; target.screenshot(path=str(file))
            record = {'name': f'{name}-{width}', 'rectangle': target.bounding_box(), 'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
            if baseline:
                from PIL import Image, ImageChops
                old = Image.open(baseline / file.name).convert('RGBA'); new = Image.open(file).convert('RGBA')
                record['identical_pixels'] = old.size == new.size and ImageChops.difference(old, new).getbbox() is None
                assert record['identical_pixels'], record
            rows.append(record)
        # Actual editable picture arrangement and pointer drag, then real fit preview.
        page.evaluate('crossed(true,true)'); page.evaluate('settle()')
        before = page.evaluate("document.querySelector('.slide').outerHTML")
        first = page.locator('.callout').first; box = first.bounding_box()
        page.mouse.move(box['x'] + 8, box['y'] + 8); page.mouse.down()
        page.mouse.move(box['x'] + 38, box['y'] + 28); page.mouse.up(); page.evaluate('settle()')
        editor = page.evaluate("({html:document.querySelector('.slide').outerHTML,data:slideData})")
        page.evaluate("approvedLayout('marine',true)"); page.evaluate('settle()')
        preview = page.evaluate("document.querySelector('.slide').outerHTML")
        dom = {'editable_before': before, 'editable_after_drag': editor, 'preview': preview}
        file = output / f'align-dom-{width}.json'; write_json(file, dom)
        if baseline:
            assert json.loads((baseline / file.name).read_text()) == dom, f'Align DOM changed at {width}'
        rows.append({'name': f'align-dom-{width}', 'byte_identical': True if baseline else None})
    assert not errors and not rejected, {'errors': errors, 'rejected': rejected}
    write_json(output / 'parity.json', {'rows': rows, 'errors': errors, 'rejected': rejected,
               'baseline': str(baseline) if baseline else None, 'boundary': 'Real DOM and pointer drag; deterministic local fixture, reduced motion, no provider or microphone.'})
    context.close()
    return len(rows)


def html_contract(browser, repo, output):
    """The exact built-in player_browser.Handler, on an ephemeral owned loopback port."""
    import threading
    from http.server import ThreadingHTTPServer
    harness = module_from(repo / 'evals/player_browser.py', 'wp12_player_browser')
    server = ThreadingHTTPServer(('127.0.0.1', 0), harness.Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    context = browser.new_context(viewport={'width': 1440, 'height': 1000})
    external, errors = [], []
    def guard(route):
        if route.request.url.startswith(base + '/'):
            route.continue_()
        else:
            external.append(route.request.url); route.abort()
    context.route('**/*', guard)
    page = context.new_page(); page.on('pageerror', lambda e: errors.append(str(e)))
    try:
        page.goto(base + '/')
        page.locator('#run:not([disabled])').click()
        import time
        deadline = time.monotonic() + 120
        while not page.evaluate('Boolean(window.playerContractReport)'):
            if time.monotonic() > deadline:
                write_json(output / 'player-html-incomplete.json', {'summary': page.locator('#summary').inner_text(), 'results': page.locator('#results').inner_text(), 'errors': errors})
                raise AssertionError('Player HTML contract did not complete; see incomplete report')
            page.wait_for_timeout(100)
        report = page.evaluate('window.playerContractReport')
        report.update(errors=errors, external=external)
        write_json(output / 'player-html.json', report)
        assert report['passed'] == report['total'] and not errors and not external, report
        return report['passed']
    finally:
        context.close(); server.shutdown(); server.server_close()


TOUR_HTML = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="stylesheet" href="/web/styles.css"><link rel="stylesheet" href="/web/design-system.css"><link rel="stylesheet" href="/web/player-ui.css">
<style>html,body{margin:0;width:100%;height:100%;overflow:hidden}#fixture{height:100dvh;width:100%;position:relative}</style><div id="fixture"></div>
<script type="module">
window.__events=[];window.__spoken=[];window.__logicalTime=0;window.__active=null;window.__saved=[];window.__errors=[];
const __nativeTimeout=window.setTimeout.bind(window);window.setTimeout=(fn,delay,...args)=>{const id=__nativeTimeout(fn,delay,...args);window.__lastTimer={id,delay};return id;};
window.__speechCount=0;window.SpeechSynthesisUtterance=class{constructor(text){this.text=text;}};
Object.defineProperty(window,'speechSynthesis',{configurable:true,value:{getVoices:()=>[],cancel(){window.__active=null;},speak(u){if(window.__lastTimer?.delay===Math.max(1500,u.text.length*75)+4000)clearTimeout(window.__lastTimer.id);window.__active=u;window.__speechCount++;window.__spoken.push({text:u.text,t:window.__logicalTime,context:window.player?.context()});u.onstart?.();}}});
window.__finish=()=>{const u=window.__active;if(!u)return false;window.__active=null;window.__logicalTime+=Math.max(1500,u.text.split(/\s+/).length*500);u.onend?.();return true;};
Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{getUserMedia(){throw Error('Physical microphone forbidden in WP12 recorder')}}});
const {mountPlayer}=await import('/web/player/player.js');
const did=location.hash.split('/').at(-1);window.bundle=await(await fetch('/api/demos/'+did+'/bundle')).json();
window.__bundleBefore=JSON.stringify(bundle);
const api={tts:async()=>null,pitch:async()=>null,session:async b=>{__saved.push(b);return{};},beacon:b=>__saved.push(b),lead:async()=>({}),qa:async body=>{
 const target=bundle.slides.find(s=>s.id!==body.slide_id&&s.callouts?.some(c=>c.anchor)&&s.kind==='proof');const callout=target.callouts.find(c=>c.anchor);
 return {answered:true,answer:'This is the reviewed detail from the selected slide.',fact_ids:callout.fact_ids,route:'jump',slide_id:target.id,callout_id:callout.id,audio:null};}};
window.player=mountPlayer(document.querySelector('#fixture'),bundle,api);
new MutationObserver(()=>{const hall=document.querySelector('.wt-hall');if(hall){const state=JSON.stringify(hall.dataset);if(window.__lastState!==state){window.__lastState=state;__events.push({state:JSON.parse(state),context:player.context(),t:performance.now()});}}}).observe(document.querySelector('#fixture'),{subtree:true,attributes:true,attributeFilter:['data-phase','data-frame','data-stop','data-zoom','data-active','data-frozen']});
window.__snapshot=()=>({context:player.context(),hall:document.querySelector('.wt-hall')?{...document.querySelector('.wt-hall').dataset}:null,active:__active?.text,stage:document.querySelector('.pl-stage').getBoundingClientRect().toJSON(),pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,bundleUnchanged:JSON.stringify(bundle)===__bundleBefore});
window.ready=true;
</script>"""


def walkthrough_record(url, output, repo=None):
    """Real mountPlayer and exact supplied bundle; audio end events are controlled locally.

    This is motion/ownership acceptance, not a microphone or provider-quality claim.
    The backing URL must point at the caller's isolated MOCK_LLM server.
    """
    import time
    repo = (repo or Path(__file__).resolve().parents[1]).resolve()
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    parsed = urlsplit(url)
    assert parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1','localhost') and parsed.port != 8896
    assert 'mute=1' in parsed.query and parsed.fragment.startswith('/play/')
    base = f'{parsed.scheme}://{parsed.netloc}'
    errors, rejected, results = [], [], []
    def check(name, value):
        results.append({'name':name,'passed':bool(value)})
        print(('PASS ' if value else 'FAIL ') + name, flush=True)
        assert value, name
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_executable(),headless=True,args=['--mute-audio','--disable-background-networking'])
        def make_page(enabled=True, width=1280, height=720, reduced=False):
            context = browser.new_context(viewport={'width':width,'height':height},reduced_motion='reduce' if reduced else 'no-preference')
            def guard(route):
                u=urlsplit(route.request.url); path=u.path
                if not route.request.url.startswith(base+'/'):
                    rejected.append(route.request.url);route.abort();return
                if path=='/__wp12_record__':route.fulfill(body=TOUR_HTML,content_type='text/html');return
                if path.startswith('/web/'):
                    file=(repo/path.lstrip('/')).resolve()
                    if file.is_relative_to(repo/'web') and file.is_file():route.fulfill(body=file.read_bytes(),content_type=mimetypes.guess_type(file.name)[0] or 'text/plain');return
                if route.request.method=='GET':route.continue_();return
                rejected.append(route.request.url);route.abort()
            context.route('**/*',guard);page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            query='?mute=1'+('&presentation=walkthrough' if enabled else '')
            page.goto(base+'/__wp12_record__'+query+'#'+parsed.fragment);page.wait_for_function('window.ready')
            page.wait_for_function("[...document.querySelectorAll('.slide img')].every(i=>i.complete)")
            return context,page
        # Deterministic speech-end schedule: the presentation may never hold a line.
        traces=[]
        for enabled in (False,True):
            context,page=make_page(enabled)
            page.get_by_role('button',name='Browse at my pace',exact=True).click()
            for step in range(100):
                page.wait_for_timeout(35)
                if page.evaluate('!!window.__active'):page.evaluate('__finish()');continue
                if page.locator('.pl-handoff.open').count():break
                labels=page.locator('.pl-chips button').all_text_contents()
                choice=next((x for x in ['Not yet','Continue demo','That settles it','Continue','Yes, continue'] if x in labels),None)
                if choice:page.get_by_role('button',name=choice,exact=True).click();continue
                if page.locator('.pl-lead.open .lead-close').count():page.locator('.pl-lead.open .lead-close').click()
            else:raise AssertionError('Full tour did not reach handoff within100 audio/choice events')
            trace=page.evaluate('({spoken:__spoken,events:__events,state:__snapshot(),saved:__saved})')
            traces.append(trace);write_json(output/('full-on.json' if enabled else 'full-off.json'),trace)
            check(('flag-on' if enabled else 'flag-off')+' full real-script tour reaches recap and keeps bundle immutable',trace['state']['bundleUnchanged'] and page.locator('.pl-handoff.open').count()==1)
            context.close()
        check('flag does not change narrated text, logical audio timing or public context checkpoints',traces[0]['spoken']==traces[1]['spoken'])
        # A complete paced pass lets every real deck line reach its camera pose,
        # in addition to the rapid retargeting trace above. Five-point-two seconds
        # is an explicit synthetic line fixture, never a measured voice duration.
        context,page=make_page(True);page.get_by_role('button',name='Browse at my pace',exact=True).click()
        paced=[];seen_pictures=set()
        for step in range(60):
            if page.locator('.pl-handoff.open').count():break
            if page.evaluate('!!__active'):
                page.wait_for_timeout(5200)
                row=page.evaluate("""(()=>{const state=__snapshot(),sl=bundle.slides.find(s=>s.id===state.context.slide),line=sl?.lines?.findIndex(l=>l.text===state.active),pic=document.querySelector('.wt-picture-live'),cam=pic?.querySelector('.slide-cam'),image=pic?.querySelector('img'),r=pic?.getBoundingClientRect(),c=cam?.getBoundingClientRect();return {...state,line,media:sl?.media,clip:pic?getComputedStyle(pic).overflow:null,cap:pic?Math.min(2.2,image.naturalWidth/pic.clientWidth*1.15):null,panCovered:r&&c?c.left<=r.left+1&&c.right>=r.right-1&&c.top<=r.top+1&&c.bottom>=r.bottom-1:null}})()""")
                paced.append(row)
                write_json(output/'paced-tour.json',{'rows':paced,'events':page.evaluate('__events'),'boundary':'Synthetic5200ms held speech per line; synthetic speech completion is driver-owned. Actual camera transitionend and computed geometry; not measured TTS duration.'})
                if row['line'] is not None and row['line']>=0 and row.get('media') and row['hall'] and row['hall']['phase'] not in ('wide','transient'):
                    media_index=max((i for i,m in enumerate(row['media']) if m.get('from_line',0)<=row['line']),default=0)
                    expected=page.locator(f'.wt-frame[data-slide-id="{row["context"]["slide"]}"][data-media-index="{media_index}"]').get_attribute('data-frame')
                    check(f'paced {row["context"]["slide"]} line{row["line"]} reaches its picture frame',row['hall']['frame']==expected)
                    seen_pictures.add((row['context']['slide'],media_index))
                    if row.get('cap') is not None:check(f'paced {row["context"]["slide"]} line{row["line"]} caps zoom and covers viewport',float(row['hall']['zoom'])<=row['cap']+0.01 and row['panCovered'])
                    if media_index==1 and not (output/'two-picture-walk.png').exists():page.locator('.pl-stage').screenshot(path=str(output/'two-picture-walk.png'))
                page.evaluate('__finish()');page.wait_for_timeout(40);continue
            choices=page.locator('.pl-chips button').all_text_contents()
            if 'Not yet' in choices:page.get_by_role('button',name='Not yet',exact=True).click();continue
            page.wait_for_timeout(70)
        check('paced walkthrough traverses all content slides and reaches closing',page.locator('.pl-handoff.open').count()==1 and set(row['context']['slide'] for row in paced)>=set(page.evaluate("bundle.slides.filter(s=>s.kind!=='hero_open').map(s=>s.id)")))
        expected_count=page.evaluate("bundle.slides.filter(s=>!['hero_open','closing','hero_close'].includes(s.kind)).reduce((n,s)=>n+(s.media?.length||1),0)")
        check('paced walkthrough visits every published picture including second-picture stops',len(seen_pictures)==expected_count)
        write_json(output/'paced-tour.json',{'rows':paced,'events':page.evaluate('__events'),'boundary':'Synthetic5200ms held speech per line; actual transitionend and computed geometry. Not measured TTS duration.'});context.close()
        # Hold real player speech at each line so the event-driven camera can settle.
        context,page=make_page(True)
        page.locator('.pl-stage').screenshot(path=str(output/'gallery.png'))
        page.get_by_role('button',name='Browse at my pace',exact=True).click()
        captured=set(); pause_phases=set()
        wanted={'walk':'walk','straighten':'straighten','dive':'dive','stop':'tour-stop','rise':'rise'}
        for step in range(40):
            deadline=time.monotonic()+5.8
            while time.monotonic()<deadline:
                state=page.evaluate('__snapshot()');hall=state['hall'] or {};phase=hall.get('phase')
                if phase in wanted and phase not in captured:
                    if phase=='stop':
                        check('tour viewport clips camera while labels and leaders hide immediately',page.evaluate("(()=>{const p=document.querySelector('.wt-picture-live');return !!p&&getComputedStyle(p).overflow==='hidden'&&[...p.querySelectorAll('.callout,.leaders')].every(n=>getComputedStyle(n).visibility==='hidden')})()"))
                    page.locator('.pl-stage').screenshot(path=str(output/(wanted[phase]+'.png')));captured.add(phase)
                if phase in ('walk','dive','stop') and phase not in pause_phases:
                    beforeSpeech=page.evaluate('__active?.text');page.get_by_role('button',name='Pause / resume',exact=True).click()
                    frozenPose=page.evaluate("[...document.querySelectorAll('.wt-world,.wt-frame,.slide-cam')].map(n=>getComputedStyle(n).transform)")
                    page.wait_for_timeout(200)
                    check(phase+' nav pause freezes every computed moving transform',frozenPose==page.evaluate("[...document.querySelectorAll('.wt-world,.wt-frame,.slide-cam')].map(n=>getComputedStyle(n).transform)"))
                    page.get_by_role('button',name='Pause / resume',exact=True).click();page.wait_for_timeout(40)
                    check(phase+' nav resume replays interrupted speech',page.evaluate('__active?.text')==beforeSpeech)
                    pause_phases.add(phase)
                if phase=='stop' and hall.get('stop'):break
                page.wait_for_timeout(40)
            if len(captured)==len(wanted) and any(e['state'].get('frame') not in ('0','-1') for e in page.evaluate('__events')):break
            if page.evaluate('!!__active'):page.evaluate('__finish()')
            elif page.locator('.pl-handoff.open').count():break
        write_json(output/'camera-events.json',page.evaluate('__events'))
        check('recorded gallery, walk, straighten, dive, tour stop and rise',set(wanted)<=captured)
        check('pause and resume exercised mid-walk, mid-dive and mid-tour',pause_phases=={'walk','dive','stop'})
        # Nav pause freezes computed transforms; replay resumes the interrupted line.
        before=page.evaluate('__snapshot()');page.locator('button[title="Pause / resume"]').click()
        frozen=page.evaluate("[...document.querySelectorAll('.wt-world,.slide-cam')].map(n=>getComputedStyle(n).transform)")
        page.wait_for_timeout(350)
        check('nav pause freezes moving transforms',frozen==page.evaluate("[...document.querySelectorAll('.wt-world,.slide-cam')].map(n=>getComputedStyle(n).transform)"))
        page.locator('button[title="Pause / resume"]').click();page.wait_for_timeout(50)
        check('nav resume replays same narration checkpoint',page.evaluate('__snapshot().context.line_index')==before['context']['line_index'])
        # Typed Q&A uses a deterministic reviewed slide route, then real Continue.
        origin=page.evaluate('player.context()');question=page.get_by_role('textbox',name='Your question or answer',exact=True)
        question.fill('Show another reviewed feature.');question.press('Enter')
        for _ in range(5):
            page.wait_for_timeout(60)
            if page.evaluate('player.context().slide')!=origin['slide']:break
            page.evaluate('__finish()')
        page.wait_for_timeout(250)
        page.locator('.pl-stage').screenshot(path=str(output/'jump-to-slide.png'))
        check('answer jumps to another reviewed slide',page.evaluate('player.context().slide')!=origin['slide'])
        for _ in range(4):
            if page.locator('.pl-chips button').filter(has_text='Continue demo').count():break
            page.evaluate('__finish()');page.wait_for_timeout(60)
        page.get_by_role('button',name='Continue demo',exact=True).click()
        page.wait_for_timeout(70)
        # The existing recorded back-to-demo filler may precede restoring the view.
        if page.evaluate('player.context().slide')!=origin['slide']:page.evaluate('__finish()');page.wait_for_timeout(70)
        check('Continue restores interrupted slide and line',page.evaluate('player.context().slide')==origin['slide'] and page.evaluate('player.context().line_index')==origin['line_index'])
        page.locator('.pl-stage').screenshot(path=str(output/'return-to-origin.png'))
        write_json(output/'interactive-events.json',page.evaluate('({events:__events,state:__snapshot()})'))
        context.close()
        for stop_phase in ('walk','dive','stop'):
            context,page=make_page(True)
            page.get_by_role('button',name='Browse at my pace',exact=True).click()
            page.wait_for_function("phase=>document.querySelector('.wt-hall')?.dataset.phase===phase",arg=stop_phase,timeout=8000)
            page.get_by_role('button',name='Stop and see the summary',exact=True).click();page.wait_for_timeout(100)
            check(stop_phase+' Stop returns gallery wide and shows recap',page.locator('.pl-handoff.open').count()==1 and page.evaluate("document.querySelector('.wt-hall')?.dataset.phase")=='wide')
            page.get_by_role('button',name='Restart',exact=True).click();page.wait_for_timeout(100)
            check(stop_phase+' Restart rebuilds frames and clears prior route',page.locator('.wt-frame').count()>0 and page.evaluate('player.context().route.length')==0 and page.locator('.pl-intake.open').count()==1)
            context.close()
        # Leave walkthrough during the first picture, progress the real narration
        # while fallback methods own the view, then restore the large stage.
        for mode in ('narrow','reduced'):
            context,page=make_page(True)
            page.get_by_role('button',name='Browse at my pace',exact=True).click()
            target=page.evaluate("bundle.slides.find(s=>s.media?.length===2)")
            for _ in range(12):
                if page.evaluate('player.context().slide')==target['id']:break
                page.evaluate('__finish()');page.wait_for_timeout(50)
            check(mode+' toggle starts from first picture of an actual two-picture slide',page.evaluate('player.context().slide')==target['id'])
            if mode=='narrow':page.set_viewport_size({'width':699,'height':720})
            else:page.emulate_media(reduced_motion='reduce')
            page.wait_for_timeout(120)
            check(mode+' transition uses unchanged fallback',not page.locator('.wt-hall').count())
            second=target['media'][1]['from_line']
            for _ in range(second):page.evaluate('__finish()');page.wait_for_timeout(70)
            active=page.evaluate('__active?.text')
            check(mode+' fallback advances narration to second-picture line',active==target['lines'][second]['text'])
            if mode=='narrow':page.set_viewport_size({'width':1280,'height':720})
            else:page.emulate_media(reduced_motion='no-preference')
            if mode=='narrow':
                page.locator('.pl-stage').screenshot(path=str(output/'two-picture-walk.png'))
            page.wait_for_timeout(4500)
            current=page.evaluate('__snapshot()');expected=page.locator(f'.wt-frame[data-slide-id="{target["id"]}"][data-media-index="1"]').get_attribute('data-frame')
            check(mode+' return retains current second picture and speech',current['hall']['frame']==expected and current['active']==active)
            page.locator('.pl-stage').screenshot(path=str(output/(mode+'-restore-second-picture.png')))
            context.close()
        for width,height,reduced in [(1280,720,False),(1024,640,False),(800,600,False),(700,600,False),(699,600,False),(1280,720,True)]:
            context,page=make_page(True,width,height,reduced);page.get_by_role('button',name='Browse at my pace',exact=True).click();page.wait_for_timeout(250)
            state=page.evaluate('__snapshot()');hall=state['hall'] or {}
            check(f'{width}x{height} reduce={reduced} stays within stage',state['pageWidth']<=width+1)
            if reduced or width<700:check(f'{width} reduce={reduced} uses ordinary crossfade fallback',hall.get('active') in ('false',None) and page.locator('.slide-stack .slide.on').count()==1)
            page.locator('.pl-stage').screenshot(path=str(output/(f'reduced-motion.png' if reduced else f'stage-{width}x{height}.png')));context.close()
        check('no browser exceptions or external/mutation requests',not errors and not rejected)
        write_json(output/'recording-results.json',{'results':results,'errors':errors,'rejected':rejected,'boundary':'Exact published scratch bundle, real mountPlayer and motion; synthetic browser speech end events and local QA route fixture. No paid provider, real microphone, or acoustic timing claim.'})
        browser.close()
        print(f'WP12 recording: {len(results)}/{len(results)}',flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--parity-only', action='store_true')
    parser.add_argument('--url', help='Record an isolated MOCK_LLM player URL instead of parity')
    args = parser.parse_args()
    repo = args.repo.resolve(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    assert not output.is_relative_to(repo), 'Keep browser artifacts outside the repository'
    if args.url:
        walkthrough_record(args.url, output, repo)
        return
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_executable(), headless=True,
             args=['--mute-audio', '--disable-background-networking', '--autoplay-policy=no-user-gesture-required'])
        try:
            count = parity(browser, repo, output, args.baseline)
            if not args.parity_only:
                count += html_contract(browser, repo, output)
            print(f'WP12 browser baseline/parity: {count}/{count}', flush=True)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
