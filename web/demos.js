import { api, h, toast, fmtTime } from "/web/api.js";

const STATUS_LABEL = { sources: "needs sources", reading: "reading sources…", align: "in alignment", building: "building…", ready: "ready", error: "error" };
const STATUS_CLASS = { ready: "ok", align: "warn", building: "run", reading: "run", error: "bad" };

export async function renderDemos({ main, navigate }) {
  const demos = await api.get("/api/demos");
  const page = h("div", { class: "page" },
    h("div", { class: "page-head" }, h("h1", {}, "Demos"), h("button", { class: "btn primary", onclick: () => newDemoModal(navigate) }, "+ New demo")),
    demos.length ? h("div", { class: "grid" }, ...demos.map((d) => card(d, navigate, () => renderDemos({ main, navigate })))) :
      h("div", { class: "empty" }, "No demos yet. Create one, drop in a product video or a few images plus the catalogue, and the agent takes it from there."),
  );
  main.replaceChildren(page);
}

function card(d, navigate, refresh) {
  const open = () => navigate(`#/studio/${d.id}/${d.status === "sources" ? "sources" : d.status === "ready" ? "rehearse" : "align"}`);
  return h("div", { class: "card" },
    h("div", { style: "display:flex;justify-content:space-between;gap:10px;align-items:flex-start" }, h("h3", {}, d.name), h("span", { class: "pill " + (STATUS_CLASS[d.status] || "") }, STATUS_LABEL[d.status] || d.status)),
    h("div", { class: "meta" }, d.location === "cloud" ? h("span", { class: "pill run", style: "margin-right:6px" }, "cloud only") : d.location === "local+cloud" ? h("span", { class: "pill ok", style: "margin-right:6px" }, "synced") : null, `${d.id} · v${d.version || 0}`, h("br"), `${d.sources} source${d.sources === 1 ? "" : "s"} · ${d.sessions} session${d.sessions === 1 ? "" : "s"} · updated ${fmtTime(d.updated_at)}`),
    h("div", { class: "row" },
      d.status === "ready" ? h("button", { class: "btn sm primary", onclick: () => { document.documentElement.requestFullscreen?.().catch(() => {}); navigate(`#/play/${d.id}`); } }, "▶ View") : null,
      h("button", { class: "btn sm" + (d.status === "ready" ? " ghost" : " primary"), onclick: open }, d.status === "ready" ? "Edit" : "Open"),
      h("button", { class: "btn sm ghost", onclick: async () => { const n = await api.post(`/api/demos/${d.id}/duplicate`); toast("Duplicated as " + n.id); refresh(); } }, "Duplicate"),
      h("button", { class: "btn sm ghost danger", onclick: async () => { if (!confirm(`Delete “${d.name}” and all its files?`)) return; await api.del(`/api/demos/${d.id}`); refresh(); } }, "Delete"),
    ),
  );
}

function newDemoModal(navigate) {
  const name = h("input", { placeholder: "e.g. TVS iQube, Acme Analytics, Dyson V15" });
  const url = h("input", { placeholder: "https://… product page (optional, becomes a source)" });
  const bg = h("div", { class: "modal-bg", onclick: (e) => { if (e.target === bg) bg.remove(); } },
    h("div", { class: "modal" },
      h("h2", {}, "New demo"),
      h("p", { class: "muted", style: "margin:0" }, "Name the product. You'll add video, images and documents next."),
      h("div", { class: "field" }, h("label", {}, "Product"), name),
      h("div", { class: "field" }, h("label", {}, "Product URL"), url),
      h("div", { class: "actions" }, h("button", { class: "btn ghost", onclick: () => bg.remove() }, "Cancel"),
        h("button", { class: "btn primary", onclick: async () => { if (!name.value.trim()) { name.focus(); return; } try { const d = await api.post("/api/demos", { name: name.value.trim(), url: url.value.trim() }); bg.remove(); navigate(`#/studio/${d.id}/visual`); } catch (e) { toast(e.message, true); } } }, "Create")),
    ));
  document.body.appendChild(bg); setTimeout(() => name.focus(), 30);
  name.addEventListener("keydown", (e) => { if (e.key === "Enter") bg.querySelector(".btn.primary").click(); });
}
