# B2 comparison repeat — final source review

Session `s_mu744a0l0l8o`, ended via Stop → Done. The safe API snapshot and hash are in `session.json` and `snapshot.json`; `responses.json` preserves trace rows 374–391 without request prompts or raw credential-bearing errors. `source-mapping.json` records exact successful answers, citations, conditions and official origins. This is evidence for these repeat questions, not a perfect whole-demo result. No product writes or paid calls were made for the audit.

## Separate the two runtime versions

The **first Q08 attempt**, on `b78c4d9` before the NX31 restart, failed. Trace 374 reports a closed Gemini client, followed by Claude credit failure and Runware timeout; trace 381 records the all-provider failure. Concurrent pitch work appears between those rows and is not a completed Q08 answer. The player heard its standardized unavailable-answer message. The frozen session retains this failed turn.

The **same session after the restart**, reported by the root operator as `d8fc422`, delivered Q08, Q07 and Q02 successfully. The runtime version split is operator-supplied; a session row does not itself encode a commit. Earlier B failures remain in the separate `customer-comparison-initial` folder and have not been overwritten.

## Q08 — selected Venue comparison

Trace 384 and Priya input 385 match the complete heard answer: **50 whitespace words, two sentences**, comparing screen size and speaker systems with the rival verification caveat. It cites F007/F026/C5-007/C5-008.

- Nexon Fearless+PS petrol DCA: F007 documents the 26.03 cm touchscreen from Pure+ upward in the petrol/diesel persona hierarchy (Tata May-2026 brochure pages 38–39). F026 documents JBL-branded nine speakers with subwoofer, restricted to Fearless+PS DCA (pages 17/40). It does not add a tenth speaker or generalize to every trim.
- Regular Venue HX10: the official feature-table headers and table-5 rows 2/6 mark the 31.24 cm navigation system and Bose eight-speaker system as standard for HX10 and HX10 Knight. Both rows lack a fuel/transmission restriction, so they cover the selected regular HX10 turbo petrol DCT. The answer does not confuse the navigation screen with the separate digital cluster.

**Supported positive comparison.** There is no sound-quality, usability, safety or overall-winner claim. `jumps` confirms `sl00 → sl08`, the cockpit slide. The spoken bridge precedes the recorded answer. The official Hyundai table is uploaded as `src_73036b`, preserving origin `https://www.hyundai.com/in/en/find-a-car/venue/features` and exact expanded column headers.

## Q07 — selected Brezza comparison

Trace 388 and Priya input 389 match the complete heard answer: **52 whitespace words, two sentences**, with the verification caveat. F019 supports the selected Nexon Fearless+PS petrol seven-speed DCA; C6-001 supports Brezza ZXi+ 1.5L K15C petrol six-speed automatic. This is a concrete supported gearbox difference, without an invented performance or suitability ranking.

F025 also supports ADAS on this exact Nexon petrol DCA, and C3-031/032/033 plus C6-004 support six airbags, ESP, Hill Hold and ISOFIX on Brezza ZXi+. **Presentation remains asymmetric:** “On safety, Nexon also lists ADAS features, while Brezza lists…” compares different kinds of equipment. A listener could infer that omitted features are absent, even though the answer does not explicitly make that claim or name a safety winner. The Nexon also has standard airbags/ESP/ISOFIX in F003/F004. Therefore count the gearbox difference and pacing improvement as supported; do not claim the safety comparison is fully balanced. The prior B Q06 is the cleaner matched ISOFIX parity comparison.

`jumps` confirms `sl08 → sl01`. The current algorithm selected a slide carrying an answer fact; this audit does not establish that the opening/outcome slide is the best explanatory view for a gearbox comparison.

## Q02 — warranty

Trace 390 and Priya input 391 match the complete heard **57-word, two-sentence** answer. F027’s Tata brochure page-40 badge states `3 years | 100 000 km`; its reviewed conditions leave the duration/distance relationship and detailed exclusions unstated. The answer now explicitly preserves the unknown relationship. It does **not** repeat the earlier unsupported Tata “or/whichever first” inference.

C3-029 quotes Brezza brochure page 10: `*3 years or 1 00 000 km whichever is earlier.` The answer preserves that explicit relationship for Brezza and the rival verification caveat. The two different source treatments are correct; no Tata term has been copied from Brezza. It does not promise claim acceptance or treat an extended-warranty option as standard coverage.

The Brezza sentence is **unsolicited by “Yes, but what is the warranty?”**, though relevant to the preceding comparison shortlist. It adds length and scope to a direct Tata question. This is a consultation/focus weakness, not an unsupported-fact finding. Literal pipe/space-grouped source notation is also less natural speech than a concise verbal headline plus its missing qualification; acoustic pronunciation was not independently scored here.

`jumps` confirms `sl01 → sl09`, ownership. The root’s `screenshots/B-Q02-completed-ui.txt` records the completed UI answer and citation display. This repeat demonstrates compliance for this answer, not general semantic enforcement.

## Latency, recap and limits

All four turns are typed and live (no FAQ-bank hit). Typed submit to first-answer stamps are 15.9s for the failed initial Q08, **17.8s for successful Q08, 46.7s for Q07, and 14.0s for Q02**. For Q07, trace 386 records a 30.946s Gemini deadline failure before Claude credit failure and the successful 8.502s Runware response, followed by voice and jump bridge. Successful sourcing has not eliminated slow response time.

The player asks “Did that answer it?” after each successful answer. The operator moved to a new question instead of pressing the explicit Yes confirmation. Questions remaining open in the Stop recap are therefore not automatically a resolution bug; `screenshots/B2-stopped-recap.txt` is retained for that distinction.

The full session spans a server restart and an intentional diagnostic pause, so its total minutes are not a clean uninterrupted-tour measure. The audit validates stored heard text, speech inputs, citation/source applicability and recorded routing; it does not independently score acoustics or speech recognition. Q07’s asymmetric safety framing, Q02’s extra rival scope, response waits and the initial failure remain visible.
