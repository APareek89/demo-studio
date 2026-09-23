# WP11 implementation receipt — 23 September 2026

Implemented on `codex/sales-trainer-flow`, after WP10 `da76db5`, as one `WP11:` package. Read answers only uploaded FAQ questions; empty Asked and answered auto-approves with the specified note. Runtime v1/live reuse clean snapshot-bound answers before reasoning, with scope/date/grounding checks and exact published voice/persona/language audio. Customer unknowns retain identity, counts and review state across Read; Coach exposes the gaps. Rejection is permanent, edits remain verbatim, and rehearsal runs only from its button.

**Approved finishing decisions:** Marine with numbered image anchors and an evidence rail; Marine/Sage/Graphite selection within the existing Visuals approval. Search the public web immediately when approved evidence cannot answer, customer-selected sites first, with cited turn-local evidence and existing tool limits. Default narration extends beyond three proof stops and publication requires at least 180 seconds of readable recorded speech; film, intake and Q&A do not count. Explicit shorter tours, refinements, skips and exits remain available. Raw microphone spikes/VAD no longer interrupt without recognized words. Citation-held facts have bounded retry and explicit batch owner restore; unresolved conflicts/manual exclusions remain held. Align/Rehearse layout and fixed white player dock are verified.



## Gates

- `evals/qa_deck.py`: **365/365**.
- `evals/qa_accept.py`: **24/24**.
- `evals/smoke_mock.py`: **both phases + on-demand rehearsal**.
- `evals/faq_cache_contract.py`: **27/27**.
- `evals/faq_scope_contract.py`: **19/19**.
- `evals/faq_review_contract.py`: **42/42**.
- `evals/faq_plain_language_contract.py`: **21/21**.
- `evals/cached_plain_language_contract.py`: **9/9**.
- `evals/build_hardening_contract.py`: **28/28**.
- `evals/coach_contract.py`: **26/26**.
- `evals/coach_align_contract.py`: **21/21**.
- `evals/plan_playbook_contract.py`: **19/19**.
- `evals/generation_contract.py`: **58/58**.
- `evals/align_review_contract.py`: **51/51**.
- `evals/knowledge_contract.py`: **60/60**.
- `evals/source_contract.py`: **39/39**.
- `evals/fact_identity_contract.py`: **17/17**.
- `evals/fact_retry_contract.py`: **12/12**.
- `evals/voice_lock_contract.py`: **27/27**.
- `evals/runtime_graph_contract.py`: **130/130**.
- `evals/runtime_repair_contract.py`: **106/106**.
- `evals/runtime_customer_sites_contract.py`: **20/20**.
- `evals/runtime_plain_language_contract.py`: **24/24**.
- `evals/runtime_web_search_contract.py`: **34/34**.
- `evals/runtime_tools_replay_contract.py`: **20/20**.
- `evals/runtime_delivery_contract.py`: **27/27**.
- `evals/runtime_operational_failure_contract.py`: **13/13**.
- `evals/runtime_calculation_deadline_contract.py`: **17/17**.
- `evals/live_transport_contract.py`: **24/24**.
- `evals/sarvam_stream_contract.py`: **17/17**.
- `evals/runtime_conversation_contract.py`: **18/18**.
- `evals/session_input_mode_contract.py`: **8/8**.
- `evals/runtime_metrics_contract.py`: **19/19**.
- `evals/deck_media_contract.py`: **45/45**.
- `evals/deck_media_align_contract.py`: **15/15**.
- `evals/speech_style_contract.py`: **30/30**.
- `evals/narrative_roles_contract.py`: **14/14**.
- `evals/visual_theme_contract.py`: **12/12**.
- `evals/minimum_narration_contract.py`: **25/25**.
- `evals/pitch_fundamental_contract.py`: **12/12**.
- `evals/pitch_grounding_contract.py`: **47/47**.
- `evals/pitch_priority_revision_contract.py`: **7/7**.
- `evals/pitch_delivery_contract.py`: **18/18**.
- `evals/qa_policy_contract.py`: **12/12**.
- `evals/align_progress_contract.mjs`: **9/9**.
- `evals/align_timing_contract.cjs`: **11/11**.
- `evals/coach_align_ui_contract.cjs`: **9/9**.
- `evals/live_voice_contract.mjs`: **74/74**.
- `evals/player_customer_sites_contract.cjs`: **19/19**.
- `evals/player_focus_contract.cjs`: **21/21**.
- `evals/player_fundamental_contract.cjs`: **10/10**.
- `evals/player_listen_contract.cjs`: **16/16**.
- `evals/player_media_contract.cjs`: **7/7**.
- `evals/player_priority_revision_contract.cjs`: **11/11**.
- `evals/readiness_ui_contract.mjs`: **5/5**.
- `evals/sse_client_contract.mjs`: **4/4**.
- `evals/player_contract.html`: **76/76**.
- `evals/ui_layout_contract.py`: **103/103**.
- `evals/public_search_ui_contract.py`: **30/30**.

## Verification limits and protected paths

