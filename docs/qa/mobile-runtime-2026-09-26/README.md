# Mobile runtime correction — 26 September 2026

Status: mobile fixes are on GitHub master and AWS. Deployed application3591fb7 plus the explicit5543fe1 CSS overlay preserves exact source provenance. The [release receipt](../../aws/release-mobile-2026-09-26.md) records main cutover, subsequent CSS correction, backup and actual public checks. Later documentation-only commits retain these results without implying another application rollout.

## Reproduced defects and changes

- Native WebKit blocks a newly created HTML audio element after the welcome tap expires, even when Web Audio was unlocked. Reusing the element played during that tap succeeds. The player now primes a persistent recorded-audio element with an unmuted silent WAV synchronously from deliberate taps. Recorded lines retain their exact source and voice; browser-policy rejection holds the current line with an explicit Enable audio button. It never creates another provider request. Cancellation, source ownership and actual ended state fence late media events.
- On rotation with several tags already revealed, the selected label could remain outside its resized scroll panel and lose its pointer. Resize now keeps the selected label visible (or its readable start for an oversized label), without changing the narration or taking over manual scrolling at an unchanged size.
- A short slide hides its footer. Measuring that hidden footer's zero offset consumed the gallery's full height in landscape and a keyboard-height viewport. Hidden footers now use the existing small inset.
- The closed absolute conversation drawer lacked a positioned player containing block. WebKit document width doubled; Chromium changed the visual viewport scale after rotation. Positioning the existing clipped player contains its drawer without redesigning the controls.
- Web Audio resume could remain pending before capture/output deadlines existed, or fail after a provisional speech hold removed the output deadline. Resume is now bounded to four seconds, checks the running state and retains context/delivery ownership. Late microphone grants remain fenced and typing remains available.
- Optional browser icon/manifest probes encountered the operator authentication boundary. Only GET/HEAD on the four exact optional paths now return an unchallenged404. Adjacent paths, mutations, builder routes and private records retain authentication. The auth challenge was reproduced; an actual iPhone credential popup caused by these probes was not.

## Evidence and limits

Native policy12/12 used real WebKit HTML media with unmuted digital-silence audio and no autoplay bypass. No-gesture/new-element/Web-Audio-only failures and same-element success were observed after the activation window expired. The earlier probe that polled page JavaScript could contaminate activation and is not acceptance evidence. Final raw evidence: `output/playwright/mobile-audio-policy-20260926-final/`.

Mobile gallery104/104 covers WebKit and Chromium portrait, landscape, narrow/small phones, synthetic keyboard resize, drawer open/close, feature taps, exact picture/caption and narration ownership. The baseline reproduces collapse/overflow. Raw evidence: `output/mobile-layout-2026-09-26/`.

No physical iPhone or iOS simulator is available on this host. WebKit with Safari/Chrome-iOS user agents checks shared engine policy and layout, not either installed iOS app, actual keyboard behavior, microphone acoustics, OS background suspension or mobile-network reliability. Provider calls are mocked, storage and graph state isolated, and outbound provider sockets blocked. Existing BMW sources and recordings are not regenerated.

Initial candidate gates found two test-harness dependencies on the former implementation: qa_deck444/445 expected an exact old onplaying string; speech_noise stopped after25groups because its extracted micTap fixture omitted the new unlock helper. The updated structural check retains ownership/hold assertions, and the speech fixture supplies a no-op unlock. Native browser regressions separately exercise that helper. Reusable-Audio fakes now implement native src/ended lifecycle instead of advancing a replaced source.

## Final local gates

- Core: deck445/445, acceptance24/24, smoke3/3, full mock28/28 (194.22s synthetic narration); isolated storage/graph, zero outbound provider attempts.
- Native mounted WebKit recorded audio26/26: two Safari/CriOS profiles × continuous and delayed recording cases. The old application after a6.5s local recording delay fails7/13: both profiles reject the second/closing clip with NotAllowedError at inactive user activation. Candidate13/13 for that case. Continuous old playback can succeed; its11/13 baseline fails only reuse checks. New recorded ownership12/12; Web Audio lifecycle13/13.
- Voice96/96, LiveKit58/58, transport15/15, immediate hold26/26, noise31/31, recovery17/17, listen16/16, session save18/18, HTTP question6/6, media7/7, walkthrough fallback18/18, priority revision11/11.
- Gallery320/320, mobile geometry104/104, continuity28/28, image load14/14; current native player88/88. FakeAudio's obsolete old-element finish simulation now dispatches the saved old event callback; finishing a reused element would incorrectly finish its new source.
- Native local RTC30/30: exact UDP candidate,64 actual received/forwarded synthetic frames, microphone off/retry, reversible hold, picture before answer, ordinary flag-free typed intake/question and saved visit. Two previous attempts failed (candidate assertion; microphone publication timeout), remain preserved, and caused no widening of network/timeout rules. This is bounded acceptance, not a universal network reliability claim.
- Real isolated AWS edge58/58 and existing boundary153/153; deployment-helper fixtures18/18. Actual AWS staging36/36 suites passes with zero outbound attempts; knowledge58passes+2explicit environment skips. Complete counts and hashes: [AWS gate inventory](aws-gate-counts.json). Public application32/32, proxy20/20 and post-cutover hosted WebKit RTC10/10 pass. All4273 existing stored files survived main cutover unchanged.

