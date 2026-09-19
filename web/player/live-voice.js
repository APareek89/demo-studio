// Session-scoped transport. Capture survives delivery cancellation; media never advances a server clock.
const abortError = () => Object.assign(new Error("Turn superseded"), { name: "AbortError" });
const deadline = (promise, ms, message) => new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error(message)), ms);
  promise.then(value => { clearTimeout(timer); resolve(value); }, error => { clearTimeout(timer); reject(error); });
});
export function pcmToFloat(audio, decode = atob) {
  const bytes = decode(audio);
  if (!bytes.length || bytes.length % 2) throw new Error("Invalid PCM16 audio");
  const out = new Float32Array(bytes.length / 2);
  for (let i = 0; i < out.length; i++) { let sample = bytes.charCodeAt(i * 2) | bytes.charCodeAt(i * 2 + 1) << 8; if (sample >= 32768) sample -= 65536; out[i] = sample / 32768; }
  return out;
}
function encodePCM(buffer) { const bytes = new Uint8Array(buffer); let binary = ""; for (const byte of bytes) binary += String.fromCharCode(byte); return btoa(binary); }

export class LiveVoiceClient {
  constructor({ url, sessionId, language = "en-IN", onSpeechStart = () => {}, onTranscript = () => {}, onState = () => {}, onError = () => {}, env = globalThis }) {
    Object.assign(this, { url, sessionId, language, onSpeechStart, onTranscript, onState, onError, env });
    this.socket = null; this.ready = false; this.closed = false; this.connecting = null; this.turn = 0; this.turnId = "t_0";
    this.pending = null; this.delivery = null; this.mic = false; this.captureEpoch = 0; this.captureStarting = null;
    this.speechActive = false; this.seenInputs = new Set(); this.inputGeneration = 0; this.muted = false; this.generation = 0; this.audioEpoch = 0;
  }
  send(type, data = {}) { if (this.socket?.readyState === 1) this.socket.send(JSON.stringify({ type, session_id: this.sessionId, turn_id: this.turnId, ...data })); }
  connect() {
    if (this.ready) return Promise.resolve();
    if (this.connecting) return this.connecting;
    this.closed = false;
    const raw = new Promise((resolve, reject) => {
      const url = new URL(this.url, this.env.location?.href || "http://localhost/"); url.protocol = url.protocol === "https:" ? "wss:" : url.protocol === "http:" ? "ws:" : url.protocol;
      url.searchParams.set("session_id", this.sessionId);
      const socket = new this.env.WebSocket(url.href); this.socket = socket;
      socket.onopen = () => { if (this.socket === socket) this.send("session.start", { language: this.language, mic: false }); };
      socket.onmessage = event => {
        if (this.socket !== socket) return;
        let data; try { data = JSON.parse(event.data); } catch { return; }
        if (data.session_id && data.session_id !== this.sessionId) return;
        if (data.type === "session.ready") { this.ready = true; resolve(); return; }
        this.receive(data);
      };
      socket.onerror = () => reject(new Error("Live connection unavailable"));
      socket.onclose = () => {
        if (this.socket !== socket) return;
        this.ready = false; this.connecting = null; reject(new Error("Live connection closed"));
        this.failPending(new Error("Live connection closed")); this.cancelAudio(); this.stopCapture(false);
        if (!this.closed) { this.onState("unavailable"); this.onError("Connection lost. Type your reply, or tap the microphone to reconnect."); }
      };
    });
    this.connecting = deadline(raw, 8000, "Live connection timed out").catch(error => { const socket = this.socket; this.socket = null; this.ready = false; this.connecting = null; socket?.close(); throw error; });
    return this.connecting;
  }
  async startCapture() {
    if (this.mic) return true;
    if (this.captureStarting) return this.captureStarting;
    const epoch = ++this.captureEpoch;
    this.onState("opening");
    const opening = this.openCapture(epoch);
    this.captureStarting = opening;
    try { return await opening; } finally { if (this.captureStarting === opening) this.captureStarting = null; }
  }
  async openCapture(epoch) {
    let stream, context;
    try {
      const Context = this.env.AudioContext || this.env.webkitAudioContext;
      if (!Context || !this.env.navigator?.mediaDevices?.getUserMedia) throw new Error("Microphone capture is unavailable in this browser");
      context = new Context(); await context.resume();
      const permission = this.env.navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      // A late permission grant after timeout/stop must release the device immediately.
      permission.then(value => { if (epoch !== this.captureEpoch) value.getTracks().forEach(track => track.stop()); }, () => {});
      stream = await deadline(permission, 8000, "Microphone permission timed out");
      await this.connect();
      if (epoch !== this.captureEpoch || this.closed) { stream.getTracks().forEach(track => track.stop()); await context.close(); return false; }
      await deadline(context.audioWorklet.addModule("/web/player/voice-worklet.js"), 4000, "Microphone initialization timed out");
      if (epoch !== this.captureEpoch) { stream.getTracks().forEach(track => track.stop()); await context.close(); return false; }
      this.captureContext = context; this.stream = stream; this.input = context.createMediaStreamSource(stream);
      this.worklet = new this.env.AudioWorkletNode(context, "demo-capture"); this.silent = context.createGain(); this.silent.gain.value = 0;
      this.input.connect(this.worklet); this.worklet.connect(this.silent); this.silent.connect(context.destination);
      this.mic = true; this.micReady = false; this.preRoll = []; this.speechActive = false; this.seenInputs.clear(); this.inputGeneration++; this.loudFrames = 0; this.quietFrames = 0; this.noise = 0.003;
      this.send("mic.set", { enabled: true, input_generation: this.inputGeneration });
      this.micReadyTimer = setTimeout(() => { if (this.mic && !this.micReady && epoch === this.captureEpoch) { this.stopCapture(); this.onError("Voice input did not connect. Type below or tap the mic to retry."); } }, 9000);
      this.worklet.port.onmessage = ({ data }) => {
        if (!this.mic || epoch !== this.captureEpoch) return;
        if (!this.ready || this.socket.bufferedAmount > 256000) { this.stopCapture(); this.onError("Listening connection is slow. Type your reply or tap the mic to reconnect."); return; }
        const threshold = Math.max(0.018, this.noise * 3.5);
        if (data.rms > threshold) { this.loudFrames++; this.quietFrames = 0; this.lastSpeechAt = Date.now(); } else { this.loudFrames = 0; this.quietFrames++; this.noise = this.noise * 0.98 + Math.min(data.rms, 0.02) * 0.02; }
        if (this.loudFrames >= 4) this.speechStart({ source: "local", detected_at: Date.now() });
        const frame = { audio: encodePCM(data.pcm), sample_rate: 16000, input_generation: this.inputGeneration };
        if (this.micReady) this.send("audio.input", frame);
        else if (this.preRoll.length < 400) this.preRoll.push(frame);
        else { this.stopCapture(); this.onError("Voice input took too long to connect. Please retry or type your answer."); }
      };
      for (const track of stream.getAudioTracks()) track.onended = () => { if (this.mic && epoch === this.captureEpoch) { this.stopCapture(); this.onError("Microphone disconnected. Type your reply or reconnect it and tap the mic."); } };
      return true;
    } catch (error) {
      if (epoch === this.captureEpoch) { this.captureEpoch++; this.mic = false; this.onState("unavailable"); this.onError(error.name === "NotAllowedError" ? "Microphone permission was not granted. Type below, or allow access and tap the mic." : `${error.message}. You can type below.`); }
      stream?.getTracks().forEach(track => track.stop()); if (context && context.state !== "closed") await context.close().catch(() => {});
      return false;
    }
  }
  stopCapture(notify = true) {
    this.captureEpoch++; this.captureStarting = null; this.mic = false; this.micReady = false; this.preRoll = []; this.speechActive = false; clearTimeout(this.micReadyTimer);
    if (notify) this.send("mic.set", { enabled: false, input_generation: this.inputGeneration });
    if (this.worklet) this.worklet.port.onmessage = null;
    for (const node of [this.input, this.worklet, this.silent]) { try { node?.disconnect(); } catch {} }
    this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
    this.captureContext?.close().catch(() => {}); this.captureContext = null;
    this.onState("muted");
  }
  speechStart(event) {
    if (!this.mic || this.speechActive) return;
    this.speechActive = true; this.voiceEnded = null; this.endpointAt = null; this.serverEndpointAt = null; this.endpointBasis = null; this.speechStartedAt = event.detected_at || Date.now();
    this.cancelAudio(); // local stop precedes server cancellation and application work
    this.onSpeechStart(event);
  }
  receive(data) {
    // Turn IDs own answers; a separate generation owns each microphone capture.
    // A delayed final/ready/error from before mute must not affect a reopened mic.
    const inputEvent = data.type === "mic.ready" || data.type?.startsWith("input.") || data.type?.startsWith("transcript.") || (data.type === "error" && ["microphone_unavailable", "microphone_stream"].includes(data.code));
    if (inputEvent && (!this.mic || data.input_generation !== this.inputGeneration)) return;
    if (data.type === "mic.ready") {
      if (!this.mic) return;
      this.micReady = true; clearTimeout(this.micReadyTimer);
      for (const frame of this.preRoll || []) this.send("audio.input", frame);
      this.preRoll = []; this.onState("listening"); return;
    }
    if (data.type === "input.speech_start") { this.speechStart({ ...data, source: "provider", detected_at: Date.now() }); return; }
    if (data.type === "input.speech_end") {
      this.endpointAt = Date.now();
      this.serverEndpointAt = data.voice_ended || null;
      const localEnd = this.lastSpeechAt >= this.speechStartedAt && this.endpointAt - this.lastSpeechAt < 2500;
      // Playback is timed on the browser clock. The server receipt is useful
      // provenance, but cannot be subtracted from a browser wall clock.
      this.voiceEnded = localEnd ? this.lastSpeechAt : this.endpointAt;
      this.endpointBasis = localEnd ? "local_vad_estimate" : "browser_endpoint_receipt"; return;
    }
    if (data.type === "transcript.partial" || data.type === "transcript.final") {
      if (!this.mic) return;
      const final = data.type === "transcript.final";
      if (!final && data.text) this.speechStart({ source: "partial", detected_at: Date.now() });
      if (final) {
        const key = data.input_id !== undefined || data.seq !== undefined ? `${this.inputGeneration}:${data.input_id ?? data.seq}` : null;
        // Without a provider identity, repeated wording can be a real new turn.
        // Do not permanently dedupe a customer's second "yes" or repeated question.
        if (key && this.seenInputs.has(key)) return;
        if (key) this.seenInputs.add(key); if (this.seenInputs.size > 256) this.seenInputs.delete(this.seenInputs.values().next().value);
        this.speechActive = false; this.loudFrames = 0;
      }
      this.onTranscript({ ...data, final, voice_ended: this.voiceEnded || Date.now(), endpoint_received_at: this.endpointAt, server_endpoint_received_at: this.serverEndpointAt, speech_end_basis: this.endpointBasis || "browser_transcript_receipt", stt_done: Date.now() });
      if (final) { this.voiceEnded = null; this.endpointAt = null; this.serverEndpointAt = null; this.endpointBasis = null; }
      return;
    }
    if (data.type === "turn.result" && data.turn_id === this.pending?.turnId) {
      const pending = this.pending; this.pending = null; clearTimeout(pending.timer);
      pending.resolve({ ...data.answer, runtime_utterance_id: data.utterance_id || data.answer?.runtime_utterance_id, runtime_turn_id: data.turn_id }); return;
    }
    const active = this.delivery;
    if (data.type === "error") {
      if (data.is_fatal || ["microphone_unavailable", "microphone_stream"].includes(data.code)) { this.stopCapture(); this.onError(data.message || "Voice input disconnected. Type below or tap the microphone to retry."); return; }
      if (data.turn_id && data.turn_id !== this.turnId) return;
      const error = new Error(data.message || "Live voice is unavailable");
      if (data.utterance_id && active?.utteranceId === data.utterance_id) this.finishAudio(false, error);
      else if (this.pending) this.failPending(error);
      else this.onError(error.message);
      return;
    }
    if (!active || data.turn_id !== active.turnId || data.utterance_id !== active.utteranceId) return;
    if (data.type === "audio.chunk") {
      const seq = data.seq ?? data.sequence;
      if (!Number.isInteger(seq) || seq <= active.sequence) return;
      active.sequence = seq;
      try { this.queueAudio(data, active); } catch (error) { this.finishAudio(false, error); }
    } else if (data.type === "audio.end") { active.ended = true; if (!active.sources.size) this.finishAudio(true); }
  }
  failPending(error) { if (this.pending) { const pending = this.pending; this.pending = null; clearTimeout(pending.timer); pending.reject(error); } }
  interrupt({ preservePlanning = false } = {}) {
    this.generation++; this.cancelAudio(); this.failPending(abortError()); this.turnId = `t_${++this.turn}`; this.send("turn.interrupt", { preserve_planning: !!preservePlanning });
  }
  async ask(payload) {
    const generation = this.generation; await this.connect(); if (generation !== this.generation || this.closed) throw abortError(); this.failPending(abortError());
    const turnId = this.turnId = `t_${++this.turn}`;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { if (this.pending?.turnId !== turnId) return; this.send("turn.interrupt", { turn_id: turnId }); this.failPending(new Error("Answer timed out")); }, 16000);
      this.pending = { turnId, resolve, reject, timer }; this.send("turn.ask", { ...payload, turn_id: turnId });
    });
  }
  async speak(text, { utteranceId, turnId, onStart = () => {} } = {}) {
    const generation = this.generation; this.cancelAudio(); const audioEpoch = this.audioEpoch;
    await this.connect(); if (generation !== this.generation || audioEpoch !== this.audioEpoch || this.closed) throw abortError();
    await this.unlockOutput(); if (generation !== this.generation || audioEpoch !== this.audioEpoch || this.closed) throw abortError();
    const id = utteranceId || `u_${Date.now().toString(36)}_${++this.turn}`;
    const owner = turnId || this.turnId;
    return new Promise((resolve, reject) => {
      this.delivery = { utteranceId: id, turnId: owner, sequence: -1, sources: new Set(), nextAt: this.outputContext.currentTime + 0.025, ended: false, started: false, resolve, reject, onStart,
        timer: setTimeout(() => this.finishAudio(false, new Error("Speech stream timed out")), 30000) };
      this.send(utteranceId ? "delivery.request" : "delivery.speak", { turn_id: owner, utterance_id: id, ...(utteranceId ? {} : { text }) });
    });
  }
  async unlockOutput() {
    const Context = this.env.AudioContext || this.env.webkitAudioContext;
    if (!this.outputContext || this.outputContext.state === "closed") { this.outputContext = new Context(); this.gain = this.outputContext.createGain(); this.gain.connect(this.outputContext.destination); }
    this.gain.gain.value = this.muted ? 0 : 1; await this.outputContext.resume();
  }
  queueAudio(data, active) {
    if (data.format && data.format !== "pcm_s16le" && data.format !== "linear16") throw new Error("Unsupported streamed audio format");
    const sampleRate = Number(data.sample_rate || 24000); if (![8000, 16000, 22050, 24000].includes(sampleRate)) throw new Error("Unsupported audio rate");
    const samples = pcmToFloat(data.audio, this.env.atob?.bind(this.env) || atob), ctx = this.outputContext;
    const buffer = ctx.createBuffer(1, samples.length, sampleRate); buffer.copyToChannel(samples, 0);
    const source = ctx.createBufferSource(); source.buffer = buffer; source.connect(this.gain);
    const at = Math.max(ctx.currentTime + 0.01, active.nextAt); active.nextAt = at + buffer.duration; active.sources.add(source);
    source.onended = () => { source.disconnect(); active.sources.delete(source); if (this.delivery === active && active.ended && !active.sources.size) this.finishAudio(true); };
    source.start(at);
    if (!active.started) {
      active.started = true; this.send("delivery.start", { turn_id: active.turnId, utterance_id: active.utteranceId });
      active.startTimer = setTimeout(() => { if (this.delivery === active) active.onStart(Date.now()); }, Math.max(0, (at - ctx.currentTime) * 1000));
    }
  }
  finishAudio(completed, error) {
    const active = this.delivery; if (!active) return;
    this.delivery = null; clearTimeout(active.timer); clearTimeout(active.startTimer);
    for (const source of active.sources) { source.onended = null; try { source.stop(); source.disconnect(); } catch {} }
    active.sources.clear(); this.send("delivery.end", { turn_id: active.turnId, utterance_id: active.utteranceId, completed });
    if (error) { error.audioStarted = active.started; active.reject(error); } else active.resolve(completed);
  }
  cancelAudio() { this.audioEpoch++; if (this.delivery) this.send("delivery.cancel", { turn_id: this.delivery.turnId, utterance_id: this.delivery.utteranceId }); this.finishAudio(false); }
  setMuted(muted) { this.muted = muted; if (this.gain) this.gain.gain.value = muted ? 0 : 1; }
  close() {
    this.closed = true; this.stopCapture(); this.interrupt(); this.send("session.end"); this.socket?.close(); this.socket = null; this.ready = false; this.connecting = null;
    this.outputContext?.close().catch(() => {}); this.outputContext = null;
  }
}
