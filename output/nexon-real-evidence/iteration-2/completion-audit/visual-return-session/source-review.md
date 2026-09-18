# Muted proof/deeper return — actual session audit

Session **`s_mu75bjmvm5pw`** is ended, with empty intake `why`, two typed FAQ-bank answers, 28 transcript entries and zero leads. Its 23.3 minutes include long operator review/idle periods and are not narration duration. Root identifies the loaded frontend as **3412b11**, before the new focus/citation changes. The session completed after the backend restarted on **cde49fe**, which generated its saved summary. No new provider call, UI action, API/share-capability access or production write was made for this audit.

[The sanitized session](session.json) is captured from the local saved record. [Snapshot provenance and hashes](snapshot.json) identify the source files and sanitized output. [Return checks](return-checks.json) preserve exact transcript indices and [current reviewed lines/bank answers](reviewed-lines-and-bank.json) preserve the comparison text and fact IDs.

## Proof line return

The boot's first reviewed line (F014, petrol/diesel 382 litres with ISO V215) is interrupted at transcript index 7; its `full` field exactly matches `boot-practicality-L1`. The safety question at 8 uses a bank answer with F003/F004; the stored jump is `sl05 → sl02`. After the answer and “Did that answer it?”, the return cue at 12 precedes the **exact full interrupted L1** at 13, followed once by L2 at 14. The full L1 and L2 each occur once; already completed narration was not replayed. Root's explicit confirmation/return UI is preserved in `../proof-interrupt-return-line.txt`, which also shows F014 correctly.

## Deeper line return and separate citation failure

The first deeper boot line is interrupted at 16; its `full` field exactly matches `boot-practicality-D1`: CNG 321 litres with ISO V215 and no fit inference. The ventilation question at 17 is answered from the bank with F020/F021 and jumps `sl05 → sl02`. The return cue at 21 is followed by the **exact full D1** at 22, then D2 at 23 and “Is that clearer?” at 24. D1 and D2 each occur fully once. This proves the actual deeper return sequence, not merely synthetic coverage.

The pre-fix UI simultaneously exposes **NX38**: `../deeper-interrupt-return-line.txt` shows the correct resumed D1 caption but stale **F020/F021**, while D1 cites **F014** and D2 cites **F024**. The successful narration return does not make citation display pass. The later code fix and 33-case browser regression must be cited separately; this frozen record remains the actual failure reproduction.

## Summary attribution after backend repair

All three successful Gemini summary requests in this completion window now appear in this demo's trace (**429–431**) and usage (**363–365**). Each request contains both exact customer questions; the final response at 431 matches the saved summary, generated at 1789748693.365653 with 28 transcript entries. [Safe summary trace/usage extracts](summary-accounting.json) retain tokens, timestamps, response fields and matching checks without full prompts or capabilities. This is actual evidence that new background summaries have demo-scoped accounting; it does not backfill the earlier missing calls.

There were **three generations for the same ended transcript**, not one. Repeated Stop/Done/pagehide saves before a summary completes can start parallel threads under the current code. All three are preserved for cost accounting; the latest result is saved. This audit did not trigger them or change that behaviour.

All validation here is muted caption/transcript and file evidence. Transcript interruption fractions are player estimates; no acoustic intelligibility, exact audible prefix or microphone accuracy is claimed. Explicit confirmation clicks come from root's UI observation, since chip clicks are not copied into user transcript text.
