# Script pipeline code QA and FMEA — 24 September 2026

**Result:** the reviewed code and free regression gates are green through iteration10:25suites,1,069reported overlapping checks/groups/phases. Two PDF integration defects and the later visual-fallback overwrite defect were fixed and covered. No unresolved P0 or P1 code finding remains in this diff. A cooperative PDF deadline/resource limit remains a P2. This is not blanket approval of a generated narrative, live-model quality or acoustic delivery; the preserved iteration05 narrative audit and separate06 image-binding delta distinguish those surfaces.

**Scope:** `git diff 582ae1a` in `codex/crack-the-script`, including the working changes through iteration10: ten application Python files, six Python contract files and one JavaScript module. Two archived QA helpers bring Python compilation coverage to18files. Bulky model request/response transcripts are excluded from the code scan; their narrative audits remain separate evidence. Documentation and the Understand/Build diagrams were checked against the implementation. No source code was changed by this review.

**Product context:** [PRD](../../../PRD.md), [architecture](../../ARCHITECTURE_FLOW.md), [Learning](../../../Learning.MD), `.power-coding/config.json`, and the user's current overrides. The app must keep Sources → Read → Align → Build → Rehearse, approved evidence, literal visual checks, the 495-word default preparation margin and measured 180-second default publication gate. The goal script is a reference, not permission to weaken validation. The user separately approved embedded PDF picture extraction inside Understand. No schema, graph, library-order or claim-validator change was authorized or made.

The scan uses the twelve-category protocol from [power-coding](/Users/macbook/.agents/skills/power-coding/SKILL.md). Configuration thresholds are P0 ≥200, P1 100–199 and P2 <100. Existing deployment constraints are a single uvicorn worker on an EC2 t3.micro with approximately913MiB RAM, 2GiB swap and20GiB disk. The requested full QA authorizes this scan; no paid evaluation was run.

## What changed and why it stays within scope

- **Writing guidance:** Coach defines supported buyer choices within exactly the existing category stops. Planner allocates distinct evidence, exact trim/engine/gearbox qualifications, three powertrain batches for the default compact-SUV story, at most two at other stops, and two final closing statements. Author receives complete26–33-word main batches, disjoint overview/proof evidence and literal picture subjects. These are prompt instructions; the existing validators still decide what is acceptable.
- **Coach cache:** `server/agents/coach.py:260` formats the same system prompt used for the provider call and includes it in the cache identity. A guidance change now regenerates the playbook once; another unchanged run reuses it. Evidence bytes do not change.
- **PDF pictures:** `server/sources.py:24` extracts bounded embedded images using already-declared pypdf and Pillow. `server/agents/understand.py:149` registers them as derived children with the parent PDF ID, revision, page/resource occurrences and normalized image hash. The original PDF remains the fact source. Images enter the existing image-tagging batches and visual checks; no invented part boxes, image-derived facts or special simulated-proof bypass was introduced.
- **Parent ownership:** `server/store.py:553` requires a derived picture's current enabled PDF parent and matching revision. Missing, deleted, revised, excluded, competitor, scope-excluded and inactive parent sources cannot authorize derived images. Ordinary unknown legacy upload IDs keep their prior behavior.
- **Publication and UI:** the same allowance now filters image enhancement and every Bundle image surface, including line visuals, alternate languages, slide pictures, attached callouts, catalogue and fact/image map. Remaining reviewed pictures keep their own labels. `web/studio/sources.js:67` hides only PDF child rows from the upload list/count/empty state; the parent PDF and ordinary upload workflow remain visible, and Visuals still reviews extracted pictures.
- **No-verdict visual fallback:** `server/agents/visuals.py:338` retains the already validated Author bindings, including explicit `none`, when there is no pixel decision. Lexical matches and unused-image suggestions remain recorded proposals. The successful pixel-audit path, its rejection rules, model prompt and output schemas are unchanged; this removes an unsupported reassignment rather than granting any new proof status.

