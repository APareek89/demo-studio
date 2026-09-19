// Full shipped Align module + actual SSE client, with a DOM-shaped local host.
// No browser, provider, network, timer waiting, or real demo writes.
import fs from 'node:fs';
class Node {
  constructor(tag = '#text', text = '') { this.tag = tag; this.nodeType = tag === '#text' ? 3 : 1; this.children = []; this.className = ''; this.attrs = {}; this.listeners = {}; this.value = ''; this._text = text; }
  get classList() {
    const node = this;
    return { contains: name => node.className.split(/\s+/).includes(name),
      add: name => { node.className = [...new Set([...node.className.split(/\s+/).filter(Boolean), name])].join(' '); },
      remove: name => { node.className = node.className.split(/\s+/).filter(value => value !== name).join(' '); },
      toggle(name, force) { const on = force ?? !this.contains(name); this[on ? 'add' : 'remove'](name); return on; } };
  }
  setAttribute(name, value) { this.attrs[name] = String(value); }
  addEventListener(name, listener) { this.listeners[name] = listener; }
  append(...children) { for (const child of children.flat()) { if (child === null || child === undefined || child === false) continue; const node = child instanceof Node ? child : new Node('#text', String(child)); node.parent?.removeChild(node); node.parent = this; this.children.push(node); } }
  removeChild(node) { this.children = this.children.filter(child => child !== node); node.parent = null; }
  replaceChildren(...children) { this.children.forEach(child => { child.parent = null; }); this.children = []; this.append(...children); }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set textContent(text) { this._text = String(text); this.replaceChildren(); }
  querySelector(selector) { return descendants(this).find(node => selector.startsWith('.') && node.classList.contains(selector.slice(1))) || null; }
}
const descendants = node => node.children.flatMap(child => [child, ...descendants(child)]);
const area = new Node('main'), docListeners = new Map(), windowListeners = new Map(), timers = new Map();
globalThis.document = { visibilityState: 'visible', createElement: tag => new Node(tag), createTextNode: text => new Node('#text', text),
  addEventListener: (type, fn) => docListeners.set(type, fn), removeEventListener: (type, fn) => { if (docListeners.get(type) === fn) docListeners.delete(type); },
  querySelector: selector => area.querySelector(selector) };
globalThis.window = { addEventListener: (type, fn) => windowListeners.set(type, fn) };
globalThis.setInterval = (fn, ms) => { const id = timers.size + 1; timers.set(id, { fn, ms }); return id; };
globalThis.clearInterval = id => timers.delete(id);
globalThis.fetch = () => { throw new Error('Outbound fetch forbidden'); };
class Source {
  static instances = [];
  constructor(url) { this.url = url; this.listeners = {}; Source.instances.push(this); }
  addEventListener(type, fn) { this.listeners[type] = fn; }
  fire(type, value) { this.listeners[type]?.({ data: JSON.stringify(value) }); }
  close() { this.closed = true; }
}
globalThis.EventSource = Source;
const { api, h, esc } = await import('../web/api.js');
const did = 'dm_12345678';
const initial = { demo: { id: did, status: 'reading', approvals: {}, stages: {
  understand: { status: 'done', progress: [{ t: 0, message: 'Historical source message' }] },
  author: { status: 'running', progress: [{ t: 2, message: 'Checking the latest script' }, { t: 1, message: 'Writing the story' }] },
} }, cards: null, conversation: [] };
let remote = structuredClone(initial), reads = 0;
api.get = async () => { reads++; return structuredClone(remote); };
let source = fs.readFileSync(new URL('../web/studio/align.js', import.meta.url), 'utf8').replace(/^import .*;\n/gm, '');
globalThis.__alignFixture = { api, h, esc, toast: () => {}, renderSlide: () => { throw new Error('No slide preview expected'); }, icon: () => h('svg'), readinessQuery: () => '' };
source = 'const {api,h,esc,toast,renderSlide,icon,readinessQuery}=globalThis.__alignFixture;\n' + source;
const { renderAlign } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const routes = [], rail = []; let unsubscribe;
renderAlign({ demoId: did, state: initial, area, setRailStatus: value => rail.push(value), navigate: value => routes.push(value), subscribe: fn => { unsubscribe = api.subscribe(did, fn); } });
const stream = Source.instances.at(-1), overlay = area.querySelector('.overlay'), log = area.querySelector('.progress-log');
const rows = [];
const check = (name, ok) => { rows.push(Boolean(ok)); console.log(`${ok ? 'PASS' : 'FAIL'} ${name}`); };
const flush = async () => { for (let i = 0; i < 6; i++) await Promise.resolve(); };
check('initial running mount restores current-stage progress in time order without historical stages', !overlay.classList.contains('hidden') && log.textContent.indexOf('Writing the story') < log.textContent.indexOf('Checking the latest script') && !log.textContent.includes('Historical source message'));
remote.demo.status = 'align'; remote.demo.stages.author.status = 'done';
stream.fire('hello', { seq: 100, snapshot: structuredClone(remote.demo) }); await flush();
check('fresh done snapshot hides an earlier running overlay and reloads current state', overlay.classList.contains('hidden') && reads === 1 && rail.at(-1) === 'align');
stream.fire('phase_done', { seq: 90, phase: 'build' }); await flush();
check('actual SSE client suppresses historical build completion after snapshot', routes.length === 0 && reads === 1);
remote.demo.status = 'building'; remote.demo.stages.voice = { status: 'running', message: 'Recording current narration', updated_at: 5 };
stream.fire('hello', { seq: 100, snapshot: structuredClone(remote.demo) }); await flush();
check('reconnect restores latest stage message even without progress array', !overlay.classList.contains('hidden') && log.textContent === 'voice · Recording current narration');
const poll = [...timers.values()][0], before = reads;
remote.demo.status = 'align'; remote.demo.stages.voice.status = 'done'; poll.fn(); await flush();
check('visible 30-second polling recovers completion despite overlay node existing', poll.ms === 30000 && reads === before + 1 && overlay.classList.contains('hidden'));
const hiddenReads = reads; document.visibilityState = 'hidden'; poll.fn(); await flush(); document.visibilityState = 'visible'; docListeners.get('visibilitychange')(); await flush();
check('hidden tabs do not poll and visible-tab return reloads', reads === hiddenReads + 1);
stream.fire('hello', { seq: 101, snapshot: structuredClone(remote.demo) }); await flush();
stream.fire('phase_done', { seq: 100, phase: 'build' }); await flush();
check('reconnect does not revive an old completion navigation', routes.length === 0);
remote.demo.status = 'ready'; stream.fire('phase_done', { seq: 102, phase: 'build' }); await flush();
check('new live completion retains intended Rehearse navigation', routes.length === 1 && routes[0] === `#/studio/${did}/rehearse`);
windowListeners.get('hashchange')(); unsubscribe();
check('navigation cleans up polling visibility listener and event subscription', timers.size === 0 && !docListeners.has('visibilitychange') && stream.closed);
console.log(`Align progress contracts: ${rows.filter(Boolean).length}/${rows.length} (actual modules, DOM-shaped host, no browser/network)`);
process.exitCode = rows.every(Boolean) ? 0 : 1;
