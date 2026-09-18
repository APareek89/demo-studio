# Iteration 2 competitor review

Reviewed all 95 rival facts across seven source groups against the original official material, the first reviewed registry and the visually checked addenda. Prepared **17 fact patches and 3 holds**, leaving 92 approved rival facts after application. No production write or paid call was made.

## Apply through Align

- Send each `review-edits/competitor-patches.json` row's `patch` to `PATCH /api/demos/dm_36d47b86/align/facts/{id}`; then send each `competitor-approvals.json` row's `patch` to `POST /api/demos/dm_36d47b86/align/facts/{id}/approval`.
- `competitor-provenance.json` retains every before value, reason, owner and supporting source. Recheck these preconditions if rival content changes. Product F-facts are outside this payload.
- `competitor-id-map.json` maps all 74 previous facts, including absent rows, split claims and separately owned replacements. Never transfer an approval by numeric ID alone.

## Required corrections

- **C1-002/003/004/005/006:** restore ZXi+ scope for ambient lighting, ventilated-seat cooling levels, large screen, app launcher and 360-view camera. The model page supplies feature details; the brochure matrix supplies trim availability. Their provenance remains distinct.
- **C2-012/013:** restore HX10/HX10 Knight scope for Bose audio and ADAS.
- **C3-023–028:** restore printed efficiency units. Petrol figures use km/l; CNG is **26.90 km/kg**, not 26.90 kg. The brochure explicitly identifies these as certified test figures. They do not establish real-world mileage or a running-cost comparison.
- **C4-018:** restore Bluelink-equipped trim scope, paid renewal after three years and network conditions.
- **C6-001/003/004:** restore the dropped “+” in ZXi+; retain the selected 1.5L K15C petrol/6AT pairing.

## Prior holds survive semantic remapping

- Old **C2-003 → new C2-003** remains held: generic Venue height omits wheel/roof-rail conditions. Qualified C4-003/C4-004 remain usable.
- Old **C2-007 → new C2-007** remains held: generic four-cylinder wording must not describe an unspecified or turbo-petrol engine.
- Old **C2-015** navigation wording was not separately re-extracted. Hold the related generic dual-display highlight **C2-011** and retain qualified HX10/HX10 Knight navigation **C5-007**. **New C2-015 means six airbags and must stay approved.**
- Keep the new `stated` classifications for ordinary Brezza emissions and Venue boot capacity; do not restore their previous `certified` labels. New Brezza fuel-efficiency rows have an explicit certification footnote and can remain `certified`.

## Positive comparison material retained

- **Brezza ZXi+, 1.5L K15C petrol ISG, 6AT:** C6-001 establishes the pairing. C6-002–005 support front-seat ventilation, rear AC vents, ISOFIX and 60:40 rear seating. C3-007/009/013 describe the correct engine. The 1.0L Turbo manual outputs belong to a different powertrain.
- **Venue regular HX10, 1.0L Turbo GDi petrol, 7DCT:** C7-001 establishes the pairing. C7-002–005 support ventilation, rear AC, ISOFIX and 60:40 rear seating. C4-011–013 describe the turbo engine. HX10 Knight and diesel AT remain distinct configurations.
- These support useful shared-feature and transmission comparisons. They do not establish smoother driving, better rear-seat comfort, lower ownership cost or a safety winner. No Brezza boot figure was added. Keep Nexon ISO V215 and Venue VDA 215 measurements distinct; no practical luggage-fit or method-equivalence claim is established.
- Actual Q07 and Q08 must still cite the approved Nexon and rival facts, state the website/date verification caveat and demonstrate a useful comparison. Source review does not complete either customer path.

## Seven source groups

- `src_07ea50`, Brezza model page: 8 rows checked; five trim-scope patches. Feature details agree with the saved official model page and page-10 brochure matrix.
- `src_acce5c`, Venue highlights: 15 rows checked; two trim-scope patches and three semantic holds. The former navigation ID now names airbags.
- `src_b28460`, Brezza brochure: 34 rows checked; six efficiency-unit patches. Engine columns, CNG modes, tyre/spare-wheel details, brakes, warranty and safety rows agree with page 10. No turbo-manual output is assigned to the selected automatic.
- `src_43582f`, Venue brochure: 18 rows checked; one Bluelink correction. Dimensions and powertrain figures agree with page 18; boot basis remains VDA 215; extended warranty remains distinct from standard warranty.
- `src_73036b`, Venue feature tables: 10 rows checked; no patch. Exact HX columns and conditional `S^` footnotes remain intact. The malformed Leather Pack rows are absent.
- `src_87ab79`, reviewed Brezza addendum: 5 rows checked; three lost-plus corrections. Original manufacturer PDF and matrix provenance remain in the addendum.
- `src_64d8ad`, reviewed Venue addendum: 5 rows checked; no patch. The selected regular HX10 pairing and family features agree with the visual matrix and independent official HTML cells.

All source refs match their owning competitor source, and every owner retains role `competitor`. The addenda are identified as reviewer transcriptions of the original PDFs, not new manufacturer publications. Original source text and rendered pages are under `output/nexon-sources/rivals/` and `output/nexon-sources/review/`.

Raw iteration-2 registry SHA256: `1dbe622300027330b2539902baf53fc891ce23a7c93220093d0c964806234f7f`. All 95 row decisions and the complete 74-row remapping are in the JSON sidecars. Local Fact-schema simulation, source ownership and semantic-hold checks passed. These payloads have **not been applied**.
