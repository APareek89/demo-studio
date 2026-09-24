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
import time
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
const api={tts:async()=>null,pitch:async()=>null,saveSession:async b=>{__saved.push(b);return{};},beacon:b=>__saved.push(b),lead:async()=>({}),qa:async body=>{
 const target=bundle.slides.find(s=>s.id!==body.slide_id&&s.callouts?.some(c=>c.anchor)&&s.kind==='proof');const callout=target.callouts.find(c=>c.anchor);
 return {answered:true,answer:'This is the reviewed detail from the selected slide.',fact_ids:callout.fact_ids,route:'jump',slide_id:target.id,callout_id:callout.id,audio:null};}};
window.player=mountPlayer(document.querySelector('#fixture'),bundle,api);
new MutationObserver(()=>{const hall=document.querySelector('.wt-hall');if(hall){const state=JSON.stringify(hall.dataset);if(window.__lastState!==state){window.__lastState=state;__events.push({state:JSON.parse(state),context:player.context(),t:performance.now()});}}}).observe(document.querySelector('#fixture'),{subtree:true,attributes:true,attributeFilter:['data-phase','data-frame','data-stop','data-zoom','data-active','data-frozen']});
window.__snapshot=()=>({context:player.context(),hall:document.querySelector('.wt-hall')?{...document.querySelector('.wt-hall').dataset}:null,active:__active?.text,stage:document.querySelector('.pl-stage').getBoundingClientRect().toJSON(),pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,bundleUnchanged:JSON.stringify(bundle)===__bundleBefore});
window.ready=true;
</script>"""


def walkthrough_record(url, output, repo=None):
    """Record current-slide continuity for the compatible walkthrough URL.

    Gallery motion was superseded by the user's slide-first direction. This
    records native pictures/tags and unchanged playback with controlled speech
    ends; it does not claim microphone, TTS or historical gallery acceptance.
    """
    repo = (repo or Path(__file__).resolve().parents[1]).resolve()
    output = Path(output).resolve(); output.mkdir(parents=True, exist_ok=True)
    parsed = urlsplit(url)
    assert parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost') and parsed.port != 8896
    assert 'mute=1' in parsed.query and parsed.fragment.startswith('/play/')
    base = f'{parsed.scheme}://{parsed.netloc}'
    errors, rejected, results = [], [], []
    def check(name, value):
        results.append({'name': name, 'passed': bool(value)})
        print(('PASS ' if value else 'FAIL ') + name, flush=True)
        assert value, name
    inspect = r"""()=>{
      const state=__snapshot(),slide=bundle.slides.find(s=>s.id===state.context.slide),el=document.querySelector('.slide.on');
      const visible=n=>{if(!n)return false;const r=n.getBoundingClientRect(),css=getComputedStyle(n);return r.width>0&&r.height>0&&css.display!=='none'&&css.visibility==='visible'&&css.opacity!=='0';};
      const entries=Array.isArray(slide?.media)?slide.media:slide?.image_url?[{image_url:slide.image_url}]:[];
      const expected=entries.map(e=>e.image_url).filter(Boolean).map(url=>new URL(url,location.href).href);
      const actual=[...(el?.querySelectorAll('.slide-pic img')||[])].map(n=>({src:n.src,visible:visible(n)&&visible(n.closest('.slide-pic'))}));
      const line=slide?.lines?.findIndex(row=>row.text===state.active)??-1;
      const tags=(slide?.callouts||[]).filter(c=>line>=0&&Number(c.reveal_on_line)<=line);
      const labels=[...(el?.querySelectorAll('.callout,.slide-panel .item')||[])];
      const tagsVisible=tags.every(c=>labels.some(n=>n.dataset.id===c.id&&n.textContent.includes(c.text)&&visible(n)&&!n.classList.contains('hidden')));
      return {...state,line,expected,actual,tagsVisible,noGallery:!document.querySelector('.wt-hall,.wt-frame,.wt-caption'),
        camerasNative:[...(el?.querySelectorAll('.slide-cam')||[])].every(n=>getComputedStyle(n).display==='contents'&&getComputedStyle(n).transform==='none')};
    }"""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=browser_executable(), headless=True,
                                    args=['--mute-audio', '--disable-background-networking'])
        def make_page(enabled=True, width=1280, height=720, reduced=False):
            context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce' if reduced else 'no-preference')
            def guard(route):
                path = urlsplit(route.request.url).path
                if not route.request.url.startswith(base + '/'):
                    rejected.append(route.request.url); route.abort(); return
                if path == '/__wp12_record__':
                    route.fulfill(body=TOUR_HTML, content_type='text/html'); return
                if path.startswith('/web/'):
                    file = (repo / path.lstrip('/')).resolve()
                    if file.is_relative_to(repo / 'web') and file.is_file():
                        route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(file.name)[0] or 'text/plain'); return
                if route.request.method == 'GET': route.continue_(); return
                rejected.append(route.request.url); route.abort()
            context.route('**/*', guard)
            page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base + '/__wp12_record__?mute=1' + ('&presentation=walkthrough' if enabled else '') + '#' + parsed.fragment)
            page.wait_for_function('window.ready')
            page.wait_for_function("[...document.querySelectorAll('.slide img')].every(i=>i.complete)")
            return context, page
        def native(row):
            return (row['noGallery'] and row['camerasNative'] and row['tagsVisible']
                    and all(any(actual['src'] == src and actual['visible'] for actual in row['actual']) for src in row['expected'])
                    and all(actual['src'] in row['expected'] for actual in row['actual']))
        traces = []
        for enabled in (False, True):
            context, page = make_page(enabled)
            label = 'flag-on' if enabled else 'flag-off'
            page.get_by_role('button', name='Browse at my pace', exact=True).click()
            rows = []
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline and len(rows) < 200:
                page.wait_for_timeout(35)
                if page.evaluate('!!window.__active'):
                    row = page.evaluate(inspect); rows.append(row)
                    check(f'{label} speech {len(rows)} keeps its current native picture and revealed tags', native(row))
                    page.evaluate('__finish()'); continue
                if page.locator('.pl-handoff.open').count(): break
                labels = page.locator('.pl-chips button').all_text_contents()
                choice = next((name for name in ['Not yet', 'Continue demo', 'That settles it', 'Continue', 'Yes, continue'] if name in labels), None)
                if choice: page.get_by_role('button', name=choice, exact=True).click(); continue
                if page.locator('.pl-lead.open .lead-close').count(): page.locator('.pl-lead.open .lead-close').click()
            else: raise AssertionError('Full tour did not reach handoff within 120 seconds / 200 utterances')
            trace = page.evaluate('({spoken:__spoken,state:__snapshot(),saved:__saved})'); trace['native_views'] = rows
            traces.append(trace); write_json(output / ('full-on.json' if enabled else 'full-off.json'), trace)
            check(label + ' full tour reaches recap with unchanged bundle', trace['state']['bundleUnchanged'] and page.locator('.pl-handoff.open').count() == 1)
            page.locator('.pl-stage').screenshot(path=str(output / (label + '-closing.png')))
            context.close()
        check('flag preserves narrated text, logical timing and public checkpoints', traces[0]['spoken'] == traces[1]['spoken'])
        for width, height, reduced in [(1280,720,False),(1024,640,False),(800,600,False),(700,600,False),(699,600,False),(390,640,False),(1280,720,True)]:
            context, page = make_page(True, width, height, reduced)
            page.get_by_role('button', name='Browse at my pace', exact=True).click(); page.wait_for_timeout(35)
            before = page.evaluate(inspect)
            check(f'{width}x{height} reduce={reduced} shows the native slide at speech start', native(before) and before['pageWidth'] <= width + 1)
            page.get_by_role('button', name='Pause / resume', exact=True).click()
            paused = page.evaluate(inspect); page.wait_for_timeout(200)
            check(f'{width}x{height} pause retains the same photo without presentation movement', native(paused) and paused['actual'] == page.evaluate(inspect)['actual'])
            page.get_by_role('button', name='Pause / resume', exact=True).click(); page.wait_for_timeout(35)
            after = page.evaluate(inspect)
            check(f'{width}x{height} resume retains the narration checkpoint', native(after) and after['context']['slide'] == before['context']['slide'] and after['context']['line_index'] == before['context']['line_index'])
            page.locator('.pl-stage').screenshot(path=str(output / (f'native-{width}x{height}-reduce-{reduced}.png')))
            context.close()
        check('no browser exceptions or external/mutation requests', not errors and not rejected)
        write_json(output / 'recording-results.json', {'results': results, 'errors': errors, 'rejected': rejected,
            'boundary': 'Real mountPlayer and supplied bundle; controlled local speech ends. Native current-photo/tag continuity replaces historical gallery-phase assertions. No paid calls, microphone or voice-quality claim.'})
        browser.close()
        print(f'Walkthrough URL native recording: {len(results)}/{len(results)}', flush=True)


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
