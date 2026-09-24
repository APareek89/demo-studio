# Script generation experiment — 24 September 2026

This is an unmerged experiment on `codex/crack-the-script`, based on tested release `582ae1a` in a separate worktree. It does not change the running app or AWS release. Anand explicitly chose the current release over `slides-v1`, existing validation over a special PS exemption, the existing duration margin over a tighter three-minute estimate, and embedded PDF-picture extraction within Understand.

## What changed

Seven prompt constants changed. [The exact before/after diff](prompt-changes.diff) records every changed line; no prompt marked protected in the task was rewritten.

- `COACH_SYSTEM`: gives each stop an ordinary situation, supported choice and handoff; requires the supplied stop identities/order; reputation is evidence-dependent. Removed the contradictory instruction to move the emotional delighter immediately after fundamentals.
- `PLAN_SYSTEM`: allocates three powertrain batches for a three-minute compact-SUV tour and at most two per other stop, including supplemental detail; assigns exact evidence/trim scope and literal subjects, with one pictured subject per main batch; reserves a distinct first-fundamental detail for the runtime overview; final closing owns both closing statements.
- `AUTHOR_SYSTEM`: asks for complete 26–33-word main thoughts, varied independent openings and a handoff to the actual next subject. Clarifies that prepared lines split into separate delivery batches. Intro begins with a fact; the overview does not repeat a guided claim. Clause-level citation guidance includes handoffs; counted-component wording preserves whether parts are included. The final polish briefs ordinary actions and buying choices, first offered trim before higher-trim examples, varied grammatical openings and handoffs that explain a connection rather than announcing the next item. Eligibility restrictions retain their duration/package scope; a picture of one physical option cannot illustrate its opposite.
- `AUTHOR_CRAFT`: makes the ordinary use/choice, source support and connected thought the writing unit while preserving the existing role and evidence boundaries.
- `TRANSLATION_LADDER`: adds worked examples for each rung and chooses a useful supported connection instead of stopping at a picture description whenever any picture exists. Retains full technical quantities in deeper detail and never invents a result.
- `PITCH_SHAPE`: makes the two-statement final close and empty segment checkins consistent throughout the prompt; supplemental features develop unused useful detail.
- `AUDIENCE` (everyday): connects a supported function or choice to ordinary use while keeping the complete quantity available deeper and preserving source conditions.

`SIGNPOSTS`, `CUSTOMER_STATES`, `TRUTH_RULES`, `EVIDENCE_RULES` and `PRINCIPLES` are unchanged. AST comparison also verifies every Author/Planner/principles function unchanged; schema, graph, category-library and runtime-graph file hashes match the baseline. The original claim, number, jargon, truth-kind, persona, CTA, approval and duration checks remain active.

### Prohibition-to-instruction wording count

This reproducible lexical count splits paragraphs/bullets and sentence boundaries, joins wrapped lines, and classifies units containing `no|not|never|don't|cannot|can't|without|only|mustn't` as prohibition-bearing. Mixed units count in that group. Other units are counted as the other instruction group. It measures wording, not semantic compliance; positive qualifications can also contain these words. [Every counted unit is retained](prompt-counts.json).

| Constant | Before: prohibition-bearing / other | After: prohibition-bearing / other |
|---|---:|---:|
| Coach |14 /16|18 /33|
| Planner |48 /46|59 /70|
| Author |50 /52|75 /76|
| Author craft |16 /13|16 /16|
| Translation ladder |11 /9|16 /13|
| Pitch shape |13 /11|9 /18|
| Audience |8 /7|9 /8|
| Total |160 /154|202 /234|

The ratio changes from 1.04 to 0.86. Positive guidance increased; the absolute number of prohibition-bearing units did not fall. Some local prompt sections remain verbose.

### Approved code changes

The formatted Coach prompt now participates in its cache identity. Changing guidance regenerates once; unchanged inputs reuse the playbook without altering evidence.

PDF pictures are extracted within Understand and sent through existing image tagging and visual auditing. The parent PDF remains the fact source. Normalized pixel hashes and parent revision determine stable image identities; ordinary upload IDs remain unchanged. Parent exclusion, deletion or revision holds derived media out of catalogues, all-language line visuals, slide media, labels and fact/image mappings. Sources shows the uploaded PDF rather than dozens of child uploads; Visuals still reviews its pictures. Timeout-truncated extraction retries on a later Read; completed caches reuse their assets.

