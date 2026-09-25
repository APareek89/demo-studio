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
  Product classification follows source evidence rather than a stale demo name or schema example. A strict majority of at least two agreeing reader batches can correct the primary category; ties/pluralities retain it. Other product metadata, brand and cited facts keep their existing precedence.
- **Keys stay server-side.** API keys live in `.env`; the browser never sees them.
- **Keep prompt roles distinct.** Gemini structured text sends the exact application rules through the SDK's actual system-instruction field and source/history/customer material as user contents. This applies to build, runtime and extracted-text fallback; schemas, validators, budgets, retries and other providers/media paths remain unchanged. Correct request roles support instruction priority but do not prove model compliance.
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
- **Speak like a guide.** Author prioritizes varied direct sentences and occasional contextual invitations to notice a sourced pictured feature, without repeated catalogue openings or invented benefits. Planner adjectives and suggested wording are an outline, never evidence for a benefit or relaxed condition. Author may select sparse whole-line expression through optional delivery metadata; most lines omit it and new guided speech keeps pace1.0. Sarvam Bulbul v3 receives restrained temperature variation, not exact pitch/loudness or guaranteed word emphasis. Omission preserves existing audio cache identity; changed expression gets its own clip and the same measured-duration/locked-voice checks.
- **Answer real questions.** Read answers only questions in uploaded FAQ documents. Runtime v1 and live
  turns check a snapshot-bound FAQ cache before graph reasoning, retain existing scope/date/grounding
  rules, and count accepted hits. Only clean validated registry answers and completed exact-text audio
  enter the customer cache. Declines become counted customer unknowns, never facts; Coach exposes them
  as evidence gaps. Asked and answered supports exact human edits, approval and permanent rejection.
  New snapshots cannot serve old customer answers; already pinned visits retain their own evidence.
- **Rehearse on demand.** Build ends with Voice → Bundle. The Rehearse button tests customer questions
  first, then uploaded questions; at most five questions are generated only when the bank is empty.
- **Yield promptly when speech starts; commit only qualified final words.** Sustained locally speech-like microphone frames or a qualified partial recognition pause the guide reversibly, before server recognition finishes. A volume spike alone cannot do this. The hold preserves the recorded/streamed clip and visual transition; rejected input or bounded silence/no-progress recovery resumes the same position. Only a qualified final matching the active prompt, question, product topic or explicit command cancels the old turn and starts semantic work. Continue/Pause/Stop/Not now stay local. Known cough/throat annotations and fragments remain rejected; this is not speaker identification, and sustained TV speech may cause a temporary hold. The owned reply timer pauses during the hold and resumes after rejection. Legacy same-session capture may still finish within12seconds after automatic resume; newer input/control/mute revokes stale ownership.
- **Show the reviewed feature when answering.** Model and FAQ answers resolve their accepted citations to the existing published picture and owning caption, including a different image on the same slide. Snapshot, publication version, scope, image identity and caption ownership must match; source coordinates are never invented. An unambiguous “show me” picture request uses the same scoped evidence lookup without a reasoning call or learning a new fact/FAQ/unknown. It shows a matching reviewed non-illustrative photo or states that no reviewed image is available. Generic tour controls and combined factual questions keep their ordinary path; the return checkpoint is unchanged.
- **Trial LiveKit before adoption.** An explicit `?voice_transport=livekit` player flag sends the existing microphone over local WebRTC and existing validated control/answer/audio events over reliable data. Existing Build/Align, provider order, evidence validation, early speech holds, gallery readiness, playback and session owners remain authoritative. A human conversational review uses explicitly enabled live providers and a voice-enabled link; mock recognition cannot establish that acceptance. Default playback requires no LiveKit dependency. Local origin/token checks, bounded rooms/messages, generation-bound tracks and visible disconnect failure are mandatory. The launcher copies a publication into separate local storage and mocks providers by default. This trial does not implement LiveKit Agents, outbound RTP speech, speaker identification or production rollout. Real microphone/provider and network testing must precede adoption.
- **Keep evidence authoritative on the server.** Knowledge snapshots, source extractions, retrieval indexes and image/audio files remain server-side. The browser receives the published facts needed by the demo, slide/tag metadata and media URLs, then loads those assets; it does not own the full retrieval registry. Read selected source context once per request after ranking, with no eligibility or persistent-cache change. The current EC2 deployment uses local JSON/files and graph SQLite with cloud sync off. Optional DynamoDB record storage and S3 file mirroring remain disabled; this task does not migrate them.
- **Save while the customer is present.** Checkpoint the heard transcript during the visit, including a non-mutating current-speech prefix, and on visibility/exit. Ordered, retryable writes cannot replace a newer record with an older snapshot. Closing still uses the existing summary flow; public views mask contact details.
- **Review held citations together.** Retry makes up to two reads of retained source evidence using
  the same exact quote/locator rule. Restore all flagged facts is explicit owner approval; it preserves
  the failed-verification reason and excludes manual rejections and conflict/precedence exclusions.

