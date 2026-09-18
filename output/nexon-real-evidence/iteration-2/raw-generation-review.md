# Iteration 2 — raw generation review

The new prompts improve some observed failures, but **do not make raw generation ready for customer approval**. The new plan drops the flood/no-impact promise and the script drops the explicit suitcase-fit guarantee. Torque units survive. However, the raw script again calls ordinary boot volume certified, generalizes five-star ratings across all trims, omits the later EMI increase, and adds unproven handling/room benefits. All authored lines are marked `unverified=false`; `issues` is empty. Passing that validator is not evidence of semantic accuracy.

Review status: complete for the newly generated plan, script, deck and all 20 FAQ entries. All five raw artifacts, including their registry, are frozen before manual edits. This is a content review, not an acoustic or live customer-path test.

## Evidence identity

Demo `dm_36d47b86`, customer-tier code `bfbda1f657252b9add648575541f1882fccccf8e`. Read started `2026-09-18T14:26:49.561797+00:00`. Only files whose stage completed and whose file modification time followed that timestamp were frozen. Exact stage timestamps and SHA-256 values are in `raw-read/freeze-manifest.json`. No product API writes, source edits, production code changes, server restart or paid requests were made by this review.

The new registry has 29 product facts. The claim label differs from the pre-Read reviewed registry for 28 of the 29 reused numeric F IDs. Old correction payloads must not be reapplied by ID. The plan's references generally match the new facts: no clear direct carryover of an old F ID to its unrelated former claim was found. The three-reminders safety line cites F003/F007/F020 without the new rating fact F006; this is an unsupported rating citation, but not proof that stale IDs caused it. The old plan is passed as context; the old script is not passed on this author call because it has no author-specific revision instruction.

## Failure-family result

- **Flood and no-damage assurance:** the explicit monsoon-water/no-scrape promise is absent. The replacement still infers “useful underbody margin on rough roads” from clearance and repeats the registry's unsupported “unladen” qualifier. A neutral dimension plus a relevant question is safer.
- **Ordinary specifications called certified:** repeats in `boot-practicality-D1`: “Boot volume is certified under ISO V215 standards”. F014 is `stated`; ISO V215 is the stated measurement method. New extraction/wording rules did not prevent this.
- **Luggage fit:** the prior multiple-suitcase promise is absent. The check-in asks the buyer whether a litre figure accommodates “typical family packing”, which assumes family use and asks them to infer physical fit from volume. Ask what they carry, then suggest the physical check.
- **Trim/fuel scope:** repeats. The plan says rear vents are standard without its own F021 Pure+ qualifier. Main script says every trim has certified five-star safety and makes CNG sound available with automatic gearboxes. The DCA deeper line sounds exclusive to Fearless+ PS even though F019 establishes that selected pairing, not exclusivity.
- **Finance scope:** repeats in `ownership-details-D1`; it keeps ₹6,499, six months and lender approval, but drops the higher subsequent instalments and financier-controlled final schedule from F002.
- **Units:** improved in script and FAQ. `powertrain-choices-D1` retains 170 Nm and 260 Nm; FAQ Q06/Q07 also retain units and operating ranges. PS remains PS. This is a positive generated result; the live response still needs its own review.
- **New dimension-to-performance claims:** `intro-overview-L1` promises easy city handling and relaxed highway driving from F012 dimensions. D2 says the size preserves legroom; that line has no facts. These are the same entailment failure in a new location.
- **Registry limits propagate:** F013's unladen condition and F016's water-equivalent interpretation recur downstream. Product source review owns their exact correction. Ordinary consumer copy cannot repair a wrong registry condition merely by retaining it.

## Plan corrections before approval

These are proposed edits, not applied changes. Keep the current IDs and source-specific corrections from the parallel product audit.

