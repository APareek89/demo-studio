// The runtime player — voice-led, interruptible, grounded through the server.
// Flow: one needs question → opening film → STANDARD OPENING (intro + outcome, unchanged) →
// runtime pitch plan (decision frame · personalised route with grounded bridges) →
// proof blocks with check-ins → establish → advance → CTA → handoff.
// mountPlayer(host, bundle, {qa, tts, pitch, lead, saveSession}) → { destroy, restart, pause, context }
import { mascot } from "/web/player/mascot.js";
import { h } from "/web/api.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const pick = (a) => a[Math.floor(Math.random() * a.length)];
const PHONE = /(?:\+?91[\s-]?)?([6-9]\d{9})/;

export function mountPlayer(host, bundle, api) {
  const S = { run: 0, plan: [], seg: 0, line: 0, atCheckin: false, waiter: null, waitChips: [], timer: null, intakeResolver: null, pendingIntakeAnswer: "", intakeOpen: false,
    profile: { name: "", why: "", followup: "", focus: [] }, pitch: null, questions: [], transcript: [], escalations: [], leads: [], resolved: new Set(), unresolved: new Set(), raised: new Set(),
    cta: null, started: Date.now(), micOn: false, micDenied: false, rec: null, audio: null, preloads: [], modelTimer: null, ttsToken: 0, ttsCache: new Map(), bt: { voice: null },
    leadPromptShown: false, leadQuestion: "", leadReason: "" };
  const persona = bundle.voice?.persona || {}; const guide = persona.persona_name || "Guide";
  const useServerVoice = bundle.voice?.provider && bundle.voice.provider !== "browser";
  // Recorded filler lines in the persona's voice (acknowledgements, bridges, holds). Rule: the voice never changes mid-demo —
  // a line is spoken with server audio or shown as captions, never with the browser's built-in voice.
  // Keep preload objects alive for the full session. This covers the complete authored route,
  // not only intake, so moving between lines does not repeatedly pay a network-start pause.
  setTimeout(() => {
    try {
      const urls = [];
      for (const v of Object.values(bundle.fillers || {})) if (v.audio) urls.push(v.audio);
      for (const u of Object.values(bundle.intake?.audio || {})) if (u) urls.push(u);
      for (const seg of bundle.segments || []) {
        for (const line of [...(seg.lines || []), ...(seg.deeper || [])]) if (line.audio) urls.push(line.audio);
        if (seg.checkin?.audio) urls.push(seg.checkin.audio);
      }
      for (const line of bundle.closing || []) if (line.audio) urls.push(line.audio);
      for (const item of bundle.faq || []) if (item.audio) urls.push(item.audio);
      for (const url of [...new Set(urls)]) { const a = new Audio(url); a.preload = "auto"; a.load(); S.preloads.push(a); }
      for (const item of bundle.media?.images || []) { if (!item.url) continue; const image = new Image(); image.decoding = "async"; image.src = item.url; S.preloads.push(image); }
      for (const item of asset?.angles || []) { if (!item.url) continue; const image = new Image(); image.decoding = "async"; image.src = item.url; S.preloads.push(image); }
      if (bundle.intro_video?.url) { const v = document.createElement("video"); v.preload = "auto"; v.src = bundle.intro_video.url; v.load(); S.preloads.push(v); }
    } catch (e) {}
  }, 150);
  const F = (key, fallback) => { const f = bundle.fillers?.[key]; return f?.audio ? { text: f.text, audio: f.audio } : { text: fallback || f?.text || "", audio: null }; };
  const speakF = (key, fallback, run) => { const f = F(key, fallback); return speak(f.text, run, f.audio); };
  function captionOnly(text, run) { return new Promise((res) => { const my = ++S.ttsToken; const ms = Math.max(1200, (text.split(/\s+/).length / 2.5) * 1000); const t = setTimeout(() => res(my === S.ttsToken && run === S.run), ms); S.captionTimer = t; }); }
  let LANG = (bundle.language === "hinglish" ? "hi-IN" : bundle.language) || "en-IN";
  Object.defineProperty(S, "lang", { set(v) { LANG = v === "hinglish" ? "hi-IN" : v; }, get() { return LANG; } });
  let serverSTT = !!(api.stt && bundle.stt?.provider === "sarvam");
  const canListen = () => (serverSTT && navigator.mediaDevices?.getUserMedia) || SR;
  const opening = (bundle.segments || []).filter((s) => s.role === "intro" || s.role === "outcome");
  const library = (bundle.segments || []).filter((s) => s.role !== "intro" && s.role !== "outcome");
  const asset = bundle.visual_asset;

  // ---------- DOM ----------
  const el = {};
  const root = h("div", { class: "pl" },
    h("div", { class: "pl-top" },
      h("div", { class: "left" }, el.avatar = h("div", { class: "avatar" }), (el.mascotTop = mascot({ size: 34, image: bundle.mascot })).el, h("div", {}, h("div", { class: "pl-name" }, `${guide} · ${bundle.product?.name || bundle.name}`), el.status = h("div", { class: "pl-status" }, h("span", { class: "dot" }), el.statusTxt = h("span", {}, "Ready"))), el.progress = h("div", { class: "pl-progress" })),
      h("div", { class: "right" }, api.downloadUrl ? h("a", { class: "icon-btn link-btn download-btn", href: api.downloadUrl, download: `${bundle.name || "demo"}.mp4`, title: "Download MP4" }, "MP4 ↓") : null, el.fsBtn = h("button", { class: "icon-btn", title: "Full screen", onclick: () => toggleFullscreen() }, "⛶"), el.pauseBtn = h("button", { class: "icon-btn", title: "Pause / resume", onclick: () => togglePause() }, "⏸"), h("button", { class: "icon-btn", title: "Stop and see the summary", onclick: () => stopDemo() }, "⏹"), el.chatBtn = h("button", { class: "icon-btn", title: "Conversation", onclick: () => toggleDrawer() }, "💬", h("span", { class: "badge" })), h("button", { class: "icon-btn", title: "Restart", onclick: () => restart() }, "↺"), api.onClose ? h("button", { class: "icon-btn", title: "Close", onclick: () => { interruptAll(); if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); api.onClose(); } }, "✕") : null)),
    el.stage = h("div", { class: "pl-stage" },
      el.media = h("div", { class: "pl-media" + (asset ? " has-3d" : "") },
        asset ? (el.model = h("model-viewer", { src: asset.glb_url, poster: asset.preview_url || "", "camera-controls": true, "auto-rotate": true, "shadow-intensity": "1", "environment-image": "neutral", "interaction-prompt": "none", alt: `Interactive 3D view of ${bundle.product?.name || bundle.name}` })) : null,
        el.img = h("img", { alt: "", style: "opacity:0" }), el.video = h("video", { muted: true, playsinline: true, preload: "auto", style: "opacity:0;display:none" }), el.focus = h("div", { class: "focus" }),
        asset ? (el.support = h("div", { class: "pl-support" }, el.supportImg = h("img", { alt: "Supporting product detail" }), el.supportVideo = h("video", { muted: true, playsinline: true, preload: "auto" }), h("div", { class: "pl-support-copy" }, el.supportBadge = h("span", { class: "origin real" }, "DETAIL"), el.supportText = h("span", {}, "Supporting view")))) : null,
        asset ? h("div", { class: "pl-angle-strip", "aria-label": "Product reference views" }, ...(asset.angles || []).slice(0, 6).map((a) => h("figure", { title: `${a.label || a.angle} · ${a.generated ? "AI-created" : "real"}` }, h("img", { src: a.url, alt: a.label || a.angle }), h("figcaption", {}, a.label || a.angle, h("i", { class: a.generated ? "ai" : "" }, a.generated ? "AI" : "REAL"))))) : null),
      el.card = h("div", { class: "pl-card" }),
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
  function addMsg(role, text, extra = {}) { const d = h("div", { class: "m " + role }, text); el.thread.append(d); el.thread.scrollTop = el.thread.scrollHeight; if (role !== "note") S.transcript.push({ role, text, t: Date.now(), ...extra }); if (role === "agent" && !el.drawer.classList.contains("open")) el.chatBtn.classList.add("unread"); }
  function acceptTypedAnswer(text) {
    if (S.intakeOpen) {
      if (S.intakeResolver) S.intakeResolver(text);
      else { S.pendingIntakeAnswer = text; el.inHeard.textContent = text; }
      return;
    }
    if (S.waiter) {
      addMsg("user", text);
      resolveWait(interpretReply(text, S.waitChips));
      return;
    }
    handleQuestion(text);
  }
  function toggleDrawer(force) { const on = force === undefined ? !el.drawer.classList.contains("open") : force; el.drawer.classList.toggle("open", on); if (on) { el.chatBtn.classList.remove("unread"); setTimeout(() => el.q.focus(), 80); } }
  function setChips(list) { el.chips.replaceChildren(...list.map((c) => h("button", { class: "chip" + (c.primary ? " primary" : ""), onclick: () => resolveWait(c.value) }, c.label))); }
  function clearTimer() { if (S.timer) { clearInterval(S.timer); S.timer = null; } el.timer.replaceChildren(); }
  function newRun() { return ++S.run; }
  function renderProgress() { el.progress.replaceChildren(...S.plan.map((st, i) => h("button", { class: "pp" + (i < S.seg ? " done" : i === S.seg ? " active" : ""), title: st.seg.outcome || "", onclick: () => { interruptAll(); playFrom(i, 0); } }, st.seg.title))); }
  function renderCtas() { const ctas = (bundle.ctas || []).filter((c) => c.when === "always" || !c.when); el.ctas.replaceChildren(...ctas.map((c) => h("button", { class: "chip cta" + (c.primary ? " primary" : ""), onclick: () => { interruptAll(); ctaFlow(c.id, newRun()); } }, c.label))); }

  // ---------- visuals ----------
  let videoStop = null;
  const DETAIL_CUE = /\b(interior|inside|cabin|seat|dashboard|screen|display|cluster|touchscreen|infotainment|airbags?|curtain|gear|gearbox|shifter|transmission|manual|automatic|paddles?|climate|sunroof|roof|calipers?|alloys?|wheels?|tyres?|muffler|exhaust|tailpipe|headlamps?|headlights?|grille|spoiler|bumper|sills?|brakes?|camera|sensors?|mirror|glovebox|charging|android auto|carplay|bose|speakers?|vents?|sunshade|armrest|smartsense|adas|cruise|lane|collision|blind spot|driver attention|child seat|isofix|tyre pressure)\b/i;
  const ABSTRACT_CUE = /\b(warranty|roadside assistance|terms? (?:and )?conditions?|price|mileage|kilometres?|subscription|catalogue|brochure|not (?:printed|listed|stated)|availability|bookable|test conditions?|certified|marketing line|specifications? may change|cost extra|packages?|years?|PS\b|variant|N10\b|one-point-five litre|colou?r options?|colou?rs? listed|zero to hundred|nought to hundred|eight point nine)\b/i;
  const MODEL_CUE = /\b(looks? and drives?|more character|stands? out|at a glance|daily suv|everyday suv|feels? quick|strongest fit|test drive|highway overtake|turbo petrol pulls|product overview|walkaround)\b/i;
  function visualMode(v, text = "", card = "none") {
    if (v?.display_mode) return v.display_mode;
    if (["price", "summary", "contrast", "statement"].includes(card)) return "card";
    const detail = DETAIL_CUE.test(text), abstract = ABSTRACT_CUE.test(text);
    if (detail && abstract) return "card";
    if (detail) return v?.url ? "evidence" : "card";
    if (abstract) return "card";
    if (MODEL_CUE.test(text)) return "model";
    return v?.url ? "evidence" : (asset ? "model" : "card");
  }
  function setStageMode(mode) {
    el.media.classList.toggle("evidence-on", mode === "evidence");
    el.media.classList.toggle("card-on", mode === "card");
    el.card.classList.toggle("dominant", mode === "card" && !asset);
  }
  function directModel(v) {
    if (!asset || !el.model) return;
    const cue = `${v?.scriptText || ""} ${v?.focus || ""} ${v?.description || ""}`.toLowerCase();
    let orbit = "25deg 72deg 105%", label = "PRODUCT VIEW";
    if (/rear|tail|boot|back/.test(cue)) { orbit = "175deg 74deg 105%"; label = "REAR DETAIL"; }
    else if (/engine|turbo|drive|performance|quick|accelerat|hundred|power|torque/.test(cue)) { orbit = "38deg 68deg 100%"; label = "DRIVE / PERFORMANCE"; }
    else if (/front|grille|headlamp|headlight/.test(cue)) { orbit = "18deg 70deg 100%"; label = "FRONT DETAIL"; }
    el.model.removeAttribute("auto-rotate");
    el.model.setAttribute("camera-orbit", orbit);
    if (S.modelTimer) clearTimeout(S.modelTimer);
    S.modelTimer = setTimeout(() => { if (!el.media.classList.contains("film-on")) el.model.setAttribute("auto-rotate", ""); }, 4500);
    el.focus.textContent = label;
    el.focus.classList.add("on");
  }
  function showVisual(v, requestedMode = null) {
    let mode = requestedMode || visualMode(v, v?.scriptText || "", v?.card || "none");
    if (mode === "evidence" && (!v || v.kind === "none" || !v.url)) mode = "card";
    setStageMode(mode);
    if (el.support) { el.support.classList.remove("on"); el.supportVideo.pause(); }
    if (mode === "card") {
      el.img.style.opacity = 0; el.img.style.display = "none"; el.video.pause(); el.video.style.opacity = 0; el.video.style.display = "none";
      if (asset) directModel(v || {}); else el.focus.classList.remove("on");
      return mode;
    }
    if (mode === "model" && asset) {
      el.img.style.opacity = 0; el.img.style.display = "none"; el.video.pause(); el.video.style.opacity = 0; el.video.style.display = "none";
      directModel(v || {});
      return mode;
    }
    el.focus.classList.toggle("on", !!(v && v.focus)); el.focus.textContent = v?.focus || "";
    if (!v || v.kind === "none" || !v.url) return mode;
    if (v.kind === "image") {
      el.video.pause(); el.video.style.display = "none"; el.video.style.opacity = 0;
      const url = v.url; // exact evidence is stable; never rotate to an unrelated image on repetition
      if (el.img.getAttribute("src") !== url) { el.img.style.opacity = 0; el.img.classList.remove("kb"); el.img.src = url; el.img.onload = () => { el.img.style.opacity = 1; el.img.style.setProperty("--ox", (35 + Math.random() * 30).toFixed(0) + "%"); el.img.style.setProperty("--oy", (35 + Math.random() * 30).toFixed(0) + "%"); el.img.style.animationDelay = (-Math.random() * 12).toFixed(1) + "s"; el.img.classList.add("kb"); }; } else { el.img.style.opacity = 1; el.img.classList.add("kb"); }
      el.img.style.display = "";
    } else if (v.kind === "shot") {
      el.img.style.opacity = 0; el.img.style.display = "none"; el.video.style.display = ""; el.video.style.setProperty("--z", "1");
      const vid = el.video; if (videoStop) { vid.removeEventListener("timeupdate", videoStop); videoStop = null; }
      const start = () => { vid.currentTime = Math.max(0, v.start || 0); vid.style.opacity = 1; vid.play().catch(() => {}); videoStop = () => { if (vid.currentTime >= (v.end || 1e9)) vid.pause(); }; vid.addEventListener("timeupdate", videoStop); };
      if (vid.getAttribute("src") !== v.url) { vid.src = v.url; vid.onloadedmetadata = start; } else start();
    }
    return mode;
  }
  function firstVisual(seg) { return (seg?.lines || []).map((l) => l.visual).find((v) => v && v.kind !== "none") || null; }
  function compactText(value, limit) {
    let text = String(value || "").replace(/\s+/g, " ").trim();
    text = text.split(/[.!?;]\s+|\s[—–]\s/)[0].replace(/[.!?;]+$/, "");
    if (text.length <= limit) return text;
    const cut = text.slice(0, limit + 1).replace(/\s+\S*$/, "").trim();
    return `${cut || text.slice(0, limit).trim()}…`;
  }
  function compactRow(row) {
    const plainClaim = String(row?.claim || "Key feature").replace(/\b(listed in (?:the )?(?:catalogue|brochure)|in the (?:catalogue|brochure)|as standard)\b/gi, "").replace(/\s+/g, " ").trim();
    const claim = compactText(plainClaim || row?.claim || "Key feature", 24);
    let value = compactText(row?.value || "", 34);
    if (value.toLowerCase().startsWith(claim.toLowerCase())) value = compactText(value.slice(claim.length).replace(/^\s*[:—–-]\s*/, ""), 34);
    return { claim, value: value || "Confirmed" };
  }
  function showCard(kind, extra) {
    if (!kind || kind === "none") { el.card.classList.remove("on"); return; }
    let rows = [], title = "Key points";
    if (kind === "price") { rows = bundle.cards?.price || []; title = "Price"; }
    else if (kind === "facts") rows = bundle.cards?.facts || [];
    else if (kind === "summary") { rows = [...(bundle.cards?.facts || []).slice(0, 4), ...(bundle.cards?.price || []).slice(0, 2)]; title = "In short"; }
    else if (kind === "contrast") { rows = (bundle.cards?.price || []).slice(0, 3).concat((bundle.cards?.facts || []).slice(0, 3)); title = "Today vs. after"; }
    else if (kind === "cite" && extra) { rows = extra.map((f) => ({ claim: f.claim, value: f.value })); title = "Key points"; }
    else if (kind === "statement" && extra?.text) { rows = [{ claim: extra.value || "Key point", value: extra.text }]; title = extra.title || "Key point"; }
    if (!rows.length) { el.card.classList.remove("on"); return; }
    rows = rows.slice(0, 3).map(compactRow);  // keywords only; narration carries the detail
    el.card.replaceChildren(h("h4", {}, title), ...rows.map((r) => h("div", { class: "row" }, h("span", {}, r.claim), h("b", {}, r.value))));
    el.card.classList.add("on");
  }
  function present(v, text, card = "none", factIds = []) {
    let mode = visualMode(v, text, card);
    mode = showVisual({ ...(v || { kind: "none" }), scriptText: text, card }, mode);
    if (mode === "card") {
      const cited = (bundle.facts || []).filter((f) => (factIds || []).includes(f.id));
      if (card === "statement") showCard("statement", { text, value: "YOUR PRIORITIES", title: "Your demo, tailored" });
      else if (card && !["none", "cite"].includes(card)) showCard(card);
      else if (cited.length) showCard("cite", cited);
      else showCard("statement", { text, value: "CHECK WITH THE DEALER" });
    } else showCard(card);
    el.card.classList.toggle("dominant", mode === "card" && !asset);
    return mode;
  }
  function presentLine(line, text = line?.text || "") { return present(line?.visual, text, line?.card || "none", line?.fact_ids || []); }

  // ---------- voice out ----------
  function browserVoice() {
    if (S.bt.voice) return S.bt.voice;
    const want = LANG.slice(0, 2).toLowerCase();
    const vs = speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith(want));
    const score = (v) => { let s = 0; const n = v.name; if (v.lang.replace("_", "-").toLowerCase() === LANG.toLowerCase()) s += 25; if (/neerja|veena|heera|swara|kalpana|lekha/i.test(n)) s += 60; if (/google uk english female|google us english$|google हिन्दी|google hindi/i.test(n)) s += 45; if (/samantha|kate\b|serena|karen|moira|zira|jenny|aria|sonia|libby|emma|olivia|amy\b|joanna|salli|natasha/i.test(n)) s += 30; if (/natural|premium|enhanced|neural|online/i.test(n)) s += 8; if (/rishi|daniel|alex\b|fred|arthur|gordon|oliver|reed|tom\b|david|mark\b|james|guy\b|ryan|ravi|male|eddy|flo\b|grandma|grandpa|sandy|shelley|bahh|bells|boing|bubbles|cellos|wobble|zarvox|trinoids|whisper|jester|organ|superstar|good news|bad news|albert|junior|ralph|kathy/i.test(n)) s -= 70; return s; };
    S.bt.voice = vs.sort((a, b) => score(b) - score(a))[0] || null; return S.bt.voice;
  }
  function speakBrowser(text) {
    return new Promise((res) => { const my = ++S.ttsToken; const u = new SpeechSynthesisUtterance(text); const v = browserVoice(); if (v) u.voice = v; u.lang = LANG; u.rate = 0.98; u.pitch = 1.05; let done = false; const fin = () => { if (done) return; done = true; res(my === S.ttsToken); }; const t = setTimeout(fin, Math.max(1500, text.length * 75) + 4000); u.onend = () => { clearTimeout(t); fin(); }; u.onerror = () => { clearTimeout(t); fin(); }; try { speechSynthesis.speak(u); } catch (e) { fin(); } });
  }
  async function audioUrlFor(text, preset) { if (preset) return preset; if (!useServerVoice) return null; if (S.ttsCache.has(text)) return S.ttsCache.get(text); const p = api.tts(text).catch(() => null); S.ttsCache.set(text, p); return p; }
  function prefetch(items) { if (!useServerVoice) return; for (const it of items) if (it && !it.audio && it.text) audioUrlFor(it.text); }
  async function speak(text, run, preset) {
    if (run !== S.run || !text) return run === S.run;
    el.cap.textContent = text; if (S.intakeOpen) el.inQ.textContent = text; setStatus("speaking", "Speaking"); addMsg("agent", text);
    let url = null; try { url = await audioUrlFor(text, preset); } catch (e) {}
    if (run !== S.run) return false;
    let ok;
    if (url) ok = await new Promise((res) => { const my = ++S.ttsToken; const a = new Audio(url); S.audio = a; let done = false; const fin = () => { if (done) return; done = true; res(my === S.ttsToken); }; const safeFallback = () => { if (done) return; done = true; (useServerVoice ? captionOnly(text, run) : speakBrowser(text)).then(res); }; a.onended = fin; a.onerror = safeFallback; a.play().catch(safeFallback); });
    else ok = useServerVoice ? await captionOnly(text, run) : await speakBrowser(text);
    if (ok && run === S.run) setStatus("idle", "Ready");
    return ok && run === S.run;
  }
  function cancelSpeech() { S.ttsToken++; if (S.captionTimer) { clearTimeout(S.captionTimer); S.captionTimer = null; } try { speechSynthesis.cancel(); } catch (e) {} if (S.audio) { try { S.audio.pause(); } catch (e) {} S.audio = null; } }

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
  function listen(opts = {}) {
    if (serverSTT && !S.micDenied && navigator.mediaDevices?.getUserMedia) return listenServer(opts).then((t) => (t || !SR || S.micDenied) ? t : t);
    return listenBrowser(opts);
  }
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

  // ---------- route building ----------
  function buildRoute(plan) {
    const byId = Object.fromEntries(library.map((s) => [s.id, s]));
    let steps = [];
    if (plan?.route?.length) steps = plan.route.filter((r) => byId[r.segment_id]).map((r) => ({ seg: byId[r.segment_id], bridge: r.bridge, bridge_audio: r.bridge_audio || "", bridge_fact_ids: r.bridge_fact_ids || [] }));
    if (!steps.length) { // fallback: focus topics first, then bundle order, establish last
      const focus = new Set(S.profile.focus); const proof = library.filter((s) => s.role !== "establish"); const est = library.filter((s) => s.role === "establish");
      steps = [...proof.filter((s) => focus.has(s.topic) || focus.has(s.id)), ...proof.filter((s) => !(focus.has(s.topic) || focus.has(s.id))), ...est].map((seg) => ({ seg, bridge: "", bridge_fact_ids: [] }));
    }
    S.plan = steps; S.seg = 0; renderProgress();
    prefetch(steps.filter((s) => s.bridge).map((s) => ({ text: s.bridge })));
  }

  async function playOpening(run) {
    for (const seg of opening) {
      prefetch(seg.lines);
      for (const ln of seg.lines) { if (run !== S.run) return false; presentLine(ln); el.cite.textContent = ln.fact_ids?.length ? "sources: " + ln.fact_ids.join(", ") : ""; const ok = await speak(ln.text, run, ln.audio); if (!ok) return false; }
    }
    return run === S.run;
  }

  async function playFrom(idx, lineIdx = 0) {
    const run = newRun();
    for (let i = idx; i < S.plan.length; i++) {
      const step = S.plan[i], seg = step.seg; S.seg = i; S.atCheckin = false; renderProgress();
      prefetch([...seg.lines.slice(lineIdx), seg.checkin?.text ? { text: seg.checkin.text, audio: seg.checkin.audio } : null].filter(Boolean));
      if (lineIdx === 0 && step.bridge) { const fv = firstVisual(seg); present(fv ? { ...fv, display_mode: "" } : null, step.bridge, "none", step.bridge_fact_ids || []); el.cite.textContent = step.bridge_fact_ids?.length ? "sources: " + step.bridge_fact_ids.join(", ") : ""; const okb = await speak(step.bridge, run, step.bridge_audio); if (!okb) return; }
      for (let j = lineIdx; j < seg.lines.length; j++) { S.line = j; if (run !== S.run) return; const ln = seg.lines[j]; presentLine(ln); el.cite.textContent = ln.fact_ids?.length ? "sources: " + ln.fact_ids.join(", ") : ""; const ok = await speak(ln.text, run, ln.audio); if (!ok) return; S.line = j + 1; }
      lineIdx = 0; if (run !== S.run) return;
      if (seg.checkin?.text) {
        S.atCheckin = true; const ok = await speak(seg.checkin.text, run, seg.checkin.audio); if (!ok) return;
        const conc = !!seg.priority || S.profile.focus.includes(seg.topic);
        const chips = conc ? [{ label: "That settles it", value: "yes", primary: true }, { label: "Still unsure", value: "deeper" }, { label: "I have a question", value: "question" }] : [{ label: "Continue", value: "continue", primary: true }, { label: "Tell me more", value: "deeper" }, { label: "I have a question", value: "question" }];
        const r = await waitFor(chips, 8); if (run !== S.run) return;
        if (r.value === "yes") { S.resolved.add(seg.topic); const ok2 = await speakF("good", "Good — moving on.", run); if (!ok2) return; }
        else if (r.value === "__timeout") { const ok2 = await speakF("nudge_continue", "I'll carry on — stop me whenever you like.", run); if (!ok2) return; }
        else if (r.value === "deeper") { S.raised.add(seg.topic); prefetch(seg.deeper || []); for (const ln of seg.deeper || []) { presentLine(ln); const ok2 = await speak(ln.text, run, ln.audio); if (!ok2) return; }
          if (!(seg.deeper || []).length) { const ok3 = await speak("That's everything the material covers on this — ask me anything specific and I'll check.", run); if (!ok3) return; }
          const ok3 = await speakF("clearer", "Is that clearer?", run); if (!ok3) return;
          const r2 = await waitFor([{ label: "Yes, continue", value: "yes", primary: true }, { label: "Not really", value: "no" }, { label: "Question", value: "question" }], 15); if (run !== S.run) return;
          if (r2.value === "yes") S.resolved.add(seg.topic); else if (r2.value === "no") { S.unresolved.add(seg.topic); S.escalations.push(`${seg.topic} — still unsure after the deeper explanation`); const ok4 = await speak(`Then let's not paper over it — I've flagged ${seg.topic} for someone from the team to take up with you properly. Let me carry on for now.`, run); if (!ok4) return; }
          else if (r2.value === "question") { if (r2.text) handleQuestion(r2.text); else listenForQuestion(); return; } else if (r2.value === "__interrupted") return; }
        else if (r.value === "question") { if (r.text) handleQuestion(r.text); else listenForQuestion(); return; }
        else if (r.value === "__interrupted") return;
      }
      maybePromptLead("progress");
    }
    await closeFlow(run);
  }

  async function closeFlow(run) {
    S.atCheckin = true; showCard("summary");
    const closing = bundle.closing || [];
    if (S.pitch?.advance) { present(null, S.pitch.advance, "summary"); const ok = await speak(S.pitch.advance, run, S.pitch.advance_audio); if (!ok) return; for (const ln of closing.slice(1)) { presentLine(ln); const ok2 = await speak(ln.text, run, ln.audio); if (!ok2) return; } }
    else for (const ln of closing) { presentLine(ln); const ok = await speak(ln.text, run, ln.audio); if (!ok) return; }
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
    const wasAtCheckin = S.atCheckin; interruptAll(); const run = newRun();
    addMsg("user", text); S.questions.push(text); el.live.textContent = ""; setStatus("thinking", "Thinking"); el.cap.textContent = "…";
    let r;
    const qaP = api.qa({ question: text, history: S.transcript.slice(-8).map((t) => ({ role: t.role, text: t.text })), profile: profileForServer() });
    try { r = await withTimeout(qaP, 700); if (!r) { const okH = await speakF("hold_on_question", "Good question — give me one moment, please, while I check that for you.", run); if (!okH) return; r = await qaP; } }
    catch (e) { if (run !== S.run) return; const ok = await speak("I couldn't reach my notes just now — give me a second and ask again, or I'll flag it for the team.", run); if (!ok) return; S.escalations.push(`error answering: "${text}"`); resumeAfterQA(wasAtCheckin); return; }
    if (run !== S.run) return;
    if (!r.answered) {
      if (r.escalate) S.escalations.push(r.escalate);
      if (r.topic && r.topic !== "other") S.raised.add(r.topic);
      S.unresolved.add(r.topic || "question");
      if (asset) showVisual({ kind: "none", display_mode: "model", scriptText: text }, "model");
      else showVisual({ kind: "image", url: bundle.media?.hero, scriptText: text }, bundle.media?.hero ? "evidence" : "card");
      showCard("none"); el.cite.textContent = "";
      const unknown = "I don't know from the information I have. Share your details here and someone from the dealership can help you with that.";
      const okUnknown = await speak(unknown, run); if (!okUnknown) return;
      showLeadPrompt("unknown", text);
      resumeAfterQA(wasAtCheckin);
      return;
    }
    const answerVisual = r.visual ? { ...r.visual, url: mediaUrlFor(r.visual), focus: "" } : null;
    const answerMode = present(answerVisual, r.answer || text, r.facts?.length ? "cite" : "none", r.fact_ids || []);
    if (answerMode !== "card") { if (r.facts?.length) showCard("cite", r.facts); else showCard("none"); }
    el.cite.textContent = r.fact_ids?.length ? "sources: " + r.fact_ids.join(", ") : (r.answered ? "" : "not in the sources — flagged");
    if (r.escalate) S.escalations.push(r.escalate); if (r.topic && r.topic !== "other") S.raised.add(r.topic);
    if (r.from_bank) addMsg("note", "answered from the FAQ bank — no model call");
    const ok = await speak(r.answer, run, r.audio); if (!ok) return;
    if (r.cta) { await ctaFlow(r.cta, run); return; }
    if (r.offer_callback) showLeadPrompt("question", text);
    maybePromptLead("questions");
    if (r.clarifying_question) { const a = await askAndListen(r.clarifying_question, run, 10000); if (run !== S.run) return; if (a) { handleQuestion(a); return; } }
    const ok2 = await speakF("did_that_answer", "Did that answer it?", run); if (!ok2) return;
    const r2 = await waitFor([{ label: "Yes, that helps", value: "yes", primary: true }, { label: "Not quite", value: "no" }], 20); if (run !== S.run) return;
    if (r2.value === "yes") { S.resolved.add(r.topic || "question"); const ok3 = await speakF("glad", "Glad that helps.", run); if (!ok3) return; maybePromptLead("questions"); resumeAfterQA(wasAtCheckin); }
    else if (r2.value === "no") { S.unresolved.add(r.topic || "question"); S.escalations.push(`not satisfied: "${text}"`); const ok3 = await speak("I don't want to leave that half-answered. I've opened a short form so someone from the dealership can help you properly.", run); if (!ok3) return; showLeadPrompt("question", text); resumeAfterQA(wasAtCheckin); }
    else if (r2.value === "question" && r2.text) handleQuestion(r2.text);
    else resumeAfterQA(wasAtCheckin);
  }
  function showLeadPrompt(reason, question = "") {
    if (S.leads.length || (S.leadPromptShown && reason !== "unknown")) return;
    S.leadPromptShown = true; S.leadReason = reason; S.leadQuestion = question || "test drive";
    el.leadName.value = S.profile.name || ""; el.leadPhone.value = ""; el.leadError.textContent = "";
    el.leadCopy.textContent = reason === "unknown" ? "I don't have that answer in the approved sources. Leave your details and the dealership can answer it directly." : "You have seen enough to make a drive useful. Share your details and the dealership can arrange it.";
    el.lead.classList.add("open");
  }
  function maybePromptLead(reason) {
    const progress = S.plan.length ? (S.seg + 1) / S.plan.length : 0;
    if (S.questions.length >= 2 || progress >= 0.6) showLeadPrompt(reason, S.questions.at(-1) || "test drive");
  }
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
  function mediaUrlFor(v) { if (!v) return null; const src = v.source_id; for (const vid of bundle.media?.videos || []) if (v.kind === "shot" && vid.url.includes(src)) return vid.url; for (const im of bundle.media?.images || []) if (im.id === v.ref) return im.url; return (bundle.media?.videos || [])[0]?.url || null; }
  function resumeAfterQA(wasAtCheckin) { if (!S.plan.length) { const run = newRun(); speakF("back_to_demo", "Let's get back to where we were.", run).then((ok) => { if (ok) startAfterIntake(); }); return; } if (S.seg >= S.plan.length) { closeFlow(newRun()); return; } if (wasAtCheckin) playFrom(S.seg + 1, 0); else { const run = newRun(); speakF("back_to_demo", "Back to where we were.", run).then((ok) => { if (ok) playFrom(S.seg, S.line); }); } }

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
  function parseFocus(t) { const out = []; const s = t.toLowerCase(); for (const c of bundle.intake?.chips || []) { const words = c.label.toLowerCase().split(/[^a-z0-9ऀ-ॿ]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w)) || s.includes(c.key.toLowerCase())) out.push(c.key); } for (const seg of library) { const words = (seg.title + " " + seg.topic).toLowerCase().split(/[^a-z0-9ऀ-ॿ]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w))) out.push(seg.topic); } return [...new Set(out)].slice(0, 4); }
  function withTimeout(p, ms) { return Promise.race([p, new Promise((res) => setTimeout(() => res(null), ms))]); }

  async function runIntake() {
    const run = newRun(); S.intakeOpen = true; el.intake.classList.add("open"); el.inFallback.classList.remove("open");
    const q1 = bundle.intake?.q1 || `Hi, I'm ${guide}. Before we begin — could I get your name, and what you're hoping ${bundle.product?.name || "this"} would change for you?`;
    el.inState.textContent = guide;
    const ok = await speak(q1, run, bundle.intake?.audio?.q1); if (!ok) return;
    const a1 = await intakeWait(run); if (run !== S.run) return;
    if (a1) { addMsg("user", a1); S.profile.name = parseName(a1); S.profile.why = a1; S.profile.focus = parseFocus(a1); }
    el.intake.classList.remove("open"); S.intakeOpen = false;
    if (asset) showVisual({ kind: "none", display_mode: "model", scriptText: "product overview" }, "model");
    else if (bundle.media?.hero) showVisual({ kind: "image", url: bundle.media.hero, cycle: false }, "evidence");
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
      if (plan.decision_frame) { present(null, plan.decision_frame, "statement"); el.cite.textContent = ""; const ok = await speak(plan.decision_frame, run, plan.decision_frame_audio); if (!ok) return; }
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
    for (const b of batches) {
      if (run !== S.run) return false;
      present(b.visual ? { ...b.visual, url: mediaUrlFor(b.visual), focus: "" } : null, b.text, "none", b.fact_ids || []);
      el.cite.textContent = b.fact_ids?.length ? "sources: " + b.fact_ids.join(", ") : "";
      const ok = await speak(b.text, run, b.audio); if (!ok) return false;
    }
    return run === S.run;
  }
  function skipIntake() { interruptAll(); el.intake.classList.remove("open"); S.intakeOpen = false; S.intakeResolver = null; S.pendingIntakeAnswer = ""; const run = newRun(); playIntroFilm(run).then((okF) => { if (!okF) return; playOpening(run).then((ok) => { if (!ok) return; buildRoute(null); playFrom(0, 0); }); }); }

  // ---------- handoff ----------
  function intentScore() { let s = 20; s += Math.min(30, S.questions.length * 8); s += S.resolved.size * 8; s += S.seg >= S.plan.length - 1 ? 15 : 0; if (S.cta && S.cta !== "summary") s += 30; if (S.leads.length) s += 10; s -= S.unresolved.size * 5; return Math.max(5, Math.min(98, s)); }
  function showHandoff(c) {
    const mins = Math.round((Date.now() - S.started) / 6000) / 10; const topics = [...S.raised];
    const uspsCovered = [...new Set(S.plan.slice(0, S.seg + 1).flatMap((st) => st.seg.usp_ids || []))];
    const session = { profile: S.profile, customer_state: S.pitch?.customer_state, personalized: !!S.personalized, route: S.plan.map((st) => st.seg.id), usps_covered: uspsCovered, questions: S.questions, escalations: S.escalations, leads: S.leads, resolved: [...S.resolved], unresolved: [...S.unresolved], cta: S.cta, intent: intentScore(), drop_point: S.plan[S.seg]?.seg.title, minutes: mins, transcript: S.transcript };
    el.handoffBox.replaceChildren(h("h2", {}, c ? c.label : "Your summary"), h("div", { class: "sub" }, `what the guide passes to the team · ${mins} min · ${S.pitch?.customer_state || "no state"}${S.personalized ? "" : " · standard route (not personalised)"}`),
      h("div", { class: "grid2" },
        h("div", { class: "kvbox" }, h("h5", {}, "Intent"), h("div", { class: "score" }, intentScore(), h("small", {}, " / 100"))),
        h("div", { class: "kvbox" }, h("h5", {}, "Profile"), h("ul", {}, h("li", {}, S.profile.name || "Name not given"), S.profile.why ? h("li", {}, "Why: “", S.profile.why.slice(0, 140), "”") : null, S.profile.followup ? h("li", {}, "Follow-up: “", S.profile.followup.slice(0, 140), "”") : null, h("li", {}, "Focus: ", S.profile.focus.join(", ") || "none stated"))),
        h("div", { class: "kvbox" }, h("h5", {}, "Concerns raised → resolved"), h("ul", {}, topics.length ? topics.map((t) => h("li", {}, t, ": ", h("b", { style: `color:${S.resolved.has(t) ? "var(--accent)" : S.unresolved.has(t) ? "var(--warn)" : "var(--muted)"}` }, S.resolved.has(t) ? "resolved" : S.unresolved.has(t) ? "still unsure" : "discussed"))) : h("li", {}, "none raised explicitly"))),
        h("div", { class: "kvbox" }, h("h5", {}, `Questions asked (${S.questions.length})`), h("ul", {}, S.questions.length ? S.questions.map((q) => h("li", {}, "“", q, "”")) : h("li", {}, "none — listened through"))),
        h("div", { class: "kvbox", style: "grid-column:1/-1" }, h("h5", {}, "For a human to follow up"), h("ul", {}, S.leads.map((l) => h("li", {}, h("b", {}, "Call ", l.phone), " about “", l.question, "”")), S.escalations.length ? S.escalations.filter((e) => !e.startsWith("callback requested")).map((e) => h("li", {}, e)) : (S.leads.length ? null : h("li", {}, "nothing outstanding")))),
        h("div", { class: "kvbox", style: "grid-column:1/-1" }, h("h5", {}, "Route & drop point"), h("ul", {}, h("li", {}, "Route: ", S.plan.map((st) => st.seg.title).join(" → ") || "—"), h("li", {}, `Reached: ${S.plan[S.seg]?.seg.title || "—"} (${Math.min(S.seg + 1, S.plan.length)} of ${S.plan.length} blocks) · USPs covered: ${uspsCovered.join(", ") || "—"}`)))),
      h("div", { style: "display:flex;gap:10px;margin-top:14px" }, h("button", { class: "btn primary", onclick: () => { el.handoff.classList.remove("open"); api.saveSession(session).catch(() => {}); addMsg("note", "session saved"); const run = newRun(); speak(c ? "Done — everything we discussed goes with it. Thanks for your time." : "Thanks for your time. Ask me anything else whenever you're ready.", run); } }, c ? "Confirm (mock)" : "Done"), h("button", { class: "btn ghost", onclick: () => { el.handoff.classList.remove("open"); const run = newRun(); speak("Sure — what else would you like to know?", run).then((ok) => { if (ok) listenForQuestion(); }); } }, "Back to the demo")));
    el.handoff.classList.add("open"); api.saveSession(session).catch(() => {});
  }

  function toggleFullscreen() {
    if (api.onFullscreenRoute) { api.onFullscreenRoute(); return; }
    const target = root;
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else (target.requestFullscreen ? target.requestFullscreen() : Promise.reject()).catch(() => {});
  }

  // ---------- intro film ----------
  async function playIntroFilm(run) {
    const iv = bundle.intro_video;
    if (!iv || !iv.url || iv.enabled === false || S.introPlayed) return run === S.run;
    S.introPlayed = true;
    const ok = await speakF("before_video", "First, here's a quick film to bring it to life. Then I'll walk you through it around what you just told me.", run);
    if (!ok) return false;
    el.img.style.display = "none"; el.img.classList.remove("kb"); el.media.classList.remove("evidence-on", "card-on"); el.card.classList.remove("on", "dominant"); el.media.classList.add("film-on");
    if (el.support) el.support.classList.remove("on"); el.focus.classList.remove("on");
    const v = el.video; v.src = iv.url; v.muted = false; v.style.display = ""; v.style.opacity = 1; v.currentTime = 0;
    setStatus("idle", "Playing the film"); el.cap.textContent = ""; el.cite.textContent = "";
    el.chips.replaceChildren(h("button", { class: "chip" , onclick: () => { S.skipFilm = true; } }, "Skip the film"));
    const done = await new Promise((res) => {
      let fin = false, guard = null, cap = null; const end = (x) => { if (!fin) { fin = true; if (guard) clearInterval(guard); if (cap) clearTimeout(cap); res(x); } };
      v.onended = () => end(true); v.onerror = () => end(true);
      guard = setInterval(() => { if (run !== S.run || S.paused) end(false); if (S.skipFilm) { S.skipFilm = false; end(true); } }, 200);
      v.play().catch(() => end(true));
      cap = setTimeout(() => end(true), 45000);  // hard cap — an opening film is 10–20 s
    });
    try { v.pause(); } catch (e) {}
    v.muted = true; v.style.display = "none"; v.style.opacity = 0; el.media.classList.remove("film-on"); if (asset) showVisual({ kind: "none", display_mode: "model", scriptText: "product overview" }, "model"); setChips([]);
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
  function restart() { interruptAll(); S.customPlayed = false; S.introPlayed = false; S.skipFilm = false; S.pitchPromise = null; el.handoff.classList.remove("open"); el.lead.classList.remove("open"); S.questions.length = 0; S.transcript.length = 0; S.escalations.length = 0; S.leads.length = 0; S.resolved.clear(); S.unresolved.clear(); S.raised.clear(); S.cta = null; S.pitch = null; S.plan = []; S.leadPromptShown = false; S.leadQuestion = ""; S.started = Date.now(); S.profile = { name: "", why: "", followup: "", focus: [] }; el.thread.replaceChildren(); showCard("none"); renderProgress(); runIntake(); }
  function pause() { interruptAll(); setStatus("idle", "Paused"); }
  function context() { const st = S.plan[S.seg]; return { customer_state: S.pitch?.customer_state, route: S.plan.map((x) => x.seg.id), segment: st?.seg.id, segment_title: st?.seg.title, line_index: S.line, line_text: st?.seg.lines?.[S.line]?.text, bridge: st?.bridge, questions: S.questions.slice(-5), profile: S.profile, escalations: S.escalations.slice(-5), leads: S.leads }; }
  function destroy() { interruptAll(); if (S.modelTimer) clearTimeout(S.modelTimer); for (const media of S.preloads) { try { media.removeAttribute("src"); media.load(); } catch (e) {} } S.preloads.length = 0; root.remove(); }

  renderCtas();
  if (asset) showVisual({ kind: "none", display_mode: "model", scriptText: "product overview" }, "model");
  else showVisual({ kind: "image", url: bundle.media?.hero, focus: "" }, "evidence");
  if (!asset && bundle.media?.hero && /\.(mp4|mov|webm|m4v)$/i.test(bundle.media.hero)) showVisual({ kind: "shot", url: bundle.media.hero, start: 0, end: 4 }, "evidence");
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
    bundle.segments = alt.segments; bundle.closing = alt.closing; bundle.intake = alt.intake; bundle.language = code; bundle.voice = { ...bundle.voice, provider: alt.voice_provider || bundle.voice.provider };
    opening.length = 0; opening.push(...bundle.segments.filter((s) => s.role === "intro" || s.role === "outcome")); library.length = 0; library.push(...bundle.segments.filter((s) => s.role !== "intro" && s.role !== "outcome"));
    S.lang = code;
  }
  return { destroy, restart, pause, context };
}
