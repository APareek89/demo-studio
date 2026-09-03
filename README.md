# Demo Studio

Turn a product's video, images and documents into a voice-led, interruptible demo — built by an
agentic pipeline with a human checkpoint at every place the agent could be wrong.

```bash
# one-time
python3 -m venv .venv
.venv/bin/python -m pip install --prefer-binary --only-binary=cryptography -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY, GEMINI_API_KEY and (for Indian-language speech) SARVAM_API_KEY

# run
.venv/bin/uvicorn server.app:app --port 8877
# → http://127.0.0.1:8877
```

No keys yet? `MOCK_LLM=1 .venv/bin/uvicorn server.app:app --port 8877` runs the whole flow with
schema-shaped fake outputs (plumbing only, no intelligence).

**Flow:** Demos → New demo → **Sources** (video/images, catalogue, brand guide, product URL) →
*Reading your sources…* → **Align** (approve Visuals · Facts · Persona & voice · Calls to action
through the prompt dock) → *Building your demo…* → **Rehearse** (run it as the customer, give
feedback, it rebuilds).

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
- QA: `evals/smoke_mock.py` (free), `evals/qa_accept.py` (free, upload failure cases), `evals/qa_real.py images|video [--lang hi-IN] [--resume <id>]` (paid; writes `docs/qa/<id>.md`). Report: `docs/QA-2026-09-03.md`.
