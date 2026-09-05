# Demo Studio

Turn a product's video, images and documents into a voice-led, interruptible demo — built by an
agentic pipeline with a human checkpoint at every place the agent could be wrong.

```bash
# one-time
python3 -m venv .venv
.venv/bin/python -m pip install --prefer-binary --only-binary=cryptography -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY, GEMINI_API_KEY, RUNWARE_API_KEY and (for Indian-language speech) SARVAM_API_KEY

# run
.venv/bin/uvicorn server.app:app --port 8877
# → http://127.0.0.1:8877
```

No keys yet? `MOCK_LLM=1 .venv/bin/uvicorn server.app:app --port 8877` runs the whole flow with
schema-shaped fake outputs (plumbing only, no intelligence).

**Flow:** My Demos → New demo → **Demo Visual** (optional: five real views or a turntable video → Runware TRELLIS.2 → approve) → **Sources** (video/images, catalogue, brand guide, product URL) →
*Reading your sources…* → **Align** (approve Visuals · Facts · Persona & voice · Calls to action
through the prompt dock) → *Building your demo…* → **Rehearse** (run it as the customer, give
feedback, it rebuilds).

An approved 3D asset remains the main visual throughout the demo. Script images and video shots appear as smaller supporting evidence, and the reusable GLB is available under **My Assets**. TRELLIS.2 accepts one conditioning image, so Demo Studio sends the strongest real front-three-quarter view; the other angles support review and playback.

Speech: Sarvam (Bulbul TTS + Saarika STT) is primary when its key is set, Gemini falls back, then the browser voice.

Everything a demo produces lives in `data/demos/<id>/` as JSON + media. Facts carry citations; the
guide can only say what's in the registry ("no citation, no claim"), at authoring and at runtime.

Docs: `PRD.md` · `docs/ARCHITECTURE_FLOW.md` · `docs/architecture-flow.html` · `Handoff.MD` (session state) ·
`Loop.MD` (evals) · `Learning.MD` (root causes).

## What changed on 2026-09-03 (batch 2)
- **3-minute pitch shape**: fixed opening (≤60 s) → main pitch (top 2–3 USPs, pain point first) → one "more features" block → close; signposted ("Let's start with what matters most to you —"); every number translated into the customer's routine. Technical detail only in `deeper` lines and Q&A.
- **Audience setting** (Sources → "Who is the demo for"): `everyday` (default) bans kWh / IDC / amp / Nm… from narration; the validator flags them and the author repairs.
- **Languages**: pick several; the first is the main script, the rest are translated and voiced at build; the player offers a chooser before Start; Q&A answers in the chosen language.
- **Observability** tab: every Claude / Gemini / Sarvam call with stage, latency, tokens, cost, system prompt, input and response (`data/demos/<id>/trace.jsonl`, `GET /api/demos/<id>/trace`).
- Player: ⏸ / ⏹ controls, image motion for image-only demos, at most 3 fact rows per card. Align: Approve on every card + Approve all + lightbox. Light-blue theme. Voice picker with preview. Bundled ffmpeg (`imageio-ffmpeg`).
- QA: `evals/smoke_mock.py` (free), `evals/qa_visual.py` (free, 3D gates/failures), `evals/qa_accept.py` (free, upload failure cases), `evals/qa_real.py images|video [--lang hi-IN] [--resume <id>]` (paid; writes `docs/qa/<id>.md`). Report: `docs/QA-2026-09-03.md`.

