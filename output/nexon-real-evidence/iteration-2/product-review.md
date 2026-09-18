# Iteration 2 — product fact review

**Recommendation:** apply the 26 proposed fact patches, reconcile every plan/script/deck/FAQ/image reference, then approve the 29 reviewed product facts. The raw second extraction is **not ready for approval**: it restores the unsupported ground-clearance loading condition and cylinder-capacity interpretation, retains an unsafe comparative safety claim, and omits both cockpit displays. Seven addendum topics were recovered successfully.

This is a review proposal, not a production write. No paid calls, source changes, demo mutations or server restarts were made for this audit. Competitor facts are outside this review.

## Evidence boundary

- Demo `dm_36d47b86`; second Read began `2026-09-18T14:26:49.561797+00:00`; understand completed at `2026-09-18T14:28:41.859513+00:00`.
- Primary structured extraction: Gemini `gemini-3.8-flash`, trace timestamp `2026-09-18T14:27:34.622926+00:00`. This is recorded separately from persisted output.
- Frozen full registry: `raw-read/understanding.json`, SHA256 `1dbe622300027330b2539902baf53fc891ce23a7c93220093d0c964806234f7f`.
- Raw product response, complete source input and trace: `raw-read/product-extraction.json`, `product-source-input.txt`, `product-extraction-trace.json`. Timestamps, source records and hashes are in `raw-read/product-extraction-provenance.json`.
- Original brochure: `output/nexon-sources/brochures/nexon-brochure-may-2026.pdf`, SHA256 `d590ff0c550a3de3ae7f77683a474cc7400fb319c16bf0e10a5e0e6cd70f738f`. Pages 11, 38, 39 and 40 were visually checked, including column headers, persona inheritance, warranty badge and footnotes. The captured official page text used by this exact extraction was reviewed; earlier failed page fetches were not substituted for it.
- Prior correction intent comes from `iteration-1/review-edits/facts-provenance.json`, using each original source/meaning and its reviewed patch. Current IDs were not treated as stable across Reads.

## Findings that change approval

1. **F013 ground clearance:** `Unladen` is still unsupported. Preserve the 208 mm value and printed variant caveat; explicitly record that the loading condition is not supplied.
2. **F016 CNG capacity:** `Water-equivalent` is still unsupported by the cited brochure. Preserve 60 (30+30) litres as the manufacturer's described twin-cylinder fuel capacity, without mass/usable-gas/water interpretation.
3. **F005 GNCAP:** drop the highest-score/safest comparative claim. Retain only the manufacturer-reported named five-star rating, with test date/generation/variant scope unresolved. F006 BNCAP separately retains the precise petrol/diesel trims active as of May 2026 scope using brochure page 40.
4. **Lost reviewed provenance and qualifiers:** restore the deliberate brochure citations for BNCAP, boot measurement basis, ADAS, audio system and connected features. Add petrol/diesel persona and separate-iCNG scope to rear vents, camera, front sensors and rear-seat features. The broad brochure persona tables must not silently establish the same equipment on iCNG.
5. **Combined technical facts:** F008/F010/F011 each consolidate several old rows. Keep these complete source-specific brochure figures; an old single-field patch must not overwrite the new combined value. CNG-mode and petrol-mode figures remain distinct. Replace artificial pipe-joined quotations with actual normalized table text and explicit table column/row locators.
6. **Price/finance:** F001 is a starting ex-showroom price, not the chosen variant's exact price. F002 is an advertised written offer with first-six-month and later-EMI conditions, selected-variant restriction and financier discretion; it is not an agreed customer EMI. Restore contractual classification and full restrictions.
7. **Other scope corrections:** distinguish tyre sizes from rim diameter; remove an unstated toll-free telephone condition; include the iRA trim restriction and renewal condition without asserting a feature count or renewal price.

The other directly extracted units are retained. Ordinary dimensions/engine/equipment facts are `stated`; the named BNCAP rating is `certified`; written warranty/subscription/offer terms are `contractual`. An official source alone is not a certification.

## Deliberate cockpit recovery through the existing edit API

The raw second Read omitted both screen facts. Do not pretend an old ID mapped naturally to a new display claim. The proposed edits intentionally replace two unnecessary standalone website engine-output rows:

- **New F007:** replace raw petrol website output with **26.03 cm HARMAN infotainment touchscreen**, supported by brochure page 38 Pure + panel and pages 38–39 hierarchy. Scope: Pure + and higher in the documented petrol/diesel list; Smart + lists a smaller screen; iCNG requires its separate list. This recovers reviewed iteration-1 F027. New F008 still retains the full petrol brochure engine facts.
- **New F009:** replace raw diesel website output with **26.03 cm digital instrument cluster**, supported by brochure page 39 Fearless + PS panel. Scope: Fearless + PS in the documented petrol/diesel list, not the whole range; iCNG remains separate. This recovers reviewed iteration-1 F028. New F010 still retains the full diesel brochure engine facts.

