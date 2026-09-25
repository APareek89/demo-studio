"""Muted actual Chromium + local LiveKit, synthetic microphone, mocked providers.

Start scripts/run_livekit_trial.py separately. This harness never opens a physical
microphone, reads a secret/token into Python, or contacts a remote provider.
"""
from pathlib import Path
import argparse
import ipaddress
import json
import os
import sys
import tempfile
import urllib.request
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CAPTURE = r"""(() => {
  const NativePC=RTCPeerConnection;window.trialPeerConnections=[];
  window.RTCPeerConnection=class extends NativePC{constructor(...args){super(...args);trialPeerConnections.push(this);}};
  window.trialCapture = { calls:0, tracks:[], contexts:[] };
  navigator.mediaDevices.getUserMedia = async () => {
    trialCapture.calls++;
    const context = new AudioContext(), oscillator = context.createOscillator();
    const gain = context.createGain(), destination = context.createMediaStreamDestination();
    oscillator.frequency.value = 180; gain.gain.value = 0.002;
    oscillator.connect(gain); gain.connect(destination); oscillator.start(); await context.resume();
    trialCapture.tracks.push(...destination.stream.getAudioTracks());
    trialCapture.contexts.push(context); trialCapture.gain=gain;
    return destination.stream;
  };
  const play=HTMLMediaElement.prototype.play;
  HTMLMediaElement.prototype.play=function(){this.muted=true;this.playbackRate=8;return play.call(this);};
})();"""


