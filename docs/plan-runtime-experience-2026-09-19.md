# Live demo experience: final proposed delivery plan

**Status: proposed implementation plan, not implemented.** Prepared 19 September 2026 against application `8a7aba5` and documentation `8b51916`. The current branch contains planning documents only. Anand requested a simple runtime agent graph, continuous microphone after initial start, contextual Q&A with calculator/source tools, genuinely personalized exploration, and deep product/competition knowledge with uploaded-document precedence. These requirements expand the previous UI-only scope and the earlier exclusions of streaming and spoken interruption. They do not make those capabilities already built.

**Outcome:** a customer can speak naturally, feel heard, receive useful sourced answers, interrupt without fighting the UI, see relevant product evidence and reach an appropriate next step. A successful build, passing synthetic tests or an attractive slide is insufficient to declare this outcome achieved. Yesterday's muted runs established mechanics and some answer safety; they did not establish excellent acoustic or conversational quality.

## Current reality

- Runtime already uses an LLM for personalization and uncached Q&A: `server/agents/pitch.py:210`, `server/agents/qa.py:154`. Narration and FAQ hits normally reuse recorded speech. Conversation exists, but it is limited by its control flow, evidence, latency and voice handling.
- There is a build graph (`server/graph.py:196`), while runtime decisions/media ownership are spread across the browser player and API routes. There is no runtime graph or calculator/web tool loop.
- `server/sources.py:37` fetches only the supplied HTML URL. It neither discovers linked pages nor reads sitemaps nor renders JavaScript. Text and tables can lose structure and be truncated. It is not an exhaustive website ingestion system.
- The fact registry is a small knowledge base, but runtime sends approved facts in its prompt rather than retrieving scoped evidence chunks. There is no enforced document-over-website conflict policy. Re-Read can reassign a displayed fact ID to different evidence (NX20).
- Speech currently uses whole-recording REST transcription and complete audio responses, with REST TTS pacing. Opening microphone has remained stuck in one review. Automatic spoken interruption, continuous capture and streamed speech are unbuilt.

## Chosen architecture

Keep the existing FastAPI app, installed LangGraph, plain JavaScript player, Atelier design and cinematic slide renderer. Add **one small runtime graph** in proposed `server/runtime_graph.py`, plus session state, evidence/retrieval and tool modules. Do not introduce a separate agent framework, a new UI framework or a hosted vector database for this local release.

The runtime graph owns conversation intent, customer context, evidence retrieval, bounded tool decisions, answer composition and personalization. The browser remains the authority on what actually played: audio/video, slide position, delivery acknowledgements and immediate interruption. The two communicate over a **session-scoped WebSocket**; build progress retains its current per-demo SSE channel. Private customer turns must never be published on the shared build stream.

Use IDs for demo, session, turn, plan revision and utterance. Every tool result, transcript final, audio chunk and slide instruction carries its owner. New human input supersedes the previous turn; obsolete output cannot speak, change a slide or overwrite memory. Save turn/plan state at meaningful boundaries; do not put audio frames into graph checkpoints. Dedupe delivery by utterance ID so a graph retry cannot repeat speech. A cancelled model request may still incur provider cost even when its output is rejected.

The graph ends with a validated, versioned **DeliveryPlan** containing speech, evidence, optional slide intent and the expected wait/next interaction. A cancellable delivery coordinator outside replayable reasoning nodes handles TTS/audio emission. Browser delivery acknowledgements advance the actual cursor; graph retries cannot replay audible side effects or decide that a customer has answered based on elapsed time.

**Rejected:** moving audio timing into LangGraph, making an LLM call for every node, a general unrestricted agent, and retaining the whole conversation engine as ad hoc player branches. Models should make a few bounded decisions; deterministic code should execute and validate them.

## 1. Evidence, scoped crawling and retrieval

Fix source identity before rebuilding knowledge. Separate a stable source, its immutable content revision, exact evidence spans, versioned factual assertions and a reviewed KB snapshot. Changed values, qualifiers or quotes create new versions; extraction order cannot change what old citations mean. Existing demos retain their original snapshot. Re-Read shows added/changed/removed/conflicted evidence and invalidates affected approvals/caches rather than silently overwriting them.

