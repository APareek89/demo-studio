# Codex brief — Sales Trainer flow, script quality, slides, runtime lookup, plain language, check-ins, voice mode

Date: 23 September 2026. Author: Anand's orchestrator session. Audience: a Codex session that will implement this end to end. The design decisions are already taken; your job is to implement them exactly, keep every invariant, and prove it with the free evals. Do not re-open decisions. Where this brief says "verbatim", paste the text as given.

---

## 0. Setup and reading (about 40 minutes, then start coding)

1. Repo `/Users/macbook/Documents/demo-studio`, branch `codex/creta-conversational-demo`. Create and work on `codex/sales-trainer-flow`. Commit after every work package with the message prefix `WPn:`. Never commit `.env`.
2. Run everything with `MOCK_LLM=1` and blocked outbound sockets, the way `evals/qa_deck.py` and `evals/smoke_mock.py` do. **No paid model or voice call anywhere except WP9, and only if Anand has written "authorized" in WP9.**
3. Read, in this order: `CLAUDE.md`, `AGENTS.md`, `Handoff.MD` (top two sections and "Decisions and invariants"), `docs/core-flow-explained-2026-09-23.md`, `docs/proposal-sales-trainer-flow-2026-09-23.md`, `refine.MD`, `docs/DEMO_BUILD_AND_RUN.md`, `docs/prompt-audit-planner-author-2026-09-19.md` (§6 and §7 only). Line numbers in the two dated docs were taken before commit `0461609` added comments; navigate by function name.
4. Do not touch `data/demos/dm_41513908/` (published Creta v8, its snapshot, its one saved session) or anything under `output/`. Do not restart the server on port 8896. Use a temporary data directory for all runs.
5. The free gates that must pass before every commit: `python evals/qa_deck.py` (320/320), `python evals/qa_accept.py` (24/24), `python evals/smoke_mock.py` (both phases), plus every contract you add or touch. Syntax: `python -m compileall server` and `node --check` on every changed JS file.
6. Update in the same commit as the code: `docs/mermaid/*.mmd` and `python3 docs/build_viewer.py` when a flow changes; `Learning.MD` (5-whys entry) for each user-reported issue fixed; `Handoff.MD` at the end; `PRD.md` and `docs/ARCHITECTURE_FLOW.md` gate rows when a rule changes.

### Invariants that never change

- **No citation, no claim.** Every spoken or answered sentence with a figure or claim cites an approved fact id. Validators run at authoring (`author.validate`) and at runtime (`runtime_graph.validate_decision`). You may add validators; you may never relax one.
- Keys stay in `.env` and on the server. A stage failure leaves the previous JSON intact. The six Align approvals are honoured and never set by the agent. The align agent emits structured actions; code executes them.
- Locked voice stays Sarvam `bulbul:v3` speaker Priya. Immutable knowledge snapshots and published bundles are never rewritten.
- Build text provider chain stays `BUILD_PROVIDERS` (Gemini → Claude → Runware); runtime chain stays `RUNTIME_PROVIDERS`. New stages call `server/llm/claude.py:structured` like the others and must work under `MOCK_LLM=1`.
- No new external dependencies. Plain Python and plain ES modules only.

### Decisions already taken (implement, do not debate)

| # | Decision |
|---|---|
| D1 | The demo opens with the **category's fundamentals** in everyday language, in the reviewed playbook order; delighters come after fundamentals. This replaces "open with supported standout features". The 4 September rules stand: no decision frame and no digits in the first spoken line. |
| D2 | A new **Coach** stage (the sales trainer) owns story order, coverage, the three USPs and evidence gaps. The **Planner** owns evidence mapping, pictures, segment briefs and word budgets. The **Author** owns speech. |
| D3 | **Word budgets** are typed fields allocated by the planner per segment and summing to the demo length (`settings.pitch_minutes`). Today's flat caps become ceilings raised by 8 words to allow joins. |
| D4 | A slide may carry **up to two pictures**. A line with no audited picture gets a **proxy** picture: the closest tagged image (engine → bonnet/grille/front) else the hero, with a cited tag, marked as illustration, never counted as proof. |
| D5 | The runtime may **look up websites the customer supplied at intake**, for the whole session, when the registry has no evidence. Attribution is mandatory; results stay turn-scoped and never enter the registry. |
| D6 | Runtime answers are **plain language**. A small allowlist of common terms is permitted (cc, hp, turbo, dual clutch, automatic, airbags, sunroof). Blocklisted engineering terms are replaced by reviewed neutral phrases or trigger repair; exact terms are spoken only when the customer explicitly asks for technical detail. |
| D7 | **Check-ins never pause the demo.** After an answer the guide listens for 3 seconds, then continues automatically. Clarifying questions from the guide still wait. CTA choice remains explicit. |
| D8 | A **Voice mode toggle** on the welcome screen. On: the microphone is requested once and stays on for the whole demo, typed input remains available. Off: text only, no microphone prompt. |
| D9 | Exactly one paid Read is allowed, in WP9, on a copy of the Creta demo, with the cap written there. |

---

## WP1 — Coach stage and playbook

**Goal.** Add `server/agents/coach.py` between Understand and Plan. It writes `playbook.json` from a category library plus the approved registry, validated by code, cached by registry hash.

**Files.** `server/schemas.py`, new `server/agents/playbooks.py`, new `server/agents/coach.py`, `server/graph.py`, `server/orchestrator.py`, `server/llm/mock.py`, `server/app.py` (stage list for progress and the Align payload), `web/studio/align.js` (progress stage label and the Story order panel), `server/agents/align.py` (`cards()` payload), new `evals/coach_contract.py`.

### 1.1 Schema (`server/schemas.py`, next to `Plan`)

```python
class PlaybookStop(BaseModel):
    id: str = Field(description="slug, e.g. 'powertrain'")
    label: str = Field(description="2-6 everyday words, the thing itself, no numbers")
    kind: Literal["fundamental", "differentiator", "delighter", "hygiene", "ownership"]
    why_here: str = Field(description="one sentence: why a trained salesperson covers this at this point")
    fact_ids: list[str] = Field(description="approved registry ids that support this stop")
    picture_ids: list[str] = Field(default_factory=list, description="image/shot ids that literally show this stop")
    must_cover: bool = True
    gaps: list[str] = Field(default_factory=list, description="what the library expects here that the registry lacks")

class PlaybookUSP(BaseModel):
    id: str
    name: str = Field(description="3-8 everyday words, a promise in the buyer's language, no digits, units or model codes")
    fact_ids: list[str]
    stop_id: str

class PlaybookObjection(BaseModel):
    objection: str
    fact_ids: list[str] = Field(default_factory=list)
    status: Literal["supported", "unknown"]

class EvidenceGap(BaseModel):
    what: str
    why_it_matters: str
    suggested_source: str

class Playbook(BaseModel):
    category: str
    category_source: Literal["library", "inferred"]
    stops: list[PlaybookStop]
    usps: list[PlaybookUSP] = Field(description="exactly three")
    objections: list[PlaybookObjection] = Field(default_factory=list)
    evidence_gaps: list[EvidenceGap] = Field(default_factory=list)
    notes: str = ""
```

### 1.2 Category library (`server/agents/playbooks.py`, new)

`VERSION = "2026-09-23"`. `LIBRARY: dict[str, dict]` keyed by normalised category. Each entry: `{"order": [ {id, label, kind, covers: [keywords]} ... ], "aliases": [...]}`. `match(category: str) -> tuple[str, dict]` lower-cases, strips punctuation, matches key or alias by substring, else returns `("_generic", LIBRARY["_generic"])`.

Entries, verbatim order:

