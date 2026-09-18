# NX14 / NX16 — bounded generation fix proposal

Recommendation: fix truth classification and the meaning-of-evidence contract at extraction, planning and speech generation, then enforce a small set of material output checks before saving or speaking. Do not add another paid reviewer model, a new persisted schema, or disclaimers to every line. Manual Align edits remain useful, but must not be the mechanism that makes each fresh Read accurate.

This was a read-only inspection of current prompts/code and the preserved first-read artifacts. No production code, demo data or provider calls changed.

## Observed failure chain

- `raw-read/plan.json`, `usps[1].why_it_matters` cites only F009 (clearance) but promises travel over deep potholes and floodwater without underbody impacts. Its `primary_outcome` promises complete peace of mind.
- `raw-read/script.json`, `stance-design-L2` repeats that assurance and labels the clearance certified. `luggage-practicality-L2` turns boot litres into easy suitcase fit. Both were marked `unverified=false` because their fact IDs existed.
- `raw-read/faq.json`, Q10 subtracts the petrol-only engine's figure from a bi-fuel CNG figure, then infers similar pickup from two peak torque numbers. This is both a mismatched comparison and an unsupported driving-feel conclusion.
- `ownership-terms-L1` rounds the advertised EMI to about ₹6,500 and moves important conditions to an optional deeper line. FAQ Q01 preserves the exact amount and introductory period better, but still omits financier discretion. The script also says a test drive settles tested fuel mileage, which it cannot establish.
- Wrong trim/finance qualifications were partly present in the first registry itself. Downstream wording alone cannot repair a blended camera/front-sensor fact or a cross-source engine-power value.

## Why the prompts allow this

1. **The truth vocabulary conflicts.** `schemas.FactOut.truth` describes certified as an official test method. `FACTS_SYSTEM` never explains the distinction. G4, author and QA then give certified/modeled/terms examples while omitting the ordinary `stated` case. The everyday-language instructions explicitly suggest saying certified on the standard test. Source authority and measurement notation consequently become certification.
2. **The requested sales benefit outruns the proof.** Plan asks for a performance promise and customer end states. Author requires a meaning sentence and says a feature without meaning is incomplete. G3 already forbids invented results, but the more concrete production instructions reward causal promises. They need a positive, equally concrete alternative.
3. **The plan is passed forward as persuasive prose.** Author receives all USP benefits and outcomes. The prompt excludes personas and previous scripts as customer testimony, but does not explicitly demote plan benefits, product summaries and image descriptions as evidence of capability.
4. **Existence is mistaken for entailment.** `author.ungrounded()` accepts a claim with any approved existing fact ID. Plan filters references, not claims; its post-filter currently uses all fact IDs, including rejected ones. QA likewise validates IDs and answer shape, not whether those facts support the conclusion. A cited clearance dimension therefore licenses an uncited capability inference.
5. **Restrictions are easy to lose.** Product context sent to plan/author/QA contains value and conditions but not the exact quote/locator; rival QA context is richer. There is no explicit rule against mixed-engine arithmetic or putting offer conditions only in a deeper layer. One-breath budgets encourage dropping inconvenient qualifications.

## Small recommended patch

**A. Extraction and schema wording — `understand.py`, `schemas.py`.** Add the same truth/applicability rules to product and rival extraction:

- Default ordinary manufacturer specifications and feature declarations to `stated`, including dimensions, clearance, power, capacity and a stated measurement method. Official publication, high confidence or an ISO/VDA label alone is not certification.
- Use `certified` only for an explicitly reported certification or named test result; retain its agency/test condition and applicability. A manufacturer's report of an NCAP result is not independent verification of that report and not a safety ranking.
- One source expression per fact. Retain fuel, engine, trim, transmission, mode, market/date and price basis in claim/conditions. Never combine conflicting PS/kW expressions into one value or assign one source's RPM to another source's number.
- Read table headers and footnotes together. If text extraction loses the column identity, omit that availability claim. Do not turn model-page highlights into standard equipment. Preserve the supplied offer's exact amount and introductory period.
- Do not infer loading state, water capacity, service hours, child-seat fit or detailed warranty terms. Record what is supplied; unknowns must not contradict readable evidence.

