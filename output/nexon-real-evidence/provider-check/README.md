# Real provider verification — 2026-09-18

All five minimal requests succeeded with `MODEL_TIER=customer`, `MOCK_LLM=0`. No successful check was repeated; no product code, model selection or `.env` was changed.

- Gemini text: requested and returned `gemini-3.8-flash`; valid nested JSON with the supplied F1/42 fixture; 5.92 seconds. 76 input and 232 output tokens including thinking. Configured estimate $0.000927.
- Gemini vision: requested and returned `gemini-3.6-flash`; correctly read a synthetic solid-blue PNG; 2.93 seconds. Raw usage: 1,114 input, 7 candidate and 112 thinking tokens. Existing accounting records $0.0003517; including thinking at the same configured rates gives $0.0006317.
- Runware text: native `textInference` accepted `openai:gpt@5.5`, returned HTTP 200 and `finishReason: stop`, and passed local nested-schema and fixture validation on its first request. 3.01 seconds; 162 input / 41 output tokens; **API-returned cost $0.00204**. The response does not echo the model name; the exact requested model and matching task UUID are preserved.
- Sarvam TTS: `bulbul:v3`, Priya, en-IN; generated 2.47 seconds of non-silent WAV in 0.80 seconds.
- Sarvam STT: `saarika:v2.5`, en-IN; transcribed that audio as “My daily drive is 12 kilometers.” in 0.84 seconds. Speech configured estimate $0.00088849 combined.

The total is approximately $0.00449 using existing repository rate assumptions and including the otherwise omitted vision thinking tokens. Only Runware reports an exact USD amount; this total is not a billing invoice.

The live check establishes Runware adapter/account readiness for this nested schema. It does not induce real outages of the first two providers; existing free provider contract tests establish routing order. This is not evidence of full authoring-schema success, video/image-generation readiness, human voice quality or full demo readiness. No Claude request was made.

Each JSON file contains timestamps, exact selected models, returned response metadata, usage, cost basis and validation result. `sarvam-readiness.wav` is the returned TTS; `sarvam-stt-input.wav` is the same sample as 16 kHz mono PCM for STT. `solid-blue-fixture.png` is synthetic test input, not product imagery.
