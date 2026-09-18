# NX42 — duplicate background summary work overwrote a success

Observed in the ended live sample: duplicate summary workers ran for the same saved conversation. Runware succeeded at trace460, but later failures at461/462 replaced the stored summary with an error. The customer record did not identify which saved input owned each result. The original failed sample remains unchanged.

## Cause and correction

Every ended Stop/Done/beacon save without a completed summary started another thread. Reuse compared only transcript length. Each worker later wrote its entire old snapshot back, so it could replace a newer success, corrected input, or a resumed active session.

Session saves and result attachment now use a small per-session lock. A canonical SHA256 of the full saved input, excluding server bookkeeping (`summary` and `saved_at`), identifies the revision. Identical in-flight work is coalesced; completed unchanged input reuses its result. Equal line counts with different words, profile, CTA or other input do not qualify. Client saves cannot supply a server summary.

The worker releases the lock before all model/provider work. On completion it reloads the newest record and attaches only when the session is still ended, its input revision is unchanged, and it has no current result. It writes that newest record rather than the old snapshot, preserving fresh save metadata. A stale success or failure is discarded, while a superseded failure remains logged. Usage context still belongs to the correct demo and is reset on success and failure.

## Learning.MD — five whys

1. Why did a successful summary turn into an error? A duplicate worker completed later and overwrote it.
2. Why could duplicate work run? Repeated ended saves each started a thread before the first result existed.
3. Why could the later worker replace a newer record? The worker wrote its captured snapshot instead of checking current input ownership.
4. Why was summary reuse insufficient? It compared transcript count rather than content and the other summary inputs.
5. Why did the original tests miss it? They tested isolated worker accounting and failures, without held concurrent workers or same-length corrected/resumed input.

Prevention: provider completion is not authorization to write a saved conversation. Attach only to the unchanged revision, coalesce duplicate work, preserve the latest record, and test thread interleavings explicitly.

## Evidence and hooks

- `evals/summary_race_contract.py`: real Python threads, actual ASGI session route, temporary local data, held fake providers, blocked outbound sockets. **6/14 before →14/14 after.** Logs: `summary-race-before.log` and `summary-race-after.log`.
- Cases cover duplicate success/failure ordering, latest metadata, completed reuse, independently progressing sessions, resumed same-length changed input, newer success surviving old failure, and changed non-transcript input.
- The existing summary usage fixture creates a genuinely new revision before its direct-call and failure checks; it no longer expects a valid current summary to be overwritten. Its **8/8** context/accounting checks remain required.
- The new14 cases are wired into `evals/qa_deck.py`. Python compilation and scoped diff checks pass. Root owns broad gates and final real-session recovery evidence.
- Loop/diagram/Handoff: session save → unchanged-input summary reuse or background request → per-session revision coalescing → provider outside locks → attach to current unchanged ended record only.

Scope: this is **per-process** coordination for the current one-worker local server. Lock/in-flight entries live in memory for the process lifetime. It adds no service, persisted schema or distributed lock. A completed error is retained for identical input, consistent with prior save behavior; the fix adds no automatic paid retry. Old missing accounting and the already failed saved summary are not retroactively repaired. No provider calls, real data writes, restart or Build were performed by this regression task.
