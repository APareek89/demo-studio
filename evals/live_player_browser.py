"""Isolated, muted Chromium checks against an already built MOCK_LLM fixture.

Does not attach to a running browser/profile. The capture stream is synthetic
silence and transcript events are injected through the real browser WS listener;
this tests ownership and lifecycle, not acoustic STT/echo quality.
"""
import argparse
import json
from pathlib import Path

from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument("--url", required=True, help="Local, isolated MOCK_LLM player URL including ?mute=1")
args = parser.parse_args()
assert args.url.startswith("http://127.0.0.1:8897/") and "mute=1" in args.url, "Use the dedicated muted mock server"
output = Path("output/playwright/creta-runtime")
output.mkdir(parents=True, exist_ok=True)
results = []


def check(name, ok):
    results.append({"name": name, "passed": bool(ok)})
    print(("PASS " if ok else "FAIL ") + name, flush=True)
    assert ok, name


instrument = """(() => {
window.__wire=[]; window.__captures=0; window.__tracks=[]; window.__audios=[];
const WS=window.WebSocket;
window.WebSocket=class extends WS {
 constructor(...args){super(...args); window.__liveSocket=this; this.addEventListener('message',e=>{try{window.__wire.push({direction:'in',...JSON.parse(e.data)});}catch{}});}
 send(raw){try{const e=JSON.parse(raw);window.__wire.push({direction:'out',type:e.type,turn_id:e.turn_id,utterance_id:e.utterance_id,input_generation:e.input_generation,enabled:e.enabled});}catch{} return super.send(raw);}
};
const Audio=window.Audio;window.Audio=function(...args){const a=new Audio(...args);window.__audios.push(a);return a;};window.Audio.prototype=Audio.prototype;
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
    context.route("**/*", lambda route: route.continue_() if route.request.url.startswith(("http://127.0.0.1:", "data:", "blob:")) else route.abort())
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(args.url)
    page.get_by_role("button", name="Explore with me", exact=True).click()
    answer = page.get_by_role("textbox", name="Your answer", exact=True)
    expect(answer).to_be_visible()
    check("muted Explore opens transport without microphone", page.evaluate("__captures===0"))
    answer.fill("I want a family car with useful boot space and clear ownership costs.")
    answer.press("Enter")
    expect(page.get_by_role("button", name="That settles it", exact=True)).to_be_visible(timeout=15000)
    check("Explore reaches its first owned wait", "quick overview" in page.locator(".pl-thread, .pl-drawer .body").inner_text())
    page.screenshot(path=str(output / "explore-wait.png"))
    question = page.get_by_role("textbox", name="Your question or answer", exact=True)
    question.fill("What is the warranty?"); question.press("Enter")
    expect(page.get_by_role("button", name="Continue demo", exact=True)).to_be_visible()
    check("live QA uses WS graph and deferred answer delivery", page.evaluate("__wire.some(e=>e.type==='turn.ask') && __wire.some(e=>e.type==='turn.result') && __wire.some(e=>e.type==='delivery.request')"))
    check("a completed answer waits rather than auto-resuming", page.locator(".pl-status").inner_text() == "Your turn")
    page.locator(".lead-close").click()
    page.get_by_role("button", name="Continue demo", exact=True).click()
    expect(page.get_by_role("button", name="That settles it", exact=True)).to_be_visible()
    check("QA returns forward from the completed proof check-in", page.locator(".pl-progress .pp").nth(1).get_attribute("class").find("active") >= 0)
    asks = page.evaluate("__wire.filter(e=>e.type==='turn.ask').length")
    question.fill("Actually, boot space matters more."); question.press("Enter")
    expect(page.get_by_role("button", name="Continue demo", exact=True)).to_be_visible()
    check("explicit correction does not become a factual QA request", page.evaluate("__wire.filter(e=>e.type==='turn.ask').length") == asks)
    page.get_by_role("button", name="Continue demo", exact=True).click()
    expect(page.get_by_role("button", name="That settles it", exact=True)).to_be_visible()
    page.get_by_role("button", name="Stop and see the summary", exact=True).click()
    expect(page.get_by_role("heading", name="Your recap", exact=True)).to_be_visible()
    check("recap keeps explicit customer wording and unresolved question", "boot space matters more" in page.locator(".pl-handoff").inner_text() and "What is the warranty?" in page.locator(".pl-handoff").inner_text())
    page.screenshot(path=str(output / "typed-recap.png"))

    # Same real player and worklet, synthetic microphone and STT events. No physical device.
    page.get_by_role("button", name="Restart", exact=True).click()
    expect(answer).to_be_visible()
    page.locator(".pl-intake.open .mic").click()
    expect(page.locator(".pl-intake.open .mic")).to_have_attribute("aria-label", "Mute microphone")
    page.wait_for_function("__wire.some(e=>e.type==='audio.input')")
    check("one synthetic capture sends real worklet PCM after mic.ready", page.evaluate("__captures===1 && __wire.some(e=>e.type==='mic.ready')"))
    page.locator(".pl-intake.open .mic").click()
    expect(page.locator(".pl-intake.open .mic")).to_have_attribute("aria-label", "Enable microphone")
    page.locator(".pl-intake.open .mic").click()
    page.wait_for_function("__wire.some(e=>e.type==='audio.input'&&e.input_generation===2)")
    before_stale = page.locator(".pl-thread, .pl-drawer .body").inner_text()
    page.evaluate("__stt({type:'input.speech_start',input_generation:1,input_id:'old'}); __stt({type:'transcript.final',input_generation:1,input_id:'old',text:'An obsolete answer from the muted capture'}); __stt({type:'error',input_generation:1,code:'microphone_stream',message:'Old failure'})")
    check("muting and reopening rejects delayed old capture events", page.locator(".pl-thread, .pl-drawer .body").inner_text() == before_stale and answer.is_visible())
    check("old capture is stopped and new capture remains live", page.evaluate("__captures===2 && __tracks[0].readyState==='ended' && __tracks[1].readyState==='live'"))
    page.evaluate("__stt({type:'input.speech_start',input_id:'voice-1'}); __stt({type:'transcript.final',input_id:'voice-1',text:'Boot space matters to me.'})")
    expect(page.get_by_role("button", name="That settles it", exact=True)).to_be_visible(timeout=15000)
    check("voice intake retains one active capture through narration", page.evaluate("__captures===2 && __tracks[1].readyState==='live'"))
    page.get_by_role("button", name="That settles it", exact=True).click()
    page.wait_for_function("__audios.some(a=>!a.paused && !a.ended)")
    page.evaluate("__stt({type:'input.speech_start',input_id:'voice-2'})")
    check("speech onset immediately pauses actual HTML audio", page.evaluate("__audios.every(a=>a.paused || a.ended)"))
    before = page.evaluate("__wire.filter(e=>e.type==='turn.ask').length")
    page.evaluate("__stt({type:'transcript.partial',input_id:'voice-2',text:'What is'}); __stt({type:'transcript.final',input_id:'voice-2',text:'What is the warranty?'}); __stt({type:'transcript.final',input_id:'voice-2',text:'What is the warranty?'})")
    expect(page.get_by_role("button", name="Continue demo", exact=True)).to_be_visible()
    check("duplicate final creates exactly one question", page.evaluate("__wire.filter(e=>e.type==='turn.ask').length") == before + 1)
    check("answer and interruption leave the same capture running", page.evaluate("__captures===2 && __tracks[1].readyState==='live'"))
    page.get_by_role("button", name="Stop and see the summary", exact=True).click()
    expect(page.get_by_role("heading", name="Your recap", exact=True)).to_be_visible()
    check("ending visit releases microphone tracks", page.evaluate("__tracks.every(t=>t.readyState==='ended')"))
    check("all audio remains muted", page.evaluate("__audios.every(a=>a.paused || a.muted)"))
    check("no browser runtime exception", not errors)
    page.screenshot(path=str(output / "voice-lifecycle-recap.png"))
    (output / "results.json").write_text(json.dumps({"results": results, "errors": errors, "boundary": "Headless isolated Chrome; real app/WS/worklet, mock backend, synthetic capture/transcripts; no acoustic quality assertion."}, indent=2))
    context.close(); browser.close()
print(f"Live browser: {len(results)}/{len(results)} passed")
