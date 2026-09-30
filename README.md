# Demo Studio

Turn product images, documents, videos and owner-supplied websites into a voice-led sales demo with human review and grounded customer Q&A. Python/FastAPI backend; plain JavaScript modules and CSS, without a frontend build step.

## Start here

[Current handoff](Handoff.MD) · [Contributor orientation](CODEX_INSTRUCTIONS.MD) · [Product rules](PRD.md) · [Build and runtime flow](docs/DEMO_BUILD_AND_RUN.md) · [Architecture](docs/ARCHITECTURE_FLOW.md) · [QA](Loop.MD) · [Lessons](Learning.MD).

Live AWS app: [Demo Studio](https://demo-studio.3-6-183-210.sslip.io).

1. Create an account or sign in with your email and password.
2. Choose **Try with an example** for your own copy of a reviewed, recorded demo. Or create a demo and upload documents/images, paste product text, or add a product website.
3. Rehearse the BMW example immediately with existing narration and prepared evidence answers, without new AI calls. For your own material, Read → review six Align cards → Build → Rehearse. Build publishes only after the chosen narration duration and review gates pass.

The example is a cached copy in your workspace with public published playback; microphone conversation, new answers and editing are available in demos you create from your own sources. Original unpublished source documents and customer records are not copied. The portfolio example does not collect contact details, book test drives or arrange dealership follow-ups.

The portfolio release adds isolated creator accounts and light/dark shared UI while retaining the script pipeline, gallery, and image/tag/voice continuity. Hosted signup, sign-in/out, private owner/visitor and S3 isolation, all 96 example media hashes, and the muted BMW flow have passed. Native LiveKit typed conversation and saved recap also passed with microphone capture disabled.

One ordinary HTTP Build regenerated a 16-character Sarvam Bulbul v3 filler (1.195 s), reused 50 recordings and preserved the 122.64 s main route against its 120 s minimum. Its estimated cost was ₹0.048 (about $0.000571 at assumed ₹84/USD), not a billed invoice or a fully uncached generation proof. The final muted smoke check passed after restoration to ordinary real mode.

The [previous BMW deployment](https://13-202-0-79.sslip.io/#/play/dm_29df0418) and its data remain unchanged; its [release history](docs/aws/release-mobile-2026-09-26.md) is separate from this new app. The previous README is retained in [history](docs/history/context-before-master-2026-09-25/README.md).

## Local app with LiveKit

Install dependencies in a Python3.11 virtual environment using `requirements.txt` and install LiveKit Server1.13.7. The launcher finds the server on PATH or at `~/.local/lib/demo-studio/livekit-1.13.7/livekit-server`. For an isolated free preview:

```bash
preview_root=$(mktemp -d /tmp/demo-studio-preview.XXXXXX)
MOCK_LLM=1 PORTFOLIO_AUTH_ENABLED=0 CLOUD_SYNC=0 STORAGE_BACKEND=local \
  DEMO_STUDIO_DATA="$preview_root/data" \
  DEMO_STUDIO_GRAPH_DB="$preview_root/graph.sqlite" \
  .venv/bin/python scripts/run_local.py --state-dir "$HOME/.local/state/demo-studio/mock-preview"
```

Open [localhost:8910](http://127.0.0.1:8910). Public playback and Rehearse select LiveKit automatically; no URL flag is needed. The launcher starts only its own app and SFU and preserves the selected workspace data. On this Mac it detects the active private interface; other machines can pass `--rtc-host PRIVATE_IPV4`. See [transport and launch configuration](docs/livekit.md).

Mock outputs demonstrate plumbing, not customer-ready content or acoustic quality. For an authorized real build/conversation, retain the intended DATA/GRAPH paths and pass `--live-providers` with configured server-side credentials. Do not use protected port8896; `.env` must stay untracked. Raw uvicorn without transport configuration retains the diagnostic WebSocket transport.

## Hosted accounts and storage

Hosted mode requires `PORTFOLIO_AUTH_ENABLED=1`, `PUBLIC_BASE_URL`, `DATABASE_URL`, `DATABASE_SSL_CA_FILE`, and a private `AUTH_SECRET` of at least32characters. Secrets are loaded by deployment from AWS SSM. PostgreSQL holds users, bcrypt hashes, opaque session/visit capabilities, ownership and rate budgets; JSON/media and graph SQLite use persistent app-specific mounts. `migrations/001_portfolio_auth.sql` is idempotently initialized at startup. TLS verifies the PostgreSQL host against its configured CA. Health checks make a bounded database query and return503 on an outage.

Mock mode does not bypass accounts when auth is enabled. The explicit auth-off fixture mode is rejected with real providers. Private builder routes and metrics are creator-scoped; published playback uses a separate cookie-bound visit, including LiveKit and WebSocket. Recaps require the owning visitor or creator plus their signed link. New examples and duplicates do not import private visits or leads.

Known launch limits: password-reset email and Google sign-in are not configured. Examples use existing recordings; mock synthetic audio is not a voice-quality proof. MP4 export remains parked. Physical microphone/acoustic quality and a fully uncached hosted generation are not established by the current release checks. See [the exact verification scope](Loop.MD).

## Current flow

Sources selects material, audience, languages, voice and one to five minutes (three by default). Read runs Understand → Coach → Plan → Author → Deck → FAQ. Align reviews six cards: Visuals, Facts, Script, Asked and answered, Persona & voice, and CTAs. Build records Voice → Bundle, enforcing approved evidence and the selected measured narration minimum. Rehearse offers the actual player, feedback and an explicit rehearsal action.

The player keeps source images, reviewed feature tags and recorded voice together. Its default gallery changes only the middle slide area: walk through pictures, enlarge the current view and focus a trusted feature anchor before its main narration. Top navbar and bottom transcript/microphone/chat/actions stay unchanged. Heroes and picture-free slides retain native rendering; `?presentation=native` is a diagnostic fallback. The player supports qualified final-speech interruption, local playback commands, grounded answers, three-second question windows and incremental session saving. Live lookup is restricted to enabled owner-source domains; external evidence stays turn-scoped. A snapshot-bound cache retains clean customer answers; unknowns remain evidence gaps.

Optional background cleanup and guide artwork use Runware first, then PixelBin on provider failure. Configure `RUNWARE_API_KEY`, `RUNWARE_IMAGE_MODEL`, `PIXELBIN_API_TOKEN` and `MEDIA_PROVIDER_ORDER` on the server; generated assets retain their provider badge. Local originals and cached example assets do not call either service.

One locked guide voice covers recorded and streamed speech. Text providers default to Gemini → Claude → Runware; provider readiness and speech configuration are independent. Sources, stage JSON, recordings and publications live under the configured demo storage; published evidence snapshots preserve existing sessions.

## Tests and limits

[Loop.MD](Loop.MD) records reproducible free contracts and exact counts. Free QA uses mock providers, isolated storage and blocked outbound sockets. The current [gallery-template review](docs/qa/gallery-template-2026-09-25/README.md) records verification and desktop/phone screenshots. The preceding [native slide review](docs/qa/slide-continuity-2026-09-24/review.md) remains historical evidence. [Paid QA](docs/qa/runtime-recovery-2026-09-24/paid-acceptance.md) retains the initial generation and answer failures as well as the reviewed recovery; it is not unattended first-pass proof. Physical microphone acceptance, caption word synchronization and selective Align rebuild routing remain outside completed work.
