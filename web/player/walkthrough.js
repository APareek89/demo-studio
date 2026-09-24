// Optional gallery presentation. Playback owns all line starts; this module only
// follows them. No speech, routing, checkpoint or bundle data is changed here.
const WIDE_KINDS = new Set(['hero_open', 'closing', 'hero_close']);
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const entriesOf = slide => Array.isArray(slide.media) ? slide.media.slice(0, 2) :
  (slide.image_url ? [{image_id: slide.image_id || '', image_url: slide.image_url, image_parts: slide.image_parts || [], from_line: 0}] : []);

// Exported pure geometry also exercises the actual production cap/clamp in the
// free contract. A sub-native frame never gets enlarged to fill the stage.
export function walkthroughStopGeometry(callout, naturalWidth, renderedWidth) {
  const cap = Math.min(2.2, naturalWidth > 0 && renderedWidth > 0 ? naturalWidth / renderedWidth * 1.15 : 1);
  const part = callout?.part_box;
  const span = Math.max(number(part?.w), number(part?.h));
  const requested = part && span > 0 ? Math.max(1.15, 0.45 / span) : 1.5;
  const z = callout?.placement === 'overlay' && callout.anchor ? Math.min(requested, cap) : 1;
  // For z=1 the literal formula is negative: the effective pan range is zero.
  const lim = Math.max(0, 0.5 * (1 - 1 / z) - 0.01);
  return {z, cap, x: clamp(0.5 - number(callout?.anchor?.x, .5), -lim, lim),
    y: clamp(0.5 - number(callout?.anchor?.y, .5), -lim, lim), lim};
}
export function walkthroughFit(naturalWidth, naturalHeight, width, height) {
  const nw = Math.max(1, number(naturalWidth, width)), nh = Math.max(1, number(naturalHeight, height));
  const scale = Math.min(1, Math.max(1, width) / nw, Math.max(1, height) / nh);
  return {width: nw * scale, height: nh * scale, scale};
}

