# Handoff.MD — Demo Studio
> AGENT: read this fully at session start; open with the pending points below (or ask
> "what would you like to do now?" if none). Update after every major change and when
> ~10% of context remains — then tell the user to start a fresh session with:
> "Refer to Handoff.MD in /Users/macbook/Documents/demo-studio and begin".
> Keep this file ONE SCREEN: current state only; history lives in Learning.MD and git.

## Compact summary of previous session
2026-09-04 (afternoon) — **Script at Align**: Configure now runs plan → author → FAQ bank; Align has six cards (Visuals, Facts, Script, FAQ bank,
Persona, CTAs) each with a **Preview pop-up**; the Script card is batch-by-batch (≤ 20 s), **mapped to seconds** with the picture per line.
**No visible latency at runtime**: custom batches for the buyer's context are written and voiced server-side while the opening plays;
recorded filler lines cover every gap; **the voice never changes** (same provider or captions); the **FAQ bank** (20 generated + FAQ doc)
is pre-voiced so known questions are instant; an information→image map keeps pictures in sync with words.

2026-09-04 — **Workflow moved to LangGraph** (`server/graph.py`, sqlite checkpointer, Align as an interrupt, `GET /api/workflow` → Mermaid,
`langgraph.json` for Studio), **cheapest models for the MVP** (Haiku everywhere, Sonnet 5 for the plan, Gemini 3.5 flash-lite for vision,
Sarvam bulbul v3 / Gemini flash TTS), a **picture-editor pass** so the screen shows the part being talked about (`agents/visuals.py`),
**local image clean-up** for transparent cut-outs (`media.enhance_images`, Gemini image model when billing allows), a **mascot**
(`web/player/mascot.js`, generated PNG when the Gemini image quota allows), and a **full-detail run log** per demo (`RUN.md`: INPUT / OUTPUT / MODEL CALLS per stage, full prompts).

2026-09-03 — Built Demo Studio v1 (FastAPI + no-build web; Claude reasons/writes, Gemini looks, Sarvam speaks),
folded in the evidence-based sales playbook (P01–P10, fixed opening + runtime pitch planner, scorecard, callback
lead capture, Indian languages), then the second feedback batch: **3-minute pitch shape** (opening ≤60 s → main
pitch → one "more features" block → close; signposts; every number translated into the customer's routine; a
plain-language **audience** setting with a jargon validator), **multi-language demos** (translate + voice per
language, chooser in the player), **Observability** tab (every call: stage, model, latency, tokens, cost, prompt,
response), light-blue theme, player pause/stop + image motion (max 3 fact rows), Approve on every Align card +
Approve-all + lightbox, "Configure Demo", voice picker with preview, bundled ffmpeg, acceptance/failure QA.

## Current state
- ✅ Backend: `server/app.py`, `orchestrator.py` (stage graph + per-stage seconds), `agents/{understand,plan,author,
  translate,voice,rehearsal,qa,align,pitch,bundle,principles}.py`, `llm/{claude,gemini,sarvam,mock}.py`, `store.py`,
  `usage.py` (usage.jsonl + trace.jsonl), `media.py` (AVIF/HEIC → JPEG; ffmpeg via imageio-ffmpeg: fast-start remux, 720p proxy >60 MB).
- ✅ Frontend: `web/app.js`, `demos.js`, `studio/{sources,align,rehearse}.js`, `player/player.js`, `playground.js`,
  `observability.js`, `styles.css` (light blue). Tabs: Demos · Studio (Sources → Align → Rehearse) · Playground · Observability.
- ✅ Settings per demo: `audience` (everyday | informed | expert), `languages` (first = main script), `pitch_minutes`,
  voice (`sarvam_speaker` / `voice_name`), `competition` (off), `rehearsal_questions`.
- ✅ Free evals green: `evals/smoke_mock.py` (pipeline + settings + hi-IN bundle + trace + jargon), `evals/qa_accept.py`
  (24/24 upload cases), browser click-through of Align approvals / lightbox / player pause-stop / Observability (mock server 8878).
