# Automatic narration preparation — 24 September 2026

Read must prepare the three-minute narration for review by default. Requiring the user to calculate a duration deficit or press Prepare was the wrong workflow. This supersedes the manual-recovery design in the earlier narration release.

The reported localhost case was also a mock-preview artifact: generic repeated `(mock)` speech contained only four distinct words (2.11 estimated seconds), while stale approvals displayed six of six. Correct duration accounting exposed the placeholder, but approval/readiness and presentation gave the user the wrong result.

## Changed behavior

- Every Author entry deterministically rebudgets its existing reviewed Plan. The default target remains 495 distinct supported words, with higher matching-recording calibration retained. No extra Planner/persona request is needed.
- Initial drafting and its existing repair may be followed by one focused completion when the assigned approved evidence and planned capacity permit it. There are at most three writing calls per Author run; a provider failure stops further automatic attempts. Grounding, delivery ceilings, word deduplication and human review remain in force.
- A still-short draft is pending. It skips Deck and picture auditing, cannot receive Script approval through the UI/API/chat, and cannot start Build with forged or stale approval flags. Other cards remain reviewable. No approved facts and a failed drafting request have distinct states; a short draft alone does not prove that source material is missing.
- Direct Script edits retain preparation metadata and the reviewer’s wording. A below-target manual edit stays incomplete and skips picture auditing; it is never reclassified as legacy content for an automatic Build rewrite. Changed speech clears whole-stage recording identity before timing/readiness are calculated.
- A first writing-request failure with no saved script is incomplete, not a legacy draft. A failed later revision preserves a valid prior script. This edge case was found in independent review and reproduced through the normal Read API before correction.
- Align removes the large deficit/Prepare panel. Script contains compact timing; Retry drafting appears only after an unsuccessful real draft. Mock placeholder previews are labelled and cannot masquerade as a prepared customer demo. Read-only page visits/polling do not start paid work.
- Ordinary Build prepares a legacy short draft and returns it for review. If complete current recordings are under 180 seconds, Build performs one Author revision and returns to Align without another Voice pass or publication. Missing, unreadable or stale recordings take the recording-recovery path instead of rewriting content. Selected-language freshness includes voice identity and available translation source digest.
- Changed Script/Visuals require approval again. Final approval and measured-duration checks still precede snapshot, bundle and version writes. Prior published artifacts and recorded files remain available.

## Verification

Exact suite counts, source hashes and isolated log hashes are in `automatic-narration-gates-2026-09-24.json`; Loop.MD records the final totals. The actual upload→Read contract covers first-pass success, short repair followed by focused completion, repeated-short bounded failure, no approved facts, first/repair provider outages, mock placeholders, approval guards and legacy recovery. It does not inject a prepared final script or bypass readiness/duration checks.

The full mock release journey runs API creation/upload/Read, six approvals, Voice, Bundle, runtime/cache/review/rehearsal and the actual browser/session flow. It records real local silent WAV fixtures and measures 194.22 seconds with the 180-second publication guard active. The focused preparation pipeline separately proves 495 distinct supported fixture words produce and play 198 seconds. The small generic deck/smoke/build-plumbing fixtures explicitly stub preparation readiness alongside their existing provider/duration stubs; the dedicated automatic and release contracts exercise the real boundaries.

Independent muted-browser checks cover desktop and 390px views, ordinary ready drafts, incomplete drafts, provider-readiness failure, mock previews, source gaps, legacy drafts and recording recovery. No paid provider request, microphone capture or external browser request was made. All Python tests use MOCK_LLM=1, isolated data/graph storage, cloud off and blocked outbound sockets.

## FMEA — automatic Read, Align and Build recovery

Product context: PRD.md, architecture flows 00/02/03/04, Learning.MD and the current one-worker, one-GiB AWS pilot. Scope: the current package's backend, approval API, Align UI and tests. Scores below are pre-fix severity × occurrence × detection; regression coverage reduces detection for these particular cases to 1–2. These are resolved findings, not claims that all provider outputs are correct.

