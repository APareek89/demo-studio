# Demo Studio

Turn product images, documents, videos and owner-supplied websites into a voice-led sales demo with human review and grounded customer Q&A. Python/FastAPI backend; plain JavaScript modules and CSS, without a frontend build step.

## Start here

[Current handoff](Handoff.MD) · [Contributor orientation](CODEX_INSTRUCTIONS.MD) · [Product rules](PRD.md) · [Build and runtime flow](docs/DEMO_BUILD_AND_RUN.md) · [Architecture](docs/ARCHITECTURE_FLOW.md) · [QA](Loop.MD) · [Lessons](Learning.MD).

The current gallery integration keeps the reviewed script pipeline, runtime recovery and image/tag/voice continuity. Anand authorized master/GitHub publication; the [gallery-template receipt](docs/qa/gallery-template-2026-09-25/README.md) records verification and Git status. AWS is a separate release: see [current release status](Handoff.MD#release-and-authorization), not this repository's branch name. The previous README is retained in [history](docs/history/context-before-master-2026-09-25/README.md).

## Local app with LiveKit

Install dependencies in a Python3.11 virtual environment using `requirements.txt` and install LiveKit Server1.13.7. The launcher finds the server on PATH or at `~/.local/lib/demo-studio/livekit-1.13.7/livekit-server`. For an isolated free preview:

```bash
preview_root=$(mktemp -d /tmp/demo-studio-preview.XXXXXX)
MOCK_LLM=1 CLOUD_SYNC=0 STORAGE_BACKEND=local \
  DEMO_STUDIO_DATA="$preview_root/data" \
  DEMO_STUDIO_GRAPH_DB="$preview_root/graph.sqlite" \
  .venv/bin/python scripts/run_local.py --state-dir "$HOME/.local/state/demo-studio/mock-preview"
```

Open [localhost:8910](http://127.0.0.1:8910). Public playback and Rehearse select LiveKit automatically; no URL flag is needed. The launcher starts only its own app and SFU and preserves the selected workspace data. On this Mac it detects the active private interface; other machines can pass `--rtc-host PRIVATE_IPV4`. See [transport and launch configuration](docs/livekit.md).

Mock outputs demonstrate plumbing, not customer-ready content or acoustic quality. For an authorized real build/conversation, retain the intended DATA/GRAPH paths and pass `--live-providers` with configured server-side credentials. Do not use protected port8896; `.env` must stay untracked. Raw uvicorn without transport configuration retains the diagnostic WebSocket transport.

## Current flow

Sources selects material, audience, languages, voice and one to five minutes (three by default). Read runs Understand → Coach → Plan → Author → Deck → FAQ. Align reviews six cards: Visuals, Facts, Script, Asked and answered, Persona & voice, and CTAs. Build records Voice → Bundle, enforcing approved evidence and the selected measured narration minimum. Rehearse offers the actual player, feedback and an explicit rehearsal action.

The player keeps source images, reviewed feature tags and recorded voice together. Its default gallery changes only the middle slide area: walk through pictures, enlarge the current view and focus a trusted feature anchor before its main narration. Top navbar and bottom transcript/microphone/chat/actions stay unchanged. Heroes and picture-free slides retain native rendering; `?presentation=native` is a diagnostic fallback. The player supports qualified final-speech interruption, local playback commands, grounded answers, three-second question windows and incremental session saving. Live lookup is restricted to enabled owner-source domains; external evidence stays turn-scoped. A snapshot-bound cache retains clean customer answers; unknowns remain evidence gaps.

One locked guide voice covers recorded and streamed speech. Text providers default to Gemini → Claude → Runware; provider readiness and speech configuration are independent. Sources, stage JSON, recordings and publications live under the configured demo storage; published evidence snapshots preserve existing sessions.

## Tests and limits

[Loop.MD](Loop.MD) records reproducible free contracts and exact counts. Free QA uses mock providers, isolated storage and blocked outbound sockets. The current [gallery-template review](docs/qa/gallery-template-2026-09-25/README.md) records verification and desktop/phone screenshots. The preceding [native slide review](docs/qa/slide-continuity-2026-09-24/review.md) remains historical evidence. [Paid QA](docs/qa/runtime-recovery-2026-09-24/paid-acceptance.md) retains the initial generation and answer failures as well as the reviewed recovery; it is not unattended first-pass proof. Physical microphone acceptance, caption word synchronization and selective Align rebuild routing remain outside completed work.
