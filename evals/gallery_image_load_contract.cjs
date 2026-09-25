// Execute the production gallery with controlled image events; no browser,
// providers or network. A canceled picture must never replace the current view.
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
require('node:net').Socket.prototype.connect = function () { throw Error('Outbound sockets blocked'); };
const source = fs.readFileSync(path.join(__dirname, '../web/player/walkthrough.js'), 'utf8').replace(/export function /g, 'function ');
const player = fs.readFileSync(path.join(__dirname, '../web/player/player.js'), 'utf8');
const playerStart = player.indexOf('  async function playLines(');
const playLinesSource = player.slice(playerStart, player.indexOf('  // Present the fixed opening', playerStart));
const flush = () => new Promise(resolve => setImmediate(resolve));

function fixture({sameLine = false, mapped = false, readySecond = false, unanchored = false, firstProxy = false, holdAnimations = false} = {}) {
  const elements = [], timers = new Map(), observers = [], nativeCalls = [], animations = []; let timerId = 0;
  const readySources = new Set(['/ready-A.png', ...(readySecond ? ['/pending-B.png'] : [])]);
  class Element {
    constructor(tag) {
      Object.assign(this, {tag, style: {}, dataset: {}, attrs: {}, children: [], listeners: new Map(),
        isConnected: false, clientWidth: 1000, clientHeight: 500, offsetTop: 350, offsetHeight: 80,
        classes: new Set(), complete: false, naturalWidth: 0, naturalHeight: 0});
      this.classList = {add: value => this.classes.add(value), remove: value => this.classes.delete(value),
        contains: value => this.classes.has(value), toggle: (value, on) => on ? this.classes.add(value) : this.classes.delete(value)};
      if (holdAnimations) this.animate = () => {
        let finish, cancel, settled = false;
        const animation = {element: this, finished: new Promise((resolve, reject) => { finish = resolve; cancel = reject; }), commitStyles() {},
          finish() { if (!settled) { settled = true; finish(); } }, cancel() { if (!settled) { settled = true; cancel(Error('Canceled fixture animation')); } }};
        animations.push(animation); return animation;
      };
      elements.push(this);
    }
    set className(value) { this.classes = new Set(value.split(' ')); }
    get className() { return [...this.classes].join(' '); }
    set src(value) {
      this.attrs.src = value; this.complete = readySources.has(value);
      this.naturalWidth = this.complete ? 1000 : 0; this.naturalHeight = this.complete ? 500 : 0;
    }
    get src() { return this.attrs.src; }
    setAttribute(key, value) { this.attrs[key] = value; if (key === 'class') this.className = value; }
    getAttribute(key) { return this.attrs[key]; }
    append(...children) { this.children.push(...children); for (const child of children) { child.parent = this; child.isConnected = this.isConnected; } }
    replaceChildren(...children) { for (const child of this.children) { child.parent = null; child.isConnected = false; } this.children = []; this.append(...children); }
    remove() { if (this.parent) this.parent.children = this.parent.children.filter(child => child !== this); this.parent = null; this.isConnected = false; }
    querySelector() { return null; }
    getBoundingClientRect() { return this.tag === 'button' ? {left: 600, top: 350, right: 950, bottom: 430, width: 350, height: 80}
      : {left: 0, top: 0, right: 1000, bottom: 500, width: 1000, height: 500}; }
    addEventListener(type, callback) { if (!this.listeners.has(type)) this.listeners.set(type, new Set()); this.listeners.get(type).add(callback); }
    removeEventListener(type, callback) { this.listeners.get(type)?.delete(callback); }
    emit(type) { for (const callback of [...this.listeners.get(type) || []]) callback(); }
  }
  class Observer { constructor() { this.disconnected = false; observers.push(this); } observe() {} disconnect() { this.disconnected = true; } }
  const api = vm.runInNewContext(source + '\n({createWalkthrough})', {
    document: {createElement: tag => new Element(tag), createElementNS: (_, tag) => new Element(tag)},
    matchMedia: () => ({matches: false}), ResizeObserver: Observer,
    getComputedStyle: element => element.style,
    setTimeout: (callback, ms) => { const id = ++timerId; timers.set(id, {callback, ms}); return id; },
    clearTimeout: id => timers.delete(id),
  });
  const slide = {id: 'pair', kind: 'proof', media: [
    {image_id: 'A', image_url: '/ready-A.png', from_line: 0}, {image_id: 'B', image_url: '/pending-B.png', from_line: sameLine ? 0 : 1}],
  callouts: [{id: 'a', image_id: 'A', text: 'Reviewed first feature', placement: 'overlay', anchor: {x: .25, y: .5}, reveal_on_line: 0},
    {id: 'b', image_id: 'B', text: 'Reviewed second feature', placement: 'overlay', anchor: {x: .75, y: .5}, reveal_on_line: sameLine ? 0 : 1}]};
  if (mapped) slide.media_by_line = ['A'];
  if (firstProxy) slide.media[0].proxy = true;
  if (unanchored) for (const callout of slide.callouts) { callout.placement = 'panel'; callout.anchor = null; }
  const before = JSON.stringify(slide), el = new Element('div'); el.isConnected = true;
  const native = {el, images: [], layout() {}, setRevealed: line => nativeCalls.push(['reveal', line]),
    highlight: id => nativeCalls.push(['highlight', id]), setImage() {}, destroy: () => el.remove()};
  const presentation = api.createWalkthrough(); presentation.mount([slide]); const view = presentation.wrap(slide, native);
  const find = cls => elements.find(element => element.classList.contains(cls));
  const surface = find('gallery-surface'), camera = find('gallery-camera');
  const request = (url = '/pending-B.png') => elements.find(element => element.src === url && element.listeners.get('load')?.size);
  const complete = image => { image.complete = true; image.naturalWidth = 1200; image.naturalHeight = 900; image.emit('load'); };
  return {presentation, view, native, nativeCalls, surface, camera, elements, observers, timers, request, complete, find, animations, readySources,
    unchanged: () => assert.equal(JSON.stringify(slide), before), image: () => camera.children[0],
    expire: () => { const active = [...timers.values()]; assert(active.length); for (const timer of active) { assert.equal(timer.ms, 2500); timer.callback(); } }};
}

