// Opt-in transport adapter. The existing client remains the sole owner of
// qualification, speech holds, turn cancellation and streamed audio playback.
import { LiveVoiceClient } from "/web/player/live-voice.js";
import * as LiveKit from "/web/vendor/livekit-client-2.22.3.esm.mjs";

export const LIVEKIT_TOPIC = "demo.runtime.v1";
const PART_BYTES = 8000, MAX_PARTS = 128, MAX_BYTES = PART_BYTES * MAX_PARTS;
const WIRE_BYTES = 12288, MAX_INFLIGHT = 4, FRAGMENT_TTL = 10000;
const encoder = new TextEncoder(), decoder = new TextDecoder("utf-8", { fatal: true });
const failure = message => new Error(`LiveKit trial: ${message}`);
const expired = () => failure("connection ended; retry the microphone or remove voice_transport=livekit from the URL");
const wait = (promise, ms, message) => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(failure(message)), ms);
  promise.then(value => { clearTimeout(timer); resolve(value); }, error => { clearTimeout(timer); reject(error); });
});
function base64(bytes) { let raw = ""; for (const byte of bytes) raw += String.fromCharCode(byte); return btoa(raw); }
function unbase64(raw) {
  if (typeof raw !== "string" || !raw.length || raw.length > 10668 || !/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(raw)) throw failure("invalid data fragment");
  const bytes = Uint8Array.from(atob(raw), value => value.charCodeAt(0));
  if (bytes.length > PART_BYTES || base64(bytes) !== raw) throw failure("invalid data fragment");
  return bytes;
}
export function fragmentMessage(raw, id) {
  const bytes = encoder.encode(raw);
  if (!bytes.length || bytes.length > MAX_BYTES || !/^[A-Za-z0-9_-]{1,80}$/.test(id)) throw failure("message exceeds the trial limit");
  const parts = Math.ceil(bytes.length / PART_BYTES), packets = [];
  for (let part = 0; part < parts; part++) packets.push(encoder.encode(JSON.stringify({ v: 1, id, part, parts, payload: base64(bytes.subarray(part * PART_BYTES, (part + 1) * PART_BYTES)) })));
  return packets;
}

export class FragmentReader {
  constructor({ onMessage, onFailure, now = Date.now }) { Object.assign(this, { onMessage, onFailure, now }); this.pending = new Map(); this.completed = new Map(); }
  add(packet) {
    if (!(packet instanceof Uint8Array) || packet.byteLength > WIRE_BYTES) throw failure("invalid data packet");
    const frame = JSON.parse(decoder.decode(packet));
    if (!frame || frame.v !== 1 || !/^[A-Za-z0-9_-]{1,80}$/.test(frame.id) || !Number.isInteger(frame.part) || !Number.isInteger(frame.parts) || frame.parts < 1 || frame.parts > MAX_PARTS || frame.part < 0 || frame.part >= frame.parts) throw failure("invalid data fragment");
    for (const [id, at] of this.completed) if (this.now() - at >= FRAGMENT_TTL) this.completed.delete(id);
    if (this.completed.has(frame.id)) return;
    const bytes = unbase64(frame.payload);
    let owner = this.pending.get(frame.id);
    if (!owner) {
      if (frame.part !== 0 || this.pending.size >= MAX_INFLIGHT) throw failure("out-of-order or excessive data fragments");
      owner = { parts: frame.parts, chunks: [], bytes: 0, started: this.now() };
      owner.timer = setTimeout(() => this.onFailure(failure("incomplete data message timed out")), FRAGMENT_TTL);
      this.pending.set(frame.id, owner);
    }
    if (this.now() - owner.started >= FRAGMENT_TTL || owner.parts !== frame.parts || frame.part !== owner.chunks.length) throw failure("out-of-order or expired data fragments");
    owner.chunks.push(bytes); owner.bytes += bytes.length;
    if (owner.bytes > MAX_BYTES) throw failure("message exceeds the trial limit");
    if (owner.chunks.length !== owner.parts) return;
    clearTimeout(owner.timer); this.pending.delete(frame.id);
    const joined = new Uint8Array(owner.bytes); let offset = 0;
    for (const chunk of owner.chunks) { joined.set(chunk, offset); offset += chunk.length; }
    const raw = decoder.decode(joined); JSON.parse(raw);
    this.completed.set(frame.id, this.now());
    while (this.completed.size > 64) this.completed.delete(this.completed.keys().next().value);
    this.onMessage(raw);
  }
  close() { for (const owner of this.pending.values()) clearTimeout(owner.timer); this.pending.clear(); this.completed.clear(); }
}

