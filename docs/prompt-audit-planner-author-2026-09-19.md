# DELIVERABLE THREE — SYSTEM PROMPT AUDIT
## Decision document for the product owner · 19 Sep 2026

**Read and verified:** `server/agents/plan.py`, `server/agents/author.py`, `server/agents/principles.py`, `server/agents/pitch.py`, `server/schemas.py`, `PRD.md`, `AGENTS.md`. Behavioural evidence is two real runs — the N Line run at `data/demos/dm_c6a354fd/` (5 Sep) and the most recent CRETA run at `data/demos/dm_41513908/` (19 Sep, 18:46). Prompt engineering only; every change below is text inside a prompt string.

---

## 1. THE DECISIONS, AND WHAT WAS REJECTED

Your split is right about *who decides* and wrong about *where the feeling comes from*. The emotional payload is chosen when the planner picks which three USPs and in what order — not when the author writes the sentence. Six calls, each with the alternative I turned down.

| # | Decision | Rejected alternative | Why |
|---|---|---|---|
| 1 | **Stop injecting `PITCH_SHAPE` into the author** (`author.py:339`). The author gets the itinerary, not the manual for writing itineraries. | Trim `PITCH_SHAPE` to a summary for the author | 37% of the author's assembled 2,587-word prompt is duplicated planning. A summary keeps the duplication and the shape-template behaviour it causes. Remove it. |
| 2 | **Reinterpret "stand alone" as a ban on *reference*, not on *connection*.** Add real joins on the five joints that never move. | Add a droppable `lead_in` / `hand_off` field the runtime strips | Schema change, and `pitch.py:379` already discards every bridge when there is no customer context — it would ship dead in Phase 1. |
| 3 | **Add a translation ladder**: a named third way to speak a spec that is neither the bare number nor invented praise. | Loosen `CLAIMISH` so mild praise passes | Rung R1 — describing what the picture literally shows — is already legal under `author.py:121-125` and completely unused. Free warmth, zero grounding cost. |
| 4 | **The planner selects by felt consequence, then verifies the evidence.** Not the reverse. | Keep `plan.py:33` "Rank by relevance and strength of evidence" and ask the author for warmth | That rule is what produced the USP name `"Turbo-petrol punch, 0-100 in 8.9 seconds"` — a number inside a promise — and it is the same rule that would happily select "15,786 units in June 2025". |
| 5 | **The plan gets more structured, not more narrative.** Precise about felt things, not prose. | Take "the script is a story / outline" literally | A prose outline shrinks the author's input to three strings and reads as a summary the author then paraphrases. |
| 6 | **Continuous mode ships through the existing `instruction` string.** | Wait for a schema mode flag | Both `plan.run()` and `author.run()` paste `instruction` verbatim as a follow-precisely block. Works today, costs nothing, tells you whether the mode deserves a flag. |

**Also decided:** the author keeps the right to **drop the least decisive fact to buy a join**. It is the only stage that sees the fact registry with source quotes (`fact_context`), so it must be able to refuse a claim — and at 38 words for three beats, the join is otherwise always the first casualty.

---

## 2. WHAT I VERIFIED FIRST

Five checks, because they decide which complaint is a prompt problem and which is a schema problem.

1. **Your split is currently inverted in code.** `plan.py:12` imports `PROOF_BLOCK`, but `PLAN_SYSTEM` has no `{proof_block}` placeholder and `plan.py:223` never passes it. The content pattern — *say the decision → show the evidence → explain relevance* — reaches **only the author**, where it becomes a sentence template. The planner, whose job that pattern is, never sees it.
2. **The author is handed the planner's manual twice.** `author.py:339` injects `PITCH_SHAPE` (508 words, the whole seven-step flow) alongside rule 4 (`author.py:30-55`, 447 words restating the same flow).
3. **Only about 30% of the joints are actually uncertain.** `pitch.py:387-392` builds the live route as `proof[:3] + features[:1] + establish[:1]`, and `pitch.py:46` says *"Never put intro/outcome segments in the route (they already played)."* The played order is always overview → intro → outcome → [3 proof, reordered] → features → establish → closing. **Five joints are fixed every run.** The prompts impose the stand-alone rule on 100% of the script to protect the proof↔proof joints.
4. **In Phase 1 the runtime cannot add a single connective word.** `pitch.py:379`: with no customer context every bridge is discarded, including the code-owned neutral cue. Whatever seam exists must be authored into the segments — and `author.py:12-13` forbids exactly that.
5. **Descriptive sensory language is already legal.** `ungrounded()` (`author.py:121-125`) marks a line bad only when it has no fact id *and* trips `NUMBERISH` or `CLAIMISH`. A sentence describing what a picture literally shows — no number, no claim word — passes today. **No prompt anywhere tells the author this.**

**The behavioural evidence, both runs.**

