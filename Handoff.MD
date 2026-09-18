# Handoff.MD — Demo Studio

> Read fully at session start. Keep this to one screen; history belongs in `Learning.MD` and git.

## slides-v1 build — branch `slides-v1` (from `master` 794b8e5) — started 2026-09-18
Plan and the user's answers are in the 2026-09-18 chat; `master` stays untouched. Phases: 1 simplify ✅ · 2 sources + image parts · 3 deck ·
4 Align slide review · 5 player · 6 questions + slide routing · 7 AWS storage + session summary · 8 measure.
- **Phase 1 done (committed):** 3D/Runware path removed (7 files deleted, 23 edited, net ≈ −900 lines); player stage = `video` | `slide`;
  `qa._local_grounded_answer` + the 10-minute cooldown deleted — every provider down → decline + callback; `server/llm/runtime.py`
  tries `RUNTIME_PROVIDERS` (default `gemini,claude`) with `RUNTIME_TIMEOUT` 15 s and one retry; `CLAUDE_RUNTIME_MODEL` /
  `GEMINI_RUNTIME_MODEL`; MP4 export parked (409); `evals/qa_deck.py` replaces the three retired evals. Gates: compile ·
  smoke ✅ · qa_accept 24/24 · qa_deck 20/20 · JS syntax ✅. Docs, mermaid 01/04/05, Loop.MD, PRD, README updated.
- **Phase 2 done (committed):** `hero` drop zone in Sources (one image; a new hero demotes the previous to `product`); the Gemini image
  pass returns every visible part with a box (`[ymin,xmin,ymax,xmax]` 0-1000 → `{x,y,w,h}` 0-1) and a confidence, plus `full_product`;
  `visuals.part_names()` / `part_boxes()` read both the new and the old shape; `bundle.hero_image` = hero upload, else best full-product
  image, else first; a demo with video and no images gets one ffmpeg still per good shot (`media.extract_still`, `derived_from` on the
  source) and those stills are tagged like uploads. Diagram 02 updated; `qa_deck.py` covers it.
- 🧑 AWS access still needed for Phase 7: the `demo-studio` IAM user cannot create an instance role (needs `iam:CreateRole`,
  `iam:AttachRolePolicy`, `iam:PassRole`, `ec2:AssociateIamInstanceProfile`) or revoke security-group rules
  (`ec2:RevokeSecurityGroupIngress`). Your IP rotates (three addresses in one hour), so Phase 7 moves SSH to SSM Session Manager.

## Current state — 2026-09-06

Demo Studio is a local FastAPI + no-build ES-module app that turns product media and documents into a voice-led, interruptible, citation-grounded demo. The committed workflow is **Demo Visual (optional) → Sources → Align → Rehearse**.

- **Sequential programme complete:** Volkswagen Taigun `dm_5afb6dc5` v2, Tata Harrier `dm_7fe9d434` v2 and Audi Q5 `dm_302ab4aa` v1 each passed at **94/100 with zero open P0/P1**. Reports are in `docs/qa/taigun-e2e-2026-09-05.md`, `docs/qa/harrier-e2e-2026-09-05.md` and `docs/qa/audi-q5-e2e-2026-09-06.md`.
- **Audi evidence:** 26 source records, 45 approved facts, 25/28 grounded FAQ answers, six individually approved Align cards, complete audio for all 88 playable items, three saved ten-question sessions, responsive checks at 320/390/768/1280 px, and a fully decoded 1280×720 H.264/AAC MP4. Quiet mode stayed active throughout.
- **Audi visual:** one reviewed Rodin Gen-2 attempt from five real same-identity angles; task `f68aff15-6e2f-4bdb-8594-ed430159ed16`, 12.28 MB GLB, exact charge $0.40. Do not create another paid asset without the pre-billable view-review gate.
- **Grounding hardening:** compound intent paths are product-derived and fail closed for unsupported scope. Prices can name reviewed variants without inventing “cheapest”; pictures do not prove fitted equipment; finance guarantees, ground clearance, per-variant ADAS and crash-rating inferences decline without evidence. Runtime unknowns clear when answered and deduplicate against extraction gaps.
- **Source resilience:** visually rich PDFs that exceed a provider envelope may use only an explicit human-reviewed manifest with resolvable source citations. Control manifests remain excluded from ordinary extraction.
- **Voice resilience:** Align shows the resolved provider/speaker; ready requires audio for main, closing, deep, check-in, FAQ and filler branches. Provider circuit state is locked across render workers and partial work checkpoints for retry.
- **State integrity:** stage JSON publishes atomically, preventing browser polling from observing a partial file and resetting in-flight worker state. Async visual tests use an explicit barrier instead of scheduler timing.
- **Visual truth:** 3D is broad product overview only. Exact evidence supports observable features; prices, capacities, terms and hidden mechanisms use cited cards or refusals.
- **Quiet QA:** append `?mute=1` before the hash to mute narration, browser speech and opening film while retaining typed conversation and the visual timeline. Mute is keyboard and screen-reader accessible.
- **Persistence / observability:** folder-per-demo store remains the hot path; S3 mirrors files and DynamoDB stores metadata/events. Model and 3D calls record stage, latency, inputs, outputs and cost in `trace.jsonl` / `usage.jsonl`; visual actions enter `RUN.md`.

