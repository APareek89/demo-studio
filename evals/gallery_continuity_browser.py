#!/usr/bin/env python3
"""Muted actual-player regression for consecutive uses of one reviewed photo.

Only a loopback static server is reachable. Audio/API are the existing deterministic
gallery harness; optional BMW bundle/assets are read-only, never regenerated.
"""
import argparse
from http.server import ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import threading
from urllib.parse import unquote, urlsplit

from gallery_template_browser import Handler, ROOT


class ContinuityHandler(Handler):
    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        target = None
        if path == '/fixtures/bmw.json':
            target = self.server.bmw / 'bundle.json'
        elif path.startswith('/media/dm_29df0418/'):
            target = (self.server.bmw / path.removeprefix('/media/dm_29df0418/')).resolve()
            if not target.is_relative_to(self.server.bmw):
                self.send_error(404)
                return
        if target is None:
            return super().do_GET()
        if not target.is_file():
            self.send_error(404)
            return
        data = target.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type', mimetypes.guess_type(target.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/gallery-continuity-2026-09-25')
    parser.add_argument('--bmw', type=Path, default=Path('/tmp/demo-livekit-trial-20260925/review/data/dm_29df0418'))
    parser.add_argument('--revision', help='Read-only baseline code revision.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), ContinuityHandler)
    server.revision, server.creta, server.bmw = args.revision, None, args.bmw.resolve()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    rows, errors, blocked = [], [], []

    def check(name, value, detail=None):
        rows.append({'name': name, 'passed': bool(value), **({'detail': detail} if detail is not None else {})})
        print(('PASS ' if value else 'FAIL ') + name, flush=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True, args=['--mute-audio'])

        def page_for(width=1440, height=960):
            context = browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='no-preference')
            def route(r):
                if r.request.url.startswith(base + '/') and r.request.method == 'GET':
                    return r.continue_()
                blocked.append(r.request.url)
                return r.abort()
            context.route('**/*', route)
            context.route_web_socket('**/*', lambda ws: ws.close())
            page = context.new_page()
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.add_init_script("""window.galleryMoves=[];const animate=Element.prototype.animate;
                Element.prototype.animate=function(...args){if(String(this.className).startsWith('gallery-'))window.galleryMoves.push({target:this.className,frames:args[0],at:performance.now()});return animate.apply(this,args);};""")
            page.goto(base)
            page.wait_for_function('()=>window.galleryQA?.ready')
            return page

        def active(page):
            page.wait_for_function('()=>galleryQA.state().active.length===1', timeout=15000)
        def click(page, text):
            page.evaluate('(text)=>galleryQA.click(text)', text)
        def state(page):
            return page.evaluate('galleryQA.state()')
        def moves(page):
            return page.evaluate('window.galleryMoves.splice(0)')
        def entry_moves(items):
            return [item for item in items if item['target'] in ('gallery-world', 'gallery-frame', 'gallery-focus')]
        def frame(page):
            return page.locator('.slide.on .gallery-image').evaluate("""e=>{const r=e.getBoundingClientRect(),c=e.parentElement;return {src:e.getAttribute('src'),x:r.x,y:r.y,w:r.width,h:r.height,transform:c.style.transform,loaded:e.complete&&e.naturalWidth>0};}""")

        # Reproduce the user's exact opening: sl01 and sl02 share the hero photo.
        if (server.bmw / 'bundle.json').is_file():
            for width, height in [(1440, 960), (390, 844)]:
                page = page_for(width, height)
                page.evaluate("async()=>galleryQA.setup(await(await fetch('/fixtures/bmw.json')).json())")
                click(page, 'Browse at my pace')
                active(page)
                first, before = frame(page), state(page)
                check(f'BMW {width}: opening is the published intro', before['context']['slide'] == 'sl01' and first['loaded'])
                check(f'BMW {width}: first gallery visit retains its entrance', bool(entry_moves(moves(page))))
                page.screenshot(path=str(args.output / f'bmw-{width}-intro.png'), animations='disabled')
                page.evaluate('galleryQA.finish()')
                active(page)
                after, second, observed = state(page), frame(page), moves(page)
                check(f'BMW {width}: repeated source has no walk/enlarge replay', not entry_moves(observed), observed)
                check(f'BMW {width}: repeated source remains loaded at the same framing', first == second, {'before': first, 'after': second})
                check(f'BMW {width}: identical pixels do not crossfade or wash out', page.locator('.slide.on').evaluate("e=>getComputedStyle(e).opacity==='1'&&getComputedStyle(e).transitionDuration.split(',').every(t=>parseFloat(t)===0)"))
                check(f'BMW {width}: next reviewed captions and exact recording are ready', after['context']['slide'] == 'sl02' and after['played'][-1]['phase'] == 'ready' and after['active'][0]['text'] == after['caption'])
                shell = ['.pl-top', '.pl-progress', '.pl-dock']
                check(f'BMW {width}: outer shell and bundle stay unchanged', all(before['geometry'][key] == after['geometry'][key] for key in shell) and after['unchanged'],
                      {key: {'before': before['geometry'][key], 'after': after['geometry'][key]} for key in shell})
                page.screenshot(path=str(args.output / f'bmw-{width}-outcome.png'), animations='disabled')
                page.context.close()

        page = page_for(1000, 960)
        page.evaluate("""()=>{const b=galleryQA.synthetic(),a=b.slides[1];a.media=a.media.slice(0,1);a.lines=a.lines.slice(0,2);a.callouts=a.callouts.slice(0,1);a.callouts.push({...a.callouts[0],id:'same-anchor-next',text:'Another reviewed detail on this feature',reveal_on_line:1});
            const shared=structuredClone(a);shared.id='shared';shared.title='Another feature in the same picture';shared.lines=shared.lines.slice(0,1);shared.callouts=[{...shared.callouts[0],id:'shared-tag',text:'Next reviewed anchor',anchor:{x:.73,y:.75},part_box:{x:.5,y:.3,w:.4,h:.4}}];
            const distinct=structuredClone(shared);distinct.id='distinct';distinct.title='A different reviewed picture';distinct.media=[{...b.slides[3].media[0],proxy:false}];distinct.callouts=[{...distinct.callouts[0],image_id:distinct.media[0].image_id,id:'distinct-tag'}];
            b.slides=[b.slides[0],a,shared,distinct,b.slides[2],b.slides[4]];return galleryQA.setup(b);}""")
        click(page, 'Browse at my pace')
        active(page)
        moves(page)
        before = frame(page)
        page.evaluate('galleryQA.finish()')
        active(page)
        observed = moves(page)
        check('Same slide, same feature: no no-op camera or entrance animation', not observed, observed)
        check('Same slide, same feature: picture framing is stable and new caption appears', frame(page) == before and page.locator('.slide.on .gallery-tag.active').get_attribute('data-id') == 'same-anchor-next')
        page.evaluate('galleryQA.finish()')
        active(page)
        observed = moves(page)
        check('New slide, same source: only the new reviewed feature receives a focus move', len(observed) == 1 and observed[0]['target'] == 'gallery-camera', observed)
        check('New slide, same source: selected pointer belongs to the new reviewed tag', page.locator('.slide.on .gallery-tag.active').get_attribute('data-id') == 'shared-tag' and page.locator('.slide.on .gallery-pointer').evaluate("e=>getComputedStyle(e).opacity==='1'"))
        # Pausing/re-entering the same reviewed slide retains the exact frame.
        moves(page)
        click(page, 'Pause / resume')
        held = frame(page)
        page.wait_for_timeout(180)
        check('Pause freezes the carried frame', frame(page) == held and not state(page)['active'])
        click(page, 'Pause / resume')
        active(page)
        check('Resume does not replay the gallery entrance', not entry_moves(moves(page)) and state(page)['maxActive'] == 1)
        click(page, 'A different reviewed picture')
        page.wait_for_function("()=>['walking','straightening','entering','focusing','returning'].includes(document.querySelector('.slide.on .gallery-surface')?.dataset.state)")
        check('A distinct source keeps its gallery transition before narration', not state(page)['active'])
        active(page)
        check('Distinct source completes a real entrance and correct mapped picture', bool(entry_moves(moves(page))) and state(page)['context']['slide'] == 'distinct' and state(page)['played'][-1]['phase'] == 'ready')
        # A text-only slide breaks visual continuity, even if a later slide reuses a photo.
        click(page, 'Reviewed terms')
        active(page)
        moves(page)
        click(page, 'A different reviewed picture')
        active(page)
        check('An intervening native/text view ends the continuous-photo run', bool(entry_moves(moves(page))))
        # A question during a fresh entrance must cancel stale visual/audio work.
        click(page, 'Two reviewed pictures')
        page.wait_for_function("()=>['walking','straightening','entering','focusing','returning'].includes(document.querySelector('.slide.on .gallery-surface')?.dataset.state)")
        page.evaluate("galleryQA.question('What is supported?')")
        page.wait_for_function('()=>galleryQA.state().qa.length===1')
        page.wait_for_timeout(300)
        check('Question cancels the pending entrance without starting its stale narration', not state(page)['active'] and state(page)['maxActive'] == 1)
        click(page, 'Continue demo')
        active(page)
        check('Question return restores the exact approved line with one voice', state(page)['context']['slide'] == 'pair' and state(page)['context']['line_index'] == 0 and state(page)['active'][0]['text'] == 'Approved first image detail.' and state(page)['maxActive'] == 1)
        check('All synthetic navigation leaves approved bundle bytes unchanged', state(page)['unchanged'])
        page.context.close()
        # Existing two-picture source ownership still gets its distinct-photo intro.
        page = page_for()
        click(page, 'Browse at my pace')
        active(page)
        moves(page)
        page.evaluate('galleryQA.finish()')
        active(page)
        check('Two pictures in one slide retain bound-line ownership and transition', bool(entry_moves(moves(page))) and state(page)['played'][-1]['imageId'] == 'cabin' and state(page)['played'][-1]['tag'] == 'cabin-tag')
        page.context.close()
        browser.close()
    server.shutdown()
    check('No script errors or outbound browser requests', not errors and not blocked, {'errors': errors, 'blocked': blocked})
    receipt = {'passed': sum(row['passed'] for row in rows), 'total': len(rows), 'checks': rows, 'provider_calls': 0,
               'scope': 'Actual player/DOM/animations, real read-only BMW pictures, simulated muted audio/API, loopback-only network', 'revision': args.revision or 'working tree'}
    (args.output / 'gallery-continuity-browser.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(f"Gallery continuity: {receipt['passed']}/{receipt['total']}")
    return 0 if all(row['passed'] for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
