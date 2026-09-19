# Demo Studio — pending tasks and challenges

**Latest runtime evidence:** unchanged100 on9d46913/v7: **87 supported /3partial /2unhelpful /0unsafe /8provider failures**. Text median3.917s,p9511.814s; settled cumulative estimate$11.7293. Previous7133f23 cohort remains93/4/2/0/1. Provider tails now dominate; earlier-fallback testing is bounded and experimental. No new speech budget; quality and audio latency remain unaccepted.

**Current update:** Anand subsequently approved the [conversational runtime plan](plan-runtime-experience-2026-09-19.md). Implementation is on `codex/creta-conversational-demo`; Atelier remains. The original audit below is preserved as history and must not be read as the current capability list. [Current workflow and code map](DEMO_BUILD_AND_RUN.md) · [Creta acceptance in progress](CRETA_ACCEPTANCE.md).

## Remaining now

1. **Finish real runtime acceptance.** Latest87 supported answers miss95%; eight turns failed across providers. Test an earlier fallback launch within the same deadline after preserving the current cohort. Remaining content issues include incomplete road-wheel choices, an imprecise standard-warranty limit, a dealer-timeline assurance and two discarded refusals. Source extraction needs stronger table-role and fact-coverage checks: reviewed road/spare repairs do not establish robust extraction for future products. Rear-armrest/storage data exists in source extracts but was omitted from approved facts.
2. **Meet speech latency and physical listening targets.** Latest successful typed ADAS probe: acknowledgement 434 ms, answer audio 3.703 s, result-ready→audio 580 ms; exact Continue return passes. One sample establishes no percentile. Twenty controlled interruptions pass, with sixteen active-audio stops within 253 ms of injected onset receipt. Human microphone accuracy, acoustic delay, echo and perceived voice naturalness remain unverified under muted review. Browser speech cap reached at 32; no silent counter reset.
3. **Finish the TVS iQube artifact if selected next.** Nine supported FAQ texts were repaired without provider calls; eleven evidence gaps remain honest declines. Its speech, rehearsal and published bundle were not rebuilt. The legacy QA approval boundary is documented in Handoff.
4. **Review remaining product and operations scope.** Image-only re-tagging, refresh-resume, any change to exact-line resumption, multi-worker coordination, deployment credentials and activation still need their own implementation/validation. Deployment has not occurred.

## Implemented since the original audit

Immutable evidence identity and published snapshots; scoped crawl/extraction with upload precedence; runtime LangGraph, calculator and customer-supplied URL lookup; continuous capture and cancellation; published Explore personalization; sparse real check-in waits; readiness probes and durable events; semantic speech/rehearsal reuse; Ready-to-Align event recovery; optional-media import and mock-provider guards. Their existence does not imply that all real acceptance targets have passed. See the current acceptance report for the boundary.

## Historical audit before runtime approval

Reviewed against the then-current code, final Nexon evidence and earlier instructions. This audit itself changed no functionality. Anand had selected **B · Atelier**; the visual system was applied through four CSS files. [Atelier delivery](design/atelier-ui.md).

## Recommended sequence

