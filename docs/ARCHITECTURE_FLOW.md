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
| Read allowed | FUNCTION | ≥1 source; keys present or `MOCK_LLM=1` | `server/app.py` `read_sources` |
| One run per demo | FUNCTION | a second read/build/revise while a thread is alive → 409 | `orchestrator._spawn` |
| Build allowed | FUNCTION | all 6 approvals true | `orchestrator.start_build` |
| Grounding (authoring) | FUNCTION | `fact_ids ⊆ registry`; visual ref exists; text matching `NUMBERISH`/`CLAIMISH` with no fact id → `unverified` (excluded from voice + bundle) | `agents/author.validate` |
| Script-image proof | AGENT + FUNCTION | after stable line ids: Gemini inspects every real image (batches ≤12) against every spoken line; every line and image must return; only `full` coverage binds an image to a concrete feature line; otherwise the hero + cited card; model failure uses conservative rules | `agents/visuals.py`, `visual-audit.json` |
| Deck: picture per slide | FUNCTION | tagged parts vs. the slide's words, +2 for the script's own pick, score ≥ 3 else the hero | `agents/deck.choose_image` |
| Deck: callouts | AGENT + FUNCTION | model writes ≤ 3 per slide, ≤ 8 words, citing fact ids and a listed part; `author.ungrounded` drops an uncited figure/claim; an empty slide gets its own cited facts; Align overrides win | `agents/deck.py`, `deck-overrides.json` |
| Deck: label position | FUNCTION | part confidence ≥ 0.6 → anchor at the box centre and a label spot inside the frame, off the part box, clear of other labels; else side panel — never guessed | `agents/deck.place_callouts` |
| Grounding (runtime) | FUNCTION | invalid/empty fact ids on a number/claim answer → don't-guess reply + escalate + unknown recorded; every provider down → the same decline + callback, no cooldown, no local guessing | `agents/qa.answer` |
| Runtime providers | CONFIG | `RUNTIME_PROVIDERS` (default `gemini,claude,runware`); `MODEL_TIER=eval|customer` selects text defaults; explicit role overrides win. `RUNTIME_TIMEOUT` 15 s per provider request; Runware repair gets remaining budget (network-phase timeouts, not a strict wall timer); models `GEMINI_RUNTIME_MODEL` / `CLAUDE_RUNTIME_MODEL` / `RUNWARE_TEXT_MODEL` | `server/llm/runtime.py`, `config.py` |
| Build text fallback | FUNCTION | Claude → Gemini → Runware; Runware JSON + Pydantic, at most one repair; extracted PDFs retain source labels; media blocks never flattened; mock never calls out; vision/speech independent of text tier | `server/llm/claude.py`, `gemini.py`, `runware.py`, `agents/understand.py` |
| Voice completeness | FUNCTION | Locked builds retain the configured provider/speaker across narration, FAQ and fillers; matching hash caches remain usable during a circuit cooldown. Sarvam starts are paced; only 429 retries, within a bounded budget and Retry-After. Missing required audio checkpoints and fails before bundle; policy refusal is not routed around. | `agents/voice.render_script`, `llm/sarvam.py` |
| Rehearsal size | CONFIG | `settings.rehearsal_questions` (default 12, each a paid Claude call) | `config.REHEARSAL_QUESTIONS` |
| Player check-in | FUNCTION | owned response turn without auto-advance; voice and visible typing settle once; stale speech is ignored; qualified confirmations reach Q&A; follow-ups hold playback until explicit resolution | `web/player/player.js` `waitFor` |
| Pitch time budget | FUNCTION | runtime providers in order (Gemini → Claude → Runware), 15 s request budgets; player waits ≤2.65 s after the opening then falls back to the standard route (`personalized:false` in the session) | `agents/pitch.py`, `player.js` `startAfterIntake` |
| Bridge grounding | FUNCTION | a runtime bridge with a figure/claim and no fact id is dropped (`bridge_dropped`) | `agents/pitch.py` |
| Decline categories | AGENT rule + FUNCTION | pricing, discounts, finance, insurance, features, availability, warranty/service, comparisons → decline when not in the registry; comparisons only from approved competitor page/document facts with variant conditions and provenance when `settings.competition=on`, always with a verify caveat | `agents/qa.py` |
| Uploads | FUNCTION | 1 GB per file; AVIF/HEIC converted for the models, originals served; videos play from the original (ffmpeg optional) | `config.MAX_UPLOAD_MB`, `server/media.py` |
| Intake + opening film | FUNCTION | greet and ask exactly one needs/focus question; typing always visible; mic denied leaves the same turn open; then play the optional film with audio and an explicit spoken return | `player.js` `runIntake`, `playIntroFilm` |
| Slide stage | FUNCTION | one `.slide-stack`; `web/slide.js` renders each slide (native-fit picture, anchored callouts, evidence rail); callout reveal recomputes leader geometry; cinematic headings/shading and evidence retain native-aspect images, immutable Align coordinates and measured dock clearance; real questions wait, completed statements advance; a question routes stay / jump / none on fact ids and topics and returns to the exact interrupted line | `web/player/player.js` showSlideView / playLines / handleQuestion · `server/agents/deck.py` route_for |
| Storage | FUNCTION | one interface, two backends: local files (default) · AWS = local working copy + DynamoDB rows (`demo-studio-sessions`, TTL) + S3 mirror + pre-signed media; falls back to local without credentials; session summary written in the background from the true transcript; keyed read-only share link | `server/storage.py` · `server/agents/summary.py` · `server/cloud.py` |
| Answer latency | FUNCTION | four stamps per customer turn (voice ended → STT done → QA done → first answer audio) on the session record; `/trace` rolls them up to p50 / p95 per stage; Observability › Answer latency | `web/player/player.js` handleQuestion · `server/app.py` _latency · `web/observability.js` |
| Lead capture | FUNCTION | open dismissible form after ≥60% of route, ≥2 questions, or any unknown answer; valid phone is ten digits starting 6–9 | `player.js`, `POST /run/lead` |
| MP4 export | FUNCTION | parked: `GET /export.mp4` → 409 until the exporter is rebuilt for slides with HTML callouts | `server/exporter.py` |
| Approvals reset | FUNCTION | new uploads and source/fact/script edits reset affected approvals and re-run the relevant alignment path | `server/app.py`, `orchestrator.py` |
| Align review completeness | FUNCTION | F and C facts are shown together for review but stored separately; API/chat edit/reject share schema and source-ownership validation. Optional truth/source corrections require existing sources; changing a product source requires fresh locator/quote/conditions, while C facts stay with their source group. Script review supports lines, one intake, check-ins and title/outcome metadata; question claims reject, changed question audio clears and downstream work becomes stale | `store.edit_fact`, `store.set_fact_approval`, `agents/align.py`, `PATCH /align/script` |

