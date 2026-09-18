# Final recorded customer latency and cost — 18 September 2026

Frozen through **2026-09-18 16:01:50.303 UTC** (timestamp 1789747310.303246), after the root confirmed all sessions ended. The final A summary is present and current. Usage/trace byte counts were unchanged across a 54-second check; no further paid run was requested. Full per-session/stage/source/input statistics and source-file hashes are in `customer-latency-cost-final.json`.

**Recorded demo usage: $3.987538 (about ₹334.95 at the configured ₹84/USD).** Iteration1 before the second Read: $1.140407; iteration2 before customer testing: $1.582453; subsequent customer validation: $1.264677 across 94 recorded usage rows. The full demo has 361 usage rows. These are configured estimates, not an invoice; split rounding may differ in the last decimal. Readiness probes outside this demo folder are outside this total.

This total is incomplete: ten successful Gemini TTS clips in Build1 reported zero tokens and no native charge. Background session-summary model calls also have no per-demo usage/trace records: the plain summary thread does not restore the usage context. All eight final summaries exist, but their actual charges are unavailable here. Failed calls without reported usage may add further billed cost. Do not present $3.987538 as the complete amount paid.

**26 customer turns across eight ended sessions; seven sessions have turns.** Twenty-five have all four ordered timestamps and enter the latency percentiles; one incomplete server-input turn remains counted and excluded. Flags report 16 answered and 9 declined; these are delivery flags, not semantic acceptance scores. All failed, slow and ambient-contaminated samples remain. Overall first-answer latency: **p50 13.552s, p95 36.419s, worst 46.745s**.

Complete turns by answer source and input:

- Bank/typed: n=2; total p50 19ms, p95/worst 37ms; QA itself 13/22ms.
- Model/typed: n=21; total p50 15.878s, p95 36.419s, worst 46.745s.
- Model/server speech: n=2; total p50 11.775s, p95/worst 13.366s. STT stamp differences 338/479ms; these samples do not establish intended-user speech quality.
- Unclassified/server speech: one incomplete turn, excluded from every latency percentile. No browser-recognition samples.

Per-session total latency (complete/recorded; p50, p95, worst):

- `s_mu72zmm82u16` (initial A, known failures): 4/4; 11.775s, 21.494s, 21.494s.
- `s_mu73j2rpe8ug` (routing check, ambient contamination): 2/3; 0.019s, 13.366s, 13.366s.
- `s_mu73pdkozfj6` (initial B): 7/7; 22.096s, 36.419s, 36.419s.
- `s_mu744a0l0l8o` (B comparison recovery): 4/4; 17.791s, 46.745s, 46.745s.
- `s_mu74j6zw4ubr` (initial C boundaries): 3/3; 7.663s, 9.828s, 9.828s.
- `s_mu74mrok5jgd` (A before pitch correction): 3/3; 13.552s, 20.088s, 20.088s.
- `s_mu74vi17dltu` (final C recovery): 2/2; 5.156s, 26.803s, 26.803s.
- `s_mu752gpf8em1` (final A, later operator resumption): 0/0; no complete QA timings.

Provider-window evidence includes 28 raw Gemini responses and 14 Gemini dispatch errors (12 schema/JSON, one closed client, one timeout), 14 Claude credit failures, and 14 Runware transport events (10 without transport error, four timeouts). Two QA requests exhausted all providers. These counts include pitch as well as QA and distinguish duplicated dispatcher wrappers from transport events; they are not a count of paid attempts. All 49 recorded runtime Sarvam TTS trace events and seven STT events have no trace error; that does not prove acoustic quality.

Percentiles use the app's existing selected-rank method, so p50 on two samples is the lower sample; small n is visible rather than smoothed away. Post-QA-to-audio includes route-announcement playback and scheduling, not just synthesis. Trace and usage lack session IDs, so no exact per-session cost or provider allocation is invented.

The final A natural ending was observed at 5.6 minutes; operator navigation subsequently resumed a partial clip and the latest record is 5.9 minutes. Earlier natural-end evidence is preserved separately. Operator pauses/visual inspection mean neither value is a clean uninterrupted tour duration. Later QA was explicitly muted and final A partly muted/caption-only. **No actual microphone or acoustic-intelligibility pass is claimed.**
