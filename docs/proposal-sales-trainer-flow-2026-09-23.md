# Proposal — a Sales Trainer stage before the planner (23 September 2026)

**Status: proposal only. No code changed.** It needs three separate approvals from Anand: (1) the decision reversal in §5, (2) the architecture delta in §6, and (3) one paid Read on Creta to judge real model output (§8). Evidence is from Agent A (Creta trace) and Agent B (cross-demo pattern, runtime constraints), spot-checked by the Orchestrator against the working tree at `ba448ff`.

> **Line numbers:** taken at commit `ba448ff`. Commit `0461609` (23 September, code-study comments) shifted most lines in `server/graph.py`, `orchestrator.py`, `store.py`, `schemas.py`, the build agents and `web/player/player.js`. Use the function names; the numbers are approximate after that commit.


---

## 1. The design calls, with what was rejected

| # | Decision | Rejected alternative | Why |
|---|---|---|---|
| 1 | **Add a Coach stage (the sales trainer) between Understand and Plan.** It writes `playbook.json`: the category's buyer evaluation order, each registry fact classed as fundamental / differentiator / delighter / hygiene / ownership, the three USPs, objections, and evidence gaps. | Fold the sales-trainer role into the planner prompt | The planner is already the overloaded stage: 181 fact rows, 89 unknowns, 12 images and a 100-line prompt in one call. The cross-demo evidence (§2) shows its opening choice drifts with how the product is framed in Sources. A separate, small, reviewable artifact makes the story order auditable. |
| 2 | **The playbook is binding on the planner and checked by code**: segment order follows the playbook, every must-cover stop appears, USP ids match. | Advisory notes to the planner | `plan.notes` is already discarded by the author today. Advice that cannot be validated is not a control. |
| 3 | **A small versioned category library seeds the Coach** (compact SUV, premium SUV, EV scooter, generic). The Coach adapts it to the product's actual evidence and marks the source `library` or `inferred`. | LLM-only playbook from scratch | Order must be reproducible across builds of the same category. The library is the sales-training content; the model's job is to map it to this product's evidence and find the gaps. |
| 4 | **Review the playbook inside the existing Script card** as a "Story order" panel: drag-reorder stops, see the fundamental/delighter label, see the gap list. An edit triggers the existing `revise plan` path. | A seventh Align card | "Build requires six reviewed approvals" is an invariant wired through `store.CARDS`, the build gate, `changed_cards`, `align.js` and the docs. Not worth touching for v1. |
| 5 | **At runtime, pin at most one fundamental stop to the front of the Explore route, at initial planning only.** Refinements and revisits keep today's rules. | Fixed full order at runtime | Explore's buyer-signal ordering and the CR47 revisit path are working, tested behaviour. Pinning one stop keeps the buyer's stated priority within the first 40 seconds. |
| 6 | **Fundamentals are spoken through the translation ladder, not as specs.** The 4 September rules stand: no decision frame and no digits in the first spoken line. | Relax the jargon and number rules to let "1.5 turbo, 160 PS" open the demo | That is the opening Anand rejected on 4 September, and Loop eval 27 exists to catch it. "A turbo petrol option, a raised SUV stance, a suspension set up for rough roads" is a fundamentals opening with no digits. |
| 7 | **Evidence gaps become upload requests**, using the existing Align `request_upload` action. | Let the Coach fill gaps from general knowledge | "No citation, no claim." A category playbook that needs ground clearance and the registry has no such fact must say so and ask for the spec sheet. |

---

## 2. What the evidence says

**The Creta opening, traced** [Agent A]. "Look up at the panoramic roof: it's available on selected trims." is the intro segment's first line, typed by the session agent against `plan.segments[0].goal` and `plan.usps[0]`. The genuine model run opened the same way ("Look up through the available panoramic sunroof…"). The prompts themselves say so:

