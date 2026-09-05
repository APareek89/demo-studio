# Demo Studio QA best practices

Last reviewed: 2026-09-05

## Product calls

1. **A demo is decision support, not a narrated catalogue.** It should learn the buyer's outcome, choose the smallest relevant proof route, answer the immediate question, and advance to a concrete next step.
2. **Evidence outranks fluency.** A graceful refusal with the missing document named is better than a plausible answer without support.
3. **Synthetic commercial data stays synthetic in every surface.** Pricing and EMI test fixtures must be labelled before the amount, carry their assumptions, and never be presented as an offer, eligibility result or approval.
4. **Product identity is a hard gate.** A high-resolution visual of the wrong trim, colour or product is a failure. Multi-view 3D inputs must represent one product identity across all required angles.
5. **Voice is optional; comprehension is not.** The customer can mute immediately, continue entirely in chat, read the current utterance, and operate controls by keyboard.
6. **A passing build is not a passing demo.** The packaged script, runtime planner, FAQ, source citations, media handoffs, MP4 export, responsive layout and traces all need evidence.

## Current authoritative guidance translated into tests

### Conversation quality

Google's conversation-design guidance applies the cooperative principle: responses should be truthful, no longer than needed, relevant and clear. It also recommends role-playing sample dialogs and listening to TTS rather than judging spoken copy only on the page.

Tests:

- The first question captures name plus the outcome the buyer wants, without asking for a data dump.
- Each answer leads with a direct response, then the minimum evidence, condition and next move.
- Follow-up prompts do not repeat information already supplied.
- No-match and unsupported-answer turns are brief, name the gap, and offer a useful recovery path.
- Intent-specific matching is fail-closed: if the required claim is absent, decline instead of falling back to the nearest lexical fact.
- Scope words such as “standard”, “every variant” and “across the range” require explicit variant-scope evidence; feature availability alone is insufficient.
- Three distinct customer conversations per demo exercise terse, detailed and adversarial/boundary-seeking behaviour.
- Spoken lines are checked in both audio and chat form for length, rhythm, pronunciation and interruption recovery.

Sources:

- https://developers.google.com/assistant/conversation-design/learn-about-conversation
- https://developers.google.com/assistant/conversation-design/write-sample-dialogs
- https://developers.google.com/assistant/conversation-design/table

### Accessibility and media control

WCAG 2.2 requires text alternatives for controls, captions for prerecorded synchronized media, keyboard operation, logical focus order, visible focus, adequate target size, programmatic name/role/value and perceivable status messages. Audio that starts automatically needs a mechanism to pause, stop or control volume.

Tests:

- Mute is available before narration, has an accessible name and pressed state, and governs recorded narration, browser speech and film audio together.
- Chat is a complete interaction path; speech recognition is never required.
- Prerecorded speech has synchronized captions or an equivalent transcript in the visible experience.
- Pause/resume/skip/restart are keyboard operable; focus order follows the visible sequence and never becomes trapped.
- Status changes such as planning, buffering, rebuilding, errors and saved leads are exposed to assistive technology.
- 320 px mobile reflow, tablet and desktop layouts preserve chat, captions, controls, CTA and the product focal point without overlap.
- Reduced-motion and quiet-mode behaviour do not remove information.

Sources:

- https://www.w3.org/TR/WCAG22/
- https://www.w3.org/WAI/WCAG22/understanding/
- https://www.w3.org/WAI/WCAG22/Understanding/captions-prerecorded
- https://www.w3.org/WAI/WCAG22/Understanding/focus-order

### Finance and price representations

RBI guidance for regulated lenders centres the pre-contract Key Facts Statement and disclosure of the all-inclusive annual percentage rate. Demo Studio is not a lender and must not imitate an approval or replace the lender's KFS. The product test is therefore conservative: show assumptions, distinguish EMI from total cost, disclose exclusions, and route the buyer to a written lender quotation.

Tests:

- Official ex-showroom facts are separated from synthetic on-road examples.
- EMI responses state price basis, down payment, principal, rate type/rate, tenure and indicative EMI before a CTA.
- Processing fees, insurance, registration, add-ons, foreclosure and eligibility are never silently assumed.
- The guide does not claim approval, guaranteed rate, guaranteed disbursal, stock or delivery.
- A comparison names its official manufacturer source and ends with a live-verification caveat when trim, price or availability can change.

