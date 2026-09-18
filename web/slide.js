// One slide on a stage: the picture, callout chips at their positions (or in a side panel), leader lines to the
// anchored part, numbered dots for narrow screens. Positions are fractions of the picture, so the same numbers work
// in Align (editable: drag) and in the player (reveal per line). Plain DOM; no build step.
import { h } from "/web/api.js";

const SVG_NS = "http://www.w3.org/2000/svg";

export function renderSlide(slide, opts = {}) {
  const callouts = slide.callouts || [];
  const el = h("div", { class: `slide motion-${slide.motion || "none"}${opts.editable ? " editable" : ""}` });
  const pic = h("div", { class: "slide-pic" + (slide.image_url ? "" : " noimg") });
  const img = h("img", { alt: "", draggable: "false" });
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
  el.append(pic, panel);

  function layout() {  // leader lines run from each chip's centre to its anchor; chip size is only known after layout
    const W = pic.clientWidth || 1, H = pic.clientHeight || 1;
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
  }
  function highlight(id) { for (const [cid, chip] of chips) chip.classList.toggle("hot", cid === id); for (const it of panel.children) it.classList.toggle("hot", it.dataset.id === id); }
  function setImage(url, parts) { pic.classList.toggle("noimg", !url); img.src = url || ""; slide.image_parts = parts || []; }
  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(layout) : null; ro?.observe(pic);
  img.addEventListener("load", layout);
  requestAnimationFrame(layout);
  return { el, pic, img, layout, setRevealed, highlight, setImage, destroy: () => { ro?.disconnect(); el.remove(); } };
}
