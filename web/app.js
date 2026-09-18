// Shell + hash router.  #/home · #/demos · #/studio/<id>/sources|align|rehearse · #/play/<id>
import { api, h, toast } from "/web/api.js";
import { renderDemos } from "/web/demos.js";
import { renderHome } from "/web/home.js";
import { icon } from "/web/icons.js";
import { renderSources } from "/web/studio/sources.js";
import { renderAlign } from "/web/studio/align.js?v=3e0";
import { renderRehearse } from "/web/studio/rehearse.js";
import { renderSessions, renderShare } from "/web/studio/sessions.js";
import { renderPlayground } from "/web/playground.js";
import { renderObservability } from "/web/observability.js";
import { mountPlayer } from "/web/player/player.js";

const main = document.getElementById("main");
let current = { unsub: null, demoId: null };

async function health() {
  try {
    const hh = await api.get("/api/health");
    for (const el of document.querySelectorAll("#health .k")) { const k = el.dataset.k; el.classList.toggle("ok", !!hh[k]); el.classList.toggle("bad", !hh[k]); el.title = hh[k] ? "key found" : "key missing in .env"; }
  } catch (e) {}
}

function setTab(name) { for (const a of document.querySelectorAll("#tabs a")) { const active = a.dataset.tab === name; a.classList.toggle("active", active); if (active) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); } }

export function navigate(hash) { location.hash = hash; }

const STEPS = [
  { key: "sources", n: "1", label: "Sources", sub: "upload, then configure" },
  { key: "align", n: "2", label: "Align", sub: "approve what the agent found" },
  { key: "rehearse", n: "3", label: "Rehearse", sub: "run it, give feedback" },
  { key: "sessions", n: "•", label: "Sessions", sub: "who watched, what they asked" },
];

function stepState(demo, key) {
  const st = demo.status;
  if (key === "sources") return { done: st !== "sources", locked: false };
  if (key === "align") return { done: st === "ready", locked: st === "sources" };
  if (key === "rehearse") return { done: false, locked: !["ready", "building"].includes(st) && !demo.__bundle };
  if (key === "sessions") return { done: false, locked: false };
  return {};
}

async function renderStudio(demoId, stage) {
  if (!demoId) {
    const demos = await api.get("/api/demos");
    if (demos.length) return navigate(`#/studio/${demos[0].id}/sources`);
    return navigate("#/demos");
  }
  let state;
  try { state = await api.get(`/api/demos/${demoId}`); } catch (e) { toast("Demo not found", true); return navigate("#/demos"); }
  const demo = state.demo; demo.__bundle = state.bundle_ready;
  if (!stage) stage = demo.status === "sources" ? "sources" : demo.status === "ready" ? "rehearse" : "align";
  const rail = h("aside", { class: "rail" },
    h("a", { class: "rail-back", href: "#/demos" }, icon("arrow-left", { size: 13 }), "All demos"),
    h("div", { class: "demo-name" }, demo.name, h("span", { class: "id" }, demo.id, " · v", String(demo.version || 0))),
    h("div", { class: "rail-label" }, "BUILD YOUR EXPERIENCE"),
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
  else if (stage === "sessions") renderSessions(ctx);
}

async function route() {
  const parts = (location.hash || "#/home").slice(2).split("/");
  if (parts[0] === "home") { setTab("home"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderHome({ main, navigate }); }
  if (parts[0] === "studio") { setTab("studio"); return renderStudio(parts[1], parts[2]); }
  if (parts[0] === "share" && parts[1] && parts[2]) { setTab(""); if (current.unsub) { current.unsub(); current.unsub = null; } return renderShare({ main, demoId: parts[1], sid: parts[2], key: parts[3] || "" }); }
  if (parts[0] === "play" && parts[1]) {
    setTab("");
    if (current.unsub) { current.unsub(); current.unsub = null; }
    return renderPlay(parts[1]);
  }
  if (parts[0] === "observability") { setTab("observability"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderObservability({ main, navigate, demoId: parts[1] }); }
  if (parts[0] === "playground") { setTab("playground"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderPlayground({ main, navigate, demoId: parts[1] }); }
  setTab("demos");
  if (current.unsub) { current.unsub(); current.unsub = null; }
  return renderDemos({ main, navigate });
}

let playInstance = null;
async function renderPlay(demoId) {
  const main = document.getElementById("main");
  if (playInstance) { try { playInstance.destroy(); } catch (e) {} playInstance = null; }
  let bundle;
  try { bundle = await api.get(`/api/demos/${demoId}/bundle`); }
  catch (e) { toast("This demo isn't built yet — open it in the studio and build it first.", true); navigate("#/demos"); return; }
  const host = h("div", { class: "play-page" });
  main.replaceChildren(host);
  playInstance = mountPlayer(host, bundle, {
    qa: (body) => api.post(`/api/demos/${demoId}/run/qa`, body),
    tts: (text) => api.post(`/api/demos/${demoId}/run/tts`, { text }).then((r) => r.url),
    tts_lang: (text, language) => api.post(`/api/demos/${demoId}/run/tts`, { text, language }).then((r) => r.url),
    pitch: (body) => api.post(`/api/demos/${demoId}/run/pitch`, body),
    lead: (body) => api.post(`/api/demos/${demoId}/run/lead`, body),
    stt: (blob, lang) => { const fd = new FormData(); fd.append("file", blob, "speech.wav"); fd.append("language", lang || "en-IN"); return api.form(`/api/demos/${demoId}/run/stt`, fd).then((r) => r.transcript || ""); },
    saveSession: (s) => api.post(`/api/demos/${demoId}/run/session`, s).catch(() => {}),
    beacon: (s) => navigator.sendBeacon(`/api/demos/${demoId}/run/session`, new Blob([JSON.stringify(s)], { type: "application/json" })),
    downloadUrl: `/api/demos/${demoId}/export.mp4`,
    onClose: () => { try { playInstance.destroy(); } catch (e) {} playInstance = null; navigate("#/demos"); },
  });
}

document.querySelector(".skip-link")?.addEventListener("click", e => { e.preventDefault(); main.focus(); });
window.addEventListener("hashchange", route);
health(); route();
