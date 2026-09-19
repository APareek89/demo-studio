import { api, h, toast, fmtTime } from "/web/api.js";
import { icon } from "/web/icons.js";

// An explicit, demo-scoped operator choice. It lasts only in this loaded tab.
const overrides = new Set();
export const readinessQuery = (demoId) => overrides.has(demoId) ? "?override_readiness=true" : "";

export function providerReadiness(demoId) {
  const details = h("div", { class: "small", role: "status", "aria-live": "polite" }, "Loading provider checks…");
  const override = h("input", { type: "checkbox", checked: overrides.has(demoId), onchange: () => {
    if (override.checked) overrides.add(demoId); else overrides.delete(demoId);
  } });
  const probe = h("button", { class: "btn sm", onclick: async () => {
    probe.disabled = true; details.textContent = "Checking reasoning, speech and listening…";
    try { render(await api.post(`/api/demos/${demoId}/readiness/probe`)); }
    catch (error) { details.textContent = "Provider check failed: " + error.message; toast(error.message, true); }
    finally { probe.disabled = false; }
  } }, icon("check-circle", { size: 15 }), "Check providers");
  function render(result) {
    const checks = result.checks || {};
    const labels = [["reasoning", "Reasoning"], ["streaming_speech", "Speech"], ["streaming_transcription", "Listening"]];
    details.replaceChildren(
      h("p", { style: "margin:0 0 8px" }, result.checked_at ? `${result.mock ? "Mock check" : "Last check"}: ${fmtTime(result.checked_at)}${result.stale ? " · expired" : ""}` : "No observed provider check yet."),
      ...labels.map(([key, label]) => {
        const check = checks[key];
        const state = !check ? "Not checked" : check.ready ? (result.stale ? "Expired" : result.mock ? "Mock only" : "Ready") : "Unavailable";
        return h("p", { style: "margin:4px 0;overflow-wrap:anywhere" }, h("strong", {}, label + ": "), state,
          check?.reason ? " · " + check.reason : "");
      }),
      h("p", { class: "muted", style: "margin:8px 0" }, "Checks expire after 24 hours. Listening checks the connection, not microphone quality. Availability can change.")
    );
  }
  api.get(`/api/demos/${demoId}/readiness`).then(render).catch((error) => { details.textContent = "Could not load provider checks: " + error.message; });
  return h("section", { class: "box", "aria-label": "Provider readiness" },
    h("h3", {}, icon("shield", { size: 18 }), "Provider readiness"), details,
    h("div", { style: "display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin:12px 0" }, probe,
      h("span", { class: "small muted" }, "A check uses a small amount of provider credit; no audio is played.")),
    h("label", { class: "small", style: "display:flex;align-items:flex-start;gap:8px;text-transform:none;letter-spacing:0;color:var(--ink)" }, override,
      "Continue Read / Build despite missing or failed checks for this demo in this tab.")
  );
}
