// Free fake-device/transport checks; no browser microphone, server or provider call.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(new URL("../web/player/live-voice.js", import.meta.url), "utf8");
const { LiveVoiceClient, pcmToFloat, meaningfulTranscript } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
let passes = 0;
function check(name, condition) { assert.ok(condition, name); passes++; console.log("PASS", name); }
class Socket {
  static instances = [];
  constructor() { this.readyState = 0; this.sent = []; this.bufferedAmount = 0; Socket.instances.push(this); queueMicrotask(() => { this.readyState = 1; this.onopen?.(); }); }
  send(raw) { const event = JSON.parse(raw); this.sent.push(event); if (event.type === "session.start") queueMicrotask(() => this.emit({ type: "session.ready", session_id: event.session_id })); }
  emit(event) { this.onmessage?.({ data: JSON.stringify(event) }); }
  close() { this.readyState = 3; this.onclose?.(); }
}
class Node { connect() {} disconnect() { this.disconnected = true; } }
class Source extends Node { start() { this.started = true; } stop() { this.stopped = true; } }
class Context {
  static sources = [];
  constructor() { this.currentTime = 0; this.state = "running"; this.destination = {}; this.audioWorklet = { addModule: async () => {} }; }
  async resume() {} async close() { this.state = "closed"; }
  createGain() { return Object.assign(new Node(), { gain: { value: 1 } }); }
  createMediaStreamSource() { return new Node(); }
  createBuffer(_, samples, rate) { return { duration: samples / rate, copyToChannel() {} }; }
  createBufferSource() { const source = new Source(); Context.sources.push(source); return source; }
}
class Worklet extends Node { constructor() { super(); this.port = {}; } }
let captures = 0; const tracks = [];
function stream() { const track = { stopped: false, stop() { this.stopped = true; } }; tracks.push(track); return { getTracks: () => [track], getAudioTracks: () => [track] }; }
const env = { WebSocket: Socket, AudioContext: Context, AudioWorkletNode: Worklet, atob, location: { href: "http://localhost/" }, navigator: { mediaDevices: { getUserMedia: async () => { captures++; return stream(); } } } };
const transcripts = [], onsets = [];
let client = new LiveVoiceClient({ url: "/run/live", sessionId: "test", env, onTranscript: e => transcripts.push(e), onSpeechStart: e => { onsets.push(e); client.interrupt(); } });
await client.connect();
check("text-only session never opens microphone", captures === 0 && client.socket.sent[0].mic === false);
await Promise.all([client.startCapture(), client.startCapture()]);
check("concurrent mic starts acquire one continuous stream", captures === 1 && client.mic);
client.worklet.port.onmessage({ data: { pcm: new Int16Array(320).buffer, rms: 0 } });
check("first audio is retained until provider ready", client.preRoll.length === 1 && !client.socket.sent.some(e => e.type === "audio.input"));
client.receive({ type: "mic.ready", input_generation: client.inputGeneration });
check("provider readiness flushes initial audio instead of losing first words", client.micReady && client.preRoll.length === 0 && client.socket.sent.some(e => e.type === "audio.input"));
client.receive({ input_generation: client.inputGeneration, type: "transcript.partial", input_id: "a", text: "boot" });
client.receive({ input_generation: client.inputGeneration, type: "input.speech_start", input_id: "a" });
check("partial and raw VAD remain provisional until a final", onsets.length === 0);
client.receive({ input_generation: client.inputGeneration, type: "input.speech_end", input_id: "a", voice_ended: 123 });
const endpointReceived = client.endpointAt;
client.receive({ input_generation: client.inputGeneration, type: "transcript.final", input_id: "a", text: "boot space" });
client.receive({ input_generation: client.inputGeneration, type: "transcript.final", input_id: "a", text: "boot space" });
check("qualified final interrupts once and uses the browser receipt clock", onsets.length === 1 && onsets[0].source === "final" && transcripts.filter(e => e.final).length === 1 && transcripts.at(-1).voice_ended === endpointReceived && transcripts.at(-1).speech_end_basis === "browser_endpoint_receipt");
check("server timestamp is provenance and cannot skew browser latency", transcripts.at(-1).server_endpoint_received_at === 123 && transcripts.at(-1).voice_ended !== 123);
client.receive({ input_generation: client.inputGeneration, type: "transcript.final", text: "yes" }); client.receive({ input_generation: client.inputGeneration, type: "transcript.final", text: "yes" });
check("same wording without provider identity is not permanently swallowed", transcripts.filter(e => e.final && e.text === "yes").length === 2);
check("an unsegmented later final cannot reuse an older endpoint", transcripts.at(-1).speech_end_basis === "browser_transcript_receipt" && transcripts.at(-1).endpoint_received_at === null);
check("a completed utterance keeps capture open", client.mic && captures === 1 && !tracks[0].stopped);
const answer = client.ask({ question: "What is covered?" }); await tick(); const turn = client.pending.turnId;
client.socket.emit({ type: "turn.result", session_id: "another", turn_id: turn, answer: { answer: "wrong session" } });
check("another session cannot resolve this question", !!client.pending);
client.receive({ type: "turn.result", turn_id: "obsolete", answer: { answer: "wrong turn" } });
check("another turn cannot resolve this question", !!client.pending);
client.receive({ type: "turn.result", turn_id: turn, utterance_id: "answer-1", answer: { answer: "Reviewed answer", answered: true } });
const result = await answer;
check("validated result retains deferred delivery identity", result.runtime_utterance_id === "answer-1" && !client.socket.sent.some(e => e.type === "delivery.request"));
const audio = Buffer.from([0, 0, 0, 64, 0, 128]).toString("base64");
check("PCM signed samples decode accurately", JSON.stringify([...pcmToFloat(audio)]) === "[0,0.5,-1]");
let played = false;
const speech = client.speak(result.answer, { utteranceId: result.runtime_utterance_id, turnId: result.runtime_turn_id }).then(value => { played = value; return value; }); await tick();
client.receive({ type: "audio.chunk", turn_id: turn, utterance_id: "answer-1", seq: 0, audio, sample_rate: 24000, format: "pcm_s16le" });
const audioSource = Context.sources.at(-1);
client.receive({ type: "audio.chunk", turn_id: turn, utterance_id: "answer-1", seq: 0, audio });
check("duplicate audio sequence is not replayed", Context.sources.length === 1);
client.receive({ type: "audio.end", turn_id: turn, utterance_id: "answer-1" }); await tick();
check("provider completion does not advance before local audio ends", played === false && !!client.delivery);
audioSource.onended(); check("local audio ending completes delivery", await speech);
const interrupted = client.speak("Another answer"); await tick(); const active = client.delivery;
client.receive({ type: "audio.chunk", turn_id: active.turnId, utterance_id: active.utteranceId, seq: 0, audio });
const cut = Context.sources.at(-1); client.speechStart({ source: "local" });
check("speech onset stops active audio immediately", cut.stopped && client.delivery === null && await interrupted === false);
check("interrupt does not stop microphone", client.mic && !tracks[0].stopped);
const before = Context.sources.length;
client.receive({ type: "audio.chunk", turn_id: active.turnId, utterance_id: active.utteranceId, seq: 1, audio });
check("late chunks of interrupted utterance are discarded", Context.sources.length === before);
const pending = client.ask({ question: "Long lookup" }).catch(e => e); await tick(); client.interrupt();
check("interrupt rejects owned waiting question", (await pending).name === "AbortError");
check("server cancellation takes the same new owner as client", client.socket.sent.filter(e => e.type === "turn.interrupt").at(-1).turn_id === client.turnId);
client.interrupt({ preservePlanning: true });
check("media-only cancellation explicitly preserves background planning", client.socket.sent.at(-1).type === "turn.interrupt" && client.socket.sent.at(-1).preserve_planning === true && !client.pending);
client.interrupt();
check("ordinary cancellation never implicitly preserves a planner", client.socket.sent.at(-1).preserve_planning === false);
client.setMuted(true); check("review mute applies to streamed audio gain", client.gain.gain.value === 0);
const racing = client.speak("Cancelled before asynchronous audio setup").catch(e => e); client.cancelAudio();
check("cancel during audio initialization cannot start obsolete speech", (await racing).name === "AbortError" && !client.delivery);
const replacement = client.speak("New speech after cancellation"); await tick();
check("new speech can acquire delivery after earlier cancellation", !!client.delivery);
client.cancelAudio(); await replacement;
const oldInputGeneration = client.inputGeneration;
client.stopCapture(); check("microphone mute releases device but keeps text transport", tracks[0].stopped && !client.mic && client.ready);
await client.startCapture(); check("explicit retry can recover microphone", captures === 2 && client.mic);
const transcriptCount = transcripts.length, onsetCount = onsets.length;
client.receive({ type: "mic.ready", input_generation: oldInputGeneration });
client.receive({ type: "input.speech_start", input_generation: oldInputGeneration, input_id: "late" });
client.receive({ type: "transcript.final", input_generation: oldInputGeneration, input_id: "late", text: "An old answer" });
client.receive({ type: "error", input_generation: oldInputGeneration, code: "microphone_stream", message: "Old connection failed" });
check("mute then unmute rejects stale ready, onset, final and error", client.mic && !client.micReady && transcripts.length === transcriptCount && onsets.length === onsetCount && !tracks[1].stopped);
client.receive({ type: "transcript.final", text: "An unowned transcript" });
check("unowned microphone event cannot cross capture boundary", transcripts.length === transcriptCount);
client.receive({ type: "mic.ready", input_generation: client.inputGeneration });
client.receive({ type: "transcript.final", input_generation: client.inputGeneration, input_id: "late", text: "A new answer" });
check("new capture accepts its own final even when input ID repeats", client.micReady && transcripts.length === transcriptCount + 1 && transcripts.at(-1).text === "A new answer");
check("capture commands and audio carry microphone ownership", client.socket.sent.filter(e => ["mic.set", "audio.input"].includes(e.type)).every(e => Number.isInteger(e.input_generation) && e.input_generation > 0));
client.receive({ type: "error", input_generation: client.inputGeneration, code: "microphone_stream", message: "Disconnected" });
check("fatal input connection failure releases microphone", tracks[1].stopped && !client.mic);
client.close(); check("end releases microphone and both audio contexts", tracks[1].stopped && !client.ready && !client.outputContext);
let grant; const slowEnv = { ...env, navigator: { mediaDevices: { getUserMedia: () => new Promise(resolve => { grant = resolve; }) } } };
const slow = new LiveVoiceClient({ url: "/run/live", sessionId: "slow", env: slowEnv });
const permission = slow.startCapture(); await tick(); slow.stopCapture(); const late = stream(); grant(late);
await permission;
check("permission arriving after cancellation releases its device", late.getTracks()[0].stopped && !slow.mic);
slow.close();
const connecting = new LiveVoiceClient({ url: "/run/live", sessionId: "connection-race", env });
const superseded = connecting.ask({ question: "Obsolete connection question" }).catch(e => e); connecting.interrupt();
check("cancel during socket initialization fences the old request", (await superseded).name === "AbortError" && !connecting.socket.sent.some(e => e.type === "turn.ask"));
connecting.close();
const disconnected = new LiveVoiceClient({ url: "/run/live", sessionId: "farewell-disconnect", env });
const failedFarewell = disconnected.speak("Your recap is ready.").catch(error => error); await tick();
disconnected.socket.close();
const farewellError = await failedFarewell;
check("unexpected connection loss rejects farewell speech for readable fallback", farewellError instanceof Error && farewellError.name !== "AbortError" && !farewellError.audioStarted && !disconnected.delivery);
disconnected.close();
const cancelledFarewell = new LiveVoiceClient({ url: "/run/live", sessionId: "farewell-new-turn", env });
const oldFarewell = cancelledFarewell.speak("An obsolete farewell."); await tick();
cancelledFarewell.interrupt(); cancelledFarewell.socket.close();
check("new turn before connection loss retains cancellation instead of reviving farewell", await oldFarewell === false);
cancelledFarewell.close();
let Capture; const packets = [];
vm.runInNewContext(fs.readFileSync(new URL("../web/player/voice-worklet.js", import.meta.url), "utf8"), {
  AudioWorkletProcessor: class { constructor() { this.port = { postMessage: packet => packets.push(packet) }; } },
  sampleRate: 48000, registerProcessor: (_, implementation) => { Capture = implementation; },
});
const processor = new Capture();
for (let i = 0; i < 375; i++) processor.process([[new Float32Array(128).fill(0.5)]]);
check("capture resamples one second into exactly 50 PCM16 packets", packets.length === 50 && packets.every(p => p.pcm.byteLength === 640));
check("capture preserves speech amplitude without sending audible output", packets.every(p => Math.abs(p.rms - 0.5) < 0.0001));
const playerSource = fs.readFileSync(new URL("../web/player/player.js", import.meta.url), "utf8");
const correctionSource = playerSource.slice(playerSource.indexOf("function explicitContextCorrection("), playerSource.indexOf("\nexport function mountPlayer"));
const correction = vm.runInNewContext(correctionSource + "\nexplicitContextCorrection");
const questionAckKey = vm.runInNewContext(correctionSource + "\nquestionAckKey");
const qualification = vm.runInNewContext(correctionSource + "\n({qualifiesCustomerSpeech,playbackCommand,genericTour})",{meaningfulTranscript});
check("actual player qualifier rejects fragment intake and unrelated TV statement",!qualification.qualifiesCustomerSpeech("It’s",{prompt:true}) && !qualification.qualifiesCustomerSpeech("Breaking news and the weather forecast",{terms:["warranty","creta"]}));
check("actual player qualifier keeps short questions and prompt-owned phone input",qualification.qualifiesCustomerSpeech("Warranty?",{terms:[]}) && qualification.qualifiesCustomerSpeech("Automatic?",{terms:[]}) && qualification.qualifiesCustomerSpeech("9876543210",{prompt:true}) && !qualification.qualifiesCustomerSpeech("9876543210",{prompt:false}));
check("actual player qualifier accepts repeated yes only for a current question",qualification.qualifiesCustomerSpeech("yes",{prompt:true}) && qualification.qualifiesCustomerSpeech("yes",{prompt:true}) && !qualification.qualifiesCustomerSpeech("yes",{prompt:false}));
check("generic tour and playback commands are recognized without product preference",qualification.genericTour("show me around") && qualification.playbackCommand("Continue") === "continue" && qualification.playbackCommand("Not now") === "notnow" && !qualification.genericTour("I care about rear seat comfort"));

