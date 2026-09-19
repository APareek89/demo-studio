// The shipped readiness module with a DOM-shaped host and explicit fake API.
import fs from "node:fs";
const calls = [], rows = [];
const h = (tag, attrs = {}, ...children) => ({ tag, attrs, children: children.flat(), checked: !!attrs.checked,
  replaceChildren(...next) { this.children = next; }, set textContent(text) { this.children = [text]; } });
globalThis.__readinessFixture = {
  h, icon: () => h("svg"), toast: () => {}, fmtTime: () => "fixture time",
  api: {
    get: async (path) => { calls.push(["GET", path]); return { checks: {} }; },
    post: async (path) => { calls.push(["POST", path]); return { checked_at: 1, checks: { reasoning: { ready: true } } }; },
  },
};
let source = fs.readFileSync(new URL("../web/provider-readiness.js", import.meta.url), "utf8")
  .replace(/^import .*;\n/gm, "");
source = "const { api, h, toast, fmtTime, icon } = globalThis.__readinessFixture;\n" + source;
const { providerReadiness, readinessQuery } = await import("data:text/javascript;base64," + Buffer.from(source).toString("base64"));
const find = (node, tag) => node && typeof node === "object" && (node.tag === tag ? node : node.children.map((child) => find(child, tag)).find(Boolean));
const check = (name, ok) => { rows.push(!!ok); console.log((ok ? "PASS " : "FAIL ") + name); };
const panel = providerReadiness("first"); await Promise.resolve();
check("readiness UI loads status without a paid probe", calls.length === 1 && calls[0][0] === "GET");
check("readiness UI defaults to no override", readinessQuery("first") === "");
const checkbox = find(panel, "input"); checkbox.checked = true; checkbox.attrs.onchange();
check("explicit override is scoped to this demo", readinessQuery("first") === "?override_readiness=true" && readinessQuery("second") === "");
const button = find(panel, "button"); await button.attrs.onclick();
check("only explicit Check providers click posts the probe", calls.length === 2 && calls[1][0] === "POST" && calls[1][1].endsWith("/readiness/probe") && button.disabled === false);
checkbox.checked = false; checkbox.attrs.onchange();
check("operator can revoke override", readinessQuery("first") === "");
console.log(`Readiness UI contracts: ${rows.filter(Boolean).length}/${rows.length}`);
process.exitCode = rows.every(Boolean) ? 0 : 1;
