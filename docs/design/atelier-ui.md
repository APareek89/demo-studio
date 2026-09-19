# Atelier UI — 2026-09-19

Anand explicitly selected **B · Atelier** from the [design gallery](options-2026-09-18/index.html), with the requirement to preserve the app's UX and functionality. This integration applies Atelier's typography, palette and surface treatment to the existing app on `codex/atelier-ui`, based on `47ac11b`.

**Decision:** use editorial serif display headings, paper-white surfaces, navy primary actions, restrained blue accents, fine borders and flat panels. **Rejected:** adopting the prototype's page composition, navigation, controls or sample content. That would change the workflow beyond the approved visual scope.

## Design and ownership

Only four application files change:

- [web/design-system.css](../../web/design-system.css): shared tokens and components, navigation shell, Home and demo library.
- [web/studio-ui.css](../../web/studio-ui.css): Sources, Align, review/editor dialogs, Rehearse, Sessions and read-only share pages.
- [web/player-ui.css](../../web/player-ui.css): player chrome, welcome and intake, captions, controls, conversation, contact panel and recap.
- [web/insights-ui.css](../../web/insights-ui.css): Playground and Observability.

The shared palette is paper `#f8f9f6`, white `#fff`, soft blue `#eaf3f9`, ink `#082d4f`, navy `#08243c`, accent blue `#0879be`, muted text `#5e7180`, line `#dce3e5` and stronger line `#bfcdd3`. Primary buttons use navy; blue marks links and active states. Existing success, warning and error distinctions remain. The radius scale is 3px and decorative panel shadows are removed.

Display headings use the system stack `Georgia, "Times New Roman", serif`, generally at weight 400. Body text, form labels, controls and dense information retain the existing Inter/system sans stack. Technical values retain IBM Plex Mono. No font dependency, package, asset or network integration is added.

The stylesheet order remains `styles.css` → `design-system.css` → `studio-ui.css` → `insights-ui.css` → `player-ui.css`. The home preview's decorative −1° tilt is removed; this is a visual exception with no change to its content, controls or workflow.

## Preserved behavior

JavaScript, HTML, SVG, server/API code and the base `web/styles.css` are unchanged. Existing product images and icons remain; prototype sample data and assets are not imported.

Routes, navigation, control placement, grids, breakpoints, visibility states, docking and scroll containment remain. Sources → Align → Rehearse and all six approvals are unchanged. The shared cinematic slide renderer retains its native-image sizing, callout geometry and evidence placement. Runtime questions, interruptions, exact return points, audio events, citations, consent, session recording and provider selection retain their existing implementation.

## Verification and evidence

Evidence is in [output/atelier-ui](../../output/atelier-ui/), with the [final gate report](../../output/atelier-ui/final/summary.md), [application scope audit](../../output/atelier-ui/final/scope.json), [CSS audit](../../output/atelier-ui/final/css-audit.json) and [screenshots](../../output/atelier-ui/screenshots/).

- Before and after: deck **307/307**, acceptance **24/24**, both mock smoke phases passed. Final syntax checks passed for **39 Python files** and **14 JavaScript modules**.
- Actual browser contract runs at 1440px: [workspace **5/5**](../../output/atelier-ui/workspace-browser.txt) and [player **36/36**](../../output/atelier-ui/player-browser.txt). These exercise actual app modules with fake APIs and synthetic media/events; they do not establish live provider or microphone performance.
- Phone review at 390px covers Home, library, create dialog, Sources, Align, Rehearse, Sessions, share, player, conversation, recap, Playground and Observability. [Nine real read-only route measurements](../../output/atelier-ui/mobile-review.json) each report a 390px document width; the muted mock player, conversation and recap also fit. The screenshots folder records the reviewed surfaces.
- A targeted CSS audit confirms the four-file scope and preservation of layout/interaction declarations, except the accepted home-preview rotation removal. Reported contrast findings were corrected. This is not a full accessibility certification.

Playback review remains muted. No paid calls, real demo mutation, new build, merge or deployment is part of this pass. Acoustic quality, native microphone accuracy and live response latency are not validated by these checks.

## Still separate

The [12-item pending task list](../pending-tasks-2026-09-19.md) records the remaining work for sequencing. The [architecture guide](../ARCHITECTURE_FLOW.md) remains the reference for the actual agent workflow. Runtime calculator/live-web tools and their approach alignment, further conversation/TVS experience work, and the hardening tasks in [CODEX_INSTRUCTIONS.MD, Part 3](../../CODEX_INSTRUCTIONS.MD) remain outside this visual pass. Existing findings and open issues remain in the [Nexon issue log](../issues/2026-09-18-nexon.md) and [Handoff.MD](../../Handoff.MD). Historical latency measurements are not new Atelier UI KPIs.
