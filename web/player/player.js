// The runtime player — voice-led, interruptible, grounded through the server.
// Order: intake question (over the hero slide) → opening film (skippable) → the standard opening slides (unchanged) →
// runtime pitch plan (decision frame · custom batches as slides · personalised order) → proof slides with check-ins →
// establish → closing (fit summary) → hero close + CTA → handoff.
// Narration is event-driven: audio leads, the screen follows. A line starting reveals its callouts; its audio end
// advances the narration. After Q&A, a short silent reply window returns to the saved narration checkpoint.
// A question is routed by the server on fact ids and topics (stay on this slide · jump to the slide that carries the
// facts, then return to the interrupted line · none): S.seg / S.line are never touched by a jump, so the return point is
// always the interrupted line — a return stack of depth 1. A slide seen during a jump is covered: reached later, it plays
// its title and first line only.
// Every customer turn is stamped four times — voice ended, STT done, QA done, first answer audio playing — and kept on
// the session record; Observability shows p50 / p95 per stage.
// The transcript holds only what the customer actually heard (a cut-off line is logged as the words that played and
// marked interrupted); only that transcript is sent as history to /run/qa.
// mountPlayer(host, bundle, {qa, tts, pitch, lead, stt, saveSession}) → { destroy, restart, pause, context }
// These imports supply the guide, slide renderer, HTML builder, icons and live voice connection.
// They are assembled below; the entry point that supplies this player is web/app.js:renderPlay.
import { mascot } from "/web/player/mascot.js";
import { renderSlide } from "/web/slide.js";
import { h } from "/web/api.js";
import { icon } from "/web/icons.js";
import { LiveVoiceClient } from "/web/player/live-voice.js";

// Read browser speech support once; the other constants describe text helpers and contact consent.
// These are local defaults; server speech is connected through web/app.js:renderPlay.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const POST_ANSWER_LISTEN_MS = 3000;
// Choose one wording from the supplied array and return it for a spoken acknowledgment.
// This changes phrasing only; playback still goes through player.js:speak.
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const PHONE = /(?:\+?91[\s-]?)?([6-9]\d{9})/;
// Take text and a word limit, then return a shorter string for display or local phrasing.
// This helper does not retrieve facts or send a request to server/app.py:run_qa.
const compact = (t, n) => String(t || "").split(/\s+/).slice(0, n).join(" ");
// Make a fresh session identifier from the current time and a random suffix.
// The same ID follows questions and reports into server/app.py:save_session.
const newSessionId = () => "s_" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
const CONSENT = "By sharing your number you agree the dealership may call you about this product. Nothing else is shared.";
// Check a configured next-step link and return a usable HTTPS URL, or null when it is unsuitable.
// Recap buttons use this result; configured actions arrive through web/app.js:renderPlay.
function ctaLink(cta) {
  if (!["link", "contact", "book"].includes(cta?.kind) || typeof cta.url !== "string" || /[\u0000-\u0020\u007f]/.test(cta.url)) return null;
  try { const url = new URL(cta.url); return url.protocol === "https:" && url.hostname && !url.username && !url.password ? url.href : null; } catch (_) { return null; }
}
// Read customer text and identify an explicit change of priority, rather than a question or hypothetical.
// The boolean controls route refinement through server/app.py:run_pitch.
function explicitContextCorrection(text) {
  const value = String(text || "").trim();
  if (/[?？]/.test(value) || /^(?:what if|if |suppose|imagine|for example|hypothetically)\b/i.test(value)) return false;
  return /^(?:actually[,\s]+)?(?:my (?:priority|main concern) is\b|i (?:care (?:most|more) about|want to focus on|would (?:rather|prefer)|prefer)\b|(?:boot(?: space)?|safety|comfort|range|space|ownership costs?|running costs?|performance|technology) (?:matters? more|is (?:my )?priority)\b)/i.test(value);
}
// Compare the available recorded acknowledgments and return the shorter usable filler key.
// player.js:questionResult uses it while server/runtime_graph.py:run_turn prepares an answer.
function questionAckKey(fillers = {}) {
  const lookup = fillers.hold_on_lookup, question = fillers.hold_on_question;
  return lookup?.audio && lookup.text && (!question?.audio || lookup.text.split(/\s+/).length < (question.text || "").split(/\s+/).length) ? "hold_on_lookup" : "hold_on_question";
}

function defaultVoiceMode(bundle, muted) { return bundle.runtime?.continuous_voice === true && !muted; }

