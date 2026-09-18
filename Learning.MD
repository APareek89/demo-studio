# Learning.MD — Demo Studio
> AGENT: add an entry whenever the basic flow changes, the user reports a bug or gives
> corrective feedback, or something took real time to figure out. CHECK THIS FILE FIRST
> before debugging — the answer may already be here. Plain language; first use of any
> technical term gets a one-line bracket explanation.

<!-- Newest first. -->

### 2026-09-18 — Align could not correct competitor citations or spoken questions

**Symptom:** Real Nexon source review found competitor facts outside the review card and edit/reject lookup. Incorrect truth labels and blended citations could not be repaired directly; intake questions, check-ins and segment outcomes also remained outside script editing.
**Why 1:** The fact card and handlers traversed only the product `facts` list, while competitors were stored separately.
**Why 2:** The original correction API accepted value/claim/conditions but not the existing truth/source fields.
**Why 3:** Chat actions duplicated the product-only lookup instead of sharing validated review operations.
**Why 4:** Script editing identified spoken lines only; questions and segment metadata are sibling fields with separate audio.
**Why 5:** Free review checks exercised line edits and product facts, without testing the full set of source-backed material a reviewer must correct before approving a build.
**Action taken:** Review cards show both registries with explicit ownership, while storage remains separate. API and chat corrections share schema/source validation; foreign, blended and cross-role source references reject before saving. Competitor facts remain bound to their source group. Review can change one intake, check-ins and title/outcome metadata, with grounding checks, stale question audio cleared and downstream approvals invalidated. The full smoke gate also caught unescaped citation-example braces in the expanded Align prompt; a focused prompt-format regression now covers it.
**Preventive action:** `evals/align_review_contract.py` exercises successful and rejected edits through real routes, source/approval isolation, chat parity, no partial writes, no second intake and zero provider/network calls. Review truth and variant applicability against the source: valid ids and field types do not prove that a quoted source supports every word of an edited claim.

### 2026-09-18 — Claude's grammar repair lost the selected model and timeout

**Symptom:** Code inspection for text tiers found that a constrained-schema error could silently retry with the general model and default timeout instead of the caller's selected model/budget.
**Why 1:** The grammar-error branch called `_soft_structured` without forwarding `model`, `timeout`, `effort` or `max_retries`.
**Why 2:** The recovery path was written before callers selected separate runtime/plan/lite models.
**Why 3:** Existing mock gates never enter Anthropic's schema-rejection branch.
**Why 4:** Provider repair was treated as a new request rather than the continuation of the same configured operation.
**Why 5:** The provider contract lacked a regression for preserving call options across recovery.
**Action taken:** Forward all four options into the existing soft-JSON recovery. The fake Anthropic grammar-rejection regression in `evals/provider_contract.py` proves that the selected model, timeout, effort and retry count survive the recovery path.
**Preventive action:** Every repair/fallback test asserts model selection, retry budget and history as well as output validity; free fakes must exercise provider error branches.

### 2026-09-05 — QA playback needed a single quiet-mode control

**Symptom:** End-to-end browser QA could play recorded narration, browser speech or the promotional film aloud, disturbing someone using the same machine even when the test conversation itself used typed chat.
**Why 1:** The player had separate audio objects for narration, browser speech and film playback, with no shared mute state.
**Why 2:** The film path explicitly unmuted its video element, so muting one narration object would not make the session quiet.
**Deepest why type:** `design`
**Action taken:** Added one accessible top-bar mute control backed by shared player state. `?mute=1` starts a QA session muted; the control updates current and future recorded narration, browser speech and film audio without pausing the visual flow. Added deterministic coverage and verified the control plus a typed intake in the real browser.
**Preventive action:** Every new audible runtime path must subscribe to the player's shared mute state and be covered by the visual-sync regression.

### 2026-09-05 — Image tags were not strong enough to prove script-to-screen alignment

**Symptom:** The existing post-author picture matcher could explain why “gearbox” mapped to a gear image, but its final Haiku pass only saw Gemini's earlier text tags, not the uploaded pixels. Multi-feature lines could therefore look related while still leaving one spoken feature invisible. Runtime fact cards also repeated long source/caveat prose and could overlap the topic badge.
**Why 1:** Source understanding and final visual proof were treated as the same decision even though the script did not exist during initial image tagging.
**Why 2:** The assignment schema recorded only a visual id and reason, not the spoken features, visible features, missing features or coverage level.
**Why 3:** The player card was designed as a miniature citation panel instead of a glanceable visual aid.
**Deepest why type:** `design`
**Action taken:** Upgraded the existing post-author checkpoint: Gemini 3.6 Flash now inspects the real uploaded images in batches of twelve against every stable script line, returns a detailed audit for every image and line, and is accepted only when both sets are complete and internally consistent. Deterministic code binds an image only on `full` coverage; partial, missing and non-visual decisions all fall back to the neutral 3D/card stage, even when an older draft carried a picture. The audit is saved in `visual-audit.json` and shown in Align. Runtime cards now contain at most three short keyword/value rows, with no source locator or caveat prose, and the topic badge hides while a card is visible. Live CRETA audit: 13 images, 60 lines, 29 corrected assignments, 18 uncovered feature lines.
**Preventive action:** A ready demo must expose per-image visible features and per-line full/partial/missing coverage after the script exists. Tag-only matching is a fallback, never the success criterion.

### 2026-09-05 — A supplied 3D asset still needs the product-truth approval gate

**Symptom:** Users with an existing GLB had to rebuild it through Runware even though the player already consumes GLB files.
**Why 1:** Demo Visual modelled only image/video inputs, not the reusable asset contract at the gate boundary.
**Deepest why type:** `design`
**Action taken:** Added direct `.glb` upload with a 150 MB limit and binary glTF v2 header/chunk validation. It creates a zero-cost versioned review attempt, opens in the same rotatable viewer, and only enters the demo bundle/My Assets after explicit approval.
**Preventive action:** Bypassing generation must never bypass structural validation, review, approval, version history or observability.

### 2026-09-05 — A good 3D asset still fails when the spoken claim and stage use different evidence

**Symptom:** The 3D vehicle remained dominant while Ravi discussed hidden safety/cabin features, exact images were relegated to thumbnails, and one personalised safety sentence combined airbags, brakes and hill assist while showing only the airbag frame. A transition about the demo roadmap also inherited stale safety/warranty evidence and citations.
**Why 1:** Playback treated the approved 3D asset as persistent decoration instead of making a per-line decision about what could actually prove the spoken words.
**Why 2:** The script and runtime planner could put several visually distinct claims into one spoken batch; image selection then chose one related frame and silently implied that it covered the rest.
**Why 3:** Transitions changed narration without resetting the preceding line's evidence/citation state, and a typed reply during the greeting could race into general Q&A before the intake listener existed.
**Deepest why type:** `design`
**Action taken:** Added a deterministic `model | evidence | card` contract to every bundled line. The player now uses mutually exclusive full-stage modes, never rotates an exact evidence image to a sibling, preloads all visual/audio media, gives personalised roadmaps their own card, routes multi-fact runtime batches to cited cards, clears stale citations on transitions, and queues early typed discovery answers. The CRETA narration was split into single-subject lines and rebuilt as `dm_c6a354fd`. Rodin Gen-2 replaced TRELLIS.2 after a five-real-view offline render comparison preserved the mixed black/silver/red source identity substantially better.
**Preventive action:** Every ready demo must pass `evals/qa_visual_sync.py` plus three buyer-profile browser runs. A line may use 3D only for a visible exterior claim; hidden, abstract or multi-claim language must have literal evidence or a cited card before speech starts.

### 2026-09-05 — Gemini fallback passed configuration checks but returned no audio

**Symptom:** Sarvam produced a valid WAV, but a forced Sarvam→Gemini fallback ended with “Gemini TTS returned no audio.”
**Why 1:** The fallback still used the legacy `generate_content` audio response shape while Google's current speech contract uses the Interactions API and exposes `output_audio`.
**Why 2:** Provider health only checked whether a key was present, and the existing probe called Gemini directly rather than forcing the actual fallback path through `voice.render_line`.
**Deepest why type:** `code`
**Action taken:** Moved Gemini speech to the current Interactions audio contract, upgraded the default to `gemini-3.1-flash-tts-preview`, kept the model environment-overridable, and verified a synthetic Sarvam failure produces a playable RIFF/WAV through the real fallback chain.
**Preventive action:** Voice-chain QA must force the primary provider to fail and validate the fallback file header; a configured key or direct provider call does not prove fallback wiring.

### 2026-09-05 — The opening film needed an explicit conversational handoff

**Symptom:** Runtime order was already needs question → film → demo, but Sources copy incorrectly said the film played before the guide started, and the guide resumed after the film without an explicit return line.
**Why 1:** The film was added as a latency-covering mechanism and its customer-facing transition was not represented in the flow diagram or bundle eval.
**Deepest why type:** `design`
**Action taken:** Tightened the acknowledgement, kept film audio unmuted, added a recorded post-film return line, corrected Sources copy, updated the runtime diagram, and made the smoke test require both film handoff clips.
**Preventive action:** Any full-screen media interlude needs recorded entry and exit lines plus a flow-level test for its exact position.

### 2026-09-05 — Runware's useful credit error was hidden behind a generic HTTP 400

**Symptom:** A real TRELLIS.2 build stopped with only `400 Bad Request`, while Runware's task audit contained `insufficientCredits`; Observability also showed the fallback asset price even though the rejected task cost nothing.
**Why 1:** The REST client called `raise_for_status()` before parsing Runware's JSON `errors` array.
**Why 2:** The mock path never exercises HTTP status bodies, multi-row polling responses, or provider download URLs.
**Why 3:** The integration tests covered the visual workflow but not the raw provider contract and its failure accounting.
**Deepest why type:** `code`
**Action taken:** Parse Runware errors before HTTP raising, translate known credit/key failures into actionable messages, preflight both the documented balance-object and live balance-number shapes before video analysis, prefer completed polling rows, handle malformed progress safely, record rejected jobs at $0, preserve exact returned cost when a later local step fails, require HTTPS asset URLs, and download through a separate unauthenticated client so the API key is never forwarded to a CDN. Added thirteen free provider-contract cases in `evals/qa_runware.py`.
**Preventive action:** Every external paid provider gets a no-network contract suite for 4xx bodies, transient retries, multi-result polling, cost accounting, output validation and credential isolation before its first live run.

### 2026-09-05 — TRELLIS.2 takes one image, not the five-view set the workflow collects

**Symptom:** The approved design described sending five uploaded or video-derived angles into the image-to-3D model, but Runware's TRELLIS.2 schema requires one `inputs.image`.
**Why 1:** The product flow (collect multi-view evidence) was mistaken for the provider contract (single conditioning image).
**Why 2:** The initial brief named an outcome and a model but did not include its exact request schema.
**Why 3:** Provider validation happened after the UX had already been described as multi-view inference.
**Deepest why type:** `design`
**Action taken:** The studio still collects exactly five real views because they catch identity/angle mistakes and are useful during the demo. The strongest real front-three-quarter view alone goes to `microsoft:trellis-2@4b`; other views remain labelled thumbnails. Video uses Gemini to select real frames and creates only missing views, but a generated view can never be the primary input. Runware request/poll/cost metadata is traced without storing the data URI or key.
**Preventive action:** Before fixing an external-model UX, validate the live provider schema and distinguish “inputs the user supplies” from “inputs the provider accepts”.

