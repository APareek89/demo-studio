# LiveKit local trial — 25 September 2026

The optional trial is implemented on `codex/sales-trainer-flow`, after local runtime-fix commit `aeddec9`. Default playback, master and AWS are unchanged. Use the [launcher instructions](../../livekit-trial.md). The currently running isolated BMW trial is [localhost8920](http://127.0.0.1:8920/?voice_transport=livekit#/play/dm_29df0418).

This is real WebRTC microphone transport with mock STT/model/TTS providers. Existing runtime control events and PCM output use reliable LiveKit data; recorded narration stays HTTP. It does not add LiveKit Agents, automatic turn ownership, outbound RTP speech or speaker isolation. Existing graph, grounding, image-before-speech, interruption, playback and persistence owners remain in charge.

## Final gates

- Default app, with no LiveKit installed in its Python environment: **qa_deck445/445, qa_accept24/24, smoke3/3, full mock journey28/28**. Core test fixtures and duration boundaries remain disclosed in their logs. The full journey measures194.22seconds of synthetic narration; this is not a new BMW recording.
- New backend transport **50/50**, browser adapter **47/47**, isolated launcher/network boundary **16/16**.
- Existing voice **96/96**, immediate speech hold **26/26**, listening **16/16**, runtime recovery **17/17**, incremental save **18/18**.
- Actual default gallery **320/320**, current native player **87/87**; unchanged prior revision `aeddec9` baseline also87/87. Desktop1440/phone390 screenshots retain the approved top and bottom UI and gallery.
- Actual LiveKit browser **24/24**: pinned SDK and real local SFU, synthetic microphone over RTC, nonzero media bytes and server PCM frames, exact configured host candidate, no duplicate data-channel microphone, mic off/reopen generations, reversible hold/recovery, pinned BMW cabin picture before answer audio, worker departure, desktop/phone player and saved visit. See `livekit-browser-results.json` for final counters and limits.
- Python/JavaScript syntax, vendor content hashes and all9 Mermaid source/viewer pairs checked. Git whitespace validation preserves upstream vendor CRLF bytes with `cr-at-eol`; the vendored SDK stays byte-identical to its recorded distribution. Optional environment `pip check` passes. [Twelve-category FMEA](FMEA.md) has no remaining P0/P1 in the scoped local trial; production/adoption gates remain open.

Counts overlap; they are not additive unique cases. Python unit/core tests use isolated DATA/GRAPH, blank provider keys, mocks and blocked sockets. Actual RTC requires local sockets: app/signaling are loopback, media UDP uses one validated machine-owned private IPv4 interface, with explicit local-only STUN and no TCP media. The browser blocks external HTTP/WebSocket traffic and substitutes the existing font stylesheet locally. Native RTC bypasses Python socket interception and is verified separately through actual selected candidates and listeners. No system-wide firewall claim is made.

## What real integration caught

1. Empty Python/server ICE settings inherited public STUN defaults, and RTC TCP ignored the loopback signaling bind. Explicit STUN and disabling TCP corrected both.
2. Native libwebrtc could not establish loopback-only media. Three real SDK probes failed before an explicit private host interface connected in0.259seconds with same-machine host candidates. That single join timing is not a latency improvement benchmark.
3. Cancelling a Python await did not cancel native join/disconnect. Capacity now remains reserved until native disposal completes; uncertainty cannot open unlimited extra connections.
4. The first reliable control could arrive before the Python SDK knew its participant. A strictly bound `trial.ready` handshake now precedes `session.start`; bounded readiness-only retries never replay a question. Real SDK and browser tests reproduced the failure and verified the correction.

Initial failed diagnostic captures are retained separately under local `output/playwright/livekit-trial/`; the final success receipt lists only its three successful screenshots. A test runner initially called one `.cjs` test as `.mjs`; its invocation-error log is retained, and the correct test passes. Raw SDK probes, private server configuration, tokens and unfiltered server logs are excluded from Git.

## Evidence and remaining limits

Source hashes, gate results, logs, compact native-browser case inventories with full local-receipt hashes, SDK/tool provenance, default/RTC screenshots and publication immutability checks accompany this receipt. The optional environment is separate from the ordinary app environment. Original BMW data, protected demo/port, default app and AWS are not trial storage or deployment targets.

Mock STT receives RTC frames but does not recognize a person's question. Type questions in mock mode. Physical speech/noise, provider latency, long live conversations, low-powered devices, Internet/TURN behavior and hosted capacity still need acceptance before promotion. The current SDK-only diagnostic process emitted an upstream native-handle warning at interpreter exit; the owned app's tested shutdown/startup logs did not show that warning. No acoustic, paid-call or AWS-readiness claim follows from these free tests.
