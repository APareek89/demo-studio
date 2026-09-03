// Thin API client + SSE subscription.
async function handle(r) {
  if (r.ok) return r.status === 204 ? null : r.json();
  let msg = r.statusText;
  try { const j = await r.json(); msg = j.detail || JSON.stringify(j); } catch (e) {}
  const err = new Error(msg); err.status = r.status; throw err;
}
export const api = {
  get: (p) => fetch(p).then(handle),
  post: (p, body) => fetch(p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}) }).then(handle),
  patch: (p, body) => fetch(p, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify(body || {}) }).then(handle),
  del: (p) => fetch(p, { method: "DELETE" }).then(handle),
  form: (p, fd) => fetch(p, { method: "POST", body: fd }).then(handle),
  subscribe(demoId, onEvent, since = 0) {
    const es = new EventSource(`/api/demos/${demoId}/events?since=${since}`);
    for (const t of ["progress", "stage", "status", "message", "phase_done", "phase_error", "hello"]) {
      es.addEventListener(t, (e) => { try { onEvent(t, JSON.parse(e.data)); } catch (err) {} });
    }
    es.onerror = () => {};
    return () => es.close();
  },
};
export function toast(text, bad = false) {
  const el = document.createElement("div"); el.className = "toast" + (bad ? " bad" : ""); el.textContent = text;
  document.getElementById("toasts").appendChild(el); setTimeout(() => el.remove(), bad ? 7000 : 3500);
}
export function h(tag, attrs = {}, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (k === "class") el.className = v; else if (k === "html") el.innerHTML = v; else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v !== null && v !== undefined && v !== false) el.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) { if (c === null || c === undefined || c === false) continue; el.append(c.nodeType ? c : document.createTextNode(String(c))); }
  return el;
}
export const fmtSize = (n) => n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : n > 1e3 ? Math.round(n / 1e3) + " KB" : n + " B";
export const fmtTime = (t) => new Date(t * 1000).toLocaleString("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
