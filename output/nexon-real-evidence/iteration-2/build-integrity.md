# Iteration 2 Build integrity

**PASS. The second actual Build produced ready bundle version 1.** Commit `5cc9288`, demo `dm_36d47b86`; artifact snapshots are under `build2/`. No production data was changed by this audit.

- **84/84 required audio references** are present across 18 main lines, 18 deeper lines, six check-ins, two closing lines, one intake, twenty FAQ and nineteen fillers. They resolve to 80 unique WAV files.
- Every referenced cache key matches the exact current text plus **Sarvam / Priya / en-IN**. All files decode fully and have nonzero PCM signal. Voice recorded 78 successful Sarvam calls, zero errors and zero Gemini voice calls.
- All nine main batches are **10.411–18.859 seconds**, within 20.5 seconds. Safety plus its separately played check-in is 21.675 seconds; the main alone is 18.859 seconds.
- Main/deeper/closing narration, citations, turn steps, timings, audio, intake, check-ins, twelve slides, twenty FAQ, nineteen fillers and CTAs match the reviewed sources of the bundle. All four manual FAQ corrections survived Build. Every published local media reference exists.
- The cockpit is `sl08`, image `im08`, title “Your cockpit, closer”. Touchscreen callout `sl08-c3` retains its normalized label position **(0.0401, 0.0453)** and anchor **(0.503, 0.475)**.

Actual Build duration was **210.635s**: voice 163.3s, rehearsal 47.1s, bundle under 0.1s. New Build usage is estimated **$0.293438** (voice **$0.149161**); iteration 2 through the pre-customer cutoff is **$1.582453**. Costs use configured rates, not invoices. The cutoff is timestamp **1789743348**; later customer calls are excluded. Detailed successful/error trace counts, stages, file hashes, durations and cost splits are in `build-integrity.json`.

Nonzero audio proves the files are not entirely silent. It does **not** prove intelligibility, pronunciation, pacing or perceptual voice consistency. Actual listening and all twelve customer paths remain separate evidence; rehearsal is not a customer-session pass. The failed first Build evidence remains unchanged.
