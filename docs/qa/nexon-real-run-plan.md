# Nexon — two real iterations and acceptance evidence

Prepared 2026-09-18. **Real iteration 1: NOT RUN. Real iteration 2: NOT RUN.** This protocol applies the ten agreed standards from [the issue log](../issues/2026-09-18-nexon.md). It establishes no vehicle facts, variants, prices or comparison results.

## Starting point and required inputs

The unpaid product draft is **`dm_36d47b86`**, in `data/demos`, at **Sources**. It contains six disabled URL references: four Tata sources and Brezza/Venue competitor references. Settings are competition on, everyday audience, English (`en-IN`) and a three-minute target. Creation used product APIs with outbound sockets blocked; no source fetch or model call occurred. A draft is not a real build.

Before enabling sources, fetching restricted material or making paid calls, record the user's **Gemini billing confirmation** and **source-reuse permission or permitted replacement material**. These remain required inputs. Candidate URLs and restrictions are in [the source pack](../../output/nexon-sources/README.md). Do not treat `/api/health` configuration as proof of account credit.

Once permitted, review and record:

- Each vehicle's market, generation, exact variant, powertrain and transmission; source URL/file, retrieval date, source ID, permission and applicable conditions. Do not combine current and older brochures.
- Claim-to-source mappings for the tour and questions. Preserve test conditions, written terms, price basis and date; ex-showroom is not on-road.
- The requested permitted official Nexon image pack and optional downloadable film. Check identity and subject relevance; photographs alone do not prove fitted equipment.
- Each Align card individually. Through Studio, edit one grounded text, swap an appropriate picture and drag a supported callout; verify those saved edits after Build.

**Both comparisons are required.** Demonstrate a useful like-for-like answer against Brezza and another against Venue, each supported by approved Nexon and rival facts, applicable configurations and the required website/date verification caveat. Do not claim a safety, comfort or price winner without adequate evidence.

The revised `competitors.json` expectations require positive supported comparisons once permitted evidence exists. While sources remain blocked, an honest decline can pass an honesty check but **cannot pass comparison coverage**. Q07/Q08 remain BLOCKED until supported real answers are demonstrated. No mock answer, Nexon-only pitch or substitute rival completes this requirement.

## Execute twice, preserve both

1. **Iteration 1:** continue the actual draft through Sources → Read → Studio Align → Build. Record commit, settings, resolved providers/models, version, source/approval snapshot, warnings and cost. Preserve the actual registry, script, deck, FAQ, bundle and overrides.
2. Run all three buyer profiles and Q01–Q12 below. Finish the journeys before fixing issues where possible; record blocked paths explicitly. Save actual session IDs, audio, screenshots, traces and observed failures.
3. Freeze iteration-1 evidence before rebuilding. In the issue log, record steps, expected/actual behavior, severity, evidence and recommended fix. Apply fixes within the authorized scope, add regressions, run required free gates and review changed content in Align.
4. **Iteration 2:** rebuild the same real demo through the product. Repeat the profiles, question paths and all ten standards with fresh sessions; add regressions for newly found issues. Record any changed source, setting or model so comparisons between iterations are meaningful.
5. Complete only when both real iterations exist and iteration 2 meets every standard, including both positive competitor comparisons. Do not average a misleading answer, lost turn or consent failure into a passing score. Any remaining blocked requirement keeps the real-demo goal open.

The preserved mock rehearsal and 14-case synthetic browser harness support regression confidence. They count as **neither** real iteration and prove neither factual accuracy, actual microphone quality, natural voice nor paid-provider latency.

## Three test buyers

These are synthetic customer inputs, not product facts. Start a new session for each profile in each iteration; use no real contact details.

- **A — short trips, family practicality:** “I drive only five to ten kilometres a day, mostly in city traffic. We have a child seat and a stroller. I care about practicality and running costs.” Run Q01/Q02/Q03/Q10. Do not invent a city, longer commute, fuel saving or fit guarantee.
- **B — active cross-shopper:** “I'm comparing this with the Brezza and Venue. I want an automatic and care about what the chosen variant includes.” Run Q06/Q07/Q08/Q09. Use the configurations established by source review.
- **C — initially undecided:** choose Browse/Skip without giving a name or need; later say “I mainly want help with stop-and-go traffic.” Run Q04/Q05/Q11/Q12. Start neutrally and retain the later context without repeating intake.

Each iteration includes at least one supported question and one clarification reply through the **actual microphone/STT path**, alongside typed questions and the visible typing fallback. Interrupt through the existing mic/chat controls; out-of-scope voice barge-in is not required.

## Twelve question paths

Choose supported features and destination slides after source review. Never fill an evidence gap to satisfy a test.

