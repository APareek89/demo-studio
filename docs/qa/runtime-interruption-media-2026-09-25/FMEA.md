# FMEA — immediate speech hold and reviewed answer pictures

Status: **independent code review and core gates complete, 2026-09-25.** No new unresolved code blocker was found after the fixes below. This receipt does not claim paid-provider, physical acoustic, load or deployed acceptance.

Scope: the current runtime-interruption/media diff against `e80a180`, including nine application files (`knowledge.py`, `runtime_graph.py`, `runtime_visuals.py`, `live-voice.js`, `voice-worklet.js`, `player.js`, `answer-visual.js`, `walkthrough.js`, `slide.js`) and associated regression contracts. Product context: current `PRD.md`, runtime diagrams, `docs/ARCHITECTURE_FLOW.md`, `Handoff.MD`, and the microphone/gallery/session incidents in `Learning.MD`. The user requested prompt interruption, cited-answer pictures, explicit picture navigation and worthwhile retrieval improvements while preserving workflow and guardrails.

Application diff: nine files, 495 added and 52 removed lines against `e80a180`, including the two new helpers. Product intent is the runtime voice, reviewed gallery and source-grounding flow in `PRD.md` and `docs/ARCHITECTURE_FLOW.md`.

This is a one-worker EC2 feedback service with local JSON/media and SQLite, cloud sync off, approximately 913 MiB RAM and 2 GiB swap. No new service, dependency, provider, database or stored schema is introduced. LiveKit is discussion/recommendation only.

## Findings corrected during independent review

| Finding | Customer effect | Required correction | Verification status |
|---|---|---|---|
| Local voiced frames shortened a qualified partial's silence grace | Old narration can resume before final recognition arrives | Preserve the recognized-progress deadline while raw local frames refresh the hold | Fixed; code re-read and owner 26/26 hold contract, including 2.4-second tail-grace case |
| Caption/browser fallback deadlines progressed during a provisional hold | Fallback logs a complete unheard line or advances while customer is still speaking | Pause/restore remaining completion deadline under the same run/token; cancellation stays final | Fixed; code re-read and four owner deadline/cancellation regressions in 26/26 |
| Image loads/Q&A results could start new visual motion after onset | Audio pauses but the picture still changes while the customer speaks | Await the owned hold at presentation boundaries and pause newly created motion | Fixed; decoded-image attachment, line preparation and answer-result boundaries re-read; root image/player contract 42/42 |
| `prepareLine` callback argument shape briefly differed across owners | Gallery path can skip the newly added hold callback | Accept the same bare playback callback at caller and renderer | Fixed; exact caller/callee signature re-read; root callback-ownership regression included in 42/42 |
| Failed image load still used an affirmative show acknowledgement | Customer hears “Here is…” without a displayed picture | Require decoded image success; neutral visual-navigation fallback on failure | Fixed; gallery/native boolean propagated to visual-only answer path; root 42/42 |
| HTTP missing-image result lost its actual meaning; recap retained it as an unresolved fact | Picture navigation became generic unsupported-answer/callback flow | Preserve visual-only response, avoid factual unknown/callback tracking, clear recap open-question entry | Fixed; both unavailable branches clear `openQuestions`; root 42/42 |
| Broad title/other picture parts licensed a different caption qualifier | Request for first-row feature could point at second-row label | Require literal owned-feature qualification and reject contradictory location/negated applicability | Fixed; independent 23/23 visual contract includes shared-title, shared-photo qualifiers and negative variant regression |
| Republish or disappearing-media race cleared image but kept affirmative visual-only response | Old visit can claim a picture was shown after its selection became invalid | Keep factual pinned speech, but neutralize visual-only success when re-selection fails | Fixed; independent 23/23 visual contract includes publication and disappearing-media races |
| Per-fact extraction parsing before result limiting | Repeated local reads waste CPU and memory on each answer | Select first; per-request source memo; retain independent copied contexts and exact evidence | Fixed; independent 12/12 retrieval contract and five BMW deep-equality probes |

