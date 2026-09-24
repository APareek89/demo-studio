# Final saved draft: literal picture review

Reviewed the actual saved Script and normal Deck from `author-final-unedited`, before any review patch or approval. Script SHA256 `680a3a3f3433e8ebf581485460c510933f0dfec699a2b96f1801837b783e7a4b`; Deck SHA256 `943f9c77336c5764c25bdbbfb089814d2a204f66a18692a88f4f34b047d0eb2e`. Viewed all 16 distinct pictures selected by main/overview Script or generated Deck in `final-used-pictures-1.jpg` and `final-used-pictures-2.jpg`, made from exact supplied files. Closing has no Script image reference. No paid/model call, approval, app mutation or synthetic bundle was made.

## Finding and cause

Script main/overview image subjects are safe as illustrations. The generated Deck is not ready: its regular-petrol and turbo slides use a grille proxy; the rear-seat, cabin, roof and charger slides use a side-profile hero. `visual-audit.json` is `rules_fallback` with `lines: []`, not a successful pixel audit. `deck.choose_media` rejects each unproven Script binding at its existing full-coverage gate, then explicitly chooses a proxy. This is intentional fallback rather than a lost Script reference. It must not be relabelled as a successful visual audit.

The proxy branch also turns the first cited claim into a part label. It pins five-door/five-seat body style to a grille (`sl01-c1`), and a mixed trim/wheel claim to a wheel in a different picture (`sl06-c1`). Neither pin proves those claims. The literal wheel box for the rear-three-quarter image is additionally inaccurate: its x=.706 y=.685 w=.104 h=.171 box lands near the rear bumper, not either visible wheel. Do not use that tag or invent replacement coordinates.

## Safe normal review corrections

`final-reviewed-deck-patch.json` is a proposed ordinary PATCH `/api/demos/dm_7bbf10d0/align/deck` body. It uses only allowed existing picture IDs. The endpoint keeps newly chosen images as `proxy:true` illustrations until audited. It does not certify whole-line fitment, variant availability, service/network prerequisites or warranties from pixels. No new anchor coordinates are proposed.

- `sl01`: white front-three-quarter vehicle picture from the overview; body-style text is a panel caption with no part/anchor.
- `sl02`: no picture for three unrelated highlights; editorial agent clears its outcome refs too.
- `sl03`/`sl04`/`sl05`: exact source specification panels visibly headed regular petrol [6MT and IVT], diesel [6MT and 6AT], turbo petrol [7DCT], respectively. These panels match the spoken pairings and avoid the wrong grille/selector substitutions.
- `sl06`/`sl07`: no picture for multi-trim wheel/lighting comparisons. The source side-profile and rear-three-quarter images cannot establish all finishes, sizes or trim mappings. Clearing media also clears their old callouts through the normal endpoint.
- `sl08`: actual folded rear-seat picture showing one split section down and the neighbouring seat upright.
- `sl09`: supplied boot photograph visibly containing bags behind the rear bench; it does not establish litre capacity or complete seat count.
- `sl10`: supplied multi-airbag cabin illustration. It illustrates airbags, not a safety outcome guarantee or complete driver-assistance/variant availability.
- `sl11`: no picture for the multi-trim driver-assistance availability and stop-and-go claim.
- `sl12`: supplied close dashboard display picture (`im09`). Literal view shows the infotainment display plus instrument cluster behind the steering wheel, so the current focus `dual screen dashboard layout` is acceptable. My preliminary concern that it was only one screen was withdrawn after viewing these pixels. No adapter is visible; no adapter-proof pin should appear.
- `sl13`: supplied full dashboard cabin context (`im06`), without implying it proves Bluelink availability, connectivity, compatibility or separate Alexa purchase. Literal focus `driver perspective dashboard` is appropriate.
- `sl14`: supplied overhead glass-roof cabin picture (`im07`). Glass panel is plainly visible; voice activation and trim availability remain source statements, not visual proof.
- `sl15`: no picture for dated and conflicting pricing terms.
- `sl16`: supplied close wireless-charging pad with charging phone (`im05`). It illustrates the part; trim and phone compatibility stay textual conditions.
- `sl17`/`sl18`: no picture for warranty, package-cost, specification-change and purchase-next-step terms.
- `sl00`/`sl19`: unchanged supplied side-profile hero for opening/closing branding; no fact pins.

This reviewed Deck selection is not a browser geometry/render pass. Actual rendered desktop/mobile slides and anchors must still be checked after normal review/build. No narration wording or fact citations require changing for these picture corrections.
