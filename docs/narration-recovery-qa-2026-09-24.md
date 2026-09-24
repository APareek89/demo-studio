# Three-minute narration preparation and recovery — 24 September 2026

The reported128.3-second draft reproduced the correct180-second publication rejection, but the app only enforced duration at publication. Planning targeted342 words at an optimistic1.9 words/second, one short delivery-batch ceiling limited an entire story stop, and Build reused the same recordings. Prior passing release fixtures supplied already-long scripts, so they did not expose this preparation failure.

## Implemented behavior

- New plans reserve495distinct supported words by default (180 ×2.5 ×1.10). Matching recorded main/selected-language durations can raise the content target; the voice/language/duration/persona identity preserves that calibration across unvoiced retries. This is a drafting margin, not a duration guarantee or a playback-speed adjustment.
- A reviewed story stop can hold several complete cited thoughts. Existing delivery splitting keeps short role ceilings, unique IDs and the original allowance; whole-stop identity survives Bundle and runtime routing. Unreachable extra tail groups, question-shaped speech, deeper-only text and repeated exact speech cannot fill the content target.
- Author’s existing single repair receives the required global content deficit. Unsupported expansion remains a visible evidence gap; no citation or human approval rule is relaxed.
- Align offers Prepare three-minute narration above the cards and within an old error overlay. The canonical request reuses the reviewed Plan and rebudgets it without a new Planner/persona call, then runs Author/Deck and returns for review. Facts, reviewed voice and CTAs remain; changed Script/Visuals approvals reset. Reasoning readiness or the explicit existing override is required.
- A short measured Build becomes Bundle pending and returns to Align with Script review reopened. Previous audio, snapshot, bundle and version remain intact. No automatic paid rewrite, approval or successful Build event occurs. The limiting current selected-language recording is shown, and bounded UI refresh handles a worker finishing just after the completion event.

## Verification

Final per-gate counts and isolated evidence paths are recorded in `narration-recovery-gates-2026-09-24.json` and Loop.MD. Baseline deck365/365, acceptance24/24, smoke both phases plus rehearsal, minimum25/25, generation58/58, Plan19/19, narrative14/14 and speech30/30 passed before edits.

The new preparation contract runs actual Plan→Author repair→Deck→Bundle→Pitch around source-backed canned model responses and local silent WAVs at2.5 words/second:495-words publish and play as198 seconds, retaining all 13 guided delivery pieces. The independent recovery contract reproduces128.3-seconds through real APIs/graph and verifies preservation, explicit reapproval, readiness, alternate-language visibility and genuine provider failures. The original full release mock journey still exercises new-demo upload→Read→six approvals→Voice→Bundle→runtime/cache→review/rehearsal→browser/session saving with the unchanged measured minimum.

AWS staging initially caught a QA harness timing race: `qa_deck` saw Align before the worker exited and its immediate FAQ PATCH correctly received409. The deck/smoke wait helpers now require the requested phase and `running:false`. No production guard was relaxed and no mutation was retried blindly. The staged rerun result is recorded in the deployment receipt.

## FMEA — complete twelve-category review

Product context: PRD.md, architecture diagrams02–05, existing Learning.MD failures and one-worker AWS constraints. Ratings are pre-fix severity ×occurrence ×detection; focused regressions reduce detection to1–2 for these specific mechanics, not all possible provider outputs.

| Failure mode | S | O | D | RPN | Action and evidence |
|---|---:|---:|---:|---:|---|
| Short script/recordings reused forever after Build |6|7|7|294| Larger supported-content preparation and explicit review recovery; real128.3-second regression and198-second positive pipeline. |
| Larger stop truncated/reordered or loses tail continuation |6|5|6|180| Whole-stop grouping retained in Bundle/route; first fundamental plus all selected features/establish pieces tested. |
| Preparation bypasses reasoning readiness |6|5|6|180| Canonical revise path checks readiness before worker start; failed, observed, explicit override and MOCK cases tested. |
| Faster-voice calibration disappears after unvoiced rewrite |5|4|6|120| Persist target with exact preparation identity; same-identity retry and changed-identity controls tested. |
| Secondary-language shortfall hidden by passing main recording |5|3|6|90| Limiting current selected language exposed/calibrated; stale and unselected translations excluded. |
| Completion event arrives before worker exits; action stays disabled |3|5|5|75| Four bounded short refreshes, then existing polling; hashchange cleanup and actual browser race tested. |

Coverage **12/12**: unhandled errors (provider failures retain error, duration is review); external dependencies (no implicit probe/new retry); race/state (worker completion and publication lock); resource exhaustion (one existing repair, bounded stop allowance/refresh); security/access (readiness enforced, no new credential/client egress); data integrity (old publication and audio preserved); observability (specific deficit, language and pending stage); scale/load (same per-demo worker boundary); billing/credits (no automatic Planner/persona/rewrite loop); retry/idempotency (stable target, explicit review); config drift (voice/language/persona/duration identity); PRD edges (no padding/slowdown, actual measured180-seconds, missing evidence and short-tour exceptions).

No new unresolved blocker remained after this review. Inherited public-builder authentication C7, Cloud alternate-language speaker C8, small-instance concurrency and damaged nonempty audio-cache repair are unchanged and must not be described as solved by this fix. Missing/unreadable audio still prevents publication.

## Limits and preservation

All tests use MOCK_LLM=1, isolated DEMO_STUDIO_DATA/DEMO_STUDIO_GRAPH_DB and blocked outbound sockets; browser tests are muted with requests fulfilled in process. No paid generation, real acoustic/noise test or fresh model-writing quality claim. The word target cannot manufacture missing source evidence; Align review and the measured publication guard remain final. Local protected dm_41513908, output/, port8896 and existing untracked files were not edited or operated. GitHub/AWS release `e506448` passed15/15 staged suites and preserved all4,087 stored files; [deployment receipt](aws/release-narration-2026-09-24.md) records exact staged counts, the three optional legacy checks not repeated on AWS, public-file verification and rollback.
