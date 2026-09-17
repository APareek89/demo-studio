# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## Current state — 2026-09-06

Demo Studio is a local FastAPI + no-build ES-module app that turns product media and documents into a voice-led, interruptible, citation-grounded demo. The committed workflow is **Demo Visual (optional) → Sources → Align → Rehearse**.

- **Sequential programme complete:** Volkswagen Taigun `dm_5afb6dc5` v2, Tata Harrier `dm_7fe9d434` v2 and Audi Q5 `dm_302ab4aa` v1 each passed at **94/100 with zero open P0/P1**. Reports are in `docs/qa/taigun-e2e-2026-09-05.md`, `docs/qa/harrier-e2e-2026-09-05.md` and `docs/qa/audi-q5-e2e-2026-09-06.md`.
- **Audi evidence:** 26 source records, 45 approved facts, 25/28 grounded FAQ answers, six individually approved Align cards, complete audio for all 88 playable items, three saved ten-question sessions, responsive checks at 320/390/768/1280 px, and a fully decoded 1280×720 H.264/AAC MP4. Quiet mode stayed active throughout.
- **Audi visual:** one reviewed Rodin Gen-2 attempt from five real same-identity angles; task `f68aff15-6e2f-4bdb-8594-ed430159ed16`, 12.28 MB GLB, exact charge $0.40. Do not create another paid asset without the pre-billable view-review gate.
- **Grounding hardening:** compound intent paths are product-derived and fail closed for unsupported scope. Prices can name reviewed variants without inventing “cheapest”; pictures do not prove fitted equipment; finance guarantees, ground clearance, per-variant ADAS and crash-rating inferences decline without evidence. Runtime unknowns clear when answered and deduplicate against extraction gaps.
- **Source resilience:** visually rich PDFs that exceed a provider envelope may use only an explicit human-reviewed manifest with resolvable source citations. Control manifests remain excluded from ordinary extraction.
- **Voice resilience:** Align shows the resolved provider/speaker; ready requires audio for main, closing, deep, check-in, FAQ and filler branches. Provider circuit state is locked across render workers and partial work checkpoints for retry.
- **State integrity:** stage JSON publishes atomically, preventing browser polling from observing a partial file and resetting in-flight worker state. Async visual tests use an explicit barrier instead of scheduler timing.
- **Visual truth:** 3D is broad product overview only. Exact evidence supports observable features; prices, capacities, terms and hidden mechanisms use cited cards or refusals.
- **Quiet QA:** append `?mute=1` before the hash to mute narration, browser speech and opening film while retaining typed conversation and the visual timeline. Mute is keyboard and screen-reader accessible.
- **Persistence / observability:** folder-per-demo store remains the hot path; S3 mirrors files and DynamoDB stores metadata/events. Model and 3D calls record stage, latency, inputs, outputs and cost in `trace.jsonl` / `usage.jsonl`; visual actions enter `RUN.md`.

## Verification

- ✅ `evals/qa_visual_sync.py`: 98/98; `evals/qa_visual.py`: 32/32; `evals/qa_runware.py`: 17/17; `evals/qa_accept.py`: 24/24.
- ✅ `evals/smoke_mock.py`: full mocked source-to-bundle, multilingual build, speech, reuse/delete, trace and atomic visual-state paths.
- ✅ Python compilation and player/Align/Rehearse JavaScript syntax checks.
- ✅ Audi browser E2E: six card approvals; three muted ten-question sessions; strict variant, safety, comparison, finance and refusal paths; pause/resume, restart, chat, mute and responsive reflow.
- ✅ Audi MP4 v1: 1280×720, 23.93 fps, 157.54 s, H.264 High video + stereo AAC-LC 48 kHz; full decode completed without errors.
- ✅ 2026-09-17 re-verification before publishing: `py_compile` OK · `smoke_mock` OK · `qa_accept` 24/24 · `qa_visual_sync` 98/98 · `qa_visual` 32/32 · server boots and serves `/`, `/api/demos`, `/api/workflow`. `qa_runware` skipped (makes paid calls).
- ⏹ Power-coding Loop stays OFF by user decision. Full FMEA remains opt-in; Sentinel/Pulse checks stay on.

## Current blocker / next input

