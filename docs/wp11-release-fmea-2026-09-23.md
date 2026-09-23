# WP11 release QA and FMEA — 23 September 2026

The release includes WP1–WP11 and the approved Marine slide-first player, compared with deployed application `63abb8569eba605199e400aa6c7524b881609ff4`. The subsequent original deployment receipt on `master` did not change that application. Anand explicitly authorized this full review, GitHub publication and deployment to the existing AWS host. This review does not certify that the software has no bugs.

**Failure modes:** 11: two P0, five P1 and four P2 before fixes. Eight are fixed; the inherited public-access issue and two explicit pilot limitations remain.

## Review basis

- Product: `PRD.md`, the dated work-package brief and latest user decisions; six approvals, grounded claims, customer learning, three minutes of measured narration, stable on-slide layout and controlled microphone ownership.
- Architecture: `docs/ARCHITECTURE_FLOW.md`, the nine Mermaid flows, `Learning.MD`, `.power-coding/config.json`, deployed systemd/Caddy configuration and read-only health inspection.
- Host: existing Mumbai EC2 `t3.micro`, approximately 913 MiB RAM, 2 GiB swap, 20 GiB disk; one uvicorn worker, shared local files and SQLite. Dependencies remain unchanged. Chromium and Poppler exist; scanned-image OCR remains unavailable.
- Three independent work streams reviewed backend/runtime, browser/deployment lifecycle and all free contracts/full journey. Findings were reproduced in isolated fixtures before changes. No external source instructions were treated as authorization.
- Tests use `MOCK_LLM=1`, fresh `DEMO_STUDIO_DATA` and `DEMO_STUDIO_GRAPH_DB`, cloud sync off, blocked outbound sockets and muted isolated browsers. No paid model/speech calls or acoustic test was performed. Local port 8896 and the protected demo were not operated or edited.

## Findings

Scores are pre-fix estimates at the existing pilot's scale; S = severity, O = occurrence, D = difficulty detecting before a customer encounters it. RPN = S × O × D; configured thresholds P0 ≥200, P1 ≥100, P2 <100. These priorities are numerical review labels, not claims of active exploitation or measured incident rates.

| ID | User-facing failure and cause | Origin | S | O | D | RPN / priority | Action / state |
|---|---|---|---:|---:|---:|---|---|
| F1 | Anyone who can reach the hosted builder can list demos and call unprotected edit/build/session routes. Confirmed with read-only anonymous requests and route inspection; no anonymous mutation attempted. | Inherited; authentication is excluded from the existing PRD | 9 | 3 | 8 | 216 / P0 | **Open C7:** recommend password protection. Asked Anand because protecting the entire host changes viewer access too; preserve existing access until decided. This release must not be described as access-controlled. |
| F2 | Leaving Play or Rehearse through navigation can leave audio, capture/socket work and pending mounts owned by a detached player. | Inherited | 6 | 5 | 7 | 210 / P0 | **Fixed:** route-owned cleanup and hash/epoch guards; idempotent destroy cancels preloads, subscriptions and active work. Actual browser navigation and delayed-mount checks; nonempty active visits are saved under the same ID without inventing completion. |
| F3 | Customer FAQ learning during Voice resets approval, yet the old graph still published that changed content. A check outside the final write also leaves a smaller race. | WP11 makes the old late-gate omission reachable | 6 | 4 | 8 | 192 / P1 | **Fixed:** recheck after Voice and hold the shared per-demo reentrant lock across final approval, input reads and publication. Expected review invalidation returns to Align and preserves old bundle/version. Publication contract 8 groups. |
| F4 | A failed recap save is swallowed, so the customer sees a recap that was never persisted. | Inherited | 5 | 4 | 9 | 180 / P1 | **Fixed:** explicit save state and retry of the same frozen content revision; equal pending/successful revisions coalesce, changed revisions serialize, and Done includes later recap lead details. Failure after Done remains visible. |
| F5 | The optional second search page can exhaust the deadline and erase a complete usable first-page answer. | WP11 | 5 | 5 | 6 | 150 / P1 | **Fixed:** reserve a return margin; retain completed cited passages with a coverage warning; cancellation still aborts. Real tools-node timeout regression included. |
| F6 | A large film is read wholly into app memory before its size check on a roughly one-GiB server. | Inherited | 6 | 3 | 7 | 126 / P1 | **Fixed:** known-size precheck, actual-byte limit, one-MiB streaming copy in a worker, atomic completion, partial/unregistered-file cleanup. Upload contract 19 groups. |
| F7 | A stalled HTTP Q&A fallback can remain on Checking indefinitely even though the WebSocket route has a deadline. | Inherited | 5 | 3 | 7 | 105 / P1 | **Fixed:** bounded fallback using the existing answer deadline, abort on timeout/supersession/teardown, existing honest failure UI. |
| F8 | A delayed preload timer creates media after the player was already destroyed. | Inherited | 3 | 4 | 7 | 84 / P2 | **Fixed with F2:** retain and cancel the timer; callback and destroy check ownership. |
| F9 | Concurrent builds/sessions across several demos can exceed this small instance's resources; locks are per demo/process, not a global admission queue. | Inherited | 6 | 2 | 6 | 72 / P2 | **Residual capacity limit:** pilot scale only; no production load certification or multi-worker support. Upload memory is now bounded, but a queue/instance-sizing decision is separate work. |
| F10 | Google Cloud alternate-language speech can select the configured main-language speaker. | Inherited | 5 | 2 | 7 | 70 / P2 | **Open:** define language-specific Cloud voice identities before relying on that alternate-language path. The current Sarvam voice is unaffected. No provider call was made to claim compatibility. |
| F11 | Adjacent brand/technical aliases can yield repeated wording such as a repeated Hyundai name. | WP6 | 3 | 6 | 3 | 54 / P2 | **Fixed:** consume only adjacent equivalent aliases and duplicate brand prefixes; keep the approved replacement map, citations, conditions and technical bypass intact. Plain-language contract 25 groups. |