- `takeaway`: **“The Nexon offers standard safety equipment, several fuel and gearbox choices, and cabin features to compare by trim.”** Replaces the confused “standard five-star crash safety equipment”.
- `primary_outcome`: **“Choosing a Nexon powertrain and trim using published specifications, applicable crash-test ratings and the equipment that matters to the buyer.”** “Verified” should not imply independent verification.
- `usp-comfort.why_it_matters`: **“Rear AC vents are listed from Pure Plus; Fearless Plus PS petrol and diesel add ventilated front seats, giving you specific equipment to compare by trim.”** F020/F021. Retain the verified trim conditions after registry review.
- `usp-safety.why_it_matters`: **“Six airbags, electronic stability control and ISOFIX are standard. Tata reports a five-star Bharat NCAP result for petrol and diesel trims active in May 2026.”** F003/F004/F006. Do not combine the generic GNCAP highlight and scoped BNCAP result into an all-variant guarantee.
- `cabin-comfort.goal`: **“Show rear AC vents from Pure Plus and the front-seat ventilation listed for Fearless Plus PS petrol/diesel.”**
- `exterior-stance.outcome`: **“Published dimensions and variant-qualified ground clearance.”** Remove “unladen” after the source correction.
- `decision_frame`: **“The choice is the fuel, gearbox and equipment that fit your needs; the next steps are a test drive and a quote for the exact variant.”** Avoid making five-star ratings a universal trim attribute.
- `do_not_recommend_if`: **“Do not recommend a configuration until a decisive requirement has been checked against its documented equipment or a relevant in-person fit check.”** The present line treats missing fuel-economy evidence as a reason to reject the product itself and asserts unsupported third-row scope without a seating fact.

## Exact script replacements

All replacements below use the **frozen raw I2 registry IDs**, not a live patch payload. The parallel review subsequently repurposes F007/F009 to restore the omitted cockpit facts; map any affected citation by source and claim before applying suggestions. Keep unaffected lines and saved visual design. The changed main batches remain within the existing word budgets. Root owns the actual reviewed API corrections and their applied-record audit.

