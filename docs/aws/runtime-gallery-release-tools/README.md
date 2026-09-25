# One code-only runtime/gallery release

These scripts are a task-scoped continuation of the previous verified deployment, not a generic provisioner. Do not run `docs/aws/deploy-ec2.sh`; it provisions infrastructure. No new infrastructure, proxy, environment, dependency, demo/media import or paid provider QA is required here.

Paths:

- Receipt `/opt/demo-studio-backups/20260925-runtime-gallery` (ec2-user-owned,0700).
- Source `/opt/demo-studio-releases/20260925-runtime-gallery` (empty, ec2-user-owned,0755).
- Prior source `/opt/demo-studio-releases/20260925-bmw-gallery` remains intact.
- Runtime Python `/opt/demo-studio-releases/20260923-creta-v8/.venv/bin/python`.
- Only systemd change `/etc/systemd/system/demo-studio.service.d/zz-release-20260925-runtime-gallery.conf`, containing `[Service]` and the new `WorkingDirectory` only. Existing ExecStart/environment overrides remain authoritative.

Prepare from the final committed revision:

1. `source.tar.gz` contains only the chosen committed source/docs/evals. No `.git`, `.env`, production `data`, virtualenv or `output` tree. Archive member names are safe paths relative to the repository root; regular files/directories only.
2. `source-manifest.json` is `{relative_path: sha256}` for exactly the archive files.
3. `package.json` is `{ "commit": "<full40hex>", "archives": { "source.tar.gz": { "bytes": <integer>, "sha256": "<digest>" } } }`.
4. Upload the package, manifest, archive and these five Python files to the private receipt directory. There is no BMW/data archive.

Use SSH/SCP with key `/Users/macbook/.ssh/demo-studio.pem`, user `ec2-user@13.202.0.79`, `BatchMode=yes`, `StrictHostKeyChecking=yes` and `UserKnownHostsFile=/Users/macbook/.config/demo-studio/aws-known-hosts`. Never print private environment or operator-login files.

Execute sequentially on AWS with the existing runtime Python, from the receipt directory:

```sh
/opt/demo-studio-releases/20260923-creta-v8/.venv/bin/python stage.py
/opt/demo-studio-releases/20260923-creta-v8/.venv/bin/python staged-gates.py
/opt/demo-studio-releases/20260923-creta-v8/.venv/bin/python cutover.py
/opt/demo-studio-releases/20260923-creta-v8/.venv/bin/python verify.py
```

`stage.py` writes `stage-verified.json`. `staged-gates.py` runs27 suites and writes a commit/manifest/results-bound `staged-gates.ok.json` only when all pass. It does not install LiveKit or run browser RTC. System PATH has no Node; one Python/JavaScript parser-parity case reuses the existing Playwright driver’s bundled Node through the staging-only PATH. Focused local JavaScript/browser receipts remain required separately. Hostname DNS and outbound sockets are blocked; numeric IP parsing uses AI_NUMERICHOST without DNS so private-address rejection tests can run. Cutover verifies the marker and requires explicit inactive worker state. A stale persisted running marker is accepted only when its file is unchanged and both file/stored timestamps exceed24hours; actual workers, recent markers and ambiguous API state block. It snapshots private configuration, stops the app, hashes/backs up all shared data, verifies the backup, links existing data/env into the source release and switches only the WorkingDirectory. On failure it independently attempts old-app recovery, moves only its own drop-in aside, retains all current data, and writes `rollback.json`.

`verify.py` checks deployed source/frontend identity, production health, Caddy/environment identity, anonymous private-route denial, unchanged BMW bundle and a no-input/mic-off WebSocket handshake. It makes no provider calls or session-save requests. Existing media assets are unchanged and should additionally receive a representative public byte-range check and muted desktop/phone welcome review through the root's browser harness. Preserve any observed legitimate customer activity when interpreting post-release data differences; do not overwrite it with the backup.

Manual code rollback uses the same narrow boundary: stop demo-studio, move only this release's `zz-…conf` into its private receipt directory, daemon-reload, start demo-studio, and verify the prior WorkingDirectory/health. Leave Caddy/auth/env/shared data untouched. A data restore is not part of a code rollback.
