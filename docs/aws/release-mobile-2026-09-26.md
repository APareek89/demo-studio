# Mobile runtime release — 26 September 2026

Application3591fb7 is on GitHub master and AWS, cut over2026-09-26T08:17:17Z. The separately tested5543fe1 CSS-only welcome correction is also deployed and publicly hash-verified. Subsequent documentation commits do not change running application bytes.

This release fixes recorded-audio gesture ownership and retry, bounded Web Audio resume, short-screen gallery height, drawer overflow, selected-label visibility after rotation and clipped welcome/intake controls in short landscape windows. The exact BMW publication/recordings, core graph/workflow, approved gallery and existing provider/LiveKit configuration remain. Optional browser icon/manifest GET/HEAD requests return404 without an operator challenge; private routes stay protected.

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
- Exact proxy patch20/20; public application32/32, including33 exact frontend hashes, BMW bundle/media ranges, transport discovery and private-route protection. All1436 source files verified before the CSS overlay and again afterward with only its explicit CSS digest exception. Providers, runtime and operator authentication unchanged.
- Post-cutover public WebKit10/10: six frontend hashes bound to3591fb7; actual session.ready via TURN/TLS443, no microphone/question/provider/visit-save calls, no script errors or blocked URLs, and zero participants after cleanup. Its landscape screenshot exposed a separate welcome-button clipping defect; the10/10 is connectivity/source acceptance, not whole-screen acceptance. The separately tested CSS correction below fixes that defect.
- Actual raw receipts: `output/deploy-mobile-20260926/` locally and the private remote receipt directory above. No paid QA; physical iPhone remains untested.

## Final welcome CSS correction

- GitHub commit `5543fe1b76be8236d9e78be2baaae3722aa975d2`; only `web/player-ui.css` is overlaid on the deployed3591fb7 source. SOURCE_COMMIT remains3591fb7 and SOURCE_OVERLAY.json records the exact one-file change. Other files in5543fe1 are tests, release tooling and documentation, not a second application-source rollout.
- New CSS SHA256: `553311e9974c8e8527db59b04bf65a232f4d9276ebfde0a8fdbdd69c3f5dd2b8`. Original: `4b29880722c98a05292741bfecb6f8046e13483fda813c767360820ebb7eade6`. Exact full-manifest verification covers1436 files with this single explicit exception; public CSS bytes match.
- Real BMW welcome66/66 in native WebKit and Chromium covers portrait, three short landscape sizes, desktop, synthetic keyboard-height intake, long-title scrolling and toggle/Explore/Skip actions. The15/15 overlay fixtures cover source/payload validation, atomic replacement, backup, public mismatch/SIGTERM recovery and provenance.
- Actual private receipt: `/opt/demo-studio-backups/20260926-mobile/css-overlay-5543fe1b76be/verified.json`; original CSS is retained beside it. Local copy: `output/deploy-mobile-20260926/css-overlay-verified.json`. No app restart or customer-data write; the existing LiveKit relay and rooms are untouched. [Runbook](mobile-release-tools/README.md) includes independent CSS rollback.
- Final read-only public welcome21/21: exact CSS hash and native WebKit/Chromium at390×844,844×390 and844×320; complete, hit-testable voice toggle/start buttons and no overflow/unintended zoom. Screenshots inspected. No sessions, microphone, provider, mutation or socket calls. Two initial WebKit failures were caused by the temporary test's read-only getUserMedia guard interfering with the SDK shim; both failures and the confirmed import trace are retained, followed by the corrected WebKit12/12 run. Evidence: `output/deploy-mobile-20260926/public-welcome-final/final-results.json`. No production change was made for that harness issue.
