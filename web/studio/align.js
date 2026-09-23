import { api, h, toast, esc } from "/web/api.js";
import { renderSlide } from "/web/slide.js";
import { icon } from "/web/icons.js";
import { readinessQuery } from "/web/provider-readiness.js";

const CARD_DEFS = [
  { key: "visuals", n: "1", title: "Visuals", icon: "image" },
  { key: "facts", n: "2", title: "Facts", icon: "shield" },
  { key: "script", n: "3", title: "Script", icon: "layers" },
  { key: "faq", n: "4", title: "FAQ bank", icon: "message" },
  { key: "persona", n: "5", title: "Persona & voice", icon: "agent" },
  { key: "ctas", n: "6", title: "Calls to action", icon: "arrow-right" },
];
const PHASE_TITLES = { reading: ["Preparing your demo…", "Reviewing the evidence and preparing your story, visuals and answers."], building: ["Building your demo…", "Writing the script, recording narration, rehearsing it against likely questions."] };
const STAGE_LABELS = { coach: "Sales playbook" };

// Keep the reviewed route editable without adding a seventh approval card.
export function storyOrderPanel(playbook, draft, onSave, onRequestUpload) {
  if (!playbook?.stops?.length) return null;
  const kinds = ["fundamental", "differentiator", "delighter", "hygiene", "ownership"];
  const panel = h("section", { "aria-label": "Story order", style: "margin-top:16px" });
  const list = h("ol", { class: "story-order", style: "list-style:none;padding:0;margin:10px 0" });
  let dragged = null;
  const save = h("button", { class: "btn sm primary", disabled: !draft.changed, onclick: async () => {
    save.disabled = true;
    try { await onSave({ stop_order: draft.stops.map((stop) => stop.id), kinds: Object.fromEntries(draft.stops.map((stop) => [stop.id, stop.kind])) }); }
    catch (error) { toast(error.message, true); save.disabled = false; }
  } }, "Save story order");
  function change() { draft.changed = true; save.disabled = false; draw(); }
  function move(from, to) {
    if (from < 0 || to < 0 || from === to || to >= draft.stops.length) return;
    const [stop] = draft.stops.splice(from, 1); draft.stops.splice(to, 0, stop); change();
  }
  function gapRow(gap, source = "") {
    return h("div", { class: "gap small", style: "margin:6px 0" }, gap,
      source ? h("div", { class: "muted" }, `Suggested source: ${source}`) : null,
      h("button", { class: "btn sm ghost", onclick: async (event) => {
        const button = event.currentTarget; button.disabled = true;
        try { await onRequestUpload({ type: "request_upload", upload_kind: /photo|picture|image/i.test(`${gap} ${source}`) ? "image" : "document", reason: source ? `${gap} — ${source}` : gap }); }
        catch (error) { toast(error.message, true); }
        finally { button.disabled = false; }
      } }, "Ask for this source"));
  }
  function draw() {
    list.replaceChildren(...draft.stops.map((stop, index) => {
      const badge = h("span", { class: "pill" }, stop.kind);
      const kind = h("select", { "aria-label": `Kind for ${stop.label}`, onchange: (event) => { stop.kind = event.target.value; change(); } },
        ...kinds.map((value) => h("option", { value, selected: value === stop.kind }, value)));
      const row = h("li", { draggable: "true", "data-stop-id": stop.id, style: "border-bottom:1px solid var(--line);padding:10px 0",
        ondragstart: (event) => { dragged = stop.id; event.dataTransfer?.setData("text/plain", stop.id); if (event.dataTransfer) event.dataTransfer.effectAllowed = "move"; },
        ondragover: (event) => { if (dragged) { event.preventDefault(); if (event.dataTransfer) event.dataTransfer.dropEffect = "move"; } },
        ondrop: (event) => { event.preventDefault(); const from = draft.stops.findIndex((item) => item.id === dragged); dragged = null; move(from, draft.stops.findIndex((item) => item.id === stop.id)); },
        ondragend: () => { dragged = null; } },
        h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, h("span", { class: "muted", "aria-hidden": "true" }, "↕"), h("b", {}, `${index + 1}. ${stop.label}`), badge,
          h("span", { class: "small muted" }, `${(stop.fact_ids || []).length} facts · ${(stop.picture_ids || []).length} pictures${stop.must_cover ? "" : " · awaiting evidence"}`),
          kind,
          h("button", { class: "btn sm ghost", "aria-label": `Move ${stop.label} up`, disabled: index === 0, onclick: () => move(index, index - 1) }, "↑"),
          h("button", { class: "btn sm ghost", "aria-label": `Move ${stop.label} down`, disabled: index === draft.stops.length - 1, onclick: () => move(index, index + 1) }, "↓")),
        stop.why_here ? h("p", { class: "small muted", style: "margin:5px 0" }, stop.why_here) : null,
        ...(stop.gaps || []).map((gap) => gapRow(gap)));
      return row;
    }));
  }
  draw();
  panel.append(h("h4", { style: "margin:0" }, "Story order"), h("p", { class: "small muted", style: "margin:5px 0" }, "Drag stops or use the arrows to arrange the story. Saving rebuilds the draft and asks you to review script and visuals again."), list,
    ...(playbook.gaps || []).map((gap) => gapRow(gap.what, gap.suggested_source)),
    ...(playbook.issues || []).map((issue) => h("p", { class: "small muted" }, issue)), save);
  return panel;
}

