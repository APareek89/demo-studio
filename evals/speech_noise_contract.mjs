// Actual qualification/capture functions with fake devices and transport only.
// No microphone, provider, network, stored demo or production session is used.
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import net from "node:net";
import tls from "node:tls";
net.connect = net.createConnection = net.Socket.prototype.connect = tls.connect = () => { throw new Error("Sockets blocked for speech-noise contract"); };
globalThis.fetch = () => { throw new Error("Network blocked for speech-noise contract"); };
const liveSource = fs.readFileSync(new URL("../web/player/live-voice.js", import.meta.url), "utf8");
const playerSource = fs.readFileSync(new URL("../web/player/player.js", import.meta.url), "utf8");
const { LiveVoiceClient, meaningfulTranscript } = await import("data:text/javascript;base64," + Buffer.from(liveSource).toString("base64"));
const part = (source, start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
const helpers = vm.runInNewContext(part(playerSource, "function playbackCommand(", "function defaultVoiceMode(") + "\n({qualifiesCustomerSpeech,playbackCommand})", { meaningfulTranscript });
let count = 0;
async function check(name, run) { await run(); count++; console.log("PASS", name); }
const sounds = ["[clears throat]", "(clearing throat)", "<throat-clearing>", "[throat clearing]?", "[coughing]?", "(coughs)", "Ahem?", "Cough?", "Ah…", "uh, um?", "Hmmm?", "Mmm.", "'Ahem?'", "Clears throat."];

await check("sound descriptions and standalone vocalizations are not customer speech", () => {
  for (const sound of sounds) assert.equal(meaningfulTranscript(sound), false, sound);
});
await check("question punctuation cannot promote a throat sound into a customer question", () => {
  for (const sound of sounds) for (const prompt of [false, true]) assert.equal(helpers.qualifiesCustomerSpeech(sound, { prompt, terms: ["creta", "throat"] }), false, sound);
});
await check("a real question survives an adjacent sound annotation", () => {
  for (const text of ["[clears throat] Warranty?", "Ahem, what is the boot space?", "[coughing] क्या इसमें सनरूफ है?"]) assert(helpers.qualifiesCustomerSpeech(text, { terms: ["warranty"] }), text);
});
await check("short commands and feature questions remain actionable", () => {
  for (const text of ["Continue", "Pause", "Stop", "Not now", "Warranty?", "Automatic?", "Huh?"]) assert(helpers.qualifiesCustomerSpeech(text), text);
});
await check("meaningful intake and supported-language questions survive", () => {
  for (const text of ["I need room for my family", "Show me around", "क्या इसमें सनरूफ है?", "இதில் எத்தனை இருக்கைகள் உள்ளன?", "9876543210", "हाँ"]) assert(helpers.qualifiesCustomerSpeech(text, { prompt: true }), text);
  assert(!helpers.qualifiesCustomerSpeech("हाँ", { prompt: false }));
});

const cancelled = [], onsets = [], finals = [];
const client = new LiveVoiceClient({ url: "/unused", sessionId: "noise-contract", qualifyInput: text => helpers.qualifiesCustomerSpeech(text, { prompt: true, terms: ["warranty"] }), shouldInterrupt: text => !helpers.playbackCommand(text), onSpeechStart: event => onsets.push(event), onTranscript: event => { if (event.final) finals.push(event); } });
client.mic = true; client.inputGeneration = 4;
client.cancelAudio = () => cancelled.push(true);
const deliver = (text, id, type = "transcript.final", generation = 4) => client.receive({ type, text, input_id: id, input_generation: generation });
await check("raw onset and throat-clearing partial/final never cancel active output", () => {
  client.receive({ type: "input.speech_start", input_generation: 4, input_id: "noise" });
  for (const [index, text] of sounds.entries()) { deliver(text, `noise-${index}`, "transcript.partial"); deliver(text, `noise-${index}`); }
  assert.equal(cancelled.length, 0); assert.equal(onsets.length, 0); assert.equal(finals.length, 0);
});
await check("next real final after ignored sounds interrupts exactly once", () => {
  deliver("Warranty?", "question");
  assert.equal(cancelled.length, 1); assert.equal(onsets.length, 1); assert.equal(finals[0].text, "Warranty?");
});
await check("duplicate and stale finals do not steal the next output owner", () => {
  deliver("Warranty?", "question"); deliver("Warranty?", "stale", "transcript.final", 3);
  assert.equal(cancelled.length, 1); assert.equal(finals.length, 1);
});
await check("Continue remains local and cannot cause an unnecessary speech interruption", () => {
  deliver("Continue", "control"); assert.equal(cancelled.length, 1); assert.equal(finals.at(-1).text, "Continue");
});

const legacySource = part(playerSource, "  async function listenServer(", "  // Start a fresh listening attempt");
function legacyFixture(answer) {
  let now = 1000, processor, endCapture, nextTimer = 1;
  const timers = new Map(), track = { stopped: false, stop() { this.stopped = true; } };
  const state = { listenId: 1, intakeOpen: false, lastListen: null, postAnswerListen: { timer: "resume-in-three-seconds" } };
  const calls = { cancel: 0, stt: 0, states: [] };
  const node = () => ({ connect() {}, disconnect() {} });
  class Context { constructor() { this.sampleRate = 16000; this.destination = {}; } createMediaStreamSource() { return node(); } createScriptProcessor() { return processor = node(); } close() { return Promise.resolve(); } }
  const context = { S: state, LANG: "en-IN", speechTerms: ["warranty"], qualifiesCustomerSpeech: helpers.qualifiesCustomerSpeech, meaningfulTranscript,
    navigator: { mediaDevices: { getUserMedia: async () => ({ getTracks: () => [track] }) } },
    window: { AudioContext: Context }, Date: { now: () => now }, el: { inState: {} }, setMicUI() {},
    setStatus: (...args) => calls.states.push(args), cancelPostAnswerListen: () => { calls.cancel++; state.postAnswerListen = null; },
    setTimeout: (fn, ms) => { const id = nextTimer++; timers.set(id, { fn, ms, at: now + ms }); return id; }, clearTimeout: id => timers.delete(id),
    encodeWav: chunks => { assert(chunks.length); return "synthetic-recording"; },
    api: { stt: async () => { calls.stt++; return typeof answer === "function" ? answer() : answer; } }, SR: null, addMsg() {} };
  const capture = vm.runInNewContext(legacySource + "\nlistenServer", context);
  return { state, calls, track, timers, context,
    async start() { const result = capture({}, 1); for (let i = 0; i < 12 && !state.finishListen; i++) await Promise.resolve(); endCapture = state.finishListen; assert.equal(typeof endCapture, "function"); return { result }; },
    sound() { now += 20; processor.onaudioprocess({ inputBuffer: { getChannelData: () => new Float32Array(320).fill(0.5) } }); },
    finish() { return (endCapture || state.finishListen)(); },
    async advance(ms) { const end = now + ms; await flush(); for (;;) { const job = [...timers].filter(([, value]) => value.at <= end).sort((a, b) => a[1].at - b[1].at)[0]; if (!job) break; now = job[1].at; timers.delete(job[0]); job[1].fn(); await flush(); } now = end; await flush(); } };
}
async function flush() { for (let i = 0; i < 30; i++) await Promise.resolve(); }
await check("legacy high-energy noise leaves the three-second resume owner intact", async () => {
  const f = legacyFixture("[clears throat]"); const { result } = await f.start();
  const owner = f.state.postAnswerListen; f.sound();
  assert.equal(f.calls.cancel, 0); assert.equal(f.state.postAnswerListen, owner);
  await f.finish(); assert.equal(await result, ""); assert.equal(f.state.postAnswerListen, owner);
});
await check("legacy rejected final creates no input timing record and releases microphone", async () => {
  const f = legacyFixture("Ahem?"); const { result } = await f.start(); f.sound(); await f.finish();
  assert.equal(await result, ""); assert.equal(f.state.lastListen, null); assert.equal(f.calls.cancel, 0); assert(f.track.stopped); assert.equal(f.timers.size, 0);
});
await check("legacy silence does not call STT or cancel resume", async () => {
  const f = legacyFixture("unused"); const { result } = await f.start(); await f.finish();
  assert.equal(await result, ""); assert.equal(f.calls.stt, 0); assert.equal(f.calls.cancel, 0);
});
await check("legacy relevant final takes the reply only after it is recognized", async () => {
  let resolve; const f = legacyFixture(() => new Promise(r => { resolve = r; })); const { result } = await f.start(); f.sound();
  const pending = f.finish(); await Promise.resolve(); assert.equal(f.calls.cancel, 0); assert(f.state.postAnswerListen);
  resolve("Warranty?"); await pending; assert.equal(await result, "Warranty?"); assert.equal(f.calls.cancel, 1); assert.equal(f.state.lastListen.via, "server");
});
await check("legacy intake preserves a short real answer", async () => {
  const f = legacyFixture("हाँ"); f.state.intakeOpen = true; const { result } = await f.start(); f.sound(); await f.finish();
  assert.equal(await result, "हाँ"); assert.equal(f.calls.cancel, 1);
});
await check("deliberate server capture keeps names, locations and freeform household replies", async () => {
  for (const text of ["Mumbai", "Anand Pareek", "Two adults and two children"]) {
    const f = legacyFixture(text); f.state.intakeOpen = true; const { result } = await f.start(); f.sound(); await f.finish();
    assert.equal(await result, text); assert.equal(f.calls.cancel, 1); assert.equal(f.state.lastListen.via, "server");
  }
});
await check("a late legacy final after cancellation cannot revoke resume or write timing", async () => {
  let resolve; const f = legacyFixture(() => new Promise(r => { resolve = r; })); const { result } = await f.start(); f.sound();
  const pending = f.finish(); await Promise.resolve(); f.state.cancelListen(); f.state.listenId = 2;
  resolve("Warranty?"); await pending;
  assert.equal(await result, ""); assert.equal(f.calls.cancel, 0); assert.equal(f.state.lastListen, null); assert(f.state.postAnswerListen);
});

function replyWindowFixture(answer) {
  const f = legacyFixture(answer), { state: S, context, calls } = f;
  Object.assign(S, { run: 1, sessionId: "same-visit", inputMode: "voice", voiceMode: true, micDenied: false, ended: false, postAnswerListen: null });
  const quiet = () => {}, classes = { contains: () => false, remove: quiet }, field = { value: "", focus: quiet };
  Object.assign(calls, { resumed: [], questions: [], controls: [] });
  Object.assign(context, { live: null, serverSTT: true, bundle: { ctas: [] }, POST_ANSWER_LISTEN_MS: 3000,
    el: { ...context.el, live: {}, cite: {}, hint: {}, timer: { replaceChildren: quiet }, lead: { classList: classes }, drawer: { classList: classes }, q: field, reply: field, film: { pause: quiet } },
    canListen: () => true, clearInterval: context.clearTimeout, setChips: quiet, meaningfulTranscript,
    replyForTurn: text => ({ value: "question", text }), addMsg: quiet,
    resumeAfterQA: opts => { calls.resumed.push(opts); S.run++; },
    handleQuestion: text => calls.questions.push(text), handlePlaybackCommand: text => { const kind = helpers.playbackCommand(text); if (kind) calls.controls.push(kind); return !!kind; },
    ctaFlow: quiet, listenForQuestion: quiet, showLeadPrompt: quiet, newRun: () => ++S.run,
    presentation: { freeze: quiet }, root: { classList: classes }, cancelSpeech: quiet, setVoiceMode: enabled => { S.voiceMode = enabled; S.inputMode = enabled ? "voice" : "typed"; }, resumeSession: quiet, intakeMic: quiet,
    updateMuteUi: quiet });
  const code = [
    part(playerSource, "  function listen(opts", "  // Capture one turn with browser speech"),
    part(playerSource, "  function listenBrowser(", "  // Stop or finish legacy listening"),
    part(playerSource, "  function stopListening(", "  // Show whether the microphone"),
    part(playerSource, "  function cancelPostAnswerListen()", "  // Increment and return"),
    part(playerSource, "  function listenForTurn(", "  // Speak a question and wait"),
    part(playerSource, "  async function holdConversation(", "  // ---------- questions,"),
    part(playerSource, "  function preferTyping()", "  // Accept typed words"),
    part(playerSource, "  function interruptAll(", "  // Interpret customer words"),
    part(playerSource, "  function micTap()", "  // Offer reply choices"),
    part(playerSource, "  function toggleMute()", "  // Turn reply choices"),
  ].join("\n");
  f.api = vm.runInNewContext(code + "\n({holdConversation,resolveWait,stopListening,preferTyping,interruptAll,micTap,toggleMute})", context);
  context.playbackCommand = helpers.playbackCommand;
  f.api.command = vm.runInNewContext(part(playerSource, "  function handlePlaybackCommand(", "  // Open or close the conversation drawer") + "\nhandlePlaybackCommand", context);
  f.open = async () => { f.api.holdConversation(S.run); await flush(); assert(S.finishListen); };
  return f;
}
await check("an utterance extending beyond3s can finish after automatic resume", async () => {
  const f = replyWindowFixture("What does the warranty cover?"); await f.open(); await f.advance(2800); f.sound(); await f.advance(200);
  assert.equal(f.calls.resumed.length, 1); assert.equal(f.calls.resumed[0].automatic, true); assert(f.state.waiterVoice.autoResumed); assert(!f.track.stopped);
  await f.advance(500); f.sound(); await f.finish(); await flush();
  assert.deepEqual(f.calls.questions, ["What does the warranty cover?"]); assert(f.track.stopped); assert.equal(f.state.waiterVoice, null); assert.equal(f.timers.size, 0);
});
await check("an STT result already in flight at3s is delivered after resume", async () => {
  let resolve; const f = replyWindowFixture(() => new Promise(r => { resolve = r; })); await f.open(); f.sound(); const result = f.finish(); await flush();
  await f.advance(3000); assert.equal(f.calls.resumed.length, 1); resolve("Warranty?"); await result; await flush();
  assert.deepEqual(f.calls.questions, ["Warranty?"]); assert.equal(f.state.waiterVoice, null);
});
await check("a retained late server reply keeps freeform name/location/family wording", async () => {
  for (const text of ["Mumbai", "Anand Pareek", "Two adults and two children"]) {
    let resolve; const f = replyWindowFixture(() => new Promise(r => { resolve = r; })); await f.open(); f.sound(); const result = f.finish(); await flush();
    await f.advance(3000); assert.equal(f.calls.resumed.length, 1); resolve(text); await result; await flush();
    assert.deepEqual(f.calls.questions, [text]); assert.equal(f.state.waiterVoice, null);
  }
});
await check("noise can finish after resume without changing playback or UI status", async () => {
  const f = replyWindowFixture("Ahem?"); await f.open(); f.sound(); await f.advance(3000); const states = f.calls.states.length;
  await f.finish(); await flush(); assert.equal(f.calls.resumed.length, 1); assert.equal(f.calls.questions.length, 0); assert.equal(f.calls.states.length, states); assert.equal(f.state.waiterVoice, null);
});
await check("silence at3s ends capture and cannot start recording the resumed narration", async () => {
  const f = replyWindowFixture("unused"); await f.open(); await f.advance(3000);
  assert.equal(f.calls.resumed.length, 1); assert(f.track.stopped); assert.equal(f.calls.stt, 0); assert.equal(f.state.waiterVoice, null); assert.equal(f.timers.size, 0);
});
await check("a qualified final before the3s boundary takes the original reply exactly once", async () => {
  const f = replyWindowFixture("Warranty?"); await f.open(); f.sound(); await f.finish(); await flush(); await f.advance(3000);
  assert.deepEqual(f.calls.questions, ["Warranty?"]); assert.equal(f.calls.resumed.length, 0);
});
await check("an expired late-final deadline cancels capture without holding narration", async () => {
  let resolve; const f = replyWindowFixture(() => new Promise(r => { resolve = r; })); await f.open(); f.sound(); const result = f.finish(); await flush();
  await f.advance(15000); assert.equal(f.calls.resumed.length, 1); assert.equal(f.state.waiterVoice, null);
  resolve("Warranty?"); await result; await flush(); assert.equal(f.calls.questions.length, 0); assert.equal(f.state.lastListen, null);
});
for (const action of ["preferTyping", "interruptAll", "micTap", "toggleMute"]) {
  await check(`${action} cancels a late final after auto-resume`, async () => {
    let resolve; const f = replyWindowFixture(() => new Promise(r => { resolve = r; })); await f.open(); f.sound(); const result = f.finish(); await flush();
    await f.advance(3000); f.api[action](); resolve("Warranty?"); await result; await flush();
    assert.equal(f.calls.questions.length, 0); assert.equal(f.state.lastListen, null); assert.equal(f.state.waiterVoice, null); assert.equal(f.timers.size, 0);
  });
}
await check("a new wait/capture supersedes the old delayed final", async () => {
  const resolvers = []; const f = replyWindowFixture(() => new Promise(r => resolvers.push(r))); await f.open(); f.sound(); const first = f.finish(); await flush();
  await f.advance(3000); await f.open(); f.sound(); const second = f.finish(); await flush();
  resolvers[0]("The obsolete question?"); await first; await flush(); assert.equal(f.calls.questions.length, 0);
  resolvers[1]("Warranty?"); await second; await flush(); assert.deepEqual(f.calls.questions, ["Warranty?"]);
});
await check("an explicit Continue cancels the older pending spoken reply", async () => {
  let resolve; const f = replyWindowFixture(() => new Promise(r => { resolve = r; })); await f.open(); f.sound(); const result = f.finish(); await flush();
  await f.advance(3000); assert(f.api.command("Continue")); resolve("Warranty?"); await result; await flush();
  assert.equal(f.calls.questions.length, 0); assert.equal(f.state.waiterVoice, null);
});
await check("browser recognition can finish a real partial after automatic resume", async () => {
  const f = replyWindowFixture("unused");
  class Recognition { start() {} stop() { this.onend?.(); } abort() { this.aborted = true; this.onend?.(); } }
  f.context.serverSTT = false; f.context.SR = Recognition; await f.open();
  const rec = f.state.rec;
  const result = (text, final) => ({ results: [Object.assign([{ transcript: text }], { isFinal: final })] });
  rec.onresult(result("What does the warranty", false)); await f.advance(3000);
  assert.equal(f.calls.resumed.length, 1); assert(!rec.aborted);
  rec.onresult(result("What does the warranty cover?", true)); rec.onend(); await flush();
  assert.deepEqual(f.calls.questions, ["What does the warranty cover?"]); assert.equal(f.state.waiterVoice, null);
});
await check("browser noise partial cannot retain capture beyond the reply window", async () => {
  const f = replyWindowFixture("unused");
  class Recognition { start() {} stop() { this.onend?.(); } abort() { this.aborted = true; this.onend?.(); } }
  f.context.serverSTT = false; f.context.SR = Recognition; await f.open(); const rec = f.state.rec;
  rec.onresult({ results: [Object.assign([{ transcript: "Ahem?" }], { isFinal: false })] }); await f.advance(3000);
  assert(rec.aborted); assert.equal(f.calls.resumed.length, 1); assert.equal(f.calls.questions.length, 0); assert.equal(f.state.waiterVoice, null);
});
console.log(`Speech noise: ${count}/${count} passed (synthetic events, no acoustic acceptance claim)`);
