# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## Current state — 2026-09-05

Demo Studio is a local FastAPI + no-build ES-module app. It turns product media and documents into a voice-led, interruptible, grounded demo. The committed workflow is:

**Demo Visual (optional) → Sources → Align → Rehearse**

- **Demo Visual:** either exactly five product views (front, front ¾, side, rear ¾, rear) or one turntable video. Video frames are extracted locally and Gemini selects the clearest real angles; generated gap-fill stays review-only and is never sent as product truth. Runware defaults to multi-view Rodin Gen-2 (`hyper3d:rodin@gen-2`, up to five real images), with Tripo v3.1 and TRELLIS.2 available as fallbacks. Generation is asynchronous, skip-safe, cost-traced, versioned and review-gated. `My Assets` supports view, download, reuse and delete.
- **Sources / Align / Rehearse:** Configure runs the LangGraph pipeline through script + FAQ before Align. Six approval cards expose the actual visual map, facts, script, FAQ, persona and CTAs. Build records one consistent voice, rehearses and bundles. Runtime personalisation is produced under recorded cover; grounded Q&A never guesses.
- **Final CRETA QA:** `dm_c6a354fd` (“Hyundai CRETA N Line — Source-Synced”) is ready: 67 grounded facts, 20 pre-voiced FAQ entries, a 198.0 s authored narration, Sarvam `aditya` throughout, a 20 s audio opening film, and the approved 11.9 MB Rodin Gen-2 asset built from five real recording views in `dm_a07d9306`. Test at `http://127.0.0.1:8877/?qa=source-sync-ready#/play/dm_c6a354fd`.
- **Persistence:** the folder-per-demo store is the hot path. S3 incrementally mirrors every file including GLBs; DynamoDB stores demo/asset metadata and events. AWS account `511833557379`, region `ap-south-1`, bucket `demo-studio-511833557379`, tables `demo-studio-demos` and `demo-studio-events`.
- **Models:** Claude Opus 5 for fact registry, plan, script, Q&A and runtime route; Haiku for translation/picture matching; Gemini 3.6 Flash for vision; Gemini 3.1 Flash Lite Image (cheapest configured image tier) for optional cleanup/gap-fill; Sarvam Bulbul v3 / Saarika v2.5 with Gemini speech fallback; Runware Rodin Gen-2 for 3D.
- **Observability:** every model/3D call records stage, latency, input metadata, output and cost in `trace.jsonl` / `usage.jsonl`; every visual action is added to `RUN.md`. API keys remain server-side.

## Verification

- ✅ `evals/smoke_mock.py`: image-to-3D → approve → complete demo build → bundle/player asset → reuse/delete, plus the previous pipeline, multi-language and grounding checks.
- ✅ `evals/qa_visual.py`: 21/21 gates and failure paths; `evals/qa_runware.py`: 17/17 provider-contract cases across Rodin, Tripo and TRELLIS; `evals/qa_visual_sync.py`: 18/18 stage-routing cases.
- ✅ video path: ffmpeg frame extraction → five real-angle selection → multi-view mock Rodin GLB.
- ✅ `evals/qa_accept.py`: 24/24 upload and failure cases.
- ✅ Browser QA: new upload screen, 3D review, My Assets, large viewer and 3D-led player at desktop, 820 px and 430 px widths. Free GitHub screenshot skill installed and run; OS capture is black for the in-app browser, so final page inspection used the browser-native captures.
- ✅ Three live browser profiles: Ravi asks needs and focus → the audio film takes over → Ravi returns → approved opening → tailored roadmap → personalised route. All audio/media is preloaded and real waits use the recorded “give me one moment, please” bridge. Broad exterior/performance lines use the Rodin model; literal details replace it full-stage; abstract or multi-claim language uses a cited card. An early typed reply is queued as discovery context instead of racing into Q&A.
- 📊 Pulse: ~25% feature · ~30% support · ~45% rework. The main rework was replacing mock-only assumptions with the real Runware error, polling, cost and download contracts.
- ✅ JavaScriptCore parse checks and Python compile checks.
- ⏹ Loop stays OFF by user decision. Full FMEA remains opt-in per `.power-coding/config.json`; Sentinel/Pulse checks stay on.

## Current blocker / next input

- **No blocker for testing the CRETA demo.** The local server is running on port 8877.
- Gemini image generation still returns quota 429 with a limit of 0; the current asset needs no generated angle because all five identity-consistent views came from the recording. Future missing-angle synthesis needs Gemini image quota.
- Existing product follow-ups remain: FAQ PDF question extraction; translated filler/FAQ audio; optional publish/embed step.

## Key decisions

- Uploaded media defines product identity: explicit uploaded images take precedence; otherwise the recording does. Generated derivatives may preserve that identity but never redefine colour, trim, pattern or feature detail.
- Rodin Gen-2 receives up to five **real** views, primary first. Tripo v3.1 receives up to four real views; TRELLIS.2 remains the one-image fallback. Generated gap-fill is never a 3D conditioning input.
- Approving a 3D asset updates an existing `bundle.json` immediately; new builds include it automatically.
- The opening film owns the full stage. After it, each spoken line chooses exactly one mutually exclusive stage: `model` for visible exterior/performance, `evidence` for a literally matching uploaded image/shot, or `card` for abstract/multi-claim/source terms. Evidence never rotates to a merely attractive sibling.
- Deleting an asset removes the GLB locally and from S3 when connected, while retaining source views for regeneration.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
