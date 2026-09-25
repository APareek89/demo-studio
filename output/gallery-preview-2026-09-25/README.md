# CRETA guided gallery — visual preview

Open http://127.0.0.1:8911/ and press Start. Sound plays only after that click; the Sound button toggles it. Automated review uses `?mute=1`. This is a six-feature visual-flow excerpt, not a published full demo, live Q&A or a new Build.

Gallery walk → straighten the selected frame → enlarge the picture → focus a visible feature with a pointer and on-image text box → play its existing reviewed recording → return and move to the next frame. The chapter buttons, Previous/Next, Pause/Resume and Return to gallery let you inspect the sequence. Phone captions remain on the image and below the focus point. Reduced motion minimizes transitions without enlarging the photo.

Existing source: isolated CRETA `dm_7bbf10d0`, published v3, snapshot `kb_2679d87aeeb0ab06c7284862`. Six selected slides contain75.1seconds of existing narration, plus camera transitions. No new voice/provider calls. `preview.json` retains original line words, citations, source bundle hash and copied asset hashes. Pictures are illustrations; trim equipment is established by the existing cited narration, not by the pointer. Visible feature locations were checked manually against the actual padded photo bytes; prototype camera coordinates never write back to the demo.

This directory is standalone. It imports no app module, requests no microphone, opens no WebSocket, and writes no app/demo data. The source reference was read as HTML; browser access to its original local file was denied and not bypassed. The new prototype itself was reviewed in an isolated browser.

To launch:

```bash
cd /Users/macbook/Documents/demo-studio
python3 -m http.server 8911 --bind 127.0.0.1 --directory output/gallery-preview-2026-09-25
```

Resizing during narration pauses and refits the picture; Resume continues the same clip. Resizing during a camera move returns to the current gallery chapter; Play restarts that feature safely. The production app remains on8910 with its native slide renderer. No master or AWS release is part of this preview. Evidence: `docs/qa/noise-gallery-2026-09-25/README.md`.
