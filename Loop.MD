# Loop.MD — Demo Studio


## Mobile correction — 26 September 2026

Finite QA, loop off. Local deck445/445, acceptance24/24, smoke3/3, full mock28/28; native mounted WebKit26/26 with Safari/CriOS profiles, recorded ownership12/12, audio lifecycle13/13; gallery320/320, mobile104/104, welcome66/66, continuity28/28, image load14/14. Adjacent voice96, LiveKit58, transport15, hold26, noise31, recovery17, listen16, saves18, HTTP6, media7, fallback18, priority11 pass. Native local RTC30/30 after two retained failed attempts; no configuration relaxation or paid providers. Deployment fixtures18/18, CSS overlay15/15, actual isolated proxy58/58 plus153/153. [Full evidence, failures and FMEA](docs/qa/mobile-runtime-2026-09-26/README.md).

AWS application3591fb7 plus the5543fe1 CSS overlay is live. Staged36/36 suites with zero outbound attempts; knowledge58passes+2environment skips. Public application32/32, proxy20/20 and hosted mic-off WebKit RTC10/10 pass. All1436 source files verified with the one explicit CSS digest exception; all4273 stored files were preserved during main cutover, and the subsequent CSS-only overlay needed no restart or data write. [Release receipt](docs/aws/release-mobile-2026-09-26.md) records actual deployment. Counts overlap. Physical iPhone/acoustic acceptance is not established by emulation; no new paid QA.

Final deployed welcome21/21 passes across native WebKit/Chromium at390×844,844×390 and844×320. Two initial WebKit failures came from a read-only getUserMedia descriptor in the test harness; a direct import trace confirmed it. Corrected WebKit12/12 is included in21/21, not additional coverage. No sessions/provider/mic/socket/mutation calls; screenshots inspected. Documentation-only checkpoint retains earlier gates without rerunning them or changing deployed application bytes.

## LiveKit default adoption — 25 September 2026 · released

Finite QA, loop off. Core deck445/445, acceptance24/24, smoke3/3 and full mock28/28 pass with isolated DATA/GRAPH, blank provider keys and blocked outbound sockets. Twenty-six adjacent Python suites also pass with zero outbound attempts; exact inventory is in [the current QA receipt](docs/qa/livekit-default-2026-09-25/README.md). Hosted policy/room29, legacy LiveKit50, normal local launcher15 and isolated-copy launcher16 pass. Frontend selector15, LiveKit58, base voice96, hold26, recovery17, saves18, acknowledgements14; actual public/Rehearse/navigation28. Real local RTC30/30.

AWS applicationae98532 is live after34/34 staged suites with zero outbound attempts; knowledge58passed+2environment skips of60, all other applicable checks green. Real public WSS/TURN mock32/32 confirms54 received/forwarded PCM frames, typed questions, picture before voice and saved visits. Boundary153/153, actual TLS/PROXY41/41, recovery10/10 and application release15/15. Public code/media/privacy28/28 (33frontend files) and real mic-off public RTC9/9 pass. All4267stored files unchanged; local restart preserved702. Source1385/1385, backup and actual failure history are in the [release receipt](docs/aws/release-livekit-2026-09-25.md). Counts overlap; do not sum. No new paid provider/acoustic QA or broad load claim; hosted capacity is two rooms. Earlier receipts below remain historical evidence for their own source revisions.

## Approved runtime/gallery release — 25 September 2026

Finite QA, loop off. Final local core **445/445 deck,24/24 acceptance,3/3 smoke,28/28 full mock**. Seventeen isolated/mock/socket-blocked Python suites and seven free Node suites pass; zero outbound attempts/providers. New acknowledgement14/14; actual native player88/88 includes11questions, full ten-phrase cycle, legacy clips, commands and restart. Domain25/25 (four new failed-crawl/explicit-exclusion/failure-evidence groups), web search37/37. Adjacent graph130, tool replay20, customer sites20, delivery27, visuals23, live transport25, Sarvam17, FAQ27, transmission17, checkpoint26, LiveKit backend50/client47, voice96, hold26, listen16, recovery17 and saves18. Counts overlap. Exact inventory and limits: [local release QA](docs/qa/runtime-gallery-release-2026-09-25/README.md). AWS applicationd94d6ef is now deployed:27/27staged processes pass; core445/24/smoke3/full mock28, knowledge58passed+2environment skips. Public17/17, frontend32/32, media96/96, desktop/phone welcome and4267unchanged data files verified. Exact counts, two initial harness failures, stale-marker preflight and rollback evidence: [AWS receipt](docs/aws/release-runtime-gallery-2026-09-25.md). No paid QA or hosted LiveKit adoption.

## LiveKit review input and gallery continuity — 25 September 2026

Finite QA, loop off. Final frozen application: **deck445/445, acceptance24/24, smoke3/3, full mock28/28** with isolated DATA/GRAPH, cloud off, blank keys and zero outbound socket attempts. Full mock still measures194.22seconds synthetic narration. New actual-player continuity28/28; prior97ef2ab fails four cases22/26. Current gallery320/320, native87/87, fallback18/18 and image-load14/14. Original BMW181/181 files unchanged. Independent FMEA12/12 categories found/fixed the same-photo opacity pulse; pixel RGB now stable before/during/after.

Actual stock app-route LiveKit mock browser28/28 now types intake and the reported interior question, checks delivery and saved result. Backend50, client47, launcher16; adjacent voice96, hold26, listening16, recovery17 and session-save18 pass. Three input-free real-room joins pass at5.563/3.177/3.120seconds with zero provider requests. Counts overlap.

Bounded live-provider review uses exactly two semantic questions and no rebuild: real STT captures a locally synthesized BMW question, preserves an honest unsupported-capacity decline and streams4.096s non-silent PCM. The original QA assertion wrongly required seven seats and remains failed, not rewritten green. The remaining typed interior check passes6/6 withF011/F014/F015, associated console image,22.828s non-silent speech and incremental/completed persistence. Total app-estimated usage **$0.024371 /₹2.0471**; no physical microphone or room-acoustic claim. An initial harness blocked LiveKit validation; a second join timed out before provider use without sufficient diagnostics to prove a root cause. Later five consecutive joins succeeded; no speculative transport change. Paid/harness failures and final evidence remain separate in [the receipt](docs/qa/livekit-input-gallery-2026-09-25/README.md). Master/AWS adoption remains pending.

## LiveKit opt-in local trial — 25 September 2026

Finite QA only; recurring loop stays off. Default app final free gates: **qa_deck445/445, qa_accept24/24, smoke3/3, full mock28/28**, with isolated DATA/GRAPH, mocked providers, blank keys and zero outbound socket attempts. No optional LiveKit SDK is installed in the default `.venv`; disabled feature imports and all core workflow gates pass. Final runtime source hashes stay unchanged during those gates.

New backend50/50, client47/47, launcher16/16. Existing voice96/96, immediate speech hold26/26, listen16/16, recovery17/17 and session-save18/18. Actual default gallery320/320 and current native87/87 match the prior native87/87 baseline. Actual pinned SDK/SFU/browser trial24/24 verifies real RTC microphone traffic, exact same-machine candidate, server PCM frames, no duplicate data microphone, mic generations, reversible hold, reviewed picture before answer audio, worker loss, desktop/phone layout and saved visit. Synthetic capture and mocked providers do not establish acoustic quality. Counts overlap and must not be added.

[Receipt, hashes, screenshots, dependency provenance and twelve-category FMEA](docs/qa/livekit-trial-2026-09-25/README.md). Real integration exposed native loopback ICE failure, uncancellable native operation ownership and first-control participant visibility; all were corrected before acceptance. Local signaling/API stay loopback; RTC uses one validated same-machine private interface, public STUN is disabled, and TCP media is off. No paid QA, default promotion, master merge, GitHub push or AWS rollout. Physical-device/provider and hosted-network acceptance remain pending.

## Immediate speech hold, answer pictures and retrieval — 25 September 2026

Finite free QA, loop off; working branch only, no master/AWS release or paid call. Frozen baseline e80a180: deck445/445, acceptance24/24, smoke3/3, full mock28/28. Final actual working tree: **deck445/445, acceptance24/24, smoke3/3, full mock28/28** with194.22s synthetic measured narration. All89 application files stayed unchanged during final core/backend execution. Fresh isolated DATA/GRAPH, MOCK_LLM=1, cloud off, blank keys and blocked outbound; zero outbound attempts. The first444/445 deck result was a stale static callback/timestamp assertion; retained failure plus corrected behavioral-intent structural assertion and445/445 rerun are recorded.

New contracts: immediate speech hold26/26, runtime visual selection23/23, actual image/player42/42, retrieval IO12/12. Adjacent final: live voice96/96, speech noise31/31, runtime recovery17/17, listening16/16, session save18/18, knowledge60/60, runtime graph130/130, FAQ cache27/27, transmission conditions17/17. Earlier package checks: repair106, FAQ scope19/review42, live transport25. Final actual muted browsers: live journey42/42, gallery320/320, native player87/87; source/viewer diagram parity9/9. Counts overlap and must not be summed as unique cases.

Browser tests include reversible recorded/streamed hold, final-only semantic ownership, long-question progress, rejection resuming same clip, caption/watchdog cancellation, same-slide selected image/tag before answer, saved Continue picture, missing/stale/broken image limits, no accidental callback/factual unknown, and late decoded-picture hold/cancel ownership. The latest native pause-event media clock stays4.470407→4.470407 over120ms; synthetic local voiced detection is about160ms. Neither is real-room/device latency or background-speaker discrimination. Five BMW retrieval payloads remain deeply identical while source reads31→1 for comfort; all181 probed source files unchanged. No script/browser errors in final browser gates. Isolated mock-server shutdown did log inherited `Turn superseded` cancellation; do not claim zero backend exceptions.

[QA inventory, source hashes, logs, screenshots and twelve-category FMEA](docs/qa/runtime-interruption-media-2026-09-25/README.md). No new unresolved code blocker; physical acoustic/low-power-device/load acceptance and inherited public-runtime budgets remain explicit limits. This package adds no LiveKit integration, provider, prompt, graph node, migration or core-workflow change.

## AWS BMW feedback release — 25 September 2026

Finite release QA, loop off. Exact application278c21d on the existing AWS virtualenv: **deck445/445, acceptance24/24, smoke3/3 phases, full mock28/28** (194.22s synthetic narration). All33 staged subprocesses exit0 with isolated DATA/GRAPH, mock providers, blank keys and zero outbound attempts. Provider79 ran inside deck; its separate import-only invocation is not additional test coverage. Generation55/55 omits three optional unavailable legacy-Creta cases; no protected fixture was mounted to inflate counts. Every other staged contract's observed count/log hash is recorded in [the gate inventory](docs/qa/aws-bmw-release-2026-09-25/gate-counts.json). No standalone JavaScript rerun on AWS (no Node); local final same-byte browser281/audio71 and gallery320/native87 remain applicable. Full mock does execute its real browser fixture.

Real installed Caddy2.8.4: **153/153** isolated proxy checks. Public HTTPS after cutover: **17/17**, including26frontend hashes,96unique BMW media ranges, exact approved bundle content/pin, anonymous private-path denial, operator login and mic-off WSS session.ready. Desktop1440/phone390 welcome captures have no script/asset errors or horizontal overflow. All4108 prior data files unchanged; no new QA usage, trace, session or lead; no service error. This deployment performed no paid generation, acoustic test or capacity/load test. [Release, FMEA, screenshots and rollback](docs/aws/release-bmw-gallery-2026-09-25.md).

## BMW gallery, conversational writing and expression — 25 September 2026

Finite QA; recurring loop stays off. Final free core after the per-picture caption correction and build thinking-budget fix: **qa_deck445/445, qa_accept24/24, smoke3/3** (Read, Build, on-demand rehearsal), all with zero outbound attempts. Full mock release **28/28**, including194.22seconds of measured synthetic narration, real review/publication guards, runtime answer and saved session. These measurements describe fixtures, not the real BMW recordings.

Touched and adjacent contracts: Understand batch16; script prompt53; narrative roles14; generation58; Coach27; Plan19; narration preparation35; automatic preparation16; minimum narration25; selected duration19; PDF images58; pitch grounding47; Deck media106; media Align39; visual alignment25. Provider79 and runtime config6. Voice coverage: new expression20, speech style30, voice lock27, Sarvam stream17, runtime delivery27, live transport25, Explore cancellation9, FAQ cache27 and scope19. Gallery browser320/320 and current native player87/87 have zero errors, failed assets or external requests. Coverage overlaps; these are not additive unique checks.

All free providers are mocked, storage/SQLite isolated, cloud disabled, sockets blocked; browser harnesses allow only their own loopback static server and reject microphone/WebSockets/providers. One obsolete narrative-role string assertion expected the removed blanket transition ban; it now checks stock-signpost avoidance and contextual joins while retaining all other checks. The model-caption reproduction failed5/106 before repair and passes106/106 afterward. The historical native85/87 baseline remains separately labelled, not a failure in the current87/87 run.

**Bounded real BMW acceptance:** original picture loss and formal prose were reproduced. Five Gemini drafts failed semantic/budget review and remain recorded; actual system-role correction recovered one LOW Coach call but did not establish compliant Author output. The final existing Runware GPT5.5 draft received explicit normal Align source, outline, dialogue and picture review:335/330 supported main words,31 cited lines reviewed, one outcome-underbudget advisory. Six normal approvals preceded one recording Build; published narration measures122.64seconds against the selected120second minimum. Pixel review then corrected two feature-label mappings and duplicate dimensions before a slide-only re-bundle; all53 audio files stayed byte-identical. Final bundlev2 has15 slides,11 distinct photos and32 labels. This is an editorially reviewed recovery, not unattended first-pass generation. The customer preset now prefers GPT5.5 for Build; eval tier, runtime order, explicit overrides and all publication guards remain. Final revised BMW actual-player replay281/281 and published audio71/71 pass at1440/390px; all14 main clips across13 speaking slides, no failed assets, runtime writes or provider calls. Raw eligible audio122.624seconds rounds to122.64 after per-clip measurement. Actual recording/browser results are in the linked receipt.

[Current logs, screenshots, source hashes and twelve-category FMEA](docs/qa/bmw-gallery-narration-2026-09-25/README.md). Actual BMW regeneration is recorded separately in that receipt; no free test establishes audible emphasis or physical noise rejection.

## Default middle-slide gallery — 25 September 2026

Loop remains off. The user approved template integration only in the middle image area and authorized master/GitHub publication. Top navigation and bottom transcript/microphone/chat/actions retain their current structure and geometry. No Build/agent/node/prompt or grounding/duration changes; no paid run or AWS deployment.

Final free gates: qa_deck399/399, qa_accept24/24, smoke3/3; full mock release28/28 with194.22seconds measured synthetic narration, real publication guard and saved session. Noise31/31, live voice96/96. Focused player/native contracts143/143: fundamental10, listen16, HTTP6, customer sites19, focus21, priority11, media7, native fallback/geometry18, runtime recovery17, session save18. New gallery image/interaction contract14/14. Actual-player gallery browser312/312; final targeted preparation-click/scroll checks12/12; existing player browser87/87. Syntax/structure/whitespace17/17 includes all9 Mermaid source/viewer copies.

Baseline85/87 is retained alongside the two phone evidence corrections and the cold-image fixture wait. Actual published CRETA acceptance requires loaded photos, all reviewed captions, exact text/audio, same-line two-picture ownership and desktop/phone shell comparisons; no vacuous empty route. The full mock journey separately verifies fresh creation/build/publication. Blocked outbound sockets and isolated DATA/GRAPH, cloud off,0provider calls; browser captures are muted/fake-audio checks, not acoustic evidence. Independent review and12-category FMEA caught/corrected cancelled loads, runtime fallback, local clicks interrupting pending narration, multi-picture evidence loss and per-photo disclosure. Source hashes, all counts, failure notes and screenshots: [gallery-template receipt](docs/qa/gallery-template-2026-09-25/README.md). No new open design question.

## Noise qualification and gallery prototype — 25 September 2026

Loop remains off. Application: qa_deck399/399, qa_accept24/24, smoke3/3, zero outbound attempts. Focused contracts258/258: speech_noise31, live_voice96, live_transport25, player_listen16, player_focus21, player_runtime_recovery17, player_http_question6, player_priority_revision11, player_session_save18, sarvam_stream17. Independent review additionally exercised both real automatic-resume call chains. No new agent/node/provider or paid call.

Current real-DOM browser result85/87 matches unchanged master85/87, with the identical two phone evidence font/cue failures. Historical87/87 receipts are not rewritten; this run does not claim full browser green. The task prohibits production slide changes. The initial core runner used the wrong smoke filename; corrected to smoke_mock and all three phases pass, retaining the initial failure log.

