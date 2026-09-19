# CRETA browser runtime evidence — 19 September 2026

Status: not ready on answer quality. Twenty controlled interruption cases passed, and both commute and safety journeys completed their full selected routes and natural recaps. The final safety run retained one failed ADAS answer check. The family scenario intentionally exits early and must not be described as a full tour. All reviews were muted.

## Boundaries

The real runs use published CRETA bundle v2 (`dm_41513908`) through the actual player, backend reasoning, calculator and Sarvam speech delivery. Chrome runs headless with a fresh isolated profile and `--mute-audio`; no user Chrome window, physical microphone or contact submission is used. Captured input is silent synthetic audio, with controlled STT events injected into the browser. These runs establish delivery and ownership mechanics, not acoustic onset, echo cancellation, human recognition or voice naturalness.

The separate synthetic STT content check retained the intended family/boot-space request, loan amount/rate/term and comfort-priority correction in three prerecorded customer utterances. It also does not establish real acoustic performance.

## Preserved real attempts

- `output/playwright/creta-real-runtime/attempt-03/`: code checkpoint `24c2b76`, 47/47 completed assertions and 20/20 controlled interruption cases. Family interruption scenario reached an explicitly labelled early-exit recap. Commute completed every selected slide, a calculator-backed EMI answer, closing, explicit Not yet and natural recap. Safety completed its selected slides and ADAS answer, but the runner's still-loaded TTS cap 20 blocked the final recap request 21. Do not report this as three completed journeys.
- `output/playwright/creta-real-runtime/safety-replay/attempt-01/`: backend `eb27b71`. The selected safety route contained no authored check-in; playback advanced normally into closing. The old harness incorrectly required a first question wait within 75 seconds and stopped before asking ADAS. This is a harness assumption, not stuck player playback.
- `output/playwright/creta-real-runtime/safety-replay/attempt-02/`: backend `eb27b71`. Gemini read timeout 7,019 ms, Claude credit error 441 ms and Runware timeout 4,544 ms left planning without a result at the 12-second graph deadline. The player disclosed that tailoring failed and entered the reviewed fallback route. The old assertion required successful personalization and stopped the run before QA. Provider errors are preserved in `provider-failure-redacted.json`.
- `output/playwright/creta-real-runtime/safety-replay/attempt-03/`: application `2a07c750b52e95750d7d09531c5e2b7f9433ca7d`, corrected source publication v3. Successful personalization, every selected slide visited, explicit Not yet, natural recap and optional consent preview completed without submitting a lead. Results are **12/13**, exit1: the broad ADAS question was safely declined after `overgeneralized_variant` validation, despite available relevant evidence. No browser or budget-guard error occurred. The harness hash and its nonfatal assertion-collection change are preserved in `run-metadata.json` and `harness-uncommitted.diff`; this failed quality assertion remains failed rather than being counted as completion success.

Each archived attempt retains its own results, event ledger, screenshots and state; `SHA256SUMS.json` identifies the preserved files. Attempts are never replaced by later passing evidence.

## Observed timing, with separate cohorts

`attempt-03/timing-cohorts.json` preserves the measurements before subsequent replays.

- Sixteen interruption cases had active audio; the worst measured browser onset-event receipt to local cancellation was 253 ms. Four additional calculation-request-pending cases established cancellation while waiting; their name does not prove that a backend tool had begun executing. These are synthetic onset measurements, not true acoustic onset.
- The successful typed EMI turn acknowledged at 734 ms, began useful answer audio at 7,764 ms and completed delivery at 25,919 ms. The session records calculator provenance.
- The successful typed ADAS turn acknowledged at 761 ms, began useful answer audio at 4,944 ms and completed delivery at 18,269 ms.
- Twelve deliberately cancelled questions are excluded from successful-answer timing. Two completed typed answers cannot establish reliable p50/p95 release performance or microphone latency. Both observed acknowledgments exceed the proposed 700 ms target; retain that finding rather than rounding it into a pass.

