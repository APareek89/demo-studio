# Published Bundle render review — 24 September 2026

The empty-media renderer showed a broken-image box and “no picture” instead of reviewed terms. The before/after desktop and mobile screenshots reproduce and verify that correction. The replacement text card displays the exact reviewed narration and stays within the slide region; long text scrolls inside the card. Picture slides retain their existing renderer.

The after pass used the actual published `dm_7bbf10d0` Bundle from the isolated app on port 8910. The real player shell was loaded, its welcome buttons were left unclicked, and the production `renderSlide` module presented unchanged Bundle slides in that shell. Narration text in the conversation dock was set to the same published line for screenshot context. This is a renderer and geometry review, not a natural customer session or audio-timing test.

- **48 slide renders / 480 checks passed:** all 20 slides at 1440×1000 and 390×844; three slides with the walkthrough flag at its 390px fallback; five text slides at 390×400.
- Checked heading, picture, label and text-card bounds; asset loading; exact reviewed text; absent guessed anchors and broken-image placeholders; horizontal overflow; narrow walkthrough fallback.
- Zero page errors, POSTs, WebSockets or audio starts. All external requests were blocked; four Google Fonts CSS attempts were blocked, so screenshots use available fallback fonts. No provider/model calls, microphone capture, session saves or lead writes occurred.
- The before pass passed its 301 geometry-only checks but **failed visual review** because of the visible placeholder. It is retained as failure evidence, not a green release gate.
- Image choices remain reviewed illustrations. The earlier provider pixel audit timed out and retains its `rules_fallback` status; these captures do not claim model-certified visual proof.

The initial `after-receipt.json` and `manifest.json` are preserved. After the internal text-scroll and empty-media walkthrough corrections, a single fresh pass again completed **48 renders / 480 checks**: `final-receipt.json` records every render and final frontend hash, and `final-manifest.json` identifies the unchanged published Bundle and new `final-*.png` captures. This replaces the earlier renderer result for the latest source; the two passes are not added together as 960 checks. The final pass again had zero page errors, writes, WebSockets or audio starts; four external font attempts were blocked.

`interaction-regression-summary.json` links the separate failing and passing text Q&A return and stale legacy-image regressions. These renderer checks overlap the separate browser contracts and are not added to their suite total. Natural paid playback is recorded separately.

Selected evidence:

- `before-desktop-terms.png` / `after-desktop-terms.png`
- `before-mobile-terms.png` / `after-mobile-terms.png`
- `after-short-mobile-closing.png`
- `after-desktop-petrol.png`, `after-desktop-screen.png`, `after-mobile-screen.png`, `after-mobile-roof.png`
