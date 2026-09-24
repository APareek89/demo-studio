# Reviewed revision audit — iteration11

Iteration11 is a **QA-driven revision through the existing Author path**, not a perfect fresh first pass. It fixes10's two flagged lines, returns `issues:[]`, and preserves **495 prepared words,16 compliant delivery batches,14 compliant guided lines,16 distinct batch first words, and two closing statements**. One concrete reference gap remains: the diesel main batch gives the SX Premium manual-only example, while first manual availability on E is still deeper.

The actual selected route has345 words across nine rendered batches and estimates181.58 seconds at the application's rate. No audio was recorded or measured. The retained495-word inventory and measured180-second publication gate must not be confused with an already verified recording.

Evidence: [saved Author artifact](iteration-11/artifacts/author.json), [effective native-repair response](iteration-11/calls/author-02.response.json), [review instruction](iteration-11/review-instruction.txt), [review provenance](iteration-11/review-provenance.json), [application-derived metrics](final11-metrics.json), and the separate [source audit](final11-source-audit.md). Application prompts remain those of10. Coach/Planner context is unchanged. The previous10 script was supplied unchanged as revision context; generated outputs were not hand-edited.

## Thirteen criteria

| # | Reference criterion | Actual11 evidence | Assessment |
|---|---|---|---|
|1|Open immediately with a product fact or standing.|The intro begins with CRETA's supported auto-hold function, then first automatic availability and standard fitment from King. No warm-up precedes the fact.|**Pass.**|
|2|One supported figure-free reputation sentence, without company statistics.|No reputation sentence, sales count, rank, tenure or awards narration appears. The supplied evidence does not support “one of the best in the market.”|**Strict positive criterion unmet; evidence-blocked difference.** The user's grounding override is preserved.|
|3|Powertrain first with three batches; other proof stops at most two.|Powertrain → stance and ride → space and practicality → safety → cabin and tech → delighters → ownership remains the proof order, with3,1,1,2,2,2,1 batches.|**Pass.**|
|4|Every delivery batch26–33 words.|16/16 rendered batches pass, as do14/14 guided lines. The alternative outcome is31 words split across11/7/13-word subject-specific lines, so15/18 individual main lines pass independently.|**Pass at delivery-batch level.** The shorter outcome lines are not counted as three compliant batches.|
|5|Connect features to ordinary situations or useful buyer choices.|Changing gears, selecting an automatic or matte finish, sharing space on a journey, taking a seat in E, choosing separate front temperatures, preparing remotely, warm-evening airflow, budgeting for a quote and stowing small items give the features a context. Written engine/trim and warranty choices are consequential decisions rather than isolated inventory. Some phrasing remains administrative.|**Substantially met under the reference-only direction.** This is a reasoned writing assessment, not an acoustic or persuasive-effect measurement.|
|6|Give exact first applicable trim and material restrictions.|Non-turbo manual E/automatic EX(O), automatic-only auto hold from S(O), the exact matte-black alloy set, airbags E, climate S(O), Alexa SX, ventilation SX Premium, roof EX(O), voice roof SX, and sliding King are specific. Diesel automatic's exact list begins EX(O), but its main line still describes the SX Premium manual-only exception; manual's first trim E remains deeper.|**One concrete main-route miss remains.** Replacing that higher-trim manual example with the source-supported E start can close it within the same budget. Other main claims are specific; banned vague-variant phrases are absent.|
|7|Vary openings without repeated first words, bare topic labels or stock transitions.|The16 distinct first words remain The, Changing, With, If, Opting, To, When, Take, Watching, Turn, Before, A, Looking, Budgeting, Stow and For. Most introduce a purpose, choice or action. “Looking upward” is a mild directional cue; “With non-turbo petrol” frames an engine choice. Ordinary shared imperative or prepositional grammar alone is not a repeated template.|**Mechanical uniqueness passes; practical variety improved.** Remaining register preferences are editorial, not another concrete evidence failure.|
|8|Turn each batch toward the next subject without bare-spec endings.|The chain moves through gearbox, engine, finish, space, occupants, assistance, temperature before driving, remote preparation, seats, overhead space, quote, storage, terms and choice. The ventilation handoff now says “the space overhead,” directing attention without asserting the unpictured glass-roof feature. The next roof line carries its own facts/picture.|**Functional continuity passes.** Some broad links remain, and the complete authored order is distinct from a shorter selected route.|
|9|At most two closing statements, no questions.|Checkins are empty. Final closing has21+23=44 words in exactly two statements. Dealer contact/quotation remains a requested next step, not a completed booking.|**Pass.**|
|10|Runtime overview23–28 words, no digits.|26 words, zero digits. It preserves the reserved auto-hold fact and availability exactly from10. Alternative intro/outcome speech is excluded from the guided count.|**Pass.**|
|11|No absent acceleration, economy, capacity, clearance, crash or rival figures.|No prohibited figure is asserted across49 units. Missing fuel-economy, boot-capacity and crash evidence remains unknown. Cited engine/tyre/screen/source-price/warranty quantities are distinct supported categories.160PS remains deeper under the unchanged everyday-language validator.|**Pass.**|
|12|Empty issues, local grounding and literal pictures.|`issues=[]`. The source-free decline no longer contains the uncited CLAIMISH token “certified”; it remains an explicit unknown with empty fact IDs and none visual. The ventilation handoff introduces no separate roof claim. All49 effective-response text/citation units and refs survive normalization, with25 image units and24 intentional none units. Manual source review remains separate from the rules fallback.|**Validator requirement passes; reviewed corrections address the known failures.** The literal reference demand for a picture on every line is not met: nonvisual policies/comparisons intentionally use none. No live pixel-provider pass is claimed.|
|13|Three-minute target with preserved495-word preparation margin.|Prepared inventory is495 words. The selected route is345 words/181.58 estimated seconds at1.9 words/s, or154.02 seconds at reference2.24. The full inventory is220.98 seconds at2.24. Recording must determine which complete reviewed stops the selector includes.|**Preparation passes; acoustic acceptance unverified.** Publication still requires180 measured seconds.|

