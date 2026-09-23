// Exercise the actual Story order renderer with a tiny DOM; no browser/network dependency.
const fs = require("node:fs"), vm = require("node:vm"), assert = require("node:assert/strict");
const source = fs.readFileSync("web/studio/align.js", "utf8");
class Element {
  constructor(tag, attrs, children) { this.tag = tag; this.attrs = attrs; this.disabled = !!attrs.disabled; this.children = children.flat().filter((item) => item != null && item !== false); }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children.flat(); }
  get textContent() { return this.children.map((item) => item instanceof Element ? item.textContent : String(item)).join(""); }
}
const h = (tag, attrs = {}, ...children) => new Element(tag, attrs, children);
const errors = [];
const render = vm.runInNewContext(source.slice(source.indexOf("export function storyOrderPanel"), source.indexOf("export function renderAlign")).replace("export function", "function") + "; storyOrderPanel", { h, toast: (message) => errors.push(message) });
const find = (root, predicate) => root instanceof Element ? [ ...(predicate(root) ? [root] : []), ...root.children.flatMap((item) => find(item, predicate)) ] : [];
let passed = 0;
function check(label, condition) { assert.ok(condition, label); console.log(`PASS ${label}`); passed++; }
(async () => {
  const stops = [
    { id: "engine", label: "Engine choice", kind: "fundamental", fact_ids: ["F1", "F2"], picture_ids: [], must_cover: true, gaps: ["Engine bay photo"] },
    { id: "space", label: "Passenger space", kind: "fundamental", fact_ids: ["F3"], picture_ids: ["im1"], must_cover: true, gaps: [] },
    { id: "extras", label: "Cabin extras", kind: "delighter", fact_ids: [], picture_ids: [], must_cover: false, gaps: ["Cabin feature list"] },
  ];
  const draft = { stops, changed: false }, saves = [], requests = [];
  const panel = render({ stops, gaps: [{ what: "Warranty terms", suggested_source: "Official warranty document" }], issues: ["Picture gap retained"] }, draft, async (value) => saves.push(value), async (value) => requests.push(value));
  check("story panel names, kinds and evidence counts are visible", panel.textContent.includes("Story order") && panel.textContent.includes("fundamental") && panel.textContent.includes("2 facts · 0 pictures") && panel.textContent.includes("awaiting evidence"));
  const save = find(panel, (node) => node.tag === "button" && node.textContent === "Save story order")[0];
  check("unchanged story cannot be saved", save.disabled);
  let rows = find(panel, (node) => node.tag === "li");
  rows[1].attrs.ondragstart({ dataTransfer: { setData() {} } });
  rows[0].attrs.ondrop({ preventDefault() {} });
  check("drag reorder updates the saved route", draft.stops[0].id === "space" && !save.disabled);
  const up = find(panel, (node) => node.attrs["aria-label"] === "Move Engine choice up")[0];
  up.attrs.onclick();
  check("keyboard accessible arrows reorder stops", draft.stops[0].id === "engine");
  const kind = find(panel, (node) => node.attrs["aria-label"] === "Kind for Cabin extras")[0];
  kind.attrs.onchange({ target: { value: "ownership" } });
  await save.attrs.onclick();
  check("save sends full order and reviewed kinds", saves.length === 1 && saves[0].stop_order.join(",") === "engine,space,extras" && saves[0].kinds.extras === "ownership");
  const gaps = find(panel, (node) => node.tag === "button" && node.textContent === "Ask for this source");
  check("every stop and category evidence gap has a source button", gaps.length === 3);
  await gaps[0].attrs.onclick({ currentTarget: gaps[0] });
  await gaps[2].attrs.onclick({ currentTarget: gaps[2] });
  check("gap action requests the exact missing source without an approval", requests.length === 2 && requests.every((action) => action.type === "request_upload") && requests[0].upload_kind === "image" && requests[1].reason.includes("Warranty terms"));
  check("old demos without playbooks stay renderable", render({}, { stops: [] }, () => {}, () => {}) === null);
  check("renderer completes without errors", !errors.length);
  console.log(`${passed}/${passed} coach Align UI contracts passed`);
})().catch((error) => { console.error(error); process.exitCode = 1; });