- `intake_q1`: **“Welcome to Tata Nexon. What matters most in your next car? You can skip this and browse.”** One greeting and one useful question; names the actual product.
- `intro-overview-L1` → **“The Tata Nexon is a compact SUV with petrol, diesel and CNG choices.”** Cite F012/F018.
- `intro-overview-L2` → **“We'll look at the cabin, luggage space and gearbox choices, and you can steer us toward what matters most.”** No product-capability citation needed for this tour signpost.
- `intro-overview-D2` → **“Those dimensions are useful to compare with your parking space; a visit lets you check the seating position for yourself.”** Cite F012. Removes unproved easy parking/preserved legroom.
- `three-reminders-L1` → **“The three things I'd look at are cabin features by trim, the choice of fuel and gearbox, and the standard safety equipment.”** Cite F003/F018/F020/F021. Together with its unchanged L2 this remains within the 38-word batch limit.
- `exterior-stance-L2` → **“Tata lists two hundred and eight millimetres of ground clearance, with the figure varying by variant.”** Cite corrected F013. No road-capability inference.
- `exterior-stance.checkin` → **“Is ground clearance a concern on the roads you use?”** Asks about their need, without asking them to approve an engineering inference.
- `cabin-comfort-L2` → **“From Pure Plus, rear air vents are listed; Fearless Plus PS petrol and diesel add ventilated front seats.”** Cite corrected F020/F021. Its unchanged L1 can remain.
- `cabin-comfort-D1` → **“Fearless Plus PS petrol and diesel list ventilation for both the driver and front passenger seats.”** Cite F020.
- `boot-practicality-D1` → **“The boot figures use the ISO V215 measurement standard. The brochure lists two CNG cylinders totalling sixty litres.”** Cite corrected F014/F016. This avoids invented certification and water-capacity wording.
- `boot-practicality-D2` → **“On Fearless Plus PS petrol DCA, the rear seats split and fold. Try the items you normally carry before deciding.”** Cite F024/F019 after confirming the selected trim in the source audit.
- `boot-practicality.checkin` → **“What would you usually need to carry?”**
- `powertrain-choices-L1`: keep its text but add F018 for its actual three-fuel claim.
- `powertrain-choices-L2` → **“Petrol and diesel have manual and automatic options. CNG uses a manual gearbox; the exact pairing depends on the trim.”** Cite F018.
- `powertrain-choices-D2` → **“Fearless Plus PS petrol pairs the one point two litre engine with a seven-speed dual-clutch automatic.”** Cite F019. No exclusive-availability claim.
- `safety-standards-L1` → **“Every trim has six airbags, electronic stability control and ISOFIX.”** Cite F003/F004.
- `safety-standards-L2` → **“Tata reports five Bharat NCAP stars for petrol and diesel trims active in May twenty twenty-six.”** Cite F006.
- `safety-standards-D1` → **“Tata also reports a Global NCAP five-star result; the supplied highlight does not give its full test protocol or date.”** Cite F005. Do not claim the two schemes' scores “match”.
- `tech-convenience-L2` → **“Fearless Plus PS petrol DCA includes surround-view cameras, front sensors and JBL audio. Those are details to compare alongside your chosen trim's price.”** Cite corrected F022/F023/F026/F019.
- `tech-convenience-D1` → **“Creative and higher petrol or diesel trims list a surround-view camera with a blind-view monitor.”** Cite corrected F022. Preserve the fuel limitation rather than relying on a generic highlight.
- `ownership-details-L1` → **“Prices start at seven point three nine lakh rupees ex-showroom; the basic warranty headline lists three years and one hundred thousand kilometres.”** Cite F001/F027. Avoid imposing “or”/whichever-first when the badge does not state it.
- `ownership-details-L2` → **“Check your trim's quote and the written warranty terms.”** Keeps the missing-policy action concrete, without presenting a dealer test as a substitute for official evidence.
- `ownership-details-D1` → **“The flexi offer starts at six thousand four hundred and ninety-nine rupees a month for six months. Later instalments are higher, and the financier decides the final schedule.”** Cite F002.
- `ownership-details-D2` → **“Tata lists its toll-free roadside assistance contact as 1800 209 8282.”** Cite F029. The number is evidence of the contact, not service availability everywhere in India.
- `close-L1` → **“The choice comes down to the fuel, gearbox and equipment that matter to you, with a test drive to check the fit.”** Cite F018/F020/F021 as relevant; keep the existing CTA line. Remove “proven” and universal standard five-star safety.

## Human-quality review

The raw main script totals 301 words including closing. Nine main batches are 24–35 words, roughly 13–18 seconds at the app's 1.9 words/second estimate; closing is 40 words. This is a meaningful pacing improvement over the old long specification tour. There is one intake question, no second intake, no hidden narration questions and no invented commute/budget. Actual voice intelligibility and timing have not been tested by this review.

The copy is nevertheless generic: “standard five-star safety architecture”, “core pillars”, “powertrain configurations” and repeated feature inventory feel like brochure narration. The first overview promises driving feel; the first three-reminders line is a jargon-heavy list. Boot and clearance check-ins ask buyers to validate a technical specification rather than explain their needs. “Typical family packing” presumes family use before any profile is known. The exact replacements above improve these points without adding a disclaimer to every slide.

Keep the current choice to let the customer interrupt and steer. Optional further polish: the safety check-in could be **“Would you like to hear which safety features change by trim?”** instead of re-asking whether safety is their top priority; avoid treating every check-in as another discovery survey.

## New FAQ review

The fresh bank is complete (`partial=false`), with 18 answered entries and two explicit declines. That is answer coverage, not an accuracy score. The current question set does **not** ask the original same-engine petrol-to-CNG power-loss question. There is no computed delta in this bank, but the absence of that probe cannot demonstrate the arithmetic failure is fixed.

