# CRETA acceptance — 19 September 2026

**Status: implementation and the reviewed demo are built; runtime acceptance remains in progress.** A playable bundle is not proof of a reliable sales conversation. This report separates actual provider results, deterministic checks and the physical listening checks that muted testing cannot establish.

## Latest provider-tail replay

Commit `9d46913`, unchanged v7 and100 questions: **87 supported, 3 partial, 2 unhelpful, 0 unsafe and 8 provider failures**. All-request REST text median **3.917s**, p95 **11.814s**; maximum11.921s. Recorded cost **$0.621665**, settled cumulative **$11.7293**. The100 exact row hashes and semantic reviews are preserved in `qa100-v7-conversation-final/`.

The remaining partials omit the R18 road-wheel category(q026), a precise standard-warranty limit(q028), or add an unsupported dealer-timeline assurance(q084). Two refusals became generic or irrelevant(q085/q086). All ten fully specified calculations independently recompute; a timed-out optional repair did not erase q052's completed EMI answer. The eight whole-turn outages are q027/037/040/044/048/066/067/095. Both q066/q067 fetched source information before composition failed. Runware successfully composed q063; its other late timeout outcomes remain in the audit.

The trace and usage tails were unchanged for51.878s before code edits resumed. Sequential fallback often received less than4s after Gemini's7s timeout, shorter than the earlier successful Runware range3.316–5.563s. A separately bounded earlier-fallback experiment is being prepared with the same12s deadline; it may increase billed overlap and is not yet an established improvement. The default remains off. No source, authored story or speech changed.

## Earlier typed-conversation replay

On `7133f23` and the same v7 snapshot, the unchanged100 scored **93 supported, 4 partial, 2 unhelpful, 0 unsafe and 1 provider failure**. REST text median **2.7595s**, p95 **6.270s**, maximum11.822s. The cohort added an estimated **$0.6451** to a settled cumulative **$11.1077**;134 completions were recorded. No TTS or source changes ran.

All100 answer hashes were verified against the raw JSONL. Independent review moved q095 from supported to partial: the answer attributed an applicability caveat from reviewed records to an explicit brochure statement. The original review is preserved. The other partials lost connected features(q025), spare-wheel detail(q026) or the EMI guarantee refusal(q064). q075/q092 gave generic fallbacks; q027 was a true provider failure. q056/q058 delivered correctly audited fuel-cost results after composition failed; q026 retained useful facts despite an optional repair timeout.

This still misses95% usefulness. Current corrections target those specific conversational and validation failures; they do not change this observed score. Full evidence and provider settlement audit are under `qa100-v7-typed-acts/`. Physical listening, warmth and audio percentiles remain unverified.

## Earlier same-code sequential and hedged comparison

On commit `1aab334` and unchanged v7, sequential delivery scored **88 supported, 5 partial, 4 unhelpful, 3 unsafe, 0 provider failures**. Text median was **2.600 s**, p95 **6.391 s**; recorded estimate **$0.6301**. Experimental delayed fallback racing scored **88 supported, 4 partial, 5 unhelpful, 2 unsafe, 1 provider failure**. Text median was **3.8895 s**, p95 **9.868 s**; recorded estimate **$0.8387**. These are REST text measurements including failures, not useful-audio percentiles. Original 100 answers and exact raw-row hashes are preserved separately in `qa100-v7-relations-sequential/` and `qa100-v7-relations-hedged/`.

Both fail acceptance. Remaining critical claims expand exact rear-camera trim lists into “EX(O) upwards”; the sequential wheel answer also invents an ordinal spare-wheel range. Missing-input and precise-limit wording is still sometimes discarded. Every completed numeric result in both runs independently recomputes. Hedged q052 delivered the audited EMI after composition timed out; q066 failed after source lookup and correctly described a temporary checking problem rather than a knowledge gap.

All launched calls have terminal events and the usage/trace tail settled before further edits. Four losing Runware completions added **$0.099183**, included in the hedged total. Hedging stays **off by default**: it successfully exercised fallback and late-result accounting but this separate-run observational comparison establishes no aggregate benefit. Primary provider conditions differed materially. Cumulative app estimate is **$10.4626**, not a provider invoice; timed-out requests may incur unreported provider billing. No additional paid browser speech ran.

## Earlier unchanged full100 — clause ownership checkpoint

Commit `24736a0`, v7 snapshot: **73 supported,11partial,7unhelpful,2unsafe,7provider failures**. Delivered answers were graded individually by three reviewers against the saved assertions;100 raw-row hashes match. The unsafe answers imply an8-inch/Bose combination across incompatible trims and claim whole-page warranty absence from a selected-passage lookup. Neither passes the zero-critical-claim requirement. Missing limits and valid comparison/input-request clauses also remain over-rejected.

