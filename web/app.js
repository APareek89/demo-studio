// Shell + hash router.  #/home · #/demos · #/studio/<id>/sources|align|rehearse · #/play/<id>
import { api, h, toast } from "/web/api.js";
import { renderDemos } from "/web/demos.js";
import { renderHome } from "/web/home.js";
import { icon } from "/web/icons.js";
import { renderSources } from "/web/studio/sources.js";
import { renderAlign } from "/web/studio/align.js";
import { renderRehearse } from "/web/studio/rehearse.js";
import { renderSessions, renderShare } from "/web/studio/sessions.js";
import { renderPlayground } from "/web/playground.js";
import { renderObservability } from "/web/observability.js";
import { mountPlayer } from "/web/player/player.js";

const main = document.getElementById("main");
let current = { unsub: null, dispose: null, demoId: null };
let viewEpoch = 0;
let viewHash = location.hash;
const isCurrentView = epoch => epoch === viewEpoch && location.hash === viewHash;

// A hash route owns its subscriptions, player and pending screen loads.
function beginView() {
  const epoch = ++viewEpoch;
  viewHash = location.hash;
  const { unsub, dispose } = current;
  current.unsub = null; current.dispose = null;
  try { unsub?.(); } finally { dispose?.(); }
  return epoch;
}

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

async function renderStudio(demoId, stage, epoch = beginView()) {
  let state;
  if (!demoId) {
    stage = "sources";
    state = { demo: { id: null, name: "", product: { name: "", url: "" }, sources: [], status: "sources", version: 0,
      settings: { pitch_minutes: 3, audience: "everyday", language: "en-IN", languages: ["en-IN"] }, stages: {}, approvals: {} },
      cards: null, conversation: [], sessions: [], leads: [], running: false, bundle_ready: false };
  } else {
    try { state = await api.get(`/api/demos/${demoId}`); } catch (e) { if (!isCurrentView(epoch)) return; toast("Demo not found", true); return navigate("#/demos"); }
  }
  if (!isCurrentView(epoch)) return;
  const demo = state.demo; demo.__bundle = state.bundle_ready;
  if (!stage) stage = demo.status === "sources" ? "sources" : demo.status === "ready" ? "rehearse" : "align";
  const rail = h("aside", { class: "rail" },
    h("a", { class: "rail-back", href: "#/demos" }, icon("arrow-left", { size: 13 }), "All demos"),
    h("div", { class: "demo-name" }, demo.name || "New demo", h("span", { class: "id" }, demo.id ? `${demo.id} · v${demo.version || 0}` : "Add your product sources")),
    h("div", { class: "rail-label" }, "BUILD YOUR EXPERIENCE"),
    ...STEPS.map((s) => { const ss = stepState(demo, s.key); const locked = !demoId && s.key !== "sources" || ss.locked; return h("a", { class: `step${stage === s.key ? " active" : ""}${ss.done ? " done" : ""}${locked ? " locked" : ""}`, "data-step": s.key, "aria-disabled": locked ? "true" : null, href: demoId ? `#/studio/${demo.id}/${s.key}` : "#/studio" }, h("span", { class: "n" }, s.n), h("span", {}, s.label, h("span", { class: "sub" }, s.sub))); }),
    h("div", { class: "spacer" }),
    h("div", { class: "status", id: "railStatus" }, demo.status === "sources" ? "waiting for sources" : demo.status),
  );
  const area = h("section", { class: "stage-area" + (stage === "rehearse" ? " rehearse-area" : ""), id: "stageArea" });
  main.replaceChildren(h("div", { class: "studio" }, rail, area));
  if (current.unsub) { current.unsub(); current.unsub = null; }
  current.demoId = demoId;
  let creating = null;
  const ctx = {
    demoId, state, area, navigate, refresh: () => isCurrentView(epoch) ? renderStudio(demoId, stage) : undefined,
    ensureDemo: () => {
      if (demoId) return Promise.resolve(demoId);
      if (!isCurrentView(epoch)) return Promise.reject(new Error("This workspace has been closed."));
      if (!creating) creating = (async () => {
        const created = await api.post("/api/demos", {});
        if (!isCurrentView(epoch)) throw new Error("This workspace has been closed.");
        demoId = created.id; current.demoId = demoId; ctx.demoId = demoId;
        // Adopt the saved URL without remounting an upload or setting change.
        history.replaceState(null, "", `#/studio/${demoId}/sources`); viewHash = location.hash;
        ctx.state = { ...state, demo: created }; state = ctx.state;
        for (const link of rail.querySelectorAll("[data-step]")) link.href = `#/studio/${demoId}/${link.dataset.step}`;
        rail.querySelector(".demo-name .id").textContent = `${demoId} · v0`;
        return demoId;
      })().catch(error => { creating = null; throw error; });
      return creating;
    },
    isCurrent: () => isCurrentView(epoch),
    setRailStatus: (t) => { const el = document.getElementById("railStatus"); if (el) el.textContent = t; },
    subscribe: (fn) => { current.unsub = api.subscribe(demoId, fn); return current.unsub; },
  };
  if (stage === "sources") renderSources(ctx);
  else if (stage === "align") renderAlign(ctx);
  else if (stage === "rehearse") current.dispose = renderRehearse(ctx);
  else if (stage === "sessions") renderSessions(ctx);
}

