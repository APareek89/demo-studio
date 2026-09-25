# PRD.md — Demo Studio
> ONE PAGE MAX. This is the product context the whole system reads: Loop.MD evals are
> drafted from it, FMEA scans cross-reference it, Sentinel checks code against it.
> AGENT: keep it current when the product direction changes — a stale brief makes every
> downstream check generic.

## What we're building
A local app that turns any product's video, images and documents into a **voice-led,
interruptible product demo** a prospective buyer can run on the brand's website — built by an
agentic pipeline with a human checkpoint at every place the agent could be wrong.

## Users & jobs
- **Brand / product-marketing user (Anand, testing as the builder):** drop in sources → approve
  what the agent found (visuals, facts, persona & voice, calls to action) → rehearse the demo as the
  customer → give feedback → publish. Wants a demo for *any* product, not just the sample.
- **Prospective buyer (the demo's audience):** watch a builder-selected 1–5 minute walkthrough (three by default) shaped around their
  concerns, interrupt with questions, get honest answers, take a call to action.

## Must never break
- **No citation, no claim.** Authored speech uses the approved registry. Live answers use its pinned
  snapshot, attributed live evidence from enabled owner-supplied URL domains, or audited calculations from
  supplied inputs. Live evidence never silently updates the registry; promotion requires Align.
  An unanswerable question takes the "I won't guess" path and is escalated — never invented.
  Enforced deterministically at authoring (validator) and at runtime (server-side Q&A validator).
- **Retain the source details.** Read documents in smaller page-preserving batches, keeping table associations and footnotes. Qualitative features and gearboxes matter alongside numbers; retain source-stated stale warnings. An exact cited PDF cell can verify a quote when flattened text interleaves columns. Neither valid JSON nor an attached citation proves semantic completeness; Align review remains required.
- **Keys stay server-side.** API keys live in `.env`; the browser never sees them.
- **A stage failure never corrupts a demo.** Each stage writes its own JSON; a failed run leaves the
  previous outputs intact and the UI shows the error with a retry.
- **The user's approvals are honoured.** Cards require review again only when their content changes.
  An empty Asked and answered card auto-approves with “No questions yet; this card fills from customer questions”.
  Answer counts and completed audio alone do not reset approval. Build rechecks all six approvals after Voice and under the final publication lock; a concurrent content change returns to Align and preserves the old bundle.
- **Review the sales playbook.** Coach runs after Understand, validates category order, approved
  evidence and explicit gaps, then exposes Story order inside the existing Script card. Reordering
  resets Script/Visuals approval and requests Plan revision. Planner follows its required stops and
  USPs, mapping evidence, pictures and typed word budgets; Author writes the speech.
- **Budget the speech.** Planner allocates feasible 26–33-word narration batches for `settings.pitch_minutes`,
  sharing the existing section allowance with supplemental material about that section. It preserves
  evidence and delivery limits, reports infeasible targets, and recalculates saved plans consistently.
  Author checks the resulting whole-stop budgets within the unchanged role ceilings.
  Align distinguishes planned, estimated and recorded durations; a word target is not measured audio.
- **Explain in everyday words.** Everyday answers use reviewed neutral terminology substitutions
  after grounding and before word limits. Remaining blocked terms receive repair feedback; exact
  cited names are allowed for explicit technical questions and expert audiences. FAQ answers use
  the same map, Author warns on blocked terms, and saved turns record applied substitutions.
- **Answer real questions.** Read answers only questions in uploaded FAQ documents. Runtime v1 and live
  turns check a snapshot-bound FAQ cache before graph reasoning, retain existing scope/date/grounding
  rules, and count accepted hits. Only clean validated registry answers and completed exact-text audio
  enter the customer cache. Declines become counted customer unknowns, never facts; Coach exposes them
  as evidence gaps. Asked and answered supports exact human edits, approval and permanent rejection.
  New snapshots cannot serve old customer answers; already pinned visits retain their own evidence.
- **Rehearse on demand.** Build ends with Voice → Bundle. The Rehearse button tests customer questions
  first, then uploaded questions; at most five questions are generated only when the bank is empty.
- **Interrupt on qualified final speech.** Raw volume/VAD, provisional recognition and fragments do not stop the guide. A final utterance must fit the active prompt, a question, a product topic or an explicit playback command. Continue/Pause/Stop/Not now are local controls. Text qualification reduces accidental interruptions; it is not speaker identification or proof against all TV speech. Known cough/throat annotations and standalone vocalizations are rejected even with question punctuation. Legacy one-shot volume cannot cancel the reply timer; an already-started recording/transcription may deliver a same-session final within12seconds after automatic resume, unless explicit/newer ownership cancels it. Deliberate server-capture replies retain freeform names and locations.
- **Save while the customer is present.** Checkpoint the heard transcript during the visit, including a non-mutating current-speech prefix, and on visibility/exit. Ordered, retryable writes cannot replace a newer record with an older snapshot. Closing still uses the existing summary flow; public views mask contact details.
- **Review held citations together.** Retry makes up to two reads of retained source evidence using
  the same exact quote/locator rule. Restore all flagged facts is explicit owner approval; it preserves
  the failed-verification reason and excludes manual rejections and conflict/precedence exclusions.

The 24 September feedback workbook supersedes the earlier dark Marine sample. The player
uses a white borderless surface, selected-template dark text/buttons and native-aspect
hero imagery across welcome/intake, faded behind the text. Content slides have a smaller
heading and up to two distinct supported pictures side by side, rounded with a subtle shadow.
Reviewed feature labels and anchors remain on-slide; neither a second picture nor a position
is invented when evidence is unavailable. The current image and tags must remain visible
while their recorded narration plays; gallery experiments cannot replace this accompaniment.
Illustrative pictures may carry source-cited captions without guessed feature coordinates. Ordinary slides retain 75% of the player viewport,
with a white fixed conversation dock; short windows reserve usable controls. Portrait phones
show rotation guidance and remain usable. Visuals retains Marine/Sage/Graphite color approval.
Studio navigation opens blank Sources without creating a record until the first mutation;
My demos → Open Studio retains its saved context. Rehearse keeps the left steps and replaces
the heading and panel stack with one full-height feedback chat with uploads and on-demand rehearsal. When approved evidence cannot answer, search only enabled owner-supplied URL domains, with cited, turn-local, uncached sources. Other relevant pages on those domains are allowed; customer text cannot authorize a new domain. PDF/image-only demos have no external runtime web access.
Sources selects a whole-number duration from one to five minutes, default three. The guided tour
extends through reviewed stops to that selected measured duration; publication blocks if supported
narration falls short in any selected language. Changing duration invalidates the affected draft approvals
and preparation, preserving the prior publication. Film and Q&A do not count; customers may explicitly shorten, skip or exit. New drafts budget distinct supported content at a conservative natural speaking rate with ten-percent headroom; matching recordings can raise that target. One reviewed story stop may use several short delivery batches, which stay together in the guided route. Read and Author revisions prepare this content automatically before Script approval, with the existing repair plus at most one focused completion attempt. An unfinished draft cannot be approved or published; a word deficit alone is not evidence that more uploads are needed. Align shows compact timing within Script, with Retry only for an unsuccessful drafting attempt and an explicit notice for mock placeholders. Legacy short drafts are prepared during a user-requested Build. If a complete recording still falls short, that Build prepares a revised draft automatically and returns it for Script/Visuals review; it never records or publishes the changed words without renewed approval. Missing audio requests recording recovery, not more content. Prior published content and audio remain intact; there is no padding, duplication or slowdown.

## Done for v1
One product (the TVS iQube sample: 5 images + product URL, optionally a video and a PDF) goes
end-to-end **locally**: Sources → *Reading your sources…* → Align (six cards approved through the
prompt dock) → *Building your demo…* → Rehearse (voice intake, segments with visuals, grounded Q&A,
check-ins, CTA, handoff summary saved as a session) → feedback → rebuild. `MOCK_LLM=1` exercises the
same path without keys, including the Coach playbook and its review within the six Align cards.

**Current feedback gate receipt:** 51/51 suites; 1,790/1,790 reported checks/groups/phases (nested coverage overlaps); deck380/380, acceptance24/24, smoke3/3, duration19/19, upload retry12/12, workbook player101/101, full-app integration19/19, layout193/193. Full counts and fixture boundaries are in `Loop.MD`; no paid/acoustic acceptance is implied.

**Latest slide gate receipt:**15suites/2,635overlapping checks; actual published-v3 render1,505/1,505 across88states, core399/24/smoke3, full mock28. Evidence/screenshots: `docs/qa/slide-continuity-2026-09-24/`. The25September checkpoint adds a free core recheck without changing application source.

**Runtime recovery gate receipt:**60suites/2,335overlapping checks; core386/24/smoke3, full mock journey28, new allocation17, reader10, checkpoint26, domain21 and runtime recovery17. Exact per-contract results, screenshots, FMEA and the separate paid QA record are in `docs/qa/runtime-recovery-2026-09-24/`. Master integration was authorized on25September; AWS deployment remains separate.

## Out of scope (for now)
Auth, multi-user, hosted publishing/embed snippet, analytics dashboard, holdout
measurement, payments, 3D product visuals (removed 2026-09-18), unvalidated LLM-token speech,
session resume after refresh and multi-worker runtime ownership.

## Approved runtime upgrade — 2026-09-19; D1–D8 reconciled 2026-09-23

- D1: Use the current workbook-approved slide layout with the selected Marine/Sage/Graphite palette and supplied media. Open with the category's fundamentals in everyday language,
  in reviewed playbook order; delighters come after fundamentals. No decision frame or digits in the
  first spoken line. This replaces the earlier supported-standout opening. Use a warm, cheerful guide
  with restrained pace and punctuation, never invented SSML/emotion controls.
- Initial Explore plans lead with the first unseen fundamental and extend through reviewed stops
  to reach the published selected-duration minimum (three minutes by default); the initial player fallback uses the same rule.
  Seen filtering, explicit short requests, refinements and revisits retain customer control.
- D4: slides allow up to two pictures; when no literal audited picture is available, use a nearby tagged image or hero with a cited label, mark it **illustration**, and never count it as proof.
- D8: welcome **Voice mode** defaults on only for continuous-voice demos without `?mute=1`; on requests capture once, off keeps streamed speech without a microphone prompt, toggles never reconnect, and typing stays available. Save `input_mode`; actual turn source controls cohorts and ownership rejects stale output.
- A separate LangGraph retrieves → reasons → optionally calculates/checks a supplied public source →
  validates → produces a delivery plan. Selected-voice streaming happens outside graph replay. Tools share
  two rounds/four calls and a 12-second foreground reasoning budget; failures are explicit.
- D5 (24 September): enabled top-level owner URL sources define runtime web permission. Customer-selected pages are usable only within those domains; www/apex are equivalent, other subdomains need their own owner source. Lookup/search may check relevant same-domain pages beyond the initial path, retaining model/market, public-network, redirect, attribution and tool-budget guards. Removing an owner source revokes permission on the next lookup. This supersedes unrestricted public search and customer-created allow-lists.
- D6: everyday runtime answers use reviewed neutral substitutions for blocked engineering terms or trigger repair; common terms pass, while explicit technical requests and expert audiences may retain cited exact names. Grounding still applies.
- Explore plays a grounded, measured 10–15-second overview while the LLM orders unseen slides and
  personalizes spoken framing. Explicit corrections affect the next safe boundary.
- D7 (24 September): after a logical reviewed section, invite questions and continue after three seconds of silence. Answers and declines use the same owned reply window; qualified final speech, typing or a chip takes the turn. Explicit Continue receives a resume acknowledgement, never a question filler. Generic show-me-around intake uses the reviewed default tour without invented preferences. Legacy authored question check-ins remain skipped. Clarifications, closing and explicitly opened contact forms still wait; declines only offer a follow-up button, and Not now dismisses it and resumes. Healthy speech streams may exceed thirty seconds; only inactivity after buffered speech times out.
- Crawl only the intended model/market and relevant policies; retain page/table context and visible gaps.
  Uploaded documents win genuine same-scope conflicts. Immutable evidence IDs and published snapshots
  preserve old demos. Semantic relevance never proves a claim.
- Build → record failures → fix → replay against the supplied Hyundai Creta material. Publish observed
  latency/sample sizes separately from targets. Muted automation cannot sign off acoustic listening/echo quality.

## Added 2026-09-03 (batch 2)
- The default guided demo contains at least three measured minutes of distinct supported narration before Q&A, prepared automatically as described above. The guide signposts, translates numbers into the customer's routine, and keeps deeper technical detail for questions; customers can explicitly request a shorter tour.
- Every demo has an audience level; the default assumes a non-technical buyer, so unit jargon never appears in narration.
- A demo can carry several languages (translations of the same approved script); the customer picks one before it starts.
- Everything the agents do is observable per call (stage, model, latency, tokens, cost, prompt, response) inside the app.

## Slides v1 (branch `slides-v1`, from 2026-09-18)
- One script segment = one slide with up to two native-fit pictures and ≤3 grounded callouts per picture. Callouts and picture emphasis follow the matching spoken line; labels belong to their own picture and pass the same validator as speech. This supersedes the original single-picture limit.
- The player has two stage modes, video and slide; the opening film shows only native-fit video and a separate Skip button below, hiding the slide shell. Sync is event-driven (audio leads, screen follows).
- Runtime model calls try providers in a configurable order (default Gemini → Claude → Runware) with a short per-provider timeout; when every provider fails the guide declines and offers a callback. `MODEL_TIER=eval` selects cheaper text defaults; `customer` opts into premium text models. Only `MOCK_LLM=1` avoids paid calls.
- The transcript sent to Q&A holds only the words the customer actually heard.
- Sessions, leads and a per-session summary live in DynamoDB; assets and audio in S3 via the instance role.
