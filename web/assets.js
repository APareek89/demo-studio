import { api, h, toast, fmtSize, fmtTime } from "/web/api.js";

export async function renderAssets({ main, navigate }) {
  let assets = await api.get("/api/assets");
  const demos = await api.get("/api/demos");
  const draw = () => {
    const page = h("div", { class: "page assets-page" },
      h("div", { class: "page-head" }, h("div", {}, h("div", { class: "eyebrow" }, "Reusable library"), h("h1", {}, "My Assets")), h("button", { class: "btn primary", onclick: () => navigate("#/studio") }, "+ Build an asset")),
      assets.length ? h("div", { class: "asset-grid" }, ...assets.map((asset) => assetCard(asset))) : h("div", { class: "empty" }, "No approved 3D assets yet. Add a Demo Visual to any demo, review it, then approve it here."));
    main.replaceChildren(page);
  };
  function viewerModal(asset) {
    const bg = h("div", { class: "modal-bg asset-modal", onclick: (e) => { if (e.target === bg) bg.remove(); } },
      h("div", { class: "asset-viewer-modal" }, h("div", { class: "viewer-head" }, h("div", {}, h("div", { class: "eyebrow" }, asset.demo_name), h("h2", {}, asset.product?.name || asset.demo_name)), h("button", { class: "icon-btn", onclick: () => bg.remove() }, "✕")), h("model-viewer", { src: asset.glb_url, poster: asset.preview_url || "", "camera-controls": true, "auto-rotate": true, "shadow-intensity": "1", "environment-image": "neutral", alt: `3D asset for ${asset.demo_name}` })));
    document.body.appendChild(bg);
  }
  function useModal(asset) {
    const choices = demos.filter((d) => d.id !== asset.demo_id);
    const select = h("select", {}, ...choices.map((d) => h("option", { value: d.id }, d.name)));
    const bg = h("div", { class: "modal-bg", onclick: (e) => { if (e.target === bg) bg.remove(); } }, h("div", { class: "modal" }, h("h2", {}, "Use in another demo"), h("p", { class: "muted" }, "A private copy is attached to the selected demo. Its existing approved asset, if any, is replaced."), choices.length ? h("div", { class: "field" }, h("label", {}, "Demo"), select) : h("div", { class: "empty small" }, "Create another demo first."), h("div", { class: "actions" }, h("button", { class: "btn ghost", onclick: () => bg.remove() }, "Cancel"), choices.length ? h("button", { class: "btn primary", onclick: async () => { try { await api.post(`/api/assets/${asset.demo_id}/use`, { target_demo_id: select.value }); toast("Asset attached to demo"); bg.remove(); } catch (e) { toast(e.message, true); } } }, "Use asset") : null)));
    document.body.appendChild(bg);
  }
  function assetCard(asset) {
    return h("article", { class: "asset-card" },
      h("button", { class: "asset-preview", onclick: () => viewerModal(asset), "aria-label": `Open 3D asset for ${asset.demo_name}` }, h("model-viewer", { src: asset.glb_url, poster: asset.preview_url || "", "auto-rotate": true, "interaction-prompt": "none", alt: "" }), h("span", {}, "Open 3D")),
      h("div", { class: "asset-body" }, h("div", { class: "eyebrow" }, asset.product?.category || "3D product asset"), h("h3", {}, asset.product?.name || asset.demo_name), h("p", { class: "asset-source" }, `From ${asset.demo_name} · attempt ${asset.attempt || "imported"}`),
        h("div", { class: "asset-stats" }, h("span", {}, `${asset.real_count || 0} real`), h("span", {}, `${asset.generated_count || 0} AI`), h("span", {}, fmtSize(asset.size || 0)), h("span", {}, fmtTime(asset.created_at))),
        h("div", { class: "asset-actions" }, h("button", { class: "btn sm primary", onclick: () => viewerModal(asset) }, "View"), h("a", { class: "btn sm", href: asset.glb_url, download: `${asset.demo_name || "asset"}.glb` }, "Download"), h("button", { class: "btn sm", onclick: () => useModal(asset) }, "Use elsewhere"), h("button", { class: "btn sm ghost danger", onclick: async () => { if (!confirm(`Delete the approved 3D asset for “${asset.demo_name}”? Source views remain.`)) return; try { await api.del(`/api/assets/${asset.demo_id}`); assets = assets.filter((x) => x.demo_id !== asset.demo_id); draw(); toast("Asset deleted"); } catch (e) { toast(e.message, true); } } }, "Delete"))));
  }
  draw();
}
