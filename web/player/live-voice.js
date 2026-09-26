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

// Early speech can pause output reversibly. Only a qualified final takes
// semantic ownership of a turn; a discarded sound resumes the same audio.
export function meaningfulTranscript(text) {
  // Providers can describe a sound instead of leaving the transcript empty.
  // Remove only known sound annotations, retaining any real words around them.
  const words = String(text || "").replace(/[\[<(]\s*(?:background\s+(?:noise|sound)|noise|silence|music|laughter|laughing|cough(?:ing|s)?|breathing|(?:clear(?:s|ing)?[\s-]+(?:the[\s-]+)?throat)|(?:throat[\s-]+clear(?:ing)?)|inaudible|unintelligible|unk)\s*[\])>]/gi, "");
  const value = words.toLowerCase().replace(/[’]/g, "'").replace(/\s+/g, " ").replace(/^[\s\p{P}]+|[\s\p{P}]+$/gu, "");
  if (!/[\p{L}\p{N}]/u.test(value)) return false;
  // A question mark supplied by STT does not turn an ahem into a question.
  // This is deliberately a small list of sounds, not a minimum word count:
  // short controls, feature questions and supported languages must still work.
  const sounds = value.split(/[\s\p{P}]+/u).filter(Boolean);
  if (sounds.length && sounds.every(word => /^(?:ahem+|ah+|uh+|um+|hm+|mm+|erm+|er+|eh+)$/.test(word))) return false;
  if (/^(?:clear(?:s|ing)?[\s-]+(?:the[\s-]+)?throat|throat[\s-]+clear(?:ing)?|cough(?:ing|s)?)$/.test(value)) return false;
  return !/^(?:i|i'm|i am|it's|it is|it|the|a|an|and|but|so|you|you know|this|that|there|there's|well)$/.test(value);
}

export class LiveVoiceClient {
  constructor({ url, sessionId, language = "en-IN", qualifyInput = meaningfulTranscript, shouldInterrupt = () => true, canHold = () => true, onSpeechHold = () => {}, onSpeechHoldEnd = () => {}, onSpeechStart = () => {}, onTranscript = () => {}, onState = () => {}, onError = () => {}, env = globalThis }) {
    Object.assign(this, { url, sessionId, language, qualifyInput, shouldInterrupt, canHold, onSpeechHold, onSpeechHoldEnd, onSpeechStart, onTranscript, onState, onError, env });
    this.socket = null; this.ready = false; this.closed = false; this.connecting = null; this.turn = 0; this.turnId = "t_0";
    this.pending = null; this.delivery = null; this.inputMode = "text"; this.mic = false; this.captureEpoch = 0; this.captureStarting = null;
    this.speechActive = false; this.seenInputs = new Set(); this.inputGeneration = 0; this.muted = false; this.generation = 0; this.audioEpoch = 0;
  }
  send(type, data = {}) { if (this.socket?.readyState === 1) this.socket.send(JSON.stringify({ type, session_id: this.sessionId, turn_id: this.turnId, ...data })); }
  connect() {
    if (this.ready) return Promise.resolve();
    if (this.connecting) return this.connecting;
    this.closed = false;
    let connectingSocket;
    const raw = new Promise((resolve, reject) => {
      const url = new URL(this.url, this.env.location?.href || "http://localhost/"); url.protocol = url.protocol === "https:" ? "wss:" : url.protocol === "http:" ? "ws:" : url.protocol;
      url.searchParams.set("session_id", this.sessionId);
      const socket = new this.env.WebSocket(url.href); this.socket = connectingSocket = socket;
      socket.onopen = () => { if (this.socket === socket) this.send("session.start", { language: this.language, mic: false, input_mode: this.inputMode }); };
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
        const error = new Error("Live connection closed");
        this.ready = false; this.connecting = null; reject(error);
        // A broken transport is a delivery failure, not a customer cancellation.
        // Reject owned speech so its readable fallback can finish the same turn.
        // Explicit interruption/end already invalidates its owner and resolves false.
        this.audioEpoch++; this.failPending(error); this.finishAudio(false, error); this.stopCapture(false);
        if (!this.closed) { this.onState("unavailable"); this.onError("Connection lost. Type your reply, or tap the microphone to reconnect."); }
      };
    });
    this.connecting = deadline(raw, this.connectTimeoutMs || 8000, "Live connection timed out").catch(error => {
      if (this.socket === connectingSocket) { this.socket = null; this.ready = false; this.connecting = null; }
      connectingSocket?.close(); throw error;
    });
    return this.connecting;
  }
  // Text mode retains the live socket for streamed speech without opening a device.
  async setMicEnabled(enabled) {
    if (enabled) return this.startCapture();
    const wasReady = this.ready;
    this.stopCapture();
    const epoch = this.captureEpoch;
    await this.connect();
    if (!wasReady && epoch === this.captureEpoch && !this.closed && !this.mic) {
      this.send("mic.set", { enabled: false, input_generation: this.inputGeneration, input_mode: "text" });
    }
    return true;
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
      context = new Context(); this.captureSetupContext = context;
      // WebKit can leave resume pending when playback is blocked/interrupted.
      // Bound setup before device permission and retain ownership for mic-off.
      await deadline(context.resume(), 4000, "Audio could not start. Tap the microphone to retry");
      if (epoch !== this.captureEpoch || this.closed) { await context.close(); return false; }
      if (context.state !== "running") throw new Error("Audio is paused by this browser. Tap the microphone to retry");
      const permission = this.env.navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      // A late permission grant after timeout/stop must release the device immediately.
      permission.then(value => { if (epoch !== this.captureEpoch) value.getTracks().forEach(track => track.stop()); }, () => {});
      stream = await deadline(permission, 8000, "Microphone permission timed out");
      if (epoch !== this.captureEpoch || this.closed) { stream.getTracks().forEach(track => track.stop()); await context.close(); return false; }
      await this.connect();
      if (epoch !== this.captureEpoch || this.closed) { stream.getTracks().forEach(track => track.stop()); await context.close(); return false; }
      await deadline(context.audioWorklet.addModule("/web/player/voice-worklet.js"), 4000, "Microphone initialization timed out");
      if (epoch !== this.captureEpoch) { stream.getTracks().forEach(track => track.stop()); await context.close(); return false; }
      this.captureContext = context; this.captureSetupContext = null; this.stream = stream; this.input = context.createMediaStreamSource(stream);
      this.worklet = new this.env.AudioWorkletNode(context, "demo-capture"); this.silent = context.createGain(); this.silent.gain.value = 0;
      this.input.connect(this.worklet); this.worklet.connect(this.silent); this.silent.connect(context.destination);
      this.inputMode = "voice"; this.mic = true; this.micReady = false; this.preRoll = []; this.speechActive = false; this.speechCandidateAt = null; this.seenInputs.clear(); this.inputGeneration++; this.loudFrames = 0; this.quietFrames = 0; this.noise = 0.003; this.speechFrames = []; this.localOnsetArmed = true; this.holdBlockedUntil = 0;
      this.send("mic.set", { enabled: true, input_generation: this.inputGeneration, input_mode: "voice" });
      this.micReadyTimer = setTimeout(() => { if (this.mic && !this.micReady && epoch === this.captureEpoch) { this.stopCapture(); this.onError("Voice input did not connect. Type below or tap the mic to retry."); } }, 9000);
      this.worklet.port.onmessage = ({ data }) => {
        if (!this.mic || epoch !== this.captureEpoch) return;
        if (!this.ready || this.socket.bufferedAmount > 256000) { this.stopCapture(); this.onError("Listening connection is slow. Type your reply or tap the mic to reconnect."); return; }
        const threshold = Math.max(0.018, this.noise * 3.5);
        if (data.rms > threshold) { this.loudFrames++; this.quietFrames = 0; this.lastSpeechAt = Date.now(); } else { this.loudFrames = 0; this.quietFrames++; this.noise = this.noise * 0.98 + Math.min(data.rms, 0.02) * 0.02; }
        if (this.loudFrames === 1 && !this.speechActive) this.speechCandidateAt = Date.now();
        this.observeSpeechFrame(data, threshold);
        const frame = { audio: encodePCM(data.pcm), sample_rate: 16000, input_generation: this.inputGeneration };
        if (this.micReady) this.send("audio.input", frame);
        else if (this.preRoll.length < 400) this.preRoll.push(frame);
        else { this.stopCapture(); this.onError("Voice input took too long to connect. Please retry or type your answer."); }
      };
      for (const track of stream.getAudioTracks()) track.onended = () => { if (this.mic && epoch === this.captureEpoch) { this.stopCapture(); this.onError("Microphone disconnected. Type your reply or reconnect it and tap the mic."); } };
      return true;
    } catch (error) {
      if (epoch === this.captureEpoch) { this.captureEpoch++; this.inputMode = "text"; this.mic = false; this.onState("unavailable"); this.onError(error.name === "NotAllowedError" ? "Microphone permission was not granted. Type below, or allow access and tap the mic." : `${error.message}. You can type below.`); }
      stream?.getTracks().forEach(track => track.stop()); if (context && context.state !== "closed") await context.close().catch(() => {});
      return false;
    } finally {
      if (this.captureSetupContext === context) this.captureSetupContext = null;
    }
  }
  stopCapture(notify = true) {
    this.endSpeechHold(this.closed ? "closed" : "microphone_off", !this.closed);
    this.captureEpoch++; this.captureStarting = null; this.mic = false; this.micReady = false; this.preRoll = []; this.speechActive = false; this.speechCandidateAt = null; clearTimeout(this.micReadyTimer);
    if (notify || !this.closed) this.inputMode = "text";
    if (notify) this.send("mic.set", { enabled: false, input_generation: this.inputGeneration, input_mode: "text" });
    if (this.worklet) this.worklet.port.onmessage = null;
    for (const node of [this.input, this.worklet, this.silent]) { try { node?.disconnect(); } catch {} }
    this.stream?.getTracks().forEach(track => track.stop()); this.stream = null;
    this.captureSetupContext?.close().catch(() => {}); this.captureSetupContext = null;
    this.captureContext?.close().catch(() => {}); this.captureContext = null;
    if (!this.closed) this.onState("muted");
  }
  speechStart(event) {
    if (!this.mic || this.speechActive) return;
    this.speechActive = true;
    if (!event.preserve_endpoint) { this.voiceEnded = null; this.endpointAt = null; this.serverEndpointAt = null; this.endpointBasis = null; }
    this.speechStartedAt = this.speechCandidateAt || event.detected_at || Date.now();
    const provisional = this.inputHold;
    this.endSpeechHold("confirmed", false);
    this.cancelAudio(); // local stop precedes server cancellation and application work
    this.onSpeechStart({ ...event, provisional_detected_at: provisional?.detected_at, provisional_source: provisional?.source });
  }
  observeSpeechFrame(data, threshold) {
    this.speechFrames ||= [];
    this.speechFrames.push(data.rms > threshold && data.speechLike === true);
    if (this.speechFrames.length > 10) this.speechFrames.shift();
    if (!this.speechFrames.some(Boolean)) this.localOnsetArmed = true;
    // Eight voiced 20ms frames reject brief bumps/clears. This may still pause
    // for sustained background speech; it cannot establish who is speaking.
    if ((this.inputHold || this.localOnsetArmed) && this.speechFrames.filter(Boolean).length >= 8) this.holdSpeech({ source: "local_speech", detected_at: Date.now() });
  }
  holdSpeech(event) {
    if (!this.mic || this.speechActive || !this.canHold() || Date.now() < (this.holdBlockedUntil || 0)) return;
    let hold = this.inputHold;
    if (!hold) {
      hold = this.inputHold = { ...event, startedAt: Date.now() };
      this.localOnsetArmed = false;
      this.speechStartedAt = this.speechCandidateAt || event.detected_at || hold.startedAt;
      // Gain drops synchronously, before the audio context suspension promise.
      if (this.gain) this.gain.gain.value = 0;
      this.outputContext?.suspend?.().catch(() => {});
      if (this.delivery) { clearTimeout(this.delivery.timer); clearTimeout(this.delivery.startTimer); }
      this.onSpeechHold(event);
      hold.limit = setTimeout(() => this.endSpeechHold("deadline"), 20000);
    }
    // Recognized progress means a real question can take longer than20s.
    // Repeated unchanged partials and raw background energy cannot renew this
    // watchdog forever. No completion/final means no semantic question yet.
    if (event.source === "partial" && event.text !== hold.partialText) {
      hold.partialText = event.text; clearTimeout(hold.limit);
      hold.limit = setTimeout(() => this.endSpeechHold("deadline"), 20000);
    }
    clearTimeout(hold.timer);
    hold.timer = setTimeout(() => this.endSpeechHold("silence"), hold.partialText !== undefined ? 2400 : 1400);
  }
  endSpeechHold(reason, resume = true) {
    const hold = this.inputHold; if (!hold) return;
    this.inputHold = null; clearTimeout(hold.timer); clearTimeout(hold.limit); this.speechFrames = [];
    if (reason === "deadline") this.holdBlockedUntil = Date.now() + 2000;
    this.onSpeechHoldEnd({ reason, resume, detected_at: hold.detected_at });
    if (resume && !this.closed) this.resumeOutput();
  }
  resumeOutput() {
    const context = this.outputContext, active = this.delivery;
    if (context && context.state !== "closed") deadline(context.resume(), 4000, "Audio could not resume. Tap to retry").then(() => {
      if (this.outputContext !== context || this.closed) return;
      if (this.inputHold) { context.suspend?.().catch(() => {}); return; }
      if (context.state !== "running") throw new Error("Audio is paused by this browser");
      if (this.gain) this.gain.gain.value = this.muted ? 0 : 1;
      if (this.delivery) { this.armAudioDeadline(this.delivery); this.armAudioStart(this.delivery); }
    }).catch(error => {
      if (this.outputContext === context && !this.closed && !this.inputHold && active && this.delivery === active) this.finishAudio(false, error);
    });
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
    if (data.type === "input.speech_start") { if (!this.speechActive) this.speechCandidateAt = Date.now(); return; }
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
      if (final) {
        const key = data.input_id !== undefined || data.seq !== undefined ? `${this.inputGeneration}:${data.input_id ?? data.seq}` : null;
        // Without a provider identity, repeated wording can be a real new turn.
        // Do not permanently dedupe a customer's second "yes" or repeated question.
        if (key && this.seenInputs.has(key)) return;
        if (key) this.seenInputs.add(key); if (this.seenInputs.size > 256) this.seenInputs.delete(this.seenInputs.values().next().value);
      }
      const meaningful = meaningfulTranscript(data.text) && (!final || this.qualifyInput(data.text));
      if (!final && meaningful && this.qualifyInput(data.text) && this.shouldInterrupt(data.text)) this.holdSpeech({ source: "partial", text: String(data.text).trim().toLowerCase(), detected_at: Date.now() });
      if (meaningful && final && this.shouldInterrupt(data.text)) this.speechStart({ source: "final", detected_at: Date.now(), preserve_endpoint: true });
      else if (final) this.endSpeechHold(meaningful ? "control" : "rejected");
      if (final) { this.speechActive = false; this.loudFrames = 0; this.speechCandidateAt = null; }
      if (!meaningful) {
        if (final) { this.voiceEnded = null; this.endpointAt = null; this.serverEndpointAt = null; this.endpointBasis = null; }
        return;
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
    this.endSpeechHold("superseded", false);
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
      this.delivery = { utteranceId: id, turnId: owner, sequence: -1, sources: new Set(), nextAt: this.outputContext.currentTime + 0.025, ended: false, started: false, resolve, reject, onStart };
      this.armAudioDeadline(this.delivery);
      this.send(utteranceId ? "delivery.request" : "delivery.speak", { turn_id: owner, utterance_id: id, ...(utteranceId ? {} : { text }) });
    });
  }
  async unlockOutput() {
    if (this.closed) throw abortError();
    const Context = this.env.AudioContext || this.env.webkitAudioContext;
    if (!this.outputContext || this.outputContext.state === "closed") { this.outputContext = new Context(); this.gain = this.outputContext.createGain(); this.gain.connect(this.outputContext.destination); }
    const context = this.outputContext;
    this.gain.gain.value = this.muted || this.inputHold ? 0 : 1;
    if (this.inputHold) await context.suspend?.(); else {
      await deadline(context.resume(), 4000, "Audio could not start. Tap to retry");
      if (this.closed || this.outputContext !== context) throw abortError();
      if (this.inputHold) { this.gain.gain.value = 0; await context.suspend?.(); }
      else if (context.state !== "running") throw new Error("Audio is paused by this browser. Tap to retry");
    }
  }
  armAudioDeadline(active) {
    clearTimeout(active.timer);
    if (this.inputHold) return;
    // Healthy queued speech may exceed thirty seconds. Bound inactivity after
    // its scheduled audio drains, instead of truncating the whole utterance.
    const buffered = Math.max(0, active.nextAt - this.outputContext.currentTime) * 1000;
    active.timer = setTimeout(() => {
      if (this.delivery === active) this.finishAudio(false, new Error("Speech stream timed out"));
    }, 30000 + buffered);
  }
  queueAudio(data, active) {
    if (data.format && data.format !== "pcm_s16le" && data.format !== "linear16") throw new Error("Unsupported streamed audio format");
    const sampleRate = Number(data.sample_rate || 24000); if (![8000, 16000, 22050, 24000].includes(sampleRate)) throw new Error("Unsupported audio rate");
    const samples = pcmToFloat(data.audio, this.env.atob?.bind(this.env) || atob), ctx = this.outputContext;
    const buffer = ctx.createBuffer(1, samples.length, sampleRate); buffer.copyToChannel(samples, 0);
    const source = ctx.createBufferSource(); source.buffer = buffer; source.connect(this.gain);
    const at = Math.max(ctx.currentTime + 0.01, active.nextAt); active.nextAt = at + buffer.duration; active.sources.add(source);
    this.armAudioDeadline(active);
    source.onended = () => { source.disconnect(); active.sources.delete(source); if (this.delivery === active && active.ended && !active.sources.size) this.finishAudio(true); };
    source.start(at);
    if (!active.started) {
      active.started = true; this.send("delivery.start", { turn_id: active.turnId, utterance_id: active.utteranceId });
      active.startAt = at; this.armAudioStart(active);
    }
  }
  armAudioStart(active) {
    if (this.inputHold || active.startNotified || !active.started) return;
    clearTimeout(active.startTimer);
    active.startTimer = setTimeout(() => { if (this.delivery === active && !this.inputHold && !active.startNotified) { active.startNotified = true; active.onStart(Date.now()); } }, Math.max(0, (active.startAt - this.outputContext.currentTime) * 1000));
  }
  finishAudio(completed, error) {
    const active = this.delivery; if (!active) return;
    this.delivery = null; clearTimeout(active.timer); clearTimeout(active.startTimer);
    for (const source of active.sources) { source.onended = null; try { source.stop(); source.disconnect(); } catch {} }
    active.sources.clear(); this.send("delivery.end", { turn_id: active.turnId, utterance_id: active.utteranceId, completed });
    if (error) { error.audioStarted = active.started; active.reject(error); } else active.resolve(completed);
  }
  cancelAudio() { this.audioEpoch++; if (this.delivery) this.send("delivery.cancel", { turn_id: this.delivery.turnId, utterance_id: this.delivery.utteranceId }); this.finishAudio(false); }
  setMuted(muted) { this.muted = muted; if (this.gain) this.gain.gain.value = muted || this.inputHold ? 0 : 1; }
  close() {
    this.closed = true; this.stopCapture(false); this.interrupt(); this.send("session.end"); this.socket?.close(); this.socket = null; this.ready = false; this.connecting = null;
    this.outputContext?.close().catch(() => {}); this.outputContext = null;
  }
}
