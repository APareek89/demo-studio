# Independent source and visual audit — iterations 05 and 06

Final status: **iteration06 preserves all reviewed text, citations and raw picture/no-picture decisions.** The P1 fallback corruption is resolved in the exact-response replay. Source coverage and unmeasured-audio limitations below remain.

Historical iteration05 status: **raw Author text passes this semantic review; pre-fix normalized visuals fail.** `issues: []` is the actual authoring-validator result, not proof of semantic or visual correctness. The rules-fallback corruption below is being fixed separately; this section preserves the pre-fix evidence for comparison with an exact-response replay.

## Scope and provenance

Reviewed every clause in 48 raw units: one runtime overview, 16 main lines, 29 deeper lines and two closing statements. Compared the referenced fact IDs, full conditions and trim memberships with `final-source-v2/understanding.json`, the source PDF pages and the previously inspected actual image pixels. Then matched every unit by unchanged text to normalized `iteration-05/artifacts/author.json`.

- Source: `Hyundai_CRETA_Complete_Guide.pdf`, sole uploaded source ID `src_0ac142`, file SHA256 `f2159835f5993c55380132bc048a488476fbbc9e2b4a2f95a51fe558d32ae87c`.
- Frozen fixture: 68 manually reviewed facts, 10 unknowns and 48 manually described inspected image assets. The image IDs are actual derived assets; normalized-pixel hashes connect the inspected pictures to the extractor's output.
- Actual extraction plumbing ran with mocked providers and blocked sockets: 95 pictures, 26,467,885 bytes, eight mock vision batches, zero socket attempts. Retained 48 pictures total 15,012,240 bytes.
- Semantic facts and image tags are reviewed simulation inputs. A live model's Understand extraction accuracy was **not** evaluated. No paid model, TTS, web or external provider call was made for this audit.
- Raw response SHA256: `e312c06a28bb37adc76749f132cde7a3a196040b337dc062fa411e85f79f7b68`.
- Pre-fix normalized artifact SHA256: `8331081b56c54bf655d2a47319a55c8a478de2e9484015690c590894baf908ae`.
- Frozen registry SHA256: `f4965c3b537f13d1787137a1a8dadd5759554d340da020431fdcf9bbf6c086e7`.

## Text findings

No unsupported product statement, incorrect trim set, invented performance measurement or counted-component error was found in this candidate. This conclusion follows clause-level inspection, not merely the presence of valid IDs. The previous missing engine-choice citations were resolved by making the opening handoffs genuinely non-claim transitions; no new engine/gearbox capability is asserted in the F015/F016-only opening.

Reviewed groups and evidence:

- **Overview/opening and both deeper lines:** F015/F016 support stationary brake holding, standard fitment on King/King Knight/Lounge and conditional earlier automatic-only equipment rows. “Standard from King” in the alternative opening is compressed standard-fitment wording, not an assertion that earlier trims cannot offer it. The deeper wording correctly distinguishes equipment-table rows from offered powertrain combinations.
- **Three anchors and both deeper lines:** F003/F005/F006/F008/F009/F065–F068 support engine-dependent gearbox choice and King-only turbo automatic. F022/F023 support standard split seating and its storage function; F025 supports six standard airbags including E. No crash-test result is implied.
- **All three engine main lines and all three deeper lines:** SX non-turbo petrol is manual-only; SX Premium petrol offers manual and IVT; SX Premium diesel is manual-only. The diesel automatic set is exactly EX(O), S(O), King, King Knight and Lounge. Full petrol MT/IVT and diesel MT/AT sets match F065–F068 and every dot/dash in PDF p31. F006 is King-only turbo/DCT, without implying all Kings are turbo. F004/F007/F008/F009 support the stated power, torque, rev ranges and transmission specifications on p16. The source date is explicitly a compilation date, not live stock. Smooth acceleration is attributed to Hyundai marketing (F010), not converted to a measurement.
- **Wheels, including all deeper lines:** F017/p8 supports each steel/alloy type and trim. F064/pp29–30 supports tyre sizes. Red caliper and black spokes are directly visible in the selected raw picture. No ride, clearance or tyre-safety result is inferred.
- **Split seating, including all deeper lines:** F022/F023 support standard split function; F021/F024/F060 retain different start trims for rear recline and sunshades. F001/F020/F059 support five seats, rear vents and rear armrest. No personal-fit, boot-litre, cooling-time or rear-legroom result is invented.
- **Airbags and forward assistance, including all deeper lines:** F025–F036 and F062 preserve standard equipment versus selected assistance. Cameras start SX Premium; stop-and-go cruise remains automatic-only on King/King Knight/Lounge. Driver responsibility and no guaranteed intervention are retained. Rear sensors are not described as cameras or automatic parking.
- **Climate/Alexa, including all deeper lines:** F039/F040 support independent front settings from S(O). F043/F044 support SX Home-to-Car functions, separate Alexa hardware and power/network limitations. Remote phone-app engine start is explicitly not established. F041/F042 retain 26.03 cm/10.25 inches. F045/F046 retain compatible phone mirroring from EX and the SX-and-above adapter condition.
- **Seat airflow/roof, including all deeper lines:** F037/F038 support the source's cool-airflow function from SX Premium without a cooldown guarantee. F048/F049 preserve panoramic availability from EX(O) and voice operation from SX. Bose is correctly an **eight-speaker system with a subwoofer** (F050), avoiding an implied extra ninth speaker. F051/F052 preserve driver-side and passenger-side lamp scopes; F053 does not become a refrigeration-temperature claim.
- **Quote and both deeper lines:** F054–F056 preserve the dated conflicting entry amounts, ex-showroom/on-road distinction and city-dependent additions. Neither amount is presented as today's confirmed price.
- **Front storage and both deeper lines:** F061 supports standard compartment storage and King/King Knight/Lounge sliding adjustment. Visible open storage is not claimed to demonstrate sliding, cooling, locking or a specific capacity.
- **Terms and all three deeper lines:** F057/F058 retain petrol-only, up-to-seven-year, separately paid extension and separately paid Shield of Trust. Missing certification, exact-model/year crash report, package price/coverage, live stock and delivery are treated as unresolved evidence. The contact request does not claim completed contact or booking.
- **Closing statements:** These are fit/decision guidance and a contact-preference action, not uncited product-performance claims. Their CTA wording is consistent with the plan's contact action and does not fabricate a destination.