- [plan.py:56](../server/agents/plan.py:56): "strongest supported standout feature first … Avoid a fixed exterior-to-engine checklist."
- [plan.py:89](../server/agents/plan.py:89): "For everyday buyers, plan around a standout visible feature … a sunroof and ventilated front seats can lead a cabin-first route."
- [principles.py:185](../server/agents/principles.py:185): "A specific supported cabin experience beats a generic promise or a list."
- [principles.py:192](../server/agents/principles.py:192): "The route is a narrative, not a fixed exterior-to-engine checklist."
- [author.py:59](../server/agents/author.py:59): the preferred example is "Start with the cabin: selected variants offer a panoramic sunroof and ventilated front seats."
- `PRD.md:44` "Open with supported standout features in everyday language"; `Handoff.MD:43` "sourced feature-led opening".

No prompt or code carries category knowledge. `understanding.product.category` is "Compact SUV", and nothing reads it for ordering.

**The registry could support a fundamentals story, mostly** [Agent A]. Of 181 approved Creta facts, 142 are used nowhere. Engine has 28 facts, transmission 23, suspension 4, dimensions 13, airbags 6, ADAS 11, price 9, wheels 6. None of the engine, gearbox, suspension or price facts has a picture. Ground clearance, boot volume and fuel efficiency have **zero** facts. Eight of the twelve uploaded images are interior shots.

**It is systemic, not a Creta accident** [Agent B]. Across the other eleven demo folders, the first proof stop is a delighter in six and a fundamental in five. The split follows product framing, not model: every EV-scooter build and both "performance"-framed N Line builds lead with range or torque; every general SUV build leads with cabin or styling. In three of the four styling-first plans the first proof is not even the priority topic. Haiku, Opus and Gemini plans appear on both sides.

**History** (`Learning.MD`, 4 September). The demo once opened with a decision frame and a four-spec takeaway; Anand rejected it ("you don't know what the buyer wants"). The fix intended a "natural category discovery order" but encoded no category knowledge, and the later runtime upgrade (19 September) turned "natural order" into "standout feature first". Both lessons stand: no decision frame or spec list before the buyer speaks, and now, fundamentals before delighters.

---

## 3. The revised flow

```text
Sources → Read: Understand → Coach → Plan → Author → Deck → FAQ → Align → Build (unchanged)
```

### 3.1 Coach — the sales trainer (`server/agents/coach.py`, new)

- **Persona.** "You are a sales trainer for {category}. You have trained showroom staff on this product class. Decide what a good salesperson covers, in what order, for this product, from its approved evidence only."
- **Inputs.** `understanding.product` (name, category, audience), the approved registry rows (same `fact_context` rows, plus picture ids and origin tag per proposal P6), open unknowns, demo settings (audience, language), and the category library entry.
- **Output `playbook.json`** (new `Playbook` schema):
  - `category`, `category_source: library | inferred`
  - `stops[]` in evaluation order: `{id, label, kind: fundamental | differentiator | delighter | hygiene | ownership, why_here, fact_ids, picture_ids, must_cover: bool, gaps: [what is missing]}`
  - `usps[3]` chosen by the "tell a friend" test then evidence-checked, each with fact ids and no numbers in the name
  - `objections[]` with supported fact ids or `unknown`
  - `evidence_gaps[]` `{what, why_it_matters, suggested_source}`
- **Deterministic checks** (code, after the call): every `fact_ids` entry is an approved id; kinds are from the enum; the first stop is a fundamental; exactly three USPs; gaps name only items the library requires and the registry lacks; at least one picture id per must-cover stop or a picture gap.
- **Cost and cache.** One structured call on the build chain (Gemini first). Cached by registry hash plus library version, like the FAQ bank, so a revision that changes no fact does not re-run it.

### 3.2 Category library (`server/agents/playbooks.py`, new, versioned)

Compact SUV, India, everyday buyer:

| Stop | Kind | Covers |
|---|---|---|
| 1 Powertrain choices | fundamental | engine options, turbo, gearbox choice |
| 2 Stance and ride | fundamental | ground clearance, suspension, wheels and tyres |
| 3 Space and practicality | fundamental | seating, rear seat, boot |
| 4 Safety | fundamental | airbags, structure, ADAS |
| 5 Cabin and tech | differentiator | screens, climate, connected features |
| 6 Delighters | delighter | sunroof, ventilated seats, audio |
| 7 Ownership | ownership | price, warranty, efficiency, service |

