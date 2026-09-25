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
          let energy = 0, mean = 0, crossings = 0, peak = 0;
          for (let i = 0; i < this.packet.length; i++) {
            const sample = this.packet[i] / 32768;
            energy += sample ** 2; mean += sample; peak = Math.max(peak, Math.abs(sample));
            if (i && (this.packet[i] >= 0) !== (this.packet[i - 1] >= 0)) crossings++;
          }
          const rms = Math.sqrt(energy / this.packet.length);
          // A bounded voiced-sound estimate, not speaker recognition. Sustained
          // speech needs both energy and structure; a loud click/DC level alone
          // cannot claim an interruption. Semantic STT still owns actual turns.
          let periodicity = 0;
          if (rms > .008 && Math.abs(mean / this.packet.length) < rms * .65) {
            for (let lag = 32; lag <= 160; lag += 4) {
              let product = 0, left = 0, right = 0;
              for (let i = lag; i < this.packet.length; i++) {
                const a = this.packet[i], b = this.packet[i - lag];
                product += a * b; left += a * a; right += b * b;
              }
              periodicity = Math.max(periodicity, product / Math.sqrt(left * right || 1));
            }
          }
          const speechLike = periodicity > .55 && crossings >= 3 && crossings <= 82 && peak / Math.max(rms, .001) < 5;
          this.port.postMessage({ pcm: this.packet.buffer, rms, speechLike }, [this.packet.buffer]);
          this.packet = new Int16Array(320); this.at = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("demo-capture", DemoCapture);
