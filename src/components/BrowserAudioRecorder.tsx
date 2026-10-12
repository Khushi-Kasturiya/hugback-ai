"use client";

import { useEffect, useRef, useState } from "react";
import { Mic, RotateCcw, Square } from "lucide-react";

const MAX_SECONDS = 30;

function preferredMimeType() {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  return ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"]
    .find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionFor(type: string) {
  return type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
}

export function BrowserAudioRecorder({
  disabled,
  label,
  minimumSeconds,
  help,
  onRecorded,
  onRecordingChange,
}: {
  disabled: boolean;
  label: string;
  minimumSeconds: number;
  help: string;
  onRecorded: (file: File | null) => void;
  onRecordingChange?: (recording: boolean) => void;
}) {
  const [phase, setPhase] = useState<"idle" | "requesting" | "recording" | "ready">("idle");
  const [seconds, setSeconds] = useState(0);
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef(0);
  const previewUrlRef = useRef("");

  function clearTimer() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }

  function releaseMicrophone() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function replacePreviewUrl(next: string) {
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
    previewUrlRef.current = next;
    setPreviewUrl(next);
  }

  useEffect(() => () => {
    clearTimer();
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.ondataavailable = null;
      recorderRef.current.onstop = null;
      recorderRef.current.stop();
    }
    releaseMicrophone();
    if (previewUrlRef.current) URL.revokeObjectURL(previewUrlRef.current);
  }, []);

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  async function startRecording() {
    if (disabled || phase === "requesting" || phase === "recording") return;
    setError("");
    setSeconds(0);
    replacePreviewUrl("");
    onRecorded(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Browser microphone recording is not supported here. Use a current Chrome, Edge, Firefox, or Safari browser.");
      return;
    }
    setPhase("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;
      const mimeType = preferredMimeType();
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunks.push(event.data); };
      recorder.onstop = () => {
        clearTimer();
        releaseMicrophone();
        onRecordingChange?.(false);
        recorderRef.current = null;
        const elapsed = Math.min(MAX_SECONDS, (Date.now() - startedAtRef.current) / 1000);
        setSeconds(Math.floor(elapsed));
        if (elapsed < minimumSeconds) {
          setPhase("idle");
          setError(`${label} must be at least ${minimumSeconds} seconds. Please record again.`);
          return;
        }
        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        if (!blob.size) {
          setPhase("idle");
          setError("No microphone audio was captured. Check microphone access and try again.");
          return;
        }
        const file = new File([blob], `${label.toLowerCase().replace(/\s+/g, "-")}.${extensionFor(type)}`, { type });
        replacePreviewUrl(URL.createObjectURL(blob));
        onRecorded(file);
        setPhase("ready");
      };
      startedAtRef.current = Date.now();
      recorder.start(250);
      setPhase("recording");
      onRecordingChange?.(true);
      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAtRef.current) / 1000);
        setSeconds(Math.min(elapsed, MAX_SECONDS));
        if (elapsed >= MAX_SECONDS && recorder.state === "recording") recorder.stop();
      }, 250);
    } catch (recordingError) {
      clearTimer();
      releaseMicrophone();
      recorderRef.current = null;
      onRecordingChange?.(false);
      setPhase("idle");
      setError(recordingError instanceof DOMException && recordingError.name === "NotAllowedError"
        ? "Microphone access was denied. Allow microphone access in your browser and try again."
        : "The microphone could not start. Check that it is available and try again.");
    }
  }

  const isRecording = phase === "recording";
  return (
    <div className="rounded-[24px] border border-dashed border-[#9BA5FC]/35 bg-gradient-to-br from-[#FCFAFF] to-[#F2F8FF] p-5 text-sm font-semibold text-stone-800">
      <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-violet-700">{label}</span>
      <p>{help}</p>

      <div className="mt-5 flex flex-wrap items-center gap-4">
        {isRecording ? <button type="button" onClick={stopRecording} className="grid h-16 w-16 place-items-center rounded-full bg-rose-600 text-white shadow-[0_0_0_8px_rgba(225,29,72,0.12)] transition hover:scale-105 hover:bg-rose-700" aria-label="Stop recording">
          <Square className="h-5 w-5 fill-current" />
        </button> : <button type="button" disabled={disabled || phase === "requesting"} onClick={startRecording} className="grid h-16 w-16 place-items-center rounded-full bg-gradient-to-br from-[#56619C] via-violet-500 to-blue-400 text-white shadow-[0_12px_30px_rgba(86,97,156,0.3)] transition hover:scale-105 hover:shadow-[0_16px_36px_rgba(139,92,246,0.35)] disabled:cursor-not-allowed disabled:opacity-40" aria-label={phase === "ready" ? "Record again" : "Start recording"}>
          {phase === "ready" ? <RotateCcw className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
        </button>}
        <span className="text-sm font-bold text-[#56619C]">{phase === "requesting" ? "Requesting microphone…" : isRecording ? "Recording… tap to stop" : phase === "ready" ? "Record again" : "Start recording"}</span>
        {(isRecording || phase === "ready") && <span className={`font-mono text-xs ${isRecording ? "text-rose-700" : "text-stone-500"}`} aria-live="polite">
          {isRecording ? "● " : ""}{String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")}
        </span>}
      </div>
      {isRecording && <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-stone-200"><div className="h-full bg-gradient-to-r from-hugback-sky to-hugback-violet transition-all" style={{ width: `${Math.max(2, (seconds / MAX_SECONDS) * 100)}%` }} /></div>}
      {previewUrl && <audio className="mt-4 w-full" controls preload="metadata" src={previewUrl}>Your browser does not support audio playback.</audio>}
      {phase === "ready" && <p className="mt-2 text-xs font-normal text-[#56619C]">Recording ready. Listen once, then record again if needed.</p>}
      {error && <p className="mt-3 text-xs font-normal leading-5 text-rose-700" role="alert">{error}</p>}
    </div>
  );
}
