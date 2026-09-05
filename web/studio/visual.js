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
    return h("div", { class: "visual-review" },
      h("section", { class: "viewer-panel" },
        h("div", { class: "viewer-head" }, h("div", {}, h("div", { class: "eyebrow" }, `Attempt ${attempt.number}`), h("h2", {}, "Rotate it. Inspect the silhouette and details.")), h("span", { class: "pill run" }, state.model)),
        h("model-viewer", { src: attempt.glb_url, poster: attempt.preview_url || "", "camera-controls": true, "auto-rotate": true, "shadow-intensity": "1", "environment-image": "neutral", "touch-action": "pan-y", alt: "Generated 3D product asset" }),
        h("div", { class: "review-meta" }, h("span", {}, `${attempt.real_count || 0} real view${attempt.real_count === 1 ? "" : "s"}`), h("span", {}, `${attempt.generated_count || 0} AI-created supporting view${attempt.generated_count === 1 ? "" : "s"}`), h("span", {}, attempt.size ? fmtSize(attempt.size) : "GLB"), h("span", {}, attempt.primary_angle?.replaceAll("_", " ") || "primary view"))),
      h("aside", { class: "review-side" },
        h("h3", {}, "Supporting views"), h("p", { class: "muted small" }, "These stay visible as labelled thumbnails while the approved 3D product remains the main demo visual."),
        h("div", { class: "support-grid" }, ...Object.values(state.angles || {}).map((x) => h("figure", {}, h("img", { src: x.url, alt: x.label }), h("figcaption", {}, x.label, h("span", { class: `origin ${x.generated ? "generated" : "real"}` }, x.generated ? "AI" : "REAL"))))),
        h("div", { class: "review-actions" },
          h("button", { class: "btn primary", onclick: async () => { const r = await act(`/api/demos/${demoId}/visual/approve`); if (r) { toast("3D asset approved"); navigate(`#/studio/${demoId}/sources`); } } }, "Approve & continue"),
          h("button", { class: "btn", onclick: () => act(`/api/demos/${demoId}/visual/generate`) }, "Regenerate"),
          h("button", { class: "btn ghost", onclick: async () => { await act(`/api/demos/${demoId}/visual/skip`); navigate(`#/studio/${demoId}/sources`); } }, "Skip for now")),
        attempts()));
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
    const [videoPick, videoInput] = inputFor(uploadVideo, "video/mp4,video/quicktime,video/webm,.m4v", state.video ? "Replace video" : "Choose video");
    const progressPanel = state.status === "generating" ? h("section", { class: "visual-progress" }, h("div", { class: "progress-copy" }, h("div", { class: "eyebrow" }, "Building your 3D asset"), h("h2", {}, state.message || "Working…"), h("p", { class: "muted" }, "You can skip this optional step and continue building the demo. Saved inputs and earlier attempts remain here. If Runware has already accepted the job, it may still finish and bill.")), h("div", { class: "bar" }, h("span", { style: `width:${state.progress || 1}%` })), h("div", { class: "mono muted" }, `${state.progress || 1}%`), h("button", { class: "btn ghost", onclick: async () => { await act(`/api/demos/${demoId}/visual/skip`); navigate(`#/studio/${demoId}/sources`); } }, "Skip and continue")) : null;
    const error = state.error ? h("div", { class: "visual-error" }, h("b", {}, "The 3D build stopped."), " ", state.error, h("div", { class: "small muted" }, "Your uploaded views are intact. Fix the issue and try again, or skip this step.")) : null;
    const imagePanel = h("section", {},
      h("div", { class: "section-title" },
        h("div", {}, h("h2", {}, state.category === "vehicle" ? "Five required vehicle views" : "Five required product views"), h("p", {}, "Use the same physical product, variant, colour and lighting. Front ¾ becomes the preferred TRELLIS.2 input.")),
        h("span", { class: `pill ${missing.length ? "warn" : "ok"}` }, missing.length ? `${missing.length} required left` : "ready to build")),
      h("div", { class: "shot-grid" }, ...state.schema.map(imageSlot)));
    const videoPanel = h("section", { class: "video-option" },
      h("div", { class: "video-drop" },
        state.video ? h("video", { src: state.video.url, controls: true, muted: true, playsinline: true }) : h("div", { class: "video-glyph" }, "◫"),
        h("div", {}, h("h2", {}, state.video ? state.video.name : "Upload a slow 360° product turn"), h("p", {}, state.video ? fmtSize(state.video.size) : "Keep the full product in frame. A clean 10–30 second rotation works best; MP4, MOV, M4V or WebM."), h("div", {}, videoPick, videoInput))),
      h("div", { class: "pipeline-note" }, h("b", {}, "What happens next"), " Gemini selects real frames for each angle. Only missing views are created and visibly labelled. The strongest real view—not an AI-created angle—drives TRELLIS.2."));
    const footer = h("div", { class: "visual-footer" },
      h("div", {}, h("b", {}, state.runware_ready ? (canBuild ? "Ready for TRELLIS.2" : "Complete the input first") : "Runware key needed"), h("span", {}, !state.runware_ready ? " Add RUNWARE_API_KEY to .env to enable live generation." : state.mode === "images" && missing.length ? ` Missing: ${missing.map((x) => x.label).join(", ")}.` : " The build runs in the background and records its exact cost.")),
      h("div", { class: "actions" },
        h("button", { class: "btn ghost", onclick: async () => { await act(`/api/demos/${demoId}/visual/skip`); navigate(`#/studio/${demoId}/sources`); } }, "Skip for now"),
        h("button", { class: "btn primary", disabled: !canBuild || !state.runware_ready || state.status === "generating", onclick: () => act(`/api/demos/${demoId}/visual/generate`) }, state.attempts?.length ? "Regenerate 3D" : "Build 3D asset")));
    const page = h("div", { class: "visual-page" },
      h("div", { class: "visual-hero" }, h("div", {}, h("div", { class: "eyebrow" }, "Optional · Demo visual"), h("h1", {}, "Make the product the stage."), h("p", {}, "Create one reusable 3D product asset before the agent builds the story. It stays centre stage during playback; evidence images become smaller supporting views."))),
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
    if (event.phase !== "visual") return;
    if (type === "progress") { state.progress = event.percent; state.message = event.message; state.status = "generating"; draw(); }
    else refresh();
  });
}