Raw receipts are under `output/playwright/mobile-20260926/`, `output/playwright/mobile-recorded-audio*-20260926/`, `output/mobile-layout-2026-09-26/` and `output/mobile-public-access-2026-09-26/`. Counts overlap and should not be summed as unique coverage.

Additional stock WebKit checks: permission-denied typed fallback10/10, saved answer and stopped visit, real BMW phone/landscape screenshots. One local private-ICE join failed before that fallback; it is not represented as a successful WebKit RTC run. Public hosted WebKit mic-off RTC10/10 reached session.ready over TURN/TLS443 with real data and returned to zero participants, without provider or visit writes. Its first harness attempt was inconclusive (over-narrow path allowlist and an unbounded diagnostics wait); the one replacement used exact SDK paths and bounded diagnostics. Physical iPhone acceptance remains distinct.

## FMEA and product boundary

Product context: PRD's interruptible, grounded voice tour; existing gallery, three-second reply window, incremental session saves and human approvals. System context: existing LiveKit/runtime graph, local JSON/SQLite, single AWS worker and two-room admission on a t3.micro. This change adds no graph node, source, provider, migration or automatic turn replay.

- Unhandled errors: bounded Web Audio resume and visible recorded-media policy retry replace unbounded waits/silent policy fallback. Prior S6/O7/D8=336; covered residual S6/O2/D2=24.
- External dependency failures: browser policy and suspended contexts tested separately from provider failures; existing selected-voice caption fallback remains for non-policy media failures. Physical hardware behavior remains unverified.
- Races/state: prime/source/token/run ownership, cancellation during permission/prime, rejected held playback and late events require regression coverage. No new independent narration clock.
- Resource exhaustion: one active recorded element per mount, bounded prime/resume; destroy releases it and existing preloads. Existing room/body/queue limits retained.
- Security/access: four exact GET/HEAD optional assets; no wildcard public route, token scope change or credential output. Real proxy edge58/58 and boundary153/153.
- Data integrity: heard-only transcript and ordered incremental save behavior retained; deployment snapshots and verifies every current data file before code cutover.
- Observability: retry/error status is visible; existing session timing remains. Production traces do not establish physical device acoustic quality or prove a browser-cancellation cause.
- Scale/load: no new server work per recorded clip or retry. Existing two concurrent rooms remain a disclosed capacity limit; this is not a load test.
- Billing: silent primer/local retry makes no model/STT/TTS request. No new paid QA.
- Retry/idempotency: retry resumes the exact owned audio source; Pause/Stop/navigation remove pending retry; no question replay.
- Configuration drift: no transport/provider flag change; verify exact frontend hashes on deployed release and ordinary flag-free public route.
- PRD edge cases: portrait/rotation/keyboard, touch tags, voice off/permission failure, typing, interrupt/resume, restart and recorded/live ownership are the relevant user flows.

Coverage:12/12 categories checked. Remaining acceptance limits are physical iPhone/acoustics, real cellular conditions and existing two-room hosted capacity, not claims resolved by mocked tests.

## Final short-screen welcome correction

The post-cutover real BMW landscape screenshot exposed clipped start buttons that the gallery-only checks did not cover. A single `max-height:500px` CSS block compacts welcome/intake spacing, title and controls; ordinary desktop/portrait rules stay intact and unusually long copy remains internally scrollable. Real BMW welcome66/66 in Chromium/WebKit checks portrait,844×390,844×320,568×320, desktop, synthetic keyboard-height intake, long-title scrolling and actual voice-toggle/Explore/Skip actions. No model, source, graph or audio change. Evidence: `output/mobile-welcome-2026-09-26/current/`.

The15/15 CSS deployment fixtures verify the exact base/payload, complete source preflight, single-file atomic replacement, original backup, public hash, rollback on public mismatch/SIGTERM, and explicit base-plus-overlay provenance. No service restart or customer-data write is needed. The [release receipt](../../aws/release-mobile-2026-09-26.md) records actual deployment separately. FMEA reviewed the new layout and deployment boundaries; no unresolved blocking finding.

Final public welcome checks initially passed Chromium but failed to load WebKit twice. All assets returned200. A GET-only dynamic-import diagnostic confirmed `TypeError: Attempted to assign to readonly property` in LiveKit's Safari getUserMedia shim: the temporary test guard had defined getUserMedia with writable:false. This was test instrumentation, not an application-source defect. Both attempts and the import trace are preserved under `output/deploy-mobile-20260926/public-welcome-final/`; only the temporary guard descriptor was corrected for the final WebKit checks, retaining microphone, mutation and socket denial.

Final public welcome acceptance21/21 passes: actual AWS CSS hash, Chromium and native WebKit at390×844,844×390 and844×320, both start buttons/voice toggle visible and hit-testable, no horizontal overflow or unintended zoom. The corrected WebKit-only run is12/12; counts overlap. Screenshots were visually inspected, including the shortest landscape viewport. No JavaScript errors, microphone access, provider calls, WebSockets, mutations or visit starts occurred. Exact result: `output/deploy-mobile-20260926/public-welcome-final/final-results.json`; screenshots are beside it and under `webkit-corrected/`. This final documentation checkpoint retains all earlier code gates and adds only these bounded public read-only checks; no application code changed after5543fe1.