// Build one interactive demo from a host element, published bundle and API callbacks.
// Return lifecycle methods for web/app.js:renderPlay; all visit state stays inside this player.
export function mountPlayer(host, bundle, api) {
  const mutedByDefault = ["1", "true", "on"].includes(new URLSearchParams(window.location.search).get("mute"));
  // Keep the current route, audio, customer input, timing and report fields together for this visit.
  // Run and listening counters identify the owner of asynchronous work; server/runtime_state.py:claim_turn uses matching session IDs.
  const S = { run: 0, plan: [], seg: 0, line: 0, atCheckin: false, waiter: null, waitChips: [], timer: null, intakeResolver: null, pendingIntakeAnswer: "", intakeOpen: false,
    profile: { name: "", why: "", followup: "", focus: [], stated_needs: [] }, pitch: null, questions: [], transcript: [], escalations: [], leads: [], resolved: new Set(), unresolved: new Set(), raised: new Set(),
    cta: null, started: Date.now(), micOn: false, micDenied: false, voiceMode: defaultVoiceMode(bundle, mutedByDefault), inputMode: defaultVoiceMode(bundle, mutedByDefault) ? "voice" : "typed", rec: null, audio: null, utterance: null, muted: mutedByDefault, preloads: [], ttsToken: 0, ttsCache: new Map(), bt: { voice: null },
    leadPromptShown: false, leadQuestion: "", leadReason: "", speaking: null, visited: [], covered: new Set(), jumps: [], sessionId: newSessionId(), ended: false, endedAt: null, turns: [], lastListen: null, onFirstAudio: null,
    listenId: 0, cancelListen: null, finishListen: null, cancelVoice: null, playback: { phase: "opening", index: 0, line: 0 }, conversationOrigin: null, browseOnly: false, openQuestions: new Set(), interruptions: [] };
  const persona = bundle.voice?.persona || {}; const guide = persona.persona_name || "Guide";
  const useServerVoice = bundle.voice?.provider && bundle.voice.provider !== "browser";

  // ---------- slides ----------
  // The deck is the structure. A bundle built before the deck existed gets one slide per segment (its line's own
  // picture, no callouts) so older demos keep playing until they are rebuilt.
  // Use published slides when present; otherwise convert older segments into compatible slide objects.
  // Return the deck consumed by web/slide.js:renderSlide, with one image selected for each slide.
  function slidesOf(b) {
    if (b.slides?.length) return b.slides;
    // Read the bundle hero and map older segment roles to the slide kinds used by this player.
    // kindOf returns a kind; web/slide.js:renderSlide receives the resulting slide, not the old segment.
    const hero = b.media?.hero || null; const kindOf = (r) => ({ intro: "intro", outcome: "outcome", proof: "proof", features: "features", establish: "establish" })[r] || "proof";
    // Build one legacy slide from its ID, role, title, segment and narration lines.
    // Return one image URL and empty callouts so web/slide.js:renderSlide can show older bundles safely.
    const mk = (id, kind, title, seg, lines) => ({ id, segment_id: seg?.id || null, kind, title, topics: seg?.topic ? [seg.topic] : [], image_url: (lines.map((l) => l.visual).find((v) => v?.kind === "image" && v.url) || {}).url || hero, image_parts: [], callouts: [], lines, checkin: seg?.checkin || { text: "" }, deeper: seg?.deeper || [], usp_ids: seg?.usp_ids || [], priority: !!seg?.priority, fundamental: !!seg?.fundamental, role: seg?.role || kind, motion: "zoom_in" });
    const segs = (b.segments || []).map((s, i) => mk(`sl${i + 1}`, kindOf(s.role), s.title, s, s.lines || []));
    return [mk("sl00", "hero_open", b.product?.name || b.name, null, []), ...segs, mk("sl-close", "closing", "Where that leaves you", null, b.closing || []), mk("sl-end", "hero_close", b.product?.name || b.name, null, [])];
  }
  let slides = slidesOf(bundle);
  // Select slides whose kind matches any supplied kind name.
  // Return a filtered deck for opening and route helpers before web/slide.js:renderSlide is called.
  const byKind = (...k) => slides.filter((s) => k.includes(s.kind));
  // Split the deck into the fixed opening and the proof or feature library available for routing.
  // Both helpers return slide arrays; server/agents/pitch.py:plan_pitch chooses from the same published content.
  const opening = () => byKind("intro", "outcome"), library = () => byKind("proof", "features", "establish");
  // Find opening, ending and closing slides, with fallbacks for bundles that omit those kinds.
  // Return slide objects for the main flow; web/slide.js:renderSlide handles their appearance.
  const heroOpen = () => byKind("hero_open")[0] || slides[0], heroClose = () => byKind("hero_close")[0] || heroOpen(), closingSlide = () => byKind("closing")[0] || null;
  // Return a stable topic key, falling back to the segment or slide ID when a topic is missing.
  // Local resolved and unresolved sets use it; server/app.py:save_session receives those sets as arrays.
  const topicOf = (sl) => sl.topics?.[0] || sl.segment_id || sl.id;

  // Keep preload objects alive for the full session: every recorded line, filler, FAQ answer and picture, plus the film.
  // Warm the browser cache with published audio, slide images and the optional opening film.
  // The delayed callback keeps preload objects alive; no new narration is requested from server/app.py:run_tts.
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
  // Look up a short recorded filler and return its text plus audio URL, or a text-only fallback.
  // These bundle assets come from server/agents/voice.py:render_script; player.js:speak chooses the playback path.
  const F = (key, fallback) => { const f = bundle.fillers?.[key]; return f?.audio ? { text: f.text, audio: f.audio } : { text: fallback || f?.text || "", audio: null }; };
  // Speak the chosen filler for the supplied run and clear any previous fact citation.
  // Return the playback result from player.js:speak, which may use live-voice.js:LiveVoiceClient.speak.
  const speakF = (key, fallback, run) => { if (run === S.run) el.cite.textContent = ""; const f = F(key, fallback); return speak(f.text, run, f.audio); };
  let LANG = (bundle.language === "hinglish" ? "hi-IN" : bundle.language) || "en-IN";
  // Expose a language getter and setter that map Hinglish to the browser speech locale.
  // Reads return the active locale; web/player/live-voice.js:LiveVoiceClient also receives it when language changes.
  Object.defineProperty(S, "lang", { set(v) { LANG = v === "hinglish" ? "hi-IN" : v; }, get() { return LANG; } });
  let serverSTT = !!(api.stt && bundle.stt?.provider === "sarvam");
  // Check whether server microphone capture or browser speech recognition is available.
  // Return capability only; web/player/live-voice.js:LiveVoiceClient.startCapture still requests microphone access.
  const canListen = () => (serverSTT && navigator.mediaDevices?.getUserMedia) || SR;

  // ---------- DOM ----------
  // Store references to visible controls while constructing the player with web/api.js:h.
  // The resulting elements let later callbacks update the screen without rebuilding the whole page.
  const el = {};
  // Create the header, slide stage, caption dock, intake, contact form and conversation drawer.
  // Input events call the flow helpers below; web/api.js:h turns these descriptions into DOM elements.
  const root = h("div", { class: "pl" },
    h("div", { class: "pl-top" },
      h("div", { class: "left" }, el.avatar = h("div", { class: "avatar" }), (el.mascotTop = mascot({ size: 34, image: bundle.mascot })).el, h("div", {}, h("div", { class: "pl-name" }, `${guide} · ${bundle.product?.name || bundle.name}`), el.status = h("div", { class: "pl-status" }, h("span", { class: "dot" }), el.statusTxt = h("span", {}, "Ready"))), el.progress = h("div", { class: "pl-progress" })),
      // Wire header buttons to fullscreen, mute, pause, stop, conversation, restart and close actions.
      // Clicks update this visit or call the parent callback provided by web/app.js:renderPlay.
      h("div", { class: "right" }, el.fsBtn = h("button", { class: "icon-btn", title: "Full screen", "aria-label": "Full screen", onclick: () => toggleFullscreen() }, icon("expand", { size: 18 })), el.muteBtn = h("button", { class: "icon-btn", title: "Mute audio", "aria-label": "Mute audio", "aria-pressed": "false", onclick: () => toggleMute() }, icon("volume", { size: 18 })), el.pauseBtn = h("button", { class: "icon-btn", title: "Pause / resume", "aria-label": "Pause / resume", onclick: () => togglePause() }, icon("pause", { size: 18 })), h("button", { class: "icon-btn", title: "Stop and see the summary", "aria-label": "Stop and see the summary", onclick: () => stopDemo() }, icon("stop", { size: 18 })), el.chatBtn = h("button", { class: "icon-btn", title: "Conversation", "aria-label": "Conversation", onclick: () => toggleDrawer() }, icon("message", { size: 18 }), h("span", { class: "badge" })), h("button", { class: "icon-btn", title: "Restart", "aria-label": "Restart", onclick: () => restart() }, icon("restart", { size: 18 })), api.onClose ? h("button", { class: "icon-btn", title: "Close", "aria-label": "Close", onclick: () => { interruptAll(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); api.onClose(); } }, icon("close", { size: 18 })) : null)),
    el.stage = h("div", { class: "pl-stage" },
      el.stack = h("div", { class: "slide-stack" }),
      // Reserve a slide stack, optional film and action area beneath the player header.
      // web/slide.js:renderSlide supplies one image per slide; fading old and new slides can briefly overlap.
      el.film = h("video", { class: "pl-film", muted: true, playsinline: true, preload: "auto" }),
      el.ctas = h("div", { class: "pl-ctas" }),
      h("div", { class: "pl-dock" },
        // Keep the guide, captions, citations and reply controls together in the bottom dock.
        // Narration and question callbacks update these elements; web/player/mascot.js:mascot animates the guide.
        h("div", { class: "pl-cap" }, (el.mascotStage = mascot({ size: 72, image: bundle.mascot })).el, h("div", { class: "who" }, guide), el.cap = h("div", { class: "txt" }), el.cite = h("div", { class: "cite" })),
        h("div", { class: "pl-controls" }, el.live = h("div", { class: "pl-live" }), el.chips = h("div", { class: "pl-chips" }), el.timer = h("div", { class: "pl-timer" }),
          // Submit the typed dock reply without reloading the page, then clear its input field.
          // acceptTypedAnswer routes it to the active wait or server/app.py:run_qa.
          h("form", { class: "pl-reply", onsubmit: (e) => { e.preventDefault(); const t = el.reply.value.trim(); if (t) { el.reply.value = ""; acceptTypedAnswer(t); } } }, el.reply = h("input", { oninput: preferTyping, placeholder: "Ask a question or type your answer…", "aria-label": "Your question or answer" }), h("button", { class: "btn primary sm", type: "submit" }, "Send", icon("send", { size: 16 }))),
          // Wire the microphone button beside the status hint to the current listening flow.
          // micTap may call web/player/live-voice.js:LiveVoiceClient.startCapture or stopCapture.
          h("div", { class: "pl-mic-row" }, el.hint = h("div", { class: "pl-hint" }, (serverSTT || SR) ? "Tap to talk — I'll stop and listen." : "Voice input needs Chrome or Safari — type your question below."), el.mic = h("button", { class: "mic", title: "Talk to your guide", "aria-label": "Talk to your guide", onclick: () => micTap() }, icon("mic", { size: 21 }))))),
      el.intake = h("div", { class: "pl-intake" }, h("div", { class: "inner" }, el.orb = h("div", { class: "orb-slot" }, (el.mascotIntake = mascot({ size: 132, image: bundle.mascot })).el), el.inState = h("div", { class: "state" }, guide), el.inQ = h("p", { class: "q" }), el.inHeard = h("div", { class: "heard" }),
        // Submit typed intake text through the same answer handler used by the main reply box.
        // Its output fills local customer context before server/app.py:run_pitch is requested.
        el.inFallback = h("form", { class: "fallback open", onsubmit: (e) => { e.preventDefault(); const t = el.inText.value.trim(); if (t) { el.inText.value = ""; acceptTypedAnswer(t); } } }, el.inText = h("input", { oninput: preferTyping, placeholder: "Type your answer…", "aria-label": "Your answer" }), h("button", { class: "btn primary sm", type: "submit" }, "Send", icon("send", { size: 16 }))),
        // Offer microphone intake or an explicit skip into browsing.
        // Clicks call intakeMic or skipIntake; neither adds product facts to the bundle from server/app.py:get_bundle.
        h("div", { class: "actions" }, el.inMic = h("button", { class: "mic", title: "Answer by voice", "aria-label": "Answer by voice", onclick: () => intakeMic() }, icon("mic", { size: 21 })), h("button", { class: "btn ghost", onclick: () => skipIntake() }, "Skip, start the demo")))),
      el.handoff = h("div", { class: "pl-handoff" }, el.handoffBox = h("div", { class: "box" })),
      // Build the optional contact form and its close buttons; submit calls saveLeadForm.
      // Only a validated, explicitly submitted form is sent to server/app.py:run_lead.
      el.lead = h("div", { class: "pl-lead" }, h("div", { class: "lead-card" }, h("button", { class: "lead-close", title: "Not now", "aria-label": "Not now", onclick: dismissLeadPrompt }, icon("close", { size: 18 })), h("div", { class: "eyebrow" }, "Optional · dealership follow-up"), h("h3", {}, "Would you like to try it in person?"), el.leadCopy = h("p", {}, "Share your details and the dealership can arrange a test drive."), el.leadForm = h("form", { onsubmit: (e) => { e.preventDefault(); saveLeadForm(); } }, el.leadName = h("input", { placeholder: "Your name", "aria-label": "Your name", autocomplete: "name" }), el.leadPhone = h("input", { placeholder: "10-digit mobile number", "aria-label": "10-digit mobile number", inputmode: "tel", autocomplete: "tel" }), el.leadError = h("div", { class: "lead-error" }), h("p", { class: "consent" }, CONSENT), h("button", { class: "btn primary", type: "submit" }, "Arrange a test drive")), h("button", { class: "btn ghost sm", onclick: dismissLeadPrompt }, "Not now")))),
    // Create a separate conversation drawer with a close button and scrolling transcript area.
    // web/api.js:h builds the DOM; addMsg later retains non-note messages for the session report.
    el.drawer = h("div", { class: "pl-drawer" }, h("div", { class: "head" }, h("span", { class: "drawer-title" }, icon("message", { size: 19 }), "Conversation"), h("button", { class: "icon-btn", title: "Close conversation", "aria-label": "Close conversation", onclick: () => toggleDrawer(false) }, icon("close", { size: 18 }))), el.thread = h("div", { class: "body" }),
      // Submit drawer text without navigation and route it through acceptTypedAnswer.
      // Questions use the API callbacks supplied by web/app.js:renderPlay, just like dock replies.
      h("form", { class: "composer", onsubmit: (e) => { e.preventDefault(); const t = el.q.value.trim(); if (t) { el.q.value = ""; acceptTypedAnswer(t); } } }, el.q = h("input", { oninput: preferTyping, placeholder: "Type a question…", "aria-label": "Type a question" }), h("button", { class: "btn primary sm", type: "submit", "aria-label": "Send question" }, icon("send", { size: 18 })))));
  host.replaceChildren(root);
  // Watch the dock height and expose its measured size as a CSS variable.
  // Resize events keep web/slide.js:renderSlide clear of the caption and input area.
  const dockObserver = typeof ResizeObserver === "function" ? new ResizeObserver(() => {
    root.style.setProperty("--player-dock-height", Math.ceil(root.querySelector(".pl-dock").getBoundingClientRect().height) + "px");
  }) : null;
  dockObserver?.observe(root.querySelector(".pl-dock"));

  // A single capture session stays independent of each narration/question delivery.
  // Old bundles keep their recorded/manual path; runtime.version=1 opts into the new protocol.
  let live = null;
  // Create the live voice client and connect its speech, transcript, state and error callbacks.
  // It consumes the visit ID and locale; web/player/live-voice.js:LiveVoiceClient manages the socket and microphone.
  function createLive() {
    S.pendingRefinement = null; S.contextRevision = 0; S.interruptions.length = 0;
    if (!api.liveUrl) return;
    live = new LiveVoiceClient({ url: api.liveUrl, sessionId: S.sessionId, language: LANG,
      // On detected speech, stop current output and preserve the return point when a conversation begins.
      // The event comes from live-voice.js:LiveVoiceClient.speechStart; local timing records when output was stopped.
      onSpeechStart: (event) => {
        if (S.ended || !S.voiceMode) return;
        cancelPostAnswerListen();
        S.inputMode = "voice"; S.speechDetectedAt = event.detected_at;
        if (S.intakeOpen || S.waiter || S.promptRun === S.run) cancelSpeech();
        else { captureOrigin(); interruptAll({ preservePlanning: openingPlanPending() }); holdConversation(newRun(), { autoResume: false }); }
        S.interruptions.push({ detected_at: event.detected_at, stopped_at: Date.now(), phase: S.playback.phase, detection_source: event.source });
        setStatus("listening", "Listening"); el.live.textContent = "Listening…";
      },
      // Show interim transcripts, then route final customer words to intake, a pending prompt or a question.
      // Input comes from live-voice.js:LiveVoiceClient.receive; only the current visit updates its wait and timing fields.
      onTranscript: (event) => {
        if (S.ended || !S.voiceMode) return;
        const text = (event.text || "").trim();
        if (!event.final) { if (S.intakeOpen) el.inHeard.textContent = text; else el.live.textContent = text; return; }
        if (!text) return;
        S.lastListen = { voice_ended: event.voice_ended, stt_done: event.stt_done, speech_detected: S.speechDetectedAt || null, endpoint_received_at: event.endpoint_received_at, server_endpoint_received_at: event.server_endpoint_received_at, speech_end_basis: event.speech_end_basis, via: "realtime" };
        resumeSession();
        if (S.intakeOpen) { if (S.intakeResolver) S.intakeResolver(text); else { S.pendingIntakeAnswer = text; el.inHeard.textContent = text; } return; }
        if (S.promptRun === S.run && !S.waiter) { S.pendingPromptAnswer = text; return; }
        if (S.waiter) { addMsg("user", text); resolveWait(replyForTurn(text, S.waiter)); return; }
        handleQuestion(text);
      },
      // Translate microphone connection states into button appearance and helpful status text.
      // This callback receives live-voice.js:LiveVoiceClient state changes; it does not submit a question.
      onState: (state) => {
        S.micOn = state === "listening"; S.micOpening = state === "opening";
        if (!S.ended && ["muted", "unavailable"].includes(state)) setVoiceMode(false);
        setMicUI(S.micOn);
        if (state === "opening") { el.hint.textContent = "Opening microphone… You can type while it connects."; if (S.intakeOpen) el.inState.textContent = "Opening microphone — or type below"; }
      },
      // Display a live transport error in the hint, intake area and conversation notes.
      // The message comes from live-voice.js:LiveVoiceClient; typing remains available through the existing controls.
      onError: (message) => { el.hint.textContent = message; if (S.intakeOpen) el.inState.textContent = message; addMsg("note", message); }
    });
    live.setMuted(S.muted);
  }
  createLive();
  // Unlock output, connect the live session and optionally begin microphone capture.
  // The capture flag selects voice or typing; live-voice.js:LiveVoiceClient owns the actual connection.
  function startLive(capture = S.voiceMode) {
    if (!live) return;
    setVoiceMode(capture);
    live.unlockOutput().catch(() => {});
    live.connect().catch(() => { el.hint.textContent = "Live voice is unavailable. You can type your question below."; });
    if (capture) live.startCapture();
    else live.setMicEnabled(false).catch(() => {});
  }

  // Voice mode is a visit preference; each typed/spoken turn keeps its own source.
  function setVoiceMode(enabled) {
    S.voiceMode = !!enabled; S.inputMode = S.voiceMode ? "voice" : "typed";
    if (el.voiceMode) el.voiceMode.checked = S.voiceMode;
    setMicUI(S.micOn);
  }

  // ---------- helpers ----------
  // Apply a status label and matching speaking, listening or thinking appearance to the guide.
  // Inputs are a state and visible text; web/player/mascot.js:mascot receives the animation state.
  function setStatus(kind, txt) { el.status.className = "pl-status " + kind; el.statusTxt.textContent = txt; el.avatar.classList.toggle("speaking", kind === "speaking"); el.avatar.classList.toggle("listening", kind === "listening"); const ms = kind === "speaking" ? "speaking" : kind === "listening" ? "listening" : kind === "thinking" ? "thinking" : "idle"; [el.mascotTop, el.mascotIntake, el.mascotStage].forEach((m) => m && m.set(ms)); }
  // Append a conversation message, scroll it into view and retain non-note text for the report.
  // Role, text and interruption details become history for server/app.py:run_qa and save_session.
  function addMsg(role, text, extra = {}) { const d = h("div", { class: "m " + role + (extra.interrupted ? " interrupted" : "") }, text, extra.interrupted ? h("span", { class: "cut", title: "cut off here" }, " —") : null); el.thread.append(d); el.thread.scrollTop = el.thread.scrollHeight; if (role !== "note") S.transcript.push({ role, text, t: Date.now(), ...extra }); if (role === "agent" && !el.drawer.classList.contains("open")) el.chatBtn.classList.add("unread"); }
  // Mark the next input as typed and stop legacy listening if there is no live capture session.
  // Legacy typing pauses automatic listening while preserving the chosen visit mode.
  function preferTyping() { cancelPostAnswerListen(); if (!live) { S.inputMode = "typed"; stopListening(); } }
  // Accept typed words, stamp their timing and deliver them to the current intake or reply wait.
  // If no wait owns the text, handleQuestion sends it through server/app.py:run_qa.
  function acceptTypedAnswer(text) {
    preferTyping();
    resumeSession();
    S.lastListen = { voice_ended: Date.now(), stt_done: Date.now(), via: "typed" };
    if (S.intakeOpen) { if (S.intakeResolver) S.intakeResolver(text); else { S.pendingIntakeAnswer = text; el.inHeard.textContent = text; } return; }
    if (S.waiter) { addMsg("user", text); resolveWait(replyForTurn(text, S.waiter)); return; }
    handleQuestion(text);
  }
  // Open or close the conversation drawer, clear its unread marker and focus the text box when opened.
  // The optional force flag overrides toggling; the drawer was built with web/api.js:h.
  function toggleDrawer(force) { const on = force === undefined ? !el.drawer.classList.contains("open") : force; el.drawer.classList.toggle("open", on); if (on) { el.chatBtn.classList.remove("unread"); setTimeout(() => el.q.focus(), 80); } }
  // Render the mute icon, label and pressed state from the current muted flag.
  // This updates controls only; web/icons.js:icon supplies the matching symbol.
  function updateMuteUi() { el.muteBtn.replaceChildren(icon(S.muted ? "volume-off" : "volume", { size: 18 })); el.muteBtn.title = S.muted ? "Unmute audio" : "Mute audio"; el.muteBtn.setAttribute("aria-label", el.muteBtn.title); el.muteBtn.setAttribute("aria-pressed", String(S.muted)); el.muteBtn.classList.toggle("on", S.muted); }
  // Toggle output mute across live speech, recorded audio, browser speech and the film.
  // The state is shared with live-voice.js:LiveVoiceClient.setMuted; microphone capture is separate.
  function toggleMute() { S.muted = !S.muted; live?.setMuted(S.muted); if (S.audio) S.audio.muted = S.muted; if (S.utterance) S.utterance.volume = S.muted ? 0 : 1; el.film.muted = S.muted || !el.stage.classList.contains("film-on"); updateMuteUi(); }
  // Turn reply choices into buttons that belong to the current wait object.
  // A stale click cannot resolve a newer wait; web/api.js:h creates the buttons and resolveWait delivers the value.
  function setChips(list) { const owner = S.waiter; el.chips.replaceChildren(...list.map((c) => h("button", { class: "chip" + (c.primary ? " primary" : ""), onclick: () => { if (S.waiter === owner) resolveWait(c.value); } }, c.label))); }
  // A customer starting to respond owns the turn, so silence can no longer resume it.
  function cancelPostAnswerListen() { const pending = S.postAnswerListen; if (!pending) return; clearTimeout(pending.timer); S.postAnswerListen = null; }
  // Lead forms keep their explicit choice boundary. Their close/save handlers
  // start this same answer window only if it still belongs to the current wait.
  function armPostAnswerListen() {
    const pending = S.postAnswerListen;
    if (!pending || pending.timer !== null || S.waiter !== pending.waiter || S.run !== pending.run || S.ended) return;
    if (el.lead.classList.contains("open")) { pending.heldForLead = true; return; }
    const reply = el.drawer.classList.contains("open") ? el.q : el.reply;
    // Typing can begin while the answer is still speaking, before a timer exists.
    if (reply.value) { cancelPostAnswerListen(); return; }
    if (pending.heldForLead) { pending.heldForLead = false; listenForTurn(pending.waiter); }
    if (pending.turn) { pending.turn.post_answer_listen_ms = POST_ANSWER_LISTEN_MS; pending.turn.auto_resumed = false; }
    pending.timer = setTimeout(() => {
      if (S.postAnswerListen !== pending || S.waiter !== pending.waiter || S.run !== pending.run || S.ended) return;
      if (el.lead.classList.contains("open")) { pending.timer = null; return; }
      if (pending.turn) { pending.turn.auto_resumed = true; pending.turn.auto_resumed_at = Date.now(); }
      resolveWait({ value: "__auto_resume" });
    }, POST_ANSWER_LISTEN_MS);
    el.hint.textContent = "Ask another question, or I'll continue in a moment.";
    reply.focus({ preventScroll: true });
  }
  function dismissLeadPrompt() { S.leadFormId = (S.leadFormId || 0) + 1; el.lead.classList.remove("open"); armPostAnswerListen(); }
  // Clear reply timing on a new wait, an explicit choice or interruption.
  function clearTimer() { cancelPostAnswerListen(); if (S.timer) { clearInterval(S.timer); S.timer = null; } el.timer.replaceChildren(); }
  // Increment and return the playback run number whenever a new flow takes ownership.
  // Async callbacks compare this number before continuing; live-voice.js:LiveVoiceClient has its own transport ownership.
  function newRun() { return ++S.run; }
  // Draw route progress buttons and wire each one to an explicit customer navigation action.
  // A click interrupts the old flow before playing the selected slide through web/slide.js:renderSlide.
  function renderProgress() { el.progress.replaceChildren(...S.plan.map((st, i) => h("button", { class: "pp" + (i < S.seg ? " done" : i === S.seg ? " active" : ""), title: st.slide.kind, onclick: () => { resumeSession(); interruptAll(); S.conversationOrigin = null; playFrom(i, 0); } }, st.slide.title))); }
  // Render configured always-visible next-step actions from the published bundle.
  // A click starts ctaFlow; server/app.py:get_bundle supplies the configured actions rather than arbitrary model links.
  function renderCtas() { const ctas = (bundle.ctas || []).filter((c) => c.when === "always" || !c.when); el.ctas.replaceChildren(...ctas.map((c) => h("button", { class: "chip cta" + (c.primary ? " primary" : ""), onclick: () => { resumeSession(); interruptAll(); ctaFlow(c.id, newRun()); } }, c.label))); }

  // ---------- stage: one slide at a time, cross-faded ----------
  // Hold the current slide, renderer controls and entry time in one local reference.
  // web/slide.js:renderSlide owns its DOM; noteVisit converts time spent there into report data.
  let cur = null;  // { slide, view, enteredAt }
  // Show the requested slide or update its reveal position if it is already on screen.
  // Return the controls from web/slide.js:renderSlide; a slide keeps one image while narration reveals its callouts.
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
  // Return the frozen end time for a completed visit, or the current time while it is active.
  // Session duration uses this value before server/app.py:save_session receives the report.
  function sessionNow() { return S.endedAt ?? Date.now(); }
  // Record the time spent on a departing slide, using its stored entry timestamp.
  // Append a visit row for server/app.py:save_session; this is viewing duration, not proof that audio played.
  function noteVisit(c) { if (!c) return; S.visited.push({ slide_id: c.slide.id, kind: c.slide.kind, seconds: Math.round((sessionNow() - c.enteredAt) / 100) / 10 }); }
  // Load the next route slide image and recorded lines while the current slide is being presented.
  // The input slide locates the next step; media URLs come from server/app.py:get_bundle.
  function preloadAfter(slide) {  // the next slide's picture and audio are fetched while this one plays
    const i = S.plan.findIndex((st) => st.slide.id === slide.id); const next = i >= 0 ? S.plan[i + 1]?.slide : null; if (!next) return;
    if (next.image_url) { const im = new Image(); im.decoding = "async"; im.src = next.image_url; S.preloads.push(im); }
    for (const l of [...(next.lines || []), next.checkin?.audio ? { audio: next.checkin.audio } : null].filter(Boolean)) if (l.audio) { const a = new Audio(l.audio); a.preload = "auto"; a.load(); S.preloads.push(a); }
  }
  // A line spoken outside the deck gets complete reviewed evidence, never a clipped fact or an unrelated current image.
  // Create a temporary evidence slide from answer text, approved fact IDs and an optional known visual.
  // Return a normal slide for web/slide.js:renderSlide; prerequisite facts stay condition labels, not new product claims.
  function transientSlide(id, kind, text, factIds, visual, title = "") {
    const facts = (bundle.facts || []).filter((f) => (factIds || []).includes(f.id) && f.approved !== false);
    const primary = facts.filter((f) => f.runtime_role !== "condition");
    const allowed = new Set(primary.map((f) => f.id));
    // Accept only short, complete labels before reusing reviewed callouts on a temporary slide.
    // Return a boolean for label selection; web/slide.js:renderSlide displays the retained text without shortening facts.
    const complete = (label) => typeof label === "string" && label.trim() && wordsOf(label) <= 8;
    const reviewed = slides.map((slide) => ({ slide, callouts: (slide.callouts || []).filter((c) => complete(c.text) && c.fact_ids?.length && c.fact_ids.every((fid) => allowed.has(fid))) }));
    const match = primary.length ? reviewed.find(({ slide, callouts }) => slide.image_url && primary.every((f) => callouts.some((c) => c.fact_ids.includes(f.id)))) : null;
    // Prefer callouts already reviewed for the same evidence, then build compact labels where possible.
    // Fact IDs and condition roles determine the panel output; web/slide.js:renderSlide receives at most three callouts.
    const candidates = [...(match?.callouts || []), ...reviewed.flatMap((s) => s.callouts)];
    const callouts = [], seen = new Set();
    for (const f of facts) {
      if (seen.has(f.id)) continue;
      const conditionOnly = f.runtime_role === "condition";
      const saved = !conditionOnly && candidates.find((c) => c.fact_ids.includes(f.id) && c.fact_ids.every((fid) => !seen.has(fid)));
      // A prerequisite donor proves its conditions, not its product/trim claim.
      let label = conditionOnly ? (f.conditions?.trim() ? `Conditions: ${f.conditions.trim()}` : "") : saved?.text;
      if (!conditionOnly && !label && f.claim != null && f.value != null) {
        label = `${f.claim}: ${f.value}` + (f.conditions ? `; ${f.conditions}` : "");
        const truth = { certified: "Certified", modeled: "Estimate", observed: "Observed", contractual: "Written terms" }[f.truth];
        if (truth) label = `${truth} — ${label}`;
        label = label.trim().replace(/\s+/g, " ");
      }
      if (conditionOnly ? !label : !complete(label)) continue;
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
  // Choose and cache a browser voice matching the active language when that fallback is allowed.
  // Return a SpeechSynthesis voice or null; server/app.py:run_tts is a separate server-voice path.
  function browserVoice() {
    if (S.bt.voice) return S.bt.voice;
    const want = LANG.slice(0, 2).toLowerCase();
    const vs = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(want));
    // Score matching browser voices by locale and preferred voice names, then choose the highest score.
    // The result only guides browser speech selection; it does not change server/agents/voice.py:render_script recordings.
    const score = (v) => { let s = 0; const n = v.name; if (v.lang.replace("_", "-").toLowerCase() === LANG.toLowerCase()) s += 25; if (/neerja|veena|heera|swara|kalpana|lekha/i.test(n)) s += 60; if (/google uk english female|google us english$|google हिन्दी|google hindi/i.test(n)) s += 45; if (/samantha|kate\b|serena|karen|moira|zira|jenny|aria|sonia|libby|emma|olivia|amy\b|joanna|salli|natasha/i.test(n)) s += 30; if (/natural|premium|enhanced|neural|online/i.test(n)) s += 8; if (/rishi|daniel|alex\b|fred|arthur|gordon|oliver|reed|tom\b|david|mark\b|james|guy\b|ryan|ravi|male|eddy|flo\b|grandma|grandpa|sandy|shelley|bahh|bells|boing|bubbles|cellos|wobble|zarvox|trinoids|whisper|jester|organ|superstar|good news|bad news|albert|junior|ralph|kathy/i.test(n)) s -= 70; return s; };
    S.bt.voice = vs.sort((a, b) => score(b) - score(a))[0] || null; return S.bt.voice;
  }
  // Count words in a supplied string for estimated reading time and interrupted transcript length.
  // These estimates support session reporting in server/app.py:save_session; they are not exact audio alignment.
  const wordsOf = (t) => String(t || "").trim().split(/\s+/).filter(Boolean).length;
  // The transcript is what the customer heard. A line is logged when its audio ends; a line cut short is logged as the
  // words that played (elapsed / duration × words) and marked interrupted. captions and the browser voice use elapsed time.
  // Log a completed spoken line once, or estimate the heard prefix when playback was interrupted.
  // The speech record supplies timing and text; server/app.py:save_session receives the marked transcript entry.
  function logHeard(sp, complete) {
    if (!sp || sp.logged) return; sp.logged = true;
    if (complete) { addMsg("agent", sp.text); return; }
    const a = sp.audio; const frac = a && isFinite(a.duration) && a.duration > 0 ? a.currentTime / a.duration : Math.min(1, (Date.now() - sp.startedAt) / Math.max(1, sp.estMs));
    const n = Math.min(sp.words, Math.round(frac * sp.words)); if (n <= 0) return;
    addMsg("agent", sp.text.split(/\s+/).slice(0, n).join(" "), { interrupted: true, full: sp.text, heard_fraction: +frac.toFixed(2) });
  }
  // Consume the one-time callback for actual audio onset and give it the current timestamp.
  // This feeds answer timing later read by server/runtime_metrics.py:aggregate, separately from caption display.
  function firstAudio() { if (S.onFirstAudio) { const f = S.onFirstAudio; S.onFirstAudio = null; f(Date.now()); } }
  // Show text for a readable interval when the selected audio cannot be delivered.
  // Return a cancellable completion promise; server/runtime_metrics.py:aggregate must not count this as successful audio.
  function captionOnly(text, run) {
    return new Promise((res) => {
      const my = ++S.ttsToken, words = wordsOf(text), ms = Math.max(1200, words / 2.5 * 1000);
      const sp = { text, words, audio: null, startedAt: Date.now(), estMs: ms }; S.speaking = sp;
      setStatus("idle", "Audio unavailable · reading together");
      // A readable caption is useful fallback, but is never successful audio.
      // Clear the callback so later narration cannot stamp this failed answer.
      S.onFirstAudio = null;
      if (S.activeTurn) {
        if (S.activeTurn.qa_done) { S.activeTurn.caption_at = Date.now(); S.activeTurn.delivery_failed = true; S.activeTurn.failed = true; }
        else S.activeTurn.ack_caption_at = Date.now();
      }
      let done = false;
      // Finish this caption once, clear its timer and log complete or interrupted text.
      // Resolve true only for the owning run and speech token; the log later reaches server/app.py:save_session.
      const finish = (complete) => { if (done) return; done = true; clearTimeout(t); if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.speaking === sp) { logHeard(sp, complete); S.speaking = null; } res(complete && my === S.ttsToken && run === S.run); };
      // Expose a cancellation callback that finishes this caption with an incomplete result.
      // interruptAll or cancelSpeech can call it; it does not contact server/runtime_live.py:live.
      const cancel = () => finish(false); S.cancelVoice = cancel;
      const t = setTimeout(() => finish(true), ms);
    });
  }
  // Speak text with the browser voice and return a promise for completion or cancellation.
  // Used only by the browser-voice path; server/app.py:run_tts supplies the separate selected-server-voice path.
  function speakBrowser(text, run) {
    return new Promise((res) => {
      const my = ++S.ttsToken, u = new SpeechSynthesisUtterance(text); S.utterance = u;
      const v = browserVoice(); if (v) u.voice = v; u.lang = LANG; u.rate = 0.98; u.pitch = 1.05; u.volume = S.muted ? 0 : 1;
      const sp = { text, words: wordsOf(text), audio: null, startedAt: Date.now(), estMs: Math.max(1500, text.length * 75) }; S.speaking = sp;
      let done = false;
      // Finish browser speech once and clear only the utterance and callbacks owned by this attempt.
      // Resolve with run and token checks; the resulting transcript is saved by server/app.py:save_session.
      const finish = (complete) => { if (done) return; done = true; clearTimeout(t); if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.utterance === u) S.utterance = null; if (S.speaking === sp) { logHeard(sp, complete); S.speaking = null; } res(complete && my === S.ttsToken && run === S.run); };
      // Connect browser-speech cancellation to the same one-time finish routine.
      // Return an incomplete result locally; live-voice.js:LiveVoiceClient.cancelAudio handles the other transport.
      const cancel = () => finish(false); S.cancelVoice = cancel;
      const t = setTimeout(() => finish(true), sp.estMs + 4000);
      // Record actual browser speech start only while this utterance still owns the current run.
      // This updates status and first-audio timing consumed later by server/runtime_metrics.py:aggregate.
      u.onstart = () => { if (!done && my === S.ttsToken && run === S.run) { sp.startedAt = Date.now(); setStatus("speaking", "Speaking"); firstAudio(); } };
      // Map browser speech end and error events to complete or incomplete playback results.
      // These callbacks settle speakBrowser; they do not request replacement text from server/app.py:run_qa.
      u.onend = () => finish(true); u.onerror = () => finish(false);
      try { speechSynthesis.speak(u); } catch (e) { finish(false); }
    });
  }
  // Use a recorded URL first, or request and cache a server voice URL for the supplied text.
  // Return a URL promise or null; web/app.js:renderPlay connects api.tts to server/app.py:run_tts.
  async function audioUrlFor(text, preset) { if (preset) return preset; if (!useServerVoice) return null; if (S.ttsCache.has(text)) return S.ttsCache.get(text); const p = api.tts(text).catch(() => null); S.ttsCache.set(text, p); return p; }
  // Prefetch server audio for text-only items when the player is not using live speech.
  // Input is a list of lines; server/app.py:run_tts may be called through audioUrlFor.
  function prefetch(items) { if (!useServerVoice || live) return; for (const it of items) if (it && !it.audio && it.text) audioUrlFor(it.text); }
  // Deliver one line through live speech, its recorded file, browser voice or captions as appropriate.
  // Return whether this run completed the line; live-voice.js:LiveVoiceClient.speak owns streamed delivery.
  async function speak(text, run, preset, delivery = null) {
    if (run !== S.run || !text) return run === S.run;
    el.cap.textContent = text; if (S.intakeOpen) el.inQ.textContent = text; setStatus("thinking", "Preparing audio");
    // Use the live channel for text that has no recorded audio, retaining its server delivery IDs.
    // The result comes from live-voice.js:LiveVoiceClient.speak and is ignored if the local run has changed.
    if (live?.ready && !preset) {
      const sp = { text, words: wordsOf(text), audio: null, startedAt: null, estMs: wordsOf(text) / 2.5 * 1000 }; S.speaking = sp;
      // Expose cancellation for this live utterance without closing the whole conversation socket.
      // The callback calls live-voice.js:LiveVoiceClient.cancelAudio and leaves the question request separate.
      const cancel = () => live?.cancelAudio(); S.cancelVoice = cancel;
      try {
        const ok = await live.speak(text, { utteranceId: delivery?.runtime_utterance_id, turnId: delivery?.runtime_turn_id,
          // On actual streamed audio start, stamp timing only if this speech still owns the player.
          // live-voice.js:LiveVoiceClient.speak supplies the speech timestamp; firstAudio separately stamps local callback time.
          onStart: (ts) => { if (run === S.run && S.speaking === sp) { sp.startedAt = ts; setStatus("speaking", "Speaking"); firstAudio(); } } });
        if (S.speaking === sp) { if (sp.startedAt) logHeard(sp, ok); S.speaking = null; }
        if (S.cancelVoice === cancel) S.cancelVoice = null;
        if (ok && run === S.run) setStatus("idle", live.mic ? "Listening" : "Ready");
        return ok && run === S.run;
      } catch (error) {
        if (S.speaking === sp) { if (sp.startedAt) logHeard(sp, false); S.speaking = null; }
        if (S.cancelVoice === cancel) S.cancelVoice = null;
        if (run !== S.run || error.name === "AbortError") return false;
        addMsg("note", "The selected voice is unavailable for this line. Showing its caption.");
        return captionOnly(text, run);
      }
    }
    // Resolve a preset or cached audio URL, then reject results from an obsolete run or speech token.
    // audioUrlFor may use server/app.py:run_tts; the checks prevent late responses from starting old narration.
    const voiceToken = S.ttsToken;
    let url = null; try { url = await audioUrlFor(text, preset); } catch (e) {}
    if (run !== S.run || voiceToken !== S.ttsToken) return false;
    let ok;
    // Play a recorded audio file and wait for playback events rather than advancing on a slide timer.
    // The URL comes from server/app.py:get_bundle or run_tts; completion is returned to the narration loop.
    if (url) ok = await new Promise((res) => {
      const my = ++S.ttsToken, a = new Audio(url); a.muted = S.muted; S.audio = a;
      const sp = { text, words: wordsOf(text), audio: a, startedAt: Date.now(), estMs: wordsOf(text) / 2.5 * 1000 }; S.speaking = sp;
      let done = false;
      // Settle file playback once and clear only the audio objects owned by this attempt.
      // Return completion with run and token checks; logHeard supplies the transcript for server/app.py:save_session.
      const finish = (complete) => { if (done) return; done = true; if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.audio === a) S.audio = null; if (S.speaking === sp) { logHeard(sp, complete); S.speaking = null; } res(complete && my === S.ttsToken && run === S.run); };
      // Pause this audio file and settle its promise as interrupted when cancellation is requested.
      // This is the recorded-file counterpart to live-voice.js:LiveVoiceClient.cancelAudio.
      const cancel = () => { a.pause(); finish(false); }; S.cancelVoice = cancel;
      // Treat the file playing event as audio onset only for the current speech and run.
      // Late playback is paused; server/runtime_metrics.py:aggregate later uses the retained first-audio timestamp.
      a.onplaying = () => { if (!done && my === S.ttsToken && run === S.run) { sp.startedAt = Date.now(); setStatus("speaking", "Speaking"); firstAudio(); } else a.pause(); };
      // Handle file playback failure without reviving a cancelled utterance.
      // Return caption or browser-voice completion according to the configured provider from server/app.py:get_bundle.
      const safeFallback = () => {
        if (done) return;
        if (my !== S.ttsToken || run !== S.run) { finish(false); return; }
        done = true; a.pause(); if (S.audio === a) S.audio = null; if (S.cancelVoice === cancel) S.cancelVoice = null; if (S.speaking === sp) S.speaking = null;
        (useServerVoice ? captionOnly(text, run) : speakBrowser(text, run)).then(res);
      };
      // Map file end and error events to completion or the provider-appropriate fallback.
      // A rejected play request uses the same fallback; server/app.py:run_tts is not retried here.
      a.onended = () => finish(true); a.onerror = safeFallback; a.play().catch(safeFallback);
    });
    else ok = useServerVoice ? await captionOnly(text, run) : await speakBrowser(text, run);
    if (ok && run === S.run) setStatus("idle", "Ready");
    return ok && run === S.run;
  }
  // Invalidate pending speech, cancel browser output and pause any current recorded file.
  // This affects output only; live-voice.js:LiveVoiceClient interruption is coordinated by interruptAll.
  function cancelSpeech() {
    S.ttsToken++; if (S.cancelVoice) S.cancelVoice(); S.cancelVoice = null;
    try { speechSynthesis.cancel(); } catch (e) {} S.utterance = null;
    if (S.audio) { try { S.audio.pause(); } catch (e) {} S.audio = null; }
  }
  // Mark a line as the active prompt, speak it and report whether the customer can answer it.
  // The live path can keep a prompt open after output trouble; live-voice.js:LiveVoiceClient still accepts input.
  async function speakPrompt(text, run, preset, delivery = null) {
    S.promptRun = run;
    const ok = await speak(text, run, preset, delivery);
    return ok || (!!live && run === S.run);
  }

  // ---------- voice in ----------
  // Convert captured floating-point microphone samples into a mono WAV blob at the target sample rate.
  // Return binary audio for the api.stt callback wired to server/app.py:run_stt.
  function encodeWav(chunks, inRate, outRate = 16000) {
    const total = chunks.reduce((n, c) => n + c.length, 0); const all = new Float32Array(total); let o = 0; for (const c of chunks) { all.set(c, o); o += c.length; }
    const ratio = inRate / outRate, outLen = Math.floor(all.length / ratio), pcm = new Int16Array(outLen);
    for (let i = 0; i < outLen; i++) { const s0 = Math.floor(i * ratio), s1 = Math.min(all.length, Math.floor((i + 1) * ratio)); let sum = 0; for (let j = s0; j < s1; j++) sum += all[j]; const v = Math.max(-1, Math.min(1, sum / Math.max(1, s1 - s0))); pcm[i] = v < 0 ? v * 0x8000 : v * 0x7fff; }
    // Allocate the WAV header and provide a small helper that writes its ASCII labels at byte offsets.
    // w takes an offset and string; the finished buffer is submitted to server/app.py:run_stt.
    const buf = new ArrayBuffer(44 + pcm.length * 2), dv = new DataView(buf); const w = (p, s) => { for (let i = 0; i < s.length; i++) dv.setUint8(p + i, s.charCodeAt(i)); };
    w(0, "RIFF"); dv.setUint32(4, 36 + pcm.length * 2, true); w(8, "WAVE"); w(12, "fmt "); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true); dv.setUint32(24, outRate, true); dv.setUint32(28, outRate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); w(36, "data"); dv.setUint32(40, pcm.length * 2, true);
    new Int16Array(buf, 44).set(pcm); return new Blob([buf], { type: "audio/wav" });
  }
  // Each capture owns its callbacks through permission, capture and transcription. Cancelling a turn
  // invalidates all three stages; finishing the mic deliberately still delivers this turn's answer.
  // Capture one legacy microphone turn, detect its end and transcribe it through the server.
  // Input options and a listening ID produce text; server/app.py:run_stt never owns the browser microphone.
  async function listenServer(opts, id) {
    const { timeout = 10000, onInterim = () => {} } = opts;
    // Check that this asynchronous capture still owns the current listening ID.
    // Return a boolean before using permission or transcription results from server/app.py:run_stt.
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
      // Resolve this capture once and clear its listening controls only when it is still current.
      // The text result returns to the waiting player flow after server/app.py:run_stt or local cancellation.
      const settle = (text) => { if (settled) return; settled = true; if (current()) { S.cancelListen = null; S.finishListen = null; S.micOn = false; setMicUI(false); } res(text); };
      // Stop audio processing and microphone tracks, then clear capture timers and UI state.
      // This releases browser resources before or after server/app.py:run_stt; it does not submit text itself.
      const cleanup = () => { if (!capturing) return; capturing = false; clearTimeout(t); try { proc.disconnect(); src.disconnect(); } catch (e) {} stream.getTracks().forEach((track) => track.stop()); ctx.close().catch(() => {}); if (current()) { S.micOn = false; setMicUI(false); } };
      // Cancel microphone capture and resolve it with no customer text.
      // This prevents stale input reaching server/app.py:run_qa after another turn has taken ownership.
      const cancel = () => { cleanup(); settle(""); };
      // Finish a valid capture, encode it and request transcription only when speech samples exist.
      // Return current transcription text or an empty result; web/app.js:renderPlay supplies the run_stt callback.
      const finish = async () => {
        if (!capturing || !current()) return; cleanup();
        if (!spoke || !chunks.length) { settle(""); return; }
        const tVoice = Date.now(); setStatus("thinking", "Transcribing"); if (S.intakeOpen) el.inState.textContent = "Transcribing your answer…"; onInterim("Transcribing…");
        try { const text = await api.stt(encodeWav(chunks, ctx.sampleRate), LANG); if (!current() || settled) return; S.lastListen = { voice_ended: tVoice, stt_done: Date.now(), via: "server" }; settle((text || "").trim()); }
        catch (e) { if (!current() || settled) return; if (SR) { serverSTT = false; addMsg("note", "Server listening is unavailable — you can retry with browser listening or type below."); } settle(""); }
      };
      S.cancelListen = cancel; S.finishListen = finish;
      const t = setTimeout(finish, timeout);
      // Collect audio buffers and use their volume plus elapsed silence to decide when capture ends.
      // The event yields samples for encodeWav; server/app.py:run_stt receives the final WAV, not these callbacks.
      proc.onaudioprocess = (e) => {
        if (!current() || !capturing) return;
        const d = e.inputBuffer.getChannelData(0); chunks.push(new Float32Array(d)); let sum = 0; for (const sample of d) sum += sample * sample;
        const now = Date.now(); if (Math.sqrt(sum / d.length) > 0.012) { if (!spoke) cancelPostAnswerListen(); spoke = true; lastVoice = now; }
        if ((spoke && now - lastVoice > 1300) || now - t0 > timeout || (!spoke && now - t0 > Math.min(timeout, 7000))) finish();
      };
      src.connect(proc); proc.connect(ctx.destination);
    });
  }
  // Start a fresh listening attempt after discarding the previous one.
  // Return server or browser transcription text; web/app.js:renderPlay provides the server STT option.
  function listen(opts = {}) {
    stopListening(); const id = ++S.listenId;
    if (serverSTT && !S.micDenied && navigator.mediaDevices?.getUserMedia) { setStatus("thinking", "Opening microphone"); return listenServer(opts, id); }
    return listenBrowser(opts, id);
  }
  // Capture one turn with browser speech recognition when the server path is unavailable or unused.
  // Return final or interim text after a bounded capture; server/app.py:run_qa receives it only later.
  function listenBrowser({ timeout = 10000, onInterim = () => {} } = {}, id) {
    return new Promise((res) => {
      if (!SR || S.micDenied) { res(""); return; }
      // Identify whether this browser recognition attempt still owns the listening slot.
      // The boolean prevents old recognition events becoming a new server/app.py:run_qa input.
      const current = () => id === S.listenId;
      const rec = new SR(); S.rec = rec; rec.lang = LANG; rec.interimResults = true; rec.continuous = false;
      let fin = "", interim = "", ended = false; S.micOn = true; setMicUI(true);
      // Finish browser recognition once, optionally discard text and preserve valid timing information.
      // Resolve the text promise; server/runtime_metrics.py:aggregate later distinguishes this browser timing source.
      const end = (discard = false) => {
        if (ended) return; ended = true; clearTimeout(t);
        const text = !discard && current() ? (fin || interim).trim() : "";
        if (current()) { S.cancelListen = null; S.finishListen = null; S.rec = null; S.micOn = false; setMicUI(false); if (text) S.lastListen = { voice_ended: Date.now(), stt_done: Date.now(), via: "browser" }; }
        res(text);
      };
      // Expose a discard action that resolves empty and aborts the browser recognizer.
      // stopListening uses it before a new turn; live-voice.js:LiveVoiceClient has independent capture cleanup.
      S.cancelListen = () => { end(true); try { rec.abort(); } catch (e) {} };
      // Expose a deliberate finish action that asks the recognizer to deliver its current result.
      // This differs from discarding a turn; returned text may later reach server/app.py:run_qa.
      S.finishListen = () => { try { rec.stop(); } catch (e) { end(); } };
      // Combine final and interim recognition results and update the visible partial transcript.
      // Ignore stale events; final text is routed locally before any server/app.py:run_qa request.
      rec.onspeechstart = () => { if (!ended && current()) cancelPostAnswerListen(); };
      rec.onresult = (e) => { if (ended || !current()) return; interim = ""; fin = ""; for (const r of e.results) { if (r.isFinal) fin += r[0].transcript; else interim += r[0].transcript; } if ((fin || interim).trim()) cancelPostAnswerListen(); onInterim((fin || interim).trim()); };
      // Remember denied microphone access and settle recognition when the browser reports an error.
      // The screen can then offer typing; this does not retry server/app.py:run_stt.
      rec.onerror = (e) => { if (!current() || ended) return; if (e.error === "not-allowed" || e.error === "service-not-allowed") S.micDenied = true; end(); };
      // Settle recognition on its end event, or request a finish when the capture timeout expires.
      // The returned text still belongs to this listening ID, unlike live-voice.js continuous capture.
      rec.onend = () => end(); const t = setTimeout(() => { if (current()) S.finishListen?.(); }, timeout);
      try { rec.start(); } catch (e) { end(); }
    });
  }
  // Stop or finish legacy listening, while leaving a live capture session under its own controls.
  // The discard flag chooses cancellation versus delivery; live-voice.js:LiveVoiceClient owns persistent capture.
  function stopListening(discard = true) {
    if (live) { S.micOn = live.mic; setMicUI(S.micOn); return; }
    if (!discard) { S.finishListen?.(); return; }
    const cancel = S.cancelListen; S.listenId++; S.cancelListen = null; S.finishListen = null; S.rec = null;
    if (cancel) cancel(); S.micOn = false; setMicUI(false);
  }
  // Show whether the microphone is enabled and explain the current input options.
  // The boolean comes from capture state; live-voice.js:LiveVoiceClient reports live microphone changes.
  function setMicUI(on) {
    const enabled = live ? S.voiceMode : S.inputMode === "voice";
    for (const button of [el.mic, el.inMic]) {
      button.classList.toggle("on", enabled);
      button.title = enabled ? "Turn voice mode off" : "Turn voice mode on";
      button.setAttribute("aria-label", button.title); button.setAttribute("aria-pressed", String(enabled));
    }
    if (live) {
      el.hint.textContent = on ? "Microphone on — speak any time to interrupt. Tap to mute." : "Microphone off — type below or tap to enable it.";
      if (S.intakeOpen) el.inState.textContent = on ? "Listening — take your time" : "Type your answer, or enable the microphone";
      if (!on) {
        el.live.textContent = "";
        if (el.status.classList.contains("listening") || el.statusTxt.textContent === "Listening") setStatus("idle", S.ended ? "Demo complete" : "Microphone off");
      }
      return;
    }
    if (on) { setStatus("listening", "Listening"); el.hint.textContent = "Listening… tap the mic when you are done, or type below."; if (S.intakeOpen) el.inState.textContent = "Listening — or type your answer below"; }
    else { el.live.textContent = ""; if (el.status.classList.contains("listening")) setStatus("idle", "Your turn"); el.hint.textContent = canListen() && !S.micDenied ? "Tap to talk, or type your reply below." : "Type your reply below."; }
  }

  // ---------- flow primitives ----------
  // Check whether opening personalization is still pending while overview or opening content plays.
  // Return whether an interruption may preserve server/agents/pitch.py:plan_pitch work.
  function openingPlanPending() { return !!S.pitchPromise && !S.planningDecided && ["opening", "overview", "planning"].includes(S.playback.phase); }
  // Invalidate the old run and stop its speech, film, waits and unfinished answer delivery.
  // The optional planning flag is forwarded to live-voice.js:LiveVoiceClient.interrupt without resuming anything automatically.
  function interruptAll({ preservePlanning = false } = {}) { newRun(); if (S.activeTurn && !S.activeTurn.delivery_done) { S.activeTurn.cancelled = true; S.activeTurn.cancelled_at = Date.now(); } S.activeTurn = null; live?.interrupt({ preservePlanning }); cancelSpeech(); stopListening(); S.promptRun = null; S.pendingPromptAnswer = ""; try { el.film.pause(); } catch (e) {} el.stage.classList.remove("film-on"); S.onFirstAudio = null; clearTimer(); if (S.waiter) { const w = S.waiter; S.waiter = null; S.waitChips = []; w.resolve({ value: "__interrupted" }); } if (S.intakeResolver) S.intakeResolver(""); setChips([]); }
  // Interpret customer words only against choices offered by the current wait.
  // Return a selected value or a question; server/app.py:run_qa handles questions that do not match a choice.
  function interpretReply(t, chips) {
    // Normalize the reply and provide a helper that checks whether a particular choice is available.
    // has returns a boolean, so locally recognized words cannot invent an action absent from server/app.py:get_bundle.
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
    // A mention (including a refusal or a question) is not a selection.
    for (const c of bundle.ctas || []) if (s === c.label.toLowerCase().trim().replace(/[.!?,]+$/g, "") && has("cta:" + c.id)) return { value: "cta:" + c.id };
    if (/(not yet|later|think about|not now|baad mein)/.test(s) && has("notyet")) return { value: "notyet" };
    if (/(human|person|advisor|someone|sales|team)/.test(s) && has("human")) return { value: "human" };
    return { value: "question", text: t };
  }
  // Treat an open-answer prompt as free text except for its explicitly available skip or continue choices.
  // Return a reply object for resolveWait; a resulting question may go to server/app.py:run_qa.
  function replyForTurn(text, turn) {
    if (!turn.openAnswer) return interpretReply(text, turn.chips);
    const value = text.toLowerCase().trim().replace(/[.!?,]+$/g, "");
    if (/^(continue(?: the demo)?|carry on|go ahead)$/.test(value) && turn.chips.some((c) => c.value === "continue")) return { value: "continue" };
    if (/^skip(?: this question)?$/.test(value)) { const skip = turn.chips.find((c) => c.value === "skip" || c.label === "Skip this question"); if (skip) return { value: skip.value }; }
    return { value: "answer", text };
  }
  // Listen for a specific pending wait and ignore results after another wait or run replaces it.
  // Legacy recognition returns text here; live-voice.js:LiveVoiceClient sends its results through onTranscript instead.
  function listenForTurn(turn) {
    if (live) { setMicUI(live.mic); return; }
    if (S.inputMode !== "voice" || S.waiter !== turn || turn.run !== S.run || !canListen() || S.micDenied) return;
    // Update interim text only for this wait, then resolve a current result or keep the customer turn open.
    // The promise comes from listen; no empty recording is submitted as a server/app.py:run_qa question.
    listen({ timeout: turn.listenSecs, onInterim: (t) => { if (S.waiter === turn) el.live.textContent = t; } }).then((t) => {
      if (S.waiter !== turn || turn.run !== S.run) return;
      if (t) { addMsg("user", t); resolveWait(replyForTurn(t, turn)); }
      else { setStatus("idle", "Your turn"); el.hint.textContent = "Type your reply, tap the mic to try again, or choose an option."; }
    });
  }
  // Create an explicit customer-turn promise with buttons and optional listening.
  // It waits for input rather than auto-advancing; web/api.js:h builds choices and live-voice.js supplies live replies.
  function waitFor(chips, seconds = 0, opts = {}) {
    return new Promise((res) => {
      clearTimer();
      const turn = { resolve: res, run: S.run, chips, openAnswer: !!opts.openAnswer, listenSecs: opts.listenSecs || 10000 };
      S.waiter = turn; S.waitChips = chips; setChips(chips); setStatus("idle", "Your turn");
      if (S.pendingPromptAnswer) { const text = S.pendingPromptAnswer; S.pendingPromptAnswer = ""; addMsg("user", text); resolveWait(replyForTurn(text, turn)); return; }
      el.hint.textContent = "Take your time. Reply by voice or type, or choose an option.";
      if (opts.listen !== false) listenForTurn(turn);
    });
  }
  // Resolve the current wait once, clearing its prompt markers, listening callbacks and choices.
  // A reply object goes back to the flow; further questions can then use server/app.py:run_qa.
  function resolveWait(v) { clearTimer(); if (S.waiter) { const w = S.waiter; S.waiter = null; S.promptRun = null; S.waitChips = []; stopListening(); setChips([]); w.resolve(typeof v === "string" ? { value: v } : v); } }
  // Speak a question and wait for an open reply or an explicit skip.
  // Return reply text only for the owning run; server/runtime_graph.py:run_turn may have supplied the clarification.
  async function askAndListen(question, run, secs = 10000, preset = null, delivery = null) { if (run !== S.run) return null; el.cite.textContent = ""; if (!(await speakPrompt(question, run, preset, delivery))) { S.promptRun = null; return null; } const r = await waitFor([{ label: "Skip this question", value: "skip" }], 0, { openAnswer: true, listenSecs: secs }); return run === S.run ? r.text || "" : null; }

  // ---------- route building: the pitch plan orders slides ----------
  // Turn the server pitch route into known deck slides, with a local reviewed-order fallback.
  // Validated replacement lines keep image and callout geometry from web/slide.js:renderSlide inputs.
  function buildRoute(plan) {
    const lib = library(); const bySeg = Object.fromEntries(lib.map((s) => [s.segment_id, s]));
    let steps = [];
    if (plan?.route?.length) steps = plan.route.map((r) => ({ r, slide: (r.slide_id && lib.find((s) => s.id === r.slide_id)) || bySeg[r.segment_id] })).filter((x) => x.slide).map(({ r, slide }) => ({ slide, bridge: r.bridge, bridge_audio: r.bridge_audio || "", bridge_fact_ids: r.bridge_fact_ids || [] }));
    if (!steps.length) { // fallback: focus topics first, then deck order, establish last
      // Match local focus keys to available proof slides, then leave establishing slides until the end.
      // hit returns a routing preference only; server/agents/pitch.py:plan_pitch remains the source of server personalization.
      const focus = new Set(S.profile.focus); const hit = (s) => focus.has(topicOf(s)) || focus.has(s.segment_id); const proof = lib.filter((s) => s.kind !== "establish"); const est = lib.filter((s) => s.kind === "establish");
      steps = [...proof.filter(hit), ...proof.filter((s) => !hit(s)), ...est].map((slide) => ({ slide, bridge: "", bridge_fact_ids: [] }));
      if (!S.plan.length) {
        // Only the initial fallback reserves one unseen fundamental. Later route
        // replacements and reviewed revisits keep their selected order.
        const visited = new Set((S.visited || []).map(visit => visit.slide_id));
        const first = lib.find(slide => slide.kind === "proof" && slide.fundamental && !visited.has(slide.id) && !S.covered?.has(slide.id));
        if (first) steps = [steps.find(step => step.slide === first), ...steps.filter(step => step.slide !== first)];
      }
    }
    // Apply selected personalized lines and remap callout reveals to their original reviewed line positions.
    // The pitch result changes visit-local speech, while web/slide.js:renderSlide keeps the reviewed visual layout.
    const personalized = new Map((plan?.personalized_segments || []).map(segment => [segment.segment_id, segment]));
    steps = steps.map(step => {
      const segment = personalized.get(step.slide.segment_id);
      if (!segment?.lines?.length) return step;
      // Keep the reviewed image/parts and citation geometry; only validated speech is visit-local.
      const reviewedMedia = (step.slide.media || []).slice(0, 2);
      const mediaByLine = segment.lines.map(line => {
        if (Number.isInteger(line.base_line_index)) {
          let owner = reviewedMedia[0], latest = -Infinity;
          for (const entry of reviewedMedia) {
            const from = Number(entry.from_line) || 0;
            if (from <= line.base_line_index && from >= latest) { owner = entry; latest = from; }
          }
          return owner?.image_id || null;
        }
        return reviewedMedia.find(entry => entry.image_id === line.visual?.ref)?.image_id || null;
      });
      // An inserted customer preface inherits the next reviewed line's picture.
      // Keep exact per-line ownership too: a reordered A/B/A sequence has two
      // pictures but cannot be expressed by a single from_line for each one.
      for (let index = 0; index < mediaByLine.length; index++) {
        if (!mediaByLine[index]) mediaByLine[index] = mediaByLine.slice(index + 1).find(Boolean) || mediaByLine[index - 1] || reviewedMedia[0]?.image_id || null;
      }
      const usedMedia = [...new Set(mediaByLine.filter(Boolean))];
      const media = usedMedia.map(imageId => ({ ...reviewedMedia.find(entry => entry.image_id === imageId), from_line: mediaByLine.indexOf(imageId) }));
      const callouts = (step.slide.callouts || []).flatMap(callout => {
        const index = segment.lines.findIndex(line => Number.isInteger(line.base_line_index) && line.base_line_index === callout.reveal_on_line);
        return index < 0 || (reviewedMedia.length && callout.image_id && !usedMedia.includes(callout.image_id)) ? [] : [{ ...callout, reveal_on_line: index }];
      });
      const checkin = segment.checkin && typeof segment.checkin === "object" && typeof segment.checkin.text === "string" ? segment.checkin : step.slide.checkin;
      const mediaFields = media.length ? { media, media_by_line: mediaByLine, image_id: media[0].image_id, image_url: media[0].image_url, image_parts: media[0].image_parts } : {};
      return { ...step, slide: { ...step.slide, ...mediaFields, lines: segment.lines, callouts, checkin } };
    });
    S.plan = steps; S.seg = 0; renderProgress();
    prefetch(steps.filter((s) => s.bridge).map((s) => ({ text: s.bridge })));
  }
  // Retain the customer wording and optionally mark it as an explicitly stated need.
  // Update local routing hints; profileForServer passes this context to server/app.py:run_pitch.
  function rememberContext(text, { statedNeed = false } = {}) {
    if (!text) return;
    S.profile.followup = [S.profile.followup, text].filter(Boolean).join("\n");
    if (statedNeed && !S.profile.stated_needs.includes(text)) S.profile.stated_needs.push(text);
    S.profile.focus = [...new Set([...S.profile.focus, ...parseFocus(text)])];
  }
  // Request a revised upcoming route after an explicit change of priority.
  // Send seen IDs and the loaded bundle version to server/app.py:run_pitch; accept only the same session and revision.
  function queueRefinement() {
    if (!api.pitch || !live) return;
    const sessionId = S.sessionId, revision = S.contextRevision = (S.contextRevision || 0) + 1;
    const origin = S.conversationOrigin || S.playback;
    const seen = [...new Set([...S.visited.map(visit => visit.slide_id), cur?.slide?.id].map(id => slides.find(slide => slide.id === id)?.segment_id).filter(Boolean))];
    const pending = { revision, afterSegment: ["route", "deeper"].includes(origin.phase) ? S.plan[origin.index]?.slide.segment_id : null, seen, status: "pending" };
    S.pendingRefinement = pending;
    withTimeout(api.pitch({ profile: profileForServer(), refine: true, voice_it: false, input_mode: S.voiceMode ? "voice" : "text", session_id: sessionId, demo_version: bundle.version, seen_segments: seen }).catch(() => null), 12000).then(plan => {
      if (S.sessionId !== sessionId || S.pendingRefinement !== pending || S.ended) return;
      pending.status = plan?.route?.length ? "ready" : "failed"; pending.plan = plan;
    });
  }
  // Apply a ready refinement at a safe boundary without replacing the completed route prefix.
  // Server-approved revisit IDs may restore seen segments; server/agents/pitch.py:plan_pitch supplies that permission.
  async function applyUpcomingPlan(index, run) {
    const pending = S.pendingRefinement;
    if (!pending || pending.status === "pending") return run === S.run;
    const prefix = S.plan.slice(0, index);
    if (pending.afterSegment && !prefix.some(step => step.slide.segment_id === pending.afterSegment)) return run === S.run;
    S.pendingRefinement = null;
    if (pending.status === "failed") return speak("I couldn't finish updating the route just now. I'll continue with the reviewed demo, and you can ask about what matters to you.", run);
    const previous = S.plan; buildRoute(pending.plan);
    const seen = new Set([...pending.seen, ...prefix.map(step => step.slide.segment_id)]);
    const selected = new Set((pending.plan.route || []).map(step => step.segment_id));
    const revisits = new Set((pending.plan.revisit_segment_ids || []).filter(id => pending.seen.includes(id) && selected.has(id)));
    const future = S.plan.filter(step => !seen.has(step.slide.segment_id) || revisits.has(step.slide.segment_id))
      .map(step => ({ ...step, reviewedRevisit: revisits.has(step.slide.segment_id) }));
    S.plan = future.length ? [...prefix, ...future] : previous;
    S.seg = index; S.pitch = { ...S.pitch, ...pending.plan }; renderProgress();
    addMsg("note", "Updated the unplayed route from your stated priority; the current return point was retained.");
    return run === S.run;
  }
  // Narration never opens a customer turn, including question-shaped legacy lines.
  // Only runtime clarification, explicit questions and CTA choices own waits.
  async function waitForLineQuestion(line, run) {
    return run === S.run;
  }
  // Play each narration line in order, revealing its callouts as the line starts.
  // Await audio completion; web/slide.js:renderSlide never chooses the narration pace.
  async function playLines(sl, run, view, from = 0, upto = sl.lines.length) {
    for (let j = from; j < upto; j++) {
      if (run !== S.run) return false;
      S.line = j; S.playback.line = j;
      const ln = sl.lines[j]; view.setRevealed(j); el.cite.textContent = ln.fact_ids?.length ? "sources: " + ln.fact_ids.join(", ") : "";
      const spoken = await speak(ln.text, run, ln.audio);
      if (!spoken) return false;
      S.line = j + 1; S.playback.line = j + 1;
      if (!(await waitForLineQuestion(ln, run))) return false;
    }
    return run === S.run;
  }
  // Present the fixed opening slides from a supplied slide and line checkpoint.
  // Return completion for the owning run; web/slide.js:renderSlide receives each opening visual.
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
  // Walk the personalized route, preserving exact line checkpoints and optional reviewed revisits.
  // Audio completion and customer choices drive progression; web/slide.js:renderSlide only handles the view.
  async function playFrom(idx, lineIdx = 0, bridgeDone = false) {
    const run = newRun();
    for (let i = idx; i < S.plan.length; i++) {
      if (!(await applyUpcomingPlan(i, run))) return;
      const step = S.plan[i], sl = step.slide; S.seg = i; S.atCheckin = false; S.playback = { phase: "route", index: i, line: lineIdx, checkin: false, bridgeDone }; renderProgress();
      prefetch([...sl.lines.slice(lineIdx), sl.checkin?.text ? { text: sl.checkin.text, audio: sl.checkin.audio } : null].filter(Boolean));
      const short = !step.reviewedRevisit && lineIdx === 0 && S.covered.has(sl.id) && sl.lines.length > 1;  // ordinary question visits stay brief; an explicit reviewed revisit keeps its proof
      const view = showSlideView(sl, { reveal: short ? 99 : lineIdx - 1 });
      if (lineIdx === 0 && step.bridge && !bridgeDone) { el.cite.textContent = step.bridge_fact_ids?.length ? "sources: " + step.bridge_fact_ids.join(", ") : ""; if (!(await speak(step.bridge, run, step.bridge_audio))) return; S.playback.bridgeDone = true; if (!(await waitForLineQuestion({ text: step.bridge }, run))) return; }
      if (!(await playLines(sl, run, view, lineIdx, short ? 1 : sl.lines.length))) return;
      lineIdx = 0; bridgeDone = false; if (run !== S.run) return;
      // A stop's closing statement is narration. Legacy question-shaped check-ins
      // still play, then the next slide starts without chips or a response wait.
      if (sl.checkin?.text && !short) {
        S.atCheckin = true; S.playback.checkin = true; el.cite.textContent = "";
        if (!(await speak(sl.checkin.text, run, sl.checkin.audio))) return;
      }
    }
    await closeFlow(run);
  }

  // Play a slide's deeper reviewed explanation and continue after its audio.
  async function playDeeper(sl, run, view, from = 0) {
    S.raised.add(topicOf(sl)); prefetch(sl.deeper || []); view.setRevealed(99);
    const lines = sl.deeper || [];
    for (let j = from; j < lines.length; j++) {
      if (run !== S.run) return false;
      S.playback = { phase: "deeper", index: S.seg, line: j };
      el.cite.textContent = lines[j].fact_ids?.length ? "sources: " + lines[j].fact_ids.join(", ") : "";
      if (!(await speak(lines[j].text, run, lines[j].audio))) return false;
      S.playback.line = j + 1;
      if (!(await waitForLineQuestion(lines[j], run))) return false;
    }
    S.playback = { phase: "route", index: S.seg, line: sl.lines.length, checkin: true, bridgeDone: true };
    el.cite.textContent = "";
    if (!lines.length && !(await speak("That's everything the material covers on this. Ask me anything specific and I'll check.", run))) return false;
    return run === S.run;
  }
  // Restore a deeper-explanation checkpoint on the correct slide and line.
  // Continue the route only after that explanation completes; web/slide.js:renderSlide restores the visual.
  async function resumeDeeper(origin, run) {
    const sl = S.plan[origin.index]?.slide; if (!sl || run !== S.run) return;
    S.seg = origin.index; const view = showSlideView(sl, { reveal: 99 });
    if (await playDeeper(sl, run, view, origin.line)) playFrom(origin.index + 1, 0);
  }

  // Deliver closing content, then let the customer choose a next step or another question.
  // The selected action comes from the bundle returned by server/app.py:get_bundle; no choice is assumed.
  async function closeFlow(run, line = 0) {
    if (run !== S.run) return;
    S.atCheckin = true; S.playback = { phase: "closing", line };
    const cs = closingSlide();
    if (cs) {
      const view = showSlideView(cs, { reveal: line - 1 });
      if (line === 0 && S.pitch?.advance) { view.setRevealed(0); el.cite.textContent = ""; if (!(await speak(S.pitch.advance, run, S.pitch.advance_audio))) return; S.playback.line = 1; if (!(await waitForLineQuestion({ text: S.pitch.advance }, run))) return; if (!(await playLines(cs, run, view, 1))) return; }
      else if (!(await playLines(cs, run, view, line))) return;
    }
    S.playback = { phase: "closing", line: cs?.lines?.length || 0 };
    showSlideView(heroClose(), { reveal: 99 });
    el.cite.textContent = "";
    const chips = (bundle.ctas || []).map((c) => ({ label: c.label, value: "cta:" + c.id, primary: !!c.primary || c.id === S.pitch?.advance_cta })).concat([{ label: "Not yet", value: "notyet" }, { label: "One more question", value: "question" }]);
    const r = await waitFor(chips, 0); if (run !== S.run) return;
    if (r.value === "question") { if (r.text) handleQuestion(r.text); else listenForQuestion(); return; }
    if (r.value === "__interrupted") return;
    if (r.value === "notyet") { const ok = await speak("Fair enough. Here's a summary of what we covered so you have it when you decide.", run); if (!ok) return; S.cta = "summary"; showHandoff(); return; }
    if (r.value.startsWith("cta:")) await ctaFlow(r.value.slice(4), run);
  }
  // Confirm a configured action selection and show its recap or follow-up option.
  // Take an action ID and run; contact details are submitted separately through server/app.py:run_lead.
  async function ctaFlow(id, run) {
    if (run !== S.run) return;
    const c = (bundle.ctas || []).find((x) => x.id === id); if (!c) return;
    S.cta = c.label;
    const line = ctaLink(c)
      ? `You chose “${c.label}”. ${c.kind === "book" ? "You can open the booking link or request a dealership follow-up from your recap." : "You can open the link from your recap."}`
      : `You chose “${c.label}”. You can leave your details if you would like the dealership to follow up.`;
    const ok = await speak(line, run); if (!ok) return; showHandoff(c);
  }
  // Save the interrupted playback position once, even when the conversation has several questions.
  // This local checkpoint complements the cursor sent to server/runtime_graph.py:run_turn.
  function captureOrigin() { if (!S.conversationOrigin) S.conversationOrigin = { ...S.playback }; }
  // Pause the presentation and invite a question while retaining the exact return position.
  // Wait for words or explicit Continue; questions are sent through server/app.py:run_qa.
  async function listenForQuestion() {
    captureOrigin(); interruptAll({ preservePlanning: openingPlanPending() }); const run = newRun();
    el.cite.textContent = "";
    el.cap.textContent = "What would you like to know?";
    const r = await waitFor([{ label: "Continue demo", value: "continue", primary: true }], 0, { openAnswer: true });
    if (run !== S.run) return;
    if (r.text) handleQuestion(r.text); else if (r.value === "continue") resumeAfterQA();
  }
  // Route a microphone click to live capture, intake, an existing wait or a new question.
  // Use live-voice.js:LiveVoiceClient.startCapture/stopCapture when available; otherwise use the legacy listener.
  function micTap() {
    cancelPostAnswerListen();
    const enabled = live ? !S.voiceMode : S.inputMode !== "voice"; setVoiceMode(enabled);
    if (live) { if (!enabled) live.stopCapture(); else { resumeSession(); live.startCapture(); } return; }
    if (!enabled) { stopListening(); return; }
    resumeSession();
    if (S.intakeOpen) { intakeMic(true); return; }
    if (S.waiter) { listenForTurn(S.waiter); return; }
    listenForQuestion();
  }
  // Offer reply choices after an answer, then resume after a short silent window.
  // Clarification and explicit question solicitation opt out of that deadline.
  async function holdConversation(run, { suggested = null, turn = null, autoResume = true } = {}) {
    const cta = (bundle.ctas || []).find(item => item.id === suggested);
    const choices = [{ label: "Ask another question", value: "question" }, { label: "Continue demo", value: "continue", primary: true }];
    if (cta) choices.push({ label: cta.label, value: "cta:" + cta.id });
    const response = waitFor(choices), owner = S.waiter;
    if (autoResume && owner?.run === run) {
      S.postAnswerListen = { waiter: owner, run, turn, timer: null };
      armPostAnswerListen();
    }
    (el.lead.classList.contains("open") ? el.leadName : el.drawer.classList.contains("open") ? el.q : el.reply).focus({ preventScroll: true });
    const r = await response;
    if (run !== S.run) return;
    if (r.value === "continue" || r.value === "__auto_resume") { el.lead.classList.remove("open"); resumeAfterQA({ automatic: r.value === "__auto_resume" }); }
    else if (r.value.startsWith("cta:")) await ctaFlow(r.value.slice(4), run);
    else if (r.text) handleQuestion(r.text);
    else if (r.value === "question") listenForQuestion();
  }

  // ---------- questions, don't-guess, lead capture ----------
  // Give fast answers a short grace period before playing an acknowledgment.
  // Race that filler with the existing QA promise; server/runtime_graph.py:run_turn is not restarted.
  async function questionResult(qaP, run, turn) {
    const early = await withTimeout(qaP, 250);
    if (run !== S.run || early) return early;
    // Stamp acknowledgment audio separately from useful answer audio.
    // The timestamp is stored on this turn for server/runtime_metrics.py:aggregate, not counted as answer onset.
    S.onFirstAudio = ts => { turn.ack_audio = ts; };
    const filler = speakF(questionAckKey(bundle.fillers), "Give me one moment while I check that for you.", run);
    const ready = qaP.then(result => ({ kind: "answer", result }), error => ({ kind: "error", error }));
    const winner = await Promise.race([ready, filler.then(ok => ({ kind: "filler", ok }))]);
    if (run !== S.run) return null;
    S.onFirstAudio = null;
    if (winner.kind !== "filler") {
      // Cancel only this acknowledgment's output. The question still owns its
      // graph turn and deferred answer; do not interrupt it or await stale TTS.
      cancelSpeech();
      if (winner.kind === "error") throw winner.error;
      return winner.result;
    }
    if (!winner.ok) return null;
    setStatus("thinking", "Checking the approved information");
    return qaP;
  }
  // Handle a customer question or explicit priority correction while preserving the interrupted demo position.
  // Send context and bundle version to server/app.py:run_qa or run_pitch; only the owning run may present the result.
  async function handleQuestion(text, options = {}) {
    if (live && !options.question && explicitContextCorrection(text)) {
      captureOrigin(); interruptAll(); const run = newRun();
      if (!(S.transcript.at(-1)?.role === "user" && S.transcript.at(-1)?.text === text)) addMsg("user", text);
      rememberContext(text, { statedNeed: true });
      S.profile.focus = [...new Set([...parseFocus(text), ...S.profile.focus])]; queueRefinement();
      if (await speak("Thanks—I've noted that priority. I'll use it to tailor the remaining demo.", run)) await holdConversation(run, { autoResume: false });
      return;
    }
    captureOrigin(); interruptAll({ preservePlanning: openingPlanPending() }); const run = newRun(); let jumped = null;
    el.cite.textContent = "";
    const customerQuestion = options.question || text;
    const last = S.transcript.at(-1); if (!(last?.role === "user" && last.text === text)) addMsg("user", text);
    // Keep raw customer wording beyond the short transcript window, without inferring a preference.
    // Clarification replay already retained its question/reply; intake and explicit-answer paths may also own it.
    if (!options.question && text !== S.profile.why && !(S.profile.followup || "").split("\n").includes(text)) {
      S.profile.followup = [S.profile.followup, text].filter(Boolean).join("\n");
    }
    // Create one answer-turn record and send the same scoped payload over live voice or HTTP.
    // live-voice.js:LiveVoiceClient.ask and server/app.py:run_qa return the answer, evidence and navigation decision.
    if (!options.question) S.questions.push(text);
    S.openQuestions.add(customerQuestion);
    const turn = { question: customerQuestion, ...(S.lastListen || { voice_ended: Date.now(), stt_done: Date.now(), via: "unknown" }), qa_done: null, answer_audio: null }; S.lastListen = null; S.turns.push(turn); el.live.textContent = ""; setStatus("thinking", "Checking your question"); el.cap.textContent = "Checking the approved information…";
    S.activeTurn = turn; turn.input_source = turn.via; turn.cancelled = false;
    let r;
    const questionPayload = { question: customerQuestion, history: S.transcript.slice(-8).map((t) => ({ role: t.role, text: t.text })), profile: profileForServer(), input_mode: S.voiceMode ? "voice" : "text", slide_id: cur?.slide?.id || null, session_id: S.sessionId, demo_version: bundle.version, voice_ended_at: turn.voice_ended, cursor: { ...S.playback }, ...(options.skipBank ? { skip_bank: true } : {}) };
    const qaP = live?.ready ? live.ask(questionPayload) : api.qa(questionPayload);
    try {
      // Wait for that question result and convert transport failure into an honest, open customer turn.
      // The request belongs to server/runtime_graph.py:run_turn; cancelled runs must not narrate a late response.
      r = await questionResult(qaP, run, turn);
      if (run !== S.run || !r) return;
    } catch (e) {
      turn.qa_done = Date.now(); if (run !== S.run || e.name === "AbortError") { turn.cancelled = true; return; } turn.error = true; turn.failed = true;
      // Record when the transport-failure explanation actually starts playing.
      // The turn remains marked failed, so server/runtime_metrics.py:aggregate can separate it from useful answers.
      S.onFirstAudio = (ts) => { turn.answer_audio = ts; };
      if (!(await speak("I couldn't reach my notes just now. You can ask again, or choose Continue when you are ready.", run))) return;
      turn.delivery_done = Date.now(); S.activeTurn = null;
      S.escalations.push(`error answering: "${customerQuestion}"`); S.unresolved.add("question"); await holdConversation(run, { turn }); return;
    }
    // Store returned classification, tool and timing metadata without treating the flag as a quality grade.
    // server/runtime_graph.py:run_turn supplies these fields; server/runtime_metrics.py:aggregate later groups their latency.
    if (run !== S.run) return;
    turn.qa_done = Date.now(); turn.from_bank = !!r.from_bank; turn.route = r.route || null; turn.answered = !!r.answered; turn.failed = !!(r.provider_failed || r.timed_out);
    turn.response_kind = r.clarifying_question ? "clarification" : r.answered ? "answer" : "decline";
    turn.plain_language_substitutions = r.plain_language_substitutions || [];
    turn.tool_count = r.tool_count || r.tool_results?.length || 0; turn.tool_results = (r.tool_results || []).map(tool => ({ type: tool.type || tool.tool, ok: tool.ok, source_url: tool.source_url, error: tool.error })); turn.graph_timings = r.graph_timings || {}; turn.answer_route = turn.tool_count ? "tool" : r.from_bank ? "cache" : "model";
    // Attach the first-audio callback to this answer turn before presenting its result.
    // Only real audio calls it; server/runtime_metrics.py:aggregate keeps caption fallback separate.
    S.onFirstAudio = (ts) => { turn.answer_audio = ts; };
    // A clarification is the answer for this turn. Do not speak a provisional claim or ask it twice.
    // Handle a clarification as the current turn's response, then retain the customer's reply as context.
    // Replay the original question with FAQ reuse skipped through server/app.py:run_qa.
    if (r.clarifying_question) {
      el.cite.textContent = "";
      const a = await askAndListen(r.clarifying_question, run, 10000, r.answer === r.clarifying_question ? r.audio : null, r.answer === r.clarifying_question ? r : null);
      if (run !== S.run) return;
      turn.delivery_done = Date.now(); S.activeTurn = null;
      if (a) { rememberContext(`${r.clarifying_question} ${a}`); handleQuestion(a, { question: customerQuestion, skipBank: true }); }
      else await holdConversation(run, { autoResume: false });
      return;
    }
    if (!r.answered) {
      // Present a supported limitation or service refusal and retain the question as unresolved.
      // The server answer from server/runtime_graph.py:run_turn is spoken before optional follow-up and explicit waiting.
      if (r.escalate) S.escalations.push(r.escalate);
      if (r.topic && r.topic !== "other") S.raised.add(r.topic);
      S.unresolved.add(r.topic || "question"); el.cite.textContent = "";
      const decline = live && r.answer ? r.answer : "I don't have that answer in the approved information. I've kept it as an open question. You can ask something else, continue when you are ready, or request help from the dealership.";
      if (!(await speak(decline, run, live ? r.audio : null, live ? r : null))) return;
      turn.delivery_done = Date.now(); S.activeTurn = null;
      showLeadPrompt("unknown", customerQuestion); await holdConversation(run, { turn }); return;
    }
    const from = cur?.slide?.id || null;
    jumped = r.route === "jump" && r.slide_id && r.slide_id !== from ? slides.find((s) => s.id === r.slide_id) || null : null;
    if (jumped) {
      // Runtime answers start with their evidence. The slide heading explains
      // Show the server-selected evidence slide without changing the saved route position.
      // web/slide.js:renderSlide displays the jump; runtime answers avoid the older spoken jump prelude.
      // the jump without adding a spoken prelude before useful answer audio.
      if (bundle.runtime?.version !== 1) {
        S.onFirstAudio = null;
        if (!(await speakF("bridge_to_custom", "Let me show you where that is.", run))) return;
      }
      showSlideView(jumped, { reveal: 99 }); S.covered.add(jumped.id); S.jumps.push({ from, to: jumped.id, question: text });
      // Start measuring the substantive answer again after any legacy slide-jump bridge.
      // The separate timestamp lets server/runtime_metrics.py:aggregate avoid counting bridge audio as the answer.
      S.onFirstAudio = (ts) => { turn.answer_audio = ts; };
    } else cur?.view.setRevealed(99);
    if (r.callout_id) cur?.view.highlight(r.callout_id);
    const conditionIds = r.condition_fact_ids || r.condition_evidence?.map((f) => f.id) || r.facts?.filter((f) => f.runtime_role === "condition").map((f) => f.id) || [];
    // Show primary citations separately from facts that only establish a required condition.
    // The IDs come from server/runtime_graph.py:run_turn; a condition donor does not become a product claim.
    el.cite.textContent = [r.fact_ids?.length ? "sources: " + r.fact_ids.join(", ") : "", conditionIds.length ? "conditions: " + [...new Set(conditionIds)].join(", ") : ""].filter(Boolean).join(" · ");
    if (r.escalate) S.escalations.push(r.escalate); if (r.topic && r.topic !== "other") S.raised.add(r.topic);
    if (r.from_bank) addMsg("note", "answered from the FAQ bank — no model call");
    if (!(await speak(r.answer, run, r.audio, r))) return;
    turn.delivery_done = Date.now(); S.activeTurn = null;
    if (r.offer_callback) showLeadPrompt("question", customerQuestion);
    S.resolved.add(r.topic || "question"); S.unresolved.delete(r.topic || "question"); S.openQuestions.delete(customerQuestion);
    // A suggested CTA remains an explicit customer choice; silence only resumes narration.
    await holdConversation(run, { suggested: r.cta, turn });
  }
  // Open the optional dealership contact form with wording appropriate to the reason.
  // Local fields are prefilled only; server/app.py:run_lead is called only after form submission.
  function showLeadPrompt(reason, question = "") {
    if (S.leads.length || (S.leadPromptShown && reason !== "unknown" && reason !== "requested")) return;
    S.leadFormId = (S.leadFormId || 0) + 1;
    S.leadPromptShown = true; S.leadReason = reason; S.leadQuestion = question || "test drive";
    el.leadName.value = S.profile.name || ""; el.leadPhone.value = ""; el.leadError.textContent = "";
    const callback = reason === "unknown" || reason === "requested";
    el.lead.querySelector("h3").textContent = callback ? "Would you like the dealership to follow up?" : "Would you like to try it in person?";
    el.leadForm.querySelector("button[type=submit]").textContent = callback ? "Request a callback" : "Arrange a test drive";
    el.leadForm.querySelector("button[type=submit]").disabled = false;
    el.leadCopy.textContent = reason === "unknown" ? "I don't have that answer in the approved sources. Leave your details and the dealership can answer it directly." : reason === "requested" ? "Share your details if you would like help with the questions we discussed." : "Share your details if you would like the dealership to arrange a test drive.";
    el.lead.classList.add("open");
    if (S.postAnswerListen) { clearTimeout(S.postAnswerListen.timer); S.postAnswerListen.timer = null; S.postAnswerListen.heldForLead = true; }
  }
  // Validate a submitted contact form and save consent, the question and customer context.
  // web/app.js:renderPlay connects api.lead to server/app.py:run_lead; failures keep the form open for retry.
  async function saveLeadForm() {
    const name = el.leadName.value.trim(); const raw = el.leadPhone.value.replace(/[\s-]/g, ""); const m = raw.match(PHONE);
    if (!m) { el.leadError.textContent = "Enter a valid 10-digit Indian mobile number."; el.leadPhone.focus(); return; }
    const sessionId = S.sessionId, formId = S.leadFormId;
    const btn = el.leadForm.querySelector("button[type=submit]"); btn.disabled = true; el.leadError.textContent = "Saving…";
    let ok = true; try { await api.lead({ phone: m[1], question: S.leadQuestion || "test drive", profile: { ...profileForServer(), name: name || S.profile.name }, consent: true, consent_text: CONSENT, session_id: S.sessionId }); } catch (e) { ok = false; }
    if (S.sessionId !== sessionId || S.leadFormId !== formId || !el.lead.classList.contains("open")) return;
    btn.disabled = false;
    if (!ok) { el.leadError.textContent = "Couldn't save that just now. Please try once more."; return; }
    if (name) S.profile.name = name; S.leads.push({ phone: m[1], question: S.leadQuestion || "test drive" }); S.escalations.push(`callback requested on ${m[1]}: "${S.leadQuestion || "test drive"}"`);
    dismissLeadPrompt(); addMsg("note", "Follow-up request saved for the dealership");
  }
  // Build the compact customer profile sent with runtime requests.
  // Return stated text, focus, server customer state and language for server/app.py:run_qa and run_pitch.
  function profileForServer() { return { name: S.profile.name, why: S.profile.why, followup: S.profile.followup, focus: S.profile.focus, customer_state: S.pitch?.customer_state, language: bundle.language }; }
  // Wrap the supplied TTS callback so new audio follows the currently selected bundle language.
  // Return a URL promise or null; web/app.js:renderPlay provides the language-aware server/app.py:run_tts call.
  const _origTts = api.tts; api.tts = (text) => _origTts ? api.tts_lang ? api.tts_lang(text, bundle.language) : _origTts(text) : Promise.resolve(null);
  // Resolve a known image reference from the bundle into its media URL.
  // Return null for unavailable or video-shot references; web/slide.js:renderSlide then uses the reviewed fallback.
  function mediaUrlFor(v) { if (!v) return null; for (const im of bundle.media?.images || []) if (im.id === v.ref) return im.url; const src = v.source_id; for (const vid of bundle.media?.videos || []) if (v.kind === "shot" && src && vid.url.includes(src)) return null; return null; }
  // Clear question highlighting and return to the single saved playback checkpoint after a short bridge.
  // The bridge may use live-voice.js:LiveVoiceClient.speak; resumePlayback restores the route rather than the jump slide.
  async function resumeAfterQA({ automatic = false } = {}) {
    const origin = S.conversationOrigin || { ...S.playback }; S.conversationOrigin = null;
    if (cur) cur.view.highlight(null);
    const run = newRun();
    if ((!automatic || bundle.fillers?.back_to_demo?.audio) && !(await speakF("back_to_demo", "Let's return to where we paused.", run))) return;
    resumePlayback(origin, run);
  }
  // Dispatch a saved phase and line checkpoint to its matching playback function.
  // Ready closing refinements may add reviewed steps from server/agents/pitch.py:plan_pitch before returning to closing.
  function resumePlayback(origin, run = newRun()) {
    if (run !== S.run) return;
    if (origin.phase === "route") { playFrom(origin.index, origin.checkin ? S.plan[origin.index]?.slide.lines.length || 0 : origin.line, origin.checkin || origin.bridgeDone); return; }
    if (origin.phase === "deeper") { resumeDeeper(origin, run); return; }
    if (origin.phase === "closing") {
      if (S.pendingRefinement?.status === "ready") {
        const next = S.plan.length;
        return applyUpcomingPlan(next, run).then(ok => {
          if (!ok || run !== S.run) return;
          if (S.plan.length > next) return playFrom(next, 0);
          return closeFlow(run, origin.line);
        });
      }
      closeFlow(run, origin.line); return;
    }
    if (origin.phase === "intake") { runIntake(); return; }
    startAfterIntake(run, S.profile.why, origin);
  }

  // ---------- intake + standard opening + pitch plan ----------
  // Wait for intake text, keeping early spoken input queued until the prompt is ready.
  // Return one answer for this run; live-voice.js:LiveVoiceClient handles persistent microphone events separately.
  function intakeWait(run) {
    return new Promise((res) => {
      // Finish intake once, clear its resolver and stop the legacy listening attempt.
      // The returned customer text later becomes profile input to server/app.py:run_pitch.
      let done = false; const fin = (t) => { if (done) return; done = true; S.intakeResolver = null; stopListening(); res(t); }; S.intakeResolver = fin; el.inHeard.textContent = "";
      if (S.pendingIntakeAnswer) { const queued = S.pendingIntakeAnswer; S.pendingIntakeAnswer = ""; fin(queued); return; }
      if (live) { setMicUI(live.mic); el.inFallback.classList.add("open"); if (!live.mic) setTimeout(() => el.inText.focus(), 50); return; }
      // For legacy voice intake, show interim text and accept a result only for this run.
      // Empty capture reveals typing instead; web/app.js:renderPlay supplies the optional server transcription callback.
      if (S.inputMode === "voice" && canListen() && !S.micDenied) { el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; listen({ timeout: 10000, onInterim: (t) => { el.inHeard.textContent = t; } }).then((t) => { if (done || run !== S.run) return; if (t) fin(t); else { el.inState.textContent = "Tap the mic to try again, or type below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); } }); }
      else { el.inState.textContent = "Type your answer below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); }
    });
  }
  // Handle the intake microphone button and deliver captured words only to the same pending intake.
  // Live sessions delegate to live-voice.js:LiveVoiceClient through micTap; legacy capture returns text here.
  async function intakeMic(alreadyEnabled = false) { if (live) { micTap(); return; } if (!alreadyEnabled) { const enabled = S.inputMode !== "voice"; setVoiceMode(enabled); if (!enabled) { stopListening(); return; } } if (!S.intakeResolver) return; cancelSpeech(); const fin = S.intakeResolver; el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; const t = await listen({ timeout: 10000, onInterim: (x) => { el.inHeard.textContent = x; } }); if (t && S.intakeResolver === fin) fin(t); else if (S.intakeResolver === fin) { el.inState.textContent = "Tap the mic to try again, or type below"; el.inFallback.classList.add("open"); } }
  // Extract a name only from a few explicit self-introduction patterns in customer text.
  // Return a capitalized name or an empty string for the profile sent to server/app.py:run_pitch.
  function parseName(t) { let m = t.match(/(?:my name is|myself|name's|call me|mera naam|naam)\s+([A-Za-zऀ-ॿ][a-zऀ-ॿ]+)/i); if (m) return cap(m[1]); m = t.match(/^([A-Za-z][a-z]+)\s+(?:here|speaking|bol raha|bol rahi)\b/i); if (m) return cap(m[1]); return ""; }

  // Capitalize the first character of an extracted name and return the formatted string.
  // The result is a presentation field in the profile saved by server/app.py:save_session.
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  // Map whole customer phrases to known intake and slide topics without ranking preferences.
  // Return at most four local route hints; server/agents/pitch.py:plan_pitch still evaluates the full context.
  function parseFocus(t) {
    // Mentioned topics guide routing; they never establish a stated or ranked preference.
    // Slide titles contain generic words (e.g. "with") and are not customer vocabulary.
    // Normalize phrase spelling and punctuation for exact whole-phrase topic matching.
    // Return comparison text only; it is not a product-evidence transformation in server/knowledge.py:retrieve.
    const norm = (s) => String(s || "").normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}\p{M}]+/gu, " ").trim();
    const text = ` ${norm(t)} `;
    const aliases = {
      performance: ["automatic", "engine", "engines", "gearbox", "gearboxes", "transmission"],
      practicality: ["boot", "luggage", "stroller"],
      ownership: ["running cost", "running costs", "cost of ownership", "price", "pricing", "warranty"],
    };
    const terms = new Map();
    // Collect a topic key, its visible labels and a small fixed alias list.
    // The map feeds local focus matching; server/agents/pitch.py:plan_pitch receives the resulting keys.
    const add = (key, labels = []) => {
      if (!key) return;
      terms.set(key, [...(terms.get(key) || []), key, ...labels, ...(aliases[key] || [])]);
    };
    for (const c of bundle.intake?.chips || []) add(c.key, String(c.label || "").split(/\s*[&/|]\s*/));
    for (const sl of library()) add(topicOf(sl));
    return [...terms].filter(([, values]) => values.some((value) => {
      const phrase = norm(value); return phrase && text.includes(` ${phrase} `);
    })).map(([key]) => key).slice(0, 4);
  }
  // Race a promise against a local time limit and return null when that wait expires.
  // This does not cancel the underlying server/app.py:run_pitch or run_qa request; ownership checks still apply.
  function withTimeout(p, ms) { return Promise.race([p, new Promise((res) => setTimeout(() => res(null), ms))]); }

  // Ask the opening preference question and save only the customer's actual response.
  // Start server/app.py:run_pitch while acknowledgment or overview audio plays, then continue the opening flow.
  async function runIntake() {
    const run = newRun(); S.browseOnly = false; S.playback = { phase: "intake", line: 0 }; S.intakeOpen = true; el.intake.classList.add("open"); el.inFallback.classList.add("open");
    el.cite.textContent = "";
    showSlideView(heroOpen(), { reveal: 99 });
    const q1 = bundle.intake?.q1 || `What matters most to you as you consider ${bundle.product?.name || "this"}?`;
    el.inState.textContent = guide;
    const ok = await speak(q1, run, bundle.intake?.audio?.q1); if (!ok && (!live || run !== S.run)) return;
    const a1 = await intakeWait(run); if (run !== S.run) return;
    if (a1) { addMsg("user", a1); S.profile.name = parseName(a1); S.profile.why = a1; S.profile.focus = parseFocus(a1); }
    el.intake.classList.remove("open"); S.intakeOpen = false;
    const ack = live ? "Thanks—that helps me focus the demo. While I tailor it, here's a quick overview of the car." : a1 ? (S.profile.name ? pick([`Lovely to meet you, ${S.profile.name}.`, `Thanks, ${S.profile.name}.`]) : "Thanks for that.") + " Let me set up what we're deciding, then I'll show you the result first." : "No problem — let me set up what we're deciding, then show you the result first.";
    // Start one version-pinned pitch request when intake provided usable context.
    // server/app.py:run_pitch runs in parallel with the opening; live mode requests text planning without extra voice generation.
    S.pitchPromise = (a1 && api.pitch) ? withTimeout(api.pitch({ profile: profileForServer(), refine: false, input_mode: S.voiceMode ? "voice" : "text", session_id: S.sessionId, demo_version: bundle.version, ...(live ? { voice_it: false } : {}) }).catch(() => null), live ? 12000 : 60000) : null;
    S.playback = { phase: "opening", index: 0, line: 0 };
    const fa = live ? { text: ack, audio: bundle.runtime?.overview_ack?.audio } : a1 ? F("ack_with_context", ack) : F("ack_no_context", ack); const ok2 = await speak(fa.text, run, fa.audio); if (!ok2) return;
    if (!live) { const okF = await playIntroFilm(run); if (!okF) return; }
    await startAfterIntake(run, a1);
  }
  // Continue from the opening checkpoint while keeping its existing personalization request alive.
  // Use the recorded overview or fixed opening, then accept a valid route from server/app.py:run_pitch or use the deck fallback.
  async function startAfterIntake(run = newRun(), a1 = S.profile.why, checkpoint = { phase: "opening", index: 0, line: 0 }) {
    // Keep the same planning request alive across questions during the opening.
    if (!S.browseOnly && !S.pitchPromise) S.pitchPromise = api.pitch ? withTimeout(api.pitch({ profile: profileForServer(), refine: false, input_mode: S.voiceMode ? "voice" : "text", session_id: S.sessionId, demo_version: bundle.version, ...(live ? { voice_it: false } : {}) }).catch(() => null), live ? 12000 : 60000) : Promise.resolve(null);
    if (["opening", "intake", "overview"].includes(checkpoint.phase)) {
      const overview = live && !S.browseOnly ? bundle.runtime?.overview : null;
      // Show the overview once, using its cited slide and recorded speech while planning proceeds.
      // web/slide.js:renderSlide displays the selected image; completed audio determines when this overview finishes.
      if (overview?.text) {
        if (!S.overviewPlayed) {
          S.playback = { phase: "overview", line: 0 };
          const visual = slides.find(slide => slide.id === overview.slide_id) || opening()[0] || heroOpen();
          showSlideView(visual, { reveal: 99 }); el.cite.textContent = overview.fact_ids?.length ? "sources: " + overview.fact_ids.join(", ") : "";
          if (!(await speak(overview.text, run, overview.audio))) return;
          S.overviewPlayed = true;
        }
      } else if (!(await playOpening(run, checkpoint.index || 0, checkpoint.line || 0))) return;
    }
    if (S.browseOnly) { buildRoute(null); playFrom(0, 0); return; }
    // At the end of the opening, make a bounded decision about the available personalized route.
    // The promise came from server/app.py:run_pitch; a late result cannot silently replace a route already chosen.
    let plan = S.pitch;
    if (!plan && !(live && S.planningDecided)) {
      S.playback = { phase: "planning", line: 0 };
      plan = await withTimeout(S.pitchPromise, 150); if (run !== S.run) return;
      if (!plan && !live) { if (!(await speakF("still_working", "One moment — I'm tailoring this to what you told me.", run))) return; plan = await withTimeout(S.pitchPromise, 2500); if (run !== S.run) return; }
    }
    S.planningDecided = true;
    if (live && plan && !plan.route?.some(step => library().some(slide => step.slide_id === slide.id || step.segment_id === slide.segment_id))) plan = null;
    S.personalized = !!plan;
    S.pitch = plan || null;
    if (!plan) addMsg("note", "personalisation was not ready in the opening window — continuing on the stable approved route");
    if (plan) {
      // Enter a valid live route directly, while older bundles retain their extra decision and custom sections.
      // server/agents/pitch.py:plan_pitch provides the plan; this branch controls delivery, not factual validation.
      S.profile.focus = [...new Set([...(plan.focus_topics || []), ...S.profile.focus])];
      // Live Explore already introduced the product while the plan was prepared.
      // Enter its approved route directly; validated replacement lines and inline
      // bridges carry the context, without replaying a planning monologue or extras.
      if (live) { buildRoute(plan); playFrom(0, 0); return; }
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
      if (!(await (live ? speak("I couldn't finish tailoring the route just now. Let's explore the reviewed demo, and you can guide me as we go.", run) : speakF("lets_go", "Let's take a closer look.", run)))) return;
    }
    buildRoute(S.pitch); playFrom(0, 0);
  }
  // Present older custom pitch batches as temporary evidence slides, once per visit.
  // Return completion for the current run; web/slide.js:renderSlide displays the cited batch while speak handles audio.
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
  // Skip preference intake and enter the reviewed browsing route.
  // This clears the old wait and skips personalization; content still comes from server/app.py:get_bundle.
  function skipIntake() {
    interruptAll(); el.intake.classList.remove("open"); S.intakeOpen = false; S.intakeResolver = null; S.pendingIntakeAnswer = ""; S.browseOnly = true;
    const run = newRun(); S.playback = { phase: "opening", index: 0, line: 0 }; showSlideView(heroOpen(), { reveal: 99 });
    playIntroFilm(run).then((ok) => { if (ok) startAfterIntake(run); });
  }

  // ---------- handoff ----------
  // Calculate a bounded engagement score from local questions, progress and explicit next steps.
  // Return a rough score for server/app.py:save_session, not a verified prediction of customer purchase intent.
  function intentScore() { let s = 20; s += Math.min(30, S.questions.length * 8); s += S.resolved.size * 8; s += S.seg >= S.plan.length - 1 ? 15 : 0; if (S.cta && S.cta !== "summary") s += 30; if (S.leads.length) s += 10; s -= S.unresolved.size * 5; return Math.max(5, Math.min(98, s)); }
  // Assemble the current visit into a report ready to save, with route, timing, questions and transcript.
  // Return data for server/app.py:save_session; constructing this object does not itself save or summarize it.
  function sessionRecord() {
    const now = sessionNow();
    const visited = [...S.visited, ...(cur ? [{ slide_id: cur.slide.id, kind: cur.slide.kind, seconds: Math.round((now - cur.enteredAt) / 100) / 10 }] : [])];
    const uspsCovered = [...new Set(S.plan.slice(0, S.seg + 1).flatMap((st) => st.slide.usp_ids || []))];
    return { id: S.sessionId, ended: S.ended, input_mode: S.voiceMode ? "voice" : "text", profile: S.profile, customer_state: S.pitch?.customer_state, personalized: !!S.personalized, bundle_version: bundle.version || null, runtime_version: bundle.runtime?.version || 0, provider: bundle.voice?.provider || "browser", interruptions: S.interruptions, route: S.plan.map((st) => st.slide.segment_id || st.slide.id), slides: S.plan.map((st) => st.slide.id), slides_visited: visited, covered: [...S.covered], jumps: S.jumps, turns: S.turns, usps_covered: uspsCovered, questions: S.questions, escalations: S.escalations, leads: S.leads, resolved: [...S.resolved], unresolved: [...S.unresolved], cta: S.cta, intent: intentScore(), drop_point: S.plan[S.seg]?.slide.title, minutes: Math.round((now - S.started) / 6000) / 10, transcript: S.transcript };
  }
  // Reopen a completed visit while excluding the idle recap interval from its duration.
  // Update local clocks and hide the recap; later server/app.py:save_session calls use the resumed record.
  function resumeSession() {
    if (S.endedAt === null) return;
    const idle = Date.now() - S.endedAt;
    S.started += idle; if (cur) cur.enteredAt += idle;
    S.endedAt = null; S.ended = false; el.handoff.classList.remove("open");
  }
  // Stop capture, freeze the visit clock, build a recap and request its save.
  // server/app.py:save_session receives the report through api.saveSession; local recap display does not prove server persistence.
  function showHandoff(c) {
    if (S.endedAt === null) S.endedAt = Date.now();
    S.ended = true;
    live?.stopCapture();
    setStatus("idle", "Demo complete");
    el.lead.classList.remove("open");
    const session = sessionRecord();
    const explored = [...new Set(session.slides_visited.map((visit) => slides.find((slide) => slide.id === visit.slide_id)).filter((slide) => slide && !["hero_open", "hero_close", "closing"].includes(slide.kind)).map((slide) => slide.title).filter(Boolean))];
    const openQuestions = [...S.openQuestions];
    const shared = [...new Set([S.profile.why, ...S.profile.stated_needs].filter(Boolean))];
    const actionUrl = ctaLink(c);
    const externalAction = actionUrl ? h("div", {}, h("a", { class: "btn primary sm", href: actionUrl, target: "_blank", rel: "noopener noreferrer", "aria-label": `${c.label} (opens in a new tab)` }, c.label), h("p", { class: "sub" }, "Opens in a new tab.")) : null;
    // Build a small recap section from a heading and its child elements.
    // Return a DOM node using web/api.js:h for priorities, explored topics, open questions or next steps.
    const section = (title, children) => h("div", { class: "kvbox" }, h("h5", {}, title), ...children);
    // Render the recap from actual customer priorities, visited slides and unresolved questions.
    // The DOM comes from web/api.js:h; server/app.py:save_session separately stores the same visit record.
    el.handoffBox.replaceChildren(h("div", { class: "recap-mark" }, icon("check-circle", { size: 24 })), h("h2", {}, "Your recap"), h("p", { class: "sub" }, bundle.product?.name || bundle.name),
      h("div", { class: "grid2" },
        shared.length ? section("What matters to you", shared.map((text) => h("p", {}, text))) : null,
        section("What you explored", [explored.length ? h("ul", {}, explored.map((title) => h("li", {}, title))) : h("p", {}, "We haven't explored the details yet.")]),
        section("Questions still open", [openQuestions.length ? h("ul", {}, openQuestions.map((question) => h("li", {}, question))) : h("p", {}, S.questions.length ? "No unanswered questions noted." : "No questions raised yet.")]),
        section("Your next step", [S.leads.length ? h("p", {}, `You requested a dealership follow-up about “${S.leads.at(-1).question}”.`) : h("div", {},
          c ? h("p", {}, `You selected “${c.label}”.${actionUrl ? "" : " You can leave your details if you would like the dealership to follow up."}`) : h("p", {}, "Take your time. A dealership follow-up is optional."),
          // Offer a follow-up form unless the selected next step is only an external information link.
          // Clicking opens local consent fields; server/app.py:run_lead is still deferred until explicit submission.
          actionUrl && c.kind === "link" ? null : h("button", { class: "btn ghost sm", onclick: () => showLeadPrompt("requested", openQuestions[0] || S.questions.at(-1) || c?.label || "test drive") }, "Request dealership follow-up")), externalAction])),
      h("div", { class: "actions", style: "display:flex;gap:10px;margin-top:14px" },
        // Wire Done to hide the recap, request another save and speak a closing acknowledgment.
        // api.saveSession targets server/app.py:save_session; a caught save failure is not surfaced by this button.
        h("button", { class: "btn primary", onclick: () => { el.handoff.classList.remove("open"); api.saveSession(sessionRecord()).catch(() => {}); const run = newRun(); speak("Thanks for your time. You can ask anything else whenever you are ready.", run); } }, "Done"),
        // Wire Back to reopen this visit and invite further questions.
        // Live capture restarts through live-voice.js:LiveVoiceClient; the existing session ID is retained.
        h("button", { class: "btn ghost", onclick: () => { resumeSession(); if (live) { startLive(); listenForQuestion(); } else { const run = newRun(); speak("What else would you like to explore?", run).then((ok) => { if (ok) listenForQuestion(); }); } } }, "Back to the demo")));
    el.handoff.classList.add("open"); api.saveSession(session).catch(() => {});
  }

  // Use a parent fullscreen route if provided, otherwise toggle browser fullscreen for the player.
  // The optional callback comes from the mounting page, such as web/app.js:renderPlay.
  function toggleFullscreen() {
    if (api.onFullscreenRoute) { api.onFullscreenRoute(); return; }
    const target = root;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else (target.requestFullscreen ? target.requestFullscreen() : Promise.reject()).catch(() => {});
  }

  // ---------- intro film (skippable; the hero slide stays underneath) ----------
  // Play an optional opening film once, with explicit skip and interruption handling.
  // Return completion to the opening flow; its published URL comes from server/app.py:get_bundle.
  async function playIntroFilm(run) {
    const iv = bundle.intro_video;
    if (!iv || !iv.url || iv.enabled === false || S.introPlayed) return run === S.run;
    S.introPlayed = true;
    const ok = await speakF("before_video", "First, here's a quick film to bring it to life. Then I'll walk you through it around what you just told me.", run);
    if (!ok) return false;
    const v = el.film; v.src = iv.url; v.muted = S.muted; v.currentTime = 0; el.stage.classList.add("film-on");
    setStatus("idle", "Playing the film"); el.cap.textContent = ""; el.cite.textContent = "";
    // Show a film-skip button that sets a local flag for the playback guard.
    // The button is built with web/api.js:h; it skips only this film rather than choosing a customer action.
    el.chips.replaceChildren(h("button", { class: "chip", onclick: () => { S.skipFilm = true; } }, "Skip the film"));
    const done = await new Promise((res) => {
      // Settle film playback once and clear its polling and duration guards.
      // The result returns to playIntroFilm; no narration is requested from server/app.py:run_tts by this helper.
      let fin = false, guard = null, capT = null; const end = (x) => { if (!fin) { fin = true; if (guard) clearInterval(guard); if (capT) clearTimeout(capT); res(x); } };
      // Treat film end or playback failure as permission to move past this optional film.
      // The remaining guards stop an obsolete run; server/app.py:get_bundle supplied the film metadata.
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
  // Pause the current phase or invoke its saved resume action after explicit customer input.
  // Output interruption reaches live-voice.js:LiveVoiceClient while pending opening planning may be preserved.
  function togglePause() {
    if (S.paused) { resumeSession(); S.paused = false; el.pauseBtn.replaceChildren(icon("pause", { size: 18 })); el.pauseBtn.classList.remove("on"); const resume = S.resume; S.resume = null; if (resume) resume(); return; }
    const origin = { ...S.playback }, intake = S.intakeOpen, conversation = !!S.conversationOrigin;
    interruptAll({ preservePlanning: openingPlanPending() }); S.paused = true; el.pauseBtn.replaceChildren(icon("play", { size: 18 })); el.pauseBtn.classList.add("on"); setStatus("idle", "Paused"); el.cap.textContent = "Paused — press play to continue.";
    // Capture a resume action that returns to intake, conversation or the saved playback phase.
    // This closure runs only on explicit resume; live-voice.js:LiveVoiceClient does not advance the route itself.
    S.resume = () => { if (intake) runIntake(); else if (conversation) holdConversation(newRun(), { autoResume: false }); else resumePlayback({ ...origin, checkin: false }); };
  }
  // Stop the active demo, clear intake and show a summary instead of continuing narration.
  // showHandoff requests persistence through server/app.py:save_session.
  function stopDemo() { interruptAll(); S.paused = false; el.pauseBtn.replaceChildren(icon("pause", { size: 18 })); el.pauseBtn.classList.remove("on"); el.intake.classList.remove("open"); S.intakeOpen = false; setStatus("idle", "Stopped"); el.cap.textContent = "Stopped."; S.cta = S.cta || "summary"; showHandoff(); }

  // ---------- lifecycle ----------
  // Start over with a fresh session ID, empty visit history and newly created live connection.
  // Destroy the old slide and capture before intake; live-voice.js:LiveVoiceClient.close ends the previous transport.
  function restart() { interruptAll(); live?.close(); S.conversationOrigin = null; S.openQuestions.clear(); S.playback = { phase: "intake", line: 0 }; S.pendingIntakeAnswer = ""; S.pendingPromptAnswer = ""; S.promptRun = null; S.overviewPlayed = false; S.planningDecided = false; S.browseOnly = false; S.paused = false; S.resume = null; el.pauseBtn.replaceChildren(icon("pause", { size: 18 })); el.pauseBtn.classList.remove("on"); S.customPlayed = false; S.introPlayed = false; S.skipFilm = false; S.pitchPromise = null; el.handoff.classList.remove("open"); el.lead.classList.remove("open"); S.questions.length = 0; S.transcript.length = 0; S.escalations.length = 0; S.leads.length = 0; S.visited.length = 0; S.covered.clear(); S.jumps.length = 0; S.turns.length = 0; S.lastListen = null; S.onFirstAudio = null; S.sessionId = newSessionId(); S.ended = false; S.endedAt = null; S.resolved.clear(); S.unresolved.clear(); S.raised.clear(); S.cta = null; S.pitch = null; S.plan = []; S.leadPromptShown = false; S.leadQuestion = ""; S.started = Date.now(); S.profile = { name: "", why: "", followup: "", focus: [], stated_needs: [] }; el.thread.replaceChildren(); if (cur) { cur.view.destroy(); cur = null; } el.stack.replaceChildren(); createLive(); startLive(); renderProgress(); runIntake(); }
  // Expose a simple pause method for callers without toggling an already paused demo back on.
  // web/app.js:renderPlay receives this method from mountPlayer.
  function pause() { if (!S.paused) togglePause(); }
  // Return the current route, line, customer context and recent questions for surrounding UI tools.
  // This is a local snapshot exposed by mountPlayer to callers such as web/app.js:renderPlay.
  function context() { const st = S.plan[S.seg]; return { customer_state: S.pitch?.customer_state, route: S.plan.map((x) => x.slide.id), slide: cur?.slide?.id, segment: st?.slide.segment_id, segment_title: st?.slide.title, line_index: S.line, line_text: st?.slide.lines?.[S.line]?.text, bridge: st?.bridge, questions: S.questions.slice(-5), profile: S.profile, escalations: S.escalations.slice(-5), leads: S.leads }; }
  // Close live capture when the page leaves and make a best-effort report beacon if conversation text was recorded.
  // web/app.js:renderPlay provides api.beacon targeting server/app.py:save_session; delivery is not guaranteed.
  const onHide = () => { live?.close(); if (S.transcript.length && api.beacon) { try { api.beacon(sessionRecord()); } catch (e) {} } };
  window.addEventListener("pagehide", onHide);
  // Remove observers and listeners, cancel active work, release preloads and destroy the player DOM.
  // web/app.js:renderPlay calls this lifecycle method when navigating away or mounting another demo.
  function destroy() { dockObserver?.disconnect(); window.removeEventListener("pagehide", onHide); interruptAll(); live?.close(); for (const media of S.preloads) { try { media.removeAttribute("src"); media.load(); } catch (e) {} } S.preloads.length = 0; if (cur) cur.view.destroy(); root.remove(); }

  // Initialize visible actions, mute state and the hero slide before starting any demo flow.
  // web/slide.js:renderSlide supplies the view; the welcome buttons below choose when interaction starts.
  renderCtas();
  updateMuteUi();
  showSlideView(heroOpen(), { reveal: 99 });
  // Offer guided Explore or self-paced Browse and start capture only after a welcome-button click.
  // Both paths use the API callbacks from web/app.js:renderPlay, then select intake or its explicit skip.
  const voiceChoice = h("label", { class: "pl-voice-choice" }, h("span", { class: "pl-voice-choice-label" }, "Voice mode"),
    el.voiceMode = h("input", { type: "checkbox", role: "switch", checked: S.voiceMode, "aria-label": "Voice mode" }),
    h("span", { class: "pl-voice-choice-caption" }, `Talk to ${guide}. You can also type at any time.`));
  const begin = (browse) => { setVoiceMode(el.voiceMode.checked); startBtn.remove(); startLive(); if (browse) skipIntake(); else runIntake(); };
  const startBtn = h("div", { class: "pl-intake pl-welcome open" }, h("div", { class: "inner" }, h("div", { class: "welcome-guide" }, mascot({ size: 58, image: bundle.mascot, title: guide }).el, h("div", {}, h("div", { class: "state" }, "YOUR VIRTUAL SHOWROOM"), h("span", { class: "guide-caption" }, `Your guide, ${guide}`))), h("h1", {}, bundle.product?.name || bundle.name), h("p", {}, "Take a closer look. Ask what matters to you."), voiceChoice, h("div", { class: "actions" }, h("button", { class: "btn primary", onclick: () => begin(false) }, "Explore with me", icon("arrow-right", { size: 17 })), h("button", { class: "btn ghost", onclick: () => begin(true) }, "Browse at my pace"))));
  el.stage.append(startBtn);
  // List alternate languages already included in the published bundle.
  // These controls switch existing content; they do not call server/agents/translate.py:translate to generate anything.
  // language chooser (multi-language bundles)
  const alts = bundle.alt_languages ? Object.keys(bundle.alt_languages) : [];
  if (alts.length) {
    const NAMES = { "en-IN": "English", "hinglish": "Hinglish", "hi-IN": "हिंदी", "ta-IN": "தமிழ்", "te-IN": "తెలుగు", "kn-IN": "ಕನ್ನಡ", "mr-IN": "मराठी", "bn-IN": "বাংলা", "gu-IN": "ગુજરાતી", "ml-IN": "മലയാളം", "pa-IN": "ਪੰਜਾਬੀ" };
    // Build language buttons that apply the chosen bundle variant and mark it as selected.
    // web/api.js:h creates the controls; applyLanguage updates the content and live locale.
    const row = h("div", { class: "pl-langs" }, h("button", { class: "chip primary" }, NAMES[bundle.language] || bundle.language), ...alts.map((code) => h("button", { class: "chip", onclick: (e) => { applyLanguage(code); row.querySelectorAll(".chip").forEach((c) => c.classList.remove("primary")); e.currentTarget.classList.add("primary"); } }, NAMES[code] || code)));
    startBtn.querySelector(".inner").insertBefore(row, startBtn.querySelector(".actions"));
  }
  // Replace narration, intake and slides with the selected prebuilt language version.
  // Refresh the hero view and live-voice.js:LiveVoiceClient language; no translation or voice rebuild happens here.
  function applyLanguage(code) {
    const alt = bundle.alt_languages?.[code]; if (!alt) return;
    bundle.segments = alt.segments; bundle.closing = alt.closing; bundle.intake = alt.intake; bundle.language = code; bundle.voice = { ...bundle.voice, provider: alt.voice_provider || bundle.voice.provider }; bundle.slides = alt.slides || bundle.slides;
    if (bundle.runtime) bundle.runtime = { ...bundle.runtime, overview: alt.runtime_overview || null };
    slides = slidesOf(bundle); S.lang = code;
    if (live) live.language = S.lang;
    if (cur) { cur.view.destroy(); cur = null; } showSlideView(heroOpen(), { reveal: 99 });
  }
  // Expose only lifecycle and context methods to the page that mounted this player.
  // web/app.js:renderPlay uses these handles instead of directly changing the internal visit state.
  return { destroy, restart, pause, context };
}
