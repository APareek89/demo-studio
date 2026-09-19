# Demo build and live conversation

This describes the implementation on `codex/creta-conversational-demo`. [Actual Creta acceptance](CRETA_ACCEPTANCE.md) and the [issue log](issues/2026-09-19-creta.md) separate measured outcomes from implementation; implementation is not an acoustic-quality sign-off.

## Build: prepare the knowledge and the reusable demo

1. **Sources.** The Studio stores the original PDFs, selected images, website URLs, language and selected voice. `web/studio/sources.js` calls `server/app.py`; `server/sources.py` preserves extraction evidence and source revisions. Originals are not rewritten.
2. **Readiness.** `server/readiness.py` distinguishes configured credentials from recently observed reasoning, voice and transcription success. Read requires reasoning readiness; Build also requires the selected voice. Probes are explicit and may incur provider charges. An explicit override does not remove the six review approvals.
3. **Read.** `server/graph.py` and `server/orchestrator.py` run the build stages. `server/crawl.py` discovers relevant pages within a model and market boundary. `server/sources.py` extracts text and tables, applies OCR when needed, and reports missing or deferred coverage. It does not promise to read an entire manufacturer's website.
4. **Understand.** `server/agents/understand.py` extracts claims with quotes, locators, applicability and source identity. `server/knowledge.py` reconciles stable assertion IDs, records conflicts and provides retrieval. Uploaded material wins a genuine conflict within the same scope; different trims, markets and dates are not automatically conflicting.
5. **Plan and author.** `server/agents/plan.py` chooses the story; `author.py` writes feature-led, plain-language segments and a separate short Explore overview. Facts support the script; images illustrate those facts. `principles.py` and validators constrain unsupported figures, policy relationships and claims. These deterministic checks do not prove arbitrary semantic entailment.
6. **Align.** `web/studio/align.js` presents facts, visuals, script, FAQ, persona and CTAs for review. Meaningful fact edits create new assertion IDs; old published snapshots remain unchanged. Rejected or changed evidence invalidates downstream approvals. `server/agents/align.py` handles conversation-based edits.
7. **Build.** `voice.py` records the selected guide voice; `speech_style.py` supplies plain speech text and restrained pace. Tone is writing guidance, not an unsupported vendor emotion control. `deck.py` assembles cinematic slides; `rehearsal.py` checks the reviewed content; `bundle.py` publishes a version tied to an immutable knowledge snapshot. All six approvals are required.

Build progress uses durable server-sent events in `server/events.py` and `web/api.js`. Reconnecting resumes from the event cursor. This is separate from the customer's live conversation connection.

## Run: a conversation over reviewed evidence

The new runtime **does use an LLM**. The prepared narration and FAQ remain useful build artifacts, but a new live question goes through a conversation graph. Legacy REST QA callers without a runtime session retain their earlier contract.

`web/player/player.js` owns the customer's experience: the current slide, narration position, question wait, captions and resumption point. `live-voice.js` owns the WebSocket and microphone lifecycle; `voice-worklet.js` supplies PCM frames. The microphone remains active after the customer starts it and grants permission, until it is muted, stopped or the session ends. A browser cannot grant permission automatically.

For a question or interruption:

1. Local voice onset stops current playback promptly. Session, turn, utterance and capture-generation IDs prevent stale audio or transcripts from taking over a newer turn. This application stop signal is distinct from measured acoustic silence.
2. Final transcription submits one customer turn. After a 250 ms grace period, the shortest compatible reviewed acknowledgement may play while work is pending. Creta uses “Let me check that.” in Priya's voice. A ready answer can cut the acknowledgement short.
3. `server/runtime_live.py` routes the turn to `runtime_graph.py`; `runtime_state.py` owns the deadline, cancellation and checkpoint. Retrieval uses the session's published knowledge snapshot plus explicitly stated scope and recent conversation context.
4. An explicit request to check a supplied URL dispatches the bounded lookup first, saving a model round and preventing a saved fact from impersonating a fresh page check. Otherwise the LLM chooses a grounded answer, one necessary clarification, or a tool request. `runtime_tools.py` offers a Decimal calculator and lookup of a URL the customer actually supplied. No arbitrary agent code execution is available.
5. Tool results return to the LLM for the final response. The graph allows at most two tool rounds and four tool calls within one twelve-second deadline. Quoted inputs, units and assumptions accompany a calculation. EMI is illustrative, not a lender offer. Web failures remain failures; the agent cannot claim to have checked an inaccessible page.
6. Validation checks cited evidence IDs, quantities, selected scope, policy conditions and tool provenance. If an answer is empty or substantive content fails validation, one bounded composition repair can use the same evidence and precise feedback, then pass the same validator again. It cannot request tools or a CTA, extend the twelve-second deadline, or override cancellation. An unsuccessful repair keeps the supported original result. A limitation-only repair cannot erase surviving facts; a precise limitation with a generic next step remains a decline cohort. `repair_failed` separately records a repair-call error or timeout. The graph creates a **delivery plan**; it does not speak inside replayable nodes.
7. `runtime_delivery.py` and `llm/sarvam_stream.py` stream the selected voice. The browser owns playback and captions. A runtime-v1 question jump shows the matching evidence and begins the answer directly, without a separate generic transition sentence. A clarification waits for an answer; ordinary Q&A returns to the saved narration position only after the customer's Continue choice. Cancelled or superseded output is ignored.