- ✅ **Code is on GitHub (2026-09-17):** https://github.com/APareek89/demo-studio — private, `master`, 44 commits, 115 files.
  Pre-publish safety check: no live key material in any tracked file; `.env` and `data/` (uploads, demos, audio) excluded by .gitignore and confirmed absent on the remote.
- ⚠️ **Deployed to Vercel 2026-09-17 at the user's instruction — live but only partly functional.**
  URL https://demo-studio-phi.vercel.app (project `anandpro26/demo-studio`). Scaffolding: `api/index.py` (ASGI entry,
  points DATA_DIR/GRAPH_DB at /tmp, CLOUD_SYNC=0), `vercel.json` (legacy `builds`+`routes` — the modern `rewrites` form
  passes the rewritten path and 404s every route), `.vercelignore`. **Measured on the live URL, not predicted:**
  - ✅ App boots, UI serves, `/`, `/api/demos`, `/api/workflow` all 200. Uploads up to ~4.5 MB succeed.
  - ❌ **Uploads over ~4.5 MB are rejected by the platform** (`FUNCTION_PAYLOAD_TOO_LARGE`): 1 MB and 4 MB → 200; 6 MB and
    12 MB → 413. The app itself allows 1024 MB. Product video, the core input, cannot be uploaded at all.
  - ❌ **State is per-instance and not shared.** A demo created on one instance was invisible to others: of 12 parallel
    requests, 10 saw an empty app and 2 saw the demo. `/tmp` is per-Lambda and is lost when the instance recycles.
  - ❓ Untested: no model API keys are set in the Vercel project, so nothing model-driven runs there. A real build would
    also meet the 60 s function ceiling against the measured 172 s build, and background threads die when a response returns.
  - Bundle is 272 MB, over Vercel's standard size; the build only passes because Vercel auto-optimises dependencies.
  **Treat the Vercel URL as a shop window, not the product.** For a working hosted demo the recommendation is unchanged:
  **Render** (a `Render_Key` is already in `~/Documents/mysecrets`) — always-on machine, persistent disk, code unchanged.
- ✅ **Real bug found and fixed 2026-09-17:** `langgraph` and `langgraph-checkpoint-sqlite` were missing from
  `requirements.txt`, so any fresh install (Vercel, Render or a new machine) crashed on import. `config.GRAPH_DB` now makes
  the LangGraph checkpoint path overridable (`DEMO_STUDIO_GRAPH_DB`) instead of hardcoded under the project directory.
- 🧹 **Disk cleanup 2026-09-17:** `data/` 1.1 GB → 804 MB. Removed `data/test-demos/` (eval fixtures) and the 115 MB
  `turntable.mov` in `dm_a07d9306` Creta3 — its 17 candidate frames were already extracted and its visual is approved in
  `images` mode, so nothing depended on the source file. All four finished demo films kept (Audi Q5, Taigun, Harrier,
  CRETA N Line); every demo is mirrored to S3 so these are restorable. Note: `visual/state.json` in Creta3 still carries a
  `video.path` pointing at the deleted file — harmless (the demo opens fine, no errors), but a re-extract would need it back.
  **`data/test-demos/` grows unboundedly** — it had reached 165 MB across runs and rebuilt at 7.5 MB for a single pass;
  worth deleting periodically, or adding a cleanup at eval teardown.
- The sequential build-and-QA programme is otherwise finished. Local server is on port 8877.
- Disclosed P2/environment limits: Gemini image/pixel audit unavailable, Audi GLB slightly high-gloss, deterministic runtime personalisation during intermittent pitch-provider 502s, and no acoustic listening score because the run stayed muted.

## Key decisions

- Uploaded media defines identity; generated derivatives may preserve it but never redefine colour, trim or feature detail.
- Approving 3D requires rotated-view inspection; paid generation is one reviewed attempt at a time.
- The opening film owns the stage. Afterwards, each line selects the model, exact evidence or a compact cited card.
- All six Align cards are opened, reviewed and approved individually. Human-corrected artifacts keep a validated state and are never silently regenerated.
- Comparisons use uploaded official rival facts, include both sides and require live-price/stock verification. Illustrative finance is always synthetic and not an offer.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
