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

export function mountPlayer(host, bundle, api) {
  const mutedByDefault = ["1", "true", "on"].includes(new URLSearchParams(window.location.search).get("mute"));
  const S = { run: 0, plan: [], seg: 0, line: 0, atCheckin: false, waiter: null, waitChips: [], timer: null, intakeResolver: null, pendingIntakeAnswer: "", intakeOpen: false,
    profile: { name: "", why: "", followup: "", focus: [] }, pitch: null, questions: [], transcript: [], escalations: [], leads: [], resolved: new Set(), unresolved: new Set(), raised: new Set(),
    cta: null, started: Date.now(), micOn: false, micDenied: false, rec: null, audio: null, utterance: null, muted: mutedByDefault, preloads: [], ttsToken: 0, ttsCache: new Map(), bt: { voice: null },
    leadPromptShown: false, leadQuestion: "", leadReason: "", speaking: null, visited: [], covered: new Set(), jumps: [] };
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
          h("div", { class: "pl-mic-row" }, el.hint = h("div", { class: "pl-hint" }, (serverSTT || SR) ? "Tap to talk — I'll stop and listen." : "Voice input needs Chrome or Safari — use 💬 to type."), el.mic = h("button", { class: "mic", onclick: () => micTap() }, "🎤")))),
      el.intake = h("div", { class: "pl-intake" }, h("div", { class: "inner" }, el.orb = h("div", { class: "orb-slot" }, (el.mascotIntake = mascot({ size: 132, image: bundle.mascot })).el), el.inState = h("div", { class: "state" }, guide), el.inQ = h("p", { class: "q" }), el.inHeard = h("div", { class: "heard" }),
        el.inFallback = h("form", { class: "fallback", onsubmit: (e) => { e.preventDefault(); const t = el.inText.value.trim(); if (t) { el.inText.value = ""; acceptTypedAnswer(t); } } }, el.inText = h("input", { placeholder: "Type your answer…" }), h("button", { class: "btn primary sm", type: "submit" }, "Send")),
        h("div", { class: "actions" }, el.inMic = h("button", { class: "mic", onclick: () => intakeMic() }, "🎤"), h("button", { class: "btn ghost", onclick: () => skipIntake() }, "Skip, start the demo")))),
      el.handoff = h("div", { class: "pl-handoff" }, el.handoffBox = h("div", { class: "box" })),
      el.lead = h("div", { class: "pl-lead" }, h("div", { class: "lead-card" }, h("button", { class: "lead-close", title: "Not now", onclick: () => el.lead.classList.remove("open") }, "×"), h("div", { class: "eyebrow" }, "Optional · dealership follow-up"), h("h3", {}, "Would you like to try it in person?"), el.leadCopy = h("p", {}, "Share your details and the dealership can arrange a test drive."), el.leadForm = h("form", { onsubmit: (e) => { e.preventDefault(); saveLeadForm(); } }, el.leadName = h("input", { placeholder: "Your name", autocomplete: "name" }), el.leadPhone = h("input", { placeholder: "10-digit mobile number", inputmode: "tel", autocomplete: "tel" }), el.leadError = h("div", { class: "lead-error" }), h("button", { class: "btn primary", type: "submit" }, "Arrange a test drive")), h("button", { class: "btn ghost sm", onclick: () => el.lead.classList.remove("open") }, "Not now")))),
    el.drawer = h("div", { class: "pl-drawer" }, h("div", { class: "head" }, h("span", {}, "Conversation"), h("button", { class: "icon-btn", onclick: () => toggleDrawer(false) }, "✕")), el.thread = h("div", { class: "body" }),
      h("form", { class: "composer", onsubmit: (e) => { e.preventDefault(); const t = el.q.value.trim(); if (t) { el.q.value = ""; acceptTypedAnswer(t); } } }, el.q = h("input", { placeholder: "Type a question…" }), h("button", { class: "btn primary sm", type: "submit" }, "↑"))));
  host.replaceChildren(root);

  // ---------- helpers ----------
  function setStatus(kind, txt) { el.status.className = "pl-status " + kind; el.statusTxt.textContent = txt; el.avatar.classList.toggle("speaking", kind === "speaking"); el.avatar.classList.toggle("listening", kind === "listening"); const ms = kind === "speaking" ? "speaking" : kind === "listening" ? "listening" : kind === "thinking" ? "thinking" : "idle"; [el.mascotTop, el.mascotIntake, el.mascotStage].forEach((m) => m && m.set(ms)); }
  function addMsg(role, text, extra = {}) { const d = h("div", { class: "m " + role + (extra.interrupted ? " interrupted" : "") }, text, extra.interrupted ? h("span", { class: "cut", title: "cut off here" }, " —") : null); el.thread.append(d); el.thread.scrollTop = el.thread.scrollHeight; if (role !== "note") S.transcript.push({ role, text, t: Date.now(), ...extra }); if (role === "agent" && !el.drawer.classList.contains("open")) el.chatBtn.classList.add("unread"); }
  function acceptTypedAnswer(text) {
    if (S.intakeOpen) { if (S.intakeResolver) S.intakeResolver(text); else { S.pendingIntakeAnswer = text; el.inHeard.textContent = text; } return; }
    if (S.waiter) { addMsg("user", text); resolveWait(interpretReply(text, S.waitChips)); return; }
    handleQuestion(text);
  }
  function toggleDrawer(force) { const on = force === undefined ? !el.drawer.classList.contains("open") : force; el.drawer.classList.toggle("open", on); if (on) { el.chatBtn.classList.remove("unread"); setTimeout(() => el.q.focus(), 80); } }
  function updateMuteUi() { el.muteBtn.textContent = S.muted ? "🔇" : "🔊"; el.muteBtn.title = S.muted ? "Unmute audio" : "Mute audio"; el.muteBtn.setAttribute("aria-label", el.muteBtn.title); el.muteBtn.setAttribute("aria-pressed", String(S.muted)); el.muteBtn.classList.toggle("on", S.muted); }
  function toggleMute() { S.muted = !S.muted; if (S.audio) S.audio.muted = S.muted; if (S.utterance) S.utterance.volume = S.muted ? 0 : 1; el.film.muted = S.muted || !el.stage.classList.contains("film-on"); updateMuteUi(); }
  function setChips(list) { el.chips.replaceChildren(...list.map((c) => h("button", { class: "chip" + (c.primary ? " primary" : ""), onclick: () => resolveWait(c.value) }, c.label))); }
  function clearTimer() { if (S.timer) { clearInterval(S.timer); S.timer = null; } el.timer.replaceChildren(); }
  function newRun() { return ++S.run; }
  function renderProgress() { el.progress.replaceChildren(...S.plan.map((st, i) => h("button", { class: "pp" + (i < S.seg ? " done" : i === S.seg ? " active" : ""), title: st.slide.kind, onclick: () => { interruptAll(); playFrom(i, 0); } }, st.slide.title))); }
  function renderCtas() { const ctas = (bundle.ctas || []).filter((c) => c.when === "always" || !c.when); el.ctas.replaceChildren(...ctas.map((c) => h("button", { class: "chip cta" + (c.primary ? " primary" : ""), onclick: () => { interruptAll(); ctaFlow(c.id, newRun()); } }, c.label))); }

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
  function noteVisit(c) { if (!c) return; S.visited.push({ slide_id: c.slide.id, kind: c.slide.kind, seconds: Math.round((Date.now() - c.enteredAt) / 100) / 10 }); }
  function preloadAfter(slide) {  // the next slide's picture and audio are fetched while this one plays
    const i = S.plan.findIndex((st) => st.slide.id === slide.id); const next = i >= 0 ? S.plan[i + 1]?.slide : null; if (!next) return;
    if (next.image_url) { const im = new Image(); im.decoding = "async"; im.src = next.image_url; S.preloads.push(im); }
    for (const l of [...(next.lines || []), next.checkin?.audio ? { audio: next.checkin.audio } : null].filter(Boolean)) if (l.audio) { const a = new Audio(l.audio); a.preload = "auto"; a.load(); S.preloads.push(a); }
  }
  // A line spoken outside the deck (decision frame, custom batch, an answer) gets a transient slide: the picture it names,
  // else the current one, with its cited facts as panel callouts.
  function transientSlide(id, kind, text, factIds, visual, title = "") {
    const facts = (bundle.facts || []).filter((f) => (factIds || []).includes(f.id));
    return { id, kind, title, topics: [], image_url: (visual && mediaUrlFor(visual)) || cur?.slide?.image_url || heroOpen().image_url || null, image_parts: [], motion: "none",
      callouts: facts.slice(0, 3).map((f, k) => ({ id: `${id}-c${k + 1}`, text: compact(`${f.claim}: ${f.value}`, 8), fact_ids: [f.id], placement: "panel", anchor: null, label_pos: null, reveal_on_line: 0 })),
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
  function captionOnly(text, run) { return new Promise((res) => { const my = ++S.ttsToken; const words = wordsOf(text); const ms = Math.max(1200, words / 2.5 * 1000); const sp = { text, words, audio: null, startedAt: Date.now(), estMs: ms }; S.speaking = sp; const t = setTimeout(() => { if (S.speaking === sp) { logHeard(sp, true); S.speaking = null; } res(my === S.ttsToken && run === S.run); }, ms); S.captionTimer = t; }); }
  function speakBrowser(text) {
    return new Promise((res) => { const my = ++S.ttsToken; const u = new SpeechSynthesisUtterance(text); S.utterance = u; const v = browserVoice(); if (v) u.voice = v; u.lang = LANG; u.rate = 0.98; u.pitch = 1.05; u.volume = S.muted ? 0 : 1; const sp = { text, words: wordsOf(text), audio: null, startedAt: Date.now(), estMs: Math.max(1500, text.length * 75) }; S.speaking = sp; let done = false; const fin = () => { if (done) return; done = true; if (S.utterance === u) S.utterance = null; if (S.speaking === sp) { logHeard(sp, true); S.speaking = null; } res(my === S.ttsToken); }; const t = setTimeout(fin, sp.estMs + 4000); u.onend = () => { clearTimeout(t); fin(); }; u.onerror = () => { clearTimeout(t); fin(); }; try { speechSynthesis.speak(u); } catch (e) { fin(); } });
  }
  async function audioUrlFor(text, preset) { if (preset) return preset; if (!useServerVoice) return null; if (S.ttsCache.has(text)) return S.ttsCache.get(text); const p = api.tts(text).catch(() => null); S.ttsCache.set(text, p); return p; }
  function prefetch(items) { if (!useServerVoice) return; for (const it of items) if (it && !it.audio && it.text) audioUrlFor(it.text); }
  async function speak(text, run, preset) {
    if (run !== S.run || !text) return run === S.run;
    el.cap.textContent = text; if (S.intakeOpen) el.inQ.textContent = text; setStatus("speaking", "Speaking");
    let url = null; try { url = await audioUrlFor(text, preset); } catch (e) {}
    if (run !== S.run) return false;
    let ok;
    if (url) ok = await new Promise((res) => { const my = ++S.ttsToken; const a = new Audio(url); a.muted = S.muted; S.audio = a; const sp = { text, words: wordsOf(text), audio: a, startedAt: Date.now(), estMs: wordsOf(text) / 2.5 * 1000 }; S.speaking = sp; let done = false; const fin = () => { if (done) return; done = true; if (S.speaking === sp) { logHeard(sp, true); S.speaking = null; } res(my === S.ttsToken); }; const safeFallback = () => { if (done) return; done = true; if (S.speaking === sp) S.speaking = null; (useServerVoice ? captionOnly(text, run) : speakBrowser(text)).then(res); }; a.onended = fin; a.onerror = safeFallback; a.play().catch(safeFallback); });
    else ok = useServerVoice ? await captionOnly(text, run) : await speakBrowser(text);
    if (ok && run === S.run) setStatus("idle", "Ready");
    return ok && run === S.run;
  }
  function cancelSpeech() { S.ttsToken++; if (S.speaking) { logHeard(S.speaking, false); S.speaking = null; } if (S.captionTimer) { clearTimeout(S.captionTimer); S.captionTimer = null; } try { speechSynthesis.cancel(); } catch (e) {} S.utterance = null; if (S.audio) { try { S.audio.pause(); } catch (e) {} S.audio = null; } }

  // ---------- voice in ----------
  function encodeWav(chunks, inRate, outRate = 16000) {
    const total = chunks.reduce((n, c) => n + c.length, 0); const all = new Float32Array(total); let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
    const ratio = inRate / outRate, outLen = Math.floor(all.length / ratio), pcm = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) { const s0 = Math.floor(i * ratio), s1 = Math.min(all.length, Math.floor((i + 1) * ratio)); let sum = 0; for (let j = s0; j < s1; j++) sum += all[j]; const v = Math.max(-1, Math.min(1, sum / Math.max(1, s1 - s0))); pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff; }
    const buf = new ArrayBuffer(44 + pcm.length * 2), dv = new DataView(buf); const w = (p, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(p + i, s.charCodeAt(i)); };
    w(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, outRate, true); dv.setUint32(28, outRate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, "data"); dv.setUint32(40, pcm.length * 2, true);
    new Int16Array(buf, 44).set(pcm); return new Blob([buf], { type: "audio/wav" });
  }
  // Server STT (Sarvam Saarika): capture PCM, stop ~1.3 s after the customer stops talking, transcribe on the server.
  async function listenServer({ timeout = 9000, onInterim = () => {} } = {}) {
    let stream; try { stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }); } catch (e) { S.micDenied = true; return ""; }
    const Ctx = window.AudioContext || window.webkitAudioContext; const ctx = new Ctx(); const src = ctx.createMediaStreamSource(stream); const proc = ctx.createScriptProcessor(4096, 1, 1);
    const chunks = []; let spoke = false, lastVoice = Date.now(), t0 = Date.now(), done = false;
    S.micOn = true; setMicUI(true); onInterim("listening…");
    return new Promise((res) => {
      const finish = async () => { if (done) return; done = true; S.stopServerListen = null; try { proc.disconnect(); src.disconnect(); stream.getTracks().forEach((t) => t.stop()); await ctx.close(); } catch (e) {} S.micOn = false; setMicUI(false);
        if (!spoke || !chunks.length) { res(""); return; }
        setStatus("thinking", "Transcribing"); onInterim("…");
        try { const t = await api.stt(encodeWav(chunks, ctx.sampleRate), LANG); res((t || "").trim()); } catch (e) { if (SR) { serverSTT = false; addMsg("note", "Server listening is unavailable — using the browser's speech recognition."); } res(""); } };
      S.stopServerListen = finish;
      proc.onaudioprocess = (e) => { const d = e.inputBuffer.getChannelData(0); chunks.push(new Float32Array(d)); let sum = 0; for (let i = 0; i < d.length; i++) sum += d[i] * d[i]; const rms = Math.sqrt(sum / d.length); const now = Date.now(); if (rms > 0.012) { spoke = true; lastVoice = now; } if ((spoke && now - lastVoice > 1300) || now - t0 > timeout || (!spoke && now - t0 > Math.min(timeout, 7000))) finish(); };
      src.connect(proc); proc.connect(ctx.destination);
    });
  }
  function listen(opts = {}) { if (serverSTT && !S.micDenied && navigator.mediaDevices?.getUserMedia) return listenServer(opts); return listenBrowser(opts); }
  function listenBrowser({ timeout = 9000, onInterim = () => {} } = {}) {
    return new Promise((res) => {
      if (!SR || S.micDenied) { res(""); return; }
      try { if (S.rec) S.rec.abort(); } catch (e) {}
      const rec = new SR(); S.rec = rec; rec.lang = LANG; rec.interimResults = true; rec.continuous = false;
      let fin = "", interim = "", ended = false; S.micOn = true; setMicUI(true);
      const end = () => { if (ended) return; ended = true; S.micOn = false; setMicUI(false); clearTimeout(t); res((fin || interim).trim()); };
      rec.onresult = (e) => { interim = ""; fin = ""; for (const r of e.results) { if (r.isFinal) fin += r[0].transcript; else interim += r[0].transcript; } onInterim((fin || interim).trim()); };
      rec.onerror = (e) => { if (e.error === "not-allowed" || e.error === "service-not-allowed") S.micDenied = true; end(); };
      rec.onend = end; const t = setTimeout(() => { try { rec.stop(); } catch (e) {} }, timeout);
      try { rec.start(); } catch (e) { end(); }
    });
  }
  function stopListening() { try { if (S.rec) S.rec.abort(); } catch (e) {} if (S.stopServerListen) { try { S.stopServerListen(); } catch (e) {} } S.micOn = false; setMicUI(false); }
  function setMicUI(on) { el.mic.classList.toggle("on", on); el.inMic.classList.toggle("on", on); if (on) { setStatus("listening", "Listening"); el.hint.textContent = serverSTT ? "Listening (Sarvam)… just talk." : "Listening… just talk."; } else { el.live.textContent = ""; if (el.status.classList.contains("listening")) setStatus("idle", "Your turn"); el.hint.textContent = (serverSTT || SR) ? "Tap to talk — I'll stop and listen." : "Use 💬 to type."; } }

  // ---------- flow primitives ----------
  function interruptAll() { cancelSpeech(); stopListening(); newRun(); clearTimer(); if (S.waiter) { const w = S.waiter; S.waiter = null; S.waitChips = []; w({ value: "__interrupted" }); } setChips([]); }
  function interpretReply(t, chips) {
    const s = t.toLowerCase().trim(), has = (v) => chips.some((c) => c.value === v), short = s.split(/\s+/).length <= 7;
    if (has("callme") && PHONE.test(s.replace(/\s|-/g, ""))) return { value: "phone", text: t };
    if (has("callme") && /(call me|yes|haan|please|sure|ok)/.test(s) && short) return { value: "callme" };
    if (short && /^(yes|yeah|yep|ya\b|haan|ok|okay|sure|fine|good|great|perfect|continue|carry on|go on|go ahead|next|move on|proceed|that helps|clear|settled|got it|understood|thanks|thank you|alright|cool|makes sense|theek|thik|achha|accha)/.test(s)) return { value: has("yes") ? "yes" : "continue" };
    if (short && /^(no\b|nope|not really|not quite|still|unsure|not sure|tell me more|more\b|deeper|explain|elaborate|not clear|i'm not sure|nahi|nahin)/.test(s)) return { value: has("deeper") ? "deeper" : has("no") ? "no" : has("continue") ? "continue" : "deeper" };
    for (const c of bundle.ctas || []) if (s.includes(c.label.toLowerCase()) && has("cta:" + c.id)) return { value: "cta:" + c.id };
    if (/(not yet|later|think about|not now|baad mein)/.test(s) && has("notyet")) return { value: "notyet" };
    if (/(human|person|advisor|someone|sales|team)/.test(s) && has("human")) return { value: "human" };
    return { value: "question", text: t };
  }
  function waitFor(chips, seconds, opts = {}) {
    return new Promise((res) => {
      S.waiter = res; S.waitChips = chips; setChips(chips); setStatus("idle", "Your turn");
      if (seconds > 0) { const t0 = Date.now(), total = seconds * 1000; el.timer.replaceChildren(h("div", { class: "r" }), h("span", {}, "I'll carry on in ", h("b", { id: "plTleft" }, seconds), "s unless you stop me"));
        S.timer = setInterval(() => { if (document.activeElement === el.q || S.micOn) return; const e = Date.now() - t0; const r = el.timer.querySelector(".r"); if (r) r.style.setProperty("--p", Math.min(100, e / total * 100) + "%"); const tl = el.timer.querySelector("#plTleft"); if (tl) tl.textContent = Math.max(0, Math.ceil((total - e) / 1000)); if (e >= total) resolveWait("__timeout"); }, 200); }
      if (opts.listen !== false && canListen() && !S.micDenied) listen({ timeout: opts.listenSecs || 8000, onInterim: (t) => { el.live.textContent = t; } }).then((t) => { if (!S.waiter) return; if (t) { addMsg("user", t); resolveWait(interpretReply(t, chips)); } else el.hint.textContent = "Tap the mic to talk, or tap a chip."; });
    });
  }
  function resolveWait(v) { clearTimer(); stopListening(); if (S.waiter) { const w = S.waiter; S.waiter = null; S.waitChips = []; setChips([]); w(typeof v === "string" ? { value: v } : v); } }
  async function askAndListen(question, run, secs = 10000, preset = null) { const ok = await speak(question, run, preset); if (!ok) return null; const t = await listen({ timeout: secs, onInterim: (x) => { el.live.textContent = x; } }); if (run !== S.run) return null; if (t) addMsg("user", t); return t; }

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
  async function playLines(sl, run, view, from = 0, upto = sl.lines.length) {  // reveal a line's callouts as it starts; the audio ending is the only clock
    for (let j = from; j < upto; j++) { S.line = j; if (run !== S.run) return false; const ln = sl.lines[j]; view.setRevealed(j); el.cite.textContent = ln.fact_ids?.length ? "sources: " + ln.fact_ids.join(", ") : ""; const ok = await speak(ln.text, run, ln.audio); if (!ok) return false; S.line = j + 1; }
    return run === S.run;
  }
  async function playOpening(run) {
    for (const sl of opening()) { prefetch(sl.lines); const view = showSlideView(sl, { reveal: -1 }); if (!(await playLines(sl, run, view))) return false; }
    return run === S.run;
  }
  async function playFrom(idx, lineIdx = 0) {
    const run = newRun();
    for (let i = idx; i < S.plan.length; i++) {
      const step = S.plan[i], sl = step.slide; S.seg = i; S.atCheckin = false; renderProgress();
      prefetch([...sl.lines.slice(lineIdx), sl.checkin?.text ? { text: sl.checkin.text, audio: sl.checkin.audio } : null].filter(Boolean));
      const short = lineIdx === 0 && S.covered.has(sl.id) && sl.lines.length > 1;  // seen during a question: title + first line, no check-in
      const view = showSlideView(sl, { reveal: short ? 99 : lineIdx - 1 });
      if (lineIdx === 0 && step.bridge) { el.cite.textContent = step.bridge_fact_ids?.length ? "sources: " + step.bridge_fact_ids.join(", ") : ""; const okb = await speak(step.bridge, run, step.bridge_audio); if (!okb) return; }
      if (!(await playLines(sl, run, view, lineIdx, short ? 1 : sl.lines.length))) return;
      lineIdx = 0; if (run !== S.run) return;
      const topic = topicOf(sl);
      if (sl.checkin?.text && !short) {
        S.atCheckin = true; const ok = await speak(sl.checkin.text, run, sl.checkin.audio); if (!ok) return;
        const conc = !!sl.priority || S.profile.focus.includes(topic);
        const chips = conc ? [{ label: "That settles it", value: "yes", primary: true }, { label: "Still unsure", value: "deeper" }, { label: "I have a question", value: "question" }] : [{ label: "Continue", value: "continue", primary: true }, { label: "Tell me more", value: "deeper" }, { label: "I have a question", value: "question" }];
        const r = await waitFor(chips, 8); if (run !== S.run) return;
        if (r.value === "yes") { S.resolved.add(topic); const ok2 = await speakF("good", "Good — moving on.", run); if (!ok2) return; }
        else if (r.value === "__timeout") { const ok2 = await speakF("nudge_continue", "I'll carry on — stop me whenever you like.", run); if (!ok2) return; }
        else if (r.value === "deeper") { S.raised.add(topic); prefetch(sl.deeper || []); view.setRevealed(99); for (const ln of sl.deeper || []) { const ok2 = await speak(ln.text, run, ln.audio); if (!ok2) return; }
          if (!(sl.deeper || []).length) { const ok3 = await speak("That's everything the material covers on this — ask me anything specific and I'll check.", run); if (!ok3) return; }
          const ok3 = await speakF("clearer", "Is that clearer?", run); if (!ok3) return;
          const r2 = await waitFor([{ label: "Yes, continue", value: "yes", primary: true }, { label: "Not really", value: "no" }, { label: "Question", value: "question" }], 15); if (run !== S.run) return;
          if (r2.value === "yes") S.resolved.add(topic); else if (r2.value === "no") { S.unresolved.add(topic); S.escalations.push(`${topic} — still unsure after the deeper explanation`); const ok4 = await speak(`Then let's not paper over it — I've flagged ${topic} for someone from the team to take up with you properly. Let me carry on for now.`, run); if (!ok4) return; }
          else if (r2.value === "question") { if (r2.text) handleQuestion(r2.text); else listenForQuestion(); return; } else if (r2.value === "__interrupted") return; }
        else if (r.value === "question") { if (r.text) handleQuestion(r.text); else listenForQuestion(); return; }
        else if (r.value === "__interrupted") return;
      }
      maybePromptLead("progress");
    }
    await closeFlow(run);
  }

  async function closeFlow(run) {
    S.atCheckin = true;
    const cs = closingSlide();
    if (cs) {
      const view = showSlideView(cs, { reveal: -1 }); const lines = cs.lines || [];
      if (S.pitch?.advance) { view.setRevealed(0); const ok = await speak(S.pitch.advance, run, S.pitch.advance_audio); if (!ok) return; if (!(await playLines(cs, run, view, 1))) return; }
      else if (!(await playLines(cs, run, view))) return;
    }
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
  async function listenForQuestion() {
    const wasAt = S.atCheckin; interruptAll(); const run = newRun(); el.cap.textContent = "Go ahead — I'm listening."; setStatus("listening", "Listening");
    const t = await listen({ timeout: 10000, onInterim: (x) => { el.live.textContent = x; } }); if (run !== S.run) return;
    if (t) handleQuestion(t); else { const ok = await speak("I didn't catch that. Tap the mic and try again, or use the chat to type.", run); if (!ok) return; const r = await waitFor([{ label: "Continue", value: "continue", primary: true }], 15); if (run !== S.run) return; if (r.value === "question" && r.text) handleQuestion(r.text); else resumeAfterQA(wasAt); }
  }
  function micTap() { if (S.micOn) { stopListening(); return; } if (S.intakeOpen) { intakeMic(); return; } listenForQuestion(); }

  // ---------- questions, don't-guess, lead capture ----------
  async function handleQuestion(text) {
    const wasAtCheckin = S.atCheckin; interruptAll(); const run = newRun(); let jumped = null;
    const last = S.transcript.at(-1); if (!(last?.role === "user" && last.text === text)) addMsg("user", text);  // a chip-wait reply is already logged
    S.questions.push(text); el.live.textContent = ""; setStatus("thinking", "Thinking"); el.cap.textContent = "…";
    let r;
    const qaP = api.qa({ question: text, history: S.transcript.slice(-8).map((t) => ({ role: t.role, text: t.text })), profile: profileForServer(), slide_id: cur?.slide?.id || null });
    try { r = await withTimeout(qaP, 700); if (!r) { const okH = await speakF("hold_on_question", "Good question — give me one moment, please, while I check that for you.", run); if (!okH) return; r = await qaP; } }
    catch (e) { if (run !== S.run) return; const ok = await speak("I couldn't reach my notes just now — give me a second and ask again, or I'll flag it for the team.", run); if (!ok) return; S.escalations.push(`error answering: "${text}"`); resumeAfterQA(wasAtCheckin, !!jumped); return; }
    if (run !== S.run) return;
    if (!r.answered) {
      if (r.escalate) S.escalations.push(r.escalate);
      if (r.topic && r.topic !== "other") S.raised.add(r.topic);
      S.unresolved.add(r.topic || "question"); el.cite.textContent = "";
      const unknown = "I don't know from the information I have. Share your details here and someone from the dealership can help you with that.";
      const okUnknown = await speak(unknown, run); if (!okUnknown) return;
      showLeadPrompt("unknown", text);
      resumeAfterQA(wasAtCheckin, !!jumped);
      return;
    }
    // stay: this slide, every callout shown, the matching one lit · jump: cross-fade to the slide that carries the facts
    // (marked covered) · none: answer here. The return point (S.seg / S.line) is untouched either way.
    const from = cur?.slide?.id || null;
    jumped = r.route === "jump" && r.slide_id && r.slide_id !== from ? slides.find((s) => s.id === r.slide_id) || null : null;
    if (jumped) { showSlideView(jumped, { reveal: 99 }); S.covered.add(jumped.id); S.jumps.push({ from, to: jumped.id, question: text }); } else cur?.view.setRevealed(99);
    if (r.callout_id) cur?.view.highlight(r.callout_id);
    el.cite.textContent = r.fact_ids?.length ? "sources: " + r.fact_ids.join(", ") : "";
    if (r.escalate) S.escalations.push(r.escalate); if (r.topic && r.topic !== "other") S.raised.add(r.topic);
    if (r.from_bank) addMsg("note", "answered from the FAQ bank — no model call");
    const ok = await speak(r.answer, run, r.audio); if (!ok) return;
    if (r.cta) { await ctaFlow(r.cta, run); return; }
    if (r.offer_callback) showLeadPrompt("question", text);
    maybePromptLead("questions");
    if (r.clarifying_question) { const a = await askAndListen(r.clarifying_question, run, 10000); if (run !== S.run) return; if (a) { handleQuestion(a); return; } }
    const ok2 = await speakF("did_that_answer", "Did that answer it?", run); if (!ok2) return;
    const r2 = await waitFor([{ label: "Yes, that helps", value: "yes", primary: true }, { label: "Not quite", value: "no" }], 20); if (run !== S.run) return;
    if (r2.value === "yes") { S.resolved.add(r.topic || "question"); const ok3 = await speakF("glad", "Glad that helps.", run); if (!ok3) return; maybePromptLead("questions"); resumeAfterQA(wasAtCheckin, !!jumped); }
    else if (r2.value === "no") { S.unresolved.add(r.topic || "question"); S.escalations.push(`not satisfied: "${text}"`); const ok3 = await speak("I don't want to leave that half-answered. I've opened a short form so someone from the dealership can help you properly.", run); if (!ok3) return; showLeadPrompt("question", text); resumeAfterQA(wasAtCheckin, !!jumped); }
    else if (r2.value === "question" && r2.text) handleQuestion(r2.text);
    else resumeAfterQA(wasAtCheckin, !!jumped);
  }
  function showLeadPrompt(reason, question = "") {
    if (S.leads.length || (S.leadPromptShown && reason !== "unknown")) return;
    S.leadPromptShown = true; S.leadReason = reason; S.leadQuestion = question || "test drive";
    el.leadName.value = S.profile.name || ""; el.leadPhone.value = ""; el.leadError.textContent = "";
    el.leadCopy.textContent = reason === "unknown" ? "I don't have that answer in the approved sources. Leave your details and the dealership can answer it directly." : "You have seen enough to make a drive useful. Share your details and the dealership can arrange it.";
    el.lead.classList.add("open");
  }
  function maybePromptLead(reason) { const progress = S.plan.length ? (S.seg + 1) / S.plan.length : 0; if (S.questions.length >= 2 || progress >= 0.6) showLeadPrompt(reason, S.questions.at(-1) || "test drive"); }
  async function saveLeadForm() {
    const name = el.leadName.value.trim(); const raw = el.leadPhone.value.replace(/[\s-]/g, ""); const m = raw.match(PHONE);
    if (!m) { el.leadError.textContent = "Enter a valid 10-digit Indian mobile number."; el.leadPhone.focus(); return; }
    const btn = el.leadForm.querySelector("button[type=submit]"); btn.disabled = true; el.leadError.textContent = "Saving…";
    let ok = true; try { await api.lead({ phone: m[1], question: S.leadQuestion || "test drive", profile: { ...profileForServer(), name: name || S.profile.name } }); } catch (e) { ok = false; }
    btn.disabled = false;
    if (!ok) { el.leadError.textContent = "Couldn't save that just now. Please try once more."; return; }
    if (name) S.profile.name = name; S.leads.push({ phone: m[1], question: S.leadQuestion || "test drive" }); S.escalations.push(`callback requested on ${m[1]}: "${S.leadQuestion || "test drive"}"`);
    el.lead.classList.remove("open"); addMsg("note", "Test-drive request saved for the dealership");
  }
  function profileForServer() { return { name: S.profile.name, why: S.profile.why, followup: S.profile.followup, focus: S.profile.focus, customer_state: S.pitch?.customer_state, language: bundle.language }; }
  const _origTts = api.tts; api.tts = (text) => _origTts ? api.tts_lang ? api.tts_lang(text, bundle.language) : _origTts(text) : Promise.resolve(null);
  function mediaUrlFor(v) { if (!v) return null; for (const im of bundle.media?.images || []) if (im.id === v.ref) return im.url; const src = v.source_id; for (const vid of bundle.media?.videos || []) if (v.kind === "shot" && src && vid.url.includes(src)) return null; return null; }
  function resumeAfterQA(wasAtCheckin, jumped = false) {
    if (cur) cur.view.highlight(null);
    if (!S.plan.length) { const run = newRun(); speakF("back_to_demo", "Let's get back to where we were.", run).then((ok) => { if (ok) startAfterIntake(); }); return; }
    if (S.seg >= S.plan.length) { closeFlow(newRun()); return; }
    if (wasAtCheckin && !jumped) { playFrom(S.seg + 1, 0); return; }
    const run = newRun(); speakF("back_to_demo", "Back to where we were.", run).then((ok) => { if (ok) playFrom(wasAtCheckin ? S.seg + 1 : S.seg, wasAtCheckin ? 0 : S.line); });  // the exact interrupted line
  }

  // ---------- intake + standard opening + pitch plan ----------
  function intakeWait(run) {
    return new Promise((res) => {
      let done = false; const fin = (t) => { if (done) return; done = true; S.intakeResolver = null; stopListening(); res(t); }; S.intakeResolver = fin; el.inHeard.textContent = "";
      if (S.pendingIntakeAnswer) { const queued = S.pendingIntakeAnswer; S.pendingIntakeAnswer = ""; fin(queued); return; }
      if (canListen() && !S.micDenied) { el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; listen({ timeout: 10000, onInterim: (t) => { el.inHeard.textContent = t; } }).then((t) => { if (done || run !== S.run) return; if (t) fin(t); else { el.inState.textContent = "Tap the mic to try again, or type below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); } }); }
      else { el.inState.textContent = "Type your answer below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); }
    });
  }
  async function intakeMic() { if (S.micOn) { stopListening(); return; } if (!S.intakeResolver) return; cancelSpeech(); const fin = S.intakeResolver; el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; const t = await listen({ timeout: 10000, onInterim: (x) => { el.inHeard.textContent = x; } }); if (t && S.intakeResolver === fin) fin(t); else if (S.intakeResolver === fin) { el.inState.textContent = "Tap the mic to try again, or type below"; el.inFallback.classList.add("open"); } }
  function parseName(t) { let m = t.match(/(?:my name is|i am|i'm|this is|myself|name's|call me|mera naam|naam)\s+([A-Za-zऀ-ॿ][a-zऀ-ॿ]+)/i); if (m) return cap(m[1]); m = t.match(/^([A-Za-z][a-z]+)\s+(?:here|speaking|bol raha|bol rahi)\b/i); if (m) return cap(m[1]); const w = t.trim().split(/\s+/); if (w.length <= 2 && /^[A-Za-z]+$/.test(w[0]) && !/^(hi|hello|hey|yes|no|ok|okay|namaste)$/i.test(w[0])) return cap(w[0]); return ""; }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  function parseFocus(t) { const out = []; const s = t.toLowerCase(); for (const c of bundle.intake?.chips || []) { const words = c.label.toLowerCase().split(/[^a-z0-9ऀ-ॿ]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w)) || s.includes(c.key.toLowerCase())) out.push(c.key); } for (const sl of library()) { const words = (sl.title + " " + topicOf(sl)).toLowerCase().split(/[^a-z0-9ऀ-ॿ]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w))) out.push(topicOf(sl)); } return [...new Set(out)].slice(0, 4); }
  function withTimeout(p, ms) { return Promise.race([p, new Promise((res) => setTimeout(() => res(null), ms))]); }

  async function runIntake() {
    const run = newRun(); S.intakeOpen = true; el.intake.classList.add("open"); el.inFallback.classList.remove("open");
    showSlideView(heroOpen(), { reveal: 99 });
    const q1 = bundle.intake?.q1 || `Hi, I'm ${guide}. Before we begin — could I get your name, and what you're hoping ${bundle.product?.name || "this"} would change for you?`;
    el.inState.textContent = guide;
    const ok = await speak(q1, run, bundle.intake?.audio?.q1); if (!ok) return;
    const a1 = await intakeWait(run); if (run !== S.run) return;
    if (a1) { addMsg("user", a1); S.profile.name = parseName(a1); S.profile.why = a1; S.profile.focus = parseFocus(a1); }
    el.intake.classList.remove("open"); S.intakeOpen = false;
    const ack = a1 ? (S.profile.name ? pick([`Lovely to meet you, ${S.profile.name}.`, `Thanks, ${S.profile.name}.`]) : "Thanks for that.") + " Let me set up what we're deciding, then I'll show you the result first." : "No problem — let me set up what we're deciding, then show you the result first.";
    S.pitchPromise = (a1 && api.pitch) ? withTimeout(api.pitch({ profile: profileForServer(), refine: true }).catch(() => null), 60000) : null;
    const fa = a1 ? F("ack_with_context", ack) : F("ack_no_context", ack); const ok2 = await speak(fa.text, run, fa.audio); if (!ok2) return;
    const okF = await playIntroFilm(run); if (!okF) return;
    await startAfterIntake(run, a1);
  }
  async function startAfterIntake(run = newRun(), a1 = S.profile.why) {
    // The planner starts before the film and continues under recorded audio until its route is needed.
    const pitchP = S.pitchPromise || (api.pitch ? withTimeout(api.pitch({ profile: profileForServer(), refine: true }).catch(() => null), 60000) : Promise.resolve(null)); S.pitchPromise = null;
    const okO = await playOpening(run); if (!okO) return;
    let plan = await withTimeout(pitchP, 150); if (run !== S.run) return;
    if (!plan) { const okH = await speakF("still_working", "Give me one moment, please — I'm tailoring this to what you just told me.", run); if (!okH) return; plan = await withTimeout(pitchP, 2500); if (run !== S.run) return; }
    S.personalized = !!plan;
    if (!plan) addMsg("note", "personalisation was not ready in the opening window — continuing on the stable approved route");
    if (plan) {
      S.pitch = plan; S.profile.focus = [...new Set([...(plan.focus_topics || []), ...S.profile.focus])];
      if (plan.decision_frame) { showSlideView(transientSlide("df", "custom", plan.decision_frame, [], null, "Your demo, tailored"), { reveal: 0 }); el.cite.textContent = ""; const ok = await speak(plan.decision_frame, run, plan.decision_frame_audio); if (!ok) return; }
      const okC = await playCustomBatches(plan, run); if (!okC) return;
      el.cite.textContent = "";
      const ok = await speakF("how_i_go", "Here's how I'll go about it.", run); if (!ok) return;
    } else if (!S.profile.followup) {
      const ok = await speakF("lets_go", "Alright — here we go.", run); if (!ok) return;
    } else {
      const ok = await speakF("focus_first", "Got it — let me show you the part that matters most for that first.", run); if (!ok) return;
    }
    buildRoute(S.pitch); playFrom(0, 0);
  }
  async function playCustomBatches(plan, run) {
    const batches = plan?.custom_batches || [];
    if (!batches.length || S.customPlayed) return run === S.run;
    S.customPlayed = true;
    el.cite.textContent = "";
    const okB = await speakF("bridge_to_custom", "Now, let me get to what you asked about.", run); if (!okB) return false;
    for (const [k, b] of batches.entries()) {
      if (run !== S.run) return false;
      showSlideView(transientSlide(`custom-${k + 1}`, "custom", b.text, b.fact_ids || [], b.visual, "For you"), { reveal: 0 });
      el.cite.textContent = b.fact_ids?.length ? "sources: " + b.fact_ids.join(", ") : "";
      const ok = await speak(b.text, run, b.audio); if (!ok) return false;
    }
    return run === S.run;
  }
  function skipIntake() { interruptAll(); el.intake.classList.remove("open"); S.intakeOpen = false; S.intakeResolver = null; S.pendingIntakeAnswer = ""; const run = newRun(); showSlideView(heroOpen(), { reveal: 99 }); playIntroFilm(run).then((okF) => { if (!okF) return; playOpening(run).then((ok) => { if (!ok) return; buildRoute(null); playFrom(0, 0); }); }); }

  // ---------- handoff ----------
  function intentScore() { let s = 20; s += Math.min(30, S.questions.length * 8); s += S.resolved.size * 8; s += S.seg >= S.plan.length - 1 ? 15 : 0; if (S.cta && S.cta !== "summary") s += 30; if (S.leads.length) s += 10; s -= S.unresolved.size * 5; return Math.max(5, Math.min(98, s)); }
  function sessionRecord() {
    const visited = [...S.visited, ...(cur ? [{ slide_id: cur.slide.id, kind: cur.slide.kind, seconds: Math.round((Date.now() - cur.enteredAt) / 100) / 10 }] : [])];
    const uspsCovered = [...new Set(S.plan.slice(0, S.seg + 1).flatMap((st) => st.slide.usp_ids || []))];
    return { profile: S.profile, customer_state: S.pitch?.customer_state, personalized: !!S.personalized, route: S.plan.map((st) => st.slide.segment_id || st.slide.id), slides: S.plan.map((st) => st.slide.id), slides_visited: visited, covered: [...S.covered], jumps: S.jumps, usps_covered: uspsCovered, questions: S.questions, escalations: S.escalations, leads: S.leads, resolved: [...S.resolved], unresolved: [...S.unresolved], cta: S.cta, intent: intentScore(), drop_point: S.plan[S.seg]?.slide.title, minutes: Math.round((Date.now() - S.started) / 6000) / 10, transcript: S.transcript };
  }
  function showHandoff(c) {
    const session = sessionRecord(); const mins = session.minutes; const topics = [...S.raised]; const uspsCovered = session.usps_covered;
    el.handoffBox.replaceChildren(h("h2", {}, c ? c.label : "Your summary"), h("div", { class: "sub" }, `what the guide passes to the team · ${mins} min · ${S.pitch?.customer_state || "no state"}${S.personalized ? "" : " · standard route (not personalised)"}`),
      h("div", { class: "grid2" },
        h("div", { class: "kvbox" }, h("h5", {}, "Intent"), h("div", { class: "score" }, intentScore(), h("small", {}, " / 100"))),
        h("div", { class: "kvbox" }, h("h5", {}, "Profile"), h("ul", {}, h("li", {}, S.profile.name || "Name not given"), S.profile.why ? h("li", {}, "Why: “", S.profile.why.slice(0, 140), "”") : null, S.profile.followup ? h("li", {}, "Follow-up: “", S.profile.followup.slice(0, 140), "”") : null, h("li", {}, "Focus: ", S.profile.focus.join(", ") || "none stated"))),
        h("div", { class: "kvbox" }, h("h5", {}, "Concerns raised → resolved"), h("ul", {}, topics.length ? topics.map((t) => h("li", {}, t, ": ", h("b", { style: `color:${S.resolved.has(t) ? "var(--accent)" : S.unresolved.has(t) ? "var(--warn)" : "var(--muted)"}` }, S.resolved.has(t) ? "resolved" : S.unresolved.has(t) ? "still unsure" : "discussed"))) : h("li", {}, "none raised explicitly"))),
        h("div", { class: "kvbox" }, h("h5", {}, `Questions asked (${S.questions.length})`), h("ul", {}, S.questions.length ? S.questions.map((q) => h("li", {}, "“", q, "”")) : h("li", {}, "none — listened through"))),
        h("div", { class: "kvbox", style: "grid-column:1/-1" }, h("h5", {}, "For a human to follow up"), h("ul", {}, S.leads.map((l) => h("li", {}, h("b", {}, "Call ", l.phone), " about “", l.question, "”")), S.escalations.length ? S.escalations.filter((e) => !e.startsWith("callback requested")).map((e) => h("li", {}, e)) : (S.leads.length ? null : h("li", {}, "nothing outstanding")))),
        h("div", { class: "kvbox", style: "grid-column:1/-1" }, h("h5", {}, "Route & drop point"), h("ul", {}, h("li", {}, "Route: ", S.plan.map((st) => st.slide.title).join(" → ") || "—"), h("li", {}, `Reached: ${S.plan[S.seg]?.slide.title || "—"} (${Math.min(S.seg + 1, S.plan.length)} of ${S.plan.length} slides) · USPs covered: ${uspsCovered.join(", ") || "—"}`)))),
      h("div", { style: "display:flex;gap:10px;margin-top:14px" }, h("button", { class: "btn primary", onclick: () => { el.handoff.classList.remove("open"); api.saveSession(sessionRecord()).catch(() => {}); addMsg("note", "session saved"); const run = newRun(); speak(c ? "Done — everything we discussed goes with it. Thanks for your time." : "Thanks for your time. Ask me anything else whenever you're ready.", run); } }, c ? "Confirm (mock)" : "Done"), h("button", { class: "btn ghost", onclick: () => { el.handoff.classList.remove("open"); const run = newRun(); speak("Sure — what else would you like to know?", run).then((ok) => { if (ok) listenForQuestion(); }); } }, "Back to the demo")));
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
    try { v.pause(); } catch (e) {}
    v.muted = true; el.stage.classList.remove("film-on"); setChips([]);
    if (!done || run !== S.run) return false;
    return speakF("after_video", "Now, let's get into what matters to you.", run);
  }

  // ---------- pause / stop ----------
  function togglePause() {
    if (S.paused) { S.paused = false; el.pauseBtn.textContent = "⏸"; el.pauseBtn.classList.remove("on"); const r = S.resume; S.resume = null; if (r) r(); else if (S.plan.length) playFrom(S.seg, S.line); return; }
    const wasAt = S.atCheckin, seg = S.seg, line = S.line, intake = S.intakeOpen;
    interruptAll(); S.paused = true; el.pauseBtn.textContent = "▶"; el.pauseBtn.classList.add("on"); setStatus("idle", "Paused"); el.cap.textContent = "Paused — press ▶ to continue.";
    S.resume = () => { if (intake) { runIntake(); return; } if (!S.plan.length) { startAfterIntake(); return; } if (wasAt) playFrom(seg + 1, 0); else playFrom(seg, line); };
  }
  function stopDemo() { interruptAll(); S.paused = false; el.pauseBtn.textContent = "⏸"; el.pauseBtn.classList.remove("on"); el.intake.classList.remove("open"); S.intakeOpen = false; setStatus("idle", "Stopped"); el.cap.textContent = "Stopped."; S.cta = S.cta || "summary"; showHandoff(); }

  // ---------- lifecycle ----------
  function restart() { interruptAll(); S.customPlayed = false; S.introPlayed = false; S.skipFilm = false; S.pitchPromise = null; el.handoff.classList.remove("open"); el.lead.classList.remove("open"); S.questions.length = 0; S.transcript.length = 0; S.escalations.length = 0; S.leads.length = 0; S.visited.length = 0; S.covered.clear(); S.jumps.length = 0; S.resolved.clear(); S.unresolved.clear(); S.raised.clear(); S.cta = null; S.pitch = null; S.plan = []; S.leadPromptShown = false; S.leadQuestion = ""; S.started = Date.now(); S.profile = { name: "", why: "", followup: "", focus: [] }; el.thread.replaceChildren(); if (cur) { cur.view.destroy(); cur = null; } el.stack.replaceChildren(); renderProgress(); runIntake(); }
  function pause() { interruptAll(); setStatus("idle", "Paused"); }
  function context() { const st = S.plan[S.seg]; return { customer_state: S.pitch?.customer_state, route: S.plan.map((x) => x.slide.id), slide: cur?.slide?.id, segment: st?.slide.segment_id, segment_title: st?.slide.title, line_index: S.line, line_text: st?.slide.lines?.[S.line]?.text, bridge: st?.bridge, questions: S.questions.slice(-5), profile: S.profile, escalations: S.escalations.slice(-5), leads: S.leads }; }
  function destroy() { interruptAll(); for (const media of S.preloads) { try { media.removeAttribute("src"); media.load(); } catch (e) {} } S.preloads.length = 0; if (cur) cur.view.destroy(); root.remove(); }

  renderCtas();
  updateMuteUi();
  showSlideView(heroOpen(), { reveal: 99 });
  const startBtn = h("div", { class: "pl-intake open" }, h("div", { class: "inner" }, mascot({ size: 132, image: bundle.mascot }).el, h("div", { class: "state" }, guide), h("p", { class: "q" }, bundle.pitch?.takeaway || `A voice-led walkthrough of ${bundle.product?.name || bundle.name}. Just talk — interrupt anytime.`), h("div", { class: "actions" }, h("button", { class: "btn primary", onclick: () => { startBtn.remove(); runIntake(); } }, "▶ Start"), h("button", { class: "btn ghost", onclick: () => { startBtn.remove(); skipIntake(); } }, "Skip the intro"))));
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