- `compact suv` (aliases: "compact suv", "mid-size suv", "midsize suv", "suv", "crossover"): powertrain (fundamental; engine, turbo, gearbox choice) → stance and ride (fundamental; ground clearance, suspension, wheels, tyres) → space and practicality (fundamental; seating, rear seat, boot) → safety (fundamental; airbags, structure, driver assistance) → cabin and tech (differentiator; screens, climate, connected features) → delighters (delighter; sunroof, ventilated seats, audio, ambient) → ownership (ownership; price, warranty, efficiency, service).
- `premium suv` (aliases: "luxury suv", "premium"): powertrain and drive → ride and refinement → safety → cabin → tech → ownership.
- `electric scooter` (aliases: "ev scooter", "e-scooter", "electric two-wheeler", "scooter"): range → charging → running cost → battery life and warranty → ride and practicality → features → ownership.
- `_generic`: fundamentals (what it is and what it does) → proof of the main job → practicality → safety or reliability → differentiators → delighters → ownership. The Coach must set `category_source: "inferred"` when `_generic` is used.

### 1.3 Coach (`server/agents/coach.py`, new)

- `COACH_SYSTEM`, verbatim:

```
You are a sales trainer for {category}. You have trained showroom staff on this product class. Decide what a good
salesperson covers, in what order, for THIS product, using only the APPROVED FACT REGISTRY below. You do not write
dialogue. You write the playbook the planner must follow.

RULES
- Follow CATEGORY LIBRARY ORDER as the spine. Keep every stop whose evidence exists. A stop the registry cannot support
  stays in the list with must_cover=false and a gap naming exactly what is missing (e.g. "ground clearance figure").
- The first stop must be a fundamental. Delighters (sunroof, ventilated seats, audio, ambient lighting) never come before
  the fundamentals are covered.
- Each stop lists the registry ids that support it and the picture ids that literally show it. A cabin photo does not
  show an engine. If no picture shows a stop, leave picture_ids empty; do not invent one.
- usps: EXACTLY THREE. Choose each by asking what a buyer would tell a friend that evening, then check the registry
  supports it. At least two USPs must sit on fundamental stops. Names are promises in the buyer's language, 3-8 words,
  with NO digits, units, model codes or parts lists.
- objections: the 3-6 doubts a buyer in this category raises (price, running cost, service, resale, size, safety).
  Mark each supported (with ids) or unknown. Never invent a response.
- evidence_gaps: what the category playbook needs that the registry lacks, with the source that would supply it
  (spec sheet page, brochure table, official website section, a photo of the engine bay or side profile).
- Plain, everyday words everywhere. No engineering vocabulary in labels or names.
Return JSON matching the schema exactly.
```

- `run(demo_id, emit, instruction="")`: read `understanding.json`; `facts = approved`; build rows with `fact_context(f)` **plus** the suffix `(pictures: im06, im08)` from `und["image_map"]` when present and `(origin: website|uploaded)` from the fact's `origin`; `product`, `unknowns`, image list in the same format `plan.run` uses; `library_key, entry = playbooks.match(product.category)`; content = `PRODUCT`, `CATEGORY LIBRARY ORDER (version …)`, `APPROVED FACT REGISTRY (n)`, `OPEN UNKNOWNS`, `IMAGES`, and on revision `PREVIOUS PLAYBOOK` + `REVISION INSTRUCTION FROM THE USER — follow it precisely`. Call `claude.structured(COACH_SYSTEM.format(category=...), content, schemas.Playbook, max_tokens=12000)`.
- `validate(pb: dict, und: dict) -> list[str]` (deterministic, after the call): drop fact ids not approved; drop picture ids not allowed; `len(usps) == 3` else issue; first stop kind is `fundamental` else move the first fundamental to the front and add an issue; USP names must not match `author.NUMBERISH`; every `must_cover` stop needs ≥1 fact id else set `must_cover=False` and add a gap; at least one picture id or a picture gap per must-cover stop; duplicate stop ids rejected. Store `issues` in the file.
- Write `playbook.json` with `library_version`, `library_key`, `registry_hash` (reuse `faq._registry_hash`), `issues`. Cache: if an existing file has the same `registry_hash`, `library_version`, `settings.audience` and there is no instruction, return it unchanged and `emit("Playbook unchanged — reused")`.
- `apply_overrides(pb, demo_id)`: if `playbook-overrides.json` exists with `{"stop_order": [ids], "kinds": {id: kind}}`, reorder and relabel, then re-run `validate`.

### 1.4 Wiring

- `server/graph.py:build_graph`: add node `coach`; edges `understand → coach → plan`; the `router` accepts `revise` into `coach`; `start_revise` accepts stage `coach`. The stage-order list used for revision routing (find the list containing `"understand", "plan", "author"`) gets `coach` after `understand`.
- `server/orchestrator.py`: `_run_stage` dispatch adds `"coach": coach.run`; `DOWNSTREAM["understand"]` gains `"coach"`; `DOWNSTREAM["coach"]` = same list as `DOWNSTREAM["plan"]` plus `"plan"`; `changed_cards("coach", …)` returns `["script", "visuals"]` when stops, kinds or USPs changed; `apply_actions` `revise` may name `coach`; an attachment upload with no explicit stage keeps `revise understand`.
- Stage names for progress and cost: wherever the stage list `understand, plan, author, deck, faq, voice, rehearsal, bundle` appears (`server/app.py` SSE progress, `server/runlog.py`, `server/usage.py`, `web/studio/align.js`), add `coach` with label "Sales playbook".
- Mock mode: `server/llm/mock.py` fakes any schema by introspecting `model_fields` (`fake()`, `_fake_value()`), there is no registry by schema name. Do **not** rely on it for the playbook. In `coach.run`, when `config.MOCK_LLM` is true, build the playbook deterministically with `mock_playbook(und, entry)`: category from the product, library order as stops, fact ids assigned by keyword match of each stop's `covers` list against fact claims, three USPs on the first three supported stops, one gap per unsupported stop; then run `validate()` exactly as for a model result. Also add `prefer` entries in `mock._fake_value` for `kind` → `"fundamental"` and `category_source` → `"library"` so the generic faker still yields a valid `Playbook` if anything else calls it.
- Run-log and stage lists: `server/runlog.py` indexes `_REPORTS[stage]` directly (KeyError for an unknown stage) and builds input rows per stage; register `coach` there with its input files (`understanding.json`) and output (`playbook.json`). `server/store.py` `STAGES` gains `coach` after `understand` (it seeds `demo.json.stages` and `_migrate`). The three revise-stage whitelists are separate copies and all need `coach`: the tuple in `server/app.py` `revise()`, the `order` dict in `orchestrator.apply_actions`, and the `AlignAction.stage` Literal in `server/schemas.py`.
- Align: `align.cards()` adds `playbook` (stops, usps, gaps, issues) to the **script** card payload. `web/studio/align.js` renders a "Story order" panel above the segments: each stop as a row with label, kind badge, fact count, picture count, gap text; drag to reorder; a "Ask for this source" button per gap that posts the existing `request_upload` action with the gap text. Saving order posts `PATCH /api/demos/{id}/align/playbook` `{stop_order, kinds}` → writes `playbook-overrides.json`, unapproves `script` and `visuals`, and triggers `revise plan` through the existing revise path. No seventh card.

### 1.5 Acceptance

- `MOCK_LLM=1` Read of the sample demo produces `playbook.json` before `plan.json`; the Align script card shows the Story order panel; reorder → `revise plan` runs and resets script and visuals approvals.
- `evals/coach_contract.py` (≥12 groups): library match and alias; `_generic` marks inferred; first stop fundamental enforced; exactly three USPs; USP name with digits rejected; unsupported stop → must_cover false + gap; unknown fact id dropped; picture id not allowed dropped; cache hit on unchanged registry; override reorder applied and revalidated; progress stage list includes coach; blocked sockets, isolated storage.