let passed = 0;
async function check(name, test) { await test(); passed++; console.log('PASS ' + name); }
(async () => {
  await check('a canceled pending narration photo cannot replace or reposition the frozen image', async () => {
    const t = fixture(); assert.equal(await t.view.prepareLine(0), true); const original = t.image();
    const waiting = t.view.prepareLine(1), pending = t.request(); assert(pending); assert.equal(t.image(), original);
    t.presentation.freeze(); const frozen = {...t.camera.style}; assert.equal(await waiting, false);
    t.complete(pending); await flush(); assert.equal(t.image(), original); assert.deepEqual(t.camera.style, frozen);
    assert.equal(t.surface.dataset.state, 'frozen'); assert.equal(t.timers.size, 0); t.unchanged(); t.presentation.destroy();
  });
  await check('runtime reveal stays synchronous and a failed photo restores native content', async () => {
    const t = fixture(); assert.equal(t.view.setRevealed(99), undefined); assert.deepEqual(t.nativeCalls, [['reveal', 99]]);
    const pending = t.request(); assert(pending); assert.equal(t.surface.dataset.state, 'ready'); pending.emit('error'); await flush();
    assert.equal(t.surface.hidden, true); assert.equal(t.native.el.classList.contains('gallery-slide'), false);
    assert.equal(t.surface.dataset.state, 'fallback'); assert.equal(t.timers.size, 0); t.presentation.destroy();
  });
  await check('a stalled runtime photo reaches native fallback at the bounded load deadline', async () => {
    const t = fixture(); t.view.setRevealed(99); t.expire(); await flush();
    assert.equal(t.surface.hidden, true); assert.equal(t.native.el.classList.contains('gallery-slide'), false);
    assert.equal(t.timers.size, 0); t.presentation.destroy();
  });
  await check('a frozen runtime reveal ignores its late load, error and expired deadline', async () => {
    const t = fixture(); await t.view.prepareLine(0); const original = t.image(); t.view.setRevealed(99);
    const pending = t.request(), deadline = [...t.timers.values()][0].callback; t.presentation.freeze();
    const frozen = {...t.camera.style}; t.complete(pending); pending.emit('error'); deadline(); await flush();
    assert.equal(t.image(), original); assert.deepEqual(t.camera.style, frozen); assert.equal(t.surface.dataset.state, 'frozen');
    assert.equal(t.native.el.classList.contains('gallery-slide'), true); assert.equal(t.timers.size, 0); t.presentation.destroy();
  });
  await check('a superseding answer retains its photo after the previous load completes', async () => {
    const t = fixture(); await t.view.prepareLine(0); const original = t.image(); t.view.setRevealed(99); const pending = t.request();
    t.view.setRevealed(0); await flush(); const current = {...t.camera.style}; t.complete(pending); await flush();
    assert.equal(t.image(), original); assert.deepEqual(t.camera.style, current); assert.equal(t.surface.dataset.imageId, 'A');
    assert.equal(t.surface.dataset.state, 'ready'); t.unchanged(); t.presentation.destroy();
  });
  await check('an owned successful runtime load attaches the decoded image and releases its resources', async () => {
    const t = fixture(); t.view.setRevealed(99); const pending = t.request(); assert.equal(t.camera.style.visibility, 'hidden');
    t.complete(pending); await flush(); assert.equal(t.image(), pending); assert.equal(t.camera.style.visibility, 'visible');
    assert.equal(t.surface.dataset.state, 'ready'); assert.equal(t.timers.size, 0);
    assert.equal(pending.listeners.get('load').size, 0); assert.equal(pending.listeners.get('error').size, 0);
    t.unchanged(); t.presentation.destroy();
  });
  await check('failed narration image preparation permits native narration fallback', async () => {
    const t = fixture(), waiting = t.view.prepareLine(1); t.request().emit('error'); assert.equal(await waiting, true);
    t.view.setRevealed(1); assert.deepEqual(t.nativeCalls, [['reveal', 1]]); assert.equal(t.surface.hidden, true);
    assert.equal(t.native.el.classList.contains('gallery-slide'), false); t.presentation.destroy();
  });
  await check('destroy releases pending loads, listeners and observers without a late DOM change', async () => {
    const t = fixture(), waiting = t.view.prepareLine(1), pending = t.request(), original = t.image(); t.view.destroy();
    assert.equal(await waiting, false); t.complete(pending); await flush(); assert.equal(t.image(), original);
    assert.equal(t.surface.isConnected, false); assert.equal(t.timers.size, 0); assert(t.observers.every(observer => observer.disconnected));
    assert.equal(pending.listeners.get('load').size, 0); assert.equal(pending.listeners.get('error').size, 0);
    assert.equal(await t.view.prepareLine(0), false); t.unchanged();
  });
  await check('same-line photos retain both exact captions and swap image ownership without narration', async () => {
    const t = fixture({sameLine: true, readySecond: true}); assert.equal(await t.view.prepareLine(0), true); t.view.setRevealed(0);
    const secondary = t.find('gallery-secondary'), captions = t.find('gallery-captions');
    assert.equal(t.image().src, '/pending-B.png'); assert.equal(secondary.hidden, false); assert.equal(secondary.children[0].src, '/ready-A.png');
    assert.deepEqual(captions.children.map(label => label.dataset.id), ['a', 'b']);
    captions.children.find(label => label.dataset.id === 'a').emit('click'); await flush();
    assert.equal(t.image().src, '/ready-A.png'); assert.equal(secondary.children[0].src, '/pending-B.png'); assert.equal(t.surface.dataset.imageId, 'A');
    assert.deepEqual(captions.children.map(label => label.dataset.id), ['a', 'b']);
    secondary.emit('click'); await flush(); assert.equal(t.image().src, '/pending-B.png'); assert.equal(secondary.children[0].src, '/ready-A.png');
    assert.deepEqual(t.nativeCalls, [['reveal', 0], ['highlight', 'a']]); t.unchanged(); t.presentation.destroy();
  });
  await check('an explicit per-line image mapping retains single-picture presentation', async () => {
    const t = fixture({sameLine: true, mapped: true, readySecond: true}); assert.equal(await t.view.prepareLine(0), true);
    assert.equal(t.image().src, '/ready-A.png'); assert.equal(t.find('gallery-secondary').hidden, true);
    assert.deepEqual(t.find('gallery-captions').children.map(label => label.dataset.id), ['a']); t.unchanged(); t.presentation.destroy();
  });
  await check('same-line unanchored captions never invent a pointer when either photo is focused', async () => {
    const t = fixture({sameLine: true, readySecond: true, unanchored: true}); assert.equal(await t.view.prepareLine(0), true);
    const pointer = t.find('gallery-pointer'); assert.equal(pointer.style.opacity, '0');
    t.find('gallery-captions').children.find(label => label.dataset.id === 'a').emit('click'); await flush();
    assert.equal(pointer.style.opacity, '0'); assert.equal(t.surface.dataset.imageId, 'A'); t.unchanged(); t.presentation.destroy();
  });
  await check('illustration disclosure follows its own photo through primary and inset swaps', async () => {
    const t = fixture({sameLine: true, readySecond: true, firstProxy: true}); assert.equal(await t.view.prepareLine(0), true);
    assert.equal(t.find('gallery-secondary-disclosure').hidden, false); assert.equal(t.find('gallery-disclosure').hidden, true);
    t.find('gallery-secondary').emit('click'); await flush();
    assert.equal(t.find('gallery-secondary-disclosure').hidden, true); assert.equal(t.find('gallery-disclosure').hidden, false);
    assert.equal(t.find('gallery-pointer').style.opacity, '0'); t.unchanged(); t.presentation.destroy();
  });
  await check('local caption and inset clicks during entrance and focusing cannot cancel narration preparation', async () => {
    const t = fixture({sameLine: true, readySecond: true, holdAnimations: true}), spoken = [], S = {run: 1, playback: {}};
    const play = vm.runInNewContext(playLinesSource + '\nplayLines', {S, el: {cite: {}},
      speak: async (text, run, audio) => { spoken.push({text, run, audio}); return true; }, waitForLineQuestion: async () => true});
    const waiting = play({lines: [{text: 'Reviewed narration', audio: '/reviewed.wav', fact_ids: ['F1']}]}, 1, t.view);
    await flush(); let completed = 0, probes = 0;
    while (t.surface.dataset.state !== 'ready') {
      assert(t.animations.length > completed, 'Presentation must wait on an owned camera event');
      if (['entering', 'focusing'].includes(t.surface.dataset.state)) {
        const state = t.surface.dataset.state, labels = t.find('gallery-captions').children, secondary = t.find('gallery-secondary');
        assert(labels.every(label => label.disabled)); assert.equal(secondary.disabled, true);
        labels[0].emit('click'); secondary.emit('click'); await flush();
        assert.equal(t.surface.dataset.state, state); assert.equal(t.surface.dataset.imageId, 'B'); probes++;
      }
      t.animations[completed++].finish(); await flush(); assert(completed <= 8);
    }
    assert.equal(await waiting, true); assert.equal(probes, 2); assert.deepEqual(t.nativeCalls, [['reveal', 0]]);
    assert.deepEqual(spoken, [{text: 'Reviewed narration', run: 1, audio: '/reviewed.wav'}]);
    assert(t.find('gallery-captions').children.every(label => !label.disabled)); assert.equal(t.find('gallery-secondary').disabled, false);
    t.presentation.destroy();
  });
  await check('new primary pixels cannot retain the previous photo captions while the inset loads', async () => {
    const t = fixture({sameLine: true}); t.view.highlight('a'); await flush();
    assert.equal(t.image().src, '/ready-A.png'); assert.equal(t.find('gallery-captions').style.opacity, '1');
    t.readySources.delete('/ready-A.png'); t.readySources.add('/pending-B.png');
    const waiting = t.view.prepareLine(0); await flush();
    assert.equal(t.image().src, '/pending-B.png'); assert(t.request('/ready-A.png'));
    assert.equal(t.find('gallery-captions').style.opacity, '0'); assert.equal(t.find('gallery-pointer').style.opacity, '0');
    t.complete(t.request('/ready-A.png')); assert.equal(await waiting, true);
    assert.equal(t.find('gallery-captions').style.opacity, '1'); t.unchanged(); t.presentation.destroy();
  });
  console.log(`Gallery image loading contracts: ${passed}/${passed}; no browser/network/providers`);
})().catch(error => { console.error(error); process.exitCode = 1; });
