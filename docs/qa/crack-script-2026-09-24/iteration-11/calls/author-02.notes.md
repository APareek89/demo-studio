# Native Author repair notes

Restored the PLAN's whole-stop grouping: 16 delivery-split draft segments → 11 planned segments. No spoken text was added, deleted or rewritten.

- `engine-choices` absorbs `engine-choices-2` and `engine-choices-3`: 3 main lines, 94/94 words; 3 existing deeper lines retained.
- `airbags-and-help` absorbs `airbags-and-help-2`: 2 main lines, 62/62 words; 3 existing deeper lines retained.
- `climate-and-remote` absorbs `climate-and-remote-2`: 2 main lines, 62/62 words; 3 existing deeper lines retained.
- `seat-and-roof` absorbs `seat-and-roof-2`: 2 main lines, 60/60 words; 3 existing deeper lines retained.

The four planned parent IDs, titles, metadata and budgets are retained; continuation wrapper IDs/titles are removed so normal delivery splitting can run afterward. All other segments are preserved. Flattened main/deeper units keep the same text, step, fact IDs, visual, card, delivery and order. Closing and intake are unchanged.

Two metadata restorations follow the captured explicit revision instruction: the complete prior overview is copied, including `id: runtime-overview`, and `terms.deeper[1].unverified` is restored to true. The native YOUR DRAFT had stripped the overview ID and normalized that flag to false; neither field appears in the supplied LineOut schema. Root should distinguish this schema behavior from Author wording.

Prepared narration remains 495 words: 425 main + 26 overview (once) + 44 closing, excluding intro/outcome and deeper. All 14 main batches remain 26–33 words with unique first words. JSON, grouping, order, budgets and line-preservation assertions passed locally. Root will run actual Pydantic/Author checks; no duration was measured.
