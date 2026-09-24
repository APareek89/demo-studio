# Iteration11 independent source audit

**Disposition: accepted for source entailment and literal picture binding in this isolated simulation.** All 49 narration units were reviewed against the frozen `final-source-v2` registry and the previously inspected source pictures. No actual unsupported claim, lost source qualification, incorrect quantity, trim contradiction or literal-picture mismatch was found. This is an explicit QA/Align-style revision of iteration10, not a perfect first-pass result. Target coverage and measured duration are separate from this source acceptance.

## Review scope and provenance

Reviewed the runtime overview, all main and deeper lines, and both closing statements in `iteration-11/artifacts/author.json`, against `final-source-v2/understanding.json`, source-page evidence and the inspected image mapping. Also compared `calls/author-02.response.json` with the normalized artifact and the complete iteration10 artifact. No generated JSON, prompts, source fixture or code was edited during this audit.

The existing `author.run` revision path supplied the unchanged iteration10 script and two specific QA corrections. `review-provenance.json` records the previous script hash `bc390baae9ad806fd08074fff53ee592791b48d423547f2cac4646e441f12317`, unchanged previous bytes and unchanged iteration10 system prompt. The first revision corrected two texts; the genuine native repair regrouped the saved split segments into the 11 planned stops. Normal processing restored 16 segments without changing the speech.

## Iteration10 findings resolved

1. **Ventilation handoff — `seat-and-roof.lines[0]`.** F037/F038 support ventilated front seats, cool airflow through the cushions and availability from SX Premium. The revised last sentence is “Cabin choices extend from seats beneath you to the space overhead.” This is a generic transition, with no assertion of the separate glass-roof feature. The seat-airflow picture `im_pdf_498ba48d46b3d2258714` now matches the concrete subject throughout the line. The following roof line independently supplies F048/F049 and the actual roof image.

2. **Uncited decline — `terms.deeper[1]`.** The revised line remains an explicit refusal to confirm engine-specific fuel-economy figures or an exact-model-year crash result from the supplied evidence. It names the appropriate certification/testing sources needed and says a test drive cannot supply the missing results. Removing `certified` from the final phrase resolves the unchanged lexical claim check without invented IDs or a guard exception. `fact_ids` remains empty and the visual remains `none`.

The decline's normalized `unverified` value changes from true to false because the native validator derives that field after its lexical warning clears; the schema does not preserve the authored flag. This report therefore does **not** claim that every metadata field is preserved. Its wording still states an evidence gap, and no fact or understanding unknown was changed.

## Clause and image findings

- Auto hold's first availability on S(O) automatics and standard equipment from King retain their cited qualifications. The deeper line preserves the exact King/King Knight/Lounge scope and conditional earlier availability.
- The S(O) Knight automatic exclusion has local citations spanning all engine families: F005/F006 and F065–F068, alongside F016. Non-turbo petrol, diesel and turbo engine/gearbox trim sets and their SX/SX Premium exceptions match the source matrix. King-only turbo is not generalized to other King engines.
- Technical numbers and their units/ranges remain supported. The turbo PS quantity stays in deeper as required by the existing validation decision. Generic engine-choice handoffs do not assert extra uncited trim assignments.
- Knight alloy pictures show the cited black-alloy subject. Steel/alloy and full tyre-size comparisons remain nonvisual. Split seats and luggage/boot content use separate actual pictures; no boot capacity, ride outcome, acceleration or clearance is invented.
- Six airbags as standard from E, assistance availability, camera scope and automatic-only cruise qualifications remain intact. Safety equipment is not turned into an unsupported crash-rating or stopping-distance promise, and the driver-responsibility qualification survives.
- The physical display picture is separate from the nonvisual Bluelink service/seat-package discussion. Climate, Alexa prerequisites, phone-adapter conditions, ventilation and sunroof availability retain their source scopes. Bose's eight-speaker count includes its subwoofer; it is not counted as a ninth speaker.
- Puddle-lamp side/trim scope and the armrest's standard-versus-sliding distinction remain correct. A still photograph is not presented as proof of sliding motion. Glovebox wording makes no unmeasured temperature or elapsed-time guarantee.
- Prices remain dated source values with the conflict explicit, rather than a live dealer quotation. The paid extension is limited to **up to seven years for petrol variants**; it does not exclude diesel from every possible extended warranty. Stock, delivery, booking and missing test results remain unknown.
- The close records a contact preference rather than claiming a completed booking or outreach. No fabricated buyer persona, unsupported customer history or reputation claim was introduced.

All 25 explicit image bindings refer to inspected literal subjects; the other 24 units intentionally use `none`. The source remains limited to one image per narrated unit, and a manual literal-subject check does not establish provider pixel-model performance.

## Preservation and integrity checks

- **49/49** units matched by ID/order between iterations10 and11. Only two narration texts changed: `seat-and-roof.lines[0]` and `terms.deeper[1]`.
- **49/49** citation arrays and complete visual objects remained unchanged from iteration10. Delivery fields remained unchanged; the decline's derived `unverified` change is noted above.
- **49/49** raw repaired-response texts, citation arrays and full visual objects survived normalization exactly, with no missing or extra unit.
- **25/25** image bindings and **24/24** intentional empty bindings survived; no rules-fallback substitution was found.
- The actual isolated understanding retains all **68 facts and 10 unknowns**, with both lists exactly equal to the frozen source fixture. No unknown became a fact.
- Actual native `issues`: **0**. Prepared narration: **495 words**, two attempts, ready. Default route: **345 words**, **181.58 seconds estimated**. Neither estimate nor word count is a measured recording.

First revision response SHA256: `0cedb11cd40d64d2957155e3f1912fd13247145d1aa8cf482082e080f3311f04`.

Native repair response SHA256: `ca8b86d6e362f8e887a04142178a2812e00d43a9c6b3a951564420ac4f3d6b25`.

Normalized artifact SHA256: `fa30b50caa33768b126601960cd614b1631fe0d94dea84b57b85d4756c2b1c83`.

## Limits and remaining target coverage

Diesel manual availability starting at E is accurate in deeper but is not named as that first-trim choice in the main route. This is a reference/target coverage limitation, not a false source statement; the main-route diesel example accurately describes SX Premium's manual-only diesel choice.

The supplied registry is a manually reviewed simulation fixture made from the uploaded PDF and actual extracted pictures. It does not establish live Understand semantic extraction quality. Previously documented omitted-but-present dimensions, suspension and rear-cabin source details remain fixture omissions, not absent PDF evidence. No final narration falsely denies them.

The run uses rules fallback, with no paid provider calls. Full provider pixel checking, acoustic quality and measured recorded duration were not tested. Prior iteration reports are retained as historical failed drafts and corrective evidence.
