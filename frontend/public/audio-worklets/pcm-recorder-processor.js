/**
 * AudioWorkletProcessor for capturing microphone PCM data.
 * Collects incoming Float32 samples and posts them to the main thread.
 */
class PCMRecorderProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    // Gemini Live recommends 100 ms input chunks. At the requested 16 kHz
    // context rate this is 1,600 mono samples (3,200 bytes after PCM16 conversion).
    this.chunk = new Float32Array(1600);
    this.chunkOffset = 0;
  }

  process(inputs) {
    if (inputs.length > 0 && inputs[0].length > 0) {
      // Use the first channel (mono)
      const inputChannel = inputs[0][0];
      if (inputChannel && inputChannel.length > 0) {
        let inputOffset = 0;
        while (inputOffset < inputChannel.length) {
          const copyLength = Math.min(
            inputChannel.length - inputOffset,
            this.chunk.length - this.chunkOffset
          );
          this.chunk.set(
            inputChannel.subarray(inputOffset, inputOffset + copyLength),
            this.chunkOffset
          );
          inputOffset += copyLength;
          this.chunkOffset += copyLength;

          if (this.chunkOffset === this.chunk.length) {
            this.port.postMessage(this.chunk, [this.chunk.buffer]);
            this.chunk = new Float32Array(1600);
            this.chunkOffset = 0;
          }
        }
      }
    }
    return true;
  }
}

registerProcessor("pcm-recorder-processor", PCMRecorderProcessor);
