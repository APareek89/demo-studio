# Iteration10 independent source audit

**Disposition: intermediate, not accepted.** One concrete feature handoff lacks its own supporting citation/picture coverage, and the actual native validator still reports one lexical decline warning after the genuine repair. Empty issues are not claimed. No generated JSON, code or prompts were edited during this review.

Reviewed all 49 units in the fresh first response against the frozen `final-source-v2` facts and inspected assets, then inspected the actual second response and normalized output. The units comprise the runtime overview, main/deeper narration and both closing statements.

## Two open findings

1. **Uncited second product feature in a pictured ventilation line — `seat-and-roof.lines[0]`.** The first sentence is supported by F037/F038: ventilated front seats from SX Premium and cool airflow through the cushions. Its handoff then says choosing cabin equipment includes “deciding on the glass roof overhead,” but its IDs remain only F037/F038. A glass roof is a concrete product feature, not merely an invitation to consider the next topic. Roof evidence such as F048 belongs with that assertion. The ventilation image `im_pdf_498ba48d46b3d2258714` also does not show the separate glass roof. Keep the line to the pictured seat-airflow subject with a genuinely generic transition, or separately cite and appropriately represent the added roof claim. The next roof line already provides the correct roof facts and picture.

2. **Native lexical guard still flags the uncited decline — `terms.deeper[1]` / normalized `terms-D2`.** The genuine repair changes “I cannot confirm” to “I can't confirm,” but leaves the sentence ending “those missing certified results.” The unchanged `CLAIMISH` pattern matches `certified` when `fact_ids` is empty, regardless of the decline's meaning. There is no apostrophe/decline recognizer in this check. The actual artifact therefore retains one issue: “terms deeper 2: states a figure or claim without a fact id …”. Semantically the line declines to confirm unavailable results; it does not invent a certification. Revise that truthful decline through the existing Author/review path so it avoids making a certification-sounding assertion. Do not add unrelated fact IDs or change the guard. Punctuation alone does not fix it.

## Prior findings resolved and remaining clauses reviewed

- The matrix-wide S(O) Knight automatic exclusion now cites F005/F006 plus F065–F068 and F016. All engine families are covered locally.
- Physical display dimensions have their own pictured dashboard line; the separate Bluelink service and seat-package discussion is nonvisual.
- The split-seat description is separate from the boot statement, which now has the actual boot picture.
- The paid up-to-seven-year petrol warranty restriction remains qualified on the main path and in deeper. No broad exclusion of every possible diesel warranty is implied.
- Exact petrol/diesel manual/automatic trim sets, SX/SX Premium exceptions, King-only turbo, technical quantities and dated—not live—offerings remain correct against their cited facts.
- The matte-black Knight alloy subject matches the source p8 picture/caption. Steel/alloy and tyre-size comparisons remain nonvisual. No invented ride, capacity, acceleration, ground-clearance, crash-rating or cooling result was found.
- Driver-assistance and camera/cruise scopes, Alexa prerequisites, phone adapter condition, Bose membership, puddle-lamp sides, dated price conflict and armrest scope remain intact. Contact preference is not completed contact or booking.
- Other explicit pictures match their stated subjects; the glass-roof handoff is the outstanding whole-line exception.

The diesel bridge says turbo petrol brings “a different engine, gearbox and trim choice.” This is general selection guidance, with the distinct engine supported by F003; it does not assign a concrete turbo transmission or trim rule in that clause. Missing F005/F006 there is not independently classified as a failure merely because the next subject is named. That differs from asserting the specific glass-roof feature in the ventilation line.

## Repair and preservation evidence

The second response changes only `terms.deeper[1]` narration text; other text, citation arrays and visual objects are unchanged. Default delivery/unverified fields are serialized as part of the actual repair response.

Comparing that repaired response with normalized output:

- **49/49** texts and citation arrays preserved.
- **49/49** complete visual objects preserved.
- **25/25** image bindings and **24/24** empty bindings retained.
- No extra or missing unit and no rules-fallback corruption.
- Actual normalized `issues` count: **1**, the lexical warning above.

First-response SHA256: `1909524bd37001b136143cfa07993c8521126c6674875a6588aaabf3e0d911a7`.

Repair-response SHA256: `9c787f7c8b2b6e9cb3af7824189b8b60c97140b6f7dff80fbad7a16e724a39fb`.

Normalized SHA256: `bc390baae9ad806fd08074fff53ee592791b48d423547f2cac4646e441f12317`.

Iteration09's explanation has also been corrected: its successful repair removed `certified` from the uncited decline, not merely a curly apostrophe. No validator behavior was changed. The next iteration is an explicit QA/Align-style Author revision of these flagged lines, not evidence of a perfect fresh first response. Provider pixel checking, acoustic quality and recorded duration remain untested.
