# Loop.MD — Demo Studio
status: waiting_for_first_draft

> AGENT INSTRUCTION — read every session and obey:
> - While `status: waiting_for_first_draft`: the moment the first working draft exists
>   (core path runs end-to-end once — demo-able, not just compiling), ASK the user:
>   "First draft is working. Want me to turn on the Loop? After each change I'll run
>   the FREE evals below (they cost nothing) and show per-eval pass/fail. The golden
>   set costs real API money — I'll only run it when you approve or at milestones."
>   Set `status: offered` when asked; `on` or `off` per the answer. Re-ask an
>   unanswered `offered` once at next session start.
> - While `status: on`: after each meaningful change run cheapest checks first
>   (`.venv/bin/python -m py_compile server/*.py server/*/*.py`), then execute every FREE
>   eval below for real (run the app with MOCK_LLM=1 — never predict from code), report a
>   per-eval ✅/❌ table including regressions, fix, repeat.
> - GOLDEN SET (paid/graded evals): NEVER runs automatically per-change. Obey
>   `consent.paid_evals` in .power-coding/config.json — `ask` (default): offer it at
>   milestones ("feature complete — run the golden set? ~<N> paid calls") and on
>   request; `auto` only if the user explicitly set it. Before ANY paid run: one-line
>   hypothesis in the run journal; reproduce failures as free checks; one paid
>   confirmation per hypothesis.
> - GRADUATION: when an eval has passed 3 consecutive runs, offer to codify it as an
>   automated test (create the minimal pytest setup if none exists). Mark it
>   `(graduated → <test file>)` below — it then runs with the cheap checks, not the
>   manual walkthrough.

## Goal
<USER: confirm or rewrite> Build a demo for any product from images/video/documents, with a
human approving visuals, facts, persona and CTAs before it's built — and a guide that never states
an uncited fact. Done = the iQube sample runs end-to-end locally with real keys and the feedback loop
rebuilds the demo.

## Free evals — run after every change while the loop is on
(Run with `MOCK_LLM=1` unless the eval says otherwise. Free = no API spend.)

| # | Input (question / action / call) | Expected (answer / behavior / output) |
|---|----------------------------------|----------------------------------------|
| 1 | (EXAMPLE — replace me) `POST /api/demos {name:"Test"}` then `POST …/sources` with `samples/iqube/*.webp` + url | 201-style JSON; 6 sources listed; `GET /api/demos` shows the demo with status `sources` |
| 2 | (EXAMPLE — replace me) `POST …/read` with MOCK_LLM=1, then SSE `…/events` | status goes `reading` → `align`; `understanding.json` and `plan.json` written; an agent opening message appears in the conversation |
| 3 | (EXAMPLE — replace me) Approve all 4 cards via `…/approve/{card}`, then `POST …/build` | status `building` → `ready`; `script.json`, `bundle.json` exist; every bundled line has `fact_ids` ⊆ registry or is a transition line |
| 4 | (EXAMPLE — replace me) `POST …/run/qa {question:"what is the kerb weight?"}` on a registry that lacks it | `answered:false`, `fact_ids:[]`, answer contains "don't want to guess"; question appended to `understanding.unknowns` with origin `runtime` |
| 5 | (EXAMPLE — replace me) Author validator: a script line "It does 145 km on a charge" with `fact_ids:[]` | line flagged unverified and excluded from voice + bundle; issue listed on the Facts card |
| 6 | (EXAMPLE — negative) Player with mic denied (`micDenied`) or no SpeechRecognition | intake shows the typed fallback within 10 s; check-ins still offer tap chips; demo completes to the handoff |
| 7 | (EXAMPLE — replace me) `POST …/feedback {message:"say the warranty before the price"}` in Rehearse | align agent returns a `revise('author', …)` action; status `building` → `ready`; bundle version increments |

## Golden set — paid/graded evals (real keys; runs ONLY with approval)
| # | Input | Reference output / must-haves | Check (exact / contains / rubric) |
|---|-------|-------------------------------|-----------------------------------|
| G1 | (EXAMPLE — replace me) iQube images + TVS URL → Read | registry contains battery warranty "3 years / 50,000 km" and ex-showroom prices with citations to the URL source | contains |
| G2 | (EXAMPLE — replace me) Same → Plan | first two segments after welcome address range and charging; a visual gap notes "no shot of the charging port" or similar | rubric: segments match the category's top buyer concerns |
| G3 | (EXAMPLE — replace me) Q&A "does it have an engine?" | explains it is battery-electric with a hub motor, cites a spec fact, `answered:true` | contains: "no engine" or "electric"; fact_ids non-empty |
| G4 | (EXAMPLE — must-refuse) Q&A "can you give me a better price?" | no discount promised; escalates to a person; no invented number | rubric: no new numeric price/discount in the answer |
| G5 | (EXAMPLE — must-refuse) Q&A "is Ather better?" | declines to compare other brands; suggests what to compare on | contains: refusal to compare |
| G6 | (EXAMPLE — replace me) Align message "F003 is wrong — the value is ₹1,08,993" | `edit_fact` action on F003; Facts card shows the row as edited; author stage marked stale | contains: action type edit_fact |
| G7 | (EXAMPLE — replace me) Align message with an attached PDF spec sheet | `revise('understand', …)` action; registry grows; approvals for visuals/facts reset | rubric |
| G8 | (EXAMPLE — hard) Product with NO documents (images only) | registry empty; unknowns ≥ 8; plan still produces segments whose goals say the sources are silent; every scripted line passes the validator | rubric |
| G9 | (EXAMPLE — replace me) Rehearsal on the iQube demo | coverage ≥ 0.6; gaps include at least one genuinely unstated item (weight/delivery) | rubric |
| G10 | (EXAMPLE — replace me) Voice: persona sample renders with Gemini TTS | a WAV under `data/demos/<id>/audio/`, playable on the Persona card | exact: file exists |

## Run journal (paid/slow checks only)
| Date | Hypothesis (changed X, expect eval N to flip because W) | Result | Cost note |
|------|----------------------------------------------------------|--------|-----------|
