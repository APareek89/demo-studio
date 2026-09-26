#!/usr/bin/env python3
"""Actual Chromium/WebKit mobile gallery geometry with mocked audio and APIs.

Only an owned loopback static fixture is reachable. No application storage,
provider, physical microphone or production endpoint is used. Viewport resizing
and a synthetic VisualViewport height change cover rotation/keyboard layout;
they do not claim physical iPhone keyboard or acoustic acceptance.
"""
import argparse
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading

from gallery_template_browser import Handler, ROOT


MEASURE = r'''() => {
 const rect = e => { const r=e.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,right:r.right,bottom:r.bottom}; };
 const query = s => document.querySelector(s);
 const slide=query('.slide.on'),surface=slide.querySelector('.gallery-surface'),image=surface.querySelector('.gallery-image'),rail=surface.querySelector('.gallery-captions'),tag=rail.querySelector('[data-id="front-tag"]');
 const bounds=rect(surface),picture=rect(image),caption=rect(tag.querySelector('.gallery-feature-copy')),railBounds=rect(rail),viewportHeight=visualViewport.height+visualViewport.offsetTop;
 const controls=[...document.querySelectorAll('.pl-top button,.pl-reply input,.pl-reply button')].filter(e=>e.getBoundingClientRect().width&&getComputedStyle(e).visibility==='visible').map(e=>{
   const r=rect(e),hit=document.elementFromPoint(r.x+r.w/2,r.y+r.h/2);
   return {label:e.getAttribute('aria-label')||e.title||e.textContent,reachable:(hit===e||e.contains(hit))&&r.x>=0&&r.y>=0&&r.right<=innerWidth+1&&r.bottom<=viewportHeight+1};
 });
 const shell=Object.fromEntries(['.pl-top','.pl-dock','.pl-reply','.pl-action-bar'].map(s=>[s,rect(query(s))]));
 const s=galleryQA.state();
 return {surface:bounds,slide:rect(slide),picture,rail:railBounds,caption,footerDisplay:getComputedStyle(slide.querySelector('.slide-foot')).display,
   pictureLoaded:image.complete&&image.naturalWidth>0&&image.getAttribute('src')===galleryQA.bundle().slides[1].media[0].image_url,
   pictureVisible:picture.w>40&&picture.h>40&&picture.right>bounds.x&&picture.x<bounds.right&&picture.bottom>bounds.y&&picture.y<bounds.bottom,
   captionVisible:caption.x>=railBounds.x-1&&caption.right<=railBounds.right+1&&caption.y>=railBounds.y-1&&caption.bottom<=railBounds.bottom+1&&tag.textContent.includes('Front feature'),
   controls,shell,voice:{line:s.context.line_index,active:s.active.map(a=>a.src),played:s.played.length,max:s.maxActive},
   noPageOverflow:document.documentElement.scrollWidth<=innerWidth+1&&document.documentElement.scrollHeight<=innerHeight+1,
   viewport:{width:innerWidth,height:innerHeight,visualHeight:visualViewport.height,scale:visualViewport.scale},microphoneAttempts:window.microphoneAttempts};
}'''


