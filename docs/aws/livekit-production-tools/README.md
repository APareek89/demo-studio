# LiveKit on the existing feedback host

This task uses the existing EC2 instance and existing public TCP443 permission. It creates no cloud resource and changes no security group. Root owns execution. Helpers are specific to the reviewed host; they do not provision generic infrastructure or touch production demo data. The application release/cutover helpers are separate `app_*.py` files.

## Network decision

HAProxy accepts TCP443 and passes app/RTC TLS to Caddy on127.0.0.1:8443, preserving the real client address with PROXYv2. Caddy requires that header on its loopback listener, sanitizes forwarded headers, retains the existing operator-auth boundary and forwards the app only to127.0.0.1:8877. The only new anonymous app routes are exact GET `/api/runtime/transport` and exact POST `/api/demos/dm_[0-9a-f]{8}/run/livekit/token`.

`rtc.13-202-0-79.sslip.io` permits GET `/rtc`, `/rtc/v1`, `/rtc/validate` and `/rtc/v1/validate`; other RTC-host requests return404. No SFU administration API is exposed. App/signalling remain trusted HTTPS/WSS.

`turn.13-202-0-79.sslip.io` routes through a private HAProxy TLS terminator and then to authenticated embedded TURN on172.31.13.9:5349. The browser must use relay ICE. SFU and TURN relay addresses stay on the instance privateIP; the colocated Python RTC worker uses its private host candidates. TURN peers are restricted to that one privateIP, with the complement of all IPv4 plus all IPv6 denied. Public UDP/TCP ICE ports stay closed. Hosted native-browser acceptance must prove this topology; configuration parsing alone does not establish media delivery.

Opening UDP7882/TCP7881 was rejected for this release: the available IAM permissions cannot reliably revoke/reattach the existing SG policy. The chosen443 relay path has additional bandwidth/latency and a two-room host limit. It does not introduce a paid cloud account, machine, load balancer or external TURN service. Ordinary existing EC2 bandwidth billing still applies.

## Pins and private material

- Existing EC2 `i-0410e37b7ab0297e1`, EIP13.202.0.79, privateIP172.31.13.9, ap-south-1.
- Existing source before release `/opt/demo-studio-releases/20260925-runtime-gallery`; new application `/opt/demo-studio-releases/20260925-livekit`, with a separate `.venv` prepared by root.
- Receipt `/opt/demo-studio-backups/20260925-livekit`; transport subtree is root-only0700.
- LiveKit1.13.7 binary SHA256 `bcf05dcdb093657208efb1d85ac54c02ab28561bf66774db7e6bb173d3736ff3`;55,230,624bytes. Archive `https://github.com/livekit/livekit/archive/refs/tags/v1.13.7.tar.gz`, SHA256 `b42f34b095dff22639a40256c3f98fd563fdbce5d497e449ceb06ee010de88c5`. Cross-compiled using Go1.27.1, `GOOS=linux GOARCH=amd64 CGO_ENABLED=0`, `go build -trimpath -ldflags='-s -w' ./cmd/server`; officialproxy/sumdb verified modules. Binary version must also be verified on AWS.
- Amazon Linux package `haproxy-3.0.23-2.amzn2023.0.1`; existing Caddy2.8.4. No custom Caddy plugin.
- SSH pins: key `/Users/macbook/.ssh/demo-studio.pem`, user `ec2-user@13.202.0.79`, `BatchMode=yes`, `StrictHostKeyChecking=yes`, `UserKnownHostsFile=/Users/macbook/.config/demo-studio/aws-known-hosts`. ED25519 `SHA256:TlrEM+lw8RjV5DWeMZi2vfltLRP2MSh+NJFXxayGEKI` was pinned by approved TOFU after verifying EC2/EIP metadata; no independent console-key attestation is claimed.
- API credentials are generated on-host. `/etc/demo-livekit/runtime.env` is root0600 and loaded by systemd; original provider `.env` is unchanged. SFU YAML is root:demo-livekit0640 in a0750directory. TURN combined private PEM is root0600. Never copy these into Git, receipts published to users, or stdout.
- No HAProxy access logs. Caddy global error encoding removes request URI, Authorization and Cookie. The contract intentionally forces an upstream error with a synthetic query token to verify redaction. Journals are still private operational records, not safe support attachments.

