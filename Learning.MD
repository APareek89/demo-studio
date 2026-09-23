# Learning.MD — Demo Studio

## 2026-09-23 — Websites-only intake could lose its completion

**Five whys:** (1) Submitting only websites while intake speech played left the customer waiting. (2) The queued reply was an empty string. (3) A truthiness check treated it as no reply. (4) The old intake assumed every submitted answer contained words. (5) The new optional field made an empty spoken-context answer valid before its waiter existed.

**WP5 correction and verification:** use a distinct `null` no-reply sentinel, preserving accepted empty completion until the prompt finishes. Client site contracts pass 16/16 and actual browser contracts 70/70, including this timing case. The guide still asks only one spoken intake question; websites do not fabricate customer context.

## 2026-09-23 — A declined answer carried unrelated tool calls

**Five whys:** (1) Automatic lookup could execute an incidental calculator or stale URL instead of the selected customer site. (2) The tools node preferred any nonempty `tool_calls`. (3) A decline now enters that node through the new fallback route. (4) The node assumed reaching it meant the model had selected `action=tools`. (5) The schema permits answer and tool-call fields together, so that ownership assumption needed an explicit check.

**WP5 correction and verification:** accept model tool calls only for `action=tools`; the decline fallback supplies exactly its deterministic allowed-site lookup. Independently reproduced the old mismatch without network or storage, then reran all 18/18 customer-site contracts after the fix. The stale-call case, allow-list, private-network, redirect, scope, cancellation and attribution checks remain bounded to fake pages and isolated storage.

## 2026-09-23 — A cancelled microphone start could outlive its visit

**Five whys:** (1) A late permission grant could reconnect a closed player's socket. (2) Capture checked its owner only after connecting. (3) `AudioContext.resume()` and microphone permission were asynchronous boundaries without immediate ownership checks. (4) Stopping capture invalidated the generation but did not prevent those later side effects. (5) Existing late-permission coverage checked track release, without checking for an orphan socket or a prompt after cancellation.

**WP8 correction:** check capture generation and closed state immediately after audio-context resume and after permission, before requesting permission or connecting. A stale grant releases its track; a stopped initialization closes its context. Device capture and the speech socket have separate lifecycles: explicit capture toggles retain the same socket, while session teardown preserves the selected mode for the saved record.

**Verification and limits:** independently reran the fake-device/transport contract: 68/68 pass, including no permission request after cancellation during resume, no orphan reconnect after a closed visit receives permission, three turns on one capture, capture toggles without reconnecting and streamed speech in text mode. Integration gates also pass: player focus/input mode 21/21, actual browser 66/66, transport/checkpoint 18/18, session input-mode API 8/8, metrics 19/19, runtime graph 130/130, summary-race 14/14, listen-window ownership 15/15, required deck 364/364, acceptance 24/24 and both smoke phases. Compilation, changed JavaScript syntax and diff checks are clean; backend runs are isolated with blocked outbound sockets. These checks do not establish physical microphone or acoustic performance.

## 2026-09-23 — Check-ins stopped the demo after every stop

**Five whys:** (1) The guide paused where the story should have continued. (2) Authoring used a question-first check-in cadence. (3) `playFrom` opened a response gate after the check-in. (4) The post-answer conversation state had no silence timer to resume the saved narration. (5) Tests treated explicit confirmation as the normal path rather than checking uninterrupted stops and a bounded reply opportunity.

**WP7 correction:** write short stop-closing statements, flag question marks during Author validation and speak existing check-ins without a wait. After a delivered answer or decline, allow a three-second reply window and then resume the saved location once; interrupted lines restart. Speech onset, typing, chips and superseding runs cancel the pending timer. On automatic return, use an existing recorded clip or resume silently. Clarifications still need replies; closing, CTAs and lead submission still need customer action. Save `auto_resumed` and the window duration for review.

**Verification and limits:** speech style 30/30, player focus 12/12, priority 11/11 and listen-window ownership 15/15 pass, alongside generation 56/56, narrative 11/11, Plan/playbook 15/15 and required deck 364/364, acceptance 24/24 and both smoke phases. Actual browser contracts pass 62/62, including unsent drafts, Stop cancellation and stale lead-save ownership. Independent review also fixed stale asynchronous lead-save completion with form/session ownership, preventing it from closing a newer form or starting its timer. Mock clocks establish state and timer behavior, not physical microphone onset or perceived pacing. The published CRETA script and original session remain unchanged.

## 2026-09-23 — Answers recited suspension component names

**Example:** an everyday answer repeated “McPherson strut” instead of the reviewed neutral wording “strut-type front suspension.” A valid citation did not make the engineering name suitable for the listener.

**Five whys:** (1) The runtime audience rule was only a prompt instruction. (2) Runtime had no shared jargon blocklist or deterministic substitution map. (3) The validator checked citations, quantities and scope, not the answer's register. (4) Composition repair received no register-specific feedback. (5) Tests covered narration language rather than customer answers.

**WP6 correction:** use the reviewed `plain_terms.py` map after row grounding and before the word cap for everyday answers. Match whole phrases, longest first; keep ordinary allowed terms. Substitute only neutral approved renderings and retain citations. A remaining blocked term rejects its row with `technical_term` and precise repair feedback. Explicit technical requests and expert audiences may retain exact cited terminology. FAQ builds share substitutions; Author adds warnings rather than a new hard rejection. Preserve substitution metadata through cached/legacy results and session records, and do not play old cached audio for changed wording.

**Verification and limits:** runtime plain language 16/16, FAQ plain language 21/21, cached API 9/9, runtime graph 130/130, repair 106/106 and browser 51/51 pass, alongside required deck 364/364, acceptance 24/24 and both smoke phases. Independent checks confirm unsupported citations/quantities reject before rewriting and repaired output retains substitution metadata. Narrow boundary cleanup avoids doubled articles or suspension nouns without changing the reviewed map. This finite map does not detect every possible engineering phrase or prove live answer quality. Grounding requirements remain unchanged; no paid customer or voice run is implied.

## 2026-09-23 — The story opened with the roof before the car's fundamentals

**Five whys:** (1) A delighter such as the sunroof led the story. (2) The writing prompts named that example and rewarded standout features early. (3) The build had no category sales knowledge specifying the basic buying sequence. (4) Ranking was untethered to that sequence and skewed toward the pictures available. (5) Tests checked grounding, but a cited claim could still appear in the wrong order.

**WP1 correction:** add Coach with a versioned category library, evidence-backed stops, three USPs and explicit source/picture gaps. Validate the first fundamental and evidence identities, and expose its order for human review inside the existing Script card. Missing pictures remain gaps rather than silently determining the narrative.

**WP2 correction:** bind Planner to the effective reviewed playbook: one proof segment per required stop, ordered by that stop, with missing coverage restored and diagnosed. Keep Coach's USPs, record fundamental flags and allocate typed word budgets. Remove the standout-first and sunroof example from the writing prompts; Author follows the settled plan with connected thoughts, varied openings and the translation ladder rather than choosing the itinerary again.

**Follow-through:** WP3 enforces typed budgets and keeps the allocation intact across split continuations. WP4 carries the fundamental flag through Slide/bundle and reserves one unseen fundamental on initial pitch planning and player fallback; refinements retain customer-priority behavior.

**Verification and limits:** WP1 Coach 20/20, Align API 18/18, UI 9/9 and required free gates passed. WP2 Plan/playbook 14/14, narrative 11/11 and speech style 27/27 passed; WP3 generation 56/56 and Plan/playbook 15/15 passed. WP4 pitch/player fundamental 12/12 and 10/10 passed, with required deck 364/364, acceptance 24/24 and both smoke phases. WP7 still owns runtime check-in changes. Mock order/coverage checks cannot establish live sales-writing quality. Published CRETA speech and its prior evaluation remain unchanged.

**Cache lesson from WP1 review:** fact text alone does not identify Coach's input. A category edit with unchanged facts initially reused the previous category's playbook. Reuse now also checks category and the consumed evidence/picture inputs; the cache contract covers category/picture changes and preservation of the prior artifact on failure.

## 2026-09-19 — Source identity is not current trim applicability

**Causes:** a city FAQ name allowed universal equipment from unrelated sources; an uploaded mention, including a negative/uncertain or precedence-excluded assertion, could appear to establish lineage. A caveat appended to an unsupported current-lineup claim merely contradicted it. At the other extreme, literal Lounge Edition fitment was lost because its transmission-only suffix became part of the trim name.

**Fix:** filter ineligible anchors; require conservative affirmative, compatible fitment before cross-source transfer; retain literal or same-revision evidence with explicit source attribution and uncertain lineup correspondence. Reject unsupported current-lineup assertions rather than adding a disclaimer. Separate the exact trailing transmission restriction for variant matching only; retain it in the assertion and spoken qualification. Regression fixtures include observed failures, inversions and valid same-record controls.

**Conversation:** exact unknowns should survive independently from unsupported reasons; one safe first-person limit can precede a single clarification without losing the wait. Required purchase terms are explicit repair feedback, not relaxed validation. Separate comparison clauses retain only applicable citations.

**Limit:** this is conservative literal screening and scoped qualification, not a general semantic proof. Actual post-fix model answers still require review.


## 2026-09-19 — A reviewed website row still mixed road wheels with spare wheels

**Cause:** the manufacturer website's flattened specification row repeated trim names and blurred ordinary versus styled road wheels. Extraction faithfully copied it, approval let it outrank the distinction in the manufacturer's PDF, and runtime repeated the approved error. Valid citations were not proof that the underlying assertion was right.

**Correction:** visually verify page 15; replace F120/F121/F122 with versioned manufacturer-backed assertions F249/F250/F251. Explicitly store road versus spare role and named trim applicability. Preserve old snapshots and failed answers, invalidate and re-review downstream approvals, publish v6 without regenerating unchanged content. A separate city-FAQ-only trim needs source-scoped interpretation; listing existence is not proof of equivalence to another source's lineup.

**Limit:** this is a reviewed source correction, not proof that automatic extraction catches every flattened table conflict. Source-aware runtime checks and a fresh live cohort still need validation.


## 2026-09-19 — The repaired draft still lost exact scope and verification limits

**Five whys:** (1) The real connected-car repair was discarded despite two useful sentences. (2) Its remaining sentence said “SX trim and above”, while the evidence atom said “SX and above”. (3) Canonical matching treated that grammatical insertion as a different scope. (4) All-or-nothing repair correctly retained the original when one sentence failed. (5) Tests covered the original phrase, not the new live paraphrase. **Fix:** tolerate only trim/variant before the literal relative qualifier; never expand that qualifier into inferred named trims.

**Unknown-detail failure:** real economy/model-year/warranty answers lost their specific missing attribute, retained unrelated facts, or introduced a future-release premise. Narrow evidence-absence normalization now preserves a safe noun phrase as a personal verification limit. Economy-only questions cannot count tank capacity as an answer; mixed requests retain it. A verification suggestion becomes a generic source-check next step, never a bypass for alleged product features. Rejected substantive limitations may receive the existing bounded repair, while limitation-only repairs cannot erase surviving supported facts. Independent review caught both of those potential regressions before live use.

**Latency failure:** the successful ADAS answer was ready at2.271s but a generic bridge occupied2.442s before delivery. Runtime-v1 question jumps now display evidence and begin the actual answer directly; exact origin, interruption ownership and explicit Continue remain. Legacy transitions are unchanged. Explicit opening requests to use local file URLs receive a prompt unsupported-source explanation without model or file access; quoted/negated examples do not intercept real questions.

**Checks:** repair106, graph130, trace36, actual DOM44 and voice-client56 pass. The original35-case cohort and5.320s answer onset stay unchanged. A fresh live cohort/probe remains necessary; no projected latency is reported as a measurement.

## 2026-09-19 — A valid safety question became a nonexistent trim; rejected drafts lost useful answers

**Five whys:** (1) The completed safety journey declined an answer supported by reviewed ADAS facts. (2) “Which variant conditions apply?” became a request for a trim named “conditions”. (3) The scope parser accepted a generic noun after “variant”. (4) The evidence filter then excluded the real higher-trim ADAS assertions. (5) The browser checked answer success, but earlier scope fixtures lacked this ordinary phrasing. Separate QA100 cases exposed empty structured answers and useful claims removed for bad citation/scope composition, with no opportunity to repair the draft.

**Fix:** exclude generic scope nouns; supply precise row-level validation feedback; allow one optional composition repair against the same approved evidence. It retains customer language, audience and profile, cannot invoke tools/CTA, shares the twelve-second deadline, and must pass the same validator. Cancellation wins; failed repair retains the supported original result. Paid warranty and separate Echo purchase conditions are explicitly preserved. Prompts distinguish the requested unknown from an unrelated known feature.

**Verification and limit:** recorded-draft repair and existing graph/trace contracts exercise the real validator with fake composition. They establish bounded behavior, not live conversational quality. The original failed safety answer and all QA100 cohorts remain unchanged; targeted paid replay is required after the final code is running.

## 2026-09-19 — Quick declines polluted response timing; long filler prolonged an ordinary question

**Five whys:** (1) A 2.585-second decline could be mistaken for useful answer latency. (2) The old roll-up mixed response kinds. (3) Delivery timestamps described playback, not answer success. (4) Legacy records lacked explicit classifications. (5) Timing checks focused on clock consistency without separate quality cohorts. The acknowledgement also used a long recorded sentence after a 500 ms grace period.

**Fix:** persist answer/clarification/decline classification; keep old records in a labelled legacy cohort; exclude declines from answer-playback percentiles. Missing, failed and cancelled timing stays visible. Use a 250 ms grace period and the shortest compatible reviewed filler; Creta's four-word Priya clip is 1.365 seconds. A ready answer still preempts it.

**Verification:** metrics15, voice-client56 and player41 free checks pass. A new actual typed ADAS probe is pending; the old failed answer remains a decline, not a latency success. Muted tests cannot establish perceived voice warmth or physical microphone quality.

## 2026-09-19 — Lookup navigation outranked answers; table absence needed explicit evidence

**Five whys:** (1) A requested engine page yielded weak generic evidence. (2) Navigation/FAQ questions repeated the search words. (3) Ranking counted headings like answer bodies and retained request verbs. (4) A first repair dropped every paragraph ending in a question and mishandled hyphenated model slugs. (5) Ranking fixtures did not include an answer paragraph followed by a question or a multiword URL model. **Fix:** rank answer-body topic overlap first, tokenize model slugs consistently, remove only question-only rows and irrelevant contact forms, preserve exact source quotes. Thirteen actual extraction/ranking regressions pass.

**Source correction:** E/EX sunroof and rear-camera absence is supported by explicit brochure matrix cells and a matching guide legend, not inferred trim ordering. Versioned F247/F248 replace held/vague assertions; v5 retains all story/media and old snapshots. Independent retrieval/positive-inversion controls pass6/6. A missing retrieved fact still never proves absence across an entire website.

## 2026-09-19 — The second real answer batch still exposed coverage and delivery defects

**Observed:** semantic review of the second100 found64 supported,23 partial,8 unhelpful,2 unsafe and3 provider failures. Scoped retrieval dropped approved inline wheel rows and universally available parking sensors; a model then incorrectly said the comparison was absent. Fresh webpage verification could be claimed using only a saved document citation. Lookup also wandered from Creta to Alcazar and general service pages on the same host. Strict negative-claim guards sometimes removed the actual refusal and left an orphan sentence.

**Fix and boundary:** project only literal approved applicability rows, retain complete direct refusals without allowing hidden positive claims, constrain lookup to the selected model/market, and keep fetched-page claims distinct from uploaded evidence. Explicit monthly-rate EMI now uses quoted monthly inputs directly. Do not revive held source assertions to improve a score. Several source-coverage gaps still require review; the uploaded wheel chart and a website assertion also disagree, with normal/spare applicability unclear. Published data is unchanged.

**Verification:** exact saved model decisions are replayed in21 focused contracts; tools have7 new monthly-rate/source-scope controls; knowledge47 and runtime127 pass. The original22 plus six supplemental grounding controls were independently rechecked. These prove repairs to known examples, not final customer answer quality; fresh focused replay remains pending. Recap controls separately retain readable completion on speech disconnect, keep stopped capture status truthful and separate explicit needs from question history.

## 2026-09-19 — A short client timeout became an invalid provider deadline

**Observed:** real Explore failed on Gemini before generation because its seven-second HTTP timeout became `X-Server-Timeout: 7`, below the service's ten-second minimum. Claude lacked credit and the remaining Runware attempt timed out. Fake adapter contracts had proved budget allocation without exercising the SDK's wire behavior.

**Fix:** preserve the short local attempt timeout and overall twelve-second graph deadline, but explicitly set the Gemini server header to at least ten seconds. Disable hidden SDK retries for a one-attempt runtime call. Do not extend the customer's total wait to satisfy a provider header.

**Verification:** installed-SDK/fake-HTTP contracts cover 0.75/7/12-second local budgets, accepted server headers and exactly one HTTP request on 503; eight schema/wire checks pass. A real Gemini probe with local7/server10 succeeded in1.912 seconds. That tiny probe proves transport compatibility, not full Explore speed or answer quality. Full replay remains separate.

## 2026-09-19 — Explore inserted another opening and risked draft mixing

**Observed:** after an eleven-second overview, the first actual Explore returned no personalized segments and played a long decision frame plus two optional batches before the route. Integration review also found copied relative audio paths and string check-ins mismatched the browser bundle shape, and live planning still read mutable draft files.

**Five whys (delivery):** (1) a second opening delayed the slides; (2) the browser narrated legacy fields; (3) prompt/schema still requested2–3 optional batches; (4) personalized segments were optional with no reviewed replacement fallback; (5) tests proved grounding but did not exercise overview-to-slide composition. **Fix:** live-mode prompt/schema and player bypass the pre-roll; validated model selections or marked exact reviewed-route fallbacks replace slide speech. Only the first slide may carry a short verbatim customer preface. Never clip an arbitrary prefix from a longer reply.

**Five whys (published boundary):** (1) a live route could contain unpublished wording; (2) pitch loaded draft understanding/plan/script and approvals; (3) its build-era input assembly was reused for live Explore; (4) fact snapshot checks did not cover speech/deck versions; (5) tests never edited Align while a built player remained open. **Fix:** live pitch exclusively uses the published bundle and verifies session snapshot plus demo version; the checkpoint retains the first version. Changed publication returns an honest refresh-required fallback without a provider-failure claim. No historical bundle archive is added.

**Media/wait boundary:** copied reviewed audio paths are normalized to `/media/<demo>/...`; existing absolute paths survive and model-supplied media is ignored. Check-ins are exposed as `{text,audio}`, preserving the existing yes-continue/no-deeper wait. This was caught before paid revalidation.

**Regression:** `evals/pitch_delivery_contract.py`16/16 covers actual pitch and runtime checkpoint behavior, including draft edits/false approvals and a new publication sharing the same evidence snapshot. Existing pitch grounding47 and speech27 remain. These free contracts do not certify live personalization quality, acoustic delivery or response latency; browser/paid acceptance is separate.

## 2026-09-19 — A yes to more detail continued the demo

**Observed:** curated check-ins asked “Would you like a closer look?” while the existing player's affirmative answer advances; a customer agreeing to more detail would get the opposite action.

**Five whys:** (1) yes followed Continue, not deeper; (2) wording expressed an opt-in request for detail; (3) author instructions treated a check-in as any useful choice; (4) schema described a short question without its response mapping; (5) authoring contracts checked citation safety and waiting but not the meaning of affirmative/negative responses.

**Fix:** keep the existing player and question cadence. Author/shared flow/schema instructions require confirmation of enough detail or readiness: yes continues, no opens detail. A bounded English lexical warning flags common opt-in-detail/open-choice phrasing without removing text/audio or marking factual narration unverified. Intake remains a separate open question. The actual three proposed prompt edits are a review patch, not automatic data mutation.

**Regression:** `evals/speech_style_contract.py` covers the three observed questions plus opt-in variants, valid confirmations/empty fields, unchanged speech/audio, and intake independence (27 cases overall). The heuristic is not semantic proof or multilingual detection; human review and actual conversations remain required. No scorecard criteria or saved score were changed to improve the observed 11/20.
> AGENT: add an entry whenever the basic flow changes, the user reports a bug or gives
> corrective feedback, or something took real time to figure out. CHECK THIS FILE FIRST
> before debugging — the answer may already be here. Plain language; first use of any
> technical term gets a one-line bracket explanation.

<!-- Newest first. -->


## 2026-09-19 — Mandatory section questions conflicted with conversational pacing

**Why1:** The curated Creta script's three relevant check-ins still produced warnings for every other proof/features section. **Why2:** the validator required a confirmation question after each section. **Why3:** author prompts, shared proof/flow guidance, scorecard and schema field description repeated that older cadence. **Why4:** conversational quality was equated with question frequency rather than useful decision points. **Why5:** tests lacked a deliberately sparse route.
**Fix:** remove the mandatory per-section question check and align the prompts/field description. Two or three useful check-ins across a typical route is an editorial target, not a numeric requirement. Empty check-ins remain valid; any actual question must still use the explicit wait field, and uncited claims in that field are still rejected. Two real-function regressions take speech-style coverage to24; the real script is curated through the existing review API, without an additional model rewrite for this change.


## 2026-09-19 — Re-entering Align lost visible work progress

**Why1:** The in-app Align screen could reopen during a long stage with an empty progress overlay. **Why2:** mount and SSE hello did not restore retained stage messages. **Why3:** hello's current snapshot was ignored. **Why4:** polling tested whether any overlay node existed, but the hidden overlay is always mounted. **Why5:** earlier SSE tests covered replay suppression, not the actual screen's snapshot and visibility recovery.
**Fix:** restore current running-stage progress in time order, consume hello snapshots and synchronize overlay visibility after reload; visible-tab polling and visibility return refresh state. `evals/align_progress_contract.mjs`9/9 exercises the actual Align module and actual SSE client with a DOM-shaped host: initial progress, done snapshot, reconnect, historical-completion rejection, fallback stage message, polling, live navigation and cleanup. These are local state/DOM contracts; the root's actual in-app reload check is separate visual evidence.


## 2026-09-19 — A grounded draft still sounded technical and renamed the locked guide

**Why1:** The real Creta draft led with millimetres, grille terminology and four cylinders, while presenting Karan over locked Priya audio. **Why2:** generic plain-language instructions did not cover these observed everyday register failures, and the planner never received the actual selected speaker. **Why3:** the validator covered familiar abbreviations but not ordinary-looking technical component labels. **Why4:** a stored persona could survive revision despite a different locked voice. **Why5:** fixture coverage proved speech identity but not its human-facing persona brief.
**Fix:** Add grounded positive/negative examples, forbid unsupported felt benefits and engine/gearbox generalization in the author/planner brief, and warn on dimensions/component jargon in everyday main narration, check-ins, overview and closing. These editorial warnings never mark a sourced line unverified or censor technical/deeper answers. The planner receives actual voice configuration and deterministically keeps a locked speaker's display identity with a neutral description, including preserved revisions. Nine new actual-function cases bring speech-style contracts to22. This is authoring protection, not proof the next real script is excellent; the actual draft still needs explicit revision and human review.

## 2026-09-19 — CTA labels promised destinations the planner had never been given

**Why1:** Download Brochure, Locate Dealer and Book a Test Drive all pointed at the highlights URL. **Why2:** the planner received the product URL but not the action links already retained by source extraction. **Why3:** action labels were validated structurally, not against their destination purpose. **Why4:** absent links were treated as an opportunity to reuse the homepage. **Why5:** there was no negative fixture for a plausible but misleading target.
**Fix:** Feed retained same-site/model/market action-link candidates to the planner; reject mismatched action destinations and use a clearly labelled local contact request when a link is missing. No destination is fetched by planning, and retained-link discovery is not a live-availability promise. Actual planner tests cover valid targets, rival/foreign-market/host rejection and missing-link fallback. A separate player review found URLs were ignored by its existing action handler; the player owner's explicit user-gesture link correction is tracked separately and must be tested before claiming download/navigation works.


## 2026-09-19 — Editing a fact must not change an old citation's meaning

**Why1:** The review API updated a fact object in place while preserving its F/C ID. **Why2:** Identity was treated as a row key rather than the meaning of an assertion and its applicability. **Why3:** immutable publication alone did not protect later draft references and conflict decisions. **Why4:** correcting trim/year/conditions could silently rebind an old citation. **Why5:** edit tests checked the corrected value, not the old assertion's continued identity.
**Fix:** Validate under the demo lock, allocate a fresh ID for material edits, archive the prior registry, record override ancestry and supersede historical conflicts without retargeting them. Old IDs cease to resolve in the current draft, while old published snapshots remain unchanged. No-op edits do not write or invalidate. Align exposes structured applicability and validates dates. `fact_identity_contract.py`17/17 plus knowledge Re-Read lineage tests cover the actual API, immutable snapshots, retired-ID rejection and atomic invalid-input handling.

## 2026-09-19 — A declared provider preference had not reached the build adapter

**Why1:** Real text builds still attempted Claude before Gemini. **Why2:** only runtime reasoning had a configured provider order. **Why3:** the older build adapter embedded its fallback chain. **Why4:** build and runtime shared a provider module name while using different entry contracts. **Why5:** tests preserved the old default instead of asserting the approved Gemini-first build behavior.
**Fix:** `BUILD_PROVIDERS` defaults to Gemini → Claude → Runware for text-only structured builds, validates configured names and appears in health and extraction-cache identity. Explicit no-fallback calls and original media preserve their contracts; the plain Align greeting remains an explicitly documented legacy path. Seven new provider cases raise the suite to55; deck315 exercises them without network.

## 2026-09-19 — Valid application schemas were rejected by Gemini's legacy schema converter

**Why1:** Real Read failed before generation on `additionalProperties`. **Why2:** dictionary-valued scope/delivery fields are valid JSON Schema but were sent through the SDK's older `response_schema` converter. **Why3:** the converter has a narrower schema vocabulary. **Why4:** mocked model output never exercised real SDK serialization. **Why5:** schema coverage ended at application validation.
**Fix:** use `response_json_schema` with the Pydantic model's complete JSON Schema and retain typed output validation. Four SDK-wire regression cases pass; a small real FactsOut probe confirms the corrected adapter. This does not certify the full Creta source read or the factual quality of model extraction.

## 2026-09-19 — Old provider-outage FAQ answers needed a supported, reviewable repair

**Why1:** TVS iQube's20 FAQ answers were provider-outage declines, including questions with saved evidence. **Why2:** failed authored answers had been retained as a bank. **Why3:** nine questions could now be corrected deterministically, but remaining temporal/unsupported questions still lacked evidence. **Why4:** the bank's legacy fact hash omitted the newer competition envelope, obscuring safe reuse. **Why5:** neither a new full Build nor silent hash replacement would establish what was actually preserved.
**Fix:** snapshot all134 files, prove the exact legacy hash against the unchanged71 facts, record both hashes, then apply nine source-limited answers through the review API. Eleven declines remain. Live API38/38 and isolated reuse33/33 pass; no provider call or full Build. Existing legacy QA reads edited bank text before approval, so record that limitation rather than claiming card approval is a publication lock. Evidence and rollback snapshot stay in `output/creta-runtime-2026-09-19/iqube-repair/`.

## 2026-09-19 — Provider readiness must be observed, not inferred from keys

Why could a real build begin without a working runtime? Configuration presence was the only entry check. Why was that insufficient? Speech and reasoning use separate capabilities/accounts and may fail independently. Why did a previous success not suffice? It can expire, be a mock result, or belong to a different speaker. Why was this invisible in tests? The route fixture asserted key configuration only. Why was the real build not protected? Observed capability results were not part of its entry contract. The Read/Build gate now checks a fresh real reasoning result and, for Sarvam Build, the selected speech voice; it never probes implicitly. Sources/Rehearse show results, a credit-using check button, and an explicit per-demo in-tab override, recorded on use. `evals/readiness_contract.py` (10 checks) and `evals/readiness_ui_contract.mjs` (5 checks) would have caught the missing boundary.

**Mock incident accounting addendum:** retained fixture `dm_498d4665` confirms a successful Gemini mascot image request before the guard fix: 61 input/1,489 output tokens, $0.02 local estimated image cost (₹1.68 at assumed FX). This is not a provider invoice or a bound on deleted intermediate stores. Preserve `output/creta-runtime-2026-09-19/mock-guard-audit/dm_498d4665-*` alongside the earlier warnings.


## 2026-09-19 — Mock mode must guard optional media at its provider boundary

