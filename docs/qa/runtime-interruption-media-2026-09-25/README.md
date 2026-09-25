# Runtime interruption, reviewed pictures and retrieval — 25 September 2026

Implemented on `codex/sales-trainer-flow` against `e80a180`. **This follow-up is not merged to master or deployed to AWS.** The previously approved BMW feedback release remains live. No new paid call, demo/source/media mutation, LiveKit integration, agent/node, database migration or workflow change.

## What changed and why

- `web/player/live-voice.js` and `voice-worklet.js` separate early reversible output pause from qualified-final semantic interruption. Eight speech-like20ms frames (about160ms in a synthetic test), or a qualified partial, quiet playback locally. Raw volume alone does not qualify. Capture continues. Rejected/empty final or bounded silence/no-progress recovery resumes the existing clip; distinct recognized progress lets long questions retain ownership. This is not speaker identification or measured physical interruption latency.
- `web/player/player.js` pauses recorded audio, streamed output, browser voice, caption completion and gallery motion under one run owner. Delayed recognition, stream startup, rejected holds, controls and new/cancelled runs cannot revive stale speech. `walkthrough.js`/`slide.js` gate late image decode and exact-media focus before answer audio. Top navbar and bottom controls/styles are unchanged.
- `server/runtime_visuals.py` is a helper called by existing runtime retrieval/delivery, not a new graph node. It selects the exact reviewed published photo and owning caption from eligible pinned citations; current bundle version/snapshot, scope, negative applicability, local-file identity and caption qualifiers all constrain selection. FAQ hits get the same fresh selection. Pure unambiguous picture requests use existing retrieval without model reasoning or FAQ/unknown learning. Missing/illustrative-only/ambiguous part requests return an honest limit; failed/stale browser selection cannot say a picture was displayed. No arbitrary URL, invented anchor or unreviewed upload is returned.
- `server/knowledge.py` hydrates source context only after ranking/deduplication/limiting and memoizes each selected source within that request. Five BMW queries retain deeply identical evidence payloads; comfort source reads31→1, engine26→1, dashboard16→1. Diagnostic local timings are not a model/voice latency SLA. Context rows remain independent copies, and no persistent cache can go stale.

## Actual storage

Current AWS configuration uses local EC2 per-demo JSON/source/media files and graph SQLite; optional cloud adapters are disabled. Browser playback contains published fact/presentation metadata and image URLs, not the authoritative editable source store. DynamoDB would hold configured metadata/session/lead rows and S3 files only if those optional adapters were enabled. This task did not migrate them. Strict picture existence currently assumes local media; a future S3-only setup needs an explicit restored-media or serving integration.

## Verification

[Machine-readable counts](gate-counts.json), [independent twelve-category FMEA](FMEA.md), [application source hashes](source-hashes-after.json) and [unchanged source check](source-stability.json).

- Frozen baseline: deck445/445, acceptance24/24, smoke3/3, mock journey28/28 on e80a180. Its archive/logs remain in `output/runtime-interruption-media-2026-09-25/baseline/`.
- Final: deck445/445, acceptance24/24, smoke3/3 (Read, Build and on-demand rehearsal), full mock28/28 with194.22s synthetic narration. All use MOCK_LLM=1, fresh DATA/GRAPH, cloud off, blank provider keys and blocked outbound; zero outbound attempts. The initial444/445 was one stale static QA/onplaying assertion, updated to verify actual-result timing before a hold and owned/unheld first-audio callbacks. That failure remains in the original output; no behavior assertion was removed.
- New: immediate speech hold26/26; runtime visual selection23/23; actual image/player42/42; retrieval IO12/12.
- Adjacent: live voice96/96, speech noise31/31, runtime recovery17/17, listen16/16, session save18/18, knowledge60/60, runtime graph130/130, FAQ cache27/27, transmission conditions17/17. Earlier during this package: repair106, FAQ scope19/review42 and live transport25 also passed; final focused reruns above cover later source refinements. Counts overlap and are not additive unique checks.
- Final actual muted browser: live journey42/42, gallery320/320, native player87/87. New image/player42 checks desktop1440/phone390, same-slide exact-image/tag before audio, Continue return, immutable bundle, missing/stale/decode failure, no false acknowledgement/callback/factual open question, factual speech surviving image failure, and held/cancelled decoded-image ownership. Browser harnesses allow only their own loopback server; microphone/providers/other hosts are blocked or deterministic fakes. No browser errors or failed source assets in the gallery receipt (intentional missing-image cases are isolated in the new contract).
- The live browser recorded native pause at4.470407s and the same clock after120ms, then resumed the same clip on a rejected throat annotation. This verifies playback mechanics, not physical room acoustics. All181 files in the read-only BMW probe stayed unchanged. No protected demo or port8896 operation.
- Changed Python parses, JavaScript syntax, whitespace and Mermaid source/viewer parity9/9 pass. No new unaddressed code blocker found in independent review; inherited public-runtime quotas/ownership and unmeasured physical acoustics remain explicit in the FMEA.

## Visual and timing evidence

[Desktop gallery](gallery-1440-line0.png), [phone gallery](gallery-390-line0.png), [completed voice journey](voice-lifecycle-recap.png), [exact held playback clock](held-audio.json). Existing top/bottom shell geometry is checked against its prior gallery baseline; image-selection behavior is asserted through actual DOM/audio events.

## LiveKit discussion, not implementation

LiveKit supplies WebRTC room/audio transport and an Agents framework for STT, turn detection, interruption and TTS. A later trial could connect browser microphone/output to a LiveKit agent that invokes this existing validated runtime and Sarvam; Build/Align/grounding and the gallery would remain here. Prerecorded demo clips and local interruption still need coordinated playback ownership. Do not represent an SDK migration as guaranteed noise immunity or lower reasoning latency.

Official references: [overview](https://docs.livekit.io/intro/basics/), [turn/interruption tuning](https://docs.livekit.io/agents/logic/turns/tuning/), [Sarvam STT integration](https://docs.livekit.io/agents/models/stt/sarvam/).

## Limits and release status

The mock server shutdown emitted an ASGI `InterruptedError: Turn superseded` from cancelled work. The same raise exists on the baseline; no failed browser check or new regression was observed. This receipt does not claim zero server exceptions, and mapping cancelled HTTP turns to a quiet response remains a separate inherited diagnostic issue.

No paid/model-output, physical microphone/TV/cup or concurrency/load acceptance was performed. Sustained background voice or voiced throat clearing can still briefly pause playback; relevant background words can still pass semantic qualification. Same-clip false-hold recovery mitigates disruption but is not speaker recognition. Images outside published reviewed associations are intentionally unavailable. AWS/master remain at the previous approved release until a subsequent authorized integration/deployment.