## Reviewed execution phases

Upload these tools and the pinned binary to an operator-owned staging directory. Run from there with `sudo /usr/bin/python3`; each phase is explicit and prints sanitized receipts. No phase calls AWS APIs.

1. `bootstrap.py stage --binary /path/to/livekit-server-linux-amd64`: validates prior Caddy hash, snapshots it, installs the pinned package/binary and inactive units, generates private keys/configs, uses the exact binary's strict YAML parser (`ports`) and Caddy validators. LiveKit1.13.7 has a formatting bug displaying scalar UDP7882 as `%!s(int=7882)`; the helper handles this known output without relaxing the strict YAML parse. `--resume-stage` resumes only the known pre-configuration partial stage, verifying its binary/backup and retaining existing generated keys.
2. Run existing `docs/aws/check_feedback_proxy.py --template Caddyfile.app-boundary.template --caddy /usr/bin/caddy --output <receipt>/proxy-boundary.json` (153 assertions), then `sudo python3 edge_contract.py --output <receipt>/edge-contract.json`. The latter launches only ephemeral loopback fixture processes and synthetic TLS/auth. It tests all new public routes/method denials, SNI separation, trusted TLS, actual client address versus spoofed headers, TURN PROXYv2 and query-token log redaction. Run `python3 operations_contract.py` for ten failure-injection checks covering interrupted rollback and rejected certificate renewal. These fixtures passed153/153,41/41 and10/10 respectively on25September (existing boundary and edge on AWS; recovery faults locally). These are not a substitute for hosted browser RTC acceptance. A fixture caught Caddy's ordering of a bare `respond404` before matched `reverse_proxy`; RTC now uses exclusive handle blocks. Already prepared older staging Caddy files require `bootstrap.py refresh-edge-config` before the certificate phase; this preserves and checks exact SFU/HAProxy/private-env bytes and validates only the replaced staging Caddy files.
3. Capture existing Caddy/auth/provider-env hashes and service state privately. `bootstrap.py certificates` reloads the existing443 Caddy with the additional hostnames, acquires RTC/TURN certificates via HTTP01 on existing80, creates the protected TURN PEM and validates HAProxy. It restores the original edge on failure.
4. `bootstrap.py activate` starts private SFU, moves Caddy TLS to8443 and starts the SNI edge on443. It checks real trusted app HTTPS, private RTC-route denial and the exact TURN leaf through443. The old application still runs. This short listener transition can interrupt current connections; perform it when visits/builds are idle.
5. Perform the isolated mocked hosted RTC proof below before application cutover. A failed hosted proof blocks adoption; do not silently fall back to old WebSocket. Then use reviewed application cutover helpers, verify public discovery, native no-input/mic-off session startup and retained BMW media without paid providers.
6. Only after acceptance, `bootstrap.py enable` persists SFU/HAProxy and the cert-renewal timer across reboot. Record all actual counts in the release receipt.

At any failure, `bootstrap.py rollback` independently stops/disables only newly owned services, restores the original Caddy and verifies its public trusted HTTPS plus application health. It never restores demo data or provider environment. Application rollback is a separate coordinated operation when application cutover has occurred. Preserve customer writes; a code rollback must not copy old data over current data. A failed stop does not prevent attempts to restore the previous edge.

## Certificate lifetime and TURN lifetime

