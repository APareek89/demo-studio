# Bounded mobile release:20260926-mobile

Root executes these helpers after review. They change application source and the four exact optional-browser-asset proxy responses; they do not change LiveKit, HAProxy, TLS, providers, storage architecture, security groups or demo content.

Use Python3.11. The existing runtime is `/opt/demo-studio-releases/20260925-livekit/.venv/bin/python`; the source release is `/opt/demo-studio-releases/20260926-mobile`; receipts are `/opt/demo-studio-backups/20260926-mobile`. Create the source directory empty, mode0755, owned byec2-user. Create the private receipt directory0700, owned byec2-user. Reuse the pinned SSH identity/known-host options from the preceding LiveKit release README. No install or dependency upgrade is required; stage rejects any changed requirements file.

Local preparation after the final commit:

```sh
python3 docs/aws/mobile-release-tools/package_source.py --commit FULL_COMMIT --output output/deploy-mobile-20260926/package
```

Upload `source.tar.gz`, `source-manifest.json`, `package.json` and this directory's Python helpers into the receipt directory. The archive is built from the exact Git commit, not the working tree; data/output/.env/runtime are excluded. Do not overwrite prior receipts.

From the remote receipt directory, run sequentially using the existing Python3.11 runtime:

```sh
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python app_stage.py
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python app_staged_gates.py
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python proxy_patch.py prepare
```

Stage verifies the exact source inventory, archiveSHA, requirements equality and `SOURCE_COMMIT`. The36 current staged suites include deck/acceptance/smoke/full-mock, existing runtime/LiveKit contracts, `mobile_audio_contract` and `mobile_recorded_audio_contract`; all use isolatedDATA/GRAPH, mock providers and blocked sockets/DNS. Browser fixtures run separately on the Mac because the mobile gallery fixture explicitly uses installed Chrome and WebKit. Provide a private `browser-qa.json` in the receipt directory with this schema, populated from actual final-source browser results:

```json
{
  "commit": "FULL_COMMIT",
  "passed": 1,
  "total": 1,
  "provider_calls": 0,
  "network_policy": "fixture-only",
  "errors": [],
  "browsers": ["chromium", "webkit"],
  "source_hashes": {
    "web/player-ui.css": "SHA256",
    "web/player/walkthrough.js": "SHA256",
    "web/player/live-voice.js": "SHA256",
    "web/player/player.js": "SHA256"
  }
}
```

The numbers above illustrate the schema, not a test result. Include every changed browser source hash and link/copy the detailed actual receipts; cutover binds the normalized proof to the source manifest and commit. Add newly introduced headless Node contracts to the staged suite list before freezing the package if needed.

`proxy_patch.py prepare` extracts only the reviewed optional-asset matcher/handler from the staged canonical template, inserts those two blocks into a saved copy of current Caddy, proves removing them yields the exact original bytes and validates the candidate. It does not reload Caddy. GET/HEAD on `/favicon.ico`, `/apple-touch-icon.png`, `/apple-touch-icon-precomposed.png` and `/manifest.json` will return404 without WWW-Authenticate. Other methods/paths keep operator authentication. The prior real isolated proxy checks passed58/58 plus153/153. Improper401 responses were confirmed; actual mobile login-popup causality was not reproduced.

Cut over only when no Build or customer room is active:

```sh
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python app_cutover.py
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python proxy_patch.py apply
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python app_verify.py
```

Cutover checks live Build flags and makes a read-only private SFU ListRooms call returning only counts. Active visits block service stop. It snapshots service/configuration, stops the app, hashes all current data, backs it up and verifies every archived file against that exact manifest before switching. Only the new `zzzz-release-20260926-mobile.conf` WorkingDirectory override is installed; the previous ExecStart/env/proxy-trust configuration stays effective. Recent customer sessions are preserved. The app is restarted and its source, provider settings, transport and data invariants checked. The proxy then receives only its validated patch and20 public/private checks. Public app verification checks exact frontend bytes, BMW publication/media, discovery, privacy and optional assets without questions or paid calls.

Failure during application cutover independently restores the prior app and retains current data; SIGTERM also enters recovery. Proxy failure restores its prior Caddy. For a later explicit rollback:

```sh
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python proxy_patch.py rollback
/opt/demo-studio-releases/20260925-livekit/.venv/bin/python app_rollback.py
```

Never restore the data archive over current customer writes as part of code rollback. Post-release customer activity can legitimately change session/FAQ/unknown files during verification; investigate any manifest difference rather than deleting it. The18 local release fixtures cover extraction/manifest safety, unchanged dependency reuse, source-bound browser proof, active Build/visit blocks, real backup corruption detection, success/failed cutovers and SIGTERM recovery. They use temporary data and service doubles, not actual AWS mutations or provider calls.
