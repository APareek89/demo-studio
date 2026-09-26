# Mobile runtime release — 26 September 2026

Application3591fb7 is on GitHub master and AWS, cut over2026-09-26T08:17:17Z. A separately tested CSS-only welcome correction is pending; its exact overlay provenance will be recorded below.

This release fixes recorded-audio gesture ownership and retry, bounded Web Audio resume, short-screen gallery height, drawer overflow and selected-label visibility after rotation. The exact BMW publication/recordings, core graph/workflow, approved gallery and existing provider/LiveKit configuration remain. Optional browser icon/manifest GET/HEAD requests return404 without an operator challenge; private routes stay protected.

## Local evidence

[Full QA, failure history and twelve-category FMEA](../qa/mobile-runtime-2026-09-26/README.md). Core445/445, acceptance24/24, smoke3/3, full mock28/28. Native mounted WebKit26/26 (Safari/CriOS profiles), recorded ownership12/12, AudioContext13/13; mobile104/104, gallery320/320, native88/88, continuity28/28, scrolling12/12, image ownership14/14, WebKit typed fallback10/10. Native local RTC30/30 after two retained failed attempts. Public hosted WebKit mic-off RTC10/10 through TURN/TLS443; no questions, device or provider calls. Existing isolated real proxy58/58 and153/153; release-helper fixtures18/18. Counts overlap.

Native WebKit emulation is not either installed browser on a physical iPhone. Acoustic microphone/speaker behavior, actual OS keyboard/background handling and cellular conditions remain unverified. No new paid QA.

## Release inventory and recovery

- Source commit: `3591fb7b8489a565e3aa2bfde66de22d66a21b30`;1436 source files, excluding user data/output/environment/virtualenv. Archive61381855bytes. The unactivated6e0e084 upload is retained separately as superseded; it was never cut over.
- Candidate source: `/opt/demo-studio-releases/20260926-mobile`; private receipts `/opt/demo-studio-backups/20260926-mobile`.
- Prior active source/runtime: `/opt/demo-studio-releases/20260925-livekit`; its unchanged virtualenv is reused only after all dependency files match. A WorkingDirectory-only override selects the new source; original ExecStart and environment remain.
- Before cutover: confirm no Build/customer room active, snapshot configuration, stop app, hash and archive all current data (including recently saved customer visits), then verify every archived file's contents. Failure restores the prior code while keeping current shared data.
- Proxy: separately snapshot actual Caddy, insert only the exact optional-asset matcher/handler, prove removal recreates original bytes, validate and reload. Proxy rollback is independent of app rollback.
- Recovery commands and verified invariants: [release runbook](mobile-release-tools/README.md). Do not restore an old customer-data archive during ordinary code rollback.

## Actual AWS execution

- AWS staging36/36 suites, mock/isolated/blocked sockets, zero outbound attempts. Core445/24/smoke3/full mock28; per-suite results and hashes in [gate inventory](../qa/mobile-runtime-2026-09-26/aws-gate-counts.json). Knowledge58passed+2explicit environment skips (local OCR and installed Chrome unavailable).
- All4273 existing data files preserved byte-for-byte; none missing, changed or added during cutover. Full862103590-byte backup was verified file-by-file; archiveSHA256 `fd016a360b96625e992fbde2f1d765f44c1ea7b2ca83f170c5450f8f58b8f3b2`. Recent customer sessions are included.
- Exact proxy patch20/20; public application32/32, including33 exact frontend hashes, BMW bundle/media ranges, transport discovery and private-route protection. All1436 source files verified before the pending CSS overlay. Providers, runtime and operator authentication unchanged.
- Post-cutover public WebKit10/10: six frontend hashes bound to3591fb7; actual session.ready via TURN/TLS443, no microphone/question/provider/visit-save calls, no script errors or blocked URLs, and zero participants after cleanup. Its landscape screenshot exposed a separate welcome-button clipping defect; the10/10 is connectivity/source acceptance, not whole-screen acceptance. That defect remains open until the CSS correction below is verified.
- Actual raw receipts: `output/deploy-mobile-20260926/` locally and the private remote receipt directory above. No paid QA; physical iPhone remains untested.