Meaningful improvements: Q02 gives the exact introductory EMI, first-six-month period, higher later payments and financier discretion together. Q06/Q07 retain torque units. Q09 correctly identifies the selected Fearless+ PS petrol DCA pairing without exclusivity. Q17 retains the petrol/diesel scope, first-year iRA inclusion and renewal charges. Q19 declines unknown delivery timing; Q20 declines an unsupported five-year Brezza service-cost comparison. These are useful positive results without adding boilerplate to every ordinary answer.

Required or recommended replacements before the bank is voiced:

- **Q04 — rating scope.** “Active petrol and diesel models” drops the May-2026 qualifier and can be heard as every model active today. Replace with: **“Tata reports a five-star Global NCAP result. Its reported five-star Bharat NCAP rating applies to petrol and diesel trims active in May 2026.”** F005/F006. Avoid repeating the unqualified “top scores” superlative from the marketing highlight.
- **Q05 — child-seat installation.** Standard mounts are supported; a particular seat's compatibility is not established by F004. Replace with: **“ISOFIX mounts are standard, including on the base variant. Check the intended child seat's compatibility and installation instructions before fitting it.”** F004. This is a targeted fit qualification, not a reason to refuse the ordinary equipment question.
- **Q07 — new unproved driving benefit.** The first sentence is complete and grounded. Delete the second sentence, “That gives you solid pulling power for smooth overtakes and relaxed cruising.” Keep: **“The 1.5-litre Turbocharged Revotorq diesel engine delivers 260 Nm of torque between 1,500 and 2,750 rpm.”** F010.
- **Q08 — gearbox scope.** Add **“The available pairing depends on the trim.”** to the current four-option list. F018 is a range-level list, not evidence that one selected trim offers all four.
- **Q10 — water capacity and luggage benefit.** Replace with: **“The Nexon iCNG lists 321 litres of boot space, measured to ISO V215. Check the fit with the luggage you normally carry.”** F014. Remove the unnecessary cylinder interpretation and “generous room” inference. The displayed im06 is a petrol/diesel boot image; do not imply it proves the CNG configuration.
- **Q11 — unsupported registry qualifier and obstacle check.** Replace with: **“Tata lists 208 mm of ground clearance and notes that it varies by variant. The supplied material does not establish loaded clearance or whether it will clear a particular deep pothole.”** Corrected F013. Do not suggest testing a hazardous obstacle.
- **Q12 — seating flexibility.** Prefer a selected, verified scope: **“The Fearless Plus PS petrol DCA lists 60:40 split-folding rear seats. The fit of your extra luggage still needs a physical check.”** F024/F019 after the product audit confirms these current rows. The current generic “starting from” answer should not silently expand to an unverified fuel/persona.
- **Q13 — ventilation fuel scope.** Replace with: **“Rear AC vents are listed from Pure Plus. Ventilated front seats are listed for Fearless Plus PS petrol and diesel, so those versions have both features.”** Corrected F020/F021.
- **Q14 — camera scope/mechanics.** Replace with: **“Creative and higher petrol or diesel trims list the 360-degree surround-view system with Blind View Monitor. Check its views and controls on the exact variant you are considering.”** Corrected F022. The source establishes equipment, not parking outcome or blind-spot detection alerts. Ideally the generated FAQ question asks which trims offer it instead of requesting operating behavior absent from its fact.
- **Q16 — warranty logic.** Replace with: **“The brochure's basic-warranty headline lists three years and 100,000 kilometres. The detailed terms and exclusions still need checking.”** F027. Do not infer “or” or whichever-limit-comes-first from the badge alone.

Q01, Q03, Q06, Q09, Q15, Q17, Q18, Q19 and Q20 have no additional blocking claim-to-registry mismatch found in this pass, subject to the parallel source audit. Q06 combines the website's explicitly paired PS/kW expression with the same engine's brochure operating range; if the source audit changes either row, regenerate it against the corrected source-specific value rather than preserving the old answer text.