| Component / failure mode | S | O | D | RPN | Priority | Resolution |
|---|---:|---:|---:|---:|---|---|
| Read saves repeated short output as done; reviewer must repair duration | 6 | 7 | 7 | 294 | P0 | Bounded automatic completion, explicit pending status and actual Read contract. |
| Stale approvals or API/chat approval mark an incomplete draft ready | 6 | 5 | 7 | 210 | P0 | Shared recomputed status at approval/Build boundaries; forged and multi-approval cases. |
| A measured short Build loops through recording/publication without renewed review | 6 | 4 | 6 | 144 | P1 | Switch recovery to revision with rebuild=false; prior artifacts preserved and no second Voice. |
| Missing audio is mistaken for missing content, causing unnecessary rewrite | 5 | 4 | 6 | 120 | P1 | Recording state separated from content state; real missing/corrupt cache regressions. |
| Manual shortening loses preparation status and becomes an approvable legacy draft | 6 | 4 | 6 | 144 | P1 | Preserve metadata; recompute explicit current-draft readiness on PATCH; API regression retains words/audio/publication. |
| First Author request fails and an empty Script is classified as legacy/approvable | 5 | 3 | 6 | 90 | P2 | Absent output is incomplete; actual first-call failure/approval/retry regression. |
| Stale alternate translation affects preparation or recording readiness | 5 | 3 | 5 | 75 | P2 | Shared provider/speaker/source-digest freshness checks. |
| Repeated retries spend on incomplete narration's slides or picture audit | 4 | 4 | 4 | 64 | P2 | Hard writing-attempt bound; skip downstream paid generation while incomplete. |

**Coverage: 12/12 categories checked.**

1. **Unhandled error paths:** first-call outage remains an error with a recoverable incomplete draft; repair/completion failures are bounded and visible. Failed revisions retain prior valid output.
2. **External dependency failures:** provider failure stops the additional completion; canonical retry retains readiness checks/explicit override. No real providers were exercised.
3. **Race conditions and state:** approval API refuses active workers; chat/Build recompute readiness; final publication lock and approval checks remain. Completion waits include worker release.
4. **Resource exhaustion:** at most three Author calls per invocation; selected-stop allowance remains bounded; incomplete drafts skip slide/audit work. No automatic revision→Voice cycle.
5. **Security/access control:** no new endpoint, secret exposure or source capability. Existing hosted anonymous-builder access C7 remains a separate unresolved deployment decision.
6. **Data integrity/partial writes:** failed or short builds do not replace the published bundle/snapshot/version; revisions return to human review and preserve prior audio. Recorded timing is never substituted with estimates.
7. **Observability gaps:** preparation attempts, errors and reason are stored/logged; Author stage reports pending. UI distinguishes source gaps, draft failure, mock placeholders and missing recordings.
8. **Scale/load:** no new parallel workers; local per-demo serialization remains. The small AWS instance still has no global build-concurrency cap; capacity is not established by these tests.
9. **Billing/credits:** deterministic Plan reuse avoids extra Planner/persona calls; bounded third completion is the only new drafting opportunity. A Build-triggered rewrite stops before new Voice spend. No paid test calls.
10. **Retry/idempotency:** calibrated target identity survives retries; stage reuse and current voice hash checks stay in place; no page-load/reload mutation. Existing nonempty damaged voice-cache repair remains an inherited limit.
11. **Configuration drift:** real mock placeholders are detected instead of treating all MOCK_LLM fixture speech as invalid; provider/speaker/language/persona/duration identities control calibration and reuse.
12. **PRD edge cases:** 180 measured seconds per selected language, supported distinct speech only, no film/Q&A/deeper/repetition padding, no voice slowdown, unchanged shorter-tour/skip/exit affordances and renewed review of changed content.

No new unresolved blocker remains after the fixes and independent review. Inherited C7 access, C8 Cloud voice identity, small-instance concurrency, scanned-PDF OCR, damaged nonempty voice-cache recovery and selective Align rebuild routing remain open. These are not solved or silently accepted as new design choices by this package.

## Limits

Fixture evidence proves workflow and duration accounting, not fresh model-writing quality, semantic entailment of every real claim, acoustic quality or public-source availability. Insufficient approved evidence cannot be made into three minutes without additional supported material; the app keeps this exceptional case explicit rather than fabricating content. The normal workflow prepares the draft automatically.

Protected local `dm_41513908`, `output/`, port 8896 and user Chrome were not edited or operated. Existing untracked files are preserved. The AWS receipt records staged-host checks, production data/environment preservation and rollback after release.
