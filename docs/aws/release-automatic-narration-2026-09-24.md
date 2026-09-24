# Automatic narration — AWS release, 24 September 2026

**Live:** [AWS Demo Studio](https://13-202-0-79.sslip.io/#/home). Cutover: **2026-09-24T06:12:48Z**. Deployed source [`b15d23e`](https://github.com/APareek89/demo-studio/commit/b15d23ef9f8dba636734cf3242f6a592794a27a1), pushed as a fast-forward to private GitHub master while the local branch remains `codex/sales-trainer-flow`. This receipt is documentation only.

## Behavior

Read prepares the supported three-minute draft automatically. Author uses the existing reviewed plan and at most three writing calls; unfinished output stays pending and cannot be approved or built. The large deficit/Prepare panel is removed; compact timing is inside Script. Actual mock placeholder speech is labelled as a preview. Ordinary Build handles a legacy short draft, and a short measured recording triggers one revised draft for human review without another Voice pass or publication. Missing recordings use recording recovery. Manual edits retain the reviewer's exact words and cannot become an automatic legacy rewrite.

The measured 180-second publication gate, grounding, six-card review and previous publication/audio are preserved. This code deployment does not generate a new real narration. Detailed implementation/FMEA: [QA report](../automatic-narration-qa-2026-09-24.md); [exact gates and source hashes](../automatic-narration-gates-2026-09-24.json).

## Validation

- Local **35/35 suites**, **1169/1169** reported cases/checks/phases; independent muted-browser **13/13**. Counts overlap where broad suites invoke subcontracts.
- Core: deck 365/365, acceptance 24/24, smoke both phases plus on-demand rehearsal. Actual upload→Read→review→Voice→Bundle→runtime/cache/review/rehearsal→browser/session journey 28/28, 194.22 seconds measured fixture audio with the real publication minimum active.
- Automatic Read/manual edit 16/16; preparation 35/35; recovery 18/18; minimum 25/25; Align UI 21/21 and timing 13/13. Python/JavaScript syntax, whitespace and 9 Mermaid source/HTML copies pass.
- AWS exact-source staged gates **16/16**: deck 365, acceptance 24, smoke 3 phases, preparation 35, automatic 16, recovery 18, minimum 25, generation 55, plan 19, narrative 14, publication approval 8, build hardening 28, runtime graph 130, voice lock 27, readiness 10, release journey 28.
- AWS generation 55 excludes three optional legacy real-data checks that passed locally; production data was not mounted in staged tests. No assertion failed in the final staged run.
- All backend tests use MOCK_LLM=1, temporary DATA/GRAPH, cloud off and blocked sockets; outbound counters 0. Browser requests are intercepted and muted. No paid model/voice/readiness call, live Build/Q&A/session mutation or microphone capture.

## Deployment and preservation

- Same instance `i-0410e37b7ab0297e1`, ap-south-1, 13.202.0.79. No service-port, dependency, Caddy/TLS, IAM or security-group change.
- Source `/opt/demo-studio-releases/20260924-auto-narration`, **368** committed files verified by SHA-256. Archive excludes output/, real data and credentials. Existing compatible venv/Chromium reused from `20260923-creta-v8`.
- Shared environment/data linked only after isolated staged tests passed. Every real demo's worker was idle before the previous service stopped. New systemd drop-in `97-release-20260924-auto-narration.conf`; previous 96 override/source retained.
- Stopped-service full data/SQLite backup `/opt/demo-studio-backups/20260924-auto-narration/data.before.tar.gz`, **785,699,469 bytes**, SHA-256 `615001bcbbe05d4ea3667f40fd2f2bbfd15bc8383763e033cf32a111e97de3be`. Private directory mode 700 / umask 077.
- Data manifest: **4087 before /4087 after**, missing 0, changed 0, added 0. Demo bytes unchanged; any SQLite-only bookkeeping is explicitly retained in private verification. All 13 demos, 11 bundles, 22 sessions preserved; environment checksum unchanged.
- Production health remains non-mock/customer tier on loopback 8877. HTTPS 200; all 25 frontend hashes match; non-protected stored image/WAV valid 206 byte ranges. Read-only GET checks only. Service errors since cutover: `none`.
- Localhost 8905 restarted with its existing isolated **mock** data. Protected local dm_41513908, output/, port 8896 and user Chrome untouched.

Private operational evidence, gate logs, source/data manifests, backup and scripts: `/opt/demo-studio-backups/20260924-auto-narration/`; local copy `/tmp/demo-studio-auto-narration-release-20260924/`.

## Rollback and limits

Automatic rollback was reviewed and not needed. Previous application source is `/opt/demo-studio-releases/20260924-narration`; its 96 override remains. Before a later rollback, stop the app and take a fresh shared-data/SQLite backup, move only the 97 override into the private receipt directory, reload systemd, restart and verify the previous working directory and health. Do not restore pre-release data over subsequent customer work without reconciliation.

No new unresolved code-review blocker. Inherited C7 hosted-builder access, C8 Cloud alternate-language voice identity, capacity, OCR, damaged nonempty audio-cache recovery and selective Align routing remain pending. Synthetic fixtures prove mechanics, not fresh model prose, semantic entailment or acoustic quality. The three-minute minimum cannot justify invented source evidence, repetition or slowed speech.