## Deck review and bounded prompt repair

The raw deck reintroduces the same overreach more aggressively than narration. Examples: `sl03-c2` says clearance “clears rough roads easily”; `sl05-c2` says boot volume “fits family luggage”; `sl06-c3` promises highway efficiency; `sl06-c4` says CNG lowers daily fuel costs without a cost fact; `sl07-c3/c4` turn components/ratings into protection guarantees. `sl04-c3/c4` promise to beat humid weather and keep all passengers cool. The word limits and valid citation IDs do not establish those outcomes.

There is also a **confirmed stale reviewed citation**: `sl07-c1`, “Petrol/diesel: 5-star BNCAP, May 2026 scope”, still cites F004. In the first reviewed registry F004 was the BNCAP result; in the new registry F004 is ISOFIX and F006 is BNCAP. This is an old saved override surviving a reassigned numeric identity, not simply model wording. The title “Your cockpit, closer” on sl04 also survives while the new segment discusses seat ventilation. Root owns the review-preservation/override correction; the prompt patch does not fix saved identities.

Proposed concise replacements, each within eight words, with **current** citations:

- `sl02-c4` and `sl04-c3`: **“Fearless+ PS petrol/diesel: ventilated front seats”**, F020.
- `sl02-c5`: **“Tata: five-star BNCAP, May-2026 petrol/diesel trims”**, F006. Alternatively omit this duplicate rating label.
- `sl03-c2`: **“Clearance: 208 mm; varies by variant”**, corrected F013.
- `sl04-c4`: **“Rear AC vents: Pure+ and higher”**, corrected F021.
- `sl05-c2`: **“Petrol/diesel boot: 382 L, ISO V215”**, F014.
- `sl05-c3`: **“CNG boot: 321 L, ISO V215”**, F014. Use a factual panel, not an anchor implying the petrol/diesel picture shows CNG packaging.
- `sl06-c2`: **“Petrol maximum power: 120 PS”**, F007.
- `sl06-c3`: **“Diesel power: 84.5 kW at 3,750 rpm”**, F010. This uses the brochure expression rather than hiding the conflicting website/FAQ PS values.
- `sl06-c4`: **“CNG gearbox: six-speed manual”**, F018. No cost-saving inference.
- `sl07-c1`: retain its scoped rating copy but change its citation from stale F004 to F006 after review.
- `sl07-c3`: **“Six airbags standard”**, F003.
- `sl07-c4`: **“ISOFIX mounts standard”**, F004; remove a duplicate rating claim.
- `sl08-c3`: **“Creative and higher petrol/diesel: 360-degree camera”**, corrected F022.
- `sl08-c4`: **“Fearless+ PS petrol DCA: JBL nine-speaker audio”**, F026.
- `sl08-c5`: omit if the source's fuel/trim/subscription conditions cannot fit. Narration or focused Q&A can carry the complete terms.
- `sl09-c3`: **“Basic warranty headline: 3 years, 100,000 km”**, F027. Remove the invented “or” and “peace” outcome.

After freezing the raw deck, the authorized code change updates only `deck.py` prompt/schema descriptions and evidence context: a complete neutral label/specification/fit-check is now valid, qualifiers take precedence over an eight-word chip, and omission is allowed. The deck receives shared `EVIDENCE_RULES` and each fact's truth, exact quote, locator and conditions through `fact_context`. The former benefit-only examples and mandatory “promise” are removed. No actual deck rebuild or saved-override algorithm changed.

The updated free generation suite passes **23/23** including two actual deck input-envelope checks. It verifies evidence delivery and instruction assembly, not that the model will obey them. Raw I2 author failures already demonstrate why that distinction matters; a future generated deck cannot be called fixed from these checks alone.