- ✅ Paid QA drivers: `evals/qa_real.py images|video [--lang hi-IN]` → `docs/qa/<demo_id>.md` (stage seconds, calls, cost,
  runtime probes, opening script). Reports summarised in `docs/QA-2026-09-03.md`.
- ⏹ Loop is OFF by user decision (2026-09-03); FMEA stays on per config.
- ✅ AWS wired (`server/cloud.py`): account 511833557379, region ap-south-1, bucket `demo-studio-511833557379`, tables `demo-studio-demos` / `demo-studio-events`;
  incremental S3 mirror after every stage, DynamoDB record + events; cloud-only demos restore on open. Credentials via `aws configure` only.
- ✅ Workflow = `server/graph.py` (LangGraph): router → understand → plan → author → faq → align_enter → align_wait[interrupt] → voice → rehearsal → bundle → finish. `orchestrator.py` is now only the stage runner + action executor (`_run_stage`, `apply_actions`, `respond`).

## Pending points
- ✅ Runtime proof 2026-09-04 (docs/qa/runtime-2026-09-04.md): typed context → recorded acknowledgement → opening → server-voiced decision frame →
  recorded bridge → two custom batches about city + long trips; 0.0 s gaps at every boundary; one voice throughout; bank questions instant.
- 🤖 AGENT: one Creta batch still 21.2 s spoken (word limit met, this voice is slower on that line) — lower the split tolerance from +4 words to 0 if you want a hard 20.
- 🧑 USER (QA hand-over, 2026-09-04 evening): 1) RESTART your server — it runs 16:02 code:
  `pkill -f 'uvicorn server.app:app' ; .venv/bin/uvicorn server.app:app --port 8877`
  2) top up Sarvam credits (402 yesterday) 3) Creta (`dm_201201c4`) is parked at Align with the new-flow plan and author marked
  stale — press Build and the script is written by OPUS; or Configure Demo for a full fresh read. FMEA pre-QA report: docs/FMEA-2026-09-04.md.
