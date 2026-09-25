# LiveKit Demo Run trial

The trial wraps the existing demo runtime. Build, Align, approved evidence, model/provider order, gallery, early speech holds, interruption ownership and session saves remain unchanged. The normal player remains the default and does not import the optional SDK.

Use `?voice_transport=livekit` before the route hash to opt in. The local server must also have `LIVEKIT_TRIAL_ENABLED=1`; the launcher sets it only for its own process. Removing the URL flag uses the existing WebSocket transport.

## What this stage tests

- One existing microphone capture is published as a LiveKit WebRTC track. The existing worklet still performs the immediate local speech hold.
- Existing controls, transcripts, validated answers and PCM speech chunks travel through reliable LiveKit data. The existing playback queue still waits for the correct reviewed picture before speaking.
- Disconnects end the transport visibly. An explicit retry creates a fresh room; previous turns are never replayed across reconnects.
- This is **not** LiveKit Agents, outbound RTP speech, adaptive interruption or speaker identification. It makes no claim to distinguish the customer's voice from nearby television speech.

## Start an isolated trial

Use Python 3.11 and a LiveKit Server binary. The tested pins are Python `livekit==1.1.20`, `livekit-api==1.2.1`, browser SDK `2.22.3` and LiveKit Server `1.13.7`. Browser code and its Apache license are vendored; no CDN is required. Keep the existing tested app versions as constraints and optional dependencies in their own environment:

```bash
.venv/bin/python -m pip freeze > /tmp/demo-app-constraints.txt
python3.11 -m venv /tmp/demo-livekit-venv
/tmp/demo-livekit-venv/bin/python -m pip install -c /tmp/demo-app-constraints.txt -r requirements.txt -r requirements-livekit-trial.txt
/tmp/demo-livekit-venv/bin/python scripts/run_livekit_trial.py \
  --source-demo /absolute/path/to/data/dm_your_published_demo \
  --livekit-server /absolute/path/to/livekit-server \
  --state-dir /tmp/demo-livekit-review \
  --rtc-host YOUR_MAC_PRIVATE_IPV4
```

For `--rtc-host`, use the address reported by `ipconfig getifaddr en0` on this Mac (or the active interface). The launcher validates that it is private and actually owned by this machine. Native libwebrtc does not offer loopback ICE candidates, so media UDP binds only this explicit private interface; app/token/signaling still bind127.0.0.1.

The launcher prints the player URL. Defaults are app8920, signaling7880 and RTC UDP7882; it checks availability without stopping existing services. It refuses port8896 and the protected demo. Ctrl-C stops only the two processes it started.

It copies the chosen publication, pinned knowledge and assets to its own DATA/GRAPH paths, excluding old sessions, contacts, logs and usage. A later launch retains the trial's own visits; if the original bundle changes, select a fresh state directory. The original publication is never rebuilt or edited.

**Mock mode is the default.** Existing recorded narration plays and synthetic QA can exercise real RTC delivery, but mock STT does not transcribe your microphone. Type questions to exercise the demo in this mode. Python external DNS/TCP/UDP is denied; native RTC is configured separately with same-machine host ICE and no public STUN. This is not a system-wide firewall. A physical speech/provider acceptance run requires an explicitly chosen `--live-providers` launch with configured credentials; that mode may incur provider charges and does not install the mock socket guard.

## Conversational review versus transport QA

For an actual spoken review, explicitly add `--live-providers` to the launcher command and use configured provider credentials. Match the intended runtime tier, for example `MODEL_TIER=customer`. This enables paid STT, grounded answering and TTS in the isolated copy; it does not rebuild the publication. The launcher's printed URL deliberately has no `mute=1`: that query disables output and default voice input and belongs only in muted automation.

A mock RTC pass proves transport, not recognition or a useful spoken answer. The25September review failure demonstrated that typed text can reach the graph successfully while mock reasoning returns a fragment and mock speech produces a short silent clip. Review links must identify the mode; verify the stock app route and actual provider results before calling a link ready for conversation.

## Boundary and rollback

Token issuance requires a loopback caller and exact matching Origin. Tokens grant one random room and viewer identity, microphone/data permissions, and a120second join lifetime. The worker independently bounds room lifetime, active room count, queues, fragments and input generations. Secrets stay in a mode0600 local configuration file and never enter the repository or browser receipt.

This launcher is intentionally for local review. Hosted deployment still requires production authentication, TURN/network policy, capacity testing, monitoring and physical-device acceptance. Do not expose these ports or promote the flag based solely on mock results. Normal app/AWS configuration is untouched; omit the query flag to return to the existing transport.

Acceptance evidence and remaining limits: [QA receipt](qa/livekit-trial-2026-09-25/README.md).
