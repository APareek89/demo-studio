# Feedback workbook implementation — 24 September 2026

The app follows `Demo_Studio_Feedback.xlsx` from Anand Feedback: three worksheets, all populated rows and four embedded reference screenshots. The white demo direction replaces the earlier dark Marine sample. The duration choice replaces the fixed three-minute minimum for every build while preserving three minutes as the default and preserving automatic preparation.

Source SHA-256: `07bd3db79133b608d583b0b9683f5a83d41eb592e53b1ca1c06eca518ec45406`. The original workbook remains untouched; no private workbook or extracted screenshot is shipped with the app. No cell contents are treated as tool, shell or account instructions.

## Implementation mapping

| Feedback location | Result and boundary |
|---|---|
| Feedback 1, row 2 · Studio | Top-nav Studio opens blank Sources. No record is created just by viewing it; the first save/upload/read creates one draft. Explicit Open Studio links keep their saved demo. |
| Feedback 1, row 3 · nav | Asked whether “width” means height or horizontal span. Proceeded with the stated reversible assumption: height 76→45.6px, full width retained. Left Studio steps unchanged. C9 records the open interpretation. |
| Feedback 1, row 4 · Sources | Whole-number1–5minute selector, default 3. Selected duration drives supported word budgets, automatic Author preparation, Align timing, all selected-language measured publication checks and the pinned runtime route. Previous publication survives a duration change. |
| Feedback 1, row 5 · DemoView | Player fits desktop, embedded Rehearse, phone portrait and phone landscape viewports. Transient controls cannot resize the slide. Internal overflow remains scrollable where content cannot fit. |
| UI - Studio --> Reherse, K6/K8 | Top nav only receives compact-height adjustment; Studio left steps retain their function and layout. |
| UI - Studio --> Reherse, M8/M9/O9 | Remove the large Experience your Demo heading and side-panel stack. One full-height feedback conversation supports uploads, retained messages and visible progress/errors. On-demand rehearsal remains a compact chat-header action. Preview uses the shared revised player. |
| UI - Demo Slide, K3:K5 | White demo surface without separating panel/nav borders; selected-template dark text, dark filled primary actions; colored/light-blue actions use dark text. |
| UI - Demo Slide, K6 | Portrait rotation hint; native-aspect images and accessible controls before rotation; actual landscape viewport provides widescreen presentation. No forced browser orientation lock. |
| UI - Demo Slide, K8/K10/K22 | Borderless welcome, full-stage hero with a light fade behind readable content, native aspect with crop where necessary, no separate content panel below. Existing uploaded-image fallback applies when no explicit hero is supplied. |
| UI - Demo Slide, K28/K30/K42 | Intake uses the same hero-backed area and viewport-bounded text/controls; no separate panel below. |
| UI - Demo Slide, K48/K50 | Smaller heading near nav; two distinct supported pictures side by side, rounded edges/subtle shadow, reviewed labels and trusted anchors. Saved per-image full coverage can supply a second picture without another vision call. One supported picture remains one; unsupported duplicates and guessed anchors are rejected. |
| UI - Demo Slide, K62 | White conversation area with template-dark text and stable input/CTA controls. |

The original screenshots describe the previous UI and requested corrections; they are not new source evidence for any product claim. Reviewed facts, exact human wording and coordinate ownership remain unchanged. Rehearse uploads use the existing Align workflow and human review checkpoint. Selective feedback-stage routing remains pending as previously requested.

## Validation

Baseline on clean commit `a2e5097`: deck365/365, acceptance24/24, smoke3/3 phases. All baseline checks used isolated storage, MOCK_LLM=1 and blocked outbound sockets. Final local gates: **51/51 suites; 1,790/1,790 reported checks/groups/phases (nested coverage overlaps)**. Required deck380/380, acceptance24/24, smoke3/3; full release journey28/28, with194.22seconds of measured fixture audio. Every exact count and hash is in `feedback-workbook-gates-2026-09-24.json`; twelve-category review is in `feedback-workbook-fmea-2026-09-24.md`. GitHub and AWS release: `483755d`; see `aws/release-feedback-workbook-2026-09-24.md`.