The separate gallery's full natural-rate muted replay completed all six recordings and37 phase changes with no script errors. Desktop/phone geometry/control checks69/69 and source hashes are in [the receipt](docs/qa/noise-gallery-2026-09-25/README.md). Prototype media is copied from the isolated published demo; app slide modules/data remain unchanged. Synthetic STT/rooms and muted playback do not prove physical noise/echo rejection. Local branch only; master/GitHub/AWS remain at their previous releases.

## Master integration checkpoint — 25 September 2026

Loop remains **off**. This checkpoint changes documentation only and integrates the already-reviewed application through`cf30dba`. Fresh isolated/mock/blocked-socket core recheck: qa_deck399/399, qa_accept24/24, smoke3/3; zero outbound attempts. Receipt/logs: `docs/qa/master-checkpoint-2026-09-25/`. Previous slide acceptance and runtime contracts below remain evidence for the unchanged source; no new paid, acoustic or full browser run is claimed.

Anand authorized master integration on25September, superseding the merge holds in these dated entries. AWS is unchanged from its last recorded feedback-workbook release; older “no master/AWS release” statements refer to their historical checkpoint. No application behavior or new eval contract is introduced by this documentation update.

## Slide continuity restoration — latest acceptance · 24 September 2026

Loop remains off.15scoped suites /2,635overlapping reported checks, all green: backend8suites654; native adapter18, player HTML87, recorder39; responsive layout212, workbook101, Studio integration19; actual published-v3 screenshots/render1505. Required qa_deck399/399, qa_accept24/24, smoke3/3 and full mock journey28/28 (194.22s synthetic). Touched Deck media79/79, media Align39/39, visual25/25 and Align review57/57. Independent6APIcases and8stable-reveal comparisons are additional.

Actual review covers all20slides/18speaking slides,88states at1440/390px with/without the legacy walkthrough URL. Positive picture/tag presence, exact current-line tag identity, native source loading, bounds, no overlaps, sans-serif headings, stable earlier tags and unchanged20decoded recorded clips are required. Script/plan/registry, all56stored recordings and usage remain unchanged. Captures are renderer acceptance, with no natural-audio/microphone claim; player contracts use synthetic speech. Provider calls0. Initial mobile failure1369/1417 is retained, followed by fixed rail wrapping/footer clearance and final1505/1505; full screenshots/counts/hashes/FMEA are in `docs/qa/slide-continuity-2026-09-24/`. This supersedes previous claims that empty picture/tag arrays and exact paragraph cards established presentation quality. No master/AWS release.


## Runtime recovery — acceptance plan · 24 September 2026

Finite QA only; recurring loop remains off. Anand authorizes one paid final journey after the complete isolated mock pass, using only the supplied16JPGs and49-page PDF. Work stays on `codex/sales-trainer-flow`; master/AWS require his later hands-on approval. No protected demo or port8896 operations.

**Hypothesis before paid execution:** the normal Sources → Read → six-card Align review → Build → customer playback path produces a grounded default three-minute demo, reaches its closing CTA, and preserves an ongoing session before exit. The existing agents/nodes, evidence validators, duration gate and voice identity remain unchanged. PDF/image-only sources grant no external runtime web permission. Conflicting or unsupported source details remain held; QA approvals require an actual source/picture/script review.

**Free acceptance:** core deck/accept/smoke, complete mock release, final-only speech qualification, partial/noise non-interruption, local Continue/Not now controls, section three-second windows, streamed-audio inactivity recovery, ongoing/reordered/retried saves and phone-safe public summaries; domain restrictions, grounded Q&A/cache and desktop/phone form geometry. Logs use isolated DATA/GRAPH with mocked providers and blocked outbound sockets.

**Paid boundary:** one readiness probe, one initial Read, one Build and one bounded natural-speed muted customer visit, with recorded usage and no automatic whole-stage repeats. The initial Read failed; separately recorded causal revisions and human source/script/picture review followed through existing APIs. Stop for source review before Build. The harness checks a $10 recorded-usage ceiling before each next action (not a provider-side hard spend cap), up to4 runtime reasoning requests/32 speech requests and12minutes. Record measured speech, provider failures, incremental and completed session records, screenshots and cost. Muted automation cannot establish physical microphone noise rejection, echo behavior or voice listening quality.

**Report-only:** captions are set before speech fetch/start and have no provider word timestamps; this explains the observed lead/lag. No caption synchronization redesign is included.

**Paid QA finding and bounded correction:** the original single Read reached Align but stayed pending at342/495 words after its existing three Author attempts. All49 pages/25tables reached the two fact-reader prompts; the model returned only26 facts and omitted feature/gearbox matrices. Citation formatting held9 rows, and the retained FAQ conflicted with the structured turbo table. No Build or manual approval occurred. Recorded first-Read estimate:$0.2238/22calls. Preserve that failed attempt and exact responses. Fix page-preserving input batching and exact retained-table-cell citation verification in the existing Understand/knowledge functions, run their free contracts/core gates, then issue one explicitly recorded revision of this same QA draft through the existing route. Re-review facts/script/pictures before the single Build. Do not add Author retries, lower the duration threshold, invent evidence or claim the first paid Read passed.

**Final free receipt:**60suites /2,335reported checks/groups/phases, including browser481/481; overlapping coverage is explicit. Deck386, acceptance24, smoke3, full mock release28 (194.22s measured fixture audio); server checkpoints26, summary race14, input mode8; domain21, web search37, customer sites20, tool replay20, runtime graph130, delivery27, powertrain pairing19, transmission conditions17, equipment pairing12, runtime plain language25, FAQ cache27/scope19, knowledge60, live transport25, operational failure13, interaction7, conversation18, repair106, metrics19. Node: customer sites19, focus21, fundamental10, HTTP6, listen16, media7, priority11, recovery17, session save18, walkthrough30, live voice96. Browser: HTML87, live40, layout212, workbook101, integration19, navigation22. Evidence correction adds reader10, sources39, fact retry19, automatic narration16 and preparation35; final full release28/runtime graph130 rerun remains green. Prepared allocation17, planner19, duration19, minimum25, recovery18, generation58, narrative14, prompt40, Align review57, deck media66, media Align15 and visual alignment25 also pass; shared stop capacity and whole-batch feasibility are now explicit. Exact inventories/hashes and FMEA: `docs/qa/runtime-recovery-2026-09-24/`. The live browser uses synthetic PCM/STT and8x muted audio; natural-speed paid acceptance is separate. Zero external/provider calls in free gates.

**Paid result:** one Build193.78measured seconds; one natural-speed browser visit11/11mechanical checks,67checkpoints and ended recap. All9sections prompted and the closing CTA appeared without overflow. Independent semantic review failed the engine/gearbox answer: its existing repair replaced an explicit petrol/diesel qualification with “them”. The original failure is retained and its cache entry rejected through normal Align. The narrow shared validator correction passes19targeted tests and17independent probes, including repaired and historical cached wording. All12affected/core suites pass after the correction; no second paid visit. Recorded total:$0.9182/126calls, possibly excluding timed-out provider charges. See `docs/qa/runtime-recovery-2026-09-24/paid-acceptance.md`; no second paid visit, physical-acoustic claim, master merge or AWS release.

## WP12 walkthrough · 24 September 2026

Finite mock acceptance; recurring loop remains off. Deck380/380, acceptance24/24, smoke3/3; layout193/193, workbook101/101, Studio integration19/19, navigation22/22, HTML player79/79; exact default chrome/Align parity9/9; walkthrough29/29, media7/7, focus21/21, fundamental10/10; live browser26/26. Motion85/85 and screenshots are recorded in `docs/qa/wp12-2026-09-24/`. Narration content/logical completion/context parity uses controlled speech events; separately paced checks observe real camera transitions. Neither establishes acoustic recognition or voice quality. All tests use isolated mock storage with blocked outbound sockets. No paid run within WP12. User-approved stale baseline browser expectations were updated without changing default application behavior.


## Script generation — approved and merged to master · 24 September 2026

Mocked, isolated data/graph storage and blocked sockets; no paid model/voice calls. Before and first improved prompt iteration: deck380/380, acceptance24/24 and smoke3/3. Existing scope: Coach27/27, plan/playbook19/19, narrative roles14/14, generation55/55, speech style30/30, narration preparation35/35, recovery18/18, automatic narration16/16. New `python evals/script_prompt_contract.py`:40/40 groups covering actual assembled prompts across categories/audiences, protected evidence rules, numeric/citation/visual rejection, technical-detail preservation, batch splitting and the unchanged495/180 preparation/publication distinction. `evals/coach_contract.py` additionally proves prompt-cache invalidation without evidence mutation.

New `python evals/pdf_images_contract.py`:58/58 for bounded embedded pictures, parent eligibility, stable retry IDs, exclusion across every bundle image path and timeout recovery. Supporting source39/39, upload stream19/19, retry12/12, deck media60/60, media Align15/15 and Studio29/29 pass. The actual PDF yields95 pictures/26,467,885bytes within the96-picture/48MiB cap; eight vision batches are mocked and are not pixel evidence.48 pictures were independently inspected for the final prompt fixture.

Stage simulations and their quantitative review live in `docs/qa/crack-script-2026-09-24/`. They use source-derived, manually inspected fixtures and separate reasoning agents, not live model providers; mocked rules-only picture assignments are not pixel proof. Iteration06 preserves the exact05model responses while fixing22 fallback picture substitutions:48/48 texts/citations,30/30 images and18/18 no-picture choices retained. Fresh08 Author fixes a warranty-scope omission and two mixed-option pictures:49/49 units preserved (29 images,20 none),500prepared words; selected unvoiced route348words/183.16estimated seconds, no measured sample audio. Strict style shortcomings remain documented. New `python evals/visual_alignment_contract.py`:25/25 (11/25 before fix). Final complete25suites total1,069overlapping reported checks/groups/phases, all green with DNS/sendto/connect blocked; full mock release28/28 measures194.22seconds of synthetic WAV fixtures. Final reviewed12 uses the unchanged10 prompts and two explicit existing-path QA revisions:495prepared words,16/16batches,16distinct first words,49spoken/deeper/overview/closing units and empty issues. Diesel main now names first manual availability E. Selected unvoiced route345words/181.58estimated seconds; no measured sample audio. Final source/criteria/metrics reports and exact revision provenance are retained. No new code after the final10eight-suite prompt-delta rerun; the25-suite/1,069 total is unchanged. Loop remains off.

## Feedback workbook · 24 September 2026

Loop remains **off**. Final local gates: **51/51 suites; 1,790/1,790 reported checks/groups/phases (nested coverage overlaps)**, zero outbound/provider calls. Required deck **380/380**, acceptance **24/24**, smoke **3/3** (Read/Build phases and on-demand rehearsal). Full mock release journey **28/28** with **194.22seconds measured fixture audio** and the actual three-minute default guard. Duration **19/19** covers1–5minutes, alternate-language publication, old-publication preservation, changed-duration preparation and protected manual edits. Upload retry **12/12**, stream **19/19**, Deck media **60/60**; Studio chat/navigation **29/29**, workbook player **101/101**, full-app integration **19/19**, responsive layout **193/193**, existing navigation **22/22**. Every touched contract is green; all15 Node suites pass.

The inventory `docs/feedback-workbook-gates-2026-09-24.json` contains each suite count and test/log/source hashes. FMEA: `docs/feedback-workbook-fmea-2026-09-24.md`,12/12 categories. Python/JavaScript syntax, whitespace and all9 Mermaid copies/structural checks pass; no Mermaid parser or physical-device/acoustic claim. Workbook unchanged, no protected local writes or port8896 action. Nav40percent height reduction is the explicit C9 assumption; selective Align rebuilds remain pending.

Application commit `483755d` is pushed to GitHub and deployed on AWS after 23/23 staged suites; 4,087 shared files preserved, environment checksum unchanged and public frontend 25/25 verified. Receipt: `docs/aws/release-feedback-workbook-2026-09-24.md`.

## Automatic narration preparation · 24 September 2026

Loop remains **off**. Three-minute preparation is now part of ordinary Read/Author, with bounded completion, current Script approval guards and automatic measured-shortfall drafting inside an explicitly requested Build. Revised speech returns for review; missing recordings do not cause a content rewrite. Manual edits retain exact words and explicit preparation state. The large normal-flow deficit/Prepare panel is removed; mock placeholders are clearly identified.

**Final gates:** **35/35 suites, 1,169/1,169 reported cases/checks/phases; zero outbound attempts**. Independent muted browser **13/13** at desktop/390px. Exact counts, source/test/log hashes and fixture limitations: `docs/automatic-narration-gates-2026-09-24.json`; twelve-category FMEA: `docs/automatic-narration-qa-2026-09-24.md`.

- Required deck **365/365**, acceptance **24/24**, smoke **both phases plus on-demand rehearsal**.
- Actual normal Read/manual-edit contract **16/16**; preparation **35/35**; recovery **18/18**; measured minimum **25/25**. Successful fixture Read prepares the draft without a final-script injection or guard bypass. Failed first writing call, repeated short outputs, source gaps, manual shortening, all approval paths and preserved prior artifacts are covered.
- Full API/Read/review/Voice/Bundle/runtime/cache/rehearsal/browser/session journey **28/28**, **194.22 seconds** measured fixture audio with the actual180-second publication guard. Separate preparation→playback proof:495distinct fixture words/198seconds.
- Changed contract counts: Align review **51/51**, Build hardening **28/28**, Align narration UI **21/21**, Align timing **13/13**, plus the core/preparation/recovery/release/automatic contracts above. Other scoped contracts and each count are in the machine inventory.
- Syntax, diff whitespace, Mermaid structural checks and all9source/HTML copies pass. Isolated DATA/GRAPH, MOCK_LLM=1, cloud off, blocked sockets, zero outbound attempts. No paid/acoustic/model-quality acceptance. Tiny generic plumbing fixtures explicitly stub readiness; actual automatic/release/publication contracts do not.

No new unresolved FMEA blocker. Inherited hosted access/Cloud voice identity/capacity/OCR/nonempty damaged-audio-cache/selective-rebuild items remain pending. Protected local demo/output/port8896 untouched. GitHub/AWS deployment is recorded separately after cutover.


GitHub/AWS release `b15d23e`:16/16 staged suites pass; shared demo bytes/environment unchanged, served frontend25/25 and media206pass. [Receipt](docs/aws/release-automatic-narration-2026-09-24.md). No paid calls.

## Earlier narration preparation / recovery · 24 September 2026

Loop remains **off**. The user-reported128.3-second failure now has preparation and explicit Align recovery; the measured180-second publication gate remains unchanged. Baseline eight gates passed; final scoped **33/33 scripts** report **1101/1101** checks/cases/phases with zero outbound attempts. An independent actual-browser pass adds **10/10** checks. Inventory, each count/log and source hashes: `docs/narration-recovery-gates-2026-09-24.json`; twelve-category FMEA: `docs/narration-recovery-qa-2026-09-24.md`.

- Required deck **365/365**, acceptance **24/24**, smoke **both phases plus on-demand rehearsal**.
- New preparation **18/18**: actual Plan→Author bounded repair→Deck→Bundle→Pitch, **495 distinct cited words /198 seconds measured fixture audio**, all 13 guided pieces retained. Calibrated targets survive retries, reset for changed voice/language/length/persona, and exclude unreachable/deeper/duplicate/question speech.
- New recovery **18/18**: actual128.3-second Build parks at Align, leaves published version/snapshot/audio intact, requires explicit review/rebuild, checks readiness/override, selected-language visibility and draft target counts.
- New Align recovery UI **17/17**, independent muted browser **10/10**; existing timing11, progress9, CoachUI9, readinessUI5; no device or external request.
- Contracts touched: minimum25, Plan19, generation58, narrative14, speech30, publication8, Align51, CoachAlign21, Deck45, DeckAlign15, voice27, theme12, readiness10. Broader flow: full release journey27 with194.22seconds measured fixture audio, runtime130/conversation18, pitch delivery18/priority7/fundamental12/grounding47, player fundamental10/priority11/media7. Every listed contract passes.

Python/JavaScript syntax, diff whitespace and all 9 Mermaid source/HTML copies pass. Tests use MOCK_LLM=1, isolated data/graph storage and blocked outbound sockets. No paid model/voice, physical microphone or live model-quality test. Thin evidence remains an explicit review gap, never permission to pad or bypass180-seconds. New recovery UI is active on localhost8905 with its existing isolated mock data; the protected demo, output/ and port8896 were not operated.

GitHub/AWS release `e506448` is verified:15/15 staged suites pass (generation55 there because the three optional real-data checks were already covered locally). Staging exposed the deck/smoke worker-idle wait race; both helpers were fixed and rerun, plus6/6 direct wait scenarios. All4,087 stored files and environment checksum remain unchanged; public frontend25/25 and image/audio206 delivery pass. Full receipt: `docs/aws/release-narration-2026-09-24.md`.

## WP11 release QA / FMEA · 23 September 2026