EV scooter: range, charging, running cost, battery life, ride, features, ownership. Premium SUV: powertrain and drive, ride and refinement, safety, cabin, tech, ownership. Generic: the Coach infers and flags `inferred` for review.

### 3.3 Planner changes (`plan.py`)

- The playbook is inlined as `PLAYBOOK` and the prompt says: "Segments follow PLAYBOOK.stops in order. One proof segment per must-cover stop. USPs are PLAYBOOK.usps. Do not reorder or skip; put a stop with no evidence in `visual_gaps` or `deeper`, never invent it."
- Delete the ordering rules the Coach now owns: "strongest supported standout feature first" and "Avoid a fixed exterior-to-engine checklist" ([plan.py:56](../server/agents/plan.py:56)), the sunroof worked example ([plan.py:89](../server/agents/plan.py:89)), and the matching lines in `PITCH_SHAPE` steps 2 and 4 ([principles.py:185](../server/agents/principles.py:185), [principles.py:192](../server/agents/principles.py:192)).
- Keep: the three-part `goal` brief, the everyday-audience rule, "no decision frame, no spec list in the intro".
- New field `SegmentPlan.fundamental: bool` (default false) set from the stop kind; new post-check: proof segments sorted by playbook stop index, and every must-cover stop present.

### 3.4 Author changes (`author.py`)

None structural. Remove the sunroof example at [author.py:59](../server/agents/author.py:59). Apply the audit's openings rule: open on the thing itself or the place the buyer would stand, never on a signpost or a bare spec. The intro brief now comes from stop 1, so the opening is the category's fundamentals in everyday words.

### 3.5 Deck, bundle, runtime, player

- `Slide.fundamental` carried from the segment ([deck.py:327](../server/agents/deck.py:327), [bundle.py:56](../server/agents/bundle.py:56), [bundle.py:86](../server/agents/bundle.py:86)).
- Pitch library row gains the flag ([pitch.py:289](../server/agents/pitch.py:289)); at initial planning the first flagged unseen proof segment is hoisted to the front of `proof_route` before the `[:3]` slice at [pitch.py:401](../server/agents/pitch.py:401) and in the fallback at [pitch.py:407](../server/agents/pitch.py:407). Refinements (`refine=true`) and revisits are untouched, so CR47 behaviour is preserved.
- Player fallback route mirrors the hoist at [player.js:489](../web/player/player.js:489).
- The overview stays author-written and cited, 23–28 words, and now describes stop 1.

### 3.6 Align

The Script card gets a "Story order" panel above the segments: the playbook stops with kind labels, drag to reorder, and the gap list with an "Ask for this source" button that fires `request_upload`. Saving a changed order writes `playbook-overrides.json` and triggers `revise plan`, which regenerates plan and script and resets the script and visuals approvals through the existing `changed_cards` path.

### 3.7 Evals

Free, offline: playbook validator contract (order, enum, USP count, gap rule), planner order contract (segments follow stops, must-cover present), deck fixture with the `fundamental` flag, pitch hoist contract (initial plan hoists one, refine does not, seen filter wins), player fallback contract, and Loop eval 27 retained (first spoken line has no digits and no decision framing). Paid, once, on authorization: a real Read of Creta (Coach + Plan + Author on Gemini) judged on the model's own output, not a hand-authored script.

---

## 4. Worked example — Creta under the compact-SUV playbook