All backend checks used `MOCK_LLM=1`, isolated data/graph storage and blocked outbound sockets; recorded outbound attempts were zero. Browser runs used an isolated headless profile, muted audio, synthetic providers and blocked external requests. No paid Read, TTS, public-web lookup or physical microphone acceptance was performed. Loop remains off.

The deliberately short generic fixtures in `qa_deck.py`, `smoke_mock.py`, `align_review_contract.py` and `deck_media_contract.py` supply a clearly labelled synthetic duration at their bundle-assembly boundary. The actual publication gate is tested separately in `minimum_narration_contract.py` with distinct cited passages, readable WAV recordings, short/missing/corrupt clips and unchanged prior bundle/snapshot/version on rejection. There is no production mock bypass. `visual_theme_contract.py` also publishes the real recorded-duration fixture.

The approved Marine layout was checked at 1440, 850 and 390 px, including all three palettes. The latest non-protected CRETA slides sl04/sl08 and the authorized 854×480 Downloads video were inspected without altering source data. The video plays muted at desktop/390 px with only the film and Skip visible, 16 px apart. Mock/visual checks do not establish live prose quality, acoustic recognition or public-site availability.

Protected-path comparison covers 7,766 files. All protected demo files are byte-identical, with no additions or removals. One pre-existing server log, `output/deploy-2026-09-23/local-server-final.log`, changed during concurrent activity (17:28 modification time, ordinary API/voice-list GETs). This implementation did not write or restore that log or operate port 8896. The whole output tree is therefore not claimed unchanged.

## Pending work

Selective Align rebuild routing remains proposed in Handoff.MD, as requested. No unanswered WP11 design decisions remain. Published real demos were not rebuilt or bulk-restored.

## Files changed

- `Handoff.MD`
- `Learning.MD`
- `Loop.MD`
- `PRD.md`
- `docs/ARCHITECTURE_FLOW.md`
- `docs/DEMO_BUILD_AND_RUN.md`
- `docs/architecture-flow.html`
- `docs/core-flow-explained-2026-09-23.md`
- `docs/design/wp11-samples/graphite.html`
- `docs/design/wp11-samples/marine.html`
- `docs/design/wp11-samples/sage.html`
- `docs/mermaid/00-workflow.mmd`
- `docs/mermaid/01-master.mmd`
- `docs/mermaid/02-understand.mmd`
- `docs/mermaid/03-align.mmd`
- `docs/mermaid/04-build.mmd`
- `docs/mermaid/05-runtime.mmd`
- `docs/mermaid/08-runtime-graph.mmd`
- `docs/wp11-implementation-report-2026-09-23.md`
- `evals/align_review_contract.py`
- `evals/align_timing_contract.cjs`
- `evals/build_hardening_contract.py`
- `evals/cached_plain_language_contract.py`
- `evals/coach_align_contract.py`
- `evals/coach_contract.py`
- `evals/deck_media_contract.py`
- `evals/fact_retry_contract.py`
- `evals/faq_cache_contract.py`
- `evals/faq_review_contract.py`
- `evals/faq_scope_contract.py`
- `evals/generation_contract.py`
- `evals/live_transport_contract.py`
- `evals/live_voice_contract.mjs`
- `evals/minimum_narration_contract.py`
- `evals/narrative_roles_contract.py`
- `evals/pitch_delivery_contract.py`
- `evals/pitch_priority_revision_contract.py`
- `evals/plan_playbook_contract.py`
- `evals/player_contract.html`
- `evals/player_listen_contract.cjs`
- `evals/player_priority_revision_contract.cjs`
- `evals/public_search_ui_contract.py`
- `evals/qa_deck.py`
- `evals/runtime_calculation_deadline_contract.py`
- `evals/runtime_customer_sites_contract.py`
- `evals/runtime_delivery_contract.py`
- `evals/runtime_graph_contract.py`
- `evals/runtime_web_search_contract.py`
- `evals/smoke_mock.py`
- `evals/source_contract.py`
- `evals/ui_layout_contract.py`
- `evals/visual_theme_contract.py`
- `refine.MD`
- `server/agents/align.py`
- `server/agents/author.py`
- `server/agents/bundle.py`
- `server/agents/coach.py`
- `server/agents/faq.py`
- `server/agents/narration.py`
- `server/agents/pitch.py`
- `server/agents/plan.py`
- `server/agents/qa.py`
- `server/agents/rehearsal.py`
- `server/agents/understand.py`
- `server/agents/voice.py`
- `server/app.py`
- `server/graph.py`
- `server/knowledge.py`
- `server/orchestrator.py`
- `server/runtime_delivery.py`
- `server/runtime_graph.py`
- `server/runtime_live.py`
- `server/runtime_state.py`
- `server/runtime_tools.py`
- `server/store.py`
- `web/player-ui.css`
- `web/player/live-voice.js`
- `web/player/player.js`
- `web/player/public-search-ui.js`
- `web/slide.js`
- `web/studio-ui.css`
- `web/studio/align.js`
- `web/studio/rehearse.js`
- `web/styles.css`