---

## WP2 — Planner follows the playbook; script quality prompts

**Goal.** The planner maps playbook stops to segments, in order, with typed budgets and a `fundamental` flag; the author prompt gets the 19 September audit fixes that are still open.

**Files.** `server/schemas.py`, `server/agents/plan.py`, `server/agents/author.py`, `server/agents/principles.py`, `evals/narrative_roles_contract.py` (extend), new `evals/plan_playbook_contract.py`.

### 2.1 Schema

`SegmentPlan` gains `stop_id: Optional[str] = None`, `fundamental: bool = False`, `word_budget: int = 0`. `Plan` gains `total_words: int = 0`, `playbook_version: str = ""`.

### 2.2 `plan.run`

- Load `playbook.json` (+ `apply_overrides`). Inline `PLAYBOOK:` as JSON (stops in order with fact_ids, picture_ids, must_cover, gaps; usps; objections; evidence_gaps) **before** the registry block.
- Add to `PLAN_SYSTEM`, verbatim, as the first bullet under the segments rules:

```
- THE PLAYBOOK IS SETTLED. Proof segments follow PLAYBOOK.stops in that order, one proof segment per must_cover stop,
  each with stop_id set. usps are PLAYBOOK.usps, unchanged. A stop with must_cover=false gets no proof segment; put its
  supported facts in deeper detail of the nearest segment and keep its gap in visual_gaps. Never reorder, merge or invent
  a stop. The intro segment previews stop 1 in everyday words; the outcome segment names the three USPs.
- WORD BUDGETS. Set word_budget for every segment so the total over intro, outcome, proof, features and establish equals
  total_words minus 45 for the closing. Spend more on the lead fundamental stop (up to the role ceiling) and less on a
  minor stop (never under 22). An even split is a catalogue.
```

- Delete from `PLAN_SYSTEM`: the proof bullet text "strongest supported standout feature first, then the everyday use or choice it opens up, adjacent proof, practical fit and ownership. Avoid a fixed exterior-to-engine checklist." (replace with "one proof segment per playbook stop, in playbook order. One area per segment."); the everyday-buyer bullet that begins "For everyday buyers, plan around a standout visible feature" through "Technical buyers may ask for it." (replace with: "For everyday buyers, render every stop in everyday words. Engine, gearbox, suspension and dimensions are covered as choices and what they are for; their figures and component names go to deeper detail.").
- `principles.PITCH_SHAPE`: STEP 2 sentence "A specific supported cabin experience beats a generic promise or a list." → "The first stop of the playbook, in everyday words, beats a generic promise or a list."; STEP 4 "the strongest supported standout feature first … The route is a narrative, not a fixed exterior-to-engine checklist." → "the playbook's stops in order, spoken as a walk: each stop is a place to be standing after the one before."
- Post-processing after the model call: `_enforce_playbook(p, pb)`: map each proof segment to a stop by `stop_id` (fallback: best fact-id overlap); drop proof segments with no stop; add a minimal proof segment for a missing must-cover stop (title = stop label, goal = "MOMENT/SPOKEN/HANDOFF" placeholder built from the stop, fact_ids = stop fact ids, visual_refs = stop picture ids) and record an issue; sort proof segments by stop index (keep the existing role sort); set `fundamental = stop.kind == "fundamental"`; replace `usps` with the playbook USPs; set `playbook_version`.
- `_enforce_budget(p, demo)`: `total_words = round(settings.pitch_minutes * 60 * author.WPS)` (3 min → 342); clamp each `word_budget` to `[22, ceiling(role)]` where `ceiling = author.LIMITS[role] + 8`; if the sum over non-closing segments differs from `total_words - 45` by more than 10 %, rescale proportionally and clamp again; write `p["total_words"]`.

### 2.3 Author prompt (`author.py`, `principles.py`) — the audit items still open

The audit is `docs/prompt-audit-planner-author-2026-09-19.md` (restored 23 September; §6 starts at line 149, §7 at line 356). Apply it **only as mapped below**. "Verbatim" means paste the audit's fenced text unchanged; "modified" gives the exact edit; "skip" means do nothing. Do not apply anything from the audit that is not in this map.

| Audit item | Action | Exact instruction |
|---|---|---|
| §6A "author.py:339 — stop injecting PITCH_SHAPE; drop {proof_block}" | **skip** (done in commit 1cfde68) | Verify `AUTHOR_SYSTEM.format(...)` in `author.run` has no `proof_block` and no `PITCH_SHAPE`; add a group to `narrative_roles_contract.py` asserting it. |
| §6A "Delete the editorial half of rule 6" | **apply** | In `AUTHOR_SYSTEM` rule 6 delete: "Show standout features early…", the cabin-versus-dimensions example (the sentence beginning "prefer 'Start with the cabin: selected variants offer a panoramic sunroof…'"), and the engine/gearbox pairing preamble. Keep every ban sentence. |
| §6A "Delete rule 4's restatement of the flow" | **apply** | Replace the whole of rule 4 with the §6B "THE PLAN IS SETTLED" text (next rows). |
| §6B CONTINUITY block (replaces the "stand alone" opening sentences of `AUTHOR_SYSTEM`) | **verbatim** | Paste the fenced block starting "You write the spoken words for a product demo…" in place of the current opening two sentences. |
| §6B "Replace rule 4's head" | **modified** | Paste the fenced "4. THE PLAN IS SETTLED…" block, with two edits: (a) "Put a check-in only where the plan asks for one." → "Put a one-line closing statement only where the plan asks for one; never a question (WP7)."; (b) "a segment at 30 words that flows beats one at 38 that is crammed" → "a segment under its word_budget that flows beats one at the ceiling that is crammed". |
| §6B OPENINGS rule (replaces the signpost line) | **verbatim + new SIGNPOSTS** | Paste the fenced "OPENINGS…" block in place of the `Signposts, varied…` line. Replace `principles.SIGNPOSTS` with these six **shapes** (this is the new constant, verbatim): `SIGNPOSTS = ["A PLACE — where the buyer would be standing: 'Sitting in the driver's seat,'", "A MOMENT — an ordinary situation: 'On a long drive,'", "THE THING ITSELF — name what is in view: 'The glass roof runs right back'", "A CHOICE — the decision this stop gives: 'There are two gearboxes to choose from,'", "AN HONEST LIMIT — what this version does not have: 'Not every version gets this,'", "WHAT PEOPLE ASK — the question this stop answers: 'The thing people ask about first is'"]`. Render them into `{signposts}` as they are today. |
| §6B anti-padding clause | **modified** | Paste the fenced "Aim for one natural ten-to-twenty-second thought…" block with "usually 19-38 words across the batch" → "within the segment's word_budget (ceiling: the role limit)". |
| §6B rule 5 second half | **verbatim** | Paste the fenced "Concrete nouns; no 'smart/convenient…'" block in place of rule 5's second half. |
| §6B "A FIT-CHECK IS A LAST RESORT" | **verbatim** | Paste immediately after the translation ladder (see §6D row). |
| §6B rewrite instruction ("VALIDATOR ISSUES — each names a specific segment…") | **verbatim** | Replace the repair-pass instruction string used in `author.run`'s issue loop. |
| §6C stats ban ("Never build a USP or a narration line on a company or market statistic…") | **apply twice** | Paste verbatim into `COACH_SYSTEM` under the usps rule (WP1) and as a new `PLAN_SYSTEM` bullet under the segments rules. |
| §6C "Choose each USP by asking what a buyer would tell a friend…" | **skip** | Already expressed in `COACH_SYSTEM`; the planner no longer chooses USPs. |
| §6C "You choose what the demo is emotionally about…" | **modified, into COACH_SYSTEM** | Paste into `COACH_SYSTEM` with "make the first proof stop the one closest to it" → "make the lead fundamental stop the one closest to it, and place the delighter that serves it right after the fundamentals". |
| §6C check-in placement ("Exactly TWO segments carry a check-in…") | **replaced** | Add to `PLAN_SYSTEM` instead: "At most two segments end on a one-line closing statement, never a question, placed where a decision turns; name them in the goal. A question after every section is an interrogation, not a conversation." |
| §6C "Give every segment a word budget… An even split across six segments is a catalogue." | **skip** | Superseded by the typed `word_budget` rule in §2.2. |
| §6C titles ("Titles are sometimes SPOKEN at runtime…") | **verbatim** | Add to `PLAN_SYSTEM` segments rules. |
| §6C proof bullet ("4-6 × role=proof — GUIDED DISCOVERY, ordered as a walk…") | **partial** | Skip the ordering text (the playbook owns order). Add only its last two sentences ("Do not open two consecutive segments the same way… a short honest limitation.") to the playbook bullet in §2.2. |
| §6C visual tagging bullet | **verbatim** | Replace the current "Every segment needs a visual that shows its subject…" bullet with the audit's version; keep "missing → visual_gaps". |
| §6D TRANSLATION LADDER | **verbatim** | New constant `principles.TRANSLATION_LADDER` with the fenced R1–R5 text; inject into `AUTHOR_SYSTEM` through a new `{ladder}` placeholder placed right after rule 5. Then the fit-check clause from §6B. |
| §6D "replace the deletion policy" | **modified location** | The sentence "Move a technical quantity as a whole to `deeper` detail; never keep its number while dropping the unit." now lives inside `principles.AUDIENCE["everyday"]`. Replace that sentence there with the audit's fenced replacement ("When a technical quantity does not belong in the main tour, do not simply delete it…"). Keep the rest of the audience text. |
| §7 Tier 1 three-sentence goal | **skip** (done) | Already in `PLAN_SYSTEM` ("The segment goal is the Author's brief…"). Verify and leave. |
| §7 Tier 2 schema fields (`narration_fact_ids`, `say_as`, `moment`, `hands_on`, `carries_checkin`, `arc`, `excluded_from_narration`) | **skip** | Out of scope; `word_budget` alone ships (§2.1). Log the rest in `refine.MD` under P4 as remaining. |
| §8 continuous mode, §9, §10 | **skip** | Not part of this brief; the +8-word ceiling caution is implemented in WP3. |

