// Compatibility for the optional walkthrough URL. The reviewed slide renderer
// owns pictures, feature tags and reveals; presentation never replaces them.
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const number = (value, fallback = 0) => Number.isFinite(Number(value)) ? Number(value) : fallback;

// Retained pure geometry helpers keep their native-pixel cap/clamp contract.
// The compatibility adapter below does not apply camera transforms.
export function walkthroughStopGeometry(callout, naturalWidth, renderedWidth) {
  const cap = Math.min(2.2, naturalWidth > 0 && renderedWidth > 0 ? naturalWidth / renderedWidth * 1.15 : 1);
  const part = callout?.part_box;
  const span = Math.max(number(part?.w), number(part?.h));
  const requested = part && span > 0 ? Math.max(1.15, 0.45 / span) : 1.5;
  const z = callout?.placement === 'overlay' && callout.anchor ? Math.min(requested, cap) : 1;
  // For z=1 the literal formula is negative: the effective pan range is zero.
  const lim = Math.max(0, 0.5 * (1 - 1 / z) - 0.01);
  return {z, cap, x: clamp(0.5 - number(callout?.anchor?.x, .5), -lim, lim),
    y: clamp(0.5 - number(callout?.anchor?.y, .5), -lim, lim), lim};
}
export function walkthroughFit(naturalWidth, naturalHeight, width, height) {
  const nw = Math.max(1, number(naturalWidth, width)), nh = Math.max(1, number(naturalHeight, height));
  const scale = Math.min(1, Math.max(1, width) / nw, Math.max(1, height) / nh);
  return {width: nw * scale, height: nh * scale, scale};
}

// The updated slide-first direction supersedes the gallery-first experiment.
// Keep existing player hooks and URLs compatible without hiding hero/closing
// pictures or delaying a narrated image/tag behind a walk, dive or rise.
// The earlier gallery remains in version history; no dormant animation runs.
export function createWalkthrough() {
  return {
    mount() {},
    wrap(_slide, view) { return view; },
    resize() {},
    freeze() {},
    pause() {},
    resume() {},
    reset() {},
    destroy() {},
  };
}
