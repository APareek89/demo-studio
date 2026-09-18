# Professional UI evidence

Local UI-only delivery,2026-09-18,`codex/professional-ui`. See `docs/design/professional-ui.md` for scope, file map and limits.

- `baseline/`, `final/`: isolated free gates307/307 deck,24/24 acceptance,both smoke; final syntax63 Python/14 web JS.
- `ui-browser-5.json`, `.txt`, `.png`: actual browser execution of the five workspace cases using real UI modules and fake APIs.
- `player-browser-36.json`, `.txt`, `.png`: final actual browser execution of all36 player cases at1280px, with the shipped shared/player CSS and synthetic media/events.
- `player-browser-phone-attempt.*`: retained34/36 attempt. Two tests explicitly require a wide viewport and failed when the whole harness was390px. This is not the final result; do not discard or relabel it.
- `home-*`, `library-*`, `create-dialog.png`: actual workspace and card layouts. Totals and thumbnails are real local data.
- `studio-*`: Sources, Align, editor, Sessions/detail and read-only share at1440desktop and390phone. Earlier `studio-align-desktop.png` is1280.
- `observability-*`, `playground-*`: read-only reporting/testing surfaces, with unchanged metric semantics.
- `player-welcome-*`, `player-intake-desktop.png`, `player-stage-mobile.png`, `player-recap-mobile.png`: muted welcome, intake, cinematic browse/pause and recap on an isolated clone.
- `create-sources-check.txt`: real isolated HTTP creation landed in Sources.
- `review-server.json`: isolated mock store/server details. Actual demo data on8893 was not modified.

All playback was muted. Native microphone operation and acoustic quality are not established; the interactive intake review remained at Opening microphone, although the separate fake-speech browser contracts pass. No production writes, new Build, paid model calls, deployment or merge. Screenshots are direct browser captures.
