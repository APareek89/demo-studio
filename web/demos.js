import { api, h, toast, fmtTime } from "/web/api.js";
import { icon } from "/web/icons.js";

const STATUS_LABEL = { sources: "Add sources", reading: "Reading sources", align: "In review", building: "Building", ready: "Ready to present", error: "Needs attention" };
const STATUS_CLASS = { ready: "ok", align: "warn", building: "run", reading: "run", error: "bad" };
export const studioPath = (d) => `#/studio/${d.id}/${d.status === "sources" ? "sources" : d.status === "ready" ? "rehearse" : "align"}`;
const previewCache = new Map();
export function demoImage(d) {
  const key = `${d.id}:${d.version || 0}:${d.updated_at || 0}`;
  if (!previewCache.has(key)) {
    for (const old of previewCache.keys()) if (old.startsWith(d.id + ":")) previewCache.delete(old);
    previewCache.set(key, api.get(`/api/demos/${d.id}/bundle`).then(b => b.media?.hero || b.slides?.find(s => s.image_url)?.image_url || "").catch(() => { previewCache.delete(key); return ""; }));
  }
  return previewCache.get(key);
}


export function demoCard(d, navigate, refresh, { compact = false } = {}) {
  const media = h("div", { class: "demo-art" }, h("div", { class: "demo-art-icon" }, icon(/nexon|brezza|venue|car|audi|creta|iqube|tvs/i.test(d.name) ? "car" : "layers", { size: 48 })), h("span", { class: "demo-art-label" }, "PRODUCT DEMO"));
  const title = h("a", { href: studioPath(d), class: "demo-card-title" }, d.name);
  const card = h("article", { class: `demo-card${compact ? " compact" : ""}` }, media,
    h("div", { class: "demo-card-body" },
      h("div", { class: "demo-card-status" }, h("span", { class: "pill " + (STATUS_CLASS[d.status] || "") }, STATUS_LABEL[d.status] || d.status), h("span", { class: "small muted" }, `v${d.version || 0}`)),
      title,
      h("div", { class: "demo-card-metrics" }, h("span", {}, icon("file", { size: 15 }), `${d.sources || 0} source${d.sources === 1 ? "" : "s"}`), h("span", {}, icon("users", { size: 15 }), `${d.sessions || 0} session${d.sessions === 1 ? "" : "s"}`)),
      h("div", { class: "demo-card-foot" },
        h("button", { class: "btn sm " + (d.status === "ready" ? "primary" : ""), onclick: () => { if (d.status === "ready") document.documentElement.requestFullscreen?.().catch(() => {}); navigate(d.status === "ready" ? `#/play/${d.id}` : studioPath(d)); } }, icon(d.status === "ready" ? "play" : "arrow-right", { size: 16 }), d.status === "ready" ? "View demo" : "Continue"),
        d.status === "ready" ? h("a", { class: "demo-edit", href: studioPath(d) }, "Open studio", icon("arrow-right", { size: 14 })) : h("span", { class: "small muted" }, fmtTime(d.updated_at)),
        !compact ? h("details", { class: "card-menu" }, h("summary", { "aria-label": `More actions for ${d.name}` }, icon("settings", { size: 18 })),
          h("div", { class: "card-menu-panel" },
            h("button", { onclick: async () => { try { await api.post(`/api/demos/${d.id}/duplicate`); toast("Demo duplicated"); refresh(); } catch (e) { toast(e.message, true); } } }, icon("copy", { size: 16 }), "Duplicate"),
            h("button", { class: "danger", onclick: async () => { if (!confirm(`Delete “${d.name}” and all its files?`)) return; try { await api.del(`/api/demos/${d.id}`); refresh(); } catch (e) { toast(e.message, true); } } }, icon("trash", { size: 16 }), "Delete"),
            h("span", { class: "menu-id" }, d.id, d.location === "cloud" ? " · Cloud only" : d.location === "local+cloud" ? " · Synced" : "")),
        ) : null,
      ),
    ),
  );
  // Use the demo's existing approved product imagery, never stock substitutes.
  if (d.status === "ready") demoImage(d).then((src) => {
    if (!src || /\.(mp4|webm|mov)(\?|$)/i.test(src)) return;
    const img = h("img", { src, alt: d.name, loading: "lazy", onload: () => { media.classList.add("has-image"); }, onerror: () => img.remove() });
    media.prepend(img);
  }).catch(() => {});
  return card;
}

