// Continuous mono capture, resampled to 16 kHz PCM. No input is connected audibly.
class DemoCapture extends AudioWorkletProcessor {
  constructor() {
    super(); this.phase = 0; this.sum = 0; this.weight = 0; this.packet = new Int16Array(320); this.at = 0;
  }
  process(inputs) {
    const data = inputs[0]?.[0];
    if (!data) return true;
    const ratio = sampleRate / 16000;
    for (const value of data) {
      this.sum += value; this.weight++; this.phase++;
      if (this.phase >= ratio) {
        this.phase -= ratio;
        const v = Math.max(-1, Math.min(1, this.sum / this.weight));
        this.packet[this.at++] = Math.round(v < 0 ? v * 32768 : v * 32767);
        this.sum = 0; this.weight = 0;
        if (this.at === this.packet.length) {
          let energy = 0; for (const sample of this.packet) energy += (sample / 32768) ** 2;
          this.port.postMessage({ pcm: this.packet.buffer, rms: Math.sqrt(energy / this.packet.length) }, [this.packet.buffer]);
          this.packet = new Int16Array(320); this.at = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("demo-capture", DemoCapture);
