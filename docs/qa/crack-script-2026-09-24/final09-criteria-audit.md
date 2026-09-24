# Writing and route audit — iteration09

**Iteration09 is intermediate and is not accepted.** The action and choice openings improve, but independent source review found three citation/picture defects. Empty application `issues` does not override those findings. The actual stage produced **497 prepared words,16/16 complete delivery batches within26–33 words, three powertrain batches and two closing statements**. Its selected route has345 words and181.58 estimated seconds, with no recorded audio.

Inputs are the [initial Author response](iteration-09/calls/author-01.response.json), [native repair response](iteration-09/calls/author-02.response.json), [saved artifact](iteration-09/artifacts/author.json), and [application-derived metrics](final09-metrics.json). The independent [source audit](final09-source-audit.md) records semantic and literal-picture findings. The user's later instructions preserve all validation, the495-word preparation margin and180-second measured publication minimum; the goal remains a reference. No code, schema, validator, source registry, Coach response or Planner response was changed for this audit.

## Thirteen criteria

| # | Reference criterion | Actual09 evidence | Assessment |
|---|---|---|---|
|1|Start the intro with a product fact or standing.|“CRETA's auto hold holds the car stationary without keeping the brake pressed…” gives the supported function and first automatic availability before a traffic-pause situation.|**Pass.**|
|2|One grounded, figure-free reputation sentence; no company statistics.|No reputation sentence or company-statistic narration occurs. “One of the best” remains unsupported by the supplied PDF evidence.|**Strict positive criterion not met; evidence-blocked difference.** Grounding remains intact.|
|3|Powertrain first, with three batches; no other proof stop above two.|Order remains powertrain → stance and ride → space and practicality → safety → cabin and tech → delighters → ownership. Counts are3,1,1,2,2,2,1.|**Pass.**|
|4|Each delivery batch26–33 words.|16/16 batches and16/16 individual main lines pass. All14 guided batches are single complete lines. Unlike08, the combined31-word outcome has no short picture-specific fragments and uses none.|**Pass.**|
|5|Each batch connects features to an ordinary situation.|“Decide how to change gears”, “For a darker wheel finish”, “When a journey needs space”, “If driver and front passenger want different temperatures”, “Before getting in”, “On a warm evening” and “Stowing small items” give specific choices or contexts. The airbag batch still primarily lists equipment and trim, and engine detail remains heavily devoted to exact availability. The wheel finish choice is an appearance benefit, not an unsupported ride-performance claim.|**Improved, partial against strict “every batch”.** Useful buyer choices count as improvement; this is not proof of a daily-life scenario for every feature.|
|6|Give exact first trim and material exceptions, avoiding vague variant phrases.|Non-turbo manual starts at E; its automatic list starts EX(O). Diesel automatic has the exact list, while diesel manual is represented by the SX Premium exception in main and its E start in deeper. Auto hold begins on S(O) automatics. The pictured matte-black option now names S(O) Knight, King Knight and Lounge Edition. Other core first trims and the paid up-to-seven-year petrol warranty scope remain specific. No banned vague variant phrase occurs.|**Qualified.** Specific main claims are grounded; complete first-trim coverage is still partly deeper. The unrelated local-citation defect is recorded under12.|
|7|No topic/spec/stock opening, no repeated first word or construction.|Action and choice openings replace08's conspicuous “Inside this illustration” and “Under the turbo's cover”. However, “Before” begins both the Alexa and terms batches:15 distinct first words across16 batches. “Even on E” leads with availability; “Looking upward” remains a visual direction. These are narrower remaining issues, not a reason to dismiss all improved openings.|**Strict rule fails; practical variety improves.** The repeated word is measurable; naturalness remains editorial.|
|8|Turn each batch toward the next subject, without bare-spec endings.|Gearbox shortlist → turbo choice → wheel finish → journey space → safety → traffic assistance → cabin temperature → remote preparation → seat comfort → roof controls → quote → equipment → warranty → dealer evidence is maintained. No batch ends with an isolated specification. Some joins remain generic, and “Keep attention on the road while setting the temperature” is a clumsy safety-to-climate bridge.|**Functional continuity passes, with writing limits.** Complete authored order is assessed; omitted stops in a selected route may remove intervening links.|
|9|At most two closing statements, no questions.|All checkins are empty. Closing has23+21=44 words in exactly two statements, with a contact preference rather than a promise of completed dealer contact.|**Pass.**|
|10|Overview23–28 words, without digits.|The runtime overview has27 words and no digits. Auto hold is reserved for it and the alternative intro.|**Pass.**|
|11|No unsupported acceleration, economy, boot-volume, clearance, top-speed, crash or rival figures.|No prohibited figure is asserted across48 units. The script explicitly leaves economy/crash/luggage figures unconfirmed. Engine, tyre, screen, source-price and warranty quantities are separate cited categories. Complete160PS stays deeper under the preserved validator.|**Pass.**|
|12|Empty issues, local grounding and literal pictures.|`issues=[]`, but independent review found **three defects**: (a) opening deeper rules out every automatic S(O) Knight combination using non-turbo/diesel citations F066/F068 but omits F006 needed to cover turbo; (b) cabin deeper combines screens with Bluelink service features/period against a dashboard-only picture; (c) shared-space deeper combines the split rear seat with the separately described boot-storage subject against a folded-seat picture. These statements are true in the overall registry, but their local citation/visual support is incomplete. All48 effective-response units survive normalization.|**Fail.** The corrected warranty and Knight alloy remain correct; their success does not erase these regressions.|
|13|Three-minute narration with495-word preparation margin preserved.|497 prepared words exceed495. The selected route has345 words:181.58 seconds at app1.9 words/s,154.02 at reference2.24. Full inventory is221.87 seconds at2.24. No recording exists for this sample.|**Preparation passes; measured-duration acceptance unverified.** The existing recorded selector and180-second publication gate still apply.|

