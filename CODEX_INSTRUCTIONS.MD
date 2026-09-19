> Current scope (19 September 2026): the approved plan in `docs/plan-runtime-experience-2026-09-19.md` and current `PRD.md` supersede historical restrictions below on runtime streaming/barge-in, new extraction dependencies and paid Creta validation. Atelier/cinematic design remains. Keep review playback muted and use Codex's in-app browser; do not control Anand's Chrome.

# Codex — orientation, rules of work, and the first task

Written 2026-09-18 by the previous agent (Claude) when Anand moved day-to-day work to Codex. Everything here is
consistent with `Handoff.MD`, `PRD.md` and `docs/ARCHITECTURE_FLOW.md`; if this file and those ever disagree, those
win and you tell Anand.

## 0. Who you work with
Anand Pareek — product person, not an engineer. Plain language. Recommendations, not option surveys. He decides
anything that costs money, changes the architecture, or is visible to a customer. He will ask "is it working?" — answer
with what you verified, not what you expect.

## 1. Read these, in this order, before touching anything
1. `Handoff.MD` — the state of the build (phases 1–8 of "slides-v1"), the Decisions list, the open items, the provider
   situation. This is the single source of truth for "where are we".
2. `PRD.md` — what the product is and "Done for v1".
3. `docs/ARCHITECTURE_FLOW.md` + `docs/mermaid/00…07*.mmd` (rendered together in `docs/architecture-flow.html`) — the
   flow, stage by stage, with the functions and files that implement each box.
4. `Loop.MD` — the eval table (every behaviour that is proven, and the command that proves it) and its `status:` machine.
5. `Learning.MD` — every bug that was found, as a 5-whys entry. Read it to avoid re-introducing any of them.
6. `CLAUDE.md` — the previous agent's conventions; the same conventions apply to you.
7. Then the code, in this order: `server/app.py` (routes), `server/graph.py` (the LangGraph workflow, sqlite
   checkpoints, Align as the interrupt node), `server/orchestrator.py` (runs one stage, marks staleness),
   `server/store.py` (folder-per-demo JSON store), `server/storage.py` (local | AWS backends), `server/llm/*`
   (Claude, Gemini, Sarvam, the runtime provider order, the mock), `server/agents/*` (one file per stage), then
   `web/app.js` (hash router), `web/studio/*.js`, `web/player/player.js`, `web/slide.js`.

## 2. What the app is, in ten sentences
A local FastAPI app that turns a product's video, images and documents into a voice-led, interruptible sales demo.
Sources are read once by Gemini (video shots, image parts with bounding boxes, documents) into a fact registry — every
figure with its source, kind and truth-type. A planner and an author write a spoken script where every line that states
a figure cites fact ids; the validator drops anything uncited. The deck stage turns each script segment into one slide
with a picture (chosen by tagged parts vs the words), a ≤ 6-word title and ≤ 3 callouts of ≤ 8 words, each citing facts,
positioned on the part it names only when the part's box is trusted (else the side panel) — positions are never guessed.
A FAQ bank pre-answers likely questions; voice renders every line once (cache by content hash); the bundle joins it all.
A human approves the cards at Align (facts, script, deck slides, persona, CTAs) and can drag callouts, swap pictures and
edit text through the same validator. The player shows the deck: audio leads, the screen follows; a customer question is
answered from the bank or the registry and routed to the slide that carries the facts (stay / jump / none), then the
demo returns to the exact interrupted line; unknowns decline and offer a callback. Every session keeps the true
transcript (only the words actually heard), four latency stamps per turn, and a follow-up summary; Studio lists sessions
and gives a keyed read-only share link. `MOCK_LLM=1` runs all of it without keys; the free evals prove it.

