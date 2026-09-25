# BMW gallery, human narration and voice expression — 25 September 2026

User scope: diagnose the fresh BMW demo, correct gallery picture selection and LLM narration, add occasional supported voice expression, regenerate a separate BMW from the supplied files, and publish the code to master/GitHub. No AWS deployment.

## Confirmed diagnosis

The original `dm_b3a502ce` (display name BMW Q5, source product X7) used fourteen Author picture references but only two repeated Deck pictures. An unavailable empty pixel audit was treated as authoritative rejection. Fresh isolated browser replay does show the gallery: missing frontend integration or browser caching is not proven. The original's first fact batch also misclassified the vehicle as an electric scooter, despite three SUV batches.

Old writing instructions discouraged ordinary spoken joins and encouraged formal scene-setting. Later actual drafts showed additional causes: inherited outline sentences bundled unrelated pictures/claims, repair preserved bad wording, and Gemini received policy and source/task as one user message instead of actual system instructions. Empty validator issues are not semantic approval.

Sarvam tone labels previously did not change provider expression. Bulbul v3 supports temperature-driven variation, not precise pitch, amplitude, chosen-word emphasis or SSML. The new optional delivery value uses that documented control sparsely; unmarked recordings retain their previous identity/defaults.

## Implementation

- `understand.py` reconciles a strict normalized category majority across extraction batches; ties and single observations preserve the primary result. The schema no longer supplies a scooter category example.
- `author.py`/`principles.py` request direct, varied, customer-addressed speech. Author may separate a mixed pictured thought within assigned facts/budgets while retaining stop order; complete source qualifications outrank promotional plan prose. No runtime phrase rotation or handwritten product script is installed.
- `deck.py` retains allowed selected pictures only for the exact unavailable empty audit, as disclosed illustrations without fabricated anchors. Partial/rejected audits still fail closed. Both derived and model captions must belong to their own picture's spoken interval.
- Existing delivery normalization, voice/cache identity and REST/stream adapters carry optional expression. Text, speaker, language, approval and duration guards remain intact.
- Customer-tier Build now prefers existing Runware GPT5.5, then Gemini and Claude. Eval/default tier, runtime order and explicit overrides remain unchanged.
- Exact Gemini3.8 build calls request supported LOW thinking within unchanged token limits. Structured text calls send authoritative policy through SDK `system_instruction` and source/history through `contents`; shared runtime deadlines/fallback/validation remain tested.

Core workflow, agents/nodes, top navbar, conversation dock and gallery frontend are unchanged. This package fixes the content entering the approved template.

## Free acceptance

Final core: deck445/445, acceptance24/24, smoke3/3, full mock release28/28. The mock journey measures194.22seconds of fixture narration, not real BMW audio. Provider79, runtime config6, prompt53, narrative14, generation58; category16; Deck media106, media Align39, visual25. Narration preparation35, automatic16, minimum25, selected-duration19, PDF58, Coach27, Plan19, pitch grounding47. Expression20, speech style30, voice lock27, Sarvam stream17, runtime delivery27, live transport25, Explore cancellation9, FAQ cache27/scope19. Browser gallery320 and native87 pass. These overlapping counts are not additive unique cases.

All free provider tests use MOCK_LLM=1, isolated DATA/GRAPH, local storage, cloud off and blocked sockets. Browser harnesses allow only their own loopback fixture server, block providers/microphone and remain muted. Existing historical failures, before-fix reproductions and corrected harness failures are retained under this folder. See [FMEA](FMEA.md), [voice receipt](voice/results.json), [browser results](browser-regression/gallery-browser.json) and individual logs.

## Real BMW review

New demo `dm_29df0418`, from the owner's PDF and22JPGs plus the original enabled BMW URL; PDF extraction adds22 embedded pictures. [Input hashes](build-inputs.json). Original2minute selection, Sumit/en-IN, Marine, local storage and cloud-off settings retained. Original150 files remain byte-identical at the latest verification.

Reviewed source corrections were applied through normal Align: material equipment/compatibility/parking/package/warranty conditions retained; expired/ambiguous offers and image pixel metadata rejected; previously held evidence stays held. See [source review](source-review.json) and [review actions](review-actions.json).

The first eval-tier draft failed301/330words. Five saved Gemini drafts failed semantic/budget review, including after actual system-role correction; none was recorded or published. One Gemini Coach response truncated, followed by an existing Runware fallback after Anthropic reported insufficient credits. The corrected LOW Coach later completed in11.2seconds. Failures remain under local `output/bmw-revision-2026-09-25/`.

The final Runware GPT5.5 draft used the same schema/guards and received explicit Align review. Eight main/overview lines were edited for natural phrasing and one deeper warranty line restored complete conditions. Final preparation:335/330 supported main words; independent review covered31 lines with no invalid citations or concrete grounding issue. One nonblocking outcome-budget advisory remains. [Reviewed narration](reviewed-script.md) and [source review receipt](final-script-review.json) distinguish generated text from this editorial recovery.

Normal Deck review selects11 distinct source photos, removes duplicate PDF copies where possible, and keeps pointers only on reviewed seat/display geometry. Invisible specifications and ownership terms use disclosed illustration captions. All six cards were approved normally before one recording Voice→Bundle Build. The selected120second minimum passed with122.64seconds of measured eligible narration. Final pixel review corrected the seat label to its observed third-row target, removed a wrong-screen Augmented View pointer and removed two exact duplicate dimension captions. The latter data-only deletion uses the canonical store and Deck schema because the current editor has no delete control; normal Deck PATCH, Script reapproval and all Bundle guards followed. The slide-only re-bundle publishedv2 with all53 audio files byte-identical. Final content:15 slides,11 distinct photos,32 labels. [Paid build receipt](paid-build-review.json). The Explore overview is9.2seconds against its10–15second advisory target; the measured full-tour minimum passes. No first-pass generation or acoustic-quality claim is made.

Final actual-player replay passes **281/281**, with **71/71** additional published-audio checks:14 main clips across13 speaking slides at1440px and390px, exact photo/caption ownership, gallery motion and preserved shell. [Final screenshots and review](bmw-final-browser/manual-review.json) retain the corresponding bundle hash. Raw eligible audio totals122.624seconds; per-clip rounding reports122.64. [Version1 findings](bmw-version1-review/manual-review.json) remain preserved. No live runtime/provider/microphone calls were made by the browser harness.

## Release boundary

Release parent is master86f1bcf. The package commit is titled `Fix BMW gallery selection and human guided narration`, made in the existing `codex/sales-trainer-flow` checkout. Commit only this package's explicit changed files and QA artifacts; do not add unrelated output. Verify fast-forward ancestry, push HEAD to origin/master, then verify local master, remote master and worktree HEAD agree. No force push or branch checkout. Never touch protected `dm_41513908` or port8896.

The review app is [localhost8910](http://127.0.0.1:8910/#/home), launched explicitly with MODEL_TIER=customer. Its temporary demo data is not transferred by a Git push. AWS remains the previously recorded release; this task neither inspects nor deploys it. Physical microphone rejection and subjective expression quality require actual listening/device acceptance.
