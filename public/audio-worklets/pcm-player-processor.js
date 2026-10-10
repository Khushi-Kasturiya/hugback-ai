/**
 * AudioWorkletProcessor for low-latency PCM audio playback.
 * Maintains a circular ring buffer and provides instant interruption flushing.
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    // 24kHz sample rate * 60 seconds buffer
    this.bufferSize = 24000 * 60;
    this.buffer = new Float32Array(this.bufferSize);
    this.writeIndex = 0;
    this.readIndex = 0;

    this.port.onmessage = (event) => {
      // 1. Barge-in / Interruption flush command
      if (event.data && event.data.command === "endOfAudio") {
        this.readIndex = this.writeIndex; // Instantly purge the ring buffer
        return;
      }

      // 2. Incoming PCM Int16 samples (ArrayBuffer)
      if (event.data) {
        const int16Samples = new Int16Array(event.data);
        this._enqueue(int16Samples);
      }
    };
  }

  _enqueue(int16Samples) {
    for (let i = 0; i < int16Samples.length; i++) {
      // Normalize 16-bit signed integer [-32768, 32767] to float [-1.0, 1.0]
      const floatVal = int16Samples[i] / 32768.0;

      this.buffer[this.writeIndex] = floatVal;
      this.writeIndex = (this.writeIndex + 1) % this.bufferSize;

      // Handle buffer overflow: advance read pointer
      if (this.writeIndex === this.readIndex) {
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }
  }

  process(inputs, outputs, parameters) {
    const output = outputs[0];
    if (!output || output.length === 0) return true;

    const framesPerBlock = output[0].length;

    for (let frame = 0; frame < framesPerBlock; frame++) {
      const sample = this.buffer[this.readIndex];

      // Fill left and right channels
      output[0][frame] = sample;
      if (output.length > 1) {
        output[1][frame] = sample;
      }

      // Advance read pointer if data is available
      if (this.readIndex !== this.writeIndex) {
        this.readIndex = (this.readIndex + 1) % this.bufferSize;
      }
    }

    return true;
  }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