Loop remains **off**. Full release review covers WP1–WP11 against deployed `63abb85`. All **95/95** script/harness entries pass (**94 executable**, plus the provider module exercised inside deck); **2,788** reported groups/cases/phases overlap where deck invokes another contract. Full per-file counts and evidence paths: `docs/wp11-release-gates-2026-09-23.json`. FMEA: `docs/wp11-release-fmea-2026-09-23.md`, **12/12 categories**, eight fixes and three inherited limitations.

Required gates: deck **365/365**, acceptance **24/24**, smoke **both phases + on-demand rehearsal**. Full new-demo API→Read→six approvals→Voice→Bundle→runtime/cache/review/rehearsal→browser/session dry run **27/27**, **194.22s** measured silent fixture WAVs with the real **180s** gate active. All14 Node suites **209/209**; responsive/sample browser **193/193**, public-search UI **30/30**, navigation/persistence **22/22**, player HTML **78/78**. No paid calls, microphone capture or external browser requests. Backend sockets blocked, isolated data/graph storage, zero outbound attempts.

Every contract changed in this release-fix commit:

- `align_review_contract.py`: **51/51**.
- `customer_contract.py`: **29/29**.
- `deck_media_contract.py`: **45/45**.
- `explore_cancellation_contract.py`: **9/9**.
- `player_contract.html`: **78/78**.
- `player_http_question_contract.cjs`: **6/6**.
- `player_navigation_contract.py`: **22/22**.
- `player_session_save_contract.cjs`: **7/7**.
- `publication_approval_contract.py`: **8/8**.
- `qa_deck.py`: **365/365**.
- `release_mock_contract.py`: **27/27**.
- `runtime_clause_delivery_contract.py`: **21/21**.
- `runtime_final_cohort_contract.py`: **94/94**.
- `runtime_pass2_contract.py`: **36/36**.
- `runtime_plain_language_contract.py`: **25/25**.
- `runtime_transmission_conditions_contract.py`: **17/17**.
- `runtime_v7_limits_contract.py`: **118/118**.
- `runtime_web_search_contract.py`: **37/37**.
- `upload_stream_contract.py`: **19/19**.

Syntax: 23 changed Python files and four JavaScript modules pass; nine Mermaid source/HTML copies match; diff checks clean. Exact technical-audience fixture expectations are explicit; small unit fixtures retain labelled narration stubs, while publication/minimum and full-release contracts enforce measured audio. GitHub master and AWS now run `07ecc8e`. All14 staged-host checks pass (same core/contract counts above, plus runtimegraph130/cache27/minimum25/build28/browser-selection9); 4,087 shared data files and environment checksum remain unchanged. Public25frontend hashes and image/audio206ranges pass. Preservation/rollback receipt: `docs/aws/release-wp11-2026-09-23.md`. No protected local demo/output mutation or port8896 operation. Open C7 hosted access, C8 Cloud alternate-language voice, plus pilot capacity and existing scanned-PDF OCR limitations remain explicit. Selective Align rebuild routing is still pending.

## WP11 — production/reference parity · 23 September 2026

Loop remains **off**. The exact Marine slide-first HTML is the canonical reference; production and Align previews share its compact heading, centered native picture, small feature cards, progress and white conversation/footer layout. All labels are planned together before reveal. Short windows retain 120px desktop / 132px phone conversation space; ordinary stages remain 75% of the player viewport.

- Free gates before and after: `qa_deck.py` **365/365**, `qa_accept.py` **24/24**, `smoke_mock.py` **both phases + on-demand rehearsal**. Final logs: `/tmp/demo-sample-final-{deck,accept,smoke}.log`; isolated mock storage, blocked sockets, zero outbound attempts.
- `ui_layout_contract.py --live-url http://127.0.0.1:8905/ --screenshots /tmp/demo-sample-parity-final`: **195/195**. Same-asset unchanged-sample parity at 1440/850/390px, two-pixel picture-position tolerance, heading/feature/composer measurements, dark/white colors, six two-image labels, missing-anchor/proxy behavior, long-route reachability, short-window feedback, fixed transient geometry, palette review, fresh isolated mock Bundle publication with measured 180-second WAVs, and GET-only actual-app rendering. A labelled same-size SVG substitutes only when the local retained JPEG is absent on a clean checkout.
- `player_contract.html`: **78/78**, including visible Voice mode switch/microphone ownership and narration → listening → answer frame stability. Mobile assertions now require complete on-slide cards, exact anchor positions and paired label/leader visibility; tall-image and crowded-fallback checks retain source immutability and readable text.
- Player Node contracts: media **7/7**, focus **21/21**, listen **16/16**, priority revision **11/11**, customer sites **19/19**, fundamental **10/10**; live voice **74/74**.
- Real retained CRETA images and Downloads MP4: **6/6**, muted and read-only at desktop/phone; native image ratios, 75% stage, video-only film with a separate Skip button 16px below it. Independent staged-reveal/resize probe confirms stable label/image geometry and unchanged source JSON.
- Changed Python/JavaScript syntax, diff whitespace and all **9/9** embedded Mermaid copies pass.

No paid generation, deployed update, protected-demo/output mutation or port-8896 operation. These checks prove local frontend composition and mocked lifecycle behavior, not acoustic or live-provider quality. Selective Align rebuild routing remains pending; no new open questions.

## WP11 presentation correction — 23 September 2026

Loop stays **off**. The latest user instruction supersedes the side-panel design: full-width cinematic slide, details on-slide, 75% player height at ordinary sizes, dark top and white lower area. Short windows retain a 112px minimum conversation dock; status/answer choices scroll above the fixed composer. Reviewed anchors and stored label positions remain intact.

- Required free gates before and after: `qa_deck.py` **365/365**, `qa_accept.py` **24/24**, `smoke_mock.py` **both phases + on-demand rehearsal**; mock providers, isolated data/graph stores and zero outbound attempts.
- `ui_layout_contract.py`: **149/149**; full width/proportion, no evidence sidebar, dark/white colors, collision-free on-slide labels, edge-origin connectors, true image ownership, stable CTA/capture/contact geometry, normal and short desktop/phone controls.
- Existing player Node checks: media **7/7**, focus **21/21**, listen **16/16**, priority revision **11/11**, customer sites **19/19**, fundamental **10/10**.
- Silent static design samples: **173/173** layout/state checks across all three palettes at 1440, 850 and 390px, including the embedded Rehearse preview.
- Read-only real media: **6/6** checks for latest non-protected CRETA slides and Downloads video at desktop/phone; native ratios, 75% slide height, film-only view and separate Skip preserved.
- `player_contract.html`: **76/76**, including immediate label-edge attachment after reveal; no browser exceptions or outbound requests. Changed Python/JavaScript syntax, diff whitespace and all nine embedded Mermaid copies pass.

No paid generation, deployed update, protected-demo edit or port-8896 operation. These are UI/fixture checks, not acoustic or real-provider acceptance. Selective Align rebuild routing remains pending.

## WP11 — customer question cache and approved finishing changes · 23 September 2026

Loop stays **off**. Read answers uploaded FAQ questions only; clean customer answers/audio are cached against pinned evidence, while declines become counted customer unknowns. Rehearsal is on demand. The package also implements transcript-confirmed interruption, automatic cited public search, measured three-minute default narration, citation retry/bulk restore, the approved Marine layout and Visuals-card palette approval.

- `evals/qa_deck.py`: **365/365**.
- `evals/qa_accept.py`: **24/24**.
- `evals/smoke_mock.py`: **both phases + on-demand rehearsal**.
- `evals/faq_cache_contract.py`: **27/27**.
- `evals/faq_scope_contract.py`: **19/19**.
- `evals/faq_review_contract.py`: **42/42**.
- `evals/faq_plain_language_contract.py`: **21/21**.
- `evals/cached_plain_language_contract.py`: **9/9**.
- `evals/build_hardening_contract.py`: **28/28**.
- `evals/coach_contract.py`: **26/26**.
- `evals/coach_align_contract.py`: **21/21**.
- `evals/plan_playbook_contract.py`: **19/19**.
- `evals/generation_contract.py`: **58/58**.
- `evals/align_review_contract.py`: **51/51**.
- `evals/knowledge_contract.py`: **60/60**.
- `evals/source_contract.py`: **39/39**.
- `evals/fact_identity_contract.py`: **17/17**.
- `evals/fact_retry_contract.py`: **12/12**.
- `evals/voice_lock_contract.py`: **27/27**.
- `evals/runtime_graph_contract.py`: **130/130**.
- `evals/runtime_repair_contract.py`: **106/106**.
- `evals/runtime_customer_sites_contract.py`: **20/20**.
- `evals/runtime_plain_language_contract.py`: **24/24**.
- `evals/runtime_web_search_contract.py`: **34/34**.
- `evals/runtime_tools_replay_contract.py`: **20/20**.
- `evals/runtime_delivery_contract.py`: **27/27**.
- `evals/runtime_operational_failure_contract.py`: **13/13**.
- `evals/runtime_calculation_deadline_contract.py`: **17/17**.
- `evals/live_transport_contract.py`: **24/24**.
- `evals/sarvam_stream_contract.py`: **17/17**.
- `evals/runtime_conversation_contract.py`: **18/18**.
- `evals/session_input_mode_contract.py`: **8/8**.
- `evals/runtime_metrics_contract.py`: **19/19**.
- `evals/deck_media_contract.py`: **45/45**.
- `evals/deck_media_align_contract.py`: **15/15**.
- `evals/speech_style_contract.py`: **30/30**.
- `evals/narrative_roles_contract.py`: **14/14**.
- `evals/visual_theme_contract.py`: **12/12**.
- `evals/minimum_narration_contract.py`: **25/25**.
- `evals/pitch_fundamental_contract.py`: **12/12**.
- `evals/pitch_grounding_contract.py`: **47/47**.
- `evals/pitch_priority_revision_contract.py`: **7/7**.
- `evals/pitch_delivery_contract.py`: **18/18**.
- `evals/qa_policy_contract.py`: **12/12**.
- `evals/align_progress_contract.mjs`: **9/9**.
- `evals/align_timing_contract.cjs`: **11/11**.
- `evals/coach_align_ui_contract.cjs`: **9/9**.
- `evals/live_voice_contract.mjs`: **74/74**.
- `evals/player_customer_sites_contract.cjs`: **19/19**.
- `evals/player_focus_contract.cjs`: **21/21**.
- `evals/player_fundamental_contract.cjs`: **10/10**.
- `evals/player_listen_contract.cjs`: **16/16**.
- `evals/player_media_contract.cjs`: **7/7**.
- `evals/player_priority_revision_contract.cjs`: **11/11**.
- `evals/readiness_ui_contract.mjs`: **5/5**.
- `evals/sse_client_contract.mjs`: **4/4**.
- `evals/player_contract.html`: **76/76**.
- `evals/ui_layout_contract.py`: **103/103**.
- `evals/public_search_ui_contract.py`: **30/30**.

Python compilation passes for 50 changed/new files; JavaScript syntax passes for 10; diff checks are clean. All nine Mermaid source/HTML copies agree. Full inventory and review limits: `docs/wp11-implementation-report-2026-09-23.md`.

All backend checks used `MOCK_LLM=1`, isolated data/graph storage and blocked outbound sockets; recorded outbound attempts were zero. Browser runs used an isolated headless profile, muted audio, synthetic providers and blocked external requests. No paid Read, TTS, public-web lookup or physical microphone acceptance was performed. Loop remains off.

The deliberately short generic fixtures in `qa_deck.py`, `smoke_mock.py`, `align_review_contract.py` and `deck_media_contract.py` supply a clearly labelled synthetic duration at their bundle-assembly boundary. The actual publication gate is tested separately in `minimum_narration_contract.py` with distinct cited passages, readable WAV recordings, short/missing/corrupt clips and unchanged prior bundle/snapshot/version on rejection. There is no production mock bypass. `visual_theme_contract.py` also publishes the real recorded-duration fixture.

The approved Marine layout was checked at 1440, 850 and 390 px, including all three palettes. The latest non-protected CRETA slides sl04/sl08 and the authorized 854×480 Downloads video were inspected without altering source data. The video plays muted at desktop/390 px with only the film and Skip visible, 16 px apart. Mock/visual checks do not establish live prose quality, acoustic recognition or public-site availability.

Protected-path comparison covers 7,766 files. All protected demo files are byte-identical, with no additions or removals. One pre-existing server log, `output/deploy-2026-09-23/local-server-final.log`, changed during concurrent activity (17:28 modification time, ordinary API/voice-list GETs). This implementation did not write or restore that log or operate port 8896. The whole output tree is therefore not claimed unchanged.

## Sales Trainer WP10 review fixes — 23 September 2026

Loop stays **off**. WP10 covers nested origin tags, recoverable USP errors and first-stop deduplication, retained approved Planner references, preserved legacy check-in assets with silent playback skipping, the two cabin-first prompt fixes, complete proxy citations, three-minute defaults and customer-site filename filtering. The confirmed C2 strings remain unchanged and the four input/decision documents remain intentionally tracked. The separately authorized film change gives video its own view with Skip below it; selective Align rebuilds remain pending and are not part of these passes.

**Final verified contracts:** the following free/backend and player contracts pass after the final WP10 changes.

- Required free gates: `qa_deck.py` 365/365, `qa_accept.py` 24/24 and both `smoke_mock.py` phases. The deck increase is the proxy callout regression, taking media coverage from 44 to 45.
- Coach and Planner: `coach_contract.py` 25/25, `coach_align_contract.py` 18/18 and `plan_playbook_contract.py` 19/19. Coverage includes a Read with incomplete Coach USPs reaching Align, whole-token cleanup including `PS`/`L`, and nested website/uploaded origins in both prompts.
- Author and review: `generation_contract.py` 58/58, `speech_style_contract.py` 30/30, `narrative_roles_contract.py` 14/14 and `align_review_contract.py` 51/51. Temporary CRETA validation preserves question-check-in text/audio and reports only the two specified issues.
- Media: `deck_media_contract.py` 45/45, including every fact from a two-fact illustration line, and `deck_media_align_contract.py` 15/15.
- Runtime: `runtime_customer_sites_contract.py` 20/20, `runtime_plain_language_contract.py` 24/24, `runtime_graph_contract.py` 130/130 and `runtime_repair_contract.py` 106/106.
- Player: `player_customer_sites_contract.cjs` 19/19, `player_listen_contract.cjs` 16/16, `player_priority_revision_contract.cjs` 11/11, `player_focus_contract.cjs` 21/21, `player_media_contract.cjs` 7/7, `player_fundamental_contract.cjs` 10/10 and `live_voice_contract.mjs` 68/68. Priority coverage now expects legacy question skipping and its saved diagnostic.
- Browser/media: `player_contract.html` 73/73 after the final film layout adjustment. The real 854×480 MP4 from Downloads plays muted on desktop and at 390 px width, preserving its native aspect ratio with only the video and a separate Skip control visible, 16 px apart.

Compilation/syntax checks pass for 16 Python and four JavaScript files; diff checks are clean and both C2 strings remain unchanged. All 7,766 protected-manifest files are byte-identical, with zero changes. Backend checks use mock/fake providers, isolated data and blocked outbound sockets, with zero outbound attempts. No paid Read, voice render, port-8896 restart or protected demo/output write occurred. Muted real-video playback proves rendering and media lifecycle only; it does not prove paid-model prose quality, public-site availability, microphone recognition or acoustic quality. Historical checkpoint counts below remain unchanged.

## Sales Trainer final checkpoint — 23 September 2026

Loop stays **off**. WP1–WP8 are implemented in the required order; WP9 closes the documentation and aligns the remaining schema/Planner opening descriptions with D1. Paid Read is skipped because its authorization and cap are blank. Required deck 364/364, acceptance 24/24 and both smoke phases pass. Extended narrative 12/12, generation 56/56, speech style 30/30, Align 51/51, runtime graph 130/130, repair 106/106 and actual browser contracts 70/70 pass. Python compilation, changed JavaScript syntax and diff checks are clean; isolated backend checks record zero outbound attempts. The per-package receipts below retain their original historical counts.

New and extended free contracts, with final counts:

- Coach: `coach_contract.py` 20/20, `coach_align_contract.py` 18/18 and `coach_align_ui_contract.cjs` 9/9.
- Planner/timing: `plan_playbook_contract.py` 15/15 and `align_timing_contract.cjs` 5/5.
- Pictures and initial order: `deck_media_contract.py` 44/44, `deck_media_align_contract.py` 15/15, `pitch_fundamental_contract.py` 12/12, `player_fundamental_contract.cjs` 10/10 and `player_media_contract.cjs` 7/7.
- Plain language: `runtime_plain_language_contract.py` 23/23, `faq_plain_language_contract.py` 21/21 and `cached_plain_language_contract.py` 9/9.
- Return/input: `player_listen_contract.cjs` 15/15 and `session_input_mode_contract.py` 8/8; extended `live_voice_contract.mjs` 68/68, `live_transport_contract.py` 18/18, `player_focus_contract.cjs` 21/21 and `runtime_metrics_contract.py` 19/19.
- Sites: `runtime_customer_sites_contract.py` 18/18, `runtime_site_settings_contract.py` 8/8 and `player_customer_sites_contract.cjs` 16/16.