Caddy owns renewal through HTTP01 on80; TLS-ALPN challenges are disabled for these hosts because TURN's443 SNI terminates in HAProxy. ExplicitHTTP redirects target external443, never8443. `demo-livekit-cert-sync.timer` checks every6hours. The root helper verifies exact hostname, seven days of remaining lifetime, matching key and trusted served leaf, then atomically replaces its0600PEM and gracefully reloads HAProxy. A failed reload/served-leaf check restores the previousPEM and attempts another reload. Commands and network retries are bounded; SIGTERM enters the restoration path, with120second service timeout. SFU is not restarted during normal renewal. The first preparation uses `--no-reload` before the edge is active.

Embedded TURN `ttl_seconds:300` is the lifetime for a **new allocation credential**, not a five-minute call limit. Pinned `pkg/service/turn.go` authenticates Refresh/CreatePermission/ChannelBind/Send/Data after that expiry, while expired initial Allocate is rejected. Pinned `pkg/service/roommanager.go` advertises `turns:<domain>:443?transport=tcp` even though the private backend listens5349. A reconnect must obtain a new app grant/room transport as normal; reconnect/long-session acceptance remains separate from these source guarantees.

All rendered SFU fields are present in pinned `pkg/config/config.go`, including `num_tracks`, `bytes_per_sec`, signal/body limits, data-channel buffered bytes, trusted PROXY CIDRs, per-user relay allocation limit, restricted-peer allowlist and peer denylist. `rtc.node_ip` binds routing to the private host; `use_external_ip:false` and private STUN prevent external address discovery. Strict parse and actual hosted media acceptance are both required.

## Isolated hosted RTC QA

`prepare_hosted_qa.py` prepares a disposable BMW publication under `<receipt>/hosted-qa`, selecting only the same allowlisted files/directories as the local trial launcher and rejecting symlinked assets. Previous visits, leads, logs and usage are excluded. It does not start the service. Ensure ec2-user can traverse the receipt's parent directories; never make the private transport subtree readable.

`demo-livekit-qa.service` uses the new app source/venv and only LiveKit credentials from `/etc/demo-livekit/runtime.env`; a second private env file forces MOCK1, cloud off, local storage, blank provider keys and isolatedDATA/GRAPH. It accepts origin `http://127.0.0.1:8940`, listens only127.0.0.1:18877 and is capped at384MiB/oneCPU. Its Python wrapper blocks external connections/DNS and permits only loopback SFU7880. The native SDK separately uses the host's SFU media sockets; this is not a system-wide firewall claim. Start this unit only for the acceptance window, alongside the two-room/256MiB SFU cap.

Create a pinned SSH tunnel on the Mac:

```sh
ssh -N -o ExitOnForwardFailure=yes -o BatchMode=yes -o ConnectTimeout=10 \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/Users/macbook/.config/demo-studio/aws-known-hosts \
  -i /Users/macbook/.ssh/demo-studio.pem \
  -L 127.0.0.1:8940:127.0.0.1:18877 ec2-user@13.202.0.79
```

Load `http://127.0.0.1:8940/?mute=1#/play/dm_29df0418`. HTTP UI travels through the SSH tunnel; signalling and media must independently use trusted public AWS WSS/TURN443. Root's native-browser harness must observe relay ICE selection, typed control/answer, real incoming PCM and microphone-track transport using synthetic audio. This has no provider/acoustic-quality acceptance implication. Stop `demo-livekit-qa.service` after the check, remove only its owned unit, daemon-reload, and close only the owned tunnel. Keep its private receipt/data for audit; do not touch real demo state.

Official references: [LiveKit deployment](https://docs.livekit.io/transport/self-hosting/deployment/), [ports](https://docs.livekit.io/transport/self-hosting/ports-firewall/), [pinned TURN source](https://github.com/livekit/livekit/blob/v1.13.7/pkg/service/turn.go), [pinned configuration](https://github.com/livekit/livekit/blob/v1.13.7/pkg/config/config.go), [HAProxy PROXY protocol](https://www.haproxy.com/documentation/haproxy-configuration-tutorials/proxying-essentials/client-ip-preservation/enable-proxy-protocol/), [Caddy listener options](https://caddyserver.com/docs/caddyfile/options).