## Residual limitations and scoring

S/O/D follow the repository anchors; RPN is their product. These are limits, not a claim that physical or load acceptance passed.

| Component | Failure mode | Effect | Root cause | S | O | D | RPN | Priority/action |
|---|---|---|---|---:|---:|---:|---:|---|
| Public runtime | Anonymous visitors can consume paid runtime capacity | Owner can incur spend or shared-instance contention | Existing feedback deployment has no per-visitor rate/ownership limits | 5 | 4 | 6 | 120 | P1 inherited scope: new classifier adds no paid calls; account/rate-limit architecture remains separate |
| Microphone onset | Sustained background speech or a voiced noise temporarily pauses playback | Brief unwanted pause; a sufficiently relevant TV sentence may still qualify as speech | Local acoustic structure plus text relevance do not identify the speaker | 4 | 4 | 7 | 112 | P1 acoustic measurement limit: test actual devices/TV/throat clearing; never claim noise immunity |
| Small EC2/browser devices | Untested concurrent sessions or low-power microphone processing | Slower responses or audio/frame delay | Existing one-worker service and no physical device/load test | 4 | 3 | 6 | 72 | P2: report bounded mock/browser scope, no load/acoustic SLA |
| Published photo coverage | Exact requested feature has only an illustration or no approved caption | Honest “no reviewed image” response despite available generic product photos | Fail-closed ownership and visual-proof requirements | 3 | 5 | 4 | 60 | P2 product limit: retain disclosures; more coverage needs ordinary source/visual review |
| Optional cloud backend | S3-only picture not yet restored locally cannot pass image existence check | Image navigation unavailable until media is local | Runtime helper deliberately avoids remote fetches; current deployment is cloud-off | 3 | 2 | 3 | 18 | P2 future configuration limit; do not silently migrate storage in this task |
| Canceled HTTP runtime request | A superseded turn logs an ASGI exception during mock server shutdown | Noisy server error while the browser correctly discards the old request | Existing `delivery_plan` raises `InterruptedError`; HTTP boundary differs from live socket boundary | 2 | 4 | 2 | 16 | P2 inherited diagnostic issue: normalize expected supersession at the HTTP runtime boundary in a bounded follow-up |

## Mandatory category coverage

| Category | Checked flow and controls | Finding/status |
|---|---|---|
| unhandled_error_paths | Rejected playback promises, failed/slow image loads, missing/invalid source JSON, cancellation during awaited work | Image failure and fallback-deadline fixes verified; inherited shutdown supersession logging recorded above |
| external_dependency_failures | STT final delayed/missing, voice stream outage, HTTP media failure, no new external classifier | Bounded hold/no-progress recovery; exact voice still locked; physical acceptance not established |
| race_conditions_and_state | Final/partial/local events, manual Pause/Stop/Continue, late output resume, duplicate final, capture generation, republish and photo disappearance | Grace, fallback, presentation and publication fixes re-read; focused ownership regressions pass |
| resource_exhaustion | Microphone history, capture pre-roll, queued output, watchdogs, selected evidence/source memo | Ten-frame local window, existing 400-frame pre-roll, request-local memo and selected limit; no unbounded new global cache |
| security_access_control | Returned URL ownership, path/symlink traversal, bundle pin/version, public proxy and private data boundary | Demo-local known image IDs/URLs only; no arbitrary coordinates, network URL or new endpoint; no new auth surface |
| data_integrity_partial_writes | Published bundle immutability, snapshot semantics, FAQ/unknown learning, independent context objects | Showing pictures creates no fact/unknown/cache answer; memo retains complete evidence and nested-object independence |
| observability_gaps | Onset/stop timestamps, turn/delivery diagnostics, image status, source hashes and baseline receipts | Existing metrics receive provisional onset identity; physical latency is not inferred from mock clocks |
| scale_and_load_failures | Local parsing cost and small-instance behavior; no concurrency architecture change | BMW source reads 5–31 → 1 per query; local diagnostic speedup only; shared-instance/load limit retained |
| billing_credit_mismatches | Early hold, explicit image navigation, cached factual answers and free QA | No Gemini/per-noise classifier; pure show bypasses reasoning; free contracts use mock/isolated storage/blocked sockets |
| retry_idempotency_issues | Duplicate/stale transcript finals, canceled turns, cache re-selection, repeated requests, resumed media cursor | Same capture/turn ownership remains; rejected provisional sound resumes existing clip instead of making a new answer |
| config_feature_flag_drift | Live versus HTTP, voice versus text, gallery versus native, mocked versus paid, local versus optional cloud | HTTP visual-only and native failure handling reviewed; cloud-only limitation explicit; deployed config remains unchanged |
| edge_cases_from_prd | No citation/no claim, approved exact photo/tag, second photo on same slide, changed publication, caller stops mid-question, long question | Existing workflow/agents/guardrails retained; exact qualification and long-question regressions pass |

