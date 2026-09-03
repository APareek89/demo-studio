import { api, h, toast, fmtSize } from "/web/api.js";

const ZONES = [
  { role: "product", title: "Product video & images", desc: "MP4/MOV video, JPG/PNG/WEBP images. The demo seeks into the video and uses the images as visuals.", accept: "video/*,image/*", multiple: true },
  { role: "catalogue", title: "Catalogue, spec sheet, price list", desc: "PDF, DOCX, TXT, MD. Every fact the guide will ever state comes from here — with a citation.", accept: ".pdf,.docx,.txt,.md,.csv", multiple: true },
  { role: "brand", title: "Brand guidelines", desc: "PDF/DOCX, or paste a few lines about tone and what never to say. Optional — the agent infers a restrained default.", accept: ".pdf,.docx,.txt,.md", multiple: true, text: true },
];

export function renderSources(ctx) {
  const { demoId, area } = ctx;
  let demo = ctx.state.demo;
  const list = h("div", { class: "src-list" });
  const uploading = h("span", { class: "uploading" });
  const nameIn = h("input", { value: demo.product?.name || demo.name || "" });
  const urlIn = h("input", { value: demo.product?.url || "", placeholder: "https://… product page" });
  const readBtn = h("button", { class: "btn primary", onclick: startRead }, "Read sources →");

  async function refreshList() {
    list.replaceChildren(...demo.sources.map((s) => h("div", { class: "src-item" },
      h("span", { class: "kind" }, s.kind), h("span", { class: "name", title: s.name }, s.name),
      h("span", { class: "pill" }, s.role), h("span", { class: "size" }, s.size ? fmtSize(s.size) : "url"),
      h("button", { class: "btn sm ghost", onclick: async () => { const r = await api.del(`/api/demos/${demoId}/sources/${s.id}`); demo.sources = r.sources; refreshList(); } }, "✕"))));
    readBtn.disabled = !demo.sources.length;
  }

  async function upload(role, files, extra = {}) {
    const fd = new FormData();
    for (const f of files) fd.append("files", f);
    fd.append("role", role);
    for (const [k, v] of Object.entries(extra)) fd.append(k, v);
    uploading.textContent = `uploading ${files.length ? files.map((f) => f.name).join(", ") : extra.url || "text"}…`;
    try { const r = await api.form(`/api/demos/${demoId}/sources`, fd); demo.sources = r.sources; refreshList(); toast(`Added ${r.added.length} source${r.added.length === 1 ? "" : "s"}`); }
    catch (e) { toast(e.message, true); }
    uploading.textContent = "";
  }

  function zone(z) {
    const input = h("input", { type: "file", accept: z.accept, multiple: z.multiple });
    input.addEventListener("change", () => { if (input.files.length) upload(z.role, [...input.files]); input.value = ""; });
    const el = h("div", { class: "zone" + (z.text ? " wide" : "") },
      h("h3", {}, z.title), h("p", {}, z.desc),
      h("div", { class: "pick" }, h("button", { class: "btn sm", onclick: () => input.click() }, "Choose files"), h("span", { class: "muted small" }, "or drop them here"), input),
    );
    if (z.text) {
      const ta = h("textarea", { placeholder: "e.g. Warm and direct. Never say “cheapest”. Always call it a “scooter”, not a “bike”.", style: "width:100%;margin-top:10px" });
      el.append(ta, h("div", { style: "margin-top:8px" }, h("button", { class: "btn sm", onclick: () => { if (ta.value.trim()) { upload(z.role, [], { text: ta.value.trim(), text_name: "brand-guidelines" }); ta.value = ""; } } }, "Add as brand guideline")));
    }
    el.addEventListener("dragover", (e) => { e.preventDefault(); el.classList.add("over"); });
    el.addEventListener("dragleave", () => el.classList.remove("over"));
    el.addEventListener("drop", (e) => { e.preventDefault(); el.classList.remove("over"); const fs = [...e.dataTransfer.files]; if (fs.length) upload(z.role, fs); });
    return el;
  }

  async function saveMeta() {
    await api.patch(`/api/demos/${demoId}`, { name: nameIn.value.trim() || demo.name, product: { name: nameIn.value.trim(), url: urlIn.value.trim() } });
  }

  async function startRead() {
    await saveMeta();
    const u = urlIn.value.trim();
    if (u && !demo.sources.some((s) => s.kind === "url" && s.url === u)) await upload("product", [], { url: u });
    try { await api.post(`/api/demos/${demoId}/read`); ctx.navigate(`#/studio/${demoId}/align`); }
    catch (e) { toast(e.message, true); }
  }

  area.replaceChildren(h("div", { class: "sources" },
    h("h1", {}, "Sources"),
    h("p", { class: "lede" }, "Give the agent what a good salesperson would have: footage or photos of the product, the catalogue with the numbers, and how the brand likes to speak. It reads everything and shows you what it found before anything is built."),
    h("div", { class: "form-row" }, h("div", {}, h("label", {}, "Product name"), nameIn), h("div", {}, h("label", {}, "Product page URL"), urlIn)),
    h("div", { class: "src-grid" }, ...ZONES.map(zone)),
    list,
    h("div", { class: "src-actions" },
      h("div", { class: "note" }, "Reading uses Gemini for video and images and Claude for documents. Typical time: 1–3 minutes for a 2-minute video plus a catalogue.", h("br"), uploading),
      readBtn),
  ));
  refreshList();
  nameIn.addEventListener("change", saveMeta);
}
