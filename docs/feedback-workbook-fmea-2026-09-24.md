# Feedback workbook QA and FMEA — 24 September 2026

Scope: the workbook's blank Studio entry, selected 1–5minute narration, Rehearse upload chat and white viewport-contained player. Product context: `PRD.md`, the exact cell map in `docs/feedback-workbook-2026-09-24.md`, `Learning.MD`'s duration break issue and diagrams01–05/08. This is a manual twelve-category scan authorized by the continuing code-QA request. Tests are mock, isolated and outbound-blocked; the existing production environment is preserved.

## Findings resolved before release

Scores describe the reproduced or code-confirmed failure before its fix; RPN=severity×occurrence×detection. They are not estimates of residual production failure rates.

| Flow / failure | Effect and cause | S/O/D · RPN | Fix and evidence |
|---|---|---|---|
| Selecting1 or 2minutes still enforced 180seconds | The requested short demo could not publish because the earlier fixed minimum remained in multiple stages. | 6/7/7 ·294 · P0 | One validated duration drives preparation, every-language recorded publication and the pinned runtime route. Duration tests cover all five values, invalid inputs, no-op updates and old-publication preservation. |
| Mobile feedback composer outside its grid row | The parent boxes fit but a later stylesheet's 560px preview minimum pushed child controls below the screen. The full app also let the left rail's intrinsic minimum height enlarge the grid on short landscape windows. | 6/8/7 ·336 · P0 | Scoped Rehearse grid overrides, an explicit bounded grid row/scrollable rail and child-level bounds checks now require the heading, upload, input and Send controls inside the viewport. |
| Studio top nav resumed a saved demo | A user beginning a new demo saw another demo's fields. The navigation chose the first stored record. | 5/8/6 ·240 · P0 | Unsaved blank state, one shared creation promise on the first mutation, retained explicit-demo URLs and stale-navigation guards. |
| Changed duration reused an old “ready” recording status | A longer old WAV satisfied the shorter minimum before the preparation identity was checked. | 5/4/7 ·140 · P1 | Duration mismatch requires preparation before recorded-ready. Actual3→1minute Build prepares a new 165-word target, returns for review and never records/publishes the changed draft. Manual incomplete edits remain exact and blocked. |
| Feedback retry added the same attachment again | A partial multipart failure, provider failure or timeout could leave a saved source while the UI retained the file for retry. | 5/5/6 ·150 · P1 | Align-only byte-identical reuse matches filename, role, size, kind and SHA-256 under the demo lock. Busy work is rejected early; concurrent retries retain one ID. Accepted partial uploads are kept safely, not rolled back after a worker may have referenced them. |
| Rehearse attachment without model revision was never read | The deterministic uploaded-evidence fallback ran only for context=align. | 6/5/6 ·180 · P1 | Rehearse uses the same Understand fallback and human review path. Upload retry contract covers the no-action fallback. |
| Short embedded slides left almost no visible image pixels | Parent/control bounds passed while heading/footer/caption reserves consumed the tiny landscape slide. A transition-time screenshot also showed two simultaneous slides. | 5/6/7 ·210 · P0 | Compact slide decoration for short stages and bounded caption space; the composed-app test waits for one settled slide and requires both native-fit pictures to retain visible height. |
| Dark text on saturated blue controls lacked contrast | Literal color changes could make Send and active microphone icons hard to see. | 4/6/6 ·144 · P1 | Lightly tinted palette backgrounds keep dark text. Measured Send/mic contrast: Marine 10.82:1, Sage 9.36:1, Graphite 10.71:1; dark primary actions retain white text. |

No new unresolved P0/P1 finding remains in this change set. The earlier hosted-builder access decision C7 and Cloud alternate-language voice decision C8 remain pending and are not claimed fixed.

## Mandatory category walkthrough

| Category | Review conclusion |
|---|---|
| unhandled_error_paths | Sources/feedback errors remain visible; failed feedback retains text/files. Navigation guards prevent late responses remounting a closed workspace. Recordings missing or too short retain the prior publication. |
| external_dependency_failures | No new external service or model call was added for UI or the second picture. Existing bounded Author repair/completion and recording failure contracts pass. Paid model and acoustic quality are outside these mock checks. |
| race_conditions_and_state | Lazy draft creation shares one promise; abandoned views cannot take navigation back. Duration changes reject active workers, reset affected draft approvals and preserve the pinned published duration. Feedback SSE/refresh deduplication and player disposal are covered. |
| resource_exhaustion | Uploads remain bounded by the existing limit and copy/hash in 1 MiB chunks. Duplicate checking needs a temporary full-file copy and hashes matching stored candidates under the demo lock; it does not load whole videos into memory. The existing small-instance capacity limitation remains. |
| security_access_control | No new endpoint, privilege, credential, public network tool or external source is introduced. API duration validation rejects booleans, fractions, strings and out-of-range values. Browser fixtures block external requests and microphone capture. C7 is inherited. |
| data_integrity_partial_writes | Original workbook and previous published artifacts are preserved. A partially accepted multipart upload intentionally remains in Sources for safe retry with the same IDs. Separate Sources uploads keep their existing behavior. No rollback can erase a source already used by a timed-out worker. |
| observability_gaps | Compact duration status distinguishes drafting, estimated and measured speech. Feedback shows progress/errors and persists conversation. Mock placeholders are labelled. Exact suite counts and file/log hashes are recorded in the gate inventory. |
| scale_and_load_failures | Layout tests cover desktop, tablet, portrait, landscape and short windows. Caption reserves are bounded so they cannot consume every picture pixel. No multi-worker or high-concurrency capacity claim is made for the existing t3.micro. |
| billing_credit_mismatches | All validation uses MOCK_LLM=1 with blocked provider sockets. Longer selected duration can require more source-backed speech/audio at a later user-requested real Build; it does not silently run paid work on selection or viewing Rehearse. |
| retry_idempotency_issues | Same-content feedback uploads reuse their ID, including partial failures, timeout and concurrent retry. Different bytes/names/roles remain distinct. Author completion remains bounded; failed requests do not cause an unbounded retry loop. |
| config_feature_flag_drift | Legacy demos default to three minutes. Published bundles retain their own selected duration even after draft preferences change. All palettes use the same white renderer; old dark static design samples remain historical references. |
| edge_cases_from_prd | All five durations, selected alternate languages, no hero, one available supported image, paired native image ratios, trusted/missing anchors, long conversations, CTA states and preserved manual edits are covered. Portrait guidance does not pretend to lock device orientation. |

Coverage: 12/12 categories checked. No unrelated security, billing, service or data-model feature was added. The code review included independent passes over duration/review transitions, upload retries and visual audit ownership.

## Verification boundaries

The full new-demo journey exercises actual source API→Read→review→Build→recorded-duration gate→Bundle→runtime answer/cache/review→rehearsal→browser/session flow with fixture providers and real silent WAVs. It measures 194.22seconds at the default three-minute setting. This verifies mechanics, not new model wording, semantic entailment or speech quality. Physical phone rotation, soft-keyboard behavior and acoustic playback are unverified; desktop Chromium viewport emulation is the UI evidence.

Nav “width” remains the documented C9 interpretation: reduce height40percent while keeping the full-width bar. A single supported picture remains single; a second is only added from existing full pixel-audit coverage. The source workbook was read, not modified or uploaded.
