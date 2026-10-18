/**
 * Audio Player Worklet management.
 * Plays 24kHz PCM audio streams with instant barge-in flushing.
 */

export interface PlayerHandle {
  node: AudioWorkletNode;
  context: AudioContext;
  playPcm: (pcmData: ArrayBuffer, onStart?: () => void) => void;
  isBusy: () => boolean;
  flush: () => void;
  stop: () => void;
}

export async function startAudioPlayer(options: {
  onPlaybackChange?: (playing: boolean) => void;
  onError?: () => void;
} = {}): Promise<PlayerHandle> {
  const context = new AudioContext({ sampleRate: 24000 });
  if (context.state === "suspended") {
    await context.resume();
  }

  await context.audioWorklet.addModule("/audio-worklets/pcm-player-processor.js?v=2");

  const node = new AudioWorkletNode(context, "pcm-player-processor");
  node.connect(context.destination);

  let generation = 0;
  let nextId = 0;
  let lastQueuedId = 0;
  let busy = false;
  let playing = false;
  let stopped = false;
  const callbacks = new Map<number, () => void>();
  node.port.onmessage = ({ data }) => {
    if (stopped || data.generation !== generation) return;
    if (data.type === "chunkStarted") {
      if (!playing) {
        playing = true;
        options.onPlaybackChange?.(true);
      }
      const onStart = callbacks.get(data.id);
      callbacks.delete(data.id);
      onStart?.();
    } else if (data.type === "drained" && data.throughId === lastQueuedId) {
      busy = false;
      playing = false;
      options.onPlaybackChange?.(false);
    } else if (data.type === "playbackError") {
      flush();
      options.onError?.();
    }
  };
  node.onprocessorerror = () => {
    if (!stopped) {
      flush();
      options.onError?.();
    }
  };

  const playPcm = (pcmData: ArrayBuffer, onStart?: () => void) => {
    if (stopped || !pcmData.byteLength) return;
    if (pcmData.byteLength % 2) throw new Error("Invalid PCM16 audio");
    const id = ++nextId;
    lastQueuedId = id;
    busy = true;
    if (onStart) callbacks.set(id, onStart);
    node.port.postMessage({ command: "enqueue", pcm: pcmData, id, generation }, [pcmData]);
  };

  const flush = () => {
    generation++;
    callbacks.clear();
    busy = false;
    playing = false;
    node.port.postMessage({ command: "endOfAudio", generation });
    if (!stopped) options.onPlaybackChange?.(false);
  };

  const stop = () => {
    if (stopped) return;
    stopped = true;
    try {
      flush();
      node.port.onmessage = null;
      node.onprocessorerror = null;
      node.disconnect();
      if (context.state !== "closed") {
        context.close();
      }
    } catch (err) {
      console.warn("Error stopping audio player:", err);
    }
  };

  return { node, context, playPcm, isBusy: () => busy, flush, stop };
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
