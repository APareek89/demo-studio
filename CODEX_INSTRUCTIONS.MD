# Codex — current project orientation

Refreshed 26 September 2026. This is the entrypoint for a fresh session; [the previous version](docs/history/context-before-master-2026-09-25/CODEX_INSTRUCTIONS.MD) preserves the old task list. Do not restart historical tasks or paid runs from that list.

Latest completed follow-up: shared-demo mobile fixes are on GitHub master and AWS. Running application3591fb7 has one explicit5543fe1 overlay for web/player-ui.css; source markers preserve that provenance. Default hosted LiveKit is retained. Handoff and the [dated mobile release receipt](docs/aws/release-mobile-2026-09-26.md) take precedence over historical releases below. Preserve Build/Align, agents/nodes, gallery design, source grounding and demo data. No new paid QA. Native WebKit Safari/CriOS profiles and Chromium were checked; a physical iPhone was unavailable. See [mobile evidence](docs/qa/mobile-runtime-2026-09-26/README.md).

## Read first

1. `Handoff.MD`: current code versus deployment, decisions, pending work and review-demo location.
2. `PRD.md` and `docs/DEMO_BUILD_AND_RUN.md`: current product behavior and ownership.
3. `docs/ARCHITECTURE_FLOW.md`, `docs/mermaid/*.mmd` and `docs/architecture-flow.html`: exact gates and diagrams.
4. Top of `Loop.MD`, then the entries relevant to the task in `Learning.MD` and `refine.MD`. Old QA receipts describe their own dated revision; they do not establish current release status.
5. `docs/context-index-2026-09-25.md` indexes the remaining markdown. Consult current QA reports first; historical briefs/design samples are not automatically current requirements.
6. Relevant source before editing: `server/app.py` (API), `server/graph.py` (build graph), `server/orchestrator.py` (staleness), `server/store.py` / `storage.py` (persistence), then the relevant stage/runtime module and UI.

Current release: `/opt/demo-studio-releases/20260926-mobile`, application3591fb7 plus5543fe1 CSS overlay, main cutover26September08:17:17UTC. Gesture-owned recorded playback, bounded audio resume, mobile gallery/drawer/selected-label geometry and short-screen welcome controls are deployed. Existing acknowledgements, URL-domain scope and hosted LiveKit remain. All4273 stored files survived the main cutover unchanged; the subsequent CSS replacement did not touch data or restart the app. [Release receipt](docs/aws/release-mobile-2026-09-26.md) owns checks, explicit source provenance and recovery. Later documentation-only commits do not change deployed bytes.

Previous task completed: Anand approved BMW and explicitly requested master/GitHub plus AWS for public feedback. Application `278c21d` and operator proxy `0f7e2be` are deployed; public BMW is `https://13-202-0-79.sslip.io/#/play/dm_29df0418`. See Handoff and `docs/aws/release-bmw-gallery-2026-09-25.md` for exact gates, backup and limits. The approved recordings/snapshot were copied, with local test history excluded; no new paid QA. Receipt-only commits do not change the running application SHA.

Preceding implementation: [gallery-template receipt](docs/qa/gallery-template-2026-09-25/README.md). Anand approved the standalone preview, then explicitly requested its integration into the middle slide area and commitment to master. Default playback now uses that gallery for picture-bearing content slides; the navbar and bottom conversation controls stay unchanged. The receipt records verification and Git publication; AWS remains separate. The earlier [noise/preview receipt](docs/qa/noise-gallery-2026-09-25/README.md) is historical evidence for `eacbb57`.

## Standing task boundary and prior authorization

Anand authorized integrating the approved gallery preview into the app’s **middle slide area only**, then committing the completed branch to **master/GitHub** on 25 September. This includes the preceding local noise fix in `eacbb57`. That preceding gallery request had no AWS deployment or paid QA. The subsequent BMW request authorizes its bounded real regeneration, source/script/visual review, recording and master publication; consult Handoff for its actual progress. Continue implementation in the existing `codex/sales-trainer-flow` tree unless instructed otherwise; a fresh task must begin from the current tested release, not the obsolete `slides-v1` baseline. Preserve unrelated files. Do not infer permission to spend on providers or deploy from a Git merge.

Use best judgment for enhancements and fixes without repeated implementation-approval questions. Preserve the core workflow, existing agents/nodes, guardrails and no-build frontend. Latest explicit user decisions supersede old documents. If an unresolved product decision actually blocks work, record it under Questions from Codex and continue independent work.

