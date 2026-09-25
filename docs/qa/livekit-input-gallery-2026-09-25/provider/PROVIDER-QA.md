# Bounded live-input QA — 25 September 2026

The stock application route delivered real speech recognition and real answer audio after the trial was switched from mocked providers. This is a two-question local verification, not physical-microphone/noise acceptance or approval for AWS adoption.

## Scope and isolation

- Stock `/?voice_transport=livekit#/play/dm_29df0418` on app 8920, local LiveKit, fresh isolated publication copy under `/tmp/demo-livekit-live-20260925`. Original BMW publication and protected port/demo untouched.
- Existing customer-tier Gemini 3.8 runtime order and Sarvam STT/TTS, unchanged graph and source checks. No Build, Read, pitch or additional generated narration.
- Chromium playback muted at the browser level. Input was a short WAV synthesized locally with macOS Samantha and injected through a real browser MediaStream/RTC track. No physical microphone and no paid input synthesis.
- Exactly two semantic queries. Four Gemini runtime usage rows reflect the existing reasoning/answer path for those two queries; they are not four customer questions. Existing app estimates total **$0.024371 / ₹2.0471** across nine usage rows, not a provider invoice.

## Results

1. Spoken input: **“How many seats does the BMW X7 have?”** was transcribed exactly and reached the ordinary voice question handler. The approved publication did not establish a usable seating-capacity fact, so the app honestly declined: **“I couldn't verify the exact seating capacity for the BMW X7.”** Sarvam delivered 4.096 seconds of non-silent PCM (RMS 2936, peak 24670). This verifies input→reasoning→speech, while preserving the evidence guardrail.
2. Typed input: **“tell me more about interior of the car”** passed **6/6** checks through the stock UI. The answer cited F011/F014/F015, described the Merino upholstery, cockpit details and CraftedClarity glass controls, displayed the associated console picture and delivered 22.828 seconds of non-silent PCM (RMS 2909, peak 24574). Both the question and exact answer were saved in the completed incremental visit. No browser error or unexpected external browser request occurred.

The original voice harness assertion incorrectly expected the number 7. Its failed receipt is retained unchanged; the publication must not gain an unsupported fact to satisfy a test. That assertion aborted before normal Stop, so the voice visit has an incremental question checkpoint (`save_seq=3`, not ended), but the final answer transcript was not yet saved. No claim of a completed voice visit is made. The typed run completed the actual Stop/save path.

Two earlier startup attempts incurred no provider usage: the first exposed this new harness's omitted local signaling HTTP endpoint; the second still timed out after that harness correction. Later voice and typed joins succeeded. Three subsequent input-free joins passed in5.563/3.177/3.120seconds with no provider requests, giving five consecutive successful joins including the voice and typed visits. The earlier timeout remains unexplained; no speculative timeout/protocol edit was made. This small sample does not establish hosted startup reliability.

## Evidence and rerun boundary

- [Bounded summary](bounded-live-summary.json)
- [Original voice assertion failure](voice-live-original-results.json)
- [Typed run: 6/6](typed-live-results.json)
- [Typed answer and associated picture](typed-live-answer.png)
- Harness: `evals/livekit_provider_browser.py`, syntax checked. `--allow-live-runtime` is a deliberate per-run opt-in, and `--typed-only` permits one remaining typed query without repeating the voice input. Neither belongs in free/mock gate batches.

The harness was corrected to accept a supported answer **or an honest decline** for the spoken question. That corrected full two-question path was not rerun, avoiding duplicate paid queries. Physical-room noise, user microphone permission, acoustic quality, WAN/TURN/network handover and hosted capacity remain unverified.
