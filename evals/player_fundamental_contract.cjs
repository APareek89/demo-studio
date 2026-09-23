// Execute actual player fallback and request boundaries without browser/network.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
const part = (start, end) => source.slice(source.indexOf(start), source.indexOf(end, source.indexOf(start)));
const code = part('  function buildRoute(plan) {', '  function rememberContext(') + '\n({buildRoute})';
const slides = ['roof', 'screens', 'audio', 'engine', 'space', 'features', 'ownership'].map(id => ({id: 'sl-' + id, segment_id: id, kind: id === 'ownership' ? 'establish' : id === 'features' ? 'features' : 'proof', fundamental: ['engine', 'space'].includes(id), topics: [id]}));
function setup({seen = [], covered = [], previous = [], deck = slides} = {}) {
  const S = {plan: previous, profile: {focus: ['screens']}, visited: seen.map(id => ({slide_id: 'sl-' + id})), covered: new Set(covered.map(id => 'sl-' + id))};
  const api = vm.runInNewContext(code, {S, library: () => deck, topicOf: s => s.topics[0], renderProgress() {}, prefetch() {}});
  return {S, api, ids: () => Array.from(S.plan, step => step.slide.segment_id)};
}
async function run() {
  let count = 0;
  async function check(name, fn) { await fn(); count++; console.log('PASS ' + name); }
  await check('initial fallback reserves one fundamental before buyer focus', () => {const t = setup(); t.api.buildRoute(null); assert.deepEqual(t.ids(), ['engine', 'screens', 'roof', 'audio', 'space', 'features', 'ownership']);});
  await check('already-first fundamental is not duplicated', () => {const t = setup(); t.S.profile.focus = ['engine']; t.api.buildRoute(null); assert.equal(t.ids()[0], 'engine'); assert.equal(t.ids().filter(id => id === 'engine').length, 1);});
  await check('visited and covered fundamentals cannot be forced ahead of buyer focus', () => {for (const options of [{seen: ['engine']}, {covered: ['engine']}]) {const t = setup(options); t.api.buildRoute(null); assert.deepEqual(t.ids().slice(0, 2), ['space', 'screens']);}});
  await check('all fundamentals seen leaves focus first', () => {const t = setup({seen: ['engine', 'space']}); t.api.buildRoute(null); assert.equal(t.ids()[0], 'screens');});
  await check('later fallback retains focus order without another reservation', () => {const t = setup({previous: [{slide: slides[0]}]}); t.api.buildRoute(null); assert.equal(t.ids()[0], 'screens');});
  await check('validated server route is not locally rewritten', () => {const t = setup(); t.api.buildRoute({route: [{segment_id: 'screens'}, {segment_id: 'roof'}]}); assert.deepEqual(t.ids(), ['screens', 'roof']);});
  await check('legacy flags absent keep existing route order', () => {const t = setup({deck: slides.map(({fundamental, ...slide}) => slide)}); t.api.buildRoute(null); assert.equal(t.ids()[0], 'screens');});
  await check('legacy segment-to-slide adapter carries fundamental flag', () => {const adapter = vm.runInNewContext(part('  function slidesOf(b) {', '  let slides = slidesOf(bundle);') + '\nslidesOf'); const result = adapter({segments: [{id: 'engine', role: 'proof', fundamental: true, lines: []}]}); assert.equal(result[1].fundamental, true);});
  await check('intake request is initial and explicit priority correction is refinement', async () => {
    const calls = [], S = {run: 1, profile: {focus: []}, visited: [], sessionId: 'fixture'};
    const classes = {add() {}, remove() {}};
    const shared = {S, api: {pitch: async request => {calls.push(request); return {route: []};}}, bundle: {version: 1, intake: {}}, live: {}, guide: 'Guide',
      el: {intake: {classList: classes}, inFallback: {classList: classes}, cite: {}, inState: {}}, newRun: () => 1, showSlideView() {}, heroOpen: () => ({}), speak: async () => true,
      intakeWait: async () => 'Cabin', intakeSites() {}, addMsg() {}, parseName: () => '', parseFocus: () => ['screens'], profileForServer: () => S.profile, withTimeout: promise => promise, startAfterIntake: async () => {}, cur: null, slides: []};
    const api = vm.runInNewContext(part('  async function runIntake() {', '  async function startAfterIntake(') + '\n' + part('  function queueRefinement() {', '  async function applyUpcomingPlan(') + '\n({runIntake,queueRefinement})', shared);
    await api.runIntake(); assert.equal(calls[0].refine, false);
    S.playback = {phase: 'route', index: 0}; S.plan = [];
    api.queueRefinement(); await Promise.resolve(); assert.equal(calls[1].refine, true);
  });
  await check('opening-resume request also stays initial', async () => {
    const calls = [], S = {run: 1, profile: {why: ''}, sessionId: 'fixture'};
    const start = vm.runInNewContext(part('  async function startAfterIntake(', '  async function playCustomBatches(') + '\nstartAfterIntake', {
      S, api: {pitch: async request => {calls.push(request); return null;}}, live: {}, bundle: {version: 1, runtime: {overview: {text: 'Review the product.'}}},
      newRun: () => 1, profileForServer: () => S.profile, withTimeout: promise => promise, slides: [], opening: () => [], heroOpen: () => ({}), showSlideView() {}, el: {cite: {}}, speak: async () => false
    });
    await start(1); assert.equal(calls[0].refine, false);
  });
  console.log(`Player fundamental contracts: ${count}/${count}; no browser/network/provider`);
}
run().catch(error => {console.error(error); process.exitCode = 1;});