## Verification

- ✅ `evals/qa_visual_sync.py`: 98/98; `evals/qa_visual.py`: 32/32; `evals/qa_runware.py`: 17/17; `evals/qa_accept.py`: 24/24.
- ✅ `evals/smoke_mock.py`: full mocked source-to-bundle, multilingual build, speech, reuse/delete, trace and atomic visual-state paths.
- ✅ Python compilation and player/Align/Rehearse JavaScript syntax checks.
- ✅ Audi browser E2E: six card approvals; three muted ten-question sessions; strict variant, safety, comparison, finance and refusal paths; pause/resume, restart, chat, mute and responsive reflow.
- ✅ Audi MP4 v1: 1280×720, 23.93 fps, 157.54 s, H.264 High video + stereo AAC-LC 48 kHz; full decode completed without errors.
- ✅ 2026-09-17 re-verification before publishing: `py_compile` OK · `smoke_mock` OK · `qa_accept` 24/24 · `qa_visual_sync` 98/98 · `qa_visual` 32/32 · server boots and serves `/`, `/api/demos`, `/api/workflow`. `qa_runware` skipped (makes paid calls).
- ⏹ Power-coding Loop stays OFF by user decision. Full FMEA remains opt-in; Sentinel/Pulse checks stay on.

## Current blocker / next input

### ▶ PICK UP HERE (paused 2026-09-17 evening — resume tomorrow)

The AWS deployment is live and working; the instance is **deliberately left running**. Four things are queued:

1. 🧑 **USER — check AWS Console → Billing → Free tier.** Decides everything below. AWS's own flag says *both* `t3.micro`
   and `t3.small` are free-tier eligible in ap-south-1 (`t2.micro` is not), which is unusual — eligible is not the same as
   covered, so the billing page is the source of truth.
2. 🤖 **AGENT — if the allowance covers `t3.small`, resize to it.** Doubles RAM 1 GB → 2 GB and removes the reliance on swap
   for ffmpeg transcodes, which is the one real weak point in the current box. Needs one extra IAM permission the deploy
   policy deliberately omits: **`ec2:ModifyInstanceAttribute`**. Stop → change type → start, ~2 min downtime; URL and demos unaffected.
3. 🤖 **AGENT — turn S3 mirroring back on.** `CLOUD_SYNC=0` today because the box has no AWS credentials. Correct fix is an
   instance IAM role (needs `iam:PassRole` + a role with the existing S3/DynamoDB policy), **not** access keys in a file.
4. 🤖 **AGENT — one-command redeploy.** Today it is a manual `rsync` + `sudo systemctl restart demo-studio`.

Also open: a **domain** (then swap the `sslip.io` name in `/etc/caddy/Caddyfile` — one line, cert re-issues automatically),
and 🧑 **rotate the Vercel API token** that was pasted in chat on 2026-09-17.


- ✅ **Code is on GitHub (2026-09-17):** https://github.com/APareek89/demo-studio — private, `master`, 44 commits, 115 files.
  Pre-publish safety check: no live key material in any tracked file; `.env` and `data/` (uploads, demos, audio) excluded by .gitignore and confirmed absent on the remote.
