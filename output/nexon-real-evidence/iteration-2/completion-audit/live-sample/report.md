# Six-question live sample — cde49fe

Session `s_mu765nbzlv8f` ended with zero leads. Evidence frozen at 2026-09-18 16:35:50 UTC. Six logical questions produced seven model turns because L2 required a clarification and repair. All seven complete timings, including failed behavior, remain in the sample. The UI was muted: these are media-start timings and transcript/caption checks, not acoustic verification.

First-answer time: **p50 7.971s; p95/worst 10.225s**. Gemini itself: p50 2.736s, worst 7.089s; speech rendering: p50 3.241s, worst 5.054s. All seven QA responses parsed on Gemini with no provider fallback. Three routed answers additionally waited about 2.8s for the transition announcement. Faster delivery does not make this a quality pass.

- L1 passes: petrol boot 382 litres, ISO V215, no certification or luggage-fit claim.
- L2 initially fails the intended context continuity: the selected Venue trim was not supplied as selected context, so the model asked which trim. After the exact HX10 petrol 7DCT reply, it stated supported boot figures with each measurement basis and the competitor caveat. ISO V215 and VDA 215 remain different bases; this is no proof of a directly comparable capacity advantage.
- L3 passes the matched comparison: front ventilation on both named automatic configurations, with the full competitor caveat. No asymmetric safety list.
- L4's F019 gearbox answer and test-drive assessment are grounded, but its `book-test-drive` action wrongly became customer intent. The player spoke a handoff and saved “Book Test Drive” without the customer choosing it. This is a failed action boundary, despite zero leads.
- L5 fails: “3 years or 100 000 km” supplies an unsupported relationship, then contradicts itself by saying that relationship is unspecified. It correctly stayed on Nexon scope.
- L6 passes the missing-price boundary. The player delivered its truthful decline and optional callback path; no exact amount was invented. Its words differ from the model candidate, preserved separately in `answer-audit.json`.

The initial personalized pitch failed: Gemini's 3000-token response was incomplete, Claude had no credits and Runware timed out. The draft is not delivered personalized proof; the transcript shows the fallback route.

The final summary also failed in the persisted session. Two simultaneous summary requests both exhausted Gemini's 1200-token response limit. One Runware fallback succeeded (trace 460), but the other's later timeout overwrote that success with an error (461–462). All attempts and charges are retained. The new summary accounting records these attempts; it does not solve duplicate generation or overwrite races.

Recorded cost for this sample window is **$0.211976** across 21 usage rows, including failed pitch, seven QA turns, extra handoff/re-entry speech, the premature summary and both final-summary attempts. Whole-demo recorded estimate at this cutoff is **$4.211334**. These are configured estimates, not an invoice. Historical unrecorded summaries, ten zero-usage Build1 Gemini TTS clips and any unreported failed-call charges remain outside that figure. Later confirmation runs require a new cost cutoff.

The 9.1-minute session includes operator inspection and is not an uninterrupted tour duration. Exact candidates, rendered text, delivered transcript, citations, timings, usage rows and source hashes are saved alongside this report. Original artifacts are unchanged.
