# Handoff.MD — Demo Studio
> AGENT: read this fully at session start; open with the pending points below (or ask
> "what would you like to do now?" if none). Update after every major change and when
> ~10% of context remains — then tell the user to start a fresh session with:
> "Refer to Handoff.MD in /Users/macbook/Documents/demo-studio and begin".
> Keep this file ONE SCREEN: current state only; history lives in Learning.MD and git.

## Compact summary of previous session
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
- ▶ Loop offered (Loop.MD `status: offered`) — awaiting the user's answer.

## Pending points
- 🧑 USER: open http://localhost:8877 (server: `.venv/bin/uvicorn server.app:app --port 8877`), run the two QA demos
  listed in `docs/QA-2026-09-03.md` in Rehearse (mic on), judge the 3-minute shape and the plain-language narration.
- 🧑 USER: decide (a) competitor comparisons policy (default OFF); (b) "use in demo" default for uploaded video (ON);
  (c) turn the Loop on/off (Loop.MD); (d) FMEA full scan (offered at feature-complete).
- 🧑 USER: **Sarvam has no credits left** (HTTP 402 on 2026-09-03 17:58 during the Hindi lines of `dm_f79d9170`; 10 lines fell back
  to Gemini TTS, and the video QA run voiced entirely on Gemini). Top up at dashboard.sarvam.ai, then rebuild the two QA demos
  (Rehearse → Restart demo → rebuild) so every line is Sarvam again. Until then the player uses Gemini voice + browser listening.
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
- 2026-09-03 — Observability keeps the full system prompt / input / response per call (truncated at 6k chars) in `trace.jsonl`; it is local data, never sent anywhere.

**Session efficiency:** 🎯 ~70% feature · 🔧 ~15% support (server restarts, no Node, ffmpeg) · 🔁 ~15% rework (approve-button miss, derived/ folder, mock traces)