The final extraction limits are **96 unique pictures across at most10 PDFs, 48MiB normalized bytes combined, 8MiB per encoded/normalized image, 12million pixels, 2048px normalized edge, 100pages and256 candidates per PDF, a64MiB PDF file limit, and a shared cooperative30-second extraction budget**. Page-first sampling gives each page two candidates before additional gallery pictures. These are finite resource controls, not an operating-system memory or wall-clock sandbox. At the existing12-image provider batch size,96 additional pictures can require up to eight additional image-tagging batches; normal visual auditing may add its existing calls. No such paid calls were made in QA.

## Protected code verification

Independent source/AST comparison against `582ae1a` found the following byte-for-byte unchanged:

- Entire `server/schemas.py` (including `ScriptOut`), `server/graph.py`, `server/agents/playbooks.py`, `server/agents/narration.py`, `server/agents/plain_terms.py` and `requirements.txt`.
- Exact function source for `author.validate`, `author.run`, `coach.validate` and `plan.run`.
- The three protected assembled rule constants below. The concatenated runtime value was compared, not merely an assignment name or a substring.
- For the iteration06 delta, `visuals.MODEL_SYSTEM`, `_vision_batches`, all15top-level visual functions/classes other than `align` (including `Assignment`, `ImageAudit`, `VisualsOut`), and the exact AST of `align`'s authoritative pixel-decision try-body match the baseline. The only changed behavior is removal of the two heuristic assignment passes after no pixel verdict; audit wording now says existing assignments were retained.

| Protected value | SHA-256, equal to baseline |
|---|---|
| `TRUTH_RULES` | `accc4a45ca633eb7eb1892666a890c3c88ec39b0f3f3142dc2d03222e609fa26` |
| `EVIDENCE_RULES` | `8439fc97e7bb88f44a2e556281a61050c3aeede263c52a6501577699b98280fd` |
| `PRINCIPLES` | `128acf19b64ad1b49b56274006f208ab0f1135d9f3ff088d1690de44eeeac8e3` |
| `author.validate` exact source | `996e65be886a79822959f31b4f40cb88e5cab428a522056474f5d33dd8e021b9` |
| Entire narration module | `e083f5c226a45782e834daf881ca0981ab98f6eba4954a6ea8261dc699d98dff` |

The new40-group prompt contract assembles real Coach/Planner/Author requests across four supported categories and three audience levels, and checks grounding, rejected facts, numeric claims, valid image bindings, standalone complete-line splitting, unchanged category order and the495/180 defaults. `PS` in everyday main narration still raises the existing jargon warning; exact supported quantities can remain in deeper. Prompt prose cannot override that validator.

## Findings fixed during implementation and review

Scores below describe each defect **before its fix**, to make prioritisation reviewable. Closed findings are not open merge blockers.

| Finding / location | User effect and cause | S | O | D | RPN | Priority / disposition |
|---|---|---:|---:|---:|---:|---|
| No-pixel fallback overwrote literal Author image bindings; `visuals.py:338` | Metadata overlap and unused-image coverage replaced correct pictures or explicit none without a pixel verdict. Iteration05 changed11/16main bindings despite empty issues, including wheel→seat buttons and engine→instrument screen. |6|5|6|180|P1 — **fixed** by retaining validated draft bindings and logging proposals only;25/25regressions pass, versus11/25before. |
| Derived pictures escaped parent exclusion in saved publication paths; `bundle.py:44,130,205` | A deck saved before PDF exclusion/revision could still publish that child's picture or attach its labels to a different remaining picture. Earlier filtering covered the catalogue but not every serialized path. |7|4|6|168|P1 — **fixed** by one allowed image map and picture-owned media/callout filtering. |
| Timed-out PDF extraction could poison later cache reuse; `understand.py:182` | A partial extraction became the apparently complete cache, so Retry could indefinitely omit useful source pictures. |5|4|7|140|P1 — **fixed** with an explicit `interrupted` marker that prevents reuse until a complete extraction succeeds. |
| Coach cache omitted changed system guidance; `coach.py:260–265` | A user could rebuild the same sources after prompt improvement and receive the stale playbook. |5|5|5|125|P1 — **fixed** by hashing the formatted provider prompt with the consumed evidence. |
| Conflicting prompt instructions for order, closing and complete lines; Coach, Planner, Author and principles | The same model was told both to preserve order and move an emotional stop, to reserve two final statements and add segment closings, and to write independent batches while sharing pronouns across them. These produced avoidable structural failures in replay. |4|6|4|96|P2 — **fixed in guidance**; actual narrative compliance still needs separate evaluation. |