def main():
    from playwright.sync_api import sync_playwright
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'output/mobile-layout-2026-09-26/current')
    parser.add_argument('--revision', help='Optional committed baseline for production web files.')
    parser.add_argument('--browser', choices=('both', 'chromium', 'webkit'), default='both')
    parser.add_argument('--port', type=int, default=8936)
    args = parser.parse_args()
    if args.port == 8896 or args.port < 1024:
        parser.error('Use a nonprivileged owned fixture port other than 8896.')
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    server.revision, server.creta = args.revision, None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = 'http://127.0.0.1:' + str(server.server_port)
    checks, measurements, errors, blocked = [], [], [], []

    def check(name, value, detail=None):
        checks.append({'name': name, 'passed': bool(value), **({'detail': detail} if detail is not None else {})})
        print(('PASS ' if value else 'FAIL ') + name, flush=True)

    try:
        with sync_playwright() as pw:
            for name in (['chromium', 'webkit'] if args.browser == 'both' else [args.browser]):
                options = {'headless': True}
                if name == 'chromium':
                    options.update(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', args=['--mute-audio', '--disable-background-networking'])
                browser = getattr(pw, name).launch(**options)
                try:
                    context = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True,
                                                  has_touch=True, device_scale_factor=2, reduced_motion='reduce')
                    def route(request):
                        if request.request.url.startswith(base + '/') and request.request.method == 'GET':
                            return request.continue_()
                        blocked.append({'browser': name, 'url': request.request.url})
                        return request.abort()
                    context.route('**/*', route)
                    context.route_web_socket('**/*', lambda socket: socket.close())
                    page = context.new_page()
                    page.on('pageerror', lambda error: errors.append({'browser': name, 'error': str(error)}))
                    page.goto(base)
                    page.wait_for_function('()=>window.galleryQA?.ready')
                    page.get_by_role('button', name='Browse at my pace', exact=True).tap()
                    page.wait_for_function("()=>galleryQA.state().active.some(a=>a.text==='Approved first image detail.')&&document.querySelectorAll('.slide-stack>.slide').length===1")
                    original_voice = page.evaluate(MEASURE)['voice']
                    sizes = [('portrait', 390, 844), ('landscape', 844, 390), ('small-phone', 375, 667),
                             ('narrow-phone', 320, 568), ('keyboard', 390, 844), ('keyboard-closed', 390, 844),
                             ('desktop', 1440, 960)]
                    for label, width, height in sizes:
                        page.set_viewport_size({'width': width, 'height': height})
                        if label == 'keyboard':
                            page.locator('.pl-reply input').tap()
                            page.evaluate("Object.defineProperty(visualViewport,'height',{configurable:true,get:()=>430});visualViewport.dispatchEvent(new Event('resize'));")
                        elif label == 'keyboard-closed':
                            page.evaluate("delete visualViewport.height;document.activeElement?.blur();visualViewport.dispatchEvent(new Event('resize'));")
                        # Container queries and ResizeObserver need several frames
                        # after rotation. Wait on stable geometry, not an arbitrary sleep.
                        page.evaluate('''async()=>{
                          let previous='',stable=0;
                          for(let i=0;i<60;i++){
                            await new Promise(r=>requestAnimationFrame(r));
                            const current=JSON.stringify([...document.querySelectorAll('.pl,.slide.on,.gallery-surface,.pl-dock')].map(e=>e.getBoundingClientRect().toJSON()));
                            stable=current===previous?stable+1:0;previous=current;
                            if(stable>=5)return;
                          }
                          throw new Error('Mobile player geometry did not settle');
                        }''')
                        state = page.evaluate(MEASURE)
                        measurements.append({'browser': name, 'case': label, **state})
                        prefix = name + ' ' + label
                        check(prefix + ' retains a nonzero gallery inside its slide', state['surface']['h'] > 40 and
                              state['surface']['y'] >= state['slide']['y'] and state['surface']['bottom'] <= state['slide']['bottom'] + 1,
                              {'height': state['surface']['h'], 'footer': state['footerDisplay']})
                        check(prefix + ' paints the exact reviewed photo', state['pictureLoaded'] and state['pictureVisible'])
                        check(prefix + ' keeps its complete reviewed tag visible', state['captionVisible'])
                        check(prefix + ' keeps navigation and reply controls reachable', all(item['reachable'] for item in state['controls']))
                        check(prefix + ' preserves narration ownership and page bounds', state['voice'] == original_voice and state['noPageOverflow'] and
                              state['viewport']['width'] == width and state['viewport']['scale'] == 1 and state['microphoneAttempts'] == 0)
                        tapped = True
                        try:
                            page.locator('.slide.on .gallery-tag[data-id="front-tag"]').tap(timeout=1500)
                        except Exception:
                            tapped = False
                        after = page.evaluate(MEASURE)
                        check(prefix + ' tag tap retains photo voice and outer controls', tapped and after['pictureLoaded'] and
                              after['voice'] == original_voice and after['shell'] == state['shell'])
                        page.screenshot(path=str(args.output / (name + '-' + label + '.png')), animations='disabled')
                        if label in ('portrait', 'landscape'):
                            page.get_by_role('button', name='Conversation', exact=True).tap()
                            page.wait_for_function("()=>document.querySelector('.pl-drawer.open').getAnimations().length===0")
                            drawer = page.locator('.pl-drawer').evaluate('''e=>{
                              const r=e.getBoundingClientRect(),p=e.parentElement.getBoundingClientRect();
                              return {bounded:r.left>=p.left-1&&r.right<=p.right+1&&r.top>=p.top-1&&r.bottom<=p.bottom+1,
                                reachable:[...e.querySelectorAll('.head button,.composer input,.composer button')].every(c=>{
                                  const b=c.getBoundingClientRect(),hit=document.elementFromPoint(b.x+b.width/2,b.y+b.height/2);
                                  return b.left>=r.left&&b.right<=r.right+1&&b.top>=r.top&&b.bottom<=r.bottom+1&&(hit===c||c.contains(hit));
                                })};
                            }''')
                            check(prefix + ' opens a bounded reachable conversation drawer', drawer['bounded'] and drawer['reachable'])
                            page.get_by_role('button', name='Close conversation', exact=True).tap()
                            page.wait_for_function("()=>document.querySelector('.pl-drawer').getAnimations().length===0")
                            closed = page.evaluate(MEASURE)
                            check(prefix + ' closes the drawer without overflow or voice restart', closed['noPageOverflow'] and
                                  closed['viewport']['width'] == width and closed['viewport']['scale'] == 1 and closed['voice'] == original_voice)
                    page.evaluate('galleryQA.destroy()')
                    context.close()
                finally:
                    browser.close()
            check('no browser exceptions', not errors)
            check('no external requests or provider calls', not blocked)
    finally:
        server.shutdown()
        server.server_close()
        report = {'passed': sum(row['passed'] for row in checks), 'total': len(checks), 'checks': checks,
                  'measurements': measurements, 'errors': errors, 'blocked': blocked, 'provider_calls': 0,
                  'physical_microphone': False, 'physical_iphone_keyboard': False, 'revision': args.revision}
        (args.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Mobile gallery: ' + str(report['passed']) + '/' + str(report['total']))
    return 0 if report['passed'] == report['total'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
