// The actual gallery module, exercised without browser/network/providers.
// Fake transitionend events advance production states; the fake clock proves
// stale/safety callbacks cannot queue a tour after interruption or destruction.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, '../web/player/walkthrough.js'), 'utf8');
class Style {
  constructor() { this.transform = ''; this.opacity = ''; this.transition = ''; }
  setProperty(k, v) { this[k] = String(v); }
  getPropertyValue(k) { return this[k] || ''; }
  removeProperty(k) { delete this[k]; }
}
class Element {
  constructor(tag = 'div') {
    this.tagName = tag.toUpperCase(); this.children = []; this.parentElement = null; this.dataset = {}; this.style = new Style();
    this.listeners = new Map(); this.textContent = ''; this.hidden = false; this.clientWidth = this.offsetWidth = 900; this.clientHeight = 480;
    this.offsetTop = this.offsetHeight = 0; this.naturalWidth = 1120; this.naturalHeight = 600; this.classes = new Set();
    this.classList = {add: (...names) => names.forEach(name => this.classes.add(name)), remove: (...names) => names.forEach(name => this.classes.delete(name)),
      contains: name => this.classes.has(name), toggle: (name, on = !this.classes.has(name)) => {on ? this.classes.add(name) : this.classes.delete(name); return on;}};
  }
  set className(value) { this.classes = new Set(value.split(/\s+/).filter(Boolean)); }
  get className() { return [...this.classes].join(' '); }
  setAttribute(key, value) { this[key] = String(value); }
  append(...nodes) { nodes.forEach(node => {node.remove(); this.children.push(node); node.parentElement = this;}); }
  insertBefore(node, other) {node.remove(); const i = this.children.indexOf(other); this.children.splice(i < 0 ? this.children.length : i, 0, node); node.parentElement = this;}
  remove() { if (this.parentElement) {this.parentElement.children = this.parentElement.children.filter(child => child !== this); this.parentElement = null;} }
  replaceChildren(...nodes) {this.children.forEach(node => node.parentElement = null); this.children = []; this.append(...nodes);}
  querySelectorAll(query) {const cls = query.startsWith('.') ? query.slice(1) : null; return this.children.flatMap(node => [...(cls ? node.classes.has(cls) ? [node] : [] : node.tagName === query.toUpperCase() ? [node] : []), ...node.querySelectorAll(query)]);}
  querySelector(query) {return this.querySelectorAll(query)[0] || null;}
  addEventListener(type, fn) {if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(fn);}
  removeEventListener(type, fn) {this.listeners.get(type)?.delete(fn);}
  fire(type, data = {}) {for (const fn of [...(this.listeners.get(type) || [])]) fn({type, target: this, propertyName: 'transform', ...data});}
  getBoundingClientRect() {
    if (this.classes.has('wt-frame')) return {left: 310, top: 145, width: 280, height: 150, right: 590, bottom: 295};
    return {left: 0, top: 0, width: this.clientWidth, height: this.clientHeight, right: this.clientWidth, bottom: this.clientHeight};
  }
}
function harness({enabled = true, reduce = false, width = 900, height = 600, slides = null} = {}) {
  const stage = new Element(), stack = new Element(), tasks = new Map(), microtasks = [], observers = [], motionListeners = new Set();
  let serial = 0;
  stage.clientWidth = stack.clientWidth = width; stage.clientHeight = height; stack.clientHeight = Math.min(480, height);
  stage.append(stack);
  const motion = {matches: reduce, addEventListener: (_, fn) => motionListeners.add(fn), removeEventListener: (_, fn) => motionListeners.delete(fn)};
  class ResizeObserver {constructor(fn) {this.fn = fn; this.nodes = []; observers.push(this);} observe(node) {this.nodes.push(node);} disconnect() {this.nodes = [];} }
  const context = vm.createContext({document: {createElement: name => new Element(name)}, matchMedia: () => motion,
    getComputedStyle: node => node.computed || node.style, ResizeObserver, queueMicrotask: fn => microtasks.push(fn),
    setTimeout: (fn, ms) => {const id = ++serial; tasks.set(id, {fn, ms}); return id;}, clearTimeout: id => tasks.delete(id), console});
  const api = vm.runInContext(source.replace(/export function /g, 'function ') + '\n({createWalkthrough,walkthroughStopGeometry,walkthroughFit})', context);
  const first = {id: 's1', kind: 'proof', title: 'Front and cabin', media: [{image_id: 'a', image_url: '/a.png', from_line: 0}, {image_id: 'b', image_url: '/b.png', from_line: 2, proxy: true}],
    lines: [{duration: 2}, {duration: 5}, {duration: 3}], callouts: [
      {id: 'c1', part: 'Grille', text: 'Reviewed front detail', fact_ids: ['F1'], image_id: 'a', placement: 'overlay', anchor: {x: .2, y: .55}, part_box: {w: .16, h: .22}, reveal_on_line: 0},
      {id: 'c2', part: 'Seat', text: 'Reviewed seat detail', fact_ids: ['F2'], image_id: 'b', placement: 'overlay', anchor: {x: .8, y: .5}, reveal_on_line: 2}]};
  const second = {id: 's2', kind: 'features', title: 'Wheel', image_id: 'c', image_url: '/c.png', lines: [{duration: 4}], callouts: [
    {id: 'c3', text: 'Approved wheel evidence', fact_ids: ['F3'], image_id: 'c', placement: 'panel', reveal_on_line: 0}]};
  const hero = {id: 'open', kind: 'hero_open', image_url: '/hero.png', callouts: [], lines: []};
  const close = {id: 'close', kind: 'closing', image_url: '/hero.png', callouts: [], lines: []};
  const deck = slides || [hero, first, second, close];
  const presentation = api.createWalkthrough({stage, stack, bundle: {slides: deck}, enabled}); presentation.mount(deck);
  function view(slide) {
    const el = new Element(), head = new Element(), panel = new Element(), records = [], calls = [];
    head.className = 'slide-heading'; head.offsetHeight = 44; panel.className = 'slide-panel';
    el.className = 'slide cinematic sample-layout'; el.append(head, panel);
    const entries = slide.media?.length ? slide.media : [{image_id: slide.image_id, image_url: slide.image_url}];
    for (const entry of entries) {
      const pic = new Element(), cam = new Element(), img = new Element('img'), leaders = new Element('svg');
      pic.className = 'slide-pic'; cam.className = 'slide-cam'; cam.style.display = 'contents';
      pic.clientWidth = 760; pic.clientHeight = 400; cam.append(img, leaders); pic.append(cam); el.append(pic);
      for (const c of slide.callouts || []) if (c.image_id === entry.image_id && c.anchor) {const dot = new Element(); dot.className = 'dot'; dot.dataset.id = c.id; dot.style.left = c.anchor.x * 100 + '%'; dot.style.top = c.anchor.y * 100 + '%'; cam.append(dot);}
      records.push({pic, cam, img, leaders, entry});
    }
    const handle = {el, pics: records.map(r => r.pic), images: records.map(r => r.img), walkthroughPictures: records,
      setRevealed: index => calls.push(['reveal', index]), highlight: id => calls.push(['highlight', id]), layout: () => calls.push(['layout']),
      setPosition: p => calls.push(['position', p]), setImage: () => calls.push(['image']), destroy: () => {calls.push(['destroy']); el.remove();}};
    stack.append(el); return {handle, records, calls};
  }
  function wrap(slide = first, options = {}) {const t = view(slide); t.originals = {...t.handle}; t.result = presentation.wrap(slide, t.handle, {reveal: -1, position: {index: 1, total: deck.length}, ...options}); return t;}
  const hall = () => stage.querySelector('.wt-hall');
  const phase = () => hall()?.dataset.phase;
  function finish() {
    const nodes = [stage, ...stage.querySelectorAll('div'), ...stage.querySelectorAll('img')].filter(node => node.listeners.get('transitionend')?.size);
    assert.ok(nodes.length, 'a real production transition must be pending'); nodes.forEach(node => {node.fire('transitionend'); node.fire('transitionend', {propertyName: 'opacity'});});
  }
  function settle(max = 12) {while (tasks.size && max--) finish(); assert.equal(tasks.size, 0, 'transition loop must terminate');}
  return {api, presentation, stage, stack, deck, first, second, hero, close, view, wrap, hall, phase, finish, settle, tasks, observers, motion,
    flush: () => {while (microtasks.length) microtasks.shift()();}, motionChange: value => {motion.matches = value; motionListeners.forEach(fn => fn());}};
}
const groups = [];
function group(name, test) {groups.push([name, test]);}
group('flag off returns exact view and builds no hall', () => {const h = harness({enabled: false}), t = h.wrap(); assert.equal(t.result, t.handle); assert.equal(t.handle.setRevealed, t.originals.setRevealed); assert.equal(h.hall(), null); assert.equal(t.handle.el.querySelector('.wt-caption'), null);});
group('one frame per content picture in deck order; no hero/closing frames', () => {const h = harness(); const f = h.hall().querySelectorAll('.wt-frame'); assert.equal(f.length, 3); assert.deepEqual(f.map(x => [x.dataset.slideId, x.dataset.mediaIndex]), [['s1','0'],['s1','1'],['s2','0']]); assert.equal(h.stack.querySelector('.wt-frame'), null);});
group('explicit empty media cannot restore a stale legacy illustration into the gallery', () => {
  const slide = {id: 'text-only', kind: 'proof', title: 'Reviewed terms', media: [], image_url: '/stale-legacy-image.png', lines: [{id: 'terms', text: 'Reviewed terms.', fact_ids: ['F1']}], callouts: []};
  const h = harness({slides: [slide]}), t = h.view(slide), original = JSON.stringify(slide);
  t.handle.walkthroughPictures = []; t.handle.images = [];
  h.presentation.wrap(slide, t.handle, {reveal: 99, position: {index: 1, total: 1}});
  assert.equal(h.hall().querySelectorAll('.wt-frame').length, 0);
  assert.equal(h.hall().querySelectorAll('img').length, 0);
  assert.equal(h.phase(), 'transient'); assert.equal(h.hall().hidden, true);
  assert.equal(h.tasks.size, 0); assert.equal(JSON.stringify(slide), original);
});
group('real transitionend drives hall walk straighten dive stop', () => {const h = harness(), t = h.wrap(); assert.equal(h.phase(), 'walk'); t.handle.setRevealed(0); h.finish(); assert.equal(h.phase(), 'straighten'); h.finish(); assert.equal(h.phase(), 'dive'); h.finish(); assert.equal(h.phase(), 'stop'); h.finish(); assert.equal(h.tasks.size, 0);});
group('grounded caption and actual anchored dot survive camera zoom', () => {const h = harness(), t = h.wrap(); t.handle.setRevealed(0); h.settle(); const cap = t.handle.el.querySelector('.wt-caption'); assert.deepEqual(cap.children.map(x => x.textContent), ['Grille', 'Reviewed front detail', 'F1']); const dot = t.records[0].cam.querySelector('.wt-stop-dot'); assert.equal(dot.style.left, '20%'); assert.equal(dot.style.top, '55.00000000000001%'); assert.ok(Number(dot.style['--wt-dot-scale']) < 1);});
group('no newly revealed tag means no new camera move', () => {const h = harness(), t = h.wrap(); t.handle.setRevealed(0); h.settle(); const before = t.records[0].cam.style.transform; t.handle.setRevealed(1); assert.equal(t.records[0].cam.style.transform, before); assert.equal(h.tasks.size, 0);});
group('same-slide reveal then highlight(null) retains replayed stop', () => {const h = harness(), t = h.wrap(); t.handle.setRevealed(0); h.settle(); h.flush(); t.handle.setRevealed(0); t.handle.highlight(null); assert.equal(h.hall().dataset.stop, 'c1'); assert.equal(t.handle.el.querySelector('.wt-caption').hidden, false); h.settle();});
group('deeper reveal99 and later explicit highlight(null) return to rest', () => {const h = harness(), t = h.wrap(); t.handle.setRevealed(0); h.settle(); t.handle.setRevealed(99); h.settle(); assert.equal(h.hall().dataset.stop, ''); assert.equal(h.hall().dataset.zoom, '1'); t.handle.highlight('c2'); h.settle(); h.flush(); t.handle.highlight(null); h.settle(); assert.equal(h.hall().dataset.stop, '');});
group('two-picture from_line starts rise then walk to second frame', () => {const h = harness(), t = h.wrap(); t.handle.setRevealed(0); h.settle(); t.handle.setRevealed(2); assert.equal(h.phase(), 'rise'); h.finish(); assert.equal(h.phase(), 'walk'); h.settle(); assert.equal(h.hall().dataset.frame, '1'); assert.equal(h.hall().dataset.stop, 'c2'); assert.ok(t.records[1].pic.classList.contains('wt-picture-live'));});
group('mid-walk retarget uses current computed matrix and cancels old callbacks', () => {const h = harness(); h.wrap(); const world = h.hall().querySelector('.wt-world'); world.computed = {transform: 'matrix3d(current-flight)', opacity: '0.6'}; const old = [...h.tasks.values()].map(x => x.fn); h.wrap(h.second, {jump: true}); assert.equal(h.phase(), 'walk'); assert.match(world.style.transition, /0.9s/); old.forEach(fn => fn()); assert.equal(h.phase(), 'walk'); h.settle(); assert.equal(h.hall().dataset.frame, '2');});
group('pause freezes every moving layer and resume completes interrupted dive', () => {const h = harness(), t = h.wrap(); h.finish(); h.finish(); assert.equal(h.phase(), 'dive'); const cam = t.records[0].cam; cam.computed = {transform: 'matrix(0.7,0,0,0.7,5,6)', opacity: '1'}; const hall = h.hall(); hall.computed = {transform: 'none', opacity: '.4'}; h.presentation.pause(); assert.equal(h.tasks.size, 0); assert.equal(cam.style.transform, 'matrix(0.7,0,0,0.7,5,6)'); assert.equal(hall.style.opacity, '.4'); assert.equal(hall.dataset.frozen, 'true'); t.handle.setRevealed(0); assert.equal(h.tasks.size, 0); h.presentation.resume(); assert.equal(h.phase(), 'dive'); h.settle(); assert.equal(hall.style.opacity, '0');});
group('opacity completion cannot settle a still-moving transform and pause freezes all layers', () => {const h=harness(); h.wrap(); const world=h.hall().querySelector('.wt-world'); world.fire('transitionend',{propertyName:'opacity'}); assert.ok(world.listeners.get('transitionend').size); assert.equal(h.phase(),'walk'); world.computed={transform:'matrix3d(mid-walk)',opacity:'1'}; h.presentation.pause(); assert.equal(world.style.transform,'matrix3d(mid-walk)'); assert.equal(world.style.transition,'none'); assert.equal(h.tasks.size,0); h.presentation.resume(); h.settle(); assert.equal(h.phase(),'rest');});
group('interruption freeze allows an answer jump then reverse return', () => {const h = harness(), t = h.wrap(); t.handle.setRevealed(0); h.settle(); h.presentation.freeze(); const answer = h.wrap(h.second, {reveal: 99, jump: true}); answer.handle.highlight('c3'); assert.equal(h.phase(), 'rise'); h.settle(); assert.equal(h.hall().dataset.frame, '2'); const back = h.wrap(h.first, {reveal: 0, jump: true}); back.handle.setRevealed(0); h.settle(); assert.equal(h.hall().dataset.frame, '0'); assert.equal(h.hall().dataset.stop, 'c1');});
group('hero and closing remain wide; transient custom has no frame', () => {const h = harness(); h.wrap(h.hero); h.settle(); assert.equal(h.phase(), 'wide'); assert.equal(h.hall().dataset.frame, '-1'); h.wrap(h.close); h.settle(); assert.equal(h.phase(), 'wide'); const t = h.wrap({...h.first, id:'custom'}, {position: null}); assert.equal(h.phase(), 'transient'); assert.equal(h.hall().hidden, true); assert.equal(t.records[0].cam.style.display, 'contents');});
group('reduced-motion returns original DOM/methods and switches dynamically', () => {const h = harness({reduce: true}), t = h.wrap(); assert.equal(h.hall(), null); assert.equal(t.handle.setRevealed, t.originals.setRevealed); assert.equal(t.handle.el.querySelector('.wt-caption'), null); h.motionChange(false); assert.ok(h.hall()); assert.notEqual(t.handle.setRevealed, t.originals.setRevealed); h.motionChange(true); assert.equal(h.hall(), null); assert.equal(t.handle.setRevealed, t.originals.setRevealed); assert.equal(t.records[0].cam.style.display, 'contents');});
group('narrow or short stage fallback preserves view; wide resize reactivates', () => {for (const [width,height] of [[699,600],[900,319]]) {const h = harness({width,height}), t = h.wrap(); assert.equal(h.hall(),null); assert.equal(t.handle.setRevealed,t.originals.setRevealed); h.stage.clientWidth=900; h.stage.clientHeight=600; h.presentation.resize(h.stage.getBoundingClientRect()); assert.ok(h.hall()); h.presentation.destroy();}});
group('zoom cap covers real Creta sizes and never exceeds native limit', () => {const h = harness(); for (const [nw,rw] of [[1120,800],[830,760],[800,760],[100,200]]) {const g = h.api.walkthroughStopGeometry({placement:'overlay',anchor:{x:.5,y:.5},part_box:{w:.01,h:.02}},nw,rw); assert.ok(g.z <= Math.min(2.2,nw/rw*1.15));} assert.equal(h.api.walkthroughStopGeometry({placement:'panel',anchor:{x:0,y:1}},1120,800).z,1);});
group('pan clamp contains all edges and caption-only rest has zero pan', () => {const h=harness(); for(const x of [0,.2,.5,.8,1]) for(const y of [0,.5,1]) {const g=h.api.walkthroughStopGeometry({placement:'overlay',anchor:{x,y}},1120,760); assert.ok(Math.abs(g.x)<=g.lim && Math.abs(g.y)<=g.lim); assert.ok(g.z*(.5-Math.abs(g.x))>=.5);} const rest=h.api.walkthroughStopGeometry({placement:'panel',anchor:{x:0,y:1}},1120,760); assert.equal(Math.abs(rest.x),0); assert.equal(Math.abs(rest.y),0);});
group('native-size letterboxing and FLIP are uniform', () => {const h=harness(); const fit=h.api.walkthroughFit(200,100,900,400); assert.equal(fit.width,200); assert.equal(fit.height,100); assert.equal(fit.scale,1); const t=h.wrap(); h.finish(); h.finish(); assert.ok(!/scale\([^)]*,/.test(t.records[0].cam.style.transform));});
group('wrapper preserves handle shape and delegates unrelated methods', () => {const h=harness(),t=h.wrap(); assert.equal(t.result,t.handle); assert.deepEqual(Object.keys(t.handle).sort(),Object.keys(t.originals).sort()); assert.equal(t.handle.setImage,t.originals.setImage); assert.equal(t.handle.pics,t.originals.pics); t.handle.setPosition(null); assert.deepEqual(t.calls.at(-1),['position',null]);});
group('safety timeout completes missing transitionend without a queued chain', () => {const h=harness(),t=h.wrap(); t.handle.setRevealed(0); for(let steps=0;h.tasks.size && steps<8;steps++){const batch=[...h.tasks.values()]; batch.forEach(task=>task.fn());} assert.equal(h.tasks.size,0); assert.equal(h.phase(),'stop');});
group('stop/restart reset wide and destroy removes timers and observers', () => {const h=harness(); h.wrap(); const stale=[...h.tasks.values()].map(t=>t.fn); h.presentation.reset(); assert.equal(h.phase(),'wide'); assert.equal(h.hall().dataset.frame,'-1'); assert.equal(h.tasks.size,0); h.presentation.mount(h.deck); h.wrap(); h.presentation.destroy(); stale.forEach(fn=>fn()); assert.equal(h.hall(),null); assert.equal(h.tasks.size,0); assert.ok(h.observers.every(o=>o.nodes.length===0));});
group('original cross-fade destruction cannot hang a rise', () => {const h=harness(),t=h.wrap(); t.handle.setRevealed(0); h.settle(); h.wrap(h.second); assert.equal(h.phase(),'rise'); t.handle.destroy(); h.settle(); assert.equal(h.hall().dataset.frame,'2');});
group('geometry changes after layout re-cap the actual current stop', () => {const h=harness(),t=h.wrap(); t.handle.setRevealed(0); h.settle(); t.records[0].img.naturalWidth=200; t.records[0].img.naturalHeight=100; t.handle.layout(); h.settle(); assert.ok(Number(h.hall().dataset.zoom)<=1.15); assert.equal(t.records[0].pic.style['--wt-width'],'200px');});
group('module changes only its cameras and own gallery transforms', () => {const h=harness(),t=h.wrap(); t.handle.setRevealed(0); h.settle(); assert.equal(h.stage.style.transform,''); assert.equal(h.stack.style.transform,''); assert.equal(t.handle.el.style.transform,''); assert.ok(t.records.every(r=>r.pic.style.transform===''));});
group('fallback destroys stale observers and recovers the actually active second picture', () => {const h=harness(), old=h.wrap(); old.handle.setRevealed(0); h.settle(); h.motionChange(true); old.handle.destroy(); const t=h.wrap(h.first); t.records[1].pic.classList.add('active'); t.records[0].pic.classList.remove('active'); h.motionChange(false); h.settle(); assert.equal(h.hall().dataset.frame,'1'); assert.ok(h.observers.filter(o=>o.nodes.includes(old.records[0].pic)).length===0);});
group('flag-off lifecycle never adds presentation state to the default stage', () => {const h=harness({enabled:false}); h.presentation.freeze(); h.presentation.pause(); h.presentation.resume(); h.presentation.reset(); assert.equal(h.stage.className,''); assert.equal(h.tasks.size,0);});
group('resizing a paused dive discards stale cap and keeps frozen poses', () => {const h=harness(),t=h.wrap(); t.handle.setRevealed(0); h.finish(); h.finish(); const world=h.hall().querySelector('.wt-world'); world.computed={transform:'matrix3d(frozen-world)',opacity:'1'}; t.records[0].cam.computed={transform:'matrix(.6,0,0,.6,10,20)',opacity:'1'}; h.presentation.pause(); const before=t.records[0].cam.style.transform; h.stage.clientWidth=1024; h.presentation.resize(h.stage.getBoundingClientRect()); assert.equal(t.records[0].cam.style.transform,before); assert.equal(h.tasks.size,0); h.presentation.resume(); h.settle(); assert.equal(h.hall().style.opacity,'0'); assert.ok(Number(h.hall().dataset.zoom)<=2.2);});
group('a later untagged line does not replace the pending stop pacing', () => {const h=harness(),t=h.wrap(); t.handle.setRevealed(0); t.handle.setRevealed(1); h.finish(); h.finish(); h.finish(); assert.equal(h.phase(),'stop'); assert.match(t.records[0].cam.style.transition,/1.2s/); h.settle();});
group('second-picture from_line wins over an earlier-image tag revealed together', () => {const h=harness(); h.first.callouts.unshift({...h.first.callouts[0],id:'extra',reveal_on_line:2}); const t=h.wrap(); t.handle.setRevealed(0); h.settle(); t.handle.setRevealed(2); h.settle(); assert.equal(h.hall().dataset.frame,'1'); assert.equal(h.hall().dataset.stop,'c2');});
let passed=0;
for(const [name,test] of groups){try{test();passed++;console.log(`PASS walkthrough: ${name}`);}catch(error){console.error(`FAIL walkthrough: ${name}\n${error.stack}`);}}
console.log(`Player walkthrough contracts: ${passed}/${groups.length} (production module; fake transitionend; no network/providers)`);
process.exitCode=passed===groups.length?0:1;