Transitions such as “the engine deserves attention,” “the front armrest awaits inspection,” and “the seat cushions give us another focus” introduce subjects without asserting additional capabilities. The generic handoffs therefore do not need unrelated product facts attached merely because they name the next object.

`160 PS` remains in deeper, consistent with the user's explicit decision to retain the validator. This is a reference-script deviation, not absent PDF evidence or an audit defect. No unsupported acceleration, mileage, boot-litre, ground-clearance, top-speed, crash-rating or rival figure was found.

## P1 — rules fallback corrupts correct raw picture bindings

All 30 raw image-bound units have a suitable literal **primary** pictured subject. Secondary trim/availability facts remain textual evidence; a picture of an engine does not itself establish its trim matrix. The 18 deliberate raw `none` units avoid pretending a photograph proves policies, prices, a combined three-USP sequence or a different feature.

Normalization preserves all 48 text units and citation arrays, but changes **22 visual refs**. These are post-processing changes, not Author output or missing-source failures. Concrete wrong subjects include:

- `engine-choices.lines[0]`: petrol engine becomes steering-wheel paddle `im_pdf_893405c770ce75e06502`.
- `engine-choices.lines[2]` → `engine-choices-3.lines[0]`: turbo engine becomes tyre-pressure cluster `im_pdf_11d7b41540b2776d6e24`.
- `wheels.lines[0]`: wheel/caliper becomes seat movement buttons `im_pdf_b64c9a8093b659198cc1`.
- `shared-space.lines[0]`: folded rear seats become empty boot with upright seats `im_pdf_31ed8989f6cc45b71b53`.
- `shared-space.deeper[1]`: recline/sunshade discussion gets tail lamps `im_pdf_cba8789de09b20cb7670`.
- `shared-space.deeper[2]`: rear-seat/vent/rear-armrest discussion gets front centre armrest `im_pdf_25b7515fe0c9e93714e1`.
- `airbags-and-help.lines[0]`: airbags become lane-keeping illustration `im_pdf_beece6d09d55074c47bb`.
- `airbags-and-help.lines[1]` → `airbags-and-help-2.lines[0]`: forward collision becomes electric seat controls `im_pdf_6fbbc0ada78471786303`.
- `climate-and-remote.lines[1]` → `climate-and-remote-2.lines[0]`: Alexa Home-to-Car becomes USB/power sockets `im_pdf_74629d719ebbc53bbd9b`.
- `climate-and-remote.deeper[1]`: phone mirroring gets auto-hold controls `im_pdf_e1266b7974b364c1c1ba`.
- `seat-and-roof.lines[0]`: ventilated-seat arrow illustration becomes seats/panoramic-roof photograph `im_pdf_7df2ff055b2405e0a449`, which has no arrows despite the line explicitly mentioning them.
- `seat-and-roof.deeper[2]`: glove-box cooling gets loaded boot `im_pdf_086219c79f5c77a4f468`.

Other replacements assign an alloy wheel to steel-wheel or generic tyre-size text; auto-hold controls to standard-safety text; a dark cabin to assistance functions; a manual lever to three mixed USPs or general closing guidance; and exterior/engine/armrest pictures to ownership text. Some are contextual rather than directly contradictory, but none establishes the missing literal evidence. The full 22-row delta list is retained below.

