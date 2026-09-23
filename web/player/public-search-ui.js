import { h } from "/web/api.js";

// These links describe already validated answer evidence. They grant no lookup permission.
function sourceUrl(value) {
  if (typeof value !== "string" || /[\u0000-\u0020\u007f]/.test(value)) return null;
  try { const url = new URL(value); return ["https:", "http:"].includes(url.protocol) && url.hostname && !url.username && !url.password ? url : null; } catch (_) { return null; }
}

// Preserve provider styling inside an opaque document. The detached template is
// inert; active elements and navigation controls never enter the application DOM.
function suggestionDocument(html) {
  const template = document.createElement("template");
  template.innerHTML = html;
  template.content.querySelectorAll("script,iframe,frame,object,embed,link,meta,base,form,input,button,textarea,select,video,audio,source").forEach(node => node.remove());
  for (const node of template.content.querySelectorAll("*")) {
    for (const attr of [...node.attributes]) {
      if (/^on/i.test(attr.name) || ["srcdoc", "action", "formaction", "ping", "srcset", "xlink:href"].includes(attr.name)) node.removeAttribute(attr.name);
    }
    if (node.hasAttribute("href")) {
      const url = node.tagName === "A" && sourceUrl(node.getAttribute("href"));
      if (url) { node.setAttribute("href", url.href); node.setAttribute("target", "_blank"); node.setAttribute("rel", "noopener noreferrer"); }
      else node.removeAttribute("href");
    }
    if (node.hasAttribute("src") && !(node.tagName === "IMG" && /^data:image\/(?:png|gif|jpeg|webp|svg\+xml)[;,]/i.test(node.getAttribute("src")))) node.removeAttribute("src");
  }
  return '<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; script-src \'none\'; style-src \'unsafe-inline\'; img-src data:; base-uri \'none\'; form-action \'none\'"><meta name="referrer" content="no-referrer"><style>html,body{margin:0;background:white;max-width:100%;overflow:auto}body{padding:4px;box-sizing:border-box}</style>' + template.innerHTML;
}

export function renderPublicSearch(result) {
  const searches = (result?.tool_results || []).filter(tool => tool.tool === "web_search" && !tool.error);
  if (!searches.length) return null;
  const cited = new Set([...(result.fact_ids || []), ...(result.condition_fact_ids || [])]);
  const urls = new Map();
  for (const fact of [...(result.facts || []), ...searches.flatMap(tool => tool.evidence || [])]) {
    if (!cited.has(fact.id) || fact.provenance !== "live_web") continue;
    const url = sourceUrl(fact.source?.ref);
    if (url && !urls.has(url.href)) urls.set(url.href, url);
  }
  const panel = h("section", { class: "pl-public-search", "aria-label": "Web search sources and suggestions" });
  if (urls.size) panel.append(h("div", { class: "pl-web-sources" }, h("span", {}, "Cited web sources: "), [...urls.values()].map(url => h("a", { href: url.href, target: "_blank", rel: "noopener noreferrer" }, url.hostname))));
  for (const search of searches) {
    const entry = search.search_entry_point;
    const html = typeof entry === "string" ? entry : entry?.rendered_content;
    if (typeof html !== "string" || !html.trim()) continue;
    panel.append(h("iframe", { class: "pl-search-suggestions", title: "Web search suggestions", sandbox: "allow-popups allow-popups-to-escape-sandbox", referrerpolicy: "no-referrer", srcdoc: suggestionDocument(html) }));
  }
  return panel.childElementCount ? panel : null;
}