## 3. Map of the code
```
server/app.py            routes (see the list at the bottom of this file) · middleware (no-cache for the front end)
server/graph.py          LangGraph: router → understand → plan → author → deck → faq → (align_enter/align_wait) → voice → rehearsal → bundle
server/orchestrator.py   runs one stage, stage status/seconds/cost, DOWNSTREAM staleness map
server/store.py          data/demos/<id>/ folder store: demo.json, sources, derived, understanding.json, plan.json, script.json, deck.json, faq.json, bundle.json, sessions/, leads/, logs/, RUN.md
server/storage.py        Local (default) | Aws(Local): DynamoDB rows for sessions/leads, S3 mirror via cloud.py, pre-signed media
server/cloud.py          S3 mirror + DynamoDB demo/event records (CLOUD_SYNC)
server/llm/claude.py     claude.structured — constrained JSON, built-in Gemini fallback when Claude is unavailable
server/llm/gemini.py     vision + text_structured + TTS; retry/backoff; quota cooldown sized from Gemini's retry hint
server/llm/runtime.py    RUNTIME_PROVIDERS order (gemini, claude) with RUNTIME_TIMEOUT for the customer-facing calls
server/llm/sarvam.py     STT (saarika) + TTS (bulbul) · server/llm/mock.py fake outputs for MOCK_LLM=1
server/agents/understand.py  sources → registry, shots, images with parts+boxes, competitors (URL sources with role=competitor)
server/agents/plan.py / author.py  outcome plan → spoken script; author.ungrounded() is THE validator (NUMBERISH / CLAIMISH)
server/agents/deck.py    one slide per segment; choose_image, place_callouts, clean_callouts, apply_overrides, route_for/slide_for (question routing)
server/agents/faq.py     FAQ bank (reuse by registry hash; every entry carries slide_id) · voice.py (audio cache) · bundle.py (assemble)
server/agents/qa.py      runtime Q&A (model proposes, validator disposes) · pitch.py (runtime personalisation, route by slide) · summary.py (session summary)
server/agents/align.py   the Align agent: structured actions the orchestrator executes · translate.py (extra languages, numbers preserved)
web/app.js               hash router: #/demos · #/studio/<id>/sources|align|rehearse|sessions · #/play/<id> · #/observability/<id> · #/share/<demo>/<sid>/<key>
web/studio/sources.js align.js rehearse.js sessions.js   the Studio pages · web/slide.js  the slide renderer shared by Align and the player
web/player/player.js     the runtime player (state S, showSlideView, playLines, handleQuestion, logHeard, sessionRecord)
web/observability.js     traces, cost, answer latency p50/p95 · web/styles.css  all styles (no build step)
evals/qa_deck.py smoke_mock.py qa_accept.py   the free gates · docs/aws/*  deployment + IAM policies
```

## 4. Non-negotiables (from Handoff.MD Decisions — do not re-decide them)
- No citation, no claim. Single runtime voice. Event-driven player. Human checkpoint at Align. Folder-per-demo JSON.
  Content-hash audio cache. MOCK_LLM=1 for every free eval. No front-end build step.
- Runtime provider order is Gemini first, Claude fallback (Anand has no Claude credits). Every provider down → the guide
  declines and offers a callback; there is no hard-coded product fallback and no cooldown that hides the failure.
- Positions on a picture are never guessed: no trusted part box → callout in the side panel. Align edits
  (`deck-overrides.json`) win over anything computed and survive rebuilds.
- Question routing is plain code on fact ids and topics (no model call); a jump never touches the return point.
- The transcript is what the customer heard; only it goes to `/run/qa`.
- Out of scope for this build, do not start: voice barge-in, streaming STT/LLM/TTS, session resume after refresh,
  publish/embed.

