import { api, h, toast, esc } from "/web/api.js";

const CARD_DEFS = [
  { key: "visuals", n: "1", title: "Visuals" },
  { key: "facts", n: "2", title: "Facts" },
  { key: "pitch", n: "3", title: "Pitch" },
  { key: "persona", n: "4", title: "Persona & voice" },
  { key: "ctas", n: "5", title: "Calls to action" },
];
const PHASE_TITLES = { reading: ["Reading your sources…", "Gemini is watching the footage; Claude is building the fact registry."], building: ["Building your demo…", "Writing the script, recording narration, rehearsing it against likely questions."] };

export function renderAlign(ctx) {
  const { demoId, area } = ctx;
  let state = ctx.state; let demo = state.demo; let cards = state.cards; let conversation = state.conversation || [];
  const seen = new Set(conversation.map((m) => m.t));
  let openCard = null;

  const overlay = h("div", { class: "overlay hidden" });
  const logEl = h("div", { class: "progress-log" });
  const cardsCol = h("div", { class: "cards" });
  const thread = h("div", { class: "thread" });
  const dockTa = h("textarea", { placeholder: "Say what's wrong, or what to change. Attach images or documents if that's the fix." });
  const fileIn = h("input", { type: "file", multiple: true, accept: "video/*,image/*,.pdf,.docx,.txt,.md,.csv" });
  const attachRow = h("div", { class: "attach" });
  const sendBtn = h("button", { class: "btn primary", onclick: send }, "Send");
  const buildBar = h("div", { class: "build-bar hidden" }, h("span", {}, "All five cards approved."), h("button", { class: "btn primary", onclick: build }, "Build the demo →"));
  let pending = [];

  area.replaceChildren(overlay, h("div", { class: "align" }, cardsCol,
    h("div", { class: "convo" }, thread, buildBar,
      h("div", { class: "dock" }, attachRow,
        h("div", { class: "box" }, h("button", { class: "btn ghost", title: "Attach files", onclick: () => fileIn.click() }, "📎"), dockTa, sendBtn, fileIn),
        h("div", { class: "hint" }, "Enter to send · Shift+Enter for a new line · everything you say here goes to the alignment agent, which decides what to re-run")))));

  fileIn.addEventListener("change", () => { pending.push(...fileIn.files); fileIn.value = ""; renderAttach(); });
  dockTa.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  function renderAttach() { attachRow.replaceChildren(...pending.map((f, i) => h("span", {}, f.name, " ", h("a", { href: "#", onclick: (e) => { e.preventDefault(); pending.splice(i, 1); renderAttach(); } }, "✕")))); }

  // ---------- overlay ----------
  function showOverlay(kind, error) {
    const [title, sub] = PHASE_TITLES[kind] || ["Working…", ""];
    overlay.classList.remove("hidden");
    overlay.replaceChildren(h("div", { class: "box" }, error ? null : h("div", { class: "ring" }), h("h2", {}, error ? "Something went wrong" : title), h("p", { class: "sub" }, error ? "" : sub), logEl,
      error ? h("div", { class: "err" }, error) : null,
      error ? h("div", { class: "actions" }, h("button", { class: "btn", onclick: () => { overlay.classList.add("hidden"); } }, "Back to the cards"), h("button", { class: "btn primary", onclick: retry }, "Retry")) : null));
    ctx.setRailStatus(kind);
  }
  function hideOverlay() { overlay.classList.add("hidden"); }
  async function retry() {
    try { if (demo.status === "error" && !cards) await api.post(`/api/demos/${demoId}/read`); else if (Object.values(demo.approvals).every(Boolean)) await api.post(`/api/demos/${demoId}/build`); else await api.post(`/api/demos/${demoId}/read`); logEl.replaceChildren(); showOverlay(cards ? "building" : "reading"); }
    catch (e) { toast(e.message, true); }
  }
  function logLine(ev) { const d = h("div", {}, ev.stage ? h("span", { class: "stage" }, ev.stage + " · ") : null, ev.message); logEl.append(d); logEl.scrollTop = logEl.scrollHeight; }

  // ---------- cards ----------
  function renderCards() {
    const approvals = demo.approvals || {};
    const current = CARD_DEFS.find((c) => !approvals[c.key])?.key;
    if (openCard === null) openCard = current || "visuals";
    cardsCol.replaceChildren(...CARD_DEFS.map((c) => {
      const el = h("div", { class: `acard${approvals[c.key] ? " approved" : ""}${current === c.key ? " current" : ""}${openCard === c.key ? " open" : ""}` },
        h("div", { class: "head", onclick: () => { openCard = openCard === c.key ? "" : c.key; renderCards(); } }, h("span", { class: "n" }, approvals[c.key] ? "✓" : c.n), h("h3", {}, c.title), h("span", { class: "st" }, approvals[c.key] ? "approved" : current === c.key ? "review now" : "pending")),
        h("div", { class: "body" }, cards ? body(c.key) : h("p", { class: "muted small", style: "margin-top:10px" }, "Waiting for the sources to be read."),
          cards ? h("div", { class: "actions" },
            approvals[c.key] ? h("button", { class: "btn sm ghost", onclick: () => setApproval(c.key, false) }, "Un-approve") : h("button", { class: "btn sm primary", onclick: () => setApproval(c.key, true) }, "Approve"),
            h("button", { class: "btn sm ghost", onclick: () => { dockTa.value = ({ visuals: "About the visuals: ", facts: "About the facts: ", pitch: "About the pitch: ", persona: "About the persona and voice: ", ctas: "About the calls to action: " })[c.key]; dockTa.focus(); } }, "Give feedback")) : null));
      return el;
    }));
    buildBar.classList.toggle("hidden", !(cards && CARD_DEFS.every((c) => approvals[c.key]) && demo.status !== "ready"));
  }

  function body(key) {
    if (key === "visuals") {
      const v = cards.visuals;
      return h("div", {},
        h("p", { class: "small muted", style: "margin:10px 0 0" }, `${v.shots.length} video shots · ${v.images.length} images · ${v.segments.length} planned segments`),
        v.shots.length ? h("div", { class: "thumbs" }, ...v.shots.slice(0, 24).map((s) => h("div", { class: "thumb", title: s.description }, h("video", { src: `${s.url}#t=${(s.start + 0.2).toFixed(1)}`, preload: "metadata", muted: true, playsinline: true }), h("div", { class: "cap" }, `${s.id} · ${s.start.toFixed(0)}–${s.end.toFixed(0)}s · q${s.quality}`)))) : null,
        v.images.length ? h("div", { class: "thumbs" }, ...v.images.map((i) => h("div", { class: "thumb", title: i.description }, h("img", { src: i.url, alt: i.description }), h("div", { class: "cap" }, `${i.id} · ${i.angle} · q${i.quality}`)))) : null,
        ...v.gaps.map((g) => h("div", { class: "gap" }, h("b", {}, "Missing: "), g.what, " — ", g.why, h("div", { class: "small muted" }, "Suggested: ", g.suggestion))),
        Object.keys(v.video_summaries || {}).length ? h("p", { class: "small muted", style: "margin:10px 0 0" }, Object.values(v.video_summaries).join(" ")) : null);
    }
    if (key === "facts") {
      const f = cards.facts;
      const rows = f.facts.map((x) => h("tr", { class: (x.edited ? "edited" : "") + (x.approved === false ? " removed" : "") },
        h("td", { class: "id" }, x.id), h("td", {}, h("b", {}, x.claim), h("br"), x.value, x.conditions ? h("span", { class: "muted" }, ` (${x.conditions})`) : null),
        h("td", { class: "src" }, `${x.source?.ref || ""} ${x.source?.locator || ""}`, x.source?.quote ? h("div", { title: x.source.quote }, "“", x.source.quote.slice(0, 50), x.source.quote.length > 50 ? "…" : "", "”") : null),
        h("td", {}, h("button", { class: "btn sm ghost", title: "Correct this fact", onclick: () => { dockTa.value = `${x.id} (${x.claim}) is wrong — the correct value is `; dockTa.focus(); } }, "fix"))));
      const open = f.unknowns.filter((u) => u.status === "open");
      return h("div", {},
        h("p", { class: "small muted", style: "margin:10px 0 0" }, `${f.facts.length} facts from ${f.sources.length} source${f.sources.length === 1 ? "" : "s"}. The guide can only say what's in this table.`),
        h("div", { style: "max-height:360px;overflow:auto" }, h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "fact"), h("th", {}, "source"), h("th", {}, ""))), h("tbody", {}, ...rows))),
        open.length ? h("div", {}, h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin:14px 0 4px;gap:8px;flex-wrap:wrap" }, h("p", { class: "eyebrow", style: "margin:0" }, `${open.length} questions the sources don't answer`), h("a", { class: "btn sm", href: `/api/demos/${demoId}/faq-template`, download: `FAQ-${demoId}.md`, title: "A Markdown file with every open question grouped by category — fill the answers and upload it here" }, "Download FAQ template")),
          h("p", { class: "small muted", style: "margin:0 0 6px" }, "Grouped by what would answer them. Finance and insurance questions need their own documents — the guide declines these rather than guessing."),
          ...(() => { const cats = { pricing: "Pricing & offers", finance: "Finance / EMI", insurance: "Insurance", warranty_service: "Warranty & service", features: "Features & specs", availability: "Availability & delivery", comparison: "Comparisons", usage: "Usage & ownership", other: "Other" }; const groups = {}; for (const u of open) (groups[u.category || "other"] ||= []).push(u); return Object.keys(cats).filter((k) => groups[k]).map((k) => { const docs = [...new Set(groups[k].map((u) => u.suggested_document).filter(Boolean))]; return h("div", { class: "unk-group" }, h("p", { class: "eyebrow" }, `${cats[k]} · ${groups[k].length}`), docs.length ? h("p", { class: "doc" }, "upload: " + docs.join(" · ")) : null, h("div", { class: "unknowns" }, ...groups[k].map((u) => h("div", { class: "unk" }, h("span", { class: "id" }, u.id), h("span", {}, u.question, u.origin === "rehearsal" ? h("span", { class: "muted" }, " · from rehearsal") : u.origin === "runtime" ? h("span", { class: "muted" }, " · asked in a demo") : null))))); }); })()) : null,
        f.script_issues?.length ? h("div", { class: "gap" }, h("b", {}, "Script lines held back: "), f.script_issues.length, " — they stated something without a citation and were excluded from narration.") : null);
    }
    if (key === "pitch") {
      const pt = cards.pitch || {};
      const roleLabel = { intro: "standard opening · frame", outcome: "standard opening · outcome first", proof: "proof block", establish: "establish" };
      return h("div", {},
        h("div", { class: "kv" }, h("span", { class: "k" }, "Decision"), h("span", {}, pt.decision_frame || "—"), h("span", { class: "k" }, "Takeaway"), h("span", {}, h("b", {}, pt.takeaway || "—")), h("span", { class: "k" }, "Proves"), h("span", {}, pt.primary_outcome || "—", (pt.supporting_outcomes || []).length ? h("div", { class: "muted small" }, "then: " + pt.supporting_outcomes.join(" · ")) : null), h("span", { class: "k" }, "Advance"), h("span", {}, pt.advance || "—"), h("span", { class: "k" }, "Won't recommend if"), h("span", { class: "muted" }, pt.do_not_recommend_if || "—"), h("span", { class: "k" }, "Language"), h("span", {}, pt.language || "en-IN")),
        h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, `${(pt.usps || []).length} USPs`),
        h("ul", { class: "gaplist", style: "color:var(--ink)" }, ...(pt.usps || []).map((u) => h("li", {}, h("b", {}, u.name), " — ", h("span", { class: "muted" }, u.why_it_matters), u.fact_ids?.length ? h("span", { class: "mono small muted" }, ` [${u.fact_ids.join(", ")}]`) : h("span", { class: "small", style: "color:var(--warn)" }, " · no facts — a claim")))),
        h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, "Blocks"),
        h("div", { class: "unknowns" }, ...(pt.segments || []).map((s) => h("div", { class: "unk" }, h("span", { class: "id" }, s.role === "intro" || s.role === "outcome" ? "fixed" : s.role), h("span", {}, h("b", {}, s.title), s.outcome ? h("span", { class: "muted" }, ` — ${s.outcome}`) : null, h("div", { class: "small muted" }, roleLabel[s.role] || s.role, s.usp_ids?.length ? ` · usps ${s.usp_ids.join(", ")}` : ""))))),
        (pt.state_questions || []).length ? h("div", {}, h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, "Follow-up by customer state"), h("ul", { class: "gaplist" }, ...pt.state_questions.map((q) => h("li", {}, h("b", {}, q.state.replace("_", " ")), ": ", q.question)))) : null,
        pt.scorecard ? h("p", { class: "small muted", style: "margin:12px 0 0" }, `Last scorecard: ${pt.scorecard.total}/20 — weakest: ${(pt.scorecard.weakest || []).slice(0, 2).join("; ")}`) : null,
        h("p", { class: "small muted", style: "margin:10px 0 0" }, "The first two blocks always play unchanged (the standard 1–2 minute opening). At runtime the guide plans the rest per buyer from these proof blocks."));
    }
    if (key === "persona") {
      const p = cards.persona;
      const sel = h("select", {}, h("option", { value: "" }, "loading voices…"));
      let vinfo = null;
      api.get(`/api/voices?demo_id=${demoId}`).then((v) => { vinfo = v; sel.replaceChildren(...v.voices.map((o) => h("option", { value: o.id, selected: o.id === v.current }, o.label))); provLbl.textContent = `Voice: ${v.provider}` + (v.chain.length > 1 ? ` → falls back to ${v.chain.slice(1).join(" → ")}` : "") + ` · Listening: ${v.stt === "sarvam" ? "Sarvam Saarika" : "browser"}`; }).catch(() => { sel.replaceChildren(h("option", { value: "" }, "browser voice")); });
      const provLbl = h("span", { class: "small muted" }, `Provider: ${p.provider || "…"}`);
      const sample = p.sample_audio ? h("audio", { controls: true, src: p.sample_audio, style: "width:100%;margin-top:10px" }) : h("p", { class: "small muted" }, p.provider === "browser" ? "No TTS key — the demo will use the browser voice." : "No sample yet.");
      return h("div", {},
        h("div", { class: "kv" }, h("span", { class: "k" }, "Persona"), h("span", {}, h("b", {}, p.persona_name), " — ", p.persona_description), h("span", { class: "k" }, "Tone"), h("span", {}, p.tone), h("span", { class: "k" }, "Sample line"), h("span", { class: "muted" }, "“", p.sample_line, "”"), h("span", { class: "k" }, "Brand"), h("span", { class: "small" }, p.brand?.voice_style || "", p.brand?.donts?.length ? h("div", { class: "muted" }, "Never: ", p.brand.donts.join("; ")) : null)),
        sample,
        h("div", { style: "display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap" }, h("span", { class: "eyebrow" }, "Voice"), sel, h("button", { class: "btn sm", onclick: async () => { if (!vinfo || !sel.value) return; try { await api.patch(`/api/demos/${demoId}`, { settings: { [vinfo.setting_key]: sel.value } }); await api.post(`/api/demos/${demoId}/voice/sample`, { text: p.sample_line }); toast("Sample re-recorded"); await reload(); } catch (e) { toast(e.message, true); } } }, "Re-record sample")),
        h("p", { class: "small muted", style: "margin:8px 0 0" }, provLbl, " · Say “warmer”, “more formal”, “a male voice” in the dock to change the persona."));
    }
    if (key === "ctas") {
      const list = cards.ctas.map((c) => ({ ...c }));
      const wrap = h("div", { class: "cta-list" });
      const draw = () => wrap.replaceChildren(...list.map((c, i) => h("div", { class: "cta-item" },
        h("input", { value: c.label, placeholder: "Label", oninput: (e) => (c.label = e.target.value) }),
        h("select", { onchange: (e) => (c.kind = e.target.value) }, ...["book", "reserve", "buy", "contact", "trial", "link", "custom"].map((k) => h("option", { value: k, selected: k === c.kind }, k))),
        h("input", { value: c.url || "", placeholder: "https://… (optional)", oninput: (e) => (c.url = e.target.value) }),
        h("span", {}, h("label", { class: "primary" }, h("input", { type: "radio", name: "primary", checked: !!c.primary, onchange: () => { list.forEach((x, j) => (x.primary = j === i)); } }), " primary"), " ", h("button", { class: "btn sm ghost", onclick: () => { list.splice(i, 1); draw(); } }, "✕")))));
      draw();
      return h("div", {}, h("p", { class: "small muted", style: "margin:10px 0 0" }, "Buttons the customer sees during the demo. The guide names the primary one at the end."), wrap,
        h("div", { style: "display:flex;gap:8px;margin-top:10px" }, h("button", { class: "btn sm ghost", onclick: () => { list.push({ id: "cta" + (list.length + 1), label: "", kind: "link", url: "", primary: false, when: "always" }); draw(); } }, "+ Add"),
          h("button", { class: "btn sm", onclick: async () => { const clean = list.filter((c) => c.label.trim()).map((c, i) => ({ ...c, id: c.id || "cta" + (i + 1), when: c.when || "always" })); try { await api.post(`/api/demos/${demoId}/ctas`, { ctas: clean }); toast("CTAs saved"); await reload(); } catch (e) { toast(e.message, true); } } }, "Save CTAs")));
    }
  }

  async function setApproval(card, on) {
    try { await api.post(`/api/demos/${demoId}/${on ? "approve" : "unapprove"}/${card}`); await reload(); if (on) { openCard = CARD_DEFS.find((c) => !demo.approvals[c.key])?.key || ""; renderCards(); } }
    catch (e) { toast(e.message, true); }
  }

  // ---------- conversation ----------
  function addMsg(m) {
    if (m.t && seen.has(m.t)) return; if (m.t) seen.add(m.t);
    const el = h("div", { class: "msg " + (m.role === "user" ? "user" : m.system ? "system" : "agent") }, m.text,
      m.attachments?.length ? h("div", { class: "att" }, "attached: " + m.attachments.map((a) => a.name).join(", ")) : null,
      m.notes?.length ? h("div", { class: "notes" }, m.notes.join(" · ")) : null);
    thread.append(el); thread.scrollTop = thread.scrollHeight;
  }
  function renderThread() { thread.replaceChildren(); seen.clear(); conversation.forEach(addMsg); if (!conversation.length) thread.append(h("div", { class: "msg system" }, "The agent will start the conversation once your sources are read.")); }

  async function send() {
    const text = dockTa.value.trim();
    if (!text && !pending.length) return;
    const fd = new FormData(); fd.append("message", text); fd.append("context", "align"); pending.forEach((f) => fd.append("files", f));
    dockTa.value = ""; const files = pending; pending = []; renderAttach();
    addMsg({ role: "user", text: text || "(files)", t: Date.now() / 1000, attachments: files.map((f) => ({ name: f.name })) });
    const thinking = h("div", { class: "msg agent thinking" }, "thinking…"); thread.append(thinking); thread.scrollTop = thread.scrollHeight;
    sendBtn.disabled = true;
    try { const r = await api.form(`/api/demos/${demoId}/align`, fd); thinking.remove(); addMsg(r.message); await reload(); }
    catch (e) { thinking.remove(); toast(e.message, true); }
    sendBtn.disabled = false;
  }

  async function build() { try { await api.post(`/api/demos/${demoId}/build`); logEl.replaceChildren(); showOverlay("building"); } catch (e) { toast(e.message, true); } }

  async function reload() {
    state = await api.get(`/api/demos/${demoId}`); demo = state.demo; cards = state.cards; conversation = state.conversation || [];
    renderCards(); conversation.forEach(addMsg); ctx.setRailStatus(demo.status);
    if (demo.status === "ready") buildBar.classList.add("hidden");
  }

  // ---------- events ----------
  ctx.subscribe((type, ev) => {
    if (type === "progress") logLine(ev);
    else if (type === "status") { demo.status = ev.status; ctx.setRailStatus(ev.status); if (ev.status === "reading" || ev.status === "building") showOverlay(ev.status); }
    else if (type === "message") addMsg(ev.message);
    else if (type === "phase_done") { if (ev.phase === "build") { hideOverlay(); reload().then(() => ctx.navigate(`#/studio/${demoId}/rehearse`)); } else { hideOverlay(); reload(); } }
    else if (type === "phase_error") showOverlay(demo.status === "building" ? "building" : "reading", ev.error);
  });

  // initial
  renderCards(); renderThread();
  if (demo.status === "reading" || demo.status === "building" || state.running) showOverlay(demo.status === "building" ? "building" : "reading");
  else if (demo.status === "error") { const st = Object.values(demo.stages).find((s) => s.status === "error"); showOverlay(cards ? "building" : "reading", st?.error || "unknown error"); }
}
