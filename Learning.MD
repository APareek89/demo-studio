# Learning.MD — Demo Studio
> AGENT: add an entry whenever the basic flow changes, the user reports a bug or gives
> corrective feedback, or something took real time to figure out. CHECK THIS FILE FIRST
> before debugging — the answer may already be here. Plain language; first use of any
> technical term gets a one-line bracket explanation.

<!-- Newest first. -->

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
