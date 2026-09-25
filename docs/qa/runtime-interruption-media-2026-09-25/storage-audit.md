# Storage and retrieval audit — 25 September 2026

Public AWS health was read directly during this task: `storage=local`, `mock=false`, `model_tier=customer`, `cloud.enabled=false`, cloud reason `off (mock or CLOUD_SYNC=0)`. This matches the BMW deployment receipt. No AWS write or provider request was made.

The authoritative working data is on the EC2 server under `/opt/demo-studio/data/demos/<demo_id>/`: source files, extracted evidence, immutable knowledge snapshots, saved BM25/concept/character indexes, scripts, slides, FAQ cache and recorded audio. The graph database is a separate server-side SQLite file. The browser gets the published bundle, which includes approved fact records, slide/tag geometry, image metadata, the fact-to-image map and media URLs. It fetches image/audio bytes from the server's media endpoint; it does not own the authoritative knowledge registry or run grounded answer retrieval. Every runtime question is validated against its pinned snapshot.

The repository has an optional AWS storage adapter. Enabled cloud sync mirrors file/media bytes to S3, with DynamoDB records for demo metadata, events, sessions and leads. `storage.Aws.media_url` can use signed S3 URLs for already mirrored objects; a missing mirrored file falls back to local serving. This adapter is not enabled in the deployed app. Enabling it is an operational durability/media-offload choice, not an automatic semantic-retrieval or answer-latency improvement.

Current code links: `server/storage.py`, `server/cloud.py`, `server/store.py`, `server/config.py`, `server/knowledge.py`, `server/agents/bundle.py`, `server/runtime_graph.py`, `server/app.py`, `web/app.js`. The public bundle contains approved fact details, so do not describe all knowledge as private server-only data; complete source extraction, historical registry and runtime authority remain server-side.

## Bounded correction

`knowledge.retrieve` previously loaded and parsed a complete extracted source JSON for each matching fact before ranking, deduplication and the return limit. It now preserves exactly the same selection/scoring/scope rules, then attaches context only for selected evidence. A per-call memo parses each selected source once. Context is deep-copied per result, preserving the previous independent-object behavior. Nothing survives the request, so no cross-session cache key, expiry, new database or invalidation rule is introduced.

The isolated BMW-copy probe compares full old/new evidence objects for five questions, including identical scores, source metadata, context ordering, conflicts and coverage. All equal. Engine question:26 source parses to1; comfort:31 to1; dashboard:16 to1; roof:5 to1. The comfort probe reduces parsed source bytes from7,334,941 to236,611. Diagnostic local single-run times change from30.217ms to8.952ms for comfort; these are not a latency SLA and do not measure provider/voice delay.

## Verification

Frozen exact e80a180 baseline: deck445/445, acceptance24/24, smoke3/3 and release mock28/28,194.22seconds synthetic narration, zero outbound attempts. Exact source hashes and logs are under `../baseline/`.

Focused new contract:8/12 pass before change,12/12 after; all four previous failures are redundant/unselected source read assertions. New tests also establish complete golden response equality for five fixture queries, scope/competitor/expired/unapproved exclusions, request freshness, old/new pin independence, context object independence, missing/malformed source behavior and invalid pin rejection. Related contracts: knowledge60/60, runtime graph130/130, FAQ cache27/27, transmission conditions17/17. Syntax and whitespace checks pass. Source/log evidence: `verification.json`, `results.json`, `before-contract.json` and suite logs.

The first knowledge-contract wrapper blocked harmless literal-IP DNS resolution, producing five harness failures before the test's SSRF assertion. The corrected harness resolves numeric IPs locally and still blocks all actual DNS/connect/sendto calls; its final result is60/60 with zero outbound attempts. The original failed log is retained. No application safety guard was changed for testing.
