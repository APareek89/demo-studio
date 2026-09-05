# Architecture flow — Demo Studio

Diagrams follow the Mindful Coding convention: one step per box, every box labelled
`[AGENT · model]` (an LLM decides), `[FUNCTION]` (deterministic code), `[LIBRARY · name]` or
`[DATA · store]`; decisions are diamonds with the decider on the diamond and the condition on the
edge; gates show the threshold. Source: `docs/mermaid/*.mmd` (authored by hand — update in the same
session as any structural change). Viewer: `python3 docs/build_viewer.py` → `docs/architecture-flow.html`.

Legend: 🟦 agent (LLM) · 🟩 function · 🟪 decision · ⬜ result · 🟦(cyan) question to the user · 🟪(violet) data/library.

## Gates at a glance

| Gate | Enforcer | Threshold / rule | Where |
|---|---|---|---|
| 3D image input | FUNCTION | exactly five required real product views; front ¾ preferred | `server/visual.py` |
| 3D video input | FUNCTION + AGENT | ≥1 readable extracted frame; Gemini selects real angles and creates only missing views; a generated image is never primary | `server/visual.py`, `server/media.py` |
| 3D provider | LIBRARY | one real image → async `microsoft:trellis-2@4b`; GLB header validated; exact returned cost traced | `server/llm/runware.py` |
| 3D approval | USER | review-ready attempt must be explicitly approved before it enters the player bundle / My Assets | `server/visual.py` |
| Read allowed | FUNCTION | ≥1 source; keys present or `MOCK_LLM=1` | `server/app.py` `read_sources` |
| One run per demo | FUNCTION | a second read/build/revise while a thread is alive → 409 | `orchestrator._spawn` |
| Build allowed | FUNCTION | all 4 approvals true | `orchestrator.start_build` |
| Grounding (authoring) | FUNCTION | `fact_ids ⊆ registry`; visual ref exists; text matching `NUMBERISH`/`CLAIMISH` with no fact id → `unverified` (excluded from voice + bundle) | `agents/author.validate` |
| Grounding (runtime) | FUNCTION | invalid/empty fact ids on a number/claim answer → don't-guess reply + escalate + unknown recorded | `agents/qa.answer` |
| Voice failure budget | FUNCTION | stop rendering after 4 provider errors; player falls back to browser voice | `agents/voice.render_script` |
| Rehearsal size | CONFIG | `settings.rehearsal_questions` (default 12, each a paid Claude call) | `config.REHEARSAL_QUESTIONS` |
| Player check-in | FUNCTION | 15 s countdown, 8 s auto-listen, 20 s after an answer | `web/player/player.js` `waitFor` |
| Pitch time budget | FUNCTION | soft JSON + `effort: low` + 50 s API timeout; player waits ≤45 s then falls back to the standard route (`personalized:false` in the session) | `agents/pitch.py`, `player.js` `startAfterIntake` |
| Bridge grounding | FUNCTION | a runtime bridge with a figure/claim and no fact id is dropped (`bridge_dropped`) | `agents/pitch.py` |
| Decline categories | AGENT rule + FUNCTION | pricing, discounts, finance, insurance, features, availability, warranty/service, comparisons → decline when not in the registry; comparisons only from competitor URLs when `settings.competition=on`, always with a verify caveat | `agents/qa.py` |
| Uploads | FUNCTION | 1 GB per file; AVIF/HEIC converted for the models, originals served; videos play from the original (ffmpeg optional) | `config.MAX_UPLOAD_MB`, `server/media.py` |
| Intake + opening film | FUNCTION | greet and ask one needs question; mic denied → typed fallback; then play the optional film with audio and an explicit spoken return before the interactive walkthrough | `player.js` `runIntake`, `playIntroFilm` |
| Approvals reset | FUNCTION | revise(understand) resets visuals + facts; edits mark author stale | `orchestrator._revise`, `apply_actions` |

## File index

| Stage | Files |
|---|---|
| Shell, routes, SSE | `server/app.py`, `server/events.py`, `web/app.js`, `web/api.js` |
| Demo Visual / assets | `server/visual.py`, `server/llm/runware.py`, `web/studio/visual.js`, `web/assets.js` |
| Store | `server/store.py` (`data/demos/<id>/…`) |
| Understand | `server/agents/understand.py`, `server/sources.py`, `server/llm/gemini.py`, `server/llm/claude.py`, `server/schemas.py` |
| Plan | `server/agents/plan.py` |
| Align | `server/agents/align.py`, `server/orchestrator.py` (`handle_message`, `apply_actions`, `_revise`), `web/studio/align.js` |
| Author / validator | `server/agents/author.py` |
| Voice | `server/agents/voice.py` |
| Rehearsal | `server/agents/rehearsal.py` |
| Bundle | `server/agents/bundle.py` |
| Runtime Q&A | `server/agents/qa.py` |
| Player | `web/player/player.js`, `web/studio/rehearse.js` |
| Mock mode | `server/llm/mock.py` (`MOCK_LLM=1`) |
| Playground | `web/playground.js`, `POST /evals`, `GET /usage`, `GET /faq-template` in `server/app.py` |
| Usage / cost | `server/usage.py` (contextvars; `usage.jsonl` per demo; price table overridable in `.env`) |
| Media | `server/media.py` (AVIF/HEIC → JPEG for the models; optional ffmpeg 720p proxy + fast-start) |
| Sales layer | `server/agents/principles.py`, `pitch.py`, scorecard in `rehearsal.py`, `llm/sarvam.py` |

## 01 · Master flow

```mermaid
%% see docs/mermaid/01-master.mmd
flowchart TD
  V["Optional Demo Visual: five views or video → TRELLIS.2 → approve"]:::ask --> U["USER adds sources"]:::ask --> READ["Read phase: Understand → Plan (02)"]:::fn --> CARDS["Align: 6 cards"]:::data --> ALIGN["Align loop (03)"]:::agent --> APPR{"all approved?"}:::dec
  APPR -- "yes" --> BUILD["Build: Author → Voice → Rehearsal → Bundle (04)"]:::fn --> PLAY["Rehearse: player (05)"]:::fn --> FB["feedback → align agent → rebuild"]:::agent
  APPR -- "no" --> ALIGN
  classDef agent fill:#dbeafe,stroke:#2563eb,color:#0b2a5b;
  classDef fn fill:#dcfce7,stroke:#16a34a,color:#052e16;
  classDef dec fill:#f3e8ff,stroke:#9333ea,color:#2a0a4a;
  classDef data fill:#ede9fe,stroke:#7c3aed,color:#2a0a4a;
  classDef ask fill:#cffafe,stroke:#0891b2,color:#083344;
```

Full-detail versions of 01–05 are in `docs/mermaid/` and rendered together in
`docs/architecture-flow.html`.
