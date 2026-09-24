"""Isolated, muted Chromium checks against an already built MOCK_LLM fixture.

Does not attach to a running browser/profile. The capture stream is synthetic
silence and transcript events are injected through the real browser WS listener;
this tests ownership and lifecycle, not acoustic STT/echo quality.
"""
import argparse
import json
import mimetypes
from urllib.parse import urlsplit
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True, help="Local, isolated MOCK_LLM player URL including ?mute=1")
parser.add_argument("--walkthrough-record", action="store_true", help="Record WP12 with the exact isolated bundle and synthetic speech events")
parser.add_argument("--output", type=Path, help="New isolated evidence folder")
args = parser.parse_args()
if args.walkthrough_record:
    from wp12_browser_acceptance import walkthrough_record
    walkthrough_record(args.url, args.output or Path("/tmp/demo-wp12-20260924/walkthrough-recording"))
    raise SystemExit(0)
assert args.url.startswith("http://127.0.0.1:8897/") and "mute=1" in args.url, "Use the dedicated muted mock server"
output = args.output or Path("output/playwright/creta-runtime")
output.mkdir(parents=True, exist_ok=True)
results = []


def check(name, ok):
    results.append({"name": name, "passed": bool(ok)})
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    if not ok and 'page' in globals():
        (output / 'failure.json').write_text(json.dumps({'name': name, 'wire': page.evaluate('__wire'), 'status': page.locator('.pl-status').inner_text(), 'text': page.locator('.pl-thread, .pl-drawer .body').inner_text()}, indent=2))
        page.screenshot(path=str(output/'failure.png'))
    assert ok, name


