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
- **Prospective buyer (the demo's audience):** watch a 4–5 minute walkthrough shaped around their
  concerns, interrupt with questions, get honest answers, take a call to action.

## Must never break
- **No citation, no claim.** Authored speech uses the approved registry. Live answers use its pinned
  snapshot, explicitly attributed public-web or customer-selected website evidence, or audited calculations from
  supplied inputs. Live evidence never silently updates the registry; promotion requires Align.
  An unanswerable question takes the "I won't guess" path and is escalated — never invented.
  Enforced deterministically at authoring (validator) and at runtime (server-side Q&A validator).
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
- **Budget the speech.** Planner allocates typed segment word budgets for `settings.pitch_minutes`;
  Author checks each budget within shared role ceilings raised by eight words for natural joins.
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
- **Interrupt on words.** Raw volume/VAD events do not stop the live guide. A meaningful partial or
  final transcript confirms speech; explicit interrupt controls still stop immediately.
- **Review held citations together.** Retry makes up to two reads of retained source evidence using
  the same exact quote/locator rule. Restore all flagged facts is explicit owner approval; it preserves
  the failed-verification reason and excludes manual rejections and conflict/precedence exclusions.

WP11 finishing decisions and the later presentation correction are recorded in `refine.MD`.
The canonical design is `docs/design/wp11-samples/marine.html?revision=slide-first`.
The production player and Align preview use its compact top heading, centered native-aspect
picture, small feature cards with thin leaders and reviewed anchor dots, counter and slide
progress. The dark slide fills 75% of the player viewport above a white conversation dock;
CTAs sit below the composer in a fixed footer. Short viewports reserve a minimum usable dock.
All feature words come from reviewed callout content. This supersedes the separate evidence
rail and the older oversized title over the picture; Marine/Sage/Graphite color
selection remains in the existing Visuals card. Search the
public web immediately when approved evidence cannot answer, with cited, turn-local, uncached sources.
The default guided tour extends through reviewed stops to at least 180 seconds of narration and publication
blocks if supported narration falls short. Film and Q&A do not count; customers may explicitly shorten, skip or exit. New drafts budget distinct supported content at a conservative natural speaking rate with ten-percent headroom; matching recordings can raise that target. One reviewed story stop may use several short delivery batches, which stay together in the guided route. Align offers “Prepare three-minute narration” for an existing short draft: reuse its reviewed plan, rebudget and rewrite supported detail, then return for Script/Visuals approval. A measured shortfall pauses publication at Align, preserving the previous bundle and recordings; it never triggers an automatic paid rewrite or slower speech.

## Done for v1
One product (the TVS iQube sample: 5 images + product URL, optionally a video and a PDF) goes
end-to-end **locally**: Sources → *Reading your sources…* → Align (six cards approved through the
prompt dock) → *Building your demo…* → Rehearse (voice intake, segments with visuals, grounded Q&A,
check-ins, CTA, handoff summary saved as a session) → feedback → rebuild. `MOCK_LLM=1` exercises the
same path without keys, including the Coach playbook and its review within the six Align cards.

**WP11 gate receipt:** deck365/365, acceptance24/24, smoke both phases; cache27, scope19, public web34, minimum narration25, fact retry12, palette12, browser76, responsive UI103 and search UI30 all pass. Full counts and synthetic-fixture limits are in `Loop.MD`; no paid/acoustic acceptance or deployment is implied.

## Out of scope (for now)
Auth, multi-user, hosted publishing/embed snippet, analytics dashboard, holdout
measurement, payments, 3D product visuals (removed 2026-09-18), unvalidated LLM-token speech,
session resume after refresh and multi-worker runtime ownership.

## Approved runtime upgrade — 2026-09-19; D1–D8 reconciled 2026-09-23

- D1: Use the approved Marine layout with supplied cinematic media. Open with the category's fundamentals in everyday language,
  in reviewed playbook order; delighters come after fundamentals. No decision frame or digits in the
  first spoken line. This replaces the earlier supported-standout opening. Use a warm, cheerful guide
  with restrained pace and punctuation, never invented SSML/emotion controls.
- Initial Explore plans lead with the first unseen fundamental and extend through reviewed stops
  to reach the approved three-minute narration minimum; the initial player fallback uses the same rule.
  Seen filtering, explicit short requests, refinements and revisits retain customer control.
- D4: slides allow up to two pictures; when no literal audited picture is available, use a nearby tagged image or hero with a cited label, mark it **illustration**, and never count it as proof.
- D8: welcome **Voice mode** defaults on only for continuous-voice demos without `?mute=1`; on requests capture once, off keeps streamed speech without a microphone prompt, toggles never reconnect, and typing stays available. Save `input_mode`; actual turn source controls cohorts and ownership rejects stale output.
- A separate LangGraph retrieves → reasons → optionally calculates/checks a supplied public source →
  validates → produces a delivery plan. Selected-voice streaming happens outside graph replay. Tools share
  two rounds/four calls and a 12-second foreground reasoning budget; failures are explicit.
- D5: customer-supplied websites persist for bounded session lookup when evidence is absent or a first decline needs checking; attribute live facts and keep them outside the registry. Default sites use only enabled product URL sources and remain off unless explicitly enabled.
- D6: everyday runtime answers use reviewed neutral substitutions for blocked engineering terms or trigger repair; common terms pass, while explicit technical requests and expert audiences may retain cited exact names. Grounding still applies.
- Explore plays a grounded, measured 10–15-second overview while the LLM orders unseen slides and
  personalizes spoken framing. Explicit corrections affect the next safe boundary.
- D7: stop-closing check-ins never pause narration; legacy question-shaped check-ins retain their source text/audio and are skipped in playback with a run log; answers and declines resume after three seconds of silence, using a recorded return clip or silence. Customer speech, typing or a chip cancels the timer; guide clarifications, closing, CTA and lead choices still wait.
- Crawl only the intended model/market and relevant policies; retain page/table context and visible gaps.
  Uploaded documents win genuine same-scope conflicts. Immutable evidence IDs and published snapshots
  preserve old demos. Semantic relevance never proves a claim.
- Build → record failures → fix → replay against the supplied Hyundai Creta material. Publish observed
  latency/sample sizes separately from targets. Muted automation cannot sign off acoustic listening/echo quality.

## Added 2026-09-03 (batch 2)
- A demo is at most ~3 minutes of narration before Q&A: opening ≤ 60 s, main pitch 60–90 s, one "more features" block 60–90 s, close ≤ 30 s. The guide signposts, translates numbers into the customer's routine, and keeps technical detail for questions.
- Every demo has an audience level; the default assumes a non-technical buyer, so unit jargon never appears in narration.
- A demo can carry several languages (translations of the same approved script); the customer picks one before it starts.
- Everything the agents do is observable per call (stage, model, latency, tokens, cost, prompt, response) inside the app.

## Slides v1 (branch `slides-v1`, from 2026-09-18)
- One script segment = one slide with up to two native-fit pictures and ≤3 grounded callouts per picture. Callouts and picture emphasis follow the matching spoken line; labels belong to their own picture and pass the same validator as speech. This supersedes the original single-picture limit.
- The player has two stage modes, video and slide; the opening film shows only native-fit video and a separate Skip button below, hiding the slide shell. Sync is event-driven (audio leads, screen follows).
- Runtime model calls try providers in a configurable order (default Gemini → Claude → Runware) with a short per-provider timeout; when every provider fails the guide declines and offers a callback. `MODEL_TIER=eval` selects cheaper text defaults; `customer` opts into premium text models. Only `MOCK_LLM=1` avoids paid calls.
- The transcript sent to Q&A holds only the words the customer actually heard.
- Sessions, leads and a per-session summary live in DynamoDB; assets and audio in S3 via the instance role.
