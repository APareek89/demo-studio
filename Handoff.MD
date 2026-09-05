# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## Current state — 2026-09-05

Demo Studio is a local FastAPI + no-build ES-module app. It turns product media and documents into a voice-led, interruptible, grounded demo. The committed workflow is:

**Demo Visual (optional) → Sources → Align → Rehearse**

- **Demo Visual:** either exactly five real product views (front, front ¾, side, rear ¾, rear) or one turntable video. Video frames are extracted locally; Gemini selects real angles and generates only missing views. Every derived view is labelled. The strongest real front ¾ view drives Runware TRELLIS.2 (`microsoft:trellis-2@4b`) because that model accepts one input image. Generation is asynchronous, skip-safe, cost-traced, versioned and review-gated. Approval makes the GLB the persistent main player visual; evidence images remain small labelled thumbnails. `My Assets` supports view, download, attach to another demo and delete.
- **Sources / Align / Rehearse:** Configure runs the LangGraph pipeline through script + FAQ before Align. Six approval cards expose the actual visual map, facts, script, FAQ, persona and CTAs. Build records one consistent voice, rehearses and bundles. Runtime personalisation is produced under recorded cover; grounded Q&A never guesses.
- **Persistence:** the folder-per-demo store is the hot path. S3 incrementally mirrors every file including GLBs; DynamoDB stores demo/asset metadata and events. AWS account `511833557379`, region `ap-south-1`, bucket `demo-studio-511833557379`, tables `demo-studio-demos` and `demo-studio-events`.
- **Models:** Claude Opus 5 for fact registry, plan, script, Q&A and runtime route; Haiku for translation/picture matching; Gemini 3.6 Flash for vision; Gemini image model for derived views/cleanup when quota permits; Sarvam Bulbul v3 / Saarika v2.5 for Indian speech; Runware TRELLIS.2 for 3D.
- **Observability:** every model/3D call records stage, latency, input metadata, output and cost in `trace.jsonl` / `usage.jsonl`; every visual action is added to `RUN.md`. API keys remain server-side.

## Verification

- ✅ `evals/smoke_mock.py`: image-to-3D → approve → complete demo build → bundle/player asset → reuse/delete, plus the previous pipeline, multi-language and grounding checks.
- ✅ `evals/qa_visual.py`: 20/20 gates and failure paths (missing views/video, corrupt image, bad angle, duplicate build, locked inputs, skip/regenerate, GLB validation, one-time approval).
- ✅ `evals/qa_runware.py`: 12/12 no-spend provider-contract cases (wallet preflight, actionable 4xx, retries, multi-row polling, HTTPS output, credential isolation and exact/rejected cost accounting).
- ✅ video path: ffmpeg frame extraction → real-angle selection → mock TRELLIS.2 GLB.
- ✅ `evals/qa_accept.py`: 24/24 upload and failure cases.
- ✅ Browser QA: new upload screen, 3D review, My Assets, large viewer and 3D-led player at desktop, 820 px and 430 px widths. Free GitHub screenshot skill installed and run; OS capture is black for the in-app browser, so final page inspection used the browser-native captures.
- 📊 Pulse: ~25% feature · ~30% support · ~45% rework. The main rework was replacing mock-only assumptions with the real Runware error, polling, cost and download contracts.
- ✅ JavaScriptCore parse checks and Python compile checks.
- ⏹ Loop stays OFF by user decision. Full FMEA remains opt-in per `.power-coding/config.json`; Sentinel/Pulse checks stay on.

## Current blocker / next input

- **Runware is connected, but the wallet needs credits.** The first real task `03eedd6b-26ac-40b8-9a9a-89ffc6504a95` was rejected as `insufficientCredits`. After topping up, retry the existing Demo Visual; the request matches the official TRELLIS.2 schema and rejected work is now shown as $0 with the provider's actionable message.
- Gemini image generation previously returned quota 429; video still succeeds when all five real angles are visible, but missing-angle synthesis needs Gemini image quota/billing.
- Existing product follow-ups remain: Sarvam credit top-up; FAQ PDF question extraction; translated filler/FAQ audio; optional publish/embed step.

## Key decisions

- TRELLIS.2 is deliberately single-image conditioned; multi-view inputs improve selection/QA and supply thumbnails, but are not misrepresented as inputs to Runware.
- An AI-created angle is never the primary TRELLIS.2 conditioning image.
- Approving a 3D asset updates an existing `bundle.json` immediately; new builds include it automatically.
- Deleting an asset removes the GLB locally and from S3 when connected, while retaining source views for regeneration.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