## What changed on 2026-09-04
- **Workflow is a LangGraph graph** (`server/graph.py`): router → understand → plan → align_enter → align_wait (interrupt: waits for your approvals / messages) → author → voice → rehearsal → bundle → finish. Checkpoints in `data/graph.sqlite`. `GET /api/workflow` returns the graph as Mermaid (also `docs/mermaid/00-workflow.mmd`). `pip install "langgraph-cli[inmem]"` then `langgraph dev` opens it in LangGraph Studio.
- **Cheapest models for the MVP**: Haiku 4.5 everywhere, Sonnet 5 for the plan, Gemini 3.5 flash-lite for vision, Sarvam bulbul v3 / Gemini flash TTS. Override with `CLAUDE_MODEL`, `CLAUDE_PLAN_MODEL`, `GEMINI_MODEL`, `GEMINI_IMAGE_MODEL`.
- **Picture editor** (`server/agents/visuals.py`): after authoring, every line's picture is chosen to show the part being described, with a reason per line in the run log.
- **Image clean-up** (`server/media.py`): transparent cut-outs get a clean studio background and defringed edges locally; `settings.enhance_images = "ai"` uses the Gemini image model when the key has quota. **Mascot**: built-in SVG guide in the player (`web/player/mascot.js`); a generated PNG when the image model is available.
- **Run log** `data/demos/<id>/RUN.md`: INPUT / OUTPUT / MODEL CALLS per stage with full prompts and responses; `GET /api/demos/<id>/runlog`.

## What changed on 2026-09-04 (afternoon)
- **Script at Align.** Configure runs plan → author → FAQ bank. Align has six cards — Visuals, Facts, Script, FAQ bank, Persona, CTAs — each with a **Preview** pop-up. The Script card lists every batch (≤ 20 s) mapped to seconds with the picture on screen per line; exact seconds appear after voicing.
- **No visible latency.** After the customer speaks, the planner writes 2–3 custom batches for their context and voices them server-side while the standard opening plays; recorded filler lines (acknowledgement, bridges, holds, nudges, small talk) cover every gap. The FAQ bank (20 generated + your FAQ document) is pre-voiced, so known questions answer instantly; new questions get a recorded "bear with me" then a live answer with server audio.
- **The voice never changes.** Runtime lines use the same provider or captions; the browser voice is never used when a server voice exists.
- **Pictures match words.** An information→image map is built at Configure and used by the script, the custom batches and the answers.

## AWS (added 2026-09-04)
Credentials come from `aws configure` (`~/.aws`), never from the repo. `server/cloud.py` mirrors every demo:
- **DynamoDB** `demo-studio-demos` (one item per demo: name, status, version, settings, approvals, stages, sources) and `demo-studio-events` (sessions, leads, stage completions; key `demo_id` + `ts#kind`).
- **S3** `demo-studio-<account>` — the whole demo folder under `demos/<id>/…` (sources, cleaned images, audio, JSON, `RUN.md`, traces). Private bucket; incremental sync after every stage in a background thread.
- Local `data/demos/` stays the working copy. A demo that exists only in the cloud is listed with a "cloud only" pill and restored on first open; media is fetched on demand.
- Routes: `GET /api/cloud` (status), `POST /api/cloud/setup` (create bucket + tables), `POST /api/demos/<id>/sync`. Disable with `CLOUD_SYNC=0`. Least-privilege policy for the IAM user: `docs/aws/iam-policy.json`.

## Where the logs are
| what | file per demo | written by | read by |
|---|---|---|---|
| the story of a run: inputs, every stage's INPUT / OUTPUT, every model call in full | `data/demos/<id>/RUN.md` | `server/runlog.py` (`stage_report`, `event`, `chat`, `runtime_qa`) | VS Code, `GET /api/demos/<id>/runlog` |
| one row per model / speech call with prompt, response, latency, tokens, cost | `trace.jsonl` | `server/usage.py:trace` called from `server/llm/claude.py`, `gemini.py`, `sarvam.py` | Observability tab, `GET /api/demos/<id>/trace` |
| cost accounting rows | `usage.jsonl` | `server/usage.py:record` | Playground › Cost, `GET /api/demos/<id>/usage` |
| stage decisions (validator issues, picture choices, FAQ questions, errors) | `logs/<epoch>-<stage>.json` | `server/store.py:log` from the agents | RUN.md folds them in |
| live progress lines shown in the overlay | in memory | `server/events.py:publish` via `orchestrator.emit_for` | `GET /api/demos/<id>/events` (SSE) |
| sessions, leads, eval runs | `sessions/`, `leads/`, `evals/` | `server/app.py` routes | Rehearse panel, Playground, DynamoDB `demo-studio-events` |
| server stdout (requests, uncaught errors) | terminal | uvicorn | the terminal that runs `uvicorn server.app:app --port 8877` |