// This facade deliberately closes on an RTC reconnect: reliable packets are
// not durable/replayable turns. An explicit retry creates a fresh room owner.
export class LiveKitSocket {
  constructor(url, { client, sdk = LiveKit, env = globalThis } = {}) {
    Object.assign(this, { client, sdk, env }); this.readyState = 0; this.bufferedAmount = 0; this.epoch = 1; this.queueCount = 0; this.chain = Promise.resolve(); this.messageId = 0;
    this.reader = new FragmentReader({ onMessage: raw => {
      const event = JSON.parse(raw);
      if (event.session_id && event.session_id !== this.client.sessionId) throw failure("another session received data");
      if (event.type === "trial.ready") {
        if (event.session_id !== this.client.sessionId) throw failure("unowned worker readiness");
        this.workerReady = true; this.readyResolve?.(); return;
      }
      if (this.readyState !== 1) throw failure("runtime data arrived before worker readiness");
      if (event.type === "trial.pong") { clearTimeout(this.pongDeadline); this.pongDeadline = null; return; }
      this.onmessage?.({ data: raw });
    }, onFailure: error => this.fail(error) });
    queueMicrotask(() => this.open(url).catch(error => this.fail(error)));
  }
  async open(rawUrl) {
    const epoch = this.epoch, endpoint = new URL(rawUrl, this.env.location?.href || "http://localhost/");
    endpoint.protocol = endpoint.protocol === "wss:" ? "https:" : endpoint.protocol === "ws:" ? "http:" : endpoint.protocol;
    endpoint.pathname += "kit/token"; endpoint.search = "";
    this.abort = new AbortController();
    const response = await wait(this.env.fetch(endpoint.href, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: this.client.sessionId }), signal: this.abort.signal }), 6000, "token request timed out");
    if (epoch !== this.epoch) throw expired();
    if (!response.ok) throw failure("trial is unavailable on this server; remove voice_transport=livekit from the URL to use the standard demo");
    const grant = await response.json();
    if (grant.transport !== "livekit-trial" || grant.session_id !== this.client.sessionId || typeof grant.token !== "string" || !grant.token || typeof grant.url !== "string" || !/^wss?:\/\//.test(grant.url) || !grant.agent_identity || !grant.identity || !grant.room) throw failure("invalid trial connection grant");
    if (epoch !== this.epoch) throw expired();
    this.agentIdentity = grant.agent_identity;
    const room = this.room = new this.sdk.Room({ adaptiveStream: false, dynacast: false, disconnectOnPageLeave: true });
    const events = this.sdk.RoomEvent;
    room.on(events.DataReceived, (packet, participant, kind, topic) => {
      if (epoch !== this.epoch || this.readyState === 3 || participant?.identity !== this.agentIdentity || topic !== LIVEKIT_TOPIC) return;
      try {
        if (kind !== (this.sdk.DataPacket_Kind?.RELIABLE ?? 0)) throw failure("unreliable runtime packet");
        this.reader.add(packet);
      } catch (error) { this.fail(error); }
    });
    room.on(events.Disconnected, () => this.fail(expired()));
    room.on(events.ParticipantDisconnected, participant => { if (participant.identity === this.agentIdentity) this.fail(failure("runtime worker disconnected; explicit retry is required")); });
    room.on(events.Reconnecting, () => this.fail(failure("connection interrupted; explicit retry is required")));
    if (events.SignalReconnecting) room.on(events.SignalReconnecting, () => this.fail(failure("connection interrupted; explicit retry is required")));
    // A media track from the worker must never create a second playback voice.
    // Output remains the existing owned PCM queue, received as reliable data.
    await room.connect(grant.url, grant.token, { autoSubscribe: false, rtcConfig: { iceServers: [] } });
    if (epoch !== this.epoch) { await room.disconnect(); throw expired(); }
    if (!room.remoteParticipants.has(this.agentIdentity)) {
      await wait(new Promise(resolve => {
        const connected = participant => { if (participant.identity === this.agentIdentity) { room.off(events.ParticipantConnected, connected); resolve(); } };
        room.on(events.ParticipantConnected, connected);
        if (room.remoteParticipants.has(this.agentIdentity)) connected({ identity: this.agentIdentity });
      }), 6000, "runtime worker did not join");
    }
    if (epoch !== this.epoch) throw expired();
    // A joined peer can send data before the Python SDK has delivered its
    // ParticipantConnected event. Wait for the worker's identity-bound ready
    // acknowledgement; never drop or replay session/turn controls to work
    // around that participant-visibility race.
    if (!this.workerReady) await wait(new Promise((resolve, reject) => { this.readyResolve = resolve; this.readyReject = reject; }), 6000, "runtime worker was not ready");
    this.readyResolve = this.readyReject = null;
    if (epoch !== this.epoch) throw expired();
    this.readyState = 1;
    this.ping = setInterval(() => this.pingWorker(), 20000);
    this.onopen?.();
  }
  pingWorker() {
    if (this.readyState !== 1 || this.pongDeadline) return;
    this.pongDeadline = setTimeout(() => this.fail(failure("runtime worker stopped responding; explicit retry is required")), 10000);
    this.send(JSON.stringify({ type: "trial.ping", session_id: this.client.sessionId }));
  }
  enqueue(operation, bytes = 0) {
    if (this.readyState !== 1) return Promise.reject(expired());
    if (++this.queueCount > 128 || this.bufferedAmount + bytes > MAX_BYTES) { this.queueCount--; this.fail(failure("send queue exceeded its limit")); return Promise.reject(expired()); }
    this.bufferedAmount += bytes; const epoch = this.epoch;
    const queued = this.chain.then(async () => { if (epoch !== this.epoch || this.readyState !== 1) throw expired(); return operation(epoch); });
    this.chain = queued.catch(error => this.fail(error)).finally(() => { this.bufferedAmount = Math.max(0, this.bufferedAmount - bytes); this.queueCount = Math.max(0, this.queueCount - 1); });
    return queued;
  }
  send(raw) {
    if (this.readyState !== 1) return;
    let packets;
    try { JSON.parse(raw); packets = fragmentMessage(raw, `m_${this.env.crypto?.randomUUID?.().replace(/-/g, "") || `${Date.now().toString(36)}_${++this.messageId}`}`); }
    catch (error) { this.fail(error); return; }
    this.enqueue(async epoch => {
      for (const packet of packets) {
        if (epoch !== this.epoch) throw expired();
        await wait(this.room.localParticipant.publishData(packet, { reliable: true, topic: LIVEKIT_TOPIC, destinationIdentities: [this.agentIdentity] }), 5000, "data publication timed out");
      }
    }, encoder.encode(raw).length).catch(() => {});
  }
  publishMicrophone(mediaTrack, generation, captureEpoch) {
    if (!mediaTrack || this.readyState !== 1) return;
    this.enqueue(async epoch => {
      const current = () => epoch === this.epoch && this.client.mic && this.client.captureEpoch === captureEpoch && this.client.inputGeneration === generation && mediaTrack.readyState !== "ended";
      if (!current()) return;
      const track = new this.sdk.LocalAudioTrack(mediaTrack, undefined, true);
      this.localTrack = track;
      await wait(this.room.localParticipant.publishTrack(track, { source: this.sdk.Track.Source.Microphone, name: `demo-mic-${generation}`, stopMicTrackOnMute: true }), 5000, "microphone publication timed out");
      if (!current()) { await this.room.localParticipant.unpublishTrack(track, false); if (this.localTrack === track) this.localTrack = null; }
    }).catch(() => {});
  }
  unpublishMicrophone() {
    const track = this.localTrack;
    if (!track || this.readyState !== 1) return;
    this.localTrack = null;
    this.enqueue(() => wait(this.room.localParticipant.unpublishTrack(track, false), 5000, "microphone release timed out")).catch(() => {});
  }
  fail(error) {
    if (this.readyState === 3) return;
    this.client.onError(error?.message?.startsWith("LiveKit trial:") ? error.message : "LiveKit trial connection failed. Remove voice_transport=livekit from the URL to use the standard demo.");
    this.onerror?.({ error }); this.close();
  }
  close() {
    if (this.readyState === 3) return;
    this.readyState = 3; this.epoch++; this.abort?.abort(); this.readyReject?.(expired()); this.readyResolve = this.readyReject = null; clearInterval(this.ping); clearTimeout(this.pongDeadline); this.pongDeadline = null; this.reader.close();
    this.localTrack = null;
    this.room?.disconnect(true).catch(() => {});
    this.onclose?.();
  }
}

