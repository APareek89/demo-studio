# Demo Studio: core build and runtime walkthrough

Verified against application commit `8a7aba5` on 19 September 2026. This document explains existing behaviour; it adds no functionality. Start with [Handoff.MD](../Handoff.MD) for current readiness and [the pending list](pending-tasks-2026-09-19.md) for remaining work.

The app has two controllers. **LangGraph coordinates creation** of a reviewed, reusable demo. **The browser player coordinates each customer visit**, calling models for personalization, uncached answers and the final summary. The runtime is not another LangGraph run or an autonomous web/tool-use agent.

## 1. Demo creation: Sources → Read → Align → Build → Ready

### Add source material

Home/library create a demo; Sources accepts documents, images, optional video, URLs and notes. Source roles separate product evidence, hero imagery, intro video, competitor information and brand guidance. Settings hold audience, language, voice and competition choices.

Read [web/studio/sources.js](../web/studio/sources.js), [server/app.py](../server/app.py) (`create_demo:105`, `add_sources:172`, `read_sources:327`) and [server/store.py](../server/store.py) (`new_demo:63`, source helpers from `289`). Storage starts with `data/demos/<id>/demo.json` plus source files. The Read endpoint checks source/key presence and starts a background graph run; key presence is not a live provider-readiness probe.

### Read creates the material the human will review

Actual order in [server/graph.py](../server/graph.py), `build_graph:196`:

```text
Understand → Plan → Author → Deck → FAQ → Align checkpoint
```

1. **Understand** extracts product identity, facts, provenance, conditions, unknowns, image descriptions/parts and video shots. Competitor URLs are fetched during ingestion and become saved evidence. Output: `understanding.json` and derived media. [understand.py:run, line 144](../server/agents/understand.py), [sources.py](../server/sources.py).
2. **Plan** proposes the sales story, audience emphasis, segments, guide persona and CTAs. Output: `plan.json`. The Read path also attempts a persona image and voice sample. [plan.py:run, line 71](../server/agents/plan.py), [orchestrator.py:_persona_sample, line 113](../server/orchestrator.py).
3. **Author** drafts the spoken lines, deeper explanations and questions, assigns segment-and-position-based line IDs, and validates citations and references. Those IDs can change when lines are inserted or reordered. A visual-evidence pass checks which pictures support the spoken material. Outputs: `script.json`, timeline and `visual-audit.json`. [author.py:run, line 236; validate, line 90](../server/agents/author.py), [visuals.py:align, line 229](../server/agents/visuals.py).
4. **Deck** creates slide descriptions, chooses pictures and positions callouts. Code filters model-written labels, uses trusted image-part boxes where available and applies saved human overrides last. Output: `deck.json`; review changes live in `deck-overrides.json`. [deck.py:build, line 284; apply_overrides, line 214](../server/agents/deck.py).
5. **FAQ** prepares reusable answers to likely questions and records the evidence they use. Output: `faq.json`. A provider outage must not become a permanently cached knowledge gap. [faq.py](../server/agents/faq.py), [qa.py:answer, line 154](../server/agents/qa.py).

Each stage runs through [orchestrator.py:_run_stage, line 59](../server/orchestrator.py), which records status, elapsed time and run reports, publishes progress, and invalidates downstream outputs. [graph.py](../server/graph.py) checkpoints graph state in SQLite and allows one active worker per demo. These build checkpoints are separate from customer-session state; they do not provide browser-refresh session resume.

### Align is the human checkpoint

The six cards are **Visuals, Facts, Script, FAQ, Persona & voice, Calls to action**. The user can inspect/edit the material and approve it. Align chat asks a model for structured actions; the orchestrator executes supported actions rather than treating prose as executable instructions.

Read [web/studio/align.js](../web/studio/align.js), [server/agents/align.py](../server/agents/align.py), [orchestrator.py:apply_actions, line 138](../server/orchestrator.py) and [graph.py:align_wait, line 95](../server/graph.py). Explicit edit/approval routes are in [app.py](../server/app.py), starting at `approve:388`. Fact changes mark downstream artifacts stale and reset relevant approvals; the precise invalidation depends on the edit.

### Build creates the playable package

The normal Build entry checks **all six approvals**, then visits Author and Deck, reusing each when marked done. It routes through FAQ only when that stage is not done. Stale outputs are regenerated. It proceeds through:

```text
Voice → Rehearsal → Bundle → status ready
```

