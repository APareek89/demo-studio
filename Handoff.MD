# Handoff.MD — Demo Studio
> AGENT: read this fully at session start; open with the pending points below (or ask
> "what would you like to do now?" if none). Update after every major change and when
> ~10% of context remains — then tell the user to start a fresh session with:
> "Refer to Handoff.MD in /Users/macbook/Documents/demo-studio and begin".
> Keep this file ONE SCREEN: current state only; history lives in Learning.MD and git.

## Compact summary of previous session
2026-09-03 — Built Demo Studio v1 from the approved architecture (FastAPI + no-build web, Claude for
reasoning/writing, Gemini for video/images/TTS). Pipeline: Understand → Plan → [Align: 4 cards] →
Author (with grounding validator) → Voice → Rehearsal → Bundle → player. Added `MOCK_LLM=1` so the
whole path runs without keys. Configured power-coding (all layers).

## Current state
- ✅ Backend: `server/app.py` (routes), `server/orchestrator.py` (stage graph, invalidation, threads,
  align actions), `server/agents/*` (understand, plan, author, voice, rehearsal, qa, align, bundle),
  `server/llm/{claude,gemini,mock}.py`, `server/store.py` (folder-per-demo JSON), `server/events.py` (SSE log).
- ✅ Frontend: `web/app.js` (router/shell), `demos.js`, `studio/{sources,align,rehearse}.js`, `player/player.js`.
- ▶ Verification: backend compiles/imports; mock outputs validate. **Browser run of the full flow with
  MOCK_LLM=1: in progress this session — see Loop.MD evals.** Real-key run not yet done (keys not in .env).

## Pending points
- 🧑 USER: copy `.env.example` → `.env`, add `ANTHROPIC_API_KEY` and `GEMINI_API_KEY`; run one real demo
  (samples/iqube images + https://www.tvsmotor.com/electric-scooters/tvs-iqube) and report what's off.
- 🧑 USER: edit Loop.MD — confirm the goal and replace the example evals with real ones.
- 🤖 AGENT: offer the Loop when the first working draft is confirmed (mock run green + one real run).
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

**Session efficiency:** 🎯 ~75% feature · 🔧 ~20% support (pip `cryptography` wheel on Anaconda Python; no Node) · 🔁 ~5% rework