The58-group PDF contract includes behavioral publication tests for parent exclusion, revision and removal in both main and alternate languages. It checks line/deeper/closing visuals, paired and legacy slides, picture URLs, labels, catalogue and fact/image maps. It also verifies the saved design, ordinary upload bytes and prior returned bundle remain intact. The media-focused cases stub only narration sufficiency to isolate this boundary; measured-duration behavior is independently covered by the narration and release contracts.

Timeout recovery tests retain the already extracted child, retry the interrupted manifest, preserve its identity and bytes, add missing pictures, and then reuse the completed result without duplicates. Corrupt PDF/image/cache, masks, file/pixel/byte/count/page limits, deduplication, stable IDs, concurrent parent removal and unchanged ordinary upload IDs are also exercised. Parent ownership and retry recovery are not merely prompt-string assertions.

Prompt reconciliation leaves the category library and order validator intact. It removes the old instruction to move delighters immediately after fundamentals, confines emotional emphasis to existing stops, reserves final closing statements instead of extra checkins, and distinguishes complete delivery batches from short legacy lines. The translation ladder now permits a supported function or buying choice alongside the visible subject without claiming that an image proves a function or outcome.

The visual fix is within the user's minor-code, guard-preserving scope. It changes no source authority, fact, picture, stage, schema, validator, approval, role or duration rule. In both `author.run` and the existing Align edit path, `author.validate` runs before `visuals.align`; unknown/excluded references remain cleared by that boundary, and publication applies current source allowances again. The fallback does not certify the retained binding: `rules_fallback`, null model and zero pixel findings remain explicit. It cannot override a successful pixel rejection. A provider outage therefore no longer manufactures a replacement from tag similarity.

The new `visual_alignment_contract` reproduces sparse-tag and unused-steering-wheel distractors, main/deeper/closing focus preservation, explicit none/null, empty catalogue, provider failure and empty pixel results. Fake authoritative pixel decisions still clear partial/none/not_visual coverage, permit full-coverage replacement and reject internally inconsistent full coverage with missing features through the real `_vision_batches` boundary. An Author-cleared excluded reference remains cleared after fallback. The contract records25/25after versus11/25before; the fresh strict runner reports zero outbound attempts. Fixtures substitute the pixel function/provider response only for these tests; no live pixels or provider semantics were inferred.

## Remaining code risk

| Finding / location | Effect and residual cause | S | O | D | RPN | Priority / recommended action |
|---|---|---:|---:|---:|---:|---|
| PDF deadline and memory controls are cooperative; `sources.py:40,52,92,96` | An unusually expensive PDF parser/resource enumeration/image decode can overrun30seconds before the next check and temporarily contend with the single small-host worker. Input, candidate, pixel and output bounds reduce exposure but do not cap decompression working memory or interrupt a running library call. |6|3|5|90|P2 — retain the documented limitation. Before higher-volume or untrusted bulk uploads, move this same extraction behind a bounded worker/process with enforced wall-clock and memory limits, with separate architecture approval. |

No hard30-second completion promise or production load acceptance is claimed. Repeated document revisions also retain old derived bytes for existing references; the per-run48MiB bound is not a lifetime storage quota. At the current single-builder scope this is a capacity consideration under the same resource finding, not a reason to delete previously referenced media.