| | 5 Sep run (`dm_c6a354fd`) | 19 Sep run (`dm_41513908`) |
|---|---|---|
| Openings | 5 of 10 segments open with a verbatim or trimmed `SIGNPOSTS` string; 9 of 10 use the same "Label —" construction | No signposts at all — every proof segment opens on a bare specification: *"Selected variants offer ventilated front seats."* / *"The rear seats offer a split-folding arrangement"* / *"The published starting price is ₹10,90,700 ex-showroom."* |
| Check-ins | 8 of 8 non-intro segments; two invent customer context (*"How long is your usual daily drive?"*, *"Who usually travels with you — kids, parents, or mostly just you?"*) — your complaint #3, in production | 3 of 8, correctly worded. The quota guidance works; **placement is still the author's invention** |
| Figures | *"nought to hundred in eight point nine seconds"* spoken twice, in two different segments | ₹10,90,700 spoken in the establish segment as its opening line |
| Selling | 27 lines; **exactly one** sells an experience: *"On a hot afternoon in traffic, your back stays dry and the cabin stays comfortable."* Nothing in either prompt asked for it | 19 lines; **zero**. Nine carry a variant hedge (*"on selected variants"*, *"depends on the variant you choose"*). Five end in "come and check it yourself" |
| Length | 389 words linear ≈ 3 min 25 s, over the PRD rule — `ROUTE_LIMIT = 360` only governs the Explore route, not the linear run | 303 words |

The newer run is the more damning one: no signposts, and it is *still* a catalogue. Removing the signposts alone does not fix this.

---

## 3. THE DIAGNOSIS — five root causes, ranked by damage

### RC1 · The prompt forbids joins, then hands the model six frame-resets to open with
**Damage: the "disconnected segments" complaint, whole.**

`author.py:12-13`:
> *"You write the spoken script for a product demo delivered by a voice guide. The customer can interrupt at any moment, so every line and every segment must stand alone (no "as I said")."*

mirrored at `principles.py:171` (*"The runtime reorders these per buyer; each must stand alone"*) and `plan.py:46-47` (*"The runtime plays the buyer's strongest signal first, so each must stand alone"*).

Two errors in one clause. First, **"stand alone" conflates a reference with a connection.** What breaks when a segment plays out of order is a *reference* — "as I said", "that engine we just looked at". What does not break is a *connection* — the next thing being about a subject the buyer has just arrived at, in the same voice. The prompt bans both with one phrase. Second, it is stated at **line** granularity, and lines inside a segment are never separated (`split_long_batches` splits only at line boundaries and preserves order). So the model restates the subject in every sentence and refuses anaphora *inside* a batch, where there is no risk at all — hence *"Selected variants offer ventilated front seats… Alongside them, selected variants offer automatic temperature control"* in consecutive sentences of one breath.

Then `author.py:52` — *"Signposts, varied, in the persona's voice: {signposts}"* — supplies six canned openers (`principles.py:180-181`), every one a frame reset. *"One thing you'll notice first —"* at segment four tells the buyer the previous three did not count. "Varied" instructs the model to rotate them, producing an audible bumper → content → bumper → content rhythm. The 5 Sep script is the receipt. The 19 Sep script shows the failure mode when the model declines the signposts: it opens on a specification instead, because **nothing in the prompt says how to open a segment.**

### RC2 · There is no legal way to say what a specification feels like
**Damage: "leans technical, recites specifications" — your complaints #1 and #2.**

`author.py:66-68`:
> *"Do not make "four-cylinder", "quad-beam", "dual-clutch" or dimensions the everyday opening or a headline benefit. Do not replace those with unsupported praise such as "responsive turbo", "assured stopping performance", "diesel pulling power" or "extra pep". Equipment describes equipment; a felt result needs its own evidence."*

and the only handling rule for a number, `principles.py:188`:
> *"Move a technical quantity as a whole to `deeper` detail; never keep its number while dropping the unit."*

Rung A (the bare number) is banned. Rung B (invented praise) is banned. **No rung C is ever named, and the only sanctioned move on a number is deletion.** What survives deletion is the un-numbered spec noun — "a 1.5-litre turbo petrol engine", "a split-folding arrangement" — which is precisely the recitation you are objecting to. `schemas.py:242` even defines a line step called `"translate"`; the word appears in no prompt in the repo.

Both bans are correct and must survive. **Your own example would be rejected by this pipeline, and should be:** "powerful pick-up" is an invented felt result and "100 km/h in 5 seconds" is a figure not in the registry. Your *instinct* — translate, don't recite — is right; that specific sentence breaks "no citation, no claim". The fix is to open a third rung that is already fully evidenced.

Supporting count: across the assembled author prompt there are ~31 quoted exemplars. **Exactly one** is a model of a good narrative sentence (`author.py:64-65`), against ~17 banned phrases plus a 39-token `JARGON` blocklist. Given one good example and seventeen bad ones under a hard schema, the model optimises for the thing it can verify — not tripping a ban. The safest sentence that satisfies every ban is a neutral restatement of the fact.

### RC3 · The fit-check escape hatch has become the default ending
**Damage: this is why the newest script sells nothing, and it is not fixed by removing signposts.**

The phrase reaches the author five times in one assembled prompt:

