// One slide on a stage: the picture, callout chips on the slide, leader lines to the
// anchored part, numbered dots for narrow screens. Positions are fractions of the picture, so the same numbers work
// in Align (editable: drag) and in the player (reveal per line). Plain DOM; no build step.
import { h } from "/web/api.js";

const SVG_NS = "http://www.w3.org/2000/svg";

// Include touching/collinear segments: a shared run of line is as confusing as a cross.
function segmentsIntersect(a, b) {
  const cross = (p, q, r) => (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x);
  const inside = (p, q, r) => r.x >= Math.min(p.x, q.x) - .01 && r.x <= Math.max(p.x, q.x) + .01 && r.y >= Math.min(p.y, q.y) - .01 && r.y <= Math.max(p.y, q.y) + .01;
  const ab1 = cross(a[0], a[1], b[0]), ab2 = cross(a[0], a[1], b[1]);
  const ba1 = cross(b[0], b[1], a[0]), ba2 = cross(b[0], b[1], a[1]);
  return (ab1 * ab2 < 0 && ba1 * ba2 < 0) ||
    (Math.abs(ab1) < .01 && inside(a[0], a[1], b[0])) || (Math.abs(ab2) < .01 && inside(a[0], a[1], b[1])) ||
    (Math.abs(ba1) < .01 && inside(b[0], b[1], a[0])) || (Math.abs(ba2) < .01 && inside(b[0], b[1], a[1]));
}
function segmentHitsBox(line, box) {
  const corners = [{x: box.left, y: box.top}, {x: box.right, y: box.top}, {x: box.right, y: box.bottom}, {x: box.left, y: box.bottom}];
  return line.some(p => p.x >= box.left && p.x <= box.right && p.y >= box.top && p.y <= box.bottom) ||
    corners.some((p, i) => segmentsIntersect(line, [p, corners[(i + 1) % 4]]));
}

// Start at the label edge, keeping the pointer out of the label text.
function labelEdge(box, anchor) {
  const x = (box.left + box.right) / 2, y = (box.top + box.bottom) / 2;
  const dx = anchor.x - x, dy = anchor.y - y;
  const scale = Math.min(dx ? (box.right - box.left) / 2 / Math.abs(dx) : Infinity,
    dy ? (box.bottom - box.top) / 2 / Math.abs(dy) : Infinity, 1);
  return {x: x + dx * scale, y: y + dy * scale};
}