export function createWalkthrough({stage, stack, bundle, enabled = false}) {
  const mediaQuery = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null;
  const views = new Set();
  let deck = [], frames = [], hall = null, world = null, active = false, destroyed = false;
  let box = {width: 0, height: 0}, height = 0, depth = 0, side = 0, current = null, desired = null;
  let location = -1, flat = -1, expanded = null, phase = 'wide', flight = null;
  let frozen = false, hardPaused = false, suspended = null, version = 0, paintedVersion = -1;
  // Every moving layer has one current transition. Retargeting reads its live
  // computed pose; transitionend (with a bounded safety fallback) advances state.
  const moving = new Map();
  const make = (tag, cls, text) => { const node = document.createElement(tag); node.className = cls; if (text != null) node.textContent = text; return node; };
  const computed = node => typeof getComputedStyle === 'function' ? getComputedStyle(node) : node.style;
  const connected = node => typeof node.isConnected === 'boolean' ? node.isConnected : !!node.parentElement;
  function pruneViews() {
    for (const meta of [...views]) {
      if (connected(meta.view.el)) meta.wasConnected = true;
      else if (meta.wasConnected) disposeMeta(meta);
    }
  }
  function recoverFallback(meta) {
    // Fallback used the untouched renderer, so recover its actual visible
    // picture rather than a stale line index from before the viewport changed.
    const activePicture = meta.pictures.findIndex(record => record.pic.classList.contains('active'));
    const visible = (meta.slide.callouts || []).filter(callout =>
      [...meta.view.el.querySelectorAll('.dot'), ...meta.view.el.querySelectorAll('.item')].some(node => node.dataset.id === callout.id && !node.classList.contains('hidden')));
    const hot = visible.find(callout => [...meta.view.el.querySelectorAll('.dot'), ...meta.view.el.querySelectorAll('.item')].some(node => node.dataset.id === callout.id && node.classList.contains('hot')));
    meta.lastReveal = Math.max(-1, ...visible.map(item => number(item.reveal_on_line)), activePicture >= 0 ? number(meta.pictures[activePicture].entry.from_line) : -1);
    meta.stop = hot || null;
    return activePicture >= 0 ? activePicture : 0;
  }
  function diagnostic() {
    if (!hall) return;
    Object.assign(hall.dataset, {phase, frame: String(expanded?.frame ?? location), stop: desired?.stop?.id || '',
      zoom: String(desired?.geometry?.z || 1), active: String(active), frozen: String(frozen)});
  }
  function cancelMoves(allLayers = false) {
    const nodes = new Set(moving.keys());
    // A settled opacity event must never leave an untracked transform moving
    // through Pause. Capture every layer this presentation can animate.
    if (allLayers) {
      for (const node of [hall, world, ...frames.map(frame => frame.el),
        ...[...views].flatMap(meta => meta.pictures.map(record => record.cam))]) if (node) nodes.add(node);
    }
    const poses = [...nodes].map(node => [node, computed(node).transform, computed(node).opacity]);
    for (const [node, task] of moving) { clearTimeout(task.timer); node.removeEventListener('transitionend', task.end); }
    moving.clear(); flight = null;
    for (const [node, transform, opacity] of poses) {
      node.style.transition = 'none';
      if (transform) node.style.transform = transform;
      if (opacity != null && opacity !== '') node.style.opacity = opacity;
    }
  }
  function move(name, targetFrame, changes, seconds, done) {
    cancelMoves();
    if (!active || frozen || destroyed) return;
    phase = name;
    const token = {}; flight = {token, targetFrame, name, changes, seconds, done, owner: desired?.meta, targetVersion: version, started: Date.now()}; diagnostic();
    let pending = changes.length;
    if (!pending) { flight = null; done(); return; }
    for (const {node, transform, opacity} of changes) {
      const before = computed(node);
      const oldTransform = before.transform, oldOpacity = before.opacity;
      node.style.transition = 'none';
      if (oldTransform && oldTransform !== 'none') node.style.transform = oldTransform;
      if (oldOpacity != null && oldOpacity !== '') node.style.opacity = oldOpacity;
      void node.offsetWidth;
      node.style.transition = `transform ${seconds}s cubic-bezier(.3,.7,.22,1), opacity ${seconds}s ease`;
      let settled = false;
      const end = event => {
        if (event && (event.target !== node || event.propertyName !== (transform != null ? 'transform' : 'opacity'))) return;
        if (settled) return; settled = true;
        const task = moving.get(node); if (!task || task.token !== token) return;
        clearTimeout(task.timer); node.removeEventListener('transitionend', end); moving.delete(node);
        if (!flight || flight.token !== token || frozen || destroyed) return;
        if (--pending === 0) { flight = null; done(); }
      };
      moving.set(node, {end, token, timer: setTimeout(() => end(), Math.ceil(seconds * 1000) + 120)});
      node.addEventListener('transitionend', end);
      if (transform != null) node.style.transform = transform;
      if (opacity != null) node.style.opacity = String(opacity);
    }
  }
  function pose(index, straight = false, passed = false) {
    const sign = index % 2 ? 1 : -1;
    return `translate3d(${straight ? 0 : sign * (passed ? box.width * .58 : side)}px,0,${-index * depth}px) rotateY(${straight ? 0 : -sign * (passed ? 55 : 32)}deg)`;
  }
  function galleryChanges(index, straight = false, wide = false) {
    return [{node: world, transform: `translateZ(${index < 0 ? -box.width * .18 : index * depth}px)`},
      ...frames.map((frame, i) => {
        const distance = i - Math.max(0, index);
        frame.el.classList.toggle('wt-current', i === index);
        return {node: frame.el, transform: pose(i, straight && i === index, i < index),
          opacity: distance < 0 ? 0 : distance === 0 ? 1 : distance === 1 ? .8 : distance === 2 ? .5 : .28};
      }), {node: hall, opacity: 1}];
  }
  function clearStop(meta) {
    if (!meta) return;
    meta.caption.hidden = true;
    meta.view.el.classList.remove('wt-tour');
    for (const record of meta.pictures) for (const dot of record.cam?.querySelectorAll('.dot') || []) {
      dot.classList.remove('wt-stop-dot'); dot.style.removeProperty('--wt-dot-scale');
    }
  }
  function showStop(meta, callout, geometry) {
    clearStop(meta);
    if (!callout) return;
    const picture = meta.pictures.find(item => item.entry.image_id === callout.image_id) || meta.pictures[0];
    const parts = picture?.entry.image_parts || [];
    const sameBox = part => part.box && callout.part_box && ['x', 'y', 'w', 'h'].every(key => Math.abs(number(part.box[key]) - number(callout.part_box[key])) < .001);
    const part = typeof callout.part === 'string' ? callout.part : parts.find(sameBox)?.name || '';
    meta.caption.replaceChildren();
    if (part) meta.caption.append(make('strong', 'wt-caption-part', part));
    meta.caption.append(make('span', 'wt-caption-text', callout.text || ''));
    if (callout.fact_ids?.length) meta.caption.append(make('small', 'wt-caption-cite', callout.fact_ids.join(', ')));
    meta.caption.hidden = false;
    meta.view.el.classList.add('wt-tour');
    const dot = [...(picture?.cam?.querySelectorAll('.dot') || [])].find(node => node.dataset.id === callout.id);
    if (dot) { dot.classList.add('wt-stop-dot'); dot.style.setProperty('--wt-dot-scale', String(1 / geometry.z)); }
  }
  function revealPicture(meta, index) {
    if (!meta) return;
    meta.pictures.forEach((item, i) => item.pic.classList.toggle('wt-picture-live', i === index));
  }
  function restoreMeta(meta) {
    clearStop(meta);
    meta.view.el.classList.remove('wt-view', 'wt-wide', 'wt-tour', 'wt-expanded');
    for (const picture of meta.pictures) {
      picture.pic.classList.remove('wt-picture', 'wt-picture-live');
      if (picture.cam) { picture.cam.style.transition = ''; picture.cam.style.transform = ''; picture.cam.style.display = 'contents'; }
      for (const key of ['width', 'height', 'left', 'top']) picture.pic.style.removeProperty(`--wt-${key}`);
    }
    meta.caption.hidden = true; meta.caption.remove();
    for (const key of Object.keys(meta.original)) meta.view[key] = meta.original[key];
    meta.installed = false;
  }
  function setupMeta(meta) {
    if (!active || meta.dead || meta.installed) return;
    meta.installed = true;
    meta.view.el.append(meta.caption);
    meta.view.setRevealed = index => {
      meta.original.setRevealed.call(meta.view, index);
      if (!active || current !== meta) return;
      // showSlideView's same-slide branch calls highlight(null) synchronously.
      // Do not let that bookkeeping erase the replayed line's new stop.
      meta.ignoreRest = true; const marker = ++meta.restMarker;
      queueMicrotask(() => { if (meta.restMarker === marker) meta.ignoreRest = false; });
      lineStart(meta, index);
    };
    meta.view.highlight = id => {
      meta.original.highlight.call(meta.view, id);
      if (!active || current !== meta) return;
      if (!id && meta.ignoreRest) { meta.ignoreRest = false; return; }
      const callout = (meta.slide.callouts || []).find(item => item.id === id) || null;
      if (callout || meta.stop !== callout) version++;
      meta.stop = callout; meta.stopLine = meta.lastReveal;
      select(meta, meta.lastReveal, callout, !!id);
    };
    meta.view.layout = () => { meta.original.layout.call(meta.view); layoutMeta(meta); };
    meta.view.destroy = () => disposeMeta(meta);
    if (meta.original.setPosition) meta.view.setPosition = position => {
      meta.position = position; meta.original.setPosition.call(meta.view, position);
    };
  }
  function disposeMeta(meta) {
    if (meta.dead) return;
    meta.dead = true; meta.observer?.disconnect();
    for (const record of meta.pictures) record.img.removeEventListener('load', meta.onLoad);
    views.delete(meta); meta.caption.remove();
    if (current === meta) current = null;
    // Old cross-fade views are destroyed after 700 ms. Their camera must not
    // keep a pending one-second rise alive after its DOM has been removed.
    if (expanded?.meta === meta) {
      cancelMoves(); expanded = null;
      if (current && desired?.meta === current) drive();
    }
    meta.original.destroy.call(meta.view);
  }
  function layoutMeta(meta) {
    if (!active || meta.dead || meta.position === null || WIDE_KINDS.has(meta.slide.kind)) return false;
    const head = meta.view.el.querySelector('.slide-heading');
    const top = Math.max(54, (head?.offsetTop || 0) + (head?.offsetHeight || 0) + 12);
    const rail = Number.parseFloat(meta.view.el.style.getPropertyValue('--slide-panel-space')) || 0;
    const availableHeight = Math.max(40, height - top - Math.max(88, rail + 42));
    let signature = `${box.width}:${height}:${top}:${rail}`;
    for (const record of meta.pictures) {
      const fit = walkthroughFit(record.img.naturalWidth || 4, record.img.naturalHeight || 3, box.width - 72, availableHeight);
      // Unloaded pictures use the existing rendered size until native dimensions arrive.
      if (!record.img.naturalWidth) { fit.width = Math.min(box.width - 72, availableHeight * 4 / 3); fit.height = fit.width * 3 / 4; }
      const left = (box.width - fit.width) / 2, y = top + (availableHeight - fit.height) / 2;
      Object.assign(record, {width: fit.width, height: fit.height, left, top: y});
      signature += `:${fit.width}:${fit.height}`;
      record.pic.classList.add('wt-picture');
      record.pic.style.setProperty('--wt-width', fit.width + 'px'); record.pic.style.setProperty('--wt-height', fit.height + 'px');
      record.pic.style.setProperty('--wt-left', left + 'px'); record.pic.style.setProperty('--wt-top', y + 'px');
      if (record.cam) record.cam.style.display = 'block';
    }
    const changed = signature !== meta.signature; meta.signature = signature;
    if (changed && desired?.meta === meta) {
      desired.geometry = geometryFor(desired);
      if (expanded?.meta === meta && !flight && !frozen) applyStop();
    }
    return changed;
  }
  function frameFor(meta, mediaIndex) {
    if (meta.position === null) return -1;
    return frames.findIndex(frame => (frame.slide === meta.slide || frame.slide.id && frame.slide.id === meta.slide.id) && frame.mediaIndex === mediaIndex);
  }
  function mediaFor(meta, line, callout = null) {
    if (callout?.image_id) {
      const hit = meta.pictures.findIndex(record => record.entry.image_id === callout.image_id); if (hit >= 0) return hit;
    }
    const own = meta.slide.media_by_line?.[line];
    const mapped = meta.pictures.findIndex(record => own && record.entry.image_id === own); if (mapped >= 0) return mapped;
    let result = 0, latest = -Infinity;
    meta.pictures.forEach((record, i) => { const from = number(record.entry.from_line); if (from <= line && from >= latest) { result = i; latest = from; } });
    return result;
  }
  function geometryFor(target) {
    const record = target.meta.pictures[target.mediaIndex];
    return walkthroughStopGeometry(target.stop, record?.img.naturalWidth || 0, record?.width || record?.pic.clientWidth || 1);
  }
  function lineStart(meta, index) {
    const previous = meta.lastReveal, previousStop = meta.stop; meta.lastReveal = index;
    const eligible = (meta.slide.callouts || []).filter(item => number(item.reveal_on_line) <= index &&
      (number(item.reveal_on_line) > previous || index <= previous && number(item.reveal_on_line) === index));
    const activePicture = mediaFor(meta, index);
    const pictureChanged = desired?.meta === meta && activePicture !== desired.mediaIndex;
    const owned = eligible.filter(item => !item.image_id || item.image_id === meta.pictures[activePicture]?.entry.image_id);
    if (index >= 99 || index < 0 || pictureChanged) meta.stop = null;
    if (index >= 0 && index < 99 && owned.length) {
      meta.stop = owned.find(item => item.placement === 'overlay' && item.anchor) || owned[0]; meta.stopLine = index;
    }
    if (pictureChanged || previousStop !== meta.stop || index >= 0 && index < 99 && owned.length) version++;
    select(meta, index, meta.stop, meta.jump, activePicture);
  }
  function select(meta, line, stop, jump = meta.jump, recoveredMedia = null) {
    const mediaIndex = recoveredMedia ?? mediaFor(meta, line, stop);
    const isWide = WIDE_KINDS.has(meta.slide.kind);
    const frame = frameFor(meta, mediaIndex);
    const kind = isWide ? 'wide' : meta.position === null || frame < 0 ? 'transient' : 'content';
    desired = {meta, kind, frame, mediaIndex, stop: kind === 'content' ? stop : null, jump,
      duration: meta.slide.lines?.[stop ? meta.stopLine ?? line : line]?.duration};
    desired.geometry = geometryFor(desired);
    if (frozen && !hardPaused) resume(); else drive();
  }
  function flip(record, frame) {
    const rect = frame?.el.getBoundingClientRect(), parent = stage.getBoundingClientRect();
    if (!rect || !record) return 'translate(0px,0px) scale(1)';
    const width = record.width || record.pic.clientWidth || 1, hh = record.height || record.pic.clientHeight || 1;
    const uniform = Math.min(rect.width / width, rect.height / hh, 1);
    const x = rect.left - parent.left + rect.width / 2 - (record.left + width / 2);
    const y = rect.top - parent.top + rect.height / 2 - (record.top + hh / 2);
    return `translate(${x}px,${y}px) scale(${uniform})`;
  }
  function rise() {
    const old = expanded;
    if (!old || old.meta.dead || !old.record?.cam) { expanded = null; drive(); return; }
    clearStop(old.meta); old.meta.view.el.classList.remove('wt-expanded');
    move('rise', desired?.frame ?? -1, [{node: old.record.cam, transform: flip(old.record, frames[old.frame])}, {node: hall, opacity: 1}], 1, () => {
      revealPicture(old.meta, -1); expanded = null; drive();
    });
  }
  function applyStop() {
    if (!desired || !expanded || expanded.meta !== desired.meta) return;
    desired.geometry = geometryFor(desired);
    const {z, x, y} = desired.geometry;
    showStop(desired.meta, desired.stop, desired.geometry);
    const id = version; paintedVersion = id;
    const duration = desired.duration > 0 ? Math.min(1.6, .6 * desired.duration) : 1.2;
    const changes = [{node: expanded.record.cam, transform: `scale(${z}) translate(${x * 100}%,${y * 100}%)`}];
    if (Number.parseFloat(computed(hall).opacity) > 0) changes.push({node: hall, opacity: 0});
    move(desired.stop ? 'stop' : 'rest', desired.frame, changes, duration, () => {
        if (paintedVersion !== version) drive(); else diagnostic();
      });
  }
  function drive() {
    if (!active || destroyed || frozen || !desired) return;
    const target = desired;
    if (flight) {
      if (flight.owner === target.meta && flight.targetFrame === target.frame && target.kind === 'content') {
        if (!['stop', 'rest'].includes(flight.name) || paintedVersion === version) return;
      }
      cancelMoves();
    }
    if (target.kind === 'transient') {
      if (expanded) clearStop(expanded.meta);
      expanded = null; location = -1; flat = -1; phase = 'transient';
      hall.hidden = true; restoreMeta(target.meta); setupMeta(target.meta); diagnostic(); return;
    }
    hall.hidden = false;
    target.meta.view.el.classList.add('wt-view');
    target.meta.view.el.classList.toggle('wt-wide', target.kind === 'wide');
    if (target.kind === 'wide') {
      if (expanded) { rise(); return; }
      const end = target.meta.slide.kind !== 'hero_open';
      const index = end ? Math.max(-1, frames.length - 1) : -1;
      if (phase === 'wide' && location === index) { diagnostic(); return; }
      move('wide', -1, galleryChanges(index, false, true), target.jump ? .9 : 1.4, () => { location = index; flat = -1; phase = 'wide'; diagnostic(); });
      return;
    }
    if (expanded && (expanded.frame !== target.frame || expanded.meta !== target.meta)) { rise(); return; }
    if (location !== target.frame) {
      move('walk', target.frame, galleryChanges(target.frame), target.jump ? .9 : 1.4, () => { location = target.frame; flat = -1; drive(); }); return;
    }
    if (flat !== target.frame) {
      move('straighten', target.frame, [{node: frames[target.frame].el, transform: pose(target.frame, true)}], 1, () => { flat = target.frame; drive(); }); return;
    }
    if (!expanded) {
      const record = target.meta.pictures[target.mediaIndex];
      if (!record?.cam) { phase = 'rest'; diagnostic(); return; }
      layoutMeta(target.meta); revealPicture(target.meta, target.mediaIndex);
      record.cam.style.transition = 'none'; record.cam.style.transform = flip(record, frames[target.frame]);
      void record.cam.offsetWidth;
      expanded = {meta: target.meta, record, frame: target.frame};
      target.meta.view.el.classList.add('wt-expanded');
      move('dive', target.frame, [{node: record.cam, transform: 'scale(1) translate(0%,0%)'}, {node: hall, opacity: 0}], 1, () => { paintedVersion = -1; drive(); }); return;
    }
    if (paintedVersion !== version) applyStop();
  }
  function buildHall() {
    hall?.remove();
    hall = make('div', 'wt-hall'); hall.setAttribute('aria-hidden', 'true');
    world = make('div', 'wt-world'); hall.append(world); frames = [];
    for (const slide of deck) {
      if (WIDE_KINDS.has(slide.kind)) continue;
      entriesOf(slide).forEach((entry, mediaIndex) => {
        if (!entry.image_url) return;
        const index = frames.length, frame = make('div', 'wt-frame'), mat = make('div', 'wt-mat'), img = make('img', 'wt-frame-image');
        img.src = entry.image_url; img.alt = ''; img.draggable = false;
        mat.append(img); frame.append(mat, make('div', 'wt-label', slide.title || ''));
        Object.assign(frame.dataset, {frame: String(index), slideId: slide.id || '', mediaIndex: String(mediaIndex)});
        world.append(frame); frames.push({slide, entry, mediaIndex, el: frame, img});
      });
    }
    stage.insertBefore(hall, stack); layoutHall(); diagnostic();
  }
  function layoutHall(keepPoses = false) {
    if (!hall) return;
    height = Math.min(box.height, stack.clientHeight || box.height);
    depth = box.width * .52; side = box.width * .23;
    hall.style.height = height + 'px'; hall.style.perspective = box.width * 1.05 + 'px';
    const maxW = Math.min(box.width * .4, height * 1.2), maxH = Math.max(40, height * .56);
    frames.forEach((frame, index) => {
      const ratio = frame.img.naturalWidth && frame.img.naturalHeight ? frame.img.naturalWidth / frame.img.naturalHeight : 1.8;
      const width = Math.min(maxW, maxH * ratio), hh = width / ratio;
      frame.el.style.width = width + 'px'; frame.el.style.height = hh + 'px';
      frame.el.style.marginLeft = -width / 2 + 'px'; frame.el.style.marginTop = -hh / 2 + 'px';
      if (!keepPoses && !frozen && !moving.has(frame.el)) frame.el.style.transform = pose(index, index === flat, index < location);
    });
    if (!keepPoses && !frozen && !moving.has(world)) world.style.transform = `translateZ(${location < 0 ? -box.width * .18 : location * depth}px)`;
  }
  function resize(rect = stage.getBoundingClientRect()) {
    if (destroyed) return;
    pruneViews();
    const changed = box.width !== rect.width || box.height !== rect.height || height !== Math.min(rect.height, stack.clientHeight || rect.height);
    box = {width: Math.max(0, rect.width), height: Math.max(0, rect.height)};
    const next = !!enabled && !mediaQuery?.matches && box.width >= 700 && box.height >= 320;
    if (next !== active) {
      cancelMoves(); active = next; stage.classList.toggle('wt-active', active);
      if (!active) {
        for (const meta of views) restoreMeta(meta);
        hall?.remove(); hall = world = null; frames = []; expanded = null; location = flat = -1; phase = 'wide';
        return;
      }
      buildHall();
      const recoveredMedia = current ? recoverFallback(current) : null;
      for (const meta of views) { setupMeta(meta); layoutMeta(meta); }
      if (current) { version++; select(current, current.lastReveal, current.stop, current.jump, recoveredMedia); }
    } else if (active && changed) {
      // A new viewport invalidates the old FLIP/cap. Keep its live pose and
      // recompute the destination instead of replaying stale geometry.
      cancelMoves(); suspended = null; layoutHall(true); for (const meta of views) layoutMeta(meta);
      paintedVersion = -1; if (desired) desired.geometry = geometryFor(desired); drive();
    }
    diagnostic();
  }
  function mount(slides) {
    if (destroyed) return;
    deck = Array.isArray(slides) ? slides : bundle?.slides || [];
    if (active) { cancelMoves(); location = flat = -1; expanded = null; buildHall(); }
    resize();
  }
  function wrap(slide, view, options = {}) {
    if (!enabled || destroyed) return view;
    pruneViews();
    // Language switches reuse slide IDs. Refresh existing gallery content from
    // the actually rendered slide rather than retaining the previous language.
    for (const frame of frames) if (frame.slide.id && frame.slide.id === slide.id) {
      const entry = entriesOf(slide)[frame.mediaIndex];
      if (entry?.image_url) { frame.slide = slide; frame.entry = entry; frame.img.src = entry.image_url; frame.el.querySelector('.wt-label').textContent = slide.title || ''; }
    }
    // Keep the original handle and all unrelated methods/properties intact.
    // When narrow or reduced-motion, even the method identities stay unchanged.
    const pictures = view.walkthroughPictures || [];
    const meta = {slide, view, pictures, position: options.position, jump: !!options.jump, lastReveal: options.reveal ?? -1,
      stop: null, stopLine: null, dead: false, wasConnected: connected(view.el), installed: false, ignoreRest: false, restMarker: 0, signature: '',
      caption: make('div', 'wt-caption'), original: {setRevealed: view.setRevealed, highlight: view.highlight,
        layout: view.layout, destroy: view.destroy, ...(view.setPosition ? {setPosition: view.setPosition} : {})}};
    meta.caption.hidden = true; meta.caption.setAttribute('aria-live', 'off');
    // Fallback keeps the original DOM and method identities; observers only
    // remember the view in case this same player grows wide enough later.
    views.add(meta); current = meta;
    queueMicrotask(() => { if (!meta.dead && connected(view.el)) meta.wasConnected = true; });
    meta.onLoad = () => { layoutHall(); layoutMeta(meta); };
    meta.observer = typeof ResizeObserver === 'function' ? new ResizeObserver(() => layoutMeta(meta)) : null;
    for (const record of pictures) { meta.observer?.observe(record.pic); record.img.addEventListener('load', meta.onLoad); }
    setupMeta(meta); layoutMeta(meta);
    if (active) { version++; select(meta, meta.lastReveal, null); }
    return view;
  }
  function freeze() {
    if (!enabled || destroyed || frozen) return;
    frozen = true; suspended = flight ? {...flight, seconds: Math.max(.05, flight.seconds - (Date.now() - flight.started) / 1000)} : null;
    cancelMoves(true); stage.classList.add('wt-frozen'); diagnostic();
  }
  function pause() { if (enabled) { hardPaused = true; freeze(); } }
  function resume() {
    if (!enabled || destroyed) return;
    hardPaused = false; frozen = false; stage.classList.remove('wt-frozen'); paintedVersion = -1;
    // Resume the interrupted phase from its frozen computed pose. A newer
    // event invalidates it and retargets the latest destination instead.
    const pending = suspended; suspended = null;
    if (pending && pending.owner === desired?.meta && pending.targetFrame === desired?.frame &&
        (!['stop', 'rest'].includes(pending.name) || pending.targetVersion === version)) {
      if (['stop', 'rest'].includes(pending.name)) paintedVersion = version;
      move(pending.name, pending.targetFrame, pending.changes, pending.seconds, pending.done);
    }
    else if (expanded && desired?.kind === 'content' && expanded.frame === desired.frame) applyStop(); else drive();
    diagnostic();
  }
  function reset() {
    cancelMoves(); expanded = null; desired = null; current = null; location = flat = -1; phase = 'wide';
    frozen = hardPaused = false; suspended = null; stage.classList.remove('wt-frozen');
    for (const meta of views) { clearStop(meta); revealPicture(meta, -1); }
    hall?.remove(); hall = world = null; frames = [];
    if (active && !destroyed) buildHall(); diagnostic();
  }
  const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(() => resize()) : null;
  if (enabled) { observer?.observe(stage); observer?.observe(stack); mediaQuery?.addEventListener?.('change', onMotion); }
  function onMotion() { resize(); }
  function destroy() {
    if (destroyed) return;
    destroyed = true; cancelMoves(); observer?.disconnect(); mediaQuery?.removeEventListener?.('change', onMotion);
    for (const meta of views) { meta.observer?.disconnect(); for (const record of meta.pictures) record.img.removeEventListener('load', meta.onLoad); restoreMeta(meta); meta.caption.remove(); }
    views.clear(); hall?.remove(); hall = world = null; frames = [];
    stage.classList.remove('wt-active', 'wt-frozen');
  }
  return {mount, wrap, resize, pause, freeze, resume, reset, destroy, get active() { return active; }};
}
