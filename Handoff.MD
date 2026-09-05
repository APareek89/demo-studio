# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## Current state — 2026-09-05

Demo Studio is a local FastAPI + no-build ES-module app. It turns product media and documents into a voice-led, interruptible, grounded demo. The committed workflow is:

**Demo Visual (optional) → Sources → Align → Rehearse**

- **Demo Visual:** the user can upload a ready self-contained GLB directly, or provide exactly five product views / one turntable video for image-to-3D. A direct GLB is structurally validated and enters the same rotate-and-approve gate at $0. For generated assets, Gemini selects real video frames and Nano Banana 2 Lite fills only missing angles; the user approves every view before Runware starts. Rodin Gen-2 accepts up to five approved views (real first, generated gap-fill after them), with Tripo v3.1 and TRELLIS.2 available. Generation is async, skip-safe, cost-traced and versioned. `My Assets` supports view, download, reuse and delete.
- **Sources / Align / Rehearse:** Configure runs the LangGraph pipeline through script + FAQ before Align. After stable script ids exist, Gemini 3.6 Flash inspects every real uploaded image against every spoken line and records full/partial/missing proof in `visual-audit.json`; incomplete model output is rejected, with conservative rules as the fallback. Align exposes this audit, supports direct fact/script edits, uses a compact card column and only 4–5 actionable chat bullets. New uploads re-read and re-align before Build.
- **Final CRETA QA:** `dm_c6a354fd` (“Hyundai CRETA N Line — Source-Synced”) is ready at bundle v11: 67 grounded facts, 20 pre-voiced FAQ entries, one opening question, 60 audited spoken lines, 13 Gemini-inspected images, a 20 s audio film, Sarvam `aditya`, and the approved 11.9 MB Rodin asset from five real recording views in `dm_a07d9306`. Gemini plus the strict full-proof gate corrected 29 picture assignments and identified 18 lines that need the 3D/card fallback because no image fully proves every feature. Test at `http://127.0.0.1:8877/?qa=final-audit#/play/dm_c6a354fd`.
- **Persistence:** the folder-per-demo store is the hot path. S3 incrementally mirrors every file including GLBs; DynamoDB stores demo/asset metadata and events. AWS account `511833557379`, region `ap-south-1`, bucket `demo-studio-511833557379`, tables `demo-studio-demos` and `demo-studio-events`.
- **Models:** Claude Opus 5 for fact registry, plan, script, Q&A and runtime route; Haiku for translation; Gemini 3.6 Flash for source vision and the post-script pixel audit; Gemini 3.1 Flash Lite Image / Nano Banana 2 Lite in minimal-thinking mode for optional cleanup/gap-fill; Sarvam Bulbul v3 / Saarika v2.5 with Gemini speech fallback; Runware Rodin Gen-2 for 3D.
- **Observability:** every model/3D call records stage, latency, input metadata, output and cost in `trace.jsonl` / `usage.jsonl`; every visual action is added to `RUN.md`. API keys remain server-side.

## Verification

- ✅ `evals/qa_visual.py`: 32/32 gates and failure paths, including direct GLB structure/dependency validation, review and approval; `evals/qa_runware.py`: 17/17 provider-contract cases; `evals/qa_visual_sync.py`: 25/25 stage/audit/card-routing cases.
- ✅ `evals/smoke_mock.py`: image-to-3D → approve → complete demo build → bundle/player asset → reuse/delete, plus the previous pipeline, multi-language, grounding, one-question and film-handoff checks.
- ✅ video path: ffmpeg frame extraction → five real-angle selection → multi-view mock Rodin GLB.
- ✅ `evals/qa_accept.py`: 24/24 upload and failure cases.
- ✅ Browser QA: new upload screen, 3D review, My Assets, large viewer and 3D-led player at desktop, 820 px and 430 px widths. Free GitHub screenshot skill installed and run; OS capture is black for the in-app browser, so final page inspection used the browser-native captures.
- ✅ Live browser QA on v10: Ravi asks exactly one needs question → polite bridge → full-stage film with audio → explicit spoken return → interactive walkthrough. Broad exterior lines use Rodin; missing/abstract claims use a compact ≤3-row keyword card over the 3D placeholder. The topic badge no longer overlaps that card. MP4 download is visible in the header. Unknown answers say “I don't know” and open the dealer-help form; the form also appears after 60% or two questions. v11 is the same UI/runtime with eight remaining non-full picture bindings cleared from data; the restarted v11 server, bundle contract, audit invariant and MP4 response passed, but a new browser capture was unavailable after the Mac locked.
- **Session efficiency:** 🎯 ~55% feature · 🔧 ~20% support · 🔁 ~25% rework. Rework came from live browser findings: stale intake data, a card/badge overlap and two Mermaid syntax issues.
- ✅ JavaScriptCore parse checks and Python compile checks.
- ⏹ Loop stays OFF by user decision. Full FMEA remains opt-in per `.power-coding/config.json`; Sentinel/Pulse checks stay on.

## Current blocker / next input

- **No blocker for testing the CRETA demo.** The local server is running on port 8877.
- Gemini image generation last returned quota 429 with a limit of 0; the current asset needs no generated angle because all five identity-consistent views came from the recording. Direct GLB upload is now the no-generation alternative.
- Existing product follow-ups remain: FAQ PDF question extraction; translated filler/FAQ audio; optional publish/embed step.

## Key decisions

- Uploaded media defines product identity: explicit uploaded images take precedence; otherwise the recording does. Generated derivatives may preserve that identity but never redefine colour, trim, pattern or feature detail.
- Rodin Gen-2 receives up to five **approved** views, always with a real identity view first; remaining real views precede human-approved AI gap-fill. Tripo v3.1 receives up to four; TRELLIS.2 remains the one-image fallback.
- Approving a 3D asset updates an existing `bundle.json` immediately; new builds include it automatically.
- The opening film owns the full stage. After it, each line chooses `model`, `evidence` or `card`; a literal image is allowed only on full visual coverage. A compact card may sit over the 3D placeholder, but never over unrelated evidence. Evidence never rotates to an attractive sibling.
- Script-image alignment is one existing post-author checkpoint, now upgraded from Haiku/tag-only judgment to Gemini pixel inspection. It is not a second workflow.
- Deleting an asset removes the GLB locally and from S3 when connected, while retaining source views for regeneration.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
