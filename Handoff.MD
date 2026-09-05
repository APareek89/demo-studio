# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## Current state — 2026-09-05

Demo Studio is a local FastAPI + no-build ES-module app that turns product media and documents into a voice-led, interruptible, citation-grounded demo. The committed workflow is **Demo Visual (optional) → Sources → Align → Rehearse**.

- **Current gate:** Volkswagen Taigun `dm_5afb6dc5` is ready at v2 and passed the first sequential E2E gate at **94/100 with no open P0/P1**. It has 21 sources, 10 official identity-consistent product views, a reviewed 11.18 MB Rodin Gen-2 GLB, 92 extracted facts with two unsupported safety claims explicitly rejected, a 10-segment script, 28 FAQ entries, complete audio across all playable branches, three saved 10+ question sessions, and an integrity-checked 1280×720 H.264/AAC MP4. Evidence is in `docs/qa/taigun-e2e-2026-09-05.md`.
- **Next:** start Tata Harrier only after the Taigun report and clean commit. Audi Q5 remains third. Do not create or regenerate another paid 3D asset without passing the pre-billable review gate; Taigun's only paid visual call was Rodin task `f7126cb9-a73a-470d-b81b-81a9d3fba26f` at $0.40.
- **Grounding hardening:** unsupported facts can be rejected/restored; product framing, pitch and script/citations/visual refs have validated direct editors. Rejected facts cannot survive script validation. Human replacements preserve their completed model stage while invalidating dependants and requiring re-approval.
- **Resilience:** text-only structured work can fall back to Gemini when Claude is unavailable. FAQ generation checkpoints per answer and can resume or explicitly retry. Runtime Q&A uses a traced approved-registry fallback during provider outage cooldown, with hard refusal for unsupported high-risk claims.
- **Visual truth:** the runtime map excludes prices, capacities, terms and hidden safety mechanisms from generic product-photo proof. Literal evidence is used only when it supports the spoken claim; otherwise the UI uses a cited fact card or neutral 3D overview.
- **Voice / quiet QA:** Align shows the actual resolved Sarvam provider/speaker, re-recorded samples persist, and completeness covers main lines, FAQ, check-ins and fillers. Append `?mute=1` before the hash to mute narration, browser speech and opening film while keeping typed conversation and the visual timeline active. The current hidden browser is muted.
- **Responsive:** live player checks pass without document overflow at 320, 390, 768 and 1280 px; mobile controls wrap. The temporary mute is keyboard and screen-reader accessible.
- **Persistence / observability:** folder-per-demo store remains the hot path; S3 mirrors files and DynamoDB stores metadata/events. Every model and 3D call records stage, latency, inputs, outputs and cost in `trace.jsonl` / `usage.jsonl`; every visual action enters `RUN.md`. API keys remain server-side.

## Verification

- ✅ `evals/qa_visual_sync.py`: 59/59; `evals/qa_visual.py`: 32/32; `evals/qa_runware.py`: 17/17; `evals/qa_accept.py`: 24/24.
- ✅ `evals/smoke_mock.py`: full mocked image-to-3D/build/bundle/reuse/delete path and prior pipeline coverage.
- ✅ Python compilation and JavaScript parse checks.
- ✅ Taigun browser E2E: six individual Align approvals; 28-question rehearsal; three 10+ question chat sessions; refusal, comparison and synthetic-finance regressions; responsive widths; hidden muted run; cloud sync.
- ✅ Taigun MP4 v2: 1280×720, 23.92 fps, 175.88 s, H.264 video + stereo AAC; full decode completed without errors.
- ⏹ Power-coding Loop stays OFF by user decision. Full FMEA remains opt-in; Sentinel/Pulse checks stay on.

## Current blocker / next input

- **No blocker.** Local server is running on port 8877. Begin the Tata Harrier gate next.
- Known Taigun source gaps are intentional P2/input gaps, not hidden defects: no literal boot, rear-seat, safety-graphic, engine/GT-exterior or colour-swatch media; no supported current crash rating, city on-road price, binding finance offer or delivery promise. The demo uses cards/refusals instead of fabrication.

## Key decisions

- Uploaded media defines identity; generated derivatives may preserve it but never redefine colour, trim or feature detail.
- Approving 3D requires rotated-view inspection; paid generation is one reviewed attempt at a time.
- The opening film owns the stage. After it, every line chooses model, exact evidence or a compact cited card; evidence never rotates to an attractive sibling.
- All six Align cards are opened, reviewed and approved individually. A build never bulk-approves or silently regenerates a human-corrected artifact.
- Comparison answers use uploaded official rival facts, include both sides and end with live-price/stock verification. Illustrative finance always identifies itself as synthetic and not an offer.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