### 2026-09-05 — A pre-demo 3D asset must stay in the content flow, not become a disconnected generator

**Symptom:** A standalone 3D tool would create an asset but leave the voice-led demo showing full-size script images, making the expensive asset decorative.
**Why 1:** Asset generation and demo authoring were initially separate navigation concepts.
**Why 2:** `bundle.json` had no stable visual-asset field, so playback could not give 3D persistent priority.
**Why 3:** Reuse, approval, version history and deletion were not part of the demo state machine.
**Deepest why type:** `design`
**Action taken:** Added optional Demo Visual as studio step 1, an approval-gated `visual_asset` on the demo and bundle, persistent 3D playback with small supporting thumbnails, attempt history, `My Assets`, AWS mirroring, and mock-backed end-to-end tests.
**Preventive action:** Any generated media feature must define its owner, approval gate, bundle contract and exact runtime prominence before its provider call is implemented.

### 2026-09-03 — A multi-file patch script silently applied nothing (Python quoting)

**Symptom:** After "backend batch 2" the compile step said OK but none of the edits were present; the smoke test still passed on old code.
**Why 1:** The patch script (a Python heredoc) had an unterminated triple-quoted string, so Python rejected the whole file before running a single replacement — the following `py_compile` then checked the unchanged sources.
**Why 2:** Replacement bodies were embedded as triple-quoted literals while some bodies themselves contained triple quotes; one mismatch invalidated the file. (The same slip then hit the docs script once more.)
**Why 3:** The batch was applied as one shell heredoc, so a parse error had no per-file feedback and the success message came from a different command.
**Deepest why type:** `process`
**Action taken:** Re-applied from a saved script file with bodies in named variables and plain-string concatenation where quotes clash; every `patch()` prints its file.
**Preventive action:** For edits across many files, write the patch script to a file first and require every `patch()` to print — a missing "patched X" line is the failure signal, not the compile step. Never put three quote characters inside a triple-quoted body.

### 2026-09-03 — Anthropic 400 "compiled grammar is too large" on the Plan schema (first real run)

