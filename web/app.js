// Shell + hash router.  #/demos · #/studio/<id>/sources|align|rehearse
import { api, h, toast } from "/web/api.js";
import { renderDemos } from "/web/demos.js";
import { renderSources } from "/web/studio/sources.js";
import { renderAlign } from "/web/studio/align.js";
import { renderRehearse } from "/web/studio/rehearse.js";
import { renderPlayground } from "/web/playground.js";
import { renderObservability } from "/web/observability.js";

const main = document.getElementById("main");
let current = { unsub: null, demoId: null };

async function health() {
  try {
    const hh = await api.get("/api/health");
    for (const el of document.querySelectorAll("#health .k")) { const k = el.dataset.k; el.classList.toggle("ok", !!hh[k]); el.classList.toggle("bad", !hh[k]); el.title = hh[k] ? "key found" : "key missing in .env"; }
  } catch (e) {}
}

function setTab(name) { for (const a of document.querySelectorAll("#tabs a")) a.classList.toggle("active", a.dataset.tab === name); }

export function navigate(hash) { location.hash = hash; }

const STEPS = [
  { key: "sources", n: "1", label: "Sources", sub: "upload, then configure" },
  { key: "align", n: "2", label: "Align", sub: "approve what the agent found" },
  { key: "rehearse", n: "3", label: "Rehearse", sub: "run it, give feedback" },
];

function stepState(demo, key) {
  const st = demo.status;
  if (key === "sources") return { done: st !== "sources", locked: false };
  if (key === "align") return { done: st === "ready", locked: st === "sources" };
  if (key === "rehearse") return { done: false, locked: !["ready", "building"].includes(st) && !demo.__bundle };
  return {};
}

async function renderStudio(demoId, stage) {
  if (!demoId) {
    const demos = await api.get("/api/demos");
    if (demos.length) return navigate(`#/studio/${demos[0].id}/${demos[0].status === "sources" ? "sources" : demos[0].status === "ready" ? "rehearse" : "align"}`);
    return navigate("#/demos");
  }
  let state;
  try { state = await api.get(`/api/demos/${demoId}`); } catch (e) { toast("Demo not found", true); return navigate("#/demos"); }
  const demo = state.demo; demo.__bundle = state.bundle_ready;
  if (!stage) stage = demo.status === "sources" ? "sources" : demo.status === "ready" ? "rehearse" : "align";
  const rail = h("aside", { class: "rail" },
    h("div", { class: "demo-name" }, demo.name, h("span", { class: "id" }, demo.id, " · v", String(demo.version || 0))),
    ...STEPS.map((s) => { const ss = stepState(demo, s.key); return h("a", { class: `step${stage === s.key ? " active" : ""}${ss.done ? " done" : ""}${ss.locked ? " locked" : ""}`, href: `#/studio/${demo.id}/${s.key}` }, h("span", { class: "n" }, s.n), h("span", {}, s.label, h("span", { class: "sub" }, s.sub))); }),
    h("div", { class: "spacer" }),
    h("div", { class: "status", id: "railStatus" }, demo.status === "sources" ? "waiting for sources" : demo.status),
  );
  const area = h("section", { class: "stage-area", id: "stageArea" });
  main.replaceChildren(h("div", { class: "studio" }, rail, area));
  if (current.unsub) { current.unsub(); current.unsub = null; }
  current.demoId = demoId;
  const ctx = {
    demoId, state, area, navigate, refresh: () => renderStudio(demoId, stage),
    setRailStatus: (t) => { const el = document.getElementById("railStatus"); if (el) el.textContent = t; },
    subscribe: (fn) => { current.unsub = api.subscribe(demoId, fn); return current.unsub; },
  };
  if (stage === "sources") renderSources(ctx);
  else if (stage === "align") renderAlign(ctx);
  else if (stage === "rehearse") renderRehearse(ctx);
}

async function route() {
  const parts = (location.hash || "#/demos").slice(2).split("/");
  if (parts[0] === "studio") { setTab("studio"); return renderStudio(parts[1], parts[2]); }
  if (parts[0] === "observability") { setTab("observability"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderObservability({ main, navigate, demoId: parts[1] }); }
  if (parts[0] === "playground") { setTab("playground"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderPlayground({ main, navigate, demoId: parts[1] }); }
  setTab("demos");
  if (current.unsub) { current.unsub(); current.unsub = null; }
  return renderDemos({ main, navigate });
}

window.addEventListener("hashchange", route);
health(); route();
