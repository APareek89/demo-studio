# Gallery continuity FMEA — 25 September 2026

Scope: independent review of the current `web/player/walkthrough.js` diff and its actual-player browser regression, against `PRD.md` and `docs/ARCHITECTURE_FLOW.md`. Base commit: `97ef2ab`. Reviewed source SHA-256: `a93cc7f8d9d45e81a90b4510557c46e7d8db168a2489a8bfe5df8f3ce3aacbe5`.

The intended change is limited to consecutive narration about the same published picture. The existing player retains navigation, reviewed caption ownership, readiness-before-audio, interruption, pause and return. No Build/Align, graph, provider, storage or session ownership change is part of this visual diff.

## Finding and disposition

**Fixed P1 — identical pictures still pulsed during the parent slide crossfade.** Reusing the loaded image and camera geometry avoided the gallery entrance, but the old/new slide opacity transition composited both copies over the background, briefly bleaching unchanged pixels. Location: `web/player/walkthrough.js:336` (carried-view opacity fix); triggering existing rule: `web/styles.css:231`.

Before the fix, an independent muted Chromium probe sampled a stable point at 42% image width and 50% image height: RGB `[102,140,142]` before, `[134,164,166]` during transition, then `[102,140,142]` after. The old/new parent opacities were `0.333739` and `0.666261`; image geometry had not moved. After the fix, the same probe returned `[102,140,142]` before, immediately after, during and after the boundary, with the active slide at opacity 1. Carried-picture views now enter at full opacity; different-picture entrance behavior remains unchanged.

Score before fix: severity 3 × occurrence 8 × detection 7 = **168 (P1)**. Residual score after the narrow fix and regression: 3 × 2 × 2 = **12 (P2)**. No open actionable defect remains from this scan.

## Mandatory coverage — 12/12 categories checked

- **Unhandled errors:** no new throwing I/O path; only a loaded, settled, current image can be carried. Broken/load-timeout images retain native fallback.
- **External dependency failures:** no new service or remote dependency; cached image identity must match. Existing bounded image loading remains authoritative.
- **Race conditions and state:** parent-opacity defect above fixed. Epoch cancellation, settled-frame eligibility and immediate-previous-gallery ownership prevent carrying a pending or obsolete transition.
- **Resource exhaustion:** one image clone per visible transition; existing view disposal and image-cache reuse remain bounded. No new persistent collection or timer.
- **Security/access control:** no new input, endpoint, permission or HTML interpolation. Captions still come from reviewed data and use text nodes.
- **Data integrity/partial writes:** presentation never writes bundle, evidence or session data; regression confirms approved bundle bytes stay unchanged.
- **Observability:** no-op animation and mid-transition opacity regressions now cover the user-visible failure; this scan does not claim acoustic acceptance.
- **Scale/load:** changes are per-client DOM work on at most two allowed slide pictures, without shared backend load.
- **Billing/credit:** no provider or billing path changed; this review and pixel probe made zero provider calls.
- **Retry/idempotency:** repeated preparation skips a no-op camera move, while new feature geometry may focus once. Pause/resume and question return retain one voice owner.
- **Configuration/flags:** gallery-disabled/native hero/text-only views break continuity normally; native fallback and reduced-motion branches remain available.
- **PRD edge cases:** current reviewed label and pointer ownership are recalculated for each line; distinct pictures still transition before narration. Two-picture bindings, illustration disclosure, native welcome/closing and top/bottom shell ownership are preserved.

Verification available at review completion: final gallery continuity browser **28/28**, baseline **22/26** (four repeated-photo regressions reproduced), original targeted gallery source tests reported separately by the implementation owner. This independent review additionally verified the RGB failure and fix above using real Chromium, deterministic muted audio and loopback-only static assets. No physical microphone, paid provider or AWS test was performed by this reviewer.
