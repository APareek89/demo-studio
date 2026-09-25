# Runtime/gallery release — 25 September 2026

Anand approved the reviewed app improvements and requested master/GitHub plus AWS after varied acknowledgements and website-search confirmation. This receipt covers the application change and local verification; the AWS release receipt records the actual cutover separately.

## Changes and reason

- Ten neutral question acknowledgements rotate once each per visit before repeating. Fast answers, Continue/Pause/Stop bypass holding speech. Restart resets the cycle. Exact existing audio may be reused; otherwise the existing locked voice supplies speech, so old published BMW needs no rebuild. Answer readiness still cancels only filler; one voice and turn ownership remain intact.
- An enabled BMW owner URL had a build crawl timeout. `crawl_active` records availability, but runtime treated it as consent. Authorize enabled top-level non-excluded owner URLs independent of that last fetch result. Keep owner-domain/www-only scope, private-network and redirect checks, actual fetched passages/citations, tool budgets and no caching of live-web answers. Failed live reads never become evidence, facts or cached answers.
- Release includes prior reviewed gallery continuity, immediate reversible speech hold and exact answer-image/retrieval improvements from`aeddec9`, `97ef2ab` and`2d931c9`. Their detailed baseline and before/after receipts remain current for unchanged sources.
- AWS retains its existing WebSocket voice. Local-only LiveKit remains optional/dormant on AWS: this code release does not provide hosted signaling, ICE/TURN or the different token boundary that would require.

## Local verification

Core **deck445/445, acceptance24/24, smoke3/3, full mock28/28**. New acknowledgements**14/14**, actual player**88/88** includes eleven consecutive questions, playback commands and restart; live voice**96/96**, LiveKit adapter47, early hold26, listening16, recovery17 and saves18. Domain**25/25** includes four new failed-crawl/explicit-exclusion/live-read regressions; search**37/37**. Seventeen Python suites and seven Node suites pass; counts overlap and full per-suite inventory is`local-gate-counts.json`.

All free app gates use mocked providers, isolated DATA/GRAPH, blank keys, cloud off and blocked outbound sockets. Browser uses synthetic speech/API, muted Chromium and blocked external requests. Zero new paid calls or physical microphone tests. The native browser's initial87/88 fixture mismatch used the mute query; the normal query plus process-level audio mute passes88/88. No application behavior was relaxed for that harness correction.

Independent source review found no actionable acknowledgement defect. It checked exact legacy audio compatibility, full cycles, cancelled/stale turns, answer-first cancellation, commands and per-visit state. Syntax/whitespace and nine Mermaid source/viewer pairs pass. No Build, approved script/audio, pinned evidence or source mutation is needed.

## Remaining limits

This release is not another real-provider/acoustic or load acceptance. Website authorization and bounded tools are verified with fixtures; current external website/provider availability can still fail and must decline honestly. Prior local LiveKit real-input evidence does not establish Internet transport or speaker/noise isolation. AWS operator boundary and customer records must remain unchanged; live cutover verification and rollback are recorded separately.
