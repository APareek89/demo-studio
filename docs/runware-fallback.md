# Text fallback and model tiers

Approved 2026-09-18. `MODEL_TIER=eval` is the default; `customer` explicitly selects the higher-cost text models. `eval` is a cost tier, not a free mode: only `MOCK_LLM=1` avoids provider calls.

| Provider | Eval model | Input / output USD per million tokens | Customer model | Input / output USD per million tokens |
|---|---|---|---|---|
| Claude | `claude-haiku-4-5-20251001` | $1 / $5 | `claude-opus-5` | $5 / $25 |
| Gemini | `gemini-3.5-flash-lite` | $0.30 / $2.50 | `gemini-3.8-flash` | $0.75 / $3.75 through 2026-12-31 UTC; $1.50 / $7.50 thereafter |
| Runware | `deepseek:v4@flash` (DeepSeek V4 Flash) | $0.076 / $0.153 | `openai:gpt@5.5` (GPT-5.5) | $5 / $30 |

Sources checked 2026-09-18: [Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing), [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Runware DeepSeek](https://runware.ai/docs/models/deepseek-v4-flash), [Runware GPT-5.5](https://runware.ai/docs/models/openai-gpt-5-5), [Runware native API](https://runware.ai/docs/platform/introduction).

These are standard uncached token rates, not a quote for a whole demo. Runware's returned cost takes precedence over an estimate, including on generated responses that fail validation. Both malformed and repaired generations count. If returned cost is absent, the two approved models and their documented slug aliases use `usage.PRICES`. An unknown Runware override without a returned cost is flagged as unpriced in traces and usage notes; its cost is not included in the numeric total. Gemini text accounting includes thinking tokens and chooses the promotional rate from each call's timestamp.

## Design calls

- Build structured-text calls try Claude → Gemini → Runware. Runtime tries Gemini → Claude → Runware, controlled by `RUNTIME_PROVIDERS`. Runtime disables Claude's nested fallback so it never traverses the same chain twice. All down still means decline + callback.
- The native Runware `textInference` endpoint was chosen because JSON mode and `jsonSchema` are explicitly documented there. No SDK or additional dependency is needed. Routing the third fallback back to Gemini was rejected: DeepSeek and GPT provide a different underlying model provider.
- Each Runware request uses synchronous delivery, JSON output, a schema envelope with `strict:false`, local Pydantic validation and at most one JSON repair. The docs do not establish support for every nested Pydantic schema; live compatibility remains unverified. No schema is silently stripped to make a response pass.
- Text-only fallbacks reject image/PDF blocks. Understand explicitly extracts PDF text with source IDs and names before its secondary text chain. Failed text-only extraction does not start the chain again. The existing reviewed-manifest recovery remains available.
- `GEMINI_TEXT_MODEL` is separate from `GEMINI_MODEL`: the tier switch affects text, while image/video analysis, image generation and speech keep their existing configuration. No player, Align, stage graph or persisted demo schema changes.
- Explicit Claude role overrides and Gemini text/runtime overrides win over tier defaults. `RUNWARE_TEXT_MODEL` overrides eval; `RUNWARE_TEXT_MODEL_PREMIUM` overrides customer. An invalid tier fails configuration instead of silently selecting a model. `/api/health` reports the tier, effective models and whether keys are configured; it is not a live account probe.

## Verify and operate

Set the tier and any overrides in the environment, then restart the local server. Inspect `/api/health` for effective selection. `.env.example` documents the knobs; the real `.env` is not changed by this work.

Run the free gates with isolated test data, `MOCK_LLM=1`, `CLOUD_SYNC=0`, `STORAGE_BACKEND=local` and a separate `DEMO_STUDIO_GRAPH_DB`. `evals/qa_deck.py` includes `evals/provider_contract.py`, whose fake transport exercises provider dispatch and failures without sending requests. The acceptance and smoke gates and Python/JavaScript syntax checks remain required.

From the repository root:

```bash
(
  set -e
  gate_dir="$(mktemp -d /tmp/demo-studio-eval.XXXXXX)"
  export MOCK_LLM=1 CLOUD_SYNC=0 STORAGE_BACKEND=local SHARE_SECRET=mock-gate-secret
  for gate in qa_deck qa_accept smoke_mock; do
    DEMO_STUDIO_DATA="$gate_dir/$gate/demos" \
    DEMO_STUDIO_GRAPH_DB="$gate_dir/$gate/graph.sqlite" \
      .venv/bin/python "evals/$gate.py"
  done
  .venv/bin/python -m py_compile server/*.py server/agents/*.py server/llm/*.py evals/provider_contract.py
  for file in web/app.js web/slide.js web/player/player.js web/studio/*.js web/observability.js; do
    ~/.local/node/bin/node --check "$file"
  done
)
```

Runware's default build timeout is 120 seconds. Runtime passes `RUNTIME_TIMEOUT` (15 seconds by default); the optional repair gets only the remaining budget. HTTP timeouts bound individual network phases/inactivity, not a strict whole-call wall timer. Adding a third provider increases the possible total wait; the player may fall back to its approved route before a late personalization answer arrives. Player timing is unchanged.

No paid call, account balance, live schema compatibility, narration quality or real latency is proven by these free checks. The real demo and provider preflight remain separate approved-run work. Never deploy or merge this branch without Anand's instruction.

Verified 2026-09-18: deck 174/174 including 39 provider contracts, acceptance 24/24, both smoke phases, Python compilation, syntax checks for all 8 required JavaScript files, and all 8 Mermaid/HTML copies. Independent code review found no additional issues. Core checkpoint: `cdedb28`; the follow-up commit contains the extended contracts and verification record.
