# Iteration04 — normalized Author replay, superseded for evidence completeness

Actual Coach → Planner → Author stage replay completed; the saved Author artifact has `issues=[]` and preparation status `ready`, with one writing attempt. Counts below use the app's actual `author.words`, `narration.preparation_report` and `narration.default_route` under MOCK_LLM=1, isolated storage and blocked sockets. No paid provider or voice was used.

| Measure | Baseline00 | Iteration02 | Iteration04 |
|---|---:|---:|---:|
| Rendered segments / complete main lines |16 /24|16 /16|16 /16|
| Main delivery batches within26–33words |6/16|16/16|16/16|
| Powertrain batches; other proof maximum |3;2|3;2|3;2|
| Intro / outcome words, excluded from guided duration |31 /37|30 /32|28 /32|
| Runtime overview words |23|23|27|
| Segment checkins / final closing statements |2 /2|0 /2|0 /2|
| Eligible main words + overview + closing |411+16 checkin+23+45|427+23+45|426+27+45|
| Full prepared inventory / eligible segments |495 /14|495 /14|498 /14|
| Selected default route words / rendered segments |366 /9|404 /11|345 /9|
| Default-route estimate at app1.9words/s |192.63s|212.63s|181.58s|
| Default-route arithmetic at reference2.24words/s |163.39s|180.36s|154.02s|
| Measured audio rows |0|0|0|

Iteration04's **498words are the full prepared inventory, not the default route**. Role counts are intro28, outcome32, proof367, features26 and establish33. The two final closing statements have22 and23words; the27-word runtime overview contains no digits. The full498-word inventory estimates262.11s at the app's1.9words/s, or222.32s at the brief's illustrative2.24rate. Neither estimate is a recording.

All16 persisted main batches have one complete line. Exact sizes in order: **28,32,30,30,30,27,33,32,32,32,32,31,30,28,26,33**. The first proof is powertrain with three30-word batches. Other proof groups are stance1, space1, safety2, cabin2, delighters2 and ownership1, in the existing library order. Every rendered-batch first word is distinct; this mechanical fact does not prove every opening is a buyer situation.

The selected route is `driving-choices`, `driving-choices-2`, `driving-choices-3`, `wheels`, `rear-space`, `occupants-and-assistance`, `occupants-and-assistance-2`, `front-storage`, `written-terms`. It omits cabin, delighters and ownership proofs because the unvoiced app estimate already reaches181.58s. The normal measured selector/publication gate is unchanged and must select sufficient recorded content after Voice; **this replay does not establish a measured three-minute sample**.

The structural reference criteria remain improved over baseline: product-fact intro, three powertrain batches, all26–33-word main batches, two final closing statements and a valid runtime-overview length. Later handoffs name the next subject more often, but qualitative craft is not scored as automatically passed. The unsupported market-reputation sentence remains omitted under the user's instruction to preserve grounding.

Two remaining problems justify iteration05: (1) the non-turbo/diesel batches still say “depending on trim” / “pairings dependent on trim”; subsequent source audit found exact pairings on PDF page31 missing from the simulation registry, so the next fixture must expose that existing source evidence; (2) roof and Bose audio share a main batch despite needing different literal pictures. The new generic Planner instruction assigns a different pictured subject its own available batch or deeper detail. Neither fix requires a validator, schema, category-order or duration change.

Visual audit is **`rules_fallback`, model null,0 lines and0 images pixel-audited**. Empty issues and real extracted image IDs are not a pixel-proof pass. A main roof/audio combination and other fallback bindings still need separate literal-subject review. Exact fact IDs and clause-level entailment require review against the cited registry, including openings and handoffs; this short status does not substitute for the final thirteen-criterion audit.

## Final05 prompt/code gate receipt, separate from pending narrative

The proposed05 wording has six green suites in `/tmp/demo-crack-script-20260924/final05-gates`: script prompts40/40, Planner/playbook19/19, speech style30/30, deck380/380, acceptance24/24, smoke3/3 (both phases plus on-demand rehearsal). Every suite reports zero outbound attempts. These are the same counts as their prior successful runs and do not add unique cases to the consolidated overlapping total. The latest68-fact source fixture, Coach/Planner/Author replay and final narrative assessment remain pending; no result is claimed for iteration05 here.