The 24 September feedback workbook supersedes the earlier dark Marine sample. The player
uses a white borderless surface, selected-template dark text/buttons and native-aspect
hero imagery across welcome/intake, faded behind the text. The approved25September gallery
changes only the middle content-slide presentation: walk through source pictures, enlarge the
current picture and focus its reviewed feature label. Up to two supported pictures follow their
existing line bindings; a selectable inset retains the second picture when both support one line. Main narration begins when its image and labels are ready; the player
retains interruption, pause, return and speech ownership. Reviewed anchors alone receive a
pointer; illustrative or unanchored pictures retain source-cited captions without guessed
coordinates. An exactly empty unavailable pixel-audit result may retain the allowed Author-selected pictures as disclosed illustrations; missing, partial or rejected audit decisions do not qualify. Each illustration's captions use its own narrated interval and citations, without invented feature anchors. `hero_open`/`hero_close` (welcome/end heroes) and picture-free slides keep the native view; the
`presentation=native` URL is a diagnostic fallback. Align’s native editor remains unchanged.
Slide heading/footer, top navbar and bottom articulation/microphone/chat/action controls
retain their existing structure and geometry. Ordinary slides retain 75% of the player viewport,
with a white fixed conversation dock; short windows reserve usable controls. Portrait phones
show rotation guidance and remain usable. Visuals retains Marine/Sage/Graphite color approval.
Studio navigation opens blank Sources without creating a record until the first mutation;
My demos → Open Studio retains its saved context. Rehearse keeps the left steps and replaces
the heading and panel stack with one full-height feedback chat with uploads and on-demand rehearsal. When approved evidence cannot answer, search only enabled owner-supplied URL domains, with cited, turn-local, uncached sources. Other relevant pages on those domains are allowed; customer text cannot authorize a new domain. PDF/image-only demos have no external runtime web access.
Sources selects a whole-number duration from one to five minutes, default three. The guided tour
extends through reviewed stops to that selected measured duration; publication blocks if supported
narration falls short in any selected language. Changing duration invalidates the affected draft approvals
and preparation, preserving the prior publication. Film and Q&A do not count; customers may explicitly shorten, skip or exit. New drafts budget distinct supported content at a conservative natural speaking rate with ten-percent headroom; matching recordings can raise that target. One reviewed story stop may use several short delivery batches, which stay together in the guided route. Read and Author revisions prepare this content automatically before Script approval, with the existing repair plus at most one focused completion attempt. An unfinished draft cannot be approved or published; a word deficit alone is not evidence that more uploads are needed. Align shows compact timing within Script, with Retry only for an unsuccessful drafting attempt and an explicit notice for mock placeholders. Legacy short drafts are prepared during a user-requested Build. If a complete recording still falls short, that Build prepares a revised draft automatically and returns it for Script/Visuals review; it never records or publishes the changed words without renewed approval. Missing audio requests recording recovery, not more content. Prior published content and audio remain intact; there is no padding, duplication or slowdown. Consecutive uses of the same settled photograph keep it in place across slide boundaries; only a changed reviewed feature may move focus. A new photograph retains the gallery entrance.

## Done for v1

The25September immediate listening hold, published-picture Q&A and selected-source I/O fixes describe the current implementation branch only. They are not deployed by this task. The separately authorized LiveKit trial adds an opt-in local transport and server, with no new graph node or autonomous answering agent.

