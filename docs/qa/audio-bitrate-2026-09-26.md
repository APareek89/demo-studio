# Sarvam bitrate comparison — 26 September 2026

The existing stream adapter now explicitly sends `output_audio_bitrate: "128k"`, Sarvam's documented default. It retains `output_audio_codec: "linear16"`, mono PCM16 at24000Hz and the existing browser decoder. This is an explicit default, not a claimed quality upgrade. Recorded BMW narration remains lossless mono PCM16 WAV at22050Hz. No production release or regeneration is part of this local comparison.

Provider references: [bitrate configuration](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/how-to/set-bitrate-for-output), [WebSocket configuration](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/streaming-api/web-socket). Canonical spelling is lowercase128k. The ordinary REST conversion endpoint does not need this streaming setting.

## Evidence

- Required gates: deck445/445, acceptance24/24, smoke3/3.
- Sarvam streaming19/19 checks the exact outbound bitrate value and unchanged PCM bytes on completion and cancellation. Speech style30/30 and runtime delivery27/27 remain green.
- Six isolated suites use MOCK_LLM=1, temporary DATA/GRAPH, blank credentials, cloud off and blocked sockets; zero outbound attempts. Protocol fixtures fake the provider connection while exercising the real request-building branch. Logs: `output/audio-bitrate-20260926-qa/`.
- The listening comparison uses14 published BMW main/closing clips, encoded locally as128kbps MP3 from their original WAV files. Speaker, performance, words, pace and volume are preserved; no new Sarvam synthesis or paid call. Conversion43/43 verifies no missing clips,128kbps encoding and decoded durations within1ms.
- Source bundle SHA256: `73d8bdf91a6d7af6c7d5fd61520f18d8102462912dbd4481b3a40eb010437c58`. It was read from the existing local app's public bundle/media endpoints; original demo files are not rewritten.
- Local comparison: `http://127.0.0.1:8935/`; assets/scripts/receipts live only under `output/audio-bitrate-20260926/`. Default clip is the exact side-profile narration, ride-proof-L1. This is a listening comparison, not a replacement runtime or a new published demo.
- Browser10/10 checks original/MP3 switching with retained playback position, muted continuous playback/advance/stop, closing and390px layout. The initial preview server lacked HTTP Range support, so switching could lose position; its local-only server now supports ranges and the corrected check passes. No production server was changed. Loopback listener PID80081 is retained for review.

## Scoped FMEA

Product/system context: existing interruptible, grounded demo and locked voice in PRD.md/docs/ARCHITECTURE_FLOW.md. Source change is one provider configuration field; no graph, storage, decoder, runtime flow or AWS infrastructure change.

Coverage12/12: unhandled errors and external dependency failures retain bounded provider error handling; races/state retain utterance cancellation; resources retain current buffers; security retains server-side keys and loopback-only preview; data integrity uses copied public audio and leaves original media unchanged; observability distinguishes transcoding from synthesis; scale adds no per-turn requests; billing performs no synthesis; retry/idempotency retains current ownership; configuration drift is covered by the mocked actual wire message; product edge cases preserve playback format, timing and voice.

No new blocking finding. The principal misuse risk is describing a lossy128kbps MP3 as an upgrade over uncompressed audio, or feeding MP3 bytes to the PCM player. Both are explicitly avoided. Mocked wire tests do not prove a new provider response, and codec/bitrate measurements do not establish subjective naturalness.
