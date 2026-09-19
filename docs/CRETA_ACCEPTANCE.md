# CRETA acceptance — 19 September 2026

**Status: implementation and the reviewed demo are built; runtime acceptance remains in progress.** A playable bundle is not proof of a reliable sales conversation. This report separates actual provider results, deterministic checks and the physical listening checks that muted testing cannot establish.

## Reviewed demo

Hyundai CRETA `dm_41513908`, published version **2**, knowledge snapshot `kb_0aa4afd7c249769b1208267f`, all six Studio approvals true. [Open muted in the local app](http://127.0.0.1:8896/?mute=1&review=creta-runtime#/play/dm_41513908).

The demo uses eleven selected official images and the supplied PDFs alongside model-scoped official India pages. Manufacturer engine-table figures were visually checked. Conflicting turbo displacement and airbag assertions were rejected; repaired assertions have new identities. Variant, market and optional-package conditions remain visible. A brochure publication date is not treated as a vehicle model year.

The opening highlights the cabin, panoramic sunroof and ventilated front seats with variant qualifications. Priya's recorded Explore overview is **11.25 seconds**. Main narration and three confirmation questions total **131.5 seconds**, before customer pauses or deeper explanations. The check-ins consistently mean yes=continue and no=more detail. Atelier and the cinematic slide geometry remain.

The static scorecard improved from **11/20 to 13/20**; neither is a pass. Its whole-library scoring and old opening preferences do not exactly match the personalized runtime and the requested feature-first opening. That mismatch is documented rather than used to relabel the score.

## First real test: retained baseline

The first 100-question run completed against the published snapshot. Independent semantic review found **38 supported, 36 partially correct, 16 unhelpful, 5 unsafe and 5 provider failures**. These categories evaluate the actual answer, including useful uncertainty or refusal; an HTTP success or `answered=true` is not a semantic pass. One early review incorrectly used a rejected wheel assertion as approved counterevidence; correcting that review reduced unsafe answers from six to five, without changing any response.

HTTP text response time was median **2.823 seconds**, p95 **8.385 seconds**, including failures. This cohort has no speech playback and cannot establish first-useful-audio latency. The tracked usage delta was **$1.9206** and includes concurrent work recorded in the same demo ledger; it is not exact browser-versus-QA attribution or a provider invoice.

The first real browser attempt passed four controlled overview interruptions, then failed to enter the selected tour within 45 seconds. The plan itself arrived in 4.038 seconds, but legacy decision-frame and custom-batch speech created an extra opening. That is a product failure, not a reason to relax the test timeout.

Evidence remains in local `output/creta-runtime-2026-09-19/qa100-reviewed-v2/` and `output/playwright/creta-real-runtime/attempt-01/`. The original answers and failed run are preserved.

## Repairs being revalidated

- The overview leads directly into selected slide narration. Missing model replacements use explicitly marked reviewed-route speech. Published inputs and demo-version checks prevent draft edits or a new publication from silently changing a running visit.
- Runtime reasoning sees compact approved assertions and their conditions. Full provenance tables remain available for audit, but cannot serve as permission to borrow an unrelated feature from a large quote.
- Calculations preserve quoted inputs, units, derivation and assumptions. Explicit approximate currency wording can use nearest-rupee rounding. Verified tool results can rescue a missing model rendering; a caveat alone is not counted as a useful calculation answer.
- Selected-trim qualifications and exact negative applicability are preserved. Held or rejected assertions remain ineligible. Opaque ordering such as “SX and above” is not expanded into invented trim coverage.
- Cancellation, stale output, real question waits and audio timing have separate checks. Caption-only fallback does not count as first answer audio. Align overlays are removed on navigation; mobile evidence overflow has a cue only when needed.

The second real QA batch, full customer journeys and final required regression gates will be recorded here when complete. Additional deterministic grounding probes found unit/feature and negative-clause loopholes before the repeat batch; these are being repaired before further paid acceptance.

## What muted acceptance cannot prove

The controlled browser uses real application state, prerecorded playback, provider reasoning/tools and streamed speech bytes. Synthetic silent capture and injected transcript/onset events exercise control flow without using Anand's physical microphone or Chrome window. The browser remains muted.

Those checks do **not** prove physical listening accuracy, acoustic speech-onset delay, speaker echo cancellation, perceived voice warmth or human interruption quality. Three separate prerecorded synthetic utterances passed actual transcription intent/entity checks, which is still not a human microphone benchmark. These limits remain explicit even if every automated case passes.

[Build/run workflow and code references](DEMO_BUILD_AND_RUN.md) · [Issue log](issues/2026-09-19-creta.md) · [Approved acceptance targets](plan-runtime-experience-2026-09-19.md)
