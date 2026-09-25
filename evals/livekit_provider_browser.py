"""Opt-in, bounded provider QA through the stock LiveKit player route.

Requires an explicitly authorized live trial and a locally generated speech WAV.
It never opens a physical microphone. Only two semantic questions are permitted;
the existing provider chain and voice implementation remain untouched.
"""
from pathlib import Path
import argparse
import base64
import json
import os
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CAPTURE = r"""(() => {
  const NativePC=RTCPeerConnection;window.trialPeerConnections=[];
  window.RTCPeerConnection=class extends NativePC{constructor(...args){super(...args);trialPeerConnections.push(this);}};
  window.trialCapture={calls:0,contexts:[],tracks:[]};
  navigator.mediaDevices.getUserMedia=async()=>{
    trialCapture.calls++;
    const context=new AudioContext(),destination=context.createMediaStreamDestination();
    trialCapture.context=context;trialCapture.destination=destination;
    trialCapture.contexts.push(context);trialCapture.tracks.push(...destination.stream.getTracks());
    await context.resume();return destination.stream;
  };
  window.playQuestion=async encoded=>{
    const raw=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));
    const source=trialCapture.context.createBufferSource();
    source.buffer=await trialCapture.context.decodeAudioData(raw.buffer);
    source.connect(trialCapture.destination);source.start();
    return source.buffer.duration;
  };
})();"""