export class LiveKitVoiceClient extends LiveVoiceClient {
  constructor(options, { sdk = LiveKit, env = options.env || globalThis } = {}) {
    let client;
    const transportEnv = { location: env.location, navigator: env.navigator, AudioContext: env.AudioContext, webkitAudioContext: env.webkitAudioContext, AudioWorkletNode: env.AudioWorkletNode, atob: env.atob?.bind(env), WebSocket: class { constructor(url) { return new LiveKitSocket(url, { client, sdk, env }); } } };
    super({ ...options, env: transportEnv, onError: message => options.onError?.(message.startsWith("LiveKit trial:") ? message : `LiveKit trial: ${message} Remove voice_transport=livekit from the URL to use the standard demo.`) }); client = this; this.transport = "livekit-trial";
  }
  send(type, data = {}) {
    // RTC is the only microphone uplink; the worklet still supplies immediate
    // local speech detection to the inherited reversible hold implementation.
    if (type === "audio.input") return;
    super.send(type, data);
    if (type === "mic.set") {
      if (data.enabled) this.socket?.publishMicrophone(this.stream?.getAudioTracks()[0], data.input_generation, this.captureEpoch);
      else this.socket?.unpublishMicrophone();
    }
  }
  stopCapture(notify = true) { const socket = this.socket; super.stopCapture(notify); socket?.unpublishMicrophone(); }
}
