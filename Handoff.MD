# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## Current state — 2026-09-05

Demo Studio is a local FastAPI + no-build ES-module app that turns product media and documents into a voice-led, interruptible, citation-grounded demo. The committed workflow is **Demo Visual (optional) → Sources → Align → Rehearse**.

- **Current gate:** Tata Harrier `dm_7fe9d434` is ready at v2 and passed the second sequential E2E gate at **94/100 with no open P0/P1**. It has 25 source records, ten official product images, a reviewed 10.89 MB Rodin Gen-2 GLB, 54 approved facts, a ten-segment script, 24/28 grounded FAQ answers with four intentional refusals, complete audio across every playable branch, three saved 10+ question sessions, and an integrity-checked 1280×720 H.264/AAC MP4. Evidence is in `docs/qa/harrier-e2e-2026-09-05.md`. Taigun remains passed at 94/100 in `docs/qa/taigun-e2e-2026-09-05.md`.
- **Next:** commit the Harrier checkpoint, then start Audi Q5. Do not create or regenerate another paid 3D asset without passing the pre-billable review gate. Harrier's only paid visual call was Rodin task `56b7fde2-a7b1-4937-81d3-a44c924f92bb` at exactly $0.40.
- **Grounding hardening:** unsupported facts can be rejected/restored; product framing, pitch and script/citations/visual refs have validated direct editors. Rejected facts cannot survive script validation. Human replacements preserve their completed model stage while invalidating dependants and requiring re-approval.
- **Resilience:** text-only structured work can fall back to Gemini when Claude is unavailable, or to explicit human-reviewed manifests when both reasoning providers are unavailable. FAQ generation checkpoints per answer and can resume or explicitly retry. Runtime Q&A uses a traced approved-registry fallback during provider outage cooldown, with fail-closed intent narrowing and explicit scope requirements.
- **Visual truth:** the runtime map excludes prices, capacities, terms and hidden safety mechanisms from generic product-photo proof. Literal evidence is used only when it supports the spoken claim; otherwise the UI uses a cited fact card or neutral 3D overview.
- **Voice / quiet QA:** Align shows the actual resolved Sarvam provider/speaker, re-recorded samples persist, and completeness covers main lines, FAQ, check-ins and fillers. Append `?mute=1` before the hash to mute narration, browser speech and opening film while keeping typed conversation and the visual timeline active. The current hidden browser is muted.
- **Responsive:** live player checks pass without document overflow at 320, 390, 768 and 1280 px; mobile controls wrap. The temporary mute is keyboard and screen-reader accessible.
- **Persistence / observability:** folder-per-demo store remains the hot path; S3 mirrors files and DynamoDB stores metadata/events. Every model and 3D call records stage, latency, inputs, outputs and cost in `trace.jsonl` / `usage.jsonl`; every visual action enters `RUN.md`. API keys remain server-side.

## Verification

- ✅ `evals/qa_visual_sync.py`: 82/82; `evals/qa_visual.py`: 32/32; `evals/qa_runware.py`: 17/17; `evals/qa_accept.py`: 24/24.
- ✅ `evals/smoke_mock.py`: full mocked image-to-3D/build/bundle/reuse/delete path and prior pipeline coverage.
- ✅ Python compilation and JavaScript parse checks.
- ✅ Harrier browser E2E: six individual Align approvals; 28-question rehearsal; three 10+ question chat sessions; strict variant-scope, refusal, comparison and synthetic-finance regressions; responsive widths; hidden muted run.
- ✅ Harrier MP4 v2: 1280×720, 23.94 fps, 160.00 s, H.264 High video + stereo AAC-LC; full decode completed without errors.
- ⏹ Power-coding Loop stays OFF by user decision. Full FMEA remains opt-in; Sentinel/Pulse checks stay on.

## Current blocker / next input

- **No blocker.** Local server is running on port 8877. Commit Harrier, then begin the Audi Q5 gate.
- Harrier residuals are disclosed P2/environment limits: unavailable Gemini pixel audit, minor GLB plate/texture imperfections and deterministic rather than model-led runtime personalisation during provider exhaustion. None permits unsupported claims.

## Key decisions

- Uploaded media defines identity; generated derivatives may preserve it but never redefine colour, trim or feature detail.
- Approving 3D requires rotated-view inspection; paid generation is one reviewed attempt at a time.
- The opening film owns the stage. After it, every line chooses model, exact evidence or a compact cited card; evidence never rotates to an attractive sibling.
- All six Align cards are opened, reviewed and approved individually. A build never bulk-approves or silently regenerates a human-corrected artifact.
- Comparison answers use uploaded official rival facts, include both sides and end with live-price/stock verification. Illustrative finance always identifies itself as synthetic and not an offer.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
