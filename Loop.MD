# Loop.MD — Demo Studio
status: off
> USER DECISION 2026-09-03: keep running FMEA per .power-coding/config.json; do NOT turn the Loop on in this project. Free evals may still be run on request; never automatically.

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
| 8 | (EXAMPLE — replace me) `POST …/run/pitch {profile:{why:"25 km commute, replace my Activa"}}` | `route` non-empty, every `segment_id` exists in the script, establish segment last, a bridge with a figure but no fact id is dropped (`bridge_dropped` set) |
| 9 | (EXAMPLE — replace me) `POST …/run/lead {phone:"my number is 98765 43210", question:"kerb weight"}` and `{phone:"12345"}` | first → 200 with `phone:"9876543210"` and a file under `data/demos/<id>/leads/`; second → 400 |
| 10 | (EXAMPLE — replace me) `POST …/run/stt` with a 0.1 s WAV, `GET /api/voices?demo_id=` | 200 with a transcript (mock: "(mock transcript)"); voices lists Sarvam speakers when `SARVAM_API_KEY` is set, Gemini voices otherwise, and `chain` shows the fallback order |
| 11 | (EXAMPLE — negative) Player with an empty route (no proof blocks) | standard opening plays, then the closing + CTAs — no crash, no infinite loop |
| 12 | (EXAMPLE — replace me) Upload an `.avif` and a `.heic` image | accepted as `image`; `derived/*.jpg` created for the models; original served at `/media/…` |
| 13 | (EXAMPLE — replace me) `PATCH …/sources/{id} {use_in_demo:false}` then build | that source's visuals never appear in `bundle.json`; the registry still contains facts learned from it |
| 14 | (EXAMPLE — replace me) `GET …/faq-template` | Markdown grouped by category with suggested documents; `POST …/evals {questions:[…]}` returns per-question ✓/✗ and is listed by `GET …/evals` |
| 15 | (EXAMPLE — replace me) `GET …/usage` after one `/run/qa` | one `runtime` row with input/output tokens and a non-zero USD estimate |
| 16 | UI click-through (mock server, pane at 800×450): open `#/studio/<id>/align`, click **Approve** in the head of the 2nd card, click a thumbnail, click **Approve all** | Approve/Un-approve visible in *every* card head without scrolling tricks; the cards column scrolls; lightbox opens and closes on click; all five approved; no console errors |
| 17 | `MOCK_LLM=1 .venv/bin/python evals/qa_accept.py` (acceptance / failure QA) | 24/24: supported formats accepted (webp/png/jpg/avif/heic/mp4/mov/pdf/txt/docx), unsupported rejected 400 with the extension named, empty file 400, over-limit 413, corrupted media accepted and the READ stage still reaches `align`; path-traversal name stays inside the demo folder |
| 18 | `PATCH …/ {settings:{languages:["en-IN","hi-IN"]}}` then build (mock) | `bundle.languages == [en-IN, hi-IN]`, `alt_languages.hi-IN` has the same segment count with its own audio; `/run/tts {language:"hi-IN"}` returns a URL; the player shows a language chooser before Start |
| 19 | `GET …/trace` after a mock build; open the Observability tab | stages carry `seconds`; rows exist (mock Claude calls are traced); clicking a row reveals system prompt / input / response |
| 20 | `author.validate` on a script whose intro says "3.4 kWh … 15A … IDC" with audience=everyday | issue list names the jargon term and asks for plain language; route > 480 words is reported as over budget |
| 21 | Monkeypatch `sarvam.tts` to raise `RuntimeError("sarvam tts 402: No credits")`, call `voice.render_line` twice (mock off, gemini key present) | first call falls through to Gemini and trips sarvam; second call skips sarvam without calling it; `GET /api/voices` lists `unavailable.sarvam`; the voice stage log says "sarvam is unavailable … top up, then rebuild" |
| 22 | `translate._keeps_numbers("145 km certified, Rs 1,24,990", "१४५ किमी प्रमाणित, ₹1,24,990")` is True; with "१४० किमी" it is False; a mock build with languages en-IN + hi-IN reports 0 "kept in the main language" | translated lines keep every source figure; a changed figure keeps the English line and is counted in `logs/translate` |
| 23 | Run `visuals.align` on the Creta script (`dm_201201c4`) in mock mode (rules only) | every line whose text mentions gear / DCT / paddle ends up on a gear or paddle image; every uploaded image with a distinctive part is used at least once; `logs/*-visuals.json` has a reason per change |
| 24 | Mock read → Align: `GET /api/demos/{id}` cards | `cards.script.segments` present with `timeline.total_seconds > 0` and every batch ≤ 20.5 s; `cards.faq.total ≥ 1`; six approvals keys (visuals, facts, script, faq, persona, ctas) |
| 25 | Mock build → bundle | `bundle.fillers` has audio for every filler key; every `bundle.faq` entry with an answer has audio; `bundle.timeline.exact` is true after voicing |
| 26 | Player (pane): start with a spoken context, then ask a bank question, then a new question | recorded acknowledgement plays before the opening; custom batches play with their pictures after the opening; bank question answers with no model call (note "answered from the FAQ bank"); new question is preceded by the recorded "bear with me"; the voice never changes; no silent gap longer than 2 s |

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
| G10 | (EXAMPLE — replace me) Voice: persona sample renders with Sarvam Bulbul (falls back to Gemini) | a WAV under `data/demos/<id>/audio/`, playable on the Persona card; `voice_provider` in script.json says which provider produced it | exact: file exists |
| G11 | (EXAMPLE — replace me) Pitch plan for "I need at least 100 km range" | `customer_state: stated_want`; follow-up asks whether it's one long day or charging less often (P03); route leads with the range proof block | rubric |
| G12 | (EXAMPLE — replace me) Pitch plan for "45 km commute, want it cheaper than petrol without range worry" | `customer_state: stated_need`; decision frame recaps 45 km + cost + range in the buyer's words; bridges cite fact ids | rubric |
| G13 | (EXAMPLE — replace me) Script scorecard on the iQube demo | total ≥ 14 on first build; `weakest` names concrete rewrites | rubric |
| G14 | (EXAMPLE — replace me) Demo language = Hinglish | intake q1 and proof lines in Devanagari-mixed Hinglish, product names/units unchanged; Sarvam TTS renders `hi-IN` | rubric |

