# Iteration 02 script audit against baseline

Read-only comparison of `iteration-02/artifacts/author.json` with the frozen iteration00 artifact and `baseline-criteria-audit.md`. Counts use the app's `author.words`, `narration.default_route` and `narration.preparation_report` under MOCK_LLM=1, isolated storage and blocked sockets. No source edits or paid providers were used. The user's later decisions remain binding: the goal is a reference; existing validators, the 495-word preparation margin and the measured 180-second publication gate remain intact.

## Quantitative comparison

| Measure | Baseline00 | Iteration02 |
|---|---:|---:|
| Rendered segments / complete main lines |16 /24|16 /16|
| Rendered narration batches within26–33 words |6/16|16/16|
| Complete main lines within26–33 words |7/24|16/16|
| Powertrain rendered batches |3, from4 complete lines|3, each one complete line|
| Other proof-stop maximum |2 batches|2 batches|
| Distinct rendered-batch opening words |16/16|16/16|
| Intro words / outcome words |31 /37|30 /32|
| Separate runtime overview |23 words, no digits|23 words, no digits|
| Segment checkins |2 /16 words|0 /0 words|
| Final closing lines |2 /45 words|2 /45 words|
| All closing statements including checkins |4|2|
| Eligible segment narration |411 words|427 words|
| Full prepared inventory |495 words|495 words|
| Eligible rendered segments |14|14|
| Selected default route |9 segments /366 words|11 segments /404 words|
| Default-route estimate at app1.9words/s |192.63s|212.63s|
| Default route at reference2.24words/s |163.39s|180.36s|
| Full prepared inventory at2.24words/s |220.98s|220.98s|
| Deeper material, excluded from guided duration |31 lines /1,057 words|28 lines /987 words|
| Reported author issues |0|0|
| Pixel-audited lines /images |0 /0|0 /0|

Iteration02 role totals are intro30, outcome32, proof368, features26 and establish33. Its preparation is **427 eligible segment words +23 overview +45 final closing =495**; intro/outcome's62 words and deeper's987 words do not count. Baseline had411 eligible words plus16 checkin words, the same23-word overview and45-word final closing. No exact duplicate line is excluded by the accountant in either case; this is not proof that all meanings are distinct.

The default route in iteration02 selects `engines`, `engines-2`, `engines-3`, `wheels`, `space`, `safety`, `safety-2`, `controls`, `controls-2`, `armrest`, `terms-and-unknowns`. It omits the two delighters batches and the ownership batch. It adds cabin coverage compared with baseline. The 495-word full prepared inventory remains260.53s at the app's unvoiced1.9words/s estimate. The saved `narration_preparation` reports `words:495` but `seconds:212.63` because these fields refer to prepared inventory and selected default route respectively. Neither is measured audio. No publication-duration pass is claimed.

## Exact delivery batches

| Rendered segment | Role /stop | Narration words |
|---|---|---:|
| opening |intro|30|
| three-choices |outcome|32|
| engines |proof /powertrain|31|
| engines-2 |proof /powertrain|31|
| engines-3 |proof /powertrain|30|
| wheels |proof /stance-and-ride|27|
| space |proof /space-and-practicality|33|
| safety |proof /safety|31|
| safety-2 |proof /safety|31|
| controls |proof /cabin-and-tech|31|
| controls-2 |proof /cabin-and-tech|32|
| comfort |proof /delighters|31|
| comfort-2 |proof /delighters|31|
| price |proof /ownership|29|
| armrest |features|26|
| terms-and-unknowns |establish|33|

Every batch now consists of one complete main line; no short fragments are being mistaken for compliant delivery batches. Stop allocation is powertrain3, stance1, space1, safety2, cabin2, delighters2 and ownership1. Proof order now follows the existing compact-SUV library: powertrain → stance → space → safety → cabin → delighters → ownership. Baseline inverted cabin and delighters.

The opening words are **CRETA's, Your, Changing, Choosing, When, Beneath, Packing, Inside, Across, At, Connecting, On, Above, Without, Beside, Keeping**. Uniqueness passes mechanically, but some still begin from equipment or a picture rather than an ordinary use situation.

## Reference criteria still requiring honest qualification

1. **Product-first intro improved.** The intro now starts with a product fact, not “Hi, I'm Priya.” The separate runtime overview remains23 words without digits. Intro, outcome and runtime overview are different surfaces and must not be added together for default-tour duration.
2. **No reputational sentence is supplied.** This remains a reference difference under the user's later instruction, rather than a reason to invent an unsupported claim.
3. **Three powertrain batches and ≤2 elsewhere pass.** All26–33-word narration batches now pass, and only two final closing statements remain. Final closing lengths are20 and25 words, with no questions; neither is a delivery batch subject to26–33.
4. **Exact trim qualification is not fully resolved.** Intro and the first powertrain batch use “combinations set by trim”; the runtime overview says “subject to trim”. The PDF's engine/gearbox matrix is nonuniform, and exact combinations remain mostly in deeper. Other lines do name specific starting trims. Do not mark the strict exact-trim criterion entirely passed.
5. **Everyday use and forward handoffs are improved unevenly.** The traffic/auto-hold, luggage/seating, temperature and hot-day/ventilation lines offer use situations. Several passages remain descriptions or availability summaries. Auto-hold ends at the parking-brake switch; the first controls batch repeats the temperature-setting point; the next ends “cabin equipment”; armrest ends “choosing the version”. The ventilation line does explicitly turn toward the roof. These do not establish a consistent forward handoff for every batch.
6. **Empty issues is not proof of all claims or images.** The saved audit is `rules_fallback`, `model:null`, `line_count:0`, `image_count:0`, `missing_line_count:0`. Actual app-extracted PDF asset IDs are used now, but that is provenance, not evidence that the spoken subject is visibly shown.
7. **495-word margin is preserved; duration remains unmeasured.** The selected default route is now404words, barely180.36s at the brief's illustrative2.24rate. The normal measured-audio selector/publication gate must still decide; no paid speech or production recording was generated for this replay.

## Literal visual mismatches remain in fallback output

These comparisons use the independently reviewed `production-source/understanding.json` descriptions of actual extracted PDF assets. They are not a model-pixel audit:

- `price` and `terms-and-unknowns` bind `im_pdf_eb83000c135195546031`, a **turbo petrol engine illustration with power/torque labels**, while discussing on-road pricing or warranty/document gaps. The pictured engine cannot establish those claims; these can appropriately remain nonvisual under the preserved rules.
- `controls` and `controls-2` bind `im_pdf_f422a4dec2ba86f0f22f`, an **equirectangular cabin panorama**, while describing independent temperatures and wireless phone projection/adapter requirements. General dashboard presence is not literal proof of these functions.
- `comfort-2` combines panoramic roof and Bose audio, but binds `im_pdf_2eaa12b3086c47d07a0f`, **front seats and a panoramic roof**. That picture does not prove the added audio subject.
- The outcome and first closing line bind a **manual gear lever** while summarising seating, airbags or wider equipment. A broad recap should not acquire false literal proof from that narrow picture.

Therefore iteration02 is a substantial mechanical and structural improvement over baseline, while precise trim wording, consistent buyer-situation/handoff craft, and literal visual binding remain open. The rules fallback must never be described as a successful pixel review, and unvoiced timing must never be described as a measured three-minute demo.