## Exact counts and native repair

The actual application counters give **367 proof +27 features +32 establish +27 overview +44 closing =497 prepared words**. Intro28 and outcome31 are59 excluded alternative-opening words. Deeper contains29 lines and1,012 words, also excluded. No checkin speech or exact duplicate line contributes to the preparation count.

All16 rendered/main-line lengths, in order, are **28,31,31,31,32,28,32,30,31,31,31,30,30,30,27,32**. Each is26–33. The14 guided lines together have426 words.

`narration.default_route` selects nine rendered batch IDs: `engine-choices`, `engine-choices-2`, `engine-choices-3`, `wheels`, `shared-space`, `airbags-and-help`, `airbags-and-help-2`, `small-storage`, `terms`. Their274 words plus27 overview and44 closing total345. Cabin, delighters and quote remain prepared but outside the provisional selection. The full preparation report is261.58 estimated seconds at1.9 words/s; the selected route is181.58. Both report `measured:false`.

Saved preparation status is `ready`, `target_words:495`, `words:497`, `attempts:2`, `seconds:181.58`, `basis:estimated`. The two attempts are actual Author requests: the existing validator sent a native repair request because the source-free decline contained “certified”, which matches CLAIMISH even in a negative statement. The second response rephrased only that deeper text and removed the matching word. Its change from curly “can’t” to ASCII “can't” was not the cause of the successful validation: `author.ungrounded` has no special can't/cannot decline recognizer. It did not add a fact or relax the validator. All other narrative text, citation arrays and visual choices remain unchanged between the initial and repair responses; schema/stage defaults also appear in the repaired payload.

The metric comparison uses **author-02.response.json as the effective response**:48/48 text/citation units and48/48 visual refs are preserved in the saved artifact, comprising26 pictures and22 none references. Against author-01,47/48 texts remain identical; the single decline repair is recorded in the metric JSON. It would be inaccurate to claim that all initial prose survived unchanged.

## Comparison with08

| Measure | Iteration08 | Iteration09 |
|---|---:|---:|
| Complete rendered batches / main lines |16/18|16/16|
| Rendered batches within26–33 words |16/16|16/16|
| Eligible guided lines within26–33 words |14/14|14/14|
| Distinct batch first words |16|15|
| Prepared words |500|497|
| Selected route words / estimated seconds |348 /183.16|345 /181.58|
| Overview / closing words |28 /45|27 /44|
| Deeper words excluded |939|1,012|
| Actual Author requests |1|2|
| Preserved effective-response units |49/49|48/48|
| Source/literal review |No additional defect found|Three confirmed defects|
| New audio measured |No|No|

The wording gains and citation/picture regressions are separate findings. Action-led prose improves even though one first word repeats. Conversely, faithful normalization correctly preserves the authored visual choices—including the two bad mixed-subject choices—so this is not a recurrence of the06 fallback-normalization bug.

## Verification boundary

Metrics use `server.agents.author.words`, `narration.preparation_report` and `narration.default_route` with MOCK_LLM=1, isolated DATA/GRAPH storage, and blocked DNS/connection/datagram methods. The artifact's visual audit remains `rules_fallback`, null model and0 pixel-audited lines/images. No paid provider, web, voice or acoustic check was used.

The09 rerun passes eight suites: script prompts40/40, visual alignment25/25, speech style30/30, generation55/55, narrative roles14/14, deck380/380, acceptance24/24 and smoke3/3. All exit successfully with zero outbound attempts. These reruns refresh the existing25-suite/1,069 reported-check ledger and must not be added as unique cases. Their success does not establish source entailment, literal picture coverage or recorded duration; this sample demonstrates why the independent review remains necessary.

No application data, protected demo, AWS or port8896 was touched, and no code or script artifact was edited. The repair diagnosis above was corrected after inspecting the unchanged validator during10 review; the09 metrics and findings remain unchanged. Saved Author SHA-256: `50248beb7003814bac87dde2b4dfe6a925ffc6837e7fba713f1672c12bfb232b`.
