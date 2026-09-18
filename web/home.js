import { api, h } from "/web/api.js";
import { icon } from "/web/icons.js";
import { demoCard, demoImage, newDemoModal, studioPath } from "/web/demos.js";

export async function renderHome({ main, navigate }) {
  main.replaceChildren(h("div", { class: "page" }, h("div", { class: "page-loading", role: "status" }, "Opening your workspace…")));
  let demos;
  try { demos = await api.get("/api/demos"); }
  catch (e) { main.replaceChildren(h("div", { class: "page" }, h("div", { class: "empty" }, icon("alert-circle", { size: 32 }), h("h2", {}, "Your workspace couldn’t load"), h("p", {}, e.message), h("button", { class: "btn", onclick: () => renderHome({ main, navigate }) }, "Try again")))); return; }
  const ready = demos.filter(d => d.status === "ready");
  const preview = h("div", { class: "home-preview" },
    h("div", { class: "preview-head" }, h("span", { class: "preview-agent" }, icon("agent", { size: 21 })), h("div", {}, h("strong", {}, "Your product. Expertly presented."), h("span", {}, "An interactive experience, built from your knowledge."))),
    h("div", { class: "preview-product" }, icon("layers", { size: 80 })),
    h("div", { class: "preview-caption" }, h("span", { class: "preview-eq", "aria-hidden": "true" }, ...[1,2,3,4,5].map(n => h("i", { style: `--bar:${n}` }))), h("span", {}, ready.length ? ready[0].name : "Product knowledge, brought to life")),
    h("div", { class: "preview-path" }, ...[["file", "Your sources"], ["check-circle", "Your approval"], ["play", "Their discovery"]].map(([i,t]) => h("span", {}, icon(i, { size: 15 }), t))));
  if (ready.length) demoImage(ready[0]).then(src => { if (src && !/\.(mp4|webm|mov)(\?|$)/i.test(src)) { const img = h("img", { src, alt: ready[0].name, onerror: () => img.remove() }); preview.querySelector(".preview-product").replaceChildren(img); } }).catch(() => {});
  const metric = (name, count, i, sub) => h("div", { class: "workspace-stat" }, h("span", { class: "stat-icon" }, icon(i)), h("div", {}, h("div", { class: "stat-value" }, String(count)), h("div", { class: "stat-name" }, name), h("div", { class: "stat-sub" }, sub)));
  const page = h("div", { class: "page home-page" },
    h("div", { class: "home-welcome" }, h("span", { class: "eyebrow" }, "YOUR DEMO WORKSPACE"), h("span", { class: "home-date" }, new Date().toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" }))),
    h("section", { class: "home-hero" }, h("div", { class: "home-hero-copy" }, h("div", { class: "hero-tag" }, icon("sparkles", { size: 15 }), "A better way to experience products"), h("h1", {}, "Bring your product", h("br"), h("span", {}, "story to life.")), h("p", {}, "Turn your product knowledge into guided demos that welcome questions and help customers explore what matters."), h("div", { class: "hero-actions" }, h("button", { class: "btn primary", onclick: () => newDemoModal(navigate) }, icon("plus", { size: 19 }), "Create a demo"), h("a", { class: "btn", href: "#/demos" }, "Explore your demos", icon("arrow-right", { size: 17 }))), h("div", { class: "hero-assurance" }, icon("shield", { size: 16 }), "Your knowledge. Your review. Your customer experience.")), preview),
    h("section", { class: "workspace-stats", "aria-label": "Workspace overview" }, metric("Total demos", demos.length, "layers", "In your workspace"), metric("Ready to present", ready.length, "play", "Built and ready to explore"), metric("In progress", demos.length - ready.length, "edit", "From sources to rehearsal"), metric("Demo sessions", demos.reduce((s,d) => s + (d.sessions || 0), 0), "users", "Recorded conversations")),
    h("section", { class: "home-recent" }, h("div", { class: "section-heading" }, h("div", {}, h("h2", {}, demos.length ? "Pick up where you left off" : "Build your first product experience"), h("p", {}, demos.length ? "Your most recently updated demos, all in one place." : "A clear path from product material to a customer conversation.")), demos.length ? h("a", { class: "text-link", href: "#/demos" }, "View all demos", icon("arrow-right", { size: 16 })) : null), demos.length ? h("div", { class: "demo-grid home-grid" }, ...demos.slice(0,3).map(d => demoCard(d, navigate, () => renderHome({ main, navigate }), { compact: true }))) : null),
    h("section", { class: "home-workflow" }, ...[
      ["01", "file", "Start with what you know", "Add your product website, documents and images.", "Add product sources", () => newDemoModal(navigate)],
      ["02", "shield", "Make it yours", "Review the facts, refine the story and choose your voice.", "Open your studio", () => navigate(demos.length ? studioPath(demos[0]) : "#/demos")],
      ["03", "message", "Let the conversation begin", "Rehearse the experience and review what customers ask.", "Browse your demos", () => navigate("#/demos")],
    ].map(([n,i,title,body,label,action]) => h("article", { class: "workflow-item" }, h("div", { class: "workflow-top" }, h("span", { class: "section-icon" }, icon(i, { size: 24 })), h("span", {}, n)), h("h3", {}, title), h("p", {}, body), h("button", { class: "text-link", onclick: action }, label, icon("arrow-right", { size: 15 }))))),
    h("footer", { class: "home-footer" }, h("span", {}, "Demo Studio"), h("span", {}, "Thoughtful demos. Better conversations.")));
  main.replaceChildren(page);
}
