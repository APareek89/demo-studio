// Observability — model/speech calls and stamped customer answer latency. Presentation only;
// recorded metrics, filters and trace expansion retain their existing behavior.
import { api, h, fmtTime } from "/web/api.js";
import { icon } from "/web/icons.js";

const rc = (el, ...nodes) => el.replaceChildren(...nodes.flat().filter(Boolean));
const sectionHead = (name, title, description, trailing = null) => h("div", { class: "insight-section-head" },
  h("div", { class: "insight-section-title" }, h("span", { class: "insight-icon" }, icon(name)), h("div", {}, h("h2", {}, title), description ? h("p", {}, description) : null)), trailing);
const metric = (label, value, detail, note = "", extraClass = "") => h("div", { class: `insight-metric ${extraClass}` },
  h("div", { class: "insight-metric-label" }, label), h("div", { class: "insight-metric-value" }, value),
  h("div", { class: "insight-metric-detail" }, detail), note ? h("div", { class: "insight-metric-note" }, note) : null);

export async function renderObservability({ main, navigate, demoId }) {
  const demos = await api.get("/api/demos");
  const usable = demos.filter((d) => d.status !== "sources");
  let id = demoId && usable.some((d) => d.id === demoId) ? demoId : usable[0]?.id;
  const sel = h("select", { "aria-label": "Demo to observe", onchange: () => navigate(`#/observability/${sel.value}`) }, ...usable.map((d) => h("option", { value: d.id, selected: d.id === id }, `${d.name} · ${d.id} · ${d.status}`)));
  const stageFilter = h("select", { "aria-label": "Filter calls by stage", onchange: () => renderRows() }, h("option", { value: "" }, "All stages"));
  const page = h("div", { class: "page insight-page" }, h("div", { class: "page-head insight-page-head" },
    h("div", { class: "insight-page-title" }, h("span", { class: "insight-page-symbol" }, icon("chart", { size: 25 })), h("div", {}, h("div", { class: "eyebrow" }, "Performance & quality"), h("h1", {}, "Observability"), h("p", {}, "Understand every answer, model call and moment your customer waits."))),
    h("div", { class: "insight-page-tools" }, h("label", { class: "insight-demo-select" }, h("span", {}, "Demo"), sel), h("button", { class: "btn insight-refresh", onclick: () => load() }, "Refresh"))));
  rc(main, page);
  if (!id) {
    page.append(h("div", { class: "insight-empty-page" }, h("span", { class: "insight-empty-symbol" }, icon("chart", { size: 32 })), h("h2", {}, "Your demo insights will appear here"), h("p", {}, "Read a demo’s sources in Studio to begin tracking its stages, calls and answer times.")));
    return;
  }
  const wrap = h("div", { class: "obs insight-stack" }); page.append(wrap);
  const stagesBox = h("section", { class: "box insight-panel insight-stages" });
  const totalsBox = h("section", { class: "box insight-panel" });
  const latencyBox = h("section", { class: "box insight-panel insight-latency" });
  const rowsBox = h("section", { class: "box insight-panel insight-calls" });
  wrap.append(latencyBox, totalsBox, stagesBox, rowsBox);
  let data = null;

  async function load() {
    data = await api.get(`/api/demos/${id}/trace?limit=400`);
    const stages = Object.entries(data.stages || {});
    rc(stagesBox, sectionHead("layers", "Build stages", "Recorded duration and status for each stage of this demo."),
      h("div", { class: "insight-stage-grid" }, ...stages.map(([k, v]) => h("div", { class: "insight-stage" },
        h("div", { class: "insight-stage-top" }, h("span", { class: "insight-stage-name" }, k), h("span", { class: `insight-status-dot ${v.status === "done" || v.status === "complete" ? "is-done" : v.status === "error" ? "is-error" : v.status === "running" ? "is-running" : ""}`, "aria-hidden": "true" })),
        h("div", { class: "insight-stage-value" }, v.seconds != null ? `${v.seconds}s` : (v.status === "running" ? "…" : "—")), h("div", { class: "insight-stage-status" }, v.status + (v.error ? " · " + v.error.slice(0, 60) : ""))))));
    const u = data.usage || {}; const byModel = Object.entries(u.by_model || {});
    rc(totalsBox, sectionHead("chart", "Usage & cost", "Recorded calls and estimated usage across this demo."),
      h("div", { class: "insight-metric-grid insight-cost-grid" }, metric("Total cost", `$${(u.total_usd || 0).toFixed(3)}`, `≈ ₹${(u.total_inr || 0).toFixed(0)} · ${u.rows || 0} calls`, "", "is-primary"),
        ...byModel.map(([m, v]) => metric(m, `$${v.usd.toFixed(3)}`, `${v.calls} calls`, `${v.in.toLocaleString()} in / ${v.out.toLocaleString()} out` + (v.chars ? ` · ${v.chars.toLocaleString()} chars` : "")))));
    const lat = data.latency || { turns: 0, stages: {} }; const ms = (v) => v == null ? "—" : v >= 1000 ? `${(v / 1000).toFixed(1)}s` : `${v}ms`;
    const LABELS = { stt: ["Speech → text", "Voice ended → STT done"], qa: ["Answer", "STT done → QA done"], tts: ["First audio", "QA done → answer audio playing"], total: ["Customer waits", "Voice ended → answer audio playing"] };
    rc(latencyBox, sectionHead("clock", "Answer latency", `${lat.turns || 0} customer turn${lat.turns === 1 ? "" : "s"} · ${lat.sessions_with_turns || 0} session${lat.sessions_with_turns === 1 ? "" : "s"}` + (lat.by_source ? ` · ${lat.by_source.bank} from the FAQ bank, ${lat.by_source.model} from the model` : ""), h("span", { class: "insight-section-tag" }, "Customer experience")),
      lat.turns ? h("div", { class: "insight-metric-grid" }, ...Object.entries(lat.stages).map(([k, v]) => metric(LABELS[k]?.[0] || k, h("span", {}, h("small", {}, "p50 "), ms(v.p50)), `p95 ${ms(v.p95)} · ${v.n} turn${v.n === 1 ? "" : "s"}`, LABELS[k]?.[1] || "", k === "total" ? "is-primary" : "")))
        : h("div", { class: "insight-inline-empty" }, icon("clock", { size: 24 }), h("div", {}, h("strong", {}, "No customer questions yet"), h("p", {}, "Each session question records voice ended, STT done, QA done and first answer audio."))),
      h("p", { class: "insight-footnote" }, "Answer includes speech generation. First audio measures the remaining delay until answer playback begins, including a slide transition when needed."));
    const opts = [...new Set((data.rows || []).map((r) => r.stage))];
    const cur = stageFilter.value; rc(stageFilter, h("option", { value: "" }, "All stages"), ...opts.map((s) => h("option", { value: s, selected: s === cur }, s)));
    renderRows();
  }
  function renderRows() {
    const rows = (data?.rows || []).filter((r) => !stageFilter.value || r.stage === stageFilter.value).slice().reverse();
    const tbody = h("tbody", {});
    for (const [index, r] of rows.entries()) {
      const detailId = `trace-detail-${index}`;
      const tr = h("tr", { class: "row", tabindex: "0", role: "button", "aria-expanded": "false", "aria-controls": detailId, "aria-label": `View ${r.kind} call details at ${fmtTime(r.t)}` },
        h("td", {}, h("div", { class: "insight-trace-time" }, icon("chevron-right", { size: 15, className: "insight-trace-chevron" }), fmtTime(r.t))),
        h("td", {}, h("span", { class: "insight-stage-badge" }, r.stage)), h("td", {}, h("span", { class: "insight-call-name" }, r.kind), h("div", { class: "insight-model-name" }, r.model)),
        h("td", { class: "num" }, `${(r.latency_ms / 1000).toFixed(1)}s`), h("td", { class: "num" }, `${r.in.toLocaleString()} / ${r.out.toLocaleString()}` + (r.chars ? ` · ${r.chars}c` : "")),
        h("td", { class: "num" }, `$${(r.usd || 0).toFixed(4)}`), h("td", {}, h("span", { class: "pill " + (r.error ? "bad" : "ok") }, icon(r.error ? "alert-circle" : "check-circle", { size: 12 }), r.error ? "Error" : "OK")));
      const det = h("tr", { class: "detail hidden", id: detailId }, h("td", { colspan: 7 }, h("div", { class: "insight-trace-detail" },
        r.system ? [h("h3", {}, "System prompt"), h("pre", {}, r.system)] : null, h("h3", {}, "Input"), h("pre", {}, r.user || "—"), h("h3", {}, "Response"), h("pre", {}, r.response || "—"), r.error ? [h("h3", { class: "insight-error-label" }, "Error"), h("pre", {}, r.error)] : null)));
      const toggle = () => { const hidden = det.classList.toggle("hidden"); tr.setAttribute("aria-expanded", String(!hidden)); };
      tr.onclick = toggle;
      tr.onkeydown = (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); toggle(); } };
      tbody.append(tr, det);
    }
    rc(rowsBox, sectionHead("file", `Calls (${rows.length})`, "Select a call to inspect its prompt, input and raw response.", stageFilter),
      rows.length ? h("div", { class: "insight-table-scroll" }, h("table", { class: "trace insight-table" }, h("thead", {}, h("tr", {}, h("th", {}, "When"), h("th", {}, "Stage"), h("th", {}, "Call · model"), h("th", { class: "num" }, "Latency"), h("th", { class: "num" }, "Tokens in / out"), h("th", { class: "num" }, "Cost"), h("th", {}, "Status"))), tbody))
        : h("div", { class: "insight-inline-empty" }, icon("file", { size: 24 }), h("div", {}, h("strong", {}, "No recorded calls"), h("p", {}, stageFilter.value ? "No calls match this stage. Choose another stage to see its activity." : "Calls appear here after a build or a customer question. Earlier builds may predate tracing."))),
      h("p", { class: "insight-footnote" }, "Latency is wall-clock time per call. Cost uses the price assumptions in Playground."));
  }
  await load();
}
