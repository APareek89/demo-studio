# LiveKit input and continuous gallery review — 25 September 2026

The reported typed question reached the mock graph; mocked recognition, short mock audio and a muted review URL caused the unusable experience. The requested local review now explicitly uses configured live STT/answer/TTS providers and a URL without `mute=1`. No unproven transport rewrite was made. Consecutive uses of one photograph retain its settled frame and update reviewed tags, without another gallery entrance, no-op camera movement or brightness pulse.

## Application and review boundaries

- Working branch `codex/sales-trainer-flow`, based on`97ef2ab`; no master merge, GitHub push, AWS deployment, rebuild or original source edit.
- App8920 uses `/tmp/demo-livekit-live-20260925`, its own BMW copy/data/graph, customer-tier configured runtime order and Sarvam speech. Initial mock visits remain in the prior trial directory. Original publication181/181 baseline hashes unchanged; normal app8910 and protected demo/port untouched.
- Gallery code is confined to`web/player/walkthrough.js`. Loaded/settled immediately previous photos may hand off framing. Different photos still enter; new reviewed features may refocus. Native hero/text boundaries, two-image ownership, image-before-speech and cancellation stay intact. No navbar/bottom-panel, script/audio, graph, prompt or evidence changes.

## Verification

Final frozen source passes **qa_deck445/445, qa_accept24/24, smoke3/3, full mock28/28**. Isolated DATA/GRAPH, cloud off, mocked providers, blank keys and blocked outbound sockets: zero attempts. The release journey measures194.22seconds of synthetic audio, not a regenerated BMW.

New gallery continuity**28/28** includes actual BMW desktop1440/phone390, exact image bounds, animation/opacity checks, changed feature versus changed photo, two-picture mapping and pause/question/return/Stop ownership. Baseline97ef2ab fails four of the original26 checks. Existing gallery**320/320**, current native**87/87**, fallback**18/18**, image loading**14/14**. Historicaleacbb57native85/87 is not the current result.

Actual real-RTC mock browser**28/28** now exercises the stock application route, typed intake and the exact reported question, delivered speech and saved answer. Backend**50/50**, client**47/47**, launcher**16/16**; existing voice**96/96**, hold**26/26**, listening**16/16**, recovery**17/17**, session saves**18/18**. Three input-free real-room joins pass without provider usage. Counts overlap; see`gate-counts.json` and individual receipts.

Two bounded real-provider queries cost an app-estimated **$0.024371 /₹2.0471**. Prerecorded speech transcribed exactly and received an honest evidence-limited decline with4.096s non-silent PCM. The exact typed interior question passes**6/6** withF011/F014/F015, an associated console image,22.828s non-silent PCM and a completed incremental visit. [Detailed provider report and original failures](provider/PROVIDER-QA.md). The initial speech harness incorrectly required seven seats; its original failure remains, and that aborted voice visit saved only its question checkpoint. It is not a completed-voice-session pass. No repeat paid question was issued to turn that assertion green.

[Independent FMEA](FMEA.md) covers all12 categories and reproduced/fixed one P1: parent crossfade brightened identical-photo pixels. RGB now remains[102,140,142] before/during/after; no confirmed actionable visual defect remains. Python/JS syntax, whitespace and all9 Mermaid source/viewer pairs pass.

## Retained failures and limits

The first provider harness omitted local signaling HTTP validation; a second zero-cost join timed out without enough diagnostics to establish why. Five later joins succeeded. A free-gate wrapper initially passed its suite argument to unittest and then blocked an intentional loopback DNS check; both invocation failures and the corrected launcher16/16 are retained. No production provider/protocol behavior was changed to mask those tests.

Mock RTC and prerecorded real STT are distinct evidence. Physical microphone permissions, throat/TV/room noise, long sessions, low-power devices, Internet/TURN, network handover and hosted capacity still require acceptance before LiveKit adoption. Output still uses owned PCM over reliable data rather than RTP. This local fix is not an AWS rollout or a claim that every connection will succeed.
