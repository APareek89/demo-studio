import { api, h, toast, fmtSize } from "/web/api.js";
import { icon } from "/web/icons.js";

const SOURCE_ICONS = { intro_video: "video", hero: "image", product: "layers", catalogue: "file", brand: "sparkles", competitor: "globe" };

const ZONES = [
  { role: "intro_video", title: "Opening film (optional)", desc: "A 10–20 second brand or product film with audio. The guide greets the customer and asks what they need, then plays this film before beginning the tailored walkthrough. MP4/MOV.", accept: "video/*", multiple: false },
  { role: "hero", title: "Hero image (optional)", desc: "One picture of the whole product for the first and last slide. Without it, the best full-product image is used. JPG/PNG/WEBP/AVIF/HEIC.", accept: "image/*,.avif,.heic,.heif", multiple: false },
  { role: "product", title: "Product video & images", desc: "MP4/MOV video (up to 1 GB — the demo plays your original; export with “fast start” so seeking is instant), JPG/PNG/WEBP/AVIF/HEIC images.", accept: "video/*,image/*,.avif,.heic,.heif", multiple: true },
  { role: "catalogue", title: "Catalogue, spec sheet, price list", desc: "PDF, DOCX, TXT, MD, CSV. Every fact the guide will ever state comes from here — with a citation.", accept: ".pdf,.docx,.txt,.md,.csv", multiple: true },
  { role: "brand", title: "Brand guidelines", desc: "PDF/DOCX, or paste a few lines about tone and what never to say. Optional — the agent infers a restrained default.", accept: ".pdf,.docx,.txt,.md", multiple: true, text: true },
  { role: "competitor", title: "Competitor pages (optional)", desc: "Official product-page URLs only. Figures are extracted with citations and used for comparisons only if you switch comparisons on — every comparison ends with “as per their website when we checked — please verify”.", url: true },
];

