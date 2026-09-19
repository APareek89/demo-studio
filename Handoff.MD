# Handoff.MD — Demo Studio

## Current checkpoint — 19 September 2026

**Work is active following Anand’s “go”.** Branch `codex/creta-conversational-demo`. Approved runtime implementation and reviewed Creta demo exist; **real acceptance is still incomplete**. No push, merge or deployment. Use Codex’s in-app browser, keep playback muted, and leave Anand’s native Chrome untouched.

**Playable artifact:** Hyundai CRETA `dm_41513908`, corrective **v5**, snapshot `kb_5af02e3769b5c51a0b44f50e`, **181 approved facts**, all six cards approved. [Muted demo](http://127.0.0.1:8896/?mute=1&review=creta-runtime#/play/dm_41513908). Eleven official images; Atelier/cinematic presentation; Priya voice. Explore overview11.25s, main narration plus three check-ins131.5s before pauses/deeper detail. The historical static score13/20 remains below its rubric; rehearsal is stale, not a new pass.

**Source and media corrections:** v3 rejected conflicting/unsupportedF056/F048/F076/F126 and replacedF123 with explicit spare-wheelF246. V4 recorded only the short “Let me check that.” acknowledgement (1.365s). V5 replaced held/vague sunroof/camera assertions with exact manufacturer-matrixF247/F248, explicitly excluding E/EX. These are corrective publications beyond two authored iterations; no additional generated story. Existing narration/slides/media and previous snapshots are retained. Private audits: `output/creta-runtime-2026-09-19/{source-correction-v3,short-ack,source-fitment-v5}/`.

**Latest complete quality cohort:** on `2a07c75`/v3, third unchangedQA100 = **75 supported /18 partial /6 unhelpful /0 unsafe flagged /1 provider failure**. All-request HTTP text median2.353s,p956.953s; not audio. Earlier cohorts and all failed answers are preserved. A supported result can be an appropriate clarification or honest refusal; a transport success is not a semantic pass. The quality target remains≥95% useful supported answers for answerable questions and zero unsupported critical claims.

**Actual browser evidence:**20/20 controlled interruptions;16 active-audio samples, maximum253ms from injected onset receipt to local stop. Family intentionally exited after controls; commute and safety completed selected routes and recap. Safety remained12/13 because its ADAS answer failed: generic “variant conditions” became a nonexistent trim. Its679ms acknowledgement and2.585s decline audio are not useful-answer success. Earlier actual typed answers: EMI7.764s,ADAS4.944s. These small samples establish no reliable p95. Physical listening, echo and perceived warmth remain unverified under the muted-review constraint.

**Repairs being finalized:** generic trim-word parsing; one bounded composition repair with identical evidence/validator/language/profile and the same12-second deadline; narrow safe-limit preservation; material warranty/Echo conditions; better answer-passage lookup ranking. Player uses250ms acknowledgement grace and shortest compatible reviewed clip. Metrics separate answer/clarification/decline/legacy, with semantic quality reviewed independently. Final free checks and independent review precede a focused paid replay, then a separately reviewed100-case cohort if justified. Do not merge focused results into an older score.

**Local server:**8896 currently runs last committed `2a07c75` (PID68189, exec session80253); no autoreload. Restart after the repair commit with `MODEL_TIER=customer CLOUD_SYNC=0 STORAGE_BACKEND=local DEMO_STUDIO_GRAPH_DB=/Users/macbook/Documents/demo-studio/data/creta-runtime-graph.sqlite .venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8896`. Do not disturb8893. Published data is alreadyv5.

**Spend guards:** app estimate$6.2714 before next validation, not a provider invoice. Overall work ceiling$20. Browser cumulative counters23reasoning/30TTS, ceilings32/32; retain original shared baseline$2.8719, incremental ceiling$6,total$19.50. Prepared single ADAS probe may use one reasoning and one answerTTS after restart. Do not reset counters or silently expand a run.

## Decisions and invariants

- Anand approved the expanded [runtime plan](docs/plan-runtime-experience-2026-09-19.md) and using the official Creta PDFs/relevant images. Prior UI-only and no-runtime-streaming restrictions are historical.
- Keep Atelier and cinematic slides. Plain customer language, sourced feature-led opening, helpful cheerful persona and sparse confirmation questions; yes=continue/no=more detail. Real questions always wait.
- Build requires six reviewed approvals. Source changes allocate new assertion IDs, preserve historical meaning, invalidate affected approval and publish a new immutable snapshot. Human edits must not be silently regenerated.
- Uploaded sources win genuine same-scope conflicts; unreviewed contradictions remain visible. Original media defines vehicle identity. No invented trim/model-year/current-stock applicability or product benefits.
- Runtime uses an LLM over pinned approved evidence. Two tool rounds/four calls and at most one composition repair share12seconds. Calculator operands/basis are auditable; URL lookup uses customer-supplied public sources, with explicit attribution. Live evidence stays turn-scoped.
- Browser owns playback, question waits, interruption and exact return point. Capture starts only after initial customer permission. Separate planning/QA ownership rejects stale work. No lead submission without explicit choice and separate consent.
- Gemini→Claude→Runware is the text fallback chain; locked speech stays Priya. Claude credit failure and provider timeouts have occurred; configured credentials are not proof of readiness. Recorded cost is an estimate.
- Loop remains off. Authorized finite checks are allowed. No secrets in git, no deployment/push without authorization. Legacy TVS text repairs exist but its recordings/bundle are not rebuilt.

## Read next

[Build/run workflow and code map](docs/DEMO_BUILD_AND_RUN.md) · [acceptance and measured limits](docs/CRETA_ACCEPTANCE.md) · [issue log](docs/issues/2026-09-19-creta.md) · [pending tasks](docs/pending-tasks-2026-09-19.md) · [architecture viewer](docs/architecture-flow.html). `Loop.MD` records tests; `Learning.MD` records failure causes. [Earlier checkpoints and decisions](docs/history/handoff-2026-09-19-before-final-repair.md) are history, not current instructions.