## File index

| Stage | Files |
|---|---|
| Shell, routes, SSE | `server/app.py`, `server/events.py`, `web/app.js`, `web/api.js` |
| Store | `server/store.py` (`data/demos/<id>/…`) |
| Understand | `server/agents/understand.py`, `server/sources.py`, `server/llm/gemini.py`, `server/llm/claude.py`, `server/schemas.py` |
| Plan | `server/agents/plan.py` |
| Align | `server/agents/align.py`, `server/orchestrator.py` (`handle_message`, `apply_actions`, `_revise`), `web/studio/align.js` |
| Author / validator / pixel audit | `server/agents/author.py`, `server/agents/visuals.py`, `visual-audit.json` |
| Deck (one slide per segment) | `server/agents/deck.py`, `deck.json`, `deck-overrides.json`, `deck.<lang>.json` |
| Voice | `server/agents/voice.py` |
| Rehearsal | `server/agents/rehearsal.py` |
| Bundle | `server/agents/bundle.py` |
| Runtime Q&A | `server/agents/qa.py`, `server/llm/runtime.py` |
| Player | `web/player/player.js`, `web/studio/rehearse.js` (`server/exporter.py` parked) |
| Mock mode | `server/llm/mock.py` (`MOCK_LLM=1`) |
| Playground | `web/playground.js`, `POST /evals`, `GET /usage`, `GET /faq-template` in `server/app.py` |
| Usage / cost | `server/usage.py` (contextvars; `usage.jsonl` per demo; price table overridable in `.env`; Runware returned USD wins, Gemini text includes thinking tokens and uses the call-date promotional rate) |
| Media | `server/media.py` (AVIF/HEIC → JPEG for the models; optional ffmpeg 720p proxy + fast-start) |
| Sales layer | `server/agents/principles.py`, `pitch.py`, scorecard in `rehearsal.py`, `llm/sarvam.py` |

## 01 · Master flow

```mermaid
%% see docs/mermaid/01-master.mmd
flowchart TD
  U["USER adds sources"]:::ask --> READ["Read: Understand → Plan → Author → Deck → FAQ (02/04)"]:::fn --> CARDS["Align: 6 cards · editable script/facts · pixel coverage"]:::data --> ALIGN["Align loop (03)"]:::agent --> APPR{"all approved?"}:::dec
  APPR -- "yes" --> BUILD["Build: Voice → Rehearsal → Bundle (04)"]:::fn --> PLAY["Rehearse: one question → film → interactive player (05)"]:::fn --> FB["feedback → align agent → rebuild"]:::agent
  APPR -- "no" --> ALIGN
  classDef agent fill:#dbeafe,stroke:#2563eb,color:#0b2a5b;
  classDef fn fill:#dcfce7,stroke:#16a34a,color:#052e16;
  classDef dec fill:#f3e8ff,stroke:#9333ea,color:#2a0a4a;
  classDef data fill:#ede9fe,stroke:#7c3aed,color:#2a0a4a;
  classDef ask fill:#cffafe,stroke:#0891b2,color:#083344;
```

Full-detail versions of 01–05 are in `docs/mermaid/` and rendered together in
`docs/architecture-flow.html`.
