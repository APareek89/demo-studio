# Handoff.MD — Demo Studio
> AGENT: read this fully at session start; open with the pending points below (or ask
> "what would you like to do now?" if none). Update after every major change and when
> ~10% of context remains — then tell the user to start a fresh session with:
> "Refer to Handoff.MD in /Users/macbook/Documents/demo-studio and begin".
> Keep this file ONE SCREEN: current state only; history lives in Learning.MD and git.

## Compact summary of previous session
2026-09-03 — Built Demo Studio v1 (FastAPI + no-build web; Claude reasons/writes, Gemini looks/speaks),
then folded in the evidence-based sales playbook: principles P01–P10 in the plan/author/pitch/Q&A prompts,
a fixed standard opening (intro + outcome) followed by a **runtime pitch planner** (customer state → one
follow-up → personalised route with grounded bridges), a 5th Align card (Pitch: decision frame, takeaway,
USPs, advance), a demo scorecard, callback/lead capture on the don't-guess path, per-demo Indian language,
and **Sarvam** (Bulbul TTS + Saarika STT) as the primary speech provider with Gemini fallback.

## Current state
- ✅ Backend: `server/app.py` (routes), `server/orchestrator.py` (stage graph, invalidation, threads,
  align actions), `server/agents/*` (understand, plan, author, voice, rehearsal, qa, align, bundle),
  `server/llm/{claude,gemini,mock}.py`, `server/store.py` (folder-per-demo JSON), `server/events.py` (SSE log).
- ✅ Frontend: `web/app.js` (router/shell), `demos.js`, `studio/{sources,align,rehearse}.js`, `player/player.js`
  (standard opening → `/run/pitch` while it plays → decision frame → follow-up → refined route with bridges →
  proof blocks → establish → advance; Sarvam STT capture via PCM→WAV→`/run/stt`; lead capture; language-aware).
- ✅ Sales layer: `server/agents/principles.py`, `pitch.py` (runtime planner + bridge validator), scorecard in
  `rehearsal.py`, `qa.py` don't-guess → callback + `parse_phone`/`save_lead`, `llm/sarvam.py`, provider chain in `voice.py`.
- ✅ Verified with MOCK_LLM=1: `evals/smoke_mock.py` (create → sources → read → align → approve → CTAs → build →
  bundle+audio served → Q&A don't-guess path → session → feedback → rehearsal) passes; UI checked in the browser
  (Demos, Sources, Align cards + conversation, Rehearse player). Real-key run NOT yet done (no .env).
- ▶ Loop offered (Loop.MD `status: offered`) — awaiting the user's answer.

## Pending points
- 🧑 USER: `.env` is still EMPTY (all keys) — add `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `SARVAM_API_KEY`
  (`open -a "Visual Studio Code" /Users/macbook/Documents/demo-studio/.env`), then run one real demo
  (samples/iqube images + https://www.tvsmotor.com/electric-scooters/tvs-iqube) and report what's off.
- ⚠️ Sarvam request shapes (`/text-to-speech` bulbul:v2 `text`/`speaker`; `/speech-to-text` saarika:v2.5 multipart)
  are from memory of the public API and untested against the live service — first real run will confirm; `sarvam.py`
  already retries the older `inputs` body shape on a 400.
- 🧑 USER: edit Loop.MD — confirm the goal and replace the example evals with real ones.
- 🤖 AGENT: Loop was offered on 2026-09-03; set Loop.MD status on/off per the user's reply. FMEA full scan offered (feature complete).
- 🤖 AGENT: publish step (embed snippet / share link) — out of v1 scope, parked.
- 🤖 AGENT: `validate-mmd.mjs` needs Node (not installed) — diagrams were checked by eye; viewer built with `docs/build_viewer.py`.

## Decisions
- 2026-09-03 — Python FastAPI + no-build ES-module frontend — machine has Python 3.11, no Node/ffmpeg.
- 2026-09-03 — Gemini for video/images/TTS, Claude Opus 5 for plan/author/align/Q&A/rehearsal — by model strength; Claude can't take video, Gemini shouldn't own grounding.
- 2026-09-03 — Fact registry with ids + deterministic validator (authoring and runtime), not RAG — "you can validate an id, not a vibe".
- 2026-09-03 — Stage graph with one align agent emitting structured actions; orchestrator executes and invalidates — auditable, re-runnable.
- 2026-09-03 — Playback seeks the original video to timecodes; no clipping — no ffmpeg dependency.
- 2026-09-03 — Folder-per-demo JSON store (`data/demos/<id>/`), DB later via one adapter.
- 2026-09-03 — Names: Studio → Sources · Align · Rehearse; Demos tab. Streaming states "Reading your sources…" / "Building your demo…".
- 2026-09-03 — Rehearsal default 12 questions (each a paid Claude call); configurable per demo.
- 2026-09-03 — power-coding: Handoff (all 3 sections), git checkpoints auto, diagrams+viewer only (no debug tab), FMEA on feature-complete, Sentinel on, Pulse on.
- 2026-09-03 — Standard opening (intro + outcome, ≤ ~2 min) is pre-authored and never changes; everything after is planned at runtime per buyer from approved proof blocks — "pre-render the spine, generate the edges" applied to the pitch.
- 2026-09-03 — Runtime bridges obey the same validator as the script (figure without fact id → dropped); the planner may reorder/skip blocks but cannot invent content.
- 2026-09-03 — Don't-guess path offers a salesperson callback and captures a 10-digit Indian mobile (regex `[6-9]\d{9}`) → `leads/`; the guide never asks for the number itself, the player does.
- 2026-09-03 — Speech: Sarvam primary (Indian languages), Gemini → Cloud TTS → browser fallback per line; STT Sarvam when its key is set, else Web Speech. Language is a per-demo setting used by plan/author/Q&A/TTS/STT.
- 2026-09-03 — Align has 5 cards (Pitch added); the playbook's 10-criterion scorecard runs at build time as a Claude judge.

**Session efficiency:** 🎯 ~75% feature · 🔧 ~20% support (pip `cryptography` wheel on Anaconda Python; no Node) · 🔁 ~5% rework