export async function renderDemos({ main, navigate }) {
  main.replaceChildren(h("div", { class: "page" }, h("div", { class: "page-loading", role: "status" }, "Loading your demos…")));
  let demos;
  try { demos = await api.get("/api/demos"); }
  catch (e) { main.replaceChildren(h("div", { class: "page" }, h("div", { class: "empty" }, icon("alert-circle", { size: 32 }), h("h2", {}, "Your demos couldn’t load"), h("p", {}, e.message), h("button", { class: "btn", onclick: () => renderDemos({ main, navigate }) }, "Try again")))); return; }
  let filter = "all";
  const grid = h("div", { class: "demo-grid" });
  const search = h("input", { type: "search", placeholder: "Search demos…", "aria-label": "Search demos", oninput: update });
  const filters = ["all", "ready", "progress"].map((key) => h("button", { class: "filter-tab" + (key === filter ? " active" : ""), "aria-pressed": key === filter ? "true" : "false", onclick: () => { filter = key; update(); } }, key === "all" ? "All demos" : key === "ready" ? "Ready to present" : "In progress"));
  const page = h("div", { class: "page library-page" },
    h("div", { class: "page-head" }, h("div", {}, h("div", { class: "eyebrow" }, "YOUR WORKSPACE"), h("h1", {}, "My demos"), h("p", { class: "page-description" }, "Create, refine and share the story behind every product.")), h("button", { class: "btn primary", onclick: () => newDemoModal(navigate) }, icon("plus", { size: 18 }), "New demo")),
    h("div", { class: "library-toolbar" }, h("div", { class: "filter-tabs", "aria-label": "Filter demos" }, ...filters), h("label", { class: "search-field" }, icon("search", { size: 18 }), search)), grid);
  main.replaceChildren(page);
  function update() {
    filters.forEach((b, i) => { const selected = ["all", "ready", "progress"][i] === filter; b.classList.toggle("active", selected); b.setAttribute("aria-pressed", String(selected)); });
    const list = demos.filter(d => d.name.toLowerCase().includes(search.value.trim().toLowerCase()) && (filter === "all" || (filter === "ready" ? d.status === "ready" : d.status !== "ready")));
    grid.replaceChildren(...list.map(d => demoCard(d, navigate, () => renderDemos({ main, navigate }))));
    if (!list.length) grid.append(h("div", { class: "empty library-empty" }, icon(demos.length ? "search" : "layers", { size: 40 }), h("h2", {}, demos.length ? "No matching demos" : "Your next great demo starts here"), h("p", {}, demos.length ? "Try another name or choose a different filter." : "Bring your product images, documents and website. Your agent will help turn them into a guided experience."), !demos.length ? h("button", { class: "btn primary", onclick: () => newDemoModal(navigate) }, icon("plus", { size: 18 }), "Create your first demo") : null));
  }
  update();
}

export function newDemoModal(navigate) {
  const name = h("input", { id: "new-demo-name", placeholder: "e.g. Tata Nexon", autocomplete: "off" });
  const url = h("input", { id: "new-demo-url", type: "url", placeholder: "https://your-product-page.com" });
  const priorFocus = document.activeElement;
  function close() { bg.remove(); priorFocus?.focus?.(); }
  const bg = h("div", { class: "modal-bg", onclick: e => { if (e.target === bg) close(); }, onkeydown: e => { if (e.key === "Escape") close(); if (e.key === "Tab") { const nodes = [...bg.querySelectorAll('button:not(:disabled),input')]; if (e.shiftKey && document.activeElement === nodes[0]) { e.preventDefault(); nodes.at(-1).focus(); } else if (!e.shiftKey && document.activeElement === nodes.at(-1)) { e.preventDefault(); nodes[0].focus(); } } } },
    h("div", { class: "modal create-modal", role: "dialog", "aria-modal": "true", "aria-labelledby": "create-demo-title" },
      h("div", { class: "modal-title-row" }, h("span", { class: "section-icon" }, icon("layers", { size: 25 })), h("button", { class: "btn ghost icon-only", "aria-label": "Close new demo", onclick: close }, icon("close"))),
      h("h2", { id: "create-demo-title" }, "Give your product a voice"), h("p", { class: "muted" }, "Start with a name. Add your product knowledge in the next step."),
      h("div", { class: "field" }, h("label", { for: "new-demo-name" }, "Product name"), name),
      h("div", { class: "field" }, h("label", { for: "new-demo-url" }, "Product website ", h("span", { class: "optional" }, "Optional")), url, h("p", { class: "field-help" }, "This page will be added to your source material.")),
      h("div", { class: "actions" }, h("button", { class: "btn ghost", onclick: close }, "Cancel"), h("button", { class: "btn primary", onclick: async (e) => { if (!name.value.trim()) { name.focus(); return; } if (url.value && !url.reportValidity()) return; const button = e.currentTarget; button.disabled = true; try { const d = await api.post("/api/demos", { name: name.value.trim(), url: url.value.trim() }); close(); navigate(`#/studio/${d.id}/sources`); } catch (err) { toast(err.message, true); button.disabled = false; } } }, "Create demo", icon("arrow-right", { size: 17 }))),
    ));
  document.body.appendChild(bg); name.focus();
  name.addEventListener("keydown", e => { if (e.key === "Enter") bg.querySelector(".btn.primary").click(); });
}
