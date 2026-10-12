// Talk mode's microphone: turns the browser's audio (any sample rate, 32-bit float) into 16 kHz
// 16-bit PCM, the Live API's input format, and posts it to the page in 100 ms pieces.
// A file of its own because the page's content policy allows scripts from this site only.
"use strict";

const RATE = 16000;
const PIECE = RATE / 10; // samples in 100 ms

class MicPcm extends AudioWorkletProcessor {
  constructor() {
    super();
    this.step = sampleRate / RATE; // input samples per output sample (e.g. 3 at 48 kHz)
    this.position = 0;
    this.sum = 0;
    this.count = 0;
    this.piece = new Int16Array(PIECE);
    this.filled = 0;
  }

  process(inputs) {
    const channel = inputs[0] && inputs[0][0];
    if (!channel) return true;
    for (const sample of channel) {
      // Each output sample is the average of the input samples it covers: a cheap low-pass
      // filter, so downsampling doesn't fold high pitches into noise.
      this.sum += sample;
      this.count += 1;
      this.position += 1;
      if (this.position < this.step) continue;
      this.position -= this.step;
      const value = Math.max(-1, Math.min(1, this.sum / this.count));
      this.piece[this.filled++] = value < 0 ? value * 0x8000 : value * 0x7fff;
      this.sum = 0;
      this.count = 0;
      if (this.filled === PIECE) {
        this.port.postMessage(this.piece.buffer, [this.piece.buffer]);
        this.piece = new Int16Array(PIECE);
        this.filled = 0;
      }
    }
    return true;
  }
}

registerProcessor("mic-pcm", MicPcm);