- **Voice** renders narration, deeper lines, questions, FAQ and reusable fillers. Cache identity includes provider, speaker, language and text. Locked builds retain the configured voice; missing required recordings fail the build before bundle assembly. [voice.py:render_script, line 215; render_line, line 168](../server/agents/voice.py).
- **Rehearsal** uses existing FAQ results when available, exercises questions otherwise, and scores the script. This is an automated review, not proof of human conversation quality. [rehearsal.py:run, line 26; score_script, line 81](../server/agents/rehearsal.py).
- **Bundle** assembles the reviewed script/slides, facts, audio URLs, images/film, FAQs, guide, intake and CTAs into `bundle.json`. The browser consumes this package. [bundle.py:build, line 14](../server/agents/bundle.py).

Build entry: [app.py:build, line 795](../server/app.py) → [graph.py:start_build, line 282](../server/graph.py). Inspect [the actual Nexon bundle](../data/demos/dm_36d47b86/bundle.json) to connect code to a real output.

**Revision nuance:** `start_revise` can start at Understand, Plan, Author, Deck or FAQ. A revision with `rebuild=true`, or one whose demo was already ready, continues into voice and bundle; that path skips rehearsal. A plain non-ready revision returns to Align. An Understand revision clears all six approvals; ordinary Read may reuse the existing registry and does not itself clear them. Revisions do not all re-enter the normal Build approval gate. Read [graph.py:after_author, line 175; after_voice, line 192; start_revise, line 291](../server/graph.py). Evidence-identity preservation across Re-Read remains an open issue.

### Provider boundaries

Build structured text normally follows **Claude → Gemini → Runware**, for eligible provider-unavailability errors and text-compatible inputs; this is not a universal retry of refusals or arbitrary media. Live QA/pitch/summary use **Gemini → Claude → Runware** by default, configurable in `RUNTIME_PROVIDERS`. Vision and speech have their own paths; Runware text fallback does not replace Gemini image understanding or the selected voice. Build-time FAQ/rehearsal calls use the build chain. The simple Align greeting also has a direct text path and a deterministic fallback.

Read [llm/claude.py](../server/llm/claude.py), [llm/runtime.py:structured, line 19](../server/llm/runtime.py), [llm/runware.py](../server/llm/runware.py) and [config.py](../server/config.py). Timeout settings bound individual requests/attempts, not the total customer wait across model fallbacks, synthesis and media transitions. `MOCK_LLM=1` selects fake providers for free checks.

## 2. Customer visit: intake → opening → tailored route → questions → recap

### Load the existing demo and establish context

[web/app.js:renderPlay, line 95](../web/app.js) fetches `/bundle` and mounts [player.js:mountPlayer, line 28](../web/player/player.js), wiring QA, pitch, speech-to-text, text-to-speech, lead and session endpoints. Studio Rehearse mounts the same player through [web/studio/rehearse.js](../web/studio/rehearse.js).

Player state `S` holds the current phase, slide/line, route, customer profile, transcript, questions, timing and session ID. A separate `run` token identifies which asynchronous work is still allowed to control the UI.

The guided path asks **one intake question and waits**. It retains the actual response as context, launches `/run/pitch` while acknowledgement/optional film/opening play, then uses a timely plan or the stable reviewed route. Browse mode skips personalization. A pitch can choose/order approved material, provide a decision frame and reuse reviewed factual proof; it cannot freely invent product claims.

Read [player.js:runIntake, line 687; startAfterIntake, line 704](../web/player/player.js), [app.py:run_pitch, line 888](../server/app.py) and [pitch.py:plan_pitch, line 210](../server/agents/pitch.py). The post-opening plan waits are 150ms and a further 2,500ms around a spoken filler; these are not a 2.65-second total experience guarantee.

### Play speech and visuals together

Ordinary narration uses recorded lines from the bundle. Line start reveals that line's visual evidence; audio completion advances playback. [player.js:playLines, line 404; playFrom, line 427](../web/player/player.js) owns sequencing. [web/slide.js:renderSlide, line 8; setRevealed, line 101](../web/slide.js) draws the image, callouts and evidence panel.

Check-ins use [player.js:waitFor, line 366](../web/player/player.js). Input ownership prevents a late microphone result from submitting after typing has already taken the turn. Listening may time out, but the response wait does not automatically resume narration. Server-voice demos retain the selected voice; unavailable speech can fall back to captions rather than switching to a browser voice.

### A question interrupts playback without losing its place

1. **Capture the return point once.** `captureOrigin:510` keeps the current phase, route position and line for the whole question/follow-up exchange.
2. **Stop old playback and invalidate its ownership.** `interruptAll:333` stops speech/listening/film and resolves old waits. Late asynchronous responses check the run token and cannot take over the player. This does **not** cancel an upstream HTTP/model request; that work may still complete and incur cost.
3. **Obtain question text.** Typed input goes directly to Q&A. Microphone input uses browser capture and the configured STT path, including `/run/stt` for Sarvam. `listenServer:261`, `listen:296`; [app.py:run_stt, line 940](../server/app.py). Automatic spoken barge-in while narration is playing is not implemented.
4. **Request an answer.** `handleQuestion:536` sends the question, current slide, retained customer profile and the **last eight transcript messages**. A delayed acknowledgement may play after 700ms; it is not counted as the answer beginning.

