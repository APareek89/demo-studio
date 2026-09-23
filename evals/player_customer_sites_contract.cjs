// Execute actual URL and intake helpers with fake DOM; no browser, network or provider.
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
const part = (start, end) => {
  const from = source.indexOf(start), to = source.indexOf(end, from);
  assert(from >= 0 && to > from, `Missing helper: ${start}`);
  return source.slice(from, to);
};
const urlCode = part('const CUSTOMER_URL_PATTERN', '// Build one interactive demo');
const customerUrls = vm.runInNewContext(urlCode + '\ncustomerUrls');
const list = (text, limit) => Array.from(customerUrls(text, limit));
const sites = count => Array.from({length: count}, (_, i) => `car${i}.example.com/model`).join(' ');
function fixture() {
  const node = () => ({value: '', classList: {add() {}, remove() {}, contains: () => false}, replaceChildren() {}, append() {}});
  const el = Object.fromEntries(['inSites', 'inText', 'thread', 'drawer', 'chatBtn', 'intake', 'pauseBtn', 'handoff', 'lead', 'stack'].map(key => [key, node()]));
  const S = {profile: {name: '', why: '', followup: '', focus: [], stated_needs: [], customer_urls: []}, transcript: [],
    openQuestions: new Set(), questions: [], escalations: [], leads: [], visited: [], covered: new Set(), jumps: [], turns: [],
    resolved: new Set(), unresolved: new Set(), raised: new Set(), sessionId: 'old-session'};
  const accepted = [];
  const code = [urlCode, part('  function addMsg(', '  // Mark the next input'),
    part('  function profileForServer()', '  // Wrap the supplied TTS'),
    part('  function skipIntake()', '  // ---------- handoff ----------'),
    part('  function restart()', '  // Expose a simple pause method')].join('\n') +
    '\n({addMsg,rememberCustomerUrls,intakeSites,submitIntake,profileForServer,skipIntake,restart})';
  const api = vm.runInNewContext(code, {S, el, bundle: {language: 'en-IN'}, live: null, cur: null, h: () => ({}),
    acceptTypedAnswer: text => accepted.push(text), interruptAll() {}, newRun: () => 1, showSlideView() {}, heroOpen: () => ({}),
    playIntroFilm: () => Promise.resolve(false), startAfterIntake() {}, newSessionId: () => 'fresh-session', icon() {},
    createLive() {}, startLive() {}, renderProgress() {}, runIntake() {}});
  return {S, el, accepted, api};
}
const cases = [
  ['bare placeholder is normalized to HTTPS', () => assert.deepEqual(list('hyundai.com/in/en/find-a-car/creta'), ['https://hyundai.com/in/en/find-a-car/creta'])],
  ['full HTTP, HTTPS and www URLs are retained in order', () => assert.deepEqual(list('http://a.example.com/car www.hyundai.com/creta https://b.example.com/spec'), ['http://a.example.com/car', 'https://www.hyundai.com/creta', 'https://b.example.com/spec'])],
  ['uppercase HTTP scheme is not prefixed a second time', () => assert.deepEqual(list('HTTPS://Hyundai.com/car'), ['HTTPS://Hyundai.com/car'])],
  ['brackets and trailing sentence marks stay outside the URL', () => assert.deepEqual(list('See (https://hyundai.com/car), [tata.com/spec].'), ['https://hyundai.com/car', 'https://tata.com/spec'])],
  ['emails do not become domains or subdomain fragments', () => assert.deepEqual(list('person@example.co.in user@hyundai.com user.name@sub.example.com'), [])],
  ['decimal specifications do not become sites', () => assert.deepEqual(list('It has a 1.5 litre engine and 17.4 km/l.'), [])],
  ['normalization deduplicates bare and full copies', () => assert.deepEqual(list('hyundai.com/car https://hyundai.com/car hyundai.com/car'), ['https://hyundai.com/car'])],
  ['intake URL parsing keeps the first five distinct sites', () => assert.equal(list(sites(9), 5).length, 5)],
  ['intake submits the actual answer once and stores only five field URLs', () => {
    const f = fixture(); f.el.inSites.value = sites(7); f.el.inText.value = 'I need family space.'; f.api.submitIntake();
    assert.equal(f.S.profile.customer_urls.length, 5); assert.deepEqual(f.accepted, ['I need family space.']); assert.equal(f.el.inText.value, '');
  }],
  ['a sites-only submission does not fabricate an intake response', () => {
    const f = fixture(); f.el.inSites.value = 'hyundai.com/car'; f.api.submitIntake();
    assert.deepEqual(f.accepted, ['']); assert.equal(f.S.profile.why, ''); assert.equal(f.S.transcript.length, 0);
  }],
  ['a sites-only submission before the prompt ends resolves the later intake wait', async () => {
    const S = {run: 1, intakeOpen: true, intakeResolver: null, pendingIntakeAnswer: null};
    const code = part('  function acceptTypedAnswer(', '  // Open or close the conversation drawer') + '\n' +
      part('  function intakeWait(', '  // Handle the intake microphone button') + '\n({acceptTypedAnswer,intakeWait})';
    const api = vm.runInNewContext(code, {S, el: {inHeard: {}}, live: null, preferTyping() {}, resumeSession() {}, stopListening() {}});
    api.acceptTypedAnswer('');
    assert.equal(S.pendingIntakeAnswer, '');
    assert.equal(await api.intakeWait(1), '');
    assert.equal(S.pendingIntakeAnswer, null); assert.equal(S.intakeResolver, null);
  }],
  ['accepted customer messages append sites up to eight without duplicates', () => {
    const f = fixture(); f.el.inSites.value = sites(5); f.api.intakeSites(); f.api.addMsg('user', 'Compare ' + sites(12));
    assert.equal(f.S.profile.customer_urls.length, 8); assert.equal(f.S.profile.customer_urls[0], 'https://car0.example.com/model');
    assert.equal(f.S.profile.customer_urls[7], 'https://car7.example.com/model');
  }],
  ['URLs in guide speech never join the customer allow-list', () => {
    const f = fixture(); f.api.addMsg('agent', 'According to hyundai.com/car, the page says this.'); assert.equal(f.S.profile.customer_urls.length, 0);
  }],
  ['every runtime profile carries an independent copy of the saved sites', () => {
    const f = fixture(); f.api.addMsg('user', 'Check hyundai.com/car'); const profile = f.api.profileForServer();
    assert.deepEqual(Array.from(profile.customer_urls), ['https://hyundai.com/car']); profile.customer_urls.push('https://other.example.com');
    assert.equal(f.S.profile.customer_urls.length, 1);
  }],
  ['skipping context retains websites the customer entered', () => {
    const f = fixture(); f.el.inSites.value = 'hyundai.com/car'; f.api.skipIntake();
    assert.equal(f.S.profile.customer_urls[0], 'https://hyundai.com/car'); assert.equal(f.S.browseOnly, true);
  }],
  ['restart clears field and URL profile for the new visit', () => {
    const f = fixture(); f.el.inSites.value = 'hyundai.com/car'; f.api.intakeSites(); f.api.restart();
    assert.equal(f.el.inSites.value, ''); assert.equal(f.S.profile.customer_urls.length, 0); assert.equal(f.S.sessionId, 'fresh-session');
  }],
];
async function run() {
  let passed = 0;
  for (const [name, test] of cases) {
    try { await test(); passed++; console.log('PASS ' + name); }
    catch (error) { console.error('FAIL ' + name); throw error; }
  }
  console.log(`Player customer sites contracts: ${passed}/${cases.length}; real helpers, no browser/network/provider`);
}
run().catch(error => {console.error(error); process.exitCode = 1;});
