"""Public-search widgets in an isolated browser; no app or provider requests."""
from http.server import ThreadingHTTPServer
import threading
from playwright.sync_api import sync_playwright
import ui_layout_contract as layout

layout.HTML = layout.HTML.replace("window.ready=true;", """
const {renderPublicSearch}=await import('/web/player/public-search-ui.js');
window.searchPanel=result=>{const panel=renderPublicSearch(result);if(panel)document.querySelector('.pl-cap .cite').append(panel);return !!panel;};
window.searchThread=result=>{const panel=renderPublicSearch(result);if(panel)document.querySelector('.pl-drawer .body').append(panel);};
window.ready=true;
""")


class Handler(layout.Handler):
    def send_header(self, name, value):
        if name == 'Content-Security-Policy':
            value += "; frame-src 'self'"
        super().send_header(name, value)


def main():
    results, errors, rejected = [], [], []
    def check(name, ok):
        assert ok, name
        results.append(name)
        print('PASS', name, flush=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f'http://127.0.0.1:{server.server_port}'
    evidence = [
        {'id': 'W1', 'provenance': 'live_web', 'source': {'ref': 'https://example.com/product'}},
        {'id': 'W2', 'provenance': 'live_web', 'source': {'ref': 'https://uncited.example/details'}},
        {'id': 'W3', 'provenance': 'live_web', 'source': {'ref': 'javascript:parent.pwned=1'}},
    ]
    markup = '''<style>body{color:rgb(10,20,30)}body:before{content:"Google Search"}</style>
<div id="suggestion">Product details <a href="https://www.google.com/search?q=product">Search</a></div>
<script>parent.pwned=1</script><img src="https://evil.example/leak" onerror="parent.pwned=2">
<svg onload="parent.pwned=3"></svg><a href="javascript:parent.pwned=4" onclick="parent.pwned=5">Unsafe</a>
<iframe src="https://evil.example/frame"></iframe><meta http-equiv="refresh" content="0;url=https://evil.example/">
<form action="https://evil.example/form"><input name="secret"></form><base href="https://evil.example/">'''
    result = {'answered': True, 'answer': 'A grounded answer.', 'fact_ids': ['W1', 'W3'], 'facts': evidence,
              'tool_results': [{'tool': 'web_search', 'evidence': evidence, 'search_entry_point': markup}]}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless=True, args=['--mute-audio', '--disable-background-networking'])
            context = browser.new_context(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
            def guard(route):
                if route.request.url.startswith(base + '/') and route.request.method == 'GET': route.continue_()
                else: rejected.append(route.request.url); route.abort()
            context.route('**/*', guard)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base + '/?mute=1'); page.wait_for_function('window.ready')
            for width in (1440, 390):
                page.set_viewport_size({'width': width, 'height': 1000}); page.evaluate("show('player')")
                geometry = "Object.fromEntries(['.slide-stack','.slide-pic','.pl-dock'].map(s=>{const r=document.querySelector(s).getBoundingClientRect();return[s,[r.x,r.y,r.width,r.height]]}))"
                before = page.evaluate(geometry)
                page.evaluate('result=>searchPanel(result)', result)
                page.evaluate('settle()')
                check(f'{width}px search panel preserves picture and dock geometry', before == page.evaluate(geometry))
                check(f'{width}px search iframe has bounded height', page.locator('.pl-search-suggestions').evaluate('el=>el.getBoundingClientRect().height===112'))
                check(f'{width}px only cited safe web sources are links', page.locator('.pl-web-sources a').evaluate_all("nodes=>nodes.length===1&&nodes[0].href==='https://example.com/product'"))
                check(f'{width}px citation link has safe new-tab behavior', page.locator('.pl-web-sources a').evaluate("el=>el.target==='_blank'&&el.rel.includes('noopener')&&el.rel.includes('noreferrer')"))
                check(f'{width}px markup stays outside application DOM', page.locator('#suggestion').count() == 0)
                frame_element = page.locator('iframe.pl-search-suggestions')
                check(f'{width}px sandbox grants no script, origin, form or ancestor navigation', frame_element.evaluate("el=>el.sandbox.value==='allow-popups allow-popups-to-escape-sandbox'&&el.title==='Web search suggestions'"))
                frame = frame_element.element_handle().content_frame()
                frame.wait_for_selector('#suggestion')
                check(f'{width}px provider suggestion HTML is visible', frame.locator('#suggestion').inner_text() == 'Product details Search')
                check(f'{width}px frame cannot access ancestor document', frame.evaluate("(()=>{try{return !!parent.document&&false}catch(e){return e.name==='SecurityError'}})()"))
                check(f'{width}px active content and navigation controls removed', frame.locator('script,iframe,meta[http-equiv=refresh],form,base,[onclick],[onerror],[onload]').count() == 0)
                check(f'{width}px frame CSP denies scripts and external resources', frame.locator('meta[http-equiv=Content-Security-Policy]').get_attribute('content') == "default-src 'none'; script-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; form-action 'none'")
                check(f'{width}px no unsafe href or passive external source survives', frame.locator('[href^="javascript:"],[src^="https:"]').count() == 0)
                check(f'{width}px no ancestor script ran', page.evaluate('window.pwned===undefined'))
            page.evaluate('result=>searchThread(result)', result)
            check('sources and suggestions can remain with the question thread', page.locator('.pl-drawer .body .pl-public-search iframe').count() == 1)
            page.evaluate("document.querySelector('.pl-cap .cite').replaceChildren()")
            check('non-search tool results do not create search UI', not page.evaluate('result=>searchPanel(result)', {'tool_results': [{'tool': 'source_lookup', 'evidence': evidence, 'search_entry_point': markup}]}))
            check('failed search results do not create search UI', not page.evaluate('result=>searchPanel(result)', {'tool_results': [{'tool': 'web_search', 'error': 'failed', 'search_entry_point': markup}]}))
            nested = {**result, 'tool_results': [{'tool': 'web_search', 'search_entry_point': {'rendered_content': '<div>Search suggestions</div>'}}]}
            check('nested provider entry-point shape is supported', page.evaluate('result=>searchPanel(result)', nested))
            check('no browser exceptions', not errors)
            check('no external request or mutation attempts', not rejected)
            context.close(); browser.close()
    finally:
        server.shutdown(); server.server_close()
    print(f'Public search UI: {len(results)}/{len(results)} passed; isolated headless browser, zero outbound attempts')


if __name__ == '__main__': main()
