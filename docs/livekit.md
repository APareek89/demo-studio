# LiveKit Demo Run

LiveKit is the default public player and Rehearse transport locally and on AWS. Applicationae98532 is deployed after actual public TLS-relay verification. [Release receipt](aws/release-livekit-2026-09-25.md) records the source, gates, preserved data, two-room hosted capacity and rollback; [Handoff](../Handoff.MD) identifies the current local workspace.

Both entry points request `GET /api/runtime/transport` before mounting the player. Configured LiveKit needs no URL flag. `?voice_transport=websocket` is a diagnostic override; it never activates automatically after a failed join. Configuration discovery returns only mode/readiness, has `Cache-Control: no-store`, and never creates a room or calls a provider.

One microphone capture becomes a WebRTC audio track. Reliable room data carries the existing controls, transcripts, validated answers and owned PCM output. Existing STT, grounded reasoning, voice lock, gallery preparation, interruption and incremental-session owners remain authoritative. Build/Align and graph nodes are unchanged. This does not add LiveKit Agents, outbound RTP speech or speaker identification.

## Normal local workspace

Python3.11 dependencies include pinned `livekit==1.1.20` and `livekit-api==1.2.1`. The browser SDK2.22.3 and its license are vendored. Install LiveKit Server1.13.7 separately; the launcher finds PATH or `~/.local/lib/demo-studio/livekit-1.13.7/livekit-server`.

```bash
cd /Users/macbook/Documents/demo-studio
DEMO_STUDIO_DATA=/path/to/existing/demos \
DEMO_STUDIO_GRAPH_DB=/path/to/existing/graph.sqlite \
  .venv/bin/python scripts/run_local.py --live-providers
```

Choose the existing workspace paths deliberately. This launcher never copies or rebuilds a publication. Defaults use configured DATA/GRAPH or the repository's ordinary data paths. State/logs are private under `~/.local/state/demo-studio/livekit`; default app8910, local signaling7890 and RTC UDP7892 are checked before starting. Mac private IPv4 detection can be overridden with `--rtc-host`; it must be owned by this machine. Ctrl-C stops only this launcher's children. Occupied ports cause an error, never another process's termination.

Omit `--live-providers` for mocked providers with blank credentials, cloud sync off and external Python sockets blocked. Use isolated DATA/GRAPH for QA. Mock STT cannot transcribe a real conversation. Native RTC uses the separately constrained same-machine private interface and local STUN; Python socket blocking is not a system firewall. The printed link has no mute query: `mute=1` disables output/default voice input and belongs in muted automation.

The separate [isolated trial launcher](livekit-trial.md) remains available for copying one publication into temporary review storage.

## Hosted deployment

Set `LIVEKIT_ENABLED=1`, public secure `LIVEKIT_URL`, private `LIVEKIT_INTERNAL_URL`, exact comma-separated `LIVEKIT_ALLOWED_ORIGINS`, and private API key/secret. Public hosted signaling requires WSS. Origins are exact; HTTP is allowed only for an explicitly configured loopback-origin QA client whose actual ASGI peer is loopback. Do not trust arbitrary forwarded headers. Tokens are short-lived, room/identity scoped, and grant only microphone/data publication; private worker credentials never reach the browser.

The AWS deployment uses two active rooms on the existing small EC2 instance, configurable through `LIVEKIT_MAX_ROOMS`. Token issuance permits twelve attempts per real client IP per minute, including failed requests. Room joins, message/body size, fragments, audio pre-roll, idle and visit duration are bounded. Publication version/snapshot is checked before and after joining the worker. Disconnects require explicit retry and never replay a customer turn. The browser's connection deadline is30seconds; older diagnostic WebSocket remains8seconds.

`LIVEKIT_ICE_TRANSPORT_POLICY=relay` forces the browser through authenticated TURN/TLS on443. The colocated worker keeps private host ICE. Public TLS routes split by server name: the app and WSS pass to Caddy, TURN passes to its TLS terminator. Only existing ports80/443 are public; no security-group expansion or new instance is required. Certificate renewal copies only the TURN certificate into a private PEM, validates its host/key/expiry and reloads the terminator. The app's operator authentication boundary remains in force.

Official deployment references: [TLS/TURN deployment](https://docs.livekit.io/transport/self-hosting/deployment/) and [port requirements](https://docs.livekit.io/transport/self-hosting/ports-firewall/). Exact installed configuration, acceptance and rollback belong to the dated AWS release receipt. Server-configured readiness is not a live connectivity probe; real browser room/relay tests establish connectivity.