| Stop | Evidence available today | Picture | Gap the Coach must raise |
|---|---|---|---|
| 1 Powertrain choices | three engines F081, turbo F230–F232, gearboxes F225 / F229 / F233 | none | engine bay or side-profile photo |
| 2 Stance and ride | suspension F234 / F235, wheels F049 / F074, tyres F249 / F250 | wheels only | **ground clearance: no fact**; spec sheet needed |
| 3 Space | seating F032, split seat F096, recline F097 | im06, im08 | **boot litres: no fact** |
| 4 Safety | six airbags F237, ADAS F240, F153, F154 | ADAS im-refs exist | none |
| 5 Cabin and tech | screens, climate facts (F159, F162, F165) | im03–im05 | none |
| 6 Delighters | panoramic roof F247, ventilated seats F063, Bose | im01, im05 | none |
| 7 Ownership | price F031, extended warranty F245 | none | **fuel efficiency: no fact**; standard warranty |

What the buyer would hear first, illustratively and subject to the real Author and validator: an intro on the turbo petrol option and the choice of gearbox in everyday words, no figures; the outcome segment naming three USPs led by a fundamental; then Explore plays stop 1 pinned, the buyer's stated priority, one more stop, features, establish. The panoramic roof moves to stop 6 and stays in the route when the buyer's words point at the cabin.

---

## 5. Decision reversal to log (needs Anand's approval)

| Where | Today | Proposed |
|---|---|---|
| `PRD.md:44` | "Open with supported standout features in everyday language" | "Open with the category's fundamentals in everyday language, in the reviewed playbook order; delighters after fundamentals; no decision frame and no digits in the first spoken line" |
| `Handoff.MD` Decisions | "sourced feature-led opening" | "playbook-led opening; the Coach owns story order and coverage, the planner owns evidence and pictures, the author owns speech" |
| [plan.py:56](../server/agents/plan.py:56), [principles.py:192](../server/agents/principles.py:192) | "not a fixed exterior-to-engine checklist" | "ordered by the playbook, spoken as a walk" |
| [plan.py:89](../server/agents/plan.py:89), [author.py:59](../server/agents/author.py:59) | sunroof and ventilated seats as the worked opening | removed |

The 4 September decision (no decision frame, no spec list before the buyer speaks) is **not** reversed.

---

## 6. Delta against diagram 02 (build)

New agent node between `UND` and `PLAN`: `COACH["Category playbook: evaluation order, fact classes, USPs, gaps [AGENT · configured text tier · coach.py] in: product, approved registry + picture ids, unknowns, category library · out: Playbook schema"]`, a function node `CVAL["order, enum, USP count, gap rule [FUNCTION · coach.run]"]`, a data node `PB["playbook.json [DATA]"]`, and a new edge `PB → PLAN`. `PLAN`'s label gains "in: playbook (binding)"; `PVAL` gains "segments follow playbook stops; must-cover present". Diagram 03 (Align) gains the Story order panel on the Script card with edges to `request_upload` and `revise plan`. Diagram 05 gains the one-stop hoist in `plan_pitch`. `docs/mermaid/02-understand.mmd`, `03-align.mmd`, `05-runtime.mmd` and the viewer are updated in the same change.

---

## 7. Cost and risk

- One extra structured call per Read on the build chain, cached by registry hash and library version. Comparable to the FAQ stage's cheapest call.
- Wrong category from Understand: the panel shows `category` and `category_source`; the reviewer corrects it and the Coach re-runs.
- Over-pinning: at most one stop is pinned, only on the initial plan.
- Missing evidence blocks a fundamentals story: the Coach surfaces the gap as an upload request; nothing is invented. For Creta that means asking for the spec sheet page with ground clearance, boot volume and efficiency, and an exterior or engine-bay photo.

---

## 8. Order of work

1. `Playbook` schema, category library, `coach.py` with mock provider, validator contract.
2. Planner prompt edits, `fundamental` flag, order validator, mock Read passes end to end.
3. Deck, bundle, pitch hoist, player fallback, contracts.
4. Align Story order panel, `playbook-overrides.json`, `request_upload` wiring.
5. Free gates: deck, acceptance, smoke, new contracts, Loop eval 27.
6. One authorized paid Read on Creta; judge the model's plan, script and opening.
7. Log the decision in `Handoff.MD` and `PRD.md`; update diagrams 02, 03, 05.