Required correction: fallback must preserve valid explicit primary bindings and deliberate no-image decisions rather than replacing them through broad noun/score matches. The live pixel-review path and semantic evidence rules must retain their meaning. Replaying the identical raw responses after the small post-processing correction will isolate the fix from new model wording.

## Simulation limits, not PDF impossibilities

- The manual registry omits overall length **4,330 mm**, width **1,790 mm** (pp3/29), and front McPherson-strut/coil-spring and rear coupled-torsion-beam suspension (p29). Coach/Planner list these as gaps in supplied support, not explicitly as facts absent from the PDF. They were neither spoken nor falsely denied in this candidate. Do not report them as missing uploaded evidence.
- The manual image description for panorama `im_pdf_74c2156461739f493698` omits visibly deployed rear-window mesh shades and rear centre-console vents. The seatback-table photo `im_pdf_3674ecf9de31118cb325` partially shows the vents too. Their gap labels reflect catalogue-description coverage. The final script does not falsely deny that those pixels exist.
- Source facts for the exact engine/gearbox matrix were initially omitted; v2 independently added F065–F068 from p31. No old fact, schema or validator was changed to make that correction.
- A three-USP line needs multiple distinct visual subjects but has only one `visual.ref`. A neutral car photo is not literal price or warranty evidence. Main-subject handoff narration can also name the next object before its picture appears. These are representation boundaries; binding an arbitrary picture does not solve them.
- The source still does not establish the target's market-best reputation, guaranteed loaded climb, comparative rough-road comfort, driver eye-height, rapid cabin cooling or phone-app start. Literal target prose implying those claims must not be treated as required factual output.
- Final pre-fix metadata reports preparation at 498 words, and the selected default route at 347 words / 182.63 seconds **estimated**, `measured: false`. This audit does not certify TTS duration, published audio or customer playback. Recording and the existing measured-duration publication check remain necessary.

## Complete pre-fix visual-ref delta ledger

