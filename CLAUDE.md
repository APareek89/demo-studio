# Demo Studio

Local app that turns a product's video/images/documents into a voice-led, interruptible demo via an
agentic pipeline with human checkpoints. Python FastAPI backend (`server/`), no-build ES-module
frontend (`web/`), folder-per-demo JSON store (`data/demos/<id>/`). Claude Opus 5 = plan / author /
align agent / grounded Q&A / rehearsal; Gemini = video & image understanding + TTS.

Run: `.venv/bin/uvicorn server.app:app --port 8877` → http://127.0.0.1:8877 · keys in `.env` ·
`MOCK_LLM=1` runs the whole path without keys. Docs: `PRD.md`, `docs/ARCHITECTURE_FLOW.md`,
`docs/architecture-flow.html`. Architecture rationale: see Handoff.MD → Decisions.

Conventions: every stage writes its own JSON and is a pure function of its inputs; the align agent
emits structured actions, the orchestrator executes them; the grounding validator runs at authoring
and at runtime — "no citation, no claim" is the product rule, never relax it.

## Power Coding (auto — do not remove without asking the user)
At session start read Handoff.MD; open with its pending points. Update Handoff.MD
after major changes and when ~10% of context remains (then tell the user to start a
fresh session with: "Refer to Handoff.MD in /Users/macbook/Documents/demo-studio and begin").
Log flow changes / user-reported bugs in Learning.MD (5-whys entry format).
Read Loop.MD every session and obey its `status:` machine — when the first working
draft is done, ASK the user whether to turn the loop on (disclosing the free/paid eval
split); while `status: on`, run the FREE Loop.MD evals after every meaningful change
and report per-eval pass/fail. The golden set / paid evals run ONLY per
consent.paid_evals (ask by default — offer at milestones, never auto per-change).
Keep docs/mermaid/*.mmd current when the flow changes (see docs/ARCHITECTURE_FLOW.md).
Obey .power-coding/config.json FMEA triggers: if on_pre_commit, run the light FMEA
scan on the staged diff BEFORE any commit you make (P0 → block and ask); if
on_feature_complete, full scan when a feature is declared done; if smart_suggest,
suggest a scan at a natural pause when its signals fire (never twice for the same
changes). The config's failure_categories list is the mandatory checklist.
If sentinel is enabled in .power-coding/config.json, run the four-lens Sentinel Scan
silently after every major task completion — flag only what fires, one line each.
If session_pulse is enabled, show a 2-line effort split (feature/support/rework) after
major milestones and log it in Handoff.MD updates.
Commit a git checkpoint at every working state and before any risky change (obey
consent.git_checkpoints: auto = commit + one-line announce, propose = ask first).
Before starting a feature, build the smallest version that proves it works (per PRD.md's
"Done for v1"), checkpoint, then extend. Any architecture-shaping change (new service,
external dependency, data-model change, async flow) gets a plain-language delta proposal
against the current diagram and user approval BEFORE code. Log
stack/architecture/behavior decisions as one line in Handoff.MD's Decisions; never
silently reverse a logged decision. PRD.md is the product context for evals and scans —
keep it current. Full FMEA scans obey consent.fmea_full_scan (ask | auto).
