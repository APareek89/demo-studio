# Playground redesign — four prototypes (2026-09-03)

Clickable dummy flows, no app code touched. Each covers the same requirements from the 2026-09-03 feedback:
tabs renamed and reordered (Demo Studio · My Demos · Playground · Observability), My Demos opens a demo
full screen, Demo Studio › Rehearse gets a Full screen button, and the Playground becomes: pick an approved
demo → Test Now → question / expected-answer table (AI pre-fill, edit, add rows) → confirm → evals run in
real demo mode (voice-led player with live Q / A / pass / fail / reason) → score + insights → Take Action →
Demo Studio › Sources with only the missing material → rebuild → re-run.

Design inputs came from the UI/UX Pro Max databases (B2B SaaS reasoning profile: professional blue or navy,
Minimal Swiss / Soft UI / data-dense styles, 150–250 ms motion, skeleton loading, visible focus, SVG icons,
no emoji as icons, no purple gradients) and the artifact-design pass.

| option | file | layout idea | style · type | best when |
|---|---|---|---|---|
| A · Console | option-a-console.html | three panes: demos · questions/player · live eval ledger | Minimal Swiss + data-dense · JetBrains Mono / IBM Plex Sans | you and product folks run many evals and want everything on one screen |
| B · Stage | option-b-stage.html | the player is the hero; evals in a frosted drawer over a dark stage | Dark OLED + glass · Space Grotesk / DM Sans | the demo experience itself is what you're judging; showing customers/partners |
| C · Worksheet | option-c-worksheet.html | one scrolling sheet; the question table becomes the results table in place | Soft UI + flat · Lexend / Source Sans 3 | spreadsheet-minded users; long question lists; printing/sharing results |
| D · Guided | option-d-guided.html | five-step wizard, one thing per screen, one orange next-action | Flat + conversion-focused · Plus Jakarta Sans | non-technical sales-ops users; first-time use; mobile |

All four share the dummy data (your real demo names, 8 questions, 5/8 pass, 3 gaps: EMI, Pune on-road price,
Ather comparison) so only the layout and treatment differ.

## Missing links found while designing (to confirm before build)
1. **Grader.** Pass/fail needs a judge: Claude compares the guide's answer with the expected answer (semantic match + citation present) and writes the one-line reason. Today's evals only check "answered from sources or declined".
2. **Insights generator.** Failures are grouped by decline category (pricing, financing, competition, availability…) and mapped to the document that closes each — the same map the Facts card already uses.
3. **Additions-only rebuild.** Take Action must read only the new sources and merge facts into the registry (new F-ids), then re-plan, re-author, voice only changed lines (audio cache already makes unchanged lines free), rebuild, and re-run the same question set. Needs a "delta read" path in the orchestrator.
4. **Before / after.** Keep the last eval run per demo and show the score change after a rebuild (63 % → 88 % in the mockups). Cheap and it's the whole point of the loop.
5. **Demo-mode evals cost real voice.** Each question is spoken and answered aloud (TTS per answer). Offer a "silent run" toggle for long lists; demo mode stays the default because that's what the customer hears.
6. **Full-screen route.** A `#/play/<id>` route that mounts only the player (no rail), used by My Demos › Open and the Studio button; also the future embed target.
7. **Only approved demos in Playground.** Status `ready` = all five cards approved and built; anything else stays out of the list with a hint.
8. **Question sets are saved per demo** and reusable across builds (they become the regression suite for that product).
