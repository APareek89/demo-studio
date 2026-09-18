# Build 1 integrity — failed at voice

Demo `dm_36d47b86`, commit `a5a663b`. The first actual Build stopped after 128.5 seconds in the voice stage. No bundle was created; all real customer paths and script-to-bundle checks are **BLOCKED**.

## Blocking findings

- Audio coverage: 60/85 required clips. Missing 11 FAQ answers and 14 fillers.
- Missing FAQ IDs: Q05, Q10, Q11, Q12, Q13, Q14, Q16, Q17, Q18, Q19, Q20.
- Missing filler IDs: ack_with_context, ack_no_context, hold_on_question, back_to_demo, nudge_continue, put_in_writing, still_working, good, glad, clearer, lets_go, how_i_go, before_video, after_video.
- The script declares Sarvam/Priya, but the exact saved audio cache hashes prove these second-voice clips:
  - faq `Q06`: gemini/Sulafat, `audio/0b8de2e7151724fa6e03.wav`.
  - faq `Q07`: gemini/Sulafat, `audio/971edb00d61b41c0f8b1.wav`.
  - faq `Q08`: gemini/Sulafat, `audio/9d2a2efe148e2cd0bce6.wav`.
  - faq `Q09`: gemini/Sulafat, `audio/bb0600b371f1b3c0d9dd.wav`.
  - faq `Q15`: gemini/Sulafat, `audio/30d3a44ff6642f16c831.wav`.
  - filler `bridge_to_custom`: gemini/Sulafat, `audio/bf9b5ca0371f14fe5a2d.wav`.
  - filler `hold_on_lookup`: gemini/Sulafat, `audio/704b30821afb08a5e617.wav`.
  - filler `did_that_answer`: gemini/Sulafat, `audio/18b9a1c4129eed618996.wav`.
  - filler `focus_first`: gemini/Sulafat, `audio/4d77b2bf9632768c670e.wav`.
  - filler `no_guess`: gemini/Sulafat, `audio/2c8d62f87ff94914b083.wav`.

Sarvam rate limits triggered the fallback. The trace also contains Gemini input-block refusals and a closed-client error. The bank was checkpointed incomplete; this is not a voice pass.

## Verified without playback

- All nine main batches have complete WAVs and run 9.30–16.21 seconds, below the twenty-second budget.
- Main narration, check-ins and closing total 144.13 seconds; intake adds 6.14 seconds. User waits, deeper branches and runtime personalization are excluded.
- 60 referenced WAVs have valid nonempty headers; hashes, file paths, exact frame durations and all reference IDs are retained in `build-integrity.json`. Audio/source originals were not copied.
- sl04 image `im08`, title, both labels, panel placement and c1's saved drag at x0.0401/y0.0453 remain in deck and overrides: PASS. Bundle persistence remains blocked.
- All three CTA URLs use the official Tata HTTPS host, contain no fabricated hash fragments and are present as links in saved official HTML. This audit made no live destination request.

## Cost and evidence

Successful build trace rows record an estimate of $0.084050; including estimates attached to failed rows yields $0.095480. These are log estimates, not an invoice. The 10 successful Gemini TTS rows have zero reported token usage, so their actual charge is not established here.

`build1-failed/snapshot-manifest.json` hashes the failed artifacts. `trace-summary.json` and `usage-summary.json` retain safe metadata and hashes of the originals, without prompt/error bodies. `run.json` records iteration 1 as failed_voice; the next actual Build is iteration 2.

No acoustic intelligibility, naturalness, overlap or customer-experience pass is claimed.
