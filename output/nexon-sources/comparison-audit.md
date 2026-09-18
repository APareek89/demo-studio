# Official-source comparison audit

Checked 18 September 2026 for the India market. This is a source audit for reviewing the generated registry, not a dealer quotation or a purchase recommendation. Manufacturer-material permission is recorded in manifest.json as user-confirmed for this local demo. No paid model calls or product API writes were made for this audit.

## Candidate names verified

- **Tata Nexon Fearless + PS, 1.2L turbocharged Revotron petrol, DCA.** The May 2026 brochure's page 40 matrix ticks the DCA column for this trim. Page 18 identifies the automatic as seven-speed. This is the petrol DCA, not the diesel AMT or CNG manual.
- **Maruti Suzuki Brezza ZXi+, 1.5L K15C petrol ISG, 6AT.** July 2026 brochure page 10 confirms this combination. The separate 1.0L Turbo Boosterjet row is six-speed manual; its engine figures must not be assigned to this automatic candidate.
- **Hyundai Venue HX10, Kappa 1.0L Turbo GDi petrol, 7DCT.** Official feature table 1, data row 2, lists DCT under HX10; brochure page 18 supplies seven speeds. Use regular HX10, not the separate HX10 Knight column or the HX10 diesel automatic.

## Tata Nexon: five supported facts