Limits:96 unique pictures,48MiB combined,8MiB per image,12 million pixels,2048px normalized edge,100 pages,256 candidates,10 PDFs and a cooperative30-second budget. The initial48-picture cap missed airbag, folded-seat, petrol-engine and climate pictures that actually exist in the PDF;64 still missed two. At96, this PDF yields all95 pictures,26,467,885 bytes, in6.001seconds through mocked Understand. This can add up to eight image-tagging batches; no paid cost/latency measurement is claimed. Decoding/parsing is not isolated behind a hard process deadline.

Independent review reproduced and fixed two PDF integration defects: stale child images could escape the parent exclusion through saved slide/line paths; interrupted extraction could remain permanently cached. Regression coverage is in `evals/pdf_images_contract.py`.

A third code defect appeared in exact script replay: when pixel inspection was unavailable, metadata matching and an unused-picture diversity pass replaced correct Author refs, including deliberate no-picture choices. The fallback now retains the validated draft and records proposals only. The real pixel auditor, its completeness checks and full-coverage rejection remain unchanged. The new visual-alignment regression improves from11/25 to25/25; the code-only06 replay uses byte-identical05 responses to prove this change separately from writing quality.

## How to test it

All verification uses `MOCK_LLM=1`, temporary `DEMO_STUDIO_DATA` and `DEMO_STUDIO_GRAPH_DB`, mocked providers and blocked sockets. No paid model, voice or web call was made. Protected demo `dm_41513908`, port8896, the original app tree and AWS were not used for mutation.

[The exact free-gate runner](run_free_gates.py) takes `REPO OUTPUT_DIR SUITE...` arguments, creates temporary isolated storage per suite and blocks socket connect/sendto plus DNS resolution. Its Python path is the existing local app virtualenv. Run it with suite names from [the receipt](gates.json); no server, keys or paid calls are needed.

Before: deck380/380, acceptance24/24, smoke3/3. After: [25 actual suites,1,069 reported checks/groups/phases](gates.json), with overlapping coverage. The60 provider checks ran inside deck380; importing the provider-contract module alone is not a separate test run.

| Gate | Count |
|---|---:|
| qa_deck / qa_accept / smoke |380/380 ·24/24 ·3/3|
| Coach / Planner-playbook / narrative roles |27/27 ·19/19 ·14/14|
| New script prompts / new PDF images / visual fallback |40/40 ·58/58 ·25/25|
| Generation / speech style |55/55 ·30/30|
| Narration preparation / recovery / automatic |35/35 ·18/18 ·16/16|
| Minimum narration |25/25|
| Source / upload stream / upload retry |39/39 ·19/19 ·12/12|
| Deck media / media Align / Studio feedback |60/60 ·15/15 ·29/29|
| FAQ review / voice lock / customer |42/42 ·27/27 ·29/29|
| Full mock release journey |28/28|

The release journey exercises Read → human-review APIs → Build/Voice/Bundle → runtime and rehearsal with real synthetic WAV fixtures. Its194.22seconds verifies the unchanged publication mechanics, **not the acoustic duration of the new sample**. Generation's55 cases are the standalone worktree corpus; optional original-tree stored-demo fixtures are absent and were not fetched.

Two existing tests pinned the old contradictory closing sentences verbatim. Their text expectations were updated and both suites rerun; rejection, grounding and interaction behavior checks were retained. Python compilation covers all18 touched Python files, including both archived QA harnesses; the changed JavaScript module passes syntax checking; all nine embedded Mermaid copies are regenerated and checked.

### Simulation evidence

The final factual fixture contains68 manually reviewed PDF facts and10 explicit unknowns. The earlier64-fact fixture omitted four exact engine/gearbox trim-table rows; these were recovered from the same uploaded PDF, preserving the original facts. [Table coverage review](engine-trim-coverage-review.md). Source quotes were checked on their cited pages. This is the shape Understand produces, not a claim that a live extraction model generated the fixture. The uploaded PDF is a compilation, including manufacturer material; its own disclaimer does not make the entire compilation an official Hyundai publication. [Source audit](source-review.md), [final provenance](final-source-provenance.json), [inspected image mapping](final-source-image-mapping.json) and [visual review](final-source-visual-review.md) preserve that distinction.

