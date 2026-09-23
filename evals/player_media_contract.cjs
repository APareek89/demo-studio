// Actual route personalization and renderer emphasis; fake DOM only, no providers.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const player = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
const start = player.indexOf('  function buildRoute(plan) {');
const routeCode = player.slice(start, player.indexOf('  function rememberContext(', start)) + '\nbuildRoute';
const renderer = fs.readFileSync(path.join(__dirname, '../web/slide.js'), 'utf8');
class Element {
  constructor(tag, attrs = {}, children = []) {
    this.tag = tag; this.attrs = attrs; this.children = children.filter(Boolean); this.style = {}; this.dataset = {};
    const classes = new Set((attrs.class || '').split(' ').filter(Boolean));
    this.classList = {toggle(name, on) {if (on) classes.add(name); else classes.delete(name);}, contains: name => classes.has(name), add: name => classes.add(name), remove: name => classes.delete(name)};
    this.clientWidth = this.clientHeight = 400;
  }
  append(...children) {this.children.push(...children);}
  addEventListener() {}
  setAttribute(name, value) {this.attrs[name] = value;}
  querySelector() {return null;}
  closest() {return null;}
}
const renderSlide = vm.runInNewContext(renderer.replace(/^import .*;\n/m, '').replace('export function renderSlide', 'function renderSlide') + '\nrenderSlide', {
  h: (tag, attrs, ...children) => new Element(tag, attrs, children), document: {createElementNS: (_, tag) => new Element(tag)}, requestAnimationFrame() {}
});
const slide = {id: 'sl-proof', segment_id: 'proof', kind: 'proof', title: 'Reviewed pair', image_id: 'A', image_url: '/A.png', image_parts: [{id: 'partA'}],
  media: [{image_id: 'A', image_url: '/A.png', image_parts: [{id: 'partA'}], from_line: 0}, {image_id: 'B', image_url: '/B.png', image_parts: [{id: 'partB'}], from_line: 1, proxy: true, proxy_reason: 'Exterior illustration'}],
  lines: [{id: 'a', text: 'A'}, {id: 'b', text: 'B'}],
  callouts: [{id: 'ca', image_id: 'A', reveal_on_line: 0, placement: 'panel', text: 'First', fact_ids: ['F1']}, {id: 'cb', image_id: 'B', reveal_on_line: 1, placement: 'panel', text: 'Second', fact_ids: ['F2']} ]};
function route(lines) {
  const S = {plan: [], profile: {focus: []}};
  const build = vm.runInNewContext(routeCode, {S, library: () => [slide], renderProgress() {}, prefetch() {}});
  build({route: [{segment_id: 'proof'}], personalized_segments: [{segment_id: 'proof', lines}]});
  return S.plan[0].slide;
}
const line = index => ({id: String(index), text: 'Reviewed speech', base_line_index: index});
let count = 0;
function check(name, fn) {fn(); count++; console.log('PASS ' + name);}
check('preface shifts second picture and matching callout together', () => {
  const result = route([{text: 'You said cabin.', base_line_index: null}, line(0), line(1)]);
  assert.deepEqual(Array.from(result.media, m => [m.image_id, m.from_line]), [['A', 0], ['B', 2]]);
  assert.deepEqual(Array.from(result.media_by_line), ['A', 'A', 'B']);
  assert.deepEqual(Array.from(result.callouts, c => c.reveal_on_line), [1, 2]);
  const view = renderSlide(result); view.setRevealed(1); assert.equal(view.pics[0].classList.contains('active'), true); assert.equal(view.pics[1].classList.contains('dimmed'), true);
  view.setRevealed(2); assert.equal(view.pics[1].classList.contains('active'), true);
});
check('subset drops unused image and retains the selected picture provenance and aliases', () => {
  const result = route([line(1)]);
  assert.deepEqual(Array.from(result.media, m => [m.image_id, m.from_line]), [['B', 0]]);
  assert.equal(result.media[0].proxy, true); assert.equal(result.media[0].proxy_reason, 'Exterior illustration');
  assert.equal(result.image_id, 'B'); assert.equal(result.image_url, '/B.png'); assert.equal(result.image_parts[0].id, 'partB');
  assert.deepEqual(Array.from(result.callouts, c => c.id), ['cb']);
});
check('reordered reviewed speech reorders picture activation without changing geometry', () => {
  const result = route([line(1), line(0)]);
  assert.deepEqual(Array.from(result.media, m => [m.image_id, m.from_line]), [['B', 0], ['A', 1]]);
  assert.equal(result.media[0].image_parts, slide.media[1].image_parts);
  assert.deepEqual(Array.from(result.callouts, c => [c.id, c.reveal_on_line]), [['ca', 1], ['cb', 0]]);
});
check('A B A repeated ownership emphasizes each played line using only two pictures', () => {
  const result = route([line(0), line(1), line(0)]), view = renderSlide(result);
  assert.equal(result.media.length, 2);
  for (const [index, expected] of [[0, 0], [1, 1], [2, 0]]) {view.setRevealed(index); assert.equal(view.pics[expected].classList.contains('active'), true); assert.equal(view.pics[1 - expected].classList.contains('dimmed'), true);}
});
check('reviewed deeper visual chooses its matching picture without a main-line index', () => {
  const result = route([{text: 'Reviewed deeper speech', base_line_index: null, visual: {kind: 'image', ref: 'B'}}]);
  assert.deepEqual(Array.from(result.media_by_line), ['B']); assert.equal(result.media[0].image_id, 'B');
});
check('published reviewed slide is not mutated by visit-local remapping', () => {
  assert.deepEqual(slide.media.map(m => [m.image_id, m.from_line]), [['A', 0], ['B', 1]]);
  assert.deepEqual(slide.callouts.map(c => c.reveal_on_line), [0, 1]); assert.equal(slide.image_id, 'A');
});
check('legacy single image slide keeps its original shape', () => {
  const originalMedia = slide.media; delete slide.media;
  try {const result = route([line(1)]); assert.equal(result.media, undefined); assert.equal(result.image_url, '/A.png'); assert.equal(result.media_by_line, undefined);} finally {slide.media = originalMedia;}
});
console.log(`Player media contracts: ${count}/${count}; no browser/network/provider`);