- ✅ Opening film (2026-09-04 evening): optional 10–20 s video (Sources → “Opening film” zone, role intro_video; toggle in settings,
  default on when uploaded). Player: greeting → context → recorded lead-in (“here's a short film…”) → film plays unmuted with a Skip
  chip — the personalisation planner runs DURING the film; Gemini never reads it; it stays out of the demo's media pool.
- ✅ Full screen: `#/play/<id>` route mounts only the player (⛶, ⏸, ⏹, 💬, ↺, ✕ close → My Demos). My Demos → “▶ View” opens it
  (requests browser fullscreen on the click); Studio → Rehearse ⛶ routes there too. Fixed a TDZ crash on direct #/play loads.
- ✅ Models (user decision 2026-09-04): Opus = registry, plan, script, Q&A, runtime route; Haiku only for translation + picture
  matching (CLAUDE_LITE_MODEL); Gemini vision back to 3.6-flash; Sarvam already on bulbul:v3 / saarika:v2.5 (their newest). Loop stays OFF; FMEA on.
- ✅ Pre-QA fixes: fact edit/remove now stales the FAQ bank and Build re-answers it before voicing; Creta's stopped Haiku rebuild cleaned up.
- 🧑 USER: open Creta (`dm_201201c4`) → Align: check the Script card (Preview = second-by-second table) and the FAQ bank; then Rehearse: speak your context, ask a bank question and a new one — report any silence or voice change.
- 🧑 USER: the IAM user lacks s3:PutEncryptionConfiguration / PutBucketVersioning (bucket still private; S3 encrypts by default) — attach docs/aws/iam-policy.json if you want versioning.
- 🤖 AGENT: FAQ documents in PDF are not yet parsed for questions (text/markdown only); add the PDF text extractor hook in `faq.doc_questions`.
- 🤖 AGENT: fillers and FAQ answers are voiced in the main language only; extend `translate` to cover them for extra languages.
- 🧑 USER: pick one of the four Playground/tab-redesign prototypes (docs/design/README.md; artifacts published 2026-09-03 evening:
  A Console · B Stage · C Worksheet · D Guided) and confirm the 8 "missing links" listed there — nothing in the app changes until then.
- 🤖 AGENT: after the pick — build: tab rename/order, `#/play/<id>` full-screen route, Playground v2 (approved-only list → Test Now →
  Q/expected-A table with AI pre-fill → demo-mode evals with a Claude grader → insights by decline category → Take Action → additions-only
  rebuild → before/after). Playground QA on existing demos passed 2026-09-03 (docs/qa/playground-2026-09-03.md); answer latency outliers of
  17–26 s on decline paths are worth a look (soft-JSON path with long reasoning).
- ✅ FMEA scan done in-session (docs/FMEA-2026-09-03.md): 1 P0 + 3 P1 fixed the same evening (translation figure guard, trace PII
  redaction + TRACE_CAPTURE, breaker hard/soft classes, eval double-click guard); 14 P2 items tracked there — next: trace rotation,
  streamed uploads, settings snapshot at build, language-code allow-list, route trim to 480 words.
- 🧑 USER: open http://localhost:8877 (server: `.venv/bin/uvicorn server.app:app --port 8877`) → Rehearse on `dm_f79d9170`
  (images, English + Hindi) and `dm_78890026` (video); judge the 3-minute shape and the plain-language narration. Numbers in `docs/QA-2026-09-03.md`.
- 🧑 USER: decide (a) competitor comparisons policy (default OFF); (b) "use in demo" default for uploaded video (ON).
- 🧑 USER: **Sarvam has no credits left** (HTTP 402 on 2026-09-03 17:58 during the Hindi lines of `dm_f79d9170`; 10 lines fell back
  to Gemini TTS, and the video QA run voiced entirely on Gemini). Top up at dashboard.sarvam.ai, then rebuild the two QA demos
  (Rehearse → Restart demo → rebuild) so every line is Sarvam again. Until then the player uses Gemini voice + browser listening.
- ✅ Proof run 2026-09-04 13:22: Creta (`dm_201201c4`) re-authored and rebuilt through the graph on Haiku — 172 s, $0.31 (author 130 s incl.
  repair + picture editor, voice 41 s for 38 Sarvam lines); every gearbox line now shows a gear-lever / paddle / manual-knob image (docs/qa/run_creata_graph.log).
- 🧑 USER: the Gemini key has **no image-generation quota** (429 on every image model on 2026-09-04) — enable billing on the key to get AI background clean-up (`settings.enhance_images = "ai"`) and a generated mascot; until then clean-up is local (Pillow) and the mascot is the built-in SVG.
- 🤖 AGENT: prices for Gemini / Sarvam in `usage.py` are assumptions — set PRICE_* in `.env` once known.
- 🤖 AGENT: mock traces only Claude calls; Gemini/Sarvam mock branches are untraced (fine for UI QA).
- 🤖 AGENT: `validate-mmd.mjs` needs Node (not installed) — diagrams checked by eye; viewer built with `docs/build_viewer.py`.
- 🤖 AGENT: publish step (embed snippet / share link) — out of v1 scope, parked.

## Decisions
- 2026-09-03 — Python FastAPI + no-build ES-module frontend — machine has Python 3.11, no Node; ffmpeg now bundled via imageio-ffmpeg.
- 2026-09-03 — Gemini for video/images (+TTS fallback), Claude Opus 5 for plan/author/translate/align/Q&A/rehearsal, Sarvam for Indian speech — by model strength.
- 2026-09-03 — Fact registry with ids + deterministic validator (authoring and runtime), not RAG — "you can validate an id, not a vibe".
- 2026-09-03 — Stage graph with one align agent emitting structured actions; orchestrator executes and invalidates — auditable, re-runnable.
- 2026-09-03 — Playback seeks the original video to timecodes; no clipping. Fast-start remux + 720p agent proxy only when ffmpeg is present.
- 2026-09-03 — Folder-per-demo JSON store (`data/demos/<id>/`), DB later via one adapter.
- 2026-09-03 — Names: Studio → Sources · Align · Rehearse; "Configure Demo" starts the read. Streaming states "Reading your sources…" / "Building your demo…".
- 2026-09-03 — power-coding: Handoff (all 3 sections), git checkpoints auto, diagrams+viewer only (no debug tab), FMEA on feature-complete, Sentinel on, Pulse on.
- 2026-09-03 — Standard opening (intro + outcome, ≤ 60 s) is pre-authored and never changes; everything after is planned at runtime per buyer from approved blocks.
- 2026-09-03 — Runtime bridges obey the same validator as the script (figure without fact id → dropped); the planner may reorder/skip blocks but cannot invent content.
- 2026-09-03 — Don't-guess path offers a salesperson callback and captures a 10-digit Indian mobile (`[6-9]\d{9}`) → `leads/`.
- 2026-09-03 — Speech: Sarvam primary, Gemini → Cloud TTS → browser fallback per line; STT Sarvam when its key is set, else Web Speech.
- 2026-09-03 — Align has 5 cards (Pitch added); the playbook's 10-criterion scorecard runs at build time as a Claude judge.
- 2026-09-03 — Competitor comparisons OFF by default; when on, only user-added official URLs, C-ids, verify caveat on every comparative line.
- 2026-09-03 — Cost is measured, not estimated: `usage.jsonl` + `trace.jsonl` per demo; Observability reads both.
- 2026-09-03 — Pitch shape: ≤3 min narrated (opening ≤115 words, proof ≤60 words each ×3, features block ≤110, establish ≤45, closing ≤45; route ≤480 words) then Q&A; technical detail only in `deeper` lines and answers. Audience default `everyday` = no kWh/IDC/amp/Nm in narration.
- 2026-09-03 — Extra languages are translations of the approved script (same ids, visuals, facts), voiced at build; Q&A/pitch answer in the session's language; the player switches bundles client-side.
- 2026-09-03 — Voice providers have a circuit breaker: a 401/402/403/quota error trips the provider for 10 minutes so the chain
  moves on per line instead of retrying every line; the stage log and `/api/voices.unavailable` say which provider is out.
- 2026-09-03 — Narration lines render in parallel (`VOICE_WORKERS`, default 4) with per-task contextvars so usage/trace rows keep the demo id.
- 2026-09-04 — Persistence: local folder store stays the working copy; S3 mirrors files, DynamoDB holds the demo record and events; nothing in the pipeline reads from AWS on the hot path.
- 2026-09-04 — Script and FAQ bank are produced at Configure and aligned on before Build; Build only records voice, scores and bundles.
- 2026-09-04 — Runtime rule: nothing the customer hears is voiced live in a different voice — recorded fillers, server-voiced custom batches and answers in the same provider, captions otherwise; never the browser voice.
- 2026-09-04 — Batches are ≤ 20 s (≤ 50 words) and every batch ends at a pause point.
- 2026-09-04 — Workflow runs on LangGraph (reverses the 2026-09-03 plain-code decision at the user's request): one graph, sqlite checkpoints, Align = interrupt; nodes call vendor SDKs directly, no LangChain model wrappers.
- 2026-09-04 — Models for the MVP: Claude Haiku 4.5 everywhere, Claude Sonnet 5 for the plan only, Gemini 3.5 flash-lite for video/images, cheapest TTS tiers; env-overridable (CLAUDE_MODEL, CLAUDE_PLAN_MODEL, GEMINI_MODEL).
- 2026-09-04 — Every picture on screen is chosen per line by the picture-editor pass with a logged reason; uploaded pictures with a spoken subject are always shown at least once.
- 2026-09-04 — Run log keeps full prompts and responses (TRACE_MAX_CHARS 400k) with PII masked; TRACE_CAPTURE=meta turns text off.
- 2026-09-03 — Loop.MD stays `off` in this project (user decision); FMEA scans continue per `.power-coding/config.json`.
- 2026-09-03 — Observability keeps the full system prompt / input / response per call (truncated at 6k chars) in `trace.jsonl`; it is local data, never sent anywhere.

**Session efficiency:** 🎯 ~70% feature · 🔧 ~15% support (server restarts, no Node, ffmpeg) · 🔁 ~15% rework (approve-button miss, derived/ folder, mock traces)
