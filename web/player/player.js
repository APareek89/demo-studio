// The runtime player — voice-led, interruptible, grounded through the server.
// mountPlayer(host, bundle, {qa, tts, saveSession}) → { destroy, restart, pause, context }
import { h } from "/web/api.js";

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const pick = (a) => a[Math.floor(Math.random() * a.length)];

export function mountPlayer(host, bundle, api) {
  // ---------- state ----------
  const S = { run: 0, plan: [], seg: 0, line: 0, atCheckin: false, waiter: null, timer: null, intakeResolver: null, intakeOpen: false,
    profile: { name: "", why: "", focus: [] }, questions: [], transcript: [], escalations: [], resolved: new Set(), unresolved: new Set(), raised: new Set(),
    cta: null, started: Date.now(), micOn: false, micDenied: false, rec: null, audio: null, ttsToken: 0, ttsCache: new Map(), destroyed: false, bt: { voice: null } };
  const persona = bundle.voice?.persona || {}; const guide = persona.persona_name || "Guide";
  const useServerVoice = bundle.voice?.provider && bundle.voice.provider !== "browser";

  // ---------- DOM ----------
  const el = {};
  const root = h("div", { class: "pl" },
    h("div", { class: "pl-top" },
      h("div", { class: "left" }, el.avatar = h("div", { class: "avatar" }), h("div", {}, h("div", { class: "pl-name" }, `${guide} · ${bundle.product?.name || bundle.name}`), el.status = h("div", { class: "pl-status" }, h("span", { class: "dot" }), el.statusTxt = h("span", {}, "Ready"))), el.progress = h("div", { class: "pl-progress" })),
      h("div", { class: "right" }, el.chatBtn = h("button", { class: "icon-btn", title: "Conversation", onclick: () => toggleDrawer() }, "💬", h("span", { class: "badge" })), h("button", { class: "icon-btn", title: "Restart", onclick: () => restart() }, "↺"))),
    el.stage = h("div", { class: "pl-stage" },
      el.media = h("div", { class: "pl-media" }, el.img = h("img", { alt: "", style: "opacity:0" }), el.video = h("video", { muted: true, playsinline: true, preload: "auto", style: "opacity:0;display:none" }), el.focus = h("div", { class: "focus" })),
      el.card = h("div", { class: "pl-card" }),
      el.ctas = h("div", { class: "pl-ctas" }),
      h("div", { class: "pl-dock" },
        h("div", { class: "pl-cap" }, h("div", { class: "who" }, guide), el.cap = h("div", { class: "txt" }), el.cite = h("div", { class: "cite" })),
        h("div", { class: "pl-controls" }, el.live = h("div", { class: "pl-live" }), el.chips = h("div", { class: "pl-chips" }), el.timer = h("div", { class: "pl-timer" }),
          h("div", { class: "pl-mic-row" }, el.hint = h("div", { class: "pl-hint" }, SR ? "Tap to talk — I'll stop and listen." : "Voice input needs Chrome or Safari — use 💬 to type."), el.mic = h("button", { class: "mic", onclick: () => micTap() }, "🎤")))),
      el.intake = h("div", { class: "pl-intake" }, h("div", { class: "inner" }, el.orb = h("div", { class: "orb" }, h("div", { class: "r" })), el.inState = h("div", { class: "state" }, guide), el.inQ = h("p", { class: "q" }), el.inHeard = h("div", { class: "heard" }),
        el.inFallback = h("form", { class: "fallback", onsubmit: (e) => { e.preventDefault(); const t = el.inText.value.trim(); if (t && S.intakeResolver) { el.inText.value = ""; S.intakeResolver(t); } } }, el.inText = h("input", { placeholder: "Type your answer…" }), h("button", { class: "btn primary sm", type: "submit" }, "Send")),
        h("div", { class: "actions" }, el.inMic = h("button", { class: "mic", onclick: () => intakeMic() }, "🎤"), h("button", { class: "btn ghost", onclick: () => skipIntake() }, "Skip, start the demo")))),
      el.handoff = h("div", { class: "pl-handoff" }, el.handoffBox = h("div", { class: "box" }))),
    el.drawer = h("div", { class: "pl-drawer" }, h("div", { class: "head" }, h("span", {}, "Conversation"), h("button", { class: "icon-btn", onclick: () => toggleDrawer(false) }, "✕")), el.thread = h("div", { class: "body" }),
      h("form", { class: "composer", onsubmit: (e) => { e.preventDefault(); const t = el.q.value.trim(); if (t) { el.q.value = ""; handleQuestion(t); } } }, el.q = h("input", { placeholder: "Type a question…" }), h("button", { class: "btn primary sm", type: "submit" }, "↑"))));
  host.replaceChildren(root);

  // ---------- helpers ----------
  function setStatus(kind, txt) { el.status.className = "pl-status " + kind; el.statusTxt.textContent = txt; el.avatar.classList.toggle("speaking", kind === "speaking"); el.avatar.classList.toggle("listening", kind === "listening"); el.orb.className = "orb" + (kind === "speaking" ? " speaking" : kind === "listening" ? " listening" : ""); }
  function addMsg(role, text, extra = {}) { const d = h("div", { class: "m " + role }, text); el.thread.append(d); el.thread.scrollTop = el.thread.scrollHeight; if (role !== "note") S.transcript.push({ role, text, t: Date.now(), ...extra }); if (role === "agent" && !el.drawer.classList.contains("open")) el.chatBtn.classList.add("unread"); }
  function toggleDrawer(force) { const on = force === undefined ? !el.drawer.classList.contains("open") : force; el.drawer.classList.toggle("open", on); if (on) { el.chatBtn.classList.remove("unread"); setTimeout(() => el.q.focus(), 80); } }
  function setChips(list) { el.chips.replaceChildren(...list.map((c) => h("button", { class: "chip" + (c.primary ? " primary" : ""), onclick: () => resolveWait(c.value) }, c.label))); }
  function clearTimer() { if (S.timer) { clearInterval(S.timer); S.timer = null; } el.timer.replaceChildren(); }
  function newRun() { return ++S.run; }
  function renderProgress() { el.progress.replaceChildren(...S.plan.map((s, i) => h("button", { class: "pp" + (i < S.seg ? " done" : i === S.seg ? " active" : ""), onclick: () => { interruptAll(); playFrom(i, 0); } }, s.title))); }
  function renderCtas() { const ctas = (bundle.ctas || []).filter((c) => c.when === "always" || !c.when); el.ctas.replaceChildren(...ctas.map((c) => h("button", { class: "chip cta" + (c.primary ? " primary" : ""), onclick: () => { interruptAll(); ctaFlow(c.id, newRun()); } }, c.label))); }

  // ---------- visuals ----------
  let videoStop = null;
  function showVisual(v) {
    el.focus.classList.toggle("on", !!(v && v.focus)); el.focus.textContent = v?.focus || "";
    if (!v || v.kind === "none" || !v.url) return;
    if (v.kind === "image") {
      el.video.pause(); el.video.style.display = "none"; el.video.style.opacity = 0;
      if (el.img.getAttribute("src") !== v.url) { el.img.style.opacity = 0; el.img.src = v.url; el.img.onload = () => { el.img.style.opacity = 1; }; } else el.img.style.opacity = 1;
      el.img.style.display = ""; const z = 1 + Math.random() * 0.18; el.img.style.setProperty("--z", z.toFixed(2)); el.img.style.setProperty("--ox", (35 + Math.random() * 30).toFixed(0) + "%"); el.img.style.setProperty("--oy", (35 + Math.random() * 30).toFixed(0) + "%");
    } else if (v.kind === "shot") {
      el.img.style.opacity = 0; el.img.style.display = "none"; el.video.style.display = ""; el.video.style.setProperty("--z", "1");
      const vid = el.video; if (videoStop) { vid.removeEventListener("timeupdate", videoStop); videoStop = null; }
      const start = () => { vid.currentTime = Math.max(0, v.start || 0); vid.style.opacity = 1; vid.play().catch(() => {}); videoStop = () => { if (vid.currentTime >= (v.end || 1e9)) vid.pause(); }; vid.addEventListener("timeupdate", videoStop); };
      if (vid.getAttribute("src") !== v.url) { vid.src = v.url; vid.onloadedmetadata = start; } else start();
    }
  }
  function showCard(kind, extra) {
    if (!kind || kind === "none") { el.card.classList.remove("on"); return; }
    let rows = [];
    if (kind === "price") rows = bundle.cards?.price || [];
    else if (kind === "facts") rows = bundle.cards?.facts || [];
    else if (kind === "summary") rows = [...(bundle.cards?.facts || []).slice(0, 4), ...(bundle.cards?.price || []).slice(0, 2)];
    else if (kind === "cite" && extra) rows = extra.map((f) => ({ claim: f.claim, value: f.value, conditions: f.source?.locator ? `source ${f.source.ref} ${f.source.locator}` : "" }));
    if (!rows.length) { el.card.classList.remove("on"); return; }
    el.card.replaceChildren(h("h4", {}, kind === "cite" ? "Sources for that answer" : kind === "price" ? "Price & offers" : kind === "summary" ? "In short" : "Key facts"), ...rows.map((r) => h("div", { class: "row" }, h("span", {}, r.claim, r.conditions ? h("div", { class: "cond" }, r.conditions) : null), h("b", {}, r.value))));
    el.card.classList.add("on");
  }

  // ---------- voice out ----------
  function browserVoice() {
    if (S.bt.voice) return S.bt.voice;
    const vs = speechSynthesis.getVoices().filter((v) => /^en/i.test(v.lang));
    const score = (v) => { let s = 0; const n = v.name; if (/neerja|veena|heera/i.test(n)) s += 60; if (/google uk english female|google us english$/i.test(n)) s += 45; if (/samantha|kate\b|serena|karen|moira|zira|jenny|aria|sonia|libby|emma|olivia|amy\b|joanna|salli|natasha/i.test(n)) s += 30; if (/en-IN/i.test(v.lang)) s += 12; if (/natural|premium|enhanced|neural|online/i.test(n)) s += 8; if (/rishi|daniel|alex\b|fred|arthur|gordon|oliver|reed|tom\b|david|mark\b|james|guy\b|ryan|ravi|male|eddy|flo\b|grandma|grandpa|sandy|shelley|bahh|bells|boing|bubbles|cellos|wobble|zarvox|trinoids|whisper|jester|organ|superstar|good news|bad news|albert|junior|ralph|kathy/i.test(n)) s -= 70; return s; };
    S.bt.voice = vs.sort((a, b) => score(b) - score(a))[0] || null; return S.bt.voice;
  }
  function speakBrowser(text) {
    return new Promise((res) => { const my = ++S.ttsToken; const u = new SpeechSynthesisUtterance(text); const v = browserVoice(); if (v) u.voice = v; u.rate = 0.98; u.pitch = 1.05; let done = false; const fin = () => { if (done) return; done = true; res(my === S.ttsToken); }; const t = setTimeout(fin, Math.max(1500, text.length * 75) + 4000); u.onend = () => { clearTimeout(t); fin(); }; u.onerror = () => { clearTimeout(t); fin(); }; try { speechSynthesis.speak(u); } catch (e) { fin(); } });
  }
  async function audioUrlFor(text, preset) {
    if (preset) return preset;
    if (!useServerVoice) return null;
    if (S.ttsCache.has(text)) return S.ttsCache.get(text);
    const p = api.tts(text).catch(() => null); S.ttsCache.set(text, p); return p;
  }
  function prefetch(items) { if (!useServerVoice) return; for (const it of items) if (!it.audio && it.text) audioUrlFor(it.text); }
  async function speak(text, run, preset) {
    if (run !== S.run) return false;
    el.cap.textContent = text; if (S.intakeOpen) el.inQ.textContent = text; setStatus("speaking", "Speaking"); addMsg("agent", text);
    let url = null; try { url = await audioUrlFor(text, preset); } catch (e) {}
    if (run !== S.run) return false;
    let ok;
    if (url) ok = await new Promise((res) => { const my = ++S.ttsToken; const a = new Audio(url); S.audio = a; let done = false; const fin = () => { if (done) return; done = true; res(my === S.ttsToken); }; a.onended = fin; a.onerror = () => { done = true; speakBrowser(text).then(res); }; a.play().catch(() => { done = true; speakBrowser(text).then(res); }); });
    else ok = await speakBrowser(text);
    if (ok && run === S.run) setStatus("idle", "Ready");
    return ok && run === S.run;
  }
  function cancelSpeech() { S.ttsToken++; try { speechSynthesis.cancel(); } catch (e) {} if (S.audio) { try { S.audio.pause(); } catch (e) {} S.audio = null; } }

  // ---------- voice in ----------
  function listen({ timeout = 9000, onInterim = () => {} } = {}) {
    return new Promise((res) => {
      if (!SR || S.micDenied) { res(""); return; }
      try { if (S.rec) S.rec.abort(); } catch (e) {}
      const rec = new SR(); S.rec = rec; rec.lang = persona.language || "en-IN"; rec.interimResults = true; rec.continuous = false;
      let fin = "", interim = "", ended = false; S.micOn = true; setMicUI(true);
      const end = () => { if (ended) return; ended = true; S.micOn = false; setMicUI(false); clearTimeout(t); res((fin || interim).trim()); };
      rec.onresult = (e) => { interim = ""; fin = ""; for (const r of e.results) { if (r.isFinal) fin += r[0].transcript; else interim += r[0].transcript; } onInterim((fin || interim).trim()); };
      rec.onerror = (e) => { if (e.error === "not-allowed" || e.error === "service-not-allowed") S.micDenied = true; end(); };
      rec.onend = end; const t = setTimeout(() => { try { rec.stop(); } catch (e) {} }, timeout);
      try { rec.start(); } catch (e) { end(); }
    });
  }
  function stopListening() { try { if (S.rec) S.rec.abort(); } catch (e) {} S.micOn = false; setMicUI(false); }
  function setMicUI(on) { el.mic.classList.toggle("on", on); el.inMic.classList.toggle("on", on); if (on) { setStatus("listening", "Listening"); el.hint.textContent = "Listening… just talk."; } else { el.live.textContent = ""; if (el.status.classList.contains("listening")) setStatus("idle", "Your turn"); el.hint.textContent = SR ? "Tap to talk — I'll stop and listen." : "Use 💬 to type."; } }

  // ---------- flow ----------
  function interruptAll() { cancelSpeech(); stopListening(); newRun(); clearTimer(); if (S.waiter) { const w = S.waiter; S.waiter = null; w({ value: "__interrupted" }); } setChips([]); }
  function interpretReply(t, chips) {
    const s = t.toLowerCase().trim(), has = (v) => chips.some((c) => c.value === v), short = s.split(/\s+/).length <= 7;
    if (short && /^(yes|yeah|yep|ya\b|haan|ok|okay|sure|fine|good|great|perfect|continue|carry on|go on|go ahead|next|move on|proceed|that helps|clear|settled|got it|understood|thanks|thank you|alright|cool|makes sense)/.test(s)) return { value: has("yes") ? "yes" : has("continue") ? "continue" : "continue" };
    if (short && /^(no\b|nope|not really|not quite|still|unsure|not sure|tell me more|more\b|deeper|explain|elaborate|not clear|i'm not sure)/.test(s)) return { value: has("deeper") ? "deeper" : has("no") ? "no" : "deeper" };
    for (const c of bundle.ctas || []) if (s.includes(c.label.toLowerCase()) && has("cta:" + c.id)) return { value: "cta:" + c.id };
    if (/(not yet|later|think about|not now)/.test(s) && has("notyet")) return { value: "notyet" };
    if (/(human|person|advisor|someone|sales|team)/.test(s) && has("human")) return { value: "human" };
    return { value: "question", text: t };
  }
  function waitFor(chips, seconds, opts = {}) {
    return new Promise((res) => {
      S.waiter = res; setChips(chips); setStatus("idle", "Your turn");
      if (seconds > 0) { const t0 = Date.now(), total = seconds * 1000; el.timer.replaceChildren(h("div", { class: "r" }), h("span", {}, "I'll carry on in ", h("b", { id: "plTleft" }, seconds), "s unless you stop me"));
        S.timer = setInterval(() => { if (document.activeElement === el.q || S.micOn) return; const e = Date.now() - t0; const r = el.timer.querySelector(".r"); if (r) r.style.setProperty("--p", Math.min(100, e / total * 100) + "%"); const tl = el.timer.querySelector("#plTleft"); if (tl) tl.textContent = Math.max(0, Math.ceil((total - e) / 1000)); if (e >= total) resolveWait("__timeout"); }, 200); }
      if (opts.listen !== false && SR && !S.micDenied) listen({ timeout: 8000, onInterim: (t) => { el.live.textContent = t; } }).then((t) => { if (!S.waiter) return; if (t) { addMsg("user", t); resolveWait(interpretReply(t, chips)); } else el.hint.textContent = "Tap the mic to talk, or tap a chip."; });
    });
  }
  function resolveWait(v) { clearTimer(); stopListening(); if (S.waiter) { const w = S.waiter; S.waiter = null; setChips([]); w(typeof v === "string" ? { value: v } : v); } }

  function planSegments() {
    const segs = bundle.segments || []; const focus = new Set(S.profile.focus);
    const first = segs.filter((s, i) => i === 0); const pri = segs.filter((s, i) => i > 0 && (focus.has(s.topic) || focus.has(s.id))); const rest = segs.filter((s, i) => i > 0 && !pri.includes(s));
    S.plan = [...first, ...pri, ...rest]; S.seg = 0; renderProgress();
  }

  async function playFrom(segIdx, lineIdx = 0) {
    const run = newRun();
    for (let i = segIdx; i < S.plan.length; i++) {
      const seg = S.plan[i]; S.seg = i; S.atCheckin = false; renderProgress();
      prefetch([...seg.lines.slice(lineIdx), seg.checkin?.text ? { text: seg.checkin.text, audio: seg.checkin.audio } : null].filter(Boolean));
      for (let j = lineIdx; j < seg.lines.length; j++) { S.line = j; if (run !== S.run) return; const ln = seg.lines[j]; showVisual(ln.visual); showCard(ln.card); el.cite.textContent = ln.fact_ids?.length ? "sources: " + ln.fact_ids.join(", ") : ""; const ok = await speak(ln.text, run, ln.audio); if (!ok) return; }
      lineIdx = 0; if (run !== S.run) return;
      if (seg.checkin?.text) {
        S.atCheckin = true; const ok = await speak(seg.checkin.text, run, seg.checkin.audio); if (!ok) return;
        const conc = !!seg.priority; const chips = conc ? [{ label: "That settles it", value: "yes", primary: true }, { label: "Still unsure", value: "deeper" }, { label: "I have a question", value: "question" }] : [{ label: "Continue", value: "continue", primary: true }, { label: "Tell me more", value: "deeper" }, { label: "I have a question", value: "question" }];
        const r = await waitFor(chips, 15); if (run !== S.run) return;
        if (r.value === "yes") { S.resolved.add(seg.topic); const ok2 = await speak(pick(["Good.", "Great — moving on.", "Glad that helps."]), run); if (!ok2) return; }
        else if (r.value === "__timeout") { const ok2 = await speak(pick(["I'll keep going — interrupt me anytime.", "Carrying on. Stop me whenever."]), run); if (!ok2) return; }
        else if (r.value === "deeper") { S.raised.add(seg.topic); prefetch(seg.deeper || []); for (const ln of seg.deeper || []) { showVisual(ln.visual); const ok2 = await speak(ln.text, run, ln.audio); if (!ok2) return; }
          if (!(seg.deeper || []).length) { const ok3 = await speak("That's everything the material covers on this — ask me anything specific and I'll check.", run); if (!ok3) return; }
          const ok3 = await speak(pick(["Does that help?", "Is that clearer?"]), run); if (!ok3) return;
          const r2 = await waitFor([{ label: "Yes, continue", value: "yes", primary: true }, { label: "Not really", value: "no" }, { label: "Question", value: "question" }], 15); if (run !== S.run) return;
          if (r2.value === "yes") S.resolved.add(seg.topic); else if (r2.value === "no") { S.unresolved.add(seg.topic); S.escalations.push(`${seg.topic} — still unsure after the deeper explanation`); const ok4 = await speak(`Then let's not paper over it — I've flagged ${seg.topic} for someone from the team to take up with you properly. Let me carry on for now.`, run); if (!ok4) return; }
          else if (r2.value === "question") { if (r2.text) handleQuestion(r2.text); else listenForQuestion(); return; } else if (r2.value === "__interrupted") return; }
        else if (r.value === "question") { if (r.text) handleQuestion(r.text); else listenForQuestion(); return; }
        else if (r.value === "__interrupted") return;
      }
    }
    await closeFlow(run);
  }

  async function closeFlow(run) {
    S.atCheckin = true;
    for (const ln of bundle.closing || []) { showVisual(ln.visual); showCard(ln.card); const ok = await speak(ln.text, run, ln.audio); if (!ok) return; }
    const chips = (bundle.ctas || []).map((c) => ({ label: c.label, value: "cta:" + c.id, primary: !!c.primary })).concat([{ label: "Not yet", value: "notyet" }, { label: "One more question", value: "question" }]);
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

  async function handleQuestion(text) {
    const wasAtCheckin = S.atCheckin; interruptAll(); const run = newRun();
    addMsg("user", text); S.questions.push(text); el.live.textContent = ""; setStatus("thinking", "Thinking"); el.cap.textContent = "…";
    let r;
    try { r = await api.qa({ question: text, history: S.transcript.slice(-8).map((t) => ({ role: t.role, text: t.text })), profile: S.profile }); }
    catch (e) { if (run !== S.run) return; const ok = await speak("I couldn't reach my notes just now — give me a second and ask again, or I'll flag it for the team.", run); if (!ok) return; S.escalations.push(`error answering: "${text}"`); resumeAfterQA(wasAtCheckin); return; }
    if (run !== S.run) return;
    if (r.visual) showVisual({ ...r.visual, url: mediaUrlFor(r.visual), focus: "" });
    if (r.facts?.length) showCard("cite", r.facts); else showCard("none");
    el.cite.textContent = r.fact_ids?.length ? "sources: " + r.fact_ids.join(", ") : (r.answered ? "" : "not in the sources — flagged");
    if (r.escalate) S.escalations.push(r.escalate); if (r.topic && r.topic !== "other") S.raised.add(r.topic);
    const ok = await speak(r.answer, run); if (!ok) return;
    if (r.cta) { await ctaFlow(r.cta, run); return; }
    if (!r.answered) { const rr = await waitFor([{ label: "Continue", value: "continue", primary: true }, { label: "Talk to a person", value: "human" }], 15); if (run !== S.run) return; if (rr.value === "human") { await ctaFlow(contactCta(), run); return; } if (rr.value === "question" && rr.text) { handleQuestion(rr.text); return; } resumeAfterQA(wasAtCheckin); return; }
    const ok2 = await speak(pick(["Did that answer it?", "Does that cover your concern?", "Is that what you needed?"]), run); if (!ok2) return;
    const r2 = await waitFor([{ label: "Yes, that helps", value: "yes", primary: true }, { label: "Not quite", value: "no" }], 20); if (run !== S.run) return;
    if (r2.value === "yes") { S.resolved.add(r.topic || "question"); const ok3 = await speak(pick(["Good.", "Glad that helps.", "Okay."]), run); if (!ok3) return; resumeAfterQA(wasAtCheckin); }
    else if (r2.value === "no") { S.unresolved.add(r.topic || "question"); S.escalations.push(`not satisfied: "${text}"`); const ok3 = await speak("Then I'll have someone from the team pick that up with you — I've noted the exact question. Shall I continue meanwhile?", run); if (!ok3) return; const r3 = await waitFor([{ label: "Continue", value: "continue", primary: true }, { label: "Talk to a person", value: "human" }], 15); if (run !== S.run) return; if (r3.value === "human") { await ctaFlow(contactCta(), run); return; } if (r3.value === "question" && r3.text) { handleQuestion(r3.text); return; } resumeAfterQA(wasAtCheckin); }
    else if (r2.value === "question" && r2.text) handleQuestion(r2.text);
    else resumeAfterQA(wasAtCheckin);
  }
  function contactCta() { const c = (bundle.ctas || []).find((x) => x.kind === "contact") || (bundle.ctas || [])[0]; return c ? c.id : "contact"; }
  function mediaUrlFor(v) { if (!v) return null; const src = v.source_id; for (const vid of bundle.media?.videos || []) if (v.kind === "shot" && vid.url.includes(src)) return vid.url; for (const im of bundle.media?.images || []) if (im.id === v.ref) return im.url; return (bundle.media?.videos || [])[0]?.url || null; }
  function resumeAfterQA(wasAtCheckin) { const seg = S.plan[S.seg]; if (!seg) return; if (S.seg >= S.plan.length - 1 && wasAtCheckin && S.atCheckin && !S.plan[S.seg].checkin?.text) { closeFlow(newRun()); return; } if (wasAtCheckin) playFrom(S.seg + 1, 0); else { const run = newRun(); speak(pick(["Picking up where we left off.", "Back to where we were."]), run).then((ok) => { if (ok) playFrom(S.seg, S.line); }); } }

  // ---------- intake ----------
  function intakeWait(run) {
    return new Promise((res) => {
      let done = false; const fin = (t) => { if (done) return; done = true; S.intakeResolver = null; stopListening(); res(t); }; S.intakeResolver = fin; el.inHeard.textContent = "";
      if (SR && !S.micDenied) { el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; listen({ timeout: 10000, onInterim: (t) => { el.inHeard.textContent = t; } }).then((t) => { if (done || run !== S.run) return; if (t) fin(t); else { el.inState.textContent = "Tap the mic to try again, or type below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); } }); }
      else { el.inState.textContent = "Type your answer below"; el.inState.className = "state"; el.inFallback.classList.add("open"); setTimeout(() => el.inText.focus(), 50); }
    });
  }
  async function intakeMic() { if (S.micOn) { stopListening(); return; } if (!S.intakeResolver) return; cancelSpeech(); const fin = S.intakeResolver; el.inState.textContent = "Listening — just talk"; el.inState.className = "state listening"; const t = await listen({ timeout: 10000, onInterim: (x) => { el.inHeard.textContent = x; } }); if (t && S.intakeResolver === fin) fin(t); else if (S.intakeResolver === fin) { el.inState.textContent = "Tap the mic to try again, or type below"; el.inFallback.classList.add("open"); } }
  function parseName(t) { let m = t.match(/(?:my name is|i am|i'm|this is|myself|name's|call me)\s+([A-Za-z][a-z]+)/i); if (m) return cap(m[1]); m = t.match(/^([A-Za-z][a-z]+)\s+(?:here|speaking)\b/i); if (m) return cap(m[1]); const w = t.trim().split(/\s+/); if (w.length <= 2 && /^[A-Za-z]+$/.test(w[0]) && !/^(hi|hello|hey|yes|no|ok|okay)$/i.test(w[0])) return cap(w[0]); return ""; }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1).toLowerCase();
  function parseFocus(t) { const out = []; const s = t.toLowerCase(); for (const c of bundle.intake?.chips || []) { const words = c.label.toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w)) || s.includes(c.key.toLowerCase())) out.push(c.key); } for (const seg of bundle.segments || []) { const words = (seg.title + " " + seg.topic).toLowerCase().split(/[^a-z0-9]+/).filter((w) => w.length > 3); if (words.some((w) => s.includes(w))) out.push(seg.topic); } return [...new Set(out)].slice(0, 4); }
  const isGetGoing = (t) => /^(no|nope|nothing|not really|nah|that's it|thats it|all good|go ahead|get going|let's go|lets go|start|go on|carry on|continue|proceed|begin|just go|show me)/i.test(t.trim()) || /(get going|go ahead|let'?s (go|start|begin)|nothing (specific|else|in particular)|just (go|start|show))/i.test(t);

  async function runIntake() {
    const run = newRun(); S.intakeOpen = true; el.intake.classList.add("open"); el.inFallback.classList.remove("open");
    const q1 = bundle.intake?.q1 || `Hi, I'm ${guide}. Before we begin — could I get your name, and what's got you interested in ${bundle.product?.name || "this"}?`;
    const q2 = bundle.intake?.q2 || "Is there anything specific you'd like me to focus on, or shall we get going?";
    el.inState.textContent = guide;
    const ok = await speak(q1, run, bundle.intake?.audio?.q1); if (!ok) return;
    const a1 = await intakeWait(run); if (run !== S.run) return;
    if (a1) { addMsg("user", a1); S.profile.name = parseName(a1); S.profile.why = a1; S.profile.focus = parseFocus(a1); }
    const ack = a1 ? (S.profile.name ? pick([`Lovely to meet you, ${S.profile.name}.`, `Thanks, ${S.profile.name}.`]) : "Thanks for that.") + (S.profile.focus.length ? " I'll make sure we cover that properly." : "") : "No problem — we'll keep it general.";
    const ok2 = await speak(ack + " " + q2, run, a1 ? null : null); if (!ok2) return;
    const a2 = await intakeWait(run); if (run !== S.run) return;
    if (a2) { addMsg("user", a2); if (!isGetGoing(a2)) { S.profile.focus = [...new Set([...S.profile.focus, ...parseFocus(a2)])]; S.profile.why += " | " + a2; const ok3 = await speak(S.profile.focus.length ? "Got it — I'll spend proper time on that. Here we go." : "Noted — I'll keep that in mind. Here we go.", run); if (!ok3) return; } else { const ok3 = await speak(pick(["Let's go.", "Alright — here we go."]), run); if (!ok3) return; } }
    else { const ok3 = await speak("Alright — let's get going.", run); if (!ok3) return; }
    el.intake.classList.remove("open"); S.intakeOpen = false; planSegments(); playFrom(0, 0);
  }
  function skipIntake() { interruptAll(); el.intake.classList.remove("open"); S.intakeOpen = false; S.intakeResolver = null; planSegments(); playFrom(0, 0); }

  // ---------- handoff ----------
  function intentScore() { let s = 20; s += Math.min(30, S.questions.length * 8); s += S.resolved.size * 8; s += S.seg >= S.plan.length - 1 ? 15 : 0; if (S.cta && S.cta !== "summary") s += 30; s -= S.unresolved.size * 5; return Math.max(5, Math.min(98, s)); }
  function showHandoff(c) {
    const mins = Math.round((Date.now() - S.started) / 6000) / 10; const topics = [...S.raised];
    const session = { profile: S.profile, questions: S.questions, escalations: S.escalations, resolved: [...S.resolved], unresolved: [...S.unresolved], cta: S.cta, intent: intentScore(), drop_point: S.plan[S.seg]?.title, minutes: mins, transcript: S.transcript };
    el.handoffBox.replaceChildren(h("h2", {}, c ? c.label : "Your summary"), h("div", { class: "sub" }, `what the guide passes to the team · ${mins} min`),
      h("div", { class: "grid2" },
        h("div", { class: "kvbox" }, h("h5", {}, "Intent"), h("div", { class: "score" }, intentScore(), h("small", {}, " / 100"))),
        h("div", { class: "kvbox" }, h("h5", {}, "Profile"), h("ul", {}, h("li", {}, S.profile.name || "Name not given"), S.profile.why ? h("li", {}, "Why: “", S.profile.why.slice(0, 140), "”") : null, h("li", {}, "Focus: ", S.profile.focus.join(", ") || "none stated"))),
        h("div", { class: "kvbox" }, h("h5", {}, "Concerns raised → resolved"), h("ul", {}, topics.length ? topics.map((t) => h("li", {}, t, ": ", h("b", { style: `color:${S.resolved.has(t) ? "var(--accent)" : S.unresolved.has(t) ? "var(--warn)" : "var(--muted)"}` }, S.resolved.has(t) ? "resolved" : S.unresolved.has(t) ? "still unsure" : "discussed"))) : h("li", {}, "none raised explicitly"))),
        h("div", { class: "kvbox" }, h("h5", {}, `Questions asked (${S.questions.length})`), h("ul", {}, S.questions.length ? S.questions.map((q) => h("li", {}, "“", q, "”")) : h("li", {}, "none — listened through"))),
        h("div", { class: "kvbox", style: "grid-column:1/-1" }, h("h5", {}, "For a human to follow up"), h("ul", {}, S.escalations.length ? S.escalations.map((e) => h("li", {}, e)) : h("li", {}, "nothing outstanding"))),
        h("div", { class: "kvbox", style: "grid-column:1/-1" }, h("h5", {}, "Drop point"), h("ul", {}, h("li", {}, `Reached: ${S.plan[S.seg]?.title || "—"} (${S.seg + 1} of ${S.plan.length} sections)`)))),
      h("div", { style: "display:flex;gap:10px;margin-top:14px" }, h("button", { class: "btn primary", onclick: () => { el.handoff.classList.remove("open"); api.saveSession(session).catch(() => {}); addMsg("note", "session saved"); const run = newRun(); speak(c ? "Done — everything we discussed goes with it. Thanks for your time." : "Thanks for your time. Ask me anything else whenever you're ready.", run); } }, c ? "Confirm (mock)" : "Done"), h("button", { class: "btn ghost", onclick: () => { el.handoff.classList.remove("open"); const run = newRun(); speak("Sure — what else would you like to know?", run).then((ok) => { if (ok) listenForQuestion(); }); } }, "Back to the demo")));
    el.handoff.classList.add("open"); api.saveSession(session).catch(() => {});
  }

  // ---------- lifecycle ----------
  function restart() { interruptAll(); el.handoff.classList.remove("open"); S.questions.length = 0; S.transcript.length = 0; S.escalations.length = 0; S.resolved.clear(); S.unresolved.clear(); S.raised.clear(); S.cta = null; S.started = Date.now(); S.profile = { name: "", why: "", focus: [] }; el.thread.replaceChildren(); showCard("none"); runIntake(); }
  function pause() { interruptAll(); setStatus("idle", "Paused"); }
  function context() { const seg = S.plan[S.seg]; return { segment: seg?.id, segment_title: seg?.title, line_index: S.line, line_text: seg?.lines?.[S.line]?.text, questions: S.questions.slice(-5), profile: S.profile, escalations: S.escalations.slice(-5) }; }
  function destroy() { S.destroyed = true; interruptAll(); root.remove(); }

  renderCtas(); showVisual({ kind: "image", url: bundle.media?.hero, focus: "" });
  if (bundle.media?.hero && /\.(mp4|mov|webm|m4v)$/i.test(bundle.media.hero)) showVisual({ kind: "shot", url: bundle.media.hero, start: 0, end: 4 });
  const startBtn = h("div", { class: "pl-intake open" }, h("div", { class: "inner" }, h("div", { class: "orb" }, h("div", { class: "r" })), h("div", { class: "state" }, guide), h("p", { class: "q" }, `A voice-led walkthrough of ${bundle.product?.name || bundle.name}. Just talk — interrupt anytime.`), h("div", { class: "actions" }, h("button", { class: "btn primary", onclick: () => { startBtn.remove(); runIntake(); } }, "▶ Start"), h("button", { class: "btn ghost", onclick: () => { startBtn.remove(); skipIntake(); } }, "Skip the intro"))));
  el.stage.append(startBtn);
  return { destroy, restart, pause, context };
}
