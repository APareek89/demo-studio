# Conversational prompt refinement — 26 September 2026

Anand asked to use his Sarvam agent's instructions to refine Demo Studio and explain what affects naturalness. He considers Sumit as good as Shubh; this task preserves the selected voice and all acoustic settings. It edits instructions, not model weights.

## Inspected evidence

Read the user's Hyundai Showroom Assistant Instructions/Settings and its saved26September17:29 conversation through the signed-in Codex browser. No agent settings changed or new call started. Its prompt requests warm approachable speech, brief simple replies, natural numbers and one question at a time. Its transcript uses contextual Hindi/Hinglish conversational openings. Transfer the speaking principles, not its product claims, contact details or booking behavior. The committed version displayed pace1.15 after loading; the current draft showed1.0. Both used Shubh, starting Hindi and Quiet office ambience at slider30. These settings are not a controlled acoustic comparison or proof of the historical call's exact synthesis request.

The current local BMW uses Sumit/en-IN, explicit pace1.0 and mostly default TTS temperature, with one main/deeper line selecting expressiveness0.7. Tone/persona prose does not become a Sarvam acting instruction. Existing standalone and live Sarvam controls, audio identity and cache rules are untouched.

## Change and boundaries

- `AUTHOR_SYSTEM`: warm beside-the-visitor register; varied sentence lengths inside the existing batches; full stops/commas instead of semicolon/em-dash fact chains; reviewed observations instead of fake customer reactions.
- Runtime `SYSTEM`: answer first; simple connected thoughts; optional warmth in useful wording, not uncited empathy prefaces; preserve scope and supplied context. Existing composition repair inherits this system string.
- `QA_SYSTEM`: the same register for uploaded-document FAQ answers and legacy Q&A, within its existing60-word/citation/clarification policy.
- Added three actual-validator conversation cases: a brief supported acknowledgment plus fact remains an ordinary answer; spoken quantities retain scope; invented family/commute/agreement prefaces are rejected while the supported answer survives.

No changes to schemas, validators, graph ownership, agents, tools, source permissions, provider calls/order, voice settings, gallery, selected-duration rules, word budgets, human approvals, contact consent or app processes. Existing reviewed cache hits keep exact words and audio. Repeat-question simplification applies only when the model actually reasons, not when an approved answer is served from cache. Existing scripts/recordings require their normal reviewed regeneration to reflect new authoring.

## Verification

Before edits: deck445/445, acceptance24/24 and smoke3/3; all isolated, mock, cloud-off, blank provider keys and blocked sockets, with zero attempted outbound connections. After-edit results are recorded in Loop.MD and the raw logs below. Python AST comparison masks only the three named system constants and asserts the rest of each application module is identical to the previous checkpoint.

Final seventeen suites pass: deck445/445, acceptance24/24, smoke3/3; script prompt53/53, narrative roles14/14, speech style30/30, expression20/20; runtime conversation21/21, acts30/30, repair106/106, graph130/130; QA policy12/12, FAQ plain language21/21, FAQ cache27/27, FAQ scope19/19, runtime plain language25/25; full mock release28/28 with194.22seconds synthetic narration and zero provider calls. Counts overlap; they are not a sum of distinct acceptance scenarios. Changed Python compilation, existing player JavaScript syntax and whitespace pass. No JavaScript or Mermaid flow changes were necessary.

Raw logs and per-suite results: `output/human-guide-prompts-20260926-qa/`. The wrapper creates separate DATA/GRAPH storage for every process and forbids outbound sockets. Contract fixtures may replace the model boundary to exercise normal request/repair code; no real provider was used. Deliberately invalid media in acceptance emits expected ffmpeg diagnostics.

## Scoped failure review

Independent review found no blocking issue. Errors/external failures retain existing schema/fallback handling; races, resources and scale introduce no new state/queues; security keeps citations/domain/consent boundaries; data integrity preserves approvals/publications; observability requires honest mock-versus-acoustic claims; billing adds only a small amount of future prompt text, no new call; retries/cache remain unchanged; configuration preserves voice/pace; PRD edge cases retain conditions, duration and statement-only tours. This covers the twelve configured categories, not a new full architecture audit.

Main residual risk: an LLM can still write stiff or unsupported prose despite these instructions. Mock contracts do not establish improved generated language or audio. No new paid generation/listening test, master merge, GitHub push or AWS deployment is claimed.
