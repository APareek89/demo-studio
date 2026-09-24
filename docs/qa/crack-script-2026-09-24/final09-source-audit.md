# Iteration09 independent source audit

**Disposition: intermediate, not accepted.** The actual two-call Author path reaches `issues: []`, but manual review still finds one incomplete local citation set and two mixed-subject picture bindings. These are not repaired by the empty issue list. No prompt, code or generated JSON was edited during this audit.

Reviewed all 48 narration units in `iteration-09/calls/author-01.response.json` against `final-source-v2/understanding.json`, verified PDF evidence and inspected actual images. Then inspected the genuine `author-02.response.json` repair and matched its output to actual-stage `artifacts/author.json`.

## Required corrections

1. **Incomplete evidence for an exhaustive engine exclusion — `opening.deeper[1]`.** The sentence says the engine matrix offers no automatic S(O) Knight combination, then describes S(O) and SX Premium pairings. Its IDs are F016/F066/F067/F068. F066 and F068 establish the non-turbo petrol and diesel automatic sets; F067 is the diesel manual set; F016 is the equipment rule. To justify the matrix-wide “no automatic” exclusion, the line must also account for the third engine: F006 establishes turbo/DCT is King-only. Add that existing citation through the Author output or narrow the assertion. The statement is true in the full reviewed registry; its own citation set is incomplete. Do not convert this into a request for invented evidence or a validator exception.

2. **Dashboard plus a separate connected-service offer — `climate-and-remote.deeper[1]`.** The line cites F041/F042 for the physical screen pair and F043 for Bluelink's start trim, feature count, complimentary period and connectivity condition. It binds `im_pdf_46a6d841c01356a2e42d`, which shows the dashboard/screen pair. Those pixels do not show the separate Bluelink service offer. A broadly related in-car screen is not literal proof of that second subject. Use deliberate `none` for the combined line or separate the pictured screen subject from the service statement. Iteration08 correctly left this combined statement unbound.

3. **Folded-seat picture plus a separate boot description — `shared-space.deeper[0]`.** The line cites F022 for the split seat, declines to confirm a capacity, and adds F063's manufacturer boot-storage description. It binds `im_pdf_adb415f161dfc9567dde`, the folded rear-seat picture. That image demonstrates the seating arrangement, not the separate boot described by F063. Retain only the pictured subject in that line or use `none`; a separate boot statement can use the actual boot asset. Iteration08 separated the split-seat and boot subjects. The boot statement is textually supported; the problem is whole-line literal coverage, not invented content.

These findings survived the actual repair call. The correction should come from a new genuine Author response, not a hand edit of the generated artifact.

## Checks that passed

- The main warranty line preserves **paid up-to-seven-year extension / petrol-only** together. The iteration07 broadening has not returned.
- Main gearbox comparisons deliberately use `none` where a single manual/automatic control photo would mislead. The three engines have their actual corresponding engine pictures.
- Full non-turbo petrol and diesel MT/automatic trim lists match F065–F068 and PDF p31. King-only turbo is not misrepresented as every King being turbo. The S(O) Knight exception is factually correct, subject to the local citation correction above.
- Power, torque, rev ranges, transmission counts, wheel/tyre strings and screen dimensions are source-supported. No measured acceleration, fuel-economy, boot-volume, ground-clearance, crash-rating or comparative performance result was invented.
- The wheel main line now selects the same depicted option: Knight matte-black alloys. PDF p8 labels the selected black-wheel/red-caliper photograph as Knight; it no longer illustrates steel-wheel narration with an alloy photo. Full steel/alloy comparisons remain `none`.
- Driver-assistance scopes, camera-versus-cruise distinction, ventilation function, panoramic/voice roof starts, phone adapter requirement, Alexa hardware/network conditions, Bose counted-system membership and puddle-lamp side scopes remain intact.
- Dated conflicting entry prices are not current on-road quotes. Armrest movement is not claimed to be demonstrated by the still picture. Contact preference is not completed dealer contact or booking.
- Other primary images match their described subjects. The identified failures are the two combined deeper lines, not a recurrence of rules-fallback mutation.

## Genuine repair and normalized preservation

The actual first pass requested repair for the uncited decline in `terms.deeper[1]`. The lexical trigger was `certified`, matched by the unchanged `CLAIMISH` pattern; there is no apostrophe-based decline recognizer. The curly apostrophe was not the cause. The fresh second response changes that line from a curly-apostrophe “I can’t verify…” form to “I can't confirm engine-specific fuel-economy figures or a crash-test rating from these details…” and keeps the exact-model/year reporting requirement. The revision also removes the trigger word `certified`; that substantive wording change, not punctuation alone, clears the lexical warning. It adds no product fact and changes no other narration text, fact-ID array or visual object. Schema/default fields are serialized explicitly in the repaired response, including delivery pace and the decline's `unverified: true`; those are distinct from new source claims.

From the repaired raw response to normalized output:

- **48/48** texts and citation arrays preserved.
- **48/48** complete visual objects preserved.
- **26/26** bound image refs and **22/22** deliberate empty refs retained.
- No extra or missing narration unit; actual-stage `issues: []`.

Raw first-response SHA256: `8d29151681e44cf3f90a4ec682f412f60496cde11b2a256766dd498aaabf5207`.

Raw repair-response SHA256: `3fbe46382eff645df6e59d1549fa748444ffa87898dd47a6de4d20c51b578834`.

Normalized SHA256: `50248beb7003814bac87dde2b4dfe6a925ffc6837e7fba713f1672c12bfb232b`.

No paid provider visual check, TTS recording or acoustic test ran. The existing source-fixture coverage limitations remain documented in the historical audit. The above normalization preservation is demonstrated; complete source/literal coverage is not accepted until the three findings are resolved.
