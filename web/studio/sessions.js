// Studio › Sessions — who watched, what they asked, what the guide could not answer, and the follow-up summary.
// The same renderer serves the read-only share page (#/share/<demo>/<sid>/<key>): summary and questions, phones masked.
import { api, h, toast, fmtTime } from "/web/api.js";

const list = (items, empty) => items?.length ? h("ul", {}, ...items.map((x) => h("li", {}, typeof x === "string" ? x : x.text ?? JSON.stringify(x)))) : h("p", { class: "small muted" }, empty);

export function renderSummary(s, { full = false } = {}) {
  const sm = s.summary || {};
  const name = sm.customer_name || s.profile?.name || "Unnamed visitor";
  return h("div", { class: "session-summary" },
    h("h2", {}, name, h("span", { class: "small muted", style: "margin-left:10px;font-weight:400" }, s.saved_at ? fmtTime(s.saved_at) : "", s.minutes ? ` · ${s.minutes} min` : "", s.intent != null ? ` · intent ${s.intent}/100` : "")),
    sm.error ? h("p", { class: "small", style: "color:var(--warn)" }, "Summary unavailable: ", sm.error) : null,
    !s.summary ? h("p", { class: "small muted" }, s.ended ? "Summary is being written…" : "Session still open — the summary is written when the customer finishes or closes the tab.") : null,
    sm.context ? h("p", { class: "lead" }, sm.context) : null,
    h("div", { class: "grid2" },
      h("div", { class: "kvbox" }, h("h5", {}, "What they cared about"), list(sm.cared_about, "nothing specific stated")),
      h("div", { class: "kvbox" }, h("h5", {}, "Objections"), sm.objections?.length ? h("ul", {}, ...sm.objections.map((o) => h("li", {}, o.text, " — ", h("b", { style: `color:${o.resolved ? "var(--accent)" : "var(--warn)"}` }, o.resolved ? "resolved" : "open")))) : h("p", { class: "small muted" }, "none raised")),
      h("div", { class: "kvbox" }, h("h5", {}, `Questions asked (${(sm.questions_asked || s.questions || []).length})`), list(sm.questions_asked || s.questions, "none — listened through")),
      h("div", { class: "kvbox" }, h("h5", {}, "Could not answer from the sources"), list(sm.unanswered?.length ? sm.unanswered : s.escalations, "nothing outstanding")),
      h("div", { class: "kvbox" }, h("h5", {}, "Slides visited"), sm.slides_visited?.length ? h("ul", {}, ...sm.slides_visited.map((v) => h("li", {}, v.title || v.slide_id, " — ", String(v.seconds), " s"))) : h("p", { class: "small muted" }, "—")),
      h("div", { class: "kvbox" }, h("h5", {}, "Outcome"), h("p", {}, "CTA: ", h("b", {}, sm.cta_result || s.cta || "none")), (s.leads || []).length ? h("ul", {}, ...s.leads.map((l) => h("li", {}, "Call ", h("b", {}, l.phone), l.question ? ` about “${l.question}”` : ""))) : null)),
    sm.opening_line ? h("div", { class: "kvbox", style: "margin-top:12px" }, h("h5", {}, "Suggested opening line for the call"), h("p", { class: "quote" }, "“", sm.opening_line, "”")) : null,
    full && s.transcript?.length ? h("details", { style: "margin-top:14px" }, h("summary", {}, `Transcript — what the customer actually heard (${s.transcript.length} lines)`),
      h("div", { class: "transcript" }, ...s.transcript.map((t) => h("div", { class: "m " + t.role + (t.interrupted ? " interrupted" : "") }, t.text, t.interrupted ? h("span", { class: "cut" }, " — cut off") : null)))) : null);
}

export function renderSessions(ctx) {
  const { demoId, area } = ctx;
  const listBox = h("div", { class: "box" }, h("h3", {}, "Sessions"), h("p", { class: "small muted" }, "Loading…"));
  const detail = h("div", { class: "box" }, h("p", { class: "small muted" }, "Pick a session on the left."));
  area.replaceChildren(h("div", { class: "sessions-page" }, listBox, detail));
  async function load() {
    let r;
    try { r = await api.get(`/api/demos/${demoId}/sessions`); } catch (e) { listBox.replaceChildren(h("h3", {}, "Sessions"), h("p", { class: "small", style: "color:var(--warn)" }, "Could not load sessions.")); return; }
    const rows = r.sessions || [];
    listBox.replaceChildren(h("h3", {}, "Sessions ", h("span", { class: "small muted" }, `(${rows.length}) · storage: ${r.storage?.backend}${r.storage?.fallback_reason ? " — " + r.storage.fallback_reason : ""}`)),
      rows.length ? h("table", { class: "sessions" }, h("thead", {}, h("tr", {}, h("th", {}, "When"), h("th", {}, "Who"), h("th", {}, "Intent"), h("th", {}, "Q"), h("th", {}, "Outcome"), h("th", {}, "Summary"))),
        h("tbody", {}, ...rows.map((s) => h("tr", { class: "row", onclick: () => open(s.id) }, h("td", {}, s.saved_at ? fmtTime(s.saved_at) : "—"), h("td", {}, s.summary?.customer_name || s.profile?.name || "—"), h("td", {}, s.intent ?? "—"), h("td", {}, String(s.questions ?? 0)), h("td", {}, s.cta || "—", s.leads ? ` · ${s.leads} lead` : ""), h("td", {}, s.summary ? "✓" : s.ended ? "…" : "open")))))
        : h("p", { class: "small muted" }, "No sessions yet. Every play of this demo — from the share link or the rehearsal — lands here with a summary."));
  }
  async function open(sid) {
    let s;
    try { s = await api.get(`/api/demos/${demoId}/sessions/${sid}`); } catch (e) { toast("Could not load that session", true); return; }
    const link = `${location.origin}${location.pathname}#/share/${demoId}/${sid}/${s.share_key}`;
    detail.replaceChildren(renderSummary(s, { full: true }),
      h("div", { class: "share-row" }, h("input", { readonly: true, value: link, onclick: (e) => e.target.select() }), h("button", { class: "btn sm", onclick: async () => { try { await navigator.clipboard.writeText(link); toast("Share link copied"); } catch (e) { toast("Copy the link from the box", true); } } }, "Copy share link"), h("span", { class: "small muted" }, "Read-only · summary and questions only · phone numbers masked")));
  }
  load();
}

export async function renderShare({ main, demoId, sid, key }) {
  main.replaceChildren(h("div", { class: "share-page" }, h("p", { class: "small muted" }, "Loading…")));
  let s;
  try { s = await api.get(`/api/share/${demoId}/${sid}?k=${encodeURIComponent(key || "")}`); }
  catch (e) { main.replaceChildren(h("div", { class: "share-page" }, h("h2", {}, "This link is not valid"), h("p", { class: "small muted" }, "Ask the person who shared it for a fresh link."))); return; }
  main.replaceChildren(h("div", { class: "share-page" }, h("div", { class: "eyebrow" }, "Demo session summary · read-only"), renderSummary(s)));
}
