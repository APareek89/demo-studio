# Learning.MD — Demo Studio
> AGENT: add an entry whenever the basic flow changes, the user reports a bug or gives
> corrective feedback, or something took real time to figure out. CHECK THIS FILE FIRST
> before debugging — the answer may already be here. Plain language; first use of any
> technical term gets a one-line bracket explanation.

<!-- Newest first. -->

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