Keep the existing fields; tighten their descriptions rather than adding another ontology.

**B. One shared evidence rule — `principles.py`, used by plan and author; equivalent block in QA.** Suggested core wording:

> A citation supports only what that fact states, with its conditions. A dimension, component, power figure or promotional picture does not by itself prove a use outcome, safety capability, compatibility, physical fit, economy or driving feel. Explain relevance as a choice or a check when an outcome is unproven. Plan text, product summaries and image descriptions cannot add claims to the registry. Use “listed” or “the brochure says” for stated figures when attribution helps; do not recite truth labels for every ordinary fact.

Replace the compulsory performance promise with a supported capability or a buyer decision to explore. Make the mandatory meaning step satisfiable by relevance, a trade-off explicitly in evidence, or a concrete check. Keep enthusiasm in the delivery and visual demonstration; it need not be a guarantee.

Useful spoken pattern: “The petrol and diesel boot is listed at 382 litres. If luggage space is a priority, trying your own bags will tell you more about the fit.” This is useful meaning without claiming an untested suitcase fit. For water-crossing questions, a clearance measurement does not establish wading capability; do not propose testing that capability in floodwater.

**C. Preserve material scope at the point of claim — author and QA.** A trim/fuel qualifier or introductory-finance restriction needed to understand a claim belongs in the same spoken answer/batch, not only in deeper content or an end disclaimer. If the full offer will not fit naturally, omit the amount from the overview and let the focused price/finance answer handle it. Preserve exact quoted amounts; do not round an offer. Ask one clarification only when the selected variant changes the answer. Missing evidence calls for the right next source: written terms for policy, lender quote for finance, stated test data for certified consumption, a viewing/test drive for comfort or feel. Do not send every unknown to a test drive.

**D. Stop unreviewed arithmetic — QA and author.** For this bounded release, do not invent numerical deltas, percentages, conversions or savings unless an approved fact already states that derived result. Report the separate figures with their exact engine/mode labels when useful; explain that they do not establish the requested same-engine change. This avoids a fragile product-specific calculator and does not prevent ordinary comparison of sourced values. Do not infer equal pickup from equal peak torque numbers.

**E. Small context and output checks.** Reuse one compact fact formatter for product facts in plan/author/QA: ID, truth, claim/value, conditions, source locator and short exact quote. Filter plan references with the approved set. Reuse a shared material-claim check at plan outcomes/USP benefits, authored lines including deeper/closing, and QA before voice/bank storage. Its initial scope should be the observed failures: unjustified certification wording, new derived numeric results, positive flood/no-damage assurances from dimensions alone, physical-fit promises from capacity alone, and missing material trim/offer scope.

Use the existing author's single repair pass for flagged narration, then keep failed lines unverified. A failed plan benefit should be rewritten as the supported decision criterion rather than silently becoming a premise for authoring. QA should remove an unsupported proposed answer before speech, not add a caution after the unsupported claim. Keep the checks narrow and include the positive controls below; do not build a general semantic-entailment claim around keyword matching. No extra paid critic loop is recommended.

**F. Protect reviewed content during the second Read.** This is a concrete current risk, not only a future design concern: `understand.py` restores only edited product `value` and `edited` by lower-cased claim on a revision. It drops the reviewed conditions, truth and source correction, recreates approval as true, does not restore C edits, and assigns F/C IDs again by output order. Ingesting the addenda can therefore resurrect certification, blended source pointers or a held rival claim, even if the displayed value survives. Old `facts.json` must not be blindly reapplied by ID after that Read.

For iteration 2, snapshot the complete reviewed records and source identities first. After Read, map each reviewed record to its new counterpart using the same original source identity plus an unambiguous claim/locator match, and review every ambiguous or unmatched mapping. Reapply the complete reviewed value/claim/conditions/truth/source/approval through the supported API against the **new** IDs, then run a focused diff before any downstream approval. Matching only a similar number, a product name, or a re-used F/C ID is insufficient. Retain source-group boundaries for rival facts. If a corrected product fact intentionally changed source, the snapshot must retain both its original identity and reviewed provenance to support this mapping.