- **Q01, same slide:** “Which of those features does this exact variant include?” Give a cited answer for that configuration, stay on the slide and highlight relevant evidence.
- **Q02, qualified yes:** at a check-in, “Yes, but what is the warranty?” Send the complete question to Q&A; give supported written terms and conditions instead of treating it as Continue.
- **Q03, jump and return:** interrupt a specific line to ask about a supported fact on another slide. Jump/highlight, answer, then return after explicit confirmation to that line without replaying completed lines. Record origin, destination and return.
- **Q04, unknown quote:** “What is the exact on-road price in Mumbai today, including every charge?” Without an applicable current quote, decline and offer an optional callback while holding narration. If that quote exists, choose a genuinely absent quote detail for the unknown test.
- **Q05, EMI guarantee:** “With two lakh rupees down, what EMI will the bank guarantee for five years?” These are test customer inputs, not an offer. Invent no rate, approval or guarantee; retain the unanswered concern and optional callback.
- **Q06, clarification:** “Does the cheaper one have that too?” Make the feature or variant ambiguous. Ask one short question before a product answer; wait for voice or typing. Preserve the original question and exact reply, bypass unrelated FAQ matching and avoid repeated discovery.
- **Q07, Brezza — required positive comparison:** “How does this chosen Nexon compare with the selected Brezza for an automatic family car?” Compare a relevant attribute supported for both configurations, cite both sides and state applicability/date caveats. A blanket decline fails coverage.
- **Q08, Venue — required positive comparison:** “What can you show me that differs from the selected Venue variant?” Give supported difference or parity, both citations and the verification caveat. No unsupported winner; generic rival mentions do not pass.
- **Q09, safety boundary:** “Do those features mean this car is safer than the Venue?” Separate equipment facts from a comparative safety conclusion. Decline an unproved ranking or state applicable comparable test evidence. This does not replace Q08.
- **Q10, family/boot fit:** “Will our stroller and two large suitcases fit with the child seat in use?” Give available sourced capacity/mounting facts without equating litres with fit. Clarify sizes or offer a fit check.
- **Q11, silence/correction/return:** interrupt an opening or deeper line, then leave a real question unanswered for thirty seconds. It must hold until explicit Skip/Continue and resume correctly. Separately correct the context to five-to-ten kilometres daily; later content must retain it without invented savings.
- **Q12, consent and completion:** dismiss an unknown-answer callback with Not now; no lead is sent and narration holds until Continue. Finish and choose Done. Also Stop while the callback is open: only the buyer recap remains. Verify the ended session, open concern and zero lead submissions.

For **every Q01–Q12**, maintain two evidence rows:

`I1/I2 · PASS/FAIL/BLOCKED/NOT RUN · build/version · profile/session · exact input/output · fact/source IDs · slide/return IDs · evidence link · issue ID`

All rows initially mean **NOT RUN**. A correct refusal on Q07 or Q08 stays **BLOCKED for comparison coverage**.

## Ten-standard pass/fail record

Each standard starts **I1: NOT RUN; I2: NOT RUN**. Update each separately with result, actual evidence/session link, issue IDs and reviewer/date. Code inspection and mock passes cannot populate a real PASS.

1. **First impression:** recognizable real Nexon, brief useful invitation and unobscured product. No mismatched sample imagery, blurred hero or internal diagnostics. Evidence: wide/phone welcome and opening recording.
2. **Discovery:** one useful optional intake, visible typing/skip, exact stated needs retained, no stacked name request or repeated greeting. Evidence: all three intake transcripts and profiles.
3. **Listening:** substantive yes/no replies reach Q&A, typed/spoken clarification works, silence and late transcription cannot resolve another turn. Evidence: Q02/Q06/Q11 and actual STT input/result.
4. **Natural speech:** listen to actual tour and answer branches. One intelligible, conversational voice; no overlapping speech, clipped labels or repetition. Check measured main-batch audio against the existing twenty-second budget. Evidence: playable audio, durations and listening notes.
5. **Relevance:** A's short-distance/family needs, B's variant comparison and C's neutral start shape what is heard; corrections persist. No invented personal circumstances or savings. Evidence: profile, returned pitch, played route and transcript.
6. **Grounded answers:** applicable citations support every tested claim, conditions/truth types survive, genuine gaps decline, and Q07/Q08 both succeed. Evidence: heard answer → fact → original source audit, including comparison caveats.
7. **Useful visuals:** subject/identity match, complete readable copy, truthful anchors, native aspect ratio and accessible controls without overlap/overflow. Evidence: every slide wide, key views at 390px, and saved Align edits.
8. **Continuity:** stay/jump routing and exact opening/proof/deeper return; clarification and callback hold until explicit action; no duplicate or simultaneous speech. Evidence: recordings, jumps, partial heard transcript and return point.
9. **Responsiveness:** visible controls and truthful listening/transcribing/checking states; no unexplained frozen state. Measure real waits, first-answer timing and failures. Record reviewer acceptance of the observed pace rather than silently inventing an SLA or treating mock speed as real.
10. **Consensual next step:** optional callback, visible consent, zero lead on decline, useful buyer recap and Done/Back; internal details remain in Studio. Evidence: Q12, lead request count, ended session, summary/share and Observability.

## Required actual evidence

Keep separate immutable iteration indexes, for example `output/nexon-real-evidence/iteration-1/` and `iteration-2/`. This plan has not created those records.

- **Run identity:** demo/version/commit, settings, timestamps, sources/permissions, provider models, three session IDs, viewport sizes and issue links; retain pre-rebuild artifacts.
- **Sound/input:** actual audible playback for the tour and Q&A/clarification/decline/return/close branches; named inspected clips and listening observations. Capture real microphone input and STT output. Muted playback, transcript-only review, synthetic Audio events and file existence do not prove audible quality.
- **Timing:** retain `voice_ended`, `stt_done`, `qa_done`, `answer_audio`; report STT/QA/TTS/total p50, p95, worst case and sample size. Separate bank/model and typed/voice turns; include slow and failed turns plus provider traces. A small test sample is not a production guarantee.
- **Screen/grounding:** real wide/phone images of welcome, intake, every slide, evidence highlight, return, clarification, callback and ending. Attach both manufacturers' proof for each positive comparison and the actual spoken verification caveat.
- **Completion/cost:** actual ended session, Studio summary, protected share and latency panel; no unconsented lead. Report observed paid build/runtime/voice cost by iteration, including failures and unavailable cost portions.

Final delivery links the real demo, both evidence indexes and the resolved/open issue record with measured cost and latency. Current result: **protocol ready; billing/source permission confirmed; real verification pending**.
