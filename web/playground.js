// Playground — pick a demo, ask the guide directly, run evals, see the cost, refine.
import { api, h, toast, fmtTime } from "/web/api.js";

const rc = (el, ...nodes) => el.replaceChildren(...nodes.flat().filter(Boolean));

export async function renderPlayground({ main, navigate, demoId }) {
  const demos = await api.get("/api/demos");
  const usable = demos.filter((d) => ["ready", "align", "building"].includes(d.status));
  let id = demoId && usable.some((d) => d.id === demoId) ? demoId : usable[0]?.id;
  const sel = h("select", { onchange: () => navigate(`#/playground/${sel.value}`) }, ...usable.map((d) => h("option", { value: d.id, selected: d.id === id }, `${d.name} · ${d.id} · ${d.status}`)));
  const page = h("div", { class: "page" }, h("div", { class: "page-head" }, h("h1", {}, "Playground"), h("div", { style: "display:flex;gap:8px;align-items:center" }, h("span", { class: "eyebrow" }, "Demo"), sel)));
  rc(main, page);
  if (!id) { page.append(h("div", { class: "empty" }, "No demo has been read yet. Build one in Studio first.")); return; }
  const state = await api.get(`/api/demos/${id}`);
  const grid = h("div", { class: "pg" }); page.append(grid);

  // ---------- Ask ----------
  const askIn = h("input", { placeholder: "Ask as a customer, e.g. what's the on-road price in Pune?" });
  const askOut = h("div", { class: "pg-out" });
  async function ask() {
    const q = askIn.value.trim(); if (!q) return;
    rc(askOut, h("div", { class: "muted mono small" }, "thinking…"));
    try {
      const r = await api.post(`/api/demos/${id}/run/qa`, { question: q, history: [], profile: { name: "Playground" } });
      rc(askOut, 
        h("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:6px" }, h("span", { class: "pill " + (r.answered ? "ok" : "warn") }, r.answered ? "answered from sources" : "declined — not in sources"), r.offer_callback ? h("span", { class: "pill" }, "callback offered") : null, r.cta ? h("span", { class: "pill" }, "cta " + r.cta) : null),
        h("p", { style: "font-family:var(--body);font-size:15.5px;margin:0 0 8px" }, r.answer),
        r.clarifying_question ? h("p", { class: "small muted", style: "margin:0 0 8px" }, "then asks: “", r.clarifying_question, "”") : null,
        r.facts?.length ? h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, "id"), h("th", {}, "fact"), h("th", {}, "source"))), h("tbody", {}, ...r.facts.map((f) => h("tr", {}, h("td", { class: "id" }, f.id), h("td", {}, h("b", {}, f.claim), " — ", f.value, f.truth && f.truth !== "stated" ? h("span", { class: "muted" }, ` (${f.truth})`) : null), h("td", { class: "src" }, `${f.source?.ref || ""} ${f.source?.locator || ""}`))))) : null,
        r.escalate ? h("p", { class: "small", style: "color:var(--warn);margin:8px 0 0" }, "flagged for a human: ", r.escalate) : null);
    } catch (e) { rc(askOut, h("div", { class: "small", style: "color:var(--bad)" }, e.message)); }
  }
  askIn.addEventListener("keydown", (e) => { if (e.key === "Enter") ask(); });
  grid.append(h("div", { class: "box" }, h("h3", {}, "Ask the guide"), h("p", { class: "small muted", style: "margin:0 0 8px" }, "Text-only runtime Q&A — same grounding as the live demo: every figure must cite a fact or it declines."), h("div", { style: "display:flex;gap:8px" }, askIn, h("button", { class: "btn primary", onclick: ask }, "Ask")), askOut));

  // ---------- Evals ----------
  const reh = state.rehearsal; const seed = (reh?.questions || []).map((q) => q.question);
  const evIn = h("textarea", { style: "min-height:130px", placeholder: "One question per line. Leave empty and click “Generate 12 & run” to let the agent write them." }, seed.join("\n"));
  const evOut = h("div", { class: "pg-out" }); const evHist = h("div", { class: "small muted" });
  async function loadHist() { try { const hs = await api.get(`/api/demos/${id}/evals`); rc(evHist, ...hs.slice(0, 6).map((e) => h("div", { class: "sess" }, h("span", {}, e.label || e.id, h("span", { class: "muted" }, ` · ${e.n} q`)), h("span", { class: "mono" }, `${Math.round((e.coverage || 0) * 100)}%`, e.at ? " · " + fmtTime(e.at) : "")))); } catch (e) {} }
  async function runEvals(generate) {
    const qs = evIn.value.split("\n").map((s) => s.trim()).filter(Boolean);
    if (!generate && !qs.length) { toast("Add questions first, or generate them", true); return; }
    rc(evOut, h("div", { class: "muted mono small" }, `running ${generate ? "12 generated" : qs.length} questions — one paid call each…`));
    try {
      const r = await api.post(`/api/demos/${id}/evals`, generate ? { generate: true, n: 12, label: "generated" } : { questions: qs, label: "custom" });
      if (generate) evIn.value = r.results.map((x) => x.question).join("\n");
      rc(evOut, h("div", { class: "coverage" }, Math.round(r.coverage * 100), "%", h("small", {}, ` answered from the sources (${r.results.filter((x) => x.answered).length}/${r.results.length})`)),
        h("table", { class: "facts-table" }, h("thead", {}, h("tr", {}, h("th", {}, ""), h("th", {}, "question"), h("th", {}, "answer"), h("th", {}, "facts"))), h("tbody", {}, ...r.results.map((x) => h("tr", {}, h("td", {}, x.answered ? "✓" : "✗"), h("td", {}, x.question), h("td", { class: "small" }, (x.answer || "").slice(0, 140), x.escalate ? h("div", { style: "color:var(--warn)" }, "→ ", x.escalate.slice(0, 80)) : null), h("td", { class: "src" }, (x.fact_ids || []).join(", ")))))));
      loadHist();
    } catch (e) { rc(evOut, h("div", { class: "small", style: "color:var(--bad)" }, e.message)); }
  }
  grid.append(h("div", { class: "box" }, h("h3", {}, "Evals"), h("p", { class: "small muted", style: "margin:0 0 8px" }, "Every question runs through the real Q&A; ✗ means the guide declined because the sources don't say. Each question is a paid call."), evIn,
    h("div", { style: "display:flex;gap:8px;margin-top:8px;flex-wrap:wrap" }, h("button", { class: "btn primary", onclick: () => runEvals(false) }, "Run these"), h("button", { class: "btn", onclick: () => runEvals(true) }, "Generate 12 & run")), evOut, h("p", { class: "eyebrow", style: "margin:12px 0 4px" }, "history"), evHist));
  loadHist();

  // ---------- Cost ----------
  const costBox = h("div", { class: "box" }); grid.append(costBox);
  async function renderCost() {
    try {
      const u = await api.get(`/api/demos/${id}/usage`);
      const stages = Object.entries(u.by_stage).sort((a, b) => b[1].usd - a[1].usd);
      rc(costBox, h("h3", {}, "Cost so far"), h("div", { class: "coverage" }, "$", u.total_usd.toFixed(2), h("small", {}, ` ≈ ₹${u.total_inr.toFixed(0)} · ${u.rows} calls`)),
        u.sessions ? h("p", { class: "small muted", style: "margin:4px 0 0" }, `runtime ≈ $${(u.per_session_usd || 0).toFixed(3)} per session over ${u.sessions} session${u.sessions === 1 ? "" : "s"}`) : null,
        h("table", { class: "facts-table", style: "margin-top:8px" }, h("thead", {}, h("tr", {}, h("th", {}, "stage"), h("th", {}, "calls"), h("th", {}, "tokens in / out"), h("th", {}, "usd"))), h("tbody", {}, ...stages.map(([k, v]) => h("tr", {}, h("td", {}, k), h("td", { class: "src" }, String(v.calls)), h("td", { class: "src" }, `${v.in.toLocaleString()} / ${v.out.toLocaleString()}` + (v.chars ? ` · ${v.chars.toLocaleString()} chars` : "")), h("td", { class: "src" }, "$" + v.usd.toFixed(3)))))),
        h("details", { style: "margin-top:8px" }, h("summary", { class: "small muted" }, "price assumptions"), h("pre", { style: "font-size:11px;background:var(--panel-2);padding:8px;border-radius:6px;overflow:auto" }, JSON.stringify(u.prices, null, 1), `\nFX ₹${u.fx_inr}/$ · override any of these in .env`)),
        h("button", { class: "btn sm ghost", style: "margin-top:8px", onclick: renderCost }, "Refresh"));
    } catch (e) { rc(costBox, h("h3", {}, "Cost so far"), h("p", { class: "small muted" }, e.message)); }
  }
  renderCost();

  // ---------- Feedback ----------
  const fb = h("textarea", { placeholder: "e.g. “the intro is too long”, “F012 is wrong — the value is ₹1,08,993”, “add a segment on servicing”" });
  const fbOut = h("div", { class: "small muted", style: "margin-top:8px;line-height:1.5" });
  grid.append(h("div", { class: "box" }, h("h3", {}, "Refine"), h("p", { class: "small muted", style: "margin:0 0 8px" }, "Goes to the alignment agent with Rehearse context; a rewrite rebuilds the demo in the background — watch it in Studio › Rehearse."), fb,
    h("div", { style: "display:flex;gap:8px;margin-top:8px" }, h("button", { class: "btn primary", onclick: async () => { const m = fb.value.trim(); if (!m) return; fbOut.textContent = "thinking…"; try { const r = await api.post(`/api/demos/${id}/feedback`, { message: m, context: { source: "playground" } }); fbOut.textContent = r.reply + (r.notes?.length ? " · " + r.notes.join(" · ") : ""); fb.value = ""; } catch (e) { fbOut.textContent = ""; toast(e.message, true); } } }, "Incorporate feedback"), h("button", { class: "btn ghost", onclick: () => navigate(`#/studio/${id}/rehearse`) }, "Open in Studio →")), fbOut));
}
