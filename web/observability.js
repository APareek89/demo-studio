// Observability — every model/speech call per demo: stage, model, latency, tokens, cost, prompt, response — and the
// customer's answer latency: p50 / p95 per stage (voice ended → STT done → QA done → first answer audio) over every stamped turn.
import { api, h, fmtTime } from "/web/api.js";

const rc = (el, ...nodes) => el.replaceChildren(...nodes.flat().filter(Boolean));

export async function renderObservability({ main, navigate, demoId }) {
  const demos = await api.get("/api/demos");
  const usable = demos.filter((d) => d.status !== "sources");
  let id = demoId && usable.some((d) => d.id === demoId) ? demoId : usable[0]?.id;
  const sel = h("select", { onchange: () => navigate(`#/observability/${sel.value}`) }, ...usable.map((d) => h("option", { value: d.id, selected: d.id === id }, `${d.name} · ${d.id} · ${d.status}`)));
  const stageFilter = h("select", { onchange: () => renderRows() }, h("option", { value: "" }, "all stages"));
  const page = h("div", { class: "page" }, h("div", { class: "page-head" }, h("h1", {}, "Observability"), h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, h("span", { class: "eyebrow" }, "Demo"), sel, stageFilter, h("button", { class: "btn sm", onclick: () => load() }, "Refresh"))));
  rc(main, page);
  if (!id) { page.append(h("div", { class: "empty" }, "Nothing to observe yet — read a demo's sources first.")); return; }
  const wrap = h("div", { class: "obs" }); page.append(wrap);
  const stagesBox = h("div", { class: "box" }); const totalsBox = h("div", { class: "box" }); const latencyBox = h("div", { class: "box" }); const rowsBox = h("div", { class: "box" });
  wrap.append(stagesBox, totalsBox, latencyBox, rowsBox);
  let data = null;

  async function load() {
    data = await api.get(`/api/demos/${id}/trace?limit=400`);
    const stages = Object.entries(data.stages || {});
    rc(stagesBox, h("h3", {}, "Stages"), h("div", { class: "stages" }, ...stages.map(([k, v]) => h("div", { class: "stg" }, h("div", { class: "n" }, k), h("div", { class: "v" }, v.seconds != null ? `${v.seconds}s` : (v.status === "running" ? "…" : "—")), h("div", { class: "s" }, v.status + (v.error ? " · " + v.error.slice(0, 60) : ""))))));
    const u = data.usage || {}; const byModel = Object.entries(u.by_model || {});
    rc(totalsBox, h("h3", {}, "Totals"), h("div", { class: "stages" }, h("div", { class: "stg" }, h("div", { class: "n" }, "cost"), h("div", { class: "v" }, `$${(u.total_usd || 0).toFixed(3)}`), h("div", { class: "s" }, `≈ ₹${(u.total_inr || 0).toFixed(0)} · ${u.rows || 0} calls`)),
      ...byModel.map(([m, v]) => h("div", { class: "stg" }, h("div", { class: "n" }, m), h("div", { class: "v" }, `$${v.usd.toFixed(3)}`), h("div", { class: "s" }, `${v.calls} calls · ${v.in.toLocaleString()} in / ${v.out.toLocaleString()} out` + (v.chars ? ` · ${v.chars.toLocaleString()} chars` : ""))))));
    const lat = data.latency || { turns: 0, stages: {} }; const ms = (v) => v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`;
    const LABELS = { stt: ["speech → text", "voice ended → STT done"], qa: ["answer", "STT done → QA done"], tts: ["first audio", "QA done → answer audio playing"], total: ["customer waits", "voice ended → answer audio playing"] };
    rc(latencyBox, h("h3", {}, "Answer latency ", h("span", { class: "small muted" }, `${lat.turns || 0} customer turn${lat.turns === 1 ? "" : "s"} · ${lat.sessions_with_turns || 0} session${lat.sessions_with_turns === 1 ? "" : "s"}` + (lat.by_source ? ` · ${lat.by_source.bank} from the FAQ bank, ${lat.by_source.model} from the model` : ""))),
      lat.turns ? h("div", { class: "stages" }, ...Object.entries(lat.stages).map(([k, v]) => h("div", { class: "stg" }, h("div", { class: "n" }, LABELS[k]?.[0] || k), h("div", { class: "v" }, "p50 ", ms(v.p50)), h("div", { class: "s" }, `p95 ${ms(v.p95)} · ${v.n} turn${v.n === 1 ? "" : "s"}`), h("div", { class: "s muted" }, LABELS[k]?.[1] || ""))))
        : h("p", { class: "small muted", style: "margin:0" }, "No customer turns yet — every question asked in a session stamps voice ended, STT done, QA done and first answer audio."));
    const seen = new Set(["".concat()]); const opts = [...new Set((data.rows || []).map((r) => r.stage))];
    const cur = stageFilter.value; rc(stageFilter, h("option", { value: "" }, "all stages"), ...opts.map((s) => h("option", { value: s, selected: s === cur }, s)));
    renderRows();
  }
  function renderRows() {
    const rows = (data?.rows || []).filter((r) => !stageFilter.value || r.stage === stageFilter.value).slice().reverse();
    const tbody = h("tbody", {});
    for (const r of rows) {
      const tr = h("tr", { class: "row" }, h("td", {}, fmtTime(r.t)), h("td", {}, r.stage), h("td", {}, r.kind, h("div", { class: "muted" }, r.model)), h("td", { class: "num" }, `${(r.latency_ms / 1000).toFixed(1)}s`), h("td", { class: "num" }, `${r.in.toLocaleString()} / ${r.out.toLocaleString()}` + (r.chars ? ` · ${r.chars}c` : "")), h("td", { class: "num" }, `$${(r.usd || 0).toFixed(4)}`), h("td", {}, r.error ? h("span", { class: "pill bad" }, "error") : h("span", { class: "pill ok" }, "ok")));
      const det = h("tr", { class: "detail hidden" }, h("td", { colspan: 7 }, r.system ? [h("h6", {}, "system prompt"), h("pre", {}, r.system)] : null, h("h6", {}, "input"), h("pre", {}, r.user || "—"), h("h6", {}, "response"), h("pre", {}, r.response || "—"), r.error ? [h("h6", {}, "error"), h("pre", {}, r.error)] : null));
      tr.onclick = () => det.classList.toggle("hidden");
      tbody.append(tr, det);
    }
    rc(rowsBox, h("h3", {}, `Calls (${rows.length})`), h("p", { class: "small muted", style: "margin:0 0 8px" }, "Click a row for the system prompt, the input and the raw response. Latency is wall-clock per call; cost uses the price table in Playground › Cost."),
      rows.length ? h("table", { class: "trace" }, h("thead", {}, h("tr", {}, h("th", {}, "when"), h("th", {}, "stage"), h("th", {}, "call · model"), h("th", {}, "latency"), h("th", {}, "tokens in / out"), h("th", {}, "cost"), h("th", {}, ""))), tbody) : h("p", { class: "muted small" }, "No calls recorded for this demo yet (tracing started after it was built — rebuild or ask it something)."));
  }
  await load();
}
