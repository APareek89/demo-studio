// The guide's mascot — a warm, rounded character that "gives" the demo. No lip-sync: it breathes, blinks,
// glows while speaking, leans in while listening, and thinks with three dots. Pure inline SVG + CSS.
// Usage: const m = mascot({ size: 96, image: bundle.mascot }); m.el → node; m.set("speaking" | "listening" | "thinking" | "idle")

let cssInjected = false;
const CSS = `
.mascot{position:relative;display:inline-block;line-height:0;--m-blue:#1F5EFF;--m-sky:#9FC4FF;--m-deep:#0B2E8A;--m-amber:#D97706}
.mascot svg{width:100%;height:100%;overflow:visible}
.mascot .m-body{animation:m-breathe 3.6s ease-in-out infinite;transform-origin:50% 90%}
.mascot .m-eye{animation:m-blink 5.2s infinite;transform-origin:center}
.mascot .m-eye.r{animation-delay:.12s}
.mascot .m-wave{opacity:0;transform-origin:50% 50%}
.mascot.speaking .m-wave{animation:m-wave 1.1s ease-out infinite}
.mascot.speaking .m-wave.w2{animation-delay:.25s}.mascot.speaking .m-wave.w3{animation-delay:.5s}
.mascot.speaking .m-glow{opacity:.9;animation:m-glow 1.1s ease-in-out infinite}
.mascot .m-glow{opacity:0;transition:opacity .3s}
.mascot.listening .m-body{animation:m-lean 1.6s ease-in-out infinite}
.mascot.listening .m-ear{opacity:1;animation:m-ear 1.2s ease-out infinite}
.mascot .m-ear{opacity:0;transform-origin:center}
.mascot .m-dots{opacity:0}.mascot.thinking .m-dots{opacity:1}
.mascot.thinking .m-dot{animation:m-dot 1.2s infinite}.mascot.thinking .m-dot.d2{animation-delay:.2s}.mascot.thinking .m-dot.d3{animation-delay:.4s}
.mascot.thinking .m-mouth{d:path("M39 66 Q48 66 57 66")}
.mascot img{width:100%;height:100%;object-fit:contain;border-radius:50%;display:block}
.mascot.speaking img{box-shadow:0 0 0 6px rgba(31,94,255,.18),0 0 34px rgba(31,94,255,.35)}
.mascot.listening img{box-shadow:0 0 0 6px rgba(217,119,6,.18)}
@keyframes m-breathe{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-2px) scale(1.02,.985)}}
@keyframes m-blink{0%,92%,100%{transform:scaleY(1)}95%{transform:scaleY(.08)}}
@keyframes m-wave{0%{opacity:.85;transform:scale(.6)}100%{opacity:0;transform:scale(1.35)}}
@keyframes m-glow{0%,100%{opacity:.55}50%{opacity:1}}
@keyframes m-lean{0%,100%{transform:rotate(0)}50%{transform:rotate(-5deg) translateY(-1px)}}
@keyframes m-ear{0%{opacity:.9;transform:scale(.7)}100%{opacity:0;transform:scale(1.4)}}
@keyframes m-dot{0%,80%,100%{transform:translateY(0);opacity:.4}40%{transform:translateY(-5px);opacity:1}}
@media (prefers-reduced-motion:reduce){.mascot *{animation:none!important}}
`;

const SVG = `<svg viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Your guide">
  <defs>
    <radialGradient id="m-g" cx="38%" cy="32%" r="70%"><stop offset="0" stop-color="var(--m-sky)"/><stop offset=".55" stop-color="var(--m-blue)"/><stop offset="1" stop-color="var(--m-deep)"/></radialGradient>
    <radialGradient id="m-glowg" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="var(--m-blue)" stop-opacity=".45"/><stop offset="1" stop-color="var(--m-blue)" stop-opacity="0"/></radialGradient>
  </defs>
  <circle class="m-glow" cx="48" cy="52" r="46" fill="url(#m-glowg)"/>
  <g class="m-ear"><circle cx="48" cy="52" r="42" fill="none" stroke="var(--m-amber)" stroke-width="2"/></g>
  <g class="m-body">
    <path d="M48 10c19 0 32 14 32 33 0 18-12 33-32 37C28 76 16 61 16 43 16 24 29 10 48 10z" fill="url(#m-g)"/>
    <ellipse cx="34" cy="26" rx="9" ry="5" fill="#fff" opacity=".28" transform="rotate(-25 34 26)"/>
    <ellipse cx="30" cy="58" rx="6" ry="3.6" fill="#FF9DB0" opacity=".55"/><ellipse cx="66" cy="58" rx="6" ry="3.6" fill="#FF9DB0" opacity=".55"/>
    <g class="m-eye l"><ellipse cx="37" cy="46" rx="6.5" ry="8" fill="#fff"/><circle cx="38.5" cy="47.5" r="3.6" fill="#0B1730"/><circle cx="40" cy="45.5" r="1.2" fill="#fff"/></g>
    <g class="m-eye r"><ellipse cx="59" cy="46" rx="6.5" ry="8" fill="#fff"/><circle cx="60.5" cy="47.5" r="3.6" fill="#0B1730"/><circle cx="62" cy="45.5" r="1.2" fill="#fff"/></g>
    <path class="m-mouth" d="M39 64 Q48 72 57 64" fill="none" stroke="#0B1730" stroke-width="2.4" stroke-linecap="round"/>
    <path d="M22 44c-3-14 8-27 26-27s29 13 26 27" fill="none" stroke="#0B1730" stroke-width="3" stroke-linecap="round" opacity=".85"/>
    <rect x="16" y="40" width="8" height="13" rx="3.5" fill="#0B1730" opacity=".85"/><rect x="72" y="40" width="8" height="13" rx="3.5" fill="#0B1730" opacity=".85"/>
    <path d="M24 52c0 10 8 14 16 14" fill="none" stroke="#0B1730" stroke-width="2.4" stroke-linecap="round" opacity=".85"/><circle cx="41" cy="66.5" r="2.6" fill="#0B1730"/>
    <g class="m-dots"><circle class="m-dot d1" cx="76" cy="20" r="2.6" fill="var(--m-blue)"/><circle class="m-dot d2" cx="84" cy="16" r="3" fill="var(--m-blue)"/><circle class="m-dot d3" cx="92" cy="11" r="3.4" fill="var(--m-blue)"/></g>
  </g>
  <g class="m-wave w1"><path d="M44 72c4 2 6 6 6 10" fill="none" stroke="var(--m-blue)" stroke-width="2" stroke-linecap="round"/></g>
  <g class="m-wave w2"><path d="M46 70c7 3 10 9 10 15" fill="none" stroke="var(--m-blue)" stroke-width="2" stroke-linecap="round"/></g>
  <g class="m-wave w3"><path d="M48 68c10 4 14 12 14 20" fill="none" stroke="var(--m-blue)" stroke-width="2" stroke-linecap="round"/></g>
</svg>`;

export function mascot({ size = 96, image = null, title = "Your guide" } = {}) {
  if (!cssInjected) { const st = document.createElement("style"); st.textContent = CSS; document.head.appendChild(st); cssInjected = true; }
  const el = document.createElement("div");
  el.className = "mascot idle";
  el.style.width = el.style.height = size + "px";
  el.title = title;
  if (image) { const img = document.createElement("img"); img.src = image; img.alt = title; img.onerror = () => { el.innerHTML = SVG; }; el.appendChild(img); }
  else el.innerHTML = SVG;
  return { el, set(state) { el.className = "mascot " + (state || "idle"); } };
}