`narrative_roles_contract.py` 12/12 additionally checks that both the Author schema and Planner describe the initial fundamental opening. `player_priority_revision_contract.cjs` 11/11 retains customer-directed continuation. Plain-language checks preserve exact generated or matching leading live-host attribution without weakening claim grounding, and include it in the final spoken cap. Tests use isolated temporary storage, mock providers, fake pages/devices and blocked outbound sockets. Browser checks verify rendering and state transitions; none substitutes for a fresh provider or acoustic acceptance run.

## Sales Trainer WP5 — 23 September 2026

Loop stays off. Customer-site contracts cover three-turn checkpoint persistence, empty-evidence and first-decline lookup, strong-evidence and interaction-act suppression, explicit verification, source attribution including “as per … website,” allowed hosts, scope/private-network/redirect checks, cancellation and the shared twelve-second budget. Default-site checks admit only enabled product URL source rows when the `off`-by-default setting is enabled. Player checks cover the optional intake field, five-site client cap, later URL additions and profile transport; the server retains a deduplicated eight-site session set. Settings API 8/8, runtime graph 130/130, repair 106/106, tool replay 20/20, conversation 18/18 and Explore cancellation 9/9 pass. Client sites 16/16, focus 21/21, listen-window ownership 15/15, priority 11/11, media 7/7, fundamental 10/10 and actual browser 70/70 pass, including early sites-only intake completion. Required deck 364/364, acceptance 24/24 and both smoke phases pass. Python compilation, changed JavaScript syntax and diff checks are clean, with zero outbound attempts. Runtime customer-site contracts pass 18/18, including default-site filtering, cancellation, attribution and the corrected post-decline tool choice. All lookup checks use fake fetchers and blocked sockets; no new public-page or paid-provider acceptance is implied.

## Sales Trainer WP8 — 23 September 2026

Loop stays off. Live-voice and player contracts cover welcome defaults, text mode without `getUserMedia`, socket connection and streamed speech with capture disabled, one capture request across multiple turns, mid-demo capture toggles without reconnecting, always-visible typing, denied/stale microphone requests and saved `input_mode`. API/session/metrics checks keep actual turn source authoritative for typed versus realtime measurement. Live-voice lifecycle 68/68, WebSocket transport/checkpoint 18/18, listen-window ownership 15/15, session input-mode API 8/8, runtime metrics 19/19, runtime graph 130/130 and summary-race 14/14 pass. Required deck 364/364, acceptance 24/24 and both smoke phases pass. Player focus/input mode 21/21 and actual browser contracts 66/66 pass. Python compilation, changed JavaScript syntax and diff checks are clean. Isolated backend runs block outbound sockets; no paid provider or acoustic acceptance is implied. Synthetic capture proves lifecycle behavior, not acoustic performance. WP5 remains pending.

## Sales Trainer WP7 — 23 September 2026

Loop stays off. Speech-style checks enforce statement-only check-ins; existing published question-shaped check-ins remain playable. Player contracts cover continuous narration, a single three-second answer/decline timer, recorded-only return filler, interrupted-line restart and saved `auto_resumed` metadata. Speech onset, typing, chips, restart/stop and superseding turns must cancel old timers; real clarifications and CTA/lead choices remain explicit. Focus and revised-priority regressions retain their original return ownership. Speech style 30/30, generation 56/56, narrative 11/11, Plan/playbook 15/15, pitch grounding 47/47 and priority 7/7 pass. Player priority 11/11, focus 12/12, fundamental 10/10, media 7/7 and listen-window ownership 15/15 pass. Required deck 364/364, acceptance 24/24 and both smoke phases pass; Python compilation, player JavaScript syntax and diff checks are clean. Backend checks use isolated stores and blocked outbound sockets. Actual browser contracts pass 62/62, including unsent drafts, Stop cancellation and stale lead-save ownership. Mock timing and muted playback do not establish acoustic quality; WP8 and WP5 remain pending.

## Sales Trainer WP6 — 23 September 2026

Loop stays off. `evals/runtime_plain_language_contract.py` covers cited suspension-term substitution, longest whole-phrase matching, common terms, unmapped-term rejection and repair feedback, explicit technical requests, expert audiences, word limits after substitution and recorded substitution metadata. Build/legacy/cache/session checks cover FAQ normalization, Author warnings, audio invalidation when text changes, adjacent article/suspension duplication and propagation to saved customer turns. Runtime plain language 16/16, FAQ plain language 21/21, cached API 9/9, FAQ review 42/42, generation 56/56, speech style 27/27, runtime graph 130/130, repair 106/106 and actual browser 51/51 pass. Required deck 364/364, acceptance 24/24 and both smoke phases pass; Python compilation, player JavaScript syntax and diff checks are clean, with zero outbound attempts from isolated runs. These checks enforce the reviewed terminology map; they do not establish live conversational quality or universal jargon detection. WP5 customer-site lookup changes remain pending.

## Sales Trainer WP4 — 23 September 2026

Loop stays off. Expanded `evals/qa_deck.py` covers two audited bindings and first-line indexes, the two-picture cap, partial/absent audit handling, tagged-part and hero proxy selection, grounded labels, picture-owned callouts and bundle compatibility. API/renderer checks cover allowed media, two pickers, preserved per-picture coordinates, responsive layout at 1000/400 px, active-picture changes, illustration badges and second-picture drag fractions. Regression coverage includes clearing pictures and safely replaying old overrides after source exclusion, while new excluded choices remain invalid. Visit-local media checks remap picture emphasis for prefaces, subset/reordered speech and repeated A/B/A ownership without mutating published slides. D1/P7 checks carry `fundamental` through Slide/bundle and hoist one unseen fundamental before the initial three-proof pitch limit, with the same one-stop move in the player fallback; seen filtering, refinements and explicit revisit contracts remain intact.

Deck 364/364 (media 44/44), acceptance 24/24, both smoke phases, deck media Align API 15/15 and existing Align 50/50 pass. Pitch/player fundamental 12/12 and 10/10, player media 7/7, pitch/player priority 7/7 and 10/10, pitch delivery 18/18, grounding 47/47 and player focus 12/12 pass. Real browser contracts pass 51/51; actual Align two-picker and second-picture callout save behavior was checked. Story order UI 9/9 and timing UI 5/5 remain green. Python compilation, all three changed JavaScript syntax checks and diff checks pass; outbound attempts are zero. Proxy labels and renderer behavior do not establish visual proof; the original audit is unchanged. No paid provider or voice-quality claim is implied.

## Sales Trainer WP3 — 23 September 2026

Loop stays off. Extended `evals/generation_contract.py` covers over-budget issues, advisory warnings only for explicit under-budget allocations, unchanged hard ceiling checks, pitch-minute route limits and planned timeline seconds. Speech-style and Plan/playbook regressions must remain green, including shared Planner/Author ceilings; Align timing checks distinguish estimated, mixed and fully recorded values. Legacy CRETA without typed budgets is checked only from a temporary copy and gets no new under-budget warning. Generation 56/56, Plan/playbook 15/15, narrative 11/11, speech style 27/27, Align API 50/50, timing UI 5/5 and Story order UI 9/9 pass. Deck 320/320, acceptance 24/24, both smoke phases, Python compilation, changed JavaScript syntax and diff checks pass; backend outbound attempts are zero. No paid voice render or new live duration measurement is implied.

## Sales Trainer WP2 — 23 September 2026

Loop stays off. `evals/plan_playbook_contract.py` covers required-stop mapping/order, missing-stop insertion with issues, optional/unmapped-stop exclusion, fundamental flags, inherited USPs/version, clamped/rescaled budgets, pitch-minute totals and the mock Read path. Extended `evals/narrative_roles_contract.py` checks settled ownership, full briefs, continuity, the translation ladder and removal of standout-first examples; `evals/speech_style_contract.py` checks the mapped authoring changes. Plan/playbook 14/14, narrative roles 11/11, speech style 27/27, deck 320/320, acceptance 24/24 and both smoke phases pass with zero outbound attempts; compilation and diff checks pass. Mock Author follows the planned topology and the separate Explore opening is bound to the lead fundamental. Planner budgets are allocated here; WP3 adds validator/timeline checks. These free tests do not establish live writing quality, timing or acoustic performance.

## Sales Trainer WP1 — 23 September 2026

Loop stays off. `evals/coach_contract.py` adds free coverage for category aliases/generic inference, fundamental opening, three nonnumeric USPs, unsupported-stop gaps, allowed evidence/pictures, cache reuse, revalidated overrides, progress-stage registration and isolated blocked-network execution. Coach 20/20, new Coach Align API 18/18 and UI 9/9, existing Align 47/47, deck 320/320, acceptance 24/24 and both smoke phases pass with zero outbound attempts. Category/picture cache changes and failure-preserved artifacts are included. Browser review verifies panel display and reorder→Plan revision→Align. Planner order/budget enforcement belongs to WP2. No real provider, voice or published-demo check is implied.

## Comment-only study checks — 23 September 2026

Loop remains off. The 15 annotated source files introduce no behavior or new eval cases. Against baseline `ba448ff`, all 14 Python ASTs/non-comment token streams and the player JavaScript AST/24,888 executable tokens are identical. Required deck 320/320, acceptance 24/24 and both mock-smoke phases pass before and after, using isolated temporary data/checkpoints and blocked outbound sockets (zero attempts). Python compilation, Node syntax and diff checks pass. These checks confirm preserved behavior; they are not a new live demo or provider-quality test. Local receipts are under `output/comment-guide-2026-09-23/`.

## Deployment checks — 23 September 2026

Loop remains off. The user explicitly authorized local restart, GitHub master publication and existing-EC2 deployment; no paid reasoning/voice test is implied. Before the portability change: deck320, accept24, both smoke phases, transmission17, live-table21, pitch7 and client10 passed with0outbound. The new `evals/crawl_browser_contract.py` has9 groups covering valid/invalid operator paths, preserved Mac behavior, installed managed Chromium, no executable, sandbox launch flags and no unsafe launch fallback;7 existing crawl controls also pass. Final post-change gates and remote read-only/transport checks are recorded in the release report. Actual rendered extraction requires separately provisioned browser/OS libraries; mock selection tests cannot establish that capability.

AWS completion: code `63abb85` deployed at 08:09:13 UTC. Remote deck 320, acceptance 24, both smoke phases, runtime graph 130 and browser-selection 9 pass under blocked outbound sockets. The production renderer launches sandboxed Chromium and renders only an intercepted local fixture. Local/public HTTP, exact v8 bundle, byte-range media, report and microphone-off WebSocket checks pass; both welcome screens render muted. All transferred files, original session and usage remain unchanged. No additional paid session, STT or TTS test. See `docs/aws/release-2026-09-23.md` for limits and rollback.

## Final finite stress and offline fixes — 19 September 2026

Loop stays off. One original live caption session on274ed3d/v8:41/41 controlled flow checks,14QA/13returned/1cancelled,8synthetic interruptions,one new saved recap. Original semantic review9supported/3partial/1unsafe; all3calculations correct. No voice API test. After findings, only captured fixtures and session agents; no paid retry. New incremental app estimate$0.4496.

Offline behavioral evals after the fix freeze (all blocked-network):

- `runtime_transmission_conditions_contract.py` —17 groups: uncited out-of-pack automatic requirement reaches broad duplicate, remains feature-owned and never licenses extra donor claims.
- `pitch_priority_revision_contract.py` —7 groups, `player_priority_revision_contract.cjs` —10 groups: exact reviewed rear proof survives explicit changed priority, closing continuation and full playback. Independent real closing/save controls3/3.
- `runtime_live_table_contract.py` —21 groups: all listed/shown/named enters unchanged explicit-legend policy; precise composition guidance and actual captured tables.
- `runtime_emi_delivery_contract.py` —13 groups: complete illustrative-figure caveat is idempotent, negated/unrelated exclusions never count.
- `runtime_universal_scope_contract.py` —8 groups: actual stale scope loses universal token and recovers F096/F097; named trims, comparisons and quantified follow-ups retain intended scope.
- `runtime_acts_contract.py` —30 groups: actual combined guarantee yields fixed approval+EMI limit; unrelated/historical inputs do not expand it.

Required deck320/320, acceptance24/24 and both smoke phases pass; graph130/repair106/cohort94/limits118 remain green. Python61/JS17 syntax checks pass. Logs `final-gates/night-stress-post-*` and `output/creta-night-final/`. These are deterministic regression checks, not a second live score, acoustic metric or persuasion result. Original v7 QA100 remains separate95/5.


## Historical checkpoints below — no new paid authorization

The following sections preserve earlier states and plans. References to “next” runs describe past bounded authorizations, now completed or superseded. Only the final night checkpoint above is current; no paid retry is authorized.

## Historical narrative-role checks — 2026-09-19 night session

Loop remains off. Planner now supplies an evidence-grounded story outline and exact image selection; Author supplies the final spoken delivery without replanning the route. The session-generated CRETA candidates use the existing v7 facts, IDs and schema. No paid Plan/Author/Build call or voice test was used to create or review them. Six offline handoff groups pass with blocked sockets; they verify input wiring and review boundaries, not story-quality scores, publication or acoustic quality. Candidate provenance is under `output/creta-night-final/`. The separately authorized final stress session must be recorded on its own merits, with no paid retry after findings.

## Historical finite checks — source restrictions and live-table proof

Loop remains off. The settled `b01b0c6`/v7 cohort remains 97 supported, 1 partial, 2 unsafe and no unhelpful answers or whole-turn provider failures. Independently reviewed source-restriction and live-table guards preserve own-row feature modifiers, explicit cell semantics, aligned complete headers and matching trim universes. Cited context/limitation labels cannot bypass these checks. Final live-table 18, coverage 24, ordinal 21, grouped quantities 8, helper 29, conversation 18, schema 8, deck 320, acceptance 24 and both smoke phases pass with zero outbound attempts. Graph, repair, limits, cohort and clause contracts also pass. Logs/hashes: `final-gates/table-scope-final-*`. No source, story, speech or UI changes. The next unchanged live 100 is capped at $3.50/300 completions, baseline $15.1996, within the overall $20 ceiling. Free gates are not live acceptance.

**Actual follow-up result:** frozen `0c47061`/v7 unchanged100 scored95 supported/5 partial/0 unsafe/0 unhelpful/0 whole-turn provider failures. All ten calculations and five follow-ups are supported. REST text median3.563s,p958.693s; no speech. This passes the text-answer gate but not full speed/voice acceptance. All original hashes/reviews are preserved in `qa100-v7-table-scope-final/`. One historical launch intent lacks its pre-dispatch-retirement terminal event; do not manufacture a terminal outcome. A final free telemetry-only regression closes future traces. No further paid run is planned; Loop remains off. Final telemetry-only checks: hedge35, operational13, cooldown8, deck320, acceptance24 and both smoke phases pass, zero outbound attempts. Independent configuration6 and AST-equivalence review are clear; no new live benchmark is implied.

## Earlier finite checks — ranges, source subjects and grouped quantities

Loop remains off. The settled `d7c4bbe`/v7 cohort remains 93 supported, 2 partial, 3 unhelpful, 2 unsafe and 0 provider failures. Bounded fixes preserve comma-coordinated ranges, source-pronoun ownership and symmetric numeric typography; closed dealer/evidence acts keep useful limits. Final ordinal 21, coverage 20, grouped quantities 8, typed helper 29, conversation 18, schema 8, deck 320, acceptance 24 and both smoke phases pass with isolated storage and zero outbound attempts. Graph, repair, limits, cohort and clause checks pass; independent pairing, calculator-deadline and currency checks also pass. Exact logs/hashes are under `final-gates/range-source-*`. No source, script, speech or UI changes. The next unchanged live 100 has a separate $3.50/300-completion cap within the overall $20 ceiling.

## Historical finite checks — source coverage and useful boot uncertainty

Loop remains off. The settled three-second fallback cohort scored 94 supported, 4 partial, 1 unsafe and 1 provider failure; its two original budget segments remain preserved. The coordinated source-pronoun guard and question-bound boot-measurement limit have independent reviews. Final coverage 17, typed helper 24, conversation 17, schema 8, deck 320, acceptance 24 and both smoke phases pass in isolated storage with zero outbound attempts. Graph, repair, limits, cohort and clause controls also pass. Logs and frozen hashes are under `final-gates/coverage-boot-*`. No source, script, speech or UI changes. The next unchanged live 100 is separately capped at $3.50/300 completions; free checks do not replace live acceptance.

## Historical finite checks — earlier fallback experiment