After applying: `python -c "from server.agents import author, principles, plan"` imports clean; `narrative_roles_contract.py` and `speech_style_contract.py` pass; add one group asserting `AUTHOR_SYSTEM` contains "CONTINUITY AND STANDING ALONE" and "TRANSLATION LADDER" and does not contain "panoramic sunroof" or "Show standout features early".

### 2.4 Acceptance

- `evals/plan_playbook_contract.py` (≥10 groups): proof order equals playbook order; missing must-cover stop is added with an issue; must_cover=false stop has no segment; `fundamental` set from kind; USPs replaced; budgets clamp and rescale; total_words from `pitch_minutes`; first proof segment is fundamental for the compact-SUV fixture; mock Read end to end.
- `narrative_roles_contract.py` still passes; add a group asserting `PITCH_SHAPE` no longer contains "standout feature first" and `AUTHOR_SYSTEM` no longer contains "panoramic sunroof".

---

## WP3 — Word budgets in the validator and the timeline

**Goal.** The author is held to the planner's per-segment budget; ceilings allow joins; the timeline reports planned versus measured seconds.

**Files.** `server/agents/author.py` (`LIMITS`, `CLOSING_LIMIT`, `ROUTE_LIMIT`, `validate`, `split_long_batches`, `timeline`), `web/studio/align.js` (script card timing), `evals/generation_contract.py` (extend), `evals/speech_style_contract.py` (check still green).

1. `LIMITS = {"intro": 46, "outcome": 46, "proof": 46, "features": 48, "establish": 44}` (each +8); `CLOSING_LIMIT = 45` unchanged; replace the constant `ROUTE_LIMIT` with `route_limit(demo) = round(settings.pitch_minutes * 60 * WPS) + 40`.
2. `validate(script, und, plan, demo)`: per segment `budget = plan segment word_budget or LIMITS[role]`; issue when `total > budget + 4` ("over its budget of N") and a warning when `total < budget - 10` ("well under budget; add the join or the moment"); keep the ceiling check `total > LIMITS[role]` as a hard issue. Route check uses `route_limit(demo)`.
3. `split_long_batches`: split threshold is `LIMITS[role] + 4`, unchanged in spirit.
4. `timeline`: per segment add `planned_seconds = round(word_budget / WPS, 1)` and top-level `planned_total_seconds`; keep `exact` semantics. Align script card shows `planned / measured` per segment and the total against `pitch_minutes`.
5. `AUTHOR_SYSTEM` rule 4 references the plan's budget (done in WP2).

**Acceptance.** `generation_contract.py` gains groups: over budget flagged; under budget warned; ceiling still hard; route limit derived from `pitch_minutes` 2 and 4; timeline carries planned seconds. Creta v8 files under a temporary copy still validate with `issues: []` (budgets absent → fall back to LIMITS).

---

## WP4 — Slides: two pictures per slide, proxy picture with a tag

**Goal.** A slide shows up to two pictures from the segment's audited line bindings, switching emphasis per line; a line with no picture gets a proxy picture and a cited tag; the hero is the last resort.

**Files.** `server/schemas.py` (`Slide`, `Callout`), `server/agents/deck.py`, `server/agents/bundle.py`, `web/slide.js`, `web/player/player.js` (only if `showSlideView` does not already pass the line index), `web/studio/align.js` (deck editor), `server/app.py` (`PATCH /align/deck`), `evals/qa_deck.py` (fixtures), `web/player/player_contract.html` (or `evals/player_contract.html`) for renderer checks.

### 4.1 Schema

```python
class SlideMedia(BaseModel):
    image_id: str
    from_line: int = 0          # first line index that uses this picture
    proxy: bool = False         # true when the picture illustrates, not proves
    proxy_reason: str = ""      # "closest by part: bonnet" | "hero — no picture for this topic"
```
`Slide.media: list[SlideMedia] = []` (0–2 entries). Keep `Slide.image_id` and set it to `media[0].image_id` for old readers and the exporter. `Callout.image_id: Optional[str] = None` (the picture it anchors on; default `media[0]`).

### 4.2 `deck.build`