1. `three-anchors.lines[0]` → `three-anchors.lines[0]`: `none` → `im_pdf_3aa2ebf1c9ed94570455`. Resulting pixels: Manual gear lever and centre console buttons
2. `engine-choices.lines[0]` → `engine-choices.lines[0]`: `im_pdf_98cd4a320f9dbfd33bbd` → `im_pdf_893405c770ce75e06502`. Resulting pixels: Steering wheel paddle marked plus
3. `engine-choices.lines[2]` → `engine-choices-3.lines[0]`: `im_pdf_87bac17ee980151549ba` → `im_pdf_11d7b41540b2776d6e24`. Resulting pixels: Digital instrument cluster showing a tyre pressure diagram with four wheel-position readings; screen values are illustrative.
4. `wheels.lines[0]` → `wheels.lines[0]`: `im_pdf_a4463ebb4d4d6329f98a` → `im_pdf_b64c9a8093b659198cc1`. Resulting pixels: Two seat movement buttons on the side of a front-seat backrest, with seat pictograms on their faces.
5. `wheels.deeper[0]` → `wheels.deeper[0]`: `none` → `im_pdf_a4463ebb4d4d6329f98a`. Resulting pixels: Black alloy wheel and tyre with a red brake caliper visible through the spokes; no wheel size can be measured from this photo.
6. `wheels.deeper[2]` → `wheels.deeper[2]`: `none` → `im_pdf_a4463ebb4d4d6329f98a`. Resulting pixels: Black alloy wheel and tyre with a red brake caliper visible through the spokes; no wheel size can be measured from this photo.
7. `shared-space.lines[0]` → `shared-space.lines[0]`: `im_pdf_adb415f161dfc9567dde` → `im_pdf_31ed8989f6cc45b71b53`. Resulting pixels: Open empty boot with rear parcel tray spanning the luggage area and rear-seat head restraints above; rear seats are upright.
8. `shared-space.deeper[1]` → `shared-space.deeper[1]`: `none` → `im_pdf_cba8789de09b20cb7670`. Resulting pixels: Rear of CRETA with horizontal connected red lamps across the tailgate, rear window and badge.
9. `shared-space.deeper[2]` → `shared-space.deeper[2]`: `none` → `im_pdf_25b7515fe0c9e93714e1`. Resulting pixels: Front seats and the closed centre-console armrest with adjacent cup holders; no rear seatback table or tablet appears.
10. `airbags-and-help.lines[0]` → `airbags-and-help.lines[0]`: `im_pdf_a54e8e56f4b50c2f5596` → `im_pdf_beece6d09d55074c47bb`. Resulting pixels: Top-down lane-keeping illustration showing a vehicle between road markings and a blue projected curved path; this is an assistance diagram, not a recorded road test.
11. `airbags-and-help.lines[1]` → `airbags-and-help-2.lines[0]`: `im_pdf_87d94ba1ddd0b388c716` → `im_pdf_6fbbc0ada78471786303`. Resulting pixels: Side of a front seat with multiple electric adjustment switches visible on the seat base.
12. `airbags-and-help.deeper[0]` → `airbags-and-help-2.deeper[0]`: `none` → `im_pdf_e1266b7974b364c1c1ba`. Resulting pixels: Electronic parking brake and AUTO HOLD button
13. `airbags-and-help.deeper[2]` → `airbags-and-help-2.deeper[2]`: `none` → `im_pdf_719c076eb7882f731dcd`. Resulting pixels: Dark cabin with dashboard, steering wheel, seats and contrasting metallic-colour trim inserts; no material composition can be established visually.
14. `climate-and-remote.lines[1]` → `climate-and-remote-2.lines[0]`: `im_pdf_497f55977a7d19718157` → `im_pdf_74629d719ebbc53bbd9b`. Resulting pixels: Centre-console charging panel with two USB-C ports and a covered twelve-volt socket, with port symbols and ratings printed on the panel.
15. `climate-and-remote.deeper[1]` → `climate-and-remote-2.deeper[1]`: `none` → `im_pdf_e1266b7974b364c1c1ba`. Resulting pixels: Electronic parking brake and AUTO HOLD button
16. `seat-and-roof.lines[0]` → `seat-and-roof.lines[0]`: `im_pdf_498ba48d46b3d2258714` → `im_pdf_7df2ff055b2405e0a449`. Resulting pixels: Two front seats and panoramic roof seen from within cabin
17. `seat-and-roof.deeper[2]` → `seat-and-roof-2.deeper[2]`: `none` → `im_pdf_086219c79f5c77a4f468`. Resulting pixels: Open boot containing luggage and groceries
18. `quote.lines[0]` → `quote.lines[0]`: `none` → `im_pdf_25b7515fe0c9e93714e1`. Resulting pixels: Front seats and the closed centre-console armrest with adjacent cup holders; no rear seatback table or tablet appears.
19. `quote.deeper[0]` → `quote.deeper[0]`: `none` → `im_pdf_2f931aad60c08d1f4a9b`. Resulting pixels: Front three-quarter view of the CRETA on a mountain road
20. `terms.lines[0]` → `terms.lines[0]`: `none` → `im_pdf_87bac17ee980151549ba`. Resulting pixels: Turbo petrol engine illustration with printed power and torque labels
21. `terms.deeper[1]` → `terms.deeper[1]`: `none` → `im_pdf_2f931aad60c08d1f4a9b`. Resulting pixels: Front three-quarter view of the CRETA on a mountain road
22. `closing[0]` → `closing[0]`: `none` → `im_pdf_3aa2ebf1c9ed94570455`. Resulting pixels: Manual gear lever and centre console buttons


## Final delta — iteration06 exact-response replay

The code-only replay resolves the P1 fallback corruption without changing the independently reviewed narration. Matched all **48/48** units from the iteration05 raw Author response to `iteration-06/artifacts/author.json`: all text and fact-ID arrays are unchanged, all **30/30** explicit image refs are retained, and all **18/18** deliberate `none` refs remain empty. No extra text unit, changed visual kind, changed citation array or missing unit was found. The 22 pre-fix visual substitutions above are therefore eliminated. `issues` remains empty.

Independently compared all nine shared Coach/Planner/Author request, response and schema JSON files between iterations05 and06: **9/9 byte-identical**. This isolates the observed visual improvement to post-processing, not different simulated prompts or answers. The reviewed raw image IDs still resolve to the same inspected source catalogue; no second semantic review was necessary because the text and citations are immutable.

Read the `server/agents/visuals.py` diff and compared definition source against HEAD: `align` is the only changed definition. `_vision_batches`, `Assignment`, `ImageAudit` and `VisualsOut` are byte-identical. The entire `align` prefix through the completed pixel-decision branch is byte-identical, including the branch that applies model image rejections. The change removes rules-only replacement/diversity mutations and changes fallback status messages; rule proposals remain diagnostic. It does not weaken the live pixel-review branch or change the typed schema.

The current audit method remains `rules_fallback` with `model: null`, not a completed provider pixel inspection. Preserving independently reviewed source bindings is demonstrated; live model visual-proof performance and measured TTS/playback duration are not established by this run. The original source-catalogue omissions and one-image-per-line/context limitations remain explicitly documented above.

Final iteration06 normalized artifact SHA256: `ea75ce2786da4424b0e27a07f6af56cbcec8d48bd00539331078308b4ce07f2b`.