**Symptom:** Understand succeeded (71 facts) but Plan failed: `400 invalid_request_error: The compiled grammar is too large… Simplify your tool schemas`.
**Why 1:** `messages.parse(output_format=Plan)` compiles the Pydantic schema into a constrained-decoding grammar; `Plan` (nested USPs, segments, CTAs, intake, state questions, several Literal enums) exceeds the grammar size limit. `ScriptOut` would too.
**Why 2:** The schemas grew with the sales layer (roles, steps, USPs) and were only ever exercised in mock mode, which never touches the API.
**Why 3:** No live check exists for "schema still fits the grammar" — the mock validates shape, not the provider's limits.
**Deepest why type:** `design`
**Action taken:** `claude.structured` catches that 400 and falls back to plain JSON: the JSON schema goes into the system prompt, the reply is parsed with Pydantic, and one repair pass sends the validation errors back. Plan and the 37-line script then succeeded on the same run. Also: a re-read no longer redoes a finished Understand (saves ~2 min and a Gemini call on every retry). Targets Why 1.
**Preventive action:** Keep big stage schemas on the soft path by default if they hit the limit once (it's cached per process now only by retry — consider a `SOFT_SCHEMAS` set); add Loop eval: "Plan + ScriptOut parse on the real API".

### 2026-09-03 — Three live-API drifts on the first real-key check (Gemini model, Sarvam model, Sarvam speakers)

**Symptom:** With real keys: Gemini returned 404 for `gemini-2.5-flash` ("no longer available to new users → gemini-3.6-flash"); Sarvam returned 400 for `bulbul:v2` ("deprecated → bulbul:v3"), then 400 for `pitch`/`loudness` on v3, then 400 for speaker `anushka` (v2-only).
**Why 1:** Model ids and request shapes were written from memory of the public docs, not probed against the live service.
**Why 2:** Providers retire models and change parameter sets on a cadence faster than any training data.
**Why 3:** No "probe the provider" step existed in setup — the smoke test runs in mock mode and can't see drift.
**Deepest why type:** `process`
**Action taken:** `GEMINI_MODEL` → `gemini-3.6-flash` (env-overridable); `SARVAM_TTS_MODEL` → `bulbul:v3`; v3 body drops pitch/loudness; speaker list probed from the API's own error message (37 v3 voices, default `priya`). Verified TTS hi-IN/en-IN and STT round-trip live. Targets Why 3.
**Preventive action:** Keep the tiny live-probe script as `evals/probe_keys.py` and run it whenever a key is added or a provider 4xx appears — it costs a few paise and takes ten seconds. Never hard-code a speaker list without a probe.

### 2026-09-03 — Mock pitch planner returned an empty route (every script segment was "intro")

**Symptom:** `evals/smoke_mock.py` failed at `/run/pitch`: `route: []` even though the script had 3 segments.
**Why 1:** The pitch planner only routes through segments whose role is `proof` or `establish`; all mock segments had role `intro`.
**Why 2:** `mock._fake_value` returned the FIRST Literal value for every `Literal` field, and the name-based overrides ran after the Literal branch, so `role` never reached them.
**Why 3:** The mock generator was written before roles existed and was never given a notion of "a realistic mix" for list items.
**Deepest why type:** `code`
**Action taken:** Literal fields now honour a small preference map (`role→proof`, `step→say`, …) and segment lists get a realistic role cycle (intro, outcome, proof, establish, proof); route steps point at real segment ids. Targets Why 2.
**Preventive action:** When a schema gains a `Literal` field whose *first* value is a degenerate default, add it to `mock.py`'s preference map in the same change — Loop.MD eval 8 checks the mock route is non-empty.

### 2026-09-03 — pip could not install `cryptography` (built from source, Rust failed)

**Symptom:** `pip install -r requirements.txt` failed with `error[E0463]: can't find crate for core` while building `cryptography`.
**Why 1:** pip found no binary wheel (pre-built package) it considered compatible, so it tried to compile from source, which needs a Rust toolchain that isn't set up for this target.
**Why 2:** The venv is created from Anaconda's Python (`/Users/macbook/anaconda3`), whose platform tag is older (`macosx_10_9_x86_64`) than the tags on the newest `cryptography` wheels.
**Why 3:** Anaconda builds Python with an old deployment target; pip rejects wheels tagged for a newer macOS minimum.
**Deepest why type:** `knowledge-gap`
**Action taken:** Install with `--prefer-binary --only-binary=cryptography`, which lets pip pick the newest version that *has* a compatible wheel (targets Why 1).
**Preventive action:** `requirements.txt` install command in README uses those flags; if a future package hits the same wall, prefer a Homebrew Python (`brew install python@3.12`) over fighting wheels.

### 2026-09-03 — Browser pane blocks the microphone; mic-denied path must be first-class

**Symptom:** Voice intake never heard anything during automated testing.
**Why 1:** The preview browser blocks `getUserMedia`/speech recognition (`not-allowed`).
**Why 2:** Real users can also deny the mic, or use a browser without SpeechRecognition (Firefox).
**Deepest why type:** `design`
**Action taken:** `listen()` resolves empty on `not-allowed`, sets `micDenied`, and every voice prompt falls back to a typed input; check-ins keep tap chips. Verified the typed path in the pane.
**Preventive action:** Any new voice interaction must have a typed/tap equivalent before it ships (Loop.MD eval 6).

### 2026-09-03 — Approve buttons unreachable on four of five Align cards (user could not build a demo)

**Symptom:** "There is no approve button anywhere except for the last one … I couldn't generate demo … what kind of QA is being done by you?" Only the last card's Approve was clickable; the user got through by typing "approve all" to the agent.
**Why 1:** Approve/Feedback lived inside each card's *body*, and only the current card's body was open by default; opening another card pushed its body below the visible area.
**Why 2:** The cards column could not scroll: it is a CSS-grid item, and a grid item's default `min-height:auto` lets it grow past the row instead of scrolling, so `overflow:auto` never engaged.
**Why 3:** The browser QA of the Align screen was done at a viewport where all five closed cards fit, on a demo whose *first* card was the open one — the failing state (a later card opened, at a normal laptop height) was never exercised.
**Why 4:** There was no click-through eval for the approval path; the smoke test approves via the API, which cannot see layout.
**Deepest why type:** `process`
**Action taken:** `.cards{min-height:0}` so the column scrolls; Approve / Un-approve moved into every card *head* (always visible), plus an "Approve all" button and an explicit note that anything not provided will not be answered. Targets Why 2 and Why 1.
**Preventive action:** Every screen with a required action gets a browser click-through in the pane at 800×450 (the smallest realistic height), exercising the *non-default* state (last card, second tab, long list) — Loop.MD eval 16. API-level smoke never counts as UI QA.

### 2026-09-03 — Fast-start remux silently skipped for every video ≤ 60 MB

**Symptom:** The acceptance QA printed `Error opening output …/derived/…_play.mp4: No such file or directory`; the read stage still succeeded, so nobody noticed the remux never ran.
**Why 1:** `prepare_video` created `derived/` only on the >60 MB proxy branch; the fast-start remux branch assumed the folder existed.
**Why 2:** The remux path was never executed on this machine before today — ffmpeg was not installed until `imageio-ffmpeg` bundled it, and the mock smoke test uses images only.
**Why 3:** The `except` around the ffmpeg steps emits a one-line notice and continues, which is right for the customer but hid the bug from the developer.
**Deepest why type:** `code`
**Action taken:** `play.parent.mkdir(parents=True, exist_ok=True)` before the remux; the acceptance QA (`evals/qa_accept.py`) now uploads a real 20 s MP4 so the path runs on every loop pass. Targets Why 1 and Why 2.
**Preventive action:** Graceful-degradation branches must also *log to the trace* (not only emit), so a swallowed error is visible in Observability; any code path that writes to a derived folder does its own `mkdir`.

### 2026-09-03 — Ten Hindi lines silently switched voice mid-demo (Sarvam out of credits, fallback hid it)

**Symptom:** The images QA build finished "successfully", but the trace showed 10 `gemini-2.5-flash-preview-tts` calls among 96 Sarvam calls — the Hindi demo changes voice for those lines. No error row anywhere.
**Why 1:** Sarvam returned HTTP 402 "No credits available" once the account's balance hit zero; `render_line` caught it and fell through to Gemini TTS as designed.
**Why 2:** `sarvam.tts` only traced *successful* calls, and the fallback path emitted nothing, so the failure was invisible in Observability and in the build log.
**Why 3:** Per-line fallback retried Sarvam on every remaining line (≈0.3 s each) — wasteful, and no signal reached the person who could fix it (top up credits).
**Deepest why type:** `design`
**Action taken:** Sarvam failures are traced with the HTTP body; a circuit breaker trips a provider for 10 minutes on 401/402/403/quota errors; the voice stage emits "sarvam is unavailable (…) — lines used the next provider… top up, then rebuild"; `/api/voices` reports `unavailable` and the Sources voice picker shows it; the player falls back to browser speech recognition when server STT fails. Targets Why 2 and Why 3.
**Preventive action:** Every fallback in a provider chain must (1) trace the failure and (2) surface a one-line, actionable message to the user in the same stage log. Add a paid probe to `evals/probe_keys.py` before big builds — it costs one line of TTS and would have shown the 402 up front.

### 2026-09-03 — Parallel narration tripped Sarvam's rate limit; the fallback failed silently and two lines shipped without audio

**Symptom:** The video QA build reported "audio lines 28/30". Trace: four Sarvam HTTP 429 "Rate limit exceeded" rows; no Gemini-TTS rows at all, although Gemini is next in the chain.
**Why 1:** Four workers fired Sarvam requests at once; Sarvam's per-second limit rejected some; the chain moved to Gemini TTS, which also failed for those lines.
**Why 2:** Gemini's failure left no trace row — `render_line` swallowed provider errors and only Sarvam traced its own — so the second failure was invisible and the line silently became "browser voice".
**Why 3:** The parallel change was made minutes before the run to cut a 613 s stage; rate-limit behaviour of the providers was never measured, and there was no second pass for lines that fail under load.
**Deepest why type:** `design`
**Action taken:** Sarvam client backs off on 429/5xx (1.5 s → 3 s → 6 s); default `VOICE_WORKERS` 3; a sequential second pass re-records lines that failed under parallel load; every provider failure in the chain is traced (`gemini-tts` / `gcloud-tts` rows with the error). The two lines of `dm_78890026` were re-rendered and the bundle rebuilt (v2, 30/30). Targets Why 2 and Why 3.
**Preventive action:** Any parallelisation of a paid provider ships with (a) back-off on 429, (b) a sequential retry pass, (c) a trace row per failure — and the stage log must state "N lines on browser voice" rather than "Narration ready". Loop.MD eval 21 covers the provider-failure path.

### 2026-09-03 — FMEA found the grounding rule bypassed in every extra language

**Symptom:** The in-session FMEA scan (three subagent runs died on API 429/529) scored one P0: translated scripts are voiced without re-validation, so a Hindi line can carry a figure the registry never certified.
**Why 1:** `translate.py` copies the English script, swaps text per line id and keeps the fact_ids — the ids stay valid, the words don't have to.
**Why 2:** The grounding validator (`author.validate`) is tied to the authoring stage and English regexes; nobody re-ran it for translations because the "same ids" felt like the same script.
**Why 3:** Multi-language was added as a voice feature, not as a content feature — the checklist for "new content path → validator" wasn't applied.
**Deepest why type:** `design`
**Action taken:** Every translated line must keep exactly the digit groups of its source (Indian-script numerals normalised, separators stripped); a line that changes a number is kept in the main language and counted ("N lines kept in the main language"). Also from the scan: PII redaction + `TRACE_CAPTURE=meta` for traces, hard/soft breaker classes (transient quota → 90 s, account failures → 10 min), an in-flight guard on the Playground eval buttons. Targets Why 2.
**Preventive action:** Any stage that produces spoken text — author, translate, runtime bridges, Q&A — runs a figure check against its source before voice. Loop.MD eval 22 covers translation; the FMEA report `docs/FMEA-2026-09-03.md` carries the 14 P2 items.

### 2026-09-04 — I defended my own code when the user asked why we had no agent framework

**Symptom:** Asked "why not LangGraph or CrewAI?", I argued that plain code was better because frameworks lack deterministic checks and that a framework would replace only a small part of the code. The user rightly pushed back: Zod/Pydantic checks exist in every framework, and the thing they wanted — one structured place to see and reason about the workflow — is exactly what a graph framework provides.
**Why 1:** I weighed the cost of migrating code I had just written above the user's stated need (structure over scattered function calls).
**Why 2:** I framed "deterministic validation" as a differentiator when it is orthogonal: validators are plain functions in any framework.
**Why 3:** The original decision (2026-09-03, no framework) was taken for speed on day one and was never revisited when the workflow grew loops, interrupts and revisions.
**Deepest why type:** `process`
**Action taken:** Conceded in writing, then moved the workflow to LangGraph the same day: `server/graph.py` is the single definition (router → understand → plan → align_enter → align_wait[interrupt] → author → voice → rehearsal → bundle → finish), SQLite checkpointer, `GET /api/workflow` returns the graph as Mermaid (docs/mermaid/00-workflow.mmd), `langgraph.json` for Studio. Nodes stay thin wrappers over the vendor-SDK stage functions; the API, the file store and the run log are unchanged.
**Preventive action:** When a non-developer asks "why not X", answer the question they are asking (legibility and control), not the one that flatters the existing code; state the migration cost honestly and let them decide.

### 2026-09-04 — The screen did not show the part the guide was talking about (Creta gearbox)

**Symptom:** The Creta demo spoke about the gearbox in the intro and outcome while showing exterior beauty shots; the uploaded gear-lever, paddle-shifter and manual-knob images only appeared in the gearbox segment.
**Why 1:** The author picked one visual per line from a long catalogue while also writing 30 lines; it defaulted to hero shots outside the segment "about" that part.
**Why 2:** Nothing checked the script against the pictures afterwards; the plan assigned visuals per segment, not per line.
**Why 3:** Gemini's image tags (parts visible) were stored but never used for matching.
**Deepest why type:** `design`
**Action taken:** `server/agents/visuals.py` — a picture-editor pass after authoring: conservative rules on distinctive part words, then one Haiku call that decides every line with a stated reason, then a coverage guardrail so an uploaded picture with a spoken subject is shown at least once. Decisions are logged (logs/*-visuals.json) and appear in RUN.md.
**Preventive action:** Any content the guide shows (pictures, cards, video shots) is matched to the words by a pass that leaves a reason per decision; Loop.MD eval 23.

### 2026-09-04 — "The demo is pathetic": everything personalised was generated and voiced live, on the customer's clock

**Symptom:** In the Creta sessions the guide went silent after the intro, never focused on the stated need (city + long trips), showed an airbag image on unrelated lines, and switched from the female voice to a male one mid-demo.
**Why 1:** The personalisation planner was a live Claude call started when the opening began; at 14–17 s it outran the opening, so the player waited in silence, then gave up and played the standard route (`personalized: false`).
**Why 2:** Bridges, check-in replies, answers and small talk were all voiced live through `/run/tts`; when the request was late or the provider failed, the player fell back to the browser's built-in voice (male on this Mac).
**Why 3:** Pictures were chosen by the author per line with no map from information to images, so live lines showed whatever the segment's first visual was.
**Why 4:** Nothing at Align showed the actual script, so the user could not see any of this before pressing Build.
**Deepest why type:** `design`
**Action taken:** Configure now runs plan → author → FAQ bank, so Align shows the full Script (batch by batch, ≤ 20 s, mapped to seconds, picture per line) and the FAQ bank, each with a Preview pop-up. The planner returns custom batches for the buyer's context, voiced server-side while the standard opening plays; recorded filler lines (acknowledgement, bridge, holds, nudges, small talk) cover every gap; the rule at runtime is "same voice or captions, never the browser voice"; known questions answer from the pre-voiced bank instantly, new ones after a recorded "bear with me"; an information→image map is built at configure and used by the script, the batches and the answers.
**Preventive action:** Anything the customer hears must exist as recorded audio before the demo starts, or be produced while recorded audio is playing. A silent wait longer than a breath is a bug. Loop.MD evals 24–26.

### 2026-09-04 — The demo opened with a decision frame and specs; principles were sequenced instead of broad

**Symptom:** First words after the customer's context: "You're deciding two things today: does the N10 suit your driving, and manual or DCT?" plus a four-spec takeaway with the airbag cut-away on screen. The user: "open with what buyer must decide — why? you don't know what the buyer wants; principles should cover few broad guidelines."
**Why 1:** The playbook's P01 ("frame a decision, not a product") was placed at the TOP of the flow, where no buyer context exists; framing belongs at the fit summary once their words exist.
**Why 2:** The prompt mixed sequence and principles into one twelve-item block, so the writer treated principles as an ordered checklist and opened with the first one.
**Why 3:** No mandatory greeting step existed; the showroom sequence (greet → needs → walkaround in the customer's order) was never encoded.
**Deepest why type:** `design`
**Action taken:** Prompts rebuilt on the human-demo playbook: PRINCIPLES trimmed to seven broad rules (G1–G7); PITCH_SHAPE replaced by a seven-step FLOW (greeting lives in the intake question; overview before detail; exactly three USPs; natural category discovery order; mandatory meaning step; establish declares the top open questions; fit summary + next step at the close). Runtime planner writes the acknowledgement in the buyer's own words and runs on Sonnet. Coverage guardrail can no longer force a detail image into the opening; ack audio preloads and a neutral hero backs it.
**Preventive action:** Sequence and principles are separate blocks in every agent prompt; anything adaptive (decision framing, personalisation) is forbidden before the customer has spoken. Loop eval 27: the first spoken segment line contains no digits and no decision framing; the fit summary does.

### 2026-09-05 — The opening film sat behind the persistent 3D stage

**Symptom:** The runtime had the correct greeting → needs → film sequence, but a demo with an approved 3D asset could leave the model above the film in the stacking order.
**Why 1:** The 3D model deliberately has its own positioned layer; the opening film reused the ordinary supporting-video element and never entered an explicit stage mode.
**Why 2:** The film flow had been verified at the API/bundle level, not in the exact 3D-led player state.
**Deepest why type:** `process`
**Action taken:** `playIntroFilm` now enters `film-on`: model, reference strip and supporting detail fade away; the audio film takes the full stage; on finish/skip it is hidden and the 3D stage returns before Ravi's recorded return line. Browser QA exercised the exact state.
**Preventive action:** Media-sequence acceptance requires a browser screenshot in every mutually exclusive stage state, not only a valid URL and audio track.

### 2026-09-05 — Runtime personalisation chose the manual image for an automatic claim

**Symptom:** A live family-route batch said “automatic” and cited the transmission facts but selected the manual gear-knob image.
**Why 1:** One transmission fact legitimately maps to manual and automatic images; the runtime model picked the first valid sibling.
**Why 2:** Runtime custom batches validated that a visual id existed, but did not re-run the literal word-to-picture check used by authored lines.
**Deepest why type:** `design`
**Action taken:** Runtime batches now score all cited candidate visuals against their spoken words and override only on a strong literal match. The player passes each narration line into its 3D director, holds the relevant front/side/rear/performance angle for 4.5 seconds, and keeps the exact supporting image as the detail proof.
**Preventive action:** Any new path that creates spoken text plus a visual must pass both grounding and literal visual-alignment checks before playback.

### 2026-09-05 — Preloading only intake left avoidable pauses between authored lines

**Symptom:** Intake acknowledgements were fast, but the rest of the recorded route could still incur a first-fetch pause when each line began.
**Why 1:** Preload objects were created only for intake and fillers, then immediately lost to garbage collection.
**Why 2:** Narration, deeper lines, check-ins, FAQ, closing and the opening film were not covered.
**Deepest why type:** `code`
**Action taken:** The player now retains preload objects for every authored audio line and the opening film for the session lifetime, releasing them only when the player is destroyed. Real lookup gaps use recorded, polite “give me one moment, please” bridges.
**Preventive action:** The no-silent-gap browser gate covers the entire bundled audio graph, not just first response.

### 2026-09-05 — The player could still change voice if a recorded file failed in the browser

**Symptom:** The authored audio path was all-Sarvam, but an individual browser playback/load error still called the built-in browser voice.
**Why 1:** The earlier “same voice or captions” rule covered server generation failure, not client media playback failure.
**Deepest why type:** `code`
**Action taken:** A failed server-voice audio file now stays on-screen as timed captions; browser speech is used only for demos explicitly configured to use browser speech.
**Preventive action:** Voice consistency is enforced at both generation and playback boundaries.

### 2026-09-05 — Valid WAV files hid two severely malformed fallback durations

**Symptom:** The final bundle had an audio URL for every line, but two short lines were 33 and 173 seconds long; five narration files had silently used the Gemini fallback inside an otherwise Sarvam build.
**Why 1:** The build gate checked only that an audio URL and file existed.
**Why 2:** Provider-level success did not verify duration against word count or assert one provider across the finished customer route.
**Deepest why type:** `process`
**Action taken:** All five fallback files were re-rendered with Sarvam and the exact timeline rebuilt (186.3 seconds). Final integrity QA checks every spoken item for a readable WAV, non-silent signal, plausible duration and provider hash; all 99 spoken entries now pass as Sarvam `aditya`.
**Preventive action:** “Audio complete” requires content integrity and provider-consistency checks, not file existence.

### 2026-09-05 — Catalogue accepted CSV while the upload guidance hid it

**Symptom:** A synthetic price sheet could be uploaded as CSV, but the Catalogue panel only advertised PDF, DOCX, TXT and MD; the supported fallback looked unsupported.
**Why 1:** The file-picker accept list was expanded without updating the adjacent human-readable copy.
**Deepest why type:** `process`
**Action taken:** The Catalogue guidance now names CSV, and the visual-sync regression compares the visible promise with the accepted extension.
**Preventive action:** Any upload-format change must update both the picker contract and the copy in the same test.

### 2026-09-05 — Build blockers still said five Align cards after FAQ made six

**Symptom:** Align correctly showed six required cards, while two build errors and the Rehearse empty state still told the user to approve five.
**Why 1:** FAQ became a first-class approval card, but scattered count-specific strings were not part of that migration.
**Deepest why type:** `code`
**Action taken:** All live build guidance now says six cards; the visual-sync regression rejects either stale five-card string.
**Preventive action:** Keep workflow counts behind shared copy where practical, and make the cross-screen contract test fail when a count diverges.

### 2026-09-05 — Provider exhaustion restarted expensive work instead of resuming it

**Symptom:** A transient reasoning-provider failure left the FAQ bank partial, while a retry risked re-answering every completed question.
**Why 1:** FAQ generation had no registry-version checkpoint and provider failover treated each question as an isolated call.
**Deepest why type:** `architecture`
**Action taken:** Text-only structured calls now fall back to the configured secondary provider; FAQ progress checkpoints after every answer, reuses same-registry results, and offers an explicit cache-bypassing retry. Runtime Q&A uses a traced, approved-fact-only fallback during an outage cooldown.
**Preventive action:** Long multi-call stages need resumable checkpoints and circuit breaking before they are considered production-safe.

### 2026-09-05 — Validated human corrections were marked stale and could be overwritten

**Symptom:** A direct product, fact, pitch or script correction invalidated its own model-owned stage, so Build could regenerate over the reviewed edit.
**Why 1:** Invalidation encoded dependency freshness but did not distinguish an unvalidated mutation from a replacement artifact that had already passed validation.
**Deepest why type:** `architecture`
**Action taken:** Direct editors now validate their artifact, invalidate only dependants, restore the edited stage to done, and require all affected Align approvals again.
**Preventive action:** Human-authored replacements must have an explicit validated state transition; never route them through a model rerun implicitly.

### 2026-09-05 — Attractive product images were being used as proof for invisible claims

**Symptom:** Generic exterior photos could be attached to capacities, prices, written terms and hidden safety mechanisms they did not prove.
**Why 1:** Keyword overlap rewarded product relevance without first asking whether the claim was visually observable.
**Deepest why type:** `model`
**Action taken:** Runtime image mapping now excludes non-visual facts and sends unsupported detail to a cited fact card; direct script edits rebuild this safe map.
**Preventive action:** Visual relevance is not evidentiary coverage; gate observability before similarity scoring.

### 2026-09-05 — Voice review showed the configured label, not the voice that would play

**Symptom:** The Persona card could display a stale provider or speaker after re-recording, and partial builds could leave some FAQ or filler items silent.
**Why 1:** Review copy read raw settings while rendering resolved fallbacks dynamically; sample audio was not persisted into the reviewed plan.
**Deepest why type:** `code`
**Action taken:** Align now shows the resolved provider and voice, sample re-recording persists and invalidates Persona approval, and final QA counts audio across script, FAQ, check-ins and fillers.
**Preventive action:** Review surfaces must describe the resolved runtime artifact, and build completeness must cover every playable branch.

### 2026-09-05 — Hyphen splitting turned “crash-test rating” into a test-drive answer

**Symptom:** Asking for a current crash-test rating returned a dealership test-drive fact.
**Why 1:** Naive token overlap treated “test” as the decisive shared term and had no hard-unknown guard for unsupported safety ratings.
**Deepest why type:** `code`
**Action taken:** Safety-rating intent is now a hard unknown unless an approved matching rating fact exists; regression coverage includes the hyphenated wording.
**Preventive action:** High-risk intents need negative controls, not only positive keyword matching.

### 2026-09-05 — Comparison and finance fallbacks lost the decision caveat

**Symptom:** A named rival-price answer omitted the product's own price, and a request for one illustrative EMI scenario returned multiple scenarios without consistently repeating the non-offer caveat.
**Why 1:** Generic top-fact selection optimized lexical overlap rather than the response contract for comparative and financial decisions.
**Deepest why type:** `code`
**Action taken:** Rival matching is now derived from uploaded comparison facts, price answers cite both products plus verification guidance, and named synthetic scenarios return only the requested illustration with its caveat.
**Preventive action:** Decision-sensitive intents need explicit response shapes and mandatory caveats in tests.

### 2026-09-05 — A closed responsive panel still widened the whole page

**Symptom:** The player looked usable at phone width but the document still scrolled horizontally because nested grid tracks and a transformed closed panel retained intrinsic width.
**Why 1:** Responsive rules changed visible layout without allowing grid children to shrink at every ancestor.
**Deepest why type:** `code`
**Action taken:** Studio/player tracks now use shrinkable columns, controls wrap on phones, and root overflow is contained; live checks pass at 320, 390, 768 and 1280 px.
**Preventive action:** Responsive QA must assert document scroll width, not rely on screenshots alone.

### 2026-09-05 — A nearby true fact answered a different high-risk question

**Symptom:** “Which is the cheapest Harrier variant?” returned “55 variants,” while “Is the powered tailgate standard on every variant?” returned only that a powered tailgate exists.
**Why 1:** Intent-specific narrowing kept the original fuzzy candidates when no claim matched the required intent.
**Why 2:** The matcher treated feature presence as equivalent to universal variant scope.
**Deepest why type:** `design`
**Action taken:** Intent narrowing is now fail-closed; cheapest/entry-variant questions require a named variant fact; universal-scope wording requires explicit scope evidence. Global NCAP applicability has its own scoped response contract.
**Preventive action:** Every high-risk selector gets both a positive test and a near-miss negative test. An empty exact match must decline, never reopen the fuzzy candidate pool.

### 2026-09-05 — Ready did not mean every customer branch had audio

**Symptom:** A Harrier build briefly reached ready with only 8 of 28 FAQ answers voiced after Sarvam rate limiting.
**Why 1:** The voice stage checkpointed partial work but the final build gate accepted the partial bank.
**Deepest why type:** `code`
**Action taken:** Build now fails unless every FAQ answer and filler has audio, while retaining completed files for a rate-limit-safe retry. Harrier v2 rebuilt with 88/88 referenced WAVs populated.
**Preventive action:** Completeness gates must enumerate every runtime branch, not only the main narration path.

### 2026-09-06 — Audi Q5 passed only after envelope, intent and concurrency failures were made explicit

**Symptom:** The 34.8 MB brochure exceeded the primary reader envelope; early chat runs leaked a prior product name and overreached on cheapest/scope questions; a voice retry raised `dictionary changed size during iteration`; and the final mocked sweep caught a polled JSON artifact being read mid-write and reset.
**Why 1:** The source pipeline treated provider capacity as fact quality, several compound intents reused generic lexical matching, shared provider state was unsynchronized, and stage JSON writes were not atomic.
**Deepest why type:** `architecture`
**Action taken:** Oversized reads can use only a source-validating reviewed manifest; Q5 price, performance, equipment, comparison, photo-proof, finance, ground-clearance and ADAS intents now have narrow fail-closed contracts; voice circuit state is locked; runtime gaps self-heal and deduplicate; JSON artifacts publish by atomic replacement; the async visual test uses a deterministic concurrency barrier.
**Evidence:** Audi Q5 `dm_302ab4aa` is ready at v1 with 45 approved facts, 25/28 FAQ answers, complete 88-item playable audio coverage, three muted ten-question sessions, responsive checks at 320/390/768/1280 px, a fully decoded 157.54-second MP4, and free suites at 98/98, 32/32, 17/17 and 24/24 plus the full mocked pipeline.
**Cost:** $0.5682 recorded total; the only paid visual was Rodin task `f68aff15-6e2f-4bdb-8594-ed430159ed16` at exactly $0.40.
**Preventive action:** Treat provider envelopes, runtime registries and file-backed stage state as explicit system boundaries; every release gate must include adversarial intent tests and a polled background-worker path.

### 2026-09-18 — A revise on a ready demo never rebuilt through the API

**Symptom:** `POST /revise {stage: "deck"}` on a ready demo re-ran the deck and then parked at Align instead of re-bundling; `evals/qa_deck.py` timed out waiting for `ready`.
**Why 1:** The `faq` edge routes to `voice` only when `rebuild` or `prev_ready` is true in the graph state; both were false.
**Why 2:** `graph.start_revise` computed `prev_ready = status == "ready"` *after* `_set_status("reading")`, so it was always False.
**Why 3:** The Align-chat path (`align_wait` → `requests["revise"]`) reads the status before anything changes it, so the only path anyone had exercised worked; no eval covered `POST /revise` on a ready demo.
**Deepest why type:** `order-of-operations`
**Action taken:** `start_revise` reads `prev_ready` first and keeps the status at `building` when a rebuild will follow. `qa_deck.py` now waits for `ready` after a deck revise.
**Preventive action:** Any state read that feeds a routing decision happens before that function's side effects; every entry point of a graph command gets an eval, not just the chat one.

### 2026-09-18 — The transcript said what the guide *started* saying, not what the customer heard

**Symptom:** `addMsg("agent", text)` ran when `speak()` began, so a line cut off by a question reached `/run/qa` as if fully heard, and a typed reply during a chip wait was logged twice (once by the wait, once by `handleQuestion`).
**Why 1:** Logging lived at the start of `speak()` because that was the one place every line passed through.
**Why 2:** Nothing measured how much audio had played; an interruption only bumped the run token.
**Why 3:** The transcript was treated as a drawer display, not as the model's memory of the conversation.
**Deepest why type:** `wrong-source-of-truth`
**Action taken:** `S.speaking` tracks the playing line; `logHeard(sp, complete)` logs on `ended` (full) or from `cancelSpeech` (heard prefix = `currentTime / duration × words`, elapsed-time estimate for captions and the browser voice) marked `interrupted`; `handleQuestion` skips a user line the chip wait already logged. Evals: the transcript cases in `qa_deck.py`; browser check on the mock server (Phase 5).
**Preventive action:** Anything sent to a model as "what happened" is written by the event that proves it happened (audio ended, request returned), never by the event that started it.

### 2026-09-18 — A slide switch waited for an animation frame that a hidden tab never gets

**Symptom:** In the browser pane (a hidden document) a new slide stayed at opacity 0: `showSlideView` added the `on` class inside `requestAnimationFrame`, and hidden documents get no frames.
**Why 1:** The cross-fade needed the element inserted first and the class added "next frame" so the CSS transition would run.
**Why 2:** The visible-tab assumption was never stated; every manual check had the pane in front.
**Deepest why type:** `hidden-assumption`
**Action taken:** Insert → `layout()` → forced reflow (`void el.offsetWidth`) → add `on`, synchronously. Same transition, no frame dependency. Found by the Phase 6 scripted browser check (which itself had to move its polling into one call: model latency between calls let the demo run ahead).
**Preventive action:** Nothing that decides what is on screen may depend on animation frames or on the tab being visible; only audio events and user actions drive the player.

### 2026-09-18 — A reload kept running the old module

**Symptom:** After a deploy of new front-end modules, the Observability page still ran the previous `observability.js` after a reload; a `no-store` fetch of the same URL returned the new file.
**Why 1:** `/web` was served with an ETag but no `Cache-Control`, so browsers applied heuristic freshness (10 % of the file's age) to each module.
**Why 2:** A modern reload revalidates only the document; module imports come from the cache when still "fresh".
**Why 3:** One import already carried a hand-written `?v=3e0`, a per-file workaround that nobody extends to the next file.
**Deepest why type:** `missing-policy`
**Action taken:** A middleware sets `Cache-Control: no-cache` on `/`, `/web/*` and any `.html/.js/.css` — every load revalidates, a 304 when unchanged. APIs untouched.
**Preventive action:** Every static asset the app serves has an explicit cache policy; version queries on imports are not the mechanism.

### 2026-09-18 — A deck-only rebuild died on a model the deck never needed

**Symptom:** `POST /revise {stage: deck}` on the real TVS iQube demo ended in `error` at the FAQ stage — "Question generation failed: 503 high demand" (Gemini) — although nothing about the sources or the registry had changed; the bundle stayed stale and the player kept the old slides.
**Why 1:** The graph re-runs every node after `deck` (faq → voice → bundle), and `faq.run` regenerated its question list with a model call before checking whether the registry had changed.
**Why 2:** The reuse logic only covered the answers (by registry hash), because the question list was written first and the hash check came second.
**Why 3:** Rebuilds had only been exercised in mock mode, where every model is always up.
**Deepest why type:** `unnecessary-dependency`
**Action taken:** When the registry hash is unchanged the previously generated questions stand (no call); `force` regenerates. Proven by a counting test in `qa_deck.py`.
**Preventive action:** A rebuild of one stage may only call a model for that stage; every downstream node reuses by content hash, and the eval counts model calls on a second run.

### 2026-09-18 — One busy second froze Gemini for ten minutes

**Symptom:** On a real rebuild the deck writer fell back to derived callouts twice; the demo's log said "Gemini rate limit cooldown: current quota exhausted; wait or enable billing" while a fresh one-token probe of the same key answered fine.
**Why 1:** `gemini._retry` latched a 600 s cooldown on any message containing "exceeded your current quota".
**Why 2:** That text is also Gemini's ordinary per-minute burst 429 on a free-tier key, which carries its own "retry in Ns" hint.
**Why 3:** The latch was written against the zero-quota case (no billing) and never tested against a burst.
**Deepest why type:** `overbroad-match`
**Action taken:** `_quota_cooldown(message)` — a burst waits what Gemini asks (+1 s; 30 s without a hint); only `limit: 0` / `quota_value: 0` latches ten minutes. Unit cases in `qa_deck.py`.
**Preventive action:** Any provider cooldown is sized from the provider's own retry hint, and the zero-quota case is matched on its specific markers, never on generic quota wording.

### 2026-09-18 — The player needed a visible product and a readable conversation

**Symptom:** The welcome blurred the product behind a large mascot; slide titles were hard to find, and a revealed overlay line started at the picture corner. A phone preview of the redesign then exposed a gradient fading out the hero.
**Why 1:** The same presentation emphasized the guide and controls more than the product, and positions were measured while callout chips had no dimensions.
**Why 2:** Reveal changed visibility without recomputing leader geometry; layout reserved a fixed caption height.
**Why 3:** Existing checks covered data positions and desktop presentation, not visible rendered geometry after reveal or a changing conversation dock.
**Deepest why type:** `design`
**Action taken:** Product-first welcome, visible benefit headings, native-aspect pictures, scoped evidence panel, typed reply field, measured dock reservation, and layout recomputation after reveal. Mobile hero uses an upper picture area without an obscuring gradient.
**Preventive action:** Browser checks measure leader endpoints after reveal and wide/narrow image bounds; visually review welcome, long answers and controls on a phone before calling the experience ready.

### 2026-09-18 — Silence and qualified replies incorrectly advanced the demo

**Symptom:** The browser swallowed “Yes, but what about charging?” as agreement and continued narration behind an unknown-answer callback form.
**Why 1:** Short prefix matching classified any brief yes-prefixed reply as confirmation; timers treated silence as continuation.
**Why 2:** The player had separate paths for chips, ordinary questions and microphone input rather than one owned customer turn.
**Why 3:** A global reply resolver and mic flag let a delayed speech result target whichever wait happened to exist later.
**Deepest why type:** `architecture`
**Action taken:** Explicit question waits have no auto-advance countdown. Exact controls settle choices; qualified replies reach Q&A. Typing is always visible. Capture ownership spans permission, recording and transcription; late results cannot resolve a new turn. Unknown and dissatisfied answers retain the turn until explicit continuation.
**Preventive action:** Browser regressions exercise silence, yes-but, stale speech after skip/restart, delayed QA, clarification and callback hold. Acoustic recognition quality remains a real-device test.

### 2026-09-18 — Q&A lost the opening checkpoint and clarification context

**Symptom:** An opening interruption could replay completed narration; short clarification replies could match an unrelated cached FAQ.
**Why 1:** Return state described only the routed slides; the opening and deeper explanation had no independent checkpoint.
**Why 2:** A clarification was treated as a new standalone question rather than a reply to the original one.
**Why 3:** Tests checked structural strings and successful question routing, not a second reply inside an interrupted phase.
**Deepest why type:** `design`
**Action taken:** Preserve phase, slide and line across all follow-ups, then return with a spoken bridge after explicit resolution. Clarification speaks alone, accepts typing or voice, and sends the original question plus the actual reply/history with FAQ matching disabled.
**Preventive action:** Browser cases cover opening and off-slide interruption, exact once-only typed clarification and deeper question waits; content cases reject a clarification containing an uncited claim.

### 2026-09-18 — Fallback labels were fragments and rebuilds could remap edits

**Symptom:** The iQube deck included “Charger supplied: portable new 950W charger that plugs”. Omitting a long fact also risked attaching an existing Align edit to a different numbered callout.
**Why 1:** `_compact` sliced the first N words.
**Why 2:** Fallback considered width without preserving complete meaning, conditions or truth type.
**Why 3:** Positional callout IDs assumed the set and order could never change.
**Why 4:** Evals measured length, layout and citations without an omitted earlier fact plus a saved edit.
**Deepest why type:** `design`
**Action taken:** Keep a complete original label with its qualifications only when it fits; otherwise omit it. Preserve prior unambiguous citation identity and reserve IDs belonging to omitted callouts or existing overrides.
**Preventive action:** Long-label, condition, title and repeated-rebuild override regressions.

### 2026-09-18 — The script substituted a default customer for the real viewer

**Symptom:** The real iQube session recorded 5–10 km/day while the existing script described 30 km/day; prompts also repeated discovery.
**Why 1:** The prompt wanted one context choice while the schema asked name, purpose and a second question.
**Why 2:** Customer examples and generic personas appeared beside the actual customer context.
**Why 3:** Reused plan/script text was not explicitly excluded as evidence about this viewer.
**Why 4:** A valid product citation could license an unrelated personal quantity, and no-context output was accepted.
**Why 5:** Tests checked shape and routes without testing ownership of personal details.
**Deepest why type:** `design`
**Action taken:** Align prompts and schema, enforce empty second-intake fields, suppress invented personalization after skipped intake, and reject quantities absent from customer or cited-fact inputs. Validate check-ins as well as narration so moving a claim into a question cannot bypass grounding.
**Preventive action:** Adversarial 5–10 versus 30/thirty, skipped intake, valid spoken quantities, check-in grounding and second-intake tests. The quantity guard checks presence, not semantic entailment; the new real script still needs source and customer-profile review.

### 2026-09-18 — The buyer ending exposed the internal sales handoff

**Symptom:** Stop showed the customer an intent score, classification, route/drop point and USP identifiers; an open callback form could cover the summary.
**Why 1:** The player rendered its internal session report directly as the customer ending.
**Why 2:** One view served two audiences with different needs, and ending playback did not close subordinate overlays.
**Why 3:** Completion tests verified record saving but not what the buyer saw.
**Deepest why type:** `design`
**Action taken:** Customer recap uses their actual stated needs, explored topics and questions still open, with one optional follow-up. Internal metrics remain in session storage. Opening the recap closes the callback form.
**Preventive action:** Browser regression stops during an unresolved callback turn and checks buyer copy, visible overlays and preserved internal record separately.

## 2026-09-18 — Cinematic evidence rail collapsed and labels moved between layouts

**Why 1:** Narrow callout evidence had zero height despite visible child boxes.
**Why 2:** Evidence items reused the class `overlay`, whose global modal rule made them absolutely positioned.
**Why 3:** Renderer styling changed composition without an explicit in-flow reset for the semantic marker.
**Why 4:** Earlier geometry checks only bounded the picture and leader; they did not require a nonzero evidence parent.
**Why 5:** Saved image coordinates, responsive evidence and modal utility styles had no joint browser contract.
**Fix:** Scope evidence items to static positioning; reserve the full fallback evidence band before placing chips; measure heading bounds without animation; reject oversized chip placements; preserve native image/anchor geometry and saved Align data.
**Prevention:** The19-case player harness includes narrow/portrait evidence, nonzero fallback parent, consecutive-layout stability and exact anchors through resize. All19 pass with synthetic audio/API only; real Nexon verification stays separate.

## 2026-09-18 — Competitor applicability and rejected evidence bypassed runtime checks

**Why 1:** Rival PDF/text sources did not contribute facts, and runtime comparisons lost trim conditions.
**Why 2:** Competitor ingestion selected only URLs, while the Q&A context copied only claim/value.
**Why 3:** Upload provenance and richer fact fields were not carried consistently across source ingestion, prompt assembly and FAQ reuse.
**Why 4:** A cached FAQ answer bypassed live approval checks, and a CTA could bypass replacement of rejected or uncited answer text.
**Why 5:** The prior contract tested happy-path citations without rejected evidence combined with cached audio or action fields.
**Fix:** Read rival documents into separate C-facts; preserve conditions, truth, locator, quote and source URL/date; validate URL metadata before mutation; share approval guards between model and bank paths; invalidate FAQ reuse when approvals/competition change; reject unsafe claim text before speech regardless of CTA.
**Prevention:** `evals/source_contract.py` exercises isolated PDF/text ingestion, provenance validation through the real API, rejected/mixed citations, bank hits with revoked facts/disabled comparisons, and the actual text passed to speech. Live semantic claim-to-source review remains required; token/citation checks alone do not prove entailment.

## 2026-09-18 — Reviewed script must control the slide preview and bundle
- Why did old questions reappear? The deck held a previous copy of script text and check-ins.
- Why did direct review not remove it? Script edits invalidated the deck; saving a slide override marked it done without refreshing that copy.
- Why could the bundle retain it? Fallback joins treated an explicitly empty check-in as missing and kept deck citations.
- Why was this missed? Prior checks verified saved visual overrides, without exercising a script correction followed by a slide edit.
- Root cause and fix: the script is the authority for spoken text, citations, metadata and explicit empty questions. A shared deterministic join supplies Align and bundle without changing saved visual design. Five regressions cover preview/bundle parity, cleared questions, changed citations and held lines; Align review now47/47.

## 2026-09-18 — Valid citations were turned into unproven benefits (NX14/NX16)

**Why 1:** The first real plan/script/FAQ used clearance as flood/damage assurance, litres as demonstrated luggage fit, and unrelated engine figures as a mode-switch power delta.
**Why 2:** Generation was required to turn every feature into a customer outcome or performance promise, although source evidence often established only a specification.
**Why 3:** Truth descriptions equated an official test method with certification; product prompt context dropped exact source quotes/locators, and examples omitted the ordinary `stated` category.
**Why 4:** A valid fact id was treated as sufficient grounding for extra meaning, while trim/fuel/finance restrictions could move out of the spoken claim. The planner's final id filter also allowed human-rejected facts still present in storage.
**Why 5:** Structural mock checks covered citations and pacing, not the distinction between a sourced specification and a source-supported outcome; manual correction alone would not change the next generation.
**Deepest why type:** `design`
**Fix:** Shared extraction truth/scope rules and downstream evidence rules; prompt/schema descriptions now allow a useful choice or fit-check instead of an invented benefit. Product context carries the original quote and locator with truth/conditions. Explicit instructions preserve trim/fuel/finance scope, forbid unsupported arithmetic and route unknowns to the appropriate source. Plan reference filtering now accepts approved facts only. No new schema fields, semantic regex engine, model critic or paid call.
**Prevention:** `evals/generation_contract.py` has 21 passing free input/approval contracts, with network/providers blocked; existing customer contracts remain 29/29. Eleven synthetic adversarial cases in `evals/fixtures/generation_grounding.json` cover negative and positive generation behavior for the authorized real review. Prompts and citation checks are not semantic entailment: inspect raw second-Read artifacts before polishing or claiming these failures resolved. Re-Read review preservation remains unchanged; reviewed facts must be snapshotted, identity-mapped and reapplied through the API separately.

## 2026-09-18 — Plain-language guidance removed the unit (NX18)

**Why 1:** A refreshed real FAQ said “pulling power is 260” without Nm.
**Why 2:** The everyday-audience instruction prohibited both the technical abbreviation and its spoken unit, while asking the model to translate the number into a plain term.
**Why 3:** The same style instruction governed a general tour and a direct technical question, with no exception for a complete requested quantity.
**Why 4:** The jargon-repair instruction asked for plain wording without explicitly preserving the whole quantity.
**Why 5:** Tests checked banned words and citation presence, not whether the complete value/unit reached speech or whether prompt rules conflicted.
**Deepest why type:** `design`
**Fix:** Main narration moves unnecessary technical quantities as a whole to deeper detail; direct Q&A retains the value, unit and scope with a short gloss. Jargon repair explicitly forbids dropping only the unit. Ordinary facts need no repeated disclaimer or certification label.
**Prevention:** Free contracts capture actual build-FAQ and runtime prompt envelopes and prove a complete mocked answer reaches the speech seam unchanged; a deeper unit-bearing answer survives author validation. The adversarial unit-loss case still needs a real response review: no deterministic semantic/unit validator was added.

## 2026-09-18 — The on-screen generator kept the old benefit-only contract

**Why 1:** The second raw deck promised easy rough-road clearance, family luggage fit, highway efficiency and lower fuel costs from ordinary specifications.
**Why 2:** Its prompt and callout/title schema descriptions still required a benefit or promise and explicitly rejected a bare specification label.
**Why 3:** The earlier evidence-rule change reached plan, author and Q&A, but not this separate model-writing stage; deck context also omitted truth, exact source quote and locator.
**Why 4:** The scope review followed spoken-content generation and missed that the on-screen model can independently create unsupported customer claims.
**Why 5:** Earlier deck tests established bounded text, valid IDs and visual layout, not whether all generation surfaces received the same source/evidence contract.
**Deepest why type:** `design`
**Fix:** After freezing the raw I2 deck, align only its existing prompt/schema descriptions and fact context with the shared evidence rules. Complete neutral specifications and relevant fit-checks are allowed; omitted callouts are preferable to lost qualifications or invented benefits. No model critic, semantic regex engine, saved-override change or paid rebuild.
**Prevention:** Two actual deck input-envelope contracts bring the free generation suite to 23/23; the 12-case adversarial review set includes deck benefits and fuel-cost overreach. The raw I2 script/FAQ still repeat semantic failures despite receiving the new instructions, so prompt assembly is not a faithful-generation guarantee. Record those failures before manual corrections. A separate stale saved label bound I1's BNCAP text to I2's ISOFIX F004: root owns review-identity recovery, and the prompt fix does not address it.


## 2026-09-18 — A locked Priya build switched speakers after a Sarvam rate limit (NX19)

**Why 1:** The first real Nexon Build exhausted a Sarvam request window, then synthesized FAQ/fillers with Gemini Sulafat although the chosen voice was locked to Priya.
**Why 2:** Only strict runtime calls restricted the fallback chain; ordinary build speech ignored `voice_locked`.
**Why 3:** FAQ/filler reuse trusted any existing audio path, without checking its provider/speaker/language/content hash.
**Why 4:** The provider circuit was checked before its cache, making already-recorded Priya clips unavailable during a transient cooldown. Parallel workers also sent Sarvam requests without a shared pace.
**Why 5:** The speech gate tested fallback availability rather than the chosen-voice invariant and recovery from a partially voiced build.
**Deepest why type:** `code`
**Fix:** Locked speech keeps the configured provider and speaker for build and runtime, including a missing key or temporary circuit failure. Matching cache reads happen first. Main, deeper, check-in, closing, intake, FAQ and filler clips are reused only by their chosen-voice hash; old Gemini references are replaced or cleared. Missing locked narration or bank audio stops the build before bundling, with completed work checkpointed. Gemini policy refusals, including the observed “Input blocked sensitive words”, are not retried by the voice stage or forwarded to another provider. A locked Cloud voice also preserves mock isolation.
**Pacing evidence:** Sarvam's official [rate-limit documentation](https://docs.sarvam.ai/api/getting-started/ratelimits) lists Bulbul v3 Starter at 30 REST requests/minute, shared across account keys. This process conservatively spaces starts by 2.1 seconds; this is an application policy, not a claim about the account's actual tier. Only HTTP429 receives up to three attempts. Numeric or HTTP-date Retry-After is honored; a requested wait beyond the call's 30-second wait budget stops explicitly and preserves the shared cooldown. Other processes on the same account can still consume capacity.
**Prevention:** `evals/voice_lock_contract.py` has 27 free cases with fake speech/HTTP/clock and blocked sockets. They reproduce mixed FAQ/fillers, cached main/check-in/intake, cooldown reuse, missing-only recovery, explicit incomplete narration, policy refusal, locked Cloud mock isolation, pacing and bounded retries. Failed real Build1 remains preserved; the next real build is the user's second attempt, not an uncounted recovery run. No live provider call was made for this fix.

## 2026-09-18 — Human FAQ review could not replace a generated answer

**Why 1:** A real FAQ answer added benefits or connective wording that the reviewed facts did not establish, and Align offered no direct answer correction.
**Why 2:** The FAQ card could display and approve a generated bank, while corrections went back through regeneration.
**Why 3:** Generation and review were treated as the same operation; another model answer could repeat the defect and replace a human correction.
**Why 4:** No explicit edit contract preserved the question, origin and registry hash while discarding derived audio, visual and route metadata.
**Why 5:** The free gates checked generation/reuse, not the full human-review → ordinary Build path.
**Deepest why type:** `design`
**Fix:** Existing Align now accepts a supported answer plus fact ids at `PATCH /api/demos/{id}/align/faq/{qid}`. All ids must be approved and competition-eligible; mixed valid/invalid ids are rejected rather than filtered. Existing NUMBERISH/CLAIMISH rules reject uncited claims. Stale, partial and running banks cannot be edited. The route preserves bank/question identity and registry hash, clears old audio/error/clarification/callback, derives the visual and the slide from the current script joined to saved slide design, clears only FAQ approval, and invalidates voice/rehearsal/bundle while keeping FAQ done. Card and Preview offer a labelled, keyboard-focusable editor; no model is called.
**Prevention:** `evals/faq_review_contract.py` passes 41 free API/build/cache contracts in temporary storage with providers and networking blocked. It covers held/mixed F/C citations, competition off/on, stale hashes/stages, graph gaps between stages, mutation-free failures, changed script references, excluded cached visuals, exact-answer normal Build reuse, fresh runtime stay/jump routing and removal of old recordings. This does not prove semantic entailment: a valid citation does not certify an added benefit, so the human must review meaning and scope. Only supported-answer edits are included; question/decline/clarification authoring is unchanged.

## 2026-09-18 — Align Script Preview did not show the customer slide template

**Why 1:** Script Preview showed the plain native image layout after the customer player had moved to cinematic slides.
**Why 2:** Preview called the shared renderer without its fitted-player option.
**Why 3:** Cinematic styling is scoped to the player stage, but the read-only preview had no stage wrapper.
**Why 4:** The editable source-coordinate view and the customer presentation view shared a default rendering call despite serving different review tasks.
**Why 5:** Previous preview checks compared text and saved overrides, without checking the final presentation shell.
**Deepest why type:** `code`
**Fix:** Only Script Preview now uses the fitted shared renderer inside a bounded `.pl` / `.pl-stage` shell, with an active slide and no player controls. The editable slide view retains its native coordinates and drag behavior.
**Prevention:** Root's real-browser review must compare the customer-style Preview at wide/narrow widths before this checkpoint is accepted; syntax checks alone do not establish visual parity.

## 2026-09-18 — Hidden mobile labels left a visible diagonal leader

**Why 1:** A phone-sized cockpit preview showed a line from the picture's top-left corner to an evidence dot.
**Why 2:** Narrow-layout CSS hid the overlay label and repeated its text in the evidence rail, but kept the SVG leader visible.
**Why 3:** A hidden label has zero bounds, so layout could compute the leader origin at the picture corner.
**Why 4:** Responsive visibility was applied to the label but not to the line that depends on that label.
**Why 5:** Prior mobile checks verified native image fit, readable rail and numbered anchors, but did not inspect the leader's painted visibility.
**Deepest why type:** `code`
**Fix:** In the exact existing ≤699px cinematic container rule, hide the leaders with `visibility:hidden`. The native-image geometry, numbered dots, evidence rail and wide-screen label/leader remain unchanged.
**Prevention:** The free browser harness adds a wide →390px →304px →wide check for hidden mobile leaders, visible dots/rail and restored desktop leaders. Required isolated gates after the fix pass: deck203/203, acceptance24/24, both smoke phases, Python38/JS12 and harness-module syntax. Actual browser results are recorded by root; the subagent's CUA had no available browser.

### 2026-09-18 — A provider outage was written into the FAQ bank as knowledge

**Symptom:** After the starved rebuild every one of the TVS iQube bank's 20 entries read "I'm not sure about that from the material I've been given"; at runtime every bank question declined, and the customer heard a guide that seemed to know nothing.
**Why 1:** `qa.answer` turns any provider exception into the DONT_GUESS decline (Phase 1: never guess) and `faq.run` stored that decline exactly like a real "the sources do not say".
**Why 2:** The return value carried no sign that the decline came from an exception rather than the model.
**Why 3:** The bank had only ever been rebuilt with working providers.
**Deepest why type:** `conflated-states`
**Action taken:** `qa.answer` returns `provider_failed`; `faq.run` then keeps the previous answer (same registry) or marks the entry `error` for a retry and the bank `partial`; `faq.match` skips unbuilt entries so the live model answers. Three cases in `qa_deck.py`.
**Preventive action:** "The sources do not say" and "the model was down" are different states everywhere they can be stored; a stored decline must carry which one it is.

## 2026-09-18 — Runtime Q&A routed through an obsolete script copy (NX24)

**Why 1:** A correct boot FAQ stayed on the cabin slide during the second real customer run.
**Why 2:** The saved deck still held an old deeper-line F014 citation on that cabin slide, and runtime routing preferred a fact already present on the current slide.
**Why 3:** Align Preview and bundle hydrated saved slide design from the reviewed script, while `/run/qa` read raw deck copies.
**Why 4:** Two paths interpreted the same saved slide artifact with different authorities for spoken citations.
**Why 5:** Earlier routing regressions had consistent deck/script fixtures and did not exercise a reassigned fact after direct human review.
**Deepest why type:** `code`
**Fix:** Runtime Q&A joins current script lines/deeper citations onto saved deck design through the existing `slides_with_script` helper before routing either a bank hit or a live answer. Declines still remain on the current slide, and routing does not mutate saved design. The pitch path already reads its fact-bearing library from the script; its sole raw-deck lookup maps stable segment ids to slide ids and has no stale-fact interpretation to repair.
**Prevention:** `evals/runtime_delivery_contract.py` reproduces raw cabin-stay versus reviewed boot-jump, then exercises actual bank/model API routes, the correct stay and decline paths, and no deck/script writes. Correct fact ids and correct returned text are insufficient evidence that the displayed topic is correct.

## 2026-09-18 — Slow customer provider work blocked cached media (NX26)

**Why 1:** Prerecorded acknowledgement audio could not be delivered while a runtime pitch was waiting on its model/speech work.
**Why 2:** An `async` FastAPI endpoint called the synchronous pitch function directly and occupied its event loop.
**Why 3:** Runtime Q&A, TTS and STT endpoints used the same direct synchronous-provider pattern.
**Why 4:** Declaring an endpoint async had been treated as sufficient concurrency, despite blocking work inside it.
**Why 5:** Prior tests checked endpoint responses independently, rather than concurrent media delivery on the same ASGI loop during a held provider call.
**Deepest why type:** `code`
**Fix:** Await built-in `asyncio.to_thread` for the existing synchronous pitch, live QA, TTS and STT calls. Their provider order, result shapes, tracing context, strict selected voice, language arguments and HTTP502 behavior remain intact. No service, dependency, model, timer or streaming path was added.
**Prevention:** The combined runtime-delivery suite passes27/27 with fake providers and blocked sockets. One AsyncClient/ASGITransport event loop holds each fake provider on a threading.Event and proves actual cached media plus health complete before release. It also checks worker/context propagation and failures. This frees the event loop; it neither shortens provider work nor cancels an underlying worker if a request is abandoned, and does not establish a latency SLA.


### 2026-09-18 — Personalized slides bypassed complete-label and image review

**Symptom:** Real Nexon playback showed “Boot space capacity: 382 L for Petrol &” over the preceding cabin image.
**Why 1:** `transientSlide` sliced fact text to eight words and inherited the current picture when no explicit visual arrived.
**Why 2:** The reviewed deck already had a complete qualified boot label and its own image, but the runtime slide did not consult it.
**Why 3:** The earlier complete-label correction applied only to backend derived callouts, leaving this separate customer-visible formatter unchanged.
**Why 4:** Browser tests covered turn ownership and geometry without inspecting the content and image of a personalized fact slide.
**Why 5:** The same evidence-preservation rule had not been checked at every place that presents a fact.
**Deepest why type:** `design`
**Action taken:** Transient slides reuse complete reviewed labels only when all their citations belong to the approved transient facts. Otherwise they keep the entire claim, value, conditions and truth qualifier within eight words or omit the badge. Without an explicit visual, a reviewed slide must cover every cited fact before its picture is reused; otherwise use the neutral hero. Stored deck data is never changed.
**Preventive action:** Real-browser contract fixtures cover reviewed boot wording/image after a cabin, mixed-scope refusal, complete short conditions/truth, rejected facts and unchanged review objects. No paid call or content rebuild is needed.


## 2026-09-18 — Live warranty wording resolves an explicitly unknown policy relationship

**Why 1:** Actual profile-A Q02 was heard as “3 years or 1,00,000 km” although the cited headline only joins the limits with a bar and its reviewed conditions leave the relationship unknown.
**Why 2:** The short qualified reply missed the long reviewed FAQ question and reached live generation.
**Why 3:** General source/conditions instructions did not explicitly distinguish a list of policy limits from their legal relationship; plausible connective wording survived citation validation.
**Why 4:** The validator checks citations/claim presence, not whether “or” or “whichever first” is entailed by a source.
**Why 5:** Prior generation checks verified evidence delivery but had no synthetic headline-policy case paired with an explicit-terms control.
**Deepest why type:** `prompt`
**Fix:** One generic QA_SYSTEM bullet preserves explicit unknown terms, forbids deriving a limit relationship from a slash/bar, and retains relationships or coverage rules when explicitly supplied. The missing term belongs only in the relevant answer. No car facts, matcher changes, new service, schema field, provider or speech behavior were added.
**Prevention and limit:** Four input-envelope cases cover unknown relationships and explicit relationships/exclusions through both actual build-FAQ and runtime QA assembly, with providers and sockets blocked. Baseline was 23/27; the prompt change passes 27/27 plus compilation. These checks establish delivery of the rule and exact evidence, **not model compliance or semantic entailment**. A fresh live Q02 result remains necessary; the original failing session is retained. FAQ matching remains unchanged because a stop-word/threshold shortcut was not shown to preserve scope.


## 2026-09-18 — A greeting answer asks a question before the player's check

**Why 1:** Actual initial session `s_mu72zmm82u16` answered “Hello” with “Would you like to continue exploring cargo practicality, or look into running costs…?”, immediately followed by the player's “Did that answer it?”.
**Why 2:** Runtime trace 311 put the offer question in ordinary `answer`, with `answered=true` and empty `clarifying_question`.
**Why 3:** The player correctly handled the designated clarification field separately but treated ordinary answer text as a completed response.
**Why 4:** QA instructions did not assign ownership of the following question and also invited the model to “offer” technical detail.
**Why 5:** Input-envelope cases covered evidence and clarification structure, not greetings/ordinary answers against the player-owned satisfaction check.
**Deepest why type:** `prompt`
**Fix:** QA_SYSTEM now asks for ordinary answers as statements and brief greeting acknowledgments without restarting intake. Only the existing `clarifying_question` field may ask a question, with an identical question-only answer. Technical detail may be mentioned as a statement. Schema, matcher, provider/outage, policy and voice behavior are unchanged.
**Prevention and limit:** Six free real-envelope cases cover greeting, ordinary answer and clarification on build/runtime paths; restoring the old prompt in memory yields 27/33, the new prompt 33/33. Providers and sockets are blocked. These verify instruction delivery, not model obedience; the actual failing heard transcript remains evidence and a live rerun is still required.


### 2026-09-18 — Typed customers were returned to automatic microphone capture

**Symptom:** In the second real customer validation, the customer typed intake and a boot question. After the correct cached answer, follow-up waits automatically opened the microphone and sent unrelated ambient media as two customer questions. This run cannot establish voice recognition quality.
**Why 1:** Every owned `waitFor` attempted listening whenever a microphone was available.
**Why 2:** The player retained turn ownership but no preference for how that customer chose to reply.
**Why 3:** Submitting typed text stopped only the current capture; the next wait opened a new one.
**Why 4:** Browser regressions fenced stale results, but did not require a typed interaction to keep later microphone captures closed.
**Why 5:** Input modality was treated as a per-turn fallback rather than an explicit customer choice.
**Deepest why type:** `design`
**Action taken:** Start with the existing voice behavior. An actual input event or typed submit chooses typing and cancels current capture. Later waits, including a restarted intake, remain typed until an explicit microphone tap restores voice mode. Focus alone does not change preference. Mic controls stay visible and microphone permission policy is unchanged.
**Preventive action:** Two real-DOM browser regressions cover typed intake/check-in/QA without new listening, discarded late ambient output, explicit microphone speech and resumed voice waits, plus preference through Restart and explicit intake-mic activation. The main player owner integrates the narrow patch alongside independent session-clock and jump-announcement fixes; actual refreshed browser acceptance is recorded separately.


## 2026-09-18 — A stopped session continued accumulating time (NX27)

**Why 1:** The real initial session was saved ended but grew from the observed8.3 to11.3minutes, and its final slide kept accumulating dwell.
**Why 2:** Stop marked only an ended boolean; each later Done/pagehide snapshot subtracted the original start from the current wall clock.
**Why 3:** The still-open slide used the same moving clock even after narration had stopped.
**Why 4:** Playback cancellation and engagement accounting had no shared end boundary.
**Why 5:** Completion tests checked the ended flag and saved transcript, but never advanced time after ending.
**Deepest why type:** `code`
**Fix:** An in-memory cutoff freezes total elapsed and current-slide dwell at the first handoff. Repeated Stop, Done and pagehide preserve that boundary. Explicit Back, new typed/mic input, slide selection or CTA reopens the same session and shifts its active start/current-slide start past the inactive interval. Restart creates a fresh clock and session. Saved schema, transcript timestamps, intent scoring and QA latency stamps are unchanged. Historical records are preserved, not rewritten.
**Prevention:** Real-player browser fixtures advance five minutes after Stop/Done, verify identical elapsed/dwell across saves and pagehide, then exercise Back, another slide, Restart and an intentional new question after Done. Synthetic time tests prove accounting behavior; they do not establish acoustic quality.

## 2026-09-18 — A grounded Q&A jump lacked a spoken transition (NX28)

**Why 1:** The actual boot answer routed to the correct slide after the citation fix but changed the picture abruptly, with no announcement in the heard transcript.
**Why 2:** The player called showSlideView immediately on a jump response, then spoke the answer.
**Why 3:** The return path already had a spoken bridge, but the outward jump did not use the existing transition filler.
**Why 4:** Routing was tested as target correctness and return-point preservation without checking the customer's transition cue.
**Why 5:** Visual correctness and conversational continuity had been treated as separate success checks.
**Deepest why type:** `code`
**Fix:** Await the existing bridge_to_custom cached clip before changing slides, with one short generic speak fallback if that clip is unavailable. Only a completed, still-owned run can change the view and speak its answer. The actual answer re-arms first-answer-audio timing after the bridge; the bridge is heard transcript, not answer latency. Stay/none paths remain unchanged and no build is needed.
**Prevention:** Browser fixtures hold the cached bridge for three seconds to prove the current view and null answer timestamp persist until completion, then verify answer timing and heard transcript. Another fixture cancels it by navigating and verifies no late jump or answer. The existing off-slide return case also verifies the generic fallback precedes the answer and the exact interrupted line is retained.


## 2026-09-18 — A comparison becomes a catalogue and loses rating applicability

**Why 1:** Actual B Q07 returned 88 whitespace-separated words in one sentence, with 19 citations and many equipment items (runtime trace348, Runware GPT-5.5).
**Why 2:** “1–3 short sentences” constrained nominal sentence count without a word budget or an attribute-selection rule.
**Why 3:** A broad selected-automatic comparison encouraged listing the registry instead of choosing the buyer's most relevant differences or shared features.
**Why 4:** The long catalogue compressed “five-star BNCAP for petrol and diesel trims” and omitted F006's material May-2026 applicability condition.
**Why 5:** Prior free checks established evidence delivery, not whether the provider prioritized useful attributes while retaining scope in speech.
**Deepest why type:** `prompt`
**Fix:** The existing QA prompt now requests at most60 words including caveats. A direct single fact can use one sentence; a comparison chooses at most two buyer-relevant attributes, states both sides in two or three short sentences, and drops an extra attribute before shortening its material conditions. It stops before the player-owned follow-up. No schema, matcher, provider, bundle or voice change.
**Prevention and limit:** Two added real input-envelope fixtures deliver the focus rule, buyer context, both variant qualifications and full website-verification caveat through build-FAQ/runtime calls. The prior prompt scored33/35; the changed prompt35/35 with all provider/network calls blocked. This does not enforce a word cap or prove model entailment. Original Q07 remains a pacing/scope failure; positive comparison acceptance is pending a fresh focused live answer.


## 2026-09-18 — A sourced comparison ended inside its JSON answer (NX30)

**Why 1:** Actual customer B Q08 declined even though approved Venue comparison facts were present in the request.
**Why 2:** Gemini returned a 170-character unfinished JSON answer; local schema validation correctly rejected it. Claude then failed for missing credits and Runware timed out, so the guide declined.
**Why 3:** The live caller allowed only 1,500 output tokens; the trace recorded 1,486 combined candidate and thought tokens with very little visible text. Budget exhaustion is strongly consistent with this evidence, but not proven because the existing trace does not retain finish_reason.
**Why 4:** A short spoken-answer target had also become a tight allowance for the complete structured response and model reasoning.
**Why 5:** Provider contracts checked dispatch/schema/cost behavior, but did not exercise the live QA caller's budget through the actual SDK request envelope.
**Deepest why type:** `code`
**Fix:** Raise only live QA's existing max_tokens argument to 3,000. The QA prompt still requests at most 60 spoken words; build-time QA and unrelated runtime defaults remain 1,500. No provider, timeout, retry, thinking configuration or speech change; no additional Build.
**Prevention and limit:** Five free provider checks exercise the real QA/dispatcher/Gemini/installed-SDK path with a fake transport, synthetic keys and blocked sockets: 3,000 in the request, complete approved answer/citation validation without fallback, combined thought/candidate accounting, build-time 1,500 and unrelated-runtime 1,500. A complete fake response proves the configured envelope, not future provider compliance or an actual comparison pass. The preserved Q08 failure remains failed until the root's authorized live rerun is reviewed.


## 2026-09-18 — Concurrent cold Gemini callers closed an in-flight client (NX31)

**Why 1:** Fresh B Q08 declined after all reasoning providers failed: Gemini reported a closed client immediately, Claude lacked credits, and Runware timed out.
**Why 2:** Q&A and pitch could enter the lazy Gemini client initializer concurrently after runtime calls were moved onto workers.
**Why 3:** The initializer tested a shared None value and constructed/assigned the client without a lock, allowing two SDK clients to replace each other.
**Why 4:** The installed SDK Client destructor calls close(), while its Models object retains the API transport rather than the parent Client. Replacing the global can therefore close an already-running request.
**Why 5:** The media-concurrency regression exercised fake provider functions, not concurrent first initialization of their shared SDK resource.
**Deepest why type:** `code`
**Fix:** Protect only cold initialization with a standard-library Lock and a second None check. The already-created client remains shared; provider order, model selection, request settings, retries and timeouts are unchanged. No response is fabricated or reclassified as a fact gap.
**Prevention:** `evals/gemini_client_contract.py` holds the first fake SDK constructor while another thread calls the same real initializer, then holds both model calls and mimics the installed SDK destructor. Before the fix it constructs two clients and closes an in-flight transport (3/7); after the fix both use the same open transport (7/7). Missing-key and constructor-error recovery behavior remain covered. No live provider or network call is made. The observed trace proves the closed-client failure; the deterministic race establishes a code path that explains it, not a post-fix live success. The concurrent pitch also returned incomplete JSON separately; its cause is not resolved by this lock.


## 2026-09-18 — A complete qualifier was still clipped on a phone (NX25 follow-up)

**Why 1:** The actual final A boot slide clipped “Creative+PS/Fearless+PS” at the right edge, although the saved label was complete.
**Why 2:** The evidence item measured 164px wide but its content scrolled to 171px; the rail was 343px wide with 350px of content.
**Why 3:** Its flex text child retained its automatic minimum width, and a long trim token had no permitted wrap within that width.
**Why 4:** Whole-label preservation fixed semantic truncation but did not ensure every retained token could fit a phone card.
**Why 5:** Existing geometry fixtures used ordinary words with convenient spaces and checked rail/image bounds, not each painted text fragment.
**Deepest why type:** `code`
**Fix:** Only within the existing narrow Cinematic rule, let the evidence text child shrink and wrap anywhere. Preserve exact label text, font size, card/rail layout, image geometry and saved coordinates.
**Prevention:** A real-DOM regression uses the actual reviewed boot and split-seat labels at 390, 320, 304 and390px. It checks text preservation, each card's scroll width, painted text fragment bounds, the unchanged 12px minimum and no two-card rail/page overflow. Baseline screenshot: iteration-2/screenshots/A-final-boot-phone.png. Browser execution remains the root's responsibility; syntax or mock gates alone do not establish visual correction. No Build, provider or production-data change.


## 2026-09-18 — Open questions became a false promise in the follow-up opener (NX33)

**Symptom:** Actual C safely declined exact Mumbai price and guaranteed EMI, but its saved summary proposed “I have those details ready”. The same summary still listed those questions as unanswered. This was an internal suggested opener, not customer-heard narration.
**Why 1:** The model turned a proposed follow-up into a statement of completed research.
**Why 2:** The summary prompt allowed a natural sales opener without explicitly preserving unavailable-answer status.
**Why 3:** The code copied unresolved record fields but trusted the generated opener independently of them.
**Why 4:** Existing tests checked summary shape and record copying rather than a contradiction between unknowns and the suggested next sentence.
**Why 5:** A valid structured response was treated as sufficient evidence for a future operational claim.
**Fix:** When the session has unresolved topics, non-callback escalations, or the generated summary has unanswered questions, code replaces only the opener with a neutral invitation to discuss the open questions. The prompt also prohibits claiming missing answers/quotes/approvals/finance terms already exist. Context, interests, objections, unanswered fields and session status keep their existing behavior; the original C snapshots are not rewritten.
**Prevention:** `evals/summary_contract.py` exercises the actual summary function with the exact C bad opener, each independent open-question signal, model-field preservation, no mutation of input status, a resolved-session opener, callback-only bookkeeping and mock behavior. Before:4/10; after:10/10, fake providers and blocked sockets.
**Limit:** This is a deterministic opener safeguard, not semantic validation of all summary fields or proof that a salesperson has obtained anything. Retained historical non-callback escalations conservatively keep the invitation neutral. No paid call, session migration or provider/schema change.


## 2026-09-18 — A direct customer statement did not reach retained context (NX32)

**Why 1:** Real C said “I mainly want help with stop-and-go traffic.” The stopped recap omitted that actual need.
**Why 2:** The statement reached Q&A, transcript and question history, but profile.why/followup stayed empty.
**Why 3:** Intake and explicit line/clarification answers stored context; a direct turn during narration bypassed those paths.
**Why 4:** The recap reads the retained profile, while runtime history is limited to the latest eight messages.
**Why 5:** Earlier context tests covered intake and clarification, not a new statement entered while narration was active.
**Deepest why type:** `code`
**Fix:** Before the existing QA dispatch, retain each exact new customer turn once in followup. Skip exact intake wording, an already-retained line and the clarification replay whose question/reply was already stored. This does not infer or modify focus, classify intent or change the QA workflow. Root also adds a QA prompt instruction distinguishing a buying need/context correction from an unsupported specification: acknowledge the actual need without a promised benefit, use applicable approved evidence or the existing one-question clarification, and keep genuine unknown/guarantee declines.
**Prevention and limit:** One new real-player browser case enters a statement during held narration, checks the next API profile, repeats the intake and statement to reject duplicates, verifies unchanged focus, and confirms exact wording once in the saved session/recap. The clarification case now verifies its original question and existing clarification pair exactly once. The prompt improves consultation guidance but does not enforce semantic correctness; the actual failed C run is preserved and live recovery is still required.


## 2026-09-18 — Personalized pitch adds unsupported relations and installation benefits (NX34)

**Why 1:** Actual A trace395 produced and spoke a warranty “or” relation and predictable-ownership benefit, a properly-secured child-seat outcome and an uncited installation-ease bridge; its boot batch omitted ISO V215.
**Why 2:** Valid fact IDs and matching numbers passed validation even when the additional meaning or a material qualifier was absent.
**Why 3:** The pitch prompt still allowed a “reasonable inference,” despite the shared evidence rules, and its local fact formatter omitted original source quotes/locators.
**Why 4:** The custom/bridge path used numeric and a short claim-word list rather than checking the observed explicit unknowns, measurement basis and added benefit wording before synthesis.
**Why 5:** Prior tests guarded invented customer numbers and hidden questions, but not these real cited-yet-unsupported additions.
**Deepest why type:** `code`
**Fix:** The existing pitch path receives full fact_context and a stronger scope-before-benefit prompt. Before speech, optional custom lines/bridges are omitted if they assert a policy relation while cited evidence explicitly leaves it unknown, drop a cited quantity's explicit ISO/VDA/SAE/DIN measurement basis, or add the narrow observed benefit vocabulary absent from affirmative cited evidence. Uncited assertion bridges are rejected. Reviewed route entries remain; no replacement product claims are synthesized.
**Prevention and limits:** Real plan_pitch fixtures fail9/19 before and pass19/19 after, including actual failed text, no rejected text reaching fake speech, intact reviewed route and positive documented relation/basis/equipment/fit-check controls. Both this suite and the10-case summary contract run in qa_deck. These conservative English lexical checks can omit useful optional phrasing and do not establish general semantic entailment, complete condition preservation, variant association, or multilingual coverage. Affirmative occurrence of a benefit word in a citation is necessary for this guard but is not sufficient proof of an arbitrary claim using that word. Prompt compliance and actual post-fix spoken output still require review. The pre-fix A session remains a failed grounding example; no third Build occurred.


**NX34 independent-review follow-up:** A standard present only in the exact source quote was initially missed, while its numeric code was rejected when correctly repeated. Two actual-path cases reproduced19/21; the detector now reads conditions and quote, and numeric validation admits only the recognized quoted standard's code, not every unrelated number in the quote. Final focused coverage is21/21. Honest negated relation wording and buyer-only benefit adjectives can be conservatively omitted by these lexical guards; no general entailment or complete safe-phrase coverage is claimed.
