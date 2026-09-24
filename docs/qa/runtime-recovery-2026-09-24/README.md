# Runtime recovery QA — 24 September 2026

Branch: `codex/sales-trainer-flow`. WP12 presentation is separately committed as `721611b`; these changes enhance existing playback, transport, tools and session endpoints. No new agent, graph node, service, dependency or publication exception. Master/AWS release requires Anand's later hands-on approval.

## What changed and why

- `web/player/player.js`, `live-voice.js`, `server/runtime_live.py`: final-input qualification prevents provisional speech from opening an abandoned hold; controls stay local, generic intake stays neutral and logical sections use three-second reply windows. A progress-aware delivery deadline permits healthy long answers/closings.
- `web/player/player.js`, `server/app.py`: ongoing saves preserve visits before exit. Immutable heard-prefix snapshots, safe sequence numbers, bounded coalescing/retries and revision-bound summaries prevent lost or regressed content. Public share copies mask phone numbers; private consented sales records remain intact.
- `web/player-ui.css`, `player.js`: unknown answers offer a contact button. Explicit forms honor Not now and do not enlarge the shared phone grid. Measured390px player regions previously widened to401.53px; they now remain390px.
- `server/runtime_tools.py`, `runtime_graph.py`: enabled top-level owner URL sources define runtime web permission. Relevant same-domain pages are allowed; customer input cannot authorize arbitrary domains. Existing grounding, scope, network and tool-budget limits remain.
- `server/agents/plan.py`: prepared narration budgets now fit complete 26–33-word delivery batches and share limits across segments covering the same story stop. The previous nine-stop budget total was 495 words, but its individual allowances could not accommodate the required speech. Story order, approved evidence, voice speed and publication checks remain intact.
- `server/app.py`: a normal pitch edit retains server-owned duration metadata after strict validation. It still resets approvals and invalidates affected stages; the new regression reproduces the previous metadata loss through the real PATCH endpoint.
- `server/agents/deck.py`: fallback illustrations retain their badge and cited captions, but cannot automatically acquire a feature pointer. The paid picture-audit timeout exposed incorrect grille/wheel anchors; literal proof checks and explicit reviewed positions remain unchanged.

- `web/slide.js`, `web/styles.css`: intentionally absent pictures now yield the exact reviewed narration on the slide. Fixed reveal geometry and bounded scrolling replace broken-image placeholders; image-bearing slides and Align editing retain their existing rendering. This is a separate runtime enhancement after WP12.

- `server/runtime_facts.py`, `runtime_graph.py`: initial, repaired and cached answers now retain explicit collective engine/gearbox boundaries. The paid answer failure is preserved;19targeted tests and17independent probes verify the correction without another paid visit.

## Paid source finding

The first paid Read reached Align but failed narration preparation at342/495 eligible words after its three existing attempts. No Build or approval followed. Offline replay shows no parser truncation and no Author text loss: the model omitted supplied features/gearbox matrices, and the draft included generic benefits its cited facts did not establish. Initial recorded estimate:$0.2238/22calls. Original response fields, hashes and artifacts remain preserved under the isolated QA work directory.

`server/agents/understand.py` now uses20k page-preserving batches and requests categorical facts, table fitment and stale warnings explicitly. `server/knowledge.py` accepts an exact quote in a single retained cell only under its explicit page/source/nonempty revision. New reader10 and fact-retry19 checks plus source39, automatic16, preparation35/core/release/runtime regressions pass. These are enhancements inside the existing nodes, not semantic-completeness guarantees.

The same draft's evidence revision produced160 facts and467 eligible words. Review excluded13 unsafe or stale facts, versioned13 qualified corrections and individually restored5 exact cited facts. A normal Coach revision then produced399 words. Exact-response replay established that no text was lost: scalar budgets of45–51 words were incompatible with two or three minimum26-word batches. The new allocator has17 dedicated regression groups, an independent review and unchanged duration/grounding guards. A495-word human editorial reference was also reviewed against the uploaded sources for the final normal Author revision. Failed attempts and editorial assistance remain explicit; this is not an unattended first-pass success.

## Evidence

`free-gates.json` contains exact per-suite counts and source/log hashes. The final inventory contains60suites/2,335overlapping checks:54free suites/1,854checks and six browser suites/481checks (HTML87, live40, layout212, workbook101, integration19, navigation22). Required core386/24/smoke3 and full mock release28 pass. A fresh production-Bundle renderer pass adds480separately reported overlapping checks. Exact per-suite provenance identifies unchanged workbook coverage reused from the prior rendering pass. The paid visit reached its CTA/ended recap with67checkpoints and11/11mechanical checks; the original semantic answer failure and corrected-code replay are separated in `paid-acceptance.md`. Core mock journey exercises normal Read/review/Voice/Bundle/runtime/cache/rehearsal/session flow and measures194.22seconds of synthetic fixture audio. This proves mechanics, not real voice quality.

`fmea.md` covers all12 required categories. `form-390.png`, `form-1440.png` and geometry files record the scoped overflow fix. WP12 camera screenshots and85motion checks are in the adjacent `wp12-2026-09-24` directory.

## Limits and report-only finding

Caption text is set before asynchronous speech fetch/playback, and provider word timestamps are unavailable to the current player. The sentence can lead audible speech; caption timing is intentionally unchanged under Anand's report-only instruction.

The first resumed mock capture attempt timed out, and one diagnostic attempt failed to observe the initial recorded line. No production cause was established; preserved diagnostics and two later complete live40/40 runs are explicit in the receipt. Timeout bounds and capture assertions were not weakened.

Text qualification rejects fragments and irrelevant statements but is not speaker identification. Physical TV/cup noise, echo and voice listening quality require acoustic acceptance. Muted browser checks do not establish them. Unload/network-loss delivery is best effort; session ordering uses the existing single-worker local lock. Save deadlines unblock the queue but do not abort a stalled underlying HTTP request. No protected demo/port8896 action or AWS deployment belongs to this work.