For **Explore with me**, the customer's context starts personalization while the recorded, cited overview plays. `server/agents/pitch.py` reorders relevant unseen segments and composes exact reviewed factual sentences, with at most one short customer-context preface on the first slide. It does not freely rewrite unverified product claims. The overview leads directly into that slide speech, without an additional decision-frame or custom-batch opening. If model replacements are missing or invalid, the selected route uses explicitly marked reviewed narration and retains its recorded clips and check-ins. A changed priority can replan unseen material at a safe boundary. A slow or failed plan falls back honestly instead of claiming customization succeeded.

Live personalization reads the published bundle, not mutable Align drafts. A session pins both the knowledge snapshot and published demo version. A newer publication requires a refresh before new personalization, even if the facts have not changed. Existing Q&A stays grounded in the pinned knowledge snapshot.

## How evidence, tools and the LLM fit together

Retrieval currently uses local lexical and feature similarity over scoped evidence; it is not an external vector database. The model receives compact approved claims, values, conditions and scope. A large original source quote is retained for audit, but its unrelated table cells do not become additional licensed claims. Exact negative applicability can explain an explicitly excluded trim; a missing retrieved fact does not prove that the entire source corpus lacks that feature. A trim found only in a source-specific listing does not inherit another source’s universal equipment. Literal and same-revision facts can remain useful with explicit attribution; uncertain lineage stays uncertain. Negative, excluded and incompatible old-market/year assertions cannot establish current trim identity. This is conservative screening, not a general semantic proof.

The LLM drafts conversational language. Tools perform arithmetic and fetch a supplied public source. A verified calculator result retains its derivation and can provide a deterministic response when model rendering fails; approximate currency wording permits bounded rounding. Validators and reviewed evidence constrain the answer. None of those layers alone proves that every possible answer is correct; the real-question acceptance pack tests their combined behavior.

Live URL lookup is deliberately smaller than build-time crawling: up to three relevant same-host, model/market-scoped pages within a bounded fetch budget. It does not silently refresh the approved knowledge base. New web evidence remains attached to that turn with its source and applicability caveats. A cited child page cannot impersonate the exact requested page. Private-network destinations and unsafe redirects are rejected.

Source approval is consequential: a model can accurately repeat a wrong approved assertion. The CRETA review found this in a compiled guide's turbo displacement. Reviewed corrections now include a narrow cross-label cc/cm³ conflict check, plus explicit source review. Source changes publish a new snapshot; they never rewrite old evidence or silently retarget a running session.

## Response metrics and their limits

`server/runtime_metrics.py` aggregates session events; `web/observability.js` displays them. Compare the same demo version, voice, input mode, route and speech-end measurement basis. Typed requests, synthetic voice tests and human microphone sessions are different cohorts. Latency calculations use browser timestamps; a server endpoint timestamp is retained separately so clock skew cannot inflate or shrink response time.

Answer, clarification and decline are separate response cohorts. Historical unclassified turns remain explicitly labelled legacy data. A quick decline cannot improve answer-playback percentiles, and `answered=true` is not a semantic quality grade. Actual useful-answer quality is reviewed separately against evidence.

- **Endpoint delay:** estimated end of customer speech to final transcript.
- **Response start:** customer speech end or typed submission to actual first answer audio. An acknowledgement is not the substantive answer.
- **Reasoning and tools:** retrieval, model, tool and validation timings from the graph.
- **Completion:** submission or speech end to completed answer playback.
- **Interruption:** speech onset to the application's local stop request; this does not measure speaker echo or physical silence.
- **Reliability:** failed and cancelled turns remain visible in counts and are excluded from successful latency percentiles. Missing measurements are absent, never zero. Small cohorts are labelled.

The twelve-second graph deadline is a configured bound, **not an observed response-time KPI**. Actual latency and failure rates must come from the acceptance report. Muted playback can validate timing, captions, state transitions and audio bytes; human listening, echo cancellation and perceived naturalness still require an audible microphone session.

## Start reading the code here

- Build orchestration: `server/graph.py`, `server/orchestrator.py`, `server/agents/understand.py`, `author.py`, `voice.py`, `bundle.py`.
- Evidence lifecycle: `server/crawl.py`, `server/sources.py`, `server/knowledge.py`, `server/store.py`.
- Runtime orchestration: `server/runtime_graph.py`, `runtime_state.py`, `runtime_tools.py`.
- Voice and interaction: `server/runtime_live.py`, `runtime_delivery.py`, `llm/sarvam_stream.py`, `web/player/player.js`, `live-voice.js`, `voice-worklet.js`.
- API and telemetry: `server/app.py`, `readiness.py`, `runtime_metrics.py`, `usage.py`, `web/observability.js`.
- Flow diagrams: `docs/architecture-flow.html`, especially diagrams 02, 04, 05 and 08.