**Discover broadly, fetch selectively:**

1. Identify the intended car/model, market, generation and relevant variants from the project and sources. If a brand homepage leaves the model ambiguous, clarify once rather than crawling every car.
2. Read robots/sitemap discovery information and inspect the model page's navigation. Rank model-specific specifications, variants, exterior/interior, safety, technology, ownership, warranty, FAQs, prices and brochures. Follow relevant child URLs such as `/exterior`; do not assume URL hierarchy alone proves relevance.
3. Follow relevant official policy pages and linked document/CDN assets when applicability to the car is established. Keep product and competitor scopes separate. Ignore unrelated models, news archives, careers and dealership listings unless directly needed.
4. Fetch HTML first. Use a controlled rendered-page fallback when relevant content is JavaScript-only. Process PDFs/documents by section/page, preserving table headings, units, availability symbols and footnotes; use OCR/layout-aware extraction when required. Replace silent clipping with batches and explicit incomplete states.
5. Save source snapshots, final URL, discovery parent, fetched/effective dates, hashes and exact locators/quotes. Reuse unchanged content. Normalize redirects/canonicals and avoid duplicate pages; respect access restrictions and modest per-host concurrency.

Initial proposed budget per car: up to **40 HTML pages, 10 documents, 300 document pages, depth 4**; two concurrent fetches per host. These are work limits, not completeness claims. Rank first, reuse existing material, and show any relevant frontier left unprocessed. Coverage is complete only for the declared accessible scope; blocked pages, missing topics and exhausted budgets remain visible with a continuation option. Sitemaps help discover URLs but do not prove every relevant page was processed. [Google's sitemap explanation](https://developers.google.com/search/docs/crawling-indexing/sitemaps/overview).

**Source precedence:** for a genuine contradiction describing the same car, year, market, variant, measurement basis and applicable period, use the **uploaded document over website information**, as requested. Preserve both assertions and show the conflict and winning source in Align. Different variants/test cycles/periods are separate facts, not contradictions. Conflicting uploaded documents require review. An expired or ambiguous document must not silently become a current price or warranty promise. A human-reviewed correction retains its evidence and explicit decision.

Create a per-demo local hybrid retrieval index: lexical plus semantic candidates, filtered by KB snapshot, approval, entity/variant, conflict resolution and date. Return a small evidence pack with citations and surrounding table/footnote context. Exact numeric/scope checks remain deterministic; semantic relevance alone cannot authorize a claim. Embedding provider, crawl and extraction spend must be visible and bounded; use mock embeddings for free tests. Both **authoring and runtime use the same reviewed snapshot**. Exhaustive knowledge should produce a concise main story and deeper answers, not a spoken data dump.

Exit checks: reordered extraction cannot retarget old citations; document precedence works; wrong model/year/market is excluded; table footnotes survive; every source and skipped topic is accounted for. Include NX20, targeted image re-tagging and source-aware cache invalidation here.

## 2. Continuous voice and a complete runtime slice

Run a voice feasibility spike early, in parallel with evidence work. Once the customer starts and grants microphone permission, keep one capture stream active until they mute/end the session. Request echo cancellation/noise suppression, expose a clear listening/mute state, release the device at the end and retain typed input for permission/device failures. Do not ask for a mic click every turn. Fix the Opening microphone state with a bounded initialization/recovery path.

Use browser → FastAPI → Sarvam realtime STT, with partial transcripts, speech detection and end-of-turn events. Stop local playback promptly when human speech begins, but wait for a stable final utterance before answering; tolerate pauses and avoid clipping first words. Reject speech echo from the guide without rejecting a customer who repeats the guide's words. Browser echo cancellation is a requested capability, not proof of echo-free operation; test laptop speakers as well as headphones. [MDN capture](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getUserMedia), [echo cancellation](https://developer.mozilla.org/en-US/docs/Web/API/MediaTrackConstraints/echoCancellation).

Sarvam currently documents realtime STT with partials/VAD and Bulbul v3 streaming TTS; Priya remains a listed voice. Implement a new streaming adapter instead of simulating streaming with many paced REST calls. Preserve one voice across overview, answers, acknowledgements and narration. The first implementation validates a concise complete structured answer before streaming its audio; it does not speak unvalidated LLM tokens. [Realtime STT](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/realtime-streaming), [streaming TTS](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/streaming-api/web-socket), [voice list](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/voices).

On interruption, flush the local audio queue, invalidate the utterance, close its TTS stream and discard late chunks; open a fresh stream for the next reply. Sarvam's documented TTS protocol has no server-side clear/cancel message. Keep STT listening where the connection remains valid. Account capability, quotas, latency and actual voice quality still require an authorized live probe; documentation support alone is not a successful integration.

The first vertical slice is **speak → retrieve existing approved evidence → LLM answer → validated streamed voice → spoken interruption → correct return**. Establish this before a large rebuild. LangGraph supports streamed state/custom events; the installed version is 1.2.11. Use those primitives without introducing a model call merely to announce status. [LangGraph streaming](https://docs.langchain.com/oss/python/langgraph/streaming).

## 3. Q&A graph and bounded tools

```text
Human speech/type/interrupt
  → capture delivered position + take ownership of turn
  → brief acknowledgement alongside retrieval, when useful
  → retrieve relevant facts and customer context
  → LLM: answer / clarify / request calculator or supplied-source lookup
  → bounded tool execution, if required
  → compose response → validate evidence, numbers and scope
  → stream selected voice + synchronize evidence view
  → listen for follow-up / explicit continuation / next action
```

Acknowledgements are appropriate to intent: “Thanks—that helps” for useful context; “Let me check that” for a lookup. Use short varied recordings, avoid praising every question, and omit filler when the answer is already ready. Retrieval/model work runs concurrently with acknowledgement; filler must not add a mandatory delay or be counted as useful answer latency.

Default contextual, comparative and follow-up answers are **LLM-composed from retrieved facts**. The FAQ becomes reusable evidence and an optional exact-scope cache, not a shortcut that ignores new context. Only an unambiguous equivalent atomic query may bypass the LLM; match knowledge version, variant, question scope, context and voice. Never cache outages as “the sources do not know.”

Two initial tools:

- **Calculator:** typed operations with supplied/sourced inputs, units, formula and rounding; no arbitrary code execution. For missing inputs, ask one necessary question. Save a derivation record linking operands to facts or explicit customer assumptions. Label an estimate as an estimate; an EMI example is not a lender quote. Extend the current claim validator to accept these auditable derivations instead of allowing the LLM to improvise arithmetic.
- **Supplied-source lookup:** fetch/search within the public URL/domain identified by the customer and only relevant linked pages. Preserve exact passages, date and vehicle applicability. Validate scheme, host, redirects and response sizes; reject private/local destinations. Page text is evidence, never instructions. Do not expose the current unrestricted `fetch_url` helper as a runtime tool unchanged.

Live web evidence belongs to the **current session/turn**, clearly labelled with its source and fetch time. It may support that sourced answer after validation, but cannot silently overwrite the reviewed KB or script. Persistent promotion goes back through Align. Apply uploaded-document precedence to genuine same-scope conflicts and explain the disagreement when relevant. Manufacturer facts and a third-party site's claims must remain distinguishable; consequential unsupported claims remain unresolved.

Limit tools to two reasoning/tool rounds and four tool invocations per turn, with a **12-second foreground deadline**. A failed lookup yields the useful known part plus what could not be checked; do not block indefinitely or invent a result. Preserve cancellation throughout. Default text provider order remains Gemini → Claude → Runware; fit fallbacks inside the turn budget rather than multiplying independent 15-second waits.

Answer first in a few natural sentences; give deeper detail when requested. Clarify only when ambiguity changes the answer. Remember explicit preferences, corrections, answered questions and open questions. Do not manufacture a commute, budget or variant from the selected demo example. If an answer asks the customer a question, wait. Avoid mandatory ritual satisfaction questions after every trivial fact; leave a natural follow-up/continue point. Keep explicit CTA selection and contact consent.

## 4. Explore with me

```text
Customer describes needs
  → acknowledge the actual context
  → play an interruptible, prebuilt 10–15-second car overview
     while the LLM plans relevant order + personalizes the next script segment
  → validate selected slides, rewritten claims and voice
  → deliver the personalized segment and prepare the next one
  → listen, retain new context and adapt the unplayed remainder
```

Example acknowledgement: “Thanks—that helps me focus the demo. While I tailor it, here’s a quick overview of the car.” Follow with real supported key points, not another long generic intro. Measure the 10–15 seconds using actual audio. Start planning immediately; avoid waiting for every personalized clip before the first relevant segment can play.

The LLM may bring relevant **unseen** slides forward, shorten irrelevant sections and rewrite spoken framing to connect the customer's stated need to approved evidence. It may not change figures, variant conditions, caveats or commercial terms. Every factual sentence stays linked to evidence. Introduce a structured segment response with cited claims, purpose and proposed order, validate it before voice, and reject unsupported personalization. Preserve the reviewed base script for fallback; do not edit the stored master during a visit.

If the customer says “Actually, boot space matters more,” update context and the unplayed route. Do not restart intake, replay the overview or repeat already-resolved questions. During a Q&A detour, keep the current return point stable; apply route changes at the next safe boundary. Retain the tested interrupted-line return initially; no speculative 40%-heard skipping. If planning fails, say so naturally and continue the reviewed route without pretending tailoring succeeded.

Keep Atelier and the cinematic image treatment. Personalization should improve relevance, supporting visuals and pacing, not trigger another unrelated visual redesign.

## 5. Remaining backlog and release sequence

Implement in this order, with the voice feasibility spike starting during the first wave:

1. **Foundation and evidence:** immutable evidence identity (pending 1), scoped crawl/extraction/precedence/retrieval, provider preflight and durable warnings/traces (6), Ready→Align event replay (7), broken optional media import and cache-version maintenance (12). Stage input revisions must govern approval invalidation and every build/revise path, closing the current revision-gate ambiguity. Keep existing snapshots playable.
2. **Continuous voice + runtime vertical slice:** solve mic startup, listening, interruption, session/turn ownership and one grounded live answer (2); record trustworthy speech-end/playback timestamps from the start.
3. **Tool-assisted Q&A:** runtime graph, calculator, user-source lookup, scoped evidence/derivations and graceful failures (5), useful partial answers and context retention (4).
4. **Explore personalization:** 10–15s overview, concurrent route/script planning, context corrections and coherent presentation; remove dishonest filler and repetitive questions (10).
5. **Quality and efficiency:** optimize the measured waits and cross-demo/version/provider percentiles (3); script-hash rehearsal reuse and selective image repair (9); repair and review the existing TVS iQube FAQ bank as a second-product regression (8). Keep the fixed summary/consent/citation protections; do not reopen completed work unnecessarily.
6. **Acceptance first, hosting later:** prove the local Nexon experience below. AWS role/storage/table state, multi-worker summary/runtime ownership, deployment and rollback form the subsequent operational release (11). Hosted publishing/embed and refresh-resume are not implicitly included in this runtime improvement.

This accounts for all 12 existing pending items. It is a sequence, not a claim that the entire platform can be completed today. The first meaningful checkpoint is one real conversational Nexon slice; do not spend the day producing only a new architecture and another static demo. Build → record failure → fix → replay the failing scenario, then run the full journey. Do not run repeated paid builds to test changes that only need runtime replay.

## 6. Acceptance: what earns “ready”

These are proposed engineering release targets, not observed current performance or provider guarantees. Yesterday's final three model turns had a 9.029s median/10.458s worst; that tiny typed sample is not a baseline for microphone p95.

- **Interruption:** narration stops within p95 **300ms from detected human speech onset**. Also measure true acoustic onset→detection separately so slow detection cannot hide behind this number. Zero stale audio/slide takeovers after a committed new turn in the regression pack.
- **Acknowledgement:** p95 **700ms from detected utterance end**, only when needed. Measure endpointing delay independently. Filler is excluded from useful-answer timing and never blocks a ready answer.
- **Useful answer:** from actual speech end/text submit to first useful answer audio, including endpointing/retrieval/validation/synthesis/transition: exact cache p95 **≤1s**; non-web LLM p50 **≤3s**, p95 **≤6s**; tool-assisted p95 **≤10s** with the **12s** bounded failure path. Report full answer completion too; a quick irrelevant first phrase does not qualify.
- **Personalization:** overview is **10–15s** of actual audio; correct first personalized segment is available by its end in at least **95%** of the measured successful planning sample. Report failure/fallback rates and sample size separately. No invented context, repeated intake or unsupported rewritten claims.
- **Quality:** zero unsupported critical numerical/policy/comparison assertions, silent source-conflict overwrites, incorrect calculation outputs or unauthorized lead submissions in the acceptance pack. At least **95% of answerable benchmark questions** receive a useful supported answer; unnecessary declines count as failures. Explicitly inspect warranty partial-answer cases.
- **Listening:** one initial permission/start, natural multi-turn use without repeated mic clicks. In the declared quiet-device sample, target **≥95% intent/key-entity accuracy**; in ordinary background noise, **≥90%**. Materially uncertain model names/numbers are clarified. Test pauses, accents, mixed-language corrections and speaker echo, not just prerecorded files.

Fixed pack: **100 balanced question cases** with per-category counts; at least **20 real interruption cases** spanning overview/narration/answer/filler/tool-wait; **three complete buyer journeys** with different priorities. Include exact facts, paraphrases, follow-ups, missing evidence, document conflict, stale/wrong-variant web evidence, calculations with missing/changed inputs, malicious source instructions, provider outage, silent pause, “yes, but…”, route correction and explicit refusal of follow-up. Synthetic evidence/tools/media cover free regressions; live samples are separately labelled and costed. Do not claim a reliable per-category p95 from a handful of cases.

Test laptop speakers/headphones and a phone in the actual supported browsers. A long pause after the agent's question must not cause narration to restart. Echo-only playback must not start a fake customer turn. Interrupting a tool response must preserve the original question and return point. A voice-disconnect must show recovery without pretending it still hears the customer.

Keep automated reviews muted as previously requested, but **voice naturalness, echo and spoken interruption need an actual audible/microphone acceptance session**. Caption-only inspection cannot sign them off. Do not mark the experience complete until the acoustic pass and complete journeys meet the agreed bar; retain recordings/transcripts, timings, costs and failure evidence.

## Implementation ownership and boundaries

Proposed additions: `server/runtime_graph.py` (turn/explore routing), `server/runtime_state.py` (session/turn/evidence state), `server/runtime_delivery.py` (cancellable voice delivery), `server/runtime_tools.py` (typed calculator and supplied-source tools), `server/knowledge.py` (versioned evidence/retrieval), and `server/crawl.py` (scoped discovery/extraction). Exact file splits may be adjusted during implementation without adding services.

Extend existing `server/app.py`, `schemas.py`, `store.py`, `sources.py`, `agents/understand.py`, `qa.py`, `pitch.py`, `principles.py`, `voice.py`, `llm/sarvam.py`, `web/player/player.js`, `web/observability.js` and the Sources/Align surfaces. Separate browser voice transport from playback where it reduces ownership races. Update PRD, validators, schema/contracts and architecture diagrams together with implementation: sourced runtime evidence and audited derived results explicitly extend today's registry-only claims rule.

Preflight the actual text, streaming-STT and selected-voice capabilities before a customer run; do not treat an environment key as readiness. Keep provider keys on the server, record per-node/tool/retrieval/speech timings and costs, persist warnings, and give each live validation batch a call/spend cap. No paid provider probe, new build, TVS repair or deployment was performed while preparing this plan. Old authorizations for the completed two-build exercise are not a new unbounded testing budget.

The plan rejects a purely cosmetic fix, a generic always-speaking FAQ bot, whole-brand crawling, free-form arithmetic and unvalidated token-to-speech. Existing product evidence, consent, human review and graceful fallback remain the foundation.