Sources:

- https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=12382&Mode=0
- https://www.rbi.org.in/scripts/AnnualReportPublications.aspx?Id=1436
- https://www.rbi.org.in/commonperson/images/FAME202426022024.pdf

## 100-point acceptance rubric

### 1. Grounding and citations — 22 points

- 10: Every factual runtime answer resolves to an included source and locator.
- 5: Prices, offers, availability, warranty and variant claims carry applicable conditions.
- 4: Unsupported questions produce an explicit gap and correct escalation.
- 3: Source manifest identifies provenance, freshness, synthetic material and excluded inputs.

### 2. Conversation and decision quality — 18 points

- 5: Intake identifies the buyer outcome with low friction.
- 5: Route prioritises the buyer's concern and adapts after questions.
- 4: Turns are direct, brief and cooperative in chat and speech.
- 2: Honest do-not-recommend condition is present.
- 2: CTA resolves the largest remaining uncertainty.

### 3. Visual and product identity — 15 points

- 6: One identity across 3D views; required angles show the complete product.
- 4: Script visual references exist and match the narrated feature.
- 3: Gemini visual audit is reviewed; crop/subject confidence is acceptable.
- 2: 3D asset is manually inspected for geometry, texture, scale and rotation.

### 4. Film, voice and accessibility — 12 points

- 3: Opening film, before/after handoff and main route play without dead air or overlap.
- 3: Captions/transcript, audio control and chat-only completion work.
- 2: Pause, resume, skip, restart and mute preserve state.
- 2: TTS pronunciation and pacing are acceptable, with provider fallback recorded.
- 2: Keyboard/focus/name-role-value checks pass.

### 5. Finance and comparison safety — 10 points

- 4: Synthetic estimates are unmistakably labelled and assumptions are repeated.
- 3: No approval, price, availability or delivery promise is implied.
- 3: Comparisons are official-source-bounded and caveated.

### 6. Runtime integrity and responsive UX — 12 points

- 4: Three customer conversations and at least ten substantive questions per car complete without contradiction.
- 3: Desktop, tablet and mobile preserve controls, content order and product framing.
- 3: MP4 export has valid audio/video streams, duration and playable content.
- 2: Repeat path passes after fixes without stale state or wrong-demo leakage.

### 7. Observability and reproducibility — 6 points

- 2: `RUN.md`, usage, trace, script, FAQ, bundle and provider logs agree.
- 2: Every paid call records provider, model, result, tokens/units and USD cost where returned.
- 2: Demo IDs, URLs, source package and exact regression commands are recorded.

### 8. General UI quality — 5 points

- 2: No clipping, overlap, invisible state or unreadable contrast at target sizes.
- 2: Errors explain cause and recovery without exposing raw provider internals.
- 1: Loading and completion states are timely and unambiguous.

## Release gates

- Target score: **90/100 or higher for every car**.
- Any unresolved P0 or P1 blocks the next car regardless of score.
- Any unsupported price/finance/availability promise is a P1.
- Wrong-product or mixed-identity 3D input is a P1.
- Inability to complete in muted chat mode is a P1 for this QA programme.
- Missing paid-call cost evidence caps Observability at zero and blocks the final completion report.

## Run sequence and evidence discipline

1. Snapshot source package and manifest.
2. Inspect each 3D input at full frame, review the Studio gate, approve once, record task ID and cost.
3. Configure sources; inspect Understanding, plan, script and FAQ outputs.
4. Review and explicitly approve every Align card. Do not bulk-approve unseen cards.
5. Build, inspect Gemini visual audit, validate TTS provider/fallback and review the bundled timeline.
6. Run three chat-first customer conversations, ten or more questions each, covering facts, finance, comparison, refusal and callback capture.
   Complete or explicitly skip intake before counting the first customer question; chat entered during intake is profile context, not runtime Q&A.
7. Check desktop/tablet/mobile, controls, focus, captions, restart/skip and MP4 export.
8. Inspect `RUN.md`, trace, usage, visual-audit, script, FAQ, bundle and provider logs.
9. Separate input gaps from reusable product defects. Fix reusable defects, add the narrowest regression, rerun the affected path, then run the free suite.
10. Score only after evidence is stable. Commit a clean checkpoint before starting the next car.
