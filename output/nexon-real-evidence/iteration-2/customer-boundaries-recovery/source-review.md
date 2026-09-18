# C2 recovery — context, consultation and summary audit

Session `s_mu74vi17dltu` ended at 4.8 minutes, with zero leads. `session.json` is the complete sanitized API snapshot after the asynchronous summary finished; `snapshot.json` records its hash and runtime attribution. This backend contained NX32/NX33 and the QA prompt changes; it preceded only the final quoted-measurement pitch check. Browse did not invoke pitch, so this is not a pitch-fix test. The earlier failed C remains unchanged in `customer-boundaries-final`.

## Stated traffic need retained

The exact statement “I mainly want help with stop-and-go traffic.” appears **once** in `profile.followup`. The later exact Mumbai price question follows it once on a new line. These are retained customer words, not a model-generated preference ranking. The profile still leaves name/why/focus empty; it does not invent them.

Root’s `screenshots/C-recovery-recap.txt` shows the same statement under **What matters to you**, alongside the price request. That resolves the observed loss from the earlier structured-profile/recap path. It also means this field is conversation context rather than a carefully distilled list of needs; the audit does not claim a broader preference-extraction feature.

## Traffic answer is a useful sourced choice discussion

Trace 415 and Priya input 416 match the complete player-reported answer. F018 supports petrol six-speed AMT/seven-speed DCT options, diesel six-speed AMT, and manual-only iCNG. These are official **model-range choices by fuel**, not confirmation that every gearbox exists on Fearless+PS; a selected-trim recommendation still needs the powertrain matrix. The answer frames the gearbox as a fit check, without promising easier traffic operation, economy or comfort.

F025 lists the documented ADAS suite only on Fearless+PS petrol DCA. The answer says that list does not state stop-and-go cruise and avoids promising it. This is an evidence limitation, not an assertion that no Nexon ever has a named feature. The response therefore improves on the earlier generic semantic refusal while preserving the capability boundary. Wording such as “supported fit-check” remains somewhat procedural for a customer conversation.

Trace 412’s incomplete Gemini proposal contained “to ease driving”, an unsupported benefit from equipment alone. JSON validation rejected it; the Runware answer at 415 is the one sent to speech and stored as heard. The rejected proposal must not be counted as customer-delivered text. The stored traffic turn is `answered=true`, `route=stay`, and performance is subsequently marked resolved.

## Price boundary and truthful opener

The exact Mumbai all-charges price request still properly declines: trace 417 is a valid Gemini response with no facts and `answered=false`, rather than a provider failure. The player-reported transcript has the standardized unavailable-answer message. F001 only supports a starting ex-showroom price with source-date/change conditions, not the requested current on-road total. Ownership remains unresolved; the summary retains the specific Mumbai question in `unanswered`.

The completed saved summary now uses the deterministic opener:

> I'd like to discuss the questions left open in your demo.

It does not claim the missing price or finance details are ready. Context, customer interests and the resolved/unresolved objections remain present. This is an actual post-NX33 result, in addition to the free 10-case regression; it does not establish semantic correctness of every possible summary.

## Limits

Both questions are typed, live and have no recorded jump. Submit-to-first-answer stamps are approximately **26.8s for the traffic answer** (including provider fallback) and **5.2s for the price decline**. Source correctness and context retention improved, but the first wait remains long. No callback was submitted, no price supplied, and no finance approval established.

Root observed the UI while playback ran unmuted; **there was no independent acoustic listening**. This review checks provider outputs, speech inputs, player-reported heard text, persisted profile/summary and the saved recap UI. The observed NX32 consultation/context path and NX33 opener have recovered here; the initial C failures and wider product limits remain recorded.
