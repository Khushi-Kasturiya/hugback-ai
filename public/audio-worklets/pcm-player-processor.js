/**
 * Bounded PCM16 ring buffer with phrase-start cues from the render thread.
 * A render cue is not proof of physical speaker output or of anyone hearing it.
 */
class PCMPlayerProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    this.bufferSize = 24000 * 60;
    this.buffer = new Float32Array(this.bufferSize);
    this.readFrame = 0;
    this.writeFrame = 0;
    this.markers = [];
    this.generation = 0;
    this.lastId = 0;
    this.active = false;

    this.port.onmessage = ({ data }) => {
      if (data.command === "endOfAudio") {
        this.generation = data.generation;
        this.readFrame = this.writeFrame = 0;
        this.markers = [];
        this.active = false;
        return;
      }
      if (data.command !== "enqueue" || data.generation !== this.generation) return;
      const samples = new Int16Array(data.pcm);
      if (!samples.length) return;
      // Fail instead of silently discarding audio and revealing the wrong cue.
      if (this.writeFrame - this.readFrame + samples.length > this.bufferSize || this.markers.length >= 4096) {
        this.readFrame = this.writeFrame;
        this.markers = [];
        this.active = false;
        this.port.postMessage({ type: "playbackError", generation: this.generation });
        return;
      }
      this.markers.push({ frame: this.writeFrame, id: data.id });
      this.lastId = data.id;
      this.active = true;
      for (const sample of samples) {
        this.buffer[this.writeFrame++ % this.bufferSize] = sample / 32768;
      }
    };
  }

  process(inputs, outputs) {
    const output = outputs[0];
    if (!output || !output.length) return true;
    for (let frame = 0; frame < output[0].length; frame++) {
      let sample = 0; // Underflow/flush must be silence, not a stale ring sample.
      if (this.readFrame < this.writeFrame) {
        while (this.markers.length && this.markers[0].frame === this.readFrame) {
          const marker = this.markers.shift();
          this.port.postMessage({ type: "chunkStarted", id: marker.id, generation: this.generation });
        }
        sample = this.buffer[this.readFrame++ % this.bufferSize];
      }
      for (const channel of output) channel[frame] = sample;
    }
    if (this.active && this.readFrame === this.writeFrame) {
      this.active = false;
      this.port.postMessage({ type: "drained", throughId: this.lastId, generation: this.generation });
    }
    return true;
  }
}

registerProcessor("pcm-player-processor", PCMPlayerProcessor);