## 5. Run, gates, verify
```bash
# real keys (.env) — the app; Studio at http://127.0.0.1:8877
.venv/bin/uvicorn server.app:app --port 8877 --host 127.0.0.1
# mock, on a throwaway data folder — never touches the real demos
MOCK_LLM=1 DEMO_STUDIO_DATA=data/test-demos CLOUD_SYNC=0 .venv/bin/uvicorn server.app:app --port 8879
# the free gates (all must pass before AND after your change)
MOCK_LLM=1 .venv/bin/python evals/qa_deck.py     # 135/135 today — the slides-v1 contract, end to end
MOCK_LLM=1 .venv/bin/python evals/qa_accept.py   # 24/24
MOCK_LLM=1 .venv/bin/python evals/smoke_mock.py  # SMOKE OK
.venv/bin/python -m py_compile server/*.py server/agents/*.py server/llm/*.py
~/.local/node/bin/node --check web/app.js web/slide.js web/player/player.js web/studio/*.js web/observability.js
```
Node lives in `~/.local/node/bin` (the Mac's CLT is broken; do not try to install toolchains). Verify UI changes in a
real browser against the mock server; the previous agent's notes on scripted browser checks are in `Learning.MD`
(hidden tabs throttle timers; a page reload used to keep stale modules — now `Cache-Control: no-cache`).

## 6. How to work (the protocol)
1. Understand: read the files above; find the eval row in `Loop.MD` and the diagram box that cover what you will touch.
2. Propose: ≤ 10 lines in chat — what you will change, which files, which eval proves it, what it costs. If it is
   architecture-shaping (new service, dependency, data-model change, async flow, provider order) add a plain-language delta
   against the current diagram. Wait for Anand's OK.
3. Build the smallest version that proves it, on `codex/<task>` off `slides-v1`. Gates green. Commit.
4. Extend to the full ask. Gates green. Docs in the same commit (Handoff Decisions · Loop.MD row · mermaid + the
   `architecture-flow.html` copy (each `.mmd` is embedded, HTML-escaped, in its own `<pre class="mermaid">` block) ·
   Learning.MD for bugs). Commit.
5. Report: what changed · how to test it · what is still weak. Then stop and wait.
Never batch unrelated changes into one task. Never "fix while you are there" without asking.

## 7. State on 2026-09-18 evening (details in Handoff.MD)
- Branch `slides-v1` (off `master` 794b8e5, which is untouched): phases 1–8 done and committed; the AWS side of
  phase 7 waits on Anand (create the instance role from `docs/aws/instance-role-policy.json`; say "go on the table").
- The EC2 box (https://13-202-0-79.sslip.io, `i-0410e37b7ab0297e1`, ap-south-1) still runs `master` — the old player.
  Deploy `slides-v1` only when Anand says so (`docs/aws/deploy-ec2.sh`).
- Providers are starved: the Anthropic key has no credits; the Gemini key is free-tier (20 requests/min). Real builds
  degrade by design (derived callouts, FAQ generation errors). Anand must enable Gemini billing (or top up Anthropic)
  before any real demo build. Do not "work around" this by adding retries or cheaper prompts.
- Demos built before the deck stage play as one plain slide per segment until each gets `POST /revise {stage: deck,
  rebuild: true}` (one Gemini call). Their pictures have no part boxes until Sources are re-read, so callouts sit in
  the side panel.

---

## 8. TASK 1 — paste this into Codex as the first prompt

You are working in /Users/macbook/Documents/demo-studio on branch `slides-v1`. Read `AGENTS.md`, then
`CODEX_INSTRUCTIONS.MD` §1–§7, then `Handoff.MD`. Confirm in five lines that you understand: the product rule
"no citation, no claim", the provider situation, the Align checkpoint, the event-driven player, and the gates.
Do not change anything until Anand answers your first alignment question. Then do these three parts, each on its own
branch off `slides-v1` (`codex/runware-fallback`, `codex/real-demo-<car>`, `codex/hardening`), each with the free
gates green, docs in the same commit, and a report (what changed · how to test · what is still weak).

### Part 1 — Runware as the third model fallback, with a cost tier
Context: `RUNWARE_API_KEY` is already in `.env` (it powered the removed 3D path). Today the build-time chain is Claude →
Gemini (`server/llm/claude.py` falls back to `gemini.text_structured` when Claude is unavailable) and the runtime order is
`RUNTIME_PROVIDERS=gemini,claude` (`server/llm/runtime.py`). Anand wants Runware (https://runware.ai) as the last fallback
for text-model calls, using cheap-but-decent models by default and top models only when a real customer demo is built.
Steps:
1. Verify first, from Runware's current documentation, exactly which text / LLM (chat-completion or JSON-output) models
   they serve, with prices. If Runware does not serve text models at all, STOP after this step and report to Anand what
   they do serve (image / video tasks) with one recommendation — do not build a fallback that cannot answer a question.
2. Propose (≤ 10 lines, wait for OK): the file `server/llm/runware.py` exposing `structured(system, content, schema, *,
   history=None, max_tokens=1500, timeout=None, model=None)` with the same contract as `gemini.text_structured` — JSON mode,
   pydantic validation, one retry on invalid JSON, `usage.trace(kind="runware-structured", model=…)` on success AND on
   failure, cost recorded through `usage.PRICES`; config `RUNWARE_TEXT_MODEL` (cheap default) and `RUNWARE_TEXT_MODEL_PREMIUM`;
   a `MODEL_TIER=eval|customer` switch in `server/config.py` that selects cheap vs top models for Claude, Gemini and Runware
   (propose the exact model names and prices for both tiers; Anand decides); `runware` appended to `RUNTIME_PROVIDERS`
   default and to the Claude fallback chain (Gemini first, then Runware); `health()` reports runware and the tier.
3. Implement. Mock mode never calls Runware. Evals in `evals/qa_deck.py`: provider order includes runware; tier selection
   maps to the expected models; with every provider down the runtime still declines with a callback (unchanged); a
   fake Runware response that states a figure without a fact id is dropped by the validator (author.ungrounded).
4. Docs: `Handoff.MD` Decisions line ("Runware is the third text fallback; MODEL_TIER=eval by default"), `Loop.MD` row,
   mermaid 01 (providers) + 05 (runtime) + the HTML copies, `docs/ARCHITECTURE_FLOW.md` provider row, `.env.example` if one
   exists. Never print the key.

### Part 2 — build one real demo the way a customer would, and log every flow issue
Context: Anand still sees issues in the flow and wants a proper demo to look at. A real build needs a paid Gemini tier
(free tier = 20 requests/min); ask Anand to confirm billing is on before the real run, and do the whole flow on the mock
server first (free) to catch mechanics issues.
Steps:
1. Propose the car and two competitors (suggestion: Tata Nexon vs Maruti Brezza and Hyundai Venue — mainstream, rich
   official sites) and wait for OK.
2. Gather what a real user would have, from OFFICIAL sources only, and keep every URL: the model page, the specifications
   page, the price/variants page, the brochure PDF if public, 6–8 official product images (front, side, rear, interior,
   dashboard, boot, one or two close-ups — a mix, so the deck has pictures per topic), one official product video file if
   one is downloadable without login (otherwise skip video). Respect robots.txt and terms; no review sites as fact sources
   (the registry may only contain the maker's own statements); competitor pages go in as URL sources with
   `role=competitor` and `settings.competition=on`.
3. Build it through the product, not around it: `POST /api/demos {name}` → `POST /api/demos/{id}/sources` (files, URLs,
   text; roles product | hero | intro_video | competitor | brand) → `PATCH /api/demos/{id}` for settings (language,
   audience, competition) → `POST /read` → Align in Studio (review facts, script, deck slides; drag one callout, swap one
   picture, edit one text through the validator; approve every card) → `POST /build` → play at `#/play/<id>` as a customer:
   intake, opening film, decision frame, at least eight questions covering same-slide, off-slide (jump and return),
   unknown (decline + callback form with consent), competitor comparison (must carry the verify caveat), price/EMI (must
   decline unless in the registry), a clarifying-question case, and an interruption mid-line → Done → Studio › Sessions
   (summary, share link) → Observability (latency panel).
4. Log every issue as you go in `docs/issues/<date>-<car>.md`: id · where (stage / page / route) · steps · expected ·
   actual · severity (blocks the demo / wrong for the customer / cosmetic) · suspected cause · status. Do not fix anything
   during the run; finish the run, then present the list with one recommendation per issue and wait for Anand.
5. Fix only what Anand picks, each with an eval that would have caught it and a `Learning.MD` 5-whys entry; keep the
   demo folder (do not delete it) — Anand wants to look at it.

### Part 3 — hardening the previous agent recommends (do in this order, each after an OK)
P1. Provider pre-flight before a real build: a one-token probe per provider (Claude, Gemini, Runware, Sarvam) shown in
    Studio › Sources before "Read" and on the Build button — which providers answer, which will fall back, and a refusal
    to start a `MODEL_TIER=customer` build while a provider is starved unless Anand overrides. Today a starved account
    degrades silently (the deck's callouts fell back three times before anyone saw why).
P1. Persist stage warnings and failed calls: a stage's `emit()` warnings (e.g. "Callout writer unavailable (…)") only
    reach the live event stream; write them into the demo's `logs/<ts>-<stage>.json` and `RUN.md`, and make
    `gemini.text_structured` / `claude.structured` trace a failed call with its error (today a failed fallback is invisible).
P2. Rehearsal reuse by script hash, like the FAQ bank: a Build after an Align edit re-runs the paid rehearsal stage even
    when the script is unchanged (`server/agents/rehearsal.py` has no reuse); the graph already skips it on `revise`.
P2. "Re-tag pictures" action: an image-only re-read (Gemini image pass with boxes) for demos built before part boxes
    existed, instead of a full Sources re-read; then a deck rebuild puts callouts on the picture.
P3. Phase 7 AWS side once Anand has done his two steps: create the table with `storage.Aws().ensure_table()`, set
    `STORAGE_BACKEND=aws` + `CLOUD_SYNC=1` on the box, verify `/api/demos/{id}/sessions` → `storage.backend == "aws"`;
    deploy `slides-v1` to EC2 only on Anand's word.
P3. Remove the hand-written `?v=3e0` on the align.js import (the server now sends `Cache-Control: no-cache`).
P3. Observability: latency percentiles across all demos, not only per demo.
Explicitly NOT to do (out of scope for this build): voice barge-in, streaming STT/LLM/TTS, session resume, publish/embed.

## 9. Route list (server/app.py) — the product's API, for Part 2
GET / · GET /media/{demo}/{path} · GET /api/health · GET/POST /api/cloud(/setup) · GET/POST /api/demos ·
GET/PATCH/DELETE /api/demos/{id} · POST /duplicate · POST /sources · PATCH/DELETE /sources/{sid} · GET /faq-template ·
POST /read · GET /events (SSE) · POST /align (chat) · POST /approve/{card} · POST /unapprove/{card} ·
PATCH /align/facts/{fid} · POST /align/facts/{fid}/approval · PATCH /align/product · PATCH /align/script ·
PATCH /align/deck · PATCH /align/plan · POST /ctas · POST /build · POST /revise {stage, instruction, rebuild} ·
POST /voice/sample · GET /bundle · POST /run/qa {question, history, profile, slide_id} · POST /run/pitch ·
POST /run/lead {phone, question, profile, consent, consent_text, session_id} · POST /run/stt · POST /run/tts ·
POST /run/session · GET /sessions · GET /sessions/{sid} · GET /api/share/{demo}/{sid}?k= · POST /feedback ·
GET /usage · GET /runlog · GET /trace (with latency) · GET/POST /evals · GET /api/workflow · GET /api/voices

---

## 10. TASK 2 — Experience pass, wave 2 (reconciled with Codex's Nexon work, 2026-09-18 late)

Read first: `docs/issues/2026-09-18-nexon.md` (NX01–NX16), `docs/qa/nexon-real-run-plan.md`, and the current checkpoint
at the top of `Handoff.MD`. Do NOT redo what those already fixed. Two facts from Claude's last session:
- The FAQ bank could store a provider outage as a decline (the TVS iQube bank was overwritten with 20 declines by a
  starved rebuild). Fixed: `qa.answer` returns `provider_failed`; `faq.run` keeps the previous answer (same registry)
  or marks the entry `error` for a retry and the bank `partial`; `faq.match` skips unbuilt entries. Cases in
  `qa_deck.py`; your `faq_review_contract` still passes 41/41. Its `Learning.MD` entry ("A provider outage was written
  into the FAQ bank as knowledge") sits uncommitted in the working tree next to your own — include it in your next commit.
- Run the TVS iQube FAQ stage once (`POST /api/demos/dm_d5675e7f/revise {"stage": "faq", "rebuild": true}`) so its 20
  outage declines are replaced by real answers (≈ 20 small Gemini calls).

### Order
1. **Finish the real Nexon iteration 2 exactly per the run plan** — twelve paths, three buyers, ten standards, the
   required evidence — and report. Anand listens to that before anything below.
2. Then the residual conversation rules R1–R7 (from Anand's own TVS run; none are in NX01–NX16).
3. Then the script register audit (B) and the Gemini-first build chain (D).
4. Slides (C) only on Anand's word after he has seen the real cinematic Nexon build.
Branch `codex/experience-wave-2` off `codex/real-demo-nexon`; one commit per numbered item; gates green each time:
deck, accept, both smoke phases, and every contract (`faq_review`, `generation`, `align_review`, `voice_lock`,
`customer`, `provider`), Python compile, all JS modules, diagram copies. Ask before any paid run.

### R — residual conversation rules (web/player/player.js, web/player/intake.js (new, pure), fillers in voice.py)
R1 Name guard. `parseName` accepts a name only after an explicit cue ("my name is", "I'm <Capitalised>", "this is") and
   never a dictionary word (stop-list: looking, thinking, interested, just, here, fine, good, not, sure, okay…). No name
   → the guide uses none. The TVS run greeted the customer as "Looking". Move `parseName`/`parseFocus` to
   `web/player/intake.js` and test them with `node evals/js/intake.test.mjs` (add to the gates).
R2 Honest personalisation. The "one moment — I'm tailoring this" filler is spoken only while the pitch plan is still
   pending at the end of the opening; if the plan fails or times out the guide claims nothing and continues with
   "Let me take you through it — stop me any time." Plan wait window 6 s (paid tier answers in 2–4 s); pitch latency
   shown in Observability. The TVS run promised tailoring and delivered the standard script.
R3 Announce a jump. Before a cross-fade to another slide, a recorded bridge "That's on the <slide title> slide — one
   moment." (per-slide audio rendered at build, generic filler fallback, same voice); keep the existing return line.
R4 Resume forward. After an interruption, if ≥ 40 % of the cut line was heard, continue from the next line after a
   recorded "Let's carry on."; otherwise replay the line. Pure `resumePoint(fraction)` in `web/player/flow.js`,
   node-tested. Anand heard the same sentence twice and read it as "it went back to some slide".
R5 Pace. 350 ms of silence between lines and 700 ms between slides — a fixed gap after `ended`, still event-driven.
R6 Warm decline. "That isn't in the material I've been given, so I won't guess. I can have someone from the
   dealership answer it — or we carry on." Two recorded variants; the callback form as today.
R7 Check-in kinds. The author returns `checkin_kind: confirm | number | choice` (≤ 14 words, one topic, no "and");
   chips follow the kind (Yes that's right / No / Question · a number hint · the two choices).

### B — script register audit (server/agents/principles.py, author.py; Align Script card)
Rules as P-rules quoted in the author prompt: sentences ≤ 18 words; one figure per sentence; a term explained once in
plain words then used plainly; the kind-of-truth caveat once per topic as a short aside, never every sentence; no
marketing adjectives; refer to the customer's own words only in custom batches; the opening never assumes the
customer's numbers. `author.audit(script)` → `script.issues` (line id + rule) shown on the Script card; auto-fixed:
a question in narration → the segment's check-in, a greeting outside the intake → dropped. Evals: audit cases on a
crafted script. This complements NX09/NX14/NX16, which fixed meaning; this fixes register.

### D — build chain Gemini-first (server/llm, config)
Today build text tries Claude → Gemini → Runware, and Anthropic has no credits: every build call burns a failed Claude
request first and pollutes traces. Make the build order configurable and default to `gemini,claude,runware` (Claude
only when Gemini fails); keep the `MODEL_TIER` mapping and all fallback contracts; `health()` lists `build_providers`.
Evals: order, fallback, mock never opens a provider. Anand's paid-tier limits (28-day console): 3.6 Flash 2K RPM /
3M TPM / 100K RPD · 3.1 Pro 1K RPM · 3.1 Flash-Lite 10K RPM · Flash TTS 1K RPM — ample; keep `_retry` and the
proportional cooldown as they are.

### C — slides, only if Anand says the cinematic look is not there
C1 Mockup before code: `docs/design/slides-mockup.html` — five slide kinds at 16:9 and phone width (hero · proof with
   parts · proof without boxes as a fact strip · money as stat tiles · closing as a 3-point summary + CTAs); Anand
   approves; only then C2: one layout template per `slide.kind` in `web/slide.js`, callouts as pills with the VALUE
   large and the LABEL small (deck schema gains `value` + `label`, ≤ 8 words together; the derived fallback builds them
   from `fact.value` / `fact.claim`), 300 ms rise on their line, fact ids behind a small ⓘ toggle.

### Not to do
No countdown anywhere; no mixed TTS providers within a demo; no questions in narration; never relax the validator; no
new dependency; no barge-in / streaming / session resume / publish (out of scope). Report per item: what changed ·
how to test it · what is still weak — plus a Loop.MD row per behaviour.