- New `choose_media(seg, lines, und, script_audit, hero_id) -> list[dict]`: walk verified lines in order; a line contributes its `visual.ref` only if `visual.kind == "image"` and the audit row for that line has `coverage == "full"` (read `script["visual_audit"]["lines"]` or `visual-audit.json`; if the audit is absent, accept the author's binding); collapse consecutive repeats; keep the first two distinct refs with their first line index. If the result is empty, call `choose_proxy`.
- New `PROXY_PARTS`, verbatim: `{"engine": ["bonnet", "hood", "grille", "front bumper", "headlamp", "front"], "turbo": ["bonnet", "hood", "grille", "front"], "gearbox": ["gear lever", "gear selector", "gear knob", "centre console", "console"], "transmission": ["gear lever", "gear selector", "centre console", "console"], "suspension": ["wheel", "tyre", "wheel arch", "side profile", "side"], "ground clearance": ["wheel", "tyre", "side profile", "side", "underbody"], "tyre": ["wheel", "tyre"], "wheel": ["wheel", "alloy"], "boot": ["tailgate", "boot", "rear", "rear bumper"], "safety": ["airbag", "seat belt", "dashboard"], "price": [], "warranty": [], "efficiency": []}`.
- New `choose_proxy(seg_text, images, hero_id) -> dict`: tokens of the segment's text and topic → the first `PROXY_PARTS` key found → candidate part names; score each allowed image by tagged parts matching those names with `confidence >= PART_CONFIDENCE`; best → `{"image_id", "from_line": 0, "proxy": True, "proxy_reason": f"closest by part: {part}"}`; none → the hero with `proxy_reason: "hero — no picture for this topic"`.
- Callouts: `place_callouts` takes the picture's parts; each callout gets `image_id`. For a proxy picture, add one derived callout: the segment's first cited fact rendered by `_compact` to ≤8 words, `fact_ids` from that line, anchored on the matched part box when confidence ≥ 0.6 else panel, `reveal_on_line 0`. `clean_callouts` and `ungrounded` apply unchanged; ≤3 callouts per picture.
- `image_reason` records the media decision. `apply_overrides` accepts `media` (list of allowed image ids, max 2) and callout `image_id`.
- A proxy picture is **never** written into `visual-audit.json` and never counts as coverage; `visuals.align` is untouched.

### 4.3 `bundle.build`

Copy `media` (with URLs resolved like `image_url`) and callout `image_id` per slide; keep `image_url` for old readers.

### 4.4 `web/slide.js`

- Render a `.slide-media` container with one `.slide-pic` per `media` entry (max 2), each with its own `<img>` and leaders SVG; layout side by side when the stage is ≥700 px wide, stacked otherwise; native aspect fit per picture inside its half.
- Callouts render inside the picture matching `c.image_id` (default the first). `drag` reports `label_pos` as fractions of that picture.
- `setRevealed(lineIdx)`: reveal callouts as today; mark the picture with the largest `from_line ≤ lineIdx` as `.active` and the other as `.dimmed` (opacity 0.55, no layout change). A `proxy` picture shows a small badge "illustration".
- Keep `renderSlide`'s return shape; `setImage` may be removed or repointed; nothing else in the player changes if `showSlideView` already calls `setRevealed` per line (verify in `playLines`).

### 4.5 Align

Deck editor shows both pictures with their callouts; a picker to swap either picture from the allowed images; a proxy badge; save → `PATCH /align/deck` with `media` and callout `image_id`; server validates image ids against `store.visual_allowed` and rejects >2.

### 4.6 Acceptance (`evals/qa_deck.py` fixtures, plus a renderer check)

- Segment with lines bound to im08 then im06 (both `full`) → `media = [im08 from 0, im06 from 1]`, callouts carry `image_id`.
- Segment with three distinct pictures → only the first two.
- Engine segment with no image, fixture image tagged "bonnet" 0.9 → proxy = that image, one derived callout anchored on the bonnet box, `proxy_reason` "closest by part: bonnet".
- Price segment with no matching part → hero proxy, callout in panel.
- Audit `partial` → line contributes nothing; audit absent → author binding accepted.
- Renderer: two pictures render side by side at 1000 px and stacked at 400 px; `setRevealed(1)` marks the second picture active; proxy badge present; drag on the second picture writes fractions of that picture. Total deck contract count rises from 320 to ≥ 340.

---

## WP5 — Runtime lookup on customer-supplied websites

**Goal.** The customer can give websites at intake (or any time). They stay in the session and the graph uses them, scoped as today, when the registry has no evidence. Attribution is mandatory.

**Files.** `web/player/player.js` (`runIntake`, intake input, `profileForServer`), `server/runtime_state.py` (profile persistence), `server/runtime_graph.py` (`run_turn`, `reason`, `_verification_urls`, the page-claim regex), `server/runtime_tools.py` (`supplied_urls`), `server/app.py` (`run_pitch` passes profile unchanged), new `evals/runtime_customer_sites_contract.py`.

1. **Intake UI.** Under the intake text input add an optional single-line field labelled "Websites I can check (optional)" with placeholder `hyundai.com/in/en/find-a-car/creta`. Parse on submit with the same regex as `runtime_tools.supplied_urls`; keep at most 5; store `S.profile.customer_urls`. The guide's spoken intake stays one question. A URL typed or spoken later is appended by the client (regex on the customer's text) and by the server (existing per-turn regex).
2. **State.** `profileForServer` sends `customer_urls`. `run_turn` merges `customer_urls` from body profile, previous checkpoint profile and per-turn regex into `state["customer_urls"]` (deduped, max 8) and persists it in the checkpoint.
3. **Tools.** `supplied_urls(question, history, extra=None)` returns the union with `extra`; `source_lookup` is called with `extra=state["customer_urls"]` everywhere it checks the allow-list. The reason payload's `CUSTOMER_URLS` lists the union.
4. **Auto-lookup.** There is no retrieval score threshold today: `retrieve()` returns an evidence list that may simply be empty (knowledge drops non-positive scores). Two triggers, both bounded by the existing 2-round/4-call rule and the 12 s budget: (a) **pre-model**, in `reason()` next to the existing deterministic hook for `_verification_urls` (the `required … if pending and tool_rounds < 2 and tool_count < 4 → TurnDecision(action="tools")` pattern): if `not state["evidence"]` and `state["customer_urls"]` and `tool_rounds == 0` and the question is not an interaction act, return a `tools` decision with one `source_lookup(url = first customer url whose host contains a product token, query = question)`; (b) **post-model**, in `after_reason()`: if the decision has `answered == False` (a decline) on round 0 and `customer_urls` exist and no lookup has run, route to `tools` with the same single lookup instead of `validate`. Results then reach the model on the next `reason` round like any tool result. Add to the runtime system prompt, verbatim: `"If the evidence does not answer the question and CUSTOMER_URLS is non-empty, request source_lookup on the most relevant customer URL before declining. Never claim a page was checked unless a live_web fact from it is cited."`
5. **Attribution.** Unchanged "According to <host>, …" rewrite. Add `as per` to the page-claim regex: `\b(?:according to|as per)\b.{0,50}\b(?:page|website|webpage|site)\b`.
6. Scope, budget, private-network and redirect rules are unchanged. Live facts stay `W<sha>` turn-scoped.
7. Optional flag, default off: `settings.runtime_default_sites = "off"|"on"`; when on, the demo's `product` URL sources join `customer_urls` for every session. Implement the flag and the plumbing; leave it off.

**Acceptance (`runtime_customer_sites_contract.py`, ≥10 groups, fake fetcher, blocked sockets).** Intake URL persists across three turns via checkpoint; a question with no retrieved evidence triggers exactly one lookup and the answer starts "According to <host>"; a question with strong evidence does not trigger lookup; off-host URL rejected; `as per … website` about a stored fact is rejected; explicit "check <url>" path unchanged; flag off → product URL not used; flag on → used; cancellation during lookup honoured; latency within the 12 s budget in the fake clock.

---

## WP6 — Plain language at runtime

**Goal.** Answers are non-technical. Common terms pass; engineering terms are replaced by reviewed neutral phrases or repaired; exact terms only when the customer asks for technical detail.

**Files.** new `server/agents/plain_terms.py`, `server/runtime_graph.py` (system prompt, `validate_decision`, `_repair_composition`), `server/agents/author.py` (`JARGON` reuse), `server/agents/faq.py` (apply to FAQ answers at build), new `evals/runtime_plain_language_contract.py`, `Learning.MD` entry.

1. `plain_terms.py`, verbatim:

```python
COMMON_TERMS = {"cc", "hp", "bhp", "ps", "turbo", "turbo petrol", "diesel", "petrol", "hybrid", "automatic", "manual",
    "dual clutch", "dual-clutch", "airbag", "airbags", "abs", "sunroof", "panoramic sunroof", "touchscreen", "cruise control",
    "parking sensors", "reverse camera", "alloy wheels", "alloys", "km/l", "kmpl", "litre", "litres", "seater", "boot",
    "ground clearance", "suspension", "wheelbase", "torque", "gearbox", "ev", "battery", "range", "fast charging"}

# Neutral plain renderings. No benefit words. Reviewed by a human before release.
JARGON = {
    "mcpherson strut": "strut-type front suspension",
    "macpherson strut": "strut-type front suspension",
    "coupled torsion beam axle": "a simple rear suspension setup",
    "coupled torsion beam": "a simple rear suspension setup",
    "torsion beam": "a simple rear suspension setup",
    "multi-link": "independent rear suspension",
    "coil spring": "coil springs",
    "gdi": "direct-injection petrol engine",
    "mpi": "petrol engine",
    "crdi": "diesel engine",
    "ivt": "automatic gearbox",
    "dct": "dual-clutch automatic",
    "7-speed dct": "seven-speed dual-clutch automatic",
    "adas": "driver-assistance features",
    "level 2 adas": "advanced driver-assistance features",
    "smartsense": "Hyundai's driver-assistance package",
    "esc": "electronic stability control",
    "vsm": "stability management",
    "hac": "hill-start assist",
    "tpms": "tyre-pressure warning",
    "epb": "electronic parking brake",
    "isofix": "child-seat mounts",
    "nvh": "noise and vibration",
    "kerb weight": "weight",
    "parametric grille": "front grille",
    "quad-beam": "four-lamp",
}
TECHNICAL_REQUEST = re.compile(r"\b(technical|spec|specification|exact type|which type|what type of|engineering|details? of the (engine|suspension|gearbox))\b", re.I)

def find_jargon(text) -> list[str]           # blocklist keys present, longest first, case-insensitive, whole phrase
def substitute(text) -> tuple[str, list]     # replace mapped keys; returns (new_text, [(from, to)])
def allowed(term) -> bool                    # in COMMON_TERMS
```

2. Runtime system prompt, add verbatim: `"PLAIN LANGUAGE. The listener is an everyday buyer. Use ordinary words. The only technical terms you may use are: cc, hp, turbo, diesel, petrol, automatic, manual, dual clutch, airbags, sunroof, touchscreen, cruise control, alloy wheels, ground clearance, suspension, torque, gearbox, range, battery. Never use component or engineering names such as McPherson strut, torsion beam, GDi, IVT, ADAS, ESC, TPMS, NVH; say what kind of thing it is in plain words instead (a strut-type front suspension, an automatic gearbox, driver-assistance features). If the customer explicitly asks for the technical specification, you may give the exact term with its citation."`
3. `validate_decision`: after the row checks and before the word cap, if `settings.audience == "everyday"` and not `TECHNICAL_REQUEST.search(question)`: `text, subs = substitute(text)`; remaining `find_jargon(text)` hits (unmapped) → `reject("technical_term")` with feedback `"replace '<term>' with everyday words or drop the sentence"`, which flows into `_repair_composition` like other feedback. Record `plain_language_substitutions` on the result for observability and the session record.
4. Build side: `faq.run` applies `substitute` to FAQ answers for everyday demos and records substitutions; `author.JARGON` gains the blocklist keys as warnings (warnings only, as today).
5. `Learning.MD` entry: "Answers recited suspension component names" with the McPherson example, five whys (audience rule was instruction-only at runtime, no runtime blocklist, validator lexical on citations not register, repair had no register feedback, tests covered narration not answers).

**Acceptance (`runtime_plain_language_contract.py`, ≥12 groups).** McPherson sentence → substituted, citations kept; unmapped term → `technical_term` reject → repair feedback string; repaired sentence passes; explicit technical question → no substitution; allowlist terms untouched; substitution is whole-phrase (no "abs" inside "absolutely"); FAQ build substitution; audience `expert` bypass; word cap after substitution; result carries substitutions.

---

## WP7 — Check-ins never pause; 3-second listen after an answer

**Goal.** Narration flows through check-ins. After an answer the guide listens 3 seconds and continues on its own. Clarifications wait.

**Files.** `web/player/player.js` (`playFrom`, `waitFor` callers, `questionResult`, `holdConversation`, `resumeAfterQA`, `askAndListen`), `server/agents/author.py` (`validate` check-in rule, `AUTHOR_SYSTEM` check-in text), `server/agents/principles.py` (`AUTHOR_CRAFT` check-in text), `server/agents/plan.py` (goal brief text "whether a readiness check-in would be useful" → "whether a one-line closing statement is useful"), `docs/ARCHITECTURE_FLOW.md` gate row "Player check-in", `evals/player_focus_contract.cjs` and `evals/player_priority_revision_contract.cjs` (adjust), new groups in `web/player` contract HTML.

1. **Player.** In `playFrom`, after a slide's lines: if `checkin.text` exists, speak it and continue immediately; do not call `waitFor`; do not render the check-in chips. Keep `waitFor` for the guide's clarifying question (`next_interaction == "clarify"`), for the CTA flow and for the lead form.
2. After `questionResult` delivers an answer or a decline: `holdConversation(run, {suggested})` shows the chips as today **and** starts `POST_ANSWER_LISTEN_MS = 3000`. During the window the microphone stays open (voice mode) and the text field is focused. Speech onset (`onSpeechStart`), a typed character, or a chip click cancels the timer. On expiry call `resumeAfterQA()` with the filler `back_to_demo` only if a recorded clip exists, otherwise resume silently. Log `auto_resumed: true` and the window length on the turn record.
3. A clarifying question from the guide (`clarify`) behaves as today: wait for the answer, no timer.
4. Closing and CTA unchanged: the customer chooses.
5. **Author.** `checkin` becomes "one short closing statement for the stop, never a question"; `validate` rejects `?` in `checkin` (flip the current rule) and drops the `_CHECKIN_OPT_IN` warning. Existing scripts with question check-ins still play because the player no longer waits.
6. **Docs.** Gate row "Player check-in" → "narration never waits; answers hold 3 s then resume; clarifications wait". Handoff decision "Questions wait; yes means continue" → "The guide's clarifications wait; answers resume after 3 s of silence".

**Acceptance.** Player contract groups: slide with check-in text → next slide starts without a wait; answer → chips visible → 3000 ms fake clock → `resumeAfterQA` called once, `auto_resumed` logged; speech onset at 1200 ms cancels the timer and enters the question path; typed character cancels; clarification waits beyond 3 s; CTA still requires a click; interrupted line replays from its start after auto-resume. `speech_style_contract.py` updated for the check-in rule flip.

---

## WP8 — Voice mode toggle

**Goal.** One switch on the welcome screen decides the input mode for the whole demo.

**Files.** `web/player/player.js` (welcome screen builder, `startLive`, `mountPlayer` state, a mic button in the player bar, `sessionRecord`), `web/player/live-voice.js` (capture start/stop without reconnect), `server/runtime_live.py` (`mic.set` handling; store `input_mode` on the session), `web/player-ui.css`, `evals/live_voice_contract.mjs` (extend), `evals/player_focus_contract.cjs` (extend).

