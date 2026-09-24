# Iteration12 independent source delta audit

**Disposition: accepted for source entailment and literal picture binding in this isolated simulation.** This bounded review checks the one new diesel line against the uploaded source evidence and verifies exact preservation of the other 48 units previously reviewed in [iteration11](final11-source-audit.md). No further source, scope, quantity or picture defect was found. No generated JSON, prompts, code or source fixture was edited during this audit.

## Revised claim and source

Only `engine-choices-L2` changed from iteration11. Its 32-word text is now:

> If automatic gears matter, the diesel choices listed are EX(O), S(O), King, King Knight or Lounge Edition. Diesel manuals start at E; turbo petrol brings a different engine, gearbox and trim choice.

“Diesel manuals start at E” is supported by F067's diesel MT row on PDF page31. It identifies first availability without implying uninterrupted availability on every higher trim. The full diesel automatic set remains exactly that of F068: EX(O), S(O), King, King Knight and Lounge Edition. The source matrix retains the exceptions; the complete manual/automatic lists remain in the unchanged deeper line.

The unchanged local citations are F003/F008/F067/F068. The turbo clause remains generic engine/gearbox/trim selection guidance, not a new concrete turbo transmission or trim assignment. The unchanged image `im_pdf_5cd207807990f4eea283` is the previously inspected diesel-engine illustration. The revised first-availability detail therefore introduces no new pictured subject or visual mismatch.

This resolves iteration11's remaining main-route target-coverage omission. It replaces the higher-trim SX Premium example rather than adding padding or repeating it. The word count and first word are unchanged.

## Exact delta and normalization evidence

- **49/49** unit identities match iteration11. Exactly **1** narration text changes; the other **48/48** texts are identical.
- **49/49** citation arrays, complete visual objects, delivery objects and `unverified` values are unchanged from iteration11.
- Raw Author response to normalized artifact: **49/49** texts, citation arrays, visual objects, delivery objects and `unverified` values preserved, with no missing or extra unit.
- **25/25** image bindings and **24/24** intentional `none` bindings preserved. Intake questions and both closing statements are unchanged.
- The raw response contains 11 planned stops; existing delivery splitting yields 16 segments without speech changes.
- The actual isolated understanding's **68 facts and 10 unknowns** remain exactly equal to `final-source-v2`. No unknown became a fact.
- Actual native `issues`: **0**, from **1** Author call in this revision. Prepared narration: **495 words**; default route: **345 words**, **181.58 seconds estimated**, measured flag false.

Previous normalized artifact SHA256: `fa30b50caa33768b126601960cd614b1631fe0d94dea84b57b85d4756c2b1c83`.

Iteration12 raw response SHA256: `739bc3ff374b43f264ed695eeb888e3ac78dd40fc68d2f2d1050c5c494498f48`.

Iteration12 normalized artifact SHA256: `65d02611f783397ef161456523eccad359a18e81be7dc244afdb3c937f103fe0`.

## Provenance and limits

This result follows **two bounded QA-driven revisions through the existing Author previous-script/instruction path after fresh iteration10**: iteration11 corrected the seat-to-roof handoff and lexical decline wording; iteration12 corrected the main-route diesel first-availability omission. Both use the same iteration10 system prompt. The one-call result for iteration12 is not an unassisted perfect-first-pass claim.

This delta inherits iteration11's full source review and explicit limitations. Facts and image tags are a manually reviewed simulation fixture from the uploaded PDF and real extracted pictures, not a measurement of live Understand semantic extraction. Documented fixture omissions remain omissions of supplied registry coverage, not absent PDF evidence. Rules fallback was used; full provider pixel checking and acoustic quality were not tested. The estimated route duration is not a measured recording or proof that publication's measured-duration gate has passed.