1. **P1 · Preserve evidence identity across Re-Read.** New extraction can reuse a fact ID for a different claim while old reviewed edits still reference it. The Nexon draft was manually reconciled; durable identity/conflict handling is absent. Challenge: retain human edits without silently changing their meaning. Evidence: [NX20](issues/2026-09-18-nexon.md#nx20--re-read-reassigns-reviewed-fact-meaning-and-drops-cockpit-evidence), `server/agents/understand.py:270`.

2. **P1 · Validate the actual spoken experience.** Native microphone/STT accuracy, pronunciation, voice naturalness and acoustic overlap remain unverified because review stayed muted. A later intake attempt stayed at “Opening microphone.” Challenge: reproduce real device behaviour without confusing synthetic browser tests with acoustic evidence. Automatic spoken barge-in, streaming and refresh-resume are separately unbuilt/out of scope. Evidence: [professional UI limits](design/professional-ui.md#limits-and-follow-up), `PRD.md:36`.

3. **P1 · Reduce response waits and establish useful KPIs.** Latest three model turns: 9.029s median, 10.458s worst; one cached turn: 2.841s including its transition. These small typed samples are not a production SLA. Cross-demo latency percentiles are unbuilt. Challenge: improve actual answer latency, not merely start filler sooner. Evidence: [final measured sample](../output/nexon-real-evidence/iteration-2/final-review.md#checks-timing-and-cost), `server/app.py:1088`.

4. **P1 · Improve useful, grounded answers and conversational pacing.** The warranty guard blocks an unsupported relationship but produces a decline instead of a useful partial answer. Some authored questions repeat known context; optional proof can discuss another powertrain. Challenge: improve usefulness while retaining citation/qualification and exact-return guarantees. Evidence: [final remaining limits](../output/nexon-real-evidence/iteration-2/final-review.md#what-remains-weak).

5. **P1 · Agree and implement runtime tools for calculations and competitor URLs.** Runtime QA has no calculator or live-web tools. Competitor pages are retrieved during ingestion; current answers use the saved registry. Challenge: validate inputs, units, source/variant applicability and freshness, with clear failure behaviour. This needs an agreed approach before implementation. Evidence: `server/agents/qa.py:20`, `server/agents/principles.py:69`, `server/sources.py:37`.

6. **P1 · Add build readiness and durable failure visibility.** Provider health shows configuration/key presence, not whether the account can serve a request. Read/Build lack provider probes; progress warnings are memory-only; some build-provider failures lack detailed traces. Runtime failure tracing already exists. Challenge: distinguish degraded output from a healthy build without silently changing provider order. Evidence: `CODEX_INSTRUCTIONS.MD:181`, `server/config.py:76`, `server/orchestrator.py:31`, `server/llm/runtime.py:41`.

7. **P2 · Reproduce and fix Ready → Align event replay.** An explicit Align route is supported, but a subscription starting at zero can replay the prior Build completion and redirect back to Rehearse. This is conditional on retained events in the same server process. Challenge: distinguish history from new completion events; preserve legitimate live navigation. Evidence: `web/api.js:14`, `server/app.py:348`, `web/studio/align.js:366`. Code-supported cause; not newly reproduced in this audit.

8. **P2 · Repair the existing TVS iQube FAQ bank.** The outage-poisoning mechanism is fixed, but local `dm_d5675e7f` still contains 20 entries, all declines. Repair is a separate paid operation, followed by product review. Evidence: `CODEX_INSTRUCTIONS.MD:217`, `data/demos/dm_d5675e7f/faq.json`.

9. **P2 · Avoid unnecessary build work and enable targeted image repair.** FAQ answers are reused in rehearsal, but script scoring still makes a call and has no script-hash result reuse. An image-only re-tag action is absent. Challenge: invalidate only what changed and keep reviewed edits intact. Evidence: `server/agents/rehearsal.py:36`, `CODEX_INSTRUCTIONS.MD:189`, `server/app.py:809`.

10. **P2 · Reconcile older conversation proposals before implementation.** Planning filler can still say it is tailoring after failed/null planning; typed check-in kinds and a broader pacing/register audit remain proposals. A 40%-heard resume rule would change the current verified exact-line return and needs a separate decision. Jump announcements and warm declines already exist. Evidence: `CODEX_INSTRUCTIONS.MD:235`, `web/player/player.js:711`, `web/player/player.js:635`.

11. **P2/P3 · Confirm deployment prerequisites and scaling scope.** AWS adapters/table-creation code exist. Last documented pending actions are instance-role/table authorization, storage activation and deployment approval. Current external AWS state was not checked. Summary coordination is process-local; multi-worker deployment requires review. Historical instance/domain/token-rotation notes also need status confirmation. Evidence: `Handoff.MD:173`, `server/app.py:972`.

12. **P3 · Clear small maintenance issues.** Optional mascot generation and image enhancement retain an invalid relative import in `server/media.py`; NX21 recorded the mascot warning. The builtin guide limits visible impact. Hand-written Align import versioning also remains. Evidence: `server/media.py:267`, [NX21](issues/2026-09-18-nexon.md#nx21--read-shows-a-mascot-import-warning), `CODEX_INSTRUCTIONS.MD:196`.

## Already completed — do not reopen from stale notes

Runware fallback and model tiers; the two-build Nexon exercise; reviewed competitor comparisons; line-owned citations and exact question returns; explicit CTA consent; future summary usage attribution; same-process summary race protection; professional UI baseline; four isolated design concepts; selected Atelier styling integration. The final Nexon confirmation supersedes earlier “pending rerun” entries in the issue history.

## Boundaries

No task above was implemented during this backlog audit. No provider calls, third Build, deployment, architecture change or microphone/audio test was run. A design choice authorizes styling integration only; the functional backlog remains for sequencing afterward.
