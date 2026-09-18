# NX40 — a proposed next step was recorded as customer selection

Actual reproduction: in the predeclared live sample, the customer submitted L4, “I mainly want help with stop-and-go traffic. How should I assess this selected Nexon automatic?” No CTA was clicked. The model response included a test-drive CTA, and the player automatically spoke a handoff assurance and opened a recap saying the customer selected Book a test drive. Preserve `L4-unrequested-cta-recap.txt` and `.png`; no lead submission was observed, but the recorded selection and promise were false.

## Cause and correction

`handleQuestion` passed `r.cta` straight to `ctaFlow`. That function immediately set `S.cta`, spoke as if details would be passed to the team, and ended at the recap. A model's proposed action crossed the boundary into customer intent. Separately, closing replies used substring matching, so “Do not book a test drive; I still have a question” could select the same action.

The model field now adds only an optional configured CTA chip beside the normal answer-confirmation choices. “Yes, that helps” confirms the answer and does not select the CTA. Only a CTA button or exact typed/spoken CTA label at an available choice enters `ctaFlow`; an embedded or negated mention stays a question. `ctaFlow` rejects unknown IDs and stale runs. Its wording says details can optionally be left for follow-up; it makes no claim that a handoff has happened. The existing consent form is still required for any actual lead submission. This does not classify free-form consent using a new model or keyword parser.

## Five whys for Learning.MD

1. Why did L4 end at a selected-action recap? The answered QA response had a CTA ID.
2. Why did that ID change the customer session? `handleQuestion` invoked the selection flow directly.
3. Why was it trusted? A schema description of customer intent was treated as proof of customer intent.
4. Why did the customer hear an unsent-handoff promise? Selection and contact submission had shared success-like narration despite being separate actions.
5. Why did existing checks miss it? They covered callback refusal and explicit closing choices, not an unsolicited model CTA or a negated mention of a label.

Prevention: keep proposal, explicit selection, and consented submission as separate events. Test unsolicited/negated suggestions and the positive explicit-selection path against the real player DOM.

## Verification and documentation hooks

- Actual browser baseline: **33/36**, all three new consent cases failed; `browser-cta-before.txt`.
- Changed only `web/player/player.js` and `evals/player_contract.html`; no provider, schema, service, data or Build change.
- Local checks: player/harness syntax, focus **12/12**, scoped `git diff --check` pass. Root owns the final browser execution and targeted actual L4 recovery evidence.
- New browser cases cover an unsolicited model CTA holding for the buyer, explicit selection retaining an optional consent form without a handoff promise, and a closing refusal remaining a question while an exact label still selects.
- Loop row: “Model CTA is a suggestion only; explicit selection required; contact form owns lead consent.” Link the free player browser contract and before/after evidence.
- Runtime diagram/Handoff decision: after supported QA, optional configured CTA joins the owned answer-confirmation wait; only explicit selection leads to recap. A proposed CTA is not a recorded customer selection or a submitted follow-up.

Limits: this controls the player action and its own handoff wording. It does not prove every generated answer is semantically grounded or that model-authored text cannot itself contain an unsupported promise. Actual provider latency and acoustic quality are separate from these synthetic checks; review remains muted.
