# Demo Studio

Turn product images, documents, videos and owner-supplied websites into a voice-led sales demo with human review and grounded customer Q&A. Python/FastAPI backend; plain JavaScript modules and CSS, without a frontend build step.

## Start here

[Current handoff](Handoff.MD) · [Contributor orientation](CODEX_INSTRUCTIONS.MD) · [Product rules](PRD.md) · [Build and runtime flow](docs/DEMO_BUILD_AND_RUN.md) · [Architecture](docs/ARCHITECTURE_FLOW.md) · [QA](Loop.MD) · [Lessons](Learning.MD).

Master contains the reviewed script pipeline, runtime recovery and native image/tag slide restoration. AWS is a separate release: see [current release status](Handoff.MD#release-and-authorization), not this repository's branch name. The previous README is retained in [history](docs/history/context-before-master-2026-09-25/README.md).

## Local mock app

Install dependencies in a virtual environment using `requirements.txt`. For an isolated free preview:

```bash
preview_root=$(mktemp -d /tmp/demo-studio-preview.XXXXXX)
MOCK_LLM=1 CLOUD_SYNC=0 STORAGE_BACKEND=local \
  DEMO_STUDIO_DATA="$preview_root/data" \
  DEMO_STUDIO_GRAPH_DB="$preview_root/graph.sqlite" \
  .venv/bin/uvicorn server.app:app --host 127.0.0.1 --port 8877
```

Open [localhost:8877](http://127.0.0.1:8877). Mock outputs demonstrate plumbing, not customer-ready content or acoustic quality. Do not use protected port8896. Real provider calls require configured server-side credentials and explicit run authorization; `.env` must stay untracked.

## Current flow

Sources selects material, audience, languages, voice and one to five minutes (three by default). Read runs Understand → Coach → Plan → Author → Deck → FAQ. Align reviews six cards: Visuals, Facts, Script, Asked and answered, Persona & voice, and CTAs. Build records Voice → Bundle, enforcing approved evidence and the selected measured narration minimum. Rehearse offers the actual player, feedback and an explicit rehearsal action.

The player keeps relevant native-aspect images, feature tags and recorded voice together. It supports qualified final-speech interruption, local playback commands, grounded answers, three-second question windows and incremental session saving. Both presentation URL modes use the native slide view. Live lookup is restricted to enabled owner-source domains; external evidence stays turn-scoped. A snapshot-bound cache retains clean customer answers; unknowns remain evidence gaps.

One locked guide voice covers recorded and streamed speech. Text providers default to Gemini → Claude → Runware; provider readiness and speech configuration are independent. Sources, stage JSON, recordings and publications live under the configured demo storage; published evidence snapshots preserve existing sessions.

## Tests and limits

[Loop.MD](Loop.MD) records reproducible free contracts and exact counts. Free QA uses mock providers, isolated storage and blocked outbound sockets. The latest [slide review](docs/qa/slide-continuity-2026-09-24/review.md) includes desktop/phone screenshots. [Paid QA](docs/qa/runtime-recovery-2026-09-24/paid-acceptance.md) retains the initial generation and answer failures as well as the reviewed recovery; it is not unattended first-pass proof. Physical microphone acceptance, caption word synchronization and selective Align rebuild routing remain outside completed work.
