# Demo Studio — core flow explained (23 September 2026)

Written for Anand by an orchestrator session that ran two read-only tracer agents on non-overlapping file sets. **Agent A** traced the build side (Sources → Bundle). **Agent B** traced the run side (player → runtime graph → voice). The **Orchestrator** read the docs, spot-checked the load-bearing claims against the working tree, designed the proposals, and wrote this up. Every section is tagged with who produced it.

> **Line numbers:** taken at commit `ba448ff`. Commit `0461609` (23 September, code-study comments) shifted most lines in `server/graph.py`, `orchestrator.py`, `store.py`, `schemas.py`, the build agents and `web/player/player.js`. Use the function names; the numbers are approximate after that commit.


Line numbers are from the working tree on branch `codex/creta-conversational-demo` at commit `ba448ff`. Where a doc and the code disagree, the code wins and the disagreement is named. This document explains existing behaviour and proposes two changes; it changes no code.

---

## 0. Three things to know before you read the Creta demo — [Orchestrator]

1. **The build's text model is Gemini, not Claude.** `BUILD_PROVIDERS` defaults to `gemini,claude,runware` ([config.py:55](../server/config.py:55)). `claude.structured()` is only the entry name; for text-only calls it walks that chain Gemini-first ([claude.py:94](../server/llm/claude.py:94), [claude.py:158](../server/llm/claude.py:158)). The Creta usage log (`data/demos/dm_41513908/usage.jsonl`) has zero Claude rows: plan, author, deck and FAQ ran on `gemini-3.8-flash`, with Runware `openai:gpt@5.5` as the fallback. `CLAUDE.md`'s line "Claude Opus 5 = plan / author / align agent" is out of date for this branch.
2. **The v8 Creta script you hear was hand-authored by a session agent, not produced by the pipeline.** `output/creta-night-final/install_reviewed_session.py` writes `plan.json` and `script.json` directly and builds the deck with the model call blocked (lines 113–158, 243). The last genuine pipeline output is preserved in `output/creta-night-final/before-reviewed-install/`. Section 7 shows both, because the question "why is the script poor" has a different answer for each. `visual-audit.json` is stale: it was produced at 16:56 against a script that no longer exists, and the installer never re-ran the audit.
3. **[docs/core-workflow-walkthrough.md](core-workflow-walkthrough.md) is stale.** It says the runtime is not a LangGraph and has no calculator or URL tool. The runtime is a compiled LangGraph ([runtime_graph.py:1531](../server/runtime_graph.py:1531)) with a Decimal calculator and a bounded URL lookup ([runtime_tools.py:91](../server/runtime_tools.py:91), [runtime_tools.py:168](../server/runtime_tools.py:168)). [docs/DEMO_BUILD_AND_RUN.md](DEMO_BUILD_AND_RUN.md) and `Handoff.MD` are accurate.

---

## 1. The shape of the app — [Orchestrator]

There are two controllers and one folder.

- **Build** is a LangGraph in [graph.py:199](../server/graph.py:199). It runs stages in order, parks at a human checkpoint (Align), and only continues to voice and bundle when all six review cards are approved. Every stage is a pure function of its input files and writes its own JSON.
- **Run** is the browser player ([player.js](../web/player/player.js)) plus a second, separate LangGraph per customer question ([runtime_graph.py](../server/runtime_graph.py)). The player owns playback, waits and the exact return point. The server owns evidence, tools, validation and the delivery plan. The graph never speaks; it hands a plan to a streaming voice layer.
- **The folder** `data/demos/<id>/` holds: `demo.json` (settings, approvals), `sources/`, `understanding.json`, `knowledge/` (`identities.json` id ledger, `snapshots/kb_*.json` immutable published registries, `extractions/` cache), `plan.json`, `script.json`, `visual-audit.json`, `deck.json`, `deck-overrides.json`, `faq.json`, `conversation.json`, audio files, `rehearsal.json`, `bundle.json`, `sessions/`, `runtime/` (per-session checkpoints), `usage.jsonl`.

---

## 2. Demo build, step by step — [Agent A — Build Tracer]

### 2.1 The path

