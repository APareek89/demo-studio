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
  snapshot, explicitly attributed customer-selected website evidence, or audited calculations from
  supplied inputs. Live evidence never silently updates the registry; promotion requires Align.
  An unanswerable question takes the "I won't guess" path and is escalated — never invented.
  Enforced deterministically at authoring (validator) and at runtime (server-side Q&A validator).
- **Keys stay server-side.** API keys live in `.env`; the browser never sees them.
- **A stage failure never corrupts a demo.** Each stage writes its own JSON; a failed run leaves the
  previous outputs intact and the UI shows the error with a retry.
- **The user's approvals are honoured.** Cards re-approve only when their inputs changed; the agent
  never approves a card on its own.

## Done for v1
One product (the TVS iQube sample: 5 images + product URL, optionally a video and a PDF) goes
end-to-end **locally**: Sources → *Reading your sources…* → Align (six cards approved through the
prompt dock) → *Building your demo…* → Rehearse (voice intake, segments with visuals, grounded Q&A,
check-ins, CTA, handoff summary saved as a session) → feedback → rebuild. `MOCK_LLM=1` exercises the
same path without keys.

## Out of scope (for now)
Auth, multi-user, hosted publishing/embed snippet, analytics dashboard, holdout
measurement, payments, 3D product visuals (removed 2026-09-18), unvalidated LLM-token speech,
session resume after refresh and multi-worker runtime ownership.

## Approved runtime upgrade — 2026-09-19
- Keep Atelier and the cinematic slides. Open with supported standout features in everyday language;
  use a warm, cheerful guide with restrained pace and punctuation, never invented SSML/emotion controls.
- One initial microphone permission enables continuous listening. Speech onset cancels local audio;
  session, turn, utterance and capture-generation ownership reject stale output. Typed input remains available.
- A separate LangGraph retrieves → reasons → optionally calculates/checks a supplied public source →
  validates → produces a delivery plan. Selected-voice streaming happens outside graph replay. Tools share
  two rounds/four calls and a 12-second foreground reasoning budget; failures are explicit.
- Explore plays a grounded, measured 10–15-second overview while the LLM orders unseen slides and
  personalizes spoken framing. Explicit corrections affect the next safe boundary; questions wait for answers.
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
- One script segment = one slide: a still image chosen for the topic, ≤3 grounded callouts anchored on the tagged product part, revealed as the matching line plays. Callouts pass the same validator as script lines.
- The player has two stage modes, video and slide; sync is event-driven (audio leads, screen follows).
- Runtime model calls try providers in a configurable order (default Gemini → Claude → Runware) with a short per-provider timeout; when every provider fails the guide declines and offers a callback. `MODEL_TIER=eval` selects cheaper text defaults; `customer` opts into premium text models. Only `MOCK_LLM=1` avoids paid calls.
- The transcript sent to Q&A holds only the words the customer actually heard.
- Sessions, leads and a per-session summary live in DynamoDB; assets and audio in S3 via the instance role.