Both payloads contain a complete claim/value/truth/source/conditions correction. `kind` remains the existing `spec`, which accurately describes a display-size specification and does not require schema changes. The abandoned website rows remain intact in raw evidence. The raw 115 PS website / 113 PS FAQ discrepancy is not resolved by invention; the approved diesel engine fact uses only the brochure's 84.5 kW at 3750 rpm. A prior petrol 120 PS website wording is likewise not silently converted into a brochure quote.

**Required consequence:** every reference to F007 or F009 generated during this second Read must be deliberately rewritten or removed. Updating the fact alone cannot make an existing engine sentence, visual callout or image association into valid cockpit content. The whole downstream review is a prerequisite to applying the approval recommendations.

## Old-to-new mapping

The full 32-row mapping is `review-edits/product-old-to-new-map.json`. It records original source and claim, prior intentional patch, raw new claim, proposed claim and mapping type.

- Old F001→new F001; F002→F002; F003→F005; F004→F006.
- Old F005/F006/F007/F008→new F012 (combined dimensions).
- Old F009→new F013; F010/F011→F014 (combined boot capacities); F012→F015; F013→F016.
- Old F014/F015/F016→new F008 (combined petrol engine).
- Old F017/F018/F019→new F010 (combined diesel engine).
- Old F020/F021→new F011 (combined bifuel engine).
- Old F022→new F018; F023→F017.
- **Old F024 braking setup is unmatched and omitted.** Do not carry this old citation into new F024, which is rear-seat flexibility. No brake fact is being added or fabricated.
- Old F025→new F003; F026→F025.
- **Old F027 and F028 have no raw same-meaning match.** Proposed deliberate replacements are new F007 and F009, respectively, as explained above.
- Old F029→new F026; F030→F022 for the reviewed camera/BVM-only fact. The previously conflated front sensor now has its own new F023.
- Old F031→new F028 is a partial match: the raw new fact is subscription-only. Its proposed explicit claim/value/conditions restore the previously reviewed connected-feature scope without the unverified 70+ count.
- Old F032→new F029.

No unresolved source/meaning ambiguity was used to force a correspondence. Many-to-one combined rows, one partial match, the omitted brake fact and the two deliberate identity replacements are explicitly distinguished from ordinary matches.

## New addendum coverage

All seven reviewed addendum topics have product facts:

- N1 warranty → F027, original page-40 badge visually checked. Headline only: 3 years | 100 000 km; detailed terms and whichever-occurs-first are not supplied.
- N2 ventilated front seats → F020, Fearless + PS petrol/diesel; no rear-seat ventilation claim.
- N3 rear AC vents → F021, Pure + and inherited higher petrol/diesel personas.
- N4 standard ISOFIX → F004, page-11 label and standard-equipment footnote; no attachment-point count or universal child-seat compatibility.
- N5 selected Fearless + PS petrol automatic pairing → F019, page-40 matrix cell visually checked, seven-speed automatic label on page 18. The proposed citation points to the original brochure rather than the reviewer addendum.
- N6 front sensor → F023, Creative + PS and Fearless + PS petrol/diesel, separate from camera/BVM.
- N7 rear-seat flexibility → F024, those same documented higher petrol/diesel personas; no actual stroller/luggage-fit assertion.

## Raw extraction versus persisted restoration

Only one substantive field differed between the raw model response and the persisted product records: F017 tyre-size wording was replaced with the previous human-edited value. Five records carry `edited=true` (F001, F006, F013, F016, F017), but the restoration code carries only a value on an exact claim match. It does not preserve source, conditions or truth. Consequently the flag must not be interpreted as proof that the prior human correction survived. The recurring unsupported qualifiers above are present in both the new raw extraction and its persisted output.

## Apply order and validation

1. Verify current product facts still match the frozen raw product facts, or compare intervening product edits before applying. Later Read stages may legitimately update unknowns; do not replace the entire live understanding file with this snapshot. At the final audit check only `unknowns` had changed; all 29 product facts still matched.
2. Apply each `review-edits/product-facts.json` record using `PATCH /api/demos/dm_36d47b86/align/facts/{id}` with its `patch` object as the body. There are 26 records; F004/F020/F027 remain unchanged.
3. Reconcile and review all downstream plan/script/deck/FAQ/image citations against the final proposed registry, especially F007/F009 and all reused numeric IDs. Preserve the existing card reapproval requirement.
4. `review-edits/product-approvals.json` contains 29 approval recommendations using `POST /api/demos/dm_36d47b86/align/facts/{id}/approval` with each `patch` object. These are conditional recommendations, not evidence that approval was applied.

Free validation passed all 26 actual `store.edit_fact` calls and 29 `set_fact_approval` calls against an in-memory copy of the exact new registry and actual source records. The entire resulting Understanding schema validates. Socket connections were forbidden, every store write was intercepted, and the live registry hash remained unchanged. Twenty-eight of 29 proposed quotes match the captured source text after whitespace normalization; the warranty badge quote is instead verified visually from page 40 and the reviewed addendum. Details are in `review-edits/product-review-validation.json`.

The proposal preserves unresolved exact variant price, customer finance, detailed warranty terms, availability/delivery, real luggage fit and cross-brand safety ranking. They require an appropriately scoped answer or explicit follow-up, not an inferred fact.