- `principles.py:65` — *"Explain relevance as a choice or a fit-check when the source provides a feature/specification rather than a demonstrated outcome."*
- `principles.py:134` (`PROOF_BLOCK`) — *"EXPLAIN its supported relevance, or a useful fit-check when no outcome is demonstrated."*
- `principles.py:169` (`PITCH_SHAPE`) — *"NOTICE one thing → SHOW it (the picture) → supported RELEVANCE or a fit-check."*
- `principles.py:192` (`AUDIENCE["everyday"]`) — *"Lead with the useful choice or fit-check, without inventing an outcome."*
- `author.py:41` — *"or a useful fit-check."*

A fit-check is free, unfalsifiable and cites nothing. It is the cheapest legal way to satisfy the RELEVANCE beat, so the model takes it every time. In the 19 Sep run: *"It's a feature to try when you sit in the car"*, *"Check the rear seats and boot with the people or luggage you expect to carry"*, *"Try it with music you know on a test drive, and decide whether it matters to you"*, *"We can check the exact screen setup… for the variant you're considering"*. **Four of eight segments end by telling the buyer to go and find out for himself.** The rule is correct as a *fallback*; it is stated as an *equal option* and so became the default. It must be demoted to last resort, below the translation ladder.

### RC4 · The author spends its attention on structure compliance, not prose
**Damage: flat, template-shaped, interchangeable segments.**

`author.py:339` gives the author the entire planning manual on top of the finished plan. Every decision in `PITCH_SHAPE` — segment counts, roles, ordering, check-in quotas, budgets — was already made and is delivered inside `plan_view` at `author.py:320`. Four separate statements of the NOTICE→SHOW→RELEVANCE pattern reach the author (`PRINCIPLES` G3, `PITCH_SHAPE` STEP 4, `PROOF_BLOCK`, rule 4). Applied identically to 4-6 consecutive segments, one sentence-order template makes every segment the same shape — a form being filled in.

Meanwhile the one rule whose subject is writing quality, rule 6 (`author.py:58-75`), is 226 words of which roughly 180 are prohibition. And `SCORECARD` (`principles.py:121-132`) — ten real quality criteria including "Outcome first" and "Concrete language" — is imported **only** by `rehearsal.py:10`. The author never sees a quality criterion, before or after writing.

### RC5 · Nobody owns the meaning of the running order
**Damage: a coverage matrix instead of a pitch.**

`SegmentPlan.goal` is defined at `schemas.py:169` as *"what the customer should believe or understand after this segment"*. Here is what that produced in the 19 Sep run, all nine goals in order: *Introduce… Present… Demonstrate… Showcase… Demonstrate… Present… Clearly outline… Highlight… State…* Nine independent coverage propositions, no tension, no ordering rationale, and **not one field saying how any segment connects to any other.** An author handed a coverage matrix writes coverage.

There is no channel to fix it either: `Plan.notes` exists (`schemas.py:229`) and the 19 Sep plan filled it — but `author.py:320` builds `plan_view` from a fixed key list that omits `notes`, so it is discarded. And two genuinely pitch-level decisions sit with the author by default: **check-in placement** (no plan field exists) and **which facts are spoken versus held in `deeper`** (one flat `fact_ids` list — `cabin-comfort-proof` carries seven ids and the author decides alone which get voiced).

---

## 4. THE VERDICT ON YOUR SPLIT

> *"Planner should make the script plus tagging of images, but the script is more of a story, an outline, the content to be covered. Author should focus only on building seamless statements for the entire script. So the planner is focused on the winning pitch and the author is focused on winning the heart of the customer and keeping them engaged."*

**Right, and further than you think.** The planner should also own check-in placement, the narration-versus-`deeper` split of every fact, per-segment word budget, USP order, and the everyday rendering of each technical fact. All five are pitch decisions currently leaking into the author.

**Right for a reason you did not name.** `PROOF_BLOCK` is injected into the author and not the planner. Your split is already inverted in code, and correcting it costs one line.

**Wrong on "the script is a story / outline".** If the plan becomes prose-y outline text, the author's input shrinks to `goal`, `outcome` and `topic` strings. You cannot write a seamless sentence from *"Showcase rear passenger comfort with the 2-step reclining seat"*. It does not say what was just said, what may not be repeated, which picture is on screen, what the next segment picks up, or how many words are available. **The plan must get more precise, not more narrative** — but precise about *felt* things (the moment, the handoff, what is held back), not only about coverage.

**Wrong on "planner wins the pitch, author wins the heart" — and this is the bug you already have.** If the planner optimises for strength of evidence (`plan.py:33` explicitly tells it to) and the author is banned from adjectives (the evidence rules correctly do), then the author's only remaining lever for "heart" is language it is not allowed to use. **That is exactly how the pipeline arrives at flat recitation.** The pitch *is* the heart. The planner must select by felt consequence and then verify the evidence; the author's job is that it sounds like a person talking, not that it feels like something.

