# Code-only AWS runtime/gallery release preflight

25 September 2026. Read-only infrastructure review plus local deployment-tool preparation. No AWS mutation, restart, provider call, data import or deployment has been performed by this reviewer.

Product context: PRD.md requires an interruptible grounded demo, preserved recordings/pictures, exact publication pins and incremental customer history. The approved release adds the reviewed runtime/gallery fixes and question acknowledgements. AWS retains its existing WebSocket transport. LiveKit remains an explicit local trial: its current origin, URL and ICE restrictions, missing AWS SDK/server, and absent public token proxy path deliberately prevent accidental hosted adoption.

## Observed deployment

- AWS API verifies instance `i-0410e37b7ab0297e1`, running t3.micro, EIP `13.202.0.79`. Standard first-use SSH trust pinned ED25519 `SHA256:TlrEM+lw8RjV5DWeMZi2vfltLRP2MSh+NJFXxayGEKI` in the private local known-hosts file; later SSH uses strict checking. GetConsoleOutput was denied, so this is documented first-use trust, not an independently authenticated SSH key.
- Active app: `/opt/demo-studio-releases/20260925-bmw-gallery`, application `278c21db39abc15c4f56125637b3ff2a790e4834`. Reusable Python3.11 venv `/opt/demo-studio-releases/20260923-creta-v8/.venv`; pip check clean. Optional LiveKit is absent. Existing Playwright is installed.
- Memory496MiB available of913MiB; swap127MiB used of2047MiB; disk8.4GB free. Shared data1,124,389,511bytes. No new dependency or SFU installation is planned.
- Fourteen stored demos. BMW published v2,15slides, pin `kb_cd2f6a8cf905301b30a07d42`; disk bundle SHA256 `7baeffb535e121fa793a1b8fc5dbec4537194a20bda517f8ab0ffeed96620a02` matches the approved release.
- Caddy and app active; app8877 loopback only. Caddy SHA256 `60ba8ffeb9558bb6b22db7c822159de3d85027651b8d6c8e1948c4665c4fdb6e`; operator boundary remains installed. Public health/BMW bundle200; anonymous inventory/sessions401. Provider mode customer/mockoff/Sarvam; cloud off; runtime Gemini→Claude→Runware. No LiveKit enable flag or URL.

## Reviewed failure modes

Scores apply to the unsafe action before the stated control; none is an open blocker for the scoped code-only process after its controls and acceptance gates pass.

| Failure | Effect | S | O | D | RPN | Priority | Control |
|---|---|---:|---:|---:|---:|---|---|
| Reuse the old BMW import/cutover script unchanged | Its old-release and absent-BMW assumptions fail; careless edits can overwrite customer history. | 7 | 5 | 3 | 105 | P1 | New code-only staging; no data archive/import; assert active prior release; immutable before/after data manifests. |
| Call the local LiveKit trial an AWS rollout | Hosted customers cannot obtain a valid origin/token or reachable RTC connection. | 5 | 10 | 2 | 100 | P1 | Keep default WebSocket and local-only flag guards; state transport explicitly in receipt and user report. |
| A failed rollback step skips restarting the prior app | Outage lasts beyond failed cutover. | 6 | 3 | 5 | 90 | P2 | Every stop/drop-in removal/reload/start/health recovery is attempted independently; retain errors; never restore old data. |
| Old green staging marker authorizes new source bytes | Untested source enters production. | 6 | 3 | 4 | 72 | P2 | Bind marker to commit, source-manifest digest and gate-results digest; rehash source before and after gates/cutover. |
| Archive path or link escapes release staging | Live environment/data can be overwritten. | 8 | 2 | 3 | 48 | P2 | Exact manifest, regular files only, no absolute/traversal/link/unlisted paths, empty release requirement; seven isolated harness cases pass. |

## Mandatory coverage —12/12 categories