REST text median3.831s,p9511.802s (all requests), not first-useful-audio latency. Seven reasoning failures, two failed optional repairs, one successful Runware recovery, and one audited calculator rescue are distinguished. Ten numerical outcomes independently recompute correctly; q053 delivered the zero-interest EMI with its assumptions after second-round reasoning failed. Five fresh requested-source checks succeeded. Gemini had11 read timeouts; no quota/503 evidence. Claude returned explicit insufficient-credit errors. App recorded estimate increased$0.5773 to$8.9938; timeouts may have unreported billed work.

Evidence: `qa100-v7-clause-ownership/` raw responses, three semantic reviews, consolidated summary and provider audit. Raw JSONL SHA256 `d1d8f0761a850ffea600b90974ce241b781cec3cf4e47af5505a17e6e22a53c2`. Ongoing fixes and diagnostic replays do not replace or rescore this observed cohort. The proposed delayed fallback race stays off by default until separately tested; no claimed latency gain yet.

## Reviewed demo

Hyundai CRETA `dm_41513908`, published version **7**, knowledge snapshot `kb_2d616ba1bcec1469e8c7ab40`, **181 approved facts**, all six Studio approvals true. [Open muted in the local app](http://127.0.0.1:8896/?mute=1&review=creta-runtime#/play/dm_41513908).

The demo uses eleven selected official images and the supplied PDFs alongside model-scoped official India pages. Manufacturer engine-table figures were visually checked. Conflicting turbo displacement and airbag assertions were rejected; repaired assertions have new identities. Variant, market and optional-package conditions remain visible. A brochure publication date is not treated as a vehicle model year.

The opening highlights the cabin, panoramic sunroof and ventilated front seats with variant qualifications. Priya's recorded Explore overview is **11.25 seconds**. Main narration and three confirmation questions total **131.5 seconds**, before customer pauses or deeper explanations. The check-ins consistently mean yes=continue and no=more detail. Atelier and the cinematic slide geometry remain.

The static scorecard improved from **11/20 to 13/20**; neither is a pass. Its whole-library scoring and old opening preferences do not exactly match the personalized runtime and the requested feature-first opening. That mismatch is documented rather than used to relabel the score.

## First real test: retained baseline

The first 100-question run completed against the published snapshot. Independent semantic review found **38 supported, 36 partially correct, 16 unhelpful, 5 unsafe and 5 provider failures**. These categories evaluate the actual answer, including useful uncertainty or refusal; an HTTP success or `answered=true` is not a semantic pass. One early review incorrectly used a rejected wheel assertion as approved counterevidence; correcting that review reduced unsafe answers from six to five, without changing any response.

HTTP text response time was median **2.823 seconds**, p95 **8.385 seconds**, including failures. This cohort has no speech playback and cannot establish first-useful-audio latency. The tracked usage delta was **$1.9206** and includes concurrent work recorded in the same demo ledger; it is not exact browser-versus-QA attribution or a provider invoice.

The first real browser attempt passed four controlled overview interruptions, then failed to enter the selected tour within 45 seconds. The plan itself arrived in 4.038 seconds, but legacy decision-frame and custom-batch speech created an extra opening. That is a product failure, not a reason to relax the test timeout.

Evidence remains in local `output/creta-runtime-2026-09-19/qa100-reviewed-v2/` and `output/playwright/creta-real-runtime/attempt-01/`. The original answers and failed run are preserved.

## Second real test: improved, still below acceptance

The second full batch ran on commit `24c2b76` and completed **100/100 requests**. Independent review found **64 supported, 23 partially correct, 8 unhelpful, 2 unsafe and 3 provider failures**. The unsafe cases were a false claim that a wheel comparison was absent despite an approved uploaded assertion, and a claim of fresh webpage price verification supported only by saved document facts. Neither is acceptable. Useful text response times were not isolated in this statistic: all-request HTTP median was **2.394 seconds**, p95 **8.959 seconds**. Shared recorded usage increased **$0.5932**, including concurrent browser activity.

The browser replay passed **20 controlled interruptions**: four each during overview, reviewed narration, answer, acknowledgement and a pending calculation question. Sixteen had active audio; observed stopping across those samples was at most **253 ms**, measured from injected onset receipt rather than acoustic speech onset. The family journey intentionally exited early after these controls. The commute journey completed every selected slide, question wait, final choice and recap. The safety journey completed its route and final choice, but the test's speech-request cap blocked farewell request 21 before recap; this is retained as a harness-limited run, not a completed third journey.

The two completed typed answers measured first useful audio at **7.764 seconds for EMI** and **4.944 seconds for ADAS**; acknowledgement started at **734/761 ms**. These are small samples and do not establish reliable percentiles or meet every proposed latency target. [Pass 2 private evidence](../output/creta-runtime-2026-09-19/qa100-reviewed-v2-pass2/summary.json) and the immutable browser `attempt-03/` remain local.

Follow-up repairs recover approved wheel and parking facts, preserve clear negative refusals, constrain live lookup to the selected model/market, support explicit monthly-rate EMI and improve recap resilience.

## Focused replay and corrective publication

The 24-case focused replay on `eb27b71` produced **14 supported, 3 partial, 2 unhelpful, 2 unsafe and 3 provider failures**. It is a deliberately difficult subset, not a replacement 100-case score. The two unsafe answers exposed an approved conflicting turbo displacement in the uploaded guide and an unqualified current-lineup claim from a Pune FAQ. Universal-feature projection and compound trim parsing also lost supported answers. Results and independent reviews remain unchanged under `qa-focused-pass2-repairs/`.

The source audit rejected F056/F048/F076/F126 and replaced ambiguous F123 with F246, explicitly describing the manufacturer's spare wheel. Dependent citations were reviewed; all remaining references resolve to approved evidence. **Bundle v3 is a corrective publication beyond the two authored iterations.** It used deterministic assembly with no paid generation. Slides, narration, voice settings and audio references are unchanged; the original v2 snapshot is preserved. The old static score remains historical and its rehearsal stage is stale, not a fresh pass.

Runtime repairs retain material market scope, preserve S(O) Knight, support valid safety subsets and dispatch explicit URL verification before model reasoning. The third unchanged 100-question pack completed on `2a07c75` against v3: **75 supported,18partial,6unhelpful,0unsafe flagged,1provider failure**. All-request HTTP text median was **2.353s**, p95 **6.953s**; the shared recorded usage delta was **$0.6635**, including concurrent browser activity. This still misses the quality target. Exact results and semantic reviews are preserved in `qa100-final-source-corrected/`.

The safety journey completed every selected slide, explicit Not yet and recap, with no lead submission. It passed12/13 assertions: ADAS answering failed because ordinary “variant conditions” was parsed as a nonexistent trim. Its679ms acknowledgement and2.585s **decline** audio are not a successful useful-answer timing. The flow completion does not turn the failed answer into a pass.

Bundle v4 replaces only the long acknowledgement with **“Let me check that.”**, recorded in locked Sarvam/Priya at **1.365s**. All other bundle content and the knowledge snapshot are identical. One short render added a recorded estimate of **$0.0003**; no new story or full voice stage ran. The parser correction, one bounded validation-repair composition, shorter acknowledgement grace and outcome-separated metrics are undergoing targeted validation before another live replay.

Corrective v5 adds precise manufacturer-backed sunroof and rear-camera applicability: E/EX have explicit dashes in those rows, corroborated by the guide's symbol legend. NewF247/F248 preserve old assertion history. It contains181approved facts; all narration, slides and recordings remain unchanged. Six independent offline controls confirm retrieval, valid negative answers and rejection of inverted positive claims. These source checks do not replace live answer-quality testing.

The subsequent35-case difficult subset on `0f88ad1`/v5 returned **24 supported,3 partial,3 unhelpful,5 provider failures,0 unsafe flagged**. Two provider failures were repair timeouts that the raw API called limited/refused; semantic review retains their actual cause. HTTP text median3.351s,p9512.031s. Recorded shared cost delta$0.2164 includes the concurrent browser probe. This subset is not a new100-case score. ADAS, Bose, cruise, E-roof, EX-camera and several comparisons improved; connected-car scope phrasing, exact missing-detail wording and provider timeouts still needed work.

The separate one-question ADAS browser probe passed8/8. It now answers with supported driver-assistance examples, King/King Knight/Lounge applicability and automatic-only stop-and-go. Acknowledgement began484ms after typed submission and its1.365s clip completed. Answer audio began5.320s after submission; the saved turn is explicitly an answer cohort. The graph took2.000s, but a generic spoken slide-jump bridge occupied2.442s before answer delivery. One sample establishes no percentile. The next bounded change removes that extra bridge only from runtime-v1 question jumps, retaining evidence display, interruption ownership and explicit return.

## Latest full review and current source correction

The fourth unchanged 100-question pack, on `20649a4`/v5, produced **83 supported, 9 partial, 3 unhelpful, 2 unsafe and 3 provider failures**. All-request HTTP text median was **2.710 s**, p95 **9.736 s**. The shared recorded delta was **$0.6042**, including the concurrent browser probe. The independent reviews and original responses are retained in `qa100-repaired-final/`. The semantic target remains unmet; the increase in supported answers does not excuse either unsafe answer.

The wheel answer repeated a bad approved flattened website row: EX(O) styled road wheels became both styled and ordinary steel-with-cover wheels. Manufacturer page 15 explicitly separates ordinary E/EX road wheels, styled EX(O) road wheels and spare wheels. Corrective **v6** introduces F249/F250/F251 from those exact rows. F252 retains the genuine Pune FAQ listing but makes its uncertain correspondence to the manufacturer lineup explicit. That listing cannot license equipment borrowed from a different city/source. V6 preserves 181 approved facts, all six approvals, all spoken content/media and the original v5 snapshot. Assembly blocked all outbound sockets. The earlier unsafe answers remain in their original cohort.

The final direct-answer ADAS browser probe on `20649a4`/v5 passed **11/11**. Its acknowledgement began at **434 ms**, useful answer audio at **3.703 s**, and graph completion took **2.913 s**. Result-ready→audio fell from **3.110 s** in the earlier probe to **580 ms**, after removing the generic spoken jump bridge. Explicit Continue returned to the exact original sentence. This single typed/muted sample is separate from the earlier app revision; same-version dashboard aggregates mix those revisions and cannot establish the change's p95. Browser counters reached **25 reasoning / 32 TTS**; the finite speech cap is exhausted, with its original spend baseline preserved.

The current code follow-up targets remaining precise-limit, completeness and source-scope failures. New source publication and passing offline regressions alone do not establish that the next live answers meet acceptance.

## Focused source-scope replay

The40-case difficult subset on `f06d8b9`/v6 produced **30 supported, 7 partial, 1 unhelpful, 1 unsafe and 1 provider failure**. HTTP text median2.531s,p957.493s; recorded estimate$0.2338 without concurrent paid work. Wheel comparisons and SX(O) source handling now work. Remaining failures include an unsupported “unpublished future lineup” sentence, a connected-car answer that switches citations to omit the Echo purchase dependency, and an entirely discarded repair despite valid surviving sentences. This is not a new full100 score. Original answers and independent reviews remain under `qa-focused-source-scope/`.

Correctivev7 changes only F080→F253 canonical scope: the same official highlights page lists King Knight, labels its dedicated section King Knight and describes identical styling in the FAQ using “edition”. This is a reviewed product-specific identity decision, not a global rule that strips Edition from trim names. Existing narration, slides, audio, all six approvals and old snapshot bytes remain intact. Current graph/ranking/provenance-display repairs require independent checks and live verification.

## Fifth full replay: stricter safety exposed over-rejection

The unchanged100 cases on `0cd642c`/v7 returned **78 supported,9 partial,9 unhelpful,0 unsafe flagged,4 provider/deadline failures** after independent review. HTTP text median2.884s,p956.823s; estimate$0.5569 with no concurrent paid activity. Current cumulative app estimate$7.8827 is not a provider invoice. Independent review moved q076 from initially supported to partial because a today-price answer omitted its material current-validity caveat; the initial review and all original answers remain preserved. The API flagged only three provider failures: semantic review also counts q043’s repair timeout. Raw flags are not the acceptance score.

All nine completed calculations independently recompute correctly; one calculation failed at the provider. Five of seven live-source checks verified the requested source, while two supported answers honestly reported verification limits and separated saved fallback facts. Zero flagged critical unsafe answers does not mean every statement was fully supported: two partial answers added unlicensed financial causal explanations. The `semantic-summary.json` also separates factual, calculation, source-check and clarification/limit expectations.

This score is below target. The new uncited guard stopped an unsupported future-lineup claim but discarded useful precise limits and benign interaction. The actual `all-black` adjective was mistaken for a universal-trim quantifier. A source-backed lineup-equivalence limit was checked as positive fitment. Price-page discovery picked an unrequested city by alphabetical order. These concrete causes are being repaired and retested; no score is retroactively improved. Private evidence: `qa100-v7-dependencies/`.

## Focused limits replay on c7ec71a

The next40-case subset returned **28 supported,7 partial,4 unhelpful,0 unsafe flagged,1 provider failure**. It contains the22 non-supported turns from the fifth full replay,15 positive controls and3 required context turns. HTTP text median **3.302s**, p95 **7.034s**; recorded estimate **$0.277**, no concurrent paid work or TTS. The cumulative estimate is **$8.1597**. Immutable answers and independent reviews are under `qa-focused-v7-limits/`; this is not a replacement100-case score.

Specific limits, King Knight styling, source-lineage wording and future-offer/renewal uncertainty improved. City discovery no longer chose an arbitrary locality. The credit cooldown was exercised by actual provider failures; a subsequent Runware completion still failed semantic validation, so provider completion is not counted as useful delivery. Remaining issues include comfort retrieval, valid mixed-polarity comparisons, over-rejected clarification/assistant-behavior text and incomplete requested facets.

Both the earlier full-run and this focused q052 timeout had already completed the audited EMI calculation correctly: ₹19,530.34/month on ₹800,000 at8% annual interest over4years. The second model composition used the remaining deadline, preventing validation/delivery and dropping that result from the failure response. This is an orchestration failure despite a correct tool result. A bounded reserve for validation is being tested; no elapsed deadline or cancelled turn may be revived.

## Focused delivery replay on047f4e2

The same40 questions returned **30 supported,4partial,3unhelpful,2unsafe,1provider failure**. HTTP text median3.622s,p957.790s; estimate$0.2568,total$8.4165. Original answers and reviews remain under `qa-focused-v7-delivery/`. Initial first16 review was preserved, then adjudicated consistently with prior cohorts: claiming SX lacks electric seat adjustment without explicit negative evidence and claiming official model-year specifications are unavailable are unsafe assertions, even when other sentences are useful. This is not a new100 score or a pass.

The actual EMI turn succeeded in4.014s with normal Gemini composition; it did not exercise the new deadline fallback. Three source checks verified requested content, two gave honest verification limits, and missing-city pricing now asked a useful clarification. Exact conditional comparisons, boot measurement uncertainty and personal-comfort wording improved. Remaining failures expose shared validation causes: mixed negative-feature scope, unsupported causal premises in own limits, discarded grouped wheel clauses, a suppressed connected-feature repair and over-rejected benign interaction. Corrections are active; no paid speech is added.

Review labels use the same rule across cohorts: **supported** requires a useful response to the central requested facets with their material conditions; a specific honest limit or needed clarification can qualify when the evidence/inputs are unavailable. **Partial** means useful supported content remains but coverage is incomplete or a noncritical subjective explanation is unsupported. **Unsafe** takes precedence for an unsupported quantity, fitment, policy, model-year/publication/availability assertion or claim of fresh verification. **Unhelpful** means no useful task-specific answer or clarification survives. **Provider failure** identifies an actual availability/deadline failure that prevents useful delivery. A failed optional repair does not automatically erase useful surviving content. Fresh-source success and semantic usefulness are reported separately; HTTP status and model-generated flags do not determine these grades.

## Repair details

- The overview leads directly into selected slide narration. Missing model replacements use explicitly marked reviewed-route speech. Published inputs and demo-version checks prevent draft edits or a new publication from silently changing a running visit.
- Runtime reasoning sees compact approved assertions and their conditions. Full provenance tables remain available for audit, but cannot serve as permission to borrow an unrelated feature from a large quote.
- Calculations preserve quoted inputs, units, derivation and assumptions. Explicit approximate currency wording can use nearest-rupee rounding. Verified tool results can rescue a missing model rendering; a caveat alone is not counted as a useful calculation answer.
- Selected-trim qualifications and exact negative applicability are preserved. Held or rejected assertions remain ineligible. Opaque ordering such as “SX and above” is not expanded into invented trim coverage.
- Cancellation, stale output, real question waits and audio timing have separate checks. Caption-only fallback does not count as first answer audio. Align overlays are removed on navigation; mobile evidence overflow has a cue only when needed.

Additional deterministic grounding probes found unit/feature and negative-clause loopholes before the repeat batch; 28 independent controls pass. Follow-up validation remains necessary for useful answers, source attribution and successful full journeys.

## What muted acceptance cannot prove

The controlled browser uses real application state, prerecorded playback, provider reasoning/tools and streamed speech bytes. Synthetic silent capture and injected transcript/onset events exercise control flow without using Anand's physical microphone or Chrome window. The browser remains muted.

Those checks do **not** prove physical listening accuracy, acoustic speech-onset delay, speaker echo cancellation, perceived voice warmth or human interruption quality. Three separate prerecorded synthetic utterances passed actual transcription intent/entity checks, which is still not a human microphone benchmark. These limits remain explicit even if every automated case passes.

[Build/run workflow and code references](DEMO_BUILD_AND_RUN.md) · [Issue log](issues/2026-09-19-creta.md) · [Approved acceptance targets](plan-runtime-experience-2026-09-19.md)
