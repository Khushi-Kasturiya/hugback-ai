"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { startAudioRecorder, RecorderHandle } from "@/lib/audio-recorder";
import { startAudioPlayer, PlayerHandle, base64ToArrayBuffer } from "@/lib/audio-player";

const CONNECTION_TIMEOUT_MS = 15_000;
const SPEECH_THRESHOLD = 0.05;
const END_OF_SPEECH_SILENCE_MS = 700;

function defaultWebSocketUrl(): string {
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
  onTranscriptionUpdate?: (role: "user" | "elara", text: string) => void;
}

export function useLiveAudio({
  wsUrl = defaultWebSocketUrl(),
  onTranscriptionUpdate,
}: UseLiveAudioOptions = {}) {
  const [status, setStatus] = useState<CallStatus>("disconnected");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [userTranscript, setUserTranscript] = useState<string>("");
  const [elaraTranscript, setElaraTranscript] = useState<string>("");
  const [userVolume, setUserVolume] = useState<number>(0);
  const [elaraVolume, setElaraVolume] = useState<number>(0);

  const wsRef = useRef<WebSocket | null>(null);
  const recorderRef = useRef<RecorderHandle | null>(null);
  const playerRef = useRef<PlayerHandle | null>(null);
  const isAgentSpeakingRef = useRef<boolean>(false);
  const speakingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const intentionalCloseRef = useRef<boolean>(false);
  const userSpeechActiveRef = useRef<boolean>(false);
  const silenceStartedAtRef = useRef<number | null>(null);

  const releaseCallResources = useCallback((closeSocket: boolean) => {
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

    if (speakingTimeoutRef.current) {
      clearTimeout(speakingTimeoutRef.current);
      speakingTimeoutRef.current = null;
    }

    isAgentSpeakingRef.current = false;
    userSpeechActiveRef.current = false;
    silenceStartedAtRef.current = null;
    setUserVolume(0);
    setElaraVolume(0);
  }, []);

  const endCall = useCallback(() => {
    intentionalCloseRef.current = true;
    releaseCallResources(true);
    setErrorMessage(null);
    setStatus("disconnected");
  }, [releaseCallResources]);

  const startCall = useCallback(async () => {
    if (status === "connecting" || status === "connected" || status === "speaking" || status === "listening") {
      return;
    }

    setErrorMessage(null);
    setStatus("connecting");
    intentionalCloseRef.current = false;

    try {
      // 1. Initialize Player first
      const player = await startAudioPlayer();
      playerRef.current = player;

      // 2. Initialize WebSocket
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onmessage = (event) => {
        try {
          const adkEvent = JSON.parse(event.data);

          // Handle reconnection signal
          if (adkEvent.type === "reconnecting") {
            setStatus("connecting");
            return;
          }

          if (adkEvent.type === "ready") {
            return;
          }

          if (adkEvent.type === "error") {
            setErrorMessage(adkEvent.message || "Backend error");
            setStatus("error");
            releaseCallResources(true);
            return;
          }

          // Handle incoming Gemini Audio
          if (adkEvent.content && adkEvent.content.parts) {
            for (const part of adkEvent.content.parts) {
              if (
                part.inlineData &&
                part.inlineData.mimeType &&
                part.inlineData.mimeType.startsWith("audio/pcm") &&
                playerRef.current
              ) {
                const audioBuffer = base64ToArrayBuffer(part.inlineData.data);
                playerRef.current.playPcm(audioBuffer);

                isAgentSpeakingRef.current = true;
                setStatus("speaking");
                setElaraVolume(0.8);

                if (speakingTimeoutRef.current) {
                  clearTimeout(speakingTimeoutRef.current);
                }
                speakingTimeoutRef.current = setTimeout(() => {
                  isAgentSpeakingRef.current = false;
                  setElaraVolume(0);
                  setStatus("listening");
                }, 3000);
              }
            }
          }

          // Handle user speech transcription
          if (adkEvent.inputTranscription && adkEvent.inputTranscription.text) {
            const text = adkEvent.inputTranscription.text;
            setUserTranscript((prev) => (prev ? `${prev} ${text}` : text));
            onTranscriptionUpdate?.("user", text);
          }

          // Handle agent speech transcription
          if (adkEvent.outputTranscription && adkEvent.outputTranscription.text) {
            const text = adkEvent.outputTranscription.text;
            setElaraTranscript((prev) => (prev ? `${prev} ${text}` : text));
            onTranscriptionUpdate?.("elara", text);
          }

          // Handle turn completion
          if (adkEvent.turnComplete) {
            if (speakingTimeoutRef.current) {
              clearTimeout(speakingTimeoutRef.current);
            }
            isAgentSpeakingRef.current = false;
            setElaraVolume(0);
            setStatus("listening");
          }

          // Handle Gemini server-side interruption event
          if (adkEvent.interrupted) {
            console.log("[Elara] Server interruption signal received. Flushing audio.");
            if (playerRef.current) {
              playerRef.current.flush();
            }
            isAgentSpeakingRef.current = false;
            setElaraVolume(0);
            setStatus("listening");
          }
        } catch (err) {
          console.error("[Elara] Error processing WebSocket message:", err);
        }
      };

      // The broker accepts the browser socket before it connects to Gemini.
      // Wait for its explicit ready event so the UI cannot claim to be
      // listening while no AI session exists yet.
      await new Promise<void>((resolve, reject) => {
        const timeout = window.setTimeout(() => {
          reject(new Error("Elara backend did not become ready in time"));
        }, CONNECTION_TIMEOUT_MS);

        const handleOpen = () => {
          console.log("[Elara] WebSocket connection established. Waiting for Gemini...");
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
              reject(new Error(message.message || "Elara backend failed to start a session"));
            }
          } catch {
            // Ignore non-JSON messages while waiting for the ready event.
          }
        };
        const handleError = () => {
          window.clearTimeout(timeout);
          removeStartupListeners();
          reject(new Error(`Unable to connect to Elara backend on ${wsUrl}`));
        };
        const handleClose = () => {
          window.clearTimeout(timeout);
          removeStartupListeners();
          reject(new Error("Elara backend disconnected before Gemini was ready"));
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

      if (intentionalCloseRef.current || wsRef.current !== ws) {
        return;
      }

      ws.onerror = (event) => {
        console.error("[Elara] WebSocket error:", event);
      };
      ws.onclose = () => {
        console.log("[Elara] WebSocket closed.");
        releaseCallResources(false);
        if (!intentionalCloseRef.current) {
          setErrorMessage((current) => current || "Elara lost its connection. Please call again.");
          setStatus("error");
        }
      };

      // Start recording only after Gemini confirms the live session is ready.
      const recorder = await startAudioRecorder((pcm16Buffer) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
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
          // If the user speaks firmly (volume > threshold) while Elara is actively speaking,
          // instantly flush client playback and signal turn_complete to reclaim floor!
          if (normalizedVol > 0.35 && isAgentSpeakingRef.current) {
            console.log("[Elara] Edge VAD barge-in triggered by user voice!");
            if (playerRef.current) {
              playerRef.current.flush();
            }
            isAgentSpeakingRef.current = false;
            setElaraVolume(0);
            setStatus("listening");

            // Signal to backend
            wsRef.current.send(JSON.stringify({ type: "turn_complete" }));
          }
        }
      });
      recorderRef.current = recorder;

      setStatus("listening");
    } catch (err: unknown) {
      console.error("[Elara] Failed to start call:", err);
      releaseCallResources(true);
      if (!intentionalCloseRef.current) {
        const message = err instanceof Error ? err.message : "Failed to access microphone or connect";
        setErrorMessage(message);
        setStatus("error");
      }
    }
  }, [status, wsUrl, onTranscriptionUpdate, releaseCallResources]);

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
    elaraTranscript,
    userVolume,
    elaraVolume,
    isCallActive: status !== "disconnected" && status !== "error",
    startCall,
    endCall,
  };
}
