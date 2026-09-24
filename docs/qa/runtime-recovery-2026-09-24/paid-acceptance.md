# Paid customer visit — 24 September 2026

The single paid Build published **193.78 seconds of measured default narration**. The single natural-speed browser visit completed **11/11 mechanical checks**, reached the closing CTA, and saved an ended recap after **67 checkpoints**. Its one answer failed independent semantic review. Mechanical success does not supersede that failure.

The visit used the real isolated app and configured providers, the supplied 16 JPGs and 49-page PDF, and the URL-gated walkthrough. No lead was submitted and no physical microphone was requested. Muted playback ran at natural speed for 541.82 seconds, including intake, one question, nine section prompts and their reply windows. Full audio quality and TV/cup-noise rejection are not established by this browser run.

## Answer failure and disposition

Asked: “What engine and gearbox choices does this CRETA offer?”

The repaired answer said: “The Creta offers a petrol, a diesel, and a turbo petrol engine. You can pair them with a 6-speed manual or an automatic, and a dual-clutch automatic for the turbo petrol.”

F149 and F150 are genuine approved source rows, but “them” generalizes manual availability to the turbo engine. The source explicitly assigns manual/IVT to petrol, manual/six-speed automatic to diesel, and seven-speed dual-clutch automatic to turbo petrol. The initial gearbox sentence preserved the petrol/diesel qualification; the existing repair for a different quantity rejection lost it. The second validation accepted the ambiguity and cached it.

This is a P1 condition-loss defect (severity 5 × occurrence 4 × detection 5 = 100). The shared runtime validator now rejects the recorded collective-pairing error. Its existing cache-hit revalidation also rejects that wording before playback or count increments. The corrected code passes19targeted tests,17independent probes and all12affected/core suites; no second paid semantic success is claimed. There is no additional repair allowance, new agent/node, or second paid visit.

After preserving the original answer, cache and session evidence, the unsafe entry was rejected through the existing Align FAQ endpoint. The rejected entry remains as a tombstone and cannot be served. No provider call was needed for that review. Correction acceptance is recorded separately; the original paid answer is never relabelled a pass.

## Evidence and cost

`paid-acceptance.json` contains sanitized check results, hashes of retained local raw evidence, the failure and cache disposition. `paid-review-history.json` records the initial Read failure, bounded causal revisions, human editorial/source/picture review and single Build. This final reviewed demo is not evidence of unattended first-pass generation reliability.

Recorded cumulative estimate: **$0.9182 across 126 provider calls**, including generation, review revisions, Build and the browser visit. Timed-out provider charges may be absent from the estimate. The paid image auditor timed out; picture choices were reviewed by hand and remain illustrations, not successful automated pixel-proof claims.

Screenshots: [welcome](paid-browser/welcome.png), [guided route](paid-browser/guided-route.png), [original answer](paid-browser/question-answer.png), [closing CTA](paid-browser/natural-closing.png), [saved recap](paid-browser/saved-recap.png).

The server remains isolated on port 8910. This work does not merge master or deploy AWS; Anand's hands-on review comes first.
