# Default gallery template — 25 September 2026

The approved gallery is integrated into the app’s middle slide area. Fresh and existing demos use it automatically after reload. Top navigation, bottom articulation text, microphone, chat/actions, script, recordings, review workflow, evidence rules and measured narration gate are preserved. No server agent/node, prompt, schema, dependency or provider is added.

Source change: `web/player/walkthrough.js` owns picture/gallery/focus presentation and trusted feature pointers; `web/player/player.js` awaits preparation before its existing audio call; scoped rules in `web/player-ui.css` style only the middle area. Both same-line source pictures remain visible with selectable focus and exact labels. Illustrations retain their own disclosure and no invented pointer. `hero_open`/`hero_close`, intentionally picture-free slides and asset-failure fallback retain native rendering; `presentation=native` is a diagnostic opt-out. Align keeps its native editing renderer.

## Verification

Core gates: qa_deck399/399, qa_accept24/24, smoke3/3 (Read, Build, on-demand rehearsal). Full mock release28/28:194.22seconds measured synthetic narration with the real publication guard, all reviews, runtime question and saved session. Noise31/31, live voice96/96. Ten focused player/native contracts143/143: fundamental10, listen16, HTTP6, customer sites19, focus21, priority11, media7, native fallback/geometry18, runtime recovery17 and session save18. New image-load/interaction contract14/14.

Browser results: actual-player gallery312/312, final targeted preparation-click/scroll12/12, existing player87/87. Syntax/structure/whitespace17/17 includes9/9 Mermaid source/viewer copies. Individual assertions are in the adjacent JSON receipts. They exercise the actual mountPlayer: default gallery, compatible URL/native opt-out, exact source pictures/text/audio, before-audio readiness, two-image ownership, caption-only/no false pointers, Pause/question/Stop/restart, reduced motion and desktop/phone bounds. The actual published CRETA fixture is read-only. Original and current shell geometry are compared at1440×960 and390×844; top navbar captures are pixel-identical and bottom structure/font/spacing remain unchanged. Raster differences from pulsing native status/shadows are distinguished from geometry.

All gates use mock providers and isolated temporary data/SQLite, cloud sync off and blocked outbound network. Browser harnesses permit only their own static loopback server and deny microphone/WebSockets/provider requests. The full mock journey’s audio is silent measured WAV fixtures; gallery checks use deterministic speech events. Neither proves new paid model output, actual voice quality or physical TV/cup/throat rejection. The existing real-provider builder is checked read-only, never used to spend on a test build.

## Failures retained and corrected

The pre-change native browser baseline is85/87. Small phone evidence text is now at least12px; the overflow fixture uses four labels because three intentionally wrap. The old gallery-no-op assertion is replaced with default/compatibility/native readiness and exact playback checks. A cold-image personalized-label test now waits for the real image event before asserting the same content/scope. No historical receipt is rewritten.

Early harness issues are retained: an empty CRETA route before opening completion, `/tmp` versus `/private/tmp` resolution producing asset404s, and an initial wrong import path for the core launcher. Final checks require a nonempty route, decoded pictures, every expected caption and successful media responses; empty arrays cannot pass.

Independent review found and fixed stale image completion moving paused content, immediate Q&A image failures hiding native fallback, two simultaneous pictures losing evidence, local feature clicks cancelling awaited narration, stale labels during inset load and missing secondary illustration disclosure. Current labels scroll only inside their own box; pointers track that scroll and hide if their label leaves view. See [twelve-category FMEA](FMEA.md) and Learning.MD. No new unresolved P0/P1 or product question remains.

## Screenshots

- [Gallery walk — desktop](screenshots/creta-gallery-entry-1440.png) and [phone](screenshots/creta-gallery-entry-390.png).
- [Two-picture feature focus — desktop](screenshots/creta-focused-1440.png) and [phone](screenshots/creta-focused-390.png).
- [Trusted-anchor pointer fixture](screenshots/gallery-1440-line0.png). CRETA’s illustrated examples retain their disclosure instead of receiving an invented pointer.

## App and release

[Open the app to build a fresh demo](http://127.0.0.1:8910/#/home). Read-only health returned200; the three changed frontend files match the checkout byte-for-byte. The app uses existing isolated local storage under `/tmp/demo-runtime-final-20260924`, with real configured providers available when Anand chooses Build. Keep this server running; no special gallery URL flag is needed. Temporary demo storage is not a durable backup.

Anand explicitly authorized commitment to master/GitHub. Integration includes the preceding local noise/prototype commit `eacbb57`, plus this template change and current handoff/learning records, by fast-forward from `cf33be2`; the working tree stays on `codex/sales-trainer-flow`. After the release commit, local `master`, current `HEAD` and GitHub `refs/heads/master` are checked for identity. The exact commit is supplied in the completion message and is reproducible with `git log -1 master` and `git ls-remote origin refs/heads/master` (the release commit cannot embed its own hash).

**AWS is unchanged.** No paid calls, protected demo writes, port8896 operations, branch checkout, stash/clean or unrelated untracked-file deletion. Historical preview8911 remains a separate reference; app8910 is the fresh-build link.
