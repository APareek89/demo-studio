# AWS release — feedback workbook · 24 September 2026

Application commit: `483755d99ede07e8a6ef088909f305b05ae54910` (`WP11: apply feedback workbook and selected narration duration`). GitHub master contains this commit. Active release: `/opt/demo-studio-releases/20260924-feedback`, selected by `98-release-20260924-feedback.conf`. Previous release/drop-in97 remain available for rollback; no shared data or environment was replaced.

Live app: [Demo Studio](https://13-202-0-79.sslip.io/#/home). Local isolated mock app: [localhost:8905](http://127.0.0.1:8905/#/home). Local health and served CSS match the new source; no real Build was triggered.

## Verification

- Local: 51/51 suites, 1,790/1,790 reported checks/groups/phases, with overlapping nested coverage. Required deck 380/380, acceptance 24/24, smoke 3/3; full mock journey 28/28 with 194.22 seconds of measured fixture audio. Duration 19, upload retry 12, upload stream 19, media 60, Studio 29, workbook player 101, layout 193, navigation 22 and fully assembled app/player 19 all pass. [Exact gate inventory](../feedback-workbook-gates-2026-09-24.json).
- FMEA: 12/12 categories; fixed duration identity, upload retry/source routing, mobile child-control/rail overflow, short-stage image collapse and control contrast before release. [FMEA report](../feedback-workbook-fmea-2026-09-24.md).
- AWS staging: 23/23 suites pass using committed source, MOCK_LLM=1, fresh temporary data/graph paths, blank provider keys and blocked outbound sockets. All 23 logs record zero outbound attempts. Production data/environment were not linked during these checks. Source SHA-256 manifest verified before and after staging. No paid provider or acoustic check.
- Cutover: 2026-09-24T06:45:07Z. Health passes with production mock mode off; shared environment checksum unchanged; no new service errors at release verification. Caddy, HTTPS, IAM/security groups and provider settings remain unchanged.
- Data: 4,087 files before and after; none missing, changed or added. Stored demo bytes are unchanged. Counts remain 13 demos, 11 bundles and 22 saved sessions.
- Public read-only checks: HTTP 200, frontend 25/25 hashes match the release, and existing nonprotected image/audio byte ranges return 206. No live Read/Build/runtime question/session mutation or microphone request.

## Recovery and evidence

Full stopped-service backup: `/opt/demo-studio-backups/20260924-feedback/data.before.tar.gz`, 785,699,469 bytes, SHA-256 `615001bcbbe05d4ea3667f40fd2f2bbfd15bc8383763e033cf32a111e97de3be`. Environment checksum, service configuration, before/after data manifests, staged logs and receipt remain under the same private directory. Local receipts: `/tmp/demo-studio-feedback-release-20260924/`.

Cutover installed only a new systemd drop-in and retained the old release. On startup failure, the script stops the new service, removes only its new drop-in, reloads systemd and verifies the previous release. A code rollback must retain current shared customer data; do not restore the backup over newer customer work without reviewing it.

## Known boundaries

C9 records the stated interpretation of 40 percent less nav “width” as 40 percent less height. C7 hosted builder access, C8 Cloud alternate-language voice identity, existing small-instance capacity, scanned-PDF OCR, damaged nonempty audio-cache recovery and selective Align rebuild routing remain pending. Portrait/landscape browser geometry is verified; physical phone rotation, soft-keyboard and acoustic acceptance are not. The workbook and protected local demo/output paths were untouched; port 8896 was not operated.
