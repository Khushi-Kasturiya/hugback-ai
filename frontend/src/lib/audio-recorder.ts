/**
 * Audio Recorder Worklet management.
 * Captures microphone input at 16kHz and converts to 16-bit PCM.
 */

export interface RecorderHandle {
  node: AudioWorkletNode;
  context: AudioContext;
  stream: MediaStream;
  stop: () => void;
}

export async function startAudioRecorder(
  onPcmChunk: (pcm16Buffer: ArrayBuffer) => void
): Promise<RecorderHandle> {
  const context = new AudioContext({ sampleRate: 16000 });
  if (context.state === "suspended") {
    await context.resume();
  }

  await context.audioWorklet.addModule("/audio-worklets/pcm-recorder-processor.js");

  const stream = await navigator.mediaDevices.getUserMedia({
    audio: {
      channelCount: 1,
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true,
    },
  });

  const source = context.createMediaStreamSource(stream);
  const node = new AudioWorkletNode(context, "pcm-recorder-processor", {
    numberOfInputs: 1,
    numberOfOutputs: 1,
    outputChannelCount: [1],
  });
  const silentSink = context.createGain();
  silentSink.gain.value = 0;

  // AudioWorklets are pull-driven. Chrome can stop calling process() when a
  // node is not connected to an output, which silently prevents microphone
  // frames from reaching the WebSocket. Keep the graph active through a
  // muted gain node so captured audio is never played through the speakers.
  source.connect(node).connect(silentSink).connect(context.destination);

  node.port.onmessage = (event: MessageEvent<Float32Array>) => {
    const float32Data = event.data;
    const pcm16 = convertFloat32ToPCM16(float32Data);
    onPcmChunk(pcm16);
  };

  const stop = () => {
    try {
      stream.getTracks().forEach((track) => track.stop());
      node.disconnect();
      silentSink.disconnect();
      source.disconnect();
      if (context.state !== "closed") {
        context.close();
      }
    } catch (err) {
      console.warn("Error stopping audio recorder:", err);
    }
  };

  return { node, context, stream, stop };
}

function convertFloat32ToPCM16(input: Float32Array): ArrayBuffer {
  const pcm16 = new Int16Array(input.length);
  for (let i = 0; i < input.length; i++) {
    const sample = Math.max(-1, Math.min(1, input[i]));
    pcm16[i] = sample < 0 ? sample * 32768 : sample * 32767;
  }
  return pcm16.buffer;
}