Each `iteration-*` folder contains the exact assembled system/content/schema requests, separate-stage responses, concise agent notes and any completed stage results; the incomplete03 Author replay is labelled explicitly. The manual fixture is not an exhaustive extraction: the PDF also contains overall length/width and suspension details not selected into it, and some visible rear vents/window shades are absent from its image tags. Their registry/catalogue gap labels are simulation coverage limits, not evidence that the PDF lacks those facts or pixels. The [exact stage harness](stage_harness.py) captures requests, validates response schemas, restores only its own temporary stage inputs for repairs, and rejects a response if its request fingerprint changes. Stage code, validators, budget preparation and mock visual fallback ran normally. No final JSON was hand-edited to force a pass.

- **00 — baseline:** existing prompts on the reviewed PDF fixture; Coach reordered cabin/delighters; Author returned empty issues but6/16 batches met the target, four closing statements and several unrelated picture bindings. [Measured review](baseline-criteria-audit.md).
- **01 — first guideline draft:** Coach invented an extra front-seat-airflow stop; Planner inherited it. Author was deliberately not run on that flawed outline. This exposed the conflicting emotional-order instruction.
- **02 — first improved candidate, commit9070c06:** exact seven-stop spine;16/16 batches within26–33words (14 guided plus two alternative openings),495 prepared words, two closing statements and empty issues. The selected unvoiced route has404words, not495. Source pictures and handoffs still needed work. [Review](iteration-02-criteria-audit.md).
- **03 — source-corrected candidate:** uses the inspected48-picture catalogue from actual95-picture extraction, resolves remaining closing/continuation conflicts and reserves a distinct overview detail. Its first Author response was492words; the bounded repair supplied495. Before replay, semantic review found uncited engine handoffs and ambiguous speaker membership. The changed prompt correctly caused the harness to reject the old response fingerprint; this is not a completed normalized Author result. [Status](iteration-03/STATUS.md).
- **04 — clause-level citation guidance:** Coach and Planner requests were exactly identical to03 and their responses were explicitly reused. Author was generated fresh. This run remains useful intermediate evidence, but source review exposed missing trim-table rows in the manual fixture.
- **05 — complete table evidence:** adds four exact uploaded-table facts and briefs one literal pictured subject per batch. All three stage requests are regenerated from these inputs. The498-word draft passes actual Author validation; independent source review finds all48 spoken/deeper units grounded, but normalization corrupts22 visual references. [Pre-fix criteria](final-criteria-audit.md).
- **06 — preserve draft visual choices:** all05 requests and responses match exactly; this code-only replay removes fallback image substitution while preserving the same498-word speech and existing pixel gates. [Replay status](iteration-06/STATUS.md), [source audit and delta](final-source-audit.md). The further07 Author pass uses this same plan with more concrete action/choice and handoff guidance; no guard change is made.
- **07 — writing polish, not accepted:** identical Coach/Planner requests were reused; a fresh Author produced495 prepared words and empty issues. Root review caught a warranty restriction generalized beyond its seven-year scope; two mixed-option images also failed literal subject coverage. The independent source review corrected its initial lenient sign-off. [Corrected source audit](final07-source-audit.md), [criteria audit](final07-criteria-audit.md). The generated artifact remains unchanged as evidence.
- **08 — scope and physical-option fidelity:** a fresh independent Author receives the exact new runtime request with duration/package scope preservation and literal-option comparison guidance. Coach/Planner requests remain exactly identical to07 and their response bytes are explicitly reused. Source review confirms49/49 units preserved (29 images,20 deliberate none),500prepared words and empty issues. Warranty scope and both mixed-option picture defects are fixed. Strict style criteria still fail in catalogue/location openings, so this is an intermediate source-clean candidate. [Source audit](final08-source-audit.md), [criteria audit](final08-criteria-audit.md).

## What is still weak

The target's unsupported market reputation, loaded-climb assurance, quantified acceleration/mileage/capacity/clearance/safety/rival claims and inferred engine recommendations cannot be manufactured from this source. [Source review](source-review.md) names the exact gaps and material trim/engine/paid-option restrictions. The existing everyday validator still flags PS in main narration; complete160PS remains eligible for deeper answers, as Anand's override requires.

A495-word prepared inventory is about221seconds at the reference2.24words/second. The initial runtime chooses a measured qualifying route after recording; a pre-recording estimate is not proof of180seconds. The user expressly kept the margin rather than forcing the sample to an exact three-minute estimate.

Empty `issues` proves only the existing checks. Mock visual rules can propose unrelated pictures; they are not a completed pixel audit. Literal-picture claims, semantic entailment, consistency across live model runs and acoustic delivery need their own evidence. The production pixel audit and human Align checkpoint remain unchanged. No publication, merge or deployment is implied by this experiment.
