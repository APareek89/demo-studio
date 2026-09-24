# Author revision notes

Exactly two existing text fields changed:

- `seat-and-roof` / `lines[0]` / `seat-and-roof-L1`: 30 → 30 whitespace-delimited words. Retained the complete ventilation claim, SX Premium threshold, F037/F038 and the seat-airflow visual. Replaced the glass-roof assertion with a spatial handoff to the overhead subject.
- `terms` / `deeper[1]` / `terms-D2`: 36 → 35 words. Removed only “certified” from “missing certified results”; the unknown fuel-economy/crash evidence and authoritative sources remain explicit. Empty citations, `unverified: true`, and visual none are unchanged.

All other previous-script fields and lines, including timing metadata, segment IDs/order, titles, citations, visuals, closing and budgets, compare equal. The supplied prior runtime overview is copied exactly. The captured previous-script object contains only `segments` and `closing`; required intake fields are copied exactly from PLAN.intake.

Local checks: JSON parsed and required top-level keys checked; jsonschema is unavailable. Root will run Pydantic validation. Main narration = 425 words, overview = 26, closing = 44; total prepared narration = 495, counting overview once and excluding intro/outcome/deeper. All 14 main batches have 26–33 words and unique first words. No timing measurement was performed.
