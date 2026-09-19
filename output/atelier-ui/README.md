# Atelier UI verification — 19 September 2026

Anand chose B Atelier with no UX/functionality changes. App changes are limited to four CSS files, against `47ac11b`. [Design guide](../../docs/design/atelier-ui.md) · [Pending work](../../docs/pending-tasks-2026-09-19.md).

- `baseline/`: free deck 307/307, acceptance 24/24, both smoke runs and the old home screenshot.
- `final/`: the same gates after all contrast corrections; 39 server/API Python and 14 JavaScript syntax checks; scope/CSS declaration/contrast audit and stylesheet hashes. Each gate uses isolated mock data and graph stores with cloud off.
- `workspace-browser.txt`: actual ES-module/DOM harness,5/5. `player-browser.txt`:36/36, including interrupt/return/consent and wide/narrow slide geometry. Run at1440px with fake APIs and media. These ran before final colour-only contrast corrections; the final declaration audit confirms unchanged layout/behaviour.
- `screenshots/`: actual desktop 1440×1000 and phone 390×844 UI. Home/library/Sources/Align/Visuals review/Observability use real app read-only views on 8893. Phone adds Rehearse/Sessions/share/Playground and create dialog. Customer welcome/player/conversation/recap use isolated mock 8894. All review playback is muted; captions/transcripts provide spoken context.
- `mobile-review.json`: nine actual read-only phone route measurements, all document width 390. The existing share key is intentionally omitted. Desktop and phone screenshot filenames identify each surface.

Phone create dialog closes with Escape and restores focus to New demo. Mock browse → pause → conversation → Stop → recap → Done remains usable. No provider call, Read, Build, lead submission or real customer session was performed. No demo source, registry, approval or bundle was edited. Screenshots reflect the existing real workspace counts rather than prototype sample data.

Visual review and synthetic contracts do not prove native microphone/STT behaviour, acoustic naturalness, live provider latency, full accessibility compliance or every possible content length. The earlier Opening microphone observation and functional issues remain in the pending list. No merge/deployment was performed.