## Twelve-category coverage

| Required category | Review outcome and evidence |
|---|---|
| `unhandled_error_paths` | PDF-level and per-image failures become explicit error/warning gaps; corrupt manifests rebuild; tagging outage preserves an untagged picture with no invented boxes. Existing stage/provider failure paths remain unchanged. No new unhandled path identified in the reviewed normal inputs. |
| `external_dependency_failures` | No dependency added. The no-pixel/provider-outage path now retains validated Author refs and none without treating metadata as authority. Successful pixel decisions remain unchanged and authoritative. The25-group visual contract exercises both boundaries; live availability, semantics and latency were not tested. |
| `race_conditions_and_state` | Registration reloads current metadata under existing store update behavior; a concurrently removed parent cannot be recreated. Parent exclusions/revisions are checked again at consumption/publication, and explicit child exclusion is preserved. Existing one-worker/single-writer deployment assumptions remain. |
| `resource_exhaustion` | Input/output/candidate/pixel/page/document bounds and shared extraction budget reviewed. Cooperative decoder/parser limitation is the open P2 above. |
| `security_access_control` | No endpoint, key, auth or source-fact authority was added. Child paths/IDs are derived locally, confined by existing store path resolution; missing/cyclic/stale/nonproduct parents cannot become independent allowed uploads. Publication escape was fixed and regression-tested. |
| `data_integrity_partial_writes` | Normalized asset replacement is atomic; cache validates revision/policy/file size/hash. Interrupted extraction can retain valid children but cannot be accepted as a complete reusable result. Parent PDF/original uploads and prior bundles are preserved. No-pixel fallback no longer silently rewrites line visuals, focus or explicit none. |
| `observability_gaps` | `pdf-images.json`, extraction warnings, tagging events, provenance and visual-audit method make deferred/error output inspectable. Fallback emits retained-assignments wording, records proposals separately and reports zero pixel findings. A rules fallback remains explicitly different from pixel proof. No new alerting/SLA was introduced. |
| `scale_and_load_failures` | At most96 added images and eight ordinary tagging batches are bounded, but aggregate paid latency and concurrent small-host capacity were not benchmarked. Existing single-worker scope and the open resource risk apply. |
| `billing_credit_mismatches` | No billing/credit code touched and no paid call made. Additional extracted pictures use existing providers in production and can increase normal image-tagging/audit cost; no zero-cost production claim. |
| `retry_idempotency_issues` | Stable parent/revision/pixel identity, duplicate-image handling, completed-manifest reuse and corrupt/timeout recovery are tested. The interrupted-cache retry defect is fixed. |
| `config_feature_flag_drift` | Every test is MOCK_LLM=1 with isolated DATA/GRAPH and blocked outbound sockets. No mock flag is disabled to capture prompts. Coach cache now varies with the actual formatted prompt. Live visual/model branches remain an explicit verification boundary. |
| `edge_cases_from_prd` | PDF-only input gains ordinary reviewable pictures; text-only/corrupt/excluded PDF inputs remain honest gaps. Claims remain PDF-cited, all approval/runtime stages are retained, and495-word preparation/180-second measured publication rules are unchanged. Unsupported reputation, performance and inferred trim claims still fail their existing evidence constraints. |

**Coverage:12/12 categories checked.** No additional independent finding in unhandled errors, external dependencies, races/state, observability, billing, config drift or PRD edge cases. Security/data integrity/retry findings are closed; resource/scale share the documented open P2. Scores are review judgements, not production incident frequencies.

## Follow-up prompt delta — iteration04 and proposed05

