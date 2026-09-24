# Iteration08 independent source audit

**Result:** the three defects that blocked iteration07 are corrected. No additional unsupported product clause, broadened eligibility rule, incorrect trim set, invented quantity, or wrong pictured subject was found in this review. This is a manual audit of the supplied simulation evidence, not a live-provider or measured-audio certification.

Reviewed all **49 units**: one runtime overview, 18 main lines, 28 deeper lines and two closing statements. Main line count includes the three separately illustrated lines of the three-anchor opening. Inputs were the fresh `iteration-08/calls/author-01.response.json`, actual-stage `iteration-08/artifacts/author.json`, frozen `final-source-v2/understanding.json`, previously verified PDF page evidence and inspected extracted images. Neither prompts, code nor generated JSON was edited.

## Previously blocked findings: resolved

1. **Warranty scope:** `terms.lines[0]` now says “extended warranty up to seven years is petrol-only and separately paid.” F057's duration and fuel restriction survive together on the default path, with F058's payment condition. `terms.deeper[0]` retains the same boundary. The statement no longer implies diesel is excluded from every possible extended-warranty offering.
2. **Manual versus automatic picture:** `three-anchors.lines[0]` still correctly explains gearbox-dependent availability and automatic-only turbo, but deliberately uses `kind: none`. It no longer displays a manual lever as the illustration of that contrast. The corresponding deeper comparison also uses `none`.
3. **Steel versus alloy picture:** `wheels.lines[0]` now speaks only about the visible black alloy spokes and alloy availability. The referenced `im_pdf_a4463ebb4d4d6329f98a` literally shows that alloy wheel. The steel/alloy trim comparison is in `wheels.deeper[0]` with `none`; the multiple tyre-size line also uses `none`. This passes because the pictured option and spoken object now match, not because both objects belong to a broad “wheels” family.

## Clause and scope checks

- **Auto hold and opening:** F015/F016 support S(O)/SX Premium automatics and standard fitment from King. Deeper correctly names King/King Knight/Lounge and keeps the equipment-table S(O) Knight automatic-only entry distinct from its absent offered automatic powertrain, supported by F006/F066/F068. No all-surface guarantee is added. Gearbox-preference handoffs assert no new capability.
- **Three anchors:** F003/F005/F006/F008/F009/F065–F068 support gearbox/engine scope; F022/F023 support adjustable passenger/storage arrangements through the split rear seat; F025 supports standard airbags. The next-subject petrol mention is also cited to F003. No seat-sliding mechanism, luggage capacity or crash score is invented.
- **Engine main and deeper:** Non-turbo petrol manual first appears on E and automatic on EX(O), with SX manual-only and SX Premium both. Diesel SX Premium is manual-only; diesel automatics are exactly EX(O), S(O), King, King Knight and Lounge. Full deeper MT/automatic lists match F065–F068/p31, retaining gaps instead of implying an uninterrupted run through all later trims. Turbo is automatic-only and King-only without turning every King into turbo. F004/F005 support 117.5 kW/160 PS at 5,500 r/min, 253 Nm at 1,500–3,500 r/min and seven-speed DCT. The compilation date is not presented as current stock.
- **Wheels and seating:** F017 supports exact wheel types and trim mappings; F064 supports the tyre-size strings. The claim is that tyre numbers do not establish suspension design, not that the PDF lacks a suspension specification. F022/F023 preserve standard split function, F021/F024 preserve two-step recline and its exact trim scope, and F063 remains a qualitative luggage purpose. No boot-litre, ride, ground-clearance or personal-fit result is inferred.
- **Safety:** F025 supports the six-airbag configuration, including E; the actual airbag illustration depicts the correct system and includes its six-airbag label. F031/F032/F034 preserve King/King Knight/Lounge forward assistance and attentive-driver responsibility. F030's pictured tyre readings are explicitly illustrative. F035/F036 retain cameras from SX Premium versus automatic-only stop-and-go cruise on King/King Knight/Lounge. No autonomous-operation, guaranteed-intervention or automatic-parking claim appears.
- **Climate and connected features:** F039/F040 support independent front settings from S(O). F043/F044 support Alexa from SX with separate hardware and required power/network; “before getting in” describes the sourced remote function, not a cooling-time promise. F045/F046 preserve compatible phone mirroring from EX and the required SX-and-above adapter. F041–F043 retain 26.03 cm/10.25 inches and the stated Bluelink period/count. F047 preserves the both-front powered-seat/memory package on King/King Knight/Lounge versus the earlier driver-seat adjustment on SX Premium.
- **Ventilation, roof and conveniences:** F037/F038 support cool airflow from SX Premium without rapid-cooling or refrigerated-seat claims. F048/F049 retain EX(O) panoramic availability and SX voice operation. F050 remains an eight-speaker system with its subwoofer, not an extra ninth unit. F051/F052 preserve driver-side/passenger-side lamp scopes; F053 supplies no cooling temperature or time.
- **Quote, storage, warranty and close:** F054–F056 retain both conflicting dated entry amounts, ex-showroom/local additions, and the need for a current itemised quote. F061 supports standard armrest storage and King/King Knight/Lounge sliding; the still is explicitly not proof of the motion in deeper. F057/F058 retain the full paid up-to-seven-year petrol restriction in main and deeper. Missing fuel-economy/crash reports, package price/coverage, stock, delivery and booking remain unresolved. Contact preference does not become completed dealer contact or booking. Closing guidance selects an offered combination without inventing customer needs or a personal performance result.