**Insufficient on "the author only builds seamless statements".** It must keep two authorities. First, it is the only stage that sees the fact registry *with source quotes*. Demote it to stylist and grounding breaks — a stylist rephrasing a planner's claim is precisely how "responsive turbo" gets born. Second, seamlessness costs words; the author must be allowed to **drop the least decisive fact to buy a join**. The clean line is not *story vs. sentences*; it is **argument vs. utterance**: the planner owns what is claimed, in what order, on what evidence, against which picture. The author owns how it is spoken, how it joins, and may spend a fact to buy flow — never add one.

**On image tagging, one refinement.** `visual_refs` is per segment; the author sets the per-line `visual` and its `focus`; then `visuals.align()` re-scores every line lexically and proposes a different picture. Three owners, no authority. Workable division: **planner picks the set per segment and puts the hero first; author binds line→picture from that set only.** And the planner must now tag for what is *describable*, not only for topic match — that is where the vivid language comes from (§6D).

---

## 5. THE RESPONSIBILITY TABLE

| Decision | Current owner | Proposed owner | Ships how |
|---|---|---|---|
| What the pitch argues (`primary_outcome`, `takeaway`) | Plan | Plan | unchanged |
| Which three USPs | Plan, ranked by evidence strength | **Plan, ranked by felt consequence, then evidence-checked** | prompt text §6C |
| Wording of a USP name | Plan (numbers allowed) | **Plan, no numbers permitted** | prompt text §6C |
| Which USP leads | Author, silently | **Plan** | `goal` today, `usp_order` later |
| **Which facts are spoken vs held in `deeper`** | **Unowned → author decides alone** | **Plan** | `goal` today, `narration_fact_ids` later |
| Everyday rendering of a technical fact | Unowned; deletion is the only rule | **Plan decides, author speaks it** | ladder §6D today, `say_as` later |
| Running order / segment set | Both (author gets the flow twice) | **Plan only** | delete `PITCH_SHAPE` from author |
| Proof-block content pattern | **Author only (inverted)** | **Plan only** | move `PROOF_BLOCK` injection |
| Word budget per segment | Author (`LIMITS`) | Author for line rhythm, **Plan for allocation** | prompt text §6C |
| **Check-in placement** | **Author** | **Plan** | prompt text §6C |
| Check-in wording | Author | Author | unchanged |
| **Transitions between segments** | **Nobody; actively forbidden** | **Author** | prompt text §6B |
| The emotional arc / tension | **Nobody** | **Plan** | `goal` today, `arc` later |
| Which picture per segment | Plan, "best first" | Plan, **chosen for what it lets the guide describe** | prompt text §6C |
| Which picture per line | Author + `visuals.align()` | Author, **only from the plan's set** | prompt text §6B |
| Sentence craft, rhythm, seams, `focus` labels | Author | Author | becomes ~all of its prompt |
| Grounding at the point of writing | Both | **Both — keep the duplication** | unchanged |

---

## 6. THE NEW PROMPT TEXT

### 6A · Delete from AUTHOR_SYSTEM

**`author.py:339` — stop injecting the flow specification.** Currently:
```python
sys = AUTHOR_SYSTEM.format(principles=PRINCIPLES + "\n\n" + PITCH_SHAPE, proof_block=PROOF_BLOCK, ...)
```
Pass `PRINCIPLES` alone, and drop `{proof_block}` from `AUTHOR_SYSTEM` (`author.py:17`). `PITCH_SHAPE` stays in `plan.py:223`; `PROOF_BLOCK` moves to `PLAN_SYSTEM` via a new `{proof_block}` placeholder, framed with: *"Each proof segment must be planned as a complete argument before anyone writes a word of it:"*

**Delete the editorial half of rule 6** (`author.py:59-65` — "Show standout features early", the cabin-versus-dimensions example, the engine/gearbox pairing preamble). Those are planner decisions. The bans stay.

**Delete rule 4's restatement of the flow** (`author.py:36-49`), replaced below. Keep the validator-backed numbers.

### 6B · Replace in AUTHOR_SYSTEM

**Replace `author.py:12-13`:**
```
You write the spoken words for a product demo delivered by a voice guide. Write it as ONE continuous
talk, in the plan's order, the way a good salesperson walks a buyer round a car — each part picking up
the thread of the part before it.

CONTINUITY AND STANDING ALONE ARE DIFFERENT THINGS. What breaks when a segment plays out of order is a
REFERENCE — "as I said", "that engine we just looked at", "the second of the three". What does not
break is a CONNECTION — the next thing being about a subject the buyer has just arrived at, in the same
voice, in a sentence that carries the thought on. Never reference. Always connect.
- INSIDE one segment the lines always play together, in order, and are never separated. Write them as
  consecutive sentences of one person speaking: line two may open with "And", may finish line one's
  thought, may say "it" for a subject line one named. A segment whose lines each re-announce their topic
  is wrong even if every line is true and cited.
- ACROSS segments, only the proof segments can be reordered, and only three of them play. Those must
  open cold — no naming, numbering or pointing back at another segment — but "cold" does not mean
  "abrupt": open on a place, a moment, or the thing itself ("Sitting in the driver's seat," / "On a long
  drive,"), which reads as a continuation wherever it lands.
- THE OTHER JOINTS ARE FIXED and you should write them as real joins. intro → outcome → (proof run) →
  features → establish → closing always play in that order. Write those joins as though one person is
  still talking, because they are.
```

