# A short-trip repeat — pre-NX34 source audit

Session `s_mu74mrok5jgd` ended at 5.7 minutes with zero leads. It ran before the NX33/NX34 corrections; **it is not accepted as a fully grounded personalized demo**. Filenames beginning `A-final-` identify this test attempt, not a final acceptance verdict. The immutable sanitized API record, metadata/hash, trace extracts and fact/source map are saved beside this review. No app/demo mutation or paid calls were made for the audit.

## Q03: supported answer and exact return

The typed boot-capacity question interrupted the second intro line. Trace 401 and speech input 404 match the fully heard answer: petrol Nexon capacity **382 litres, ISO V215**, followed by an in-person stroller fit check. F014’s page-40 brochure row and method footnote support this; it does not establish that the customer’s stroller fits.

The session records `sl01 → sl05`. Root clicked explicit Yes at `1789746196793`; the transcript then records the return cue and the exact full interrupted second line. The already completed first intro line did not replay. The interrupted prefix remains separately marked as partial. `screenshots/A-final-Q03-origin.txt`, `A-final-Q03-answer.txt` and `A-final-Q03-return.txt` corroborate the live UI path. This is a successful jump-and-return observation, separate from the later pitch failures.

## Actual custom-pitch failures

Trace 395 generated the pitch; speech inputs 396–405 and the saved heard transcript establish that these were delivered, not merely rejected proposals:

- **Boot batch:** “For your stroller and daily family gear, petrol and diesel models offer 382 litres of boot space, while the CNG variant provides 321 litres.” F014 supports both numbers/fuel columns, but this batch omits its ISO V215 measurement condition. Neither the earlier Q03 answer nor later scripted boot line is counted as repairing this batch’s omission. The sentence does not explicitly promise luggage fit; its problem is incomplete scope/method delivery.
- **ISOFIX batch:** “To secure your child seat properly across your city drives, ISOFIX mounts come standard across all Nexon variants.” F004 supports standard availability. It does not establish proper installation or compatibility for this customer’s particular child seat. The personal assurance goes beyond the cited fact. A complete neutral compatibility label on the picture does not supply support for that spoken assurance.
- **Warranty batch:** “For your daily five to ten kilometre city routine, the basic warranty covers 3 years or 100 000 km to keep early ownership predictable.” The daily distance matches intake. F027 only states an advertised `3 years | 100 000 km` headline, with the limit relationship and detailed terms unknown. The spoken **“or” is unsupported**, as is the promise of predictable early ownership from that headline. This repeats a material condition loss through the pitch path despite the separate live-QA warranty improvement.
- **Safety bridge:** “For your child seat, standard mounting points keep installation straightforward.” The generated `bridge_fact_ids` is empty. ISOFIX availability does not establish installation ease for this child seat. This uncited benefit was heard before the correctly sourced scripted safety equipment.

The other heard practicality bridge says boot dimensions/loading lip matter to a stroller fit check; it gives no fabricated dimension, fit outcome or loading specification. The later scripted boot narration explicitly includes ISO V215, and the scripted BNCAP line retains petrol/diesel trims active in May 2026. Those lines are correctly qualified but do not retrospectively validate the custom claims above.

## Q11: silence, correction and a supported answer

At the Safety check-in, the root’s saved UI observations show the same `YOUR TURN` caption/options at `1789746322112` and `1789746365453`: **43.341 seconds without auto-advance**. The customer then typed “To be precise, I drive only five to ten kilometres daily. I am not planning a long commute.” The snapshot retains the original short-trip intake; the answer explicitly repeats the correction rather than inventing a longer commute.

Trace 409 (after an incomplete Gemini attempt and Claude credit failure) cites F004/F014: standard ISOFIX, 382 L petrol/diesel, 321 L CNG and ISO V215. These are framed as useful checks for the child seat/stroller, without a fit guarantee. The complete answer was heard and the stored route is `stay`. This demonstrates correction context and a working hold; it is not evidence that all personalization claims were grounded.

## Q10: no luggage-fit guarantee

The customer asked whether their stroller and two large suitcases fit with the child seat in use. Trace 411 returns a valid semantic decline, no facts, and a showroom/test-drive physical check suggestion. The actual heard text is the player’s standardized unavailable-answer message. F014 explicitly says volume does not establish a particular luggage/stroller fit; F004 does not establish universal child-seat compatibility. No guarantee was voiced. Root chose Not now; the saved record has no lead.

The final summary accurately lists that fit question as unanswered and suggests checking it; it does not repeat C’s false readiness promise. This is a pre-NX33 model result, not a post-fix proof. Both `resolved` and `unresolved` contain practicality because the boot-capacity question was confirmed and a later specific fit question was declined; do not automatically treat that topic-level bookkeeping as a contradiction.

## Evidence limits and readiness

All three turns are typed and live. Submit-to-first-answer stamps are about 13.6s (Q03, including spoken jump bridge), 20.1s (Q11), and 8.2s (Q10). The 43.341-second hold is deliberate user time, not provider latency. Root observed the UI while playback ran unmuted; there was no independent acoustic listening. This audit checks player-reported heard words, speech inputs and source mapping, not microphone accuracy.

Q03 routing/return, Q11 hold/correction and Q10 fit refusal passed their observed paths. The custom pitch contains real heard unsupported claims and an omitted measurement condition. Keep the session as the NX34 failure reproduction; free fixes or later rewrites must not relabel it accepted.
