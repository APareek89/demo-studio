// Studio › Sessions — who watched, what they asked, what the guide could not answer, and the follow-up summary.
// The same renderer serves the read-only share page (#/share/<demo>/<sid>/<key>): summary and questions, phones masked.
import { api, h, toast, fmtTime } from "/web/api.js";
import { icon } from "/web/icons.js";

const list = (items, empty) => items?.length ? h("ul", {}, ...items.map((x) => h("li", {}, typeof x === "string" ? x : x.text ?? JSON.stringify(x)))) : h("p", { class: "small muted" }, empty);

export function renderSummary(s, { full = false } = {}) {
  const sm = s.summary || {};
  const name = sm.customer_name || s.profile?.name || "Unnamed visitor";
  return h("div", { class: "session-summary" },
    h("div", { class: "session-summary-head" }, h("span", { class: "session-person-icon" }, icon("users", { size: 23 })), h("div", {}, h("h2", {}, name), h("div", { class: "session-meta" }, s.saved_at ? h("span", {}, icon("clock", { size: 13 }), fmtTime(s.saved_at)) : null, s.minutes ? h("span", {}, `${s.minutes} min`) : null, s.intent != null ? h("span", {}, `Intent ${s.intent}/100`) : null))),
    sm.error ? h("p", { class: "small", style: "color:var(--warn)" }, "Summary unavailable: ", sm.error) : null,
    !s.summary ? h("p", { class: "small muted" }, s.ended ? "Summary is being written…" : "Session still open — the summary is written when the customer finishes or closes the tab.") : null,
    sm.context ? h("p", { class: "lead" }, sm.context) : null,
    h("div", { class: "grid2" },
      h("div", { class: "kvbox" }, h("h5", {}, "What they cared about"), list(sm.cared_about, "nothing specific stated")),
      h("div", { class: "kvbox" }, h("h5", {}, "Objections"), sm.objections?.length ? h("ul", {}, ...sm.objections.map((o) => h("li", {}, o.text, " — ", h("b", { style: `color:${o.resolved ? "var(--accent)" : "var(--warn)"}` }, o.resolved ? "resolved" : "open")))) : h("p", { class: "small muted" }, "none raised")),
      h("div", { class: "kvbox" }, h("h5", {}, `Questions asked (${(sm.questions_asked || s.questions || []).length})`), list(sm.questions_asked || s.questions, "none — listened through")),
      h("div", { class: "kvbox" }, h("h5", {}, "Could not answer from the sources"), list(sm.unanswered?.length ? sm.unanswered : s.escalations, "nothing outstanding")),
      h("div", { class: "kvbox" }, h("h5", {}, "Slides visited"), sm.slides_visited?.length ? h("ul", {}, ...sm.slides_visited.map((v) => h("li", {}, v.title || v.slide_id, " — ", String(v.seconds), " s"))) : h("p", { class: "small muted" }, "—")),
      h("div", { class: "kvbox" }, h("h5", {}, "Outcome"), h("p", {}, "Action: ", h("b", {}, sm.cta_result || s.cta || "None selected")), (s.leads || []).length ? h("ul", {}, ...s.leads.map((l) => h("li", {}, "Call ", h("b", {}, l.phone), l.question ? ` about “${l.question}”` : ""))) : null)),
    sm.opening_line ? h("div", { class: "kvbox", style: "margin-top:12px" }, h("h5", {}, "Suggested opening line for the call"), h("p", { class: "quote" }, "“", sm.opening_line, "”")) : null,
    full && s.transcript?.length ? h("details", { style: "margin-top:14px" }, h("summary", {}, `Transcript — what the customer actually heard (${s.transcript.length} lines)`),
      h("div", { class: "transcript" }, ...s.transcript.map((t) => h("div", { class: "m " + t.role + (t.interrupted ? " interrupted" : "") }, t.text, t.interrupted ? h("span", { class: "cut" }, " — cut off") : null)))) : null);
}

