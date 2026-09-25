# Codex — current project orientation

Refreshed 25 September 2026. This is the entrypoint for a fresh session; [the previous version](docs/history/context-before-master-2026-09-25/CODEX_INSTRUCTIONS.MD) preserves the old task list. Do not restart historical tasks or paid runs from that list.

## Read first

1. `Handoff.MD`: current code versus deployment, decisions, pending work and review-demo location.
2. `PRD.md` and `docs/DEMO_BUILD_AND_RUN.md`: current product behavior and ownership.
3. `docs/ARCHITECTURE_FLOW.md`, `docs/mermaid/*.mmd` and `docs/architecture-flow.html`: exact gates and diagrams.
4. Top of `Loop.MD`, then the entries relevant to the task in `Learning.MD` and `refine.MD`. Old QA receipts describe their own dated revision; they do not establish current release status.
5. `docs/context-index-2026-09-25.md` indexes the remaining markdown. Consult current QA reports first; historical briefs/design samples are not automatically current requirements.
6. Relevant source before editing: `server/app.py` (API), `server/graph.py` (build graph), `server/orchestrator.py` (staleness), `server/store.py` / `storage.py` (persistence), then the relevant stage/runtime module and UI.

## Current task boundary

Anand authorized integrating the completed branch into **master** on 25 September and refreshing these records. No further feature work or AWS deployment is part of that request. Continue implementation in the existing `codex/sales-trainer-flow` tree unless instructed otherwise; a fresh task must begin from the current tested release, not the obsolete `slides-v1` baseline. Preserve unrelated files. Do not infer permission to spend on providers or deploy from a Git merge.

Use best judgment for enhancements and fixes without repeated implementation-approval questions. Preserve the core workflow, existing agents/nodes, guardrails and no-build frontend. Latest explicit user decisions supersede old documents. If an unresolved product decision actually blocks work, record it under Questions from Codex and continue independent work.

## Non-negotiables

- Sources → Read (Understand → Coach → Plan → Author → Deck → FAQ) → six-card Align → Build (Voice → Bundle) → Rehearse. Rehearsal is explicit, outside Build.
- No citation, no claim; enforce source scope/conditions, immutable fact identities and pinned evidence. Unknowns never become facts automatically. Human edits/approvals and prior publications survive failures.
- Default three-minute supported narration is prepared automatically; Sources can choose one to five minutes. Actual complete recordings decide publication. No padding, duplicated speech, slowdown or word-estimate substitution.
- Pictures + source-backed on-slide tags accompany narration in both URL modes. The gallery experiment is superseded. Grounded illustrations need no fabricated anchor. The workbook's white slide/white dock and selected-template dark text supersede the older dark Marine sample.
- One locked runtime voice; audio events lead visual state. Browser owns interruption/return, graph owns grounded reasoning. Owner-supplied enabled URL domains are the runtime web boundary.
- `MOCK_LLM=1` must exercise the whole path without keys. Every free test uses isolated data and graph paths, cloud off and blocked outbound sockets. Explicit authorization is required for each paid run; the last paid QA is completed, not standing authorization.
- Never operate port8896 or mutate `dm_41513908`. Never `git clean`, `git stash -u`, delete intentional untracked files or bulk-add `output/`. Keys stay local/server-side; do not print `.env`.
- Review UI muted in Codex's browser or the isolated browser harness; do not control Anand's Chrome. Mock audio/recognition is not acoustic acceptance.
- Loop remains off. Finite authorized QA is allowed. No old worker agents are running; don't resume yesterday's assignments.

## Code map

- Build: `server/graph.py`, `orchestrator.py`, `agents/{understand,coach,plan,author,deck,faq,voice,bundle,rehearsal}.py`.
- Evidence/pictures: `server/{sources,knowledge,runtime_facts}.py`, `agents/{visuals,narration,plain_terms}.py`.
- Runtime: `server/{runtime_graph,runtime_tools,runtime_live,runtime_delivery,runtime_metrics}.py`; `agents/{pitch,summary}.py`.
- UI: `web/app.js`, `web/studio/*.js`, `web/player/{player,live-voice,walkthrough}.js`, `web/slide.js`, `web/{styles,player-ui}.css`. Walkthrough is a native-view compatibility adapter, not a gallery.
- Persistence: `server/{store,storage,cloud}.py`; folder-per-demo JSON/media plus graph SQLite. Backend selection/configuration must be inspected, not assumed to be AWS.
- Providers: `server/config.py`, `server/llm/*`. Text defaults Gemini → Claude → Runware; speech configuration/locking is separate. A configured key is not observed readiness.

## Verification and reporting

For application changes run the three core free gates (`evals/qa_deck.py`, `qa_accept.py`, `smoke_mock.py`) and relevant contracts. Current counts are399,24,and3smoke phases. `release_mock_contract.py` separately tests the real duration/approval path; broad core fixtures intentionally stub some publication/preparation checks. Match each claimed result to its receipt and exact source revision. Parse changed Python, `node --check` changed JavaScript, check whitespace and synchronize Mermaid source/viewer copies when flow changes.

Keep `Handoff.MD` a compact current snapshot; archive prior snapshots rather than append contradictory status forever. Record bugs and root causes in the existing `Learning.MD` (do not create a duplicate casing/plural file), checks in `Loop.MD`, decisions/questions in `refine.MD`, and behavior changes in PRD/architecture. A docs-only checkpoint must state which QA is retained and which was rerun.

Report what changed, how it was verified and material remaining limits. Distinguish local, GitHub and AWS status. Never turn a mechanical pass into a claim of semantic, acoustic or production-model quality. The paid QA's original failure and manually reviewed recovery must remain visible.