| Category | Concrete release boundary/control |
|---|---|
| unhandled_error_paths | Every staged subprocess requires zero exit; startup health deadline; rollback independently attempts recovery and records failure types. |
| external_dependency_failures | Existing venv/provider order reused; no optional SDK required by app import; no dependency upgrade. Mock tests do not assert real provider availability. |
| race_conditions_and_state | Reject stored running-stage markers and the actual worker flag through nonprotected demo APIs before stop; perform a stopped-service backup; do not run concurrent release processes. Restart disconnects active visitors briefly; publication/session data remain intact. A legitimate concurrent visitor write can fail the strict post-cutover data-equality check; rollback only code and retain that newer data, never restore the backup. |
| resource_exhaustion | Sequential gates with600s cap; pre-cutover disk reserve over twice shared data plus512MiB; no new SFU on the small VM. |
| security_access_control | Strict SSH after first-use pin; loopback app unchanged; Caddy/operator-auth hashes unchanged; no secrets printed or included in source; LiveKit stays disabled. |
| data_integrity_partial_writes | No data import or provider work; full stopped-service tar/hash/list verification; only new WorkingDirectory drop-in changes; code rollback retains shared customer data. |
| observability_gaps | Exact source hashes, source commit, per-gate logs/results, selected health, before/after data manifests and public-route checks; receipt separates optional trial from active transport. |
| scale_and_load_failures | Existing one-worker feedback deployment retained; no new scale claim. Physical microphone/long-session/network quality are outside these free deployment probes. |
| billing_credit_mismatches | All staged gates mock/isolated/blocked sockets/blank keys. Post-release runtime probe sends only mic-off session.start, never questions/pitch/STT/TTS/Build. |
| retry_idempotency_issues | Existing new-release/drop-in/backup/green marker cause explicit stop rather than overwrite; recovery removes only this release's own drop-in; no semantic replay. |
| config_feature_flag_drift | Override only WorkingDirectory, inherit all existing ExecStart/environment; read-back verifies real customer/Sarvam configuration and unchanged environment/proxy. |
| edge_cases_from_prd | BMW exact bundle/media/pins survive code-only release; local gallery/voice/image contracts remain required; remote core/runtime gates run on exact packaged source. |

No additional finding in evidence grounding, authored speech, data schema, provider order or publication approvals: this operational change does not alter those flows. The new phrase code must have its own focused local contract before source is packaged. Deployment success is conditional on actual stage/cutover/verification results; this preflight is not that receipt.

## Local tooling verification

Five Python files parse. Seven isolated stage cases pass: exact source success; rejected digest mismatch, extra file, traversal, symlink, protected data manifest and occupied destination. These tests make no network call and do not inspect production files. Root owns final script review, execution, public browser check and release report.

The root reported final local17backend/7Node suites green before packaging: core445/24/smoke3/full mock28, domain25, web37, new question acknowledgement14 and native browser88. Those are reported adjacent evidence, not tests rerun by this read-only deployment reviewer. The staged27backend suites must still run against the uploaded committed bytes.

## Execution-time harness corrections

These corrections affect operational scripts outside the frozen application release. Initial logs remain retained. The numeric-IP blocker correction independently passes the exact-wrapper knowledge suite60/60 with zero outbound attempts; AI_NUMERICHOST preserves local numeric parsing while DNS/connection attempts remain blocked. The Python/JavaScript parity case reuses already-installed Playwright driver Node24.21.0 through the staging subprocess PATH only. No dependency or production environment change. All remaining fixture files were checked against d94d6ef.

The initial cutover preflight correctly stopped before service mutation on an old persisted voice marker. Two actual-worker observations were false; file/stored timestamps were504.1hours old. The revised operational check leaves that data intact and requires explicit Boolean inactive worker state, unchanged file bytes and both timestamps older than24hours. Independent fixtures12/12 verify actual workers, recent timestamps, file changes, ambiguous API state and the exact24hour boundary all block; stale inactive markers and clean idle states are accepted without writes.