Every product-bearing bridge was included in the citation check. Other handoffs invite attention to a later subject or give general decision guidance; they do not smuggle in uncited capabilities. `160 PS` remains in deeper under the user's accepted validator-preserving choice. No forbidden acceleration, mileage, boot-litre, ground-clearance, top-speed, crash-rating or rival figure was invented.

## Literal subjects and preservation

All **29 explicit image refs** resolve to the reviewed source catalogue and show the stated primary object: auto-hold control; split rear seatbacks; airbag system; distinct petrol/diesel/turbo engine; black alloy wheel; loaded boot; forward-detection diagram; tyre-pressure display; camera-view composite; dual-zone climate panel; Alexa Home-to-Car illustration; ventilated-seat airflow; panoramic roof; Bose speaker layout; puddle-lamp ground illumination; or front-armrest compartment.

The **20 deliberate no-image units** include contrasting gearbox/wheel examples, multi-feature statements, functions lacking a literal operating picture, and policies/prices. They are preserved rather than populated with related-but-different pictures. Same-object availability facts still come from their cited table, not an inferred trim identified from pixels. A still locates the actual subject without claiming to prove an unshown movement, a measured outcome or a full availability matrix. This limitation does not license the rejected manual/automatic or steel/alloy substitutions.

Raw-to-normalized comparison matched every unit uniquely by unchanged text:

- **49/49** text units preserved; no extra or missing unit.
- **49/49** fact-ID arrays preserved.
- **49/49** complete visual objects preserved, including ref, kind and focus.
- **29/29** image bindings and **20/20** intentional empty bindings preserved.
- Actual-stage `issues: []`; no rules-fallback corruption found.

Raw SHA256: `71c6ea37e76510b852e5e07cdb46e7eed27f675fc7d9d31b72a7d1f235ca91f4`.

Normalized SHA256: `3aa440850f5d5be0e21c7692d012552749c8382e51cab59867d922754ff84a8b`.

## Boundaries

The frozen facts/tags are manually reviewed simulation inputs; known fixture-coverage omissions remain documented in the historical source audit. No omitted-but-present source fact is falsely denied in this candidate. The artifact still reports `rules_fallback`, `model: null`; no live provider pixel check ran. Preparation is 500 words against the retained 495-word floor. The selected route is 348 words / 183.16 seconds **estimated**, `measured: false`. Provider quality, acoustics, recorded duration and customer playback are not certified by this audit; recording and the existing measured-duration publication gate remain required.
