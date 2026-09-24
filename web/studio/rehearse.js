import { api, h } from "/web/api.js";
import { mountPlayer } from "/web/player/player.js";
import { icon } from "/web/icons.js";

export function renderRehearse(ctx) {
  const { demoId, area } = ctx;
  let state = ctx.state, demo = state.demo, player = null;
  let disposed = false, mountEpoch = 0, sending = false, working = !!state.running;
  let pending = [], rehearsalSignature = "";
  const seen = new Set();
  const active = () => !disposed && (!ctx.isCurrent || ctx.isCurrent());
  const host = h("div", { class: "player-host" });
  const thread = h("div", { class: "thread", role: "log", "aria-label": "Demo feedback conversation", "aria-live": "polite" });
  const progress = h("div", { class: "feedback-progress hidden", role: "status", "aria-live": "polite" });
  const fb = h("textarea", { "aria-label": "Demo feedback", placeholder: "What should change? Add feedback or missing information…" });
  const files = h("input", { type: "file", multiple: true, accept: "video/*,image/*,.pdf,.docx,.txt,.md,.csv", "aria-label": "Feedback attachments" });
  const attachments = h("div", { class: "attach" });
  const attachBtn = h("button", { class: "btn ghost", "aria-label": "Attach files", title: "Attach files", onclick: () => files.click() }, icon("plus", { size: 19 }));
  const sendBtn = h("button", { class: "btn primary", onclick: sendFeedback }, icon("send", { size: 16 }), "Send");
  const rehearseBtn = h("button", { class: "btn sm ghost", "aria-label": "Run rehearsal", title: "Check reviewed questions and script coverage", onclick: runRehearsal }, "Run rehearsal");
  const conversation = h("section", { class: "convo rehearse-feedback", "aria-label": "Feedback" },
    h("div", { class: "align-agent-header" }, h("span", { class: "studio-agent-mark" }, icon("agent", { size: 24 })), h("div", {}, h("h2", {}, "Feedback"), h("p", {}, "Refine your demo together")), rehearseBtn),
    thread, progress,
    h("div", { class: "dock" }, attachments, h("div", { class: "box" }, attachBtn, fb, sendBtn, files),
      h("div", { class: "hint" }, "Add a correction or attach missing material. Review affected cards in ", h("a", { href: `#/studio/${demoId}/align` }, "Align"), " before rebuilding.")));
  area.replaceChildren(h("div", { class: "rehearse rehearse-workspace" }, conversation, host));
  files.addEventListener("change", () => { pending.push(...files.files); files.value = ""; renderAttachments(); });
  fb.addEventListener("keydown", event => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); sendFeedback(); } });

  function syncControls() {
    sendBtn.disabled = sending || working; rehearseBtn.disabled = sending || working;
    fb.disabled = sending; attachBtn.disabled = sending; files.disabled = sending;
    for (const button of attachments.querySelectorAll("button")) button.disabled = sending;
  }
  function renderAttachments() {
    attachments.replaceChildren(...pending.map((file, index) => h("span", {}, icon("file", { size: 13 }), file.name,
      h("button", { class: "btn ghost", "aria-label": `Remove ${file.name}`, onclick: () => { pending.splice(index, 1); renderAttachments(); } }, icon("close", { size: 13 })))));
    syncControls();
  }
  function addMsg(message) {
    if (!active() || message.system) return;
    const key = message.t ? `${message.role}:${message.t}` : null;
    if (key && seen.has(key)) return;
    if (key) seen.add(key);
    const text = String(message.text || "").replace(/\n\n\(Player context: [\s\S]*\)$/, "");
    thread.append(h("div", { class: "msg " + (message.role === "user" ? "user" : "agent") }, text,
      message.attachments?.length ? h("div", { class: "att" }, "attached: " + message.attachments.map(file => file.name).join(", ")) : null,
      message.notes?.length ? h("div", { class: "notes" }, message.notes.join(" · ")) : null));
    thread.scrollTop = thread.scrollHeight;
  }
  function showProgress(text, error = false) {
    if (!active()) return;
    progress.textContent = text; progress.classList.toggle("hidden", !text); progress.classList.toggle("error", error);
    progress.setAttribute("role", error ? "alert" : "status");
  }
  function rehearsalResult() {
    const result = state.rehearsal;
    if (!result || result.skipped) return;
    const signature = JSON.stringify(result);
    if (signature === rehearsalSignature) return;
    rehearsalSignature = signature;
    const parts = [`Rehearsal complete: ${Math.round((result.coverage || 0) * 100)}% of ${(result.questions || []).length} reviewed questions answered from the sources.`];
    if (result.scorecard) parts.push(`Script score: ${result.scorecard.total}/20.`);
    if (result.gaps?.length) parts.push("Missing answers: " + result.gaps.join(" · ") + ". Add a source here, then review it in Align.");
    if (result.scorecard?.weakest?.length) parts.push("Review next: " + result.scorecard.weakest.join(" · "));
    addMsg({ role: "agent", text: parts.join("\n\n") });
  }
  async function mount() {
    if (!active()) return;
    const epoch = ++mountEpoch;
    let bundle;
    try { bundle = await api.get(`/api/demos/${demoId}/bundle`); }
    catch (e) { if (!active() || epoch !== mountEpoch) return; host.replaceChildren(h("div", { class: "studio-empty rehearse-empty" }, icon(demo.status === "building" ? "clock" : "play", { size: 30 }), h("h2", {}, demo.status === "building" ? "Your demo is being built" : "Your demo will appear here"), h("p", {}, demo.status === "building" ? "The preview becomes available when your build is complete." : "Approve the six cards in Align, then build your demo to start rehearsing."))); return; }
    if (!active() || epoch !== mountEpoch) return;
    if (player) player.destroy();
    player = mountPlayer(host, bundle, {
      liveUrl: bundle.runtime?.version >= 1 ? `/api/demos/${demoId}/run/live` : null,
      qa: (body, options) => api.post(`/api/demos/${demoId}/run/qa`, body, options),
      tts: (text) => api.post(`/api/demos/${demoId}/run/tts`, { text }).then((r) => r.url),
      tts_lang: (text, language) => api.post(`/api/demos/${demoId}/run/tts`, { text, language }).then((r) => r.url),
      pitch: (body) => api.post(`/api/demos/${demoId}/run/pitch`, body),
      lead: (body) => api.post(`/api/demos/${demoId}/run/lead`, body),
      stt: (blob, lang) => { const fd = new FormData(); fd.append("file", blob, "speech.wav"); fd.append("language", lang || "en-IN"); return api.form(`/api/demos/${demoId}/run/stt`, fd).then((r) => r.transcript || ""); },
      saveSession: (s) => api.post(`/api/demos/${demoId}/run/session`, s).then(() => refreshState().catch(() => {})),
      downloadUrl: `/api/demos/${demoId}/export.mp4`,
      onFullscreenRoute: () => { document.documentElement.requestFullscreen?.().catch(() => {}); location.hash = `#/play/${demoId}`; },
    });
  }
  async function refreshState() {
    if (!active()) return;
    const next = await api.get(`/api/demos/${demoId}`);
    if (!active()) return;
    state = next; demo = state.demo;
    for (const message of state.conversation || []) addMsg(message);
    rehearsalResult();
  }

  async function runRehearsal() {
    if (sending || working || !active()) return;
    working = true; syncControls(); showProgress("Starting rehearsal…");
    try { await api.post(`/api/demos/${demoId}/rehearsal`, {}); }
    catch (error) { if (!active()) return; working = false; syncControls(); showProgress(error.message, true); }
  }

  async function sendFeedback() {
    const text = fb.value.trim();
    if ((!text && !pending.length) || sending || working || !active()) return;
    sending = true; syncControls(); showProgress(pending.length ? "Uploading material and reviewing your feedback…" : "Reviewing your feedback…");
    const startingMessages = thread.childElementCount;
    const context = player?.context() || {};
    const body = new FormData();
    body.append("message", text + (Object.keys(context).length ? `\n\n(Player context: ${JSON.stringify(context).slice(0, 1500)})` : ""));
    body.append("context", "rehearse");
    pending.forEach(file => body.append("files", file));
    try {
      const response = await api.form(`/api/demos/${demoId}/align`, body);
      if (!active()) return;
      fb.value = ""; pending = []; renderAttachments();
      // Reload the persisted conversation to avoid duplicating SSE messages.
      try { await refreshState(); }
      catch (_) {
        const alreadyReceived = [...thread.children].slice(startingMessages).some(node => node.classList.contains("agent") && node.firstChild?.textContent === response.reply);
        if (active() && !alreadyReceived) addMsg({ role: "agent", text: response.reply || "Feedback received. Open Align to review the affected cards.", notes: response.notes });
      }
      if (active() && !working) showProgress("Feedback received. Review affected cards in Align before rebuilding.");
    } catch (error) { if (active()) showProgress(error.message + " Your feedback and attachments are still here to retry.", true); }
    finally { if (active()) { sending = false; syncControls(); } }
  }

  ctx.subscribe((type, event) => {
    if (!active()) return;
    if (type === "message") addMsg(event.message);
    else if (type === "progress") showProgress((event.stage ? event.stage + " · " : "") + event.message);
    else if (type === "stage" && event.stage === "rehearsal") { working = event.status === "running"; syncControls(); }
    else if (type === "status") {
      demo.status = event.status; ctx.setRailStatus(event.status);
      if (["reading", "building"].includes(event.status)) { working = true; syncControls(); player?.pause(); showProgress(event.status === "reading" ? "Reading your new material…" : "Building the reviewed demo…"); }
    } else if (type === "phase_done") {
      working = false; syncControls();
      if (event.phase === "rehearsal") showProgress("Rehearsal complete.");
      else if (event.phase !== "build") showProgress("Changes are ready in Align. Review the affected cards before rebuilding.");
      else showProgress("Your reviewed demo is ready.");
      refreshState().then(() => { if (active() && event.phase === "build") mount(); }).catch(error => showProgress(error.message, true));
    } else if (type === "phase_error") { working = false; syncControls(); showProgress(event.error || "The request could not finish. Please try again.", true); }
  });

  for (const message of state.conversation || []) addMsg(message);
  if (!thread.childElementCount) addMsg({ role: "agent", text: "Tell me what needs work in this demo, or attach missing material. Changes return to Align for your review before rebuilding." });
  rehearsalResult(); syncControls(); mount();
  if (working) showProgress(demo.running === "rehearsal" ? "Rehearsal is running…" : "Preparing your demo…");
  return () => { if (disposed) return; disposed = true; mountEpoch++; player?.destroy(); player = null; };
}