**Replace rule 4's head (`author.py:30-55`):**
```
4. THE PLAN IS SETTLED. Write one segment for each segment in PLAN.segments, in the order given, keeping
   its id, role and title exactly. Do not add, drop, merge, split, reorder or rename a segment, and do
   not decide what the demo covers — that decision is made. Speak only the facts the plan assigned to
   that segment; anything else it cites belongs in `deeper`. Put a check-in only where the plan asks for
   one. One segment = one batch the guide speaks without stopping, then pauses. The budget exists to
   create that pause, not to compress thoughts — a segment at 30 words that flows beats one at 38 that is
   crammed. Your judgement is about WORDS: what to say first inside the segment, how long a sentence
   runs, which everyday noun carries the idea, how one segment hands over to the next.
   PLAN.customer_persona is the planner's note about who the product suits. It is not a person in the
   room. This script is written before any customer arrives and must be excellent with none: never assign
   the listener a commute, budget, city, household or job, and never hedge around them either — no
   "depending on your routine", no "if that matters to you". "You" is fine for what the product does for
   anyone: "you'd notice it the first hot afternoon", never "on your Bengaluru commute".
```

**Replace the signpost line (`author.py:52`):**
```
   OPENINGS. Never open a segment with a stock signpost, a topic label, a transition phrase, or a bare
   specification. Open on the thing itself, on where the buyer would be standing, or on the moment it
   matters: "Sitting inside, the first thing is the light." No two segments in one script may open with
   the same construction, and no two may open with the same word.
   The list below is SHAPES to vary across the script, never phrases to speak verbatim: {signposts}
   Bad, because it is a label: "Next: cabin and comfort." Bad, because it assumes an order: "As we saw
   outside —". Bad, because it is a catalogue entry: "Selected variants offer ventilated front seats."
   Where segments run in the planned order, end each one on a clause that lands the thought and turns
   towards the next, never on a specification.
```

**Replace the anti-padding clause (`author.py:31-32`):**
```
   Aim for one natural ten-to-twenty-second thought, usually 19-38 words across the batch. Padding means
   filler adjectives, restating the obvious, and repeating what was just said — cut those first. A
   joining clause is NOT padding; it is what makes this one piece of speech instead of a stack of
   captions. When the budget is tight, drop the least decisive fact and keep the remaining sentences
   whole and joined.
```

**Replace rule 5's second half (`author.py:56-57`):**
```
   Concrete nouns; no "smart/convenient/economical/premium/seamless". Relevance is not a garnish on a
   fact — it is the sentence, and the fact is the evidence inside it. Write what the thing does for the
   buyer, then the feature or figure that proves it, not the other way round. A line that is only a
   specification belongs in `deeper`. No segment may contain two consecutive sentences that are both
   specifications, and no fact may carry the narrative twice: a number that led one segment is not
   repeated in another.
```

**Add, immediately after the translation ladder — the RC3 fix:**
```
   A FIT-CHECK IS A LAST RESORT, NOT A RELEVANCE BEAT. "Try it on a test drive", "check it when you sit
   in the car", "decide whether it matters to you" — these say nothing and cost the buyer the segment.
   Use a fit-check only where the evidence genuinely cannot support any rung of the ladder, and at most
   ONCE in the whole script. Never end consecutive segments on one. Where you would have written a
   fit-check, write R1 instead: describe what the picture shows.
```

**Replace the rewrite instruction (`author.py:354`) — this is where every gain above gets undone:**
```
VALIDATOR ISSUES — each names a specific segment or line. Fix ONLY those. Return the full script with
every unflagged line reproduced exactly as you wrote it: those lines are already right, and re-deciding
them loses more than it gains. For each flagged line, try these in order and stop at the first that
works: (1) add the correct fact id if the registry genuinely supports the claim; (2) drop one rung on
the translation ladder and move the complete quantity to `deeper`; (3) state the gap honestly in the
guide's voice. Delete the thought only as a last resort. Where a segment is over budget, CUT A WHOLE
IDEA, DO NOT COMPRESS A SENTENCE. Issues whose text contains the word "warning" are advisory — fix one
only if the fix makes the line read better; a surviving warning shown to the human reviewer beats a
sentence flattened to satisfy a lexical rule. When every issue is fixed, read the whole script through
once as if speaking it aloud and repair what the fixes left behind: a sentence that no longer follows
the one before it, a subject introduced twice, a join that lost its verb.
```

### 6C · Add to PLAN_SYSTEM

**The stats ban — your complaint #1.** Add to the `usps` bullet (`plan.py:32-36`) and mirror in `PITCH_SHAPE` STEP 2:
```
Never build a USP or a narration line on a company or market statistic: units sold, monthly or annual
sales figures, customer totals, market share, sales rank, years on sale, or award counts. These are the
brand's numbers, not the buyer's experience; they date within weeks and no one buys because of a units
figure. A derived reputational line is allowed ONCE, in the intro, with no figure and no rank — "one of
the cars you see most on Indian roads" — still citing the fact id it rests on.
```

