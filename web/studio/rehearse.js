import { api, h, toast, fmtTime } from "/web/api.js";
import { mountPlayer } from "/web/player/player.js";
import { icon } from "/web/icons.js";

export function renderRehearse(ctx) {
  const { demoId, area } = ctx;
  let state = ctx.state; let demo = state.demo; let player = null;
  const overlay = h("div", { class: "overlay hidden" });
  const logEl = h("div", { class: "progress-log" });
  const host = h("div", { class: "player-host" });
  const fb = h("textarea", { "aria-label": "Demo feedback", placeholder: "What should change? For example, “shorten the opening” or “explain the warranty before the price”." });
  const fbBtn = h("button", { class: "btn primary", onclick: sendFeedback }, icon("send", { size: 15 }), "Incorporate feedback");
  const fbReply = h("div", { class: "small muted", style: "margin-top:8px;line-height:1.5" });
  const covBox = h("div", { class: "box" });
  const scoreBox = h("div", { class: "box" });
  const sessBox = h("div", { class: "box" });
  const leadBox = h("div", { class: "box" });

  area.replaceChildren(overlay, h("header", { class: "studio-page-head rehearse-page-head" }, h("div", { class: "eyebrow" }, "Demo workspace / Rehearse"), h("h1", {}, "Experience your demo"), h("p", { class: "lede" }, "Explore it as a customer, ask questions and refine the details before sharing.")), h("div", { class: "rehearse" },
    h("div", { class: "rpanel" },
      h("div", { class: "box feedback-box" }, h("h3", {}, icon("message", { size: 18 }), "Feedback"), h("p", { class: "small muted", style: "margin:0 0 12px" }, "Tell your agent what needs work. It applies the feedback to the relevant part of your demo."), fb, h("div", { class: "feedback-actions", style: "margin-top:12px;display:flex;gap:8px" }, fbBtn, h("button", { class: "btn ghost", onclick: () => player && player.restart() }, "Restart demo")), fbReply),
      scoreBox, covBox, leadBox, sessBox,
      h("div", { class: "box upcoming-box" }, h("h3", {}, icon("globe", { size: 18 }), "Publish", h("span", { class: "pill" }, "Coming soon")), h("p", { class: "small muted", style: "margin:0" }, "Hosted publishing and an embed snippet are planned. Use this workspace to rehearse your demo."))),
    host));

  function showOverlay(title, error) {
    overlay.classList.remove("hidden");
    overlay.replaceChildren(h("div", { class: "box" }, error ? null : h("div", { class: "ring" }), h("h2", {}, error ? "Something went wrong" : title), h("p", { class: "sub" }, error ? "" : "The playground reloads when it's done."), logEl,
      error ? h("div", { class: "err" }, error) : null, error ? h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => overlay.classList.add("hidden") }, "Close")) : null));
  }
  function logLine(ev) { logEl.append(h("div", {}, ev.stage ? h("span", { class: "stage" }, ev.stage + " · ") : null, ev.message)); logEl.scrollTop = logEl.scrollHeight; }

  function renderCoverage() {
    const r = state.rehearsal;
    covBox.replaceChildren(h("h3", {}, icon("shield", { size: 18 }), "Question coverage"),
      !r || r.skipped ? h("p", { class: "small muted", style: "margin:0" }, "Not rehearsed yet.") :
        h("div", {}, h("div", { class: "coverage" }, Math.round((r.coverage || 0) * 100), "%", h("small", {}, ` of ${r.questions.length} likely questions answered from the sources`)),
          r.gaps.length ? h("div", {}, h("p", { class: "eyebrow", style: "margin:10px 0 0" }, "couldn't answer"), h("ul", { class: "gaplist" }, ...r.gaps.map((g) => h("li", {}, g)))) : h("p", { class: "small muted" }, "No gaps — every rehearsal question had a cited answer."),
          h("p", { class: "small muted", style: "margin:8px 0 0" }, "Gaps are also listed on the Facts card in Align — upload material there to close them.")));
  }
  function renderScore() {
    const sc = state.rehearsal?.scorecard;
    scoreBox.replaceChildren(h("h3", {}, icon("chart", { size: 18 }), "Demo scorecard"), !sc ? h("p", { class: "small muted", style: "margin:0" }, "Scored at build time against the playbook (10 criteria × 0–2).") :
      h("div", {}, h("div", { class: "coverage" }, sc.total, h("small", {}, " / 20 — ≥16 is a good first demo")),
        h("div", { style: "display:grid;grid-template-columns:1fr auto;gap:2px 10px;font-size:12.5px;margin-top:8px" }, ...sc.scores.map((s) => [h("span", { title: s.note }, s.criterion), h("b", { class: "mono", style: `color:${s.score === 2 ? "var(--accent)" : s.score === 1 ? "var(--warn)" : "var(--bad)"}` }, String(s.score))]).flat()),
        sc.weakest?.length ? h("div", {}, h("p", { class: "eyebrow", style: "margin:10px 0 4px" }, "fix first"), h("ul", { class: "gaplist" }, ...sc.weakest.map((w) => h("li", {}, w)))) : null));
  }
  function renderLeads() {
    const ls = state.leads || [];
    leadBox.replaceChildren(h("h3", {}, icon("headphones", { size: 18 }), "Callback requests"), ls.length ? h("div", {}, ...ls.slice(0, 8).map((l) => h("div", { class: "sess" }, h("span", {}, h("b", { class: "mono" }, l.phone), h("span", { class: "muted" }, ` · ${l.profile?.name || "anonymous"}`)), h("span", { class: "muted small" }, `“${(l.question || "").slice(0, 60)}”`)))) : h("p", { class: "small muted", style: "margin:0" }, "Customer callback requests will appear here, with the question they need help with."));
  }
  function renderSessions() {
    const ss = state.sessions || [];
    sessBox.replaceChildren(h("h3", {}, icon("users", { size: 18 }), "Recent sessions"), ss.length ? h("div", {}, ...ss.slice(0, 8).map((s) => h("div", { class: "sess" }, h("span", {}, s.profile?.name || "anonymous", h("span", { class: "muted" }, ` · ${s.questions} q · ${s.cta || "no cta"}`)), h("span", { class: "mono muted" }, s.intent != null ? `intent ${s.intent}` : "", s.saved_at ? " · " + fmtTime(s.saved_at) : "")))) : h("p", { class: "small muted", style: "margin:0" }, "Every rehearsal is saved with a transcript and follow-up summary."));
  }

  async function mount() {
    let bundle;
    try { bundle = await api.get(`/api/demos/${demoId}/bundle`); }
    catch (e) { host.replaceChildren(h("div", { class: "studio-empty rehearse-empty" }, icon(demo.status === "building" ? "clock" : "play", { size: 30 }), h("h2", {}, demo.status === "building" ? "Your demo is being built" : "Your demo will appear here"), h("p", {}, demo.status === "building" ? "The preview becomes available when your build is complete." : "Approve the six cards in Align, then build your demo to start rehearsing."))); return; }
    if (player) player.destroy();
    player = mountPlayer(host, bundle, {
      qa: (body) => api.post(`/api/demos/${demoId}/run/qa`, body),
      tts: (text) => api.post(`/api/demos/${demoId}/run/tts`, { text }).then((r) => r.url),
      tts_lang: (text, language) => api.post(`/api/demos/${demoId}/run/tts`, { text, language }).then((r) => r.url),
      pitch: (body) => api.post(`/api/demos/${demoId}/run/pitch`, body),
      lead: (body) => api.post(`/api/demos/${demoId}/run/lead`, body),
      stt: (blob, lang) => { const fd = new FormData(); fd.append("file", blob, "speech.wav"); fd.append("language", lang || "en-IN"); return api.form(`/api/demos/${demoId}/run/stt`, fd).then((r) => r.transcript || ""); },
      saveSession: (s) => api.post(`/api/demos/${demoId}/run/session`, s).then(() => refreshState()),
      downloadUrl: `/api/demos/${demoId}/export.mp4`,
      onFullscreenRoute: () => { document.documentElement.requestFullscreen?.().catch(() => {}); location.hash = `#/play/${demoId}`; },
    });
  }
  async function refreshState() { try { state = await api.get(`/api/demos/${demoId}`); demo = state.demo; renderCoverage(); renderScore(); renderLeads(); renderSessions(); } catch (e) {} }

  async function sendFeedback() {
    const msg = fb.value.trim(); if (!msg) return;
    fbBtn.disabled = true; fbReply.textContent = "thinking…";
    try { const r = await api.post(`/api/demos/${demoId}/feedback`, { message: msg, context: player ? player.context() : {} }); fbReply.textContent = r.reply + (r.notes?.length ? " · " + r.notes.join(" · ") : ""); fb.value = ""; }
    catch (e) { fbReply.textContent = ""; toast(e.message, true); }
    fbBtn.disabled = false;
  }

  ctx.subscribe((type, ev) => {
    if (type === "progress") logLine(ev);
    else if (type === "status") { demo.status = ev.status; ctx.setRailStatus(ev.status); if (ev.status === "building" || ev.status === "reading") { logEl.replaceChildren(); showOverlay(ev.status === "reading" ? "Re-reading your sources…" : "Rebuilding your demo…"); if (player) player.pause(); } }
    else if (type === "phase_done") { if (ev.phase === "build") { overlay.classList.add("hidden"); refreshState().then(mount); } else if (ev.phase === "revise") { overlay.classList.add("hidden"); toast("Changes applied in Align — approve the affected cards and rebuild"); } }
    else if (type === "phase_error") showOverlay("Rebuilding…", ev.error);
  });

  renderCoverage(); renderScore(); renderLeads(); renderSessions(); mount();
  if (demo.status === "building" || state.running) showOverlay("Building your demo…");
}
