# AWS runtime/gallery release — 25 September 2026

**Live:** [BMW X7](https://13-202-0-79.sslip.io/#/play/dm_29df0418). Application **d94d6efc836a5ba08872aafbf9e37144dd113a99** is on GitHub master and AWS. Cutover completed **2026-09-25T11:35:49Z**. Subsequent receipt/tooling-only commits do not change the running application SHA.

## What changed

Ten neutral question acknowledgements rotate once each per visit before repeating. Fast answers and Continue/Pause/Stop bypass holding speech. Restart resets the cycle. Old publications can reuse exact matching recordings; other phrases use the existing locked runtime voice. Answer-first cancellation and stale-turn ownership remain intact. The approved BMW was not rebuilt or re-recorded.

The enabled BMW owner URL had an earlier crawl timeout. Runtime previously confused `crawl_active=false` with withdrawn authorization. Explicit owner enable/exclude intent now controls runtime access; the last build fetch result does not revoke it. Approved evidence remains first. When needed, the agent can fetch/search the enabled supplied domains and answer from actual retrieved passages with citations. For BMW this is bmw.in, including its www form. Unrelated domains, lookalikes and unapproved subdomains remain rejected. A failed read supplies no evidence, fact or cached answer. Current external-site/provider availability was not tested with paid questions in this release.

The release also includes the already reviewed immediate reversible speech hold, exact answer-picture retrieval and consecutive same-photo continuity. Core Build/Align workflow, graph nodes, published evidence and recordings stay unchanged.

**AWS retains the existing WebSocket voice transport. LiveKit remains an optional local trial, disabled on AWS.** Its source is committed, but hosted signaling/RTC/origin/TURN infrastructure has not been adopted. Use the public link above without the local `voice_transport=livekit` flag.

## Verification

- Exact source **1334/1334** files verified before/after staging and cutover. All **27/27** finite AWS test subprocesses passed with mock providers, isolated DATA/GRAPH, cloud off and blocked outbound connections/DNS. Numeric IP parsing is local-only through AI_NUMERICHOST.
- Core **qa_deck445/445, qa_accept24/24, smoke3/3, full mock28/28**, including194.22seconds of synthetic narration. Knowledge58passed/2skipped of60: installed Chrome and local OCR are unavailable in this AWS environment. Independent local exact-wrapper knowledge60/60 passed. [Every contract count and raw log digest](../qa/aws-runtime-gallery-release-2026-09-25/gate-counts.json). Counts overlap and must not be summed.
- Local final acknowledgement14/14, native player88/88 (eleven questions, commands, restart), voice96, LiveKit client47 and adjacent contracts remain verified against the frozen application. [Local QA](../qa/runtime-gallery-release-2026-09-25/README.md). AWS's Python/JavaScript parser-parity case uses the already-installed Playwright driver Node24.21.0 through the staging-only PATH; no dependency was installed.
- [Public checks17/17](../qa/aws-runtime-gallery-release-2026-09-25/public-verification.json): all32frontend files match committed hashes, real-provider health, retained bundle, private-route401 responses and a microphone-off WSS handshake. No question, STT/TTS, Build or session-save request was sent.
- [BMW media96/96](../qa/aws-runtime-gallery-release-2026-09-25/retained-media-and-source-permissions.json) return matching1KB range bytes, lengths and total sizes. Deployed runtime permission checks confirm bmw.in survives crawl failure and reject unrelated/lookalike/unapproved-subdomain URLs. This verifies authorization and asset delivery, not live search answer quality.
- Desktop1440/phone390 welcome screens have no script/asset errors or horizontal overflow. [Desktop](../qa/aws-runtime-gallery-release-2026-09-25/public-welcome-1440.png), [phone](../qa/aws-runtime-gallery-release-2026-09-25/public-welcome-390.png), [browser receipt](../qa/aws-runtime-gallery-release-2026-09-25/public-browser.json). Review was muted with microphone, WebSockets, beacons and non-GET requests disabled. Full gallery progression is covered by the earlier unchanged-source local receipts, not claimed by these welcome checks.
- All **4267existing data files unchanged**, none missing/added; environment, Caddy and operator auth unchanged. App and Caddy active, zero service error/traceback lines around cutover; read-only post-release checks preserved demo data. [Final receipt](../qa/aws-runtime-gallery-release-2026-09-25/final-verification.json). No new paid calls; no protected demo mutation or port8896 operation.

## Backup and rollback

New source: `/opt/demo-studio-releases/20260925-runtime-gallery`. Reused Python/Playwright runtime: `/opt/demo-studio-releases/20260923-creta-v8`. Only systemd change is `zz-release-20260925-runtime-gallery.conf`, overriding WorkingDirectory; existing ExecStart/environment remain. Caddy/operator login were not changed.

Verified stopped-service data backup: `/opt/demo-studio-backups/20260925-runtime-gallery/data.before.tar.gz`, **862035472bytes**, SHA256 **c669abb59ee59df87283377b7dc9af50f1fd547bc34f32eed661d5e20c987329**. The private directory retains configuration snapshots, before/after data manifests, complete raw gate logs and prior failed attempts. No private configuration, customer history or data manifest is committed.

Previous release `/opt/demo-studio-releases/20260925-bmw-gallery` remains intact. Code rollback: stop demo-studio, move only this release's `zz-release-20260925-runtime-gallery.conf` to the private receipt directory, daemon-reload, restart and verify the previous WorkingDirectory/health. Retain current shared data, environment and Caddy. Never restore an old data backup as part of a code rollback. No rollback was needed.

## Retained failures and limits

Two staging harness attempts stopped before service changes: an overbroad DNS blocker rejected five numeric-address safety tests; the next attempt lacked Node on system PATH for a parser-parity case. Corrections retained strict network blocking and reused the installed Node. The full27suite set then passed. Initial cutover preflight stopped on one persisted running marker504.1hours old; repeated actual-worker observations were inactive. The operational check now permits only unchanged, older-than24hour markers with explicit inactive worker state, without clearing or changing stored data; independent fixtures12/12 cover active/recent/changed/ambiguous cases. The first browser harness attempt referenced URL outside its sandbox globals; the host check was corrected and the isolated browser restarted. These are harness/preflight corrections, not application fixes or hidden production failures.

The operative deployment scripts were corrected outside the frozen source release and are committed with this receipt; [their exact hashes](../qa/aws-runtime-gallery-release-2026-09-25/operational-tool-hashes.json) distinguish them from d94d6ef's initial tooling. [Twelve-category FMEA and independent review](runtime-gallery-release-tools/review.md), [preflight corrections](../qa/aws-runtime-gallery-release-2026-09-25/preflight-corrections.json).

This remains a small single-worker feedback deployment. No new acoustic, physical microphone, load or hosted-LiveKit acceptance is claimed. The existing public runtime can incur provider spend during customer use; no new rate-limit/tenant architecture is included. No open product question blocks this release.