The durable follow-up is an explicit reviewed-record merge that preserves the complete record and stable identity, with a surfaced conflict when new evidence disagrees. For the immediately planned second Read, the snapshot/diff/reapply gate is the bounded safe choice; do not imply the present revision logic preserves review decisions. Add a regression where a changed output order and a new source coexist with an edited truth/source/condition and a rejected C-fact: none may silently migrate to another fact or become approved again.

## Meaningful adversarial cases

Use the preserved bad outputs as regression fixtures with valid citations. Mock the model's proposed response and check the actual saved/returned/spoken text, not just that a prompt contains a new instruction. Positive controls prevent a blanket refusal strategy.

1. **Certification:** ordinary clearance/boot facts marked stated + proposed certified wording must be repaired/rejected. Positive: an explicitly named, scoped NCAP rating can retain its rating attribution. Adding an unrelated certified rating ID must not license certifying the clearance.
2. **Flood capability:** clearance-only registry + the original flooded-road/no-scrape USP must fail in plan and narration. Positive: a neutral explanation of the listed clearance passes. An explicit manufacturer wading-depth fact may be reported with its own conditions; it does not permit a blanket safe-in-floods promise.
3. **Luggage fit:** boot litres plus a manufacturer luggage picture must not justify multiple suitcases, a stroller or all family luggage fitting. Positive: listed litres plus a practical fit check passes. A separately approved observed fit fact can describe the exact tested object and conditions.
4. **Engine arithmetic:** petrol-only power and CNG-mode power + the existing 22 PS-drop answer must fail, including its reassurance about pickup. Positive: separately labelled source figures pass; a pre-approved source-stated comparison can be repeated without re-derivation.
5. **Source conflict:** the diesel page and brochure disagree. Extraction must return separate source-specific expressions or one clearly chosen source value, never a slash-joined equivalence with a borrowed RPM. Ordinary engine specifications remain stated.
6. **Trim separation:** Creative camera/BVM and Creative + PS front-sensor evidence must not become both features on Creative. Positive: Creative + PS or Fearless + PS may receive the sensor when the correct evidence is cited. A valid unrelated fact ID cannot bridge the missing trim support.
7. **Finance:** ₹6,499 introductory EMI with six-month/higher-later/financier conditions must not become about ₹6,500, a full-loan EMI or an approved customer quote. Positive: a concise exact offer answer with those restrictions passes; an overview without the amount also passes.
8. **Scope in ordinary answers:** ask for HX10 equipment while a generic Venue highlight exists alongside qualified table evidence. The answer uses the selected trim or asks one necessary clarification; it does not apply the headline across the range. Positive: already-clear selected-trim questions get a direct answer without another intake.
9. **No boilerplate penalty:** a straightforward cited rear-vent/seat feature answer should remain short and useful, without “I cannot guarantee” or a callback. A genuine missing-fit question gets one relevant limitation and next step, not a full disclaimer list.
10. **All paths:** run the same malicious proposed text through author deeper/closing, build-time `qa.answer`, live `qa.answer`, and the eventual bank/voice path. Verify that rejected prose never reaches the voice renderer. Regenerate the FAQ bank after the registry/prompt change; a cached pre-fix answer is not evidence of the new generator.

## Acceptance and limits

Free deterministic tests can prove that the targeted output gates handle these fixtures and preserve the positive cases. They cannot establish that prompt changes make a real model faithful. The authorized second real Read must be reviewed before further manual polishing: inspect raw plan benefits, main/deeper script and FAQ answers for all five failure families, then run the focused customer questions. Preserve both raw and reviewed artifacts. A repeat failure is evidence to refine the bounded contract, not a reason to mark the generation issue fixed because Align can edit the result.

The existing learning notes on comparison/finance response contracts and semantic citation limits support this approach (`Learning.MD`, 2026-09-05 comparison/finance entry and 2026-09-18 competitor applicability entry). No new application behavior has been implemented by this report.