def main(*, hosted=False):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8920")
    parser.add_argument("--signal-port", type=int, default=7880)
    parser.add_argument("--signal-url", help="Explicit public WSS origin, allowed only by the hosted mock wrapper.")
    parser.add_argument("--turn-host", help="Explicit hosted TURN hostname allowed for native WebRTC DNS.")
    parser.add_argument("--require-relay", action="store_true", help="Require the selected browser candidate to use TURN relay.")
    parser.add_argument("--rtc-host", default="127.0.0.1", help="Exact validated local host IP configured by the trial launcher.")
    parser.add_argument("--demo", default="dm_29df0418")
    parser.add_argument("--output", type=Path, default=ROOT / "output/playwright/livekit-trial")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    address = urlsplit(base)
    if address.hostname not in ("127.0.0.1", "localhost") or address.port == 8896 or args.demo == "dm_41513908":
        raise ValueError("Use only an isolated, unprotected loopback trial.")
    rtc_address = ipaddress.ip_address(args.rtc_host)
    if rtc_address.is_unspecified or rtc_address.is_multicast or (not hosted and not rtc_address.is_private):
        raise ValueError("Use the exact expected RTC host; local trials require a private/loopback host.")
    signaling = urlsplit(args.signal_url or f"ws://127.0.0.1:{args.signal_port}")
    if (hosted and (signaling.scheme != "wss" or not signaling.hostname)
            or not hosted and args.signal_url
            or signaling.username or signaling.password or signaling.query or signaling.fragment
            or signaling.path not in ("", "/") or signaling.port == 8896):
        raise ValueError("Hosted QA requires one explicit secure signaling origin without credentials.")
    if args.turn_host and (not hosted or urlsplit("turns://" + args.turn_host).hostname != args.turn_host or any(c in args.turn_host for c in "/:@?#")):
        raise ValueError("TURN must be one explicit hosted DNS name without credentials or a path.")
    expected_transport = "livekit" if hosted else "livekit-trial"
    with urllib.request.urlopen(base + "/api/health", timeout=5) as response:
        health = json.load(response)
    assert health["mock"] and health["storage"] == "local" and not health["cloud"]["enabled"], "Refusing a non-mock trial"
    assert not any(health.get(key) for key in ("anthropic", "gemini", "runware", "sarvam", "gcloud_tts"))
    with urllib.request.urlopen(base + "/api/runtime/transport", timeout=5) as response:
        capability = json.load(response)
    assert capability["transport"] == "livekit" and capability["livekit_available"], "LiveKit must be the advertised default"
    assert capability["mode"] == ("hosted" if hosted else "trial")
    args.output.mkdir(parents=True, exist_ok=True)
    checks, failures, blocked, sockets, errors, styling = [], [], [], [], [], []

    def check(name, condition):
        if not condition:
            failures.append(name)
        assert condition, name
        checks.append(name)
        print("PASS", name, flush=True)

    with tempfile.TemporaryDirectory(prefix="livekit-browser-import-") as temporary:
        os.environ.update(MOCK_LLM="1", CLOUD_SYNC="0", STORAGE_BACKEND="local", DEMO_STUDIO_DATA=temporary + "/data", DEMO_STUDIO_GRAPH_DB=temporary + "/graph.sqlite")
        from server.crawl import _render_executable
        with sync_playwright() as pw:
            dns_exclusions = "".join(", EXCLUDE " + host for host in {signaling.hostname, args.turn_host} if host) if hosted else ""
            browser = pw.chromium.launch(headless=True, executable_path=_render_executable(pw.chromium), args=["--mute-audio", "--use-fake-device-for-media-stream", "--autoplay-policy=no-user-gesture-required", "--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1, EXCLUDE localhost" + dns_exclusions])
            context = browser.new_context(viewport={"width": 1440, "height": 960}, reduced_motion="reduce", service_workers="block",permissions=["microphone"])
            context.add_init_script(CAPTURE)
            allowed = {address.netloc, signaling.netloc}

            def safe_url(url):
                parsed = urlsplit(url)
                return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

            def route(request):
                parsed = urlsplit(request.request.url)
                if parsed.scheme in ("http", "https") and parsed.netloc in allowed:
                    return request.continue_()
                if parsed.scheme in ("data", "blob"):
                    return request.continue_()
                if parsed.hostname == "fonts.googleapis.com":
                    styling.append(safe_url(request.request.url))
                    return request.fulfill(status=200, content_type="text/css", body="/* Offline trial uses installed fallback fonts. */")
                blocked.append(safe_url(request.request.url))
                request.abort()

            def websocket(socket):
                parsed = urlsplit(socket.url)
                if parsed.scheme == signaling.scheme and parsed.netloc == signaling.netloc:
                    sockets.append(safe_url(socket.url))
                    socket.connect_to_server()
                else:
                    blocked.append(safe_url(socket.url))
                    socket.close()

            context.route("**/*", route)
            context.route_web_socket("**/*", websocket)
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            try:
                page.goto(base + "/?mute=1#/home")
                result = page.evaluate(r"""async demo => {
                  const {LiveKitVoiceClient,FragmentReader,LIVEKIT_TOPIC}=await import('/web/player/livekit-voice.js');
                  const sdk=await import('/web/vendor/livekit-client-2.22.3.esm.mjs');
                  const bundle=await(await fetch(`/api/demos/${demo}/bundle`)).json();
                  const state=window.liveKitQA={bundle,events:[],sent:[],audio:[],errors:[],states:[],holds:[],pongs:[],wire:[],received:[]};
                  const roomConnect=sdk.Room.prototype.connect;
                  sdk.Room.prototype.connect=async function(...args){
                    this.on(sdk.RoomEvent.DataReceived,(data,participant,kind,topic)=>state.received.push({bytes:data.byteLength,owned:participant?.identity===state.client?.socket?.agentIdentity,kind,topic}));
                    const publish=this.localParticipant.publishData.bind(this.localParticipant);
                    this.localParticipant.publishData=async(data,options)=>{await publish(data,options);state.wire.push({bytes:data.byteLength,topic:options.topic,reliable:options.reliable});};
                    return roomConnect.apply(this,args);
                  };
                  const client=state.client=new LiveKitVoiceClient({url:`/api/demos/${demo}/run/live`,sessionId:'lk_browser_'+crypto.randomUUID().replaceAll('-',''),onError:e=>state.errors.push(e),onState:e=>state.states.push(e),onSpeechHold:e=>state.holds.push(e)});
                  const send=client.send.bind(client);state.control=[];client.send=(type,data)=>{state.control.push(type);return send(type,data);};
                  const statusTimer=setTimeout(async()=>{state.earlyRTC=await Promise.all(trialPeerConnections.map(async p=>{const values=[...(await p.getStats()).values()];return {connection:p.connectionState,ice:p.iceConnectionState,signal:p.signalingState,candidates:values.filter(v=>v.type.includes('candidate')).map(v=>({type:v.type,state:v.state,candidateType:v.candidateType,protocol:v.protocol,address:v.address,port:v.port,nominated:v.nominated,bytesSent:v.bytesSent,bytesReceived:v.bytesReceived}))};}));},4500);
                  client.setMuted(true);const connecting=client.connect();state.socket=client.socket;await connecting;clearTimeout(statusTimer);
                  const room=client.socket.room,agentIdentity=client.socket.agentIdentity;
                  const reader=new FragmentReader({onMessage:raw=>{const e=JSON.parse(raw);state.events.push({type:e.type,turn_id:e.turn_id});if(e.type==='trial.pong')state.pongs.push(e);},onFailure:e=>state.errors.push(e.message)});
                  room.on(sdk.RoomEvent.DataReceived,(packet,participant,kind,topic)=>{if(participant?.identity===agentIdentity&&topic===LIVEKIT_TOPIC)reader.add(packet);});
                  const publish=room.localParticipant.publishData.bind(room.localParticipant);
                  const outgoing=new FragmentReader({onMessage:raw=>state.sent.push(JSON.parse(raw).type),onFailure:e=>state.errors.push(e.message)});
                  room.localParticipant.publishData=(packet,options)=>{outgoing.add(packet);return publish(packet,options);};
                  state.reader=reader;state.outgoing=outgoing;state.sdk=sdk;
                  return {ready:client.ready,transport:client.transport,captures:trialCapture.calls,runtime:bundle.runtime?.version,version:sdk.version};
                }""", args.demo)
                check("actual pinned SDK joins the configured runtime room", result["ready"] and result["transport"] == expected_transport and result["version"] == "2.22.3")
                check("text connection does not acquire a microphone", result["captures"] == 0)
                check("only the explicitly allowed LiveKit signaling is opened", sockets and not blocked)
                check("real synthetic capture starts once", page.evaluate("async()=>await liveKitQA.client.startCapture() && trialCapture.calls===1"))
                page.wait_for_function("()=>liveKitQA.client.micReady", timeout=15000)
                page.wait_for_timeout(700)
                page.evaluate("liveKitQA.client.socket.pingWorker()")
                page.wait_for_function("()=>liveKitQA.pongs.length && liveKitQA.pongs.at(-1).rtc_frames_forwarded>0", timeout=10000)
                counters = page.evaluate("()=>({received:liveKitQA.pongs.at(-1).rtc_frames_received,forwarded:liveKitQA.pongs.at(-1).rtc_frames_forwarded,sent:liveKitQA.sent,captures:trialCapture.calls})")
                check("server receives and forwards actual RTC PCM frames", counters["received"] > 0 and counters["forwarded"] > 0)
                check("microphone PCM never uses the reliable data uplink", "audio.input" not in counters["sent"])
                stats = page.evaluate(r"""async expectedHost=>{
                  const values=[...(await liveKitQA.client.socket.localTrack.getRTCStatsReport()).values()];
                  const transport=values.find(v=>v.type==='transport'&&v.selectedCandidatePairId);
                  const pair=values.find(v=>v.id===transport?.selectedCandidatePairId)||values.find(v=>v.type==='candidate-pair'&&v.state==='succeeded'&&v.nominated);
                  const remote=values.find(v=>v.id===pair?.remoteCandidateId),local=values.find(v=>v.id===pair?.localCandidateId);
                  return {bytes:values.filter(v=>v.type==='outbound-rtp'&&v.kind==='audio').reduce((n,v)=>n+(v.bytesSent||0),0),pairState:pair?.state,localType:local?.candidateType,remoteType:remote?.candidateType,localRelayProtocol:local?.relayProtocol||null,relayUsesTLS:local?.relayProtocol==='tls'||/^turns:/.test(local?.url||''),localProtocol:local?.protocol||null,remoteProtocol:remote?.protocol||null,remoteExpectedHost:expectedHost===(remote?.address||remote?.ip)};
                }""", args.rtc_host)
                check("real RTC audio packets use the exact configured candidate", stats["bytes"] > 0 and stats["pairState"] == "succeeded" and stats["remoteExpectedHost"])
                if args.require_relay:
                    check("actual browser audio reaches the worker through TURN relay", stats["localType"] == "relay")
                    check("selected TURN relay uses TLS", stats["localRelayProtocol"] in ("tls", "tcp") and stats["relayUsesTLS"])
                page.evaluate("trialCapture.gain.gain.value=0.09")
                page.wait_for_function("()=>liveKitQA.holds.length>0", timeout=4000)
                check("same RTC capture still drives immediate local speech hold", page.evaluate("!!liveKitQA.client.inputHold && trialCapture.calls===1"))
                page.evaluate("trialCapture.gain.gain.value=0.002")
                page.wait_for_function("()=>!liveKitQA.client.inputHold", timeout=4000)
                check("no-final synthetic input releases the reversible hold", page.evaluate("!liveKitQA.client.inputHold && liveKitQA.client.ready"))
                old_generation = page.evaluate("liveKitQA.client.inputGeneration")
                page.evaluate("liveKitQA.client.stopCapture()")
                page.wait_for_timeout(350)
                check("mic off releases the source but leaves text connected", page.evaluate("trialCapture.tracks[0].readyState==='ended' && liveKitQA.client.ready && !liveKitQA.client.mic"))
                check("second RTC capture starts", page.evaluate("async()=>await liveKitQA.client.startCapture()"))
                page.wait_for_function("()=>liveKitQA.client.micReady", timeout=15000)
                check("mic retry has a distinct generation and only its active track", page.evaluate("previous=>liveKitQA.client.inputGeneration>previous && trialCapture.calls===2 && trialCapture.tracks.filter(t=>t.readyState==='live').length===1", old_generation))
                page.evaluate("liveKitQA.client.stopCapture()")
                answer = page.evaluate(r"""async()=>{
                  const s=liveKitQA;s.answer=await s.client.ask({question:'Show me the cabin',history:[],profile:{},input_mode:'text',demo_version:s.bundle.version,slide_id:s.bundle.slides[0].id});
                  return {answered:s.answer.answered,visual_only:s.answer.visual_only,image:s.answer.visual?.ref,slide:s.answer.slide_id,snapshot:s.answer.visual?.snapshot_id===s.bundle.knowledge_snapshot_id,utterance:!!s.answer.runtime_utterance_id};
                }""")
                check("actual runtime returns pinned BMW picture and deferred audio", answer["answered"] and answer["visual_only"] and answer["image"] and answer["snapshot"] and answer["utterance"])
                before = page.evaluate("liveKitQA.sent.filter(t=>t==='delivery.request').length")
                check("runtime picture selection does not start speech prematurely", before == 0)
                visual = page.evaluate(r"""async()=>{
                  const {resolveAnswerVisual}=await import('/web/player/answer-visual.js');const {renderSlide}=await import('/web/slide.js');const {createWalkthrough}=await import('/web/player/walkthrough.js');
                  const s=liveKitQA,visual=resolveAnswerVisual(s.bundle,s.bundle.slides,s.answer);if(!visual)throw Error('Pinned image rejected');
                  const slide=s.bundle.slides.find(v=>v.id===visual.slide.id),native=renderSlide(slide,{walkthrough:true}),gallery=s.gallery=createWalkthrough();gallery.mount(s.bundle.slides);
                  const view=s.view=gallery.wrap(slide,native);document.querySelector('#main').replaceChildren(view.el);view.el.classList.add('on');Object.assign(view.el.style,{width:'100%',height:'700px'});
                  const shown=await view.focusMedia(visual.imageId,{lineIndex:visual.lineIndex,calloutId:visual.calloutId});
                  const played=await s.client.speak(s.answer.answer,{utteranceId:s.answer.runtime_utterance_id,turnId:s.answer.runtime_turn_id,onStart:()=>s.audio.push({image:document.querySelector('.gallery-surface')?.dataset.imageId,phase:document.querySelector('.gallery-surface')?.dataset.phase})});
                  return {shown,played,expected:visual.imageId,atStart:s.audio.at(-1)};
                }""")
                check("actual gallery picture is ready before real data-channel PCM playback", visual["shown"] and visual["played"] and visual["atStart"]["image"] == visual["expected"])
                page.screenshot(path=str(args.output / "bmw-livekit-answer-image.png"), full_page=False)
                page.evaluate("liveKitQA.client.send('session.end')")
                page.wait_for_function("()=>!liveKitQA.client.ready && liveKitQA.client.socket?.readyState===3", timeout=8000)
                check("real runtime worker departure closes the browser transport", page.evaluate("!liveKitQA.client.ready && !liveKitQA.client.mic && liveKitQA.errors.some(e=>e.includes('LiveKit:'))"))
                page.evaluate("liveKitQA.client.close();liveKitQA.reader.close();liveKitQA.outgoing.close();liveKitQA.gallery.destroy()")
                check("ended trial leaves no live synthetic device", page.evaluate("trialCapture.tracks.every(t=>t.readyState==='ended')"))

                # Actual player keeps its normal navigation, gallery and bottom
                # controls; the factory changes only the selected transport.
                mounted = page.evaluate(r"""async demo=>{
                  const {mountPlayer}=await import('/web/player/player.js');const {LiveKitVoiceClient}=await import('/web/player/livekit-voice.js');
                  const state=window.playerQA={saved:[],answers:[],played:[]};const bundle=await(await fetch(`/api/demos/${demo}/bundle`)).json();
                  const post=async(path,body)=>{const r=await fetch(`/api/demos/${demo}/${path}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});if(!r.ok)throw Error('Mock API failed '+r.status);return r.json();};
                  const host=document.createElement('div');host.className='play-page';document.querySelector('#main').replaceChildren(host);
                  state.player=mountPlayer(host,bundle,{liveUrl:`/api/demos/${demo}/run/live`,liveClientFactory:options=>{const client=state.client=new LiveKitVoiceClient(options);const ask=client.ask.bind(client);client.ask=async body=>{const answer=await ask(body);state.answers.push(answer);return answer;};const speak=client.speak.bind(client);client.speak=(text,options={})=>speak(text,{...options,onStart:ts=>{state.played.push({text,image:document.querySelector('.slide.on .gallery-surface')?.dataset.imageId});options.onStart?.(ts);}});return client;},qa:body=>post('run/qa',body),tts:text=>post('run/tts',{text}).then(r=>r.url),pitch:body=>post('run/pitch',body),lead:body=>post('run/lead',body),saveSession:async body=>{state.saved.push(body);return post('run/session',body);},beacon:body=>{state.saved.push(body);post('run/session',body);},onClose(){}});
                  return {transport:state.client.transport,top:!!host.querySelector('.pl-top'),bottom:!!host.querySelector('.pl-dock')};
                }""", args.demo)
                check("actual player mounts with unchanged top and bottom controls", mounted["transport"] == "livekit" and mounted["top"] and mounted["bottom"])
                page.get_by_role("button", name="Browse at my pace", exact=True).click()
                page.wait_for_function("()=>playerQA.client.ready", timeout=15000)
                page.wait_for_function("()=>document.querySelector('.slide.on .gallery-surface[data-image-id]')", timeout=25000)
                page.locator(".pl-reply input").fill("Show me the cabin")
                page.locator(".pl-reply input").press("Enter")
                page.wait_for_function("()=>playerQA.answers.some(a=>a.visual_only&&a.answered)", timeout=15000)
                page.wait_for_function("()=>{const a=playerQA.answers.find(a=>a.visual_only&&a.answered);return a&&playerQA.played.some(p=>p.text===a.answer&&p.image===a.visual.ref)}", timeout=15000)
                check("actual player brings the requested BMW picture before its answer voice", page.evaluate("()=>{const a=playerQA.answers.find(a=>a.visual_only&&a.answered);return playerQA.played.some(p=>p.text===a.answer&&p.image===a.visual.ref)}"))
                check("gallery and conversation remain inside the desktop viewport", page.locator(".pl").evaluate("e=>e.getBoundingClientRect().right<=innerWidth+1"))
                page.screenshot(path=str(args.output / "bmw-livekit-player-desktop.png"), full_page=False)
                page.set_viewport_size({"width":390,"height":844})
                check("same player remains within phone viewport", page.locator(".pl").evaluate("e=>e.getBoundingClientRect().right<=innerWidth+1"))
                page.screenshot(path=str(args.output / "bmw-livekit-player-phone.png"), full_page=False)
                page.locator('.pl-top button[aria-label="Stop and see the summary"]').click()
                page.wait_for_function("()=>playerQA.saved.some(s=>s.ended_at||s.ended)", timeout=15000)
                page.wait_for_function("""async demo=>{
                  const final=playerQA.saved.find(s=>s.ended);if(!final)return false;
                  const response=await fetch(`/api/demos/${demo}/sessions/${final.id}`);if(!response.ok)return false;
                  playerQA.persisted=await response.json();return playerQA.persisted.ended===true;
                }""", arg=args.demo, timeout=15000)
                check("trial player saves the completed visit incrementally", page.evaluate("playerQA.saved.length>1 && playerQA.persisted.ended && playerQA.persisted.save_seq>1 && playerQA.persisted.questions.includes('Show me the cabin')"))
                page.evaluate("playerQA.player.destroy();trialCapture.contexts.forEach(c=>c.close())")

                # Cover the actual application route as well as the transport
                # harness: the shared user URL must deliver intake and text
                # questions using web/app.js's own factory and API callbacks.
                page.set_viewport_size({"width":1440,"height":960})
                page.goto(base + f"/?mute=1#/play/{args.demo}")
                page.get_by_role("button", name="Explore with me", exact=True).wait_for()
                check("stock application chooses LiveKit without a transport URL flag", "voice_transport" not in page.url and capability["transport"] == "livekit")
                page.evaluate(r"""async()=>{
                  const {LiveKitVoiceClient}=await import('/web/player/livekit-voice.js');
                  const state=window.routeQA={asked:[],answers:[],saved:[],played:[],mediaPlayed:[]};
                  const mediaPlay=HTMLMediaElement.prototype.play;
                  HTMLMediaElement.prototype.play=function(...args){const url=this.currentSrc||this.src;return Promise.resolve(mediaPlay.apply(this,args)).then(value=>{state.mediaPlayed.push(url);return value;});};
                  const ask=LiveKitVoiceClient.prototype.ask,speak=LiveKitVoiceClient.prototype.speak,connect=LiveKitVoiceClient.prototype.connect;
                  LiveKitVoiceClient.prototype.connect=function(...args){state.client=this;return connect.apply(this,args);};
                  LiveKitVoiceClient.prototype.ask=async function(body){state.client=this;state.asked.push(body);const answer=await ask.call(this,body);state.answers.push(answer);return answer;};
                  LiveKitVoiceClient.prototype.speak=function(text,options={}){return speak.call(this,text,{...options,onStart:ts=>{state.played.push(text);options.onStart?.(ts);}});};
                  const fetch=window.fetch;window.fetch=async function(input,init){
                    const url=typeof input==='string'?input:input.url;
                    if(url?.endsWith('/run/session')&&init?.body)state.saved.push(JSON.parse(init.body));
                    return fetch.apply(this,arguments);
                  };
                }""")
                page.get_by_role("switch", name="Voice mode", exact=True).check()
                page.get_by_role("button", name="Explore with me", exact=True).click()
                page.get_by_role("textbox", name="Your answer", exact=True).fill("Show me around")
                page.get_by_role("textbox", name="Your answer", exact=True).press("Enter")
                page.wait_for_function("()=>!document.querySelector('.pl-intake:not(.pl-welcome)').classList.contains('open')", timeout=25000)
                page.wait_for_function("()=>routeQA.saved.some(s=>s.transcript?.some(t=>t.role==='user'&&t.text==='Show me around'))", timeout=5000)
                check("stock application accepts typed intake while voice mode is enabled", page.evaluate("()=>routeQA.saved.some(s=>s.transcript?.some(t=>t.role==='user'&&t.text==='Show me around'))"))
                page.wait_for_function("()=>routeQA.client?.ready && routeQA.client.micReady && trialPeerConnections.some(p=>p.connectionState==='connected')", timeout=30000)
                check("stock route establishes its own continuous microphone over RTC", page.evaluate("()=>routeQA.client.mic && !!routeQA.client.socket.localTrack && trialCapture.tracks.filter(t=>t.readyState==='live').length===1"))
                question = "tell me more about interior of the car"
                page.get_by_role("textbox", name="Your question or answer", exact=True).fill(question)
                page.get_by_role("textbox", name="Your question or answer", exact=True).press("Enter")
                # Reusing isolated QA state can legitimately serve an exact
                # customer cache clip. Observe that clip as well as streamed PCM.
                page.wait_for_function("()=>routeQA.answers.length===1 && (routeQA.played.includes(routeQA.answers[0].answer) || routeQA.answers[0].audio && routeQA.mediaPlayed.includes(new URL(routeQA.answers[0].audio,location.href).href))", timeout=15000)
                check("stock route sends typed question over LiveKit and delivers the answer", page.evaluate("([q,transport])=>routeQA.client.transport===transport && routeQA.asked[0].question===q && routeQA.answers[0].answered && !!routeQA.answers[0].answer && (routeQA.played.includes(routeQA.answers[0].answer) || routeQA.answers[0].audio && routeQA.mediaPlayed.includes(new URL(routeQA.answers[0].audio,location.href).href))", [question, expected_transport]))
                check("stock route clears only the submitted question field", page.get_by_role("textbox", name="Your question or answer", exact=True).input_value() == "")
                page.screenshot(path=str(args.output / "bmw-livekit-stock-route-answer.png"), full_page=False)
                page.locator('.pl-top button[aria-label="Stop and see the summary"]').click()
                page.wait_for_function("()=>routeQA.saved.some(s=>s.ended)", timeout=15000)
                page.wait_for_function("""async demo=>{
                  const final=routeQA.saved.find(s=>s.ended);if(!final)return false;
                  const response=await fetch(`/api/demos/${demo}/sessions/${final.id}`);if(!response.ok)return false;
                  routeQA.persisted=await response.json();return routeQA.persisted.ended===true;
                }""", arg=args.demo, timeout=15000)
                check("stock route persists the submitted question and actual answer", page.evaluate("q=>routeQA.persisted.questions.includes(q) && routeQA.persisted.turns.some(t=>t.question===q&&t.answered&&!t.failed) && routeQA.persisted.transcript.some(t=>t.role==='agent'&&t.text===routeQA.answers[0].answer)", question))
                check("browser opens no unapproved connection or legacy microphone WebSocket", not blocked and all(urlsplit(url).netloc == signaling.netloc for url in sockets))
                check("browser has no uncaught JavaScript error", not errors)
                report = {"passed":len(checks),"total":len(checks),"checks":checks,"provider_calls":0,"physical_microphone":False,"transport":"real-hosted-livekit" if hosted else "real-local-livekit","rtc":stats,"frames":{k:counters[k] for k in ("received","forwarded")},"errors":errors,"blocked":blocked,"offline_stylesheets":styling,"screenshots":[p.name for p in args.output.glob("bmw-livekit-*.png")]}
                (args.output / "results.json").write_text(json.dumps(report, indent=2) + "\n")
                print(json.dumps(report), flush=True)
            except Exception:
                page.screenshot(path=str(args.output / "failure.png"), full_page=False)
                state = page.evaluate("()=>({errors:window.liveKitQA?.errors,states:window.liveKitQA?.states,controls:window.liveKitQA?.control,wire:window.liveKitQA?.wire,received:window.liveKitQA?.received,earlyRTC:window.liveKitQA?.earlyRTC,room:window.liveKitQA?.socket?.room?.state,socket:window.liveKitQA?.socket?.readyState,peers:window.liveKitQA?.socket?.room?.remoteParticipants?.size,route:window.routeQA&&{asked:routeQA.asked,answers:routeQA.answers,played:routeQA.played,mediaPlayed:routeQA.mediaPlayed,ready:routeQA.client?.ready,micReady:routeQA.client?.micReady},rtc:trialPeerConnections.map(p=>({connection:p.connectionState,ice:p.iceConnectionState,signal:p.signalingState,local:!!p.localDescription,remote:!!p.remoteDescription}))})")
                (args.output / "failure.json").write_text(json.dumps({"passed":checks,"failures":failures,"errors":errors,"blocked":blocked,"sockets":sockets,"state":state},indent=2)+"\n")
                raise
            finally:
                browser.close()


if __name__ == "__main__":
    main()