The final v3 safety replay is a separate **safe-decline cohort**, not successful useful-answer latency. Typed submit was `1789821506828`, acknowledgment audio `1789821507507` (679 ms), decline audio `1789821509413` (2,585 ms), and delivery completion `1789821518926` (12,098 ms). Full timestamps and the exact rejected model draft are preserved in its `timing-cohorts.json` and `answer-trace-redacted.json`. Gemini supplied standard safety facts F174/F195 and said that higher-level packages could not be verified; it did not answer the requested variant-specific ADAS coverage.

## Fixes found through this review

The recap now displays intake context and explicit priority refinements in “What matters to you.” Raw question history remains in the internal session and conversation context. Ending capture now shows “Demo complete,” and muting capture cannot retain a stale “Listening” label.

Unexpected WebSocket loss now rejects owned speech as a transport failure, activating readable caption fallback. This lets an explicit Not yet choice still reach recap when farewell speech fails. A customer interruption or new turn retains cancellation ownership and cannot revive the old farewell or force a stale recap. Failed caption delivery does not fabricate an audio-start measurement.

Free validation after these fixes: real DOM legacy browser 40/40; actual browser/WS/worklet with mock providers 21/21; fake-device/transport client contracts 54/54. The actual mock browser deliberately closes the farewell WebSocket, observes a readable recap and verifies that no successful farewell audio-start event was recorded. Screenshots/results are in `output/playwright/creta-runtime/`; legacy evidence is in `output/playwright/creta-recap-free/`.

## Harness corrections and remaining run

The harness asks ADAS during the first reviewed narration instead of assuming that a selected route contains a check-in. It records `planning_outcomes` separately: successful personalization or an explicitly disclosed planning failure. Honest fallback may continue through QA and natural completion while remaining a recorded personalization failure. It still rejects lost customer context, an unexplained fallback, stale question ownership, failed required answers and unvisited selected slides.

The corrected harness passed 32/32 free browser checks with planning deliberately failed locally: both natural routes completed and both planning failures remained recorded, plus the labelled family early exit. Evidence is in `output/playwright/creta-harness-free-fallback/`. This mock-only mode makes no real provider, calculator accuracy or acoustic claim; recorded provider cost was $0.

Natural completion follows only visible owned continuation choices, reaches closing, explicitly selects Not yet and verifies the recap with every selected slide visited. Stop is never used to manufacture natural completion. Optional dealership follow-up is inspected but never submitted.

Corrected source publication v3 retains the exact same reviewed slides, narration, overview and voice/media; its refreshed snapshot is `kb_c70af9b392163108dee4eb7a`. Original counters and the cost baseline remain cumulative. The final completed run ended at **23 reasoning requests / 30 TTS requests**, with a shared ledger delta of **$3.2655**. The authorized guards are 32 reasoning requests and 32 TTS requests, a shared incremental estimate of $6 and a total demo estimate of $19.50. Shared cost includes separately authorized concurrent QA and must not be attributed solely to browser testing. Any cap extension is recorded explicitly; counters and baseline are never reset. No further full replay is authorized; backend answer repair may be verified by a separately coordinated selective ADAS probe.

Acknowledgment now allows a 250 ms grace for a ready answer before starting its prerecorded filler. Ready answers bypass or preempt it without overlapping voices. The player selects the shortest reviewed, recorded acknowledgment; corrective publication v4 supplies the locked Priya clip “Let me check that.” (1.365 seconds), with all other published content unchanged. Its actual customer timing remains unmeasured until the coordinated selective probe.

The session now records explicit answer, clarification and decline classifications. Timing reports separate these from unclassified legacy responses, exclude failed/cancelled turns and spoken declines from answer timing, and retain all failure/decline/missing counts. Clarification completion is unavailable because its existing end marker includes customer reply time. “Answer playback latency” means a response marked answered by the runtime; answer quality requires separate evaluation.

Free checks after the acknowledgment/reporting changes: **41/41 actual DOM cases**, **56/56 fake-device/transport client cases**, **15/15 metrics contracts**, plus JavaScript syntax checks. The actual DOM cases cover a ready answer bypassing the grace timer, an answer cutting an active filler, single-voice ownership, and persisted answer/clarification/decline identities. Evidence is in `output/playwright/creta-ack-metrics-free/resumed/`; the earlier interrupted run and original results are preserved. These free checks do not establish provider response latency or acoustic performance.
