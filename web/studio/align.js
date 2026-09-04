import { api, h, toast, esc } from "/web/api.js";

const CARD_DEFS = [
  { key: "visuals", n: "1", title: "Visuals" },
  { key: "facts", n: "2", title: "Facts" },
  { key: "script", n: "3", title: "Script" },
  { key: "faq", n: "4", title: "FAQ bank" },
  { key: "persona", n: "5", title: "Persona & voice" },
  { key: "ctas", n: "6", title: "Calls to action" },
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
    const allDone = cards && CARD_DEFS.every((c) => approvals[c.key]);
    const noteEl = h("div", { class: "align-note" }, "Approve each card as-is or tell the agent what to change. Nothing here has to be complete — ", h("b", {}, "anything you don't provide, the guide will not answer"), "; it says so and offers a callback. ", cards && !allDone ? h("button", { class: "btn sm", style: "margin-left:6px", onclick: approveAll }, "Approve all") : null);
    cardsCol.replaceChildren(noteEl, ...CARD_DEFS.map((c) => {
      const el = h("div", { class: `acard${approvals[c.key] ? " approved" : ""}${current === c.key ? " current" : ""}${openCard === c.key ? " open" : ""}` },
        h("div", { class: "head", onclick: (e) => { if (e.target.closest("button")) return; openCard = openCard === c.key ? "" : c.key; renderCards(); } }, h("span", { class: "n" }, approvals[c.key] ? "✓" : c.n), h("h3", {}, c.title), h("span", { class: "st" }, approvals[c.key] ? "approved" : current === c.key ? "review now" : "pending"),
          cards ? h("span", { class: "hact" }, h("button", { class: "btn sm ghost", onclick: () => openPreview(c.key) }, "Preview"), approvals[c.key] ? h("button", { class: "btn sm ghost", onclick: () => setApproval(c.key, false) }, "Un-approve") : h("button", { class: "btn sm primary", onclick: () => setApproval(c.key, true) }, "Approve")) : null),
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
        v.shots.length ? h("div", { class: "thumbs" }, ...v.shots.map((s) => { const vid = h("video", { src: `${s.url}#t=${(s.start + 0.2).toFixed(1)}`, preload: "metadata", muted: true, playsinline: true }); return h("div", { class: "thumb", title: s.description, onclick: () => lightbox(vid, `${s.id} · ${s.start.toFixed(0)}–${s.end.toFixed(0)}s · ${s.description}`) }, vid, h("div", { class: "cap" }, `${s.id} · ${s.start.toFixed(0)}–${s.end.toFixed(0)}s · q${s.quality}`)); })) : null,
        v.images.length ? h("div", { class: "thumbs" }, ...v.images.map((i) => { const img = h("img", { src: i.url, alt: i.description }); return h("div", { class: "thumb", title: i.description, onclick: () => lightbox(img, `${i.id} · ${i.angle} · ${i.description}`) }, img, h("div", { class: "cap" }, `${i.id} · ${i.angle} · q${i.quality}`)); })) : null,
        h("p", { class: "small muted", style: "margin:8px 0 0" }, "Click a thumbnail to enlarge. Scroll inside the grid for more."),
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
    if (key === "script") {
      const pt = cards.script || {}; const tl = pt.timeline || {};
      const mmss = (t) => t == null ? "" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
      const roleLabel = { intro: "opening · frame", outcome: "opening · outcome", proof: "proof block", features: "more features", establish: "establish" };
      return h("div", {},
        h("div", { class: "kv" }, h("span", { class: "k" }, "Written"), h("span", { class: "small muted" }, pt.written_at ? new Date(pt.written_at * 1000).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) + ` · data/demos/${demoId}/script.json · demo v${pt.version}` : "not written yet"), h("span", { class: "k" }, "Decision"), h("span", {}, pt.decision_frame || "—"), h("span", { class: "k" }, "Takeaway"), h("span", {}, h("b", {}, pt.takeaway || "—")), h("span", { class: "k" }, "Length"), h("span", {}, tl.total_seconds ? `${mmss(tl.total_seconds)} in ${(tl.batches || []).length} batches of ≤ 20 s${tl.exact ? "" : " (estimated until voiced)"}` : "not written yet")),
        h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, `Winning points · ${(pt.usps || []).length}`),
        h("ul", { class: "gaplist", style: "color:var(--ink)" }, ...(pt.usps || []).map((u) => h("li", {}, h("b", {}, u.name), " — ", h("span", { class: "muted" }, u.why_it_matters)))),
        h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, "Batches"),
        h("div", { class: "unknowns" }, ...(pt.segments || []).map((sg) => h("div", { class: "unk", style: "flex-direction:column;align-items:stretch;gap:4px" },
          h("div", { style: "display:flex;gap:8px;align-items:center" }, h("span", { class: "id" }, mmss(sg.start)), h("b", {}, sg.title), h("span", { class: "muted small" }, roleLabel[sg.role] || sg.role, sg.duration ? ` · ${Math.round(sg.duration)} s` : ""), sg.duration > 20.5 ? h("span", { class: "pill warn" }, "over 20 s") : null),
          ...sg.lines.slice(0, 3).map((l) => h("div", { class: "small", style: "display:flex;gap:8px;align-items:flex-start" }, l.visual_url ? h("img", { src: l.visual_url, style: "width:44px;height:33px;object-fit:cover;border-radius:4px;flex:none" }) : h("span", { class: "mono muted", style: "width:44px;flex:none" }, "—"), h("span", {}, l.text))),
          sg.lines.length > 3 ? h("div", { class: "small muted" }, `+ ${sg.lines.length - 3} more line(s) — open Preview`) : null))),
        h("p", { class: "small muted", style: "margin:10px 0 0" }, "The first two batches always play unchanged. After the customer speaks, custom batches are written and voiced in the background while the opening plays, then the route continues. Open Preview for every line, second by second, with the picture on screen.")
      );
    }
    if (key === "faq") {
      const f = cards.faq || { entries: [] };
      return h("div", {},
        h("p", { class: "small muted", style: "margin:10px 0 0" }, `${f.answered} of ${f.total} answered from your sources. Known questions answer instantly in the guide's voice; the rest decline and offer a callback. New questions get a recorded "bear with me" and a live answer.`),
        h("div", { class: "unknowns" }, ...f.entries.slice(0, 8).map((e) => h("div", { class: "unk" }, h("span", { class: "pill " + (e.answered ? "ok" : "warn") }, e.answered ? "answered" : "declines"), h("span", {}, h("b", {}, e.question), h("div", { class: "small muted" }, (e.answer || "").slice(0, 140), (e.answer || "").length > 140 ? "…" : "")), e.audio ? h("button", { class: "btn sm ghost", onclick: () => new Audio(e.audio).play() }, "▶") : null))),
        f.entries.length > 8 ? h("p", { class: "small muted" }, `+ ${f.entries.length - 8} more — open Preview`) : null,
        h("p", { class: "small muted", style: "margin:8px 0 0" }, "Upload an FAQ document (name it with “FAQ”) to add your own questions; say “add a question about …” or “fix the answer to Q03” in the dock."));
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

  async function approveAll() {
    try { for (const c of CARD_DEFS) if (!demo.approvals[c.key]) await api.post(`/api/demos/${demoId}/approve/${c.key}`); await reload(); toast("All six cards approved — build when ready"); }
    catch (e) { toast(e.message, true); }
  }
  function openPreview(key) {
    const title = CARD_DEFS.find((c) => c.key === key)?.title || key;
    const box = h("div", { class: "preview" }, h("div", { class: "phead" }, h("h2", {}, title, h("span", { class: "muted small", style: "margin-left:10px" }, "full detail")), h("button", { class: "btn sm", onclick: () => bg.remove() }, "Close")), h("div", { class: "pbody" }, previewBody(key)));
    const bg = h("div", { class: "preview-bg", onclick: (e) => { if (e.target === bg) bg.remove(); } }, box);
    document.body.appendChild(bg);
    const esc = (e) => { if (e.key === "Escape") { bg.remove(); document.removeEventListener("keydown", esc); } }; document.addEventListener("keydown", esc);
  }
  function previewBody(key) {
    const mmss = (t) => t == null ? "" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
    if (key === "visuals") {
      const v = cards.visuals; const sc = cards.script || {}; const usedIn = {};
      for (const sg of sc.segments || []) for (const l of sg.lines || []) if (l.visual) (usedIn[l.visual] = usedIn[l.visual] || []).push(`${sg.title}: “${l.text.slice(0, 70)}…”`);
      return h("div", { class: "pgrid" }, ...v.images.map((i) => h("div", { class: "pcard" }, h("img", { src: i.url, alt: i.description, onclick: () => lightbox(h("img", { src: i.url }), i.description) }), h("div", { class: "small" }, h("b", {}, i.id), " · ", i.angle, " · quality ", i.quality, i.enhanced?.how && i.enhanced.how !== "none" ? h("span", { class: "pill ok", style: "margin-left:6px" }, "cleaned") : null), h("div", { class: "small muted" }, i.description), i.parts?.length ? h("div", { class: "small" }, h("b", {}, "shows: "), i.parts.join(", ")) : null, h("div", { class: "small muted" }, usedIn[i.id]?.length ? h("span", {}, h("b", {}, `used in ${usedIn[i.id].length} line(s): `), usedIn[i.id].slice(0, 3).join(" · ")) : "not used by any line yet"))),
        ...v.shots.map((sh) => h("div", { class: "pcard" }, h("video", { src: `${sh.url}#t=${(sh.start + 0.2).toFixed(1)}`, controls: true, preload: "metadata", muted: true }), h("div", { class: "small" }, h("b", {}, sh.id), ` · ${sh.start.toFixed(0)}–${sh.end.toFixed(0)} s · ${sh.part} · quality ${sh.quality}`), h("div", { class: "small muted" }, sh.description))));
    }
    if (key === "facts") {
      const f = cards.facts;
      return h("div", {}, h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "kind"), h("th", {}, "truth"), h("th", {}, "claim"), h("th", {}, "value"), h("th", {}, "conditions"), h("th", {}, "source"))), h("tbody", {}, ...f.facts.map((x) => h("tr", { class: x.approved === false ? "removed" : "" }, h("td", { class: "id" }, x.id), h("td", {}, x.kind), h("td", {}, x.truth || ""), h("td", {}, x.claim), h("td", {}, h("b", {}, x.value)), h("td", { class: "small muted" }, x.conditions || ""), h("td", { class: "src" }, `${x.source?.ref || ""} ${x.source?.locator || ""}`, x.source?.quote ? h("div", {}, "“", x.source.quote, "”") : null))))),
        h("h3", { style: "margin:16px 0 6px;font-size:14px" }, `${f.unknowns.filter((u) => u.status === "open").length} open questions the sources don't answer`),
        h("table", { class: "facts-table" }, h("tbody", {}, ...f.unknowns.filter((u) => u.status === "open").map((u) => h("tr", {}, h("td", { class: "id" }, u.id), h("td", {}, u.question), h("td", { class: "small muted" }, u.category, " · ", u.suggested_document))))));
    }
    if (key === "script") {
      const pt = cards.script || {}; const tl = pt.timeline || {};
      const rows = [];
      for (const sg of pt.segments || []) {
        for (const l of sg.lines || []) rows.push(h("tr", { class: l.unverified ? "removed" : "" }, h("td", { class: "id" }, mmss(l.start)), h("td", { class: "small muted" }, sg.title, h("br"), sg.role), h("td", {}, l.text), h("td", {}, l.visual_url ? h("img", { src: l.visual_url, style: "width:96px;height:72px;object-fit:cover;border-radius:6px;display:block" }) : null, h("div", { class: "mono small muted" }, l.visual || "—")), h("td", { class: "mono small" }, (l.fact_ids || []).join(", ") || "—"), h("td", { class: "small muted" }, l.card !== "none" ? l.card : "")));
        if (sg.checkin) rows.push(h("tr", {}, h("td", { class: "id" }, ""), h("td", { class: "small muted" }, "pause point"), h("td", { class: "muted" }, h("i", {}, sg.checkin)), h("td", {}), h("td", {}), h("td", {})));
      }
      for (const l of pt.closing || []) rows.push(h("tr", {}, h("td", { class: "id" }, mmss(l.start)), h("td", { class: "small muted" }, "closing"), h("td", {}, l.text), h("td", {}), h("td", { class: "mono small" }, (l.fact_ids || []).join(", ") || "—"), h("td", {})));
      return h("div", {},
        h("div", { class: "kv" }, h("span", { class: "k" }, "Decision"), h("span", {}, pt.decision_frame || "—"), h("span", { class: "k" }, "Takeaway"), h("span", {}, h("b", {}, pt.takeaway || "—")), h("span", { class: "k" }, "Primary outcome"), h("span", {}, pt.primary_outcome || "—"), h("span", { class: "k" }, "Supporting"), h("span", {}, (pt.supporting_outcomes || []).join("; ") || "—"), h("span", { class: "k" }, "Not for"), h("span", {}, pt.do_not_recommend_if || "—"), h("span", { class: "k" }, "Advance"), h("span", {}, pt.advance || "—"), h("span", { class: "k" }, "Intake"), h("span", {}, pt.intake?.q1 || "—", h("br"), pt.intake?.q2 || "")),
        h("h3", { style: "margin:16px 0 6px;font-size:14px" }, `Winning points`), h("ul", { class: "gaplist", style: "color:var(--ink)" }, ...(pt.usps || []).map((u) => h("li", {}, h("b", {}, u.name), " — ", u.why_it_matters, u.fact_ids?.length ? h("span", { class: "mono small muted" }, ` [${u.fact_ids.join(", ")}]`) : null))),
        h("h3", { style: "margin:16px 0 6px;font-size:14px" }, `Second by second · ${mmss(tl.total_seconds || 0)} total${tl.exact ? "" : " (estimated until voiced)"}`),
        h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "at"), h("th", {}, "batch"), h("th", {}, "the guide says"), h("th", {}, "on screen"), h("th", {}, "facts"), h("th", {}, "card"))), h("tbody", {}, ...rows)),
        (pt.visual_changes || []).length ? h("div", {}, h("h3", { style: "margin:16px 0 6px;font-size:14px" }, "Why these pictures"), h("ul", { class: "gaplist" }, ...pt.visual_changes.map((c) => h("li", {}, h("b", {}, c.line_id), `: ${c.from || "—"} → ${c.to} — ${c.why}`)))) : null,
        (pt.segments || []).some((sg) => sg.deeper?.length) ? h("div", {}, h("h3", { style: "margin:16px 0 6px;font-size:14px" }, "Only if asked (deeper lines)"), h("ul", { class: "gaplist" }, ...(pt.segments || []).flatMap((sg) => (sg.deeper || []).map((l) => h("li", {}, h("b", {}, sg.title), ": ", l.text))))) : null,
        pt.scorecard ? h("p", { class: "small muted", style: "margin:12px 0 0" }, `Scorecard ${pt.scorecard.total}/20 — weakest: ${(pt.scorecard.weakest || []).slice(0, 2).join("; ")}`) : null);
    }
    if (key === "faq") {
      const f = cards.faq || { entries: [] };
      return h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "question"), h("th", {}, "answer"), h("th", {}, "facts"), h("th", {}, ""))), h("tbody", {}, ...f.entries.map((e) => h("tr", { class: e.answered ? "" : "removed" }, h("td", { class: "id" }, e.id), h("td", {}, h("b", {}, e.question), h("div", { class: "small muted" }, e.origin)), h("td", {}, e.answer), h("td", { class: "mono small" }, (e.fact_ids || []).join(", ") || "—"), h("td", {}, e.audio ? h("button", { class: "btn sm ghost", onclick: () => new Audio(e.audio).play() }, "▶") : h("span", { class: "small muted" }, "voiced at build"))))));
    }
    if (key === "persona") {
      const p = cards.persona;
      return h("div", { class: "kv" }, h("span", { class: "k" }, "Name"), h("span", {}, h("b", {}, p.persona_name)), h("span", { class: "k" }, "Persona"), h("span", {}, p.persona_description), h("span", { class: "k" }, "Tone"), h("span", {}, p.tone), h("span", { class: "k" }, "Voice"), h("span", {}, `${p.provider || ""} ${p.voice_name || ""}`), h("span", { class: "k" }, "Sample"), h("span", {}, p.sample_audio ? h("audio", { controls: true, src: p.sample_audio }) : "—"), h("span", { class: "k" }, "Brand"), h("span", {}, JSON.stringify(p.brand || {})));
    }
    if (key === "ctas") return h("ul", { class: "gaplist", style: "color:var(--ink)" }, ...cards.ctas.map((c) => h("li", {}, h("b", {}, c.label), ` · ${c.kind}${c.primary ? " · primary" : ""}${c.url ? " · " + c.url : ""} · shown ${c.when || "always"}`)));
    return h("p", {}, "No preview for this card.");
  }
  function lightbox(node, cap) {
    const clone = node.cloneNode(true); clone.removeAttribute("style"); if (clone.tagName === "VIDEO") { clone.controls = true; clone.muted = false; }
    const lb = h("div", { class: "lightbox", onclick: () => lb.remove() }, clone, h("div", { class: "cap" }, cap || ""));
    document.body.appendChild(lb);
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

  const onVis = () => { if (document.visibilityState === "visible") reload().catch(() => {}); };
  document.addEventListener("visibilitychange", onVis);
  const poll = setInterval(() => { if (document.visibilityState === "visible" && !document.querySelector(".overlay")) reload().catch(() => {}); }, 30000);
  window.addEventListener("hashchange", () => { document.removeEventListener("visibilitychange", onVis); clearInterval(poll); }, { once: true });
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