HOOKS = r"""async()=>{
  const {LiveKitVoiceClient}=await import('/web/player/livekit-voice.js');
  const q=window.providerQA={limit:2,asked:[],answers:[],saved:[],played:[],completed:[],transcripts:[],pcm:{},events:[],errors:[],states:[]};
  const connect=LiveKitVoiceClient.prototype.connect;
  LiveKitVoiceClient.prototype.connect=function(){
    q.client=this;
    if(!this.qaObserved){this.qaObserved=true;const onError=this.onError,onState=this.onState;
      this.onError=error=>{q.errors.push(error);onError(error)};this.onState=state=>{q.states.push(state);onState(state)};
    }
    return connect.call(this);
  };
  const ask=LiveKitVoiceClient.prototype.ask,speak=LiveKitVoiceClient.prototype.speak,receive=LiveKitVoiceClient.prototype.receive;
  LiveKitVoiceClient.prototype.ask=async function(body){
    if(q.asked.length>=q.limit)throw Error('Bounded QA question limit reached');
    q.client=this;q.asked.push({question:body.question,input_mode:body.input_mode});
    const answer=await ask.call(this,body);q.answers.push(answer);return answer;
  };
  LiveKitVoiceClient.prototype.speak=function(text,options={}){
    const result=speak.call(this,text,{...options,onStart:ts=>{q.played.push(text);options.onStart?.(ts);}});
    result.then(ok=>q.completed.push({text,ok}),e=>q.errors.push(e.message));return result;
  };
  LiveKitVoiceClient.prototype.receive=function(data){
    q.client=this;q.events.push(data.type);
    if(data.type==='transcript.final')q.transcripts.push(data.text);
    if(data.type==='error')q.errors.push(data.message||data.code);
    if(data.type==='audio.chunk'){
      const p=q.pcm[data.utterance_id] ||= {samples:0,energy:0,peak:0,rate:data.sample_rate||24000};
      const bytes=atob(data.audio);
      for(let i=0;i<bytes.length;i+=2){let n=bytes.charCodeAt(i)|(bytes.charCodeAt(i+1)<<8);if(n>=32768)n-=65536;p.samples++;p.energy+=n*n;p.peak=Math.max(p.peak,Math.abs(n));}
    }
    return receive.call(this,data);
  };
  const nativeFetch=window.fetch;
  window.fetch=async function(input,init){
    const url=typeof input==='string'?input:input.url;
    if(url?.endsWith('/run/session')&&init?.body)q.saved.push(JSON.parse(init.body));
    return nativeFetch.apply(this,arguments);
  };
}"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8920")
    parser.add_argument("--signal-port", type=int, default=7880)
    parser.add_argument("--demo", default="dm_29df0418")
    parser.add_argument("--state-demo", type=Path, required=True)
    parser.add_argument("--speech-wav", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-live-runtime", action="store_true")
    parser.add_argument("--typed-only", action="store_true", help="Spend only the one remaining typed question after a preserved voice receipt")
    args = parser.parse_args()
    if not args.allow_live_runtime:
        raise ValueError("Explicit per-run live-runtime authorization is required")
    base = args.base.rstrip("/")
    address = urlsplit(base)
    if address.hostname not in ("127.0.0.1", "localhost") or address.port == 8896 or args.demo == "dm_41513908":
        raise ValueError("Use an isolated unprotected local trial")
    if not str(args.state_demo.resolve()).startswith("/private/tmp/") and not str(args.state_demo.resolve()).startswith("/tmp/"):
        raise ValueError("The QA publication must be an isolated temporary copy")
    with urllib.request.urlopen(base + "/api/health", timeout=5) as response:
        health = json.load(response)
    assert not health["mock"] and health["storage"] == "local" and not health["cloud"]["enabled"]
    assert health["stt_provider"] == "sarvam" and health["tts_provider"] == "sarvam"
    args.output.mkdir(parents=True, exist_ok=True)
    usage_path = args.state_demo / "usage.jsonl"
    before = usage_path.read_text().splitlines() if usage_path.exists() else []
    checks, errors, blocked = [], [], []
    started = time.time()
    expected_answers = 1 if args.typed_only else 2

    def check(name, condition):
        assert condition, name
        checks.append(name)
        print("PASS", name, flush=True)

    with tempfile.TemporaryDirectory(prefix="livekit-provider-import-") as temporary:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=temporary + "/data", DEMO_STUDIO_GRAPH_DB=temporary + "/graph.sqlite")
        from server.crawl import _render_executable
        from server.usage import _cost_usd, FX_INR
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, executable_path=_render_executable(pw.chromium), args=["--mute-audio", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost"])
            context = browser.new_context(viewport={"width":1440,"height":960}, service_workers="block",permissions=["microphone"])
            context.add_init_script(CAPTURE)

            def route(request):
                parsed = urlsplit(request.request.url)
                if parsed.netloc in (address.netloc, f"127.0.0.1:{args.signal_port}"):
                    # Browse avoids model-generated intake; refuse accidental
                    # paid build/pitch endpoints even if the fixture changes.
                    if parsed.path.endswith(("/run/pitch", "/read", "/build")):
                        blocked.append(parsed.path)
                        return request.abort()
                    return request.continue_()
                if parsed.scheme in ("data", "blob"):
                    return request.continue_()
                if parsed.hostname == "fonts.googleapis.com":
                    return request.fulfill(status=200, content_type="text/css", body="/* installed fallback fonts */")
                blocked.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
                request.abort()

            def socket_route(socket):
                parsed = urlsplit(socket.url)
                if parsed.hostname in ("127.0.0.1", "localhost") and parsed.port == args.signal_port:
                    socket.connect_to_server()
                else:
                    blocked.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
                    socket.close()

            context.route("**/*", route)
            context.route_web_socket("**/*", socket_route)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            status = "failed"
            try:
                page.goto(base + f"/?voice_transport=livekit#/play/{args.demo}")
                page.get_by_role("button", name="Browse at my pace", exact=True).wait_for()
                page.evaluate(HOOKS)
                page.evaluate("limit=>providerQA.limit=limit", expected_answers)
                page.get_by_role("switch", name="Voice mode", exact=True).set_checked(not args.typed_only)
                page.get_by_role("button", name="Browse at my pace", exact=True).click()
                if args.typed_only:
                    page.wait_for_function("()=>providerQA.client?.ready", timeout=20000)
                    check("stock app establishes text connection over LiveKit", page.evaluate("providerQA.client.transport==='livekit-trial' && providerQA.client.ready && trialCapture.calls===0"))
                else:
                    page.wait_for_function("()=>providerQA.client?.micReady", timeout=20000)
                    check("stock app establishes live Sarvam capture over LiveKit", page.evaluate("providerQA.client.transport==='livekit-trial' && providerQA.client.ready && trialCapture.calls===1"))
                    page.wait_for_timeout(600)
                    duration = page.evaluate("playQuestion", base64.b64encode(args.speech_wav.read_bytes()).decode())
                    check("local synthetic speech is delivered as a real media track", duration > 2)
                    page.wait_for_function("()=>providerQA.asked.length===1", timeout=25000)
                    check("real STT final reaches the ordinary question handler", page.evaluate("providerQA.transcripts.some(t=>/seats/i.test(t)) && providerQA.asked[0].input_mode==='voice'"))
                    page.get_by_role("switch", name="Conversation voice mode", exact=True).click()
                    page.wait_for_function("()=>!providerQA.client.mic", timeout=5000)
                    check("microphone can close while the answer remains connected", page.evaluate("providerQA.client.ready && trialCapture.tracks.every(t=>t.readyState==='ended')"))
                    page.wait_for_function("()=>providerQA.answers.length===1 && providerQA.completed.some(p=>p.ok&&p.text===providerQA.answers[0].answer)", timeout=45000)
                    check("spoken question receives a validated answer or honest decline", page.evaluate("()=>{const a=providerQA.answers[0];return !a.from_bank&&((a.answered&&a.fact_ids?.length)||(!a.answered&&!a.fact_ids?.length&&/couldn.t verify|don.t have|can.t verify|not.*confirm/i.test(a.answer)))}"))
                    check("spoken answer has non-silent streamed speech", page.evaluate("()=>{const a=providerQA.answers[0],p=providerQA.pcm[a.runtime_utterance_id];return p&&p.samples/p.rate>1&&p.peak>1000&&Math.sqrt(p.energy/p.samples)>50}"))
                    page.screenshot(path=str(args.output / "spoken-answer.png"), full_page=False)
                question = "tell me more about interior of the car"
                page.get_by_role("textbox", name="Your question or answer", exact=True).fill(question)
                page.get_by_role("textbox", name="Your question or answer", exact=True).press("Enter")
                page.wait_for_function("n=>providerQA.answers.length===n && providerQA.completed.some(p=>p.ok&&p.text===providerQA.answers.at(-1).answer)", arg=expected_answers, timeout=45000)
                check("typed interior question receives a grounded real answer", page.evaluate("q=>{const a=providerQA.answers.at(-1);return providerQA.asked.at(-1).question===q&&providerQA.asked.at(-1).input_mode==='text'&&a.answered&&a.fact_ids?.length&&!a.from_bank&&a.answer.split(/\\s+/).length>12}", question))
                check("typed answer also has non-silent streamed speech", page.evaluate("()=>{const a=providerQA.answers.at(-1),p=providerQA.pcm[a.runtime_utterance_id];return p&&p.samples/p.rate>1&&p.peak>1000&&Math.sqrt(p.energy/p.samples)>50}"))
                page.screenshot(path=str(args.output / "typed-answer.png"), full_page=False)
                page.locator('.pl-top button[aria-label="Stop and see the summary"]').click()
                page.wait_for_function("()=>providerQA.saved.some(s=>s.ended)", timeout=10000)
                page.wait_for_function("""async demo=>{
                  const ended=providerQA.saved.find(s=>s.ended);if(!ended)return false;
                  const response=await fetch(`/api/demos/${demo}/sessions/${ended.id}`);if(!response.ok)return false;
                  providerQA.persisted=await response.json();return providerQA.persisted.ended;
                }""", arg=args.demo, timeout=10000)
                check("actual results persist in the completed visit", page.evaluate("n=>providerQA.persisted.turns.filter(t=>!t.failed).length===n && providerQA.answers.every(a=>providerQA.persisted.transcript.some(t=>t.role==='agent'&&t.text===a.answer)) && providerQA.persisted.save_seq>1", expected_answers))
                check("only the authorized questions were submitted", page.evaluate("n=>providerQA.asked.length===n", expected_answers))
                check("no browser error or unexpected external request", not errors and not blocked)
                status = "passed"
            finally:
                # No full session, token or provider trace is exported. These
                # are the two synthetic QA inputs and their reviewable answers.
                snapshot = page.evaluate("""()=>{const q=window.providerQA;if(!q)return {};return {asked:q.asked,transcripts:q.transcripts,answers:q.answers.map(a=>({answer:a.answer,answered:a.answered,fact_ids:a.fact_ids,from_bank:a.from_bank,visual:!!a.visual})),audio:q.answers.map(a=>{const p=q.pcm[a.runtime_utterance_id];return p?{seconds:p.samples/p.rate,rms:Math.sqrt(p.energy/p.samples),peak:p.peak}:null}),played:q.played,completed:q.completed,errors:q.errors,events:q.events,states:q.states,capture:trialCapture.calls,ready:q.client?.ready,socket:q.client?.socket?.readyState,room:q.client?.socket?.room?.state,workerReady:q.client?.socket?.workerReady,peers:trialPeerConnections.map(p=>({connection:p.connectionState,ice:p.iceConnectionState,signal:p.signalingState}))};}""")
                if status != "passed":
                    page.screenshot(path=str(args.output / "failure.png"), full_page=False)
                page.evaluate("()=>{window.providerQA?.client?.close();window.trialCapture?.contexts.forEach(c=>c.close())}")
                browser.close()
                time.sleep(1)
                after = usage_path.read_text().splitlines() if usage_path.exists() else []
                rows = [json.loads(line) for line in after[len(before):]]
                costs = sum(_cost_usd(row) for row in rows)
                report = {"status":status,"passed":len(checks),"checks":checks,"seconds":round(time.time()-started,1),"providers":"configured live runtime, unchanged order","physical_microphone":False,"input_speech":"locally synthesized macOS voice","browser_playback":"muted; nonzero decoded PCM verified, no room-acoustic claim","question_limit":expected_answers,"observations":snapshot,"browser_errors":errors,"blocked":blocked,"usage":rows,"estimated_usd":round(costs,6),"estimated_inr":round(costs*FX_INR,4),"price_basis":"existing app estimates, not a provider invoice"}
                (args.output / "results.json").write_text(json.dumps(report,indent=2)+"\n")
                print(json.dumps({k:report[k] for k in ("status","passed","seconds","estimated_usd","estimated_inr")}),flush=True)


if __name__ == "__main__":
    main()