**Why1:** Intermediate “free” integration runs emitted Gemini SDK image warnings after an import was repaired. **Why2:** The previously broken optional-media import had hidden a path without a MOCK_LLM early return. **Why3:** Text/speech mocks did not automatically protect image generation. **Why4:** A successful mock pipeline was assumed to imply no external side effect. **Why5:** Optional provider entry points lacked an explicit negative regression and process-level egress evidence.
**Fix:** `gemini.generate_image` and `media.generate_mascot` return before provider initialization in mock mode. `build_hardening_contract.py` patches Gemini client construction to raise and asserts it is never reached. Final gates also block socket creation/connect and record zero attempts.
**Accounting:** Intermediate warning logs are preserved in `output/creta-runtime-2026-09-19/mock-guard-audit/`. Some disposable stores had already been deleted before discovery; their spend is uncertain, not zero. Retain traces before cleanup when provider activity is in doubt. A repaired import is a behavior change and must recheck the actual downstream side effect.

## 2026-09-19 — Ready revisions skipped the human checkpoint

**Why1:** Revising a ready demo could immediately generate speech and bundle it. **Why2:** Graph routing treated previous Ready/rebuild flags as authorization to bypass Align. **Why3:** Approval fields could remain true after the reviewed content changed. **Why4:** stage invalidation and human approval invalidation were separate. **Why5:** Existing tests directly waited for Ready after a revision and reinforced the shortcut.
**Fix:** Stage output comparison clears affected approvals; Ready revisions return to the real Align interrupt. Only a fresh explicit approved Build proceeds. Visual-only maintenance does not invalidate facts. `build_hardening_contract.py` exercises the actual revise→interrupt→approve→build graph; deck/smoke fixtures preserve earlier assertions while following that sequence.

## 2026-09-19 — A reconnect replayed old navigation events and lost warnings

**Why1:** Reopening Align could replay an earlier build-complete redirect. **Why2:** every new EventSource began at sequence zero. **Why3:** hello carried a number but did not establish a client/server baseline. **Why4:** the server ignored reconnect IDs and kept event state only in memory. **Why5:** progress messages were ephemeral and stage completion overwrote their text.
**Fix:** Durable bounded event IDs, fresh snapshot hello, Last-Event-ID replay and client deduplication separate fresh navigation from reconnect. Stage records retain recent progress and warnings. Six build/SSE checks plus four real-client fake-transport cases cover these boundaries.

## 2026-09-19 — Style changes and repeated reviews need semantic cache identities

**Why1:** Identical words could reuse audio with outdated delivery/persona, while harmless audio timestamps could repeat scoring. **Why2:** speech keys omitted delivery/profile and review inputs included recording bookkeeping. **Why3:** one notion of “changed” was used for content, media and validation. **Why4:** separate overview/translation paths inherited audio or missed the translated text. **Why5:** there were no cross-path cache and metadata contracts.
**Fix:** Speech keys include normalized delivery/persona; the voice-stage key includes settings/languages and spoken inputs. Rehearsal hashes reviewed content/evidence/FAQ/prompts, excluding audio/timelines and image-only maintenance. Optional overview translation clears source audio, preserves citations and holds changed numeric units. Regression coverage: speech13 and build16, with legacy voice27 retained.

## 2026-09-19 — A factual citation is not permission to invent a customer benefit

**Why1:** A gearbox type can be rewritten into an unsupported promise such as imperceptible shifts. **Why2:** benefit-first writing was conflated with inferring a desirable outcome from a feature. **Why3:** familiar automotive jargon also made the narration feel technical and generic. **Why4:** personalization appended repeated proof rather than replacing the selected narration. **Why5:** editorial and runtime validation needed the same clear evidence boundary.
**Fix:** Lead with sourced standout features and supported relevance; otherwise present a choice or fit-check. Everyday scripts move complete technical quantities to deeper answers. Runtime personalization composes reviewed factual sentences with an exact customer-need preface and replaces slide speech; it cannot invent a new factual paraphrase. Delivery markers remain separate metadata, with supported pace/punctuation only. Free contracts prove these boundaries, not whether a live model will produce a compelling human-level pitch; that still needs real customer review.

## 2026-09-19 — A playable build did not satisfy the live-experience goal

**Feedback:** Anand said yesterday's demo did not achieve the requested human-level runtime experience.
**Why 1:** Listening, contextual conversation, response waits and natural interruptions did not meet his product bar.
**Why 2:** The work established a built bundle, visual polish, typed paths and safety regressions, while native microphone and acoustic quality remained unverified.
**Why 3:** Existing constraints excluded spoken barge-in/streaming/tools even though the intended customer experience increasingly required them.
**Why 4:** Technical completion and a small muted scripted run were treated as stronger experience evidence than they warranted.
**Why 5:** The acceptance boundary did not require an observed audible, multi-turn customer journey with measurable quality/latency gates before claiming the broader goal complete.
**Correction:** Separate “playable” from “excellent live experience.” The new proposed runtime plan explicitly includes continuous voice, relevant evidence, bounded tools and personalized delivery. It is not implemented yet.
**Prevention:** `docs/plan-runtime-experience-2026-09-19.md` defines three complete buyer journeys, real interruption/acoustic checks, a balanced question set, useful-answer metrics and zero-critical-error gates. Muted checks cannot sign off voice quality. Record failures, fix them and replay the scenario before the full journey; do not use another build or UI pass as a substitute.

## 2026-09-19 — Atelier accent needed a darker small-text variant

**Why 1:** The first Atelier Insights tag used 10px blue text with only 4.16:1 contrast on sky.
**Why 2:** The brand accent was reused as a text colour without evaluating its actual background.
**Why 3:** A colour that works for large accents and controls does not automatically meet small-text contrast needs.
**Why 4:** The existing functional browser contracts validate actions and geometry, not text luminance.
**Why 5:** A design-token change requires a targeted contrast check in addition to screenshots.
**Fix:** Darkened the small Insights tag to `#0669a6`; metadata and slide indices use `--muted:#5e7180`. Focus outlines use opaque blue. No behaviour or layout change.
**Prevention:** The bounded declaration/contrast audit in `output/atelier-ui/final/css-audit.json` verifies tag 5.221:1, metadata 5.061:1, slide index 4.789:1 and light-surface focus 4.678:1. Repeat these foreground/background checks when changing palette tokens; this does not claim a complete accessibility audit.

## 2026-09-18 — New library navigation and thumbnail reuse needed regression coverage

**Why 1:** The legacy create handler navigated to a nonexistent `/visual` stage; the first card redesign also omitted View's fullscreen request and repeatedly loaded bundles as search text changed.
**Why 2:** Creation had retained an old stage name, while the new card component recreated work previously done by a simpler list.
**Why 3:** Navigation and network behavior were coupled to each card render rather than explicitly preserved at the UI boundary.
**Why 4:** A first cache correction retained failed lookups as an empty result, so transient errors could not recover on later navigation.
**Why 5:** The existing player contract did not exercise library actions or preview request lifetimes.
**Fix:** Create opens the existing Sources stage; View retains its fullscreen request; Home and My demos share a per-demo/version/update preview promise. Rejected requests delete their key so a later visit can retry. No new endpoint or auto-retry loop.
**Prevention:** `evals/ui_contract.html` exercises the actual modules and modal DOM with fake APIs:5/5 in the browser. The real isolated HTTP create also landed in Sources. This is navigation/cache coverage, not backend or fullscreen-browser permission proof.

## 2026-09-18 — Desktop shell rules hid mobile content during the redesign

**Why 1:** Mobile Align left review cards inaccessible, and an older header rule hid the new brand.
**Why 2:** The desktop split pane kept its nested height/overflow rules on a narrow screen; the legacy `.top > .brand` selector was more specific than the new generic brand rules.
**Why 3:** The new shared skin intentionally layered over existing CSS to preserve slide geometry, so old responsive rules still participated in the cascade.
**Why 4:** Desktop screenshots could not reveal these breakpoint-specific interactions.
**Why 5:** The player geometry suite covered slides, not the workspace rail, review panels or logo.
**Fix:** Mobile Align uses a single scroll column with review cards followed by the assistant. The shared shell explicitly keeps its brand visible; checkbox/radio sizing is separated from text fields.
**Prevention:** Actual390px review checks all six cards, source upload roles, slide editor controls, assistant/build controls, Sessions/share and the shared header. Whole-page widths remain390; the wide session table has contained horizontal scrolling. See `output/professional-ui/studio-*-mobile.png` and `home-mobile.png`. No core action or approval gate changed.

## 2026-09-18 — NX42 concurrency: a later duplicate overwrote a successful summary
**Why 1:** Runware summary trace460 succeeded but duplicate failures461/462 replaced it with ERROR.
**Why 2:** Each ended save started another worker before a result existed.
**Why 3:** Workers wrote their old whole-session snapshot without checking the current saved input.
**Why 4:** Reuse compared only transcript length, ignoring changed words, context, consent and timing.
**Why 5:** Previous tests covered one worker's accounting, not held concurrent completions or resumed input.
**Action taken:** A canonical full-input revision excludes only server summary/save timestamp. Session save/result attachment share a small per-session lock; identical in-flight work coalesces. Providers run outside locks. Completion reloads the latest record and attaches only to unchanged ended input with no current result. Equal-length corrected/resumed input survives, current success cannot be replaced by old error, and client saves cannot restore an old server summary. Actual-thread/ASGI regressions6/14→14/14; accounting8/8. Coordination is per-process for the current one-worker local server; lock entries last for its lifetime. No persisted schema/service/distributed guarantee or automatic paid retry is added. Existing failures/costs remain unchanged.


## 2026-09-18 — NX42: summary reasoning consumed the output budget
**Why 1:** Both final-summary requests returned truncated Gemini JSON at1185 billed output tokens.
**Why 2:** Default hidden reasoning shared the1200-token envelope with the summary.
**Why 3:** The response-control correction had reached QA/pitch but not summary.
**Why 4:** The summary's short visible output had been mistaken for its total model output cost.
**Why 5:** No caller-envelope test required LOW alongside the complete record and unchanged schema.
**Action taken:** Summary now requests LOW through the existing guarded adapter, keeping1200 tokens and the full payload. Fake-provider10/11→11/11 checks this exact envelope. The original simultaneous requests, successful Runware fallback and later error overwrite remain evidence; generation/write concurrency needs its separate regression, and final actual completion remains pending.


## 2026-09-18 — NX40: the guide selected its own proposed CTA
**Why 1:** L4 asked how to assess traffic driving, but the model emitted a test-drive CTA.
**Why 2:** The player sent that field straight to the selection flow.
**Why 3:** Model interpretation was treated as explicit customer intent.
**Why 4:** Selection narration also promised a handoff before any consented contact form was submitted.
**Why 5:** Earlier tests covered callback refusal and explicit choices, not unsolicited/negated model actions.
**Action taken:** A model CTA becomes only an optional configured choice in the answer-confirmation wait. Exact customer selection or a CTA button is required. Unknown/stale IDs do nothing; embedded/negated label mentions remain questions. The selected-action narration offers optional details without claiming transmission. Actual free browser33/36→36/36 proves the negative and positive paths; the original L4 recap remains preserved. Zero leads were submitted. Final actual L4 recovery remains pending.

## 2026-09-18 — NX41: a cited warranty answer contradicted its explicit unknown
**Why 1:** Actual L5 spoke '3 years or100000km' while also saying the relationship was not supplied.
**Why 2:** Valid citation and quantity checks did not validate the relation between those quantities.
**Why 3:** The prompt prohibited the inference, but model prose still introduced it.
**Why 4:** The previous narrow relation guard applied only to optional pitch speech.
**Why 5:** QA tests lacked this actual cited-but-contradictory answer before synthesis.
**Action taken:** For cited policy/contractual facts explicitly marking the limit relationship unknown, reject an affirmative English time-or-distance/whichever-first relation before speech. Clear citations, proposed visual and CTA; use the existing decline/callback, without recording a provider outage. Honest attached uncertainty and explicitly documented policy relations remain usable.12 actual-QA fake-provider cases: initial3/10; independent unrelated-prefix bypass11/12; final12/12. Bad prose never reaches fake speech. This is a bounded English conflict guard, not general entailment; other unsupported paraphrases still require review. No policy is invented and no new product fallback is added.


## 2026-09-18 — NX39: QA could not resolve the demo's selected comparison example
**Symptom:** Actual L2 asks what differs from the selected Venue variant; trace439 asks which variant despite the reviewed plan defining regular HX10 turbo petrol seven-speed DCT.
**Why 1:** QA could not identify which of the source registry's many Venue trims the reference meant.
**Why 2:** The intake and recent transcript named Venue but did not specify HX10.
**Why 3:** The explicit comparison-example mapping lived in plan.notes and never reached QA.
**Why 4:** QA used the plan's persona and CTAs but omitted its reviewed contextual notes.
**Why 5:** Input tests checked complete facts and customer history, not the distinction between demo examples and buyer selections.
**Action taken:** Pass the existing notes in a separate comparison-context block, gated by competition on and script approval. The prompt uses a unique named demo configuration only for an explicit selected/chosen-demo reference; actual customer variants take precedence. Notes are neither facts nor inferred preferences. Missing or ambiguous configurations retain clarification when material. Seven real-call fake-provider checks make the generation suite39/44 before and44/44 after; all original fact conditions and provenance remain supplied. These checks prove the input contract, not model compliance. The original trace439 clarification and trace441 answer after the explicit HX10 reply are not rewritten; one live confirmation remains separate. No provider, schema or Build change.

## 2026-09-18 — NX36 follow-up: personalization exhausted the same response budget
**Symptom:** Final-sample B pitch trace432 returned incomplete JSON at2986 output tokens; Claude credit failure and Runware timeout followed, so the player used the reviewed route.
**Why 1:** The structured pitch response exhausted its3000-token envelope.
**Why 2:** Hidden reasoning shares that envelope with the required plan.
**Why 3:** Only QA had been changed to explicit LOW thinking.
**Why 4:** Pitch was treated as independent from the observed response-budget problem.
**Why 5:** The pitch caller had no regression requiring the bounded reasoning setting.
**Action taken:** Pitch now passes LOW explicitly through the existing runtime option. Full reviewed proof, schema,3000-token allowance, model/order/timeouts and deterministic grounding stay unchanged. Actual-call fake-provider contract fails46/47 before and passes47/47 after; provider48/48 preserves unknown-model and default-caller behavior. The failed live attempt remains preserved, and one subsequent runtime confirmation must establish recovery. No Build or source change.


## 2026-09-18 — NX38: deeper return retained the preceding answer's citations
**Symptom:** After a cabin answer, the resumed CNG boot caption showed F020/F021 instead of its own F014.
**Why 1:** The citation label was left over from Q&A.
**Why 2:** Main lines assigned their sources but deeper lines did not.
**Why 3:** These playback paths had separate loops with incomplete state updates.
**Why 4:** Return tests checked the caption and position, not their accompanying citations.
**Why 5:** Citation ownership across claim/question transitions was not asserted end-to-end.
**Action taken:** Every deeper line assigns its own sources, including resumed lines; question/check-in/transition states clear stale citations. Run ownership protects against late canceled fillers. The actual real-demo failure is preserved in `completion-audit/deeper-interrupt-return-line.txt`. Actual browser harness32/33→33/33 checks F014→QA F020/F021→returnedF014→D2F024→empty prompt. No new audio or Build.

## 2026-09-18 — NX34 continuation: cited speech still added an unproved location
**Symptom:** The final A pitch added “in the rear cabin” to the ISOFIX equipment fact without explicit source support.
**Why 1:** Valid fact IDs were mistaken for evidence of every word in a paraphrase.
**Why 2:** The model could freely elaborate cited proof.
**Why 3:** Lexical omission guards covered prior failures, not arbitrary new properties.
**Why 4:** The runtime did not reuse the wording already reviewed at Align.
**Why 5:** Factual generation and personal relevance were coupled in each custom batch.
**Action taken:** Keep model-led selection, order and buyer framing, but permit cited custom speech and bridges only as exact current approved script proof with the complete citation set. Unverified, rejected, unapproved and unsuitable proof is unavailable.46 adversarial checks cover new location/property additions and supported reuse (initial baseline24/38; final46/46 after uncited-cue and repetition regressions). This trusts reviewed wording and current fact identity; it does not solve NX20 or human review errors.

## 2026-09-18 — NX36: live reasoning exhausted a short-answer JSON budget
**Symptom:** Even a 3000-token envelope could end in truncated JSON, followed by the whole provider fallback chain; one measured answer took46.745s.
**Why 1:** Thinking and answer JSON share the output limit.
**Why 2:** The model used its default thinking level for a short, closed-evidence answer.
**Why 3:** More output room alone did not bound hidden reasoning.
**Why 4:** Runtime QA had no explicit thinking control distinct from other model work.
**Why 5:** Provider-envelope tests checked token capacity but not the reasoning setting.
**Action taken:** Live QA requests LOW thinking on the documented exact Gemini3.8Flash model. Full evidence, schema,3000-token envelope, model, order and timeouts remain; other calls and unknown overrides retain defaults. Provider48/48 covers actual SDK options, retries, thought-token accounting and invalid-citation rejection. QA prompt also confines direct questions to their requested product and comparisons to a shared dimension. Real speed and answer quality require the predeclared sample, not these fake transport checks.

## 2026-09-18 — NX37: a slide title invented a buyer priority
**Symptom:** A buyer comparing automatics received an invented “main” safety priority.
**Why 1:** `profile.focus` contained safety although the raw answer did not.
**Why 2:** The parser matched “with” in the safety slide's title.
**Why 3:** Any title word longer than three characters counted as interest evidence.
**Why 4:** Marketing titles had been treated as topic vocabulary.
**Why 5:** The model received computed focus alongside raw customer statements without a clear distinction.
**Action taken:** Whole canonical topic/chip phrases and specific topic aliases replace title-word matching (actual function4/12→12/12). Pitch separates computed routing hints from raw buyer language; hints never establish a stated/ranked preference. Preserve the actual failed B transcript. Negation and arbitrary semantic intent still require conversational judgment; this parser supplies route hints, not inferred preference truth.

## 2026-09-18 — NX35: background summary cost was absent
**Symptom:** Eight real summaries existed, but the demo's usage and trace files contained none of their provider work.
**Why 1:** Accounting silently returns when no demo context exists.
**Why 2:** The summary runs in a plain background thread, outside the request context.
**Why 3:** That thread did not establish its own demo and stage.
**Why 4:** Existing summary tests checked content, not an actual worker's attribution.
**Why 5:** Cost reconciliation treated saved summaries and provider records as separate concerns.
**Action taken:** Set demo/runtime ContextVars around summary generation and reset both on success or failure. A real-thread, temporary-store regression demonstrates missing records before (4/8) and correct isolated usage, costs and failure traces after (8/8). No network or provider calls. Existing unrecorded costs remain unknown; this fix does not reconstruct history.

### 2026-09-18 — Align could not correct competitor citations or spoken questions

**Symptom:** Real Nexon source review found competitor facts outside the review card and edit/reject lookup. Incorrect truth labels and blended citations could not be repaired directly; intake questions, check-ins and segment outcomes also remained outside script editing.
**Why 1:** The fact card and handlers traversed only the product `facts` list, while competitors were stored separately.
**Why 2:** The original correction API accepted value/claim/conditions but not the existing truth/source fields.
**Why 3:** Chat actions duplicated the product-only lookup instead of sharing validated review operations.
**Why 4:** Script editing identified spoken lines only; questions and segment metadata are sibling fields with separate audio.
**Why 5:** Free review checks exercised line edits and product facts, without testing the full set of source-backed material a reviewer must correct before approving a build.
**Action taken:** Review cards show both registries with explicit ownership, while storage remains separate. API and chat corrections share schema/source validation; foreign, blended and cross-role source references reject before saving. Competitor facts remain bound to their source group. Review can change one intake, check-ins and title/outcome metadata, with grounding checks, stale question audio cleared and downstream approvals invalidated. The full smoke gate also caught unescaped citation-example braces in the expanded Align prompt; a focused prompt-format regression now covers it.
**Preventive action:** `evals/align_review_contract.py` exercises successful and rejected edits through real routes, source/approval isolation, chat parity, no partial writes, no second intake and zero provider/network calls. Review truth and variant applicability against the source: valid ids and field types do not prove that a quoted source supports every word of an edited claim.

### 2026-09-18 — Claude's grammar repair lost the selected model and timeout

**Symptom:** Code inspection for text tiers found that a constrained-schema error could silently retry with the general model and default timeout instead of the caller's selected model/budget.
**Why 1:** The grammar-error branch called `_soft_structured` without forwarding `model`, `timeout`, `effort` or `max_retries`.
**Why 2:** The recovery path was written before callers selected separate runtime/plan/lite models.
**Why 3:** Existing mock gates never enter Anthropic's schema-rejection branch.
**Why 4:** Provider repair was treated as a new request rather than the continuation of the same configured operation.
**Why 5:** The provider contract lacked a regression for preserving call options across recovery.
**Action taken:** Forward all four options into the existing soft-JSON recovery. The fake Anthropic grammar-rejection regression in `evals/provider_contract.py` proves that the selected model, timeout, effort and retry count survive the recovery path.
**Preventive action:** Every repair/fallback test asserts model selection, retry budget and history as well as output validity; free fakes must exercise provider error branches.

### 2026-09-05 — QA playback needed a single quiet-mode control

**Symptom:** End-to-end browser QA could play recorded narration, browser speech or the promotional film aloud, disturbing someone using the same machine even when the test conversation itself used typed chat.
**Why 1:** The player had separate audio objects for narration, browser speech and film playback, with no shared mute state.
**Why 2:** The film path explicitly unmuted its video element, so muting one narration object would not make the session quiet.
**Deepest why type:** `design`
**Action taken:** Added one accessible top-bar mute control backed by shared player state. `?mute=1` starts a QA session muted; the control updates current and future recorded narration, browser speech and film audio without pausing the visual flow. Added deterministic coverage and verified the control plus a typed intake in the real browser.
**Preventive action:** Every new audible runtime path must subscribe to the player's shared mute state and be covered by the visual-sync regression.

### 2026-09-05 — Image tags were not strong enough to prove script-to-screen alignment

**Symptom:** The existing post-author picture matcher could explain why “gearbox” mapped to a gear image, but its final Haiku pass only saw Gemini's earlier text tags, not the uploaded pixels. Multi-feature lines could therefore look related while still leaving one spoken feature invisible. Runtime fact cards also repeated long source/caveat prose and could overlap the topic badge.
**Why 1:** Source understanding and final visual proof were treated as the same decision even though the script did not exist during initial image tagging.
**Why 2:** The assignment schema recorded only a visual id and reason, not the spoken features, visible features, missing features or coverage level.
**Why 3:** The player card was designed as a miniature citation panel instead of a glanceable visual aid.
**Deepest why type:** `design`
**Action taken:** Upgraded the existing post-author checkpoint: Gemini 3.6 Flash now inspects the real uploaded images in batches of twelve against every stable script line, returns a detailed audit for every image and line, and is accepted only when both sets are complete and internally consistent. Deterministic code binds an image only on `full` coverage; partial, missing and non-visual decisions all fall back to the neutral 3D/card stage, even when an older draft carried a picture. The audit is saved in `visual-audit.json` and shown in Align. Runtime cards now contain at most three short keyword/value rows, with no source locator or caveat prose, and the topic badge hides while a card is visible. Live CRETA audit: 13 images, 60 lines, 29 corrected assignments, 18 uncovered feature lines.
**Preventive action:** A ready demo must expose per-image visible features and per-line full/partial/missing coverage after the script exists. Tag-only matching is a fallback, never the success criterion.

### 2026-09-05 — A supplied 3D asset still needs the product-truth approval gate

**Symptom:** Users with an existing GLB had to rebuild it through Runware even though the player already consumes GLB files.
**Why 1:** Demo Visual modelled only image/video inputs, not the reusable asset contract at the gate boundary.
**Deepest why type:** `design`
**Action taken:** Added direct `.glb` upload with a 150 MB limit and binary glTF v2 header/chunk validation. It creates a zero-cost versioned review attempt, opens in the same rotatable viewer, and only enters the demo bundle/My Assets after explicit approval.
**Preventive action:** Bypassing generation must never bypass structural validation, review, approval, version history or observability.

### 2026-09-05 — A good 3D asset still fails when the spoken claim and stage use different evidence

**Symptom:** The 3D vehicle remained dominant while Ravi discussed hidden safety/cabin features, exact images were relegated to thumbnails, and one personalised safety sentence combined airbags, brakes and hill assist while showing only the airbag frame. A transition about the demo roadmap also inherited stale safety/warranty evidence and citations.
**Why 1:** Playback treated the approved 3D asset as persistent decoration instead of making a per-line decision about what could actually prove the spoken words.
**Why 2:** The script and runtime planner could put several visually distinct claims into one spoken batch; image selection then chose one related frame and silently implied that it covered the rest.
**Why 3:** Transitions changed narration without resetting the preceding line's evidence/citation state, and a typed reply during the greeting could race into general Q&A before the intake listener existed.
**Deepest why type:** `design`
**Action taken:** Added a deterministic `model | evidence | card` contract to every bundled line. The player now uses mutually exclusive full-stage modes, never rotates an exact evidence image to a sibling, preloads all visual/audio media, gives personalised roadmaps their own card, routes multi-fact runtime batches to cited cards, clears stale citations on transitions, and queues early typed discovery answers. The CRETA narration was split into single-subject lines and rebuilt as `dm_c6a354fd`. Rodin Gen-2 replaced TRELLIS.2 after a five-real-view offline render comparison preserved the mixed black/silver/red source identity substantially better.
**Preventive action:** Every ready demo must pass `evals/qa_visual_sync.py` plus three buyer-profile browser runs. A line may use 3D only for a visible exterior claim; hidden, abstract or multi-claim language must have literal evidence or a cited card before speech starts.

### 2026-09-05 — Gemini fallback passed configuration checks but returned no audio

**Symptom:** Sarvam produced a valid WAV, but a forced Sarvam→Gemini fallback ended with “Gemini TTS returned no audio.”
**Why 1:** The fallback still used the legacy `generate_content` audio response shape while Google's current speech contract uses the Interactions API and exposes `output_audio`.
**Why 2:** Provider health only checked whether a key was present, and the existing probe called Gemini directly rather than forcing the actual fallback path through `voice.render_line`.
**Deepest why type:** `code`
**Action taken:** Moved Gemini speech to the current Interactions audio contract, upgraded the default to `gemini-3.1-flash-tts-preview`, kept the model environment-overridable, and verified a synthetic Sarvam failure produces a playable RIFF/WAV through the real fallback chain.
**Preventive action:** Voice-chain QA must force the primary provider to fail and validate the fallback file header; a configured key or direct provider call does not prove fallback wiring.

### 2026-09-05 — The opening film needed an explicit conversational handoff

**Symptom:** Runtime order was already needs question → film → demo, but Sources copy incorrectly said the film played before the guide started, and the guide resumed after the film without an explicit return line.
**Why 1:** The film was added as a latency-covering mechanism and its customer-facing transition was not represented in the flow diagram or bundle eval.
**Deepest why type:** `design`
**Action taken:** Tightened the acknowledgement, kept film audio unmuted, added a recorded post-film return line, corrected Sources copy, updated the runtime diagram, and made the smoke test require both film handoff clips.
**Preventive action:** Any full-screen media interlude needs recorded entry and exit lines plus a flow-level test for its exact position.

### 2026-09-05 — Runware's useful credit error was hidden behind a generic HTTP 400

**Symptom:** A real TRELLIS.2 build stopped with only `400 Bad Request`, while Runware's task audit contained `insufficientCredits`; Observability also showed the fallback asset price even though the rejected task cost nothing.
**Why 1:** The REST client called `raise_for_status()` before parsing Runware's JSON `errors` array.
**Why 2:** The mock path never exercises HTTP status bodies, multi-row polling responses, or provider download URLs.
**Why 3:** The integration tests covered the visual workflow but not the raw provider contract and its failure accounting.
**Deepest why type:** `code`
**Action taken:** Parse Runware errors before HTTP raising, translate known credit/key failures into actionable messages, preflight both the documented balance-object and live balance-number shapes before video analysis, prefer completed polling rows, handle malformed progress safely, record rejected jobs at $0, preserve exact returned cost when a later local step fails, require HTTPS asset URLs, and download through a separate unauthenticated client so the API key is never forwarded to a CDN. Added thirteen free provider-contract cases in `evals/qa_runware.py`.
**Preventive action:** Every external paid provider gets a no-network contract suite for 4xx bodies, transient retries, multi-result polling, cost accounting, output validation and credential isolation before its first live run.

### 2026-09-05 — TRELLIS.2 takes one image, not the five-view set the workflow collects

