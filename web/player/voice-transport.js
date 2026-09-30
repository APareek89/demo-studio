// Both public playback and Rehearse use the server's transport selection.
// Selection happens before mounting; a failed join never replays a turn through
// another transport or opens a second microphone.
export async function resolveLiveClientFactory(bundle, {
  search = globalThis.location?.search || "",
  loadCapability,
  loadLiveKit = () => import("/web/player/livekit-voice.js"),
  timeoutMs = 6000,
} = {}) {
  if (bundle.example?.cached_only) return undefined;
  const override = new URLSearchParams(search).get("voice_transport");
  if (!(bundle.runtime?.version >= 1)) {
    if (override === "livekit") throw new Error("This publication does not support live conversation. Open its standard demo link or publish an updated demo.");
    return undefined;
  }
  if (override === "websocket") return undefined;
  const bounded = async (load, message) => {
    let timer;
    try {
      return await Promise.race([
        Promise.resolve().then(load),
        new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), timeoutMs); }),
      ]);
    } finally { clearTimeout(timer); }
  };
  let transport = override;
  if (transport !== "livekit") {
    const capability = await bounded(loadCapability, "Live connection settings timed out. Retry to open the demo.");
    transport = capability?.transport;
    if (!["livekit", "websocket"].includes(transport)) throw new Error("Live connection settings are unavailable. Retry to open the demo.");
  }
  if (transport === "websocket") return undefined;
  // A configured but unavailable LiveKit server stays selected. The existing
  // player can show slides and its normal retry/text guidance on join failure.
  const { LiveKitVoiceClient } = await bounded(loadLiveKit, "Live connection took too long to load. Retry to open the demo.");
  return options => new LiveKitVoiceClient({ ...options, demoVersion: bundle.version,
    knowledgeSnapshotId: bundle.knowledge_snapshot_id || bundle.runtime?.knowledge_snapshot_id });
}
