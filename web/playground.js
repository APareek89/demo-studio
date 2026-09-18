// Playground — ask the existing guide, run evals, inspect cost and refine. UI presentation only.
import { api, h, toast, fmtTime } from "/web/api.js";
import { icon } from "/web/icons.js";

const rc = (el, ...nodes) => el.replaceChildren(...nodes.flat().filter(Boolean));
const sectionHead = (name, title, description) => h("div", { class: "insight-section-head" },
  h("div", { class: "insight-section-title" }, h("span", { class: "insight-icon" }, icon(name)), h("div", {}, h("h2", {}, title), h("p", {}, description))));
const tableWrap = (table) => h("div", { class: "insight-table-scroll" }, table);

export async function renderPlayground({ main, navigate, demoId }) {
  const demos = await api.get("/api/demos");
  const usable = demos.filter((d) => ["ready", "align", "building"].includes(d.status));
  let id = demoId && usable.some((d) => d.id === demoId) ? demoId : usable[0]?.id;
  const sel = h("select", { "aria-label": "Demo to test", onchange: () => navigate(`#/playground/${sel.value}`) }, ...usable.map((d) => h("option", { value: d.id, selected: d.id === id }, `${d.name} · ${d.id} · ${d.status}`)));
  const page = h("div", { class: "page insight-page" }, h("div", { class: "page-head insight-page-head" },
    h("div", { class: "insight-page-title" }, h("span", { class: "insight-page-symbol" }, icon("flask", { size: 25 })), h("div", {}, h("div", { class: "eyebrow" }, "Test & improve"), h("h1", {}, "Playground"), h("p", {}, "Put your guide through its paces before the next customer conversation."))),
    h("div", { class: "insight-page-tools" }, h("label", { class: "insight-demo-select" }, h("span", {}, "Demo"), sel))));
  rc(main, page);
  if (!id) {
    page.append(h("div", { class: "insight-empty-page" }, h("span", { class: "insight-empty-symbol" }, icon("flask", { size: 32 })), h("h2", {}, "Make room for a great first impression"), h("p", {}, "Read a demo’s sources in Studio, then come here to test answers, evaluate coverage and refine the pitch.")));
    return;
  }
  const state = await api.get(`/api/demos/${id}`);
  const grid = h("div", { class: "pg insight-playground" }); page.append(grid);

  // ---------- Ask ----------
  const askIn = h("input", { "aria-label": "Customer question", placeholder: "Ask a question a customer might ask…" });
  const askOut = h("div", { class: "pg-out", "aria-live": "polite" }, h("div", { class: "insight-ask-empty" }, icon("agent", { size: 28 }), h("div", {}, h("strong", {}, "See how your guide responds"), h("p", {}, "Try a product question, a comparison or something outside the sources."))));
  async function ask() {
    const q = askIn.value.trim(); if (!q) return;
    rc(askOut, h("div", { class: "insight-working", role: "status" }, h("span", { class: "insight-status-dot is-running", "aria-hidden": "true" }), "Preparing an answer…"));
    try {
      const r = await api.post(`/api/demos/${id}/run/qa`, { question: q, history: [], profile: { name: "Playground" } });
      rc(askOut,
        h("div", { class: "insight-answer-badges" }, h("span", { class: "pill " + (r.answered ? "ok" : "warn") }, icon(r.answered ? "check-circle" : "alert-circle", { size: 12 }), r.answered ? "Answered from sources" : "Declined — not in sources"), r.offer_callback ? h("span", { class: "pill" }, "Callback offered") : null, r.cta ? h("span", { class: "pill" }, "CTA " + r.cta) : null),
        h("p", { class: "insight-answer-text" }, r.answer),
        r.clarifying_question ? h("p", { class: "insight-clarifier" }, "Then asks: “", r.clarifying_question, "”") : null,
        r.facts?.length ? tableWrap(h("table", { class: "facts-table insight-table" }, h("thead", {}, h("tr", {}, h("th", {}, "ID"), h("th", {}, "Fact"), h("th", {}, "Source"))), h("tbody", {}, ...r.facts.map((f) => h("tr", {}, h("td", { class: "id" }, f.id), h("td", {}, h("b", {}, f.claim), " — ", f.value, f.truth && f.truth !== "stated" ? h("span", { class: "muted" }, ` (${f.truth})`) : null), h("td", { class: "src" }, `${f.source?.ref || ""} ${f.source?.locator || ""}`)))))) : null,
        r.escalate ? h("p", { class: "insight-escalation" }, icon("alert-circle", { size: 16 }), "Flagged for a human: ", r.escalate) : null);
    } catch (e) { rc(askOut, h("div", { class: "insight-error", role: "alert" }, icon("alert-circle", { size: 18 }), e.message)); }
  }
  askIn.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
  grid.append(h("section", { class: "box insight-panel insight-ask" }, sectionHead("agent", "Ask the guide", "Text-only runtime Q&A, grounded in the same sources as the live demo."),
    h("div", { class: "insight-question-row" }, askIn, h("button", { class: "btn primary", onclick: ask }, "Ask", icon("arrow-right", { size: 16 }))), askOut));

  // ---------- Evals ----------
  const reh = state.rehearsal; const seed = (reh?.questions || []).map((q) => q.question);
  const evIn = h("textarea", { class: "insight-eval-input", "aria-label": "Evaluation questions, one per line", placeholder: "One question per line. Or generate a set of 12 questions below." }, seed.join("\n"));
  const evOut = h("div", { class: "pg-out", "aria-live": "polite" }); const evHist = h("div", { class: "insight-eval-history" });
  async function loadHist() {
    try {
      const hs = await api.get(`/api/demos/${id}/evals`);
      rc(evHist, ...(hs.length ? hs.slice(0, 6).map((e) => h("div", { class: "insight-history-row" }, h("div", {}, h("strong", {}, e.label || e.id), h("span", {}, ` · ${e.n} questions`)), h("div", { class: "insight-history-meta" }, h("strong", {}, `${Math.round((e.coverage || 0) * 100)}%`), e.at ? h("span", {}, fmtTime(e.at)) : null))) : [h("p", { class: "insight-empty-note" }, "Your recent evaluation runs will appear here.")]));
    } catch (e) {}
  }
  let evBusy = false; const evBtns = [];
  async function runEvals(generate) {
    if (evBusy) return; evBusy = true; evBtns.forEach((b) => { b.disabled = true; }); try {
      const qs = evIn.value.split("\n").map((s) => s.trim()).filter(Boolean);
      if (!generate && !qs.length) { toast("Add questions first, or generate them", true); return; }
      rc(evOut, h("div", { class: "insight-working", role: "status" }, h("span", { class: "insight-status-dot is-running", "aria-hidden": "true" }), `Running ${generate ? "12 generated" : qs.length} questions — one paid call each…`));
      try {
        const r = await api.post(`/api/demos/${id}/evals`, generate ? { generate: true, n: 12, label: "generated" } : { questions: qs, label: "custom" });
        if (generate) evIn.value = r.results.map((x) => x.question).join("\n");
        rc(evOut, h("div", { class: "insight-eval-result" }, h("div", { class: "coverage" }, Math.round(r.coverage * 100), "%"), h("p", {}, `Answered from the sources (${r.results.filter((x) => x.answered).length}/${r.results.length})`)),
          tableWrap(h("table", { class: "facts-table insight-table" }, h("thead", {}, h("tr", {}, h("th", {}, "Status"), h("th", {}, "Question"), h("th", {}, "Answer"), h("th", {}, "Facts"))), h("tbody", {}, ...r.results.map((x) => h("tr", {},
            h("td", {}, h("span", { class: "insight-result-state " + (x.answered ? "is-answered" : "is-declined"), title: x.answered ? "Answered" : "Declined", "aria-label": x.answered ? "Answered" : "Declined" }, icon(x.answered ? "check-circle" : "alert-circle", { size: 17 }))),
            h("td", {}, x.question), h("td", { class: "small" }, (x.answer || "").slice(0, 140), x.escalate ? h("div", { class: "insight-result-escalation" }, x.escalate.slice(0, 80)) : null), h("td", { class: "src" }, (x.fact_ids || []).join(", "))))))));
        loadHist();
      } catch (e) { rc(evOut, h("div", { class: "insight-error", role: "alert" }, icon("alert-circle", { size: 18 }), e.message)); }
    } finally { evBusy = false; evBtns.forEach((b) => { b.disabled = false; }); }
  }
  grid.append(h("section", { class: "box insight-panel insight-evals" }, sectionHead("flask", "Evaluations", "Test a set of customer questions and review source coverage."),
    h("p", { class: "insight-call-notice" }, icon("alert-circle", { size: 15 }), "Each question runs the real Q&A and uses a paid call. A decline means the sources do not support an answer."),
    h("label", { class: "insight-field-label" }, "Questions", evIn), h("div", { class: "insight-actions" },
      evBtns[0] = h("button", { class: "btn primary", onclick: () => runEvals(false) }, icon("play", { size: 15 }), "Run these"), evBtns[1] = h("button", { class: "btn", onclick: () => runEvals(true) }, "Generate 12 & run")), evOut,
    h("div", { class: "insight-history-title" }, icon("clock", { size: 15 }), "Recent runs"), evHist));
  loadHist();

  // ---------- Cost ----------
  const costBox = h("section", { class: "box insight-panel insight-playground-cost" }); grid.append(costBox);
  async function renderCost() {
    try {
      const u = await api.get(`/api/demos/${id}/usage`);
      const stages = Object.entries(u.by_stage).sort((a, b) => b[1].usd - a[1].usd);
      rc(costBox, sectionHead("chart", "Cost so far", "Estimated usage for this demo."),
        h("div", { class: "insight-cost-total" }, h("div", { class: "coverage" }, "$", u.total_usd.toFixed(2)), h("p", {}, `≈ ₹${u.total_inr.toFixed(0)} · ${u.rows} calls`)),
        u.sessions ? h("p", { class: "insight-cost-session" }, `Runtime ≈ $${(u.per_session_usd || 0).toFixed(3)} per session over ${u.sessions} session${u.sessions === 1 ? "" : "s"}`) : null,
        tableWrap(h("table", { class: "facts-table insight-table" }, h("thead", {}, h("tr", {}, h("th", {}, "Stage"), h("th", { class: "num" }, "Calls"), h("th", { class: "num" }, "Tokens in / out"), h("th", { class: "num" }, "USD"))), h("tbody", {}, ...stages.map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", { class: "num" }, String(v.calls)), h("td", { class: "num" }, `${v.in.toLocaleString()} / ${v.out.toLocaleString()}` + (v.chars ? ` · ${v.chars.toLocaleString()} chars` : "")), h("td", { class: "num" }, "$" + v.usd.toFixed(3))))))),
        h("details", { class: "insight-price-assumptions" }, h("summary", {}, "Price assumptions"), h("pre", {}, JSON.stringify(u.prices, null, 1), `\nFX ₹${u.fx_inr}/$ · override any of these in .env`)),
        h("button", { class: "btn sm insight-cost-refresh", onclick: renderCost }, "Refresh cost"));
    } catch (e) { rc(costBox, sectionHead("chart", "Cost so far", "Estimated usage for this demo."), h("p", { class: "insight-error", role: "alert" }, e.message)); }
  }
  renderCost();

  // ---------- Feedback ----------
  const fb = h("textarea", { "aria-label": "Feedback for the alignment agent", placeholder: "What would you improve? For example: “Shorten the opening and add a segment on servicing.”" });
  const fbOut = h("div", { class: "insight-feedback-result", "aria-live": "polite" });
  grid.append(h("section", { class: "box insight-panel insight-refine" }, sectionHead("settings", "Refine the demo", "Send focused feedback to your alignment agent."),
    h("p", { class: "insight-refine-note" }, "A rewrite rebuilds the demo in the background. Follow its progress in Studio › Rehearse."),
    h("label", { class: "insight-field-label" }, "Your feedback", fb), h("div", { class: "insight-actions" },
      h("button", { class: "btn primary", onclick: async () => { const m = fb.value.trim(); if (!m) return; fbOut.textContent = "Preparing a response…"; try { const r = await api.post(`/api/demos/${id}/feedback`, { message: m, context: { source: "playground" } }); fbOut.textContent = r.reply + (r.notes?.length ? " · " + r.notes.join(" · ") : ""); fb.value = ""; } catch (e) { fbOut.textContent = ""; toast(e.message, true); } } }, "Incorporate feedback"),
      h("button", { class: "btn ghost", onclick: () => navigate(`#/studio/${id}/rehearse`) }, "Open in Studio", icon("arrow-right", { size: 16 }))), fbOut));
}
