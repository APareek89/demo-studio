// The runtime player — voice-led, interruptible, grounded through the server.
// Order: intake question (over the hero slide) → opening film (skippable) → the standard opening slides (unchanged) →
// runtime pitch plan (decision frame · custom batches as slides · personalised order) → proof slides with check-ins →
// establish → closing (fit summary) → hero close + CTA → handoff.
// Sync is event-driven: audio leads, the screen follows. A line starting reveals its callouts; the last line's audio
// ending moves to the next slide. No timer decides what is on screen.
// A question is routed by the server on fact ids and topics (stay on this slide · jump to the slide that carries the
// facts, then return to the interrupted line · none): S.seg / S.line are never touched by a jump, so the return point is
// always the interrupted line — a return stack of depth 1. A slide seen during a jump is covered: reached later, it plays
// its title and first line only.
// Every customer turn is stamped four times — voice ended, STT done, QA done, first answer audio playing — and kept on
// the session record; Observability shows p50 / p95 per stage.
// The transcript holds only what the customer actually heard (a cut-off line is logged as the words that played and
// marked interrupted); only that transcript is sent as history to /run/qa.
// mountPlayer(host, bundle, {qa, tts, pitch, lead, stt, saveSession}) → { destroy, restart, pause, context }
import { mascot } from "/web/player/mascot.js";
import { renderSlide } from "/web/slide.js";
import { h } from "/web/api.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const PHONE = /(?:\+?91[\s-]?)?([6-9]\d{9})/;
const compact = (t, n) => String(t || "").split(/\s+/).slice(0, n).join(" ");
const newSessionId = () => "s_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const CONSENT = "By sharing your number you agree the dealership may call you about this product. Nothing else is shared.";

