# LiveKit default — implementation and release QA

User authorization: accepted trial and explicit request for LiveKit everywhere, following master/GitHub/AWS release approval. Work stays on the existing implementation branch until the tested checkpoint is promoted. Preserve Build/Align, graph nodes, grounding, locked voice, gallery and existing demo data. No new paid model/speech QA.

## Implementation

Both public playback and Rehearse share server-advertised transport selection. Configured LiveKit works with normal URLs; the old explicit flag remains compatible and explicit WebSocket selection remains diagnostic. No automatic replay or second microphone on failure. Hosted transport has WSS, exact origins, real-client rate bounds, short room-scoped grants, archived publication pins and bounded lifecycle. The normal local launcher keeps workspace data; the isolated-copy launcher remains for tests.

Independent review found and fixed first-question evidence drift after republication, deeply nested JSON callback errors, same-tick navigation creating an orphan room, unbounded SDK import and the inherited short connection deadline. [Twelve-category FMEA](FMEA.md) records these and deployment gates.

## Free checks

- Core: deck445/445, acceptance24/24, smoke3/3, full mocked build/review/publication28/28 with194.22s synthetic measured narration. Separate raw logs are retained here.
- [Adjacent Python inventory](python-gates.json):26processes, zero outbound attempts; knowledge60, retrieval12, visuals23, graph130, repair106, delivery27, hedge35/config6, operational failure13, domain25/customer-sites20/web37, live-table21/transmission17, FAQ27, live transport25, Sarvam17, checkpoint26/input-mode8, explore cancellation9, speech style30 and voice lock27. Counts overlap.
- Hosted policy29/29, legacy transport50/50, normal local launcher15/15 and isolated-copy launcher16/16. Actual graph pin regression uses the room's old six-airbag evidence after a new eight-airbag publication.
- Frontend selector15/15, LiveKit client58/58, base voice96/96, speech hold26/26, recovery17/17, session saves18/18 and acknowledgements14/14. Actual public/Rehearse/navigation28/28. Source syntax, whitespace and9/9Mermaid source/viewer pairs checked.
- [Real local RTC](local-rtc.json):30/30; synthetic microphone uses real native RTC, controls/data/audio exercise the existing runtime and stock app route, matching picture precedes answer audio and completed/incremental visits persist. Screenshots cover desktop, phone and the actual answer picture. No physical microphone or acoustic/provider quality is inferred.

The first default-route browser run checked an asynchronous session checkpoint too early; the harness now waits for actual saved state and mic readiness. Final source verification and hosted receipts supersede earlier intermediate counts without deleting the failure history. Local normal-app start retained all702existing data files unchanged and made no provider request.

## Deployment boundary

AWS staging uses an isolated new venv with old dependency versions constrained, pinned SFU1.13.7 and authenticated TURN/TLS on existing443. No new instance/security-group opening. A first staging assertion failed on upstream's `%!s(int=7882)` formatting in its ports report; strict configuration itself parsed. Resume preserves the original prepared credentials, and the old application/proxy remained running.

Hosted identity/relay/TLS renewal, staged Linux gates, full data backup, cutover and public verification are separate requirements. See the dated AWS receipt/Handoff for actual completion; this local receipt alone does not claim deployment, broad load capacity, speaker identification or a new paid conversational test.