**Selection by felt consequence.** Replace the ranking clause in the same bullet:
```
Choose each USP by asking what a buyer would tell a friend that evening, then check the registry supports
it. A feature that survives that test and has evidence beats a better-evidenced feature nobody would
mention. usps[].name is a promise in the buyer's language, 3-8 words, containing NO number, unit or model
code, and it is not a list of equipment — "A sporty cabin that stays comfortable daily" is a promise;
"Available panoramic sunroof and ventilated seats" is a parts list. The numbers live in fact_ids and are
spoken at most once, in the one segment that owns them.
You choose what the demo is emotionally about, not only what it proves: decide the one moment in owning
this product that the whole tour walks toward, and make the first proof stop the one closest to it. The
author can make any stop sound warm; it cannot rescue a tour that opens on dimensions.
```

**Check-in placement and budgets.** Add to the segments bullet:
```
Exactly TWO segments carry a check-in, placed where a real decision turns; name them in the goal. A
question after every section is an interrogation, not a conversation. Give every segment a word budget
and spend the words where the decision is — a lead proof segment can take 45 where a supporting one takes
25. An even split across six segments is a catalogue.
Titles are sometimes SPOKEN at runtime as "Next: <title>." Write each title as the thing itself in a
buyer's nouns — "The seat you'll sit in every day" — never a category label such as "Interior features".
```

**The proof bullet (`plan.py:45-47`) — order as a walk, not a checklist:**
```
4-6 × role=proof — GUIDED DISCOVERY, ordered as a walk rather than a catalogue: something striking →
   what it is like to live with → what it costs to own → what is still unsettled. One area per segment.
   The live runtime plays three of these in the buyer's own order, so order them as stops where each is a
   natural place to be standing after the one before, and none DEPENDS on a particular predecessor.
   Do not open two consecutive segments the same way: vary whether a segment opens on something noticed,
   on a doubt the previous one raised, on an ordinary situation, or on a short honest limitation.
```

**Visual tagging (`plan.py:54`):**
```
- Every segment needs a visual that literally shows its subject (shots quality ≥3 preferred, else
  images); missing → visual_gaps. Choose each visual for what it lets the guide DESCRIBE, not only for
  topic match: prefer the frame with the most concrete, nameable detail a person could point at over a
  cleaner frame that shows less. Order visual_refs best first, and make the first the frame the segment's
  opening sentence will describe. These are the ONLY pictures that segment may use.
```

### 6D · Add to principles.py — the translation ladder

The fix for RC2, and it resolves your complaint #2 **without weakening grounding by a single word.** Inject into `AUTHOR_SYSTEM` only.

```
TRANSLATION LADDER — how a specification becomes a sentence a person would say. Stop at the first rung
the evidence supports; never climb past it.
R1 SHOWN — no fact id needed. What the picture literally shows is yours to describe in ordinary sensory
   words: shape, material, where a thing sits, what opens, what lights up, how big it looks next to a
   person. "The glass roof runs right back over the second row" describes the picture. It claims nothing
   about heat, comfort, safety or resale, and it carries no number. THIS RUNG IS WHERE VIVID LANGUAGE
   COMES FROM. Reach for it first.
R2 NAMED — cite the fact id. The specification in plain words without its number, keeping the source's
   own noun and adding no adjective the source does not use: "the turbo petrol engine", "ventilated front
   seats". Naming is not promising.
R3 CHOICE — cite the fact id. What the specification lets the buyer decide, stated as a decision and not
   a result: "the gearbox follows the engine you pick, rather than being a separate decision."
R4 MOMENT — cite the fact id. The ordinary situation the specification is for, left open and never
   assigned to this buyer: "it's the one you'd want if most of your driving is highway."
R5 QUANTIFIED — cite the fact id. The number with its unit and its basis. For an everyday buyer this rung
   lives in `deeper` and in Q&A, not in the main narration. Where a figure genuinely IS the point — a
   price, a warranty period, a stated acceleration time — say it once, whole, with its unit and stated
   conditions, and never repeat it later in the script.
There is no rung above R5. "Responsive", "effortless", "confidence-inspiring", "enough power for a quick
overtake", "planted", "premium feel" are results, and a result needs a cited fact that reports it. If the
sentence you want needs a rung above R5, write R1 instead — show it rather than promise it. A picture
proves appearance. It never proves performance, safety or durability.
```

**And replace the deletion policy (`principles.py:188`):**
```
When a technical quantity does not belong in the main tour, do not simply delete it — replace it at R1 or
R2 and move the complete quantity, with its unit and basis, to `deeper`. Deleting a number and putting
nothing in its place is what makes a demo sound like a brochure with gaps. Worked through: "a 1.5-litre
turbo petrol engine, and it comes with the automatic" is R2 and is the everyday form; "253 newton metres
of torque" is R5 and goes to `deeper`; "quick off the line" is above R5 and goes nowhere at all.
```

