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
];
let passed = 0;
for (const [name, test] of cases) {
  let ok = false; try { ok = !!test(); } catch (error) { console.error(error); }
  console.log(`${ok ? 'PASS' : 'FAIL'} focus: ${name}`); passed += Number(ok);
}
console.log(`Player focus contracts: ${passed}/${cases.length} (real function; no UI/network/providers)`);
process.exitCode = passed === cases.length ? 0 : 1;