These functions are in [web/player/player.js](../web/player/player.js). The transcript stores delivered speech, not the unplayed script; interrupted text is estimated from playback duration rather than word-aligned audio.

### Answer from the FAQ or make a constrained model call

[app.py:run_qa, line 847](../server/app.py) first uses [faq.py:match, line 132](../server/agents/faq.py): deterministic token-overlap matching, not embedding search. A hit reuses its answer/audio after checking cited IDs against current approved facts. Clarification follow-ups deliberately skip this shortcut.

On a miss, [qa.py:answer, line 154](../server/agents/qa.py) receives the approved registry, relevant source conditions, permitted competitor evidence, customer context and recent transcript. The runtime provider chain proposes a structured answer. Code checks cited IDs, number/claim grounding and specific policy conflicts before selected-voice rendering. These checks reduce unsupported answers; they are not a general proof that every cited sentence is semantically correct.

The runtime has **no calculator, live browser or arbitrary URL-fetch tool**. A competitor URL must already have been ingested/reviewed to support a comparison. Without sufficient evidence, the guide declines and offers optional follow-up.

### Decide which slide to show, wait, then return

[deck.py:route_for, line 462](../server/agents/deck.py) selects **stay / jump / none** using cited facts and topic matches. This is deterministic code, not an LLM decision. A successful off-slide answer announces the transition before displaying the evidence slide. A declined answer does not cause a factual slide jump.

- **Clarification:** speak the one clarifying question, wait for the reply, and retry the original question with the clarification retained.
- **Answered:** speak the answer, ask whether it helped and wait. A qualified “Yes, but…” remains a question; model-proposed CTAs remain optional choices.
- **Unknown/failure:** retain the open question and wait for another question, explicit Continue or optional follow-up. Do not resume on a timer.
- **Continue/resolved:** [player.js:resumeAfterQA, line 635; resumePlayback, line 642](../web/player/player.js) announces the return and dispatches to the saved phase/line. An interrupted line restarts; a completed line stays complete. Answer-slide jumps do not overwrite the original return point.

### Finish with a recap and an optional consented lead

Closing presents configured actions. The customer must explicitly choose one; an LLM suggestion or “Yes, that helps” is not booking consent. A separate contact form validates the number and requires consent before saving. [player.js:ctaFlow, line 503; saveLeadForm, line 622](../web/player/player.js), [app.py:run_lead, line 900](../server/app.py).

Stop/Done/tab-close save the same session ID with questions, delivered transcript, visited slides, outcomes and timings. [player.js:sessionRecord, line 760](../web/player/player.js) → [app.py:save_session, line 993](../server/app.py) → [storage.py](../server/storage.py).

The ended session triggers a background summary. Identical in-flight revisions coalesce, and a result attaches only if the saved session is still the same ended revision. This coordination is process-local. [app.py:_summarize_session, line 1015](../server/app.py), [summary.py:summarize, line 47](../server/agents/summary.py). The revision hash covers the full saved record; the model's summary payload currently includes the **last 60 transcript entries**, plus structured session fields. It does not receive an unlimited transcript.

Sessions/detail/share appear in [web/studio/sessions.js](../web/studio/sessions.js). Per-demo timing is aggregated by [app.py:_latency, line 1088](../server/app.py) and shown in [web/observability.js](../web/observability.js). Recorded boundaries are voice end → STT done → QA done → answer audio start. QA time includes synchronous speech synthesis; the final interval also includes any announced slide transition, so it is not simply model latency plus a pure TTS metric.

## 3. What to inspect first

For build orchestration, start at `server/graph.py:build_graph`, then `orchestrator.py:_run_stage`, then one stage such as `agents/author.py:run`. For questions, start at `player.js:handleQuestion`, follow `app.py:run_qa` → `qa.py:answer` → `deck.py:route_for`, then return to `player.js:resumeAfterQA`. For saved outcomes, follow `sessionRecord` → `save_session` → `_summarize_session`.

The [existing detailed flow viewer](architecture-flow.html) and [diagram sources](mermaid/) provide the broader architecture. [Atelier's file guide](design/atelier-ui.md) explains appearance separately. This documentation pass changes no flow or diagrams; the source code above is authoritative where historical comments differ.