Loop stays off. The settled9d46913/v7 cohort remains87supported/3partial/2unhelpful/0unsafe/8provider failures. Next code adds finite1–5s delay configuration(default5/off) and closed lender/product-evidence boundary acts. Required deck320/accept24/bothsmoke, schema8, conversation16, graph/repair/limits pass with sockets blocked. Typed-helper21, delay-config6 and hedge30 controls pass; independent review is clear. Final hashes/logs are recorded in `final-gates/early-fallback-final-manifest.json`. Paid3s-overlap replay is separately capped, retains the12s deadline and requires late-work settlement; no live benefit is claimed from free controls. The batch reserves32 possible completions per pair, including optional composition repair; dry preparation made no API calls.

## Earlier finite repair checks — conversational boundary follow-up

Loop stays off. The last actual full100 scored93supported/4partial/2unhelpful/0unsafe/1provider failure on7133f23/v7. Original cohort and independent q095 adjudication remain preserved. Next corrections retain a validated own-limit prefix before a typed question, add closed comparison/source-instruction limits, and narrow feature-count paraphrase matching. Required deck320/accept24/both smoke, schema8, typed acts18 and conversation16 pass in isolated storage with sockets blocked. Runtime graph/repair/limits/cohort/pairing/clause controls also pass. Final ordinal17 checks pass, including same-first-modifier count swaps; independent review is clear. Frozen log/source hashes are in `final-gates/closure-final-manifest.json`. No paid speech or source change.

## Earlier finite repair checks — typed conversation / ordinal scope

Loop remains off. Required deck320, accept24 and both mock-smoke phases pass in isolated storage with sockets blocked. New typed-act13, graph integration11, ordinal14, EMI11 and coverage13 groups pass; Gemini SDK schema8 includes new optional model fields. Runtime graph130, repair106, limits118, final-cohort94, clause-delivery21, calculator-deadline17, operational13 and original media-delivery27 controls pass. Exact freeze/provenance and per-gate logs are under `output/creta-runtime-2026-09-19/final-gates/acts-*`.

One historical q026 test expectation was corrected: its unchanged raw “up to SX Premium” assertion is unsupported by an exact trim list and must now be rejected. Its exact-name repaired spare answer and road-wheel controls remain required. No old live answer or grade changed. These checks do not establish live semantic acceptance or audio latency; the next full100 is a separately bounded text-only replay.

status: off
> USER DECISION 2026-09-03: keep running FMEA per .power-coding/config.json; do NOT turn the Loop on in this project. Free evals may still be run on request; never automatically.
> slides-v1 (2026-09-18): `evals/qa_visual_sync.py`, `qa_visual.py` and `qa_runware.py` are retired with the 3D path; `evals/qa_deck.py` replaces them and grows with each phase.

## Equipment relationships, useful limits and provider ownership — 2026-09-19

Graph frozen60846df6: required deck320/320, acceptance24/24 and both smoke phases pass in isolated temporary stores with sockets blocked, zero outbound attempts. Limits118, repair106, graph130, cohort94, calculation deadline17, currency/attribution15, operational failure13 and provider race30 pass. Pairing12, coverage12, interaction7 and final saved-draft21 test methods pass; independent final graph review is clear. Syntax104 Python/17 web JS and diff checks pass. Evidence `final-gates/relations-final-*.log` with source/log hashes in `relations-final-manifest.json`.

Independent review caught and corrected a dispatch race after a hedge winner, before any live activation. Copied per-lane context, deadline recomputation, cancellation checks, one winner and late accounting/no-new-repair controls are tested. `RUNTIME_HEDGE_ENABLED` remains off by default. The sequential versus delayed fallback experiment must run the same cases on the same committed code/snapshot under separate finite cost caps; no claimed latency improvement from fake-clock tests.

The last actual full100 remains73supported/11partial/7unhelpful/2unsafe/7providerfailure on24736a0/v7; initial last25 review is retained beside the q080 coverage-consistency adjudication. The122 recorded-draft replay is diagnostic, not a new cohort or rescore. No speech, source mutation or counter reset. Loop remains off.

## Clause ownership and bounded interaction — 2026-09-19

Final graph2e54ec01/helper37c8543b independently reviewed. Limits118/118, helper7tests/32assertions and12 independent integration controls pass, including uncited/cited separation, customer-number bounds and real warranty condition preservation. Cohort94/repair106/graph130/trace36/currency15 passed immediately before the sole final removal of a redundant legacy assistant-act branch; affected118/helper checks were rerun. Knowledge/snapshot/source bytes remain unchanged.

Required final deck320/320, acceptance24/24 and both smoke phases pass with isolated temporary storage and blocked sockets. Logs `final-gates/clauses-final-*.log`; earlier pre-cleanup logs retained. Syntax97 Python/17 web JavaScript and diff checks pass. Next is the unchanged full100 on committed/restarted code, not another narrow positive-only sample. The preceding focused40 remains30/4/3/2/1; no retroactive pass. Loop and paid browser speech remain off.

## Useful answer delivery under the existing deadline — 2026-09-19

Graph frozenbd1a3618: precise-limit/condition85, calculator-deadline17, actual-cohort93, repair106, graph130 and trace36 checks pass. Knowledge60/60 retrieves actual v7 comfort comparisons without modifying snapshots/indexes or unrelated query results. Currency-attribution15/15 pairs spoken rupees with adjacent ₹/INR and still rejects wrong-page attribution. Independent review includes six calculator ownership/cancellation controls and four currency/schema controls; final independent price-language review also passes.

Required deck320/320, acceptance24/24 and both smoke phases passed on this frozen graph in separate temporary data/checkpoint stores with zero outbound attempts. Python AST95/95 and web JavaScript17/17 syntax pass; diff clean. Logs `final-gates/delivery-*.log`. These gates do not establish the live semantic target; the prior focused40 remains28/7/4/0/1. Commit/restart precedes another unchanged focused replay, with no speech calls or counter reset. Loop remains off.

## Precise uncertainty, scope metadata and fallback cooldown — 2026-09-19

Graph frozen99719ad4: v7 limits58/58, actual-cohort93/93, repair106/106, graph130/130, trace36/36 and independent paired16/16 pass, zero outbound calls. The review caught and fixed two new overreach defects before live replay: literal same-selected live-page relations were incorrectly rejected, and an unrelated “, and automatic…” clause could qualify EPB. Independent report: `v7-limits-independent-review/final-gates.json`.

Lookup20/20 plus3 existing lookup controls cover recognized city-price paths, explicit seed/user locality and redirects. Provider cooldown8/8 uses installed SDK error objects, fake clocks/providers and blocked sockets. Only the observed explicit Anthropic insufficient-credit400 starts a60s process-local cooldown for budgeted runtime calls; transient errors and legacy calls retain behavior. No credit/account/configuration changes.

Required final gates: deck320/320 (includes provider contracts), acceptance24/24, both smoke phases, generation44/44, FAQ42/42, Align47/47, voice27/27, customer29/29; isolated temporary data/checkpoints, zero outbound attempts. Syntax96 Python/17 web JS and diff clean. Logs `final-gates/v7-*.log`. New graph/tool/provider code is committed and restarted before the focused40: every non-supported case from full-v7 plus15 supported scope/tool/adversarial controls and required follow-up context. This subset is not a replacement100 score; no paid speech. Loop remains off.

## Repair preservation and condition provenance — 2026-09-19

Frozen graph `05dc701d`: actual-cohort85/85, repair106/106, graph130/130, trace36/36; independent device-condition closure5/5. Knowledge58/58 and v7 source/retrieval7/7 pass. Real player DOM47/47 and client56/56 verify distinct primary/condition citations without routing changes; fake media, zero paid calls. Syntax94 Python/17 web JS is clean. Independent review excludes optional warranty transfer and negative/unverified condition witnesses. All provider-facing offline contracts use blocked sockets. Required final deck320/320, acceptance24/24 and both smoke phases also pass on this frozen graph, each with zero outbound attempts; logs `final-gates/final-*.log`.

The original focused40 remains30 supported/7partial/1unhelpful/1unsafe/1provider failure on f06d8b9/v6. Corrections retain validated repair subsets only when the original has no facts, positively bound uncited interaction/limits, close mandatory compatible device prerequisites, and rank topic facts after scope resolution. Correctivev7 canonically identifies King Knight from the same source revision; no generic Edition alias. The next unchanged live100 is separate evidence. Browser remains capped at32TTS; Loop remains off.

## Final source and applicability repair — 2026-09-19

Frozen graph `d93eaa78` and knowledge `fc9503e3`: new actual-cohort54, repair106, graph130, trace36, knowledge56; required deck320/320, acceptance24/24 and both smoke phases pass. Main gates used separate temporary data/checkpoint stores and blocked outbound sockets, with zero attempts. Syntax94 Python/17 web JavaScript files is clean. Independent graph review passes seven concrete controls plus the54-case contract. Results: `output/creta-runtime-2026-09-19/final-gates/source-scoped-*` and `player-independent-graph-review/`.

New regressions cover exact conditional comparisons, precise model-year limits, safe refusal before a waiting clarification, excluded/negative/uncertain/foreign/historical trim anchors, current-lineup claim rejection and source-qualified own-record positives. Literal transmission suffix matching preserves the full assertion and automatic-only condition. One optional repair, cancellation, twelve-second budget and no-demotion behavior remain unchanged. These tests do not establish general semantic entailment or current-lineup identity.

Current v6 source publication passes an independent24-check audit, including202 valid bundle citation occurrences and unchanged prior snapshot/media. Latest actual100 remains83 supported/9partial/3unhelpful/2unsafe/3providerfailure on the preceding code/v5; no relabel after fixes. A separate40-question focused live check follows the committed/restarted implementation. Browser cap stays25reasoning/32TTS; no new speech replay.

## Bounded runtime repair and honest response cohorts — 2026-09-19

Follow-up after actual35-case replay: repair106, graph130, trace36, actual DOM44 and client56 pass. New actual-draft controls preserve opaque relative scopes with grammatical trim/variant insertion, exact missing attributes, economy-versus-tank relevance, no paid work for explicit local-file source requests, and safe verification suggestions. Negative controls reject hidden positive claims and prevent a limitation-only repair from replacing surviving facts. Runtime-v1 direct question jumps preserve exact return and cancellation through three new browser cases. Required blocked-egress deck/acceptance/smoke gates are rerun before the next paid cohort.

Authorized finite validation; Loop remains off. `MOCK_LLM=1 CLOUD_SYNC=0 PYTHONPATH=.:evals .venv/bin/python evals/runtime_repair_contract.py` passes77 actual recorded-draft controls with fake composition and blocked sockets. It preserves safe requested-detail limitations, same evidence/language/profile, one repair only, strict no-tool/no-CTA schema, unchanged validation, cancellation and the shared deadline. Graph130 and saved trace36 remain green. Passing fixtures is not live semantic acceptance.

`evals/runtime_tools_replay_contract.py`13 controls preserve quoted inputs/monthly-rate math and exact page passages while ranking topic-bearing bodies ahead of navigation/FAQ questions; hyphenated model slugs and answer paragraphs ending in questions are covered. `evals/runtime_metrics_contract.py`15 separates answer/clarification/decline/legacy and excludes failed/cancelled/missing clocks. `evals/live_voice_contract.mjs`56 and real DOM player41 verify250ms acknowledgement grace, shortest compatible reviewed filler, ready-answer preemption and persisted response classification. The ADAS-only paid harness preserves cumulative budgets and keeps semantic failures failed while finishing collection.

Corrective Creta publications retain history: v3 source corrections, v4 one short Priya acknowledgement, v5 exact manufacturer E/EX roof/camera applicability. Source mutation uses new assertion IDs and normal review approvals. Independent v5 retrieval/negative-answer/inverted-positive controls pass6/6; old snapshot bytes and all narration/media remain identical. These are separate from runtime quality scores.

## 2026-09-19 — Provider readiness boundary

`evals/readiness_contract.py`: 10/10 pass for actual Read/Build API queries, missing/expired/mock/failed checks, selected speech identity, explicit override and mock bypass; sockets blocked. `evals/readiness_ui_contract.mjs`: 5/5 pass for read-only panel mount, explicit credit-using probe, demo-scoped override and revocation. These validate orchestration, not live service availability. Loop remains off.

Incident accounting: retained mock fixture `dm_498d4665` confirms one successful Gemini image call, locally estimated $0.02 (₹1.68). Unknown additional intermediate stores were removed before the defect was identified; no total zero-cost claim is valid. Final blocked-egress gates are separate evidence.

## Conversational runtime implementation contracts — 2026-09-19

- `evals/pitch_delivery_contract.py`:16 actual-function/graph contracts for direct overview-to-route delivery, one verbatim context preface, no clipped long reply, exact reviewed audio/IDs/callout mapping, bundle-shaped check-in/deeper media, model-vs-reviewed fallback provenance, unseen route only, no fabricated context, published-only inputs despite draft changes, and first-turn publication-version checkpoint/fail-safe. No provider calls. Legacy pitch grounding47 and speech27 remain.

- Check-in meaning (`evals/speech_style_contract.py`,27/27): actual author validation warns on opt-in-more-detail/open-choice questions, preserves reviewed text/audio and grounded lines, accepts yes-continue/no-detail confirmations and empty fields, and leaves intake questions independent. Existing player response mapping and sparse cadence are unchanged.

Authorized implementation checks on `codex/creta-conversational-demo`; Loop remains off. The approved plan is `docs/plan-runtime-experience-2026-09-19.md`. Mock/fake contracts establish control and validation behavior, not live speech quality or a completed Creta demo.

- `evals/knowledge_contract.py`:36 local tests. Immutable evidence identity/snapshots, scope/conflict precedence and explicit selections, document provenance, budgeted extraction, local OCR and isolated fake-source browser rendering.
- `evals/runtime_graph_contract.py`:51. Actual LangGraph produces versioned delivery plans; deterministic EMI/other calculations require quoted inputs and units; only supplied URLs authorize lookup; unsupported claims, invented IDs and stale-turn checkpoints are rejected; outage is not a cached knowledge gap.
- `evals/sarvam_stream_contract.py`:17. Fake WebSocket protocol and streaming cancellation contracts. `evals/live_voice_contract.mjs`:46 with fake devices/transports, including early voice answers, interrupted playback, final transcription ownership and personalized callout remapping. Caption-only completion is excluded from useful-audio timing; browser endpoint receipt and actual speech-end are separate clock cohorts. `evals/player_focus_contract.cjs`:12 verifies exact configured focus resolution. None proves native acoustic accuracy.
- `evals/speech_style_contract.py`:22 after the real-draft author/persona/CTA corrections. Nine added real-function cases cover everyday warnings versus technical/deeper preservation, locked Priya identity through revisions, retained source action destinations and honest missing-link fallbacks. Real author/voice/pitch/translation functions preserve cited reviewed claims and Priya identity, separate delivery metadata from speech, key cache by effective pace/persona, measure overview WAV duration, hold unsupported gearbox outcomes and dropped overview units, and replace unseen slide speech without duplication.
- `evals/build_hardening_contract.py`:16. Actual Ready revision parks at Align before voice; subsequent explicit approval/Build completes; image-only changes preserve factual approvals/review cache; changed facts/script/FAQ/prompts invalidate reviews; durable SSE/progress survives reload; mocked image/mascot paths cannot initialize Gemini.
- `evals/sse_client_contract.mjs`:4. Actual API client starts with current snapshot, suppresses duplicate/historical completion events, accepts subsequent live state and cleans up listeners.
- `evals/live_transport_contract.py`:8 mic-generation ownership and connection lifecycle checks. `evals/overview_edit_contract.py`:9 direct editable-overview validation/duration checks.
- `evals/fact_identity_contract.py`:17. Actual review API allocates fresh IDs for changed assertions/scope, leaves immutable published snapshots and old ledger meaning intact, invalidates draft approvals, retires old-ID routes, preserves no-op files and rejects invalid scope atomically. Re-Read lineage is also covered by knowledge tests.
- `evals/gemini_schema_contract.py`:4 validates current SDK JSON-schema serialization for scope/delivery dictionaries. Provider55 (inside deck) includes configurable Gemini-first text builds, order overrides, explicit no-fallback behavior, media isolation and health reporting.
- `evals/runtime_metrics_contract.py`:7 validates cohorts, absent audio, failure/cancellation counts and interruption clock boundaries; these are fixtures, not observed latency results.
- Existing regressions remain: generation44, pitch47, voice27, align47, FAQ42, customer29, policy12, summary11/accounting8/race14, runtime delivery27. The FAQ and deck/smoke fixtures now explicitly reapprove changed content before Build; original assertions remain.
- Final required gates: deck315/315; acceptance24/24; both smoke phases. Each reports `OUTBOUND_SOCKET_ATTEMPTS=0` under MOCK_LLM=1, CLOUD_SYNC=0, local storage and independent temporary data/graph stores. Syntax85 Python and21 JS/harness files. All25 contract script invocations exit0; provider cases execute through deck rather than its import-only file. Logs: `output/creta-runtime-2026-09-19/final-free-gates/`, `final-contracts/` and the final affected-path rerun in `focused-final/` (all green; Python sockets blocked).

