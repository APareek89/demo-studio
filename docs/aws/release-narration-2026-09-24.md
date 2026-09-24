# Three-minute narration correction — AWS release, 24 September 2026

**Live:** [AWS Demo Studio](https://13-202-0-79.sslip.io/#/home). Cutover completed **2026-09-24 05:29:22 UTC / 10:59:22 IST**. Application changes are in [`293223c`](https://github.com/APareek89/demo-studio/commit/293223ce044388fa6b9fd744910019d6f6eb770e); deployed source [`e506448`](https://github.com/APareek89/demo-studio/commit/e506448a67648a3e5d268c52826f3778bbff34aa) adds corrected release-test waits. Both were pushed as fast-forwards to private GitHub master while the local branch stayed `codex/sales-trainer-flow`. This receipt adds documentation only.

## Behavior and review

New plans target at least 495 distinct supported words, with additional allowance calibrated from matching current recordings. Reviewed story stops can contain several short cited delivery batches, all retained through the default route. Author's bounded repair receives the content deficit. The actual180-second measured publication guard remains mandatory; no padding, duplicate speech or slower voice can satisfy it. Missing evidence remains a review gap.

For an existing short draft, open Align, choose **Prepare three-minute narration**, review the changed Script/Visuals and then Build. Preparation reuses the reviewed Plan, facts, voice and CTAs. A short recording returns to Align while preserving the previous publication and audio. The previous128.3-second real draft was **not** regenerated as part of this no-paid-call release.

[QA and twelve-category FMEA](../narration-recovery-qa-2026-09-24.md) and the [exact gate inventory](../narration-recovery-gates-2026-09-24.json) record the implementation, counts, evidence and limitations. There is no new unresolved blocker from this change; inherited C7 public-builder access and C8 Cloud alternate-language voice identity remain open, as do existing capacity/OCR/selective-Align-routing limitations. Corrupted nonempty audio-cache repair is outside this content-preparation fix.

Files changed: ten backend files (`server/agents/{align,author,bundle,narration,plan,principles}.py`, `server/{app,graph,orchestrator,schemas}.py`); `web/studio/align.js`; eight eval files (`align_narration_recovery_contract.mjs`, `narration_preparation_contract.py`, `narration_recovery_contract.py`, `generation_contract.py`, `narrative_roles_contract.py`, `plan_playbook_contract.py`, `qa_deck.py`, `smoke_mock.py`); PRD/refine/Handoff/Learning/Loop, architecture and Mermaid02–05, and the dated QA/gate/release receipts. No dependency, credential, design-template or production-data change.

## Validation

Local **33/33 suites**, **1101/1101 reported checks/cases/phases**, independent actual-browser **10/10**, and wait-helper follow-up **6/6** pass. Counts overlap where a broad gate invokes another contract. All9 Mermaid source/HTML copies, changed Python/JavaScript syntax and whitespace checks pass.

Core gates: deck365/365, acceptance24/24, smoke both phases plus on-demand rehearsal. New preparation18/18, recovery18/18 and Align recovery UI17/17 pass. The actual Plan→Author repair→Deck→Bundle→Pitch fixture delivers **495 cited words /198.0 measured seconds**, retaining all13 guided pieces. The full new-demo API→Read→six approvals→Voice/Build→runtime/cache/review/rehearsal→browser/session journey remains27/27 with194.22 measured fixture seconds.

All **15/15 staged AWS suites** passed against the exact committed source before cutover:

- qa_deck365/365; qa_accept24/24; smoke both phases plus rehearsal.
- narration_preparation18/18; narration_recovery18/18; minimum_narration25/25.
- generation55/55; plan_playbook19/19; narrative_roles14/14.
- publication_approval8/8; build_hardening28/28; runtime_graph130/130.
- voice_lock27/27; readiness10/10; release_mock27/27.

The staged generation count is55 rather than local58 because the three optional legacy-Creta checks require a real data directory. They passed locally on isolated copies; production data was deliberately not linked into the staged test process. No staged assertion failed in the final run.

Initial staged deck QA exposed a harness race: status reached Align before the worker released its mutation guard, so the immediate FAQ edit correctly returned409. Deck and smoke now wait for both the target phase and `running:false`; no production guard was weakened or mutation blindly retried. The failed initial log and final successful logs are retained in private evidence.

Every backend gate ran with MOCK_LLM=1, temporary DATA/GRAPH storage, cloud sync off and blocked outbound sockets; counters were zero. Browser journeys were sandboxed, muted and intercepted in process. These checks establish software mechanics, not live model prose or acoustic quality. **No paid call, readiness probe, live Build/Q&A or microphone capture was performed.**

## Deployment and preservation

- Same instance `i-0410e37b7ab0297e1`, region `ap-south-1`, EIP13.202.0.79. No new service port, dependency install, Caddy/TLS, IAM or security-group change.
- New source `/opt/demo-studio-releases/20260924-narration`; all364 committed source/doc/fixture hashes verified before tests and again before cutover. The archive excludes output/, uploads, real data and credentials.
- Reused the compatible venv/Chromium from `/opt/demo-studio-releases/20260923-creta-v8`. Only after isolated tests passed, linked the existing `/opt/demo-studio/.env` and `/opt/demo-studio/data` into the new release.
- Verified the previous Marine release was active and every real demo had no running graph before stopping. Added only systemd drop-in `96-release-20260924-narration.conf`; retained95 and the old release. Uvicorn remains on loopback8877, with customer models, MOCK_LLM=0, local shared storage and hedge enabled at3s.
- Stopped-service full data/SQLite backup: `/opt/demo-studio-backups/20260924-narration/data.before.tar.gz`, **785,699,469 bytes**, SHA-256 `615001bcbbe05d4ea3667f40fd2f2bbfd15bc8383763e033cf32a111e97de3be`. Private directory700 and umask077.
- **4,087/4,087 data files unchanged**, zero added/changed/missing, including SQLite. All13 demos,11 bundles and22 sessions remain. Environment checksum unchanged.
- Public HTTPS200, production health non-mock, all25 served frontend files match committed hashes; a non-protected published demo's image and WAV each return valid206 ranges of1,024 bytes. GET requests only. No new service error journal entries at final inspection; about11GiB disk remains available.
- Localhost8905 also serves the fix using its existing isolated **mock** data. No protected local demo/output mutation or port8896 operation.

Operational evidence, original failed staging log, final15 gate logs, source/data manifests, cutover script, backup and verification are private under `/opt/demo-studio-backups/20260924-narration/`; local copies are under `/tmp/demo-studio-narration-release-20260924/`. The inherited public unauthenticated builder/access decision and earlier narrow SSH-rule cleanup limitation remain as recorded in the prior release receipt; neither was changed here.

## Rollback

Automatic rollback was reviewed and not needed. Previous application source remains `/opt/demo-studio-releases/20260923-wp11-marine`; existing95 override remains. Before any later rollback, stop the app and take a **fresh** full shared-data/SQLite backup, move only96 into the private backup directory, reload systemd, restart and verify previous working directory plus health. Never restore the pre-release data archive over subsequent customer work without reconciliation.