export function renderSessions(ctx) {
  const { demoId, area } = ctx;
  const listBox = h("div", { class: "box session-list-box" }, h("h3", {}, "Session history"), h("p", { class: "small muted", role: "status" }, "Loading sessions…"));
  const detail = h("div", { class: "box session-detail-box" }, h("div", { class: "studio-empty session-detail-empty" }, icon("message", { size: 30 }), h("h2", {}, "Every conversation tells a story"), h("p", {}, "Choose a session to review what mattered, the questions asked and the next steps.")));
  area.replaceChildren(h("div", { class: "sessions-workspace" }, h("header", { class: "studio-page-head" }, h("div", { class: "eyebrow" }, "Demo workspace / Sessions"), h("h1", {}, "Turn conversations into next steps"), h("p", { class: "lede" }, "Review customer interests, unanswered questions and follow-up summaries in one place.")), h("div", { class: "sessions-page" }, listBox, detail)));
  async function load() {
    let r;
    try { r = await api.get(`/api/demos/${demoId}/sessions`); } catch (e) { listBox.replaceChildren(h("div", { class: "studio-empty" }, icon("alert-circle", { size: 26 }), h("h3", {}, "Sessions are unavailable"), h("p", {}, "Could not load sessions. Refresh the page to try again."))); return; }
    const rows = r.sessions || [];
    listBox.replaceChildren(h("div", { class: "session-list-heading" }, h("h3", {}, icon("users", { size: 18 }), "Session history"), h("span", { class: "pill" }, String(rows.length))),
      rows.length ? h("div", { class: "session-table-scroll" }, h("table", { class: "sessions" }, h("thead", {}, h("tr", {}, h("th", {}, "When"), h("th", {}, "Who"), h("th", {}, "Intent"), h("th", { title: "Questions" }, "Questions"), h("th", {}, "Outcome"), h("th", {}, "Summary"))),
        h("tbody", {}, ...rows.map((s) => h("tr", { class: "row", tabindex: "0", "data-session": s.id, "aria-label": `Open session for ${s.summary?.customer_name || s.profile?.name || "unnamed visitor"}${s.saved_at ? ", " + fmtTime(s.saved_at) : ""}`, onclick: () => open(s.id), onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(s.id); } } }, h("td", {}, s.saved_at ? fmtTime(s.saved_at) : "—"), h("td", {}, s.summary?.customer_name || s.profile?.name || "Unnamed visitor"), h("td", {}, s.intent ?? "—"), h("td", {}, String(s.questions ?? 0)), h("td", {}, s.cta || "—", s.leads ? ` · ${s.leads} lead` : ""), h("td", {}, h("span", { class: "session-summary-status" + (s.summary ? " ready" : ""), title: s.summary ? "Summary available" : s.ended ? "Summary pending" : "Session open" }, icon(s.summary ? "check-circle" : "clock", { size: 16 }), s.summary ? "Ready" : s.ended ? "Pending" : "Open")))))))
        : h("div", { class: "studio-empty session-list-empty" }, icon("users", { size: 28 }), h("h3", {}, "No sessions yet"), h("p", {}, "Play your demo to start a conversation. Its transcript and summary will appear here.")),
      h("div", { class: "session-storage small muted" }, `Storage: ${r.storage?.backend || "Unavailable"}${r.storage?.fallback_reason ? " — " + r.storage.fallback_reason : ""}`));
  }
  async function open(sid) {
    let s;
    try { s = await api.get(`/api/demos/${demoId}/sessions/${sid}`); } catch (e) { toast("Could not load that session", true); return; }
    const link = `${location.origin}${location.pathname}#/share/${demoId}/${sid}/${s.share_key}`;
    listBox.querySelectorAll("[data-session]").forEach((row) => row.classList.toggle("selected", row.dataset.session === sid));
    detail.replaceChildren(renderSummary(s, { full: true }),
      h("div", { class: "share-row" }, h("input", { readonly: true, "aria-label": "Read-only session share link", value: link, onclick: (e) => e.target.select() }), h("button", { class: "btn sm", onclick: async () => { try { await navigator.clipboard.writeText(link); toast("Share link copied"); } catch (e) { toast("Copy the link from the box", true); } } }, icon("copy", { size: 15 }), "Copy share link"), h("span", { class: "small muted share-privacy" }, icon("shield", { size: 14 }), "Read-only · summary and questions only · phone numbers masked")));
  }
  load();
}

export async function renderShare({ main, demoId, sid, key }) {
  main.replaceChildren(h("div", { class: "share-page" }, h("div", { class: "studio-empty", role: "status" }, icon("clock", { size: 28 }), h("h2", {}, "Loading session summary…"))));
  let s;
  try { s = await api.get(`/api/share/${demoId}/${sid}?k=${encodeURIComponent(key || "")}`); }
  catch (e) { main.replaceChildren(h("div", { class: "share-page" }, h("div", { class: "studio-empty" }, icon("shield", { size: 30 }), h("h2", {}, "This link is not valid"), h("p", {}, "Ask the person who shared it for a fresh link.")))); return; }
  main.replaceChildren(h("div", { class: "share-page" }, h("header", { class: "share-page-header" }, h("span", { class: "studio-agent-mark" }, icon("agent", { size: 24 })), h("div", {}, h("div", { class: "eyebrow" }, "Demo session summary"), h("p", {}, "A shared view of the conversation")), h("span", { class: "pill" }, icon("shield", { size: 12 }), "Read-only")), renderSummary(s)));
}