The later explicit AWS approval supersedes the preceding Git-only scope. Public player/runtime remain open; AWS editor/build/private records require the operator credentials stored privately at `/Users/macbook/.config/demo-studio/aws-admin.json`. Never print or commit that file, the AWS auth fragment, environment contents or private visit history. Caddy's tested route boundary is operational protection, not application-level tenant authorization or rate limiting.

## Non-negotiables

- Sources → Read (Understand → Coach → Plan → Author → Deck → FAQ) → six-card Align → Build (Voice → Bundle) → Rehearse. Rehearsal is explicit, outside Build.
- No citation, no claim; enforce source scope/conditions, immutable fact identities and pinned evidence. Unknowns never become facts automatically. Human edits/approvals and prior publications survive failures.
- Default three-minute supported narration is prepared automatically; Sources can choose one to five minutes. Actual complete recordings decide publication. No padding, duplicated speech, slowdown or word-estimate substitution.
- Default picture-bearing content slides use the approved gallery walk → enlarge → feature-focus presentation, including the compatible `presentation=walkthrough` URL. Pictures and reviewed labels are ready before their main narration starts. Native `hero_open`/`hero_close` (welcome/end heroes) and picture-free slides remain; `presentation=native` is a diagnostic opt-out. Gallery DOM and styles stay inside the middle slide: heading/footer, top navbar and white bottom conversation controls retain their existing structure and geometry. Only reviewed anchors may receive a feature pointer; illustrative or unanchored pictures keep factual captions without invented coordinates.
- One locked runtime voice; audio events lead visual state. Browser owns interruption/return, graph owns grounded reasoning. Owner-supplied enabled URL domains are the runtime web boundary.
- `MOCK_LLM=1` must exercise the whole path without keys. Every free test uses isolated data and graph paths, cloud off and blocked outbound sockets. Explicit authorization is required for each paid run; the current BMW regeneration is specifically authorized, and previous completed paid QA is not standing authorization.
- Never operate port8896 or mutate `dm_41513908`. Never `git clean`, `git stash -u`, delete intentional untracked files or bulk-add `output/`. Keys stay local/server-side; do not print `.env`.
- Review UI muted in Codex's browser or the isolated browser harness; do not control Anand's Chrome. Mock audio/recognition is not acoustic acceptance.
- Loop remains off. Finite authorized QA is allowed. No old worker agents are running; don't resume yesterday's assignments.

## Code map

- Build: `server/graph.py`, `orchestrator.py`, `agents/{understand,coach,plan,author,deck,faq,voice,bundle,rehearsal}.py`.
- Evidence/pictures: `server/{sources,knowledge,runtime_facts,runtime_visuals}.py`, `agents/{visuals,narration,plain_terms}.py`.
- Runtime: `server/{runtime_graph,runtime_tools,runtime_live,runtime_delivery,runtime_metrics}.py`; `agents/{pitch,summary}.py`.
- UI: `web/app.js`, `web/studio/*.js`, `web/player/{player,live-voice,walkthrough}.js`, `web/slide.js`, `web/{styles,player-ui}.css`. Walkthrough is the player-only middle-slide gallery adapter; Align retains the native renderer. `playLines` awaits its cancellable preparation before the existing speech call; the player still owns voice, route, checkpoints and interruptions.
- Persistence: `server/{store,storage,cloud}.py`; folder-per-demo JSON/media plus graph SQLite. Backend selection/configuration must be inspected, not assumed to be AWS.
- Providers: `server/config.py`, `server/llm/*`. Text defaults Gemini → Claude → Runware; speech configuration/locking is separate. A configured key is not observed readiness.

## Verification and reporting

For application changes run the three core free gates (`evals/qa_deck.py`, `qa_accept.py`, `smoke_mock.py`) and relevant contracts. Current counts are445,24,and3smoke phases. `release_mock_contract.py` separately tests the real duration/approval path; broad core fixtures intentionally stub some publication/preparation checks. Match each claimed result to its receipt and exact source revision. Parse changed Python, `node --check` changed JavaScript, check whitespace and synchronize Mermaid source/viewer copies when flow changes.

Keep `Handoff.MD` a compact current snapshot; archive prior snapshots rather than append contradictory status forever. Record bugs and root causes in the existing `Learning.MD` (do not create a duplicate casing/plural file), checks in `Loop.MD`, decisions/questions in `refine.MD`, and behavior changes in PRD/architecture. A docs-only checkpoint must state which QA is retained and which was rerun.

Report what changed, how it was verified and material remaining limits. Distinguish local, GitHub and AWS status. Never turn a mechanical pass into a claim of semantic, acoustic or production-model quality. The paid QA's original failure and manually reviewed recovery must remain visible.
