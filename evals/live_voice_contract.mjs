// Free fake-device/transport checks; no browser microphone, server or provider call.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
const source = fs.readFileSync(new URL("../web/player/live-voice.js", import.meta.url), "utf8");
const { LiveVoiceClient, pcmToFloat } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
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
check("partial and VAD onset share one human turn", onsets.length === 1);
client.receive({ input_generation: client.inputGeneration, type: "input.speech_end", input_id: "a", voice_ended: 123 });
const endpointReceived = client.endpointAt;
client.receive({ input_generation: client.inputGeneration, type: "transcript.final", input_id: "a", text: "boot space" });
client.receive({ input_generation: client.inputGeneration, type: "transcript.final", input_id: "a", text: "boot space" });
check("final transcript is delivered once using the browser receipt clock", transcripts.filter(e => e.final).length === 1 && transcripts.at(-1).voice_ended === endpointReceived && transcripts.at(-1).speech_end_basis === "browser_endpoint_receipt");
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
  const state = { run: 1 }, qa = deferred(), filler = deferred(), calls = { cancel: 0, filler: 0, status: 0 };
  const result = vm.runInNewContext(resultSource + "\nquestionResult", { S: state, withTimeout: async () => null,
    speakF() { calls.filler++; return filler.promise; }, cancelSpeech() { calls.cancel++; }, setStatus() { calls.status++; } });
  return { state, qa, filler, calls, result };
}
{
  const h = questionHarness(), turn = {}; const result = h.result(h.qa.promise, 1, turn); await tick(); h.state.onFirstAudio(100);
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
check("legacy script checkin strings cannot erase the reviewed question wait", routeState.plan[0].slide.checkin === base.checkin);
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
console.log(`Live voice: ${passes}/${passes} passed (fake devices and transports only)`);
