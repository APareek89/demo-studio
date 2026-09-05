import { api, h, toast, fmtSize, fmtTime } from "/web/api.js";

export async function renderVisual(ctx) {
  const { demoId, area, navigate } = ctx;
  let state = ctx.state.visual || await api.get(`/api/demos/${demoId}/visual`);
  let busy = false;

  async function refresh() {
    try { state = await api.get(`/api/demos/${demoId}/visual`); draw(); }
    catch (e) { toast(e.message, true); }
  }

  async function uploadImage(angle, file) {
    if (!file || busy) return;
    busy = true; draw();
    const fd = new FormData(); fd.append("angle", angle); fd.append("file", file);
    try { state = await api.form(`/api/demos/${demoId}/visual/images`, fd); toast("Product view added"); }
    catch (e) { toast(e.message, true); }
    busy = false; draw();
  }

  async function uploadVideo(file) {
    if (!file || busy) return;
    busy = true; draw();
    const fd = new FormData(); fd.append("file", file);
    try { state = await api.form(`/api/demos/${demoId}/visual/video`, fd); toast("Turntable video added"); }
    catch (e) { toast(e.message, true); }
    busy = false; draw();
  }

  async function uploadGlb(file) {
    if (!file || busy) return;
    busy = true; draw();
    const fd = new FormData(); fd.append("file", file);
    try { state = await api.form(`/api/demos/${demoId}/visual/upload`, fd); toast("3D asset ready to review"); }
    catch (e) { toast(e.message, true); }
    busy = false; draw();
  }

  async function act(path, body) {
    try { const result = await api.post(path, body || {}); state = result.visual || result; draw(); return result; }
    catch (e) { toast(e.message, true); return null; }
  }

  function inputFor(onFile, accept, label = "Choose file") {
    const input = h("input", { type: "file", accept });
    input.addEventListener("change", () => { const f = input.files?.[0]; input.value = ""; if (f) onFile(f); });
    return [h("button", { class: "btn sm", onclick: () => input.click(), disabled: busy }, label), input];
  }

  function imageSlot(spec) {
    const item = state.angles?.[spec.key];
    const [pick, input] = inputFor((f) => uploadImage(spec.key, f), "image/*,.avif,.heic,.heif", item ? "Replace" : "Add view");
    const slot = h("article", { class: `shot-slot${item ? " filled" : ""}` },
      h("div", { class: "shot-head" }, h("div", {}, h("h3", {}, spec.label), h("span", { class: `pill ${spec.required ? "warn" : ""}` }, spec.required ? "required" : "optional")), item ? h("span", { class: `origin ${item.generated ? "generated" : "real"}` }, item.generated ? "AI GENERATED" : "REAL") : null),
      item ? h("img", { src: item.url, alt: `${spec.label} product view` }) : h("div", { class: "shot-placeholder", role: "img", "aria-label": `Empty ${spec.label} upload slot` }, h("span", {}, "＋"), spec.label),
      h("p", {}, spec.guidance),
      h("div", { class: "shot-actions" }, pick, item ? h("button", { class: "btn sm ghost danger", onclick: async () => { if (!confirm(`Remove the ${spec.label} view?`)) return; state = await api.del(`/api/demos/${demoId}/visual/images/${spec.key}`); draw(); } }, "Remove") : null, input));
    slot.addEventListener("dragover", (e) => { e.preventDefault(); slot.classList.add("over"); });
    slot.addEventListener("dragleave", () => slot.classList.remove("over"));
    slot.addEventListener("drop", (e) => { e.preventDefault(); slot.classList.remove("over"); if (e.dataTransfer.files?.[0]) uploadImage(spec.key, e.dataTransfer.files[0]); });
    return slot;
  }

  function attempts() {
    if (!state.attempts?.length) return null;
    return h("section", { class: "attempts" }, h("div", { class: "eyebrow" }, "Version history"),
      ...[...state.attempts].reverse().map((a) => h("div", { class: "attempt" },
        h("span", { class: "mono" }, `#${a.number}`), h("span", { class: `pill ${a.status === "approved" ? "ok" : a.status === "error" ? "bad" : a.status === "running" ? "run" : ""}` }, a.status),
        h("span", { class: "muted" }, a.change || (a.started_at ? fmtTime(a.started_at) : "")),
        a.cost_usd ? h("span", { class: "mono muted" }, `$${Number(a.cost_usd).toFixed(4)}`) : null)));
  }

  function review(attempt) {
    const [replaceGlb, replaceGlbInput] = inputFor(uploadGlb, ".glb,model/gltf-binary", "Upload replacement");
    const modelLabel = attempt.uploaded ? "Uploaded GLB" : ((state.models || []).find((m) => m.id === attempt.model)?.label || attempt.model || state.model);
    return h("div", { class: "visual-review" },
      h("section", { class: "viewer-panel" },
        h("div", { class: "viewer-head" }, h("div", {}, h("div", { class: "eyebrow" }, `Attempt ${attempt.number}`), h("h2", {}, "Rotate it. Inspect the silhouette and details.")), h("span", { class: "pill run" }, modelLabel)),
        h("model-viewer", { src: attempt.glb_url, poster: attempt.preview_url || "", "camera-controls": true, "auto-rotate": true, "shadow-intensity": "1", "environment-image": "neutral", "touch-action": "pan-y", alt: "Generated 3D product asset" }),
        h("div", { class: "review-meta" }, attempt.uploaded ? h("span", {}, "Uploaded by you") : h("span", {}, `${attempt.real_count || 0} real view${attempt.real_count === 1 ? "" : "s"}`), attempt.uploaded ? null : h("span", {}, `${attempt.generated_count || 0} approved AI gap-fill view${attempt.generated_count === 1 ? "" : "s"}`), h("span", {}, attempt.size ? fmtSize(attempt.size) : "GLB"), attempt.uploaded ? h("span", {}, "No generation charge") : h("span", {}, attempt.primary_angle?.replaceAll("_", " ") || "primary view"))),
      h("aside", { class: "review-side" },
        h("h3", {}, attempt.uploaded ? "Your 3D asset" : "Source views"), h("p", { class: "muted small" }, attempt.uploaded ? "This file bypasses image-to-3D generation, but still needs your approval before it becomes the demo’s main visual." : "These preserve product identity and support review. During playback, the 3D hero gives way to an exact image or cited card when the narration moves to a feature the model cannot visibly prove."),
        attempt.uploaded ? null : h("div", { class: "support-grid" }, ...Object.values(state.angles || {}).map((x) => h("figure", {}, h("img", { src: x.url, alt: x.label }), h("figcaption", {}, x.label, h("span", { class: `origin ${x.generated ? "generated" : "real"}` }, x.generated ? "AI" : "REAL"))))),
        h("div", { class: "review-actions" },
          h("button", { class: "btn primary", onclick: async () => { const r = await act(`/api/demos/${demoId}/visual/approve`); if (r) { toast("3D asset approved"); navigate(`#/studio/${demoId}/sources`); } } }, "Approve & continue"),
          attempt.uploaded ? replaceGlb : h("button", { class: "btn", onclick: () => act(`/api/demos/${demoId}/visual/generate`, { model: state.model }) }, "Regenerate"),
          attempt.uploaded ? replaceGlbInput : null,
          h("button", { class: "btn ghost", onclick: async () => { await act(`/api/demos/${demoId}/visual/skip`); navigate(`#/studio/${demoId}/sources`); } }, "Skip for now")),
        attempts()));
  }

  function reviewViews() {
    const feedback = h("textarea", { placeholder: "What should change? For example: use a clearer front view, remove reflections, or keep the exact black, silver and red trim." }, state.view_feedback || "");
    const generated = Object.values(state.angles || {}).filter((x) => x.generated).length;
    return h("div", { class: "view-review-page" },
      h("div", { class: "visual-hero compact" }, h("div", {}, h("div", { class: "eyebrow" }, "Approval gate · no Runware charge yet"), h("h1", {}, "Approve the views that will shape the 3D asset."), h("p", {}, `Check colour, trim, proportions and angle. ${generated ? `${generated} missing view${generated === 1 ? " was" : "s were"} created with Nano Banana 2 Lite and labelled AI.` : "Every view came from your upload."}`))),
      h("section", { class: "view-review-grid" }, ...state.schema.filter((spec) => state.angles?.[spec.key]).map((spec) => {
        const item = state.angles[spec.key];
        return h("figure", {}, h("img", { src: item.url, alt: spec.label }), h("figcaption", {}, h("b", {}, spec.label), h("span", { class: `origin ${item.generated ? "generated" : "real"}` }, item.generated ? "AI · NANO BANANA 2 LITE" : "REAL SOURCE"), h("small", {}, item.name || "")));
      })),
      h("section", { class: "view-feedback" },
        h("div", {}, h("h3", {}, "Want a different result?"), h("p", { class: "small muted" }, generated ? "Describe the correction and regenerate the selected/generated views. Product identity must still match the recording." : "These are real uploads. Replace a view if it is wrong; feedback is used when a video frame or missing angle must be regenerated.")),
        feedback,
        h("div", { class: "actions" },
          h("button", { class: "btn ghost", onclick: () => { state.status = "collecting"; draw(); } }, "Replace a view"),
          h("button", { class: "btn", onclick: () => act(`/api/demos/${demoId}/visual/views/prepare`, { feedback: feedback.value.trim() }) }, "Regenerate views"),
          h("button", { class: "btn primary", disabled: !state.runware_ready, onclick: async () => { const approved = await act(`/api/demos/${demoId}/visual/views/approve`); if (approved) await act(`/api/demos/${demoId}/visual/generate`, { model: state.model }); } }, state.runware_ready ? "Approve views & build 3D" : "Runware key needed"))));
  }

  function draw() {
    const attempt = state.attempts?.find((a) => a.number === state.active_attempt && ["review", "approved"].includes(a.status));
    const required = state.schema.filter((x) => x.required);
    const missing = required.filter((x) => !state.angles?.[x.key]);
    const canBuild = state.mode === "video" ? !!state.video : missing.length === 0;
    if (attempt && state.status === "review") {
      area.replaceChildren(h("div", { class: "visual-page review-page" }, review(attempt)));
      return;
    }
    if (state.status === "views_review") {
      area.replaceChildren(h("div", { class: "visual-page review-page" }, reviewViews()));
      return;
    }
    const [videoPick, videoInput] = inputFor(uploadVideo, "video/mp4,video/quicktime,video/webm,.m4v", state.video ? "Replace video" : "Choose video");
    const [glbPick, glbInput] = inputFor(uploadGlb, ".glb,model/gltf-binary", "Upload GLB");
    const preparingViews = state.status === "preparing_views";
    const progressPanel = ["generating", "preparing_views"].includes(state.status) ? h("section", { class: "visual-progress" }, h("div", { class: "progress-copy" }, h("div", { class: "eyebrow" }, preparingViews ? "Preparing product views" : "Building your 3D asset"), h("h2", {}, state.message || "Working…"), h("p", { class: "muted" }, preparingViews ? "You will approve these views before Runware starts. No 3D generation charge has been incurred yet." : "You can skip this optional step and continue building the demo. Saved inputs and earlier attempts remain here. If Runware has already accepted the job, it may still finish and bill.")), h("div", { class: "bar" }, h("span", { style: `width:${state.progress || 1}%` })), h("div", { class: "mono muted" }, `${state.progress || 1}%`), h("button", { class: "btn ghost", onclick: async () => { await act(`/api/demos/${demoId}/visual/skip`); navigate(`#/studio/${demoId}/sources`); } }, "Skip and continue")) : null;
    const error = state.error ? h("div", { class: "visual-error" }, h("b", {}, "The 3D build stopped."), " ", state.error, h("div", { class: "small muted" }, "Your uploaded views are intact. Fix the issue and try again, or skip this step.")) : null;
    const imagePanel = h("section", {},
      h("div", { class: "section-title" },
        h("div", {}, h("h2", {}, state.category === "vehicle" ? "Five required vehicle views" : "Five required product views"), h("p", {}, "Use the same physical product, variant, colour and trim. Front ¾ controls material identity; the remaining real views lock the shape.")),
        h("span", { class: `pill ${missing.length ? "warn" : "ok"}` }, missing.length ? `${missing.length} required left` : "ready to build")),
      h("div", { class: "shot-grid" }, ...state.schema.map(imageSlot)));
    const videoPanel = h("section", { class: "video-option" },
      h("div", { class: "video-drop" },
        state.video ? h("video", { src: state.video.url, controls: true, muted: true, playsinline: true }) : h("div", { class: "video-glyph" }, "◫"),
        h("div", {}, h("h2", {}, state.video ? state.video.name : "Upload a slow 360° product turn"), h("p", {}, state.video ? fmtSize(state.video.size) : "Keep the full product in frame. A clean 10–30 second rotation works best; MP4, MOV, M4V or WebM."), h("div", {}, videoPick, videoInput))),
      h("div", { class: "pipeline-note" }, h("b", {}, "What happens next"), " Gemini selects real frames for each angle. Only missing views are created and visibly labelled. Nothing reaches Runware until you approve every view; the primary identity view is always real."));
    const selected = (state.models || []).find((m) => m.id === state.model) || (state.models || [])[0];
    const modelPicker = h("select", { class: "model-picker", onchange: (e) => { state.model = e.target.value; draw(); } },
      ...(state.models || []).map((m) => h("option", { value: m.id, selected: m.id === state.model }, `${m.recommended ? "Best fidelity — " : "Alternative — "}${m.label}`)));
    const footer = h("div", { class: "visual-footer" },
      h("div", {}, h("b", {}, state.runware_ready ? (canBuild ? `Ready for ${selected?.label || "Runware"}` : "Complete the input first") : "Runware key needed"), h("span", {}, !state.runware_ready ? " Add RUNWARE_API_KEY to .env to enable live generation." : state.mode === "images" && missing.length ? ` Missing: ${missing.map((x) => x.label).join(", ")}.` : ` Accepts up to ${selected?.max_images || 1} real source view${selected?.max_images === 1 ? "" : "s"}; exact cost is recorded.`), state.models?.length ? h("div", { class: "model-choice" }, modelPicker) : null),
      h("div", { class: "actions" },
        h("button", { class: "btn ghost", onclick: async () => { await act(`/api/demos/${demoId}/visual/skip`); navigate(`#/studio/${demoId}/sources`); } }, "Skip for now"),
        h("button", { class: "btn primary", disabled: !canBuild || ["generating", "preparing_views"].includes(state.status) || (state.views_approved && !state.runware_ready), onclick: () => state.views_approved ? act(`/api/demos/${demoId}/visual/generate`, { model: state.model }) : act(`/api/demos/${demoId}/visual/views/prepare`, {}), }, state.views_approved ? (state.attempts?.length ? "Regenerate 3D" : "Build 3D asset") : "Review source views")));
    const page = h("div", { class: "visual-page" },
      h("div", { class: "visual-hero" }, h("div", {}, h("div", { class: "eyebrow" }, "Optional · Demo visual"), h("h1", {}, "Make the product the stage."), h("p", {}, "The 3D product leads exterior moments. When Ravi speaks about a cabin detail, safety feature or written term, the exact source evidence takes over the stage."))),
      h("section", { class: "direct-3d" }, h("div", {}, h("h3", {}, "Already have a 3D asset?"), h("p", { class: "muted small" }, "Upload a self-contained GLB and skip image-to-3D generation. You will still rotate and approve it before use.")), h("div", {}, glbPick, glbInput)),
      h("div", { class: "mode-switch", role: "tablist", "aria-label": "Visual input method" },
        h("button", { class: state.mode === "images" ? "active" : "", role: "tab", onclick: async () => { if (state.mode !== "images") await act(`/api/demos/${demoId}/visual/mode`, { mode: "images" }); } }, h("b", {}, "Product views"), h("span", {}, "Best fidelity · five real angles")),
        h("button", { class: state.mode === "video" ? "active" : "", role: "tab", onclick: async () => { if (state.mode !== "video") await act(`/api/demos/${demoId}/visual/mode`, { mode: "video" }); } }, h("b", {}, "Turntable video"), h("span", {}, "Fastest · views extracted automatically"))),
      error,
      state.mode === "images" ? imagePanel : videoPanel,
      progressPanel,
      footer,
      attempts());
    area.replaceChildren(page);
  }

  draw();
  ctx.subscribe((type, event) => {
    if (!["visual", "visual_views"].includes(event.phase)) return;
    if (type === "progress") { state.progress = event.percent; state.message = event.message; if (state.status !== "preparing_views") state.status = "generating"; draw(); }
    else refresh();
  });
}