Primary source: [official May 2026 brochure](https://tata.cars/content/dam/tml/pv/products/nexon/year-2026/ice/promoting-vc/brochures/may/nexon-brochure-may.pdf). PDF pages below are one-based.

1. **Automatic:** Seven-speed dual-clutch automatic offered on the selected petrol trim. Exact excerpts: “DCA” (page 40, powertrain matrix, Fearless + PS row) and “7-SPEED DUAL CLUTCH AUTOMATIC” (page 18). Do not substitute AMT.
2. **Dimensions:** Length 3,995 mm, width 1,804 mm, height 1,620 mm; wheelbase 2,498 mm. Exact cells: “3995*1804*1620” and “2498” (page 40, specification table). These are exterior dimensions, not cabin-space measurements.
3. **Boot:** Petrol/diesel specification is 382 L. Exact cell: “382**”; measurement footnote: “Bootspace as per ISO V215” (page 40). The adjacent 321 L figure belongs to CNG, outside this candidate.
4. **Front-seat ventilation:** Included in this trim's feature list. Exact label: “Ventilated Driver & Co-Driver Seat” (page 39, Fearless + PS panel). Do not generalize to all Nexon trims.
5. **Rear cooling:** Rear air-conditioning vents are included through the trim's inherited equipment. Exact label: “Rear AC Vents” (page 38, Pure + panel); page 39 defines the higher-trim inheritance. This is not an exclusive advantage over the two rivals below.

## Maruti Suzuki Brezza: five supported facts

Primary source: [official current Brezza brochure](https://www.marutisuzuki.com/content/dam/msil/arena/in/en/assets/cars/brezza/brochures/new_brezza_brochure.pdf), page 10. Each equipment claim uses the ZXi+ column, not a neighbouring Turbo-qualified cell.

1. **Automatic:** The selected variant combines the 1.5L K15C petrol ISG engine with six-speed automatic. Exact labels: “1.5L K15C Petrol ISG” and “6-speed Automatic” (powertrain matrix). ZXi+ is ticked; the corresponding engine displacement is 1,462 cc in the specification sheet.
2. **Dimensions:** Length 3,995 mm, width 1,790 mm, height 1,685 mm; wheelbase 2,500 mm. Exact cells: “3995”, “1790”, “1685”, “2500” (specification sheet). Height is explicitly unladen; do not erase that qualification.
3. **Front-seat ventilation:** Available in ZXi+. Exact label: “Front Ventilated Seats” (Comfort and Convenience), with a tick in ZXi+ and dashes in the three preceding columns.
4. **Rear cooling:** Available in ZXi+. Exact label: “Rear AC Vents” (Comfort and Convenience), with ticks across all four trim columns.
5. **Flexible rear seating:** A 60:40 split rear seat is available in ZXi+. Exact label: “60:40 Split Seat (Rear)” (Comfort and Convenience), with ticks in ZXi and ZXi+.

**Boot-volume gap:** No numerical boot capacity was found in this current brochure or the captured official model-page text. Leave this field unknown; do not import an older 328 L figure or infer volume from luggage imagery.

## Hyundai Venue: five supported facts

Primary sources: [official Venue brochure](https://www.hyundai.com/content/dam/hyundai/in/en/data/brochure/venue.pdf) and [official feature tables](https://www.hyundai.com/in/en/find-a-car/venue/features). HTML locations below refer to the six ordered tables in the saved official page; the companion venue-feature-tables.txt preserves every row locator and exact HX10 column.

1. **Automatic:** HX10's 1.0L turbo petrol uses DCT (HTML table 1, data row 2, HX10 column). The exact brochure label “7 - speed DCT” appears on page 18 under the turbo-petrol engine. Do not substitute the diesel's six-speed automatic.
2. **Dimensions:** Length 3,995 mm, width 1,800 mm, height 1,665 mm; wheelbase 2,520 mm. Exact cells: “3 995”, “1 800”, “1 665^”, “2 520” (brochure page 18). Height includes R16 wheels and roof rails; HX10 has both (HTML table 3, rows 4 and 24). The 1,650 mm alternative is for R15 with roof rails.
3. **Boot:** The model brochure publishes 375 L. Exact excerpts: “Spacious boot (375 litres)*” and “As per VDA 215 method” (page 8). This is a model-family statement; no separate HX10 boot measurement is supplied.
4. **Front-seat ventilation:** HX10 is marked S. Exact label: “Front row ventilated seats” (HTML table 6, data row 5). Availability also covers other named higher trims; it is not exclusive to HX10.
5. **Rear cooling:** HX10 is marked S. Exact label: “Rear AC vents” (HTML table 6, data row 20). All listed HX trims are marked S.

## Registry review decisions

- All three selected candidates are petrol automatics, and all have documented front-seat ventilation and rear AC vents. Do not turn these shared features into Nexon-only claims.
- Preserve the precise automatic type and engine pairing. Gear count alone does not establish smoother operation, reliability, efficiency or suitability in traffic.
- All three list the same exterior length. Width, height and wheelbase differences alone do not prove rear-seat comfort, luggage practicality or family suitability.
- Preserve ISO V215 beside Nexon's boot figure and VDA 215 beside Venue's. This audit has not established equivalence of the measurement methods; do not claim a boot-space winner or a practical luggage advantage from the numerical difference. Brezza's figure remains unknown.
- No comparative price, ownership-cost, real-world mileage or safety-ranking claim is approved by this audit. No account of trim availability should be presented as dealer stock confirmation.
- Venue PDF extraction can reorder table headers. Use the saved HTML-derived tables for trim availability; the three malformed Leather Pack rows remain excluded.

## Evidence files

- Nexon original SHA256: `d590ff0c550a3de3ae7f77683a474cc7400fb319c16bf0e10a5e0e6cd70f738f`; visually checked pages 18, 38, 39 and 40 for this audit.
- Brezza original SHA256: `bdaa4654b016ad0e83c610de09d722d2381a8251a4f4630515e6fc7e81f4b591`; visually checked page 10.
- Venue original SHA256: `e08b9c95c3bac2603fe8f1051d519a8a26f7a348ad21b1f1ebf034f1b75fff9d`; visually checked pages 8 and 18. Exact feature HTML SHA256: `d5b646d7391b11ee495e402a6006950b4cae497dcb03d35ba89163061547ff79`.

Originals, retrieval times, permission metadata and URLs are recorded in [manifest.json](/Users/macbook/Documents/demo-studio/output/nexon-sources/manifest.json). The audit does not alter them or the application registry.
