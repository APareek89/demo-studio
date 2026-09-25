# AWS BMW gallery feedback release — 25 September 2026

**Live:** [BMW X7 feedback demo](https://13-202-0-79.sslip.io/#/play/dm_29df0418). Viewers need no password. The operator's [builder](https://13-202-0-79.sslip.io/#/home) now requires a private login.

Anand approved the revised BMW and explicitly requested master/GitHub plus AWS including that demo. Application **278c21db39abc15c4f56125637b3ff2a790e4834** and proxy configuration **0f7e2be8d38c453cdf43e588b02517967d41dc68** were pushed to master before deployment. Later receipt-only commits document the release; they do not change the running application bytes. No paid provider QA or regeneration was performed in this deployment.

## Deployed scope

- Cutover: **2026-09-25T09:17:44Z**. Service uses `/opt/demo-studio-releases/20260925-bmw-gallery`, selected by `99-release-20260925-bmw-gallery.conf`; upstream remains loopback `127.0.0.1:8877`. The existing virtualenv is reused from `/opt/demo-studio-releases/20260923-creta-v8`; requirements are unchanged and pip check passed.
- Running application: gallery in the middle slide area, reviewed picture/caption selection, human-guide prompting, correct Gemini system role and sparse voice expression, plus prior runtime/source/noise/session fixes in master. No new workflow, agent, node or database schema.
- AWS BMW `dm_29df0418`: approved bundle v2,15slides,11distinct photos,32labels, published evidence snapshot `kb_cd2f6a8cf905301b30a07d42`. The existing selected two-minute target remains; measured eligible narration122.64s exceeds120s. Source bundle SHA-256: `7baeffb535e121fa793a1b8fc5dbec4537194a20bda517f8ab0ffeed96620a02`. All96unique published media assets match their manifest; no audio was regenerated. Locked Sumit/en-IN stays.
- Data import contains151 approved demo/source/evidence/media files plus an empty conversation file. Local sessions, leads, runtime records, logs, traces, usage, read history and readiness were excluded. The full pinned evidence subtree is present; local global graph/share secrets and other demos were not copied.
- Effective production health: mock off, customer tier, Build Runware GPT5.5→Gemini3.8Flash→Claude, runtime Gemini→Claude→Runware, hedge enabled after3s, Sarvam TTS/STT, local storage/cloud off. The shared environment checksum is unchanged; the new customer Build default applies without replacing owner credentials or explicit overrides.

## Public and operator access

The old proxy exposed editor and private stored-record paths anonymously. The existing Caddy now admits published shell/bundle/media and the normal customer runtime/session-save endpoints publicly; all remaining methods/paths require operator Basic Auth. Signed summaries retain application HMAC verification. This operational boundary does not add multi-user accounts or alter player logic.

Operator login is saved locally in `/Users/macbook/.config/demo-studio/aws-admin.json` (mode0600). Only the bcrypt entry is installed at `/etc/caddy/demo-studio-admin.auth`, root:caddy0640. Neither credential nor hash is committed. Share the direct BMW player link without the operator login. Closing the player into the owner inventory can request login; browsing the public demo itself does not.

Source template and repeatable real-Caddy contract: [boundary documentation](feedback-proxy-boundary.md). All three600s upstream timeouts and the1GB request-body limit remain. Caddyfile SHA-256: `60ba8ffeb9558bb6b22db7c822159de3d85027651b8d6c8e1948c4665c4fdb6e`.

## Verification

- AWS committed source1116/1116 hashes verified before and after staging. Free staging uses temporary DATA/GRAPH, mock providers, blank keys, cloud off and blocked outbound sockets. All33 subprocesses succeeded with zero outbound attempts. Core **qa_deck445/445, qa_accept24/24, smoke3/3 phases, full mock28/28**, including real browser fixture and194.22s synthetic narration.
- [Exact per-contract counts and log hashes](../qa/aws-bmw-release-2026-09-25/gate-counts.json): provider79 executes inside deck; its standalone import-only exit is not extra test coverage. Generation55/55 excludes three optional unavailable legacy-Creta fixtures. No standalone JavaScript suite was rerun on AWS (Node absent); prior exact-application-byte local gallery320/native87, final BMW player281/audio71 remain recorded in [local acceptance](../qa/bmw-gallery-narration-2026-09-25/README.md).
- Real installed Caddy2.8.4: **153/153** checks against a separate loopback fixture, including correct/wrong credentials, media extension/path boundaries, encoded traversal, allowed methods, signed-summary delegation and WebSocket upgrade. No production mutation/provider call in that contract.
- [Public deployment checks17/17](../qa/aws-bmw-release-2026-09-25/public-verification.json): HTTPS shell/health, frontend26/26 SHA-256 matches, bundle content and pin identity, media96/96 byte-range responses, private paths401, owner login and wrong-password rejection. A real WSS connection sent only `session.start` with microphone off and received `session.ready`; no runtime question, pitch, voice generation, session-save or Build.
- Desktop1440 and phone390 public welcome screens load with no script/asset failures or horizontal overflow. [Desktop screenshot](../qa/aws-bmw-release-2026-09-25/public-welcome-1440.png), [phone screenshot](../qa/aws-bmw-release-2026-09-25/public-welcome-390.png), [browser receipt](../qa/aws-bmw-release-2026-09-25/public-browser.json). Browser QA disables microphone, runtime sockets, beacons and non-GET requests. Gallery progression was already checked281/281 before approval; this release browser check establishes remote loading, not another complete acoustic tour.
- Before/after: **4108existing files unchanged**, none missing;152BMW files added. Environment unchanged; application and Caddy active, no new service errors. A second read-only verification after public probes still found no BMW session, lead, runtime, log, usage or trace writes. [Final data/service receipt](../qa/aws-bmw-release-2026-09-25/final-verification.json). Protected demo bytes stayed unchanged; local port8896 was not operated.

## Backup and rollback

Stopped-service consistent data backup: `/opt/demo-studio-backups/20260925-bmw-gallery/data.before.tar.gz`, **788965772bytes**, SHA-256 **8195c495f9ae1e7df7261f7dd5b51b9078c5a4c7e956832a5404b6cd737537e1**. Archive listing/hash verified before switch. The private receipt directory also retains environment backup/hash, previous systemd configuration, previous Caddyfile, manifests, staging logs and cutover script.

Previous release `/opt/demo-studio-releases/20260924-feedback` at483755d and its98drop-in remain intact. To roll back application code, stop the app, move only the99drop-in to the private receipt directory, daemon-reload, restart and verify old WorkingDirectory/health. **Keep current shared data and the new operator boundary** during a code rollback; the routes remain compatible. Do not overwrite customer feedback with the old backup. If a proxy rollback is required, separately validate the prior configuration and explicitly account for its formerly public private-record routes.

The cutover failure path independently attempts old-app recovery even when proxy restoration fails, records aggregate recovery errors and retains current shared data. That safeguard was reviewed before the switch. The initial path-existence preflight needed sudo to inspect the protected drop-in directory and stopped before any service change; it was repaired and rerun. Later journal timestamp and screenshot-selector issues were verification harness corrections, retained in local operational logs. No application rollback was needed.

## FMEA and remaining limits

[Independent12-category release review](../qa/aws-bmw-release-2026-09-25/review.md) covers errors, providers, race/state, resources, security, integrity, observability, scale, billing, retry, configuration and product edges. Its two concrete operational actions were completed: private operator boundary and resilient rollback. No dependency/schema/media blocker remained; all listed release conditions were checked.

This is a small single-worker feedback deployment, not a load-tested multi-tenant service. Public runtime can intentionally incur provider spend; per-visitor ownership, rate limits and quotas remain future scope. Physical microphone/noise behavior, perceived voice emphasis and current paid-provider availability were not re-tested. Existing source grounding, approved evidence, selected duration, locked voice and publication safeguards remain. No new product question was opened.
