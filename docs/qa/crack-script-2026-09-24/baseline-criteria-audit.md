# Baseline script audit — iteration 00

This is an independent audit of the frozen initial-release replay, not a model-quality claim about a paid run. Inputs: `iteration-00/artifacts/{coach,planner,author}.json`, the original thirteen-criterion brief, and the manually reviewed `source/understanding.json` plus its provenance manifest. No app source was changed and no provider or network was used.

The later user decisions govern interpretation: the goal is a narrative reference; preserve all validators (so the complete power quantity may remain in deeper); preserve the 495-word preparation margin and the measured 180-second publication gate. Differences from the illustrative goal are reported, not used to weaken those rules.

## Quantitative definitions

Use the app's whitespace word counter. The persisted baseline contains **16 rendered segments** after complete-line splitting, containing **24 main lines**. Fourteen segments are default-tour-eligible roles; two are alternative intro/outcome roles. There are **31 deeper lines / 1,057 deeper words**; none counts toward guided duration. The separate runtime overview is not a segment. Checkins are counted separately from segment narration.

- Intro: **31 words**. Outcome: **37 words**. These **68 words are excluded** from the default guided route when its separate runtime overview exists.
- Proof narration: **337 words**; features: **32**; establish: **42**. Total eligible segment narration: **411 words**.
- Two checkins: **10 + 6 = 16 words**. Final closing: **21 + 24 = 45 words**. Runtime overview: **23 words**.
- Preparation total: **411 + 16 + 45 + 23 = 495 words**. Zero exact duplicate lines are excluded by the current accountant. Repeated meanings still exist: auto-hold opens the runtime overview and is repeated in the first proof.
- Computed unvoiced default route: **366 words** across nine rendered segments, plus the overview, applicable checkin and closing. It selects powertrain, wheels, space and safety, then features/establish. It omits the comfort/delighters, cabin-controls and ownership proof groups at this stage.
- Default estimate: **192.63 seconds at the app's 1.9 words/second**. At the brief's illustrative 2.24 rate, that same route is **163.39 seconds**. The full 495-word prepared inventory would be **220.98 seconds** at 2.24, or **260.53 seconds** at 1.9. These are arithmetic estimates, not audio measurements.
- The saved `narration_preparation` combines `words:495` with `seconds:192.63` because its words describe the prepared inventory while its seconds describe the selected default route. Those fields must not be presented as one measured reading of the full script.

## Thirteen criteria

| # | Reference target | Baseline produced | Result |
|---|---|---|---|
| 1 | Intro first sentence is product standing or a product fact. | First sentence is **“Hi, I'm Priya.”** The first product fact follows it. | **Fail** |
| 2 | One source-supported, figure-free reputational line in intro; no market/years-on-sale statistics. | **Zero** reputational lines. No forbidden market-sales, tenure or awards narration found. The omission fails the positive storytelling criterion, not grounding. | **Fail / reference gap** |
| 3 | Powertrain is first proof, three batches; every other stop at most two. | First proof is `powertrain`; its split group has **3** segments. Other groups: stance **1**, space **1**, safety **2**, delighters **2**, cabin **2**, ownership **1**. It leads with auto-hold rather than the engine illustration, but the stated batch/order test passes. | **Pass** |
| 4 | Every delivery batch is 26–33 words. | Rendered segment narration passes **6/16**. Complete main lines pass **7/24**. On the selected default route only **4/9** rendered segments pass. Including attached checkins makes **7/16** segments pass; it does not resolve the failure. | **Fail** |
| 5 | Each batch ties every feature to an ordinary use situation. | Several lines remain availability/equipment lists. Unambiguous examples: roof availability plus voice opening, Bose speaker positions, and Normal/Eco/Sport names. These affect at least **three rendered batches** (`comfort`, `comfort-2`, `small-touches`). Traffic/auto-hold and hot-day/seat-airflow do provide useful use situations. This is editorial/source review, not automated semantic scoring. | **Fail** |
| 6 | Each gated feature names the starting trim plainly, without vague variant placeholders. | Outcome says **“equipped versions”**. The engine-choice batch says **“depending on trim”** and **“depending on the trim”**. Bose says **“those ventilated-seat trims”** instead of naming its starting trim. Wheel design is left at **“depends on trim”**. Exact banned strings can be absent while the same ambiguity remains. | **Fail** |
| 7 | No batch starts with specs, topic labels or stock transitions; no repeated opening word/construction. | The **16 rendered segment first words are unique**. Do not misreport a repeated batch word: “The” repeats across **three complete lines**, but only one starts a rendered segment. Nevertheless, openings such as **“Petrol without the turbo…”**, **“The turbo petrol…”**, and **“Bose sound…”** start from equipment/specification rather than a buyer situation. | **Fail**, uniqueness subtest passes |
| 8 | Every batch finishes by turning toward the next subject; none ends on bare specs. | No consistent forward-handoff pattern. Concrete failures include endings on **SX roof availability**, **listed trim names**, **the wireless adapter requirement**, and **“King automatics offer Normal, Eco and Sport.”** Many other endings close a disclaimer or restate the pictured equipment rather than carrying a new subject forward. | **Fail** |
| 9 | At most two closing statements across the script, no questions. | **Four**: two checkins plus two final closing lines. All four are statements; no authored closing question was found. | **Fail** |
| 10 | Runtime overview is 23–28 words without digits. | **23 words, zero digits**, citations retained. | **Pass** |
| 11 | No absent acceleration, mileage, boot-volume, ground-clearance, top-speed, crash-rating or rival figures. | **Zero such figures found** in main, deeper, overview or closing. Mentions that a figure cannot be confirmed are not invented values. Wheel/tyre dimensions, source dates and sourced engine output are different categories. | **Pass** |
| 12 | Empty issues, supported figures, every required picture literally matches the spoken subject. | `issues=[]` and no nonexistent/rejected fact IDs, but visual audit is **`rules_fallback`, model none, 0 audited lines/images**. At least five clear subject mismatches survive; examples below. Nine lines have no picture, including correctly nonvisual policy/price material. Empty issues establishes neither semantic entailment nor literal media proof. | **Fail** |
| 13 | Three-minute narration consistent with selector, with later approved 495-word headroom. | **495/495 prepared words** and the 180-second gate are retained. **Zero measured audio rows**. The selected unvoiced route is 366 words, whose 192.63-second estimate is not a recording. At 2.24 it is shorter than 180; the full prepared inventory is longer. Actual recording and route accounting must decide publication. | **Preparation pass; measured-duration unverified** |