## Mandatory coverage — 12/12 categories

| Category | Reviewed customer flows and outcome |
|---|---|
| unhandled_error_paths | Read/Coach/Author repair, Build publication, runtime delivery, session save and upload failure. F3/F4/F6/F7 fixed. Prior artifacts and visible recovery retained. |
| external_dependency_failures | Provider retries/circuits, customer/public sources, fetch deadlines, transport fallback and optional second-page failure. F5/F7 fixed. Live provider availability is untested. |
| race_conditions_and_state | FAQ count/edit/reject/audio adoption, unknown merging, approval during Voice, delayed mounts, stale answers and microphone ownership. F2/F3/F8 fixed; one-process ownership remains explicit. |
| resource_exhaustion | Uploads, audio buffers, page byte/count limits, two-round/four-call tool budget, voice workers, preload lifetime. F2/F6/F8 fixed; F9 retained as capacity limit. |
| security_access_control | Existing public builder, server-only credentials, SSRF/DNS/redirect controls, media path boundaries, fetched evidence vs instructions and cache eligibility. F1 open; no new credential signature match in tracked release changes. |
| data_integrity_partial_writes | Atomic JSON and stream writes, failed source registration, published snapshots, approval/minimum gate failures and old-bundle retention. F3/F6 fixed. No disk-full/power-loss certification is claimed. |
| observability_gaps | Stage errors, repair/tool traces, failed saves, timeout coverage and expected review pause. F4/F5/F7 fixed. Existing logs do not constitute an external alerting service. |
| scale_and_load_failures | Small-instance memory, single worker, per-demo lock scope and concurrent sessions. F6 fixed, F9 open. No public load test performed. |
| billing_credit_mismatches | No customer billing mutation path was added. Paid model usage/retries and caching inspected; search-fee exclusions stay labelled. F1 remains a provider-cost exposure; all release checks are free. **No separate billing defect reproduced.** |
| retry_idempotency_issues | FAQ identity/count vs approval, permanent rejection, source retries, cancellation, session retry snapshot/ID and duplicate-save handling. F4 fixed; cache/session contracts remain active. |
| config_feature_flag_drift | Local/host environment, pinned voice/audience, technical bypass, runtime site settings, browser selection and mock-only isolation. Stale local-only FMEA infrastructure context corrected; F10 remains. |
| edge_cases_from_prd | Six approvals, ≥180 seconds in every published language, explicit shorter tours, fundamentals before delighters, missing evidence/images, proxy labels, empty FAQ, unknowns never facts, mobile/short windows and stable slide geometry. Targeted and end-to-end contracts run; F3/F11 fixed. |

## One full mock dry run

`evals/release_mock_contract.py` creates a new temporary demo through the actual API, uploads handbook evidence and an image, runs Read through Coach/Plan/Author/Deck/FAQ, approves all six cards, runs Voice/Build and publishes. Real WAV fixtures total **194.22 seconds** through the actual voice text-hash cache and the **unmodified 180-second measured publication gate**. The test then exercises Explore beyond three stops, clean question caching/audio hits before reasoning, customer unknown learning, FAQ approval/edit/rejection, explicit rehearsal, session idempotency/summary/share, and the real Marine browser player on that exact newly published bundle. Typed Q&A uses real HTTP runtime fallback, and Stop saves the actual player's text-mode session.

The model seams use explicit cited fixtures; the WAVs are silent fixtures, not provider-generated speech. Every browser HTTP request is fulfilled by the in-process FastAPI app; external requests and microphone access are blocked. This validates orchestration, data boundaries and UI integration, not model-writing quality, acoustics or external-site availability. Legacy plumbing smoke retains its labelled unit duration fixture; this separate release journey does not bypass the duration gate.

## Verification receipt

Final local and staged-host gate counts are recorded in `Loop.MD` and the AWS release receipt. The full per-script inventory is attached beside this report as `wp11-release-gates-2026-09-23.json`. Earlier exact-technical-wording tests now request the technical audience explicitly; everyday substitution has its own regression suite. A legacy confirmation-metadata unit labels its duration fixture; publication/minimum and the full release journey enforce the actual gate.

## Release and rollback boundary

Deploy only committed source to a fresh release directory, reuse the existing compatible environment and browser installation, and preserve the shared data/credentials. Run isolated checks on the staged code before changing systemd. Stop the service only for a consistent data/SQLite backup and controlled cutover; validate health, source hashes, stored data hashes and HTTPS afterward. A failed cutover disables only the new drop-in and restarts the previous release. Never overwrite post-release customer data during code rollback.

Paid live Read/Build/Q&A, physical cup/noise testing, exhaustive image-only PDF extraction, alternate-language Cloud voice validation and production load testing are skipped. Selective Align rebuild routing remains pending exactly as requested. F1/C7, F9 and F10 are explicit limitations; passing QA is not a zero-defect guarantee.
