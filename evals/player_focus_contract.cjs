// Free behavior checks for the actual nested player focus parser, without a browser/provider.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
const start = source.indexOf('  function parseFocus(t) {');
const end = source.indexOf('\n  function withTimeout', start);
if (start < 0 || end < 0) throw new Error('Cannot locate player parseFocus implementation');
const chips = [
  { key: 'safety', label: 'Safety equipment' },
  { key: 'performance', label: 'Engines & Gearboxes' },
  { key: 'practicality', label: 'Boot & Space' },
  { key: 'comfort', label: 'Cabin Comfort' },
  { key: 'technology', label: 'Tech & Cameras' },
  { key: 'ownership', label: 'Pricing & Terms' },
];
const slides = [
  { title: 'Safety starts with the details', topics: ['safety'] },
  { title: 'Space for what matters', topics: ['practicality'] },
  { title: 'Know the ownership details', topics: ['ownership'] },
];
function parser(intakeChips = chips, librarySlides = slides) {
  return vm.runInNewContext(`${source.slice(start, end)}\nparseFocus`, {
    bundle: { intake: { chips: intakeChips } }, library: () => librarySlides,
    topicOf: sl => sl.topics?.[0] || sl.segment_id || sl.id,
  });
}
const focus = text => Array.from(parser()(text));
const part = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
const defaultMode = vm.runInNewContext(part('function defaultVoiceMode(', '// Build one interactive demo') + '\ndefaultVoiceMode');
function modePlayer(selected = false, liveSession = true) {
  const S = {voiceMode: selected, inputMode: selected ? 'voice' : 'typed', micOn: false, sessionId: 'mode-fixture', started: 0,
    visited: [], plan: [], seg: 0, covered: new Set(), resolved: new Set(), unresolved: new Set(), raised: new Set()};
  const calls = {connect: 0, capture: 0, stop: 0, disabled: 0, cancelWindow: 0, stopListening: 0};
  const live = liveSession ? {mic: false, unlockOutput: () => Promise.resolve(), connect: () => {calls.connect++; return Promise.resolve();},
    startCapture: () => {calls.capture++; live.mic = true; return Promise.resolve(true);}, stopCapture: () => {calls.stop++; live.mic = false;},
    setMicEnabled: enabled => {if (!enabled) calls.disabled++; return Promise.resolve(enabled);}} : null;
  const code = part('  function startLive(', '  // ---------- helpers ----------') + '\n' + part('  function preferTyping()', '  // Accept typed words')
    + '\n' + part('  function micTap()', '  // Offer reply choices') + '\n' + part('  function sessionRecord()', '  // Reopen a completed visit')
    + '\n({startLive,preferTyping,micTap,sessionRecord})';
  const api = vm.runInNewContext(code, {S, live, bundle: {}, cur: null, slides: [], sessionNow: () => 0, intentScore: () => 20,
    el: {voiceMode: {checked: selected}, hint: {}}, setMicUI() {}, cancelPostAnswerListen: () => calls.cancelWindow++,
    stopListening: () => calls.stopListening++, resumeSession() {}, intakeMic() {}, listenForTurn() {}, listenForQuestion() {}});
  return {S, calls, api};
}
const b = 'I am comparing the Nexon Fearless+PS petrol 7DCA with the Brezza ZXi+ petrol 6AT and the regular Venue HX10 turbo petrol 7DCT. I want an automatic family car and care about what these exact variants include.';
const cases = [
  ['exact B intake does not invent safety priority from with', () => !focus(b).includes('safety')],
  ['exact B intake retains explicitly requested automatic topic', () => focus(b).includes('performance')],
  ['incidental slide-title words do not become customer focus', () => focus('I want the details with those exact variants.').length === 0],
  ['explicit safety still routes to safety', () => JSON.stringify(focus('Safety matters to me.')) === '["safety"]'],
  ['explicit boot still routes to practicality', () => JSON.stringify(focus('I want to see the boot.')) === '["practicality"]'],
  ['explicit running costs still route to ownership', () => JSON.stringify(focus('I care about running costs.')) === '["ownership"]'],
  ['stroller is an explicit practicality term, with is not safety', () => JSON.stringify(focus('We travel with a stroller.')) === '["practicality"]'],
  ['whole words prevent accidental topic substring matches', () => focus('It is a safetyish impracticality ownershipish question.').length === 0],
  ['punctuation and case preserve explicit matching', () => JSON.stringify(focus('BOOT; SAFETY!')) === '["safety","practicality"]'],
  ['configured labels support other products without slide-title inference', () => {
    const p = parser([{ key: 'battery', label: 'Battery & Range' }], [{ title: 'Built for your routine', topics: ['battery'] }]);
    return JSON.stringify(Array.from(p('I care about range.'))) === '["battery"]' && p('My routine is short.').length === 0;
  }],
  ['configured multiword topic matches as a phrase', () => JSON.stringify(Array.from(parser([{ key: 'fuel_economy', label: 'Fuel economy' }], [])('Tell me about fuel economy.'))) === '["fuel_economy"]'],
  ['configured Hindi phrase remains matchable', () => JSON.stringify(Array.from(parser([{ key: 'safety', label: 'सुरक्षा' }], [])('मुझे सुरक्षा चाहिए'))) === '["safety"]'],
  ['voice mode defaults on only for a continuous voice bundle', () => defaultMode({runtime: {continuous_voice: true}}, false) && !defaultMode({}, false) && !defaultMode({runtime: {continuous_voice: false}}, false)],
  ['muted automation overrides the continuous voice default', () => !defaultMode({runtime: {continuous_voice: true}}, true)],
  ['text mode connects output and explicitly disables the microphone without capture', () => {const t = modePlayer(); t.api.startLive(); return t.calls.connect === 1 && t.calls.disabled === 1 && t.calls.capture === 0 && !t.S.voiceMode;}],
  ['voice mode start requests capture once', () => {const t = modePlayer(true); t.api.startLive(); return t.calls.connect === 1 && t.calls.capture === 1 && t.calls.disabled === 0 && t.S.voiceMode;}],
  ['bar toggle turns capture on and off without reconnecting the socket', () => {const t = modePlayer(); t.api.micTap(); const on = t.S.voiceMode; t.api.micTap(); return on && !t.S.voiceMode && t.calls.capture === 1 && t.calls.stop === 1 && t.calls.connect === 0;}],
  ['typing during continuous voice cancels answer timing but keeps selected voice mode and capture', () => {const t = modePlayer(true); t.api.preferTyping(); return t.S.voiceMode && t.S.inputMode === 'voice' && t.calls.cancelWindow === 1 && t.calls.stop === 0 && t.calls.stopListening === 0;}],
  ['legacy typing pauses one-shot listening while retaining the chosen visit mode', () => {const t = modePlayer(true, false); t.api.preferTyping(); return t.S.voiceMode && t.S.inputMode === 'typed' && t.calls.stopListening === 1;}],
  ['legacy restart preserves typing preference until an explicit microphone tap', () => {const t = modePlayer(true, false); t.api.preferTyping(); t.api.startLive(); const typed = t.S.inputMode === 'typed'; t.api.micTap(); return typed && t.S.voiceMode && t.S.inputMode === 'voice';}],
  ['session records selected mode without rewriting per-turn input source', () => {const t = modePlayer(true); t.S.turns = [{via: 'typed', input_source: 'typed'}]; const voice = t.api.sessionRecord(); t.api.micTap(); const text = t.api.sessionRecord(); return voice.input_mode === 'voice' && text.input_mode === 'text' && voice.turns[0].input_source === 'typed';}],
];
let passed = 0;
for (const [name, test] of cases) {
  let ok = false; try { ok = !!test(); } catch (error) { console.error(error); }
  console.log(`${ok ? 'PASS' : 'FAIL'} focus: ${name}`); passed += Number(ok);
}
console.log(`Player focus contracts: ${passed}/${cases.length} (real function; no UI/network/providers)`);
process.exitCode = passed === cases.length ? 0 : 1;