## Run journal (paid/slow checks only)
| Date | Hypothesis (changed X, expect eval N to flip because W) | Result | Cost note |
|------|----------------------------------------------------------|--------|-----------|
| 2026-09-03 | First real run of the iQube sample (part of "build the whole thing", not a per-change eval): expect G1 (registry has warranty + prices with citations) and G10 (Sarvam sample) to pass; G9 coverage ≥ 0.6 uncertain with images-only visuals | G1 ✅ 71 facts, warranty F027/F028, prices per variant · G10 ✅ Sarvam sample + 68 lines · G9 ❌ coverage 0.50 (gaps are genuine source gaps: on-road by city, replacement battery cost, boot litres, service cost; plus 1 must-refuse) · scorecard 17/20 | ~1 read (Claude ×1 big + Gemini ×1) + build (Claude author ×2, rehearsal ×13, scorecard ×1; Sarvam ×68) |
| 2026-09-03 | Paid QA run 1 — images + spec text, English + Hindi (`evals/qa_real.py images --lang hi-IN` → `dm_f79d9170`): expect opening ≤ 115 words, a `features` block, no jargon in narration, Hindi bundle with audio, all four runtime probes behaving (grounded / grounded / no negotiation / decline + callback) | ✅ opening 111 words, roles intro·outcome·proof×4·features·establish, 496 words total; hi-IN alt bundle with audio; probes: range grounded (F001/F010), kerb weight grounded, discount → cites the written HDFC offer and refuses to negotiate, Ather → decline + callback. Build 958 s (voice 613 s = 64 % → parallelised after this run), cost $2.50 (Claude 91 %) | read: Gemini ×1 + Claude ×1 (facts) + Claude ×3 (plan) · build: Claude author ×2, translate ×1, rehearsal ×13; Sarvam ×96, Gemini-TTS ×10 fallbacks · runtime: Claude ×5 |
| 2026-09-03 | Paid QA run 2 — dummy 20 s video + images + spec text, English (`evals/qa_real.py video` → `dm_78890026`): expect the video shots to be used as visuals, opening ≤ 115 words, the same four runtime behaviours, and the voice stage well under the first run after parallelising | ✅ opening 92 words, 486 words, roles intro·outcome·proof×4·features·establish; voice 68 s (was 613 s); probes all as expected; 2 lines without audio (browser voice); build 400 s, cost $2.20 | read: Gemini ×2 + Claude ×1 + Claude ×3 (plan) · build: Claude author ×1, rehearsal ×14; Sarvam ×55 · runtime: Claude ×5 |
