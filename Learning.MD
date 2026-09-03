# Learning.MD — Demo Studio
> AGENT: add an entry whenever the basic flow changes, the user reports a bug or gives
> corrective feedback, or something took real time to figure out. CHECK THIS FILE FIRST
> before debugging — the answer may already be here. Plain language; first use of any
> technical term gets a one-line bracket explanation.

<!-- Newest first. -->

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