**Symptom:** The approved design described sending five uploaded or video-derived angles into the image-to-3D model, but Runware's TRELLIS.2 schema requires one `inputs.image`.
**Why 1:** The product flow (collect multi-view evidence) was mistaken for the provider contract (single conditioning image).
**Why 2:** The initial brief named an outcome and a model but did not include its exact request schema.
**Why 3:** Provider validation happened after the UX had already been described as multi-view inference.
**Deepest why type:** `design`
**Action taken:** The studio still collects exactly five real views because they catch identity/angle mistakes and are useful during the demo. The strongest real front-three-quarter view alone goes to `microsoft:trellis-2@4b`; other views remain labelled thumbnails. Video uses Gemini to select real frames and creates only missing views, but a generated view can never be the primary input. Runware request/poll/cost metadata is traced without storing the data URI or key.
**Preventive action:** Before fixing an external-model UX, validate the live provider schema and distinguish “inputs the user supplies” from “inputs the provider accepts”.

### 2026-09-05 — A pre-demo 3D asset must stay in the content flow, not become a disconnected generator

**Symptom:** A standalone 3D tool would create an asset but leave the voice-led demo showing full-size script images, making the expensive asset decorative.
**Why 1:** Asset generation and demo authoring were initially separate navigation concepts.
**Why 2:** `bundle.json` had no stable visual-asset field, so playback could not give 3D persistent priority.
**Why 3:** Reuse, approval, version history and deletion were not part of the demo state machine.
**Deepest why type:** `design`
**Action taken:** Added optional Demo Visual as studio step 1, an approval-gated `visual_asset` on the demo and bundle, persistent 3D playback with small supporting thumbnails, attempt history, `My Assets`, AWS mirroring, and mock-backed end-to-end tests.
**Preventive action:** Any generated media feature must define its owner, approval gate, bundle contract and exact runtime prominence before its provider call is implemented.

### 2026-09-03 — A multi-file patch script silently applied nothing (Python quoting)

**Symptom:** After "backend batch 2" the compile step said OK but none of the edits were present; the smoke test still passed on old code.
**Why 1:** The patch script (a Python heredoc) had an unterminated triple-quoted string, so Python rejected the whole file before running a single replacement — the following `py_compile` then checked the unchanged sources.
**Why 2:** Replacement bodies were embedded as triple-quoted literals while some bodies themselves contained triple quotes; one mismatch invalidated the file. (The same slip then hit the docs script once more.)
**Why 3:** The batch was applied as one shell heredoc, so a parse error had no per-file feedback and the success message came from a different command.
**Deepest why type:** `process`
**Action taken:** Re-applied from a saved script file with bodies in named variables and plain-string concatenation where quotes clash; every `patch()` prints its file.
**Preventive action:** For edits across many files, write the patch script to a file first and require every `patch()` to print — a missing "patched X" line is the failure signal, not the compile step. Never put three quote characters inside a triple-quoted body.

### 2026-09-03 — Anthropic 400 "compiled grammar is too large" on the Plan schema (first real run)

