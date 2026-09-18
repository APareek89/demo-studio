// One slide on a stage: the picture, callout chips at their positions (or in a side panel), leader lines to the
// anchored part, numbered dots for narrow screens. Positions are fractions of the picture, so the same numbers work
// in Align (editable: drag) and in the player (reveal per line). Plain DOM; no build step.
import { h } from "/web/api.js";

const SVG_NS = "http://www.w3.org/2000/svg";

export function renderSlide(slide, opts = {}) {
  const callouts = slide.callouts || [];
  const kind = slide.kind || "proof";
  const el = h("div", { class: `slide slide-${kind} motion-${slide.motion || "none"}${opts.fit ? " cinematic" : ""}${opts.editable ? " editable" : ""}` });
  const pic = h("div", { class: "slide-pic" + (slide.image_url ? "" : " noimg") });
  const img = h("img", { alt: slide.title || "Product view", draggable: "false" });
  const leaders = document.createElementNS(SVG_NS, "svg");
  leaders.setAttribute("class", "leaders"); leaders.setAttribute("viewBox", "0 0 100 100"); leaders.setAttribute("preserveAspectRatio", "none");
  const chips = new Map(), dots = new Map(), lines = new Map();
  pic.append(img, leaders);
  if (slide.image_url) img.src = slide.image_url; else pic.append(h("span", {}, "no picture"));
  callouts.forEach((c, k) => {
    const num = String(k + 1);
    if (c.placement === "overlay" && c.label_pos && c.anchor) {
      const chip = h("div", { class: "callout", "data-id": c.id, style: `left:${c.label_pos.x * 100}%;top:${c.label_pos.y * 100}%` }, h("span", { class: "num" }, num), h("span", { class: "txt" }, c.text));
      const dot = h("div", { class: "dot", "data-id": c.id, style: `left:${c.anchor.x * 100}%;top:${c.anchor.y * 100}%` }, h("span", { class: "num" }, num));
      const ln = document.createElementNS(SVG_NS, "line"); ln.setAttribute("x2", String(c.anchor.x * 100)); ln.setAttribute("y2", String(c.anchor.y * 100));
      leaders.append(ln); pic.append(dot, chip); chips.set(c.id, chip); dots.set(c.id, dot); lines.set(c.id, ln);
      if (opts.editable) drag(chip, c);
    }
  });
  const panel = h("div", { class: "slide-panel" }, ...callouts.map((c, k) => h("div", { class: "item " + (c.placement === "overlay" && c.label_pos ? "overlay" : "panel"), "data-id": c.id },
    h("span", { class: "num" }, String(k + 1)), h("span", {}, c.text, c.fact_ids?.length ? h("div", { class: "cite" }, c.fact_ids.join(", ")) : null))));
  if (opts.fit) {
    const chapter = ({hero_open: "A closer look", intro: "Meet your next possibility", outcome: "Made for your everyday",
      proof: "Look a little closer", features: "The details that matter", establish: "Before you decide",
      closing: "Your next move", hero_close: "Make it yours", custom: "Chosen for you"})[kind] || "Explore the details";
    el.append(h("div", {class: "slide-heading"}, h("div", {class: "slide-chapter"}, chapter),
      h("h2", {class: "slide-title"}, slide.title || "Explore the details")));
  }
  el.append(pic, panel);

  function layout() {  // leader lines run from each chip's centre to its anchor; chip size is only known after layout
    if (opts.fit && img.naturalWidth && img.naturalHeight) {  // player: the picture box is the largest one of the image's ratio that fits the stage
      const SW = el.clientWidth || 1, SH = el.clientHeight || 1, R = img.naturalWidth / img.naturalHeight;
      // Cinematic composition uses the whole stage. Keep the image's native box so
      // Align's normalized anchor and label positions still refer to the same pixels.
      // The existing welcome/intake composition is deliberately unchanged.
      const small = SW < 700, intake = !!el.closest(".pl-stage")?.querySelector(".pl-intake.open");
      const area = intake ? (small
        ? {x: 16, y: kind === "hero_open" ? 18 : SH * .23, w: SW - 32, h: SH * (kind === "hero_open" ? .55 : .57)}
        : {x: SW * .37, y: 18, w: SW * .60, h: SH - 36})
        : small ? {x: 0, y: SH * .25, w: SW, h: SH * .50}
        : {x: 0, y: 0, w: SW, h: SH};
      let w = area.w, hh = w / R; if (hh > area.h) { hh = area.h; w = hh * R; }
      pic.style.width = Math.round(w) + "px"; pic.style.height = Math.round(hh) + "px";
      pic.style.left = Math.round(area.x + (area.w - w) * (small || intake ? .5 : 1)) + "px";
      pic.style.top = Math.round(area.y + (area.h - hh) / 2) + "px";
    }
    const W = pic.clientWidth || 1, H = pic.clientHeight || 1;
    if (opts.fit && el.clientWidth >= 700 && !el.closest(".pl-stage")?.querySelector(".pl-intake.open")) {
      // Saved Align positions are preferred. If cinematic overlay copy would cover a
      // label, move only its displayed box; the truthful anchor and saved data stay fixed.
      const p = pic.getBoundingClientRect();
      const stage = el.getBoundingClientRect(), heading = el.querySelector(".slide-heading");
      // Reserve the whole evidence band, even before a fallback makes it visible.
      // Use unanimated heading bounds so repeated layouts cannot move the labels.
      const occupied = [{left: stage.left, right: stage.right, top: stage.top + el.clientHeight * .65, bottom: stage.bottom}];
      if (heading) occupied.push({left: stage.left + heading.offsetLeft, right: stage.left + heading.offsetLeft + heading.offsetWidth,
        top: stage.top + heading.offsetTop, bottom: stage.top + heading.offsetTop + heading.offsetHeight});
      const overlaps = (a, b) => a.left < b.right + 12 && a.right > b.left - 12 && a.top < b.bottom + 12 && a.bottom > b.top - 12;
      for (const c of callouts) {
        const chip = chips.get(c.id); if (!chip || chip.classList.contains("hidden")) continue;
        const cw = chip.offsetWidth, ch = chip.offsetHeight;
        const positions = [c.label_pos, {x: .68, y: .14}, {x: .68, y: .43}, {x: .42, y: .08}, {x: .45, y: .64}];
        let chosen = null;
        for (const pos of positions) {
          if (cw + 16 > W || ch + 16 > H) break;
          const x = Math.max(8, Math.min(W - cw - 8, pos.x * W)), y = Math.max(8, Math.min(H - ch - 8, pos.y * H));
          const rect = {left: p.left + x, top: p.top + y, right: p.left + x + cw, bottom: p.top + y + ch};
          if (!occupied.some(o => overlaps(rect, o))) { chosen = {x, y, rect}; break; }
        }
        // Tight stages can use the evidence rail rather than crop or hide the claim.
        const fallback = !chosen;
        chip.classList.toggle("rail-only", fallback); lines.get(c.id)?.classList.toggle("rail-only", fallback);
        panel.querySelector(`[data-id="${c.id}"]`)?.classList.toggle("rail-fallback", fallback);
        if (chosen) { chip.style.left = chosen.x + "px"; chip.style.top = chosen.y + "px"; occupied.push(chosen.rect); }
      }
    } else if (opts.fit) {
      for (const c of callouts) {
        chips.get(c.id)?.classList.remove("rail-only"); lines.get(c.id)?.classList.remove("rail-only");
        panel.querySelector(`[data-id="${c.id}"]`)?.classList.remove("rail-fallback");
      }
    }
    for (const [id, chip] of chips) { const ln = lines.get(id); if (!ln) continue; ln.setAttribute("x1", String((chip.offsetLeft + chip.offsetWidth / 2) / W * 100)); ln.setAttribute("y1", String((chip.offsetTop + chip.offsetHeight / 2) / H * 100)); }
  }
  function drag(chip, c) {
    let start = null;
    chip.addEventListener("pointerdown", (e) => { e.preventDefault(); chip.setPointerCapture(e.pointerId); chip.classList.add("dragging"); start = { x: e.clientX, y: e.clientY, left: chip.offsetLeft, top: chip.offsetTop }; });
    chip.addEventListener("pointermove", (e) => { if (!start) return; const W = pic.clientWidth || 1, H = pic.clientHeight || 1; const left = Math.max(0, Math.min(W - chip.offsetWidth, start.left + e.clientX - start.x)), top = Math.max(0, Math.min(H - chip.offsetHeight, start.top + e.clientY - start.y)); chip.style.left = (left / W * 100) + "%"; chip.style.top = (top / H * 100) + "%"; layout(); });
    const end = (e) => { if (!start) return; start = null; chip.classList.remove("dragging"); try { chip.releasePointerCapture(e.pointerId); } catch (err) {} const W = pic.clientWidth || 1, H = pic.clientHeight || 1; const pos = { x: +(chip.offsetLeft / W).toFixed(4), y: +(chip.offsetTop / H).toFixed(4) }; c.label_pos = pos; if (opts.onMove) opts.onMove(c.id, pos); };
    chip.addEventListener("pointerup", end); chip.addEventListener("pointercancel", end);
  }
  function setRevealed(lineIdx) {  // player: a callout appears when the line it supports starts; -1 hides all
    for (const c of callouts) { const on = c.reveal_on_line <= lineIdx; chips.get(c.id)?.classList.toggle("hidden", !on); dots.get(c.id)?.classList.toggle("hidden", !on); lines.get(c.id)?.classList.toggle("hidden", !on); panel.querySelector(`[data-id="${c.id}"]`)?.classList.toggle("hidden", !on); }
    // A hidden chip has no dimensions. Recompute its leader only after it is visible.
    layout();
  }
  function highlight(id) { for (const [cid, chip] of chips) chip.classList.toggle("hot", cid === id); for (const it of panel.children) it.classList.toggle("hot", it.dataset.id === id); }
  function setImage(url, parts) { pic.classList.toggle("noimg", !url); img.src = url || ""; slide.image_parts = parts || []; }
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(layout) : null; ro?.observe(pic); if (opts.fit) ro?.observe(el);
  img.addEventListener("load", layout);
  requestAnimationFrame(layout);
  return { el, pic, img, layout, setRevealed, highlight, setImage, destroy: () => { ro?.disconnect(); el.remove(); } };
}