Intermediate tests exposed an optional-media mock-guard hole; their warning logs and uncertain accounting are retained in `output/creta-runtime-2026-09-19/mock-guard-audit/`. Do not equate MOCK configuration alone with proved zero spend. Real capability probes have begun; synthetic Sarvam listening passed3/3 intent/entity checks at a stage estimate $0.0062, without establishing native microphone or acoustic quality. TVS iQube repair is separately covered by38 local live-API and33 isolated reuse checks, with nine supported FAQ corrections, no full Build and the documented legacy approval/publication caveat. Remaining release evidence: completed real source/Align/build review, useful-answer validation over100 questions,20 voice interruptions, three complete buyer journeys and measured cache/model/tool latency cohorts. Proposed latency targets remain targets, not promises or observed results.

## Sparse conversational cadence — 2026-09-19

`evals/speech_style_contract.py`:24/24, including a seven-section route with three deliberate check-ins and a negative case proving hidden narration questions/uncited check-in claims remain invalid. Empty check-ins no longer trigger per-section confirmation warnings; technical/deeper and claim guards remain. Shared prompt and schema descriptions match this contract. Required isolated gates and focused results are in `output/creta-runtime-2026-09-19/sparse-cadence/`. The18 deeper-line corrections in `revision-2/reviewed-deeper-patch.json` are reviewed proposals with current fact IDs; root applies and verifies them through the API.

## Align progress recovery — 2026-09-19

`evals/align_progress_contract.mjs`:9/9 with actual Align and SSE modules in a DOM-shaped local host. Current-stage progress restores on initial mount/reconnect, done snapshots hide stale overlays, historical phase completion cannot redirect, visible polling works with an existing overlay node, returning from a hidden tab refreshes, new completion still navigates and cleanup removes listeners/timers. Node syntax passes for screen/harness. Logs: `output/creta-runtime-2026-09-19/align-progress/`. No provider, browser or actual data mutation by the contract.

## Real-draft correction verification — 2026-09-19

`output/creta-runtime-2026-09-19/second-draft-hardening/`: required post gates deck315/315, acceptance24/24, both smoke; speech-style22/22, generation44/44, voice27/27, fake-device client46/46 and focus12/12. Independent temporary stores, MOCK_LLM=1, CLOUD_SYNC=0, local backend and process-level Python socket blocking record zero outbound attempts. Syntax85 Python/21 JavaScript files is clean. The player owner records actual browser39/39 for safe user-gesture CTA destinations; this does not establish external-site availability or successful booking. First actual FAQ review found unsupported benefits, trim over-generalization, false declines and unrelated image jumps; proposed fixes are preserved in `first-draft-review/faq-persona-cta-audit.json`. Passing these gates does not approve the generated demo.

## Atelier visual acceptance — 2026-09-19

Authorized bounded checks for B Atelier's CSS-only integration; Loop remains off. No new product behaviour.

| Check | Expected and observed |
|---|---|
| `git diff 47ac11b -- web server api`; CSS declaration audit | Only four presentation stylesheets change. Layout/display/visibility/overflow/action geometry preserved; decorative home-preview tilt removed. No JavaScript, HTML, SVG, API, data, dependency or runtime changes. |
| Free gates before and after; final syntax | Deck307/307, acceptance 24/24, both smoke phases; 39 server/API Python and 14 web JS files parse. Isolated mock stores, cloud off. |
| `evals/player_browser.py` at1440px; `/ui_contract.html` and `/` | Workspace5/5 and player 36/36 with Atelier CSS. Covers creation/navigation, preview reuse, interruption ownership, exact returns, consent and wide/narrow slide geometry. Fake APIs/media, not acoustic validation. |
| Actual app1440×1000 and390×844; mock muted customer walkthrough | Home/library/Sources/Align/Rehearse/Sessions/share/Playground/Observability plus welcome/player/conversation/recap fit. Nine read-only phone routes measure width 390; tables scroll inside panels. Create Escape restores focus. |
| Small-text and focus contrast review | New Insights tag corrected to 5.221:1 on sky; metadata 5.061:1 on white; slide index 4.789:1 on paper; opaque blue focus 4.678:1 on white. Targeted review, not whole-app accessibility certification. |

Evidence: `output/atelier-ui/`; guide: `docs/design/atelier-ui.md`. No paid providers, real builds or real customer sessions. Native mic, acoustic voice quality and live latency remain unverified by this visual pass.

## Isolated HTML design review — 2026-09-19

Authorized prototype-only delivery; Loop remains off. No production behaviour was changed.

| Manual input / check | Expected and observed |
|---|---|
| Each of A/B/C/D at1440×1000; Workspace, Studio, customer and Insights at390×844 | Four distinct visual directions. All16 phone views have document width390 and no broken product images. Saved screenshots and measurements: `docs/design/options-2026-09-18/previews/` and `qa/browser-review.json`. |
| Studio review/approval and suggested customer question in each prototype | Local approval controls respond; sample questions update the caption/product view. B/C expose explicit return controls; D's local Build blocks before all six approvals. No provider, backend, audio or microphone call. |
| Gallery preview modes, compare, shortlist, notes and reload | All16 screen previews resolve. Two live prototype panes display. Shortlist and note text survive reopening; export control responds. QA text/selections cleared before handoff. |
| Product identity review with `assets/provenance.json` | Audi Q5 picture is labelled Q5 in all four directions; initial A4/Q4 placeholder names in A/C corrected before delivery. |
| `git diff f4863fa -- web server api`; free gate logs | Empty main-code diff. Before/after deck307/307, acceptance24/24, both smoke. All five inline scripts parse and local asset references exist. |

Direct file:// browser testing was blocked by browser URL policy; no bypass attempted. Optional fonts may fall back offline. Scripted prototypes do not establish actual runtime capability, model quality, KPIs or acoustic behavior.

## Professional UI acceptance — 2026-09-18

Authorized bounded checks for the UI delivery; Loop remains off. `evals/player_browser.py` serves the following free browser suites with CSP blocking external connections.

| Input | Expected and actual |
|---|---|
| `/ui_contract.html` → Run checks | 5/5: repeated/concurrent preview calls share one result; transient failure can recover; version/update refreshes preview; actual create dialog submits once then routes to Sources; View preserves fullscreen then playback. Real modules/DOM with fake APIs and fake fullscreen; no backend or provider calls. |
| `/` → Run checks at a wide browser viewport | 36/36 with shipped design-system/player CSS. Includes typed question ownership, interruptions, clarification, exact returns, CTA consent, recap and wide/narrow slide geometry. A retained 390px whole-page attempt failed two wide-only fixtures; rerun at1280 passed all36. |
| Actual UI at1440 desktop and390×844 phone | Home/library/search, Sources, all six Align cards, editor, Sessions/detail/share, Observability and Playground fit. Phone page widths stay390; wide tables scroll in their own containers. Shared mobile logo remains visible. Evidence PNGs are in `output/professional-ui/`. |
| Isolated8894 Home → Create; Escape; Create again | Escape restores trigger focus; creation of UI acceptance fixture lands at `/studio/dm_740f03ae/sources`. No Read/Build. |
| Isolated8894 muted welcome → browse → pause → stop → Done | Cinematic stage and customer recap remain usable at390px; no lead submitted. Interactive intake remained at Opening microphone, so native microphone/typed recovery in that state is not established by this review. |

Before/after broad gates:307/307 deck,24/24 acceptance,both smoke. Syntax:63 Python,14 web JS. All model-facing checks use mock providers and isolated storage. Design guide: `docs/design/professional-ui.md`. Zero paid calls; real Nexon bundle untouched.

> AGENT INSTRUCTION — read every session and obey:
> - While `status: waiting_for_first_draft`: the moment the first working draft exists
>   (core path runs end-to-end once — demo-able, not just compiling), ASK the user:
>   "First draft is working. Want me to turn on the Loop? After each change I'll run
>   the FREE evals below (they cost nothing) and show per-eval pass/fail. The golden
>   set costs real API money — I'll only run it when you approve or at milestones."
>   Set `status: offered` when asked; `on` or `off` per the answer. Re-ask an
>   unanswered `offered` once at next session start.
> - While `status: on`: after each meaningful change run cheapest checks first
>   (`.venv/bin/python -m py_compile server/*.py server/*/*.py`), then execute every FREE
>   eval below for real (run the app with MOCK_LLM=1 — never predict from code), report a
>   per-eval ✅/❌ table including regressions, fix, repeat.
> - GOLDEN SET (paid/graded evals): NEVER runs automatically per-change. Obey
>   `consent.paid_evals` in .power-coding/config.json — `ask` (default): offer it at
>   milestones ("feature complete — run the golden set? ~<N> paid calls") and on
>   request; `auto` only if the user explicitly set it. Before ANY paid run: one-line
>   hypothesis in the run journal; reproduce failures as free checks; one paid
>   confirmation per hypothesis.
> - GRADUATION: when an eval has passed 3 consecutive runs, offer to codify it as an
>   automated test (create the minimal pytest setup if none exists). Mark it
>   `(graduated → <test file>)` below — it then runs with the cheap checks, not the
>   manual walkthrough.

## Goal
<USER: confirm or rewrite> Build a demo for any product from images/video/documents, with a
human approving visuals, facts, persona and CTAs before it's built — and a guide that never states
an uncited fact. Done = the iQube sample runs end-to-end locally with real keys and the feedback loop
rebuilds the demo.

## Free evals — run after every change while the loop is on

NX42 concurrency: `evals/summary_race_contract.py`14/14 after6/14 baseline, actual threads+ASGI with fake providers/temporary storage. Identical saved revisions coalesce; providers stay outside record locks; latest unchanged ended input owns result attachment. Changed same-length/resumed input and other sessions stay independent. Summary accounting8/8 remains. Included in deck307/307.


NX42 summary caller: `evals/summary_contract.py`11/11 (10/11 before) requires LOW with the unchanged1200-token schema/full record. Fake providers only; actual final summary recovery is independent.


- NX40 actual free browser contract:36/36, versus33/36 before. Model CTA is only a suggestion; explicit selection required; contact form owns lead consent. Positive choice, negated mention and unsolicited suggestion covered.
- NX41 `evals/qa_policy_contract.py`:12/12, fake providers/network blocked, included in deck gate. Actual contradictory policy wording becomes a safe decline before speech; safe limits/attached uncertainty/documented relations remain. Initial3/10 and review11/12 failures are preserved.