This is not an “all thirteen green” claim. The first-trim main-route gap is actionable; unsupported reputation, deliberate none visuals and unmeasured audio are separate evidence or verification limits. No guardrail was weakened to convert those limits into a pass.

## Review and native repair provenance

The existing `author.run` revision interface received10's byte-unchanged saved script and a QA instruction for exactly two lines. The prompt constants, source registry, Coach and Planner context remained unchanged. The two narrative changes from10 to11 are:

1. The ventilation sentence retains the supported airflow, SX Premium start and seat picture. Its final clause changes from a separate glass-roof assertion to “Cabin choices extend from seats beneath you to the space overhead.” It stays30 words and hands to the following separately cited roof batch.
2. The deeper decline removes “certified” from “missing certified results.” It retains the unknown fuel-economy/crash evidence and official sources needed, with no fact added and no picture substituted. This removes the actual lexical trigger; the unchanged guard has no special can't/cannot exception.

All other47 narrative units match10 exactly. All49 citation arrays and49 complete visual objects match10. Therefore the changes did not introduce replacement citations or new image choices.

The first11 response carried delivery-split16 segments from the previous script. The existing stage requested native repair back to the PLAN's11 grouped stops: three engine lines grouped together, and the two-line safety, cabin and delighter stops regrouped. **No spoken text was added, removed or rewritten by that native repair.** Normal delivery splitting then produced16 rendered batches again. All49 texts are identical between11's first and second responses.

Metadata is not claimed to be universally identical. In particular, the existing validator recomputes the cleaned decline's `unverified` flag from true to false after its claim-pattern match is gone. The line still says the evidence is unknown and still has no fact IDs; this marker reset does not turn unknown evidence into a product fact. Generated line IDs, grouping/timing metadata and schema-default normalization are stage operations, not hidden prose edits.

## Exact inventory and route accounting

Application functions report **366 proof +27 features +32 establish +26 overview +44 closing =495 words**. Guided segment speech is425 words. Intro28 and outcome31 total59 alternative-opening words excluded from guided duration. Deeper contains28 lines and1,023 words, also excluded. Checkins are empty and the exact-text duplicate counter excludes zero lines.

Rendered batch lengths are **28,31,31,32,31,28,32,31,31,31,31,30,30,28,27,32**. All16 meet26–33. Each of14 guided batches is one complete compliant line; outcome's11/7/13-word lines make the individual main-line count18.

The actual selector returns nine rendered IDs: `engine-choices`, `engine-choices-2`, `engine-choices-3`, `wheels`, `shared-space`, `airbags-and-help`, `airbags-and-help-2`, `small-storage`, `terms`. Their275 words plus26 overview and44 closing total345. Cabin, delighters and quote remain available in preparation but are omitted from the provisional estimate-based route. The full-inventory estimate is260.53 seconds at1.9 words/s; the selected estimate is181.58 seconds. Both have `measured:false`.

Saved preparation is `ready`, `target_words:495`, `words:495`, `attempts:2`, `seconds:181.58`, `basis:estimated`. Its words describe preparation while its seconds describe the selected route. It is not evidence of a recorded three-minute demo.

## Before and after

| Measure | Baseline00 | Iteration10 | Reviewed11 |
|---|---:|---:|---:|
| Rendered batches / individual main lines |16/24|16/18|16/18|
| Rendered batches within26–33 words |6/16|16/16|16/16|
| Eligible guided lines within26–33 words |Not one per batch|14/14|14/14|
| All closing statements |4|2|2|
| Prepared words |495|495|495|
| Selected route words / app estimate |366 /192.63s|345 /181.58s|345 /181.58s|
| Runtime overview words |23|26|26|
| Deeper words excluded |1,057|1,024|1,023|
| Distinct batch first words |Not a final writing pass|16|16|
| Remaining validator issues |Historical baseline record|1|0|
| New acoustic measurement |No|No|No|

The goal-shaped weighting, smaller delivery batches, concise closing, concrete buyer choices and natural direction changes improve on the baseline. The final reviewed corrections show the existing review path can resolve a local unsupported handoff and guard-triggering wording without changing the validator. They do not establish perfect first-pass generation on future unseen documents.

## Verification boundary

The metrics use actual `author.words`, `narration.preparation_report` and `narration.default_route`, with MOCK_LLM=1, isolated DATA/GRAPH storage, and blocked DNS/connection/datagram methods. The artifact reports `rules_fallback`, null model and0 pixel-audited lines/images. Independent manual source/picture review is not a paid vision-model run.

Prompts/code are unchanged from the final10 code receipt: script prompts40/40, visual alignment25/25, speech style30/30, generation55/55, narrative roles14/14, deck380/380, acceptance24/24 and smoke3/3 all passed with zero outbound attempts. The consolidated ledger remains25 suites and1,069 reported checks, with overlap; repeated runs are not additional unique cases. This report does not claim a new11 code-suite run, measured narration, live-provider quality or AWS load validation.

No original application data, protected demo, AWS or port8896 was touched, and no application code, generated script or previous audit was edited for this review. Saved Author SHA-256: `fa30b50caa33768b126601960cd614b1631fe0d94dea84b57b85d4756c2b1c83`.