1. Welcome screen: add a switch "Voice mode" above the two buttons, default **on** when `bundle.runtime?.continuous_voice` is true and `?mute=1` is absent, otherwise off; caption "Talk to {guide}. You can also type at any time."
2. `S.voiceMode = switch.checked` at start. `startLive(capture = S.voiceMode)`: on → request the microphone once (`openCapture`) and keep it for the whole demo; off → connect the socket for streamed speech, never call `openCapture`, send `mic.set {enabled:false}`.
3. Player bar: a mic button showing the state; turning it on mid-demo is a user gesture and calls `openCapture` then; turning it off calls `stopCapture` (add to `LiveVoiceClient` if missing) without dropping the socket.
4. The typed input is always rendered, in both modes.
5. `sessionRecord` carries `input_mode: "voice"|"text"`; the server stores it and `runtime_metrics` uses it for the typed/realtime cohorts if it does not already.
6. Muted automation (`?mute=1`) behaves exactly as today.

**Acceptance.** `live_voice_contract.mjs`: off → `getUserMedia` never called, socket connected, streamed speech plays; on → `getUserMedia` once, capture survives three turns; mid-demo on/off toggles capture without reconnect; `?mute=1` unchanged. Player contract: switch rendered with the correct default; `input_mode` in the saved record.

---

## WP9 — Docs, decisions, Learning, and the one authorized paid Read

1. `Handoff.MD`: new top section "Sales Trainer flow — <date>" with what changed, gates passed, and the branch; Decisions list gains D1–D8 in one line each; the line "sourced feature-led opening" is replaced, not deleted (keep history).
2. `PRD.md`: line 44 → the D1 wording; add D4, D5, D6, D7, D8 as one line each under "Approved runtime upgrade"; "Done for v1" mentions the playbook.
3. `docs/ARCHITECTURE_FLOW.md`: gate rows for Coach (playbook validator), Deck media/proxy, Runtime lookup (customer sites), Plain language, Player check-in, Voice mode. File index gains `coach.py`, `playbooks.py`, `plain_terms.py`.
4. Diagrams: `docs/mermaid/02-understand.mmd` (COACH, CVAL, PB nodes and edges; PLAN in: playbook), `03-align.mmd` (Story order panel → request_upload / revise plan), `04-build.mmd` (deck media/proxy), `05-runtime.mmd` and `08-runtime-graph.mmd` (customer sites, auto-lookup, plain-language check, 3 s resume, voice toggle). Run `python3 docs/build_viewer.py`.
5. `Learning.MD`: three 5-whys entries: roof-first opening (prompt named the example, no category knowledge, ranking untethered, pictures skewed, tests checked grounding not order); suspension jargon (WP6); check-in pause (question-first cadence, wait gate, no post-answer timer).
6. `Loop.MD`: list the new free contracts and their counts; Loop status stays off.
7. `refine.MD`: mark P1, P3, P4, P5, P6, P7 and the WP5–WP8 items as implemented with commit hashes.
8. **Paid Read (only if the next line says authorized).** Authorization: `[Anand to write: authorized | not yet]`. Cap: `[Anand to write, e.g. $1.00]`. Procedure: copy `data/demos/dm_41513908` to a new id (new `demo.json` id and name "CRETA v9 trial"), delete `plan.json`, `script.json`, `deck.json`, `faq.json`, `rehearsal.json`, `bundle.json`, `visual-audit.json` and audio in the copy, keep `understanding.json` and `knowledge/`, set `settings.faq_questions = 3` and `rehearsal_questions = 0` in the copy, then run a `revise` from `coach` with real providers at the current `MODEL_TIER`. Stop at Align. Do not render voice. Record cost from `usage.jsonl`, and save `playbook.json`, `plan.json`, `script.json` under `output/sales-trainer-trial-<date>/` with SHA-256s. Report: first spoken line, segment order with kinds, USPs, gaps raised, word budgets planned vs estimated, validator issues. If the cap is exceeded, abort and report.

---

## Order of work and checkpoints

WP1 → WP2 → WP3 → WP4 → WP6 → WP7 → WP8 → WP5 → WP9. Commit after each. If a gate fails, fix before moving on; never skip a gate. If a decision above cannot be implemented as written, stop and write the exact conflict in `refine.MD` under "Questions for Anand" instead of choosing a different design.

## Appendix — verified anchors (current line numbers after commit 0461609; verified by Agent A for build files and Agent B for run files)

Commands: `PY="MOCK_LLM=1 CLOUD_SYNC=0 PYTHONPATH=.:evals .venv/bin/python"`. Isolate every run with `DEMO_STUDIO_DATA=<tmp>` and `DEMO_STUDIO_GRAPH_DB=<tmp>/graph.sqlite` (see `server/config.py:17`). Gates: `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/qa_deck.py` (320/320), `MOCK_LLM=1 .venv/bin/python evals/qa_accept.py` (24/24), `MOCK_LLM=1 .venv/bin/python evals/smoke_mock.py` (two phases, 45 asserts).

### Build side (WP1–WP4)

| Item | File | Symbol | Line |
|---|---|---|---|
| Graph nodes / edges | server/graph.py | `build_graph()` nodes 259–272, edges 273–283 (`understand→plan` 274) | 259 |
| Routing | server/graph.py | `router` 48 · `after_plan` 215 · `after_author` 222 (attached to the deck node) · `after_faq` 252 · `after_voice` 245 | |
| Node wrappers | server/graph.py | `understand` 62 · `plan` 78 · `align_enter` 90 · `align_wait` 109 · `author` 145 · `deck` 160 · `voice` 173 · `rehearsal` 185 · `bundle` 193 · `finish` 201 · `faq` 232 | |
| Entry points | server/graph.py | `start_read` 364 · `start_build` 372 (six approvals 373–374) · `start_revise` 384 · `handle_message` 396 | |
| Stage dispatch | server/orchestrator.py | `_run_stage()` output-file map 148, dispatch chain 154–170, `usage.current_stage.set` 141–142 | 148 |
| Staleness / cards | server/orchestrator.py | `DOWNSTREAM` 19–28 · `invalidate()` 86 · `changed_cards()` 118–137 · `apply_actions` revise `order` dict 341 | |
| Stage constants | server/store.py | `STAGES` 27 · `CARDS` 28 · `new_demo()` 84 (stages 98, approvals 99, `pitch_minutes` 106) | |
| Run-log | server/runlog.py | `_REPORTS` 332 · `stage_report()` 335 (`_REPORTS[stage]` 345) · input rows 137–157 · iterates `store.STAGES` 384 | |
| Revise whitelists | server/app.py 915 · orchestrator.py 341 · schemas.py `AlignAction.stage` 552 | three copies | |
| Progress UI | web/studio/align.js | `restoreProgress()` 65–67 iterates `demo.stages`; no hard-coded stage list | |
| Plan schema | server/schemas.py | `SegmentPlan` 231–241 (`goal` 235) · `Plan` 297–313 (`usps` 304) · `USP` 213 · `VisualGap` 271 | |
| Plan run | server/agents/plan.py | `run()` 230 · approved filter 241 · model call 274 · unknown-id drop 288–294 · role forcing 300–307 · role sort 308–309 · write 325 | |
| PLAN_SYSTEM bullets | server/agents/plan.py | constant 16–107 · usps 40–49 (ranking 42) · intro 55–56 · outcome 57 · proof "strongest supported standout feature first… Avoid a fixed exterior-to-engine checklist" 58–60 · goal brief 64–73 · visuals 80–85 · everyday-buyer sunroof example 91–94 | |
| PITCH_SHAPE | server/agents/principles.py | constant 174 · STEP 1 182–184 · STEP 2 185–187 ("cabin experience" 186) · STEP 3 188–190 · STEP 4 191–195 ("exterior-to-engine checklist" 192–193) · STEPS 5–7 196–202 | |
| Other principles | server/agents/principles.py | `PRINCIPLES` 96 · `EVIDENCE_RULES` 61 · `CUSTOMER_STATES` 115 · `PROOF_BLOCK` 134 · `fact_context` 85 · `AUDIENCE["everyday"]` 207–216 · `audience_instruction` 223 · `language_instruction` 167 | |
| Author | server/agents/author.py | `AUTHOR_SYSTEM` 14 (intro rules 39–41, rule 6 55–65 with sunroof example 61–62 and "Show standout features early" 57–58, overview 76–78) · formatted 382 · `run()` 344 · `LIMITS` 103 · `WPS` 104 · `CLOSING_LIMIT` 105 · `ROUTE_LIMIT` 106 · `JARGON` 109 · `validate()` word check 206–207, opening 115 at 214, closing 222, route 228, overview 235, jargon warnings 148–156 · `timeline()` 259 (called 418) · `split_long_batches()` 293 (called 415) | |
| Deck | server/agents/deck.py | constants 27–32 (`PART_CONFIDENCE` 30) · `choose_image(seg, cat, script_refs, hero_id)` 103 · `_candidates` 136 · `place_callouts(slide, image)` 146 · `derive_callouts` 176 · `clean_callouts` 211 · `_ask_model` 231 · `apply_overrides` 252 · `slides_with_script` 296 · `build()` 334 (images 346, `pick_hero` 349–350, segment loop 374–379, `refs` image-only 379, `choose_image` 380, `place_callouts` 467, `apply_overrides` 470, `hero_image` 474) · `slide_for` 511 · `route_for` 546 | |
| Slide schema | server/schemas.py | `Callout` 408–418 · `Slide` 424–440 (`kind` 427) · `Deck` 446 | |
| Visuals | server/agents/visuals.py | `NON_VISUAL_FACT` 44 · `part_names` 79 · `part_boxes` 91 · `pick_hero` 98 · `_score` 139 · `align()` 271 (batches of 12 at 216, `coverage == "full"` 323, rules fallback 340/350, audit write 373) · `build_map` 389 | |
| Bundle hero | server/agents/bundle.py | `pick_hero` again 150 · `hero_image` 177 | |
| Speech style | server/agents/speech_style.py | `normalize` 17 · `prepare` 31 | |
| Mock | server/llm/mock.py | `_fake_value` 14 (fact_ids 15–16, Literal `prefer` 22, list sizes 28, role mix 38–39, name heuristics 59–80) · `fake_dict` 83 · `fake` 90 · dispatch `claude.py` 101/164/240, `gemini.py` 113/143 | |
| Build evals | evals/ | `qa_deck.py` (folds provider/customer/pitch_grounding/summary/qa_policy contracts) · `qa_accept.py` · `smoke_mock.py` · `narrative_roles_contract.py` 6 groups · `generation_contract.py` 44 · `speech_style_contract.py` 27 · `align_review_contract.py` 42 · `voice_lock_contract.py` 27 | |

