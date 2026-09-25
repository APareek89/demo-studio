# Demo Studio — standing instructions for Codex

You are implementing, not designing. The product rules, the architecture and the decisions are fixed and written down;
your job is to make specific, agreed changes that fit them exactly. Start every session by reading
`CODEX_INSTRUCTIONS.MD` (what to read, what never changes, how to work, the current task) and then `Handoff.MD`
(state, decisions, open items). Anand is a product person: talk in plain language, give one recommendation rather than a
menu of options, never make him read code to understand a change.

Hard rules — no exceptions:
- Work on the existing implementation branch; use the current tested release for newly requested branch work.
  Merge into the repository default `master` only when Anand explicitly instructs it. He authorized the completed
  approved middle-only gallery integration and preceding `eacbb57` noise fix on 25 September 2026; this does not authorize an AWS deployment. Commit working states
  with plain-language messages. The former `slides-v1` starting point is historical.
- No change to the architecture, the data model, services, dependencies, provider order, the product rules inside
  prompts, or the no-build front end (plain ES modules + CSS, no bundler) without Anand's written OK. When in doubt, ask
  first — one short paragraph, one recommendation. A "quick improvement" you were not asked for is a question, not a commit.
- Product rules that are never relaxed: "no citation, no claim" (the NUMBERISH / CLAIMISH validator at authoring and at
  runtime; an unknown answer declines and offers a callback, it never guesses); one voice at runtime (recorded audio keyed
  by content hash, never the browser voice mixed in); the player is event-driven (audio leads, the screen follows, no
  timers decide what is on screen); the human checkpoint at Align stays; every stage writes its own JSON and is a pure
  function of its inputs; `MOCK_LLM=1` must run the whole path without keys.
- Every change ships with: the free gates green before and after (`CODEX_INSTRUCTIONS.MD` § Gates), `py_compile` and
  `node --check`, the docs in the same commit (a `Handoff.MD` Decisions line for any decision, a `Loop.MD` eval row for any
  new behaviour, the `docs/mermaid/*.mmd` diagram and its embedded copy in `docs/architecture-flow.html` when the flow
  changes, a `Learning.MD` 5-whys entry for any bug you fix), and an eval that would have caught the bug.
- Paid model calls (anything without `MOCK_LLM=1`) only with Anand's OK for that run; report what it cost. Never print,
  log or commit a key; `.env` stays local.
- Report after each task in three parts: what changed · how to test it · what is still weak.