**Your example, honestly handled.** *"1.5 turbo which gives you powerful pick up and 100 km/h in 5 seconds"* fails twice: "powerful pick up" is above R5, and the 5-second figure is not in the registry. For the actual N Line registry, which does carry a catalogue-quoted 8.9 s to 100 km/h, the legal everyday form is R4 — *"the turbo petrol — the one you'd want if you spend time overtaking on the highway"* — with the 8.9 s figure spoken **once** if at all, and held in `deeper` otherwise. That is your instruction delivered without breaking the product rule.

---

## 7. THE PLAN FIELDS — what ships today, what waits

**Tier 1, this week, prompt only.** `Plan.notes` is discarded at `author.py:320` (the 19 Sep plan filled it and the author never saw it), and `SegmentPlan` has no narrative field — so **`goal` is the only channel the planner has to the author.** Use it. Add to `PLAN_SYSTEM`:

```
Write each segment's `goal` as THREE short sentences, because `goal` is the only place the author hears
your thinking.
  1. THE MOMENT — one ordinary scene, ≤15 words, in which this feature is actually felt, in the buyer's
     own nouns, stated conditionally and containing NO number. This is what stops the segment being a
     specification. A segment with no plausible moment is not a demo segment: cut it or move it to
     features and `deeper`.
  2. WHAT IS SPOKEN — which of this segment's facts the guide says out loud, and which are held for
     `deeper`. Speak at most one figure per segment, and only when the moment collapses without it.
  3. WHAT IT HANDS ON — the subject the buyer's attention is resting on as this segment ends. Name a
     SUBJECT, never a position: "leaves them sitting in the cabin looking at the screen", not "sets up
     segment three". For proof segments the runtime plays only three, in its own order, so this is the
     author's source of continuity, never a prerequisite for understanding.
```

**Worked example, replacing the real 5 Sep goal `"Believe the cabin makes a hot, slow commute easier, not just sportier."`:**
```
MOMENT: four in the afternoon, stop-go traffic, shirt already stuck to your back.
SPOKEN: ventilated front seats and dual-zone climate, named plainly. No figures — the climate zone count
stays in deeper.
HANDS ON: leaves them sitting in that seat, thinking about who else is in the car.
```

**Worked example, replacing the real 19 Sep goal `"Showcase rear passenger comfort with the 2-step reclining seat and expandable luggage space using the 60:40 split."`:**
```
MOMENT: three people in the back on a long run, and a boot that has to take the bags as well.
SPOKEN: the reclining rear seat and the split fold, named. The 60:40 ratio and the variant list stay in
deeper. No fit-check — describe the seat, do not ask him to go and sit in it.
HANDS ON: leaves them in the back seat, thinking about the drive itself.
```
Note what the moment does: **"a 2-step recline and a 60:40 split" becomes a scene without inventing an outcome**, and the next segment's cold opening ("On a long run, what you notice is…") reads as a continuation wherever it lands.

**Tier 2, next session — needs schema fields on `SegmentPlan` / `Plan`.** In priority order, and only these:

| # | Field | Why it earns its place |
|---|---|---|
| 1 | `narration_fact_ids` / `deeper_fact_ids`, splitting today's flat `fact_ids` | **The single biggest cause of spec recitation is that this decision is unowned.** `cabin-comfort-proof` carries 7 fact ids and the author alone decides which get voiced |
| 2 | `say_as` per narration fact — the planner-approved R2/R3/R4 rendering | The author never has to invent one. *"Any fact whose value is a unit-bearing engineering quantity goes to `deeper` unless a `say_as` exists for it. If you cannot write an honest `say_as`, the fact does not belong in narration."* |
| 3 | `moment` and `hands_on` as their own fields, out of `goal` | Makes the story channel reviewable at Align rather than buried in a sentence |
| 4 | `carries_checkin` (exactly two per plan) and `word_budget` | Moves both remaining leaks out of the author |
| 5 | `arc.tension` at plan level, drawn from `concerns` and `do_not_recommend_if` | **A demo with no tension is praise, and praise is what gets recited.** For the N Line: *"A car that looks this sporty usually asks you to give something up — a stiffer ride, less room for the family. Buyers assume character costs comfort."* |
| 6 | `excluded_from_narration` — facts deliberately left out, with the reason | Makes the stats problem visible to you at review instead of invisible |

---

## 8. THE UNINTERRUPTED MODE

This mode does not exist today; every prompt hardcodes interruption. **It ships with no code change:** both `plan.run()` and `author.run()` take an `instruction` string pasted verbatim as *"REVISION INSTRUCTION FROM THE USER — follow it precisely"*. `DEMO MODE: continuous` as the first line of that instruction is a working switch until a real flag exists.