### Run side (WP5–WP8)

| Item | File | Symbol | Line |
|---|---|---|---|
| Welcome screen | web/player/player.js | `startBtn` builder 1484 · `mutedByDefault` 61 (`S.muted` 66) · `startLive(capture = !mutedByDefault)` 234–239 (sets `S.inputMode`) · `createLive()` 191 (`onSpeechStart` 199–202, `onTranscript` 212) | |
| Typed inputs | web/player/player.js | dock `.pl-reply` 157 · intake `el.inText` 164 · drawer `.composer` 177 · `acceptTypedAnswer()` 254 (`via:"typed"` 257) · `preferTyping` 251 | |
| Mic control | web/player/player.js | `micTap()` 948–949 · `setMicUI()` 637 · `intakeMic()` 1202 · `toggleMute()` 270 (output only) | |
| Live client API | web/player/live-voice.js | `connect` 24 · `startCapture` 55 · `openCapture` 64 · `stopCapture` 103 · `speechStart` 112 · `interrupt` 178 · `ask` 181 · `speak` 189 · `cancelAudio` 227 · `setMuted` 228 · `close` 229 · `mic.set` sent 82/105 · constants 52/73/76/83/133/185/197, VAD 87–89 | |
| Server mic | server/runtime_live.py | `session.start` 134–139 · `mic.set` 140–144 · `start_mic()` 89–107 · `stop_mic()` 52–61 · `audio.input` 145–149 | |
| Mode persistence | player.js `turn.input_source = turn.via` 1021 · `sessionRecord()` 1350–1354 · runtime_state `checkpoint()` keys 173 · `runtime_metrics.py:46` reads `input_source` | | |
| Check-in path | web/player/player.js | `playFrom()` 837 → `speakPrompt()` 852 → chips 853–854 → `waitFor(chips)` 855 → "Good — moving on." 856 → `playDeeper()` 867 · `interpretReply()` 662 · `waitFor()` 705–716 (`listenSecs` 10000 at 708) · `holdConversation()` 959–973 (waits indefinitely) · `askAndListen()` 720 · `waitForLineQuestion()` 796 · `resumeAfterQA()` 1156 · `resumePlayback()` 1165 · `questionResult()` 974–975 (250 ms) · `questionAckKey()` 53 | |
| Pitch waits | web/player/player.js | 150/2500 ms 1287–1288 · 12000/60000 ms 1256/1266 · refine 769 · film cap 1435 | |
| Endpointing | server/llm/sarvam_stream.py | `silence_duration_ms=700, min_speech_duration_ms=180` 51 | |
| Profile / payload | web/player/player.js | `profileForServer()` 1147 · `questionPayload` 1023 (`history: slice(-8)`) | |
| Turn state | server/runtime_state.py | `RuntimeState` 90–116 · `TurnControl` 76–79 · `claim_turn()` 132 · `checkpoint()` 173 (path 175) · `previous_state()` 179 · `TurnDecision.answered` 58 | |
| Graph | server/runtime_graph.py | `run_turn()` merge 1555–1562 · `retrieve()` return 940 · `reason()` payload 992, `CUSTOMER_URLS` 996, style 1001–1002, `response_style_instructions` 1016, deterministic pre-model hook 978–987 · `_verification_urls()` 959 · `tools_node()` lookup 1044 · `validate_decision()` `reject` 1121–1124, codes 1128–1327 (`speech_markup` 1327), web attribution 1172–1175, word cap 1368–1370, `answered` fallbacks 1360/1373/1377 · repair gates 1388–1395, `left < 3.0` 1402, `validation_feedback` 1409, style reuse 1433, acceptance 1442–1457, `row_feedback` 1481–1482 | |
| Tools | server/runtime_tools.py | `supplied_urls()` 19–22 · `source_lookup()` 176 (allow-list 180–181) | |
| Pitch route | server/agents/pitch.py | `PITCH_SYSTEM` rule 38–40 · `previously_seen` 283 · `allow_revisit` 286 · role filter 287 · library row 289 · route validation 378–398 · `proof_route[:3]` 401 · defaults 402–405 · fallback 406–407 · `route =` 408 · `revisit_segment_ids` 462–463 | |
| Explore filter / player route | runtime_graph.py `explore()` 1505 (filter 1513–1515) · player.js `buildRoute()` 725 (fallback 729–732) · `queueRefinement()` 762 · `applyUpcomingPlan()` 776 | | |
| Run evals | evals/ | `runtime_graph_contract.py` (prints N/N; 130) · `runtime_conversation_contract.py` 18 tests · `runtime_repair_contract.py` 77 · `runtime_tools_replay_contract.py` 20 tests · `live_voice_contract.mjs` 56 (`node`) · `live_transport_contract.py` 9 · `player_focus_contract.cjs` 12 (`node`) · `player_priority_revision_contract.cjs` 11 (`node`) · `pitch_priority_revision_contract.py` 7 · `explore_cancellation_contract.py` 10 · `player_contract.html` served by `player_browser.py` on 8892 · `live_player_browser.py` against a `MOCK_LLM=1` server on 8897 with `?mute=1` | |