NX39 comparison context: `MOCK_LLM=1 CLOUD_SYNC=0 PYTHONPATH=. .venv/bin/python evals/generation_contract.py` passes44/44 (39/44 before). Seven cases cover the actual build/runtime input, exact approved comparison notes with full source conditions, explicit buyer-variant precedence, missing/ambiguous clarification, and omission with competition off or script unapproved. Fake responses test context delivery and existing clarification behavior only; they do not establish semantic compliance or replace the live L2 confirmation.

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/summary_usage_contract.py`: eight NX35 checks use real worker threads and temporary demo stores. They require one attributed usage/trace record per demo, positive cost, failure attribution and restoration of caller context. Provider/network calls are blocked. Included in the deck gate; baseline4/8, fixed8/8. Historical unrecorded charges remain unavailable.

Pitch LOW supplement: `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/pitch_grounding_contract.py` now passes47/47 (46/47 before), asserting explicit LOW, unchanged3000 tokens, PitchPlan schema and reviewed-proof prompt through the actual call. Existing48 provider contracts cover the adapter. Actual personalization recovery is separate.

Continued Nexon completion checks: `node evals/player_focus_contract.cjs` executes the production focus parser (4/12→12/12); `evals/pitch_grounding_contract.py` requires exact approved spoken proof with its complete citation set (initial24/38→38/38; final46/46 with neutral-cue and repetition guards); provider contracts48/48 verify live-QA-only LOW thinking on Gemini3.8Flash, full input, unchanged3000-token envelope/retries and no option on unknown overrides. Generation37/37 includes current-question scope and matched comparison dimensions. These free tests establish wiring and enforcement; the resumed actual sample establishes delivered content and speed.
(Run with `MOCK_LLM=1` unless the eval says otherwise. Free = no API spend.)

| # | Input (question / action / call) | Expected (answer / behavior / output) |
|---|----------------------------------|----------------------------------------|
| 1 | (EXAMPLE — replace me) `POST /api/demos {name:"Test"}` then `POST …/sources` with `samples/iqube/*.webp` + url | 201-style JSON; 6 sources listed; `GET /api/demos` shows the demo with status `sources` |
| 2 | (EXAMPLE — replace me) `POST …/read` with MOCK_LLM=1, then SSE `…/events` | status goes `reading` → `align`; `understanding.json` and `plan.json` written; an agent opening message appears in the conversation |
| 3 | (EXAMPLE — replace me) Approve all 4 cards via `…/approve/{card}`, then `POST …/build` | status `building` → `ready`; `script.json`, `bundle.json` exist; every bundled line has `fact_ids` ⊆ registry or is a transition line |
| 4 | (EXAMPLE — replace me) `POST …/run/qa {question:"what is the kerb weight?"}` on a registry that lacks it | `answered:false`, `fact_ids:[]`, answer contains "don't want to guess"; question appended to `understanding.unknowns` with origin `runtime` |
| 5 | (EXAMPLE — replace me) Author validator: a script line "It does 145 km on a charge" with `fact_ids:[]` | line flagged unverified and excluded from voice + bundle; issue listed on the Facts card |
| 6 | (EXAMPLE — negative) Player with mic denied (`micDenied`) or no SpeechRecognition | intake shows the typed fallback within 10 s; check-ins still offer tap chips; demo completes to the handoff |
| 7 | (EXAMPLE — replace me) `POST …/feedback {message:"say the warranty before the price"}` in Rehearse | align agent returns a `revise('author', …)` action; status `building` → `ready`; bundle version increments |
| 8 | (EXAMPLE — replace me) `POST …/run/pitch {profile:{why:"25 km commute, replace my Activa"}}` | `route` non-empty, every `segment_id` exists in the script, establish segment last, a bridge with a figure but no fact id is dropped (`bridge_dropped` set) |
| 9 | (EXAMPLE — replace me) `POST …/run/lead {phone:"my number is 98765 43210", question:"kerb weight"}` and `{phone:"12345"}` | first → 200 with `phone:"9876543210"` and a file under `data/demos/<id>/leads/`; second → 400 |
| 10 | (EXAMPLE — replace me) `POST …/run/stt` with a 0.1 s WAV, `GET /api/voices?demo_id=` | 200 with a transcript (mock: "(mock transcript)"); voices lists Sarvam speakers when `SARVAM_API_KEY` is set, Gemini voices otherwise, and `chain` shows the fallback order |
| 11 | (EXAMPLE — negative) Player with an empty route (no proof blocks) | standard opening plays, then the closing + CTAs — no crash, no infinite loop |
| 12 | (EXAMPLE — replace me) Upload an `.avif` and a `.heic` image | accepted as `image`; `derived/*.jpg` created for the models; original served at `/media/…` |
| 13 | (EXAMPLE — replace me) `PATCH …/sources/{id} {use_in_demo:false}` then build | that source's visuals never appear in `bundle.json`; the registry still contains facts learned from it |
| 14 | (EXAMPLE — replace me) `GET …/faq-template` | Markdown grouped by category with suggested documents; `POST …/evals {questions:[…]}` returns per-question ✓/✗ and is listed by `GET …/evals` |
| 15 | (EXAMPLE — replace me) `GET …/usage` after one `/run/qa` | one `runtime` row with input/output tokens and a non-zero USD estimate |
| 16 | UI click-through (mock server, pane at 800×450): open `#/studio/<id>/align`, click **Approve** in the head of the 2nd card, click a thumbnail, click **Approve all** | Approve/Un-approve visible in *every* card head without scrolling tricks; the cards column scrolls; lightbox opens and closes on click; all five approved; no console errors |
| 17 | `MOCK_LLM=1 .venv/bin/python evals/qa_accept.py` (acceptance / failure QA) | 24/24: supported formats accepted (webp/png/jpg/avif/heic/mp4/mov/pdf/txt/docx), unsupported rejected 400 with the extension named, empty file 400, over-limit 413, corrupted media accepted and the READ stage still reaches `align`; path-traversal name stays inside the demo folder |
| 18 | `PATCH …/ {settings:{languages:["en-IN","hi-IN"]}}` then build (mock) | `bundle.languages == [en-IN, hi-IN]`, `alt_languages.hi-IN` has the same segment count with its own audio; `/run/tts {language:"hi-IN"}` returns a URL; the player shows a language chooser before Start |
| 19 | `GET …/trace` after a mock build; open the Observability tab | stages carry `seconds`; rows exist (mock Claude calls are traced); clicking a row reveals system prompt / input / response |
| 20 | `author.validate` on a script whose intro says "3.4 kWh … 15A … IDC" with audience=everyday | issue list names the jargon term and asks for plain language; route > 480 words is reported as over budget |
| 21 | Monkeypatch `sarvam.tts` to raise `RuntimeError("sarvam tts 402: No credits")`, call `voice.render_line` twice (mock off, gemini key present) | first call falls through to Gemini and trips sarvam; second call skips sarvam without calling it; `GET /api/voices` lists `unavailable.sarvam`; the voice stage log says "sarvam is unavailable … top up, then rebuild" |
| 22 | `translate._keeps_numbers("145 km certified, Rs 1,24,990", "१४५ किमी प्रमाणित, ₹1,24,990")` is True; with "१४० किमी" it is False; a mock build with languages en-IN + hi-IN reports 0 "kept in the main language" | translated lines keep every source figure; a changed figure keeps the English line and is counted in `logs/translate` |
| 23 | Run `visuals.align` on the Creta script in mock mode (rules fallback) | every line whose text mentions gear / DCT / paddle ends up on a gear or paddle image; `visual-audit.json.method == rules_fallback`; `logs/*-visuals.json` has a reason per change |
| 24 | Mock read → Align: `GET /api/demos/{id}` cards | `cards.script.segments` present with `timeline.total_seconds > 0` and every batch's spoken part ≤ 20.5 s (the check-in pause is counted separately); `cards.faq.total ≥ 1`; six approvals keys (visuals, facts, script, faq, persona, ctas) |
| 25 | Mock build → bundle | `bundle.fillers` has audio for every filler key; every `bundle.faq` entry with an answer has audio; `bundle.timeline.exact` is true after voicing |
| 26 | Player (pane): start with a spoken context, then ask a bank question, then a new question | recorded acknowledgement plays before the opening; custom batches play with their pictures after the opening; bank question answers with no model call (note "answered from the FAQ bank"); new question is preceded by the recorded "bear with me"; the voice never changes; no silent gap longer than 2 s |
| 27 | Mock read → script.json | `intake_q1` greets with brand + product and asks the only intake question; `intake_q2 == ""`; intro segments contain no second greeting, no digits, no "deciding"; closing contains the fit-summary shape; establish mentions an open question |
| 28 | `MOCK_LLM=1 .venv/bin/python evals/qa_deck.py` (slides-v1 player contract, end to end through the mock server) | every case ✅: no 3D anywhere (bundle, demo record, routes, index.html, player), line visuals are none/image/shot, runtime Q&A with every provider down declines + offers a callback with no cooldown, the FAQ bank still answers with no model call, MP4 export is 409, runtime providers default gemini → claude → runware with a ≤ 30 s request timeout |
| 30 | Phase 2 (in `qa_deck.py`): mock read with images → every image's `parts` are `{name, box{x,y,w,h} in 0-1, confidence 0-1}` plus `full_product`; a `hero`-role upload becomes `bundle.hero_image` and a second hero replaces the first; a demo with only a video gets one still per good shot (`derived_from` = shot id) and the best full-product still becomes the hero | all ✅ |
| 31 | Phase 3 (in `qa_deck.py`): mock read writes `deck.json` with one slide per segment plus hero open / closing / hero close; every callout ≤ 8 words, cites only registry facts, has a placement and (panel) no position; layout unit cases: confident part → overlay anchored at the box centre with the label inside the frame, off the box and clear of other labels; low-confidence or unlisted part → panel; callout validator drops uncited claims / unknown facts / > 8 words; `POST /revise {stage: deck}` bumps only the deck; `deck-overrides.json` title and dragged position win and reach the bundle | all ✅ |
| 32 | Phase 4 (in `qa_deck.py` + browser): `PATCH /align/deck` saves title / picture / callout text / fact ids / dragged position into `deck-overrides.json` and `deck.json`, un-approves the Script card, marks only `bundle` stale; an uncited claim, a 9-word callout, an off-picture position, an unknown picture → 400; unknown slide → 404; the edits survive `POST /revise {stage: deck}` and reach the bundle. Browser (mock server 8878): Align › Script card shows the filmstrip; Review slides opens the editor; a chip drags and Save keeps its position | all ✅ |
| 33 | Phase 5 (in `qa_deck.py` + browser): `bundle.slides` is the player's structure (hero open → content → closing → hero close; every content slide has a picture, lines and placed callouts); the player renders through `web/slide.js` (segment stage, media card and 3D gone); sync is event-driven — a line's callouts reveal before its audio starts, the last line's `ended` moves the slide, no timer in the line loop or the slide switch; the transcript logs an agent line only when its audio ends (`logHeard`), a cut-off line keeps the heard prefix (`currentTime / duration × words`) marked `interrupted`, and only that transcript is sent as history to `/run/qa`; the next slide is preloaded; motion is CSS-only and honours `prefers-reduced-motion`; an older bundle without `slides` still plays; the session record carries `slides` and `slides_visited`. Browser (mock server 8879, muted): intake → opening slides → decision frame → routed slides with check-ins, cross-fade between slides, panel callouts, a typed question mid-line logs "… Share your —" as interrupted, handoff shows 3 of 3 slides, session saved | all ✅ |
| 34 | Phase 6 (in `qa_deck.py` + browser): routing is plain code (`deck.route_for`, no model call): the current slide carries an answer fact → stay with its callout named; another slide carries the facts → jump with its callout; no facts but the question names another slide's topic → jump by topic; nothing → none; hero slides are never a target; every FAQ bank entry carries a `slide_id` naming a deck slide; `/run/qa` returns `slide_id` + `route` for bank hits and model answers (a decline never moves the slide); `/run/pitch` route steps name their slide; the player sends the current slide, a jump cross-fades + lights the callout + marks the slide covered and returns to the exact interrupted line (S.seg / S.line untouched — depth 1), a covered slide plays title + first line without a check-in. Browser (mock server 8879, FAQ entries seeded with a fact only sl04 carries): a question asked during sl03's second line → cross-fade to sl04 with `sl04-c1` lit, bank answer, "Did that answer it?", "Let's get back to where we were.", then exactly one sl03 line (the interrupted one) before its check-in; sl04 reached later plays one line and no check-in; the same-slide question keeps sl03 on stage (one slide in the stack) and returns the same way; the session record carries `covered: [sl04]`, `jumps: [sl03 → sl04]` and sl04 visited twice (32 s during the jump, 1.2 s later) | all ✅ |
| 35 | Phase 7, local side (in `qa_deck.py` + browser): `storage.backend()` defaults to local; `STORAGE_BACKEND=aws` without credentials falls back to local and says why; the AWS backend is the local one plus DynamoDB rows, the S3 mirror and pre-signed media; `/run/session` keeps the player's id (Done, Stop and the tab-close beacon update one record), writes the summary in the background once the session ended (mock: no model call) with the record's own facts copied by code (name, questions, slides + seconds, CTA, leads) and the model's fields (context, cared about, objections, unanswered, opening line), and keeps the summary when nothing new was heard; `GET /sessions` lists without transcripts; the share link shows the summary with phones masked and no transcript, a wrong key → 403; a lead without consent → 400 and a lead records the consent line it was shown; the player shows one consent line; Studio has a Sessions page and a read-only share route; local media still served by the app; the instance-role policy names only the bucket and the three tables. Browser (mock server 8879): Studio › Sessions lists the sessions with `storage: local`, the detail shows the summary boxes, the transcript with its interrupted line and the share link; the share page renders read-only (no transcript), a bad key shows "This link is not valid"; the consent line sits above the lead form's submit button | all ✅ |
| 36 | Phase 8 (in `qa_deck.py` + browser): every customer turn carries four stamps — voice ended, STT done (server STT, browser recognition, or typed = both at submit), QA done (on the response), first answer audio (when the audio or its caption starts) — on the session record (`turns`); `/trace` returns `latency` with n / p50 / p95 per stage (stt, qa, tts, total; nearest rank; a turn without answer audio counts only for stt and qa) split by answer source; Observability shows the panel; `/web/*`, `/` and every `.js/.css/.html` carry `Cache-Control: no-cache` (a 304 on revalidation), APIs unchanged. Browser (mock server 8879): a typed question then Done → the session record carries one turn with all four stamps (typed: stt 0 ms, qa 16 ms, first audio 20 ms, total 36 ms, from the bank, route jump); Observability shows the Answer latency panel (1 turn · 1 session · 1 from the FAQ bank) with p50 / p95 per stage, served with `Cache-Control: no-cache` | all ✅ |
| 29 | Post-author visual audit with real Gemini (paid only when approved) | every allowed image ref and every script line id appears exactly once in the batch audit; image rows list visible features/limitations; concrete feature lines bind an image only on `coverage=full`; partial/missing lines have no image and fall back to the hero + cited card |
| 37 | Part 1: `MOCK_LLM=1 .venv/bin/python evals/qa_deck.py` includes `evals/provider_contract.py`, using fake provider clients/HTTP and a blocked network | Runtime Gemini → Claude → Runware and build Claude → Gemini → Runware; all-down decline + callback; mock isolation; JSON repair, per-attempt billing/traces, shared timeout budget, duplicate-task rejection; grounding and text-only boundaries; tier defaults/overrides and unchanged media models; exact pricing, native cost and UTC promotion boundary; Gemini thought-token billing; extracted-PDF fallback and no repeated exhausted chain; read-key guards; Claude schema recovery preserves its model and limits. See `docs/runware-fallback.md`. |
| 38 | Part 2 free customer contracts: `qa_deck.py` imports `customer_contract.py`; `python evals/player_browser.py` then Run checks in the in-app browser at desktop width (synthetic APIs/audio/speech, CSP blocks external connections) | Content29/29: one intake, no invented context, clarification-first grounding, complete qualified labels, stable reviewed overrides, old step metadata. Browser14/14: silence, yes-but, stale speech, typed clarification, callback hold, phase/jump return, late responses, legacy deeper question, consent decline/completion/session stamps, buyer-facing recap without internal scores, reveal geometry and native-aspect wide/narrow images. Actual speech recognition, source accuracy and paid latency require the real run; this free gate cannot certify customer readiness. |

### Narrative role supplement — 2026-09-19

| Contract | Expected and recorded result |
|---|---|
| `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/narrative_roles_contract.py` | 6/6 groups: production Plan → Author payloads carry goals, exact visual order and editorial notes; distinct planning/delivery prompts; approved facts and complete conditions retained, held facts/hidden images filtered; locked voice and single intake preserved; an actual rejected-citation draft enters the local rewrite; draft persistence does not approve, publish or generate audio. Temporary storage, mocked provider boundary and zero outbound attempts. This is not model-entailment or live-quality proof. |

### Cinematic/source supplement — 2026-09-18

| # | Input | Expected |
|---|---|---|
| 39 | `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/align_review_contract.py` | 42 free contracts: both F/C facts are reviewable without merging storage; truth and source corrections validate against the existing schema and source records; invalid/blended/cross-role provenance and non-boolean approvals reject atomically; chat edit/reject uses the same boundaries; approved C facts remain gated by competition; one intake/check-in/title/outcome edits preserve line behavior, clear stale question audio, invalidate downstream work and cannot introduce uncited claims or a second intake. Provider/network calls are blocked. |
| 40 | `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/generation_contract.py` | 23/23 free generation-input/approval contracts: actual product/rival extraction receives shared truth/scope rules; plan/author/deck/build FAQ/runtime receive full product quotes, locators, conditions, units and evidence rules; the deck permits a neutral specification or omission when scope cannot fit; rejected/unknown plan references are filtered; legacy fact defaults remain compatible; complete technical deeper/Q&A responses reach the next stage unchanged. Providers/network are blocked. This proves context wiring and deterministic filtering, not model entailment. |

`evals/player_browser.py` now serves19 browser cases. All original14 behavior cases remain; five new cases cover exact anchors through resize without saved edits changing, readable narrow evidence, opening/closing native ratios, stable crowded fallback and tall-image/wrapped-evidence separation. Last actual browser result19/19; synthetic media is not a real voice test.

`MOCK_LLM=1 .venv/bin/python evals/source_contract.py` covers rival PDF/text isolation, official source metadata validation, retained applicability/provenance and rejected-citation handling. Run it with the other required gates before accepting the real comparison pipeline.

NX14/NX16/NX18 real-review fixtures: `evals/fixtures/generation_grounding.json` contains 12 synthetic cases for ordinary versus certified evidence, explicit ratings, flood/luggage overreach, cross-engine arithmetic, trim/fuel scope, introductory finance, unit retention, conflicting sources, appropriate unknown resolution, direct natural feature answers and unsupported fuel-cost benefits. Review applicable raw plan/script/deck/FAQ outputs before manual polishing; record repeat failures candidly. No paid probe is started by the free contract. Re-Read still needs a snapshot/map/API-reapply of human-reviewed facts; these changes do not alter review preservation.

Second real Read evidence is frozen in `output/nexon-real-evidence/iteration-2/raw-read/`; `raw-generation-review.md` records repeat failures despite an empty script issue list: ordinary volume called certified, broad safety/trim claims, omitted higher-later finance scope, and new spec-to-performance benefits. Units and the full finance FAQ improved. The raw deck retained its older benefit-only prompt, which has now been aligned with the shared evidence rules; this later prompt fix has only free input-envelope verification, not a paid generation result. A saved I1 rating callout also cited a reassigned I2 fact ID; no prompt change repairs that review-identity risk.

## Golden set — paid/graded evals (real keys; runs ONLY with approval)
| # | Input | Reference output / must-haves | Check (exact / contains / rubric) |
|---|-------|-------------------------------|-----------------------------------|
| G1 | (EXAMPLE — replace me) iQube images + TVS URL → Read | registry contains battery warranty "3 years / 50,000 km" and ex-showroom prices with citations to the URL source | contains |
| G2 | (EXAMPLE — replace me) Same → Plan | first two segments after welcome address range and charging; a visual gap notes "no shot of the charging port" or similar | rubric: segments match the category's top buyer concerns |
| G3 | (EXAMPLE — replace me) Q&A "does it have an engine?" | explains it is battery-electric with a hub motor, cites a spec fact, `answered:true` | contains: "no engine" or "electric"; fact_ids non-empty |
| G4 | (EXAMPLE — must-refuse) Q&A "can you give me a better price?" | no discount promised; escalates to a person; no invented number | rubric: no new numeric price/discount in the answer |
| G5 | (EXAMPLE — must-refuse) Q&A "is Ather better?" | declines to compare other brands; suggests what to compare on | contains: refusal to compare |
| G6 | (EXAMPLE — replace me) Align message "F003 is wrong — the value is ₹1,08,993" | `edit_fact` action on F003; Facts card shows the row as edited; author stage marked stale | contains: action type edit_fact |
| G7 | (EXAMPLE — replace me) Align message with an attached PDF spec sheet | `revise('understand', …)` action; registry grows; approvals for visuals/facts reset | rubric |
| G8 | (EXAMPLE — hard) Product with NO documents (images only) | registry empty; unknowns ≥ 8; plan still produces segments whose goals say the sources are silent; every scripted line passes the validator | rubric |
| G9 | (EXAMPLE — replace me) Rehearsal on the iQube demo | coverage ≥ 0.6; gaps include at least one genuinely unstated item (weight/delivery) | rubric |
| G10 | (EXAMPLE — replace me) Voice: persona sample renders with Sarvam Bulbul (falls back to Gemini) | a WAV under `data/demos/<id>/audio/`, playable on the Persona card; `voice_provider` in script.json says which provider produced it | exact: file exists |
| G11 | (EXAMPLE — replace me) Pitch plan for "I need at least 100 km range" | `customer_state: stated_want`; follow-up asks whether it's one long day or charging less often (P03); route leads with the range proof block | rubric |
| G12 | (EXAMPLE — replace me) Pitch plan for "45 km commute, want it cheaper than petrol without range worry" | `customer_state: stated_need`; decision frame recaps 45 km + cost + range in the buyer's words; bridges cite fact ids | rubric |
| G13 | (EXAMPLE — replace me) Script scorecard on the iQube demo | total ≥ 14 on first build; `weakest` names concrete rewrites | rubric |
| G14 | (EXAMPLE — replace me) Demo language = Hinglish | intake q1 and proof lines in Devanagari-mixed Hinglish, product names/units unchanged; Sarvam TTS renders `hi-IN` | rubric |

## Run journal (paid/slow checks only)
| Date | Hypothesis (changed X, expect eval N to flip because W) | Result | Cost note |
|------|----------------------------------------------------------|--------|-----------|
| 2026-09-03 | First real run of the iQube sample (part of "build the whole thing", not a per-change eval): expect G1 (registry has warranty + prices with citations) and G10 (Sarvam sample) to pass; G9 coverage ≥ 0.6 uncertain with images-only visuals | G1 ✅ 71 facts, warranty F027/F028, prices per variant · G10 ✅ Sarvam sample + 68 lines · G9 ❌ coverage 0.50 (gaps are genuine source gaps: on-road by city, replacement battery cost, boot litres, service cost; plus 1 must-refuse) · scorecard 17/20 | ~1 read (Claude ×1 big + Gemini ×1) + build (Claude author ×2, rehearsal ×13, scorecard ×1; Sarvam ×68) |
| 2026-09-03 | Paid QA run 1 — images + spec text, English + Hindi (`evals/qa_real.py images --lang hi-IN` → `dm_f79d9170`): expect opening ≤ 115 words, a `features` block, no jargon in narration, Hindi bundle with audio, all four runtime probes behaving (grounded / grounded / no negotiation / decline + callback) | ✅ opening 111 words, roles intro·outcome·proof×4·features·establish, 496 words total; hi-IN alt bundle with audio; probes: range grounded (F001/F010), kerb weight grounded, discount → cites the written HDFC offer and refuses to negotiate, Ather → decline + callback. Build 958 s (voice 613 s = 64 % → parallelised after this run), cost $2.50 (Claude 91 %) | read: Gemini ×1 + Claude ×1 (facts) + Claude ×3 (plan) · build: Claude author ×2, translate ×1, rehearsal ×13; Sarvam ×96, Gemini-TTS ×10 fallbacks · runtime: Claude ×5 |
| 2026-09-03 | Paid QA run 2 — dummy 20 s video + images + spec text, English (`evals/qa_real.py video` → `dm_78890026`): expect the video shots to be used as visuals, opening ≤ 115 words, the same four runtime behaviours, and the voice stage well under the first run after parallelising | ✅ opening 92 words, 486 words, roles intro·outcome·proof×4·features·establish; voice 68 s (was 613 s); probes all as expected; 2 lines without audio (browser voice); build 400 s, cost $2.20 | read: Gemini ×2 + Claude ×1 + Claude ×3 (plan) · build: Claude author ×1, rehearsal ×14; Sarvam ×55 · runtime: Claude ×5 |
| 2026-09-05 | Paid performance attempt 1/3 — real CRETA N Line screen recording → TRELLIS.2, supplied images/PDF for content, and the 20 s audio film after the needs question; expect a reviewable GLB, one consistent human voice with Sarvam primary/Gemini fallback available, and greeting → needs → film → spoken return → personalised interactive demo | ❌ stopped at provider preflight: Sarvam produced valid WAV, forced Gemini fallback returned no audio; no Runware or content build attempted | 1 short Sarvam TTS + 1 failed short Gemini TTS |
| 2026-09-05 | Paid performance attempt 2/3 — inspect and repair Gemini's current TTS response contract, prove the forced fallback with playable audio, then run the real CRETA 3D/content/player flow; expect provider preflight and all end-to-end gates to pass | ⚠️ provider gate passed and real content reached Align (67 facts, 20 FAQ entries, 364-word script, no unverified lines); Runware returned a valid 6.2 MB GLB, but visual QA rejected floating artefacts reconstructed from the recording's UI pins | Gemini fallback WAV + $0.0192 Runware + one real content read/author/FAQ pass; build not started |
| 2026-09-05 | Paid performance attempt 3/3 — use the configured cheapest Gemini image model to remove only the screen-recording UI pins from the real primary frame, visually verify identity, then regenerate TRELLIS.2 and complete the already-reviewed content build; expect clean 3D, all-Sarvam narration, and the exact greeting → needs → audio film → spoken return → interactive route | ✅ Gemini image edit was unavailable (429, free-tier quota limit 0), so five real frames were cleaned locally; TRELLIS.2 produced a visually accepted 5.7 MB GLB. Final demo `dm_af65dad8`: 67 facts, 20 FAQ, 364-word script; live family profile routed safety → family → cabin, bank Q&A was instant; browser QA proved greeting → typed needs → full-stage audio film → spoken return → 3D-led walkthrough. Integrity QA found five fallback narration files (two with implausible durations), re-recorded all five, rebuilt the exact 186.3 s timeline, and proved all 99 spoken entries are non-silent Sarvam `aditya`. Final fixes preload the complete audio route, cover waits politely, direct/hold the 3D camera from narration, and stop automatic/manual image mismatches. | one failed Gemini image request + $0.0186 Runware + one real content build + Sarvam narration/fillers + one runtime pitch call |
| 2026-09-05 | User-authorised 3D fidelity comparison — Rodin Gen-2 receives all five real screen-recording views with front ¾ first; expect the mixed black/silver source identity and vehicle silhouette to survive with fewer single-view reconstruction artefacts than TRELLIS.2 | ✅ Rodin attempt 4 approved: 11.9 MB GLB, 51,691 vertices / 91,200 faces, PBR 2048 texture. Offline renders preserve the SUV silhouette, windows, lamps, wheels, silver/grey cladding and red rear-light accents; TRELLIS.2 was substantially darker and lower-detail. Tripo spend was not justified after the decisive comparison. | exact Runware cost $0.40 |
| 2026-09-05 | Source-sync script repair — split the overloaded Creta lines by visible subject, move the second needs question before the film, and re-record only changed lines; expect every narration line to have one literal image/card target while retaining Sarvam `aditya` throughout | ✅ `dm_c6a354fd` ready at 198.0 s. Main narration: 4 model / 13 evidence / 14 card lines; all 81 spoken route/filler/intake entries validated. Three browser profiles verified needs → focus → film → return → tailored route. Final run caught and fixed stale roadmap evidence, multi-claim visual overreach and the early typed-intake race. Free regression: Runware 17/17, Visual 21/21, sync 18/18, uploads 24/24, smoke end-to-end. | changed lines rendered through Sarvam with cache reuse; three authorised runtime pitch QA calls; no further 3D spend |
| 2026-09-05 | User-requested post-script Gemini proof pass — expect all 13 CRETA images and all 60 script lines to be audited from pixels, with partial matches removed rather than treated as proof | ✅ bundle v11. Gemini returned complete coverage for 13/13 images and 60/60 lines; deterministic enforcement corrected 29 assignments and routed 18 uncovered multi-feature/detail lines to the 3D/card fallback. Browser QA confirmed one intake question → film → return and a two-row keyword card over the 3D model. | 2 Gemini 3.6 Flash vision calls (12-image + 1-image batches); no Runware or speech spend |


## Locked voice supplement — 2026-09-18

| # | Input | Expected |
|---|---|---|
| 41 | `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/voice_lock_contract.py` | 27 free cases: chosen provider/speaker preserved across build and runtime; matching cache available during breaker/missing key; mixed FAQ/filler references replaced; all spoken branches checked; partial build fails before bundle and a later build synthesizes only missing clips; Gemini content refusal has no retry/fallback; locked Cloud remains mocked; Sarvam requests paced across calls, HTTP429 only with max3 attempts, numeric/date Retry-After honored, long waits stop explicitly. No live provider or network calls. |

The conservative Sarvam start interval is 2.1 seconds, based on the published Bulbul v3 Starter floor of 30 REST requests/minute: https://docs.sarvam.ai/api/getting-started/ratelimits. Actual account limits are not inferred. The failed real first build remains an unsuccessful first attempt; only the next authorized real Build can verify the repaired path acoustically.

## Direct FAQ review supplement — 2026-09-18

| Input | Expected |
|---|---|
| `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/faq_review_contract.py` | 41 free contracts: exact human answer retained through normal Build and unchanged-registry reuse; all approved F/C references and competition rules enforced; mixed/held/unknown/uncited claims rejected atomically; stale/partial/running banks rejected including graph stage gaps; identity/hash/unrelated rows preserved; old audio and derived metadata cleared or recomputed using current script citations; only FAQ approval and dependent audio/rehearsal/bundle invalidated; current-slide runtime route derived; excluded visuals cannot return through cached associations; no provider/network calls. Semantic claim-to-evidence review remains human. |
| Align → Script → Preview, wide and narrow browser | Customer-style cinematic slide in a bounded preview shell, with the reviewed image/title/evidence; no player controls; native editable slide positions unchanged. Visual verification is required separately from syntax tests. |

## Narrow cinematic leader supplement — 2026-09-18

| Input | Expected |
|---|---|
| Free `evals/player_browser.py` harness, new twentieth case; wide browser with simulated slide widths1000→390→304→1000 | The ≤699px layout hides both overlay label and its dependent SVG leader, retains visible numbered dot/evidence rail, and restores visible label/leader at wide width. Native anchor coordinates remain unchanged. Run through the browser; source and syntax checks are not visual proof. |

## Runtime routing and media delivery supplement — 2026-09-18

| Input | Expected |
|---|---|
| `MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/runtime_delivery_contract.py` | 27 free cases in isolated data/graph storage: actual bank/live API routing uses reviewed script citations over stale deck deeper lines; correct stay/decline behavior and unchanged saved design; a held fake pitch/QA/TTS/STT call permits cached media and health on the same ASGI event loop; worker/contextvars, language/refine/live/strict-voice arguments and HTTP502 behavior preserved. All network/providers blocked; no production changes. Provider latency and worker cancellation are not guaranteed by offloading. |


### NX25 personalized evidence — 2026-09-18

`evals/player_browser.py` now serves23 browser cases: the prior20 plus three real-DOM personalized-slide checks. Complete reviewed boot text and the reviewed boot picture win over a prior cabin; a callout containing an extra uncited fact cannot be borrowed; long facts are omitted instead of clipped; short full conditions/truth survive and rejected facts do not display. The fixture also confirms the original reviewed slides stay unchanged. Actual CUA execution passed23/23; evidence is in iteration-2 `screenshots/browser-23-contract.txt/png`. Synthetic audio remains distinct from acoustic validation.


## Headline policy terms supplement — 2026-09-18

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/generation_contract.py` now passes27/27. Four added free input-envelope cases exercise real QA assembly for build FAQ and runtime, pairing a synthetic unknown duration/distance relationship with explicitly supplied “whichever occurs first” and an exclusion. Exact values, quotes, locator, contractual classification and conditions must reach each provider envelope together with the generic headline-policy rule. The new cases failed before the prompt change (23/27); no provider or network call occurs. This is not a model-following or semantic-accuracy test; actual live warranty wording must still be reviewed.


## QA question ownership supplement — 2026-09-18

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/generation_contract.py` passes33/33. Six added input-envelope checks invoke real QA assembly for greeting/ordinary/clarification replies through build and runtime, verifying the player owns the satisfaction check, ordinary answers are statements, and only the existing clarification field asks one identical question. The ambiguous technical-detail offer instruction is replaced with a statement instruction. With the previous ownership wording restored in memory, the six new cases fail (27/33). This does not prove future model compliance or fix the player by itself; no schema/provider/voice/matcher change or paid call is part of this patch.


### NX29 typed input preference — 2026-09-18

Two `evals/player_contract.html` cases exercise the actual player with fake speech events: the initial spoken flow still opens listening; beginning to type cancels that capture; typed intake, check-in and Q&A do not reopen it; late ambient output is ignored; the visible explicit mic sends speech and restores voice waits. Restart retains typed preference until the intake mic is explicitly tapped. These regressions passed the final coordinated 30/30 CUA run; the actual B typed intake, Q&A and 35.5-second clarification hold also kept the mic closed. They prove input ownership, not real-device recognition quality. No paid call or third Build is part of this fix.


## Ended-session timing and announced Q&A jumps — 2026-09-18

| Input | Expected |
|---|---|
| Free browser harness `evals/player_browser.py`, NX27 virtual-clock cases | Stop→180s→Done→120s→pagehide retains one ended session's elapsed and final-slide dwell. Back adds only active time, subsequent slides retain correct dwell, Restart clears the cutoff, and an intentional new question after Done reopens the same session without idle inflation. |
| Free browser harness `evals/player_browser.py`, NX28 jump cases | Existing cached transition is heard before the view changes; no TTS request for that clip; held bridge does not stamp first answer audio. Actual answer does; cancellation prevents a late jump/answer. Missing cache uses the normal selected-voice speak path; return remains the exact interrupted line. |

These add five cases to the browser contract (the prior off-slide case also gains its transition assertion). Browser execution is required; syntax checks alone are not behavioral proof. No real provider call or Build is part of this harness.


## Focused comparison envelope supplement — 2026-09-18

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/generation_contract.py` passes35/35. Two new build/runtime comparison cases inspect the actual provider envelope for the60-word total budget, direct-one-sentence allowance, at-most-two relevant attributes, scope-before-brevity priority, both synthetic variants' conditions, buyer context and full verification caveat. New cases fail under the previous prompt (33/35). No generated prose is scored as semantically correct by these mocks; live B Q07's88-word catalogue and omitted BNCAP date remain recorded failures until a focused rerun is reviewed.


## Live Q&A response allowance — 2026-09-18 (NX30)

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/qa_deck.py` includes five budget regressions in `evals/provider_contract.py`. The actual live QA→runtime→Gemini→installed SDK path receives max_output_tokens 3,000 with the existing model/timeout and no explicit thinking configuration; a complete fake approved answer retains its citation and prevents later fallback. Billing includes candidate plus thought tokens. Build-time QA and unrelated runtime calls retain 1,500. All transport is fake and sockets are blocked. The 60-word spoken prompt is separate from this structured-response allowance. This free test does not prove a live provider will finish within 3,000 tokens; actual B Q08's malformed response and declined comparison are retained for a focused customer rerun.


## Shared Gemini cold initialization — 2026-09-18 (NX31)

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/gemini_client_contract.py` passes 7/7 in isolated storage. Two concurrent callers use exactly one fake SDK client, preserve its transport during both in-flight calls and retain the original 90-second client initialization setting; missing-key and constructor failure paths release correctly. The real initializer failed four race checks before the lock (3/7). No real SDK constructor, provider or socket is used. Logs are in iteration-2 `free-regression/gemini-client-before.log` and `gemini-client-after.log`. This repairs shared-resource initialization under runtime worker concurrency; it does not promise provider availability, latency or complete JSON.


## Complete phone qualifiers — 2026-09-18 (NX25 follow-up)

The browser contract adds one case (31 total) using the exact reviewed “Creative+PS/Fearless+PS petrol/diesel: 60:40 rear seats” label alongside the boot-capacity label. At390→320→304→390px, full text stays unchanged, painted text fragments and scroll width stay within their own cards, type remains at least 12px, and neither the two-card rail nor page overflows horizontally. This catches a real overflow hidden by prior space-separated synthetic labels. The root must run the browser harness and inspect the actual phone result; no provider call or extra Build is required.


## Follow-up opener preserves unresolved status — 2026-09-18 (NX33)

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/summary_contract.py` passes10/10. The exact actual-C readiness promise is supplied as a fake model response to the real `summary.summarize` function; unresolved topics, non-callback escalations and model unanswered questions independently force a neutral invitation. Tests retain context/interests/objections/unanswered fields and untouched input status; resolved sessions keep their specific opener; callback bookkeeping alone does not imply a missing answer; mock uses the same safeguard without a runtime call. A captured provider envelope checks the explicit prompt prohibition and unchanged1200-token setting. Before-fix4/10 and after-fix10/10 logs are in iteration-2 `free-regression/summary-{before,after}.log`.

No network/provider calls or saved-session writes occur. The failed C snapshot remains evidence, not retroactively corrected history. The deterministic check covers only the proposed opener; other summary semantics and a live post-fix session still require review. Root owns the coordinated broad gates.


## Direct customer wording retention — 2026-09-18 (NX32)

The player browser harness now has 32 cases. The added case submits a direct statement during held narration, confirms normal QA dispatch and exact followup in the next request, repeats intake/statement without duplicating retained context, verifies no inferred focus change and checks the saved recap. The existing clarification case requires the original question plus the exact clarifying question/reply once, with skip_bank and transcript preservation unchanged. Root separately added a prompt-level need/context-correction rule; the browser test proves storage/delivery only, not model consultation quality. Real failed-session evidence remains unchanged; actual recovery and refreshed CUA acceptance are separate checks.


## Pitch additions and material qualifiers — 2026-09-18 (NX34)

`MOCK_LLM=1 CLOUD_SYNC=0 .venv/bin/python evals/pitch_grounding_contract.py` exercises the actual pitch assembly, filtering and fake speech path:19/19, versus9/19 before. Cases reproduce the observed warranty relation/predictability, installation bridge and properly-secured child-seat additions; test missing ISO basis; preserve documented relations, qualified quantities, plain equipment, neutral bridges and a proposed personal fit-check. Rejected optional content never reaches voice and the reviewed route remains. Provider/network calls and source/script writes are blocked. Logs: iteration-2 `free-regression/pitch-nx34-before.log` and `pitch-nx34-after.log`. `qa_deck.py` also runs these19 cases and the10 summary cases. Independent review added two quote-only measurement-basis cases:19/21 before the follow-up,21/21 after. The deck gate now includes21 pitch cases plus10 summary cases. Conditions and source quotes both supply named standards; numeric evidence admits their exact codes. These are bounded lexical omission checks plus prompt-input tests, not proof that all paraphrases, conditions or language variants are entailed by their citations.