export function mountPlayer(host, bundle, api) {
  const mutedByDefault = ["1", "true", "on"].includes(new URLSearchParams(window.location.search).get("mute"));
  const S = { run: 0, plan: [], seg: 0, line: 0, atCheckin: false, waiter: null, waitChips: [], timer: null, intakeResolver: null, pendingIntakeAnswer: "", intakeOpen: false,
    profile: { name: "", why: "", followup: "", focus: [] }, pitch: null, questions: [], transcript: [], escalations: [], leads: [], resolved: new Set(), unresolved: new Set(), raised: new Set(),
    cta: null, started: Date.now(), micOn: false, micDenied: false, inputMode: "voice", rec: null, audio: null, utterance: null, muted: mutedByDefault, preloads: [], ttsToken: 0, ttsCache: new Map(), bt: { voice: null },
    leadPromptShown: false, leadQuestion: "", leadReason: "", speaking: null, visited: [], covered: new Set(), jumps: [], sessionId: newSessionId(), ended: false, endedAt: null, turns: [], lastListen: null, onFirstAudio: null,
    listenId: 0, cancelListen: null, finishListen: null, cancelVoice: null, playback: { phase: "opening", index: 0, line: 0 }, conversationOrigin: null, browseOnly: false, openQuestions: new Set() };
  const persona = bundle.voice?.persona || {}; const guide = persona.persona_name || "Guide";
  const useServerVoice = bundle.voice?.provider && bundle.voice.provider !== "browser";

  // ---------- slides ----------
  // The deck is the structure. A bundle built before the deck existed gets one slide per segment (its line's own
  // picture, no callouts) so older demos keep playing until they are rebuilt.
  function slidesOf(b) {
    if (b.slides?.length) return b.slides;
    const hero = b.media?.hero || null; const kindOf = (r) => ({ intro: "intro", outcome: "outcome", proof: "proof", features: "features", establish: "establish" })[r] || "proof";
    const mk = (id, kind, title, seg, lines) => ({ id, segment_id: seg?.id || null, kind, title, topics: seg?.topic ? [seg.topic] : [], image_url: (lines.map((l) => l.visual).find((v) => v?.kind === "image" && v.url) || {}).url || hero, image_parts: [], callouts: [], lines, checkin: seg?.checkin || { text: "" }, deeper: seg?.deeper || [], usp_ids: seg?.usp_ids || [], priority: !!seg?.priority, role: seg?.role || kind, motion: "zoom_in" });
    const segs = (b.segments || []).map((s, i) => mk(`sl${i + 1}`, kindOf(s.role), s.title, s, s.lines || []));
    return [mk("sl00", "hero_open", b.product?.name || b.name, null, []), ...segs, mk("sl-close", "closing", "Where that leaves you", null, b.closing || []), mk("sl-end", "hero_close", b.product?.name || b.name, null, [])];
  }
  let slides = slidesOf(bundle);
  const byKind = (...k) => slides.filter((s) => k.includes(s.kind));
  const opening = () => byKind("intro", "outcome"), library = () => byKind("proof", "features", "establish");
  const heroOpen = () => byKind("hero_open")[0] || slides[0], heroClose = () => byKind("hero_close")[0] || heroOpen(), closingSlide = () => byKind("closing")[0] || null;
  const topicOf = (sl) => sl.topics?.[0] || sl.segment_id || sl.id;

  // Keep preload objects alive for the full session: every recorded line, filler, FAQ answer and picture, plus the film.
  setTimeout(() => {
    try {
      const urls = [];
      for (const v of Object.values(bundle.fillers || {})) if (v.audio) urls.push(v.audio);
      for (const u of Object.values(bundle.intake?.audio || {})) if (u) urls.push(u);
      for (const sl of slides) { for (const line of [...(sl.lines || []), ...(sl.deeper || [])]) if (line.audio) urls.push(line.audio); if (sl.checkin?.audio) urls.push(sl.checkin.audio); }
      for (const item of bundle.faq || []) if (item.audio) urls.push(item.audio);
      for (const url of [...new Set(urls)]) { const a = new Audio(url); a.preload = "auto"; a.load(); S.preloads.push(a); }
      for (const url of [...new Set(slides.map((s) => s.image_url).filter(Boolean))]) { const image = new Image(); image.decoding = "async"; image.src = url; S.preloads.push(image); }
      if (bundle.intro_video?.url) { const v = document.createElement("video"); v.preload = "auto"; v.src = bundle.intro_video.url; v.load(); S.preloads.push(v); }
    } catch (e) {}
  }, 150);
  const F = (key, fallback) => { const f = bundle.fillers?.[key]; return f?.audio ? { text: f.text, audio: f.audio } : { text: fallback || f?.text || "", audio: null }; };
  const speakF = (key, fallback, run) => { const f = F(key, fallback); return speak(f.text, run, f.audio); };
  let LANG = (bundle.language === "hinglish" ? "hi-IN" : bundle.language) || "en-IN";
  Object.defineProperty(S, "lang", { set(v) { LANG = v === "hinglish" ? "hi-IN" : v; }, get() { return LANG; } });
  let serverSTT = !!(api.stt && bundle.stt?.provider === "sarvam");
  const canListen = () => (serverSTT && navigator.mediaDevices?.getUserMedia) || SR;

  // ---------- DOM ----------
  const el = {};
  const root = h("div", { class: "pl" },
    h("div", { class: "pl-top" },
      h("div", { class: "left" }, el.avatar = h("div", { class: "avatar" }), (el.mascotTop = mascot({ size: 34, image: bundle.mascot })).el, h("div", {}, h("div", { class: "pl-name" }, `${guide} · ${bundle.product?.name || bundle.name}`), el.status = h("div", { class: "pl-status" }, h("span", { class: "dot" }), el.statusTxt = h("span", {}, "Ready"))), el.progress = h("div", { class: "pl-progress" })),
      h("div", { class: "right" }, el.fsBtn = h("button", { class: "icon-btn", title: "Full screen", onclick: () => toggleFullscreen() }, "⛶"), el.muteBtn = h("button", { class: "icon-btn", title: "Mute audio", "aria-label": "Mute audio", "aria-pressed": "false", onclick: () => toggleMute() }, "🔊"), el.pauseBtn = h("button", { class: "icon-btn", title: "Pause / resume", onclick: () => togglePause() }, "⏸"), h("button", { class: "icon-btn", title: "Stop and see the summary", onclick: () => stopDemo() }, "⏹"), el.chatBtn = h("button", { class: "icon-btn", title: "Conversation", onclick: () => toggleDrawer() }, "💬", h("span", { class: "badge" })), h("button", { class: "icon-btn", title: "Restart", onclick: () => restart() }, "↺"), api.onClose ? h("button", { class: "icon-btn", title: "Close", onclick: () => { interruptAll(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); api.onClose(); } }, "✕") : null)),
    el.stage = h("div", { class: "pl-stage" },
      el.stack = h("div", { class: "slide-stack" }),
      el.film = h("video", { class: "pl-film", muted: true, playsinline: true, preload: "auto" }),
      el.ctas = h("div", { class: "pl-ctas" }),
      h("div", { class: "pl-dock" },
        h("div", { class: "pl-cap" }, (el.mascotStage = mascot({ size: 72, image: bundle.mascot })).el, h("div", { class: "who" }, guide), el.cap = h("div", { class: "txt" }), el.cite = h("div", { class: "cite" })),
        h("div", { class: "pl-controls" }, el.live = h("div", { class: "pl-live" }), el.chips = h("div", { class: "pl-chips" }), el.timer = h("div", { class: "pl-timer" }),
          h("form", { class: "pl-reply", onsubmit: (e) => { e.preventDefault(); const t = el.reply.value.trim(); if (t) { el.reply.value = ""; acceptTypedAnswer(t); } } }, el.reply = h("input", { oninput: preferTyping, placeholder: "Ask a question or type your answer…", "aria-label": "Your question or answer" }), h("button", { class: "btn primary sm", type: "submit" }, "Send")),
          h("div", { class: "pl-mic-row" }, el.hint = h("div", { class: "pl-hint" }, (serverSTT || SR) ? "Tap to talk — I'll stop and listen." : "Voice input needs Chrome or Safari — use 💬 to type."), el.mic = h("button", { class: "mic", onclick: () => micTap() }, "🎤")))),
      el.intake = h("div", { class: "pl-intake" }, h("div", { class: "inner" }, el.orb = h("div", { class: "orb-slot" }, (el.mascotIntake = mascot({ size: 132, image: bundle.mascot })).el), el.inState = h("div", { class: "state" }, guide), el.inQ = h("p", { class: "q" }), el.inHeard = h("div", { class: "heard" }),
        el.inFallback = h("form", { class: "fallback open", onsubmit: (e) => { e.preventDefault(); const t = el.inText.value.trim(); if (t) { el.inText.value = ""; acceptTypedAnswer(t); } } }, el.inText = h("input", { oninput: preferTyping, placeholder: "Type your answer…", "aria-label": "Your answer" }), h("button", { class: "btn primary sm", type: "submit" }, "Send")),
        h("div", { class: "actions" }, el.inMic = h("button", { class: "mic", onclick: () => intakeMic() }, "🎤"), h("button", { class: "btn ghost", onclick: () => skipIntake() }, "Skip, start the demo")))),
      el.handoff = h("div", { class: "pl-handoff" }, el.handoffBox = h("div", { class: "box" })),
      el.lead = h("div", { class: "pl-lead" }, h("div", { class: "lead-card" }, h("button", { class: "lead-close", title: "Not now", onclick: () => el.lead.classList.remove("open") }, "×"), h("div", { class: "eyebrow" }, "Optional · dealership follow-up"), h("h3", {}, "Would you like to try it in person?"), el.leadCopy = h("p", {}, "Share your details and the dealership can arrange a test drive."), el.leadForm = h("form", { onsubmit: (e) => { e.preventDefault(); saveLeadForm(); } }, el.leadName = h("input", { placeholder: "Your name", autocomplete: "name" }), el.leadPhone = h("input", { placeholder: "10-digit mobile number", inputmode: "tel", autocomplete: "tel" }), el.leadError = h("div", { class: "lead-error" }), h("p", { class: "consent" }, CONSENT), h("button", { class: "btn primary", type: "submit" }, "Arrange a test drive")), h("button", { class: "btn ghost sm", onclick: () => el.lead.classList.remove("open") }, "Not now")))),
    el.drawer = h("div", { class: "pl-drawer" }, h("div", { class: "head" }, h("span", {}, "Conversation"), h("button", { class: "icon-btn", onclick: () => toggleDrawer(false) }, "✕")), el.thread = h("div", { class: "body" }),
      h("form", { class: "composer", onsubmit: (e) => { e.preventDefault(); const t = el.q.value.trim(); if (t) { el.q.value = ""; acceptTypedAnswer(t); } } }, el.q = h("input", { oninput: preferTyping, placeholder: "Type a question…" }), h("button", { class: "btn primary sm", type: "submit" }, "↑"))));
  host.replaceChildren(root);
  const dockObserver = typeof ResizeObserver === "function" ? new ResizeObserver(() => {
    root.style.setProperty("--player-dock-height", Math.ceil(root.querySelector(".pl-dock").getBoundingClientRect().height) + "px");
  }) : null;
  dockObserver?.observe(root.querySelector(".pl-dock"));

  // ---------- helpers ----------
  function setStatus(kind, txt) { el.status.className = "pl-status " + kind; el.statusTxt.textContent = txt; el.avatar.classList.toggle("speaking", kind === "speaking"); el.avatar.classList.toggle("listening", kind === "listening"); const ms = kind === "speaking" ? "speaking" : kind === "listening" ? "listening" : kind === "thinking" ? "thinking" : "idle"; [el.mascotTop, el.mascotIntake, el.mascotStage].forEach((m) => m && m.set(ms)); }
  function addMsg(role, text, extra = {}) { const d = h("div", { class: "m " + role + (extra.interrupted ? " interrupted" : "") }, text, extra.interrupted ? h("span", { class: "cut", title: "cut off here" }, " —") : null); el.thread.append(d); el.thread.scrollTop = el.thread.scrollHeight; if (role !== "note") S.transcript.push({ role, text, t: Date.now(), ...extra }); if (role === "agent" && !el.drawer.classList.contains("open")) el.chatBtn.classList.add("unread"); }
  function preferTyping() { S.inputMode = "typed"; stopListening(); }
  function acceptTypedAnswer(text) {
    preferTyping();
    resumeSession();
    S.lastListen = { voice_ended: Date.now(), stt_done: Date.now(), via: "typed" };
    if (S.intakeOpen) { if (S.intakeResolver) S.intakeResolver(text); else { S.pendingIntakeAnswer = text; el.inHeard.textContent = text; } return; }
    if (S.waiter) { addMsg("user", text); resolveWait(replyForTurn(text, S.waiter)); return; }
    handleQuestion(text);
  }
  function toggleDrawer(force) { const on = force === undefined ? !el.drawer.classList.contains("open") : force; el.drawer.classList.toggle("open", on); if (on) { el.chatBtn.classList.remove("unread"); setTimeout(() => el.q.focus(), 80); } }
  function updateMuteUi() { el.muteBtn.textContent = S.muted ? "🔇" : "🔊"; el.muteBtn.title = S.muted ? "Unmute audio" : "Mute audio"; el.muteBtn.setAttribute("aria-label", el.muteBtn.title); el.muteBtn.setAttribute("aria-pressed", String(S.muted)); el.muteBtn.classList.toggle("on", S.muted); }
  function toggleMute() { S.muted = !S.muted; if (S.audio) S.audio.muted = S.muted; if (S.utterance) S.utterance.volume = S.muted ? 0 : 1; el.film.muted = S.muted || !el.stage.classList.contains("film-on"); updateMuteUi(); }
  function setChips(list) { const owner = S.waiter; el.chips.replaceChildren(...list.map((c) => h("button", { class: "chip" + (c.primary ? " primary" : ""), onclick: () => { if (S.waiter === owner) resolveWait(c.value); } }, c.label))); }
  function clearTimer() { if (S.timer) { clearInterval(S.timer); S.timer = null; } el.timer.replaceChildren(); }
  function newRun() { return ++S.run; }
  function renderProgress() { el.progress.replaceChildren(...S.plan.map((st, i) => h("button", { class: "pp" + (i < S.seg ? " done" : i === S.seg ? " active" : ""), title: st.slide.kind, onclick: () => { resumeSession(); interruptAll(); S.conversationOrigin = null; playFrom(i, 0); } }, st.slide.title))); }
  function renderCtas() { const ctas = (bundle.ctas || []).filter((c) => c.when === "always" || !c.when); el.ctas.replaceChildren(...ctas.map((c) => h("button", { class: "chip cta" + (c.primary ? " primary" : ""), onclick: () => { resumeSession(); interruptAll(); ctaFlow(c.id, newRun()); } }, c.label))); }

  // ---------- stage: one slide at a time, cross-faded ----------
  let cur = null;  // { slide, view, enteredAt }
  function showSlideView(slide, { reveal = -1 } = {}) {
    if (cur && cur.slide.id === slide.id && cur.view.el.isConnected) { cur.view.setRevealed(reveal); cur.view.highlight(null); return cur.view; }
    if (cur) { const old = cur; noteVisit(old); old.view.el.classList.remove("on"); setTimeout(() => old.view.destroy(), 700); }
    const view = renderSlide(slide, { fit: true });
    view.setRevealed(reveal);
    el.stack.append(view.el);
    view.layout(); void view.el.offsetWidth; view.el.classList.add("on");  // a forced reflow starts the cross-fade; no animation frame needed (a hidden tab never gets one)
    cur = { slide, view, enteredAt: Date.now() };
    preloadAfter(slide);
    return view;
  }
  function sessionNow() { return S.endedAt ?? Date.now(); }
  function noteVisit(c) { if (!c) return; S.visited.push({ slide_id: c.slide.id, kind: c.slide.kind, seconds: Math.round((sessionNow() - c.enteredAt) / 100) / 10 }); }
  function preloadAfter(slide) {  // the next slide's picture and audio are fetched while this one plays
    const i = S.plan.findIndex((st) => st.slide.id === slide.id); const next = i >= 0 ? S.plan[i + 1]?.slide : null; if (!next) return;
    if (next.image_url) { const im = new Image(); im.decoding = "async"; im.src = next.image_url; S.preloads.push(im); }
    for (const l of [...(next.lines || []), next.checkin?.audio ? { audio: next.checkin.audio } : null].filter(Boolean)) if (l.audio) { const a = new Audio(l.audio); a.preload = "auto"; a.load(); S.preloads.push(a); }
  }
  // A line spoken outside the deck gets complete reviewed evidence, never a clipped fact or an unrelated current image.
  function transientSlide(id, kind, text, factIds, visual, title = "") {
    const facts = (bundle.facts || []).filter((f) => (factIds || []).includes(f.id) && f.approved !== false);
    const allowed = new Set(facts.map((f) => f.id));
    const complete = (label) => typeof label === "string" && label.trim() && wordsOf(label) <= 8;
    const reviewed = slides.map((slide) => ({ slide, callouts: (slide.callouts || []).filter((c) => complete(c.text) && c.fact_ids?.length && c.fact_ids.every((fid) => allowed.has(fid))) }));
    const match = facts.length ? reviewed.find(({ slide, callouts }) => slide.image_url && facts.every((f) => callouts.some((c) => c.fact_ids.includes(f.id)))) : null;
    const candidates = [...(match?.callouts || []), ...reviewed.flatMap((s) => s.callouts)];
    const callouts = [], seen = new Set();
    for (const f of facts) {
      if (seen.has(f.id)) continue;
      const saved = candidates.find((c) => c.fact_ids.includes(f.id) && c.fact_ids.every((fid) => !seen.has(fid)));
      let label = saved?.text;
      if (!label && f.claim != null && f.value != null) {
        label = `${f.claim}: ${f.value}` + (f.conditions ? `; ${f.conditions}` : "");
        const truth = { certified: "Certified", modeled: "Estimate", observed: "Observed", contractual: "Written terms" }[f.truth];
        if (truth) label = `${truth} — ${label}`;
        label = label.trim().replace(/\s+/g, " ");
      }
      if (!complete(label)) continue;
      const citations = saved ? [...saved.fact_ids] : [f.id];
      citations.forEach((fid) => seen.add(fid));
      callouts.push({ id: `${id}-c${callouts.length + 1}`, text: label, fact_ids: citations, placement: "panel", anchor: null, label_pos: null, reveal_on_line: 0 });
      if (callouts.length === 3) break;
    }
    return { id, kind, title, topics: [], image_url: (visual && mediaUrlFor(visual)) || match?.slide.image_url || heroOpen().image_url || null, image_parts: [], motion: "none",
      callouts,
      lines: [{ id, text, fact_ids: factIds || [] }], checkin: { text: "" }, deeper: [], usp_ids: [], priority: false, role: kind };
  }

  // ---------- voice out ----------
  function browserVoice() {
    if (S.bt.voice) return S.bt.voice;
    const want = LANG.slice(0, 2).toLowerCase();
    const vs = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(want));
    const score = (v) => { let s = 0; const n = v.name; if (v.lang.replace("_", "-").toLowerCase() === LANG.toLowerCase()) s += 25; if (/neerja|veena|heera|swara|kalpana|lekha/i.test(n)) s += 60; if (/google uk english female|google us english$|google हिन्दी|google hindi/i.test(n)) s += 45; if (/samantha|kate\b|serena|karen|moira|zira|jenny|aria|sonia|libby|emma|olivia|amy\b|joanna|salli|natasha/i.test(n)) s += 30; if (/natural|premium|enhanced|neural|online/i.test(n)) s += 8; if (/rishi|daniel|alex\b|fred|arthur|gordon|oliver|reed|tom\b|david|mark\b|james|guy\b|ryan|ravi|male|eddy|flo\b|grandma|grandpa|sandy|shelley|bahh|bells|boing|bubbles|cellos|wobble|zarvox|trinoids|whisper|jester|organ|superstar|good news|bad news|albert|junior|ralph|kathy/i.test(n)) s -= 70; return s; };
    S.bt.voice = vs.sort((a, b) => score(b) - score(a))[0] || null; return S.bt.voice;
  }
  const wordsOf = (t) => String(t || "").trim().split(/\s+/).filter(Boolean).length;
  // The transcript is what the customer heard. A line is logged when its audio ends; a line cut short is logged as the
  // words that played (elapsed / duration × words) and marked interrupted. captions and the browser voice use elapsed time.
  function logHeard(sp, complete) {
    if (!sp || sp.logged) return; sp.logged = true;
    if (complete) { addMsg("agent", sp.text); return; }
    const a = sp.audio; const frac = a && isFinite(a.duration) && a.duration > 0 ? a.currentTime / a.duration : Math.min(1, (Date.now() - sp.startedAt) / Math.max(1, sp.estMs));
    const n = Math.min(sp.words, Math.round(frac * sp.words)); if (n <= 0) return;
    addMsg("agent", sp.text.split(/\s+/).slice(0, n).join(" "), { interrupted: true, full: sp.text, heard_fraction: +frac.toFixed(2) });
  }
  function firstAudio() { if (S.onFirstAudio) { const f = S.onFirstAudio; S.onFirstAudio = null; f(Date.now()); } }
  function captionOnly(text, run) {
    return new Promise((res) => {
      const my = ++S.ttsToken, words = wordsOf(text), ms = Math.max(1200, words / 2.5 * 1000);
      const sp = { text, words, audio: null, startedAt: Date.now(), estMs: ms }; S.speaking = sp;
      setStatus("idle", "Audio unavailable · reading together"); firstAudio();
      let done = false;
      const finish = (complete) => { if (done) return; done = true; clearTimeout(t); if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.speaking === sp) { logHeard(sp, complete); S.speaking = null; } res(complete && my === S.ttsToken && run === S.run); };
      const cancel = () => finish(false); S.cancelVoice = cancel;
      const t = setTimeout(() => finish(true), ms);
    });
  }
  function speakBrowser(text, run) {
    return new Promise((res) => {
      const my = ++S.ttsToken, u = new SpeechSynthesisUtterance(text); S.utterance = u;
      const v = browserVoice(); if (v) u.voice = v; u.lang = LANG; u.rate = 0.98; u.pitch = 1.05; u.volume = S.muted ? 0 : 1;
      const sp = { text, words: wordsOf(text), audio: null, startedAt: Date.now(), estMs: Math.max(1500, text.length * 75) }; S.speaking = sp;
      let done = false;
      const finish = (complete) => { if (done) return; done = true; clearTimeout(t); if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.utterance === u) S.utterance = null; if (S.speaking === sp) { logHeard(sp, complete); S.speaking = null; } res(complete && my === S.ttsToken && run === S.run); };
      const cancel = () => finish(false); S.cancelVoice = cancel;
      const t = setTimeout(() => finish(true), sp.estMs + 4000);
      u.onstart = () => { if (!done && my === S.ttsToken && run === S.run) { sp.startedAt = Date.now(); setStatus("speaking", "Speaking"); firstAudio(); } };
      u.onend = () => finish(true); u.onerror = () => finish(false);
      try { speechSynthesis.speak(u); } catch (e) { finish(false); }
    });
  }
  async function audioUrlFor(text, preset) { if (preset) return preset; if (!useServerVoice) return null; if (S.ttsCache.has(text)) return S.ttsCache.get(text); const p = api.tts(text).catch(() => null); S.ttsCache.set(text, p); return p; }
  function prefetch(items) { if (!useServerVoice) return; for (const it of items) if (it && !it.audio && it.text) audioUrlFor(it.text); }
  async function speak(text, run, preset) {
    if (run !== S.run || !text) return run === S.run;
    el.cap.textContent = text; if (S.intakeOpen) el.inQ.textContent = text; setStatus("thinking", "Preparing audio");
    let url = null; try { url = await audioUrlFor(text, preset); } catch (e) {}
    if (run !== S.run) return false;
    let ok;
    if (url) ok = await new Promise((res) => {
      const my = ++S.ttsToken, a = new Audio(url); a.muted = S.muted; S.audio = a;
      const sp = { text, words: wordsOf(text), audio: a, startedAt: Date.now(), estMs: wordsOf(text) / 2.5 * 1000 }; S.speaking = sp;
      let done = false;
      const finish = (complete) => { if (done) return; done = true; if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.audio === a) S.audio = null; if (S.speaking === sp) { logHeard(sp, complete); S.speaking = null; } res(complete && my === S.ttsToken && run === S.run); };
      const cancel = () => { a.pause(); finish(false); }; S.cancelVoice = cancel;
      a.onplaying = () => { if (!done && my === S.ttsToken && run === S.run) { sp.startedAt = Date.now(); setStatus("speaking", "Speaking"); firstAudio(); } else a.pause(); };
      const safeFallback = () => {
        if (done) return;
        if (my !== S.ttsToken || run !== S.run) { finish(false); return; }
        done = true; a.pause(); if (S.audio === a) S.audio = null; if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.speaking === sp) S.speaking = null;
        (useServerVoice ? captionOnly(text, run) : speakBrowser(text, run)).then(res);
      };
      a.onended = () => finish(true); a.onerror = safeFallback; a.play().catch(safeFallback);
    });
    else ok = useServerVoice ? await captionOnly(text, run) : await speakBrowser(text, run);
    if (ok && run === S.run) setStatus("idle", "Ready");
    return ok && run === S.run;
  }
  function cancelSpeech() {
    S.ttsToken++; if (S.cancelVoice) S.cancelVoice(); S.cancelVoice = null;
    try { speechSynthesis.cancel(); } catch (e) {} S.utterance = null;
    if (S.audio) { try { S.audio.pause(); } catch (e) {} S.audio = null; }
  }

  // ---------- voice in ----------
  function encodeWav(chunks, inRate, outRate = 16000) {
    const total = chunks.reduce((n, c) => n + c.length, 0); const all = new Float32Array(total); let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
    const ratio = inRate / outRate, outLen = Math.floor(all.length / ratio), pcm = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) { const s0 = Math.floor(i * ratio), s1 = Math.min(all.length, Math.floor((i + 1) * ratio)); let sum = 0; for (let j = s0; j < s1; j++) sum += all[j]; const v = Math.max(-1, Math.min(1, sum / Math.max(1, s1 - s0))); pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff; }
    const buf = new ArrayBuffer(44 + pcm.length * 2), dv = new DataView(buf); const w = (p, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(p + i, s.charCodeAt(i)); };
    w(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, outRate, true); dv.setUint32(28, outRate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, "data"); dv.setUint32(40, pcm.length * 2, true);
    new Int16Array(buf, 44).set(pcm); return new Blob([buf], { type: "audio/wav" });
  }
  // Each capture owns its callbacks through permission, capture and transcription. Cancelling a turn
  // invalidates all three stages; finishing the mic deliberately still delivers this turn's answer.
  async function listenServer(opts, id) {
    const { timeout = 10000, onInterim = () => {} } = opts;
    const current = () => id === S.listenId;
    let stream;
    try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); }
    catch (e) { if (current()) { S.micDenied = true; setStatus("idle", "Microphone unavailable · type below"); } return ""; }
    if (!current()) { stream.getTracks().forEach((t) => t.stop()); return ""; }
    let ctx, src, proc;
    try { const Ctx = window.AudioContext || window.webkitAudioContext; ctx = new Ctx(); src = ctx.createMediaStreamSource(stream); proc = ctx.createScriptProcessor(4096, 1, 1); }
    catch (e) { stream.getTracks().forEach((t) => t.stop()); if (ctx) ctx.close().catch(() => {}); return ""; }
    const chunks = []; let spoke = false, lastVoice = Date.now(), t0 = Date.now(), capturing = true;
    S.micOn = true; setMicUI(true); onInterim("Listening…");
    return new Promise((res) => {
      let settled = false;
      const settle = (text) => { if (settled) return; settled = true; if (current()) { S.cancelListen = null; S.finishListen = null; S.micOn = false; setMicUI(false); } res(text); };
      const cleanup = () => { if (!capturing) return; capturing = false; clearTimeout(t); try { proc.disconnect(); src.disconnect(); } catch (e) {} stream.getTracks().forEach((track) => track.stop()); ctx.close().catch(() => {}); if (current()) { S.micOn = false; setMicUI(false); } };
      const cancel = () => { cleanup(); settle(""); };
      const finish = async () => {
        if (!capturing || !current()) return; cleanup();
        if (!spoke || !chunks.length) { settle(""); return; }
        const tVoice = Date.now(); setStatus("thinking", "Transcribing"); if (S.intakeOpen) el.inState.textContent = "Transcribing your answer…"; onInterim("Transcribing…");
        try { const text = await api.stt(encodeWav(chunks, ctx.sampleRate), LANG); if (!current() || settled) return; S.lastListen = { voice_ended: tVoice, stt_done: Date.now(), via: "server" }; settle((text || "").trim()); }
        catch (e) { if (!current() || settled) return; if (SR) { serverSTT = false; addMsg("note", "Server listening is unavailable — you can retry with browser listening or type below."); } settle(""); }
      };
      S.cancelListen = cancel; S.finishListen = finish;
      const t = setTimeout(finish, timeout);
      proc.onaudioprocess = (e) => {
        if (!current() || !capturing) return;
        const d = e.inputBuffer.getChannelData(0); chunks.push(new Float32Array(d)); let sum = 0; for (const sample of d) sum += sample * sample;
        const now = Date.now(); if (Math.sqrt(sum / d.length) > 0.012) { spoke = true; lastVoice = now; }
        if ((spoke && now - lastVoice > 1300) || now - t0 > timeout || (!spoke && now - t0 > Math.min(timeout, 7000))) finish();
      };
      src.connect(proc); proc.connect(ctx.destination);
    });
  }
  function listen(opts = {}) {
    stopListening(); const id = ++S.listenId;
    if (serverSTT && !S.micDenied && navigator.mediaDevices?.getUserMedia) { setStatus("thinking", "Opening microphone"); return listenServer(opts, id); }
    return listenBrowser(opts, id);
  }
  function listenBrowser({ timeout = 10000, onInterim = () => {} } = {}, id) {
    return new Promise((res) => {
      if (!SR || S.micDenied) { res(""); return; }
      const current = () => id === S.listenId;
      const rec = new SR(); S.rec = rec; rec.lang = LANG; rec.interimResults = true; rec.continuous = false;
      let fin = "", interim = "", ended = false; S.micOn = true; setMicUI(true);
      const end = (discard = false) => {
        if (ended) return; ended = true; clearTimeout(t);
        const text = !discard && current() ? (fin || interim).trim() : "";
        if (current()) { S.cancelListen = null; S.finishListen = null; S.rec = null; S.micOn = false; setMicUI(false); if (text) S.lastListen = { voice_ended: Date.now(), stt_done: Date.now(), via: "browser" }; }
        res(text);
      };
      S.cancelListen = () => { end(true); try { rec.abort(); } catch (e) {} };
      S.finishListen = () => { try { rec.stop(); } catch (e) { end(); } };
      rec.onresult = (e) => { if (ended || !current()) return; interim = ""; fin = ""; for (const r of e.results) { if (r.isFinal) fin += r[0].transcript; else interim += r[0].transcript; } onInterim((fin || interim).trim()); };
      rec.onerror = (e) => { if (!current() || ended) return; if (e.error === "not-allowed" || e.error === "service-not-allowed") S.micDenied = true; end(); };
      rec.onend = () => end(); const t = setTimeout(() => { if (current()) S.finishListen?.(); }, timeout);
      try { rec.start(); } catch (e) { end(); }
    });
  }
  function stopListening(discard = true) {
    if (!discard) { S.finishListen?.(); return; }
    const cancel = S.cancelListen; S.listenId++; S.cancelListen = null; S.finishListen = null; S.rec = null;
    if (cancel) cancel(); S.micOn = false; setMicUI(false);
  }
  function setMicUI(on) {
    el.mic.classList.toggle("on", on); el.inMic.classList.toggle("on", on);
    if (on) { setStatus("listening", "Listening"); el.hint.textContent = "Listening… tap the mic when you are done, or type below."; if (S.intakeOpen) el.inState.textContent = "Listening — or type your answer below"; }
    else { el.live.textContent = ""; if (el.status.classList.contains("listening")) setStatus("idle", "Your turn"); el.hint.textContent = canListen() && !S.micDenied ? "Tap to talk, or type your reply below." : "Type your reply below."; }
  }

  // ---------- flow primitives ----------
  function interruptAll() { newRun(); cancelSpeech(); stopListening(); try { el.film.pause(); } catch (e) {} el.stage.classList.remove("film-on"); S.onFirstAudio = null; clearTimer(); if (S.waiter) { const w = S.waiter; S.waiter = null; S.waitChips = []; w.resolve({ value: "__interrupted" }); } if (S.intakeResolver) S.intakeResolver(""); setChips([]); }
  function interpretReply(t, chips) {
    const s = t.toLowerCase().trim().replace(/[.!?,]+$/g, ""), has = (v) => chips.some((c) => c.value === v);
    if (has("callme") && PHONE.test(s.replace(/\s|-/g, ""))) return { value: "phone", text: t };
    if (has("callme") && /^(call me|yes please|please call me)$/.test(s)) return { value: "callme" };
    if (/^(continue(?: the demo)?|carry on|go on|go ahead|next|move on|proceed)$/.test(s) && has("continue")) return { value: "continue" };
    if (/^(yes|yeah|yep|ya|haan|ok|okay|sure|fine|good|great|perfect|that helps|yes[,]? that helps|yes[,]? continue|clear|settled|that settles it|got it|understood|thanks|thank you|alright|cool|makes sense|theek|thik|achha|accha)$/.test(s)) {
      if (has("yes")) return { value: "yes" }; if (has("continue")) return { value: "continue" };
    }
    if (/^(no|nope|not really|not quite|unsure|still unsure|not sure|tell me more|more|deeper|explain|elaborate|not clear|i'm not sure|nahi|nahin)$/.test(s)) {
      if (has("deeper")) return { value: "deeper" }; if (has("no")) return { value: "no" };
    }
    for (const c of bundle.ctas || []) if (s.includes(c.label.toLowerCase()) && has("cta:" + c.id)) return { value: "cta:" + c.id };
    if (/(not yet|later|think about|not now|baad mein)/.test(s) && has("notyet")) return { value: "notyet" };
    if (/(human|person|advisor|someone|sales|team)/.test(s) && has("human")) return { value: "human" };
    return { value: "question", text: t };
  }
  function replyForTurn(text, turn) {
    if (!turn.openAnswer) return interpretReply(text, turn.chips);
    const value = text.toLowerCase().trim().replace(/[.!?,]+$/g, "");
    if (/^(continue(?: the demo)?|carry on|go ahead)$/.test(value) && turn.chips.some((c) => c.value === "continue")) return { value: "continue" };
    if (/^skip(?: this question)?$/.test(value)) { const skip = turn.chips.find((c) => c.value === "skip" || c.label === "Skip this question"); if (skip) return { value: skip.value }; }
    return { value: "answer", text };
  }
  function listenForTurn(turn) {
    if (S.inputMode !== "voice" || S.waiter !== turn || turn.run !== S.run || !canListen() || S.micDenied) return;
    listen({ timeout: turn.listenSecs, onInterim: (t) => { if (S.waiter === turn) el.live.textContent = t; } }).then((t) => {
      if (S.waiter !== turn || turn.run !== S.run) return;
      if (t) { addMsg("user", t); resolveWait(replyForTurn(t, turn)); }
      else { setStatus("idle", "Your turn"); el.hint.textContent = "Type your reply, tap the mic to try again, or choose an option."; }
    });
  }
  function waitFor(chips, seconds = 0, opts = {}) {
    return new Promise((res) => {
      clearTimer();
      const turn = { resolve: res, run: S.run, chips, openAnswer: !!opts.openAnswer, listenSecs: opts.listenSecs || 10000 };
      S.waiter = turn; S.waitChips = chips; setChips(chips); setStatus("idle", "Your turn");
      el.hint.textContent = "Take your time. Reply by voice or type, or choose an option.";
      if (opts.listen !== false) listenForTurn(turn);
    });
  }
  function resolveWait(v) { clearTimer(); if (S.waiter) { const w = S.waiter; S.waiter = null; S.waitChips = []; stopListening(); setChips([]); w.resolve(typeof v === "string" ? { value: v } : v); } }
  async function askAndListen(question, run, secs = 10000, preset = null) { const ok = await speak(question, run, preset); if (!ok) return null; const r = await waitFor([{ label: "Skip this question", value: "skip" }], 0, { openAnswer: true, listenSecs: secs }); return run === S.run ? r.text || "" : null; }

  // ---------- route building: the pitch plan orders slides ----------
  function buildRoute(plan) {
    const lib = library(); const bySeg = Object.fromEntries(lib.map((s) => [s.segment_id, s]));
    let steps = [];
    if (plan?.route?.length) steps = plan.route.map((r) => ({ r, slide: (r.slide_id && lib.find((s) => s.id === r.slide_id)) || bySeg[r.segment_id] })).filter((x) => x.slide).map(({ r, slide }) => ({ slide, bridge: r.bridge, bridge_audio: r.bridge_audio || "", bridge_fact_ids: r.bridge_fact_ids || [] }));
    if (!steps.length) { // fallback: focus topics first, then deck order, establish last
      const focus = new Set(S.profile.focus); const hit = (s) => focus.has(topicOf(s)) || focus.has(s.segment_id); const proof = lib.filter((s) => s.kind !== "establish"); const est = lib.filter((s) => s.kind === "establish");
      steps = [...proof.filter(hit), ...proof.filter((s) => !hit(s)), ...est].map((slide) => ({ slide, bridge: "", bridge_fact_ids: [] }));
    }
    S.plan = steps; S.seg = 0; renderProgress();
    prefetch(steps.filter((s) => s.bridge).map((s) => ({ text: s.bridge })));
  }
  function rememberContext(text) {
    if (!text) return;
    S.profile.followup = [S.profile.followup, text].filter(Boolean).join("\n");
    S.profile.focus = [...new Set([...S.profile.focus, ...parseFocus(text)])];
  }
  async function waitForLineQuestion(line, run) {
    if (line.step !== "confirm" && !/[?？]/.test(line.text || "")) return run === S.run;
    const r = await waitFor([{ label: "Skip this question", value: "continue" }], 0, { openAnswer: true });
    if (run !== S.run) return false;
    if (r.text) { rememberContext(r.text); handleQuestion(r.text); return false; }
    return r.value === "continue";
  }
  async function playLines(sl, run, view, from = 0, upto = sl.lines.length) {
    for (let j = from; j < upto; j++) {
      if (run !== S.run) return false;
      S.line = j; S.playback.line = j;
      const ln = sl.lines[j]; view.setRevealed(j); el.cite.textContent = ln.fact_ids?.length ? "sources: " + ln.fact_ids.join(", ") : "";
      if (!(await speak(ln.text, run, ln.audio))) return false;
      S.line = j + 1; S.playback.line = j + 1;
      if (!(await waitForLineQuestion(ln, run))) return false;
    }
    return run === S.run;
  }
  async function playOpening(run, index = 0, line = 0) {
    const list = opening();
    for (let i = index; i < list.length; i++) {
      if (run !== S.run) return false;
      const sl = list[i]; S.playback = { phase: "opening", index: i, line };
      prefetch(sl.lines); const view = showSlideView(sl, { reveal: line - 1 });
      if (!(await playLines(sl, run, view, line))) return false;
      line = 0;
    }
    S.playback = { phase: "planning", line: 0 };
    return run === S.run;
  }
  async function playFrom(idx, lineIdx = 0, bridgeDone = false) {
    const run = newRun();
    for (let i = idx; i < S.plan.length; i++) {
      const step = S.plan[i], sl = step.slide; S.seg = i; S.atCheckin = false; S.playback = { phase: "route", index: i, line: lineIdx, checkin: false, bridgeDone }; renderProgress();
      prefetch([...sl.lines.slice(lineIdx), sl.checkin?.text ? { text: sl.checkin.text, audio: sl.checkin.audio } : null].filter(Boolean));
      const short = lineIdx === 0 && S.covered.has(sl.id) && sl.lines.length > 1;  // seen during a question: title + first line, no check-in
      const view = showSlideView(sl, { reveal: short ? 99 : lineIdx - 1 });
      if (lineIdx === 0 && step.bridge && !bridgeDone) { el.cite.textContent = step.bridge_fact_ids?.length ? "sources: " + step.bridge_fact_ids.join(", ") : ""; if (!(await speak(step.bridge, run, step.bridge_audio))) return; S.playback.bridgeDone = true; if (!(await waitForLineQuestion({ text: step.bridge }, run))) return; }
      if (!(await playLines(sl, run, view, lineIdx, short ? 1 : sl.lines.length))) return;
      lineIdx = 0; bridgeDone = false; if (run !== S.run) return;
      const topic = topicOf(sl);
      if (sl.checkin?.text && !short) {
        S.atCheckin = true; S.playback.checkin = true; const ok = await speak(sl.checkin.text, run, sl.checkin.audio); if (!ok) return;
        const conc = !!sl.priority || S.profile.focus.includes(topic);
        const chips = conc ? [{ label: "That settles it", value: "yes", primary: true }, { label: "Still unsure", value: "deeper" }, { label: "I have a question", value: "question" }] : [{ label: "Continue", value: "continue", primary: true }, { label: "Tell me more", value: "deeper" }, { label: "I have a question", value: "question" }];
        const r = await waitFor(chips); if (run !== S.run) return;
        if (r.value === "yes") { S.resolved.add(topic); const ok2 = await speakF("good", "Good — moving on.", run); if (!ok2) return; }
        else if (r.value === "deeper") { if (!(await playDeeper(sl, run, view))) return; }
        else if (r.value === "question") { if (r.text) handleQuestion(r.text); else listenForQuestion(); return; }
        else if (r.value === "__interrupted") return;
      }
    }
    await closeFlow(run);
  }

  async function playDeeper(sl, run, view, from = 0) {
    S.raised.add(topicOf(sl)); prefetch(sl.deeper || []); view.setRevealed(99);
    const lines = sl.deeper || [];
    for (let j = from; j < lines.length; j++) {
      if (run !== S.run) return false;
      S.playback = { phase: "deeper", index: S.seg, line: j };
      if (!(await speak(lines[j].text, run, lines[j].audio))) return false;
      S.playback.line = j + 1;
      if (!(await waitForLineQuestion(lines[j], run))) return false;
    }
    S.playback = { phase: "route", index: S.seg, line: sl.lines.length, checkin: true, bridgeDone: true };
    if (!lines.length && !(await speak("That's everything the material covers on this. Ask me anything specific and I'll check.", run))) return false;
    if (!(await speakF("clearer", "Is that clearer?", run))) return false;
    const r = await waitFor([{ label: "Yes, continue", value: "yes", primary: true }, { label: "Not really", value: "no" }, { label: "Question", value: "question" }]);
    if (run !== S.run) return false;
    if (r.value === "yes") { S.resolved.add(topicOf(sl)); S.unresolved.delete(topicOf(sl)); S.openQuestions.delete(`More clarity on ${sl.title}`); return true; }
    if (r.value === "no") {
      S.unresolved.add(topicOf(sl)); S.openQuestions.add(`More clarity on ${sl.title}`); S.escalations.push(`${topicOf(sl)} — still unsure after the deeper explanation`);
      if (!(await speak("What would help make that clearer? You can ask something specific, or choose Continue when you are ready.", run))) return false;
      captureOrigin(); await holdConversation(run);
    } else if (r.text) handleQuestion(r.text);
    else if (r.value === "question") listenForQuestion();
    return false;
  }
  async function resumeDeeper(origin, run) {
    const sl = S.plan[origin.index]?.slide; if (!sl || run !== S.run) return;
    S.seg = origin.index; const view = showSlideView(sl, { reveal: 99 });
    if (await playDeeper(sl, run, view, origin.line)) playFrom(origin.index + 1, 0);
  }

  async function closeFlow(run, line = 0) {
    if (run !== S.run) return;
    S.atCheckin = true; S.playback = { phase: "closing", line };
    const cs = closingSlide();
    if (cs) {
      const view = showSlideView(cs, { reveal: line - 1 });
      if (line === 0 && S.pitch?.advance) { view.setRevealed(0); if (!(await speak(S.pitch.advance, run, S.pitch.advance_audio))) return; S.playback.line = 1; if (!(await waitForLineQuestion({ text: S.pitch.advance }, run))) return; if (!(await playLines(cs, run, view, 1))) return; }
      else if (!(await playLines(cs, run, view, line))) return;
    }
    S.playback = { phase: "closing", line: cs?.lines?.length || 0 };
    showSlideView(heroClose(), { reveal: 99 });
    const chips = (bundle.ctas || []).map((c) => ({ label: c.label, value: "cta:" + c.id, primary: !!c.primary || c.id === S.pitch?.advance_cta })).concat([{ label: "Not yet", value: "notyet" }, { label: "One more question", value: "question" }]);
    const r = await waitFor(chips, 0); if (run !== S.run) return;
    if (r.value === "question") { if (r.text) handleQuestion(r.text); else listenForQuestion(); return; }
    if (r.value === "__interrupted") return;
    if (r.value === "notyet") { const ok = await speak("Fair enough. Here's a summary of what we covered so you have it when you decide.", run); if (!ok) return; S.cta = "summary"; showHandoff(); return; }
    if (r.value.startsWith("cta:")) await ctaFlow(r.value.slice(4), run);
  }
  async function ctaFlow(id, run) {
    const c = (bundle.ctas || []).find((x) => x.id === id) || { label: id, kind: "custom" }; S.cta = c.label;
    const line = c.kind === "book" ? `Let's do that. I'll pass everything we discussed along so you don't repeat yourself.` : c.kind === "contact" ? `Done — someone from the team will take it from here with the full context.` : `Good call — “${c.label}” it is. Everything we discussed travels with it.`;
    const ok = await speak(line, run); if (!ok) return; showHandoff(c);
  }
  function captureOrigin() { if (!S.conversationOrigin) S.conversationOrigin = { ...S.playback }; }
  async function listenForQuestion() {
    captureOrigin(); interruptAll(); const run = newRun();
    el.cap.textContent = "What would you like to know?";
    const r = await waitFor([{ label: "Continue demo", value: "continue", primary: true }], 0, { openAnswer: true });
    if (run !== S.run) return;
    if (r.text) handleQuestion(r.text); else if (r.value === "continue") resumeAfterQA();
  }
  function micTap() {
    S.inputMode = "voice";
    resumeSession();
    if (S.micOn) { stopListening(false); return; }
    if (S.intakeOpen) { intakeMic(); return; }
    if (S.waiter) { listenForTurn(S.waiter); return; }
    listenForQuestion();
  }
  async function holdConversation(run) {
    const r = await waitFor([{ label: "Ask another question", value: "question" }, { label: "Continue demo", value: "continue", primary: true }]);
    if (run !== S.run) return;
    if (r.value === "continue") { el.lead.classList.remove("open"); resumeAfterQA(); }
    else if (r.text) handleQuestion(r.text);
    else if (r.value === "question") listenForQuestion();
  }

  // ---------- questions, don't-guess, lead capture ----------
  async function handleQuestion(text, options = {}) {
    captureOrigin(); interruptAll(); const run = newRun(); let jumped = null;
    const customerQuestion = options.question || text;
    const last = S.transcript.at(-1); if (!(last?.role === "user" && last.text === text)) addMsg("user", text);
    if (!options.question) S.questions.push(text);
    S.openQuestions.add(customerQuestion);
    const turn = { question: customerQuestion, ...(S.lastListen || { voice_ended: Date.now(), stt_done: Date.now(), via: "unknown" }), qa_done: null, answer_audio: null }; S.lastListen = null; S.turns.push(turn); el.live.textContent = ""; setStatus("thinking", "Checking your question"); el.cap.textContent = "Checking the approved information…";
    let r;
    const qaP = api.qa({ question: customerQuestion, history: S.transcript.slice(-8).map((t) => ({ role: t.role, text: t.text })), profile: profileForServer(), slide_id: cur?.slide?.id || null, ...(options.skipBank ? { skip_bank: true } : {}) });
    try {
      r = await withTimeout(qaP, 700);
      if (run !== S.run) return;
      if (!r) { if (!(await speakF("hold_on_question", "Give me one moment while I check that for you.", run))) return; setStatus("thinking", "Checking the approved information"); r = await qaP; }
    } catch (e) {
      turn.qa_done = Date.now(); turn.error = true; if (run !== S.run) return;
      S.onFirstAudio = (ts) => { turn.answer_audio = ts; };
      if (!(await speak("I couldn't reach my notes just now. You can ask again, or choose Continue when you are ready.", run))) return;
      S.escalations.push(`error answering: "${customerQuestion}"`); S.unresolved.add("question"); await holdConversation(run); return;
    }
    if (run !== S.run) return;
    turn.qa_done = Date.now(); turn.from_bank = !!r.from_bank; turn.route = r.route || null; turn.answered = !!r.answered;
    S.onFirstAudio = (ts) => { turn.answer_audio = ts; };
    // A clarification is the answer for this turn. Do not speak a provisional claim or ask it twice.
    if (r.clarifying_question) {
      el.cite.textContent = "";
      const a = await askAndListen(r.clarifying_question, run, 10000, r.answer === r.clarifying_question ? r.audio : null);
      if (run !== S.run) return;
      if (a) { rememberContext(`${r.clarifying_question} ${a}`); handleQuestion(a, { question: customerQuestion, skipBank: true }); }
      else await holdConversation(run);
      return;
    }
    if (!r.answered) {
      if (r.escalate) S.escalations.push(r.escalate);
      if (r.topic && r.topic !== "other") S.raised.add(r.topic);
      S.unresolved.add(r.topic || "question"); el.cite.textContent = "";
      if (!(await speak("I don't have that answer in the approved information. I've kept it as an open question. You can ask something else, continue when you are ready, or request help from the dealership.", run))) return;
      showLeadPrompt("unknown", customerQuestion); await holdConversation(run); return;
    }
    const from = cur?.slide?.id || null;
    jumped = r.route === "jump" && r.slide_id && r.slide_id !== from ? slides.find((s) => s.id === r.slide_id) || null : null;
    if (jumped) {
      // A transition is heard before the view changes; it is not the first answer audio.
      S.onFirstAudio = null;
      if (!(await speakF("bridge_to_custom", "Let me show you where that is.", run))) return;
      showSlideView(jumped, { reveal: 99 }); S.covered.add(jumped.id); S.jumps.push({ from, to: jumped.id, question: text });
      S.onFirstAudio = (ts) => { turn.answer_audio = ts; };
    } else cur?.view.setRevealed(99);
    if (r.callout_id) cur?.view.highlight(r.callout_id);
    el.cite.textContent = r.fact_ids?.length ? "sources: " + r.fact_ids.join(", ") : "";
    if (r.escalate) S.escalations.push(r.escalate); if (r.topic && r.topic !== "other") S.raised.add(r.topic);
    if (r.from_bank) addMsg("note", "answered from the FAQ bank — no model call");
    if (!(await speak(r.answer, run, r.audio))) return;
    if (r.cta) { await ctaFlow(r.cta, run); return; }
    if (r.offer_callback) showLeadPrompt("question", customerQuestion);
    if (!(await speakF("did_that_answer", "Did that answer it?", run))) return;
    const r2 = await waitFor([{ label: "Yes, that helps", value: "yes", primary: true }, { label: "Not quite", value: "no" }, { label: "Ask another question", value: "question" }]);
    if (run !== S.run) return;
    if (r2.value === "yes") { S.resolved.add(r.topic || "question"); S.unresolved.delete(r.topic || "question"); S.openQuestions.delete(customerQuestion); el.lead.classList.remove("open"); resumeAfterQA(); }
    else if (r2.value === "no") {
      S.unresolved.add(r.topic || "question"); S.escalations.push(`not satisfied: "${customerQuestion}"`);
      if (!(await speak("What part is still unclear? Tell me a little more, or choose Continue when you are ready. I'll keep this question open.", run))) return;
      await holdConversation(run);
    } else if (r2.text) handleQuestion(r2.text);
    else if (r2.value === "question") listenForQuestion();
  }
  function showLeadPrompt(reason, question = "") {
    if (S.leads.length || (S.leadPromptShown && reason !== "unknown" && reason !== "requested")) return;
    S.leadPromptShown = true; S.leadReason = reason; S.leadQuestion = question || "test drive";
    el.leadName.value = S.profile.name || ""; el.leadPhone.value = ""; el.leadError.textContent = "";
    const callback = reason === "unknown" || reason === "requested";
    el.lead.querySelector("h3").textContent = callback ? "Would you like the dealership to follow up?" : "Would you like to try it in person?";
    el.leadForm.querySelector("button[type=submit]").textContent = callback ? "Request a callback" : "Arrange a test drive";
    el.leadCopy.textContent = reason === "unknown" ? "I don't have that answer in the approved sources. Leave your details and the dealership can answer it directly." : reason === "requested" ? "Share your details if you would like help with the questions we discussed." : "Share your details if you would like the dealership to arrange a test drive.";
    el.lead.classList.add("open");
  }
  async function saveLeadForm() {
    const name = el.leadName.value.trim(); const raw = el.leadPhone.value.replace(/[\s-]/g, ""); const m = raw.match(PHONE);
    if (!m) { el.leadError.textContent = "Enter a valid 10-digit Indian mobile number."; el.leadPhone.focus(); return; }
    const btn = el.leadForm.querySelector("button[type=submit]"); btn.disabled = true; el.leadError.textContent = "Saving…";
    let ok = true; try { await api.lead({ phone: m[1], question: S.leadQuestion || "test drive", profile: { ...profileForServer(), name: name || S.profile.name }, consent: true, consent_text: CONSENT, session_id: S.sessionId }); } catch (e) { ok = false; }
    btn.disabled = false;
    if (!ok) { el.leadError.textContent = "Couldn't save that just now. Please try once more."; return; }
    if (name) S.profile.name = name; S.leads.push({ phone: m[1], question: S.leadQuestion || "test drive" }); S.escalations.push(`callback requested on ${m[1]}: "${S.leadQuestion || "test drive"}"`);
    el.lead.classList.remove("open"); addMsg("note", "Follow-up request saved for the dealership");
  }
  function profileForServer() { return { name: S.profile.name, why: S.profile.why, followup: S.profile.followup, focus: S.profile.focus, customer_state: S.pitch?.customer_state, language: bundle.language }; }
  const _origTts = api.tts; api.tts = (text) => _origTts ? api.tts_lang ? api.tts_lang(text, bundle.language) : _origTts(text) : Promise.resolve(null);
  function mediaUrlFor(v) { if (!v) return null; for (const im of bundle.media?.images || []) if (im.id === v.ref) return im.url; const src = v.source_id; for (const vid of bundle.media?.videos || []) if (v.kind === "shot" && src && vid.url.includes(src)) return null; return null; }
  async function resumeAfterQA() {
    const origin = S.conversationOrigin || { ...S.playback }; S.conversationOrigin = null;
    if (cur) cur.view.highlight(null);
    const run = newRun();
    if (!(await speakF("back_to_demo", "Let's return to where we paused.", run))) return;
    resumePlayback(origin, run);
  }
  function resumePlayback(origin, run = newRun()) {
    if (run !== S.run) return;
    if (origin.phase === "route") { playFrom(origin.index + (origin.checkin ? 1 : 0), origin.checkin ? 0 : origin.line, !origin.checkin && origin.bridgeDone); return; }
    if (origin.phase === "deeper") { resumeDeeper(origin, run); return; }
    if (origin.phase === "closing") { closeFlow(run, origin.line); return; }
    if (origin.phase === "intake") { runIntake(); return; }
    startAfterIntake(run, S.profile.why, origin);
  }

  // ---------- intake + standard opening + pitch plan ----------
  function intakeWait(run) {
    return new Promise((res) => {
      let done = false; const fin = (t) => { if (done) return; done = true; S.intakeResolver = null; stopListening(); res(t); }; S.intakeResolver = fin; el.inHeard.textContent = "";
      if (S.pendingIntakeAnswer) { const queued = S.pendingIntakeAnswer; S.pendingIntakeAnswer = ""; fin(queued); return; }
      if (S.inputMode === "voice" && canListen() && !S.micDenied) { el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; listen({ timeout: 10000, onInterim: (t) => { el.inHeard.textContent = t; } }).then((t) => { if (done || run !== S.run) return; if (t) fin(t); else { el.inState.textContent = "Tap the mic to try again, or type below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); } }); }
      else { el.inState.textContent = "Type your answer below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); }
    });
  }
  async function intakeMic() { S.inputMode = "voice"; if (S.micOn) { stopListening(false); return; } if (!S.intakeResolver) return; cancelSpeech(); const fin = S.intakeResolver; el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; const t = await listen({ timeout: 10000, onInterim: (x) => { el.inHeard.textContent = x; } }); if (t && S.intakeResolver === fin) fin(t); else if (S.intakeResolver === fin) { el.inState.textContent = "Tap the mic to try again, or type below"; el.inFallback.classList.add("open"); } }
  function parseName(t) { let m = t.match(/(?:my name is|myself|name's|call me|mera naam|naam)\s+([A-Za-zऀ-ॿ][a-zऀ-ॿ]+)/i); if (m) return cap(m[1]); m = t.match(/^([A-Za-z][a-z]+)\s+(?:here|speaking|bol raha|bol rahi)\b/i); if (m) return cap(m[1]); return ""; }

  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  function parseFocus(t) { const out = []; const s = t.toLowerCase(); for (const c of bundle.intake?.chips || []) { const words = c.label.toLowerCase().split(/[^a-z0-9ऀ-ॿ]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w)) || s.includes(c.key.toLowerCase())) out.push(c.key); } for (const sl of library()) { const words = (sl.title + " " + topicOf(sl)).toLowerCase().split(/[^a-z0-9ऀ-ॿ]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w))) out.push(topicOf(sl)); } return [...new Set(out)].slice(0, 4); }
  function withTimeout(p, ms) { return Promise.race([p, new Promise((res) => setTimeout(() => res(null), ms))]); }

  async function runIntake() {
    const run = newRun(); S.browseOnly = false; S.playback = { phase: "intake", line: 0 }; S.intakeOpen = true; el.intake.classList.add("open"); el.inFallback.classList.add("open");
    showSlideView(heroOpen(), { reveal: 99 });
    const q1 = bundle.intake?.q1 || `What matters most to you as you consider ${bundle.product?.name || "this"}?`;
    el.inState.textContent = guide;
    const ok = await speak(q1, run, bundle.intake?.audio?.q1); if (!ok) return;
    const a1 = await intakeWait(run); if (run !== S.run) return;
    if (a1) { addMsg("user", a1); S.profile.name = parseName(a1); S.profile.why = a1; S.profile.focus = parseFocus(a1); }
    el.intake.classList.remove("open"); S.intakeOpen = false;
    const ack = a1 ? (S.profile.name ? pick([`Lovely to meet you, ${S.profile.name}.`, `Thanks, ${S.profile.name}.`]) : "Thanks for that.") + " Let me set up what we're deciding, then I'll show you the result first." : "No problem — let me set up what we're deciding, then show you the result first.";
    S.pitchPromise = (a1 && api.pitch) ? withTimeout(api.pitch({ profile: profileForServer(), refine: true }).catch(() => null), 60000) : null;
    S.playback = { phase: "opening", index: 0, line: 0 };
    const fa = a1 ? F("ack_with_context", ack) : F("ack_no_context", ack); const ok2 = await speak(fa.text, run, fa.audio); if (!ok2) return;
    const okF = await playIntroFilm(run); if (!okF) return;
    await startAfterIntake(run, a1);
  }
  async function startAfterIntake(run = newRun(), a1 = S.profile.why, checkpoint = { phase: "opening", index: 0, line: 0 }) {
    // Keep the same planning request alive across questions during the opening.
    if (!S.browseOnly && !S.pitchPromise) S.pitchPromise = api.pitch ? withTimeout(api.pitch({ profile: profileForServer(), refine: true }).catch(() => null), 60000) : Promise.resolve(null);
    if (checkpoint.phase === "opening" || checkpoint.phase === "intake") {
      if (!(await playOpening(run, checkpoint.index || 0, checkpoint.line || 0))) return;
    }
    if (S.browseOnly) { buildRoute(null); playFrom(0, 0); return; }
    let plan = S.pitch;
    if (!plan) {
      S.playback = { phase: "planning", line: 0 };
      plan = await withTimeout(S.pitchPromise, 150); if (run !== S.run) return;
      if (!plan) { if (!(await speakF("still_working", "One moment — I'm tailoring this to what you told me.", run))) return; plan = await withTimeout(S.pitchPromise, 2500); if (run !== S.run) return; }
    }
    S.personalized = !!plan;
    if (!plan) addMsg("note", "personalisation was not ready in the opening window — continuing on the stable approved route");
    if (plan) {
      S.pitch = plan; S.profile.focus = [...new Set([...(plan.focus_topics || []), ...S.profile.focus])];
      if (!["custom", "plan_bridge"].includes(checkpoint.phase) && plan.decision_frame) {
        S.playback = { phase: "decision", line: 0 };
        showSlideView(transientSlide("df", "custom", plan.decision_frame, [], null, "Your demo, tailored"), { reveal: 0 }); el.cite.textContent = "";
        if (!(await speak(plan.decision_frame, run, plan.decision_frame_audio))) return;
        S.playback = { phase: "custom", index: 0, line: 0 };
        if (!(await waitForLineQuestion({ text: plan.decision_frame }, run))) return;
      }
      if (checkpoint.phase !== "plan_bridge" && !(await playCustomBatches(plan, run, checkpoint.phase === "custom" ? checkpoint.index : 0))) return;
      S.playback = { phase: "plan_bridge", line: 0 }; el.cite.textContent = "";
      if (!(await speakF("how_i_go", "Let's look at the parts that matter to you.", run))) return;
    } else {
      S.playback = { phase: "plan_bridge", line: 0 };
      if (!(await speakF("lets_go", "Let's take a closer look.", run))) return;
    }
    buildRoute(S.pitch); playFrom(0, 0);
  }
  async function playCustomBatches(plan, run, from = 0) {
    const batches = plan?.custom_batches || [];
    if (!batches.length || S.customPlayed) return run === S.run;
    el.cite.textContent = "";
    for (let k = from; k < batches.length; k++) {
      if (run !== S.run) return false;
      const b = batches[k]; S.playback = { phase: "custom", index: k, line: 0 };
      showSlideView(transientSlide(`custom-${k + 1}`, "custom", b.text, b.fact_ids || [], b.visual, "For you"), { reveal: 0 });
      el.cite.textContent = b.fact_ids?.length ? "sources: " + b.fact_ids.join(", ") : "";
      if (!(await speak(b.text, run, b.audio))) return false;
      S.playback.index = k + 1;
      if (!(await waitForLineQuestion(b, run))) return false;
    }
    S.customPlayed = true; return run === S.run;
  }
  function skipIntake() {
    interruptAll(); el.intake.classList.remove("open"); S.intakeOpen = false; S.intakeResolver = null; S.pendingIntakeAnswer = ""; S.browseOnly = true;
    const run = newRun(); S.playback = { phase: "opening", index: 0, line: 0 }; showSlideView(heroOpen(), { reveal: 99 });
    playIntroFilm(run).then((ok) => { if (ok) startAfterIntake(run); });
  }

  // ---------- handoff ----------
  function intentScore() { let s = 20; s += Math.min(30, S.questions.length * 8); s += S.resolved.size * 8; s += S.seg >= S.plan.length - 1 ? 15 : 0; if (S.cta && S.cta !== "summary") s += 30; if (S.leads.length) s += 10; s -= S.unresolved.size * 5; return Math.max(5, Math.min(98, s)); }
  function sessionRecord() {
    const now = sessionNow();
    const visited = [...S.visited, ...(cur ? [{ slide_id: cur.slide.id, kind: cur.slide.kind, seconds: Math.round((now - cur.enteredAt) / 100) / 10 }] : [])];
    const uspsCovered = [...new Set(S.plan.slice(0, S.seg + 1).flatMap((st) => st.slide.usp_ids || []))];
    return { id: S.sessionId, ended: S.ended, profile: S.profile, customer_state: S.pitch?.customer_state, personalized: !!S.personalized, route: S.plan.map((st) => st.slide.segment_id || st.slide.id), slides: S.plan.map((st) => st.slide.id), slides_visited: visited, covered: [...S.covered], jumps: S.jumps, turns: S.turns, usps_covered: uspsCovered, questions: S.questions, escalations: S.escalations, leads: S.leads, resolved: [...S.resolved], unresolved: [...S.unresolved], cta: S.cta, intent: intentScore(), drop_point: S.plan[S.seg]?.slide.title, minutes: Math.round((now - S.started) / 6000) / 10, transcript: S.transcript };
  }
  function resumeSession() {
    if (S.endedAt === null) return;
    const idle = Date.now() - S.endedAt;
    S.started += idle; if (cur) cur.enteredAt += idle;
    S.endedAt = null; S.ended = false; el.handoff.classList.remove("open");
  }
  function showHandoff(c) {
    if (S.endedAt === null) S.endedAt = Date.now();
    S.ended = true;
    el.lead.classList.remove("open");
    const session = sessionRecord();
    const explored = [...new Set(session.slides_visited.map((visit) => slides.find((slide) => slide.id === visit.slide_id)).filter((slide) => slide && !["hero_open", "hero_close", "closing"].includes(slide.kind)).map((slide) => slide.title).filter(Boolean))];
    const openQuestions = [...S.openQuestions];
    const shared = [S.profile.why, S.profile.followup].filter(Boolean);
    const section = (title, children) => h("div", { class: "kvbox" }, h("h5", {}, title), ...children);
    el.handoffBox.replaceChildren(h("h2", {}, "Your recap"), h("p", { class: "sub" }, bundle.product?.name || bundle.name),
      h("div", { class: "grid2" },
        shared.length ? section("What matters to you", shared.map((text) => h("p", {}, text))) : null,
        section("What you explored", [explored.length ? h("ul", {}, explored.map((title) => h("li", {}, title))) : h("p", {}, "We haven't explored the details yet.")]),
        section("Questions still open", [openQuestions.length ? h("ul", {}, openQuestions.map((question) => h("li", {}, question))) : h("p", {}, S.questions.length ? "No unanswered questions noted." : "No questions raised yet.")]),
        section("Your next step", [S.leads.length ? h("p", {}, `You requested a dealership follow-up about “${S.leads.at(-1).question}”.`) : h("div", {},
          c ? h("p", {}, `You selected “${c.label}”. You can leave your details if you would like the dealership to follow up.`) : h("p", {}, "Take your time. A dealership follow-up is optional."),
          h("button", { class: "btn ghost sm", onclick: () => showLeadPrompt("requested", openQuestions[0] || S.questions.at(-1) || c?.label || "test drive") }, "Request dealership follow-up"))])),
      h("div", { class: "actions", style: "display:flex;gap:10px;margin-top:14px" },
        h("button", { class: "btn primary", onclick: () => { el.handoff.classList.remove("open"); api.saveSession(sessionRecord()).catch(() => {}); const run = newRun(); speak("Thanks for your time. You can ask anything else whenever you are ready.", run); } }, "Done"),
        h("button", { class: "btn ghost", onclick: () => { resumeSession(); const run = newRun(); speak("What else would you like to explore?", run).then((ok) => { if (ok) listenForQuestion(); }); } }, "Back to the demo")));
    el.handoff.classList.add("open"); api.saveSession(session).catch(() => {});
  }

  function toggleFullscreen() {
    if (api.onFullscreenRoute) { api.onFullscreenRoute(); return; }
    const target = root;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else (target.requestFullscreen ? target.requestFullscreen() : Promise.reject()).catch(() => {});
  }

  // ---------- intro film (skippable; the hero slide stays underneath) ----------
  async function playIntroFilm(run) {
    const iv = bundle.intro_video;
    if (!iv || !iv.url || iv.enabled === false || S.introPlayed) return run === S.run;
    S.introPlayed = true;
    const ok = await speakF("before_video", "First, here's a quick film to bring it to life. Then I'll walk you through it around what you just told me.", run);
    if (!ok) return false;
    const v = el.film; v.src = iv.url; v.muted = S.muted; v.currentTime = 0; el.stage.classList.add("film-on");
    setStatus("idle", "Playing the film"); el.cap.textContent = ""; el.cite.textContent = "";
    el.chips.replaceChildren(h("button", { class: "chip", onclick: () => { S.skipFilm = true; } }, "Skip the film"));
    const done = await new Promise((res) => {
      let fin = false, guard = null, capT = null; const end = (x) => { if (!fin) { fin = true; if (guard) clearInterval(guard); if (capT) clearTimeout(capT); res(x); } };
      v.onended = () => end(true); v.onerror = () => end(true);
      guard = setInterval(() => { if (run !== S.run || S.paused) end(false); if (S.skipFilm) { S.skipFilm = false; end(true); } }, 200);
      v.play().catch(() => end(true));
      capT = setTimeout(() => end(true), 45000);  // hard cap — an opening film is 10–20 s
    });
    if (run !== S.run) return false;
    try { v.pause(); } catch (e) {}
    v.muted = true; el.stage.classList.remove("film-on"); setChips([]);
    if (!done) return false;
    return speakF("after_video", "Now, let's get into what matters to you.", run);
  }

  // ---------- pause / stop ----------
  function togglePause() {
    if (S.paused) { resumeSession(); S.paused = false; el.pauseBtn.textContent = "⏸"; el.pauseBtn.classList.remove("on"); const resume = S.resume; S.resume = null; if (resume) resume(); return; }
    const origin = { ...S.playback }, intake = S.intakeOpen, conversation = !!S.conversationOrigin;
    interruptAll(); S.paused = true; el.pauseBtn.textContent = "▶"; el.pauseBtn.classList.add("on"); setStatus("idle", "Paused"); el.cap.textContent = "Paused — press ▶ to continue.";
    S.resume = () => { if (intake) runIntake(); else if (conversation) holdConversation(newRun()); else resumePlayback({ ...origin, checkin: false }); };
  }
  function stopDemo() { interruptAll(); S.paused = false; el.pauseBtn.textContent = "⏸"; el.pauseBtn.classList.remove("on"); el.intake.classList.remove("open"); S.intakeOpen = false; setStatus("idle", "Stopped"); el.cap.textContent = "Stopped."; S.cta = S.cta || "summary"; showHandoff(); }

  // ---------- lifecycle ----------
  function restart() { interruptAll(); S.conversationOrigin = null; S.openQuestions.clear(); S.playback = { phase: "intake", line: 0 }; S.pendingIntakeAnswer = ""; S.browseOnly = false; S.paused = false; S.resume = null; el.pauseBtn.textContent = "⏸"; el.pauseBtn.classList.remove("on"); S.customPlayed = false; S.introPlayed = false; S.skipFilm = false; S.pitchPromise = null; el.handoff.classList.remove("open"); el.lead.classList.remove("open"); S.questions.length = 0; S.transcript.length = 0; S.escalations.length = 0; S.leads.length = 0; S.visited.length = 0; S.covered.clear(); S.jumps.length = 0; S.turns.length = 0; S.lastListen = null; S.onFirstAudio = null; S.sessionId = newSessionId(); S.ended = false; S.endedAt = null; S.resolved.clear(); S.unresolved.clear(); S.raised.clear(); S.cta = null; S.pitch = null; S.plan = []; S.leadPromptShown = false; S.leadQuestion = ""; S.started = Date.now(); S.profile = { name: "", why: "", followup: "", focus: [] }; el.thread.replaceChildren(); if (cur) { cur.view.destroy(); cur = null; } el.stack.replaceChildren(); renderProgress(); runIntake(); }
  function pause() { if (!S.paused) togglePause(); }
  function context() { const st = S.plan[S.seg]; return { customer_state: S.pitch?.customer_state, route: S.plan.map((x) => x.slide.id), slide: cur?.slide?.id, segment: st?.slide.segment_id, segment_title: st?.slide.title, line_index: S.line, line_text: st?.slide.lines?.[S.line]?.text, bridge: st?.bridge, questions: S.questions.slice(-5), profile: S.profile, escalations: S.escalations.slice(-5), leads: S.leads }; }
  const onHide = () => { if (S.transcript.length && api.beacon) { try { api.beacon(sessionRecord()); } catch (e) {} } };
  window.addEventListener("pagehide", onHide);
  function destroy() { dockObserver?.disconnect(); window.removeEventListener("pagehide", onHide); interruptAll(); for (const media of S.preloads) { try { media.removeAttribute("src"); media.load(); } catch (e) {} } S.preloads.length = 0; if (cur) cur.view.destroy(); root.remove(); }

  renderCtas();
  updateMuteUi();
  showSlideView(heroOpen(), { reveal: 99 });
  const startBtn = h("div", { class: "pl-intake pl-welcome open" }, h("div", { class: "inner" }, h("div", { class: "state" }, "YOUR VIRTUAL SHOWROOM"), h("h1", {}, bundle.product?.name || bundle.name), h("p", {}, "Take a closer look. Ask what matters to you."), h("div", { class: "actions" }, h("button", { class: "btn primary", onclick: () => { startBtn.remove(); runIntake(); } }, "Explore with me"), h("button", { class: "btn ghost", onclick: () => { startBtn.remove(); skipIntake(); } }, "Browse at my pace"))));
  el.stage.append(startBtn);
  // language chooser (multi-language bundles)
  const alts = bundle.alt_languages ? Object.keys(bundle.alt_languages) : [];
  if (alts.length) {
    const NAMES = { "en-IN": "English", "hinglish": "Hinglish", "hi-IN": "हिंदी", "ta-IN": "தமிழ்", "te-IN": "తెలుగు", "kn-IN": "ಕನ್ನಡ", "mr-IN": "मराठी", "bn-IN": "বাংলা", "gu-IN": "ગુજરાતી", "ml-IN": "മലയാളം", "pa-IN": "ਪੰਜਾਬੀ" };
    const row = h("div", { class: "pl-langs" }, h("button", { class: "chip primary" }, NAMES[bundle.language] || bundle.language), ...alts.map((code) => h("button", { class: "chip", onclick: (e) => { applyLanguage(code); row.querySelectorAll(".chip").forEach((c) => c.classList.remove("primary")); e.currentTarget.classList.add("primary"); } }, NAMES[code] || code)));
    startBtn.querySelector(".inner").insertBefore(row, startBtn.querySelector(".actions"));
  }
  function applyLanguage(code) {
    const alt = bundle.alt_languages?.[code]; if (!alt) return;
    bundle.segments = alt.segments; bundle.closing = alt.closing; bundle.intake = alt.intake; bundle.language = code; bundle.voice = { ...bundle.voice, provider: alt.voice_provider || bundle.voice.provider }; bundle.slides = alt.slides || bundle.slides;
    slides = slidesOf(bundle); S.lang = code;
    if (cur) { cur.view.destroy(); cur = null; } showSlideView(heroOpen(), { reveal: 99 });
  }
  return { destroy, restart, pause, context };
}
