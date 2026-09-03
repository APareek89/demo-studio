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
