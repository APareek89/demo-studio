# Actual runtime warranty answer review — iteration 2

Reviewed 18 September 2026. Read-only review of preserved artifacts; no live provider/API calls and no production changes. Root reported hearing the answer below; the ended session transcript and speech trace confirm its text. This review did not independently listen to its acoustic delivery.

## Observed answer and verdict

- Demo: `dm_36d47b86`; profile A, protocol Q02; ended session `s_mu72zmm82u16`.
- Exact typed input: “Yes, but what is the warranty?”
- Exact heard/transcribed answer: “The Tata Nexon comes with an advertised basic warranty of 3 years or 1,00,000 km.”
- Session turn: `from_bank=false`, `answered=true`, `route=jump`. Live response cites `F027`; `gemini-3.8-flash` returned it in runtime trace line 314, and Sarvam/Priya voiced the same text in line 315.
- Result: the qualified yes correctly reached Q&A, but the answer adds an unsupported relation between the two warranty limits and omits the known terms gap. This is a recurrence of the cited-fact-to-unsupported-meaning family tracked under NX14/NX16. A citation passing the validator did not prove this connective wording.

`F027` is the advertised basic warranty headline, value and exact source quote **“3 years | 100 000 km”**, `src_706e38`, brochure page 40 warranty badge. Its conditions expressly say the badge does not detail specific terms, exclusions, transferability or which limit applies first. Neither the source nor this review establishes the complete warranty policy; “or” cannot be treated as a sourced policy relation here.

Reviewed bank Q10 already says: “Tata advertises a basic warranty of three years and one lakh kilometres. The supplied brochure doesn't explain which limit applies first or the exclusions, so please confirm the full warranty terms.” That is the prepared, approved wording to retain. The raw session is not altered or marked passing by the presence of that better bank answer.

## Why the reviewed FAQ was missed

`server/agents/faq.py::match` accepts Jaccard overlap at least 0.6, or query coverage at least 0.75 together with FAQ-question coverage at least 0.2. Q10 is “What does the standard manufacturer warranty cover in terms of years and kilometres?” Its seven remaining tokens are `cover, kilometre, manufacturer, standard, term, warranty, year`.

The actual input retains `but, warranty, yes`: only one token overlaps, so query coverage is 1/3, FAQ coverage is 1/7 and Jaccard is 1/9. It correctly fails those configured thresholds. Removing “yes, but” still leaves FAQ coverage at 1/7 (about 0.143), below 0.2; therefore a stop-word change alone does not solve the observed miss. The exact bank question matches Q10.

The current actual bank also rejects these deliberately distinct queries: “Does this have no warranty?”, “What warranty does the Brezza get?”, “Does diesel get a different warranty?”, and “Is an extended warranty included?”. These are desirable nonmatches; the review does not assert that the current matcher is generally intent-safe.

## Recommendation and bounded counterexample

**Do not change the matcher for this run.** No proposed generic threshold/token-only adjustment has established scope equivalence, and the observed failure remains visible in the real acceptance record. Continue testing the other paths without rewriting this answer's evidence.

A free in-memory counterexample used one synthetic bank question, “Is the diesel automatic?”. The current matcher returns no hit for “Yes, but is it automatic?”; adding only `yes` and `but` to STOP returns that diesel-specific answer. The customer did not establish diesel. The change would therefore expose a wrong-scope match while still failing the actual warranty case. A unique one-topic match also cannot distinguish a general warranty question from a battery-only warranty entry. These examples reject the shortcut; they do not certify the baseline matcher.

If improved paraphrase coverage is pursued later, prefer explicit human-reviewed query aliases tied to a reviewed answer and scope, with no fuzzy lowering of negation, variant or rival constraints. That is a separate approved interface/contract change, not implemented here. Required adversarial fixtures would include distinct fuel/trim names, rival names, battery versus whole-product warranty, extension/transferability questions, negation, two-topic questions and multiple plausible bank entries.

## Evidence

- `data/demos/dm_36d47b86/sessions/s_mu72zmm82u16.json`: exact input, heard transcript, typed/live provenance and timing.
- `data/demos/dm_36d47b86/trace.jsonl`, lines 314–315: live structured response citing F027 and exact Priya speech input; no provider-error flag.
- `data/demos/dm_36d47b86/understanding.json`: F027 source quote and scope.
- `output/nexon-real-evidence/iteration-2/reviewed-faq-final.json`: reviewed Q10 wording.
- `output/nexon-real-evidence/iteration-2/screenshots/Q02-warranty-answer-routing.png`: root's actual UI evidence.

No code, current FAQ, source registry, session or paid-provider state was changed by this review.


## Bounded prompt follow-up

The accepted matching recommendation remains unchanged. A separate generic QA_SYSTEM instruction now preserves explicitly unknown policy relationships instead of inferring them from headline separators, while retaining relationships and exclusions when the source does supply them. Four synthetic input-envelope cases failed before this instruction and now pass through both build-FAQ and runtime QA assembly (27/27 total). No existing answer/session was changed, and no paid call was made for this fix. Prompt compliance and the next live Q02 answer remain unproven at this checkpoint.