export function renderAlign(ctx) {
  const { demoId, area } = ctx;
  let state = ctx.state; let demo = state.demo; let cards = state.cards; let conversation = state.conversation || [];
  const seen = new Set(conversation.map((m) => m.t));
  let openCard = null;
  let storyDraft = null, storyVersion = "";
  const detached = new Set(), escapeHandlers = new Set();
  function mountDetached(node) { detached.add(node); document.body.appendChild(node); }
  function closeOnEscape(node) {
    const handler = (event) => { if (event.key === "Escape") { node.remove(); document.removeEventListener("keydown", handler); escapeHandlers.delete(handler); } };
    escapeHandlers.add(handler); document.addEventListener("keydown", handler);
  }

  const overlay = h("div", { class: "overlay hidden" });
  const logEl = h("div", { class: "progress-log" });
  const cardsCol = h("div", { class: "cards" });
  const thread = h("div", { class: "thread" });
  const dockTa = h("textarea", { "aria-label": "Message your demo agent", placeholder: "Ask for a change or add missing information…" });
  const fileIn = h("input", { type: "file", multiple: true, accept: "video/*,image/*,.pdf,.docx,.txt,.md,.csv" });
  const attachRow = h("div", { class: "attach" });
  const sendBtn = h("button", { class: "btn primary", onclick: send }, icon("send", { size: 16 }), "Send");
  const buildBar = h("div", { class: "build-bar hidden" }, h("span", { class: "build-ready" }, icon("check-circle", { size: 19 }), "All six cards approved."), h("button", { class: "btn primary", onclick: build }, "Build the demo", icon("arrow-right", { size: 16 })));
  let pending = [];

  area.replaceChildren(overlay, h("div", { class: "align" }, cardsCol,
    h("div", { class: "convo" }, h("div", { class: "align-agent-header" }, h("span", { class: "studio-agent-mark" }, icon("agent", { size: 24 })), h("div", {}, h("h2", {}, "Your demo agent"), h("p", {}, "Refine the details together"))), thread, buildBar,
      h("div", { class: "dock" }, attachRow,
        h("div", { class: "box" }, h("button", { class: "btn ghost", title: "Attach files", "aria-label": "Attach files", onclick: () => fileIn.click() }, icon("plus", { size: 19 })), dockTa, sendBtn, fileIn),
        h("div", { class: "hint" }, "Add a correction or attach missing material. New files are re-read and every affected card must be approved again.")))));

  fileIn.addEventListener("change", () => { pending.push(...fileIn.files); fileIn.value = ""; renderAttach(); });
  dockTa.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } });
  function renderAttach() { attachRow.replaceChildren(...pending.map((f, i) => h("span", {}, icon("file", { size: 13 }), f.name, " ", h("a", { href: "#", "aria-label": `Remove ${f.name}`, onclick: (e) => { e.preventDefault(); pending.splice(i, 1); renderAttach(); } }, icon("close", { size: 13 }))))); }

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
    try { if (demo.status === "error" && !cards) await api.post(`/api/demos/${demoId}/read`); else if (Object.values(demo.approvals).every(Boolean)) await api.post(`/api/demos/${demoId}/build${readinessQuery(demoId)}`); else await api.post(`/api/demos/${demoId}/read`); logEl.replaceChildren(); showOverlay(cards ? "building" : "reading"); }
    catch (e) { toast(e.message, true); }
  }
  function logLine(ev) { const d = h("div", {}, ev.stage ? h("span", { class: "stage" }, (STAGE_LABELS[ev.stage] || ev.stage) + " · ") : null, ev.message); logEl.append(d); logEl.scrollTop = logEl.scrollHeight; }
  function restoreProgress() {
    const running = Object.entries(demo.stages || {}).filter(([, value]) => value.status === "running");
    const rows = running.flatMap(([stage, value]) => (value.progress?.length ? value.progress : [{ message: value.message, t: value.updated_at }]).filter((row) => row.message).map((row) => ({ ...row, stage })));
    logEl.replaceChildren(); rows.sort((a, b) => (a.t || 0) - (b.t || 0)).slice(-20).forEach(logLine);
  }
  function syncOverlay() {
    if (demo.status === "reading" || demo.status === "building") { restoreProgress(); showOverlay(demo.status); }
    else if (demo.status === "error") { const failed = Object.values(demo.stages || {}).find((s) => s.status === "error"); showOverlay("reading", failed?.error || "The current stage did not finish."); }
    else hideOverlay();
  }

  // ---------- cards ----------
  function renderCards() {
    const approvals = demo.approvals || {};
    const current = CARD_DEFS.find((c) => !approvals[c.key])?.key;
    if (openCard === null) openCard = current || "visuals";
    const allDone = cards && CARD_DEFS.every((c) => approvals[c.key]);
    const noteEl = h("div", { class: "align-note" }, h("span", {}, "Review each card before building. ", h("b", {}, "Only approved material goes into your demo.")), cards && !allDone ? h("button", { class: "btn sm", onclick: approveAll }, "Approve all") : null);
    cardsCol.replaceChildren(h("header", { class: "studio-page-head align-page-head" }, h("div", { class: "eyebrow" }, "Demo workspace / Align"), h("div", { class: "align-title-row" }, h("h1", {}, "Make it ready for customers"), h("span", { class: "pill" + (allDone ? " ok" : "") }, `${CARD_DEFS.filter((c) => approvals[c.key]).length} of 6 approved`)), h("p", { class: "lede" }, "Review the knowledge, story and experience your guide will deliver.")), noteEl, ...CARD_DEFS.map((c) => {
      const el = h("div", { class: `acard${approvals[c.key] ? " approved" : ""}${current === c.key ? " current" : ""}${openCard === c.key ? " open" : ""}`, "data-card": c.key },
        h("div", { class: "head", onclick: (e) => { if (e.target.closest("button")) return; openCard = openCard === c.key ? "" : c.key; renderCards(); requestAnimationFrame(() => cardsCol.querySelector(`[data-card="${c.key}"]`)?.scrollIntoView({ block: "start" })); } }, h("span", { class: "n", title: `Step ${c.n}` }, approvals[c.key] ? icon("check", { size: 15 }) : c.n), h("h3", {}, icon(c.icon, { size: 18 }), c.title), h("span", { class: "st" }, approvals[c.key] ? "Approved" : current === c.key ? "Review now" : "Pending"),
          cards ? h("span", { class: "hact" }, h("button", { class: "btn sm ghost", onclick: () => openPreview(c.key) }, "Preview"), approvals[c.key] ? h("button", { class: "btn sm ghost", onclick: () => setApproval(c.key, false) }, "Un-approve") : h("button", { class: "btn sm primary", onclick: () => setApproval(c.key, true) }, "Approve")) : null),
        h("div", { class: "body" }, cards ? body(c.key) : h("p", { class: "muted small", style: "margin-top:10px" }, "Waiting for the sources to be read."),
          cards ? h("div", { class: "actions" },
            approvals[c.key] ? h("button", { class: "btn sm ghost", onclick: () => setApproval(c.key, false) }, "Un-approve") : h("button", { class: "btn sm primary", onclick: () => setApproval(c.key, true) }, "Approve"),
            h("button", { class: "btn sm ghost", onclick: () => { dockTa.value = ({ visuals: "About the visuals: ", facts: "About the facts: ", script: "About the slides: ", faq: "About the FAQ bank: ", persona: "About the persona and voice: ", ctas: "About the calls to action: " })[c.key] || ""; dockTa.focus(); } }, "Give feedback")) : null));
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
        h("td", { class: "id" }, x.id), h("td", {}, x.scope === "competitor" ? h("div", { class: "small muted" }, x.competitor_name || "Competitor") : null, h("b", {}, x.claim), h("br"), x.value, x.conditions ? h("span", { class: "muted" }, ` (${x.conditions})`) : null,
          Object.keys(x.applicability || {}).length ? h("div", { class: "small muted" }, Object.entries(x.applicability).map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ")) : null,
          x.knowledge?.review_required ? h("div", { class: "small" }, x.knowledge.review_required) : null),
        h("td", { class: "src" }, `${x.source?.ref || ""} ${x.source?.locator || ""}`, x.source?.quote ? h("div", { title: x.source.quote }, "“", x.source.quote.slice(0, 50), x.source.quote.length > 50 ? "…" : "", "”") : null),
        h("td", {}, h("button", { class: "btn sm ghost", title: "Edit this information", onclick: () => editFact(x) }, "Edit"), " ", h("button", { class: "btn sm ghost", title: x.approved === false ? "Restore this information" : "Keep this information out of the demo", onclick: () => x.approved === false && f.conflicts?.some((c) => c.status !== "superseded" && c.fact_ids?.includes(x.id) && c.fact_ids.length > 1) ? resolveEvidence(f.conflicts.find((c) => c.status !== "superseded" && c.fact_ids?.includes(x.id) && c.fact_ids.length > 1), x) : setFactApproval(x, x.approved === false) }, x.approved === false ? (f.conflicts?.some((c) => c.status !== "superseded" && c.fact_ids?.includes(x.id) && c.fact_ids.length > 1) ? "Select evidence" : "Restore") : "Reject"))));
      const open = f.unknowns.filter((u) => u.status === "open");
      return h("div", {},
        h("div", { style: "display:flex;justify-content:space-between;align-items:center;gap:8px;margin-top:10px" }, h("p", { class: "small muted", style: "margin:0" }, `${f.facts.length} facts from ${f.sources.length} source${f.sources.length === 1 ? "" : "s"}. The guide can only say what's in this table.`), h("button", { class: "btn sm", onclick: openProductEditor }, "Edit product summary")),
        h("div", { style: "max-height:360px;overflow:auto" }, h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "fact"), h("th", {}, "source"), h("th", {}, ""))), h("tbody", {}, ...rows))),
        evidenceReview(f),
        open.length ? h("div", {}, h("div", { style: "display:flex;justify-content:space-between;align-items:center;margin:14px 0 4px;gap:8px;flex-wrap:wrap" }, h("p", { class: "eyebrow", style: "margin:0" }, `${open.length} questions the sources don't answer`), h("a", { class: "btn sm", href: `/api/demos/${demoId}/faq-template`, download: `FAQ-${demoId}.md`, title: "A Markdown file with every open question grouped by category — fill the answers and upload it here" }, "Download FAQ template")),
          h("p", { class: "small muted", style: "margin:0 0 6px" }, "Grouped by what would answer them. Finance and insurance questions need their own documents — the guide declines these rather than guessing."),
          ...(() => { const cats = { pricing: "Pricing & offers", finance: "Finance / EMI", insurance: "Insurance", warranty_service: "Warranty & service", features: "Features & specs", availability: "Availability & delivery", comparison: "Comparisons", usage: "Usage & ownership", other: "Other" }; const groups = {}; for (const u of open) (groups[u.category || "other"] ||= []).push(u); return Object.keys(cats).filter((k) => groups[k]).map((k) => { const docs = [...new Set(groups[k].map((u) => u.suggested_document).filter(Boolean))]; return h("div", { class: "unk-group" }, h("p", { class: "eyebrow" }, `${cats[k]} · ${groups[k].length}`), docs.length ? h("p", { class: "doc" }, "upload: " + docs.join(" · ")) : null, h("div", { class: "unknowns" }, ...groups[k].map((u) => h("div", { class: "unk" }, h("span", { class: "id" }, u.id), h("span", {}, u.question, u.origin === "rehearsal" ? h("span", { class: "muted" }, " · from rehearsal") : u.origin === "runtime" ? h("span", { class: "muted" }, " · asked in a demo") : null))))); }); })()) : null,
        f.script_issues?.length ? h("div", { class: "gap" }, h("b", {}, "Script lines held back: "), f.script_issues.length, " — they stated something without a citation and were excluded from narration.") : null);
    }
    if (key === "script") {
      const pt = cards.script || {}; const tl = pt.timeline || {}; const dk = cards.deck || { slides: [] };
      const version = JSON.stringify(pt.playbook || {});
      if (!storyDraft || version !== storyVersion) { storyVersion = version; storyDraft = { stops: (pt.playbook?.stops || []).map((stop) => ({ ...stop })), changed: false }; }
      const mmss = (t) => t == null ? "" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
      const secs = {}; for (const sg of pt.segments || []) secs[sg.id] = sg.spoken ?? sg.duration;
      return h("div", {},
        h("div", { style: "display:flex;justify-content:flex-end;gap:8px;margin-top:10px;flex-wrap:wrap" }, h("button", { class: "btn sm", onclick: openPitchEditor }, "Edit pitch brief"), h("button", { class: "btn sm", onclick: openScriptEditor }, "Edit the words"), dk.slides.length ? h("button", { class: "btn sm primary", onclick: () => openSlideEditor(dk.slides.length > 1 ? 1 : 0) }, "Review slides") : null),
        h("div", { class: "kv" }, h("span", { class: "k" }, "Written"), h("span", { class: "small muted" }, pt.written_at ? new Date(pt.written_at * 1000).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }) + ` · demo v${pt.version}` + (dk.version ? ` · deck v${dk.version}` : "") : "not written yet"), h("span", { class: "k" }, "Decision"), h("span", {}, pt.decision_frame || "—"), h("span", { class: "k" }, "Takeaway"), h("span", {}, h("b", {}, pt.takeaway || "—")), h("span", { class: "k" }, "Length"), h("span", {}, tl.total_seconds ? `${mmss(tl.total_seconds)} in ${(tl.batches || []).length} batches of ≤ 20 s${tl.exact ? "" : " (estimated until voiced)"}` : "not written yet")),
        pt.runtime_overview ? h("div", { class: "gap" }, h("b", {}, "Short customer overview"), h("p", {}, pt.runtime_overview.text), h("div", { class: "small muted" }, `Evidence: ${(pt.runtime_overview.fact_ids || []).join(", ") || "No factual claims"}`), h("button", { class: "btn sm ghost", onclick: openScriptEditor }, "Edit overview")) : null,
        storyOrderPanel(pt.playbook, storyDraft, async (payload) => {
          await api.patch(`/api/demos/${demoId}/align/playbook`, payload); storyDraft = null;
          toast("Story order saved. Preparing the revised script and visuals."); await reload();
        }, async (action) => {
          const result = await api.post(`/api/demos/${demoId}/align/request-upload`, action);
          if (result.message) addMsg(result.message);
          dockTa.value = `Adding a source for: ${action.reason}`; dockTa.focus();
        }),
        h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, `Slides · ${dk.slides.length}${dk.method ? ` · callouts by ${dk.method}` : ""}`),
        h("div", { class: "deck-strip" }, ...dk.slides.map((s, i) => h("button", { class: "deck-thumb", title: s.title || s.kind, onclick: () => openSlideEditor(i) },
          s.image_url ? h("img", { src: s.image_url, alt: "" }) : h("div", { class: "noimg" }, "no picture"),
          h("div", { class: "cap" }, h("b", {}, s.title || s.kind), h("span", {}, `${s.kind.replaceAll("_", " ")}${secs[s.segment_id] ? ` · ${Math.round(secs[s.segment_id])} s` : ""}${s.callouts?.length ? ` · ${s.callouts.length} callout${s.callouts.length === 1 ? "" : "s"}` : ""}`))))),
        h("p", { class: "eyebrow", style: "margin:14px 0 4px" }, `Winning points · ${(pt.usps || []).length}`),
        h("ul", { class: "gaplist", style: "color:var(--ink)" }, ...(pt.usps || []).map((u) => h("li", {}, h("b", {}, u.name), " — ", h("span", { class: "muted" }, u.why_it_matters)))),
        h("p", { class: "small muted", style: "margin:10px 0 0" }, "Click a slide to review it: drag a callout, swap the picture, edit its text. Positions you set are kept when the deck is rebuilt. Preview shows every slide with its words and seconds.")
      );
    }
    if (key === "faq") {
      const f = cards.faq || { entries: [] };
      return h("div", {},
        h("p", { class: "small muted", style: "margin:10px 0 0" }, `${f.answered} of ${f.total} answered from your sources. Known questions answer instantly in the guide's voice; unknowns are admitted plainly and open the dealership follow-up form.`),
        h("div", { class: "unknowns" }, ...f.entries.slice(0, 8).map((e) => h("div", { class: "unk" }, h("span", { class: "pill " + (e.answered ? "ok" : "warn") }, e.answered ? "answered" : "declines"), h("span", {}, h("b", {}, e.question), h("div", { class: "small muted" }, (e.answer || "").slice(0, 140), (e.answer || "").length > 140 ? "…" : "")), h("button", { class: "btn sm ghost", onclick: () => editFaq(e) }, "Edit answer"), e.audio ? h("button", { class: "btn sm ghost", title: "Play answer", "aria-label": "Play answer", onclick: () => new Audio(e.audio).play() }, icon("play", { size: 16 })) : null))),
        f.entries.length > 8 ? h("p", { class: "small muted" }, `+ ${f.entries.length - 8} more — open Preview`) : null,
        h("p", { class: "small muted", style: "margin:8px 0 0" }, "Edit an answer using approved facts, then approve the FAQ card again. Upload an FAQ document (name it with “FAQ”) to add your own questions."));
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
        h("span", {}, h("label", { class: "primary" }, h("input", { type: "radio", name: "primary", checked: !!c.primary, onchange: () => { list.forEach((x, j) => (x.primary = j === i)); } }), " primary"), " ", h("button", { class: "btn sm ghost", title: "Remove action", "aria-label": "Remove action", onclick: () => { list.splice(i, 1); draw(); } }, icon("trash", { size: 16 }))))));
      draw();
      return h("div", {}, h("p", { class: "small muted", style: "margin:10px 0 0" }, "Buttons the customer sees during the demo. The guide names the primary one at the end."), wrap,
        h("div", { style: "display:flex;gap:8px;margin-top:10px" }, h("button", { class: "btn sm ghost", onclick: () => { list.push({ id: "cta" + (list.length + 1), label: "", kind: "link", url: "", primary: false, when: "always" }); draw(); } }, icon("plus", { size: 15 }), "Add"),
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
    mountDetached(bg); closeOnEscape(bg);
  }
  function previewBody(key) {
    const mmss = (t) => t == null ? "" : `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`;
    if (key === "visuals") {
      const v = cards.visuals; const sc = cards.script || {}; const usedIn = {};
      for (const sg of sc.segments || []) for (const l of sg.lines || []) if (l.visual) (usedIn[l.visual] = usedIn[l.visual] || []).push(`${sg.title}: “${l.text.slice(0, 70)}…”`);
      return h("div", { class: "pgrid" }, ...v.images.map((i) => h("div", { class: "pcard" }, h("img", { src: i.url, alt: i.description, onclick: () => lightbox(h("img", { src: i.url }), i.description) }), h("div", { class: "small" }, h("b", {}, i.id), " · ", i.angle, " · quality ", i.quality, i.enhanced?.how && i.enhanced.how !== "none" ? h("span", { class: "pill ok", style: "margin-left:6px" }, "cleaned") : null), h("div", { class: "small muted" }, i.description), i.audit?.visible_features?.length ? h("div", { class: "small" }, h("b", {}, "Gemini confirms: "), i.audit.visible_features.join(", ")) : i.parts?.length ? h("div", { class: "small" }, h("b", {}, "Tagged as: "), i.parts.join(", ")) : null, i.audit?.limitations?.length ? h("div", { class: "small muted" }, h("b", {}, "Does not prove: "), i.audit.limitations.join(", ")) : null, h("div", { class: "small muted" }, usedIn[i.id]?.length ? h("span", {}, h("b", {}, `used in ${usedIn[i.id].length} line(s): `), usedIn[i.id].slice(0, 3).join(" · ")) : "not used by any line yet"))),
        ...v.shots.map((sh) => h("div", { class: "pcard" }, h("video", { src: `${sh.url}#t=${(sh.start + 0.2).toFixed(1)}`, controls: true, preload: "metadata", muted: true }), h("div", { class: "small" }, h("b", {}, sh.id), ` · ${sh.start.toFixed(0)}–${sh.end.toFixed(0)} s · ${sh.part} · quality ${sh.quality}`), h("div", { class: "small muted" }, sh.description))));
    }
    if (key === "facts") {
      const f = cards.facts;
      return h("div", {}, h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "kind"), h("th", {}, "truth"), h("th", {}, "claim"), h("th", {}, "value"), h("th", {}, "conditions"), h("th", {}, "source"))), h("tbody", {}, ...f.facts.map((x) => h("tr", { class: x.approved === false ? "removed" : "" }, h("td", { class: "id" }, x.id), h("td", {}, x.kind), h("td", {}, x.truth || ""), h("td", {}, x.claim), h("td", {}, h("b", {}, x.value)), h("td", { class: "small muted" }, x.conditions || ""), h("td", { class: "src" }, `${x.source?.ref || ""} ${x.source?.locator || ""}`, x.source?.quote ? h("div", {}, "“", x.source.quote, "”") : null))))),
        h("h3", { style: "margin:16px 0 6px;font-size:14px" }, `${f.unknowns.filter((u) => u.status === "open").length} open questions the sources don't answer`),
        h("table", { class: "facts-table" }, h("tbody", {}, ...f.unknowns.filter((u) => u.status === "open").map((u) => h("tr", {}, h("td", { class: "id" }, u.id), h("td", {}, u.question), h("td", { class: "small muted" }, u.category, " · ", u.suggested_document))))));
    }
    if (key === "script") {
      const pt = cards.script || {}; const tl = pt.timeline || {}; const dk = cards.deck || { slides: [] };
      const secs = {}; for (const sg of pt.segments || []) secs[sg.id] = { start: sg.start, spoken: sg.spoken ?? sg.duration, checkin: sg.checkin };
      return h("div", {},
        h("div", { class: "kv" }, h("span", { class: "k" }, "Decision"), h("span", {}, pt.decision_frame || "—"), h("span", { class: "k" }, "Takeaway"), h("span", {}, h("b", {}, pt.takeaway || "—")), h("span", { class: "k" }, "Primary outcome"), h("span", {}, pt.primary_outcome || "—"), h("span", { class: "k" }, "Supporting"), h("span", {}, (pt.supporting_outcomes || []).join("; ") || "—"), h("span", { class: "k" }, "Not for"), h("span", {}, pt.do_not_recommend_if || "—"), h("span", { class: "k" }, "Advance"), h("span", {}, pt.advance || "—"), h("span", { class: "k" }, "Intake"), h("span", {}, pt.intake?.q1 || "—")),
        h("h3", { style: "margin:16px 0 6px;font-size:14px" }, `${dk.slides.length} slides · ${mmss(tl.total_seconds || 0)} total${tl.exact ? "" : " (estimated until voiced)"}`),
        ...dk.slides.map((s, i) => { const view = renderSlide(s, { fit: true }); view.el.classList.add("on"); const tm = secs[s.segment_id] || {}; return h("div", { class: "slide-review" },
          h("div", { class: "slide-review-head" }, h("span", { class: "id mono small", style: "color:var(--accent)" }, tm.start != null ? mmss(tm.start) : ""), h("b", {}, s.title || s.kind), h("span", { class: "muted small" }, s.kind.replaceAll("_", " "), tm.spoken ? ` · ${Math.round(tm.spoken)} s` : "", s.image_id ? ` · ${s.image_id}: ${s.image_reason || ""}` : ""), h("button", { class: "btn sm ghost", onclick: () => openSlideEditor(i) }, "Edit")),
          h("div", { class: "pl slide-review-stage" }, h("div", { class: "pl-stage" }, view.el)),
          s.lines?.length ? h("ol", { class: "slide-lines" }, ...s.lines.map((l) => h("li", {}, l.text, l.fact_ids?.length ? h("span", { class: "mono small muted" }, ` [${l.fact_ids.join(", ")}]`) : null))) : null,
          tm.checkin ? h("p", { class: "small muted", style: "margin:6px 0 0" }, h("i", {}, "pause: ", tm.checkin)) : null); }),
        pt.scorecard ? h("p", { class: "small muted", style: "margin:12px 0 0" }, `Scorecard ${pt.scorecard.total}/20 — weakest: ${(pt.scorecard.weakest || []).slice(0, 2).join("; ")}`) : null);
    }
    if (key === "faq") {
      const f = cards.faq || { entries: [] };
      return h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "question"), h("th", {}, "answer"), h("th", {}, "facts"), h("th", {}, ""))), h("tbody", {}, ...f.entries.map((e) => h("tr", { class: e.answered ? "" : "removed" }, h("td", { class: "id" }, e.id), h("td", {}, h("b", {}, e.question), h("div", { class: "small muted" }, e.origin)), h("td", {}, e.answer), h("td", { class: "mono small" }, (e.fact_ids || []).join(", ") || "—"), h("td", {}, h("button", { class: "btn sm ghost", onclick: (event) => { event.currentTarget.closest(".preview-bg")?.remove(); editFaq(e); } }, "Edit answer"), e.audio ? h("button", { class: "btn sm ghost", title: "Play answer", "aria-label": "Play answer", onclick: () => new Audio(e.audio).play() }, icon("play", { size: 16 })) : h("span", { class: "small muted" }, "voiced at build"))))));
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
    mountDetached(lb);
  }
  function editor(title, content, saveLabel = "Save changes") {
    const bg = h("div", { class: "preview-bg" }, h("div", { class: "preview align-editor" }, h("div", { class: "phead" }, h("h2", {}, title), h("button", { class: "btn ghost", onclick: () => bg.remove() }, "Close")), h("div", { class: "pbody" }, content.body), h("div", { class: "editor-actions" }, h("button", { class: "btn ghost", onclick: () => bg.remove() }, "Cancel"), h("button", { class: "btn primary", onclick: async (e) => { e.currentTarget.disabled = true; try { await content.save(); bg.remove(); await reload(); } catch (err) { toast(err.message, true); e.currentTarget.disabled = false; } } }, saveLabel))));
    mountDetached(bg);
  }
  function editFaq(entry) {
    const answer = h("textarea", { rows: "5" }, entry.answer || "");
    const facts = h("input", { value: (entry.fact_ids || []).join(", "), placeholder: "F001, F002" });
    const eligible = (cards.facts?.facts || []).filter((f) => f.approved !== false && (f.scope !== "competitor" || demo.settings?.competition === "on"));
    const body = h("div", { class: "edit-form" }, h("p", {}, h("b", {}, entry.question)), h("label", {}, "Reviewed answer", answer), h("label", {}, "Supporting fact ids", facts),
      h("details", {}, h("summary", {}, "Review approved evidence"), ...eligible.map((f) => h("p", { class: "small" }, h("b", {}, `${f.id} · ${f.claim}: `), f.value, f.conditions ? ` (${f.conditions})` : ""))),
      h("p", { class: "small muted" }, "Save a supported answer using the cited facts' exact scope. This clears its recording and requires FAQ approval again. Question wording stays the same."));
    editor(`Edit answer ${entry.id}`, { body, save: () => api.patch(`/api/demos/${demoId}/align/faq/${entry.id}`, { answer: answer.value, fact_ids: facts.value.split(/[,\s]+/).filter(Boolean) }) }, "Save reviewed answer");
    answer.focus();
  }
  function editFact(fact) {
    const claim = h("input", { value: fact.claim || "" }); const value = h("textarea", {}, fact.value || ""); const conditions = h("textarea", {}, fact.conditions || "");
    const truth = h("select", {}, ...["stated", "certified", "modeled", "observed", "contractual"].map((t) => h("option", { value: t, selected: t === (fact.truth || "stated") }, t)));
    const source = h("select", {}, ...(cards.facts.sources || []).filter((s) => fact.scope === "competitor" ? s.id === fact.competitor_source_id : s.role !== "competitor").map((s) => h("option", { value: s.id, selected: s.id === fact.source?.ref }, `${s.id} · ${s.name || s.url || s.kind}`)));
    const locator = h("input", { value: fact.source?.locator || "" }); const quote = h("textarea", {}, fact.source?.quote || "");
    const applicability = [["model", "Model"], ["model_year", "Model year"], ["generation", "Generation"], ["market", "Market"], ["variant", "Variant / trim"], ["powertrain", "Powertrain"], ["transmission", "Transmission"], ["test_basis", "Test basis"], ["price_basis", "Price basis"], ["effective_from", "Effective from"], ["effective_to", "Effective until"]].map(([key, label]) => ({ key, label, input: h("input", { value: fact.applicability?.[key] || "", type: key.startsWith("effective_") ? "date" : "text", maxlength: 500 }) }));
    const scopeFields = h("details", {}, h("summary", {}, "Review applicability"), h("p", { class: "small muted" }, "Enter only what the source establishes. A blank field means unknown; it does not mean every variant or market."), ...applicability.map(({ label, input }) => h("label", {}, label, input)));
    const body = h("div", { class: "edit-form" }, h("label", {}, "Information", claim), h("label", {}, "Value", value), h("label", {}, "Conditions / caveat", conditions), scopeFields, h("label", {}, "Evidence type", truth), h("label", {}, "Source", source), h("label", {}, "Page or section", locator), h("label", {}, "Exact supporting quote", quote), h("p", { class: "small muted" }, "Use the source's exact scope and wording. A changed assertion receives a new citation ID and makes every downstream card require approval again. Published evidence keeps its original ID."));
    editor(`Edit ${fact.id}`, { body, save: async () => {
      const scope = Object.fromEntries(applicability.filter(({ input }) => input.value.trim()).map(({ key, input }) => [key, input.value.trim()]));
      const result = await api.patch(`/api/demos/${demoId}/align/facts/${fact.id}`, { claim: claim.value, value: value.value, conditions: conditions.value, scope, truth: truth.value, source: { ref: source.value, locator: locator.value, quote: quote.value } });
      const newId = result.fact?.id || result.id;
      if (newId && newId !== fact.id) toast(`${fact.id} replaced by ${newId}. Review and approve the affected cards again.`);
      return result;
    } }, "Save & re-align");
  }
  function openProductEditor() {
    const product = cards.product || {};
    const fields = [["name", "Product name"], ["category", "Category"], ["summary", "Summary"], ["audience", "Audience"]].map(([key, label]) => ({ key, label, input: h("textarea", {}, product[key] || "") }));
    const body = h("div", { class: "edit-form" }, ...fields.map(({ label, input }) => h("label", {}, label, input)), h("p", { class: "small muted" }, "Use this when the extracted framing says more than the sources support."));
    editor("Edit product summary", { body, save: () => { const changed = {}; for (const { key, input } of fields) if (input.value.trim() !== String(product[key] || "").trim()) changed[key] = input.value.trim(); if (!Object.keys(changed).length) return Promise.resolve(); return api.patch(`/api/demos/${demoId}/align/product`, changed); } }, "Save product summary");
  }
  async function setFactApproval(fact, approved) {
    try { await api.post(`/api/demos/${demoId}/align/facts/${fact.id}/approval`, { approved }); toast(`${fact.id} ${approved ? "restored" : "rejected"}`); await reload(); }
    catch (e) { toast(e.message, true); }
  }
  function openScriptEditor() {
    const all = [];
    if (cards.script?.runtime_overview) all.push({ ...cards.script.runtime_overview, id: "runtime-overview", section: "Short customer overview" });
    for (const seg of cards.script?.segments || []) for (const line of seg.lines || []) all.push({ ...line, section: seg.title });
    for (const line of cards.script?.closing || []) all.push({ ...line, section: "Closing" });
    const fields = all.map((line) => ({ line, input: h("textarea", {}, line.text), facts: h("input", { value: (line.fact_ids || []).join(", "), placeholder: "F001, F002" }), visual: h("input", { value: line.visual || "", placeholder: "im01, or blank for a fact card" }) }));
    const intake = h("textarea", {}, cards.script?.intake?.q1 || "");
    const questions = (cards.script?.segments || []).filter((s) => s.checkin || ["proof", "features"].includes(s.role)).map((s) => ({ segment: s, input: h("textarea", {}, s.checkin || "") }));
    const body = h("div", { class: "script-editor" }, h("label", {}, "Opening question", intake), ...questions.map(({ segment, input }) => h("label", {}, `${segment.title} — question`, input)), ...fields.map(({ line, input, facts, visual }) => h("label", {}, h("span", {}, h("b", {}, line.section), h("small", { class: "mono muted" }, line.id)), input, h("small", { class: "muted" }, "Approved fact ids"), facts, h("small", { class: "muted" }, "Visual ref (blank keeps unsupported details on a fact card)"), visual)));
    editor("Edit what the guide says", { body, save: () => {
      const lines = fields.map(({ line, input, facts, visual }) => ({ id: line.id, text: input.value.trim(), fact_ids: facts.value.split(",").map((x) => x.trim()).filter(Boolean), visual_ref: visual.value.trim() })).filter((x, i) => x.text !== fields[i].line.text.trim() || x.fact_ids.join(",") !== (fields[i].line.fact_ids || []).join(",") || x.visual_ref !== (fields[i].line.visual || ""));
      const checkins = questions.filter(({ segment, input }) => input.value.trim() !== (segment.checkin || "").trim()).map(({ segment, input }) => ({ segment_id: segment.id, text: input.value.trim() }));
      const payload = { lines, checkins };
      if (intake.value.trim() !== (cards.script?.intake?.q1 || "").trim()) payload.intake_q1 = intake.value.trim();
      if (!lines.length && !checkins.length && payload.intake_q1 === undefined) return Promise.resolve();
      return api.patch(`/api/demos/${demoId}/align/script`, payload);
    } }, "Save & re-align visuals");
  }
  function openSlideEditor(idx) {
    let dk = cards.deck || { slides: [], images: [] }; if (!dk.slides.length) return;
    let i = Math.max(0, Math.min(idx, dk.slides.length - 1));
    const bg = h("div", { class: "preview-bg" }); const box = h("div", { class: "preview align-editor slide-editor-box" }); bg.append(box);
    function draw() {
      const orig = dk.slides[i]; const s = JSON.parse(JSON.stringify(orig)); const images = dk.images || []; const moved = {};
      const title = h("input", { value: s.title || "", maxlength: 80 });
      const imgSel = h("select", {}, ...images.map((x) => h("option", { value: x.id, selected: x.id === s.image_id }, `${x.id} · ${x.angle || ""} · ${(x.description || "").slice(0, 48)}`)));
      const partNames = () => (images.find((x) => x.id === imgSel.value)?.parts || []).map((p) => p.name);
      const partSel = (c) => h("select", {}, h("option", { value: "" }, "— side panel —"), ...partNames().map((n) => h("option", { value: n, selected: n === c.part }, n)));
      const rows = (s.callouts || []).map((c) => ({ c, text: h("input", { value: c.text, maxlength: 90 }), facts: h("input", { value: (c.fact_ids || []).join(", "), placeholder: "F001" }), part: partSel(c) }));
      const view = renderSlide(s, { editable: true, onMove: (id, pos) => { moved[id] = pos; } });
      imgSel.onchange = () => { const nx = images.find((x) => x.id === imgSel.value); view.setImage(nx?.url, nx?.parts || []); for (const r of rows) { const keep = r.part.value; r.part.replaceChildren(h("option", { value: "" }, "— side panel —"), ...partNames().map((n) => h("option", { value: n, selected: n === keep }, n))); } };
      const form = h("div", { class: "slide-editor-form" },
        h("label", {}, "Title (≤ 6 words)", title),
        images.length ? h("label", {}, "Picture", imgSel) : h("p", { class: "small muted" }, "No pictures in this demo."),
        h("p", { class: "eyebrow", style: "margin:4px 0 0" }, `Callouts · ${rows.length}`),
        ...rows.map((r, k) => h("div", { class: "callout-row" }, h("span", { class: "num" }, String(k + 1)), h("label", {}, "Text (≤ 8 words; a figure or claim needs a fact id)", r.text), h("label", {}, "Fact ids", r.facts), h("label", {}, "Points at", r.part), h("small", { class: "muted" }, r.c.placement === "overlay" ? `on the picture · part confidence ${r.c.confidence}` : (r.c.part ? `side panel · part confidence ${r.c.confidence} is below 0.6` : "side panel · no part named")))),
        rows.length ? null : h("p", { class: "small muted" }, "No callouts on this slide."),
        s.lines?.length ? h("div", {}, h("p", { class: "eyebrow", style: "margin:4px 0 0" }, "The guide says"), h("ol", { class: "slide-lines" }, ...s.lines.map((l) => h("li", {}, l.text)))) : null);
      const save = async (approveAfter) => {
        const out = { slide_id: orig.id, callouts: [] };
        if (title.value.trim() !== (orig.title || "")) out.title = title.value.trim();
        if (images.length && imgSel.value !== orig.image_id) out.image_id = imgSel.value;
        for (const r of rows) { const co = { id: r.c.id }; if (r.text.value.trim() !== r.c.text) co.text = r.text.value.trim(); const f = r.facts.value.split(",").map((x) => x.trim()).filter(Boolean); if (f.join(",") !== (r.c.fact_ids || []).join(",")) co.fact_ids = f; if (r.part.value !== (r.c.part || "")) co.part = r.part.value; if (moved[r.c.id]) co.label_pos = moved[r.c.id]; if (Object.keys(co).length > 1) out.callouts.push(co); }
        if (out.title !== undefined || out.image_id !== undefined || out.callouts.length) { await api.patch(`/api/demos/${demoId}/align/deck`, { slides: [out] }); await reload(); dk = cards.deck; toast("Slide saved"); }
        if (approveAfter) { await setApproval("script", true); bg.remove(); } else draw();
      };
      box.replaceChildren(
        h("div", { class: "phead" }, h("h2", {}, `Slide ${i + 1} of ${dk.slides.length}`, h("span", { class: "muted small", style: "margin-left:10px" }, orig.kind.replaceAll("_", " "))), h("div", { style: "display:flex;gap:6px" }, h("button", { class: "btn sm ghost", disabled: i === 0, onclick: () => { i--; draw(); } }, icon("arrow-left", { size: 15 }), "Prev"), h("button", { class: "btn sm ghost", disabled: i === dk.slides.length - 1, onclick: () => { i++; draw(); } }, "Next", icon("arrow-right", { size: 15 })), h("button", { class: "btn sm", onclick: () => bg.remove() }, "Close"))),
        h("div", { class: "pbody slide-editor" }, h("div", {}, view.el), form),
        h("div", { class: "editor-actions" }, h("span", { class: "small muted", style: "margin-right:auto" }, "Drag a callout to move it. Saving keeps your positions over any rebuild; an uncited figure or claim is refused."), h("button", { class: "btn", onclick: () => save(false).catch((e) => toast(e.message, true)) }, "Save"), h("button", { class: "btn primary", onclick: () => save(true).catch((e) => toast(e.message, true)) }, "Save & approve")));
      requestAnimationFrame(view.layout);
    }
    draw(); mountDetached(bg); closeOnEscape(bg);
  }
  function evidenceReview(f) {
    const coverage = f.coverage || {}; const seeds = coverage.seeds || []; const conflicts = f.conflicts || [];
    const blocked = seeds.flatMap((s) => s.blocked || []); const deferred = seeds.flatMap((s) => s.deferred || []);
    const fetched = seeds.flatMap((s) => s.fetched || []); const sourceName = (id) => f.sources.find((s) => s.id === id)?.name || id;
    const extractionWarnings = (coverage.extraction || []).filter((s) => s.error || s.warnings?.length);
    const changed = f.diff || {}; const sourceLine = (s) => h("li", { style: "overflow-wrap:anywhere;margin:4px 0" }, s.url || sourceName(s.source_id), s.reason ? ` — ${s.reason}` : "", ...(s.warnings || []).map((w) => h("div", { class: "small muted" }, w)));
    return h("section", { "aria-label": "Source coverage and conflicts", style: "margin-top:14px" },
      h("div", { class: "gap" }, h("b", {}, "Source coverage · "),
        !Object.keys(coverage).length ? "Not recorded for this earlier read." : coverage.complete ? "Eligible source frontier checked within the stated scope." : "Partial — review the gaps before approving.",
        h("div", { class: "small muted" }, `${fetched.length} web pages/documents read · ${blocked.length} blocked · ${deferred.length} deferred. Uploaded sources: ${(coverage.extraction || []).filter((s) => !fetched.some((p) => p.source_id === s.source_id)).length}.`),
        coverage.budget ? h("div", { class: "small muted" }, `Per model crawl limit: ${coverage.budget.html_pages} pages, ${coverage.budget.documents} documents, ${coverage.budget.document_pages} document pages, depth ${coverage.budget.depth}. A budget limit is not complete coverage.`) : null,
        coverage.rendering || coverage.ocr ? h("div", { class: "small muted" }, `JavaScript extraction: ${(coverage.rendering || "not recorded").replaceAll("_", " ")} · OCR: ${(coverage.ocr || "not recorded").replaceAll("_", " ")}. See source warnings for actual outcomes.`) : null),
      (seeds.length || extractionWarnings.length) ? h("details", { style: "margin:10px 0" }, h("summary", { style: "cursor:pointer;font-weight:600" }, "Inspect source coverage and remaining pages"),
        ...seeds.map((seed) => h("div", { style: "margin:12px 0" }, h("b", {}, sourceName(seed.source_id)),
          h("p", { class: "small muted", style: "margin:4px 0" }, `Model scope: ${(seed.model_tokens || []).join(", ") || "ambiguous"}. Topics found: ${(seed.topics_seen || []).join(", ") || "not established"}.`),
          ...(seed.warnings || []).map((w) => h("p", { class: "small" }, w)),
          ...[["Read", seed.fetched], ["Earlier revisions retained — verify freshness", seed.retained], ["Blocked", seed.blocked], ["Deferred — another bounded read is needed", seed.deferred], ["Skipped outside model scope (sample)", seed.skipped]].filter(([, rows]) => rows?.length).map(([label, rows]) =>
            h("details", { style: "margin:6px 0" }, h("summary", {}, `${label} (${rows.length})`), h("ul", { class: "small", style: "padding-left:20px" }, ...rows.map(sourceLine)))))),
        ...extractionWarnings.map((s) => h("div", { class: "gap small" }, h("b", {}, sourceName(s.source_id)), s.error ? h("p", {}, s.error) : null, ...(s.warnings || []).map((w) => h("p", {}, w))))) : null,
      Object.keys(changed).length ? h("p", { class: "small muted" }, `This read: ${(changed.added || []).length} new · ${(changed.changed || []).length} changed · ${(changed.removed || []).length} removed · ${(changed.unchanged || []).length} unchanged fact identities. Earlier demos retain their published evidence.`) : null,
      conflicts.length ? h("details", { open: conflicts.some((c) => c.status === "unresolved"), style: "margin:10px 0" }, h("summary", { style: "cursor:pointer;font-weight:600" }, `Evidence decisions and conflicts (${conflicts.length})`),
        ...conflicts.map((conflict) => h("div", { class: "gap" },
          h("b", {}, conflict.status === "superseded" ? `Earlier decision superseded by ${conflict.superseded_by || "a reviewed edit"}` : conflict.resolution === "uploaded_document" ? `Uploaded document takes precedence: ${conflict.preferred_fact_id}` : conflict.resolution === "human_edit" ? "Human correction preserved" : conflict.resolution === "human_review" ? `Reviewer selected ${conflict.preferred_fact_id}` : "Conflicting evidence needs review"),
          h("p", { class: "small", style: "margin:5px 0" }, conflict.reason || ""),
          h("div", { class: "small muted" }, Object.entries(conflict.scope || {}).map(([key, value]) => `${key.replaceAll("_", " ")}: ${value}`).join(" · ")),
          ...(conflict.fact_ids || []).map((id) => { const fact = f.facts.find((x) => x.id === id); return h("div", { class: "small", style: "margin:6px 0" }, h("b", {}, id), fact ? ` · ${fact.claim}: ${fact.value} · ${sourceName(fact.source?.ref)}` : " · earlier fact retained in the evidence history", fact ? h("button", { class: "btn sm ghost", onclick: () => editFact(fact) }, "Review fact") : null, fact && conflict.status !== "superseded" && conflict.fact_ids.length > 1 ? h("button", { class: "btn sm ghost", onclick: () => resolveEvidence(conflict, fact) }, `Use ${id}`) : null); }),
          conflict.preferred_fact_id && conflict.status !== "superseded" ? h("p", { class: "small muted", style: "margin:5px 0" }, "Other assertions in this decision are excluded from retrieval. Different or unknown applicability is never automatically merged.") : null))) : null);
  }

  async function resolveEvidence(conflict, fact) {
    try {
      await api.patch(`/api/demos/${demoId}/knowledge/conflicts/${encodeURIComponent(conflict.id)}`, { preferred_fact_id: fact.id, note: "Selected explicitly in the Facts review." });
      toast(`${fact.id} selected. Review and approve the affected cards again.`);
      await reload();
    } catch (error) { toast(error.message, true); }
  }

  function openPitchEditor() {
    const pt = cards.script || {};
    const keys = [["customer_persona", "Customer and decision"], ["decision_frame", "Decision frame"], ["takeaway", "Takeaway"], ["primary_outcome", "Primary outcome"], ["do_not_recommend_if", "Do not recommend if"], ["advance", "Next action"]];
    const fields = keys.map(([key, label]) => ({ key, label, input: h("textarea", {}, pt[key] || "") }));
    const body = h("div", { class: "edit-form" }, ...fields.map(({ label, input }) => h("label", {}, label, input)), h("p", { class: "small muted" }, "A direct correction makes every card require approval again."));
    editor("Edit pitch brief", { body, save: () => { const changed = {}; for (const { key, input } of fields) if (input.value.trim() !== String(pt[key] || "").trim()) changed[key] = input.value.trim(); if (!Object.keys(changed).length) return Promise.resolve(); return api.patch(`/api/demos/${demoId}/align/plan`, { fields: changed }); } }, "Save pitch brief");
  }
  async function setApproval(card, on) {
    try { await api.post(`/api/demos/${demoId}/${on ? "approve" : "unapprove"}/${card}`); await reload(); if (on) { openCard = CARD_DEFS.find((c) => !demo.approvals[c.key])?.key || ""; renderCards(); } }
    catch (e) { toast(e.message, true); }
  }

  // ---------- conversation ----------
  function addMsg(m) {
    if (m.system) return;
    if (m.t && seen.has(m.t)) return; if (m.t) seen.add(m.t);
    const el = h("div", { class: "msg " + (m.role === "user" ? "user" : m.system ? "system" : "agent") }, m.text,
      m.attachments?.length ? h("div", { class: "att" }, "attached: " + m.attachments.map((a) => a.name).join(", ")) : null,
      m.notes?.length ? h("div", { class: "notes" }, m.notes.join(" · ")) : null);
    thread.append(el); thread.scrollTop = thread.scrollHeight;
  }
  function highlights() {
    if (!cards) return ["The agent is still reading your sources."];
    const out = [];
    for (const gap of cards.visuals?.gaps || []) out.push(`No matching visual: ${gap.what}`);
    const auditMissing = cards.visuals?.audit?.missing_line_count || 0;
    if (auditMissing) out.push(`${auditMissing} spoken line${auditMissing === 1 ? "" : "s"} name features no image fully proves.`);
    const open = (cards.facts?.unknowns || []).filter((u) => u.status === "open");
    for (const u of open) out.push(`Missing ${String(u.category || "information").replaceAll("_", " ")}: ${u.question}`);
    for (const issue of cards.facts?.script_issues || []) out.push(`Script held back: ${issue}`);
    if (!out.length) out.push(`${cards.visuals?.images?.length || 0} images and ${cards.visuals?.shots?.length || 0} video shots are aligned.`);
    if (out.length < 5) out.push(`${cards.faq?.answered || 0} of ${cards.faq?.total || 0} FAQ answers are grounded in the sources.`);
    if (out.length < 5) out.push(`${cards.facts?.facts?.length || 0} sourced facts are available to the guide.`);
    return out.slice(0, 5);
  }
  function renderThread() {
    thread.replaceChildren(); seen.clear();
    thread.append(h("div", { class: "readiness" }, h("div", { class: "readiness-heading" }, icon("shield", { size: 17 }), "Review notes"), h("ul", {}, ...highlights().map((x) => h("li", {}, x)))));
  }

  async function send() {
    const text = dockTa.value.trim();
    if (!text && !pending.length) return;
    const fd = new FormData(); fd.append("message", text); fd.append("context", "align"); pending.forEach((f) => fd.append("files", f));
    dockTa.value = ""; const files = pending; pending = []; renderAttach();
    addMsg({ role: "user", text: text || "(files)", t: Date.now() / 1000, attachments: files.map((f) => ({ name: f.name })) });
    const thinking = h("div", { class: "msg agent thinking", role: "status" }, icon("sparkles", { size: 16 }), "Reviewing your request…"); thread.append(thinking); thread.scrollTop = thread.scrollHeight;
    sendBtn.disabled = true;
    try { const r = await api.form(`/api/demos/${demoId}/align`, fd); thinking.remove(); if (r.reply) addMsg({ role: "agent", text: r.reply, t: Date.now() / 1000 }); await reload(); }
    catch (e) { thinking.remove(); toast(e.message, true); }
    sendBtn.disabled = false;
  }

  async function build() { try { await api.post(`/api/demos/${demoId}/build${readinessQuery(demoId)}`); logEl.replaceChildren(); showOverlay("building"); } catch (e) { toast(e.message, true); } }

  const onVis = () => { if (document.visibilityState === "visible") reload().catch(() => {}); };
  document.addEventListener("visibilitychange", onVis);
  const poll = setInterval(() => { if (document.visibilityState === "visible") reload().catch(() => {}); }, 30000);
  window.addEventListener("hashchange", () => {
    document.removeEventListener("visibilitychange", onVis); clearInterval(poll);
    for (const node of detached) node.remove(); detached.clear();
    for (const handler of escapeHandlers) document.removeEventListener("keydown", handler); escapeHandlers.clear();
  }, { once: true });
  async function reload() {
    state = await api.get(`/api/demos/${demoId}`); demo = state.demo; cards = state.cards; conversation = state.conversation || [];
    renderCards(); renderThread(); ctx.setRailStatus(demo.status);
    syncOverlay();
    if (demo.status === "ready") buildBar.classList.add("hidden");
  }

  // ---------- events ----------
  ctx.subscribe((type, ev) => {
    if (type === "hello" && ev.snapshot) { demo = { ...demo, ...ev.snapshot }; syncOverlay(); reload().catch(() => {}); }
    else if (type === "progress") logLine(ev);
    else if (type === "status") { demo.status = ev.status; ctx.setRailStatus(ev.status); if (ev.status === "reading" || ev.status === "building") showOverlay(ev.status); }
    else if (type === "message") addMsg(ev.message);
    else if (type === "phase_done") { if (ev.phase === "build") { hideOverlay(); reload().then(() => ctx.navigate(`#/studio/${demoId}/rehearse`)); } else { hideOverlay(); reload(); } }
    else if (type === "phase_error") showOverlay(demo.status === "building" ? "building" : "reading", ev.error);
  });

  // initial
  renderCards(); renderThread();
  syncOverlay();
}
