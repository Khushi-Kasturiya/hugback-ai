"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { startAudioRecorder, RecorderHandle } from "@/lib/audio-recorder";
import { startAudioPlayer, PlayerHandle, base64ToArrayBuffer } from "@/lib/audio-player";
import { getAuthenticationMessage } from "@/lib/identity";
import { getInlineVoicePayload } from "@/lib/voice-profile";
import { portalGet, PortalStatus } from "@/lib/portal-api";
import { selectedVoicePayload } from "@/lib/voice-api";
import { demoRequest, recipientCallPayload } from "@/lib/demo-api";

const CONNECTION_TIMEOUT_MS = 20_000;
const SPEECH_THRESHOLD = 0.05;
const END_OF_SPEECH_SILENCE_MS = 700;

function defaultWebSocketUrl(): string {
  if (process.env.NEXT_PUBLIC_HUGBACK_WS_URL) {
    return process.env.NEXT_PUBLIC_HUGBACK_WS_URL;
  }
  if (typeof window === "undefined") {
    return "ws://localhost:8000/ws";
  }

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.hostname}:8000/ws`;
}

export type CallStatus =
  | "disconnected"
  | "connecting"
  | "connected"
  | "listening"
  | "speaking"
  | "interrupted"
  | "error";

interface UseLiveAudioOptions {
  wsUrl?: string;
  demoParent?: boolean;
  recipientId?: string;
  workflowAcknowledged?: boolean;
  onTranscriptionUpdate?: (role: "user" | "hugback", text: string) => void;
}

export function useLiveAudio({
  wsUrl = defaultWebSocketUrl(),
  demoParent = false,
  recipientId,
  workflowAcknowledged = false,
  onTranscriptionUpdate,
}: UseLiveAudioOptions = {}) {
  const [status, setStatus] = useState<CallStatus>("disconnected");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [userTranscript, setUserTranscript] = useState<string>("");
  const [hugbackTranscript, setHugbackTranscript] = useState<string>("");
  const [userVolume, setUserVolume] = useState<number>(0);
  const [hugbackVolume, setHugbackVolume] = useState<number>(0);
  const [callInfo, setCallInfo] = useState<{ sessionId: string; memoryStatus: string; parentId?: string; recipientLabel?: string; voice?: string }>();

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const isAgentSpeakingRef = useRef<boolean>(false);
  const intentionalCloseRef = useRef<boolean>(false);
  const callAttemptRef = useRef(0);
  const userSpeechActiveRef = useRef<boolean>(false);
  const silenceStartedAtRef = useRef<number | null>(null);

  const releaseCallResources = useCallback((closeSocket: boolean) => {
    callAttemptRef.current++;
    const ws = wsRef.current;
    wsRef.current = null;

    if (closeSocket && ws) {
      try {
        ws.close();
      } catch (e) {
        console.warn("Error closing WebSocket:", e);
      }
    }

    if (recorderRef.current) {
      recorderRef.current.stop();
      recorderRef.current = null;
    }

    if (playerRef.current) {
      playerRef.current.stop();
      playerRef.current = null;
    }

    isAgentSpeakingRef.current = false;
    userSpeechActiveRef.current = false;
    silenceStartedAtRef.current = null;
    setUserVolume(0);
    setHugbackVolume(0);
  }, []);

  const endCall = useCallback(() => {
    intentionalCloseRef.current = true;
    releaseCallResources(true);
    setErrorMessage(null);
    setStatus("disconnected");
  }, [releaseCallResources]);

  useEffect(() => {
    // URL/back navigation must not relabel a running call or keep the previous
    // recipient's subtitles visible under the new identity.
    intentionalCloseRef.current = true;
    releaseCallResources(true);
    setStatus("disconnected");
    setCallInfo(undefined);
    setUserTranscript("");
    setHugbackTranscript("");
    setErrorMessage(null);
  }, [recipientId, demoParent, releaseCallResources]);

  const startCall = useCallback(async () => {
    if (status === "connecting" || status === "connected" || status === "speaking" || status === "listening") {
      return;
    }

    setErrorMessage(null);
    setStatus("connecting");
    intentionalCloseRef.current = false;
    const attempt = ++callAttemptRef.current;
    const isCurrentAttempt = () => callAttemptRef.current === attempt && !intentionalCloseRef.current;

    try {
      const [identityMessage, portalStatus] = await Promise.all([
        getAuthenticationMessage(),
        portalGet<PortalStatus>("/status"),
      ]);
      if (!isCurrentAttempt()) return;
      if (demoParent && (!portalStatus.localDemoEnabled || portalStatus.voice.mode !== "preset")) {
        throw new Error("Parent demo calls require local demo mode and preset or portal-enrolled TTS voice.");
      }
      if (demoParent && !recipientId) throw new Error("Choose the recipient for this demo call first.");
      if (demoParent && portalStatus.workflowEnabled && !workflowAcknowledged) {
        throw new Error("Acknowledge synthetic Planner and Critic processing before calling.");
      }
      const selectedVoice = demoParent
        ? recipientCallPayload(await demoRequest("/family"), recipientId, portalStatus.voice)
        : selectedVoicePayload(portalStatus.voice);
      if (!isCurrentAttempt()) return;
      // Never upload saved recordings into an ordinary preset call.
      const voicePayload = portalStatus.voice.mode === "experimental-inline"
        ? await getInlineVoicePayload()
        : null;
      if (!isCurrentAttempt()) return;
      if (portalStatus.voice.mode === "experimental-inline" && !voicePayload) {
        throw new Error("Experimental mode requires local voice and consent recordings. Open the child portal to prepare them.");
      }
      const authenticationMessage = {
        ...identityMessage,
        ...(voicePayload || {}),
        ...selectedVoice,
        ...(demoParent && portalStatus.workflowEnabled && workflowAcknowledged ? { simulateWorkflowConsent: true } : {}),
      };
      setCallInfo(undefined);
      setUserTranscript("");
      setHugbackTranscript("");

      // 1. Initialize Player first
      const player = await startAudioPlayer({
        onPlaybackChange: (playing) => {
          if (!isCurrentAttempt()) return;
          isAgentSpeakingRef.current = playing;
          setHugbackVolume(playing ? 0.8 : 0);
          setStatus(playing ? "speaking" : "listening");
        },
        onError: () => {
          if (!isCurrentAttempt()) return;
          setErrorMessage("Audio playback failed. Please start a new call.");
          setStatus("error");
          releaseCallResources(true);
        },
      });
      if (!isCurrentAttempt()) { player.stop(); return; }
      playerRef.current = player;

      // 2. Initialize WebSocket
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        if (!isCurrentAttempt() || wsRef.current !== ws) return;
        try {
          const adkEvent = JSON.parse(event.data);

          // Handle reconnection signal
          if (adkEvent.type === "reconnecting") {
            setStatus("connecting");
            return;
          }

          if (adkEvent.type === "ready") {
            setCallInfo({ sessionId: adkEvent.sessionId, memoryStatus: adkEvent.memoryStatus, parentId: adkEvent.demo?.parentId,
              recipientLabel: adkEvent.demo?.recipientLabel,
              voice: adkEvent.voice === "replicated" ? "Custom AI voice · Google TTS" : adkEvent.voiceName || adkEvent.voice });
            return;
          }

          if (adkEvent.type === "error") {
            setErrorMessage(adkEvent.message || "Backend error");
            setStatus("error");
            releaseCallResources(true);
            return;
          }

          // Your own transcription remains immediate, independent of TTS.
          if (adkEvent.inputTranscription?.text) {
            const text = adkEvent.inputTranscription.text;
            setUserTranscript((prev) => (prev ? `${prev} ${text}` : text));
            onTranscriptionUpdate?.("user", text);
          }

          // Interruption wins over audio/text bundled in the same event.
          if (adkEvent.interrupted) {
            playerRef.current?.flush();
            isAgentSpeakingRef.current = false;
            setHugbackVolume(0);
            setStatus("listening");
            return;
          }

          const outputText = adkEvent.outputTranscription?.text;
          const playbackAligned = adkEvent.outputTranscription?.playbackAligned === true;
          const publishTranscript = () => {
            if (!outputText || !isCurrentAttempt() || wsRef.current !== ws) return;
            setHugbackTranscript((prev) => (prev ? `${prev} ${outputText}` : outputText));
            onTranscriptionUpdate?.("hugback", outputText);
          };
          let onAudioStart = playbackAligned && outputText ? publishTranscript : undefined;

          // A replicated phrase travels with its first PCM chunk, but stays
          // hidden until that chunk reaches the player's render thread.
          if (adkEvent.content && adkEvent.content.parts) {
            for (const part of adkEvent.content.parts) {
              if (
                part.inlineData &&
                part.inlineData.mimeType &&
                part.inlineData.mimeType.startsWith("audio/pcm") &&
                playerRef.current
              ) {
                const audioBuffer = base64ToArrayBuffer(part.inlineData.data);
                if (audioBuffer.byteLength) {
                  playerRef.current.playPcm(audioBuffer, onAudioStart);
                  onAudioStart = undefined;
                }
              }
            }
          }

          // Preset Live transcription has no replicated-TTS delay.
          if (outputText && !playbackAligned) publishTranscript();

          // Handle turn completion
          if (adkEvent.turnComplete && !playerRef.current?.isBusy()) {
            isAgentSpeakingRef.current = false;
            setHugbackVolume(0);
            setStatus("listening");
          }

        } catch (err) {
          // Do not leave queued subtitles/audio alive after a malformed packet.
          console.warn("[Hugback] Invalid playback event; stopping call.");
          setErrorMessage("The audio response could not be played. Please start a new call.");
          setStatus("error");
          releaseCallResources(true);
        }
      };

      // The broker accepts the browser socket before it connects to Gemini.
      // Wait for its explicit ready event so the UI cannot claim to be
      // listening while no AI session exists yet.
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => {
          reject(new Error("Hugback backend did not become ready in time"));
        }, CONNECTION_TIMEOUT_MS);

        const handleOpen = () => {
          if (!isCurrentAttempt()) { ws.close(); return; }
          console.log("[Hugback] WebSocket connection established. Waiting for Gemini...");
          ws.send(JSON.stringify(authenticationMessage));
        };
        const handleMessage = (event: MessageEvent) => {
          try {
            const message = JSON.parse(event.data);
            if (message.type === "ready") {
              window.clearTimeout(timeout);
              removeStartupListeners();
              resolve();
            } else if (message.type === "error") {
              window.clearTimeout(timeout);
              removeStartupListeners();
              reject(new Error(message.message || "Hugback backend failed to start a session"));
            }
          } catch {
            // Ignore non-JSON messages while waiting for the ready event.
          }
        };
        const handleError = () => {
          window.clearTimeout(timeout);
          removeStartupListeners();
          reject(new Error(`Unable to connect to Hugback backend on ${wsUrl}`));
        };
        const handleClose = () => {
          window.clearTimeout(timeout);
          removeStartupListeners();
          reject(new Error("Hugback backend disconnected before Gemini was ready"));
        };
        const removeStartupListeners = () => {
          ws.removeEventListener("open", handleOpen);
          ws.removeEventListener("message", handleMessage);
          ws.removeEventListener("error", handleError);
          ws.removeEventListener("close", handleClose);
        };

        ws.addEventListener("open", handleOpen);
        ws.addEventListener("message", handleMessage);
        ws.addEventListener("error", handleError);
        ws.addEventListener("close", handleClose);
      });

      if (!isCurrentAttempt() || wsRef.current !== ws) {
        return;
      }

      ws.onerror = (event) => {
        console.error("[Hugback] WebSocket error:", event);
      };
      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        console.log("[Hugback] WebSocket closed.");
        releaseCallResources(false);
        if (!intentionalCloseRef.current) {
          setErrorMessage((current) => current || "Hugback lost its connection. Please call again.");
          setStatus("error");
        }
      };

      // Start recording only after Gemini confirms the live session is ready.
      const recorder = await startAudioRecorder((pcm16Buffer) => {
        if (isCurrentAttempt() && wsRef.current === ws && ws.readyState === WebSocket.OPEN) {
          // Stream raw 16-bit PCM binary frame
          wsRef.current.send(pcm16Buffer);

          // Calculate RMS volume for visualizer & client-side activity check
          const samples = new Int16Array(pcm16Buffer);
          let sumSquares = 0;
          for (let i = 0; i < samples.length; i++) {
            sumSquares += samples[i] * samples[i];
          }
          const rms = Math.sqrt(sumSquares / samples.length);
          const normalizedVol = Math.min(rms / 4000, 1.0);
          setUserVolume(normalizedVol);

          // Hybrid VAD: Gemini still performs server-side VAD, while the
          // browser explicitly flushes the turn after sustained silence.
          // This prevents an always-open microphone from leaving the model
          // waiting indefinitely in rooms with low background noise.
          if (normalizedVol >= SPEECH_THRESHOLD) {
            userSpeechActiveRef.current = true;
            silenceStartedAtRef.current = null;
          } else if (userSpeechActiveRef.current) {
            const now = performance.now();
            if (silenceStartedAtRef.current === null) {
              silenceStartedAtRef.current = now;
            } else if (now - silenceStartedAtRef.current >= END_OF_SPEECH_SILENCE_MS) {
              wsRef.current.send(JSON.stringify({ type: "audio_stream_end" }));
              userSpeechActiveRef.current = false;
              silenceStartedAtRef.current = null;
            }
          }

          // Edge VAD Barge-in Check:
          // If the user speaks firmly (volume > threshold) while Hugback is actively speaking,
          // instantly flush client playback and signal turn_complete to reclaim floor!
          if (normalizedVol > 0.35 && (isAgentSpeakingRef.current || playerRef.current?.isBusy())) {
            console.log("[Hugback] Edge VAD barge-in triggered by user voice!");
            if (playerRef.current) {
              playerRef.current.flush();
            }
            isAgentSpeakingRef.current = false;
            setHugbackVolume(0);
            setStatus("listening");

            // Signal to backend
            wsRef.current.send(JSON.stringify({ type: "turn_complete" }));
          }
        }
      });
      if (!isCurrentAttempt()) { recorder.stop(); return; }
      recorderRef.current = recorder;

      if (!isAgentSpeakingRef.current) setStatus("listening");
    } catch (err: unknown) {
      if (callAttemptRef.current !== attempt) return;
      console.error("[Hugback] Failed to start call:", err);
      releaseCallResources(true);
      if (!intentionalCloseRef.current) {
        const message = err instanceof Error ? err.message : "Failed to access microphone or connect";
        setErrorMessage(message);
        setStatus("error");
      }
    }
  }, [status, wsUrl, demoParent, recipientId, workflowAcknowledged, onTranscriptionUpdate, releaseCallResources]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      endCall();
    };
  }, [endCall]);

  return {
    status,
    errorMessage,
    userTranscript,
    hugbackTranscript,
    userVolume,
    hugbackVolume,
    callInfo,
    isCallActive: status !== "disconnected" && status !== "error",
    startCall,
    endCall,
  };
}
