import { h } from '/web/api.js';
export function providerBadge(provider) {
  const labels = { runware:'Runware', pixelbin:'PixelBin', gemini:'Gemini', local:'Local', mock:'Mock' };
  const label = labels[String(provider || 'local').toLowerCase()] || 'Local';
  return h('span', { class:'pill media-provider', title:`Image provider: ${label}` }, label);
}
