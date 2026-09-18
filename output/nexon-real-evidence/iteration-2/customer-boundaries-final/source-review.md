# C boundary run — final source and handoff audit

Session `s_mu74j6zw4ubr` is ended, **2.4 minutes, zero saved leads**, on the root-reported `d8fc422` runtime. `session.json` is the full sanitized final API snapshot; `snapshot.json` records origin/hash/time and redaction. `responses.json` contains actual model outputs at trace rows 392–394. `source-mapping.json` records relevant source limits. This audit made no app/demo writes and no paid calls.

The earlier snapshot in `customer-boundaries-pre-back` was taken immediately after Stop while a Back test was planned. Root cancelled that plan: C ended without Back; Q11 moved to another session. The earlier snapshot remains immutable evidence of the Stop state, not evidence that Back occurred.

## Customer-facing boundaries

**Traffic goal: safe refusal, weak consultation.** Browse-at-my-pace started without intake. The neutral opening was interrupted by the typed statement “I mainly want help with stop-and-go traffic.” Trace 392 is a successful Gemini response (9.784s), `answered=false`, no citations and no clarifying question. It could not establish specific stop-and-go assistance and did not invent traffic capability or a benefit. The player actually spoke the standard unavailable-answer message rather than the model’s more specific sentence.

This is not a provider outage. The customer stated a need rather than requesting a guaranteed traffic-assistance feature. F019 could support discussing the available seven-speed DCA as a choice to assess in a test drive, without promising easier traffic performance; a brief clarifying question could also have kept the consultation useful. The current response does neither. This is a material consultation gap, separate from the correct refusal to fabricate performance.

The need is saved in the heard transcript and summary, but `profile` remains `{name:"", why:"", followup:"", focus:[]}`. Root observed no “What matters to you” recap. The interaction therefore has historical context but did not visibly turn the newly stated goal into the personalized profile/recap. No broader personalization change was made during the run.

**Q04, exact Mumbai on-road price: proper semantic decline.** Trace 393 completes successfully with no facts and `answered=false`; the stored heard answer is the standard decline. F001 only supplies a starting ex-showroom price, checked on a source date and subject to change. It is not the current selected-variant Mumbai total including all local charges; U01 explicitly records that missing city-specific breakdown. The customer was not given an invented number or a starting price passed off as an exact quote.

**Q05, guaranteed five-year EMI with two lakh down: proper customer-facing decline.** Trace 394 completes successfully with no facts and `answered=false`. F002 is a conditional advertised Flexi starting EMI, including a higher subsequent instalment and financier discretion; U09 leaves the full schedule/rates/fees unknown. The heard response supplies no calculation, bank approval or guarantee.

One raw model wording weakness should remain visible: its unspoken draft says a dealer can assist with “guaranteed EMI calculations.” That wording is too loose because the source does not establish a guarantee. The player replaced it with the standard decline, so this was **not heard by the customer** and does not negate the observed boundary pass. It shows that safe delivery here should not be mistaken for perfect model semantics.

All three turns were typed, live and `route=none`. Submit-to-answer stamps were about 9.8s for the traffic goal, 5.9s for Q04 and 7.7s for Q05. They are successful provider responses followed by refusals, not fallback outages.

## Material saved-summary failure

The saved summary’s `opening_line` says:

> You mentioned that you mainly want help with stop-and-go traffic, and I have those details ready along with the exact Mumbai on-road price and EMI numbers.

That assertion is unsupported. The same record lists traffic assistance, the exact Mumbai breakdown and guaranteed EMI as unanswered; there is no saved quote, finance approval or supplied answer. A follow-up draft must not claim these details already exist. This was an internal saved handoff/summary suggestion, **not customer-heard narration and not a sent message**. It remains an open correctness issue rather than proof that a dealership has information ready. A truthful draft would acknowledge the pending checks and request the appropriate advisor’s response.

The summary correctly recognizes the traffic, price and finance interests elsewhere, but that does not validate the invented readiness assertion. Zero leads were saved; an open callback form and this summary are not proof of customer consent or a submitted callback.

## End-clock check

Root recorded Stop at `1789746099401`, waited, then Done at `1789746124072` and reloaded. `clock-comparison.json` compares the snapshots: minutes remain **2.4**, and per-slide dwell remains **15.6s on sl00 / 126.1s on sl01**. Both are ended and both have zero leads. The 24.671-second post-Stop gap did not accrue to session time/dwell. This proves the observed Stop/Done path; C did not exercise Back, later resumed playback, or Q11.

The audit verifies saved heard text, actual model responses, source constraints and snapshot timing. Root observed the UI while playback ran unmuted; there was no independent acoustic listening or speech-recognition score. Price/EMI delivery boundaries passed, while goal handling and summary truthfulness remain weak.