export function renderSlide(slide, opts = {}) {
  const callouts = slide.callouts || [];
  const kind = slide.kind || "proof";
  const theme = ["marine", "sage", "graphite"].includes(opts.theme) ? opts.theme : "marine";
  const el = h("div", { class: `slide slide-${kind} motion-${slide.motion || "none"}${opts.fit ? " cinematic" : ""}${opts.editable ? " editable" : ""}`, "data-visual-theme": theme });
  const entries = slide.media?.length ? slide.media.slice(0, 2) : [{ image_id: slide.image_id || "", image_url: slide.image_url, image_parts: slide.image_parts || [], from_line: 0 }];
  const media = h("div", { class: "slide-media" + (entries.length > 1 ? " multi" : "") });
  el.classList.toggle("has-multiple-media", entries.length > 1);
  const pictures = entries.map((entry, index) => {
  const url = entry.image_url ?? (index === 0 ? slide.image_url : null);
  const pic = h("div", { class: "slide-pic" + (url ? "" : " noimg"), "data-image-id": entry.image_id || "" });
  const img = h("img", { alt: slide.title || "Product view", draggable: "false" });
  const leaders = document.createElementNS(SVG_NS, "svg");
  leaders.setAttribute("class", "leaders"); leaders.setAttribute("viewBox", "0 0 100 100"); leaders.setAttribute("preserveAspectRatio", "none");
  pic.append(img, leaders);
  if (url) img.src = url; else pic.append(h("span", {}, "no picture"));
  if (entry.proxy) pic.append(h("span", { class: "slide-proxy-badge", title: entry.proxy_reason || "This picture illustrates the topic; it is not visual proof." }, "illustration"));
  media.append(pic);
  return { pic, img, leaders, entry };
  });
  const { pic, img } = pictures[0]; // Existing player/editor callers use the first-image aliases.
  const chips = new Map(), dots = new Map(), lines = new Map(), owners = new Map();
  callouts.forEach((c, k) => {
    const picture = pictures.find((item) => item.entry.image_id === c.image_id) || pictures[0];
    owners.set(c.id, picture);
    const { pic, leaders } = picture;
    const num = String(k + 1);
    if (c.placement === "overlay" && c.label_pos && c.anchor) {
      const chip = h("div", { class: "callout", "data-id": c.id, style: `left:${c.label_pos.x * 100}%;top:${c.label_pos.y * 100}%` }, h("span", { class: "num" }, num), h("span", { class: "txt" }, c.text));
      const dot = h("div", { class: "dot", "data-id": c.id, style: `left:${c.anchor.x * 100}%;top:${c.anchor.y * 100}%` }, h("span", { class: "num" }, num));
      if (opts.fit && !opts.editable) { dot.setAttribute("role", "button"); dot.setAttribute("tabindex", "0"); dot.setAttribute("aria-label", `Detail ${num}: ${c.text}`); const focusDetail = () => { highlight(c.id); const item = panel.querySelector(`[data-id="${c.id}"]`); if (item?.offsetWidth) panel.scrollLeft = item.offsetLeft; }; dot.addEventListener("click", focusDetail); dot.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); focusDetail(); } }); }
      const ln = document.createElementNS(SVG_NS, "line"); ln.setAttribute("x2", String(c.anchor.x * 100)); ln.setAttribute("y2", String(c.anchor.y * 100));
      leaders.append(ln); pic.append(dot, chip); chips.set(c.id, chip); dots.set(c.id, dot); lines.set(c.id, ln);
      if (opts.editable) drag(chip, c, pic);
    }
  });
  const panel = h("div", { class: "slide-panel" }, ...callouts.map((c, k) => h("div", { class: "item " + (c.placement === "overlay" && c.label_pos ? "overlay" : "panel"), "data-id": c.id, "data-image-id": owners.get(c.id).entry.image_id || "" },
    h("span", { class: "num" }, String(k + 1)), h("span", {}, c.text, c.fact_ids?.length ? h("div", { class: "cite" }, c.fact_ids.join(", ")) : null))));
  if (opts.fit) {
    const chapter = ({hero_open: "A closer look", intro: "Meet your next possibility", outcome: "Made for your everyday",
      proof: "Look a little closer", features: "The details that matter", establish: "Before you decide",
      closing: "Your next move", hero_close: "Make it yours", custom: "Chosen for you"})[kind] || "Explore the details";
    el.append(h("div", {class: "slide-heading"}, h("div", {class: "slide-chapter"}, chapter),
      h("h2", {class: "slide-title"}, slide.title || "Explore the details")));
  }
  const scrollHint = opts.fit ? h("span", { class: "slide-scroll-hint", hidden: true, "aria-hidden": "true" }) : null;
  el.append(media, panel); if (scrollHint) el.append(scrollHint);

  function updateScrollHint() {
    if (!scrollHint) return;
    const overflow = el.clientWidth < 700 && panel.clientHeight > 0 && panel.scrollWidth > panel.clientWidth + 2 && !el.closest(".pl-stage")?.querySelector(".pl-intake.open");
    scrollHint.hidden = !overflow;
    if (!overflow) return;
    const before = panel.scrollLeft > 2, after = panel.scrollWidth - panel.clientWidth - panel.scrollLeft > 2;
    scrollHint.textContent = `${before ? "← " : ""}Swipe for more${after ? " →" : ""}`;
    // The cue floats above the measured rail; it never changes the image or card boxes.
    scrollHint.style.right = Math.max(0, el.clientWidth - panel.offsetLeft - panel.clientWidth) + "px";
    scrollHint.style.bottom = Math.max(0, el.clientHeight - panel.offsetTop + 7) + "px";
  }
  panel.addEventListener("scroll", updateScrollHint, { passive: true });

  function layout() {  // label edges connect to reviewed anchors after browser measurement
    const SW = el.clientWidth || 1, SH = el.clientHeight || 1, small = SW < 700;
    media.classList.toggle("stacked", small);
    if (opts.fit) {
      const intake = !!el.closest(".pl-stage")?.querySelector(".pl-intake.open");
      const area = pictures.length > 1
        ? {x: 0, y: SH * .25, w: SW, h: SH * .50}
        : intake ? (small
          ? {x: 16, y: kind === "hero_open" ? 18 : SH * .23, w: SW - 32, h: SH * (kind === "hero_open" ? .55 : .57)}
          : {x: SW * .37, y: 18, w: SW * .60, h: SH - 36})
        : small ? {x: 0, y: SH * .25, w: SW, h: SH * .50}
        : {x: 0, y: 0, w: SW, h: SH};
      pictures.forEach(({ pic, img }, index) => {
        // Each annotation box fits its own native pixels into its allotted half.
        const R = img.naturalWidth && img.naturalHeight ? img.naturalWidth / img.naturalHeight : 4 / 3;
        const gap = 12, pair = pictures.length > 1;
        const slot = pair ? (small
          ? {x: area.x, y: area.y + index * (area.h + gap) / 2, w: area.w, h: (area.h - gap) / 2}
          : {x: area.x + index * (area.w + gap) / 2, y: area.y, w: (area.w - gap) / 2, h: area.h}) : area;
        let w = slot.w, hh = w / R; if (hh > slot.h) { hh = slot.h; w = hh * R; }
        pic.style.width = Math.round(w) + "px"; pic.style.height = Math.round(hh) + "px";
        pic.style.left = Math.round(slot.x + (slot.w - w) * (pair || small || intake ? .5 : 1)) + "px";
        pic.style.top = Math.round(slot.y + (slot.h - hh) / 2) + "px";
      });
    }
    for (const c of callouts) {
      chips.get(c.id)?.classList.remove("rail-only"); lines.get(c.id)?.classList.remove("rail-only");
      panel.querySelector(`[data-id="${c.id}"]`)?.classList.remove("rail-fallback");
    }
    if (opts.fit && !opts.editable && el.clientWidth >= 700 && !el.closest(".pl-stage")?.querySelector(".pl-intake.open")) {
      // Saved Align positions are preferred. If cinematic overlay copy would cover a
      // label, move only its displayed box; the truthful anchor and saved data stay fixed.
      const stage = el.getBoundingClientRect(), heading = el.querySelector(".slide-heading");
      // Reserve the whole evidence band, even before a fallback makes it visible.
      // Use unanimated heading bounds so repeated layouts cannot move the labels.
      const occupied = [{left: stage.left, right: stage.right, top: stage.top + el.clientHeight * .65, bottom: stage.bottom}];
      if (heading) occupied.push({left: stage.left + heading.offsetLeft, right: stage.left + heading.offsetLeft + heading.offsetWidth,
        top: stage.top + heading.offsetTop, bottom: stage.top + heading.offsetTop + heading.offsetHeight});
      const overlaps = (a, b) => a.left < b.right + 12 && a.right > b.left - 12 && a.top < b.bottom + 12 && a.bottom > b.top - 12;
      const anchorBoxes = callouts.filter(c => c.anchor && dots.has(c.id)).map(c => {
        const owner = owners.get(c.id).pic, p = owner.getBoundingClientRect();
        const x = p.left + c.anchor.x * owner.clientWidth, y = p.top + c.anchor.y * owner.clientHeight;
        return {left: x - 12, right: x + 12, top: y - 12, bottom: y + 12};
      });
      const placedLeaders = [];
      for (const c of callouts) {
        const chip = chips.get(c.id); if (!chip || chip.classList.contains("hidden")) continue;
        const pic = owners.get(c.id).pic, p = pic.getBoundingClientRect();
        const W = pic.clientWidth || 1, H = pic.clientHeight || 1;
        const cw = chip.offsetWidth, ch = chip.offsetHeight;
        // Prefer the reviewed label, then nearby positions. Never move its true
        // image anchor; only the display label is adjusted for this viewport.
        const nearby = [
          {x: c.anchor.x + .04, y: c.anchor.y - ch / H / 2},
          {x: c.anchor.x - cw / W - .04, y: c.anchor.y - ch / H / 2},
          {x: c.anchor.x - cw / W / 2, y: c.anchor.y - ch / H - .07},
          {x: c.anchor.x - cw / W / 2, y: c.anchor.y + .07},
          ...[.08, .28, .48].flatMap(y => [.08, .38, .68].map(x => ({x, y}))),
        ].sort((a, b) => Math.hypot(a.x + cw / W / 2 - c.anchor.x, a.y + ch / H / 2 - c.anchor.y) - Math.hypot(b.x + cw / W / 2 - c.anchor.x, b.y + ch / H / 2 - c.anchor.y));
        const savedDistance = Math.hypot((c.label_pos.x + cw / W / 2 - c.anchor.x) * W, (c.label_pos.y + ch / H / 2 - c.anchor.y) * H);
        const positions = savedDistance <= W * .3 ? [c.label_pos, ...nearby] : [...nearby, c.label_pos];
        let chosen = null;
        for (const pos of positions) {
          if (cw + 16 > W || ch + 16 > H) break;
          const x = Math.max(8, Math.min(W - cw - 8, pos.x * W)), y = Math.max(8, Math.min(H - ch - 8, pos.y * H));
          const rect = {left: p.left + x, top: p.top + y, right: p.left + x + cw, bottom: p.top + y + ch};
          const anchor = {x: p.left + c.anchor.x * W, y: p.top + c.anchor.y * H};
          const line = [labelEdge(rect, anchor), anchor];
          if (!anchorBoxes.some(o => overlaps(rect, o)) && !occupied.some((o, i) => overlaps(rect, o) || (i > 0 && segmentHitsBox(line, o))) &&
              !placedLeaders.some(other => segmentsIntersect(line, other) || segmentHitsBox(other, rect))) { chosen = {x, y, rect, line}; break; }
        }
        // Tight stages keep the full label in the on-slide caption band.
        const fallback = !chosen;
        chip.classList.toggle("rail-only", fallback); lines.get(c.id)?.classList.toggle("rail-only", fallback);
        panel.querySelector(`[data-id="${c.id}"]`)?.classList.toggle("rail-fallback", fallback);
        if (chosen) { chip.style.left = chosen.x + "px"; chip.style.top = chosen.y + "px"; occupied.push(chosen.rect); placedLeaders.push(chosen.line); }
      }
    }
    for (const c of callouts) {
      const chip = chips.get(c.id), ln = lines.get(c.id); if (!chip || !ln) continue;
      const owner = owners.get(c.id).pic, W = owner.clientWidth || 1, H = owner.clientHeight || 1;
      const edge = labelEdge({left: chip.offsetLeft, top: chip.offsetTop, right: chip.offsetLeft + chip.offsetWidth, bottom: chip.offsetTop + chip.offsetHeight}, {x: c.anchor.x * W, y: c.anchor.y * H});
      ln.setAttribute("x1", String(edge.x / W * 100)); ln.setAttribute("y1", String(edge.y / H * 100));
    }
    // Align's saved positions can also cross. Preserve the data (and draggable chips
    // while editing), but never draw intersecting leaders or a leader through another label.
    const visible = [];
    for (const c of callouts) {
      const chip = chips.get(c.id), ln = lines.get(c.id);
      if (!chip || chip.classList.contains("hidden") || chip.classList.contains("rail-only")) continue;
      const owner = owners.get(c.id).pic, p = owner.getBoundingClientRect();
      const rect = {left: p.left + chip.offsetLeft, top: p.top + chip.offsetTop, right: p.left + chip.offsetLeft + chip.offsetWidth, bottom: p.top + chip.offsetTop + chip.offsetHeight};
      const anchor = {x: p.left + c.anchor.x * owner.clientWidth, y: p.top + c.anchor.y * owner.clientHeight};
      const line = [labelEdge(rect, anchor), anchor];
      const collision = visible.some(other => (rect.left < other.rect.right && rect.right > other.rect.left && rect.top < other.rect.bottom && rect.bottom > other.rect.top) ||
        segmentsIntersect(line, other.line) || segmentHitsBox(line, other.rect) || segmentHitsBox(other.line, rect));
      if (collision) {
        ln?.classList.add("rail-only");
        if (!opts.editable) chip.classList.add("rail-only");
        panel.querySelector(`[data-id="${c.id}"]`)?.classList.add("rail-fallback");
      } else visible.push({rect, line});
    }
    updateScrollHint();
  }
  function drag(chip, c, pic) {
    let start = null;
    chip.addEventListener("pointerdown", (e) => { e.preventDefault(); try { chip.setPointerCapture(e.pointerId); } catch (err) {} chip.classList.add("dragging"); start = { x: e.clientX, y: e.clientY, left: chip.offsetLeft, top: chip.offsetTop }; });
    chip.addEventListener("pointermove", (e) => { if (!start) return; const W = pic.clientWidth || 1, H = pic.clientHeight || 1; const left = Math.max(0, Math.min(W - chip.offsetWidth, start.left + e.clientX - start.x)), top = Math.max(0, Math.min(H - chip.offsetHeight, start.top + e.clientY - start.y)); chip.style.left = (left / W * 100) + "%"; chip.style.top = (top / H * 100) + "%"; layout(); });
    const end = (e) => { if (!start) return; start = null; chip.classList.remove("dragging"); try { chip.releasePointerCapture(e.pointerId); } catch (err) {} const W = pic.clientWidth || 1, H = pic.clientHeight || 1; const pos = { x: +(chip.offsetLeft / W).toFixed(4), y: +(chip.offsetTop / H).toFixed(4) }; c.label_pos = pos; if (opts.onMove) opts.onMove(c.id, pos, owners.get(c.id).entry.image_id); };
    chip.addEventListener("pointerup", end); chip.addEventListener("pointercancel", end);
  }
  function setRevealed(lineIdx) {  // player: a callout appears when the line it supports starts; -1 hides all
    for (const c of callouts) { const on = c.reveal_on_line <= lineIdx; chips.get(c.id)?.classList.toggle("hidden", !on); dots.get(c.id)?.classList.toggle("hidden", !on); lines.get(c.id)?.classList.toggle("hidden", !on); panel.querySelector(`[data-id="${c.id}"]`)?.classList.toggle("hidden", !on); }
    let active = 0, latest = -Infinity;
    pictures.forEach(({ entry }, index) => { const from = Number(entry.from_line) || 0; if (from <= lineIdx && from >= latest) { active = index; latest = from; } });
    // Personalized runtime speech can revisit a picture after another one.
    // Its ownership map is derived from reviewed line indexes in player.js.
    const reviewedOwner = pictures.findIndex(({ entry }) => entry.image_id === slide.media_by_line?.[lineIdx]);
    if (reviewedOwner >= 0) active = reviewedOwner;
    pictures.forEach(({ pic }, index) => { pic.classList.toggle("active", index === active); pic.classList.toggle("dimmed", index !== active); });
    // A hidden chip has no dimensions. Recompute its leader only after it is visible.
    layout();
  }
  function highlight(id) { for (const [cid, chip] of chips) chip.classList.toggle("hot", cid === id); for (const [cid, dot] of dots) dot.classList.toggle("hot", cid === id); for (const it of panel.children) it.classList.toggle("hot", it.dataset.id === id); }
  function setImage(url, parts, index = 0) {
    const picture = pictures[index]; if (!picture) return;
    picture.pic.classList.toggle("noimg", !url); picture.img.src = url || "";
    picture.entry.image_url = url; picture.entry.image_parts = parts || [];
    if (index === 0) slide.image_parts = parts || [];
  }
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(layout) : null;
  pictures.forEach(({ pic, img }) => { ro?.observe(pic); img.addEventListener("load", layout); });
  ro?.observe(el); if (opts.fit) ro?.observe(panel);
  requestAnimationFrame(layout);
  return { el, pic, img, pics: pictures.map((item) => item.pic), images: pictures.map((item) => item.img), layout, setRevealed, highlight, setImage, destroy: () => { ro?.disconnect(); el.remove(); } };
}