The prompt-only delta reviewed before the later06 visual fix, from `08bbbbe` to the05 prompt candidate, contains only Author/Planner/principles prompt text and two old literal-string test expectations in application/test code. Seven protected files remain byte-identical: schemas, graph, category library, narration, plain terms, runtime graph and dependencies. Every function/class in Author, Planner and principles is unchanged. `TRUTH_RULES`, `EVIDENCE_RULES`, `PRINCIPLES`, `CUSTOMER_STATES` and `SIGNPOSTS` remain unchanged. Each changed test file equals its baseline after exactly one expected closing-wording substitution; no behavioral assertion was removed. All17 explicit static checks pass.

The iteration04 additions reserve distinct overview evidence, require handoffs to name the next actual subject, and check citations clause by clause, including counted-component membership. The proposed05 Planner addition gives each main batch one literal pictured subject, with another feature assigned its own available batch or deeper; a composite is permitted only when both subjects are visibly present. This strengthens the expression of existing picture grounding without altering a guard, schema, role, category order or duration rule.

The nine `final04-gates` suites passed with zero outbound attempts: script prompts40, Coach27, Planner19, speech style30, roles14, generation55, deck380, acceptance24 and smoke3. Subsequent05 verification covered the one-subject Planner sentence, and the completed06 code replay reused exact05requests/responses without changing prose. The05source fixture added exact trim evidence from the supplied PDF's page31, correcting a fixture omission rather than inventing a fact or expanding the source set. Narrative results remain separate from these code checks.

`prompt-changes.diff` and `prompt-counts.json` are refreshed for the proposed05 text. The reconstructed lexical generator exactly reproduces every saved baseline unit and negative-word classification before changing the after-count: **160 prohibition-bearing /154 other →196 /226**, ratio1.04→0.87. This is a reproducible wording metric, not evidence that the narrative criteria pass. The existing twelve-category FMEA and open cooperative-resource P2 still apply; this narrow static delta review does not add paid-provider, live-pixel, audio or production-load coverage.

## Gate receipt and limits

The machine-readable receipt is [gates.json](gates.json): **25actual suites,1,069/1,069reported checks/groups/phases, all green, zero outbound attempts**. Coverage overlaps across suites;1,069is not a unique-test count.

| Gate | Result |
|---|---:|
| `qa_deck` / `qa_accept` / smoke |380/380 ·24/24 ·3/3 (both build phases plus on-demand rehearsal)|
| Coach / new script prompt / new PDF images |27/27 ·40/40 ·58/58|
| New visual alignment |25/25|
| Plan/playbook / narrative roles / generation / speech style |19/19 ·14/14 ·55/55 ·30/30|
| Narration preparation / recovery / automatic preparation / minimum |35/35 ·18/18 ·16/16 ·25/25|
| Source / upload stream / upload retry |39/39 ·19/19 ·12/12|
| Deck media / media Align / Studio feedback |60/60 ·15/15 ·29/29|
| FAQ review / voice lock / customer / release mock |42/42 ·27/27 ·29/29 ·28/28|

The broad `final-complete-gates` run initially failed two literal-string expectations for the old closing instruction. Those exact assertions were updated to the new instruction and rerun in `final-gates-wording`: Plan/playbook19/19 and speech style30/30. Their behavioral checks were not deleted or weakened. Coach adds a real prompt-cache regression. The directly invoked provider module executes no tests and is deliberately excluded as a standalone suite; its60checks run within `qa_deck`380. Final compilation covers18Python files (ten application files, six contracts and two archived QA helpers), one JavaScript module and nine Mermaid copies.

The release mock exercises the full flow with synthetic real WAV files and reports194.22 measured seconds, with zero provider calls. That establishes measured-audio gate plumbing for the fixture, **not the duration, delivery or quality of the new sample script**. Preserved validators and passing mocked tests cannot prove model semantic entailment, natural delivery, literal picture selection, acoustic interruption, live-provider reliability or AWS capacity.

