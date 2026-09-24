# FMEA — slide continuity correction

Scope: the current branch diff for slide rendering, the walkthrough compatibility adapter, Deck caption preservation and explicit reviewed-label creation. Product context: `PRD.md` promises reviewed on-slide image/feature evidence with matching voice; the latest instruction narrows this fix to slides. Existing agents/nodes, narration, runtime and controls stay unchanged. No new dependency or paid call.

The initial actual-Bundle browser pass found two concrete residual presentation failures and was retained: mobile third-tag clipping and a seven-pixel footer overlap. Both received a narrow layout fix rather than a relaxed assertion. Code review also found stale image-part geometry on a media swap/rebuild and a legacy image-ID selection mismatch; regression tests preceded their fixes.

| Failure mode | Effect | Correction/evidence | S | O | D | Residual RPN | Priority |
|---|---|---|---|---|---|---|---|
| Discard proxy captions because pixels cannot prove a fact | Silent tagless narrated screens | Keep only approved on-slide model citations, clear part geometry, same wording/length validation; negative foreign/mixed/uncited cases | 6 | 2 | 2 | 24 | P2 |
| Previous picture's part/drag reused on a replacement | False feature location | Strip retired attachments before explicit review edits; rebuild retests exclusions; independent six-case review | 7 | 1 | 2 | 14 | P2 |
| Saved created label survives evidence retirement | Stale claim shown after rebuild | Revalidate approved slide citations, picture, reveal and count before restoration | 7 | 1 | 2 | 14 | P2 |
| Mobile third tag clipped / rail covers footer | Spoken feature loses its visible label | Wrap up to three labels in fixed reserved space, measure footer clearance; actual every-line phone screenshots | 5 | 1 | 2 | 10 | P2 |
| Walkthrough replaces hero/closing or delays labels | Wrong picture accompanies speech | Native passthrough in both URL modes; no gallery DOM, transitions, timers or alternate timing owner | 6 | 1 | 1 | 6 | P2 |
| Tests pass empty image/tag arrays | A mechanically green but broken presentation ships | Actual artifact gate requires positive image/tag counts, current-line visibility and unchanged recorded-line metadata | 6 | 1 | 1 | 6 | P2 |

These are residual scores after the corrections, not a retroactive low score for the rejected presentation. No remaining concrete P0/P1 was found in this bounded diff.

Coverage: **12/12 categories checked**.

- **unhandled_error_paths:** malformed creation, unknown edit, invalid citation/image/reveal and excess labels return review errors; no stage/provider call is introduced.
- **external_dependency_failures:** no new network dependency. Existing exact recorded bytes are reused; missing source evidence is not replaced by generated claims.
- **race_conditions_and_state:** native view identity and playback ownership remain; removal of gallery timers eliminates stale animation callbacks. Existing owner editing/concurrent publication boundaries remain.
- **resource_exhaustion:** existing sixty-slide edit bound, three labels per picture, eight words per tag and two pictures remain; adapter creates no resources.
- **security_access_control:** new creation stays within the existing owner Align endpoint, allowed image catalogue and approved slide facts; no external source or permission expansion.
- **data_integrity_partial_writes:** normal saved overrides plus deck review are used; current bundle stays intact until the normal gated Bundle stage. QA example has before-state snapshot and unchanged script/audio hashes.
- **observability_gaps:** prior empty-array acceptance corrected; every actual slide/line is captured, with failures preserved and provenance explicit. Mechanical QA is not acoustic QA.
- **scale_and_load_failures:** no new scalable service/work queue. Fewer DOM nodes/timers than the gallery path; static labels preserve current rendering bounds.
- **billing_credit_mismatches:** no provider path added or invoked; recorded usage hash unchanged. Mock release and browser checks use isolated/blocked environments.
- **retry_idempotency_issues:** repeated creation ID is explicitly rejected, avoiding duplicate tags; ordinary edits and repeated rebuilds retain stable reviewed IDs.
- **config_feature_flag_drift:** old walkthrough URL still works, using the same image/tag view; both flag states, phone and desktop are tested.
- **edge_cases_from_prd:** hero/closing ownership, two-picture labels, current-line reveal, approval invalidation, source exclusion, unanchored conditional captions, narrow layout and fixed slide/dock geometry are covered.

Sentinel: misuse (invented pins/unreviewed facts), storage (only the isolated example), motion (no alternate playback owner), and maintainability (gallery implementation removed instead of hidden dead animation) reviewed. No extra scope added.
