// An original abstract guide mark. State changes are visual only; configured brand images take precedence.
// Usage: const m = mascot({ size: 96, image: bundle.mascot }); m.el → node; m.set("speaking" | "listening" | "thinking" | "idle")
let cssInjected = false;
let markId = 0;
const CSS = `
.mascot{position:relative;display:inline-block;flex:none;line-height:0;--m-blue:#0176d3;--m-sky:#90d0ff;--m-deep:#032d60}
.mascot svg{display:block;width:100%;height:100%;overflow:visible}
.mascot .m-core{transform-origin:48px 48px;transition:transform .3s ease}
.mascot .m-ring{opacity:0;transform-origin:48px 48px;transition:opacity .25s}
.mascot .m-bar{transform-box:fill-box;transform-origin:center;transition:opacity .25s}
.mascot.speaking .m-ring{opacity:.45;animation:m-orbit 2s ease-out infinite}
.mascot.speaking .m-bar{animation:m-voice 1s ease-in-out infinite}
.mascot.speaking .m-bar.b2{animation-delay:-.3s}.mascot.speaking .m-bar.b3{animation-delay:-.6s}
.mascot.listening .m-ring{opacity:.7;stroke:#0176d3;animation:m-orbit 2.4s ease-out infinite}
.mascot.listening .m-core{transform:scale(1.035)}
.mascot.thinking .m-bar{animation:m-think 1.4s ease-in-out infinite}
.mascot.thinking .m-bar.b2{animation-delay:.2s}.mascot.thinking .m-bar.b3{animation-delay:.4s}
.mascot img{width:100%;height:100%;object-fit:contain;border-radius:24%;display:block}
.mascot.speaking img,.mascot.listening img{box-shadow:0 0 0 4px #0176d314,0 0 0 8px #0176d308}
@keyframes m-orbit{0%{transform:scale(.93);opacity:.5}100%{transform:scale(1.13);opacity:0}}
@keyframes m-voice{0%,100%{transform:scaleY(.72)}50%{transform:scaleY(1.15)}}
@keyframes m-think{0%,100%{opacity:.38}50%{opacity:1}}
@media(prefers-reduced-motion:reduce){.mascot *{animation:none!important;transition:none!important}}
`;

function mark() {
  const id = `guide-mark-${++markId}`;
  return `<svg viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" focusable="false">
    <defs><linearGradient id="${id}" x1="16" y1="8" x2="82" y2="90" gradientUnits="userSpaceOnUse"><stop stop-color="#168cf0"/><stop offset=".52" stop-color="#0176d3"/><stop offset="1" stop-color="#032d60"/></linearGradient></defs>
    <rect class="m-ring" x="7" y="7" width="82" height="82" rx="28" fill="none" stroke="#57b8ff" stroke-width="1.5"/>
    <g class="m-core">
      <rect x="10" y="10" width="76" height="76" rx="25" fill="url(#${id})"/>
      <rect x="10.75" y="10.75" width="74.5" height="74.5" rx="24.25" fill="none" stroke="#fff" stroke-opacity=".2" stroke-width="1.5"/>
      <path d="M27 35.5c0-5.25 4.25-9.5 9.5-9.5h23c5.25 0 9.5 4.25 9.5 9.5v18c0 5.25-4.25 9.5-9.5 9.5H45l-12 9v-10c-3.5-1.4-6-4.8-6-8.5z" fill="#fff" fill-opacity=".1" stroke="#fff" stroke-opacity=".86" stroke-width="2.5" stroke-linejoin="round"/>
      <rect class="m-bar b1" x="37" y="40" width="4" height="11" rx="2" fill="#fff"/>
      <rect class="m-bar b2" x="46" y="35" width="4" height="21" rx="2" fill="#fff"/>
      <rect class="m-bar b3" x="55" y="40" width="4" height="11" rx="2" fill="#fff"/>
      <circle cx="73" cy="23" r="5" fill="#bce6ff"/><circle cx="73" cy="23" r="2" fill="#fff"/>
    </g>
  </svg>`;
}

export function mascot({ size = 96, image = null, title = "Your guide" } = {}) {
  if (!cssInjected) { const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st); cssInjected = true; }
  const el = document.createElement("div");
  el.className = "mascot idle";
  el.style.width = el.style.height = size + "px";
  el.title = title;
  el.setAttribute("role", "img"); el.setAttribute("aria-label", title);
  if (image) { const img = document.createElement("img"); img.src = image; img.alt = ""; img.onerror = () => { el.innerHTML = mark(); }; el.appendChild(img); }
  else el.innerHTML = mark();
  return { el, set(state) { el.className = "mascot " + (state || "idle"); } };
}