The historical [iteration05 thirteen-criterion audit](final-criteria-audit.md) remains unchanged and explicitly describes the before-fix artifact. The independent [source-audit06delta](final-source-audit.md) matches48/48text units and citation arrays from raw05 to normalized06, retaining30/30explicit picture refs and18/18deliberate none refs. All22pre-fix substitutions across main/deeper/overview/closing are eliminated; no unit or visual kind changes. Nine shared Coach/Planner/Author request, response and schema JSON files are byte-identical between05 and06, isolating the improvement to post-processing. Neither binding preservation nor manually inspected source descriptions are a successful automatic pixel-model audit. Style weaknesses and unmeasured sample duration are not erased by the code fix. No paid voice was generated. This report does not authorize or assert merge, deployment or publication.

Final06verification reran all25suites with socket connect/connect_ex/sendto/create_connection and getaddrinfo blocked. All1,069reported checks/groups/phases passed; every suite recorded zero outbound attempts. [Exact runner](run_free_gates.py) and fresh log hashes are retained in the gate receipt. Any subsequent Author wording polish needs its own clearly scoped rerun; this receipt covers06.

## Final07 prompt-only delta

The later Author polish adds ordinary-use/choice framing, first offered trim before higher-trim examples, natural decision links and grammatical opening variation. No additional application function changed after06. A fresh [55-comparison source receipt](final-protected-checks.json) verifies the seven protected files, all unchanged Author/Planner/principles functions, Coach functions other than the approved cache-key change, all visual functions/classes other than the fallback change, and the exact authoritative pixel-application block. The final07 prompt, visual, speech, generation, narrative-role and three free gates pass with zero outbound attempts; all18Python files compile. Writing/source/timing acceptance remains separately reported from these code checks.

## Final08 scope correction

The final Author prompt additionally preserves duration/package scope on eligibility restrictions and prevents one physical option’s picture from illustrating the opposite option. The corrected07 narrative audit rejects its overbroad petrol-only warranty sentence and two mixed-option picture bindings despite empty validator issues. This does not relax a validator or turn a deeper qualification into a main-path exception.

All eight relevant final08 suites pass: prompts40, visual alignment25, speech30, generation55, roles14, deck380, acceptance24 and smoke3, each with zero outbound attempts. They replace earlier log receipts rather than increasing the25-suite/1,069 total. Eighteen touched Python files compile and the JavaScript module passes syntax. No application function changed after06; the55 protected source comparisons still apply. The twelve-category FMEA has no new code finding from this prompt-only change; final sample semantic/picture acceptance is recorded separately.

## Final09 writing-only delta

Six additional Author prompt lines put the ordinary action/choice at the beginning and prioritize first availability over a higher-trim example when space is tight. They change neither evidence eligibility nor a code function. The eight relevant suites reran after this change with all counts unchanged and zero outbound attempts;18Python files compile. Their latest log and application hashes replace prior receipts in gates.json. The25-suite/1,069 aggregate still counts each suite once. The separate narrative audit determines whether the generated wording actually follows the guidance.

## Final10 complete-response review

The final Author-only text adds self-review for exhaustive local citation coverage, all subjects in deeper visual bindings, batch opening repetition, first availability and budgets. The source and picture findings in09 are preserved in its rejected-candidate audit; empty native issues did not establish semantic acceptance. No guard/function/schema change accompanies this instruction. Eight final10 suites pass with the same counts and zero outbound attempts,18Python files compile, and receipt hashes are refreshed without double counting the25-suite/1,069 aggregate. The final source/narrative report separately evaluates the generated result.

## Final reviewed sample

Two bounded revisions through the existing Author review path produce the accepted iteration12 sample with no further application or prompt changes. The [criteria audit](final12-criteria-audit.md) records495 prepared words,16 compliant delivery batches and empty validator issues; the [source audit](final12-source-audit.md) accepts all49 reviewed text/citation/picture units. These are reviewed simulation results, not an unassisted first-pass or measured-audio claim. The final10 code receipts remain applicable; no additional suite run or production deployment is claimed. Unsupported reputation, deliberately nonvisual lines, acoustic timing and the cooperative PDF-resource P2 retain the limitations recorded above.