instrument = """(() => {
window.__wire=[]; window.__captures=0; window.__tracks=[]; window.__audios=[];
const WS=window.WebSocket;
window.WebSocket=class extends WS {
 constructor(...args){super(...args); window.__liveSocket=this; this.addEventListener('message',e=>{try{window.__wire.push({direction:'in',...JSON.parse(e.data)});}catch{}});}
 send(raw){try{const e=JSON.parse(raw);if(e.type==='turn.ask'){e.skip_bank=true;raw=JSON.stringify(e);}window.__wire.push({direction:'out',type:e.type,turn_id:e.turn_id,utterance_id:e.utterance_id,input_generation:e.input_generation,enabled:e.enabled});}catch{} return super.send(raw);}
};
const Audio=window.Audio;window.Audio=function(...args){const a=new Audio(...args);a.playbackRate=8;window.__audios.push(a);return a;};window.Audio.prototype=Audio.prototype;
navigator.mediaDevices.getUserMedia=async()=>{
 window.__captures++;
 const ctx=new AudioContext(),source=ctx.createConstantSource(),gain=ctx.createGain(),sink=ctx.createMediaStreamDestination();
 gain.gain.value=0;source.connect(gain);gain.connect(sink);source.start();await ctx.resume();
 for(const track of sink.stream.getTracks()){window.__tracks.push(track);const stop=track.stop.bind(track);track.stop=()=>{stop();source.stop();ctx.close();};}
 return sink.stream;
};
window.__stt=(event)=>window.__liveSocket.dispatchEvent(new MessageEvent('message',{data:JSON.stringify({input_generation:window.__wire.filter(e=>e.direction==='out'&&e.type==='mic.set'&&e.enabled).at(-1)?.input_generation,...event})}));
})();"""

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless=True,
                                args=["--mute-audio", "--autoplay-policy=no-user-gesture-required"])
    context = browser.new_context(viewport={"width": 1440, "height": 1000})
    context.add_init_script(instrument)
    # Serve the tested checkout's frontend even when the isolated fixture server
    # intentionally runs the preserved baseline backend.
    frontend = Path(__file__).resolve().parents[1] / 'web'
    def local_resources(route):
        url = route.request.url
        if not url.startswith(("http://127.0.0.1:", "data:", "blob:")):
            route.abort(); return
        path = urlsplit(url).path
        if path.startswith('/web/'):
            file = (frontend / path.removeprefix('/web/')).resolve()
            if file.is_relative_to(frontend) and file.is_file():
                route.fulfill(body=file.read_bytes(), content_type=mimetypes.guess_type(file.name)[0] or 'text/plain'); return
        route.continue_()
    context.route("**/*", local_resources)
    farewell_faults = []
    def fail_farewell_socket(route):
        server = route.connect_to_server()
        def outbound(raw):
            event = json.loads(raw)
            if event.get('type') == 'delivery.speak' and event.get('text', '').startswith("Fair enough. Here's a summary"):
                farewell_faults.append(event['utterance_id'])
                route.close(code=1011, reason='Free closing transport failure regression')
                return
            server.send(raw)
        route.on_message(outbound)
    context.route_web_socket('**/run/live*', fail_farewell_socket)
    page = context.new_page()
    saved_sessions = []
    page.on("request", lambda request: saved_sessions.append(request.post_data_json) if request.method == "POST" and request.url.endswith("/run/session") else None)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(args.url)
    page.get_by_role("button", name="Explore with me", exact=True).click()
    answer = page.get_by_role("textbox", name="Your answer", exact=True)
    expect(answer).to_be_visible()
    check("muted Explore opens transport without microphone", page.evaluate("__captures===0"))
    answer.fill("I want a family car with useful boot space and clear ownership costs.")
    answer.press("Enter")
    page.wait_for_function("!document.querySelector('.pl-intake.open:not(.pl-welcome)') && __audios.some(a=>!a.paused&&!a.ended)", timeout=20000)
    check("Explore begins continuous narration after accepted intake", "quick overview" in page.locator(".pl-thread, .pl-drawer .body").inner_text() or page.locator(".pl-status").inner_text() == "Speaking")
    page.screenshot(path=str(output / "explore-playing.png"))
    question = page.get_by_role("textbox", name="Your question or answer", exact=True)
    question.fill("What is the warranty? Do not search online."); question.press("Enter")
    expect(page.get_by_role("button", name="Continue demo", exact=True)).to_be_visible(timeout=20000)
    check("live QA uses WS graph and deferred answer delivery", page.evaluate("__wire.some(e=>e.type==='turn.ask') && __wire.some(e=>e.type==='turn.result') && __wire.some(e=>e.type==='delivery.request')"))
    check("explicit mock decline preserves the unanswered question and opens follow-up", page.evaluate("__wire.some(e=>e.type==='turn.result'&&e.answer?.answered===false)") and page.locator('.pl-lead.open').count()==1)
    check("completed QA opens its current three-second turn window", page.locator(".pl-status").inner_text() == "Your turn")
    if page.locator('.pl-lead.open .lead-close').count():page.locator('.pl-lead.open .lead-close').click()
    page.wait_for_function("!Array.from(document.querySelectorAll('.pl-chips button')).some(b=>b.textContent==='Continue demo')",timeout=6000)
    check("QA automatically resumes continuous narration after its owned window", not page.get_by_role('button',name='Continue demo',exact=True).count())
    asks = page.evaluate("__wire.filter(e=>e.type==='turn.ask').length")
    question.fill("Actually, boot space matters more."); question.press("Enter")
    expect(page.get_by_role("button", name="Continue demo", exact=True)).to_be_visible(timeout=15000)
    check("explicit correction does not become a factual QA request", page.evaluate("__wire.filter(e=>e.type==='turn.ask').length") == asks)
    page.get_by_role("button", name="Stop and see the summary", exact=True).click()
    expect(page.get_by_role("heading", name="Your recap", exact=True)).to_be_visible()
    check("recap retains explicit customer correction and unresolved question", "boot space matters more" in page.locator(".pl-handoff").inner_text() and "What is the warranty?" in page.locator(".pl-handoff").inner_text())
    needs = page.locator('.pl-handoff .kvbox').filter(has=page.get_by_role('heading', name='What matters to you', exact=True)).inner_text()
    check("recap needs include intake and explicit refinement, not raw QA history", "family car" in needs and "Actually, boot space matters more." in needs and "What is the warranty?" not in needs)
    page.screenshot(path=str(output / "typed-recap.png"))

    # Same real player and worklet, synthetic microphone and STT events. No physical device.
    page.get_by_role("button", name="Restart", exact=True).click()
    expect(answer).to_be_visible()
    page.locator(".pl-intake.open .mic").click()
    expect(page.locator(".pl-intake.open .mic")).to_have_attribute("aria-label", "Turn voice mode off")
    page.wait_for_function("__wire.some(e=>e.type==='audio.input')")
    check("one synthetic capture sends real worklet PCM after mic.ready", page.evaluate("__captures===1 && __wire.some(e=>e.type==='mic.ready')"))
    page.locator(".pl-intake.open .mic").click()
    expect(page.locator(".pl-intake.open .mic")).to_have_attribute("aria-label", "Turn voice mode on")
    page.locator(".pl-intake.open .mic").click()
    page.wait_for_function("__wire.some(e=>e.type==='audio.input'&&e.input_generation===2)")
    before_stale = page.locator(".pl-thread, .pl-drawer .body").inner_text()
    page.evaluate("__stt({type:'input.speech_start',input_generation:1,input_id:'old'}); __stt({type:'transcript.final',input_generation:1,input_id:'old',text:'An obsolete answer from the muted capture'}); __stt({type:'error',input_generation:1,code:'microphone_stream',message:'Old failure'})")
    check("muting and reopening rejects delayed old capture events", page.locator(".pl-thread, .pl-drawer .body").inner_text() == before_stale and answer.is_visible())
    check("old capture is stopped and new capture remains live", page.evaluate("__captures===2 && __tracks[0].readyState==='ended' && __tracks[1].readyState==='live'"))
    page.evaluate("__stt({type:'input.speech_start',input_id:'voice-1'}); __stt({type:'transcript.final',input_id:'voice-1',text:'Boot space matters to me.'})")
    page.wait_for_function("!document.querySelector('.pl-intake.open:not(.pl-welcome)') && __audios.some(a=>!a.paused&&!a.ended)", timeout=20000)
    check("voice intake retains one active capture through continuous narration", page.evaluate("__captures===2 && __tracks[1].readyState==='live'"))
    page.evaluate("__stt({type:'input.speech_start',input_id:'voice-2'})")
    check("raw speech onset alone does not interrupt narration", page.evaluate("__audios.some(a=>!a.paused&&!a.ended)"))
    page.evaluate("__stt({type:'transcript.partial',input_id:'voice-2',text:'What is the warranty'})")
    check("meaningful transcript onset immediately pauses actual HTML audio", page.evaluate("__audios.every(a=>a.paused || a.ended)"))
    before = page.evaluate("__wire.filter(e=>e.type==='turn.ask').length")
    page.evaluate("__stt({type:'transcript.partial',input_id:'voice-2',text:'What is'}); __stt({type:'transcript.final',input_id:'voice-2',text:'What is the warranty? Do not search online.'}); __stt({type:'transcript.final',input_id:'voice-2',text:'What is the warranty? Do not search online.'})")
    expect(page.get_by_role("button", name="Continue demo", exact=True)).to_be_visible()
    check("duplicate final creates exactly one question", page.evaluate("__wire.filter(e=>e.type==='turn.ask').length") == before + 1)
    check("answer and interruption leave the same capture running", page.evaluate("__captures===2 && __tracks[1].readyState==='live'"))
    # Current tours are continuous; there are no proof-stop choice buttons.
    # Eight-times playback is a muted fixture acceleration, not a duration claim.
    if page.locator('.pl-lead.open .lead-close').count():page.locator('.pl-lead.open .lead-close').click()
    page.get_by_role('button',name='Continue demo',exact=True).click()
    expect(page.get_by_role('button',name='Not yet',exact=True)).to_be_visible(timeout=60000)
    check("continuous route reaches the natural closing CTA with capture active", page.evaluate("__tracks[1].readyState==='live'") and bool(page.locator('.pl-ctas button,.pl-chips button').count()))
    page.get_by_role('button',name='Not yet',exact=True).click()
    expect(page.get_by_role("heading", name="Your recap", exact=True)).to_be_visible(timeout=12000)
    check("ending visit releases microphone tracks", page.evaluate("__tracks.every(t=>t.readyState==='ended')"))
    check("natural recap never claims to be listening after capture ends", page.locator('.pl-status').inner_text() == 'Demo complete')
    check("explicit Not yet still reaches a readable recap when farewell transport fails", len(farewell_faults) == 1 and "The selected voice is unavailable" in page.locator('.pl-thread, .pl-drawer .body').inner_text())
    check("failed farewell never records successful audio delivery", not page.evaluate("id=>__wire.some(e=>e.type==='delivery.start'&&e.utterance_id===id)", farewell_faults[0]))
    page.wait_for_timeout(250)
    check("both completed visits are posted to session storage", len({record.get('id') for record in saved_sessions if record.get('ended')}) >= 2)
    check("voice visit preserves actual per-turn voice provenance after capture closes", any(record.get('ended') and any(turn.get('input_source') == 'realtime' for turn in record.get('turns', [])) for record in saved_sessions))
    check("all audio remains muted", page.evaluate("__audios.every(a=>a.paused || a.muted)"))
    check("no browser runtime exception", not errors)
    page.screenshot(path=str(output / "voice-lifecycle-recap.png"))
    (output / "results.json").write_text(json.dumps({"results": results, "errors": errors, "saved_visits": [{"id": row.get("id"), "ended": row.get("ended"), "input_mode": row.get("input_mode"), "turn_count": len(row.get("turns", []))} for row in saved_sessions], "boundary": "Headless isolated Chrome; real app/WS/worklet and mock backend; explicit declined-question provider fixture, skip_bank request control, synthetic capture/transcripts and 8x muted audio acceleration; no acoustic quality or natural duration assertion."}, indent=2))
    context.close(); browser.close()
print(f"Live browser: {len(results)}/{len(results)} passed")