export function renderSources(ctx) {
  const { demoId, area } = ctx;
  let demo = ctx.state.demo;
  const list = h("div", { class: "src-list" });
  const sourceCount = h("span", { class: "pill" });
  const uploading = h("span", { class: "uploading", role: "status", "aria-live": "polite" });
  const nameIn = h("input", { id: "source-product-name", value: demo.product?.name || demo.name || "", placeholder: "Product name" });
  const urlIn = h("input", { id: "source-product-url", value: demo.product?.url || "", placeholder: "https://example.com/product" });
  const readBtn = h("button", { class: "btn primary", onclick: startRead }, "Configure Demo", icon("arrow-right", { size: 17 }));
  const LANG_LIST = [["en-IN", "Indian English"], ["hinglish", "Hinglish"], ["hi-IN", "Hindi"], ["ta-IN", "Tamil"], ["te-IN", "Telugu"], ["kn-IN", "Kannada"], ["mr-IN", "Marathi"], ["bn-IN", "Bengali"], ["gu-IN", "Gujarati"], ["ml-IN", "Malayalam"], ["pa-IN", "Punjabi"]];
  const chosen = new Set(demo.settings?.languages?.length ? demo.settings.languages : [demo.settings?.language || "en-IN"]);
  const langChips = h("div", { class: "lang-chips" }, ...LANG_LIST.map(([v, l]) => { const cb = h("input", { type: "checkbox", checked: chosen.has(v) }); const lab = h("label", { class: chosen.has(v) ? "on" : "" }, cb, l); cb.onchange = async () => { if (cb.checked) chosen.add(v); else chosen.delete(v); if (!chosen.size) { chosen.add("en-IN"); } lab.classList.toggle("on", chosen.has(v)); try { await api.patch(`/api/demos/${demoId}`, { settings: { languages: LANG_LIST.map((x) => x[0]).filter((x) => chosen.has(x)) } }); toast("Languages: " + [...chosen].join(", ")); } catch (e) { toast(e.message, true); } }; return lab; }));
  const audSel = h("select", { id: "source-audience", onchange: async () => { try { await api.patch(`/api/demos/${demoId}`, { settings: { audience: audSel.value } }); toast("Audience: " + audSel.selectedOptions[0].textContent); } catch (e) { toast(e.message, true); } } },
    h("option", { value: "everyday", selected: (demo.settings?.audience || "everyday") === "everyday" }, "Everyday buyer — plain language, no jargon"),
    h("option", { value: "informed", selected: demo.settings?.audience === "informed" }, "Informed — light technical terms, explained"),
    h("option", { value: "expert", selected: demo.settings?.audience === "expert" }, "Expert — full technical detail"));
  const voiceSel = h("select", { id: "source-voice" }, h("option", { value: "" }, "Loading voices…"));
  const voiceStatus = h("span", { class: "help" }, "");
  let vinfo = null;
  api.get(`/api/voices?demo_id=${demoId}`).then((v) => { vinfo = v; voiceSel.replaceChildren(...v.voices.map((o) => h("option", { value: o.id, selected: o.id === v.current }, o.label))); voiceStatus.textContent = `${v.provider}` + (v.chain.length > 1 ? ` → ${v.chain.slice(1).join(" → ")}` : "") + ` · listening: ${v.stt}` + (v.unavailable && Object.keys(v.unavailable).length ? ` · ⚠ ${Object.entries(v.unavailable).map(([k, w]) => `${k} unavailable (${w.slice(0, 60)})`).join("; ")}` : ""); }).catch(() => { voiceSel.replaceChildren(h("option", { value: "" }, "browser voice")); });
  const previewBtn = h("button", { class: "btn sm", onclick: async () => { if (!vinfo || !voiceSel.value) return; previewBtn.disabled = true; voiceStatus.textContent = "recording a sample…"; try { await api.patch(`/api/demos/${demoId}`, { settings: { [vinfo.setting_key]: voiceSel.value } }); const r = await api.post(`/api/demos/${demoId}/voice/sample`, { text: "Hi, I'm your guide for today. Tell me what you're hoping this will change for you, and I'll show you that first." }); if (r.url) { new Audio(r.url).play(); voiceStatus.textContent = "playing " + voiceSel.selectedOptions[0].textContent; } else voiceStatus.textContent = "no server voice — browser voice will be used"; } catch (e) { toast(e.message, true); voiceStatus.textContent = ""; } previewBtn.disabled = false; } }, icon("play", { size: 15 }), "Preview");

  async function refreshList() {
    sourceCount.textContent = `${demo.sources.length} added`;
    list.replaceChildren(...demo.sources.map((s) => h("div", { class: "src-item" },
      h("span", { class: "source-file-icon", title: s.kind }, icon(({ video: "video", image: "image", url: "link" })[s.kind] || "file")), h("span", { class: "kind" }, s.kind), h("span", { class: "name", title: s.name }, s.name),
      h("span", { class: "pill" }, s.role), h("span", { class: "size" }, s.size ? fmtSize(s.size) : "url"),
      (s.kind === "video" || s.kind === "image") ? h("label", { class: "use", title: "Off = the agent still learns from it, but it is not shown in the demo" }, h("input", { type: "checkbox", checked: s.use_in_demo !== false, onchange: async (e) => { try { const r = await api.patch(`/api/demos/${demoId}/sources/${s.id}`, { use_in_demo: e.target.checked }); demo.sources = r.sources; } catch (err) { toast(err.message, true); } } }), "use in demo") : null,
      h("button", { class: "btn sm ghost source-remove", title: `Remove ${s.name}`, "aria-label": `Remove ${s.name}`, onclick: async () => { const r = await api.del(`/api/demos/${demoId}/sources/${s.id}`); demo.sources = r.sources; refreshList(); } }, icon("trash", { size: 16 })) )));
    if (!demo.sources.length) list.append(h("div", { class: "studio-empty source-empty" }, icon("upload", { size: 24 }), h("div", {}, h("h3", {}, "Your source library starts here"), h("p", {}, "Add product material above. Everything you add will appear here for review."))));
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
      const u = h("input", { "aria-label": "Competitor product page URL", placeholder: "https://example.com/competitor", style: "flex:1;min-width:220px" });
      const compSel = h("select", { onchange: async () => { try { await api.patch(`/api/demos/${demoId}`, { settings: { competition: compSel.value } }); toast(compSel.value === "on" ? "Comparisons on — cited, with a verify caveat" : "Comparisons off"); } catch (e) { toast(e.message, true); } } }, h("option", { value: "off", selected: (demo.settings?.competition || "off") === "off" }, "Comparisons: off (guide declines to compare)"), h("option", { value: "on", selected: demo.settings?.competition === "on" }, "Comparisons: on — only from these pages, always with a verify caveat"));
      compSel.setAttribute("aria-label", "Competitor comparisons");
      return h("div", { class: "zone wide" }, h("div", { class: "zone-title" }, h("span", { class: "zone-icon" }, icon(SOURCE_ICONS[z.role])), h("h3", {}, z.title)), h("p", {}, z.desc), h("div", { class: "pick" }, u, h("button", { class: "btn sm", onclick: () => { const v = u.value.trim(); if (v) { upload("competitor", [], { url: v }); u.value = ""; } } }, icon("plus", { size: 15 }), "Add page"), compSel));
    }
    const input = h("input", { type: "file", accept: z.accept, multiple: z.multiple, "aria-label": z.title });
    input.addEventListener("change", () => { if (input.files.length) upload(z.role, [...input.files]); input.value = ""; });
    const el = h("div", { class: "zone" + (z.text ? " wide" : "") },
      h("div", { class: "zone-title" }, h("span", { class: "zone-icon" }, icon(SOURCE_ICONS[z.role])), h("h3", {}, z.title)), h("p", {}, z.desc),
      h("div", { class: "pick" }, h("button", { class: "btn sm", onclick: () => input.click() }, icon("upload", { size: 15 }), "Choose files"), h("span", { class: "muted small" }, "or drag and drop"), input),
    );
    if (z.text) {
      const ta = h("textarea", { "aria-label": "Brand guidelines", placeholder: "e.g. Warm and direct. Never say “cheapest”. Always call it a “scooter”, not a “bike”.", style: "width:100%;margin-top:10px" });
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
    h("header", { class: "studio-page-head" }, h("div", { class: "eyebrow" }, "Demo workspace / Sources"), h("h1", {}, "Give your demo a strong foundation"), h("p", { class: "lede" }, "Add the product knowledge, visuals and brand direction your guide needs. Review what it learns before building your demo.")),
    h("section", { class: "source-identity" }, h("div", { class: "studio-section-title" }, icon("layers", { size: 19 }), h("h2", {}, "Product details")), h("div", { class: "form-row" }, h("div", {}, h("label", { for: "source-product-name" }, "Product name"), nameIn), h("div", {}, h("label", { for: "source-product-url" }, "Product page URL"), urlIn))),
    h("div", { class: "studio-section-title" }, icon("settings", { size: 19 }), h("h2", {}, "Demo preferences")),
    h("div", { class: "settings" },
      h("div", {}, h("label", { for: "source-audience" }, "Who is the demo for"), audSel, h("div", { class: "help" }, "Match the level of detail to your audience. Everyday buyers hear plain language, with technical detail available when asked.")),
      h("div", {}, h("label", {}, "Languages"), langChips, h("div", { class: "help" }, "First one is the main script; each extra language is translated and voiced at build (more narration lines = more cost).")),
      h("div", {}, h("label", { for: "source-voice" }, "Voice"), h("div", { class: "voice-picker", style: "display:flex;gap:6px;align-items:center" }, voiceSel, previewBtn), h("div", { class: "help" }, voiceStatus)),
      h("div", {}, h("label", {}, "Opening film"), (() => { const has = demo.sources.some((x) => x.kind === "video" && x.role === "intro_video"); const cb = h("input", { type: "checkbox", checked: has && (demo.settings?.intro_video || "on") !== "off", disabled: !has, onchange: async () => { try { await api.patch(`/api/demos/${demoId}`, { settings: { intro_video: cb.checked ? "on" : "off" } }); toast(cb.checked ? "Opening film will play after the needs question" : "Opening film off"); } catch (e) { toast(e.message, true); } } }); return h("div", {}, h("label", { style: "display:flex;gap:8px;align-items:center;text-transform:none;letter-spacing:0;font-family:var(--disp);font-size:13px;color:var(--ink)" }, cb, has ? "Play after the guide asks what the customer needs" : "Upload a film in the “Opening film” box first"), h("div", { class: "help" }, "10–20 s with audio. Greeting → needs question → film → tailored walkthrough. The agent plans during the film, so there’s no visible wait.")); })())),
    h("div", { class: "studio-section-title" }, icon("layers", { size: 19 }), h("h2", {}, "Source material"), h("span", { class: "small muted" }, "Files, visuals and official pages")),
    h("div", { class: "src-grid" }, ...ZONES.map(zone)),
    h("div", { class: "studio-section-title source-library-title" }, icon("file", { size: 19 }), h("h2", {}, "Source library"), sourceCount),
    list,
    h("div", { class: "src-actions" },
      h("div", { class: "note" }, h("strong", {}, "Next: review and align"), h("br"), "Your guide reads the sources and prepares the facts, visuals and pitch for your approval. Allow 1–3 minutes. Questions outside the sources are left open.", h("br"), uploading),
      readBtn),
  ));
  refreshList();
  nameIn.addEventListener("change", saveMeta);
}