One product (the TVS iQube sample: 5 images + product URL, optionally a video and a PDF) goes
end-to-end **locally**: Sources → *Reading your sources…* → Align (six cards approved through the
prompt dock) → *Building your demo…* → Rehearse (voice intake, segments with visuals, grounded Q&A,
check-ins, CTA, handoff summary saved as a session) → feedback → rebuild. `MOCK_LLM=1` exercises the
same path without keys, including the Coach playbook and its review within the six Align cards.

**Current feedback gate receipt:** 51/51 suites; 1,790/1,790 reported checks/groups/phases (nested coverage overlaps); deck380/380, acceptance24/24, smoke3/3, duration19/19, upload retry12/12, workbook player101/101, full-app integration19/19, layout193/193. Full counts and fixture boundaries are in `Loop.MD`; no paid/acoustic acceptance is implied.

**Current gallery-template acceptance:** `docs/qa/gallery-template-2026-09-25/README.md` records the scoped browser checks, full mock verification, screenshots and release status. No paid or acoustic acceptance is implied. The preceding native browser baseline remains in `docs/qa/noise-gallery-2026-09-25/README.md`.

**BMW narration follow-up, 25 September:** final free core445/24/smoke3, provider79 and mock journey28 pass. The repository still defaults to `MODEL_TIER=eval` with Gemini → Claude → Runware builds. Selecting `customer` now defaults builds to Runware → Gemini → Claude, using its existing GPT5.5 model; explicit `BUILD_PROVIDERS` wins. This persists the customer-quality selection in configuration without changing runtime order, model IDs, budgets, voice or workflow. Fresh runtime config6 passes; prior graph130, repair106, hedge35 and delivery27 pass after actual Gemini system-role separation. Author prompt53, narrative14, generation58, preparation35, automatic preparation16 and expression20 have passing receipts. Exact Gemini3.8 build calls request LOW; one real post-role Coach completed in11.2s without truncated JSON, while LOW still cannot guarantee output room. Initial301/330 and later326/330word Author failures remain recorded. The GPT5.5 v6 draft required normal Align editorial cleanup; independent source review then accepted all31 lines with approved citations and335/330 eligible main words, with the outcome warning remaining advisory. Normal Align selected11 distinct pictures, removed duplicate/wrong seat-and-screen pointers, preserved source qualifications and completed all six card approvals. The one normal recording Build published v1 with122.64seconds of decoded narration against the selected120-second minimum;32 script clips and19 fillers succeeded. Pixel review then corrected the AR screen pointer, distinguished third-row seating from a second-row panel caption and removed duplicate dimension labels. A slide-only rebundle published v2 with15 slides,11 distinct images and32 labels; all53 existing audio files and the Voice stage stayed byte-identical. Final actual-player browser281/281 and published-audio71/71 checks pass at1440/390px; the9.2-second overview versus its10–15-second guidance remains advisory. This is reviewed output, not first-pass generation success. Evidence and FMEA: `docs/qa/bmw-gallery-narration-2026-09-25/`. Final BMW visual review is recorded; no acoustic or AWS acceptance is implied.

**Earlier native-slide gate receipt:**15suites/2,635overlapping checks; actual published-v3 render1,505/1,505 across88states, core399/24/smoke3, full mock28. Evidence/screenshots: `docs/qa/slide-continuity-2026-09-24/`. The25September checkpoint adds a free core recheck without changing application source.

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
- Optional AWS backend: DynamoDB can store records and S3 can mirror files via the instance role. This is capability, not the current deployment: the25September EC2 release uses server-local JSON/files and graph SQLite with cloud sync off.

**25September runtime release refinement:** customer questions that need a short wait rotate ten neutral acknowledgements per visit, without repetition until the full cycle. Fast answers skip the holding line; local Continue/Pause/Stop commands never trigger it. Existing locked voice and answer-first cancellation apply. Enabled owner URL consent is independent of whether the last build crawl succeeded; explicit exclusions still revoke live lookup/search. Failed live reads create no facts, evidence or cached answers. This release retains AWS WebSocket voice; LiveKit stays an optional local trial.
