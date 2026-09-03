import { api, h, toast, fmtSize } from "/web/api.js";

const ZONES = [
  { role: "product", title: "Product video & images", desc: "MP4/MOV video (up to 1 GB — the demo plays your original; export with “fast start” so seeking is instant), JPG/PNG/WEBP/AVIF/HEIC images.", accept: "video/*,image/*,.avif,.heic,.heif", multiple: true },
  { role: "catalogue", title: "Catalogue, spec sheet, price list", desc: "PDF, DOCX, TXT, MD. Every fact the guide will ever state comes from here — with a citation.", accept: ".pdf,.docx,.txt,.md,.csv", multiple: true },
  { role: "brand", title: "Brand guidelines", desc: "PDF/DOCX, or paste a few lines about tone and what never to say. Optional — the agent infers a restrained default.", accept: ".pdf,.docx,.txt,.md", multiple: true, text: true },
  { role: "competitor", title: "Competitor pages (optional)", desc: "Official product-page URLs only. Figures are extracted with citations and used for comparisons only if you switch comparisons on — every comparison ends with “as per their website when we checked — please verify”.", url: true },
];

export function renderSources(ctx) {
  const { demoId, area } = ctx;
  let demo = ctx.state.demo;
  const list = h("div", { class: "src-list" });
  const uploading = h("span", { class: "uploading" });
  const nameIn = h("input", { value: demo.product?.name || demo.name || "" });
  const urlIn = h("input", { value: demo.product?.url || "", placeholder: "https://… product page" });
  const readBtn = h("button", { class: "btn primary", onclick: startRead }, "Configure Demo →");
  const LANG_LIST = [["en-IN", "Indian English"], ["hinglish", "Hinglish"], ["hi-IN", "Hindi"], ["ta-IN", "Tamil"], ["te-IN", "Telugu"], ["kn-IN", "Kannada"], ["mr-IN", "Marathi"], ["bn-IN", "Bengali"], ["gu-IN", "Gujarati"], ["ml-IN", "Malayalam"], ["pa-IN", "Punjabi"]];
  const chosen = new Set(demo.settings?.languages?.length ? demo.settings.languages : [demo.settings?.language || "en-IN"]);
  const langChips = h("div", { class: "lang-chips" }, ...LANG_LIST.map(([v, l]) => { const cb = h("input", { type: "checkbox", checked: chosen.has(v) }); const lab = h("label", { class: chosen.has(v) ? "on" : "" }, cb, l); cb.onchange = async () => { if (cb.checked) chosen.add(v); else chosen.delete(v); if (!chosen.size) { chosen.add("en-IN"); } lab.classList.toggle("on", chosen.has(v)); try { await api.patch(`/api/demos/${demoId}`, { settings: { languages: LANG_LIST.map((x) => x[0]).filter((x) => chosen.has(x)) } }); toast("Languages: " + [...chosen].join(", ")); } catch (e) { toast(e.message, true); } }; return lab; }));
  const audSel = h("select", { onchange: async () => { try { await api.patch(`/api/demos/${demoId}`, { settings: { audience: audSel.value } }); toast("Audience: " + audSel.selectedOptions[0].textContent); } catch (e) { toast(e.message, true); } } },
    h("option", { value: "everyday", selected: (demo.settings?.audience || "everyday") === "everyday" }, "Everyday buyer — plain language, no jargon"),
    h("option", { value: "informed", selected: demo.settings?.audience === "informed" }, "Informed — light technical terms, explained"),
    h("option", { value: "expert", selected: demo.settings?.audience === "expert" }, "Expert — full technical detail"));
  const voiceSel = h("select", {}, h("option", { value: "" }, "loading voices…"));
  const voiceStatus = h("span", { class: "help" }, "");
  let vinfo = null;
  api.get(`/api/voices?demo_id=${demoId}`).then((v) => { vinfo = v; voiceSel.replaceChildren(...v.voices.map((o) => h("option", { value: o.id, selected: o.id === v.current }, o.label))); voiceStatus.textContent = `${v.provider}` + (v.chain.length > 1 ? ` → ${v.chain.slice(1).join(" → ")}` : "") + ` · listening: ${v.stt}` + (v.unavailable && Object.keys(v.unavailable).length ? ` · ⚠ ${Object.entries(v.unavailable).map(([k, w]) => `${k} unavailable (${w.slice(0, 60)})`).join("; ")}` : ""); }).catch(() => { voiceSel.replaceChildren(h("option", { value: "" }, "browser voice")); });
  const previewBtn = h("button", { class: "btn sm", onclick: async () => { if (!vinfo || !voiceSel.value) return; previewBtn.disabled = true; voiceStatus.textContent = "recording a sample…"; try { await api.patch(`/api/demos/${demoId}`, { settings: { [vinfo.setting_key]: voiceSel.value } }); const r = await api.post(`/api/demos/${demoId}/voice/sample`, { text: "Hi, I'm your guide for today. Tell me what you're hoping this will change for you, and I'll show you that first." }); if (r.url) { new Audio(r.url).play(); voiceStatus.textContent = "playing " + voiceSel.selectedOptions[0].textContent; } else voiceStatus.textContent = "no server voice — browser voice will be used"; } catch (e) { toast(e.message, true); voiceStatus.textContent = ""; } previewBtn.disabled = false; } }, "▶ Preview");

  async function refreshList() {
    list.replaceChildren(...demo.sources.map((s) => h("div", { class: "src-item" },
      h("span", { class: "kind" }, s.kind), h("span", { class: "name", title: s.name }, s.name),
      h("span", { class: "pill" }, s.role), h("span", { class: "size" }, s.size ? fmtSize(s.size) : "url"),
      (s.kind === "video" || s.kind === "image") ? h("label", { class: "use", title: "Off = the agent still learns from it, but it is not shown in the demo" }, h("input", { type: "checkbox", checked: s.use_in_demo !== false, onchange: async (e) => { try { const r = await api.patch(`/api/demos/${demoId}/sources/${s.id}`, { use_in_demo: e.target.checked }); demo.sources = r.sources; } catch (err) { toast(err.message, true); } } }), "use in demo") : null,
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
    if (z.url) {
      const u = h("input", { placeholder: "https://… competitor product page", style: "flex:1;min-width:260px" });
      const compSel = h("select", { onchange: async () => { try { await api.patch(`/api/demos/${demoId}`, { settings: { competition: compSel.value } }); toast(compSel.value === "on" ? "Comparisons on — cited, with a verify caveat" : "Comparisons off"); } catch (e) { toast(e.message, true); } } }, h("option", { value: "off", selected: (demo.settings?.competition || "off") === "off" }, "Comparisons: off (guide declines to compare)"), h("option", { value: "on", selected: demo.settings?.competition === "on" }, "Comparisons: on — only from these pages, always with a verify caveat"));
      return h("div", { class: "zone wide" }, h("h3", {}, z.title), h("p", {}, z.desc), h("div", { class: "pick" }, u, h("button", { class: "btn sm", onclick: () => { const v = u.value.trim(); if (v) { upload("competitor", [], { url: v }); u.value = ""; } } }, "Add page"), compSel));
    }
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
    h("div", { class: "settings" },
      h("div", {}, h("label", {}, "Who is the demo for"), audSel, h("div", { class: "help" }, "Everyday = no “kWh”, “IDC”, “15A” — the guide says “battery size”, “certified on the standard test”, “a normal socket”. Detail only when asked.")),
      h("div", {}, h("label", {}, "Languages"), langChips, h("div", { class: "help" }, "First one is the main script; each extra language is translated and voiced at build (more narration lines = more cost).")),
      h("div", {}, h("label", {}, "Voice"), h("div", { style: "display:flex;gap:6px;align-items:center" }, voiceSel, previewBtn), h("div", { class: "help" }, voiceStatus))),
    h("div", { class: "src-grid" }, ...ZONES.map(zone)),
    list,
    h("div", { class: "src-actions" },
      h("div", { class: "note" }, "Configuring reads everything: Gemini watches video and images, Claude builds the fact registry and plans the pitch. 1–3 minutes. Anything you don't provide, the guide will not answer — it says so and offers a callback.", h("br"), uploading),
      readBtn),
  ));
  refreshList();
  nameIn.addEventListener("change", saveMeta);
}