check("explicit stated priority triggers refinement", correction("Actually, boot space matters more.") && correction("I care more about safety."));
check("factual questions and hypotheticals cannot rewrite customer preference", !correction("Is boot space more important?") && !correction("For example, I prefer safety.") && !correction("Actually, the warranty is five years.") && !correction("What if I prefer safety?"));
const resultSource = playerSource.slice(playerSource.indexOf("  async function questionResult("), playerSource.indexOf("  async function handleQuestion("));
{
  const captionSource = playerSource.slice(playerSource.indexOf("  function captionOnly("), playerSource.indexOf("  function speakBrowser("));
  let audioStamp = 0, finish;
  const state = { run: 1, ttsToken: 0, onFirstAudio: () => { audioStamp++; }, activeTurn: { qa_done: 1, answer_audio: null } };
  const caption = vm.runInNewContext(captionSource + "\ncaptionOnly", { S: state, wordsOf: text => text.split(" ").length, setStatus() {}, firstAudio() { audioStamp++; }, logHeard() {}, setTimeout(fn) { finish = fn; return 1; }, clearTimeout() {} });
  const shown = caption("The answer remains readable.", 1);
  check("caption fallback never fabricates first answer audio", audioStamp === 0 && state.onFirstAudio === null && state.activeTurn.answer_audio === null && state.activeTurn.failed && state.activeTurn.delivery_failed && state.activeTurn.caption_at > 0);
  finish(); await shown;
}
{
  const captionSource = playerSource.slice(playerSource.indexOf("  function captionOnly("), playerSource.indexOf("  function speakBrowser("));
  const closeSource = playerSource.slice(playerSource.indexOf("  async function closeFlow("), playerSource.indexOf("  function captureOrigin("));
  const state = { run: 1, ttsToken: 0 }; let finish, recaps = 0;
  const closing = vm.runInNewContext(captionSource + closeSource + "\nfunction speak(text, run) { return captionOnly(text, run); }\ncloseFlow", {
    S: state, bundle: { ctas: [] }, el: { cite: {} }, closingSlide: () => null, heroClose: () => null, showSlideView() {},
    waitFor: async () => ({ value: "notyet" }), showHandoff() { recaps++; }, wordsOf: text => text.split(" ").length,
    setStatus() {}, logHeard() {}, setTimeout(fn) { finish = fn; return 1; }, clearTimeout() {},
  });
  const obsolete = closing(1); await tick(); state.run = 2; state.cancelVoice(); finish(); await obsolete;
  check("interrupting a failed farewell caption cannot force the obsolete recap", recaps === 0);
}
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
function questionHarness() {
  const state = { run: 1 }, qa = deferred(), filler = deferred(), calls = { cancel: 0, filler: 0, status: 0, words: [] };
  const result = vm.runInNewContext(resultSource + "\nquestionResult", { S: state, bundle: {}, questionAckKey, withTimeout: async () => null,
    speak(text) { calls.filler++; calls.words.push(text); return filler.promise; }, cancelSpeech() { calls.cancel++; }, setStatus() { calls.status++; } });
  return { state, qa, filler, calls, result };
}
{
  const h = questionHarness(), turn = {}; const result = h.result(h.qa.promise, 1, turn); await tick(); h.state.onFirstAudio(100);
  check("genuine question gets the requested acknowledgment instead of a lookup filler", h.calls.words.length === 1 && h.calls.words[0] === "This is a good question, give me a moment.");
  h.qa.resolve({ answer: "Useful answer" }); const value = await result;
  check("ready answer cuts acknowledgment without awaiting its obsolete delivery", value.answer === "Useful answer" && h.calls.cancel === 1 && turn.ack_audio === 100 && h.state.onFirstAudio === null);
  h.filler.resolve(false);
}
{
  const h = questionHarness(); let done = false; const result = h.result(h.qa.promise, 1, {}).then(value => { done = true; return value; }); await tick(); h.filler.resolve(true); await tick();
  check("finished acknowledgment never fabricates an answer or advances the wait", !done && h.calls.cancel === 0 && h.calls.status === 1);
  h.qa.resolve({ answer: "Later answer" }); await result;
}
{
  const h = questionHarness(); const result = h.result(h.qa.promise, 1, {}); await tick(); h.state.run = 2; const newCallback = () => {}; h.state.onFirstAudio = newCallback;
  h.qa.resolve({ answer: "Obsolete answer" });
  check("superseded question cannot cancel newer speech or steal its callback", await result === null && h.calls.cancel === 0 && h.state.onFirstAudio === newCallback); h.filler.resolve(false);
}
{
  const h = questionHarness(); const result = h.result(h.qa.promise, 1, {}).catch(error => error); await tick(); h.qa.reject(new Error("Provider failed"));
  check("question failure stops only acknowledgment before error recovery", (await result).message === "Provider failed" && h.calls.cancel === 1); h.filler.resolve(false);
}
const base = { id: "proof", segment_id: "boot", kind: "proof", checkin: { text: "Enough detail for now?", audio: "/media/fixture/checkin.wav" }, lines: [{ text: "A" }, { text: "B" }], callouts: [{ id: "a", reveal_on_line: 0, placement: "overlay", x: 0.72 }, { id: "b", reveal_on_line: 1, placement: "panel" }, { id: "omitted", reveal_on_line: 2 }] };
const routeState = { profile: { focus: [] } };
const routeSource = playerSource.slice(playerSource.indexOf("  function buildRoute("), playerSource.indexOf("  function rememberContext("));
const buildRoute = vm.runInNewContext(routeSource + "\nbuildRoute", { S: routeState, library: () => [base], topicOf: () => "boot", renderProgress() {}, prefetch() {} });
buildRoute({ route: [{ slide_id: "proof" }], personalized_segments: [{ segment_id: "boot", checkin: "Enough detail for now?", lines: [{ text: "Your priority", base_line_index: null }, { text: "B", base_line_index: 1 }, { text: "A", base_line_index: 0 }] }] });
check("personalized speech remaps callouts to their reviewed source line", JSON.stringify(routeState.plan[0].slide.callouts.map(c => [c.id, c.reveal_on_line])) === '[["a",2],["b",1]]');
check("personalization preserves native geometry and stored master", routeState.plan[0].slide.callouts[0].x === 0.72 && base.callouts[0].reveal_on_line === 0 && base.lines.length === 2);
check("legacy script checkin strings cannot erase the reviewed closing narration", routeState.plan[0].slide.checkin === base.checkin);
const startSource = playerSource.slice(playerSource.indexOf("  async function startAfterIntake("), playerSource.indexOf("  async function playCustomBatches("));
async function routeAfterOverview(plan) {
  const state = { run: 1, overviewPlayed: true, profile: { why: "Rear seat comfort matters", focus: [] }, pitchPromise: Promise.resolve(plan) }, heard = [], routed = [], notes = [];
  const start = vm.runInNewContext(startSource + "\nstartAfterIntake", { S: state, live: {}, api: {}, library: () => [base], withTimeout: async promise => promise,
    addMsg: (_, text) => notes.push(text), speak: async text => { heard.push(text); return true; }, speakF: async name => { heard.push(name); return true; },
    buildRoute: chosen => routed.push(chosen), playFrom: () => {}, playCustomBatches: async () => { throw Error("Duplicate custom narration"); }, el: { cite: {} } });
  await start(1, state.profile.why, { phase: "planning" }); return { state, heard, routed, notes };
}
{
  const plan = { route: [{ slide_id: "proof" }], decision_frame: "A long redundant planning explanation.", custom_batches: [{ text: "An extra prelude." }], personalized_segments: [] };
  const h = await routeAfterOverview(plan);
  check("completed overview enters reviewed selected route even when personalized script falls back", h.heard.length === 0 && h.routed[0] === plan && h.state.personalized && h.notes.length === 0);
}
{
  const h = await routeAfterOverview({ route: [{ slide_id: "not-reviewed" }], decision_frame: "Pretend this plan succeeded." });
  check("unusable live plan reports stable fallback without claiming personalization", !h.state.personalized && h.state.pitch === null && h.routed[0] === null && h.heard.length === 1 && h.heard[0].includes("couldn't finish tailoring") && h.notes.length === 1);
}
// Generic intake must retain the reviewed route, and a URL by itself remains a
// usable intake submission even when there are no preference words to qualify.
{
  const state={run:1,genericTour:true,profile:{why:"",focus:[]},pitchPromise:null};
  const heard=[],routes=[],calls={pitch:0,play:0};
  const overview={text:"Reviewed full product overview.",audio:"/fixture/overview.wav",slide_id:"proof",fact_ids:["F1"]};
  const start=vm.runInNewContext(startSource+"\nstartAfterIntake",{S:state,live:{},api:{pitch:()=>{calls.pitch++;return Promise.resolve(null);}},
    bundle:{runtime:{narration_minimum:180,overview}},slides:[base],showSlideView(){},opening:()=>[],heroOpen:()=>base,
    speak:async text=>{heard.push(text);return true;},buildRoute:route=>routes.push(route),playFrom:()=>calls.play++,el:{cite:{}},
    profileForServer:()=>state.profile,withTimeout:async promise=>promise});
  await start(1,"show me around",{phase:"opening"});
  check("generic initial tour keeps recorded overview and reviewed route without starting personalization",calls.pitch===0 && heard.length===1 && heard[0]===overview.text && routes[0]===null && calls.play===1 && state.overviewPlayed && state.planningDecided && state.personalized===false);
}
{
  const intakeSource=playerSource.slice(playerSource.indexOf("  async function runIntake("),playerSource.indexOf("  async function startAfterIntake("));
  for(const answer of ["show me around","It's"]){
    const state={run:1,profile:{customer_urls:[],focus:[]}},heard=[],calls={pitch:0,started:0};
    const classList={add(){},remove(){}};
    const intake=vm.runInNewContext(intakeSource+"\nrunIntake",{S:state,newRun:()=>1,el:{intake:{classList},inFallback:{classList},cite:{},inState:{}},
      bundle:{intake:{q1:"What matters to you?"}},guide:"Guide",live:{},showSlideView(){},heroOpen(){},
      speak:async text=>{heard.push(text);return true;},intakeWait:async()=>answer,intakeSites(){},genericTour:qualification.genericTour,meaningfulTranscript,
      addMsg(){},parseName:()=>"",parseFocus:()=>[],api:{pitch:()=>{calls.pitch++;return Promise.resolve(null);}},startAfterIntake:async()=>calls.started++});
    await intake();
    check(`generic or fragment intake ${JSON.stringify(answer)} never claims customer-specific focus`,state.genericTour && state.profile.why==="" && calls.pitch===0 && calls.started===1 && heard[1]==="Let me take you through the demo.");
  }
}
{
  const acceptSource=playerSource.slice(playerSource.indexOf("  function acceptTypedAnswer("),playerSource.indexOf("  function handlePlaybackCommand("));
  const accepted=[],state={intakeOpen:true,profile:{customer_urls:["https://www.example.com/product"]},intakeResolver:text=>accepted.push(text)},el={inState:{},inHeard:{}};
  let preferred=0;
  const accept=vm.runInNewContext(acceptSource+"\nacceptTypedAnswer",{S:state,el,meaningfulTranscript,handlePlaybackCommand:()=>false,preferTyping:()=>preferred++,resumeSession(){},Date});
  accept("");
  check("a URL-only intake submits without inventing preference text",accepted.length===1 && accepted[0]==="" && preferred===1 && state.lastListen.via==="typed");
  accept("It's");
  check("a URL does not turn a recognition fragment into preference evidence",accepted.length===1 && preferred===1 && el.inState.textContent.includes("choose Skip"));
  state.profile.customer_urls=[];accept("");
  check("empty intake without a customer URL still asks for input or Skip",accepted.length===1 && preferred===1);
}
// WP8: a selected text mode keeps streamed output while capture remains opt-in.
{
  const beforeCaptures = captures, beforeSockets = Socket.instances.length;
  const textClient = new LiveVoiceClient({ url: "/run/live", sessionId: "text-mode", env });
  await textClient.setMicEnabled(false);
  const socket = textClient.socket;
  check("Voice mode off explicitly connects text transport without requesting microphone", captures === beforeCaptures && textClient.ready && Socket.instances.length === beforeSockets + 1 && socket.sent.some(event => event.type === "session.start" && event.input_mode === "text") && socket.sent.some(event => event.type === "mic.set" && event.enabled === false && event.input_mode === "text"));
  const speakAndFinish = async text => {
    const promise = textClient.speak(text); await tick(); const delivery = textClient.delivery;
    textClient.receive({type:"audio.chunk",turn_id:delivery.turnId,utterance_id:delivery.utteranceId,seq:0,audio,sample_rate:24000,format:"pcm_s16le"});
    const source = Context.sources.at(-1); textClient.receive({type:"audio.end",turn_id:delivery.turnId,utterance_id:delivery.utteranceId}); source.onended();
    return promise;
  };
  check("text mode plays streamed speech without capture", await speakAndFinish("The narrated detail remains available.") && captures === beforeCaptures && !textClient.mic);
  await textClient.setMicEnabled(true); textClient.receive({type:"mic.ready",input_generation:textClient.inputGeneration});
  const capture = textClient.stream;
  for (let index=0; index<3; index++) {
    const promise = textClient.ask({question:"Turn " + index}); await tick(); const owner = textClient.pending.turnId;
    textClient.receive({type:"turn.result",turn_id:owner,answer:{answered:true,answer:"Reviewed answer " + index}}); await promise;
    await speakAndFinish("Reviewed answer " + index);
  }
  check("Voice mode on opens one microphone and retains it across three full turns", captures === beforeCaptures + 1 && textClient.mic && textClient.stream === capture && !capture.getTracks()[0].stopped);
  check("capture reports selected voice mode to the server", socket.sent.some(event => event.type === "mic.set" && event.enabled && event.input_mode === "voice") && textClient.inputMode === "voice");
  textClient.stopCapture();
  check("mid-demo Voice mode off releases capture and retains the same speech socket", capture.getTracks()[0].stopped && textClient.socket === socket && textClient.ready && textClient.inputMode === "text" && socket.sent.at(-1).input_mode === "text");
  await speakAndFinish("The next detail still plays.");
  await textClient.startCapture(); textClient.receive({type:"mic.ready",input_generation:textClient.inputGeneration});
  check("mid-demo Voice mode on reacquires capture without reconnecting", captures === beforeCaptures + 2 && textClient.socket === socket && Socket.instances.length === beforeSockets + 1 && textClient.mic);
  const offCommands = socket.sent.filter(event=>event.type === "mic.set" && !event.enabled).length;
  textClient.close();
  check("session teardown releases microphone without relabelling selected voice mode", textClient.inputMode === "voice" && !textClient.mic && socket.sent.filter(event=>event.type === "mic.set" && !event.enabled).length === offCommands);
}
{
  const beforeCaptures = captures;
  const muted = new LiveVoiceClient({url:"/run/live",sessionId:"muted-text",env}); muted.setMuted(true); await muted.setMicEnabled(false); await muted.unlockOutput();
  check("muted review still opens no capture and keeps streamed output gain at zero", captures === beforeCaptures && muted.gain.gain.value === 0 && muted.ready && muted.inputMode === "text"); muted.close();
}
{
  let resume; const beforeCaptures = captures, beforeSockets = Socket.instances.length;
  class DeferredContext extends Context { resume() { return new Promise(resolve => {resume=resolve;}); } }
  const stopped = new LiveVoiceClient({url:"/run/live",sessionId:"stopped-before-permission",env:{...env,AudioContext:DeferredContext}});
  const pending = stopped.startCapture(); await tick(); stopped.stopCapture(); resume();
  check("switching off before context resume prevents a later microphone permission request", await pending === false && captures === beforeCaptures && Socket.instances.length === beforeSockets); stopped.close();
}
{
  let grant; const beforeSockets = Socket.instances.length;
  const abandoned = new LiveVoiceClient({url:"/run/live",sessionId:"closed-permission",env:{...env,navigator:{mediaDevices:{getUserMedia:()=>new Promise(resolve=>{grant=resolve;})}}}});
  const pending = abandoned.startCapture(); await tick(); abandoned.close(); const late = stream(); grant(late);
  check("permission granted after close releases the track without reopening an orphan socket", await pending === false && late.getTracks()[0].stopped && Socket.instances.length === beforeSockets && abandoned.closed);
}
{
  const denied = new LiveVoiceClient({url:"/run/live",sessionId:"permission-denied",env:{...env,navigator:{mediaDevices:{getUserMedia:async()=>{throw Object.assign(new Error("Denied"),{name:"NotAllowedError"});}}}}});
  await denied.setMicEnabled(false); const socket = denied.socket;
  check("denied microphone leaves the established text speech transport available", await denied.startCapture() === false && !denied.mic && denied.ready && denied.socket === socket && denied.inputMode === "text"); denied.close();
}
{
  const dropped = new LiveVoiceClient({url:"/run/live",sessionId:"capture-disconnected",env});
  await dropped.startCapture(); const track = dropped.stream.getTracks()[0]; dropped.socket.close();
  check("unexpected disconnect falls back to text mode while releasing active capture", dropped.inputMode === "text" && !dropped.mic && track.stopped && !dropped.ready); dropped.close();
}
{
  const starts = [], heard = [];
  const noise = new LiveVoiceClient({url:"/run/live",sessionId:"noise-guard",env,onSpeechStart:event=>{starts.push(event);noise.interrupt({preservePlanning:true});},onTranscript:event=>heard.push(event)});
  await noise.startCapture(); noise.receive({type:"mic.ready",input_generation:noise.inputGeneration});
  const reading = noise.speak("Keep this narration playing."); await tick(); const owner = noise.delivery;
  noise.receive({type:"audio.chunk",turn_id:owner.turnId,utterance_id:owner.utteranceId,seq:0,audio});
  const playing = Context.sources.at(-1), sentBefore = noise.socket.sent.filter(event=>event.type==="turn.interrupt").length;
  for (let index=0;index<8;index++) noise.worklet.port.onmessage({data:{pcm:new Int16Array(320).buffer,rms:0.6}});
  noise.worklet.port.onmessage({data:{pcm:new Int16Array(320).buffer,rms:0}});
  noise.receive({type:"input.speech_start",input_generation:noise.inputGeneration,input_id:"impact"});
  noise.receive({type:"input.speech_end",input_generation:noise.inputGeneration,input_id:"impact"});
  noise.receive({type:"transcript.partial",input_generation:noise.inputGeneration,input_id:"impact",text:"[noise]"});
  noise.receive({type:"transcript.final",input_generation:noise.inputGeneration,input_id:"impact",text:"..."});
  check("cup impulse, raw VAD and noise-only transcripts preserve active narration",noise.delivery===owner && !playing.stopped && starts.length===0 && heard.length===0 && noise.socket.sent.filter(event=>event.type==="turn.interrupt").length===sentBefore);
  noise.receive({type:"transcript.partial",input_generation:noise.inputGeneration,input_id:"question",text:"Warranty"});
  check("a meaningful partial may preview words but cannot interrupt narration",starts.length===0 && !playing.stopped && noise.delivery===owner && heard.at(-1).text==="Warranty" && !heard.at(-1).final);
  noise.receive({type:"input.speech_start",input_generation:noise.inputGeneration,input_id:"question"});
  noise.receive({type:"transcript.final",input_generation:noise.inputGeneration,input_id:"question",text:"Warranty?"});
  check("short qualified warranty final interrupts exactly once",starts.length===1 && starts[0].source==="final" && playing.stopped && noise.delivery===null && await reading===false && heard.at(-1).final);
  const nextReading = noise.speak("The next reviewed line."); await tick(); const nextOwner = noise.delivery;
  noise.receive({type:"transcript.final",input_generation:noise.inputGeneration,input_id:"question",text:"Warranty?"});
  check("a duplicated final cannot interrupt the next owned narration",noise.delivery===nextOwner && starts.length===1);
  noise.receive({type:"input.speech_start",input_generation:noise.inputGeneration,input_id:"short"});
  noise.receive({type:"input.speech_end",input_generation:noise.inputGeneration,input_id:"short",voice_ended:456});
  const endedAt = noise.endpointAt;
  noise.receive({type:"transcript.final",input_generation:noise.inputGeneration,input_id:"short",text:"हाँ"});
  check("short final-only speech interrupts and preserves its endpoint timing",starts.length===2 && starts.at(-1).source==="final" && await nextReading===false && heard.at(-1).text==="हाँ" && heard.at(-1).endpoint_received_at===endedAt && heard.at(-1).server_endpoint_received_at===456);
  const explicit = noise.speak("Explicit controls remain immediate."); await tick(); noise.interrupt();
  check("explicit interruption still cancels without transcript confirmation",await explicit===false && noise.mic);
  check("speech confirmation keeps words and numbers while discarding annotations",["yes","हाँ","20","stop","[noise] warranty"].every(meaningfulTranscript) && ["","   ","...","[noise]","(silence)","<inaudible>","[background noise]","It's","It’s","It is","The","uh"].every(text=>!meaningfulTranscript(text)));
  noise.close();
}
{
  const starts = [], finals = [], rejected = [];
  const qualified = new LiveVoiceClient({url:"/run/live",sessionId:"qualified-noise",env,
    qualifyInput:text=>{const ok=!/breaking news|weather forecast/i.test(text);if(!ok)rejected.push(text);return ok;},
    onSpeechStart:event=>{starts.push(event);qualified.interrupt();},onTranscript:event=>{if(event.final)finals.push(event);}});
  await qualified.startCapture(); qualified.receive({type:"mic.ready",input_generation:qualified.inputGeneration});
  const read=qualified.speak("Keep showing the reviewed product details."); await tick(); const owner=qualified.delivery;
  qualified.receive({type:"audio.chunk",turn_id:owner.turnId,utterance_id:owner.utteranceId,seq:0,audio});
  const playing=Context.sources.at(-1), input=qualified.inputGeneration;
  qualified.receive({type:"transcript.partial",input_generation:input,input_id:"fragment",text:"It’s"});
  qualified.receive({type:"transcript.final",input_generation:input,input_id:"fragment",text:"[noise]"});
  check("recognition fragment It’s followed by noise creates no turn or audio cancellation",qualified.delivery===owner && !playing.stopped && starts.length===0 && finals.length===0);
  qualified.receive({type:"transcript.final",input_generation:input,input_id:"tv",text:"Breaking news and the weather forecast"});
  check("application qualifier rejects unrelated TV final without taking playback ownership",rejected.length===1 && starts.length===0 && finals.length===0 && qualified.delivery===owner && !playing.stopped);
  qualified.receive({type:"transcript.final",input_generation:input,input_id:"wanted",text:"Warranty?"});
  check("qualifier keeps a short relevant question actionable",starts.length===1 && finals.length===1 && finals[0].text==="Warranty?" && await read===false);
  qualified.receive({type:"transcript.final",input_generation:input,text:"yes"}); qualified.receive({type:"transcript.final",input_generation:input,text:"yes"});
  check("qualification never deduplicates separate unowned yes replies by text",finals.filter(event=>event.text==="yes").length===2);
  qualified.close();
}
{
  const starts=[],finals=[];
  const controls=new LiveVoiceClient({url:"/run/live",sessionId:"local-controls",env,shouldInterrupt:text=>!qualification.playbackCommand(text),onSpeechStart:event=>{starts.push(event);controls.interrupt();},onTranscript:event=>{if(event.final)finals.push(event.text);}});
  await controls.startCapture(); controls.receive({type:"mic.ready",input_generation:controls.inputGeneration});
  const reading=controls.speak("Current narration keeps its audio owner."); await tick(); const owner=controls.delivery;
  controls.receive({type:"audio.chunk",turn_id:owner.turnId,utterance_id:owner.utteranceId,seq:0,audio}); const playing=Context.sources.at(-1);
  controls.receive({type:"transcript.final",input_generation:controls.inputGeneration,input_id:"continue",text:"Continue"});
  check("Continue is delivered as a local command without pre-cancelling narration",finals[0]==="Continue" && starts.length===0 && controls.delivery===owner && !playing.stopped);
  controls.receive({type:"transcript.final",input_generation:controls.inputGeneration,input_id:"question",text:"Warranty?"});
  check("a genuine query still interrupts after a non-interrupting local command",starts.length===1 && finals.at(-1)==="Warranty?" && await reading===false);
  controls.close();
}
// Production timeout code with an explicit clock and scheduled fake PCM. This
// proves healthy speech can last over thirty seconds without a wall-clock wait.
function timedVoice() {
  const clock={now:0,serial:0,timers:new Map(),set(fn,ms){const id=++this.serial;this.timers.set(id,{at:this.now+ms,fn});return id;},clear(id){this.timers.delete(id);},
    advance(ms){const end=this.now+ms;for(;;){const next=[...this.timers].filter(([,t])=>t.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;this.timers.delete(next[0]);this.now=next[1].at;next[1].fn();}this.now=end;}};
  class TimedSource extends Node { start(at){this.timer=clock.set(()=>this.onended?.(),Math.max(0,(at+this.buffer.duration)*1000-clock.now));} stop(){clock.clear(this.timer);this.stopped=true;} }
  class TimedContext extends Context {constructor(){super();Object.defineProperty(this,"currentTime",{get:()=>clock.now/1000});}createBufferSource(){const node=new TimedSource();Context.sources.push(node);return node;}}
  const {LiveVoiceClient:TimedClient}=vm.runInNewContext(source.replace(/export /g,"")+"\n({LiveVoiceClient})",{
    URL,atob,btoa,Date:{now:()=>clock.now},setTimeout:(fn,ms)=>clock.set(fn,ms),clearTimeout:id=>clock.clear(id),queueMicrotask});
  const client=new TimedClient({url:"/run/live",sessionId:"deadline-fixture",env:{...env,AudioContext:TimedContext}});
  return {client,clock};
}
{
  const {client:timed,clock}=timedVoice(); let completed=false;
  const spoken=timed.speak("A healthy extended narration.").then(result=>{completed=result;return result;}); await tick(); const owner=timed.delivery;
  const longAudio=Buffer.alloc(16000*2*45).toString("base64");
  timed.receive({type:"audio.chunk",turn_id:owner.turnId,utterance_id:owner.utteranceId,seq:0,audio:longAudio,sample_rate:16000,format:"pcm_s16le"});
  timed.receive({type:"audio.end",turn_id:owner.turnId,utterance_id:owner.utteranceId});
  clock.advance(31000); await tick();
  check("healthy scheduled narration remains owned after the old thirty-second cutoff",!completed && timed.delivery===owner && owner.sources.size===1);
  clock.advance(15000);
  check("healthy forty-five-second narration completes after local audio drains",await spoken===true && timed.delivery===null);
  timed.close();
}
{
  const {client:timed,clock}=timedVoice(); const stalled=timed.speak("Caption fallback must preserve this answer.").catch(error=>error); await tick();
  clock.advance(31000); const failure=await stalled;
  check("stream that never starts rejects with a non-cancellation error for caption fallback",failure.message==="Speech stream timed out" && failure.name!=="AbortError" && failure.audioStarted===false && timed.delivery===null);
  timed.close();
}
{
  const {client:timed,clock}=timedVoice(); const missingEnd=timed.speak("A closing sentence with a missing provider end.").catch(error=>error); await tick(); const owner=timed.delivery;
  timed.receive({type:"audio.chunk",turn_id:owner.turnId,utterance_id:owner.utteranceId,seq:0,audio,sample_rate:24000});
  clock.advance(1000); check("local chunk ending alone cannot fabricate provider completion",timed.delivery===owner && owner.sources.size===0 && !owner.ended);
  clock.advance(31000); const failure=await missingEnd;
  check("missing provider end becomes an owned delivery failure instead of swallowing closing",failure.message==="Speech stream timed out" && failure.audioStarted===true && !timed.delivery);
  timed.close();
}
{
  const {client:timed,clock}=timedVoice(); const speech=timed.speak("An obsolete line cannot return."); await tick(); const owner=timed.delivery, timeout=clock.timers.get(owner.timer).fn;
  timed.interrupt(); timeout(); clock.advance(60000);
  check("cancelled stream ignores even a late timeout callback and never revives",await speech===false && !timed.delivery);
  timed.close();
}
console.log(`Live voice: ${passes}/${passes} passed (fake devices and transports only)`);