**Symptom:** Understand succeeded (71 facts) but Plan failed: `400 invalid_request_error: The compiled grammar is too large… Simplify your tool schemas`.
**Why 1:** `messages.parse(output_format=Plan)` compiles the Pydantic schema into a constrained-decoding grammar; `Plan` (nested USPs, segments, CTAs, intake, state questions, several Literal enums) exceeds the grammar size limit. `ScriptOut` would too.
**Why 2:** The schemas grew with the sales layer (roles, steps, USPs) and were only ever exercised in mock mode, which never touches the API.
**Why 3:** No live check exists for "schema still fits the grammar" — the mock validates shape, not the provider's limits.
**Deepest why type:** `design`
**Action taken:** `claude.structured` catches that 400 and falls back to plain JSON: the JSON schema goes into the system prompt, the reply is parsed with Pydantic, and one repair pass sends the validation errors back. Plan and the 37-line script then succeeded on the same run. Also: a re-read no longer redoes a finished Understand (saves ~2 min and a Gemini call on every retry). Targets Why 1.
**Preventive action:** Keep big stage schemas on the soft path by default if they hit the limit once (it's cached per process now only by retry — consider a `SOFT_SCHEMAS` set); add Loop eval: "Plan + ScriptOut parse on the real API".

### 2026-09-03 — Three live-API drifts on the first real-key check (Gemini model, Sarvam model, Sarvam speakers)

**Symptom:** With real keys: Gemini returned 404 for `gemini-2.5-flash` ("no longer available to new users → gemini-3.6-flash"); Sarvam returned 400 for `bulbul:v2` ("deprecated → bulbul:v3"), then 400 for `pitch`/`loudness` on v3, then 400 for speaker `anushka` (v2-only).
**Why 1:** Model ids and request shapes were written from memory of the public docs, not probed against the live service.
**Why 2:** Providers retire models and change parameter sets on a cadence faster than any training data.
**Why 3:** No "probe the provider" step existed in setup — the smoke test runs in mock mode and can't see drift.
**Deepest why type:** `process`
**Action taken:** `GEMINI_MODEL` → `gemini-3.6-flash` (env-overridable); `SARVAM_TTS_MODEL` → `bulbul:v3`; v3 body drops pitch/loudness; speaker list probed from the API's own error message (37 v3 voices, default `priya`). Verified TTS hi-IN/en-IN and STT round-trip live. Targets Why 3.
**Preventive action:** Keep the tiny live-probe script as `evals/probe_keys.py` and run it whenever a key is added or a provider 4xx appears — it costs a few paise and takes ten seconds. Never hard-code a speaker list without a probe.

### 2026-09-03 — Mock pitch planner returned an empty route (every script segment was "intro")

**Symptom:** `evals/smoke_mock.py` failed at `/run/pitch`: `route: []` even though the script had 3 segments.
**Why 1:** The pitch planner only routes through segments whose role is `proof` or `establish`; all mock segments had role `intro`.
**Why 2:** `mock._fake_value` returned the FIRST Literal value for every `Literal` field, and the name-based overrides ran after the Literal branch, so `role` never reached them.
**Why 3:** The mock generator was written before roles existed and was never given a notion of "a realistic mix" for list items.
**Deepest why type:** `code`
**Action taken:** Literal fields now honour a small preference map (`role→proof`, `step→say`, …) and segment lists get a realistic role cycle (intro, outcome, proof, establish, proof); route steps point at real segment ids. Targets Why 2.
**Preventive action:** When a schema gains a `Literal` field whose *first* value is a degenerate default, add it to `mock.py`'s preference map in the same change — Loop.MD eval 8 checks the mock route is non-empty.

### 2026-09-03 — pip could not install `cryptography` (built from source, Rust failed)

**Symptom:** `pip install -r requirements.txt` failed with `error[E0463]: can't find crate for core` while building `cryptography`.
**Why 1:** pip found no binary wheel (pre-built package) it considered compatible, so it tried to compile from source, which needs a Rust toolchain that isn't set up for this target.
**Why 2:** The venv is created from Anaconda's Python (`/Users/macbook/anaconda3`), whose platform tag is older (`macosx_10_9_x86_64`) than the tags on the newest `cryptography` wheels.
**Why 3:** Anaconda builds Python with an old deployment target; pip rejects wheels tagged for a newer macOS minimum.
**Deepest why type:** `knowledge-gap`
**Action taken:** Install with `--prefer-binary --only-binary=cryptography`, which lets pip pick the newest version that *has* a compatible wheel (targets Why 1).
**Preventive action:** `requirements.txt` install command in README uses those flags; if a future package hits the same wall, prefer a Homebrew Python (`brew install python@3.12`) over fighting wheels.

### 2026-09-03 — Browser pane blocks the microphone; mic-denied path must be first-class

**Symptom:** Voice intake never heard anything during automated testing.
**Why 1:** The preview browser blocks `getUserMedia`/speech recognition (`not-allowed`).
**Why 2:** Real users can also deny the mic, or use a browser without SpeechRecognition (Firefox).
**Deepest why type:** `design`
**Action taken:** `listen()` resolves empty on `not-allowed`, sets `micDenied`, and every voice prompt falls back to a typed input; check-ins keep tap chips. Verified the typed path in the pane.
**Preventive action:** Any new voice interaction must have a typed/tap equivalent before it ships (Loop.MD eval 6).

### 2026-09-03 — Approve buttons unreachable on four of five Align cards (user could not build a demo)

**Symptom:** "There is no approve button anywhere except for the last one … I couldn't generate demo … what kind of QA is being done by you?" Only the last card's Approve was clickable; the user got through by typing "approve all" to the agent.
**Why 1:** Approve/Feedback lived inside each card's *body*, and only the current card's body was open by default; opening another card pushed its body below the visible area.
**Why 2:** The cards column could not scroll: it is a CSS-grid item, and a grid item's default `min-height:auto` lets it grow past the row instead of scrolling, so `overflow:auto` never engaged.
**Why 3:** The browser QA of the Align screen was done at a viewport where all five closed cards fit, on a demo whose *first* card was the open one — the failing state (a later card opened, at a normal laptop height) was never exercised.
**Why 4:** There was no click-through eval for the approval path; the smoke test approves via the API, which cannot see layout.
**Deepest why type:** `process`
**Action taken:** `.cards{min-height:0}` so the column scrolls; Approve / Un-approve moved into every card *head* (always visible), plus an "Approve all" button and an explicit note that anything not provided will not be answered. Targets Why 2 and Why 1.
**Preventive action:** Every screen with a required action gets a browser click-through in the pane at 800×450 (the smallest realistic height), exercising the *non-default* state (last card, second tab, long list) — Loop.MD eval 16. API-level smoke never counts as UI QA.

### 2026-09-03 — Fast-start remux silently skipped for every video ≤ 60 MB

**Symptom:** The acceptance QA printed `Error opening output …/derived/…_play.mp4: No such file or directory`; the read stage still succeeded, so nobody noticed the remux never ran.
**Why 1:** `prepare_video` created `derived/` only on the >60 MB proxy branch; the fast-start remux branch assumed the folder existed.
**Why 2:** The remux path was never executed on this machine before today — ffmpeg was not installed until `imageio-ffmpeg` bundled it, and the mock smoke test uses images only.
**Why 3:** The `except` around the ffmpeg steps emits a one-line notice and continues, which is right for the customer but hid the bug from the developer.
**Deepest why type:** `code`
**Action taken:** `play.parent.mkdir(parents=True, exist_ok=True)` before the remux; the acceptance QA (`evals/qa_accept.py`) now uploads a real 20 s MP4 so the path runs on every loop pass. Targets Why 1 and Why 2.
**Preventive action:** Graceful-degradation branches must also *log to the trace* (not only emit), so a swallowed error is visible in Observability; any code path that writes to a derived folder does its own `mkdir`.

### 2026-09-03 — Ten Hindi lines silently switched voice mid-demo (Sarvam out of credits, fallback hid it)

**Symptom:** The images QA build finished "successfully", but the trace showed 10 `gemini-2.5-flash-preview-tts` calls among 96 Sarvam calls — the Hindi demo changes voice for those lines. No error row anywhere.
**Why 1:** Sarvam returned HTTP 402 "No credits available" once the account's balance hit zero; `render_line` caught it and fell through to Gemini TTS as designed.
**Why 2:** `sarvam.tts` only traced *successful* calls, and the fallback path emitted nothing, so the failure was invisible in Observability and in the build log.
**Why 3:** Per-line fallback retried Sarvam on every remaining line (≈0.3 s each) — wasteful, and no signal reached the person who could fix it (top up credits).
**Deepest why type:** `design`
**Action taken:** Sarvam failures are traced with the HTTP body; a circuit breaker trips a provider for 10 minutes on 401/402/403/quota errors; the voice stage emits "sarvam is unavailable (…) — lines used the next provider… top up, then rebuild"; `/api/voices` reports `unavailable` and the Sources voice picker shows it; the player falls back to browser speech recognition when server STT fails. Targets Why 2 and Why 3.
**Preventive action:** Every fallback in a provider chain must (1) trace the failure and (2) surface a one-line, actionable message to the user in the same stage log. Add a paid probe to `evals/probe_keys.py` before big builds — it costs one line of TTS and would have shown the 402 up front.

### 2026-09-03 — Parallel narration tripped Sarvam's rate limit; the fallback failed silently and two lines shipped without audio

**Symptom:** The video QA build reported "audio lines 28/30". Trace: four Sarvam HTTP 429 "Rate limit exceeded" rows; no Gemini-TTS rows at all, although Gemini is next in the chain.
**Why 1:** Four workers fired Sarvam requests at once; Sarvam's per-second limit rejected some; the chain moved to Gemini TTS, which also failed for those lines.
**Why 2:** Gemini's failure left no trace row — `render_line` swallowed provider errors and only Sarvam traced its own — so the second failure was invisible and the line silently became "browser voice".
**Why 3:** The parallel change was made minutes before the run to cut a 613 s stage; rate-limit behaviour of the providers was never measured, and there was no second pass for lines that fail under load.
**Deepest why type:** `design`
**Action taken:** Sarvam client backs off on 429/5xx (1.5 s → 3 s → 6 s); default `VOICE_WORKERS` 3; a sequential second pass re-records lines that failed under parallel load; every provider failure in the chain is traced (`gemini-tts` / `gcloud-tts` rows with the error). The two lines of `dm_78890026` were re-rendered and the bundle rebuilt (v2, 30/30). Targets Why 2 and Why 3.
**Preventive action:** Any parallelisation of a paid provider ships with (a) back-off on 429, (b) a sequential retry pass, (c) a trace row per failure — and the stage log must state "N lines on browser voice" rather than "Narration ready". Loop.MD eval 21 covers the provider-failure path.

### 2026-09-03 — FMEA found the grounding rule bypassed in every extra language

**Symptom:** The in-session FMEA scan (three subagent runs died on API 429/529) scored one P0: translated scripts are voiced without re-validation, so a Hindi line can carry a figure the registry never certified.
**Why 1:** `translate.py` copies the English script, swaps text per line id and keeps the fact_ids — the ids stay valid, the words don't have to.
**Why 2:** The grounding validator (`author.validate`) is tied to the authoring stage and English regexes; nobody re-ran it for translations because the "same ids" felt like the same script.
**Why 3:** Multi-language was added as a voice feature, not as a content feature — the checklist for "new content path → validator" wasn't applied.
**Deepest why type:** `design`
**Action taken:** Every translated line must keep exactly the digit groups of its source (Indian-script numerals normalised, separators stripped); a line that changes a number is kept in the main language and counted ("N lines kept in the main language"). Also from the scan: PII redaction + `TRACE_CAPTURE=meta` for traces, hard/soft breaker classes (transient quota → 90 s, account failures → 10 min), an in-flight guard on the Playground eval buttons. Targets Why 2.
**Preventive action:** Any stage that produces spoken text — author, translate, runtime bridges, Q&A — runs a figure check against its source before voice. Loop.MD eval 22 covers translation; the FMEA report `docs/FMEA-2026-09-03.md` carries the 14 P2 items.

### 2026-09-04 — I defended my own code when the user asked why we had no agent framework

**Symptom:** Asked "why not LangGraph or CrewAI?", I argued that plain code was better because frameworks lack deterministic checks and that a framework would replace only a small part of the code. The user rightly pushed back: Zod/Pydantic checks exist in every framework, and the thing they wanted — one structured place to see and reason about the workflow — is exactly what a graph framework provides.
**Why 1:** I weighed the cost of migrating code I had just written above the user's stated need (structure over scattered function calls).
**Why 2:** I framed "deterministic validation" as a differentiator when it is orthogonal: validators are plain functions in any framework.
**Why 3:** The original decision (2026-09-03, no framework) was taken for speed on day one and was never revisited when the workflow grew loops, interrupts and revisions.
**Deepest why type:** `process`
**Action taken:** Conceded in writing, then moved the workflow to LangGraph the same day: `server/graph.py` is the single definition (router → understand → plan → align_enter → align_wait[interrupt] → author → voice → rehearsal → bundle → finish), SQLite checkpointer, `GET /api/workflow` returns the graph as Mermaid (docs/mermaid/00-workflow.mmd), `langgraph.json` for Studio. Nodes stay thin wrappers over the vendor-SDK stage functions; the API, the file store and the run log are unchanged.
**Preventive action:** When a non-developer asks "why not X", answer the question they are asking (legibility and control), not the one that flatters the existing code; state the migration cost honestly and let them decide.

### 2026-09-04 — The screen did not show the part the guide was talking about (Creta gearbox)

**Symptom:** The Creta demo spoke about the gearbox in the intro and outcome while showing exterior beauty shots; the uploaded gear-lever, paddle-shifter and manual-knob images only appeared in the gearbox segment.
**Why 1:** The author picked one visual per line from a long catalogue while also writing 30 lines; it defaulted to hero shots outside the segment "about" that part.
**Why 2:** Nothing checked the script against the pictures afterwards; the plan assigned visuals per segment, not per line.
**Why 3:** Gemini's image tags (parts visible) were stored but never used for matching.
**Deepest why type:** `design`
**Action taken:** `server/agents/visuals.py` — a picture-editor pass after authoring: conservative rules on distinctive part words, then one Haiku call that decides every line with a stated reason, then a coverage guardrail so an uploaded picture with a spoken subject is shown at least once. Decisions are logged (logs/*-visuals.json) and appear in RUN.md.
**Preventive action:** Any content the guide shows (pictures, cards, video shots) is matched to the words by a pass that leaves a reason per decision; Loop.MD eval 23.

### 2026-09-04 — "The demo is pathetic": everything personalised was generated and voiced live, on the customer's clock

**Symptom:** In the Creta sessions the guide went silent after the intro, never focused on the stated need (city + long trips), showed an airbag image on unrelated lines, and switched from the female voice to a male one mid-demo.
**Why 1:** The personalisation planner was a live Claude call started when the opening began; at 14–17 s it outran the opening, so the player waited in silence, then gave up and played the standard route (`personalized: false`).
**Why 2:** Bridges, check-in replies, answers and small talk were all voiced live through `/run/tts`; when the request was late or the provider failed, the player fell back to the browser's built-in voice (male on this Mac).
**Why 3:** Pictures were chosen by the author per line with no map from information to images, so live lines showed whatever the segment's first visual was.
**Why 4:** Nothing at Align showed the actual script, so the user could not see any of this before pressing Build.
**Deepest why type:** `design`
**Action taken:** Configure now runs plan → author → FAQ bank, so Align shows the full Script (batch by batch, ≤ 20 s, mapped to seconds, picture per line) and the FAQ bank, each with a Preview pop-up. The planner returns custom batches for the buyer's context, voiced server-side while the standard opening plays; recorded filler lines (acknowledgement, bridge, holds, nudges, small talk) cover every gap; the rule at runtime is "same voice or captions, never the browser voice"; known questions answer from the pre-voiced bank instantly, new ones after a recorded "bear with me"; an information→image map is built at configure and used by the script, the batches and the answers.
**Preventive action:** Anything the customer hears must exist as recorded audio before the demo starts, or be produced while recorded audio is playing. A silent wait longer than a breath is a bug. Loop.MD evals 24–26.

### 2026-09-04 — The demo opened with a decision frame and specs; principles were sequenced instead of broad

**Symptom:** First words after the customer's context: "You're deciding two things today: does the N10 suit your driving, and manual or DCT?" plus a four-spec takeaway with the airbag cut-away on screen. The user: "open with what buyer must decide — why? you don't know what the buyer wants; principles should cover few broad guidelines."
**Why 1:** The playbook's P01 ("frame a decision, not a product") was placed at the TOP of the flow, where no buyer context exists; framing belongs at the fit summary once their words exist.
**Why 2:** The prompt mixed sequence and principles into one twelve-item block, so the writer treated principles as an ordered checklist and opened with the first one.
**Why 3:** No mandatory greeting step existed; the showroom sequence (greet → needs → walkaround in the customer's order) was never encoded.
**Deepest why type:** `design`
**Action taken:** Prompts rebuilt on the human-demo playbook: PRINCIPLES trimmed to seven broad rules (G1–G7); PITCH_SHAPE replaced by a seven-step FLOW (greeting lives in the intake question; overview before detail; exactly three USPs; natural category discovery order; mandatory meaning step; establish declares the top open questions; fit summary + next step at the close). Runtime planner writes the acknowledgement in the buyer's own words and runs on Sonnet. Coverage guardrail can no longer force a detail image into the opening; ack audio preloads and a neutral hero backs it.
**Preventive action:** Sequence and principles are separate blocks in every agent prompt; anything adaptive (decision framing, personalisation) is forbidden before the customer has spoken. Loop eval 27: the first spoken segment line contains no digits and no decision framing; the fit summary does.

### 2026-09-05 — The opening film sat behind the persistent 3D stage

**Symptom:** The runtime had the correct greeting → needs → film sequence, but a demo with an approved 3D asset could leave the model above the film in the stacking order.
**Why 1:** The 3D model deliberately has its own positioned layer; the opening film reused the ordinary supporting-video element and never entered an explicit stage mode.
**Why 2:** The film flow had been verified at the API/bundle level, not in the exact 3D-led player state.
**Deepest why type:** `process`
**Action taken:** `playIntroFilm` now enters `film-on`: model, reference strip and supporting detail fade away; the audio film takes the full stage; on finish/skip it is hidden and the 3D stage returns before Ravi's recorded return line. Browser QA exercised the exact state.
**Preventive action:** Media-sequence acceptance requires a browser screenshot in every mutually exclusive stage state, not only a valid URL and audio track.

### 2026-09-05 — Runtime personalisation chose the manual image for an automatic claim

**Symptom:** A live family-route batch said “automatic” and cited the transmission facts but selected the manual gear-knob image.
**Why 1:** One transmission fact legitimately maps to manual and automatic images; the runtime model picked the first valid sibling.
**Why 2:** Runtime custom batches validated that a visual id existed, but did not re-run the literal word-to-picture check used by authored lines.
**Deepest why type:** `design`
**Action taken:** Runtime batches now score all cited candidate visuals against their spoken words and override only on a strong literal match. The player passes each narration line into its 3D director, holds the relevant front/side/rear/performance angle for 4.5 seconds, and keeps the exact supporting image as the detail proof.
**Preventive action:** Any new path that creates spoken text plus a visual must pass both grounding and literal visual-alignment checks before playback.

### 2026-09-05 — Preloading only intake left avoidable pauses between authored lines

**Symptom:** Intake acknowledgements were fast, but the rest of the recorded route could still incur a first-fetch pause when each line began.
**Why 1:** Preload objects were created only for intake and fillers, then immediately lost to garbage collection.
**Why 2:** Narration, deeper lines, check-ins, FAQ, closing and the opening film were not covered.
**Deepest why type:** `code`
**Action taken:** The player now retains preload objects for every authored audio line and the opening film for the session lifetime, releasing them only when the player is destroyed. Real lookup gaps use recorded, polite “give me one moment, please” bridges.
**Preventive action:** The no-silent-gap browser gate covers the entire bundled audio graph, not just first response.

### 2026-09-05 — The player could still change voice if a recorded file failed in the browser

**Symptom:** The authored audio path was all-Sarvam, but an individual browser playback/load error still called the built-in browser voice.
**Why 1:** The earlier “same voice or captions” rule covered server generation failure, not client media playback failure.
**Deepest why type:** `code`
**Action taken:** A failed server-voice audio file now stays on-screen as timed captions; browser speech is used only for demos explicitly configured to use browser speech.
**Preventive action:** Voice consistency is enforced at both generation and playback boundaries.

### 2026-09-05 — Valid WAV files hid two severely malformed fallback durations

**Symptom:** The final bundle had an audio URL for every line, but two short lines were 33 and 173 seconds long; five narration files had silently used the Gemini fallback inside an otherwise Sarvam build.
**Why 1:** The build gate checked only that an audio URL and file existed.
**Why 2:** Provider-level success did not verify duration against word count or assert one provider across the finished customer route.
**Deepest why type:** `process`
**Action taken:** All five fallback files were re-rendered with Sarvam and the exact timeline rebuilt (186.3 seconds). Final integrity QA checks every spoken item for a readable WAV, non-silent signal, plausible duration and provider hash; all 99 spoken entries now pass as Sarvam `aditya`.
**Preventive action:** “Audio complete” requires content integrity and provider-consistency checks, not file existence.

### 2026-09-05 — Catalogue accepted CSV while the upload guidance hid it

**Symptom:** A synthetic price sheet could be uploaded as CSV, but the Catalogue panel only advertised PDF, DOCX, TXT and MD; the supported fallback looked unsupported.
**Why 1:** The file-picker accept list was expanded without updating the adjacent human-readable copy.
**Deepest why type:** `process`
**Action taken:** The Catalogue guidance now names CSV, and the visual-sync regression compares the visible promise with the accepted extension.
**Preventive action:** Any upload-format change must update both the picker contract and the copy in the same test.

### 2026-09-05 — Build blockers still said five Align cards after FAQ made six

**Symptom:** Align correctly showed six required cards, while two build errors and the Rehearse empty state still told the user to approve five.
**Why 1:** FAQ became a first-class approval card, but scattered count-specific strings were not part of that migration.
**Deepest why type:** `code`
**Action taken:** All live build guidance now says six cards; the visual-sync regression rejects either stale five-card string.
**Preventive action:** Keep workflow counts behind shared copy where practical, and make the cross-screen contract test fail when a count diverges.

### 2026-09-05 — Provider exhaustion restarted expensive work instead of resuming it

**Symptom:** A transient reasoning-provider failure left the FAQ bank partial, while a retry risked re-answering every completed question.
**Why 1:** FAQ generation had no registry-version checkpoint and provider failover treated each question as an isolated call.
**Deepest why type:** `architecture`
**Action taken:** Text-only structured calls now fall back to the configured secondary provider; FAQ progress checkpoints after every answer, reuses same-registry results, and offers an explicit cache-bypassing retry. Runtime Q&A uses a traced, approved-fact-only fallback during an outage cooldown.
**Preventive action:** Long multi-call stages need resumable checkpoints and circuit breaking before they are considered production-safe.

### 2026-09-05 — Validated human corrections were marked stale and could be overwritten

**Symptom:** A direct product, fact, pitch or script correction invalidated its own model-owned stage, so Build could regenerate over the reviewed edit.
**Why 1:** Invalidation encoded dependency freshness but did not distinguish an unvalidated mutation from a replacement artifact that had already passed validation.
**Deepest why type:** `architecture`
**Action taken:** Direct editors now validate their artifact, invalidate only dependants, restore the edited stage to done, and require all affected Align approvals again.
**Preventive action:** Human-authored replacements must have an explicit validated state transition; never route them through a model rerun implicitly.

### 2026-09-05 — Attractive product images were being used as proof for invisible claims

**Symptom:** Generic exterior photos could be attached to capacities, prices, written terms and hidden safety mechanisms they did not prove.
**Why 1:** Keyword overlap rewarded product relevance without first asking whether the claim was visually observable.
**Deepest why type:** `model`
**Action taken:** Runtime image mapping now excludes non-visual facts and sends unsupported detail to a cited fact card; direct script edits rebuild this safe map.
**Preventive action:** Visual relevance is not evidentiary coverage; gate observability before similarity scoring.

### 2026-09-05 — Voice review showed the configured label, not the voice that would play

**Symptom:** The Persona card could display a stale provider or speaker after re-recording, and partial builds could leave some FAQ or filler items silent.
**Why 1:** Review copy read raw settings while rendering resolved fallbacks dynamically; sample audio was not persisted into the reviewed plan.
**Deepest why type:** `code`
**Action taken:** Align now shows the resolved provider and voice, sample re-recording persists and invalidates Persona approval, and final QA counts audio across script, FAQ, check-ins and fillers.
**Preventive action:** Review surfaces must describe the resolved runtime artifact, and build completeness must cover every playable branch.

### 2026-09-05 — Hyphen splitting turned “crash-test rating” into a test-drive answer

**Symptom:** Asking for a current crash-test rating returned a dealership test-drive fact.
**Why 1:** Naive token overlap treated “test” as the decisive shared term and had no hard-unknown guard for unsupported safety ratings.
**Deepest why type:** `code`
**Action taken:** Safety-rating intent is now a hard unknown unless an approved matching rating fact exists; regression coverage includes the hyphenated wording.
**Preventive action:** High-risk intents need negative controls, not only positive keyword matching.

### 2026-09-05 — Comparison and finance fallbacks lost the decision caveat

**Symptom:** A named rival-price answer omitted the product's own price, and a request for one illustrative EMI scenario returned multiple scenarios without consistently repeating the non-offer caveat.
**Why 1:** Generic top-fact selection optimized lexical overlap rather than the response contract for comparative and financial decisions.
**Deepest why type:** `code`
**Action taken:** Rival matching is now derived from uploaded comparison facts, price answers cite both products plus verification guidance, and named synthetic scenarios return only the requested illustration with its caveat.
**Preventive action:** Decision-sensitive intents need explicit response shapes and mandatory caveats in tests.

### 2026-09-05 — A closed responsive panel still widened the whole page

**Symptom:** The player looked usable at phone width but the document still scrolled horizontally because nested grid tracks and a transformed closed panel retained intrinsic width.
**Why 1:** Responsive rules changed visible layout without allowing grid children to shrink at every ancestor.
**Deepest why type:** `code`
**Action taken:** Studio/player tracks now use shrinkable columns, controls wrap on phones, and root overflow is contained; live checks pass at 320, 390, 768 and 1280 px.
**Preventive action:** Responsive QA must assert document scroll width, not rely on screenshots alone.

### 2026-09-05 — A nearby true fact answered a different high-risk question

**Symptom:** “Which is the cheapest Harrier variant?” returned “55 variants,” while “Is the powered tailgate standard on every variant?” returned only that a powered tailgate exists.
**Why 1:** Intent-specific narrowing kept the original fuzzy candidates when no claim matched the required intent.
**Why 2:** The matcher treated feature presence as equivalent to universal variant scope.
**Deepest why type:** `design`
**Action taken:** Intent narrowing is now fail-closed; cheapest/entry-variant questions require a named variant fact; universal-scope wording requires explicit scope evidence. Global NCAP applicability has its own scoped response contract.
**Preventive action:** Every high-risk selector gets both a positive test and a near-miss negative test. An empty exact match must decline, never reopen the fuzzy candidate pool.

### 2026-09-05 — Ready did not mean every customer branch had audio

**Symptom:** A Harrier build briefly reached ready with only 8 of 28 FAQ answers voiced after Sarvam rate limiting.
**Why 1:** The voice stage checkpointed partial work but the final build gate accepted the partial bank.
**Deepest why type:** `code`
**Action taken:** Build now fails unless every FAQ answer and filler has audio, while retaining completed files for a rate-limit-safe retry. Harrier v2 rebuilt with 88/88 referenced WAVs populated.
**Preventive action:** Completeness gates must enumerate every runtime branch, not only the main narration path.

### 2026-09-06 — Audi Q5 passed only after envelope, intent and concurrency failures were made explicit

**Symptom:** The 34.8 MB brochure exceeded the primary reader envelope; early chat runs leaked a prior product name and overreached on cheapest/scope questions; a voice retry raised `dictionary changed size during iteration`; and the final mocked sweep caught a polled JSON artifact being read mid-write and reset.
**Why 1:** The source pipeline treated provider capacity as fact quality, several compound intents reused generic lexical matching, shared provider state was unsynchronized, and stage JSON writes were not atomic.
**Deepest why type:** `architecture`
**Action taken:** Oversized reads can use only a source-validating reviewed manifest; Q5 price, performance, equipment, comparison, photo-proof, finance, ground-clearance and ADAS intents now have narrow fail-closed contracts; voice circuit state is locked; runtime gaps self-heal and deduplicate; JSON artifacts publish by atomic replacement; the async visual test uses a deterministic concurrency barrier.
**Evidence:** Audi Q5 `dm_302ab4aa` is ready at v1 with 45 approved facts, 25/28 FAQ answers, complete 88-item playable audio coverage, three muted ten-question sessions, responsive checks at 320/390/768/1280 px, a fully decoded 157.54-second MP4, and free suites at 98/98, 32/32, 17/17 and 24/24 plus the full mocked pipeline.
**Cost:** $0.5682 recorded total; the only paid visual was Rodin task `f68aff15-6e2f-4bdb-8594-ed430159ed16` at exactly $0.40.
**Preventive action:** Treat provider envelopes, runtime registries and file-backed stage state as explicit system boundaries; every release gate must include adversarial intent tests and a polled background-worker path.

### 2026-09-18 — A revise on a ready demo never rebuilt through the API

**Symptom:** `POST /revise {stage: "deck"}` on a ready demo re-ran the deck and then parked at Align instead of re-bundling; `evals/qa_deck.py` timed out waiting for `ready`.
**Why 1:** The `faq` edge routes to `voice` only when `rebuild` or `prev_ready` is true in the graph state; both were false.
**Why 2:** `graph.start_revise` computed `prev_ready = status == "ready"` *after* `_set_status("reading")`, so it was always False.
**Why 3:** The Align-chat path (`align_wait` → `requests["revise"]`) reads the status before anything changes it, so the only path anyone had exercised worked; no eval covered `POST /revise` on a ready demo.
**Deepest why type:** `order-of-operations`
**Action taken:** `start_revise` reads `prev_ready` first and keeps the status at `building` when a rebuild will follow. `qa_deck.py` now waits for `ready` after a deck revise.
**Preventive action:** Any state read that feeds a routing decision happens before that function's side effects; every entry point of a graph command gets an eval, not just the chat one.

### 2026-09-18 — The transcript said what the guide *started* saying, not what the customer heard

**Symptom:** `addMsg("agent", text)` ran when `speak()` began, so a line cut off by a question reached `/run/qa` as if fully heard, and a typed reply during a chip wait was logged twice (once by the wait, once by `handleQuestion`).
**Why 1:** Logging lived at the start of `speak()` because that was the one place every line passed through.
**Why 2:** Nothing measured how much audio had played; an interruption only bumped the run token.
**Why 3:** The transcript was treated as a drawer display, not as the model's memory of the conversation.
**Deepest why type:** `wrong-source-of-truth`
**Action taken:** `S.speaking` tracks the playing line; `logHeard(sp, complete)` logs on `ended` (full) or from `cancelSpeech` (heard prefix = `currentTime / duration × words`, elapsed-time estimate for captions and the browser voice) marked `interrupted`; `handleQuestion` skips a user line the chip wait already logged. Evals: the transcript cases in `qa_deck.py`; browser check on the mock server (Phase 5).
**Preventive action:** Anything sent to a model as "what happened" is written by the event that proves it happened (audio ended, request returned), never by the event that started it.

### 2026-09-18 — A slide switch waited for an animation frame that a hidden tab never gets

**Symptom:** In the browser pane (a hidden document) a new slide stayed at opacity 0: `showSlideView` added the `on` class inside `requestAnimationFrame`, and hidden documents get no frames.
**Why 1:** The cross-fade needed the element inserted first and the class added "next frame" so the CSS transition would run.
**Why 2:** The visible-tab assumption was never stated; every manual check had the pane in front.
**Deepest why type:** `hidden-assumption`
**Action taken:** Insert → `layout()` → forced reflow (`void el.offsetWidth`) → add `on`, synchronously. Same transition, no frame dependency. Found by the Phase 6 scripted browser check (which itself had to move its polling into one call: model latency between calls let the demo run ahead).
**Preventive action:** Nothing that decides what is on screen may depend on animation frames or on the tab being visible; only audio events and user actions drive the player.

### 2026-09-18 — A reload kept running the old module

**Symptom:** After a deploy of new front-end modules, the Observability page still ran the previous `observability.js` after a reload; a `no-store` fetch of the same URL returned the new file.
**Why 1:** `/web` was served with an ETag but no `Cache-Control`, so browsers applied heuristic freshness (10 % of the file's age) to each module.
**Why 2:** A modern reload revalidates only the document; module imports come from the cache when still "fresh".
**Why 3:** One import already carried a hand-written `?v=3e0`, a per-file workaround that nobody extends to the next file.
**Deepest why type:** `missing-policy`
**Action taken:** A middleware sets `Cache-Control: no-cache` on `/`, `/web/*` and any `.html/.js/.css` — every load revalidates, a 304 when unchanged. APIs untouched.
**Preventive action:** Every static asset the app serves has an explicit cache policy; version queries on imports are not the mechanism.

### 2026-09-18 — A deck-only rebuild died on a model the deck never needed

**Symptom:** `POST /revise {stage: deck}` on the real TVS iQube demo ended in `error` at the FAQ stage — "Question generation failed: 503 high demand" (Gemini) — although nothing about the sources or the registry had changed; the bundle stayed stale and the player kept the old slides.
**Why 1:** The graph re-runs every node after `deck` (faq → voice → bundle), and `faq.run` regenerated its question list with a model call before checking whether the registry had changed.
**Why 2:** The reuse logic only covered the answers (by registry hash), because the question list was written first and the hash check came second.
**Why 3:** Rebuilds had only been exercised in mock mode, where every model is always up.
**Deepest why type:** `unnecessary-dependency`
**Action taken:** When the registry hash is unchanged the previously generated questions stand (no call); `force` regenerates. Proven by a counting test in `qa_deck.py`.
**Preventive action:** A rebuild of one stage may only call a model for that stage; every downstream node reuses by content hash, and the eval counts model calls on a second run.

### 2026-09-18 — One busy second froze Gemini for ten minutes

**Symptom:** On a real rebuild the deck writer fell back to derived callouts twice; the demo's log said "Gemini rate limit cooldown: current quota exhausted; wait or enable billing" while a fresh one-token probe of the same key answered fine.
**Why 1:** `gemini._retry` latched a 600 s cooldown on any message containing "exceeded your current quota".
**Why 2:** That text is also Gemini's ordinary per-minute burst 429 on a free-tier key, which carries its own "retry in Ns" hint.
**Why 3:** The latch was written against the zero-quota case (no billing) and never tested against a burst.
**Deepest why type:** `overbroad-match`
**Action taken:** `_quota_cooldown(message)` — a burst waits what Gemini asks (+1 s; 30 s without a hint); only `limit: 0` / `quota_value: 0` latches ten minutes. Unit cases in `qa_deck.py`.
**Preventive action:** Any provider cooldown is sized from the provider's own retry hint, and the zero-quota case is matched on its specific markers, never on generic quota wording.

### 2026-09-18 — The player needed a visible product and a readable conversation

**Symptom:** The welcome blurred the product behind a large mascot; slide titles were hard to find, and a revealed overlay line started at the picture corner. A phone preview of the redesign then exposed a gradient fading out the hero.
**Why 1:** The same presentation emphasized the guide and controls more than the product, and positions were measured while callout chips had no dimensions.
**Why 2:** Reveal changed visibility without recomputing leader geometry; layout reserved a fixed caption height.
**Why 3:** Existing checks covered data positions and desktop presentation, not visible rendered geometry after reveal or a changing conversation dock.
**Deepest why type:** `design`
**Action taken:** Product-first welcome, visible benefit headings, native-aspect pictures, scoped evidence panel, typed reply field, measured dock reservation, and layout recomputation after reveal. Mobile hero uses an upper picture area without an obscuring gradient.
**Preventive action:** Browser checks measure leader endpoints after reveal and wide/narrow image bounds; visually review welcome, long answers and controls on a phone before calling the experience ready.

### 2026-09-18 — Silence and qualified replies incorrectly advanced the demo

**Symptom:** The browser swallowed “Yes, but what about charging?” as agreement and continued narration behind an unknown-answer callback form.
**Why 1:** Short prefix matching classified any brief yes-prefixed reply as confirmation; timers treated silence as continuation.
**Why 2:** The player had separate paths for chips, ordinary questions and microphone input rather than one owned customer turn.
**Why 3:** A global reply resolver and mic flag let a delayed speech result target whichever wait happened to exist later.
**Deepest why type:** `architecture`
**Action taken:** Explicit question waits have no auto-advance countdown. Exact controls settle choices; qualified replies reach Q&A. Typing is always visible. Capture ownership spans permission, recording and transcription; late results cannot resolve a new turn. Unknown and dissatisfied answers retain the turn until explicit continuation.
**Preventive action:** Browser regressions exercise silence, yes-but, stale speech after skip/restart, delayed QA, clarification and callback hold. Acoustic recognition quality remains a real-device test.

### 2026-09-18 — Q&A lost the opening checkpoint and clarification context

**Symptom:** An opening interruption could replay completed narration; short clarification replies could match an unrelated cached FAQ.
**Why 1:** Return state described only the routed slides; the opening and deeper explanation had no independent checkpoint.
**Why 2:** A clarification was treated as a new standalone question rather than a reply to the original one.
**Why 3:** Tests checked structural strings and successful question routing, not a second reply inside an interrupted phase.
**Deepest why type:** `design`
**Action taken:** Preserve phase, slide and line across all follow-ups, then return with a spoken bridge after explicit resolution. Clarification speaks alone, accepts typing or voice, and sends the original question plus the actual reply/history with FAQ matching disabled.
**Preventive action:** Browser cases cover opening and off-slide interruption, exact once-only typed clarification and deeper question waits; content cases reject a clarification containing an uncited claim.

### 2026-09-18 — Fallback labels were fragments and rebuilds could remap edits

**Symptom:** The iQube deck included “Charger supplied: portable new 950W charger that plugs”. Omitting a long fact also risked attaching an existing Align edit to a different numbered callout.
**Why 1:** `_compact` sliced the first N words.
**Why 2:** Fallback considered width without preserving complete meaning, conditions or truth type.
**Why 3:** Positional callout IDs assumed the set and order could never change.
**Why 4:** Evals measured length, layout and citations without an omitted earlier fact plus a saved edit.
**Deepest why type:** `design`
**Action taken:** Keep a complete original label with its qualifications only when it fits; otherwise omit it. Preserve prior unambiguous citation identity and reserve IDs belonging to omitted callouts or existing overrides.
**Preventive action:** Long-label, condition, title and repeated-rebuild override regressions.

### 2026-09-18 — The script substituted a default customer for the real viewer

**Symptom:** The real iQube session recorded 5–10 km/day while the existing script described 30 km/day; prompts also repeated discovery.
**Why 1:** The prompt wanted one context choice while the schema asked name, purpose and a second question.
**Why 2:** Customer examples and generic personas appeared beside the actual customer context.
**Why 3:** Reused plan/script text was not explicitly excluded as evidence about this viewer.
**Why 4:** A valid product citation could license an unrelated personal quantity, and no-context output was accepted.
**Why 5:** Tests checked shape and routes without testing ownership of personal details.
**Deepest why type:** `design`
**Action taken:** Align prompts and schema, enforce empty second-intake fields, suppress invented personalization after skipped intake, and reject quantities absent from customer or cited-fact inputs. Validate check-ins as well as narration so moving a claim into a question cannot bypass grounding.
**Preventive action:** Adversarial 5–10 versus 30/thirty, skipped intake, valid spoken quantities, check-in grounding and second-intake tests. The quantity guard checks presence, not semantic entailment; the new real script still needs source and customer-profile review.

### 2026-09-18 — The buyer ending exposed the internal sales handoff

**Symptom:** Stop showed the customer an intent score, classification, route/drop point and USP identifiers; an open callback form could cover the summary.
**Why 1:** The player rendered its internal session report directly as the customer ending.
**Why 2:** One view served two audiences with different needs, and ending playback did not close subordinate overlays.
**Why 3:** Completion tests verified record saving but not what the buyer saw.
**Deepest why type:** `design`
**Action taken:** Customer recap uses their actual stated needs, explored topics and questions still open, with one optional follow-up. Internal metrics remain in session storage. Opening the recap closes the callback form.
**Preventive action:** Browser regression stops during an unresolved callback turn and checks buyer copy, visible overlays and preserved internal record separately.

## 2026-09-18 — Cinematic evidence rail collapsed and labels moved between layouts

**Why 1:** Narrow callout evidence had zero height despite visible child boxes.
**Why 2:** Evidence items reused the class `overlay`, whose global modal rule made them absolutely positioned.
**Why 3:** Renderer styling changed composition without an explicit in-flow reset for the semantic marker.
**Why 4:** Earlier geometry checks only bounded the picture and leader; they did not require a nonzero evidence parent.
**Why 5:** Saved image coordinates, responsive evidence and modal utility styles had no joint browser contract.
**Fix:** Scope evidence items to static positioning; reserve the full fallback evidence band before placing chips; measure heading bounds without animation; reject oversized chip placements; preserve native image/anchor geometry and saved Align data.
**Prevention:** The19-case player harness includes narrow/portrait evidence, nonzero fallback parent, consecutive-layout stability and exact anchors through resize. All19 pass with synthetic audio/API only; real Nexon verification stays separate.

## 2026-09-18 — Competitor applicability and rejected evidence bypassed runtime checks

**Why 1:** Rival PDF/text sources did not contribute facts, and runtime comparisons lost trim conditions.
**Why 2:** Competitor ingestion selected only URLs, while the Q&A context copied only claim/value.
**Why 3:** Upload provenance and richer fact fields were not carried consistently across source ingestion, prompt assembly and FAQ reuse.
**Why 4:** A cached FAQ answer bypassed live approval checks, and a CTA could bypass replacement of rejected or uncited answer text.
**Why 5:** The prior contract tested happy-path citations without rejected evidence combined with cached audio or action fields.
**Fix:** Read rival documents into separate C-facts; preserve conditions, truth, locator, quote and source URL/date; validate URL metadata before mutation; share approval guards between model and bank paths; invalidate FAQ reuse when approvals/competition change; reject unsafe claim text before speech regardless of CTA.
**Prevention:** `evals/source_contract.py` exercises isolated PDF/text ingestion, provenance validation through the real API, rejected/mixed citations, bank hits with revoked facts/disabled comparisons, and the actual text passed to speech. Live semantic claim-to-source review remains required; token/citation checks alone do not prove entailment.

## 2026-09-18 — Reviewed script must control the slide preview and bundle
- Why did old questions reappear? The deck held a previous copy of script text and check-ins.
- Why did direct review not remove it? Script edits invalidated the deck; saving a slide override marked it done without refreshing that copy.
- Why could the bundle retain it? Fallback joins treated an explicitly empty check-in as missing and kept deck citations.
- Why was this missed? Prior checks verified saved visual overrides, without exercising a script correction followed by a slide edit.
- Root cause and fix: the script is the authority for spoken text, citations, metadata and explicit empty questions. A shared deterministic join supplies Align and bundle without changing saved visual design. Five regressions cover preview/bundle parity, cleared questions, changed citations and held lines; Align review now47/47.

## 2026-09-18 — Valid citations were turned into unproven benefits (NX14/NX16)

**Why 1:** The first real plan/script/FAQ used clearance as flood/damage assurance, litres as demonstrated luggage fit, and unrelated engine figures as a mode-switch power delta.
**Why 2:** Generation was required to turn every feature into a customer outcome or performance promise, although source evidence often established only a specification.
**Why 3:** Truth descriptions equated an official test method with certification; product prompt context dropped exact source quotes/locators, and examples omitted the ordinary `stated` category.
**Why 4:** A valid fact id was treated as sufficient grounding for extra meaning, while trim/fuel/finance restrictions could move out of the spoken claim. The planner's final id filter also allowed human-rejected facts still present in storage.
**Why 5:** Structural mock checks covered citations and pacing, not the distinction between a sourced specification and a source-supported outcome; manual correction alone would not change the next generation.
**Deepest why type:** `design`
**Fix:** Shared extraction truth/scope rules and downstream evidence rules; prompt/schema descriptions now allow a useful choice or fit-check instead of an invented benefit. Product context carries the original quote and locator with truth/conditions. Explicit instructions preserve trim/fuel/finance scope, forbid unsupported arithmetic and route unknowns to the appropriate source. Plan reference filtering now accepts approved facts only. No new schema fields, semantic regex engine, model critic or paid call.
**Prevention:** `evals/generation_contract.py` has 21 passing free input/approval contracts, with network/providers blocked; existing customer contracts remain 29/29. Eleven synthetic adversarial cases in `evals/fixtures/generation_grounding.json` cover negative and positive generation behavior for the authorized real review. Prompts and citation checks are not semantic entailment: inspect raw second-Read artifacts before polishing or claiming these failures resolved. Re-Read review preservation remains unchanged; reviewed facts must be snapshotted, identity-mapped and reapplied through the API separately.

## 2026-09-18 — Plain-language guidance removed the unit (NX18)

**Why 1:** A refreshed real FAQ said “pulling power is 260” without Nm.
**Why 2:** The everyday-audience instruction prohibited both the technical abbreviation and its spoken unit, while asking the model to translate the number into a plain term.
**Why 3:** The same style instruction governed a general tour and a direct technical question, with no exception for a complete requested quantity.
**Why 4:** The jargon-repair instruction asked for plain wording without explicitly preserving the whole quantity.
**Why 5:** Tests checked banned words and citation presence, not whether the complete value/unit reached speech or whether prompt rules conflicted.
**Deepest why type:** `design`
**Fix:** Main narration moves unnecessary technical quantities as a whole to deeper detail; direct Q&A retains the value, unit and scope with a short gloss. Jargon repair explicitly forbids dropping only the unit. Ordinary facts need no repeated disclaimer or certification label.
**Prevention:** Free contracts capture actual build-FAQ and runtime prompt envelopes and prove a complete mocked answer reaches the speech seam unchanged; a deeper unit-bearing answer survives author validation. The adversarial unit-loss case still needs a real response review: no deterministic semantic/unit validator was added.

## 2026-09-18 — The on-screen generator kept the old benefit-only contract

**Why 1:** The second raw deck promised easy rough-road clearance, family luggage fit, highway efficiency and lower fuel costs from ordinary specifications.
**Why 2:** Its prompt and callout/title schema descriptions still required a benefit or promise and explicitly rejected a bare specification label.
**Why 3:** The earlier evidence-rule change reached plan, author and Q&A, but not this separate model-writing stage; deck context also omitted truth, exact source quote and locator.
**Why 4:** The scope review followed spoken-content generation and missed that the on-screen model can independently create unsupported customer claims.
**Why 5:** Earlier deck tests established bounded text, valid IDs and visual layout, not whether all generation surfaces received the same source/evidence contract.
**Deepest why type:** `design`
**Fix:** After freezing the raw I2 deck, align only its existing prompt/schema descriptions and fact context with the shared evidence rules. Complete neutral specifications and relevant fit-checks are allowed; omitted callouts are preferable to lost qualifications or invented benefits. No model critic, semantic regex engine, saved-override change or paid rebuild.
**Prevention:** Two actual deck input-envelope contracts bring the free generation suite to 23/23; the 12-case adversarial review set includes deck benefits and fuel-cost overreach. The raw I2 script/FAQ still repeat semantic failures despite receiving the new instructions, so prompt assembly is not a faithful-generation guarantee. Record those failures before manual corrections. A separate stale saved label bound I1's BNCAP text to I2's ISOFIX F004: root owns review-identity recovery, and the prompt fix does not address it.


## 2026-09-18 — A locked Priya build switched speakers after a Sarvam rate limit (NX19)

**Why 1:** The first real Nexon Build exhausted a Sarvam request window, then synthesized FAQ/fillers with Gemini Sulafat although the chosen voice was locked to Priya.
**Why 2:** Only strict runtime calls restricted the fallback chain; ordinary build speech ignored `voice_locked`.
**Why 3:** FAQ/filler reuse trusted any existing audio path, without checking its provider/speaker/language/content hash.
**Why 4:** The provider circuit was checked before its cache, making already-recorded Priya clips unavailable during a transient cooldown. Parallel workers also sent Sarvam requests without a shared pace.
**Why 5:** The speech gate tested fallback availability rather than the chosen-voice invariant and recovery from a partially voiced build.
**Deepest why type:** `code`
**Fix:** Locked speech keeps the configured provider and speaker for build and runtime, including a missing key or temporary circuit failure. Matching cache reads happen first. Main, deeper, check-in, closing, intake, FAQ and filler clips are reused only by their chosen-voice hash; old Gemini references are replaced or cleared. Missing locked narration or bank audio stops the build before bundling, with completed work checkpointed. Gemini policy refusals, including the observed “Input blocked sensitive words”, are not retried by the voice stage or forwarded to another provider. A locked Cloud voice also preserves mock isolation.
**Pacing evidence:** Sarvam's official [rate-limit documentation](https://docs.sarvam.ai/api/getting-started/ratelimits) lists Bulbul v3 Starter at 30 REST requests/minute, shared across account keys. This process conservatively spaces starts by 2.1 seconds; this is an application policy, not a claim about the account's actual tier. Only HTTP429 receives up to three attempts. Numeric or HTTP-date Retry-After is honored; a requested wait beyond the call's 30-second wait budget stops explicitly and preserves the shared cooldown. Other processes on the same account can still consume capacity.
**Prevention:** `evals/voice_lock_contract.py` has 27 free cases with fake speech/HTTP/clock and blocked sockets. They reproduce mixed FAQ/fillers, cached main/check-in/intake, cooldown reuse, missing-only recovery, explicit incomplete narration, policy refusal, locked Cloud mock isolation, pacing and bounded retries. Failed real Build1 remains preserved; the next real build is the user's second attempt, not an uncounted recovery run. No live provider call was made for this fix.

## 2026-09-18 — Human FAQ review could not replace a generated answer

**Why 1:** A real FAQ answer added benefits or connective wording that the reviewed facts did not establish, and Align offered no direct answer correction.
**Why 2:** The FAQ card could display and approve a generated bank, while corrections went back through regeneration.
**Why 3:** Generation and review were treated as the same operation; another model answer could repeat the defect and replace a human correction.
**Why 4:** No explicit edit contract preserved the question, origin and registry hash while discarding derived audio, visual and route metadata.
**Why 5:** The free gates checked generation/reuse, not the full human-review → ordinary Build path.
**Deepest why type:** `design`
**Fix:** Existing Align now accepts a supported answer plus fact ids at `PATCH /api/demos/{id}/align/faq/{qid}`. All ids must be approved and competition-eligible; mixed valid/invalid ids are rejected rather than filtered. Existing NUMBERISH/CLAIMISH rules reject uncited claims. Stale, partial and running banks cannot be edited. The route preserves bank/question identity and registry hash, clears old audio/error/clarification/callback, derives the visual and the slide from the current script joined to saved slide design, clears only FAQ approval, and invalidates voice/rehearsal/bundle while keeping FAQ done. Card and Preview offer a labelled, keyboard-focusable editor; no model is called.
**Prevention:** `evals/faq_review_contract.py` passes 41 free API/build/cache contracts in temporary storage with providers and networking blocked. It covers held/mixed F/C citations, competition off/on, stale hashes/stages, graph gaps between stages, mutation-free failures, changed script references, excluded cached visuals, exact-answer normal Build reuse, fresh runtime stay/jump routing and removal of old recordings. This does not prove semantic entailment: a valid citation does not certify an added benefit, so the human must review meaning and scope. Only supported-answer edits are included; question/decline/clarification authoring is unchanged.

## 2026-09-18 — Align Script Preview did not show the customer slide template

**Why 1:** Script Preview showed the plain native image layout after the customer player had moved to cinematic slides.
**Why 2:** Preview called the shared renderer without its fitted-player option.
**Why 3:** Cinematic styling is scoped to the player stage, but the read-only preview had no stage wrapper.
**Why 4:** The editable source-coordinate view and the customer presentation view shared a default rendering call despite serving different review tasks.
**Why 5:** Previous preview checks compared text and saved overrides, without checking the final presentation shell.
**Deepest why type:** `code`
**Fix:** Only Script Preview now uses the fitted shared renderer inside a bounded `.pl` / `.pl-stage` shell, with an active slide and no player controls. The editable slide view retains its native coordinates and drag behavior.
**Prevention:** Root's real-browser review must compare the customer-style Preview at wide/narrow widths before this checkpoint is accepted; syntax checks alone do not establish visual parity.

## 2026-09-18 — Hidden mobile labels left a visible diagonal leader

**Why 1:** A phone-sized cockpit preview showed a line from the picture's top-left corner to an evidence dot.
**Why 2:** Narrow-layout CSS hid the overlay label and repeated its text in the evidence rail, but kept the SVG leader visible.
**Why 3:** A hidden label has zero bounds, so layout could compute the leader origin at the picture corner.
**Why 4:** Responsive visibility was applied to the label but not to the line that depends on that label.
**Why 5:** Prior mobile checks verified native image fit, readable rail and numbered anchors, but did not inspect the leader's painted visibility.
**Deepest why type:** `code`
**Fix:** In the exact existing ≤699px cinematic container rule, hide the leaders with `visibility:hidden`. The native-image geometry, numbered dots, evidence rail and wide-screen label/leader remain unchanged.
**Prevention:** The free browser harness adds a wide →390px →304px →wide check for hidden mobile leaders, visible dots/rail and restored desktop leaders. Required isolated gates after the fix pass: deck203/203, acceptance24/24, both smoke phases, Python38/JS12 and harness-module syntax. Actual browser results are recorded by root; the subagent's CUA had no available browser.

### 2026-09-18 — A provider outage was written into the FAQ bank as knowledge

**Symptom:** After the starved rebuild every one of the TVS iQube bank's 20 entries read "I'm not sure about that from the material I've been given"; at runtime every bank question declined, and the customer heard a guide that seemed to know nothing.
**Why 1:** `qa.answer` turns any provider exception into the DONT_GUESS decline (Phase 1: never guess) and `faq.run` stored that decline exactly like a real "the sources do not say".
**Why 2:** The return value carried no sign that the decline came from an exception rather than the model.
**Why 3:** The bank had only ever been rebuilt with working providers.
**Deepest why type:** `conflated-states`
**Action taken:** `qa.answer` returns `provider_failed`; `faq.run` then keeps the previous answer (same registry) or marks the entry `error` for a retry and the bank `partial`; `faq.match` skips unbuilt entries so the live model answers. Three cases in `qa_deck.py`.
**Preventive action:** "The sources do not say" and "the model was down" are different states everywhere they can be stored; a stored decline must carry which one it is.

## 2026-09-18 — Runtime Q&A routed through an obsolete script copy (NX24)

**Why 1:** A correct boot FAQ stayed on the cabin slide during the second real customer run.
**Why 2:** The saved deck still held an old deeper-line F014 citation on that cabin slide, and runtime routing preferred a fact already present on the current slide.
**Why 3:** Align Preview and bundle hydrated saved slide design from the reviewed script, while `/run/qa` read raw deck copies.
**Why 4:** Two paths interpreted the same saved slide artifact with different authorities for spoken citations.
**Why 5:** Earlier routing regressions had consistent deck/script fixtures and did not exercise a reassigned fact after direct human review.
**Deepest why type:** `code`
**Fix:** Runtime Q&A joins current script lines/deeper citations onto saved deck design through the existing `slides_with_script` helper before routing either a bank hit or a live answer. Declines still remain on the current slide, and routing does not mutate saved design. The pitch path already reads its fact-bearing library from the script; its sole raw-deck lookup maps stable segment ids to slide ids and has no stale-fact interpretation to repair.
**Prevention:** `evals/runtime_delivery_contract.py` reproduces raw cabin-stay versus reviewed boot-jump, then exercises actual bank/model API routes, the correct stay and decline paths, and no deck/script writes. Correct fact ids and correct returned text are insufficient evidence that the displayed topic is correct.

## 2026-09-18 — Slow customer provider work blocked cached media (NX26)

**Why 1:** Prerecorded acknowledgement audio could not be delivered while a runtime pitch was waiting on its model/speech work.
**Why 2:** An `async` FastAPI endpoint called the synchronous pitch function directly and occupied its event loop.
**Why 3:** Runtime Q&A, TTS and STT endpoints used the same direct synchronous-provider pattern.
**Why 4:** Declaring an endpoint async had been treated as sufficient concurrency, despite blocking work inside it.
**Why 5:** Prior tests checked endpoint responses independently, rather than concurrent media delivery on the same ASGI loop during a held provider call.
**Deepest why type:** `code`
**Fix:** Await built-in `asyncio.to_thread` for the existing synchronous pitch, live QA, TTS and STT calls. Their provider order, result shapes, tracing context, strict selected voice, language arguments and HTTP502 behavior remain intact. No service, dependency, model, timer or streaming path was added.
**Prevention:** The combined runtime-delivery suite passes27/27 with fake providers and blocked sockets. One AsyncClient/ASGITransport event loop holds each fake provider on a threading.Event and proves actual cached media plus health complete before release. It also checks worker/context propagation and failures. This frees the event loop; it neither shortens provider work nor cancels an underlying worker if a request is abandoned, and does not establish a latency SLA.


### 2026-09-18 — Personalized slides bypassed complete-label and image review

**Symptom:** Real Nexon playback showed “Boot space capacity: 382 L for Petrol &” over the preceding cabin image.
**Why 1:** `transientSlide` sliced fact text to eight words and inherited the current picture when no explicit visual arrived.
**Why 2:** The reviewed deck already had a complete qualified boot label and its own image, but the runtime slide did not consult it.
**Why 3:** The earlier complete-label correction applied only to backend derived callouts, leaving this separate customer-visible formatter unchanged.
**Why 4:** Browser tests covered turn ownership and geometry without inspecting the content and image of a personalized fact slide.
**Why 5:** The same evidence-preservation rule had not been checked at every place that presents a fact.
**Deepest why type:** `design`
**Action taken:** Transient slides reuse complete reviewed labels only when all their citations belong to the approved transient facts. Otherwise they keep the entire claim, value, conditions and truth qualifier within eight words or omit the badge. Without an explicit visual, a reviewed slide must cover every cited fact before its picture is reused; otherwise use the neutral hero. Stored deck data is never changed.
**Preventive action:** Real-browser contract fixtures cover reviewed boot wording/image after a cabin, mixed-scope refusal, complete short conditions/truth, rejected facts and unchanged review objects. No paid call or content rebuild is needed.


## 2026-09-18 — Live warranty wording resolves an explicitly unknown policy relationship

**Why 1:** Actual profile-A Q02 was heard as “3 years or 1,00,000 km” although the cited headline only joins the limits with a bar and its reviewed conditions leave the relationship unknown.
**Why 2:** The short qualified reply missed the long reviewed FAQ question and reached live generation.
**Why 3:** General source/conditions instructions did not explicitly distinguish a list of policy limits from their legal relationship; plausible connective wording survived citation validation.
**Why 4:** The validator checks citations/claim presence, not whether “or” or “whichever first” is entailed by a source.
**Why 5:** Prior generation checks verified evidence delivery but had no synthetic headline-policy case paired with an explicit-terms control.
**Deepest why type:** `prompt`
**Fix:** One generic QA_SYSTEM bullet preserves explicit unknown terms, forbids deriving a limit relationship from a slash/bar, and retains relationships or coverage rules when explicitly supplied. The missing term belongs only in the relevant answer. No car facts, matcher changes, new service, schema field, provider or speech behavior were added.
**Prevention and limit:** Four input-envelope cases cover unknown relationships and explicit relationships/exclusions through both actual build-FAQ and runtime QA assembly, with providers and sockets blocked. Baseline was 23/27; the prompt change passes 27/27 plus compilation. These checks establish delivery of the rule and exact evidence, **not model compliance or semantic entailment**. A fresh live Q02 result remains necessary; the original failing session is retained. FAQ matching remains unchanged because a stop-word/threshold shortcut was not shown to preserve scope.


## 2026-09-18 — A greeting answer asks a question before the player's check

**Why 1:** Actual initial session `s_mu72zmm82u16` answered “Hello” with “Would you like to continue exploring cargo practicality, or look into running costs…?”, immediately followed by the player's “Did that answer it?”.
**Why 2:** Runtime trace 311 put the offer question in ordinary `answer`, with `answered=true` and empty `clarifying_question`.
**Why 3:** The player correctly handled the designated clarification field separately but treated ordinary answer text as a completed response.
**Why 4:** QA instructions did not assign ownership of the following question and also invited the model to “offer” technical detail.
**Why 5:** Input-envelope cases covered evidence and clarification structure, not greetings/ordinary answers against the player-owned satisfaction check.
**Deepest why type:** `prompt`
**Fix:** QA_SYSTEM now asks for ordinary answers as statements and brief greeting acknowledgments without restarting intake. Only the existing `clarifying_question` field may ask a question, with an identical question-only answer. Technical detail may be mentioned as a statement. Schema, matcher, provider/outage, policy and voice behavior are unchanged.
**Prevention and limit:** Six free real-envelope cases cover greeting, ordinary answer and clarification on build/runtime paths; restoring the old prompt in memory yields 27/33, the new prompt 33/33. Providers and sockets are blocked. These verify instruction delivery, not model obedience; the actual failing heard transcript remains evidence and a live rerun is still required.


### 2026-09-18 — Typed customers were returned to automatic microphone capture

**Symptom:** In the second real customer validation, the customer typed intake and a boot question. After the correct cached answer, follow-up waits automatically opened the microphone and sent unrelated ambient media as two customer questions. This run cannot establish voice recognition quality.
**Why 1:** Every owned `waitFor` attempted listening whenever a microphone was available.
**Why 2:** The player retained turn ownership but no preference for how that customer chose to reply.
**Why 3:** Submitting typed text stopped only the current capture; the next wait opened a new one.
**Why 4:** Browser regressions fenced stale results, but did not require a typed interaction to keep later microphone captures closed.
**Why 5:** Input modality was treated as a per-turn fallback rather than an explicit customer choice.
**Deepest why type:** `design`
**Action taken:** Start with the existing voice behavior. An actual input event or typed submit chooses typing and cancels current capture. Later waits, including a restarted intake, remain typed until an explicit microphone tap restores voice mode. Focus alone does not change preference. Mic controls stay visible and microphone permission policy is unchanged.
**Preventive action:** Two real-DOM browser regressions cover typed intake/check-in/QA without new listening, discarded late ambient output, explicit microphone speech and resumed voice waits, plus preference through Restart and explicit intake-mic activation. The main player owner integrates the narrow patch alongside independent session-clock and jump-announcement fixes; actual refreshed browser acceptance is recorded separately.


## 2026-09-18 — A stopped session continued accumulating time (NX27)

**Why 1:** The real initial session was saved ended but grew from the observed8.3 to11.3minutes, and its final slide kept accumulating dwell.
**Why 2:** Stop marked only an ended boolean; each later Done/pagehide snapshot subtracted the original start from the current wall clock.
**Why 3:** The still-open slide used the same moving clock even after narration had stopped.
**Why 4:** Playback cancellation and engagement accounting had no shared end boundary.
**Why 5:** Completion tests checked the ended flag and saved transcript, but never advanced time after ending.
**Deepest why type:** `code`
**Fix:** An in-memory cutoff freezes total elapsed and current-slide dwell at the first handoff. Repeated Stop, Done and pagehide preserve that boundary. Explicit Back, new typed/mic input, slide selection or CTA reopens the same session and shifts its active start/current-slide start past the inactive interval. Restart creates a fresh clock and session. Saved schema, transcript timestamps, intent scoring and QA latency stamps are unchanged. Historical records are preserved, not rewritten.
**Prevention:** Real-player browser fixtures advance five minutes after Stop/Done, verify identical elapsed/dwell across saves and pagehide, then exercise Back, another slide, Restart and an intentional new question after Done. Synthetic time tests prove accounting behavior; they do not establish acoustic quality.

## 2026-09-18 — A grounded Q&A jump lacked a spoken transition (NX28)

**Why 1:** The actual boot answer routed to the correct slide after the citation fix but changed the picture abruptly, with no announcement in the heard transcript.
**Why 2:** The player called showSlideView immediately on a jump response, then spoke the answer.
**Why 3:** The return path already had a spoken bridge, but the outward jump did not use the existing transition filler.
**Why 4:** Routing was tested as target correctness and return-point preservation without checking the customer's transition cue.
**Why 5:** Visual correctness and conversational continuity had been treated as separate success checks.
**Deepest why type:** `code`
**Fix:** Await the existing bridge_to_custom cached clip before changing slides, with one short generic speak fallback if that clip is unavailable. Only a completed, still-owned run can change the view and speak its answer. The actual answer re-arms first-answer-audio timing after the bridge; the bridge is heard transcript, not answer latency. Stay/none paths remain unchanged and no build is needed.
**Prevention:** Browser fixtures hold the cached bridge for three seconds to prove the current view and null answer timestamp persist until completion, then verify answer timing and heard transcript. Another fixture cancels it by navigating and verifies no late jump or answer. The existing off-slide return case also verifies the generic fallback precedes the answer and the exact interrupted line is retained.


## 2026-09-18 — A comparison becomes a catalogue and loses rating applicability

**Why 1:** Actual B Q07 returned 88 whitespace-separated words in one sentence, with 19 citations and many equipment items (runtime trace348, Runware GPT-5.5).
**Why 2:** “1–3 short sentences” constrained nominal sentence count without a word budget or an attribute-selection rule.
**Why 3:** A broad selected-automatic comparison encouraged listing the registry instead of choosing the buyer's most relevant differences or shared features.
**Why 4:** The long catalogue compressed “five-star BNCAP for petrol and diesel trims” and omitted F006's material May-2026 applicability condition.
**Why 5:** Prior free checks established evidence delivery, not whether the provider prioritized useful attributes while retaining scope in speech.
**Deepest why type:** `prompt`
**Fix:** The existing QA prompt now requests at most60 words including caveats. A direct single fact can use one sentence; a comparison chooses at most two buyer-relevant attributes, states both sides in two or three short sentences, and drops an extra attribute before shortening its material conditions. It stops before the player-owned follow-up. No schema, matcher, provider, bundle or voice change.
**Prevention and limit:** Two added real input-envelope fixtures deliver the focus rule, buyer context, both variant qualifications and full website-verification caveat through build-FAQ/runtime calls. The prior prompt scored33/35; the changed prompt35/35 with all provider/network calls blocked. This does not enforce a word cap or prove model entailment. Original Q07 remains a pacing/scope failure; positive comparison acceptance is pending a fresh focused live answer.


## 2026-09-18 — A sourced comparison ended inside its JSON answer (NX30)

**Why 1:** Actual customer B Q08 declined even though approved Venue comparison facts were present in the request.
**Why 2:** Gemini returned a 170-character unfinished JSON answer; local schema validation correctly rejected it. Claude then failed for missing credits and Runware timed out, so the guide declined.
**Why 3:** The live caller allowed only 1,500 output tokens; the trace recorded 1,486 combined candidate and thought tokens with very little visible text. Budget exhaustion is strongly consistent with this evidence, but not proven because the existing trace does not retain finish_reason.
**Why 4:** A short spoken-answer target had also become a tight allowance for the complete structured response and model reasoning.
**Why 5:** Provider contracts checked dispatch/schema/cost behavior, but did not exercise the live QA caller's budget through the actual SDK request envelope.
**Deepest why type:** `code`
**Fix:** Raise only live QA's existing max_tokens argument to 3,000. The QA prompt still requests at most 60 spoken words; build-time QA and unrelated runtime defaults remain 1,500. No provider, timeout, retry, thinking configuration or speech change; no additional Build.
**Prevention and limit:** Five free provider checks exercise the real QA/dispatcher/Gemini/installed-SDK path with a fake transport, synthetic keys and blocked sockets: 3,000 in the request, complete approved answer/citation validation without fallback, combined thought/candidate accounting, build-time 1,500 and unrelated-runtime 1,500. A complete fake response proves the configured envelope, not future provider compliance or an actual comparison pass. The preserved Q08 failure remains failed until the root's authorized live rerun is reviewed.


## 2026-09-18 — Concurrent cold Gemini callers closed an in-flight client (NX31)

**Why 1:** Fresh B Q08 declined after all reasoning providers failed: Gemini reported a closed client immediately, Claude lacked credits, and Runware timed out.
**Why 2:** Q&A and pitch could enter the lazy Gemini client initializer concurrently after runtime calls were moved onto workers.
**Why 3:** The initializer tested a shared None value and constructed/assigned the client without a lock, allowing two SDK clients to replace each other.
**Why 4:** The installed SDK Client destructor calls close(), while its Models object retains the API transport rather than the parent Client. Replacing the global can therefore close an already-running request.
**Why 5:** The media-concurrency regression exercised fake provider functions, not concurrent first initialization of their shared SDK resource.
**Deepest why type:** `code`
**Fix:** Protect only cold initialization with a standard-library Lock and a second None check. The already-created client remains shared; provider order, model selection, request settings, retries and timeouts are unchanged. No response is fabricated or reclassified as a fact gap.
**Prevention:** `evals/gemini_client_contract.py` holds the first fake SDK constructor while another thread calls the same real initializer, then holds both model calls and mimics the installed SDK destructor. Before the fix it constructs two clients and closes an in-flight transport (3/7); after the fix both use the same open transport (7/7). Missing-key and constructor-error recovery behavior remain covered. No live provider or network call is made. The observed trace proves the closed-client failure; the deterministic race establishes a code path that explains it, not a post-fix live success. The concurrent pitch also returned incomplete JSON separately; its cause is not resolved by this lock.


## 2026-09-18 — A complete qualifier was still clipped on a phone (NX25 follow-up)

**Why 1:** The actual final A boot slide clipped “Creative+PS/Fearless+PS” at the right edge, although the saved label was complete.
**Why 2:** The evidence item measured 164px wide but its content scrolled to 171px; the rail was 343px wide with 350px of content.
**Why 3:** Its flex text child retained its automatic minimum width, and a long trim token had no permitted wrap within that width.
**Why 4:** Whole-label preservation fixed semantic truncation but did not ensure every retained token could fit a phone card.
**Why 5:** Existing geometry fixtures used ordinary words with convenient spaces and checked rail/image bounds, not each painted text fragment.
**Deepest why type:** `code`
**Fix:** Only within the existing narrow Cinematic rule, let the evidence text child shrink and wrap anywhere. Preserve exact label text, font size, card/rail layout, image geometry and saved coordinates.
**Prevention:** A real-DOM regression uses the actual reviewed boot and split-seat labels at 390, 320, 304 and390px. It checks text preservation, each card's scroll width, painted text fragment bounds, the unchanged 12px minimum and no two-card rail/page overflow. Baseline screenshot: iteration-2/screenshots/A-final-boot-phone.png. Browser execution remains the root's responsibility; syntax or mock gates alone do not establish visual correction. No Build, provider or production-data change.


## 2026-09-18 — Open questions became a false promise in the follow-up opener (NX33)

**Symptom:** Actual C safely declined exact Mumbai price and guaranteed EMI, but its saved summary proposed “I have those details ready”. The same summary still listed those questions as unanswered. This was an internal suggested opener, not customer-heard narration.
**Why 1:** The model turned a proposed follow-up into a statement of completed research.
**Why 2:** The summary prompt allowed a natural sales opener without explicitly preserving unavailable-answer status.
**Why 3:** The code copied unresolved record fields but trusted the generated opener independently of them.
**Why 4:** Existing tests checked summary shape and record copying rather than a contradiction between unknowns and the suggested next sentence.
**Why 5:** A valid structured response was treated as sufficient evidence for a future operational claim.
**Fix:** When the session has unresolved topics, non-callback escalations, or the generated summary has unanswered questions, code replaces only the opener with a neutral invitation to discuss the open questions. The prompt also prohibits claiming missing answers/quotes/approvals/finance terms already exist. Context, interests, objections, unanswered fields and session status keep their existing behavior; the original C snapshots are not rewritten.
**Prevention:** `evals/summary_contract.py` exercises the actual summary function with the exact C bad opener, each independent open-question signal, model-field preservation, no mutation of input status, a resolved-session opener, callback-only bookkeeping and mock behavior. Before:4/10; after:10/10, fake providers and blocked sockets.
**Limit:** This is a deterministic opener safeguard, not semantic validation of all summary fields or proof that a salesperson has obtained anything. Retained historical non-callback escalations conservatively keep the invitation neutral. No paid call, session migration or provider/schema change.


## 2026-09-18 — A direct customer statement did not reach retained context (NX32)

**Why 1:** Real C said “I mainly want help with stop-and-go traffic.” The stopped recap omitted that actual need.
**Why 2:** The statement reached Q&A, transcript and question history, but profile.why/followup stayed empty.
**Why 3:** Intake and explicit line/clarification answers stored context; a direct turn during narration bypassed those paths.
**Why 4:** The recap reads the retained profile, while runtime history is limited to the latest eight messages.
**Why 5:** Earlier context tests covered intake and clarification, not a new statement entered while narration was active.
**Deepest why type:** `code`
**Fix:** Before the existing QA dispatch, retain each exact new customer turn once in followup. Skip exact intake wording, an already-retained line and the clarification replay whose question/reply was already stored. This does not infer or modify focus, classify intent or change the QA workflow. Root also adds a QA prompt instruction distinguishing a buying need/context correction from an unsupported specification: acknowledge the actual need without a promised benefit, use applicable approved evidence or the existing one-question clarification, and keep genuine unknown/guarantee declines.
**Prevention and limit:** One new real-player browser case enters a statement during held narration, checks the next API profile, repeats the intake and statement to reject duplicates, verifies unchanged focus, and confirms exact wording once in the saved session/recap. The clarification case now verifies its original question and existing clarification pair exactly once. The prompt improves consultation guidance but does not enforce semantic correctness; the actual failed C run is preserved and live recovery is still required.


## 2026-09-18 — Personalized pitch adds unsupported relations and installation benefits (NX34)

**Why 1:** Actual A trace395 produced and spoke a warranty “or” relation and predictable-ownership benefit, a properly-secured child-seat outcome and an uncited installation-ease bridge; its boot batch omitted ISO V215.
**Why 2:** Valid fact IDs and matching numbers passed validation even when the additional meaning or a material qualifier was absent.
**Why 3:** The pitch prompt still allowed a “reasonable inference,” despite the shared evidence rules, and its local fact formatter omitted original source quotes/locators.
**Why 4:** The custom/bridge path used numeric and a short claim-word list rather than checking the observed explicit unknowns, measurement basis and added benefit wording before synthesis.
**Why 5:** Prior tests guarded invented customer numbers and hidden questions, but not these real cited-yet-unsupported additions.
**Deepest why type:** `code`
**Fix:** The existing pitch path receives full fact_context and a stronger scope-before-benefit prompt. Before speech, optional custom lines/bridges are omitted if they assert a policy relation while cited evidence explicitly leaves it unknown, drop a cited quantity's explicit ISO/VDA/SAE/DIN measurement basis, or add the narrow observed benefit vocabulary absent from affirmative cited evidence. Uncited assertion bridges are rejected. Reviewed route entries remain; no replacement product claims are synthesized.
**Prevention and limits:** Real plan_pitch fixtures fail9/19 before and pass19/19 after, including actual failed text, no rejected text reaching fake speech, intact reviewed route and positive documented relation/basis/equipment/fit-check controls. Both this suite and the10-case summary contract run in qa_deck. These conservative English lexical checks can omit useful optional phrasing and do not establish general semantic entailment, complete condition preservation, variant association, or multilingual coverage. Affirmative occurrence of a benefit word in a citation is necessary for this guard but is not sufficient proof of an arbitrary claim using that word. Prompt compliance and actual post-fix spoken output still require review. The pre-fix A session remains a failed grounding example; no third Build occurred.


**NX34 independent-review follow-up:** A standard present only in the exact source quote was initially missed, while its numeric code was rejected when correctly repeated. Two actual-path cases reproduced19/21; the detector now reads conditions and quote, and numeric validation admits only the recognized quoted standard's code, not every unrelated number in the quote. Final focused coverage is21/21. Honest negated relation wording and buyer-only benefit adjectives can be conservatively omitted by these lexical guards; no general entailment or complete safe-phrase coverage is claimed.


## 2026-09-19 — Prototype product labels must follow the supplied image

**Symptom:** Bluebird initially called the supplied Audi Q5 picture an A4; Control Room initially called it a Q4/e-tron. These were isolated mockups; no real demo metadata changed.

**Five whys:** (1) The card name did not match its image. (2) A plausible placeholder name survived after the approved photo was connected. (3) The prototype data and asset list were authored separately. (4) Syntax/asset-existence checks proved the image loaded, not what vehicle it showed. (5) Product identity was missing from the visual review checklist.

**Fix:** Name the Audi Q5 consistently in sample data and dynamic labels. Compare every product card against the local asset provenance during browser review.

**Eval:** Open all four workspace concepts, inspect the Audi card and its accessible image name, and compare with `docs/design/options-2026-09-18/assets/provenance.json`. Final Bluebird snapshot shows Audi Q5 and Control Room shows Audi Q5 / SUV. No A4/Q4/e-tron placeholder remains in the prototypes.


## 2026-09-19 — Repair subsets, uncited context and prerequisite provenance (CR32)

**Observed:** The immutable focused40 left q001 unhelpful despite valid child-seat/comfort sentences in its repair; q025 dropped the Alexa purchase caveat after choosing a broader citation; q049 added an unsupported future-lineup publication claim as “context”. Q044 and q050 missed relevant approved styling/parking facts.

**Causes:** Repair acceptance required every candidate clause to pass; uncited screening looked for a short list of product phrases; material conditions were checked only on selected citations. Ranking repeated resolved trim words, crowding out topic facts, and one source-specific “edition” descriptor did not match the source’s own canonical trim.

**Fix:** Retain only already-validated factual repair sentences when the original has no usable facts, with errors/partial status preserved. Restrict uncited context and limitations to bounded interaction, attributed customer input and own verification/input limits. Close explicit compatible device-purchase prerequisites across supplied evidence; preserve separate primary and condition-only provenance. Optional warranty policies are excluded. Rank the topic after resolving scope. Correct F080 to new F253 only after exact same-page source review; never strip “Edition” generically.

**Limits:** These are narrow English checks, not universal entailment or multilingual validation. Source correction is a versioned publication, not silently rewritten history. The original failures and all prior scores remain unchanged. Independent adversarial controls and a new live cohort are required; fixtures alone do not establish acceptance.


## 2026-09-19 — Strict guards removed the answer’s actual uncertainty (CR33)

**Observed:** Fifth full100 fell to78 supported turns despite zero flagged critical unsafe claims. Nine turns were unhelpful; exact own-limit or interaction wording was frequently present in the model draft but lost by validation. The adjective “all-black” triggered a universal-trim check. A full-registry empty boundary result was lost and recomputed from a smaller retrieved pack, inventing uncertainty about SX. An automatic-only EPB projection used its qualifier as a feature label.

**Cause:** Lexical guards treated source/missing-input adjuncts as positive claims; absence of boundary metadata was conflated with an authoritative empty boundary; component/feature identity was conflated with qualifier text. A source’s explicit lineage limitation also went through positive equipment validation. These are validation defects, not proof that the model lacked the answer.

**Correction in progress:** Normalize only bounded own-inability/interaction forms, preserve the requested unknown, retain authoritative empty scope decisions, distinguish descriptive hyphens from trim quantifiers, and require the actual feature plus same-clause transmission qualification. Preserve rejection of source-wide absence, unsupported publication statements, new quantities and positive causal claims. Existing one-repair/deadline/cancellation safeguards remain.

**Separate lookup cause:** Model-wide city-price links tied on topic and sorted alphabetically, selecting Ahmedabad without a named city. Recognized price-in-city child pages now require the customer’s own named locality or explicit city seed. This is a narrow route-structure check, not a general location/alias/residence parser. Offline source-lookup20 controls pass; live verification remains separate.


## 2026-09-19 — leave time to deliver verified work (CR35)

**Observed:** Two real EMI turns completed the calculator correctly, then returned a provider failure with no tool results. Comfort comparisons missed relevant approved seats/climate facts. Other answers lost valid polarity, precise uncertainty or pricing qualifications.

**Causes:** Each model call could consume the entire remaining outer deadline, so deterministic validation never ran. Comfort vocabulary was absent from query expansion. A narrowed assertion projection was mistaken for the full literal trim coverage. Currency-unit matching recognized spoken rupees but not ₹, and whole-answer acceptance discarded useful validated limits.

**Correction:** Keep250ms for validation inside the same deadline; salvage only a completed audited calculator result and expose the failed composition separately. Do not revive cancelled turns. Expand explicit comfort queries at query time without changing eligibility or stored indexes. Revalidate independent clauses; expand scope only through the same assertion's literal projection. Pair adjacent currency normalization with independent requested-page attribution. Retain precise limits only if they survive final speech validation and do not erase original facts.

**Limits:** Prompt changes for completeness and individual fit checks still need real replay. These English checks do not prove general entailment, perfect phrase coverage, microphone behavior or current external prices. The failed cohorts and source snapshots remain immutable.


## 2026-09-19 — preserve clause ownership instead of matching whole answers (CR36)

**Observed:** The next unchanged40 improved to30 supported but still emitted two unsupported assertions. A ventilation absence supplied the polarity for a combined electric-seat absence. A first-person limitation admitted an unsupported causal statement about official model-year specifications. Correct grouped road-wheel and connected-feature drafts were also dropped.

**Causes:** Related seat concepts were too broad for negative entailment. The own-limit guard omitted a causal connector. Grouped trim comparisons were validated as if every citation applied to every group. A condition-only sentence made a rejected richer feature sentence appear redundant, suppressing repair. Exact interaction phrase matching rejected harmless new wording and semicolon-separated clarification.

**Correction in progress:** Independently validate each feature's polarity and each explicit trim group; preserve same-clause material conditions while checking whether the substantive requested claim survived. Normalize only bounded uncited assistant acts and literal negative main clauses, then apply normal validation. Never strip conditions from cited factual rows or turn missing retrieved evidence into whole-source absence. Original results and initial/adjudicated reviews remain saved.


## 2026-09-19 — true facts did not prove their combination or complete source coverage (CR37)

**Observed:** The unchanged full100 on `24736a0` / published v7 produced **73 supported / 11 partial / 7 unhelpful / 2 unsafe / 7 provider failures**. In q024, individually correct Bose and display facts became an unsupported Bose/8-inch pairing through “it pairs with”. In q073, selected web passages became an unsupported claim that the supplied page did not mention the warranty. Original responses, row hashes, semantic reviews and earlier cohorts remain immutable.

**Causes:** Citation and quantity checks proved the component facts but not their shared fitment. The validator tracked no immediate factual antecedent for a relational pronoun. Source lookup returned selected passages, while reporting verbs were treated as evidence of a complete page read. Separately, valid boot/armrest uncertainty and EX/SX comparison clauses were lost through narrow language recognition, feature-label matching and repair acceptance; successful provider fallback could therefore still produce an unhelpful answer.

**Correction:** Check explicit affirmative equipment pairings against compatible literal positive fitment, preserving size/unit ownership and using only the immediately preceding accepted factual row. Unknown, negative or unconfirmed applicability cannot establish a combination; separate feature lists remain separate. Convert unsupported source-coverage claims to an own-verification limit, retaining only closed, requested unknown-attribute slots when safe. Preserve exact supported comparison clauses and meaningful verified repair content without discarding original factual IDs. These are bounded checks, not a general entailment engine.

**Operational lesson:** A provider failure is different from a knowledge gap. Failure speech now explains an operational problem; a completed audited calculation may still be delivered. Reasoning duration accumulates across tool rounds. The new delayed provider race is **off by default**: one atomic winner, one whole-call deadline, copied usage context, and explicit cancellation. Independent review reproduced a fallback dispatch after a primary winner during logging/history preparation; final stop/deadline checks now run after preparation, before the adapter call. Already-started synchronous requests can still finish and incur cost; late usage is recorded and late content is discarded.

**Evidence and limits:** Pairing12 and source-coverage12 test groups, operational13 and hedge30 controls run free; independent pairing/coverage/hedge checks blocked all sockets. The full100 was typed REST with no TTS or microphone: median3.831s, p95 11.802s, estimated cost$0.5773. Offline replay saved122 exact drafts across92 cases with full original v7 assertions plus traced projections, rather than substituting the model's shortened evidence. It diagnoses current guard behavior; it does not change old grades or establish new live acceptance. The paired provider experiment and next reviewed cohort remain pending.


## 2026-09-19 — separate assistant actions from product assertions (CR38)

**Observed:** Both same-code full100 comparisons reached88 supported answers but still failed acceptance. Open trim thresholds were invented from exact lists; natural missing-input and personal-fit sentences were over-rejected. A repaired answer preserving an old fact and adding a useful new one was dropped because a nonessential aside failed.

**Correction:** Use typed closed conversational acts with backend wording and question-bound IDs. Keep them separate from citations and product sentences; remove already-provided inputs and speak the single question last before waiting. Do not relax factual guards to accommodate conversational phrasing. Literal ordinal scope needs feature/direction/boundary proof, not trim ordering or a nearby availability verb. A useful repair may retain all original facts and gain another validated fact despite rejected optional wording.

**Delivery and process:** Append only missing audited EMI terms; never rewrite a wrong claim into a correct one silently. Check whether proposed filenames already exist before adding files: this iteration briefly overwrote existing delivery files in the working tree, caught before any service/replay and restored exactly. New helpers now have unique paths. Optional model-schema changes must pass real SDK serialization and mock-pipeline tests.

**Evidence limit:** The delayed fallback comparison established correct recovery/late accounting, not a performance benefit; it remains off by default. No new speech or acoustic validation ran. Original cohorts and source publications remain immutable.

## 2026-09-19 — retain safe refusals and bind counted features (CR39)

**Observed:** The next unchanged100 improved to93 supported,4partial,2unhelpful and1provider failure, with no unsupported critical claim found. A valid typed financing question discarded its independently safe guarantee refusal. Two task-specific limits became generic fallbacks. A valid SX-and-above Bluelink sentence was rejected because “provides/along with” and “70 connected features” did not match its literal reviewed boundary.

**Correction:** Keep only an independently validated first own-limit prelude before the backend-generated question; ignore raw later questions/claims. Closed comparison-evidence and source-instruction acts remain question-bound and fact-free. Source-instruction speech states an action without yes/no polarity. Count normalization retains feature modifiers and distinguishes multiple quantities for the same counted noun; exact trim lists still cannot create an ordinal threshold.

**Review findings:** A semicolon prefix needed a final sentence boundary. Collapsing two differently modified feature counts could exchange their quantities, caught by independent paired controls before replay. Reviewed applicability conditions must not be presented as an explicit source quotation. Preserve initial review records when adjudicating this distinction. Physical listening and speech percentiles remain outside muted evidence.


## 2026-09-19 — fallback needs usable time, not just a configured provider (CR40)

**Observed:** A settled unchanged100 on9d46913/v7 scored87 supported with8 whole-turn provider failures. Sequential Gemini timeouts used7s; Claude credit failures/cooldown and Runware attempts often left less than4s. Earlier actual Runware successes took3.316–5.563s. Merely listing fallback providers cannot establish reliable recovery within12s.

**Next bounded experiment:** Expose a finite1–5s hedge-delay configuration, retaining default5s/off. Test3s under the same turn deadline, fixed provider order, cancellation and one-winner rules. Multiple reasoning/repair phases can each overlap; cost and late usage must be attributed and settled. An earlier first structured result still needs ordinary validation. Observational cohorts do not establish a causal performance gain.

**Conversation:** A bank-approval refusal packed into invalid clarification and a source-grounding refusal removed as uncited context both became unhelpful. Add only question-bound fact-free own-limit acts; do not allow raw claims or broaden product validation. Preserve original responses and grade them separately from provider status.


## 2026-09-19 — source coverage must follow coordinated pronouns (CR41)

**Observed:** The three-second fallback cohort reached94 supported answers, but q073's repaired sentence escaped a direct source-coverage guard: “the retrieved highlights page covers … but it does not detail warranty terms”. Three selected passages could not establish whole-page absence. The initial direct absence claim was rejected; one reworded pronoun clause was incorrectly accepted by the same repair validator.

**Cause and correction:** The guard bound a negative reporting predicate only to an explicit source noun. Add a bounded same-sentence source-reporting antecedent check for its coordinated pronoun, while keeping explicitly named product subjects and nested product clauses outside this source-coverage rule. Never treat this as a general semantic proof. Retain an honest own verification limit; do not voice the positive premise or a successful-check implication from the rejected sentence.

**Useful uncertainty:** q002 lost its precise capacity/measurement limit while retaining a split-seat fact. A closed boot-measurement own-limit act preserves both requested unknowns without inventing a number or assuming a seating basis. Its catalogue requires the capacity request and measurement/seating basis together, not an unrelated luggage preference and car-width question.

**Boundary:** “Available policies only cover …” is a separate ambiguous policy-inventory overstatement, graded partial. Do not broaden source nouns to every contract policy and accidentally reject legitimate warranty exclusions. The observed result and all old hashes remain unchanged.

## 2026-09-19 — punctuation and formatting must not change evidence rules (CR42)

**Observed and why:** In the next unchanged 100, q033's “EX(O), S(O), and higher” bypassed range validation. Clause splitting removed the comma-coordinated suffix before the threshold matcher could see it. q071's “page reflects … but it doesn't specify …” bypassed source coverage because antecedent binding depended on a whitelist of positive reporting verbs. Both are critical unsupported claims; their exact drafts and evidence remain preserved.

**Correction:** Bind a relative range across its optional comma without merging independent feature clauses. Bind the source and its coordinated reporting pronoun without assuming that only “lists/covers” can describe a source. Preserve explicit intervening product subjects and reject ambiguity conservatively. These are narrow controls, not a general semantic proof.

**Useful content:** Diesel power/torque failed because evidence normalized grouped digits while spoken comparison did not: “4 000” and “4000” were treated differently. Apply the same typography normalization to both sides, retaining wrong-value, wrong-unit and scope checks. Dealer-delivery uncertainty and fabricated-evidence requests need closed own-limit/operating acts, not copied raw claims or new invented quantities. Unfamiliar citation IDs alone are not fabrication requests.

**Validation boundary:** q099's E/King climate contrast remains supported despite lost optional detail; do not redefine a broad comparison as exhaustive after seeing the answer. Original 93/2/3/2/0 grades remain unchanged. The next live replay is separate evidence.

## 2026-09-19 — source restriction and live table scope need their own proof (CR43)

**Why q028 escaped:** The direct-source “only” guard still depended on reporting verbs, despite the preceding source-pronoun fix. Initial “records only show” was caught; repaired “documents only note” was not. Bind restrictive source predicates generically while excluding source-identity restrictions, attributed product terms and explicit nested product subjects.

**Why q068 escaped:** Live website passages were excluded from structured-assertion scope checks. Their table proved that feature names existed, not that a mixed list applied “across the lineup”; the universal-phrase detector also missed that wording. A bounded guard must check every claimed feature against aligned complete table headers and explicit positive cell meanings. Unknown marks, absent legends, conditional cells, malformed alignment and unrelated all-positive rows cannot license universal fitment. This does not create new approved facts or change the source snapshot.

**Audit lesson:** A root review writer used integer override keys against q-prefixed IDs, retaining old rationale text despite new answers and grades. Independent review caught it. Archive the original rationale, correct only the explanations and verify raw hashes; require override keys to be actual current case IDs. No answer or verdict changed.

**Review controls:** Shared word pools could swap front/rear qualifiers between features, and a negated quantifier could hide another positive universal. Require own-row descriptors and independently scoped quantifiers. Apply the guard to every cited claim kind, not only model-labelled facts. Multiple cited tables must share the same canonical trim-header set; never pool different trim universes. Full-validator and saved-source tests preserve ordinary selected-variant descriptions.

## 2026-09-19 — launch intent is not provider dispatch (CR44)

A fallback can log its launch intent and then see a winning primary before it reaches the provider adapter. Silent returns at that boundary leave audits unable to distinguish skipped dispatch from missing completion telemetry. Record an explicit terminal pre-dispatch retirement for each such exit; preserve actual winner/deadline/cost behavior. The controlled zero-adapter-call reproduction explains the historical shape, but cannot manufacture the missing observation retroactively. Preserve that caveat even when trace and usage tails are quiet.


<!-- dated-issue-register:2026-09-19 -->
## Dated issue register — consolidated 19 September 2026

This file now covers93 unique numbered Nexon and Creta issues (NX01–42 and CR01–51), plus a second NX25 observation. The original consolidated register below contains NX01–42 and CR01–44; CR45–51 and the separately identified harness findings follow it. Dates identify the original observation, not a new test. Historical verification limits and open statuses are retained; later five-whys entries and Handoff.MD describe superseding fixes. A proposed correction is never treated as a verified live result. The unnumbered historical five-whys above remain part of this learning record.

### 2026-09-18 — NX01 — Follow-up question discarded as agreement

**Reason / recorded failure:** short prefix-matching treats any short reply starting with yes as confirmation.

**Solution and recorded verification:** fixed; browser regression passes.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX02 — The guide resumes behind a callback form

**Reason / recorded failure:** unknown and dissatisfied paths immediately call resumeAfterQA.

**Solution and recorded verification:** fixed; browser regression passes.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX03 — Questions can advance without an answer

**Reason / recorded failure:** content/flow mismatch and timer-driven turn completion.

**Solution and recorded verification:** Replace countdown completion with explicit response waits and visible typed input; retain turn ownership through transcription, and require explicit Skip/Continue. The later second free Nexon iteration passed14/14 browser controls, including silence/late speech/clarification handling. This verifies mechanics with synthetic input, not physical microphone performance.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX04 — A late transcript can resolve the wrong turn

**Reason / recorded failure:** no turn ownership.

**Solution and recorded verification:** fixed; synthetic late-speech cases after skip/restart pass. Real microphone quality remains untested.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX05 — Clarification and opening interruption lose continuity

**Reason / recorded failure:** clarification is microphone-only; an opening interruption can restart the opening because the route has not been built.

**Solution and recorded verification:** fixed; typed clarification and opening-return browser regressions pass.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX06 — Product is obscured at the first impression

**Reason / recorded failure:** large mascot, blurred product and generic centred text. Long iQube takeaway fills the opening.

**Solution and recorded verification:** redesigned and inspected on desktop/phone with mock content; final Nexon art direction awaits its permitted source pack.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX07 — Slides lack hierarchy and callout lines can point from the wrong place

**Reason / recorded failure:** layout computed while callout hidden; no recompute after reveal.

**Solution and recorded verification:** fixed; reveal geometry and native-aspect wide/narrow browser regressions pass.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX08 — Fallback labels are unfinished fragments

**Reason / recorded failure:** blind word slicing.

**Solution and recorded verification:** fallback fixed and covered by content regressions; new real Nexon deck still needs review.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX09 — Script ignores stated customer context

**Reason / recorded failure:** old script reuse, unavailable runtime personalisation, conflicting schema/prompt wording and unlabelled assumptions.

**Solution and recorded verification:** The later Nexon implementation aligned schema/prompts on one useful intake, removed repeated discovery, prohibited personalized batches after skipped intake, checked quantities against customer context/cited facts, and added grounded check-ins and clarification-only responses. Free content/browser checks establish containment, not full semantic entailment or natural speech. Later actual customer and Creta evidence remain separately dated.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX10 — Input availability and state are unclear

**Reason / recorded failure:** The capture UI exposed listening/transcribing state without a consistently visible typed alternative.

**Solution and recorded verification:** Keep keyboard input available throughout intake and every reply turn; accurate listening/transcribing states and mic-denied recovery must be checked independently of real microphone recognition.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX11 — The customer sees internal sales scoring at the end

**Reason / recorded failure:** the internal dealership/session view doubles as the customer ending.

**Solution and recorded verification:** fixed; final buyer-recap and overlay browser regression passes. Internal session record remains intact; buyer recap uses actual conversation data.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX12 — Plain slides do not deliver the requested cinematic experience

**Reason / recorded failure:** a light gallery with a reserved copy column.

**Solution and recorded verification:** renderer updated with dark image-led composition, white headings, lime anchors, restrained motion and readable evidence rail; intake/dock/conversation retained. During validation, runtime labels could collide with a newly expanded fallback rail, and a global `.overlay` selector collapsed rail height. Fixed with a stable reserved band, unanimated heading bounds, native image geometry and explicitly in-flow evidence items. Mobile image space ends before wrapped evidence. Browser19/19 passed, including all original14 conversation/layout cases; actual Nexon visual review remains pending.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX13 — Rival documents and applicability can disappear before comparisons

**Reason / recorded failure:** non-URL competitor sources were ignored; runtime competitor rows omitted conditions/truth/quote/date, and rejected facts could remain usable.

**Solution and recorded verification:** bounded ingestion/provenance/approval fix passes39/39 source contracts and203/203 deck cases; all live comparisons still require source review and real question evidence. No product claim is approved merely because a provider returned it.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX14 — Cited clearance becomes an unsupported safety assurance

**Reason / recorded failure:** existence of a citation is treated as enough to support an inferred benefit.

**Solution and recorded verification:** corrected through Align before Build 1, but not closed. Raw iteration 2 removes the explicit flood/no-impact promise from plan/script, while its deck again says clearance “clears rough roads easily” and narration infers rough-road margin. Its new registry also restores the unsupported “unladen” qualifier. The frozen raw artifacts retain these failures; current-draft corrections use source review and product APIs. Prompt/context changes, including a later deck-specific change, do not demonstrate reliable generation or a passing live response.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX15 — Rival highlights lose applicability and cannot be reviewed in the Facts card

**Reason / recorded failure:** some high-level C-facts omit conditions present in detailed sources; the Facts card and direct fact endpoints currently enumerate only product facts, so C-facts need file-level audit and have no direct review action.

**Solution and recorded verification:** source audit and direct F/C-fact review support completed before Build 1; approved corrections were applied through product APIs. Positive real comparisons remain BLOCKED by NX19, not established by this source review.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX16 — Generated narration and FAQ infer promises beyond cited facts

**Reason / recorded failure:** boot litres became a suitcase-fit promise; generic engine facts became highway/traffic performance promises; camera and front-sensor trim scope was blended; ordinary specs were called certified; introductory EMI was rounded and lost conditions; the FAQ computed a misleading petrol-to-CNG power drop using different engine columns.

**Solution and recorded verification:** original artifacts preserved and manual Align corrections applied before Build 1. Raw iteration 2 still calls boot volume certified, generalizes five-star ratings across trims, makes CNG sound automatic, drops higher subsequent EMI from a deeper line, and adds handling/overtaking benefits unsupported by dimensions/torque. Its deck independently promises family luggage fit and lower fuel costs. The new finance FAQ preserves the full material offer conditions, which is an improvement; the old cross-engine delta question was not generated, so that case remains untested. Current-draft source, script and deck corrections are applied through the review/API workflow; FAQ corrections receive their own review. This is content recovery, not closure of the durable generation failure. Raw script `issues=[]` and valid citations did not establish semantic accuracy.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX17 — Spoken questions cannot be directly reviewed

**Reason / recorded failure:** the editor and route accepted only narration/closing lines; correcting generated discovery required a full paid rewrite, while unsafe segment outcomes remained in runtime personalization.

**Solution and recorded verification:** bounded direct-question and segment metadata support implemented and used through Align before Build 1, with focused free regressions. No workflow redesign.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX18 — Simplifying an answer removes the torque unit

**Reason / recorded failure:** diesel torque is spoken as “pulling power is 260” with no unit. The number is sourced but the answer is unclear.

**Solution and recorded verification:** plain-language and repair instructions now preserve a complete requested quantity. Raw iteration-2 script and FAQ Q06/Q07 retain 170 Nm/260 Nm and operating ranges; this is a positive generated result before manual polishing. Q07 nevertheless adds unsupported smooth-overtaking/relaxed-cruising prose, tracked under NX16. Live voice delivery and the customer-path question remain unverified here; the issue is not closed solely by manual copy review or mocked speech-seam checks.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX19 — First Build fails at voice and mixes recorded speakers

**Reason / recorded failure:** three observed Sarvam 429 responses tripped the provider circuit, and the build-time fallback chain switched to Gemini despite the selected voice lock. The cache lookup happened after the circuit check, so even an existing selected-voice clip could be skipped. FAQ/filler reuse checked only whether an audio path existed, allowing a second-voice cached path to survive a retry. Gemini calls also produced input-block refusals and a closed-client failure.

**Solution and recorded verification:** selected-voice/cache/rate-limit fix implemented; 27/27 focused contracts pass with fake transports and outbound sockets blocked. Independent review found and closed a locked Google Cloud mock-mode outbound-call gap, covered by a dedicated regression. No further scoped blocker found; the actual iteration-2 Build has not run.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX20 — Re-Read reassigns reviewed fact meaning and drops cockpit evidence

**Reason / recorded failure:** extraction enumerates fact IDs again and its limited revision merge does not preserve the full reviewed record or C edits. Saved slide/callout overrides refer to those numeric IDs without a source-identity conflict check.

**Solution and recorded verification:** the current draft is recovered through source audit and API edits: cockpit evidence is restored, dependent content/references are reconciled, and the stale rating citation is corrected. See iteration-2 `review-edits/applied.json` and the raw review. **Durable identity preservation is not implemented.** A later Read still requires a full reviewed snapshot, source/claim mapping and explicit reconciliation; old patch IDs must not be replayed blindly. The later deck prompt change does not solve this issue.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX21 — Read shows a mascot import warning

**Reason / recorded failure:** The optional mascot path attempted an unavailable import during Read.

**Solution and recorded verification:** The original Nexon record left this warning open; the later Creta optional-media correction restored the path and added the provider-boundary mock guard (CR03). This does not establish mascot or acoustic quality.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX22 — Align cannot directly correct a generated FAQ answer

**Reason / recorded failure:** the bank could be previewed/approved, while answer correction required regeneration, which could repeat unsupported benefits. Four reviewed corrections (Q07, Q10, Q11, Q12) are prepared in `output/nexon-real-evidence/iteration-2/review-edits/faq-patches.json`.

**Solution and recorded verification:** bounded direct-review route and labelled editor implemented. Every cited F/C id must be approved and comparison-eligible; empty/mixed-invalid citations, stale/partial banks and active graph/stage work reject without writes. Saving preserves exact wording/question/hash, clears old audio and clarification/callback metadata, excludes disabled visuals, derives the slide from current script citations, resets FAQ approval and invalidates voice/rehearsal/bundle while retaining the reviewed bank. Independent free gate: **41/41** API/cache contracts; actual FAQ voice helper also preserves reviewed text/hash through mocked synthesis and locked-cache reuse. All four real corrections are applied and read back exactly; Q12 was edited and saved through the labelled Studio form with initial textarea focus confirmed. Full keyboard-only navigation was not exercised. All six cards were approved individually; Build 2 has not run. Valid citations do not prove meaning: the edit still requires human source/scope review. This closes the missing editing mechanism at code/contract level, not the generation failures in NX14/NX16 or real customer acceptance.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX23 — Mobile labels hide but their leader line remains

**Reason / recorded failure:** Mobile layout hid callout labels without hiding their associated leader lines.

**Solution and recorded verification:** Hide or recalculate the leader with its owner; retain mobile layout regression and distinguish free visual checks from real customer playback.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX24 — Runtime Q&A routed through an obsolete script copy

**Reason / recorded failure:** The reviewed script was correct, but /run/qa read stale raw deck-line citations. An obsolete cabin deeper-line citation made a correct boot answer stay on the cabin slide; Preview and bundle already hydrated from the current script.

**Solution and recorded verification:** Hydrate saved slide design from current script lines/deeper citations through slides_with_script before bank or live routing. Do not mutate saved deck design. Actual-function regressions cover boot jump, correct stay, decline and no deck/script writes; the full earlier NX24 five-whys remain the authoritative detailed record.

**Source record:** `Learning.MD`.

### 2026-09-18 — NX25 follow-up — Full mobile qualifier overflows its evidence card

**Reason / recorded failure:** The personalized frontend formatter clipped complete qualifiers and reused the current image when no topic-specific visual was supplied; narrow cards also failed to expand.

**Solution and recorded verification:** Preserve complete labels/qualifiers and authoritative visual references, omit unsupported imagery, and let mobile cards accommodate wrapped evidence. Original and follow-up browser regressions are retained; no false acoustic pass.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX25 — Personalized boot evidence clipped its scope and inherited a cabin picture

**Reason / recorded failure:** The personalized frontend formatter clipped complete qualifiers and reused the current image when no topic-specific visual was supplied; narrow cards also failed to expand.

**Solution and recorded verification:** Preserve complete labels/qualifiers and authoritative visual references, omit unsupported imagery, and let mobile cards accommodate wrapped evidence. Original and follow-up browser regressions are retained; no false acoustic pass.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX26 — Slow customer provider work blocked cached media

**Reason / recorded failure:** Synchronous provider work on the request event loop delayed unrelated audio/media delivery.

**Solution and recorded verification:** Run blocking provider work outside the event loop and verify cached-media concurrency; keep API latency separate from audio delivery timing.

**Source record:** `Learning.MD`.

### 2026-09-18 — NX27 — Session clock continues after Stop and Done

**Reason / recorded failure:** session snapshots used Date.now even after Stop, with no timing cutoff.

**Solution and recorded verification:** freeze elapsed/current-slide dwell at first handoff, retain it through repeated Done/pagehide, and exclude inactive time when the customer explicitly returns. Restart resets the cutoff. Historical failed-run records remain intact. The refreshed browser contract passed30/30 for the primary paths; review subsequently extended an existing case to cover the top Pause/Resume return path. The final refreshed browser run verifies that extension:30/30 (`browser-30-contract-final.txt/png`). No source/data/provider changes or additional Build.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX28 — Correct answer slide appears without a spoken transition

**Reason / recorded failure:** Legacy Q&A routing changed the slide without a conversational transition before the answer.

**Solution and recorded verification:** The historical fix used an existing cached transition with cancellation and exact-return ownership. Later CR29 deliberately removes the redundant bridge for runtime-v1 direct answer delivery to avoid extra delay; legacy behavior remains separately documented.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX29 — Typed replies re-enabled ambient microphone capture

**Reason / recorded failure:** automatic `waitFor` listening ignored the customer's chosen reply method.

**Solution and recorded verification:** a typed input event or submit cancels current capture and chooses typing; all subsequent waits and Restart keep that preference. An explicit regular or intake mic tap restores voice mode. Initial spoken behavior, visible mic controls and permission policy remain unchanged. integrated with NX27/NX28; final refreshed CUA passes30/30. Actual B typed intake/Q&A and35.5-second clarification hold kept the mic closed; explicit real spoken input remains unverified. No provider call, source edit or third Build.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX30 — Live comparison response truncates before its citations

**Reason / recorded failure:** Gemini returned only a 170-character JSON prefix ending “whereas the Venue HX10 turbo petrol DCT lists a 3”, with no complete answer or fact_ids field. Its schema validation failed; Claude lacked credits and Runware timed out, so the customer heard a decline after 22.0 seconds.

**Solution and recorded verification:** implementation saved; the isolated deck gate passes 211/211 including all five new regressions. The actual focused rerun is pending. No extra Build or paid call belongs to this patch.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX31 — Concurrent Gemini cold initialization can close the active transport

**Reason / recorded failure:** Concurrent cold Gemini initialization could replace and close a transport already used by another call.

**Solution and recorded verification:** Synchronize cold client initialization and retain the active client; exercise concurrent calls with fake transports before relying on live recovery.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX32 — A stated traffic need becomes a decline and is absent from the buyer profile

**Reason / recorded failure:** trace392 is a valid Gemini response with `answered=false` and no citations after9.784s; the player gives its generic unknown-answer/callback response. This is a semantic model decline, not a provider outage. The need survives in transcript, questions and summary, but the saved profile still has empty name/why/followup/focus. Consequently the buyer recap omits “What matters to you.” The distinction matters: context was not lost everywhere, but it was not retained in the structured path used by that recap.

**Solution and recorded verification:** **targeted recovery verified.** Browser32/32 passes; actual C2 `s_mu74vi17dltu` retains the traffic statement once in profile.followup and the buyer recap, and answers with sourced gearbox options without promising stop-and-go assistance. The prompt does not guarantee semantic correctness. Neutral Browse and honest refusal alone still do not establish relevant guidance; preserve the failed C run and both completed Build attempts.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX33 — Internal follow-up summary promises unavailable price and EMI details

**Reason / recorded failure:** The summary model proposed an opener promising quote/finance details even though the same session marked those requests unresolved.

**Solution and recorded verification:** Enforce a neutral invitation to discuss outstanding questions independently of model wording; keep unanswered fields and the original failed session intact.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX34 — Personalized spoken proof invents a policy relation and practical benefits

**Reason / recorded failure:** Personalized prose inferred policy relationships, practical benefits and equipment locations beyond the cited assertions.

**Solution and recorded verification:** Preserve literal reviewed facts and mandatory qualifiers; reject unsupported policy/benefit relations and retain original failed responses. Later clause-level runtime guards provide additional bounded controls, not general semantic proof.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX35 — Background session summaries lack demo-scoped usage accounting

**Reason / recorded failure:** Background summary work ran without the demo/stage usage context, leaving its cost unattributed.

**Solution and recorded verification:** Capture and restore demo/stage context in the worker; preserve real repeated-call costs and test attribution.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX36 — Long live waits include reasoning exhaustion and fallbacks

**Reason / recorded failure:** default hidden reasoning shares the JSON output budget; TTS and transition also add delay.

**Solution and recorded verification:** explicit LOW thinking for live QA on supported Gemini3.8Flash; unchanged full facts, budget, models/order/timeouts. Other calls/unknown overrides unchanged. Provider48/48 passes; actual matched final sample pending. Do not describe filler or bank hits as faster reasoning.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX37 — Generic title words create a fictitious safety preference

**Reason / recorded failure:** title word “with” matches the input, yielding focus=[safety]; trace335/TTS338 and transcript call it the buyer's “main priority.” B2's malformed trace376 proposal is not evidence of delivered recurrence.

**Solution and recorded verification:** canonical topic/chip phrases and narrow topic aliases, no title-token matching; computed focus is explicitly a route hint distinct from raw statements. Actual-function regression4/12→12/12. Actual new B preference/pitch check pending. Direct warranty/comparison prompt scope was also tightened; delivered quality requires the predeclared sample.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX38 — Deeper narration shows stale answer source labels

**Reason / recorded failure:** D1 caption says CNG321L/ISO V215 while dock retains cabin F020/F021.

**Solution and recorded verification:** line-owned citations in deeper playback; empty citations on question/transition/check-in states, with run ownership for fillers. Actual synthetic browser32/33→33/33. Proof/deeper exact return itself passed in the real muted session; the label defect is kept separate and awaits the brief real post-fix check.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX39 — QA asks for a configuration already defined as the demo comparison example

**Reason / recorded failure:** trace439 asks “Which specific Venue variant are you comparing with?” The intake only names Venue/Brezza, and the model input contains many rival trims. C7-001 proves the regular HX10 turbo-petrol seven-speed DCT pairing but does not mark it as the chosen demo example. The unique mapping exists in current plan.notes and was omitted from QA; settings have no selection field and bundle.pitch omits those notes too. This is a context-delivery gap, not proven disregard of a supplied unique selection.

**Solution and recorded verification:** code/input contract fixed39/44→44/44; actual confirmation pending. No new selection field, source mutation, provider, Build or deterministic semantic-resolution claim.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX40 — Model recommendation becomes an unrequested selected action

**Reason / recorded failure:** Direct `r.cta`→`ctaFlow` forwarding and substring choice matching treated a model recommendation as the customer's selected action.

**Solution and recorded verification:** Show an optional proposal chip; require an exact, explicit choice of a known CTA in the current run, with honest optional-contact wording. Actual free browser checks improved33/36→36/36. The historical record marked actual recovery pending; this register does not create a new live pass. Evidence: completion-audit/nx40-cta-consent.md and L4-unrequested-cta-recap.*.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX41 — Warranty relation contradicts a cited explicit unknown

**Reason / recorded failure:** Citation validity checked that evidence existed, but did not validate whether the warranty relationship contradicted that evidence.

**Solution and recorded verification:** Reject the explicit policy contradiction before voice and use the ordinary honest limit/callback response, without labelling it a provider outage. Fake real-QA regressions passed12/12 after initial3/10 and an independent11/12 bypass finding. The guard covers bounded English patterns, not general entailment. The historical live recovery remained pending; original speech is retained.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-18 — NX42 — Final summary exhausts its structured-response budget

**Reason / recorded failure:** The summary used default hidden reasoning inside its1200-token output budget. Changed ended-session records could also launch duplicate workers or allow a stale worker to overwrite a newer record.

**Solution and recorded verification:** Set explicit LOW reasoning through the existing adapter while preserving the schema, budget and provider order. Revision hashing and worker coalescing prevent stale attachment to a changed record within the local process. Cross-process coordination remains a limitation. The original issue's bounded-repair confirmation was pending; later evidence remains separately dated in the five-whys/history. Duplicate historical calls and costs are retained.

**Source record:** `docs/issues/2026-09-18-nexon.md`.

### 2026-09-19 — CR01 — crawler crossed the market/model boundary

**Reason / recorded failure:** loose model-token matches plus no inherited locale boundary.

**Solution and recorded verification:** fixed and replayed. Exact model path and inherited locale checks kept the next two discovery runs within India Creta pages. Original run evidence remains in stage progress and coverage.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR02 — readiness sent an oversized realtime audio frame

**Reason / recorded failure:** the one-second probe was rejected with `chunk_too_large`; the provider accepts ten smaller frames. Real browser frames were already small.

**Solution and recorded verification:** pace/split the probe into small frames, defensively bound adapter frames, retain a redacted actionable error. fixed. Repeat preflight observed reasoning 1,819 ms, selected-voice stream 895 ms and bounded STT probe 1,585 ms. Three subsequent synthetic customer recordings retained family/boot intent, EMI inputs and a comfort/seats correction. Physical microphone and echo behavior remain untested.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR03 — mock mascot path could reach a real provider

**Reason / recorded failure:** pre-existing image-generation code lacked a mock guard; the repaired import exposed it. Some intermediate logs show SDK activity. Deleted temporary trace stores prevent exact reconstruction of every attempt.

**Solution and recorded verification:** guard both image-generation entry points; regression replaces the provider client with a raising stub. Final free gates additionally block outbound sockets and recorded zero attempts. fixed. Preserved evidence and accounting limits are under `output/creta-runtime-2026-09-19/mock-guard-audit/`.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR04 — calculator could borrow an unrelated unit

**Reason / recorded failure:** broad quoted text could pair a five-year warranty with an unrelated months unit, or treat a monthly percentage as annual.

**Solution and recorded verification:** bind each numeric occurrence to adjacent units; require explicit annual/monthly/per-litre basis; preserve lakh/crore scale. fixed; regression covers the failure and zero-interest EMI/fuel calculations.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR05 — stale transcription after microphone restart

**Reason / recorded failure:** session/turn IDs did not distinguish two microphone capture generations.

**Solution and recorded verification:** generation IDs on capture commands, PCM, ready events, transcripts and failures; ignore stale generations at both ends. implemented with transport/client regressions; real acoustic acceptance still pending.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR06 — brochure layout inflated and fragmented the feature matrix

**Reason / recorded failure:** pypdf's layout mode expanded pages 13/14 to approximately 295k/261k characters, mostly spacing. Combined with the identical linked brochure, this produced 27 extraction batches and split column context. Read was stopped before publication.

**Solution and recorded verification:** bounded coordinate-preserving PDF text extraction, preserved raw table cells, deduplicated identical uploaded/linked document content and versioned extraction separately from the original source hash. extraction replay passed. The brochure is approximately 48k characters; both PDFs fit three evidence batches rather than duplicating the brochure. All sources together create eight batches. Original PDFs remain unchanged. The next model call exposed CR07 before factual publication.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR07 — Gemini's legacy schema converter rejected flexible fields

**Reason / recorded failure:** `response_schema` uses a legacy schema converter that rejects dictionary properties. The new evidence scope and delivery metadata contain dictionaries. Readiness's simpler schema did not exercise this shape.

**Solution and recorded verification:** send the model's JSON Schema through `response_json_schema`, preserving constraints and validating the response with Pydantic. Separate build routing now tries Gemini first for text-only calls; explicit runtime routing and media calls keep their contracts. SDK wire regression 4/4; real extraction completed in eight batches and produced 203 candidate assertions. Later factual review is recorded in CR11. Official API reference: https://ai.google.dev/gemini-api/docs/generate-content/structured-output.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR08 — edited assertion retained a published identity

**Reason / recorded failure:** edits could change the meaning associated with an existing ID.

**Solution and recorded verification:** copy on meaningful edit, preserve lineage and old snapshots, reject edits through retired IDs, invalidate downstream approvals and update chat edit references. A no-op leaves identity unchanged. identity/scope regression 17/17 and existing Align regression 47/47.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR09 — real draft remained technical and generalized engine choices

**Reason / recorded failure:** opening narration included dimensions and a parametric grille; the summary introduced cylinder counts; an engine line suggested every engine had both manual and automatic options. The turbo has its own automatic pairing. Some questions assumed a customer's commute or technical knowledge. FAQ Q02 added an unsupported stopping-performance benefit to equipment facts.

**Solution and recorded verification:** preserve the first draft, repair evidence before rewriting, add concrete authoring examples and everyday-register warnings, and review the second story before voice generation. Equipment is not a demonstrated performance outcome. two model drafts reviewed; a final explicit edit corrected main narration, all 18 deeper lines, seven FAQ answers and slide labels. Three useful check-ins replace seven repetitive prompts. The authoring validator now permits this cadence. Playback acceptance remains separate; no first-draft bundle was published.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR10 — precise trim lists did not match individual trim questions

**Reason / recorded failure:** an explicitly listed scope such as `King, King Knight` was treated as one variant name. Requests for King could miss valid evidence.

**Solution and recorded verification:** safely split comma/semicolon variant lists and match exact alternatives. Opaque ordering such as `SX and above` is not expanded. knowledge 36 and runtime 51 checks pass, including preventing King evidence from leaking into E queries.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR11 — source disagreements and interleaved table quotes required review

**Reason / recorded failure:** website FAQ claimed the turbo displacement was 1497 cc; the supplied manufacturer brochure states 1482 cc. A compiled-guide FAQ said six airbags in most variants, while the manufacturer's matrix states standard equipment. These differently worded claims did not enter the strict automatic-conflict matcher. Some accurate engine facts were held because generated quotes stitched together noncontiguous cells.

**Solution and recorded verification:** visually checked the manufacturer engine table; replaced nine quote/locator pairs with a literal excerpt preserving all three headers; rejected the two conflicting FAQ assertions. Reviewed all-variant airbag/ISOFIX scope, parking-assistance scope and the wireless adapter footnote. Meaningful corrections received new assertion IDs. India market scope uses the publisher/footer and byte-identical official India brochure, not a guessed model year. curated through Align APIs; `ingestion-audit/applied-curation.json` and `india-scope-review.json` preserve the ID mappings. Zero automatic conflicts must not be presented as proof of no semantic disagreement. The first draft is preserved privately for comparison.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR12 — captions could masquerade as successful answer audio

**Reason / recorded failure:** a speech failure's caption fallback stamped first audio; server/browser timestamp mixing could also distort latency.

**Solution and recorded verification:** caption failures retain missing audio timestamps and failed-delivery state. Answer timing uses one browser clock; server receipt is separate provenance. Stale endpoint timestamps cannot leak into a later utterance. client 46/46 and muted mock browser 17/17. Real browser cohort replay pending.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR13 — CTA labels and locked persona did not match their behavior

**Reason / recorded failure:** the planner named a male Karan persona despite locked Priya speech. Download Brochure and Locate Dealer pointed at the product homepage, and the player ignored configured URLs.

**Solution and recorded verification:** enforce the selected voice's persona identity, supply real source-discovered action URLs, and honor safe external links through explicit customer interaction. No automatic form submission. locked identity and three real destinations confirmed in the second plan; player CTA regression 39/39. Official brochure, dealer finder and Creta test-drive destinations returned HTTP 200 on review. Real customer replay remains separate.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR14 — reconnecting to Align hid the running stage

**Reason / recorded failure:** entering Align during a revision showed no progress. The client ignored the SSE hello snapshot; its polling condition looked for an absent overlay even though the overlay always exists in the DOM.

**Solution and recorded verification:** restore current stage progress at entry and reconnect, hide it on completion, and poll while visible. Ignore historical completion events rather than navigating from stale history. full Align module/SSE client contract 9/9; Codex browser reload displayed live FAQ progress and returned to the review screen on completion.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR15 — a multi-variant comparison could overstate shared equipment

**Reason / recorded failure:** a pure validation probe accepted “Both E and King have a panoramic sunroof” using a King-only fact. The comparison filter found an intersecting scope but did not prove the universal wording.
- Related failures: an empty answered decision could show a limitation while retaining answered=true; the first provider could consume the entire turn deadline, preventing timeout fallback.

**Solution and recorded verification:** implemented before the real batch; runtime 75/75 and provider 60/60. Explicit unlisted trim corrections clear stale scope; unknown model years stay restrictive; the first provider leaves fallback time; empty decisions are unanswered. Further actual-answer defects are tracked below.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR16 — an affirmative reply skipped requested detail

**Reason / recorded failure:** a curated question offered a closer look, but the existing player mapped “yes” to Continue. The static model scorecard missed this semantic mismatch.

**Solution and recorded verification:** three confirmation questions now mean yes=continue/no=more detail; authoring prompts, schema guidance and a warning enforce that convention. No new interaction type was introduced. speech-style 27/27; bundle v2 has three recorded, corrected prompts and zero author issues. Overview duration is 11.25 seconds; main narration and prompts total 131.5 seconds before customer pauses/deeper answers.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR17 — review overlays survived navigation

**Reason / recorded failure:** navigating from an open Align script preview to the customer player left the detached preview covering the player.

**Solution and recorded verification:** Align owns and removes its detached previews, editors, lightbox and Escape handlers on navigation. actual read-only muted browser replay passed; Align progress 9/9 remains green. An initial test selector error and a run attempted during the blocking Build overlay were corrected before the completed replay.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR18 — real Explore fallback delayed the selected tour

**Reason / recorded failure:** the real planner returned in 4.038 seconds with no personalized segments, two custom batches and a 43-word decision frame. After the requested overview, the player prepended roughly 45 seconds of additional narration before showing the chosen route.

**Solution and recorded verification:** first browser batch preserved; four controlled overview interruptions passed, then the journey timed out. Backend live delivery and player fallback are corrected; 18 pitch delivery contracts and 47 legacy grounding controls pass. The actual replay is pending; increasing the test timeout alone is not a fix.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR19 — calculation and qualification guards harmed valid answers

**Reason / recorded failure:** the calculator produced correct EMI values, but nearest-rupee phrasing was rejected; caveat-only remnants still counted as answers. A zero-interest calculation succeeded but the model returned no sentences. Some rejected introductory clauses also removed the scope needed by a surviving feature list.

**Solution and recorded verification:** original 100-question baseline retained. Bounded numeric rounding, verified calculation rescue, meaningful-answer flags and condition-preserving validation are implemented in the 127-case runtime contract. Actual repeat quality remains pending; mechanical citation checks alone are not semantic acceptance.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR20 — mobile evidence overflow lacked a visible cue

**Reason / recorded failure:** three-card evidence strips showed almost no hint that another card was offscreen on a narrow viewport.

**Solution and recorded verification:** show a directional swipe cue only for measured horizontal overflow, retaining image and card dimensions. all 12 slides reviewed at desktop and mobile widths; five mobile cues, none on desktop; player browser contract 40/40.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR21 — the local runtime timeout became an invalid Gemini server deadline

**Reason / recorded failure:** the second browser attempt received a Gemini 400 before generation: its manually set seven-second server deadline was below the allowed ten-second minimum. Claude then reported insufficient credit and Runware timed out. The original first-provider budget regression used fake transports and missed this SDK behavior.

**Solution and recorded verification:** explicitly supply a server deadline of at least ten seconds while preserving the shorter local HTTP timeout and the graph's twelve-second total deadline. A single runtime attempt also disables the SDK's internal five-attempt retry default.
- Evidence: the installed Google SDK automatically derives `X-Server-Timeout` from the HTTP timeout unless explicitly set; its [upstream implementation](https://github.com/googleapis/python-genai/blob/main/google/genai/_api_client.py) documents the same behavior. Eight serialization/wire contracts now include real SDK requests through a fake HTTP transport, subsecond/seven/twelve-second budgets, and a one-request 503 case. The real local7/server10 probe succeeded in 1.912 seconds; full replay remains pending.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR22 — valid citations did not bind every feature, polarity or unit

**Reason / recorded failure:** independent deterministic probes accepted a positive feature inside an uncited limitation clause, an unrelated feature under a negative trim projection, and 253 PS supported by a 253 Nm torque assertion. Follow-up probes also found positive safety assertions licensing their negative inverse, or an airbag count being borrowed for a gearbox count.

**Solution and recorded verification:** bind negative projections to the named feature, reject clause continuations that introduce uncited claims, and validate feature families, polarity and measurement units/counts. These are bounded guards, not a general proof of semantic entailment. 127 runtime and 42 knowledge contracts pass. All 22 original and six supplemental adversarial controls were independently rechecked. These probes are not 28 additional failures observed in QA100, and do not establish universal semantic correctness.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR23 — stopping the overview cancelled background personalization

**Reason / recorded failure:** the second browser attempt's overview interruption called the session-wide cancellation path while the HTTP Explore plan was still pending. The browser deliberately retained its planning promise, but the backend cancelled that work, leaving an accepted-only checkpoint.

**Solution and recorded verification:** separate stopping current delivery/QA from cancelling an unrelated background Explore plan; new context, replanning and session closure must still supersede stale work. separate planning/QA ownership and a latest-accepted-turn checkpoint fence pass nine actual graph/socket controls. An ordinary question preserves valid background planning, while refinement and ending the session cancel stale work. A late plan cannot overwrite the latest question checkpoint or start browser narration. This is independent of CR21; the null plan cannot be attributed only to provider availability.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR24 — approved conflicting assertions survived source review

**Reason / recorded failure:** focused q067 spoke 1497 cc for the turbo engine from uploaded F056, despite the original manufacturer table's reviewed F230 stating 1482 cm³. It made no lookup despite the explicit URL request. Exact-claim matching had missed the compound FAQ label. The audit also found an unqualified seven-variant count, a misleading all-standard 70+ safety count and a memory claim whose quote only supported power adjustment.

**Solution and recorded verification:** reject F056/F048/F076/F126; retain their historical evidence. Replace ambiguous website F123 with F246, explicitly identifying the manufacturer brochure's 17-inch **spare** wheel. Remove obsolete dependent citations, review all remaining references, and publish immutable snapshot `kb_c70af9b392163108dee4eb7a` as bundle v3. Existing narration, slides and recordings are unchanged; deterministic assembly made no paid calls. Old v2 and its snapshot remain preserved. This is a corrective publication beyond the two authored iterations, not a third generated story.
- Prevention: narrow dimensional conflict detection compares explicit same-engine cc/cm³ assertions across compound claim labels. Conflicting uploaded material remains reviewable; nominal engine names and unrelated quantities do not trigger this rule. Explicit supplied-URL checks dispatch the bounded lookup before model reasoning. Saved-decision tests preserve the actual failure.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR25 — scope and projection guards lost supported answers

**Reason / recorded failure:** Scope parsing and applicability projection discarded valid exact trim facts and conservative limits while trying to prevent unsupported combinations.

**Solution and recorded verification:** Preserve reviewed exact scope and qualified comparisons without expanding opaque trim ordering. Saved-draft and actual-question regressions distinguish retained useful facts from still-invalid claims.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR26 — the completed safety journey still declined available ADAS evidence

**Reason / recorded failure:** the full safety route reached recap, but its required question failed; “variant conditions” was parsed as a trim named conditions. The run remains12/13, not a pass.

**Solution and recorded verification:** generic scope nouns cannot become trim names. Empty/rejected factual drafts get at most one bounded composition repair, retaining the same evidence, language, profile, validator, cancellation and12-second deadline. Exact unknowns remain distinct from unrelated known facts. Drafts cannot use repair to request more tools or a CTA. offline regressions and independent review precede the paid targeted replay. The third complete100-question result remains75supported/18partial/6unhelpful/0unsafe flagged/1providerfailure until a separate cohort is reviewed.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR27 — declines were not a useful-answer latency cohort

**Reason / recorded failure:** the failed safety answer's2.585-second playback start was a decline; aggregation did not keep it separate from answers. Its long acknowledgement also occupied unnecessary time.

**Solution and recorded verification:** explicit answer/clarification/decline/legacy cohorts, truthful answer-playback labels,250ms acknowledgement grace and shortest compatible reviewed clip. Correctivev4 recorded only “Let me check that.” in Priya's voice (1.365s); existing story/media remained unchanged. metrics15/client56/player41 free checks pass. New real acknowledgement and successful answer timings remain to measure; no physical microphone claim.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR28 — explicit brochure fitment and lookup passage relevance

**Reason / recorded failure:** held sunroof evidence and vague higher-variant camera wording left basic E/EX questions unhelpful. Web extraction ranked navigation/FAQ questions too highly; an initial filter then overreached on answer paragraphs ending with a question.

**Solution and recorded verification:** visually verify exact manufacturer matrix cells and guide legend, publish newF247/F248 assertions as correctivev5 with181approved facts and immutable history. Prefer answer-bearing passages, retain full exact quotes and tokenize hyphenated model URLs consistently. No trim absence inferred from ordering. fitment6/6 and lookup13/13 isolated controls. All existing citations remain approved and all narration/slides/audio are identical across the fitment publication.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR29 — unnecessary transition audio and precise answer limits

**Reason / recorded failure:** the successful ADAS probe returned text in2.271s, then played a2.442s generic jump bridge before requesting answer speech. The35-case focused replay also lost “SX trim and above” scope, specific economy/warranty/model-year uncertainty, and spent12s on an unsupported file-URL request.

**Solution and recorded verification:** runtime-v1 jumps show evidence and start the substantive answer directly, with exact return/cancellation/wait preserved. Scope matching permits a grammatical trim/variant insertion without inferring ordering. Safe source-absence wording becomes a precise personal verification limit; unrelated tank facts cannot substitute for economy. Explicit local-file source requests bypass paid reasoning. A repaired refusal cannot erase a surviving useful factual answer, and source-check suggestions cannot license uncited claims. offline repair106/graph130/trace36 and actual DOM44/client56 pass; independent review precedes a fresh live100-case cohort and one bounded audio probe. Prior results remain retained.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR30 — flattened website wheel rows conflicted with manufacturer fitment

**Reason / recorded failure:** q039 in the fourth full QA100 used approved F120 to offer EX(O) ordinary steel-with-cover road wheels alongside styled road wheels. The manufacturer explicitly assigns ordinary road wheels to E/EX and styled road wheels to EX(O); the separate EX(O) ordinary steel entry is a spare wheel.

**Solution and recorded verification:** source-only v6 allocates F249/F250/F251 from visually checked manufacturer page 15, separating road and spare roles and exact named trims. All story/media/citations remain valid and unchanged; old snapshots and original failed answers are retained. No paid regeneration.
- Related critical scope failure: q047 correctly mentions the Pune FAQ's SX(O) listing, then borrows VSM/rear-disc equipment from a Lucknow source without verified lineup equivalence. New F252 preserves the truthful listing with an explicit applicability limit. Runtime borrowing prevention is under independent review; same-source attributed safety facts are not automatically false. source publication complete; live repaired-answer verification pending. Fourth QA100 remains 83/9/3/2/3, not relabelled after correction.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR31 — exact unknowns and conditional comparisons were lost

**Reason / recorded failure:** connected-car repair omitted the Echo purchase requirement, a two-trim wheel sentence pooled inapplicable citations, and model-year uncertainty was stripped while an unsupported future/current premise survived. A guarantee-plus-EMI question only asked inputs. These actual drafts remain fixtures.

**Solution and recorded verification:** precise required-condition feedback for the existing single repair; independent validation of comparison clauses; direct unknown preservation; a safe first-person refusal before one waiting clarification. Source-specific trim matching excludes invalid anchors and rejects positive current-lineup claims. The literal transmission-only suffix is retained as a material condition.
- Checks: actual-cohort54, repair106, graph130, trace36, knowledge56; independent seven-control graph review; required deck320/accept24/both smoke with blocked sockets. Live post-fix verification remains separate. General semantic entailment, all future table extraction and physical voice behavior are not proved.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR32 — useful repair clauses and mandatory device conditions

**Reason / recorded failure:** A partly invalid optional repair discarded useful supported sentences; alternate citations could also lose the mandatory device-purchase condition.

**Solution and recorded verification:** Keep independently revalidated repair subsets only under the preservation rules, bind own limits safely, and carry same-evidence positive prerequisite witnesses. No cited row grants unrelated benefits.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR33 — precise limits, lineage metadata and qualified projections were over-rejected

**Reason / recorded failure:** Precise uncertainty was handled as an uncited world claim; uncertain source-specific trim identity and qualified projections were also over-rejected.

**Solution and recorded verification:** Separate question-bound own limits from factual assertions, retain source-specific lineage metadata, and preserve literal selected-trim qualifications without inventing current-lineup equivalence.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR34 — repeated known credit failure consumed fallback time

**Reason / recorded failure:** full100 traces show repeated Gemini timeouts followed by explicit Anthropic insufficient-credit400 errors, consuming0.4–0.7s each before Runware. Several Runware attempts then timed out within the remaining3.3–4.5s.

**Solution and recorded verification:** short process-local cooldown for the observed non-retryable balance failure, with explicit trace provenance, expiry and credential/model identity isolation. Preserve configured provider order, ordinary transient retries and whole-turn deadline. No purchase, credit change or deadline extension. eight free controls passed and c7ec71a exercised the cooldown after a real credit failure. A later Runware call completed, but validation rejected its content. This proves the skip occurred, not useful answer recovery or a latency percentile gain.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR35 — completed calculations and valid answer details were discarded

**Reason / recorded failure:** Final model composition exhausted the shared deadline after a successful calculation, while strict relation/quantity checks removed valid requested details.

**Solution and recorded verification:** Reserve validation time and permit only a completed audited calculation to survive failed composition. Preserve supported exact quantities, scope and useful limits; never revive failed tools, cancelled turns or expired work.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR36 — clause ownership caused both unsafe claims and over-rejection

**Reason / recorded failure:** Validation borrowed predicates, negatives or scope from elsewhere in a multi-clause answer; conversational text shared the same permissive paths.

**Solution and recorded verification:** Check ownership within the actual clause, distinguish fact-free interaction from product assertions, and reject ambiguous semantic relationships conservatively. Keep actual saved-draft positive and negative controls.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR37 — cross-fact pairing, source coverage and operational fallbacks

**Reason / recorded failure:** Individually true features did not prove their combination, exact lists did not prove relative ranges, and selected passages did not prove entire-source absence.

**Solution and recorded verification:** Require joint assertion scope, preserve literal range provenance, reject unsupported source-coverage claims, and keep operational failures distinct from knowledge gaps. Provider races retain one winner and attributable late cost.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR38 — ordinal scope and conversational acts

**Reason / recorded failure:** Ad hoc free-form conversational exceptions could discard helpful interaction or bypass factual validation; ordinal/count patterns lost feature ownership.

**Solution and recorded verification:** Use closed, question-bound interaction acts with no arbitrary facts/citations; retain clause-owned exact scope and independently validated numerical modifiers. EMI completion may add only missing audited assumptions.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR39 — useful boundaries, safe clarification prefixes and feature-count binding

**Reason / recorded failure:** Safe own-limit prefixes and bounded feature-count paraphrases were rejected or lost when conversational acts and facts shared validation paths.

**Solution and recorded verification:** Preserve independently validated limits before one typed question; bind counted feature modifiers; retain all prior failed responses.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR40 — exhausted fallback window and discarded refusals

**Reason / recorded failure:** Sequential provider timeouts left too little usable time for fallback; missing closed boundary acts also discarded helpful refusals.

**Solution and recorded verification:** Keep the default provider order and bounded deadline, test configurable early overlap separately, and add question-bound lender/evidence limits. Recovery adds cost and is not a general latency pass.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR41 — repaired source-pronoun absence escaped validation

**Reason / recorded failure:** Source absence validation lost ownership across a coordinated pronoun; a valid boot-measurement limit was also removed.

**Solution and recorded verification:** Bind the source antecedent conservatively and add a closed, question-bound capacity/measurement limit; retain the source-policy distinction.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR42 — comma ranges, source pronouns and asymmetric digit grouping

**Reason / recorded failure:** Clause splitting detached comma-coordinated ranges, source-pronoun binding used a small verb list, and digit grouping was normalized asymmetrically.

**Solution and recorded verification:** Preserve relative range ownership, bind source pronouns independently of positive reporting verbs, normalize quantity typography symmetrically, and retain specific dealer/evidence limits.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR43 — remaining source-only and universal live-table claims

**Reason / recorded failure:** A source-only restriction escaped through a new reporting verb; live table feature names were mistaken for universal fitment proof.

**Solution and recorded verification:** Validate restrictive source ownership and require own-row descriptors, complete aligned headers, equal trim sets and explicit status meanings for universal live-table claims. Final unchanged100 scored95 supported/5 partial/0 unsafe; unknown wording remains conservatively rejected.

**Source record:** `docs/issues/2026-09-19-creta.md`.

### 2026-09-19 — CR44 — missing terminal event at pre-dispatch fallback retirement

**Reason / recorded failure:** Three stop/budget returns after a launch-intent trace could exit before calling the provider adapter without recording a terminal event.

**Solution and recorded verification:** Emit exactly one skipped_before_dispatch event with dispatched=false on those existing branches. Free race/configuration checks and independent AST comparison preserve dispatch behavior; the historical missing terminal remains an inference, never rewritten.

**Source record:** `docs/issues/2026-09-19-creta.md`.


## 2026-09-19 — CR45 — Planner and Author shared story design, producing repetitive delivery

- Date: 2026-09-19, night session.
- Where: `server/agents/plan.py`, `author.py` and their shared prompt inputs; reusable CRETA script preparation before Align.
- Observed problem: Planner selected the segment structure while Author also received `PITCH_SHAPE` and `PROOF_BLOCK`. Existing plan goals often named an equipment category rather than the intended story beat, and `plan.notes` did not reach Author. The resulting division of work encouraged a second itinerary and repeated feature-list openings. In the first session candidate, five successive proof/feature blocks ended with a visit/try/check instruction; this was independently identified and revised before publication.
- Expected: Planner chooses a concrete, supported buyer story, evidence emphasis and literal images. Author turns that outline into connected speech, retaining independent proof stops and all material evidence conditions.
- Severity: customer-experience quality and role clarity. This is not a demonstrated runtime-provider, source-accuracy or acoustic failure.
- Cause: overlapping prompt ownership plus a thin planning handoff. A requirement that every line stand alone encouraged conversational resets; fit-checks became a repeated substitute for an unsupported benefit. This is a code-and-artifact diagnosis, not a controlled causal experiment.
- Implemented solution: Planner now owns three supported reasons to explore, segment ordering, spoken/deeper evidence, visual subjects and handoffs using the existing `goal` field. Its prompt receives `PITCH_SHAPE` and `PROOF_BLOCK`; it does not write final segment dialogue. Author receives those goals and `plan.notes`, uses separate `AUTHOR_CRAFT`, and preserves the planned IDs/roles/order while writing the final spoken delivery. A local rewrite preserves unaffected grounded lines. No new schema, graph node, provider or publication route was introduced.
- Candidate correction: final speech explicitly distinguishes non-turbo petrol/diesel gearbox choices from turbo automatic-only; cockpit, gearbox and music blocks no longer all end in a future visit instruction. Personal seat/luggage checks remain where useful. Unseen engine, child-anchor, app and policy claims use no literal image rather than borrowing unrelated pictures.
- Verification: `evals/narrative_roles_contract.py` passes six socket-blocked groups through actual Plan/Author payload construction and draft persistence, with the provider boundary replaced. It covers story/visual/notes handoff, approved-fact filtering, locked voice/single intake, rejected-citation rewrite and no approval/publication/audio generation. Independent review checked 46 candidate lines against 20 approved v7 assertions and inspected all ten assigned original images. Actual author validation reported no issues. These checks are not general semantic entailment or live story-quality proof.
- Status at candidate freeze: prompt changes and a session-generated candidate are independently reviewed. No paid Plan/Author/Build provider call and no voice API test produced this candidate. Final stress-session, publication and any narration-render evidence must be appended separately; do not mark them passed from this record.
- Provenance: plan `a4c38377bc7c27a674dfb42c847fc82a6734dfcace20049fcb02bcd0ec37086f`; first frozen spoken-text candidate `9d49a7b8f597cfe7d5874e2b97aa74d4cdff9dca8b4dcad71ba1ae9cad023b88` (the final pace-adjusted candidate is `6b6375e5e0c35bcc371d043bda8d10f01fd546572cef3d14b11d9a01255b9986`; words/citations/images are unchanged); independent Author review `a15e2b141a2d7975ba31d245ef02796b2f7a54298a7ff450a4ab152a867cc8cd`. Artifacts: `output/creta-night-final/plan.reasoning.md`, `plan.semantic-review.json`, `script.session.review.json`, `author-independent-review.json`.

### Five whys — bounded diagnostic chain

1. **Why did the tour feel repetitive?** Several blocks repeated a feature statement followed by a future visit or fit-check, rather than developing a distinct thought.
2. **Why was that the easy composition path?** The Author had to invent the narrative connection while meeting short segment budgets and strict evidence limits; another fit-check was a safe but repetitive ending.
3. **Why did the Author have to invent the connection?** The prior goals mainly specified topics/equipment, and editorial notes were dropped from its payload.
4. **Why did it also redesign the route?** Both stages received flow/proof planning instructions, blurring ownership between selecting the story and delivering it.
5. **Why was this not established by existing passing checks?** Citation, word-budget and structural checks do not measure narrative repetition or arbitrary claim entailment. The fix therefore pairs a clearer handoff contract with direct editorial review, without claiming the new offline checks prove persuasion or acoustic quality.

Rejected alternative: relaxing grounding or inventing cooling, comfort, acceleration or safety benefits to make the script sound warmer. The accepted change uses the existing evidence, literal imagery and clearer writing responsibilities instead.


## 2026-09-19 — final-session harness findings (H01–H03)

These were defects in the disposable test harness, not demonstrated application or provider failures. No paid calls were made in these attempts. The original failed outputs remain preserved.

### H01

**Reason / recorded failure:** Programmatic root command is not a trusted autoplay gesture; Codex blocked AudioContext.resume before synthetic capture became ready.

**Solution:** Eval-only AudioContext/worklet/stream clock fakes; physical microphone and browser audio device are never opened. Real LiveVoiceClient state and ownership remain under test.

**Evidence:** `offline-initial/stress-browser-result.json: failed_preserved, Timed out: synthetic capture ready; one offline session still saved.`

### H02

**Reason / recorded failure:** Continue observer sampled the old playback index during the reviewed return bridge, before resumePlayback advanced the completed check-in.

**Solution:** Wait until the bridge caption has ended; then assert the expected next route index or natural closing after the last check-in.

**Evidence:** `offline-attempt02/stress-browser-result.json: 42/44 checks; s05 and final question return checks sampled identical old origin/playback while the final natural route check passed.`

### H03

**Reason / recorded failure:** The client wire observer counted the intentionally injected stale-result test packet among observed answers.

**Solution:** Each response packet now has provenance live_api_result, offline_synthetic, or injected_stale_test; report totals distinguish these categories.

**Evidence:** `offline-attempt02/stress-browser-result.json has14 session turns and15 observed response packets, including utterance_id stale-synthetic.`

**Verification:** Offline-attempt03 completed14 questions,8 controlled interruptions, natural route end and one isolated saved recap. All44 flow assertions passed; every synthetic response is labelled as such. None of these offline records is a real customer session.

**Five whys:** The automated run could not start because the command was not a trusted audio gesture; the harness had retained a browser audio dependency despite claiming synthetic capture; device-independent fakes were needed. Later false failures came from sampling during the real return bridge rather than after its completion. A final response-count mismatch came from mixing an intentionally injected stale packet with upstream results. The general correction is to keep synthetic transport, observation timing and response provenance explicit, while executing the real application state machine. This does not establish acoustic performance.


### 2026-09-19 — H04 — duplicate save after an upstream failure looked successful

**Reason:** The disposable session proxy cached only successful save responses. After a failed or unknown upstream save, an identical second request could return a fabricated success even though its first result was not known.

**Solution:** Keep successful, in-progress and failed/unknown outcomes distinct. A duplicate of failed/unknown work returns502, in-progress returns409, and none triggers another upstream save or summary request.

**Verification:** Independent fake-upstream guard proves one upstream POST; all9 proxy guards pass with zero outbound calls. This is a harness defect found before the single live session, not a demonstrated production session-save defect. Original failure evidence is retained.

### 2026-09-19 — CR45 candidate integration refinements

**Reason:** The first candidate set every explicit pace to1.0, so its warm/reassuring labels alone did not vary the provider's pace. Separately, deterministic callout derivation omitted all labels because the complete source assertions exceeded the short-label budget. Reordering proof stops also makes old positional slide overrides and FAQ routing unsuitable.

**Solution:** Keep speech text/evidence unchanged and add sparse0.97–1.03 pace choices through the supported delivery field; never send emotion tags or SSML. Supply seven independently reviewed concise feature labels with citations and selected-trim qualifiers. Rebuild label placement from trusted image parts, replace positional overrides, and route the unchanged FAQ through production fact-based slide selection. Clear old audio and require each fresh clip to match the current text, voice and delivery identity before publication.

**Verification:** Socket-blocked integration preserves all181 approved fact objects and the immutable v7 snapshot; candidate script validates with no issues. All changes remain pre-publication at this entry; narration and one live session are separately recorded when complete. First frozen candidate and failed harness attempts are preserved.


### 2026-09-19 — H05 — synthetic control timings could enter real latency statistics

**Reason:** The generic latency aggregator does not interpret the harness evaluation label. Synthetic interruption timestamps still matched its detected-to-stopped calculation; synthetic input clocks could also resemble measured STT.

**Solution:** Sanitize the exact saved body at the proxy boundary before hashing or forwarding it. Clear voice-input, endpoint, audio and interruption timestamps; retain event counts, phases, response status and actual result-ready time. Store synthetic timing evidence separately under explicit evaluation metadata and in the browser sidecar.

**Verification:** The production runtime_metrics.aggregate control first demonstrates a measured sample with the original fixture, then none with the exact sanitized forwarded body. All10 proxy guards pass with zero outbound calls, independently confirmed by two reviewers. No production app change, provider call or new real session was used for this fix.

### 2026-09-19 — CR45 publication evidence

The one matching-narration build completed without voice failures. Published local CRETA v8 contains12 slides,7 cited labels,9 segments and the unchanged181-fact snapshot kb_2d616ba1bcec1469e8c7ab40. Every expected audio reference matches its current text/voice/delivery cache identity. The overview is measured10.58s; full main narration plus the two spoken check-ins is114.0s before customer waits/deeper answers. Configured usage increased from$16.3976 to$16.5596 (about$0.162). This is narration assembly and file validation, not an acoustic or perceived-warmth test. The single live stress session is still pending at this checkpoint.


## 2026-09-19 — CR46 — a broad ADAS duplicate omitted Smart Cruise's transmission requirement

- Actual single live session: `s_mu8ozv2etxtx`, question s01 / turn `t_7`, published bundle v8 with unchanged v7 snapshot `kb_2d616ba1bcec1469e8c7ab40`. The answer listed Smart Cruise Control with Stop & Go on selected higher trims but omitted its automatic-transmission condition. This is a material safety-equipment fitment omission, not evidence that the actual car lacks the feature. The later s02 / `t_9` answer correctly states automatic / IVT / AT / DCT, but does not replace or regrade s01.
- Evidence: original event line28 SHA `07c2d975425750e7646dbb431eae90d316cf7ac1677aa57b37403aafc4a8dd13`; model trace line7355 SHA `b704587187a3f3a6c2a0325c9d0a6343228097a700ab86ce5eb3530146ba6e9a`. Full originals are retained in `cr46-smart-cruise-condition.fixture.json`; `cr46-baseline-reproduction.json` records the pre-fix acceptance with no validation errors and zero network calls.

### Five whys

1. Why was the spoken availability incomplete? The broad feature list did not carry Smart Cruise's automatic-only restriction.
2. Why could that wording cite approved evidence? F176/F196 describe the larger suite with only a higher-trim condition; the precise F154 transmission restriction and corroborating F045 were absent from the actual 14-fact pack.
3. Why did validation not use the known restriction? It checked conditions on cited facts. Its existing cross-assertion dependency closure handled explicit device-purchase prerequisites, not feature-specific transmission requirements. Merely adding F154 to the pack still accepted the original draft in the baseline probe.
4. Why did retrieval and validation lose the relation? Relevance-ranked fact selection had no separate condition-only path from the pinned registry to a broad duplicate's explicitly named feature.
5. Why did earlier checks miss it? Directly cited F154 tests already checked automatic phrasing. They did not reproduce an uncited, out-of-pack restriction on an otherwise approved broad duplicate.

### Bounded correction

Before the existing 14-fact ranking boundary can lose a requirement, derive condition-only records from the immutable registry for exact same-feature, scope-compatible, explicit enumerated transmission restrictions. Keep the primary citeable set unchanged. Carry the donor ID, named feature, condition and provenance in the initial prompt, validation feedback and existing one-attempt repair. Reject the missing-condition row; preserve other supported sentences. A qualified row retains the donor as separate condition evidence, not as a new product-fact citation. A manual customer profile cannot filter out the very transmission requirement being checked.

The donor must be approved, not held/conflicted/suppressed, not a calculation or live-web record, and compatible with model/market/year/generation and other explicit identity dimensions. Matching uses assertion text, not quotes, table order or inferred trim ordering. Unrelated lane assistance and ordinary cruise do not inherit Smart Cruise's condition. The donor's unrelated values do not become licensed product claims. Existing device and warranty checks remain intact. Automatic headlamps do not satisfy an automatic-transmission condition.

### Verification and limits

`evals/runtime_transmission_conditions_contract.py` covers the immutable actual draft, its explicitly qualified positive, full-registry retrieval wiring without increasing 14 facts, one mocked repair with feature-owned feedback, manual profiles, scope/eligibility exclusions, quote-only/negative witnesses and no donor-value licensing. Existing runtime, repair and final-cohort contracts are rerun separately. All checks use blocked sockets and no providers.

This is an offline fix and regression result, not another live answer or an acoustic acceptance result. The original session, grade and provider traces remain unchanged. The closure intentionally recognizes only explicit enumerated transmission-only conditions and distinctive literal feature phrases; it does not claim general semantic entailment, infer every natural-language prerequisite, or guarantee coverage of absent/unreviewed restrictions. No source record, snapshot, provider order, deadline, schema or publication is changed by CR46.


## 2026-09-19 — CR47 — Explicit priority correction could not revisit relevant reviewed proof

Date: 2026-09-19. Status: fixed and checked offline; not live retested.

Observed in the sole final stress session `s_mu8ozv2etxtx`, app `274ed3d`, published version 8. The original safety-led route correctly began with standard safety and rear-seat proof. After the customer said, “Actually, comfort matters more. I want to focus on my parents in the rear seats,” the returned route began with front ventilated seats, screens and powertrains. The original requests, replies and saved session remain unchanged.

## Root cause and five whys

1. Why did the corrected rear-passenger priority start with front-cabin equipment? The rear-seat segment was no longer in the planner's available library.
2. Why was it absent? A prior route or question visit had marked its slide as seen; the planner excluded every seen segment before composing the route.
3. Why did explicit refinement not change that rule? The request's existing `refine` intent was not passed through the runtime graph, and both graph and client independently filtered seen IDs again.
4. Why would making the segment eligible still fail at the actual return point? Continue from closing resumed closing without applying a ready revised route; the ordinary covered-slide shortcut could also play only its contextual first line and omit the factual proof.
5. Why had the defect escaped checks? Earlier coverage verified profile preservation and non-repetition, but did not exercise a revised priority after a prior question visit through all three filters, closing continuation, and the reviewed speech sequence.

## Implemented solution

Explicit, request-local refinement can reconsider published reviewed segments. The planner derives `revisit_segment_ids` only from its validated selected route intersected with the request's seen IDs; model-supplied permission cannot authorize unrelated IDs. Ordinary continuation still excludes previously seen material. The prompt distinguishes rear-passenger needs from front-seat equipment, gives the latest raw correction priority, and requests the smallest useful route.

The graph passes the explicit flag and permits only these selected revisits. The client intersects returned permissions with the pending request's seen IDs and chosen route. A ready refinement is applied when the customer continues from closing; authorized revisit steps retain all exact reviewed lines. Publication pins, cancellation/run checks, other continuation behavior and the ordinary brief covered-slide replay remain intact. Reviewed wording, factual conditions, citations, media identity and recorded audio are preserved.

## Evidence and checks

- Baseline: `live/cr47-baseline.json` reproduces the unavailable rear-seat selection through the real original planner with an offline selection boundary.
- Immutable actual request/bundle fixture: `evals/fixtures/pitch_priority_revision.json`.
- New controls: 7 Python pitch/graph groups and 10 JavaScript groups executing real route assembly/application, playback and continuation functions.
- Existing controls: 18 pitch delivery, 47 pitch grounding and 6 narrative-role checks passed; JavaScript syntax and diff checks passed.
- Candidate: `live/pitch.session-revision.json` selects only rear-seat proof and reuses its exact selected-trim recline sentence. Its provenance explicitly says offline session-token selection, no live result.
- Frozen implementation/check hashes: `live/cr47-studio-frozen-review.json`.

## Limits

No paid API, source, publishing or voice test was performed after the issue was found. No production session was rewritten. The offline candidate demonstrates that a correct reviewed selection is now eligible and survives the actual functions; it does not establish that every future model selection will be relevant. Repeat permission is limited to an explicit refinement, not a guarantee of individual comfort or a general invitation to replay the whole demo. Independent Player review passed, including three additional controls executing real closing/session-save functions: one ended save, unchanged ordinary closing and stale-owner suppression.


## 2026-09-19 — CR48 — supplied-table status and useful limitation

19 September 2026. Original live session `s_mu8ozv2etxtx`, bundle v8, code `274ed3d`.

The s10 lookup fetched the exact customer-selected Hyundai CRETA features page. Its comfort table contains complete trim headers and the wireless-charging/cruise rows, but the captured evidence has no readable S/– legend. The original and repaired drafts interpreted those symbols as standard/absent. Validation rejected the substantive clauses; the delivered answer retained a generic limitation and an unrequested Smart Cruise footnote. The original answer remains **partial**.

The next question, s11, used “all listed trims,” which escaped the universal-fitment quantifier. Its rear-vent row is S in all ten named columns. Retain the independent **supported** semantic grade under the prior complete-table rubric, while explicitly recording the stricter missing-legend policy failure. These are separate assessments; neither silently changes the original answer or earlier grades.

The bounded guard fix includes listed/shown/named trim qualifiers in the existing universal check. It does not reinterpret S/–, add source facts, infer trim order, or relax the requirement for an explicit legend. The exact original s10/s11 table and drafts are preserved in `live/source-table-actual-fixture.json` and `evals/fixtures/runtime_stress_source_table.json`. Twenty-one focused tests pass, including all three cited row labels, missing-legend rejection, an explicitly labelled synthetic legend positive, mixed-status rejection, and the new composer instruction.

Five whys:

1. Why was the answer incomplete? The two requested fitment clauses were rejected, leaving a generic limit plus a separate Stop & Go footnote.
2. Why were those clauses rejected? They interpreted unlegend S/– marks as standard/absent; the first draft also turned exact table columns into trim ranges.
3. Why did the repair still fail? It removed the range wording but retained the unsupported status interpretation.
4. Why did composition miss the actual uncertainty? The instructions did not explicitly require an own-verification limit when table-symbol meaning was unverified, despite the guard already requiring it.
5. Why did the adjacent s11 phrasing pass? The universal grammar and tests covered plain all/every/each trims but omitted the ordinary modifier “listed.” The new exact-session controls cover that gap without weakening symbol semantics.

A separate offline agent-authored candidate, using the captured runtime instructions and evidence, says:

> I couldn't verify the meaning of the table's symbols. I can't confirm whether wireless charging or cruise control is standard on every trim.

The existing validator accepts that candidate with five assertions and zero outbound attempts. It is **not** a new live response or proof that the model will choose this wording. It improves specificity without asserting source-wide absence or inventing symbol definitions.

The coordinated graph owner added composition guidance: unexplained source-table marks cannot establish standard/absent fitment. When this prevents the requested check, state the specific feature-status and symbol-meaning verification limit; do not substitute an unrelated feature detail. Both initial composition and repair inherit that instruction. The original source remains immutable. No additional source/provider/voice calls were made. Whether a future live model follows that instruction is unmeasured; the offline candidate proves validator acceptance only.


## 2026-09-19 — CR49 — a complete illustrative EMI caveat was repeated

**Observed:** In the single live session, s08 correctly calculated about₹22,244/month at1% monthly over5years. Its second sentence already said “This is an illustrative figure that excludes taxes and fees, and it is not a formal lender quote.” The delivery helper appended “This estimate excludes fees and taxes.” Original text, correct arithmetic and the redundant output remain preserved in `live/emi-duplicate-actual-fixture.json`.

**Reason and five whys:** (1) The customer heard the same exclusion twice because the helper thought it was missing. (2) It ignored the model's exclusion because the clause subject was not recognized as the estimate. (3) Its recognized subjects covered estimate/EMI/loan and short this/it forms, not “This is an illustrative figure that.” (4) The exclusion parser intentionally requires ownership to avoid borrowing a warranty or unrelated fee clause; removing that check would be unsafe. (5) Earlier actual-output controls covered reordered exclusions but not this exact valid subject form.

**Solution:** Add only the anchored this/it + is an illustrative figure + optional that/which form to estimate ownership. Keep original validated speech intact and append only genuinely missing terms; never alter the calculation or infer omitted inputs.

**Verification:** The captured case and missing-tax counterpart fail before the change and pass after it. Thirteen delivery groups pass with blocked sockets, including negated/unrelated illustrative figures, wrong interest basis and idempotence. Two independent reviewers pass the frozen helper. No paid retry, voice call, source or original-session change. This improves duplicate delivery; it is not a new live response.


## 2026-09-19 — CR50 — a prior universal-fitment filter hid relevant comfort facts

- Actual session `s_mu8ozv2etxtx`, s14 / `t_39`: the customer asked which reviewed comfort features to check with their family and what could not be verified about personal comfort. The response gave a truthful fit-check limit but omitted known equipment. It remains an original partial answer, not a provider failure.
- Preserved evidence: `live/comfort-retrieval-actual-fixture.json`, model trace line7476 SHA `e9e7c98eaec67009436a2d6a38b28ab5f59567d11d819115aeb2442ba36261c0`; final event line208 SHA `a6c67654950580da33448c943c2c8889a436ee1fb6ff9eacca31f1918b434893`. The actual pack contained only F214/F237, not rear-seat recline F097 or split-seat F096.

### Five whys

1. Why did the answer omit useful known comfort equipment? The model received only two universal safety assertions and correctly avoided inventing comfort claims.
2. Why did relevant approved equipment disappear? Retrieval required the literal scope `all variants` inherited from an earlier all-trim equipment question.
3. Why did that filter survive a topic change? `explicit_scope` treated every stored scope dimension as durable customer preference, including a question's universal quantifier.
4. Why was that distinction missing? Named chosen trims/comparisons and universal question scope shared the same profile field without a lifetime distinction.
5. Why did earlier checks not expose it? Topic-relevance checks exercised the comfort query without this real preceding universal filter. The new regression uses the captured profile/history through production scope inference and retrieval.

### Bounded correction and limits

Treat a stored all/all-variants/all-trims filter as request-local. Preserve it only when the current question explicitly asks across all trims or makes a quantified follow-up such as “all of them.” Named trims and explicit comparisons continue to persist; changing models still clears stale dependent configuration. `_requested_variants` continues to reject generic all/every/conditions words rather than inventing a trim name.

The actual-input offline contract reproduces the original two-fact pack with the old explicit filter, then executes production retrieval after the corrected scope and recovers F097/F096 within the unchanged 14-fact limit. It uses the immutable v7 assertions and a disposable in-memory index; no source, snapshot, demo or provider is written. Paired checks retain explicit universal follow-ups, named trims/comparisons, restrictive unknown trims and model corrections. This is a retrieval fix and offline verification, not a regenerated live answer or proof of personal comfort. No topic classifier or inferred trim ordering is added.


## 2026-09-19 — CR51 — a combined loan and EMI guarantee received only one limit

**Observed:** Actual s12 asked whether the bank would approve the loan and guarantee that EMI if the customer decided today. The response stated only the loan-approval limit. It remains graded partial; it never approved the loan or promised an EMI. Original evidence is in `live/combined-guarantee-actual-fixture.json`.

**Reason and five whys:** (1) Half the requested boundary was omitted because the selected lender-approval act rendered one fixed sentence. (2) The act's closed template covered approval but not the co-requested EMI promise. (3) The model could select only the available boundary ID and correctly avoided unsupported financial claims. (4) The backend did not specialize that safe act for two explicitly joined guarantees. (5) Prior controls tested loan guarantees and illustrative calculation disclaimers separately, not this actual joined request after a calculation.

**Solution:** Retain the same closed act and render a fixed combined limit only when the current request explicitly joins the EMI guarantee: “I cannot confirm or guarantee a lender's loan approval or a final EMI quote.” No customer text, numbers or invented lender policy is emitted. A past EMI question, an approval-only question or a separate request to calculate EMI does not add this refusal.

**Verification:** The exact live wording fails the new control before the change and passes afterward. All30 typed-act groups pass with blocked sockets; independent reviewers verify current-question ownership, fixed output and unchanged historical/unrelated behavior. No new schema, provider request, financial-data collection, live rewrite or fresh quality claim.



### 2026-09-19 — CR46–51 final verification and evidence boundary

All six corrections passed independent review and blocked-network regressions; required deck320/accept24/both smoke pass. Feature conditions17, priority revision7+client10, table21, EMI13, universal scope8 and typed acts30 pass. The corrected comfort candidate uses recovered F097/F096 with selected-trim wording and separate closed personal-fit limits; full validation reports zero errors. That candidate is session-token authored, not a new live response. CR46 additionally lowercases only grammatical That/These when prepending a qualifier; Hyundai and ADAS capitalization are preserved. No source/snapshot change or paid retest followed the single live session. Original grades9supported/3partial/1unsafe/1cancelled and their raw hashes remain intact. Final recorded increment$0.4496; physical microphone and acoustic performance remain unmeasured.


## 2026-09-23 — DEP01 — local server could not start after base Python disappeared

**Symptom:** Uvicorn exited126 before importing the app: its virtual-environment interpreter pointed to `/Users/macbook/anaconda3/bin/python3`, which no longer existed.

**Five whys:** (1) The launcher could not find its interpreter. (2) The venv's python3 symlink referenced the removed Anaconda installation. (3) Virtual environments preserve an external base-interpreter relationship. (4) The previous successful server was not evidence that this path would survive a later machine change. (5) Startup instructions did not make base-interpreter availability an explicit check.

**Reason:** local environment lifecycle, not an application regression. **Solution:** preserve the original pyvenv metadata/link receipt, point the environment to the installed compatible CPython3.11.13 x86_64, and update base metadata. Existing compiled3.11 x86_64 wheels are retained. Runtime imports and pip check pass; the real local health and unchanged12-slide CRETA v8 bundle load on8896. No source rebuild or paid model call.

**Prevention:** check the interpreter path/version and pip consistency before restarting; rebuild a venv if major/minor or architecture changes rather than reusing incompatible wheels. Receipt: `output/deploy-2026-09-23/interpreter-repair.json`.

## 2026-09-23 — DEP02 — source rendering assumed the developer's Mac browser path

**Symptom:** EC2 has no `/Applications/Google Chrome.app/...`; rendered authoring extraction would always fail before browser launch even with Playwright installed.

**Five whys:** (1) Rendering preflight required a Mac-only path. (2) Browser selection was an application constant. (3) Local development used one known installed browser. (4) No operator override or installed-managed-browser fallback existed. (5) Earlier contracts exercised source/network boundaries but not Linux executable selection.

**Solution:** an absolute validated `CRAWL_BROWSER_EXECUTABLE` override, otherwise existing Mac Chrome, otherwise Playwright's installed Chromium. The application never downloads a browser, retries without sandbox, or accepts executable arguments from source/customer input. Missing executable or unsupported system dependencies remain explicit availability failures. Preserve all pinned public-host fetch, redirect, request-budget, worker/WebSocket and sandbox rules.

**Verification:**9 new socket/subprocess-blocked selection/launch contracts plus7 existing public-source contracts pass; independent review is clear. The real EC2 browser dependency/launch outcome is separately recorded in the deployment report. These offline checks alone do not prove Linux browser availability. No source facts or published script changed.

## 2026-09-23 — DEP03 — EC2 SSH allowed only previous laptop IP addresses

**Symptom:** healthy EC2 and HTTPS, but SSH connection timed out. **Reason:** the security group allowed22 only from two prior /32 addresses; the current laptop egress address was different.

**Five whys:** (1) SSH packets did not reach the permitted rule. (2) Current egress was not in its allowlist. (3) The laptop's public address changed. (4) Provisioning intentionally pins SSH to one laptop IP for narrow access. (5) The update path did not check current egress before attempting SSH.

**Solution:** save the complete security-group snapshot and add only current121.241.7.122/32 to port22, preserving previous rules. AWS IAM permits adding rules but denies revocation, so this is recorded as current-laptop access, not falsely described as a temporary rule already cleaned up. First SSH host-key trust is explicitly TOFU for the AWS-account-verified instance/EIP; subsequent connections use the recorded task-specific key with strict checking. No mismatching key was accepted and SSH was never opened to the public internet.

**Prevention:** verify instance/EIP/current allowlist before release; removal of obsolete /32 rules requires an operator with revoke permission. No IAM role/policy change was made.


## 2026-09-23 — DEP04 — staged test archive omitted a documentation fixture

**Symptom:** the first remote `qa_deck.py` stopped with `FileNotFoundError` for `docs/aws/instance-role-policy.json`, after reaching its deployment-policy assertion. No outbound socket was attempted; the old app was still serving.

**Reason / five whys:** (1) The assertion loads a real policy fixture. (2) That fixture lives under `docs/aws`, outside `evals`. (3) The check archive contained only evals and samples. (4) Production packaging correctly excluded unrelated documentation, but the test package reused that narrower assumption. (5) Test packaging did not enumerate file dependencies outside the test folder.

**Solution:** transfer the exact fixture from the same committed release, preserve the initial failure, then rerun the free remote gates with isolated data and blocked sockets. Deck 320, acceptance 24, both smoke phases, runtime graph 130 and browser-selection 9 passed. The failure was packaging, not an application or provider regression. Future staged checks must include their explicit non-code fixtures.

### 2026-09-23 — deployment completion and remaining OCR limitation

DEP02 is verified on the actual AWS host: installed Chromium 153 and trusted Amazon Linux libraries launch with the sandbox enabled, and the production source renderer executes an intercepted local JavaScript fixture. Poppler is installed for PDF rasterization; ordinary PDF text extraction is available. Tesseract is absent from the configured trusted repositories, so scanned-image OCR remains unavailable; do not claim exhaustive image-only PDF extraction on this host. No new repository, unsupported binary, unsandboxed browser or compile-from-source workaround was introduced.

The service switched successfully, all prior AWS demo bundles and `.env` remain unchanged, and the 2,017 transferred CRETA files retain their hashes after HTTPS/media/report/WebSocket readback. The original session is the only CRETA session on AWS; no additional usage or session record was created. Deployment receipt and rollback: `docs/aws/release-2026-09-23.md`.