- ✅ **LIVE ON AWS 2026-09-17 — https://13-202-0-79.sslip.io** (this is the working deployment).
  Instance `i-0410e37b7ab0297e1`, t3.micro, ap-south-1, Elastic IP 13.202.0.79, SSH `ssh -i ~/.ssh/demo-studio.pem ec2-user@13.202.0.79`.
  Caddy terminates HTTPS with a Let's Encrypt cert (auto-renews, expires 16 Dec 2026) and proxies to uvicorn on 127.0.0.1:8877;
  both run as systemd units (`demo-studio`, `caddy`) with Restart=always, so they survive reboots. 2 GB swap covers the 913 MB RAM.
  **HTTPS is mandatory, not cosmetic:** the player calls `getUserMedia` + `SpeechRecognition`, which browsers only allow on a
  secure origin — on plain HTTP the demo would load with no voice input. `sslip.io` provides the hostname until a domain is bought.
  **Verified live:** uploads of 6 / 12 / 40 MB all 200; 12 parallel requests all saw consistent state; idle usage 317 MB of 913 MB.
  Deployment scripts: `docs/aws/deploy-ec2.sh` (idempotent), `docs/aws/ec2-userdata.sh`, `docs/aws/ec2-deploy-policy.json`.
  **All 12 demos copied up 2026-09-17** (821 MB at ~14 MB/s); Audi Q5 verified end to end over HTTPS — bundle 200, `demo.mp4`
  streams 7.5 MB as video/mp4. Server: 847 MB of demos, 15 GB disk free, 273 MB of 913 MB RAM at idle.
  Open items: **`CLOUD_SYNC=0`** (no AWS creds on the box, so no S3 mirror — an instance IAM role is the right fix, not keys
  in a file), redeploys are a manual `rsync` + `sudo systemctl restart demo-studio`, and **SSH is locked to the laptop IP
  49.36.114.210** — a home IP change locks you out until the security group rule is updated.
  Note: macOS ships openrsync (protocol 29); `--info=progress2` is unsupported and fails the transfer. Use plain `-az`.
- ⚠️ **Vercel (2026-09-17, superseded by AWS — keep only as a shop window):** https://demo-studio-phi.vercel.app loads, but
  uploads over ~4.5 MB are refused by the platform (`FUNCTION_PAYLOAD_TOO_LARGE`) and state is per-instance — of 12 parallel
  requests, 10 saw an empty app. Scaffolding is `api/index.py` + `vercel.json` (legacy `builds`+`routes`; the modern `rewrites`
  form passes the rewritten path and 404s every route). No model keys are set there. Do not treat it as the product.
- ✅ **Real bug found and fixed 2026-09-17:** `langgraph` and `langgraph-checkpoint-sqlite` were missing from
  `requirements.txt`, so any fresh install (Vercel, Render or a new machine) crashed on import. `config.GRAPH_DB` now makes
  the LangGraph checkpoint path overridable (`DEMO_STUDIO_GRAPH_DB`) instead of hardcoded under the project directory.
- 🧹 **Disk cleanup 2026-09-17:** `data/` 1.1 GB → 804 MB. Removed `data/test-demos/` (eval fixtures) and the 115 MB
  `turntable.mov` in `dm_a07d9306` Creta3 — its 17 candidate frames were already extracted and its visual is approved in
  `images` mode, so nothing depended on the source file. All four finished demo films kept (Audi Q5, Taigun, Harrier,
  CRETA N Line); every demo is mirrored to S3 so these are restorable. Note: `visual/state.json` in Creta3 still carries a
  `video.path` pointing at the deleted file — harmless (the demo opens fine, no errors), but a re-extract would need it back.
  **`data/test-demos/` grows unboundedly** — it had reached 165 MB across runs and rebuilt at 7.5 MB for a single pass;
  worth deleting periodically, or adding a cleanup at eval teardown.
- The sequential build-and-QA programme is otherwise finished. Local server is on port 8877.
- Disclosed P2/environment limits: Gemini image/pixel audit unavailable, Audi GLB slightly high-gloss, deterministic runtime personalisation during intermittent pitch-provider 502s, and no acoustic listening score because the run stayed muted.

## Key decisions

- Uploaded media defines identity; generated derivatives may preserve it but never redefine colour, trim or feature detail.
- Approving 3D requires rotated-view inspection; paid generation is one reviewed attempt at a time.
- The opening film owns the stage. Afterwards, each line selects the model, exact evidence or a compact cited card.
- All six Align cards are opened, reviewed and approved individually. Human-corrected artifacts keep a validated state and are never silently regenerated.
- Comparisons use uploaded official rival facts, include both sides and require live-price/stock verification. Illustrative finance is always synthetic and not an offer.
- 2026-09-18 — slides-v1 removes the 3D / Runware path at the user's instruction (reverses the 2026-09-06 3D decisions below). Player stage modes are `video` | `slide`; existing GLB files on disk are untouched.
- 2026-09-18 — Runtime model calls (`/run/qa`, `/run/pitch`) go through `llm/runtime.py`: `RUNTIME_PROVIDERS` in order (default Gemini then Claude — no Claude credits), 15 s each, one retry; all fail → decline + callback. No local guessing, no cooldown. Build stages keep Claude-first with the existing Gemini fallback.
- 2026-09-18 — MP4 export is parked until a renderer exists for slides with HTML callouts.
- 2026-09-18 — `evals/qa_visual_sync.py` (source-grep assertions) is retired; `evals/qa_deck.py` tests the player contract end to end through the mock server.
- Git author: `Anand Pareek <anandp.pareek6@gmail.com>`.