**Coverage: 12/12 categories checked.** No new unresolved failure found in security/access, partial-write integrity, retry/idempotency or billing. Six residual limits are recorded: 0 P0, 2 P1 (existing public capacity and unmeasured acoustics), 4 P2. The P1 acoustic action is device acceptance using actual speech, throat clearing and background TV against `LiveVoiceClient.observeSpeechFrame`; synthetic periodic audio is not that evidence. Public request budgets/rate limits remain separate work in the existing runtime endpoints, not a hidden service migration.

## Final verification

Independent actual-working-tree run: `qa_deck 445/445`, `qa_accept 24/24`, `smoke 3/3`, full mock `28/28` with 194.22 seconds of synthetic measured narration; `retrieval_io 12/12`, `runtime_visuals 23/23`, `knowledge 60/60`, `runtime_graph 130/130`, `faq_cache 27/27`, `runtime_transmission_conditions 17/17`. Every suite used `MOCK_LLM=1`, fresh isolated `DEMO_STUDIO_DATA`/`DEMO_STUDIO_GRAPH_DB`, blank provider keys, cloud off and blocked outbound sockets; zero outbound attempts. Numeric literal-IP resolution was emulated locally for the SSRF contract; no DNS request was permitted.

Receipts: `final-results.json`, per-suite logs, `source-hashes-after.json`, and `source-stability.json`. All 89 application files remained unchanged throughout the run. The initial deck run was 444/445 only because a source-string assertion expected the pre-hold timestamp syntax; its log is retained, and `qa_deck-rerun.json` records the corrected structural assertion and passing 445/445. No application change was made between those runs.

Audio owner's final receipts recorded in `speech-receipt.json` and the adjacent `*-final.log` files (independent original review/provenance under `output/runtime-interruption-media-2026-09-25/review/`): immediate hold `26/26`, live voice `96/96`, speech/noise `31/31`, session save `18/18`, listen `16/16`, recovery `17/17`. Integrated live browser `42/42` reached the natural closing, CTA and recap; `../speech/receipt.json`, `browser-results.json` and `browser-held-audio.json` retain that owner's final evidence. These were executed by the audio owner and independently reviewed here. The server shutdown emitted one `InterruptedError: Turn superseded`, verified as an existing HEAD code path; no claim of zero backend exceptions is made.

Root's final verification: image/player `42/42` in `../runtime_image_player-final.log`; gallery `320/320` in `../gallery-final/gallery-browser.json`; native player `87/87` in `../gallery-final/player-browser-current.json`. Browser/gallery execution is separately owned by root and is not claimed as an independent run here. The root reports source syntax and diff whitespace checks passed.

Frozen before baseline remains separately recorded under `output/runtime-interruption-media-2026-09-25/baseline/`: `qa_deck 445/445`, `qa_accept 24/24`, `smoke 3/3`, full mock `28/28` with 194.22 seconds of synthetic narration; zero outbound attempts. No paid call, AWS write, protected demo or port 8896 was used. No commit or deployment is asserted by this review.
