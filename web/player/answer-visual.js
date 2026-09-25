// Resolve server-selected evidence against this visit's published presentation.
// The response may select an existing image; it cannot introduce a URL or pointer.
export function resolveAnswerVisual(bundle, slides, result) {
  const visual = result?.visual;
  if (!result?.answered || result.clarifying_question || visual?.kind !== "image") return null;
  if (!bundle.knowledge_snapshot_id || visual.snapshot_id !== bundle.knowledge_snapshot_id ||
      visual.demo_version !== bundle.version) return null;
  const slide = slides.find(item => item.id === result.slide_id);
  if (!slide) return null;
  const entries = Array.isArray(slide.media) && slide.media.length ? slide.media :
    [{ image_id: slide.image_id, image_url: slide.image_url }];
  const entry = entries.find(item => item.image_id && item.image_id === visual.ref && item.image_url === visual.url);
  if (!entry) return null;
  const callout = (slide.callouts || []).find(item => item.id === result.callout_id &&
    (item.image_id ? item.image_id === entry.image_id : entries[0] === entry));
  const candidate = visual.line_index;
  const lineIndex = Number.isInteger(candidate) && candidate >= 0 && candidate < (slide.lines || []).length
    ? candidate : Math.max(0, Number(entry.from_line) || 0);
  return { slide, imageId: entry.image_id, lineIndex, calloutId: callout?.id || null };
}
