# WP12 — gallery walkthrough review · 24 September 2026

Implemented only behind `?presentation=walkthrough` before the route hash. The default player, Align editor and preview retain their prior layout. A wrapper on the existing renderer owns the gallery, one frame per content picture, reveal-driven feature stops, bounded native-aspect zoom, pause/resume and interruption retargeting. Narrow stages and reduced motion use the existing layout. No backend, bundle, workflow, narration or runtime change belongs to this package.

## Validation

- Core: qa_deck380/380; qa_accept24/24; smoke3/3 (Read, Build, on-demand rehearsal).
- Browser: layout193/193; workbook101/101; Studio integration19/19; navigation22/22; HTML player79/79.
- Default-mode chrome screenshots and Align editor/preview DOM:9/9 exact matches.
- Node: walkthrough29/29; media7/7; focus21/21; fundamental10/10.
- Motion85/85 and live browser26/26 pass; receipts are in the adjacent JSON files. Mock speech controls verify ownership and visual pacing, not acoustic voice quality.

The baseline already had two stale HTML assertions (mobile picture stacking and dimming) and obsolete live-flow expectations. Anand authorized correcting those tests. The preserved baseline and new assertions retain geometry, voice, interruption and session coverage.

The reference HTML source was inspected, but browser security rejected its local-file URL. No alternate access route was used. The requested visual evidence was recorded from the running app harness. All checks use MOCK_LLM=1, isolated storage and blocked external sockets; browser loopback only. No paid calls, protected demo operation, port8896 use or AWS deployment.

## FMEA

Twelve configured categories reviewed against the PRD and runtime diagram. No unresolved P0/P1 in this package. Closed findings: zoomed media could escape its viewport; CSS now clips at the actual picture box. Old callout chips could briefly overlay the grounded stop caption; scoped visibility hides them immediately. Resize during pause previously retained obsolete geometry; the state machine now discards that geometry while preserving the frozen pose. Fallback cleanup removes detached observers and restores the actually active second picture. Reveals select the active picture when multiple tags appear together.

Reviewed controls: generation-owned callbacks and safety timeouts; idempotent stop/destroy; no provider/dependency addition; immutable bundle and checkpoint state; textContent captions; existing approved media only; one frame per bounded deck picture; diagnostic phase/frame/stop attributes; before-hash flag isolation; native-size fitting/zoom caps/pan clamps; reduced-motion and stage-size fallback. Grounding comes from existing tag text/part/fact IDs without new visual or factual claims.

A stricter mid-walk pause check found that an opacity transition could settle a moving-layer task before its transform ended. Completion now waits for the intended property, and freeze captures every owned live layer defensively. The new state regression and actual pause/resume during walk/dive/stop all pass.
