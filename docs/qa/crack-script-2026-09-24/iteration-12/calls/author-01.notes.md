# Final first-availability revision

Exactly one existing text unit changed: saved `engine-choices-2` / `engine-choices-L2`, now PLAN `engine-choices.lines[1]`. Replaced “SX Premium diesel stays manual-only;” with “Diesel manuals start at E;”, supported by F067. The batch remains 32 words and begins “If”. The complete diesel automatic trim set, turbo handoff, F003/F008/F067/F068 citations, diesel image and every other line field are unchanged.

As explicitly requested, regrouped 16 delivery segments into PLAN's 11 whole stops: engine-choices plus its two continuations = 3 lines / 94 words; airbags-and-help = 2 / 62; climate-and-remote = 2 / 62; seat-and-roof = 2 / 60. Existing deeper lines accompany their original parent stop. Parent IDs/titles/order and planned whole-stop budgets are restored; normal app delivery splitting can recreate batches. Saved line metadata is preserved, without any new timing measurement.

Flattened comparison confirms exactly one changed text field and no other main/deeper line-field differences. Closing is unchanged; complete runtime overview is copied exactly; intake is copied verbatim from PLAN because the saved previous-script object contains only segments and closing. No evidence flags or validation rules were changed.

Local checks: supplied-schema required fields/types/enums/references, planned IDs/order/budgets, citations/visual preservation, and exact delta assertions pass. All 14 main batches have 26–33 words and unique first words. Prepared narration remains 495 words: 425 main + 26 overview counted once + 44 closing. Root will run actual Pydantic/Author validation.