1. **Create the demo.** `POST /api/demos` → [app.py:106](../server/app.py:106) `create_demo()` → [store.py:63](../server/store.py:63) `new_demo()`: status `sources`, all six approvals `false` ([store.py:79](../server/store.py:79)). An optional product URL becomes a `url` source with role `product`.
2. **Add sources.** `POST /api/demos/{id}/sources` → [app.py:173](../server/app.py:173) `add_sources()`. Empty file → 400; over `MAX_UPLOAD_MB` (default 1024, [config.py:87](../server/config.py:87)) → 413. Extension → kind via `KIND_BY_EXT` ([store.py:27](../server/store.py:27)); anything else is refused. Roles come from the upload zones in [sources.js:7](../web/studio/sources.js:7): `intro_video` (one), `hero` (one; "one hero at a time" [app.py:188](../server/app.py:188)), `product` (many images or videos), `catalogue` (PDF/DOCX/TXT/MD/CSV), `brand` (docs or pasted text), `competitor` (URL only). There is **no count limit** on images. `PATCH /sources/{sid}` with `use_in_demo=false` keeps an image for learning but bars it from the screen ([store.py:389](../server/store.py:389) `visual_allowed`).
3. **Read gate.** `POST /read` → [app.py:381](../server/app.py:381) `read_sources()`: needs at least one source, a text key or `MOCK_LLM=1`, a Gemini key if any image or video, then `_require_provider_readiness` ([app.py:355](../server/app.py:355)): a fresh, observed, non-mock reasoning success, or an explicitly logged override. Then [graph.py:280](../server/graph.py:280) `start_read()`.
4. **The graph.** [graph.py:199](../server/graph.py:199) `build_graph()` declares nodes `router, understand, plan, align_enter, align_wait, author, deck, faq, voice, rehearsal, bundle, finish`. Edges: `START→router` (routes by entry: read→understand, build→author, revise→the requested stage, else align_wait, [graph.py:42](../server/graph.py:42)); `understand→plan→author→deck`; after `deck`, `after_author` ([graph.py:174](../server/graph.py:174)) goes to `voice` only on a build entry with every approval true (or to `faq` if FAQ is not done), otherwise `faq`; after `faq`, `after_faq` ([graph.py:195](../server/graph.py:195)) goes to `voice` (build + approved) or parks at `align_enter→align_wait`; `voice→rehearsal→bundle→finish→END`. There is no separate visuals node; the pixel audit runs inside the author stage. `start_revise` ([graph.py:294](../server/graph.py:294)) resumes the parked interrupt with `{"type":"revise"}` and `align_wait` routes it ([graph.py:112](../server/graph.py:112)); a revise always re-parks at Align.
5. **Every stage runs through one wrapper.** [orchestrator.py:104](../server/orchestrator.py:104) `_run_stage()`: mark running, snapshot the previous output file ([orchestrator.py:109](../server/orchestrator.py:109)), run the stage, compute `changed_cards()` ([orchestrator.py:85](../server/orchestrator.py:85)) and **un-approve those cards** ([orchestrator.py:130](../server/orchestrator.py:130)), mark downstream stages stale via `DOWNSTREAM` ([orchestrator.py:16](../server/orchestrator.py:16)), write run log and cost. A failed stage leaves the previous JSON in place.
6. **Understand** — [understand.py:176](../server/agents/understand.py:176) `run()`. Website ingestion first: [crawl.py:29](../server/crawl.py:29) budget `40 html pages / 10 documents / 300 document pages / depth 4 / 180 s`, scoped to the model and market. Documents through pdfplumber and local OCR ([sources.py:18](../server/sources.py:18)). Images through Gemini vision with `IMAGES_PROMPT` ([understand.py:54](../server/agents/understand.py:54)) in batches of 12 ([understand.py:211](../server/agents/understand.py:211)); each image returns a description, angle, quality 1–5 and **parts with bounding boxes and confidence** (`ImageG`/`PartG`, [schemas.py:27](../server/schemas.py:27)). Facts through `FACTS_SYSTEM` ([understand.py:60](../server/agents/understand.py:60)) plus `TRUTH_RULES` ([principles.py:46](../server/agents/principles.py:46)) per ≤70 000-character batch ([understand.py:308](../server/agents/understand.py:308)); each fact carries claim, value, conditions, applicability, source id, locator and a verbatim quote. Then [knowledge.py:333](../server/knowledge.py:333) `reconcile()` assigns **never-reused assertion ids** from the `identities.json` ledger and stamps `assertion_hash`/`evidence_id`. [visuals.py:333](../server/agents/visuals.py:333) `build_map()` scores fact↔picture overlap. Output `understanding.json`.
7. **Plan** — [plan.py:214](../server/agents/plan.py:214) `run()`. System prompt `PLAN_SYSTEM` ([plan.py:14](../server/agents/plan.py:14)) formatted with `PRINCIPLES` ([principles.py:96](../server/agents/principles.py:96)), `CUSTOMER_STATES` ([principles.py:115](../server/agents/principles.py:115)), `PITCH_SHAPE` ([principles.py:174](../server/agents/principles.py:174)), `PROOF_BLOCK` ([principles.py:134](../server/agents/principles.py:134)), audience and language. User content ([plan.py:230](../server/agents/plan.py:230)): product, brand profile, product URL, the configured (locked) voice, source-discovered action URLs, the **approved fact registry as one row per fact** via `fact_context()` ([principles.py:85](../server/agents/principles.py:85)), open unknowns, video shots, and the image list rendered as `im08 q4 · interior · rear seat · <description>` ([plan.py:228](../server/agents/plan.py:228)). Output schema `Plan` ([schemas.py:213](../server/schemas.py:213)) with `SegmentPlan` ([schemas.py:165](../server/schemas.py:165)). Post-filters drop unknown fact/visual/usp ids, force intro/outcome/features roles and role order, keep a locked persona, and rewrite brochure/dealer/test-drive CTAs to discovered URLs or a local contact ([plan.py:262](../server/agents/plan.py:262)). Then a persona image and a voice sample ([orchestrator.py:163](../server/orchestrator.py:163)). Output `plan.json`.
8. **Author** — [author.py:300](../server/agents/author.py:300) `run()`. System prompt `AUTHOR_SYSTEM` ([author.py:12](../server/agents/author.py:12)) formatted with `PRINCIPLES`, `AUTHOR_CRAFT` ([principles.py:136](../server/agents/principles.py:136)), audience, language ([author.py:334](../server/agents/author.py:334)). **`PITCH_SHAPE` is no longer injected** into the author (the 19 September audit's first fix landed in commit `1cfde68`). User content: product, brand, the full plan view including every segment goal and the plan's notes ([author.py:315](../server/agents/author.py:315)), the same fact registry rows, shots and images. Output schema `ScriptOut` ([schemas.py:261](../server/schemas.py:261)). Then the validator (2.3), one repair pass on issues ([author.py:346](../server/agents/author.py:346)), stable line ids `<segment>-L<n>` ([author.py:286](../server/agents/author.py:286)), the pixel audit ([author.py:362](../server/agents/author.py:362)), batch splitting over `LIMITS+4` words ([author.py:255](../server/agents/author.py:255)), and a timeline at 1.9 words per second ([author.py:227](../server/agents/author.py:227)). Output `script.json`.
9. **Pixel audit** (inside author) — [visuals.py:229](../server/agents/visuals.py:229) `align()`. Gemini looks at the real image bytes in batches of ≤12 ([visuals.py:180](../server/agents/visuals.py:180)) against every spoken line and must return every line and every image or the batch raises. **Only `coverage == "full"` keeps a picture bound to a line**; anything else nulls the line's visual ([visuals.py:275](../server/agents/visuals.py:275)). Model failure falls back to lexical rules ([visuals.py:288](../server/agents/visuals.py:288)). Output `visual-audit.json`.
10. **Deck** — [deck.py:284](../server/agents/deck.py:284) `build()`. One slide per segment with at least one verified line ([deck.py:316](../server/agents/deck.py:316)). Picture per slide by `choose_image()` ([deck.py:87](../server/agents/deck.py:87)): lexical score of tagged parts against the slide's words, +2 if the script picked that image, accept at ≥3, else the script's own first image, else the hero. Callouts from the model (`DECK_SYSTEM`, [deck.py:51](../server/agents/deck.py:51)) cleaned by `clean_callouts()` ([deck.py:177](../server/agents/deck.py:177)): ≤3 per slide, ≤8 words, must cite a fact if it states a figure or claim. Positions by `place_callouts()` ([deck.py:122](../server/agents/deck.py:122)): overlay only if the named part exists in that image with confidence ≥0.6 ([deck.py:28](../server/agents/deck.py:28)); anchor is the box centre, label at the first of eight candidate spots that is inside the frame, off the box and not overlapping; otherwise the side panel. Human overrides from `deck-overrides.json` win last ([deck.py:214](../server/agents/deck.py:214)). Output `deck.json`.
11. **FAQ** — [faq.py:84](../server/agents/faq.py:84) `run()`: likely questions from `QGEN_SYSTEM` ([rehearsal.py:12](../server/agents/rehearsal.py:12)) plus any FAQ documents, up to 20, each answered by the grounded answerer ([faq.py:109](../server/agents/faq.py:109)). Output `faq.json`; reused when the registry hash is unchanged ([faq.py:76](../server/agents/faq.py:76)).
12. **Align (the human checkpoint).** Six cards in order `visuals, facts, script, faq, persona, ctas` ([store.py:25](../server/store.py:25)). Card payloads from [align.py:72](../server/agents/align.py:72) `cards()`. Chat: `POST /align` ([app.py:430](../server/app.py:430)) → [graph.py:303](../server/graph.py:303) `handle_message()` → the parked `align_wait` resumes ([graph.py:94](../server/graph.py:94)) → [align.py:180](../server/agents/align.py:180) `respond()` returns `AlignOut{reply, actions[]}` ([schemas.py:409](../server/schemas.py:409)) with action types `revise | approve | request_upload | set_ctas | set_voice | edit_fact | remove_fact | build | answer | resolve_unknown`. [orchestrator.py:188](../server/orchestrator.py:188) `apply_actions()` executes them; prose is never executed. Direct edit routes live in `app.py` from `approve` at [app.py:450](../server/app.py:450). What resets approvals: a fact edit or removal resets all six ([orchestrator.py:219](../server/orchestrator.py:219)); a script edit resets script and visuals ([app.py:696](../server/app.py:696)); a deck edit resets script only ([app.py:835](../server/app.py:835)); CTA or voice changes reset their card plus script and visuals.
13. **Build gate.** `POST /build` → [app.py:899](../server/app.py:899) → readiness for build (adds streaming speech and voice-match checks for Sarvam, [app.py:371](../server/app.py:371)) → [graph.py:285](../server/graph.py:285) `start_build()` raises unless `all(approvals.values())`. Author, deck and FAQ are skipped when already done.
14. **Voice** — [voice.py:231](../server/agents/voice.py:231) `render_script()`: every narration line, deeper line, check-in, FAQ answer and filler through the provider chain ([voice.py:25](../server/agents/voice.py:25); Sarvam `bulbul:v3` here). Cache identity = provider + speaker + language + text ([voice.py:266](../server/agents/voice.py:266)); a matching hash skips the call ([graph.py:142](../server/graph.py:142)). Estimated timeline replaced by measured wave durations ([voice.py:238](../server/agents/voice.py:238)). A locked build with a missing required clip fails before bundle.
15. **Rehearsal** — [rehearsal.py:51](../server/agents/rehearsal.py:51) `run()`: reuses the FAQ bank as questions, scores the script against `SCORECARD` ([principles.py:121](../server/agents/principles.py:121)). Output `rehearsal.json`. This is an automated review, not proof of quality.
16. **Bundle** — [bundle.py:14](../server/agents/bundle.py:14) `build()`: joins script, slides, audio URLs, images, FAQ, guide, intake, CTAs; drops unverified lines ([bundle.py:58](../server/agents/bundle.py:58)); publishes an **immutable knowledge snapshot** `kb_…` via [knowledge.py:572](../server/knowledge.py:572). `finish` sets status `ready` ([graph.py:159](../server/graph.py:159)).

### 2.2 Stage summary

| Stage | Reads | Model (prompt) | Writes | Deterministic guard |
|---|---|---|---|---|
| Understand | sources, crawl | Gemini vision `IMAGES_PROMPT`; build chain `FACTS_SYSTEM` | `understanding.json`, `knowledge/` | box clamping, fingerprint dedupe, id ledger |
| Plan | understanding | build chain `PLAN_SYSTEM` + `PITCH_SHAPE` + `PROOF_BLOCK` | `plan.json` | id filters, role order, CTA grounding, locked persona |
| Author | understanding, plan | build chain `AUTHOR_SYSTEM` + `AUTHOR_CRAFT` | `script.json` | `validate()` (2.3), line ids, batch split, timeline |
| Pixel audit | script + image bytes | Gemini vision `MODEL_SYSTEM` | `visual-audit.json` | only `full` coverage binds |
| Deck | understanding, script, plan, overrides | build chain `DECK_SYSTEM` | `deck.json` | image score, ≤3 callouts, ≤8 words, part ≥0.6, never guessed |
| FAQ | understanding, docs | `QGEN_SYSTEM` + grounded answerer | `faq.json` | registry hash reuse |
| Align | all cards | `ALIGN_SYSTEM` → structured actions | `conversation.json` | actions executed by code only |
| Voice | script, faq | Sarvam / Gemini / GCloud TTS | audio + hashes | cache identity, required clips |
| Rehearsal | faq, script | `SCORE_SYSTEM` + `SCORECARD` | `rehearsal.json` | score clamp |
| Bundle | everything | none | `bundle.json`, `kb_` snapshot | unverified lines dropped |

### 2.3 The authoring validator — what "no citation, no claim" means in code

[author.py:123](../server/agents/author.py:123) `validate()`:

- `fact_ids` are filtered to **approved** registry ids ([author.py:126](../server/agents/author.py:126), [author.py:145](../server/agents/author.py:145)).
- A line matching `NUMBERISH` ([author.py:93](../server/agents/author.py:93): numbers with units or currency, two-plus digits, spelled counts like "six airbags") or `CLAIMISH` ([author.py:94](../server/agents/author.py:94): warrant, guarantee, certified, rated, fastest, best-in-class, free, discount, offer, included, supports, compatible, waterproof, IP6x) **with no surviving fact id** is marked `unverified` ([author.py:158](../server/agents/author.py:158)). Unverified lines are excluded from the timeline, the deck and the bundle; they never reach voice.
- A visual ref that does not exist is cleared to `kind: none` ([author.py:152](../server/agents/author.py:152)).
- A question mark in narration is an issue ([author.py:177](../server/agents/author.py:177)); a check-in carrying a figure or claim is deleted ([author.py:172](../server/agents/author.py:172)).
- Word budgets `LIMITS` ([author.py:95](../server/agents/author.py:95)): intro/outcome/proof ≤38, features ≤40, establish ≤36, closing ≤45, route ≤360, overview 23–28 words.
- Jargon warnings for the everyday audience ([author.py:99](../server/agents/author.py:99)).

---

## 3. Demo run, step by step — [Agent B — Run Tracer]

### 3.1 The path, in the order the customer experiences it

1. **Load.** `#/play/<id>` → [app.js:99](../web/app.js:99) `renderPlay()` fetches `GET /api/demos/{id}/bundle` ([app.py:943](../server/app.py:943)). The bundle carries `segments` (each with `lines[{id,text,audio,visual,fact_ids,step,delivery}]`, `checkin`, `deeper`), `slides` (12 for Creta), `facts` (181), `faq`, `fillers`, `intake`, `ctas`, `knowledge_snapshot_id` (`kb_2d616ba1…`) and `runtime = {version:1, continuous_voice:true, tools:["calculator","source_lookup"], overview:{text,audio,fact_ids,…}}`.
2. **Mount.** [player.js:44](../web/player/player.js:44) `mountPlayer()` builds state `S` (phase, slide, line, route, profile, transcript, `sessionId`). Every async step checks the run token from `newRun()` ([player.js:177](../web/player/player.js:177)); a stale result cannot touch the UI. `createLive()` ([player.js:119](../web/player/player.js:119)) opens the WebSocket client; `startLive()` ([player.js:152](../web/player/player.js:152)) connects and starts capture unless `?mute=1`.
3. **Intake: one question, then wait.** [player.js:903](../web/player/player.js:903) `runIntake()` speaks `bundle.intake.q1` ("Hello, I'm Priya, your Hyundai guide. What matters most in your next car?") and waits. The microphone was requested once by [live-voice.js:70](../web/player/live-voice.js:70) `openCapture()` (`getUserMedia`, PCM frames from [voice-worklet.js](../web/player/voice-worklet.js)). The answer becomes `S.profile.{name, why, focus}` ([player.js:877](../web/player/player.js:877)).
4. **Explore: personalise while the overview plays.** [player.js:914](../web/player/player.js:914) fires `POST /run/pitch` with a 12 s timeout → [app.py:1009](../server/app.py:1009) `run_pitch()` → `run_turn(kind="explore")` → graph node `explore` ([runtime_graph.py:1505](../server/runtime_graph.py:1505)) → [pitch.py:254](../server/agents/pitch.py:254) `plan_pitch()`. Meanwhile the recorded overview plays ([player.js:924](../web/player/player.js:924)); the player waits only 150 ms more for the plan ([player.js:939](../web/player/player.js:939)). What the pitch **may** change: the order of unseen proof/features/establish segments (max 3 proof + 1 features + 1 establish, establish last, [pitch.py:399](../server/agents/pitch.py:399)); replacement slide speech composed **only from exact reviewed lines** keyed by text and fact ids ([pitch.py:475](../server/agents/pitch.py:475)); one ≤8-word verbatim customer quote as a preface ([pitch.py:497](../server/agents/pitch.py:497)). What it **may not**: invent a bridge ([pitch.py:385](../server/agents/pitch.py:385)), invent a number ([pitch.py:366](../server/agents/pitch.py:366)), add a question, revisit seen segments unless the customer explicitly changed priority, or plan against a changed publication ([pitch.py:262](../server/agents/pitch.py:262)). No plan in time → "I couldn't finish tailoring the route just now…" and the reviewed route ([player.js:965](../web/player/player.js:965), [player.js:489](../web/player/player.js:489)).
5. **Play.** [player.js:579](../web/player/player.js:579) `playFrom()` → `showSlideView()` → [player.js:553](../web/player/player.js:553) `playLines()`: for line j, `view.setRevealed(j)` reveals that line's callouts ([slide.js:116](../web/slide.js:116)), the caption shows `sources: F…`, then `speak()` ([player.js:287](../web/player/player.js:287)) plays the recorded clip or streams through the live socket. Audio leads, screen follows.
6. **Check-ins.** After a slide with `checkin.text`, `waitFor()` ([player.js:471](../web/player/player.js:471)) holds with chips "Continue / Tell me more / I have a question". Voice replies are classified by `interpretReply()` ([player.js:438](../web/player/player.js:438)): yes → continue; no → `playDeeper()` ([player.js:605](../web/player/player.js:605)); a question → the question path. Nothing resumes on a timer.
7. **Interruption.** Local voice-onset detection in [live-voice.js:87](../web/player/live-voice.js:87) (RMS above noise × 3.5 for 4 frames) → `speechStart()` cancels audio → [player.js:123](../web/player/player.js:123) `onSpeechStart()` → `captureOrigin()` ([player.js:665](../web/player/player.js:665)) saves the exact playback position once, `interruptAll()` ([player.js:437](../web/player/player.js:437)) bumps the run token, cancels speech, listening and waits. The server mirrors it: `speech_start` → [runtime_live.py:69](../server/runtime_live.py:69) `stop_turn(preserve_planning=True)`. Session, turn, utterance and capture-generation ids reject stale audio or transcripts.
8. **Question turn.** [player.js:716](../web/player/player.js:716) `handleQuestion()` sends question, the **last 8 transcript messages**, profile, `slide_id`, session id and demo version ([player.js:739](../web/player/player.js:739)) over the socket ([live-voice.js:181](../web/player/live-voice.js:181)). [runtime_live.py:154](../server/runtime_live.py:154) → `answer()` → [runtime_graph.py:1548](../server/runtime_graph.py:1548) `run_turn()` → `graph.ainvoke(..., timeout=12.0)` ([runtime_graph.py:1569](../server/runtime_graph.py:1569)). Node order: `retrieve → reason → (tools → reason)* → validate → delivery_plan` ([runtime_graph.py:1531](../server/runtime_graph.py:1531)).
9. **Acknowledgement.** [player.js:696](../web/player/player.js:696) `questionResult()` waits 250 ms ([player.js:697](../web/player/player.js:697)); if no answer yet, it plays the shortest compatible reviewed filler ("Let me check that.", chosen by [player.js:37](../web/player/player.js:37)). A ready answer cuts it short.
10. **Answer and evidence slide.** Routing was decided server-side by [deck.py:462](../server/agents/deck.py:462) `route_for()`: `stay` if the current slide carries a cited fact, else `jump` to the slide sharing the most cited facts, else `none`; a decline or clarification never moves the slide. Player: jump → show that slide with all callouts, highlight the cited callout ([player.js:784](../web/player/player.js:784)); caption shows `sources: … · conditions: …`. Speech streams: `delivery.request` → [runtime_delivery.py:45](../server/runtime_delivery.py:45) → [sarvam_stream.py:128](../server/llm/sarvam_stream.py:128) (24 kHz PCM chunks) → [live-voice.js:206](../web/player/live-voice.js:206) `queueAudio()`. Then `holdConversation()` ([player.js:683](../web/player/player.js:683)) waits for Continue, another question or a CTA.
11. **Continue: exact return point.** [player.js:840](../web/player/player.js:840) `resumeAfterQA()` plays "Let's get back to where we were." then [player.js:847](../web/player/player.js:847) `resumePlayback(origin)`: an interrupted line replays from its start; an interruption at a check-in resumes at the next slide; deeper and closing have their own returns. An answer-slide jump never overwrites the saved origin.
12. **Close, lead, session, summary.** [player.js:637](../web/player/player.js:637) `closeFlow()` shows the closing slide and the CTA chips; the customer must choose explicitly ([player.js:656](../web/player/player.js:656)). Lead form ([player.js:827](../web/player/player.js:827): ten-digit phone, consent text) → [app.py:1024](../server/app.py:1024) `run_lead()`. Session record ([player.js:992](../web/player/player.js:992)) → [app.py:1117](../server/app.py:1117) `save_session()` → [storage.py:29](../server/storage.py:29). An ended session starts a background summary ([app.py:1140](../server/app.py:1140) → [summary.py:47](../server/agents/summary.py:47)) from the words actually heard.

**Legacy REST path.** [app.py:964](../server/app.py:964) `run_qa()` routes to the graph whenever the body carries `runtime_version: 1` or a `session_id` on a v1 bundle. The player always sends `session_id`, so even the HTTP fallback runs the graph. The old path `faq.match()` ([faq.py:132](../server/agents/faq.py:132), token overlap) → `qa.answer()` ([qa.py:154](../server/agents/qa.py:154)) is used only for pre-v1 bundles or callers without a session.

### 3.2 The runtime graph nodes

| # | Node / function | Line | What it does |
|---|---|---|---|
| 0 | `run_turn()` | [1548](../server/runtime_graph.py:1548) | claims a 12 s turn ([runtime_state.py:132](../server/runtime_state.py:132)), merges the previous checkpoint's profile and history (server keeps the last 16), pins the `snapshot_id`, invokes the graph, and on timeout returns a fixed "taking longer than expected" result |
| 1 | `explicit_scope()` | [798](../server/runtime_graph.py:798) | regex scope from the question: model, variant, generation, model year, market, powertrain, transmission; "all variants" is a request quantifier that expires unless renewed |
| 2 | `retrieve()` | [916](../server/runtime_graph.py:916) | query = question + last 2 user messages; loads `knowledge/snapshots/{kb_…}.json`; [knowledge.py:635](../server/knowledge.py:635) `retrieve()` is BM25 plus fixed concept and character-trigram cosine over claim + value + conditions + scope, scope-filtered, `limit=14`; condition-only donor facts (e.g. a transmission requirement) are attached but cannot be cited |
| 3 | `reason()` | [970](../server/runtime_graph.py:970) | refuses `file://`; if the customer explicitly asked to check a URL, dispatches the lookup first; otherwise builds the payload ([991](../server/runtime_graph.py:991)) and calls the provider chain via [runtime.py](../server/llm/runtime.py) with budget = time left − 0.25 s; returns `TurnDecision` ([runtime_state.py:52](../server/runtime_state.py:52)) = answer, clarify, or tools |
| 4 | `after_reason()` | [1027](../server/runtime_graph.py:1027) | to `tools` only while rounds < 2 and calls < 4 |
| 5 | `tools_node()` | [1031](../server/runtime_graph.py:1031) | runs `calculate()` or `source_lookup()` (≤5 s), merges new evidence ids, back to `reason` |
| 6 | `validate()` | [1467](../server/runtime_graph.py:1467) | `validate_decision()` ([1069](../server/runtime_graph.py:1069)) per sentence; then one optional composition repair ([1385](../server/runtime_graph.py:1385), needs ≥3 s left, no tools, same validator); then slide routing via `deck.route_for` ([1490](../server/runtime_graph.py:1490)) |
| 7 | `delivery_plan()` | [1520](../server/runtime_graph.py:1520) | utterance id `u_<sha>`, `DeliveryPlan(speech, next_interaction = clarify \| listen)`, checkpoint `ready_to_deliver` |
| 8 | `explore()` | [1505](../server/runtime_graph.py:1505) | the personalisation branch (3.1 step 4) |

Validator order inside `validate_decision()`, per sentence: fixed interaction acts ([runtime_acts.py](../server/runtime_acts.py)) → citation exists → own-limit and behaviour rewrites → coverage claims ([runtime_coverage.py](../server/runtime_coverage.py)) → uncited fact → web attribution → source lineage → required conditions ([runtime_facts.py](../server/runtime_facts.py)) → projected support and variant scope → feature support → negative polarity → unsupported quantity or unit → live-table universals ([runtime_tables.py](../server/runtime_tables.py)) → policy relations → equipment pairing → ordinal fitment → unqualified calculation → speech markup; then audited-calculation insertion and EMI terms ([runtime_emi_delivery.py](../server/runtime_emi_delivery.py)); 115-word cap.

### 3.3 Budgets

| Constant | Value | Where |
|---|---|---|
| Whole turn | 12 s | [runtime_state.py:132](../server/runtime_state.py:132), [runtime_graph.py:1569](../server/runtime_graph.py:1569) |
| Validation and delivery reserve | 250 ms | [runtime_graph.py:1007](../server/runtime_graph.py:1007) |
| First provider (Gemini) cap | 7 s | [runtime.py:84](../server/llm/runtime.py:84) |
| Per-provider timeout | 15 s | [config.py:61](../server/config.py:61) |
| Provider order | gemini → claude → runware | [config.py:60](../server/config.py:60) |
| Claude insufficient-credit cooldown | 60 s | [runtime.py:25](../server/llm/runtime.py:25) |
| Tool rounds / calls | 2 / 4 | [runtime_graph.py:1028](../server/runtime_graph.py:1028) |
| URL lookup | ≤5 s, ≤3 pages, ≤3 child links, ≤6 passages, 18 000 chars | [runtime_tools.py:182](../server/runtime_tools.py:182) onwards |
| Retrieval | 14 facts | [runtime_graph.py:930](../server/runtime_graph.py:930) |
| Filler grace | 250 ms | [player.js:697](../web/player/player.js:697) |
| Hedge lane | off by default, 5 s delay (local server runs 3 s) | [config.py:63](../server/config.py:63) |

---

## 4. Question 1 — images: how many, and how they map to content — [Agent A, with Orchestrator notes]

**How many.** No count limit anywhere ([app.py:173](../server/app.py:173), [store.py:320](../server/store.py:320)). Per-file cap 1 GB. Accepted: jpg, jpeg, png, webp, gif, avif, heic, heif. One hero, one intro video, any number of product images. A video-only demo derives up to 12 stills as product images ([understand.py:102](../server/agents/understand.py:102)). The practical costs scale per image: Gemini tagging in batches of 12, pixel audit in batches of 12, each cached by image revision.

**How an image becomes content, in order.** There are four owners, and that is the design weakness.

| Step | Owner | What is decided | Where |
|---|---|---|---|
| 1 Tag | Understand (Gemini vision) | description, angle, quality 1–5, `parts[{name, box{x,y,w,h}, confidence}]`, id `im01…` | [understand.py:222](../server/agents/understand.py:222), [schemas.py:27](../server/schemas.py:27) |
| 2 Map | code | fact ↔ picture lexical score (parts ×3, description ×1); price, warranty, airbags, boot litres are `NON_VISUAL_FACT` and get no picture | [visuals.py:333](../server/agents/visuals.py:333), [visuals.py:38](../server/agents/visuals.py:38) |
| 3 Choose the set | Planner | `visual_refs` per segment, best first; a missing literal picture goes to `visual_gaps` | [schemas.py:174](../server/schemas.py:174), [plan.py:78](../server/agents/plan.py:78) |
| 4 Bind per line | Author | each line's `visual {kind: shot\|image\|none, ref, focus}` | [schemas.py:234](../server/schemas.py:234) |
| 5 Prove | Pixel audit (Gemini) | keeps a binding only at `coverage == "full"`; else nulls it | [visuals.py:275](../server/agents/visuals.py:275) |
| 6 Collapse to one | Deck | **one `image_id` per slide** by score (+2 for the script's pick, ≥3, else the script's first image, else hero) | [deck.py:87](../server/agents/deck.py:87), [schemas.py:320](../server/schemas.py:320) |
| 7 Override | Human in Align | picture, title, callout text and facts, dragged label positions | [app.py:760](../server/app.py:760), [deck.py:214](../server/agents/deck.py:214) |

**Concrete: Creta slide `sl04`.** File `creta-interior…830x530-6.jpg` → `im08`, description "Rear seat row with 60:40 split seat back folded flat…", one part `rear seat` box `{x .099, y .427, w .882, h .571}` confidence 0.95. Planner segment `seating-and-cargo` chose `["im08","im06","im07"]`. The author bound line 1 → im08, line 2 → im06, line 3 → im07. The deck kept **im08 only** for the whole slide. Callout `sl04-reviewed-1` "Split rear seat" cites F096, anchors at the box centre `{.54, .7125}`, label at the first candidate spot above the box, revealed on line 0.

**Orchestrator note.** The player never calls the renderer's `setImage()` ([slide.js:122](../web/slide.js:122)); the only media lookup, `mediaUrlFor()` ([player.js:839](../web/player/player.js:839)), is unused for slides. So lines 2 and 3 of that segment talk about the bench and the luggage while the screen keeps showing the folded seat. The audited per-line binding is thrown away on screen. That is the single biggest gap between what the pipeline proves and what the customer sees, and section 5 proposes the fix.

---

## 5. Question 2 — is the slide a template, what are its constraints, and how to keep it templatized but flexible — [Agent A constraints · Orchestrator proposal]

### 5.1 What it is

**A fixed DOM template rendered live from data.** `deck.py` never writes layout; it writes normalised fractions. [slide.js:8](../web/slide.js:8) `renderSlide()` builds: a `.slide-pic` with one `<img>` and an SVG leader layer; per overlay callout a numbered chip at `label_pos`, a dot at `anchor`, and one leader line between them ([slide.js:19](../web/slide.js:19)); an evidence rail listing every callout with its fact ids ([slide.js:29](../web/slide.js:29)); in player mode a chapter heading keyed by slide kind ([slide.js:31](../web/slide.js:31)). `layout()` ([slide.js:54](../web/slide.js:54)) fits the picture at native aspect ratio and, on wide stages, moves a chip's **displayed** box if it would collide with the heading or the bottom evidence band, without touching saved data. `setRevealed(lineIdx)` ([slide.js:116](../web/slide.js:116)) shows callouts whose `reveal_on_line ≤ lineIdx`.

### 5.2 Constraint inventory

| # | Constraint | Enforced at | Change site |
|---|---|---|---|
| 1 | One script segment = one slide; a segment with no verified line gets no slide | [deck.py:316](../server/agents/deck.py:316) | deck.py |
| 2 | **One image per slide**; only images, never video shots | [schemas.py:320](../server/schemas.py:320), [deck.py:296](../server/agents/deck.py:296) | schema + deck.py |
| 3 | Fixed skeleton: `hero_open` first, `closing`, `hero_close` last; kinds enumerated | [deck.py:314](../server/agents/deck.py:314), [schemas.py:316](../server/schemas.py:316) | deck.py + schema |
| 4 | Motion only `zoom_in`, `pan_left`, `none`, alternating by index | [deck.py:325](../server/agents/deck.py:325), [schemas.py:322](../server/schemas.py:322) | deck.py |
| 5 | **≤3 callouts per slide** | [deck.py:25](../server/agents/deck.py:25) | deck.py |
| 6 | ≤8 words per callout, whole-or-nothing | [deck.py:26](../server/agents/deck.py:26), [app.py:811](../server/app.py:811) | deck.py + app.py |
| 7 | ≤6-word title | [deck.py:27](../server/agents/deck.py:27) | deck.py + align.js |
| 8 | No callouts on hero slides | [deck.py:352](../server/agents/deck.py:352) | deck.py |
| 9 | A callout with a figure or claim must cite an approved fact | [deck.py:184](../server/agents/deck.py:184), [app.py:808](../server/app.py:808) | author.py regexes |
| 10 | **One anchor per callout**, only on a tagged part of that image with confidence ≥0.6; anchor = box centre, never guessed; else side panel | [deck.py:128](../server/agents/deck.py:128), [deck.py:28](../server/agents/deck.py:28) | deck.py |
| 11 | Chip footprint fixed 0.30 × 0.09 of the frame; 8 candidate spots; inside frame, off the part box, non-overlapping | [deck.py:29](../server/agents/deck.py:29), [deck.py:114](../server/agents/deck.py:114) | deck.py |
| 12 | Evidence rail always lists all callouts; overlay needs `label_pos` and `anchor` | [slide.js:21](../web/slide.js:21), [slide.js:29](../web/slide.js:29) | slide.js |
| 13 | Reveal is cumulative by line index | [deck.py:189](../server/agents/deck.py:189), [slide.js:117](../web/slide.js:117) | both |
| 14 | Align coordinates are immutable data; dragged positions are 0–1 fractions trusted on rebuild | [app.py:816](../server/app.py:816), [deck.py:245](../server/agents/deck.py:245) | app.py + deck.py |
| 15 | Runtime collision handling moves only the displayed chip, ≥700 px stages only | [slide.js:72](../web/slide.js:72) | slide.js |
| 16 | Callout ids survive a rebuild only on unambiguous fact identity; overrides keyed by id | [deck.py:359](../server/agents/deck.py:359) | deck.py |
| 17 | Overrides may pick only allowed images and approved facts | [app.py:773](../server/app.py:773) | app.py |
| 18 | Editing a slide un-approves `script`, not `visuals` | [app.py:835](../server/app.py:835) | app.py + align.js |

So yes: your suspicion is right on both counts. One picture per slide, one pointer per callout, at most three pointers per slide, and the picture never changes while the segment plays.

### 5.3 Proposal — keep one template, make its media a sequence — [Orchestrator]

**The call.** Add *beats* to the existing slide: an ordered list of pictures that switch when a given line starts, exactly the way callouts already reveal by line. Do not add new layouts, an LLM layout composer, or video on slides.

**Why this one.** The pipeline already produces and audits the data. The author binds each line to a picture; the pixel audit proves each binding at `full` coverage; the deck throws two of three away. Beats re-use that proven binding, cost no new prompt and no new model call, and leave every grounding rule untouched. The renderer already has an unused `setImage(url, parts)` ([slide.js:122](../web/slide.js:122)), so the screen side is wiring, not new drawing.

**Data model delta** (this is a data-model change, so per the project rule it needs your approval before code):

| Object | Today | Proposed | Compatibility |
|---|---|---|---|
| `Slide` | `image_id: Optional[str]` | add `beats: list[{image_id, from_line}]` (≥1) | `image_id` stays and equals `beats[0].image_id`, so old bundles and the exporter keep working |
| `Callout` | `anchor: {x,y}` on the slide's one image | add `image_id` (which beat it belongs to) and `anchors: list[{x,y}]` (1–2 points) | `anchor` stays and equals `anchors[0]`; `image_id` defaults to `beats[0]` |
| `deck-overrides.json` | keyed by callout id | keyed by callout id + image id | old overrides apply to beat 0 |

**Builder rule (deterministic, no LLM).** `choose_beats(segment)`: walk the segment's verified lines; take each line's image ref that the pixel audit marked `full`; drop consecutive duplicates; a line with `none` keeps the previous beat; beat 0 falls back to today's `choose_image()` score so the hero rule survives. Callouts are placed per beat with the same `place_callouts()` rule (part ≥0.6 **in that image**, box centre, eight spots), and the existing ≤3 callouts, ≤8 words and "cite or drop" rules apply **per beat**. Hero slides still get no callouts.

**Renderer rule.** `setRevealed(lineIdx)` also selects the beat with the largest `from_line ≤ lineIdx`; if it differs from the current one, crossfade the image and swap `image_parts`; only callouts whose `image_id` is on stage are shown. Leader geometry recomputes on image load, which the renderer already does ([slide.js:124](../web/slide.js:124)).

**Multi-anchor** (the "one pointer" limit). Allow 1–2 anchors on one callout when the same part name is tagged twice in the image (both front seats ventilated, both rear vents). Same rule per anchor: tagged part, confidence ≥0.6, box centre. The renderer draws one chip and N leader lines. This is a small extension and can ship after beats.

**Align.** A beat strip under the picture (thumbnails, one per beat); drag saves `label_pos` per callout per image; overrides keyed accordingly. The rail lists all callouts of the current beat.

**Phasing.** Phase 1: schema + `choose_beats` + renderer + player wiring (`schemas.py`, `deck.py`, `slide.js`, `player.js`), with `beats` derived and `image_id` unchanged, so nothing visible changes until a segment has ≥2 audited pictures. Phase 2: Align beat editor and per-image overrides. Phase 3: multi-anchor. Free evals: extend `deck` contracts (currently 320) with a two-beat segment fixture and a "no full-coverage image → single beat" fixture.

**Rejected alternatives, and why.**

| Alternative | Why not |
|---|---|
| Let the model compose a free layout per slide (HTML or a layout enum it chooses) | Loses drag-editing in Align, the "position never guessed" rule, the cinematic consistency you chose to keep, and adds a paid call per slide. A layout decided by an LLM is the one thing the reviewer cannot audit. |
| Video shots as slide media | Shots have no part boxes, so no anchors; the MP4 exporter is parked; ffmpeg is absent on the machine; the intro film already carries video where it earns its place. |
| A second "pair" template (two pictures side by side, e.g. seat up vs folded) | Real, but it needs a new template, a new Align mode and a planner field naming the pair. Do it only after beats show the two-picture segments actually exist in real decks. |
| Raise the ≤3 callouts limit | Three labels is the legibility ceiling on a 830×530 picture with a heading and an evidence band; more labels turns the slide back into a brochure. Beats give you more labels *over time* without more on screen at once. |

---

## 6. Question 3 — what the agent can see and use during a run — [Agent B, with Orchestrator notes]

**Short answer.** The runtime agent has no general web access and no access to the demo's own source websites. On each question it sees a pinned, reviewed fact set, the customer's own words, and two tools: a calculator and a URL lookup that works **only on a URL the customer literally said or typed in this session**. Everything it says is validated sentence by sentence before it is spoken.

### 6.1 Inputs on one question turn

| Input | Detail | Where assembled |
|---|---|---|
| Pinned knowledge snapshot | `knowledge/snapshots/{kb_…}.json`, pinned per session; lexical retrieval (BM25 + concept and trigram cosine, not vectors) returns ≤14 facts | [runtime_graph.py:925](../server/runtime_graph.py:925), [knowledge.py:635](../server/knowledge.py:635) |
| What a fact looks like to the model | `id, kind, claim, value, conditions, scope, truth, entity, source {ref, locator}, source_origin ("website" or "uploaded")`. The raw quote and the source URL are **stripped**; the model never sees a hostname for a stored fact | [runtime_graph.py:149](../server/runtime_graph.py:149) |
| Condition-only donors | e.g. a transmission requirement attached to a feature; usable as a caveat, never as a new claim | [runtime_graph.py:938](../server/runtime_graph.py:938) |
| Customer profile | name, why, focus, customer state, language, plus resolved scope (trim, year, market) | [player.js:837](../web/player/player.js:837), [runtime_graph.py:942](../server/runtime_graph.py:942) |
| Conversation | client sends last 8 messages; server keeps last 16; prompt gets last 12; retrieval query uses last 2 user turns | [player.js:739](../web/player/player.js:739), [runtime_graph.py:1562](../server/runtime_graph.py:1562), [runtime_graph.py:922](../server/runtime_graph.py:922) |
| Current slide | used for routing only, **not** in the prompt | [runtime_graph.py:1490](../server/runtime_graph.py:1490) |
| Tools so far, errors, remaining budget, allowed fixed acts, guide persona, product, CTAs | | [runtime_graph.py:991](../server/runtime_graph.py:991) |
| Competitor examples | only when `settings.competition == "on"` | [runtime_graph.py:1000](../server/runtime_graph.py:1000) |

### 6.2 The two tools ([runtime_tools.py](../server/runtime_tools.py))

- **Calculator** ([runtime_tools.py:91](../server/runtime_tools.py:91)): operations `emi, fuel_cost, difference, sum, product, divide, percentage`. Every operand needs a name, value, unit, `source_id` (`customer` or an evidence id) and a **quote**; the quote must appear in the customer's words or the fact text, the value must appear in the quote, and the unit is bound to that occurrence ([runtime_tools.py:109](../server/runtime_tools.py:109)). Decimal math, half-up rounding, result stored as a `D<sha>` fact with its derivation and `truth: modeled`. If the model then fails to word the answer, the graph can still deliver the audited number with its assumptions (`calculation_fallback`).
- **URL lookup** ([runtime_tools.py:168](../server/runtime_tools.py:168)): `allowed = supplied_urls(question, history)`; a URL not in that list raises "Provide the exact public website URL you want checked" ([runtime_tools.py:176](../server/runtime_tools.py:176)). `supplied_urls()` ([runtime_tools.py:19](../server/runtime_tools.py:19)) is a regex over the customer's own messages, max 8. Then: same host only, model and market tokens must match, `price-in-<city>` pages only if the customer named the city, ≤3 pages, ≤5 s, private networks and unsafe redirects rejected ([crawl.py:40](../server/crawl.py:40)). Results become turn-scoped `W<sha>` facts with `provenance: live_web` and `scope_unverified: true`; they never enter the registry.

### 6.3 "As per Hyundai's official website" — can it say that?

- **Only if the customer supplies a hyundai.com URL in this session.** Then, if the lookup returns passages, the validator forces attribution: a sentence citing live-web evidence that lacks "according to" or a "page/site says/lists/…" phrase is rewritten to `"According to www.hyundai.com, …"` ([runtime_graph.py:1180](../server/runtime_graph.py:1180)).
- **For a stored fact it must not, and mostly cannot.** The model has no hostname for stored facts; a page claim ("according to the website", "the page lists…") with no live-web fact is rejected as `unverified_web_attribution` ([runtime_graph.py:1174](../server/runtime_graph.py:1174)). A named "provided/supplied page" that was not actually fetched is also rejected.
- **A small gap.** The page-claim regex matches "according to … website" and "website … lists/shows/states", but not the phrase "as per". A sentence like "As per Hyundai's website, the Creta offers X" about a stored fact would be blocked only by the prompt instruction ([runtime_graph.py:73](../server/runtime_graph.py:73)), not by code. Worth one regex alternation if you want the guarantee.
- **Where the brand's website does reach the customer.** Build-time crawling ([crawl.py](../server/crawl.py)) reads the brand site within the model and market boundary; those facts carry `source_origin: website`, a locator and a URL, all visible in Align and in the player's `sources:` caption as fact ids. The provenance exists; it is just not spoken as "the website".

**Orchestrator recommendation, if you want the behaviour you described.** Add a `DEMO_URLS` allowlist to the turn: the demo's approved `product` URL sources (already stored on `demo.sources`) join `CUSTOMER_URLS` as lookup targets, with the same host, model and market scoping, so the guide can say "According to hyundai.com, checked just now, …" when a customer asks for the current price or offer. It fits the existing invariant that live evidence stays turn-scoped and attributed, and it needs no new tool. It is an architecture-shaping change (a new evidence source at runtime), so it needs your explicit approval and a delta against diagram 05 before code.

### 6.4 What it cannot do

No registry writes (the graph only reads snapshots), no code execution, no local files ("I can't access local files.", [runtime_graph.py:964](../server/runtime_graph.py:964)), no browsing beyond the customer's URLs. Fixed-wording acts ([runtime_acts.py:27](../server/runtime_acts.py:27)) cover its own limits: "I cannot guarantee a future resale value.", "I could not verify your dealer's current stock or delivery timing.", "Could you share <inputs>?" — the model picks the act id, code supplies the words, and acts can never carry a product fact. When nothing survives validation: "I don't have a supported answer to that yet. We can check it with a salesperson or carry on." ([runtime_graph.py:1360](../server/runtime_graph.py:1360)); partial: "There's a part of that I couldn't verify, so I won't guess." CTAs are suggestions only; the customer must choose.

### 6.5 The reasoning prompt, key lines ([runtime_graph.py:34](../server/runtime_graph.py:34))

- "answer: normally 1–3 short sentences (75 words total), each with supporting fact_ids" (line 40); "For an explicit comparison or list, use up to four sentences and 100 words" (83).
- "clarify: ONE useful question when a missing input/ambiguous scope changes the answer" (41).
- "Every factual sentence must cite evidence IDs" (48). "Calculator does all arithmetic; never calculate a new figure yourself" (107). "source_lookup(url, query) only checks a URL in CUSTOMER_URLS. Never invent a URL" (119).
- "For a refusal, state your own limit directly" (71). "No markdown, SSML… No guarantee to submit/book/contact anyone" (127).

---

## 7. Question 4 — planner → author, with a real 10–15 second example — [Agent A, with Orchestrator diagnosis]

Segment `seating-and-cargo` of the Creta demo. Two datasets: **(M)** the genuine model run on 19 September at 16:55 (`gemini-3.8-flash`, under the pre-CR45 prompts, preserved in `output/creta-night-final/before-reviewed-install/`); **(S)** the session-authored replacement installed at 23:24 that plays today. Both are about 11 seconds of speech.

### 7.1 What the planner receives ([plan.py:230](../server/agents/plan.py:230))

System prompt: `PLAN_SYSTEM` with `PRINCIPLES`, `CUSTOMER_STATES`, `PITCH_SHAPE` (the seven-step demo shape, "Every batch ≤ 20 seconds (≤ 38 spoken words)"), `PROOF_BLOCK` (say the decision → show the evidence → explain relevance), the everyday-audience instruction and the language instruction. User content, in order: `PRODUCT`, `BRAND PROFILE`, `PRODUCT URL`, `CONFIGURED VOICE` (locked Priya), action-URL candidates, `APPROVED FACT REGISTRY (181)` as rows, `OPEN UNKNOWNS` (89 lines), `VIDEO SHOTS (0)`, `IMAGES (12)`.

The three registry rows this segment cites, exactly as inlined:

```
F032 [spec·stated] Body style and seating capacity: Compact SUV, 5 doors, 5 seats (conditions: Standard across all variants) (source: src_51f57f; locator: page 3, Key facts; quote: "Compact SUV, 5 doors, 5 seats")
F096 [feature·stated] Rear seat split functionality: 60:40 Split rear seat (conditions: Standard rear seating arrangement) (source: src_cb7525943988; locator: 60:40 Split rear seat · block 43; quote: "60:40 Split rear seat")
F097 [feature·stated] Rear seat recline: 2-step rear reclining seat in select trims (conditions: Available in select trims only) (source: src_cb7525943988; locator: FAQs · 4.Does the CRETA have a rear-seat reclining function? · block 101; quote: "The CRETA offers a 2-step rear-seat reclining function in select trims.")
```

### 7.2 What the planner produced

**(M), the real model output** (`SegmentPlan`, verbatim):

```json
{"id":"seating-and-cargo","title":"Passenger Comfort and Cargo Flexibility","role":"proof",
 "goal":"Showcase rear passenger comfort with the 2-step reclining seat and expandable luggage space using the 60:40 split.",
 "outcome":"Verify rear seating space and boot flexibility","topic":"space",
 "fact_ids":["F032","F075","F096","F097","F098","F106"],"usp_ids":["usp-space-flexibility"],
 "visual_refs":["im06","im08","im07"],"priority_topic":false}
```

**(S), the session-authored plan** that plays today. Its `goal` uses the post-CR45 three-part form:

> MOMENT: when people and bags share a trip, notice the pictured split seat with one part folded. SPOKEN: F096 split rear-seat arrangement, then F097 recline on selected trims; keep the split ratio and recline-step count in DEEPER with F032 seating count and an honest missing boot-volume/measurement-basis limit. VISUAL / HANDOFF: im08 proves the split arrangement, im06 shows the bench and im07 illustrates luggage only; never infer litres or guaranteed fit from bags in a photograph; leave attention on what the buyer would load, budget 31-36 words, no check-in.

Title "When the rear seat folds", `fact_ids [F032, F096, F097]`, `visual_refs [im08, im06, im07]`.

### 7.3 What the author receives ([author.py:315](../server/agents/author.py:315))

System prompt: `AUTHOR_SYSTEM` with `PRINCIPLES`, `AUTHOR_CRAFT`, audience, language. **No `PITCH_SHAPE`.** Rule 4 still restates the word budgets in prose ([author.py:31](../server/agents/author.py:31)). User content: `PRODUCT`, `BRAND`, `PLAN` (the full plan view: every segment goal, intake wording, voice with sample line, notes), `FACT REGISTRY` (the same 181 rows), shots, images. Output schema `ScriptOut`; `LineOut` describes a line as "one natural spoken thought, 1–2 short sentences; the whole batch fits 10–20 seconds" ([schemas.py:240](../server/schemas.py:240)). Then the validator in 2.3.

### 7.4 What the author produced

**(M), the real model output**, title "Room for everyday plans", with a check-in "Is that enough detail on the seats and boot for now?":

| Line | Visual | Facts | Text | Audio |
|---|---|---|---|---|
| L1 (say) | im08 | F096, F097 | "The rear seats offer a split-folding arrangement for luggage; recline adjustment is available on selected variants." | 7.59 s |
| L2 (show) | im07 | none | "Check the rear seats and boot with the people or luggage you expect to carry." | 4.27 s |
| deeper D1 | im06 | F032 | "The CRETA has five seats. Try the rear bench with the people who usually travel with you to judge the space for yourselves." | |
| deeper D2 | im08 | F096 | "The rear seat has a sixty-forty split. Bring your usual luggage when you visit to check how the space works for you." | |

31 words, 11.9 s spoken, 17.0 s with the check-in, `issues: []`.

**(S), what plays today**, title "When the rear seat folds", no check-in:

| Line | Visual | Facts | Text | Audio |
|---|---|---|---|---|
| L1 (show) | im08 | F096 | "The split rear seat is shown with one part folded." | 3.58 s |
| L2 (show) | im06 | F097 | "Selected trims also offer rear-seat recline." | 3.24 s |
| L3 (translate) | im07 | none | "Bring your usual bags to check how the boot works for you." | 3.84 s |
| deeper D3 | | none | "I can't confirm a boot-capacity figure or its seating and measurement basis from these details…" | |

28 words, 10.7 s, `issues: []`.

### 7.5 Why it reads flat — [Orchestrator diagnosis, built on Agent A's observations and the 19 September audit]

1. **The line is the unit of grounding, so the line becomes the unit of writing.** Every line with a number or claim must cite, and the registry rows arrive as `claim: value (conditions)`. (M) line 1 is literally F096 and F097 concatenated. Three lines bound to three pictures, capped at 38 words, become three captions, not one thought.
2. **The only legal move on a number is deletion.** The prompts ban the bare figure and ban invented praise, and name no third way. What survives is the un-numbered spec noun ("a split-folding arrangement"). The audit's translation ladder (describe what the picture shows → name it → the choice it gives → the moment it is for → the figure, once) was written for this and is the fix; it sits in the doc, not yet fully in `principles.py`.
3. **The fit-check is the default ending.** "Check the rear seats and boot with the people or luggage you expect to carry" (M) and "Bring your usual bags to check…" (S). Four of eight proof segments in the model run end by sending the buyer to find out for themselves, because a fit-check is free, cites nothing and satisfies the RELEVANCE beat.
4. **"Stand alone" is read as "never connect".** Both prompts forbid referring back, and the author reads that as re-announcing the subject in every sentence; the check-in is the only permitted question and is itself templated.
5. **The script you judged is not the author's.** (S) was hand-written by a session agent inside the validator's constraints and then installed. It is shorter and more careful than (M), and still a catalogue, which tells you the constraints, not the model, are producing the shape. Any test of a prompt change must run the real Plan → Author path (it costs one Gemini call each at customer tier) and be judged on (M)-type output.

What has already been fixed since the audit: `PITCH_SHAPE` removed from the author, the three-part `goal` (MOMENT / SPOKEN / HANDOFF) in use, the mandatory per-section question removed, jargon and unsupported-benefit warnings added. What is still open: the translation ladder as a named rule, the fit-check demoted to last resort, the openings rule ("open on the thing itself, never on a spec or a signpost"), the stats ban in the planner, and the schema fields (`narration_fact_ids` vs `deeper_fact_ids`, `say_as`, `carries_checkin`, `word_budget`) that would move the spoken-versus-deeper decision from the author to the planner.

---

## 8. Reading order — [Orchestrator]

1. Build: [graph.py:199](../server/graph.py:199) `build_graph` → [orchestrator.py:104](../server/orchestrator.py:104) `_run_stage` → [plan.py:214](../server/agents/plan.py:214) `run` → [author.py:300](../server/agents/author.py:300) `run` and [author.py:123](../server/agents/author.py:123) `validate` → [deck.py:284](../server/agents/deck.py:284) `build` → [bundle.py:14](../server/agents/bundle.py:14) `build`.
2. Run: [player.js:903](../web/player/player.js:903) `runIntake` → [player.js:579](../web/player/player.js:579) `playFrom` → [player.js:716](../web/player/player.js:716) `handleQuestion` → [runtime_graph.py:1548](../server/runtime_graph.py:1548) `run_turn` → [runtime_graph.py:916](../server/runtime_graph.py:916) `retrieve` → [runtime_graph.py:970](../server/runtime_graph.py:970) `reason` → [runtime_tools.py:168](../server/runtime_tools.py:168) `source_lookup` → [runtime_graph.py:1069](../server/runtime_graph.py:1069) `validate_decision` → [player.js:847](../web/player/player.js:847) `resumePlayback`.
3. Real data: `data/demos/dm_41513908/plan.json`, `script.json`, `deck.json`, `bundle.json`, and the genuine model versions under `output/creta-night-final/before-reviewed-install/`.
4. Diagrams: [architecture-flow.html](architecture-flow.html), especially 02 (build), 04 (voice/bundle), 05 (runtime).
