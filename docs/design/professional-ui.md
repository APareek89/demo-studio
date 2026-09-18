# Professional UI — 2026-09-18

Anand requested a professional blue-and-white interface across the whole app, including a home page, a better agent mark and better demo cards. This is the current UI on `codex/professional-ui`. The visual reference is [Salesforce's website](https://www.salesforce.com/); the logo, agent mark and components are original Demo Studio assets.

**Decision:** use one shared design system, Inter typography, restrained blue accents, white surfaces and navy headings. Keep the existing plain ES modules and CSS. Keep Sources → Align → Rehearse, all six approvals, runtime question handling, source validation, speech, provider selection and data storage unchanged. The previous cinematic slide composition remains; its accent and dark-stage palette now match the app.

**Rejected:** independent cosmetic skins for each page, a framework migration, and implementing calculator or live-web runtime tools during this pass. Those would fragment the product or expand the authorized scope.

## Design system

- Primary action: `#0176d3`; headings: `#032d60`; body: `#16325c`; muted text: `#596c85`; workspace: `#f4f7fc`; surfaces: white.
- Inter for interface and display text; IBM Plex Mono only for technical values. System fonts are the fallback. Google Fonts was already used by the app; no package or service dependency was added.
- Shared buttons, fields, focus outlines, status pills, cards, modals and navigation. Native SVG icons share a 24-unit coordinate system and consistent stroke weight.
- Restrained border, shadow and radius scale. Explicit reduced-motion rules. Layouts tested at desktop and 390px phone width.
- Product thumbnails come from each demo's existing bundle. Missing imagery gets a neutral icon. No invented results, stock product substitutes or simulated business metrics.

## Files to use

- `web/design-system.css`: tokens, global components, header, rail, home, library and responsive rules.
- `web/icons.js`, `web/brand.svg`: shared icons and application mark.
- `web/index.html`, `web/app.js`: fonts, stylesheet order, accessible navigation and the default `#/home` entry.
- `web/home.js`: real workspace totals, recent demos and entry points into existing actions.
- `web/demos.js`: searchable/filterable library, approved thumbnails and create dialog. Preview requests share an in-flight/result cache by demo/version/update time; a failed lookup can retry on a later visit.
- `web/studio-ui.css`, `web/studio/*.js`: Sources, Align, slide editor, Rehearse, Sessions and read-only share pages. Narrow Align uses one scroll column so review cards and the assistant both remain reachable.
- `web/player-ui.css`, `web/player/mascot.js`, presentation markup in `web/player/player.js`: original agent mark, welcome, intake, playback controls, conversation, recap and optional contact panel. Runtime state and event handlers remain unchanged.
- `web/insights-ui.css`, `web/observability.js`, `web/playground.js`: reporting and testing surfaces. Metric definitions, calculations and API actions remain unchanged.

Cascade order is `styles.css` → `design-system.css` → `studio-ui.css` → `insights-ui.css` → `player-ui.css`. The original layout rules remain the base; each new sheet owns a defined surface.

## Verification

Before and after free gates: **307/307 deck**, **24/24 acceptance**, and both smoke phases. Python compilation covers 63 repository files; JavaScript syntax covers all 14 web modules. No provider calls or real demo writes were required.

The actual browser player harness passes **36/36** using the shipped design-system and player styles, synthetic media/events and fake APIs. The new actual-module workspace harness passes **5/5**: preview reuse, transient failure recovery, version/update invalidation, single create submission → Sources, and View → fullscreen/playback. Run `.venv/bin/python evals/player_browser.py`, then open `/` or `/ui_contract.html` on port 8892.

Manual browser checks cover desktop and phone home/library/search, all Studio screens and the slide editor, session details/share, Observability, Playground, muted welcome/intake, cinematic browse mode and customer recap. All tested phone documents measure 390px without page overflow; wide data tables scroll inside their own panels. Escape closes the create dialog and restores focus. A real HTTP create against isolated mock port 8894 made `dm_740f03ae` and landed in Sources; no Read or Build followed.

Evidence is in `output/professional-ui/`. `baseline/` and `final/` contain gate records, `ui-browser-5.*` and `player-browser-36.*` contain browser results, and the PNGs show actual reviewed screens. A retained player run at 390px failed two explicitly wide geometry fixtures; the final run at 1280px passed all 36. The phone geometry fixtures also run inside that suite.

## Limits and follow-up

This is a local UI delivery, not a deployment or a new real demo build. The real Nexon bundle and its customer evidence remain unchanged. Paid usage for this pass is zero. Muted visual checks do not prove voice quality, native microphone behavior or runtime latency. During the isolated interactive intake review, the browser remained at “Opening microphone” and did not accept the submitted typed turn; the separate real-DOM harness passes typed intake and interruption cases. No microphone or runtime behavior was changed to work around that observation. Browse, pause, stop and recap were verified separately.

The existing several-second model response time and the earlier questions about calculator/live-web tools remain separate work. Those capabilities were not added by this UI pass.
