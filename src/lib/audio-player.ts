/**
 * Audio Player Worklet management.
 * Plays 24kHz PCM audio streams with instant barge-in flushing.
 */

export interface PlayerHandle {
  node: AudioWorkletNode;
  context: AudioContext;
  playPcm: (pcmData: ArrayBuffer) => void;
  flush: () => void;
  stop: () => void;
}

export async function startAudioPlayer(): Promise<PlayerHandle> {
  const context = new AudioContext({ sampleRate: 24000 });
  if (context.state === "suspended") {
    await context.resume();
  }

  await context.audioWorklet.addModule("/audio-worklets/pcm-player-processor.js");

  const node = new AudioWorkletNode(context, "pcm-player-processor");
  node.connect(context.destination);

  const playPcm = (pcmData: ArrayBuffer) => {
    node.port.postMessage(pcmData);
  };

  const flush = () => {
    node.port.postMessage({ command: "endOfAudio" });
  };

  const stop = () => {
    try {
      flush();
      node.disconnect();
      if (context.state !== "closed") {
        context.close();
      }
    } catch (err) {
      console.warn("Error stopping audio player:", err);
    }
  };

  return { node, context, playPcm, flush, stop };
}

/**
 * Utility to decode base64 audio payload to ArrayBuffer.
 */
export function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const cleanBase64 = base64.replace(/-/g, "+").replace(/_/g, "/");
  const binaryString = window.atob(cleanBase64);
  const len = binaryString.length;
  const bytes = new Uint8Array(len);
  for (let i = 0; i < len; i++) {
    bytes[i] = binaryString.charCodeAt(i);
  }
  return bytes.buffer;
}