Strict reference score: **3 pass, 9 fail, 1 mixed/unverified**. This is deliberately not “all criteria green” merely because `issues` is empty. The latest user overrides mean criterion2's missing reputation and the power quantity's placement are narrative differences to review, not grounds for a validator exemption.

## Exact batch sizes

| Rendered segment | Role / stop | Narration words | Checkin words | Within26–33 narration words? |
|---|---|---:|---:|---|
| overview | intro |31|0|Yes|
| remember | outcome |37|0|No|
| driving | proof / powertrain |32|0|Yes|
| driving-2 | proof / powertrain |37|0|No|
| driving-3 | proof / powertrain |21|0|No|
| wheels | proof / stance-and-ride |24|0|No|
| space | proof / space-and-practicality |42|10|No|
| protection | proof / safety |29|0|Yes|
| protection-2 | proof / safety |29|0|Yes|
| comfort | proof / delighters |40|0|No|
| comfort-2 | proof / delighters |13|0|No|
| controls | proof / cabin-and-tech |23|0|No|
| controls-2 | proof / cabin-and-tech |27|0|Yes|
| cost | proof / ownership |20|6|No|
| small-touches | features |32|0|Yes|
| ownership-checks | establish |42|0|No|

The authored powertrain has **four complete lines**, but the splitter combines its two middle lines into one37-word delivery segment, producing three batches. Safety has two complete lines and two batches. Delighters has three lines but two batches; cabin has two lines/two batches. Thus “three lines” and “three delivery batches” are not interchangeable.

## Literal-picture failures hidden by empty issues

These comparisons use the independently reviewed source fixture descriptions, not invented scene inspection:

1. `controls-L2` describes wireless Android Auto/Apple CarPlay and adapter requirements, but binds `im29`, **a phone on a wireless charging pad**. Charging does not show phone projection/connectivity.
2. `driving-L2` discusses non-turbo petrol manual/automatic choice, but binds `im08`, **a plus-marked steering-wheel paddle**. It does not literally show that engine/gearbox choice.
3. `overview-D2` states auto-hold availability, but binds `im30`, **a rear-seat table/device-holder image**.
4. `protection-D1` lists stability control, disc brakes, hill-start assistance, tyre pressure and parking sensors, but binds `im23`, **the climate-control panel**.
5. `ownership-checks-D3` discusses absent fuel-economy/crash documentation and dealer stock/delivery, but binds `im07`, **a manual gear lever**.

The `visuals.align` rules fallback changed some author bindings after the validator ran. That output is not a successful real-pixel audit. Several legitimate policy/availability/performance lines should remain nonvisual instead of being forced onto unrelated pictures; the user's preserved G5 rule takes precedence over a literal reading of “every line has a picture.”

There are58 line records including main/deeper/overview/closing; **49 have a picture reference and9 have none**. All referenced fact IDs exist in the supplied approved fixture, but a valid ID does not itself prove each sentence's claims. The fixture is a manually simulated Understand registry, clearly labelled as such; baseline production did not itself extract PDF pictures. The final extraction implementation and independently reviewed final asset selection must be assessed separately.

## Additional before/after comparison cautions

- Baseline Coach places `delighters` before `cabin-and-tech`, despite the compact-SUV library listing cabin before delighters. Criterion3 does not test their relative order, so its pass must not be stretched into full library-order compliance.
- The runtime overview is an auto-hold opening; intro and outcome are alternate Browse material, not additional guided seconds. Do not count all three openings toward the minimum.
- The complete power quantity is present in deeper with its unit and basis. It is absent from main narration. Under the user's later direction, keeping that validator-compatible placement is acceptable and must not be falsely reported as a fixed failure.
- No paid speech was produced. A final three-minute publication claim still requires the normal measured-audio gate; a mock fixture or a words/second calculation cannot replace it.