async function route() {
  const epoch = beginView();
  const parts = (location.hash || "#/home").slice(2).split("/");
  if (parts[0] === "home") { setTab("home"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderHome({ main, navigate }); }
  if (parts[0] === "studio") { setTab("studio"); return renderStudio(parts[1], parts[2], epoch); }
  if (parts[0] === "share" && parts[1] && parts[2]) { setTab(""); if (current.unsub) { current.unsub(); current.unsub = null; } return renderShare({ main, demoId: parts[1], sid: parts[2], key: parts[3] || "" }); }
  if (parts[0] === "play" && parts[1]) {
    setTab("");
    if (current.unsub) { current.unsub(); current.unsub = null; }
    return renderPlay(parts[1], epoch);
  }
  if (parts[0] === "observability") { setTab("observability"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderObservability({ main, navigate, demoId: parts[1] }); }
  if (parts[0] === "playground") { setTab("playground"); if (current.unsub) { current.unsub(); current.unsub = null; } return renderPlayground({ main, navigate, demoId: parts[1] }); }
  setTab("demos");
  if (current.unsub) { current.unsub(); current.unsub = null; }
  return renderDemos({ main, navigate });
}

let playInstance = null;
async function renderPlay(demoId, epoch = beginView()) {
  const main = document.getElementById("main");
  if (playInstance) { try { playInstance.destroy(); } catch (e) {} playInstance = null; }
  let bundle;
  try { bundle = await api.get(`/api/demos/${demoId}/bundle`); }
  catch (e) { if (!isCurrentView(epoch)) return; toast("This demo isn't built yet — open it in the studio and build it first.", true); navigate("#/demos"); return; }
  if (!isCurrentView(epoch)) return;
  const host = h("div", { class: "play-page" });
  main.replaceChildren(host);
  playInstance = mountPlayer(host, bundle, {
    liveUrl: bundle.runtime?.version >= 1 ? `/api/demos/${demoId}/run/live` : null,
    qa: (body, options) => api.post(`/api/demos/${demoId}/run/qa`, body, options),
    tts: (text) => api.post(`/api/demos/${demoId}/run/tts`, { text }).then((r) => r.url),
    tts_lang: (text, language) => api.post(`/api/demos/${demoId}/run/tts`, { text, language }).then((r) => r.url),
    pitch: (body) => api.post(`/api/demos/${demoId}/run/pitch`, body),
    lead: (body) => api.post(`/api/demos/${demoId}/run/lead`, body),
    stt: (blob, lang) => { const fd = new FormData(); fd.append("file", blob, "speech.wav"); fd.append("language", lang || "en-IN"); return api.form(`/api/demos/${demoId}/run/stt`, fd).then((r) => r.transcript || ""); },
    saveSession: (s) => api.post(`/api/demos/${demoId}/run/session`, s),
    beacon: (s) => navigator.sendBeacon(`/api/demos/${demoId}/run/session`, new Blob([JSON.stringify(s)], { type: "application/json" })),
    downloadUrl: `/api/demos/${demoId}/export.mp4`,
    onClose: () => { try { playInstance.destroy(); } catch (e) {} playInstance = null; navigate("#/demos"); },
  });
  const ownedPlayer = playInstance;
  current.dispose = () => { ownedPlayer.destroy(); if (playInstance === ownedPlayer) playInstance = null; };
}

document.querySelector(".skip-link")?.addEventListener("click", e => { e.preventDefault(); main.focus(); });
document.querySelector('#tabs a[href="#/studio"]')?.addEventListener("click", event => {
  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button) return;
  if (location.hash === "#/studio") { event.preventDefault(); route(); }
});
window.addEventListener("hashchange", route);
health(); route();