```
DEMO MODE: CONTINUOUS. Nobody can interrupt and nobody answers. Every planned segment plays, in the
plan's order, exactly once. There is no intake answer, no deeper layer and no Q&A during the run.
GREETING — intake_q1 contains NO question. One breath, ≤32 words: the brand and product, the one thing
the next few minutes will show, and an explicit release from having to respond. "Hi, I'm Ravi from
Hyundai. This is the CRETA N Line, and over the next few minutes I want to show you why it's the CRETA
people actually look forward to driving. Just sit back — nothing to answer."
CHECK-INS — every `checkin` field is empty. In their place, the two segments the plan marked for a
check-in end on a spoken breath instead: one clause stating what has been settled, and an unnamed hand
forward. "That's the cabin sorted. The bit people ask about first is what happens when you press the
pedal." A statement, never a question.
SEAMS — self-containment is not required here. Every joint is fixed, so write the whole thing as one
continuous piece of speech: each segment picks up the thread the previous one handed on, and the last
clause of each sets up the next.
FIT-CHECKS — banned outright. There is no test drive in this room and nobody to check anything. Where the
evidence supports no rung above R2, describe the picture (R1) and move on.
BATCHES — the ≤20-second batch exists so an interruption lands quickly; with no interruption it governs
only when the picture changes. Budget the whole transcript, not each segment: 6-8 segments, 380-430
words, about three and a half minutes end to end.
DEEPER — nothing load-bearing may live in `deeper`: it becomes the answer bank for the question set that
ships with the transcript, and the main narration must stand as a complete demo without it.
FIT SUMMARY — there are no buyer words, so frame the fit conditionally and let the listener place
themselves, speak do_not_recommend_if out loud in one clause, then the one next step naming the CTA.
All grounding, citation and truth rules are unchanged.
```

**Two budget conflicts to settle before you tune anything against a number.** `PRD.md:16` says "4–5 minute walkthrough" while `PRD.md:60` says "at most ~3 minutes"; and `LIMITS["features"] = 40` words against `PRD.md:60`'s "60–90 s" block, which at the measured 1.9 words/s is 114–171 words. The features block is budgeted at roughly a quarter of its own specification. **Pick one set of numbers and write it into the PRD** — a five-minute decision that removes a lot of downstream argument.

---

## 9. WHAT NOT TO DO

- **Do not relax the grounding rules to make the script warmer.** "Powerful pick-up", "responsive turbo", "100 km/h in 5 seconds" — the bans that block these are the product. Losing "no citation, no claim" to gain adjectives would destroy the only thing that makes this defensible for a brand. Everything in §6D gets the warmth without touching a guard.
- **Do not delete the stand-alone rule.** It is genuinely load-bearing for the three reordered proof segments in interactive mode. Reinterpret it as a ban on *reference*; do not remove it.
- **Do not fix this by deleting `SIGNPOSTS` alone.** The 19 Sep run uses no signpost and is still a catalogue — it opens each segment on a specification instead. The opening rule has to say what to open *on*, not only what not to say.
- **Do not let the planner write prose.** The temptation, once you say "the script is a story", is a narrative paragraph per segment. That gives the author less to work with, not more.
- **Do not make the author a pure stylist.** It is the only stage that sees the source quotes. If it cannot refuse a claim the evidence does not support, the validator becomes the only guard and the validator is lexical.
- **Do not put numbers in the `moment`.** A moment is a scene, not a measurement: *"a single-lane highway, a truck ahead, and a gap you'd rather not gamble on"*, never *"a gap that closes in four seconds"*, which quietly invents a figure.
- **Do not add fields for their own sake.** The six in §7 earn their keep. Fourteen would turn planning into form-filling and reintroduce the recitation problem one level up.
- **One correction to an earlier claim, on the record.** The 5 Sep script stores `issues: []` while containing a question inside a narration line and an opt-in check-in. I re-ran today's validator against that stored file: it now flags both. The artifact predates the checks — **the validator is not broken**. It remains true that the validator is lexical and cannot see flatness, so these prompts are the primary control, not the safety net.

---

## 10. ORDER OF WORK

1. **`author.py:339` — remove `PITCH_SHAPE`; move `PROOF_BLOCK` to `PLAN_SYSTEM`.** Two lines. Largest effect, and it is your own instinct.
2. **`author.py:12-13` — the reference/connection replacement, plus the fixed-joints map.** Unblocks everything else.
3. **The openings rule at `author.py:52`, and `SIGNPOSTS` reframed from six phrases to six shapes.** The one with a visible before/after in the next run.
4. **The translation ladder into `AUTHOR_SYSTEM`; the deletion policy replaced; the fit-check demoted to last resort.** Your complaint #2 closed, and the catalogue problem in the 19 Sep run closed with it.
5. **The stats ban and felt-consequence selection into `PLAN_SYSTEM`.** Your complaint #1 closed.
6. **The three-sentence `goal` (moment / spoken / hands-on).** The Tier-1 story channel, no schema change.
7. **The rewrite instruction at `author.py:354`.** Without this, the compliance pass flattens everything above on any run where the validator fires — and it fires often.
8. Then, next session: the six schema fields, `narration_fact_ids` and `say_as` first.

**One sequencing caution.** Step 3 is partly inert until the word budgets absorb it. `LIMITS["proof"] = 38` gives three beats plus a join about twelve words each; a join costs five to eight. **Roughly +8 words per segment on `LIMITS` and `ROUTE_LIMIT` is a real ceiling on how seamless the output can get** — a constants change, flagged not proposed, to be decided alongside the PRD budget conflict in §8.