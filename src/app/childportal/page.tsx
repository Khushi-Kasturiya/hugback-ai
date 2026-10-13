"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Camera,
  Check,
  CheckCircle2,
  ChevronDown,
  Clock,
  Heart,
  Loader2,
  LockKeyhole,
  Mic,
  PhoneCall,
  Plus,
  RotateCcw,
  Settings2,
  Sparkles,
  Square,
  Upload,
  User,
  Volume2,
  X,
} from "lucide-react";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import {
  DemoCallSummary,
  DemoFamily,
  DemoRecipient,
  WellbeingSignal,
  demoCallSummary,
  demoRequest,
  parentCallUrl,
} from "@/lib/demo-api";
import { getBrowserIdentity } from "@/lib/identity";
import { PortalStatus, portalGet } from "@/lib/portal-api";
import {
  loadChildPhoto,
  removeChildPhoto,
  saveChildPhoto,
  saveImport,
} from "@/lib/portal-storage";
import { ChatPreview, MAX_IMPORT_BYTES, parseChat } from "@/lib/chat-import";
import { audioBase64, voiceRequest } from "@/lib/voice-api";
import { prepareVoiceWav } from "@/lib/voice-wav";

type DashboardView = "family-room" | "wizard";

function readableCallStatus(status?: string) {
  if (!status) return "No check-ins yet";
  if (status === "active" || status === "processing") return "Check-in in progress";
  if (status === "memory_failed") return "Check-in finished · Memory needs attention";
  if (status === "privacy_hold") return "Check-in finished · Privacy hold";
  if (status === "failed" || status === "interrupted") return "Check-in ended early";
  return "Check-in completed";
}

function formatDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function getSignalBadgeColor(category: WellbeingSignal["category"]) {
  switch (category) {
    case "upbeat":
      return "bg-emerald-50 text-emerald-700 border-emerald-200/60";
    case "calm":
      return "bg-[#EDF7FF] text-[#315F89] border-[#C7E6FF]";
    case "neutral":
      return "bg-stone-50 text-stone-600 border-stone-200";
    case "lower_energy":
      return "bg-amber-50 text-amber-700 border-amber-200/60";
    case "tense":
      return "bg-rose-50 text-rose-700 border-rose-200/60";
    default:
      return "bg-violet-50 text-[#56619C] border-[#D9CDF8]";
  }
}

// ---------------------------------------------------------------------------
// Custom Audio Recorder with Pulsing Gradient Button (#9BA5FC to #B69CF2)
// ---------------------------------------------------------------------------
function PulsingAudioRecorder({
  disabled,
  label,
  minimumSeconds,
  promptText,
  compact = false,
  onRecorded,
}: {
  disabled: boolean;
  label: string;
  minimumSeconds: number;
  promptText?: string;
  compact?: boolean;
  onRecorded: (file: File | null) => void;
}) {
  const [phase, setPhase] = useState<"idle" | "requesting" | "recording" | "ready">("idle");
  const [seconds, setSeconds] = useState(0);
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef(0);
  const MAX_SECONDS = 30;

  function clearTimer() {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  }

  function releaseMicrophone() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  useEffect(() => {
    return () => {
      clearTimer();
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.ondataavailable = null;
        recorderRef.current.onstop = null;
        recorderRef.current.stop();
      }
      releaseMicrophone();
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  function stopRecording() {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }

  async function startRecording() {
    if (disabled || phase === "requesting" || phase === "recording") return;
    setError("");
    setSeconds(0);
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    setPreviewUrl("");
    onRecorded(null);

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Microphone recording is not supported on this browser.");
      return;
    }

    setPhase("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      streamRef.current = stream;

      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (t) => MediaRecorder.isTypeSupported?.(t)
      ) || "";

      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      const chunks: Blob[] = [];
      recorderRef.current = recorder;

      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };

      recorder.onstop = () => {
        clearTimer();
        releaseMicrophone();
        recorderRef.current = null;
        const elapsed = Math.min(MAX_SECONDS, (Date.now() - startedAtRef.current) / 1000);
        setSeconds(Math.floor(elapsed));

        if (elapsed < minimumSeconds) {
          setPhase("idle");
          setError(`Please record for at least ${minimumSeconds} seconds.`);
          return;
        }

        const type = recorder.mimeType || mimeType || "audio/webm";
        const blob = new Blob(chunks, { type });
        if (!blob.size) {
          setPhase("idle");
          setError("No audio captured. Check microphone settings.");
          return;
        }

        const ext = type.includes("mp4") ? "m4a" : "webm";
        const file = new File([blob], `${label.toLowerCase().replace(/\s+/g, "-")}.${ext}`, { type });
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
        onRecorded(file);
        setPhase("ready");
      };

      startedAtRef.current = Date.now();
      recorder.start(250);
      setPhase("recording");

      timerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startedAtRef.current) / 1000);
        setSeconds(Math.min(elapsed, MAX_SECONDS));
        if (elapsed >= MAX_SECONDS && recorder.state === "recording") recorder.stop();
      }, 250);
    } catch {
      clearTimer();
      releaseMicrophone();
      recorderRef.current = null;
      setPhase("idle");
      setError("Microphone access was denied or is unavailable.");
    }
  }

  const isRecording = phase === "recording";

  if (compact) {
    return (
      <div className="rounded-2xl border border-[#9BA5FC]/20 bg-white/80 p-3.5 shadow-xs backdrop-blur-xs transition hover:border-[#9BA5FC]/40">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-baseline gap-2">
            <span className="text-[11px] font-bold uppercase tracking-wider text-[#56619C]">{label}</span>
          </div>
          {phase === "ready" && (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
              <Check className="h-2.5 w-2.5" /> Captured
            </span>
          )}
        </div>

        {promptText && (
          <div className="mt-2 rounded-xl border border-[#9BA5FC]/15 bg-[#FAF8FF] px-3 py-2 text-xs leading-relaxed text-[#454E6D]">
            <span className="block text-[11px] font-semibold text-[#56619C]">Say this aloud:</span>
            <p className="mt-0.5 italic text-xs leading-normal">“{promptText}”</p>
          </div>
        )}

        <div className="mt-2.5 flex items-center gap-3">
          {isRecording ? (
            <button
              type="button"
              onClick={stopRecording}
              className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-[#9BA5FC] to-[#B69CF2] text-white shadow-md animate-pulse"
              aria-label="Stop recording"
            >
              <Square className="h-3.5 w-3.5 fill-current" />
            </button>
          ) : (
            <button
              type="button"
              disabled={disabled || phase === "requesting"}
              onClick={startRecording}
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-r from-[#9BA5FC] to-[#B69CF2] text-white shadow-sm transition hover:scale-105 disabled:opacity-40"
              aria-label={phase === "ready" ? "Record again" : "Start recording"}
            >
              {phase === "ready" ? <RotateCcw className="h-4 w-4" /> : <Mic className="h-4 w-4" />}
            </button>
          )}

          <div className="min-w-0 flex-1 flex items-center justify-between">
            <span className="text-xs font-semibold text-[#252D49] truncate">
              {phase === "requesting"
                ? "Connecting…"
                : isRecording
                ? "Recording…"
                : phase === "ready"
                ? "Tap to re-record"
                : "Tap to record"}
            </span>
            {(isRecording || phase === "ready") && (
              <span className={`font-mono text-[11px] shrink-0 ${isRecording ? "text-[#56619C] font-bold" : "text-stone-400"}`}>
                {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")} / {MAX_SECONDS}s
              </span>
            )}
          </div>
        </div>

        {previewUrl && (
          <audio controls src={previewUrl} className="mt-2 h-7 w-full rounded-md" preload="metadata" />
        )}

        {error && <p className="mt-1 text-[11px] text-rose-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[#9BA5FC]/20 bg-white/70 p-5 shadow-sm backdrop-blur-sm transition-all hover:border-[#9BA5FC]/40">
      <div className="flex items-start justify-between gap-3">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-wider text-[#56619C]">{label}</span>
        </div>
        {phase === "ready" && (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-700">
            <Check className="h-3 w-3" /> Captured
          </span>
        )}
      </div>

      {promptText && (
        <div className="mt-3 rounded-xl border border-[#9BA5FC]/15 bg-[#FAF8FF] p-3 text-xs leading-relaxed text-[#454E6D]">
          <p className="font-semibold text-[#56619C]">Say this aloud:</p>
          <p className="mt-1 italic">“{promptText}”</p>
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-4">
        {/* Pulsing gradient button for the record state (#9BA5FC to #B69CF2) */}
        {isRecording ? (
          <button
            type="button"
            onClick={stopRecording}
            className="group relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-r from-[#9BA5FC] to-[#B69CF2] text-white shadow-[0_0_25px_rgba(155,165,252,0.6)] animate-pulse transition hover:scale-105"
            aria-label="Stop recording"
          >
            <span className="absolute inset-0 rounded-full bg-gradient-to-r from-[#9BA5FC] to-[#B69CF2] opacity-75 blur-md animate-ping" />
            <Square className="relative h-5 w-5 fill-current" />
          </button>
        ) : (
          <button
            type="button"
            disabled={disabled || phase === "requesting"}
            onClick={startRecording}
            className="flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-r from-[#9BA5FC] to-[#B69CF2] text-white shadow-[0_8px_20px_rgba(155,165,252,0.35)] transition duration-200 hover:scale-105 hover:shadow-[0_12px_28px_rgba(182,156,242,0.45)] disabled:cursor-not-allowed disabled:opacity-40"
            aria-label={phase === "ready" ? "Record again" : "Start recording"}
          >
            {phase === "ready" ? <RotateCcw className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          </button>
        )}

        <div className="flex flex-col">
          <span className="text-sm font-semibold text-[#252D49]">
            {phase === "requesting"
              ? "Connecting microphone…"
              : isRecording
              ? "Recording voice… tap to finish"
              : phase === "ready"
              ? "Tap to re-record"
              : "Tap to record"}
          </span>
          {(isRecording || phase === "ready") && (
            <span className={`font-mono text-xs ${isRecording ? "text-[#56619C] font-bold" : "text-stone-400"}`}>
              {isRecording ? "● " : ""}
              {String(Math.floor(seconds / 60)).padStart(2, "0")}:{String(seconds % 60).padStart(2, "0")} / {MAX_SECONDS}s
            </span>
          )}
        </div>
      </div>

      {previewUrl && (
        <div className="mt-4">
          <audio controls src={previewUrl} className="h-9 w-full rounded-lg" preload="metadata" />
        </div>
      )}

      {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Child Portal Component
// ---------------------------------------------------------------------------
export default function ChildPortal() {
  const [hasCompletedProfile, setHasCompletedProfile] = useState<boolean | null>(null);
  const [onboardingStep, setOnboardingStep] = useState<1 | 2>(1);
  const [dashboardView, setDashboardView] = useState<DashboardView>("family-room");

  // Profile modal state for returning user
  const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
  const [profileModalTab, setProfileModalTab] = useState<"identity" | "voice">("identity");

  // Backend state
  const [identity, setIdentity] = useState<{ owner: string; mode: "development" | "firebase" }>();
  const [status, setStatus] = useState<PortalStatus>();
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);

  // Demo family hook & selected recipient
  const demo = useDemoFamily(Boolean(status?.localDemoEnabled));
  const [selectedRecipientId, setSelectedRecipientId] = useState<string>("");

  // Child Profile state
  const [childName, setChildName] = useState(demo.family?.childName ?? "Khushi");
  const [childGender, setChildGender] = useState<"female" | "male" | "neutral" | "">(
    demo.family?.childGender ?? "female"
  );
  const [notificationEmail, setNotificationEmail] = useState("");
  const [photoUrl, setPhotoUrl] = useState("");
  const [pendingPhoto, setPendingPhoto] = useState<File>();
  const [photoBusy, setPhotoBusy] = useState(false);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileSavedToast, setProfileSavedToast] = useState(false);

  // Voice Setup state
  const [voiceSampleFile, setVoiceSampleFile] = useState<File | null>(null);
  const [consentFile, setConsentFile] = useState<File | null>(null);
  const [voiceConsentAcknowledged, setVoiceConsentAcknowledged] = useState(false);
  const [voiceEnrolling, setVoiceEnrolling] = useState(false);
  const [voiceToast, setVoiceToast] = useState("");

  // Wizard state (View 3: Parent Setup Wizard)
  const [wizardStep, setWizardStep] = useState<1 | 2 | 3>(1);
  const [wizardName, setWizardName] = useState("");
  const [wizardRelationship, setWizardRelationship] = useState<DemoRecipient["relationship"]>("mother");
  const [wizardLanguage, setWizardLanguage] = useState<NonNullable<DemoRecipient["language"]>>("auto");
  const [wizardChatFile, setWizardChatFile] = useState<File | null>(null);
  const [wizardChatPreview, setWizardChatPreview] = useState<ChatPreview | null>(null);
  const [wizardChatChildSender, setWizardChatChildSender] = useState("");
  const [wizardChatParsing, setWizardChatParsing] = useState(false);
  const [wizardEnableSignals, setWizardEnableSignals] = useState(true);
  const [wizardEnableTone, setWizardEnableTone] = useState(true);
  const [wizardEnableSummaries, setWizardEnableSummaries] = useState(true);
  const [wizardDemoSettingsOpen, setWizardDemoSettingsOpen] = useState(false);
  const [wizardTestEmail, setWizardTestEmail] = useState("");
  const [wizardTestEmailConfirm, setWizardTestEmailConfirm] = useState(false);
  const [wizardBusy, setWizardBusy] = useState(false);

  // Daily Signals Modal state
  const [signalsModalRecipient, setSignalsModalRecipient] = useState<DemoRecipient | null>(null);
  const [callSummariesCache, setCallSummariesCache] = useState<Record<string, DemoCallSummary>>({});
  const [loadingSummaryId, setLoadingSummaryId] = useState<string>("");

  // 1. Check Onboarding Profile Gate
  useEffect(() => {
    if (typeof window === "undefined") return;
    const storedCompleted = localStorage.getItem("hugback_onboarding_completed");
    if (storedCompleted === "true") {
      setHasCompletedProfile(true);
    } else if (demo.family?.childName && (demo.family?.recipients?.length > 0 || status?.voice?.profile)) {
      setHasCompletedProfile(true);
      localStorage.setItem("hugback_onboarding_completed", "true");
    } else if (demo.loading) {
      // Keep null while loading initial status
    } else {
      setHasCompletedProfile(false);
    }
  }, [demo.family, demo.loading, status?.voice]);

  // Sync profile details
  useEffect(() => {
    if (demo.family?.childName) setChildName(demo.family.childName);
    if (demo.family?.childGender) setChildGender(demo.family.childGender);
    if (demo.family?.recipients?.length && !selectedRecipientId) {
      setSelectedRecipientId(demo.family.recipients[0].recipientId);
    }
  }, [demo.family, selectedRecipientId]);

  // Load browser identity & portal capabilities
  useEffect(() => {
    let current = true;
    void (async () => {
      try {
        const browserIdentity = await getBrowserIdentity();
        if (!current) return;
        setIdentity(browserIdentity);
        const capabilities = await portalGet<PortalStatus>("/status");
        if (!current) return;
        setStatus(capabilities);
      } catch (loadError) {
        if (current) setError(loadError instanceof Error ? loadError.message : "Could not load portal capabilities.");
      }
    })();
    return () => {
      current = false;
    };
  }, [revision]);

  // Load browser-local child photo
  useEffect(() => {
    if (typeof window === "undefined" || !demo.family?.familyId) return;
    let active = true;
    void loadChildPhoto(demo.family.familyId)
      .then((blob) => {
        if (!active || !blob) return;
        setPhotoUrl(URL.createObjectURL(blob));
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [demo.family?.familyId]);

  // Cleanup photo URL
  useEffect(() => {
    return () => {
      if (photoUrl) URL.revokeObjectURL(photoUrl);
    };
  }, [photoUrl]);

  // Photo handlers
  async function handlePhotoFile(file?: File) {
    if (!file || photoBusy) return;
    setPhotoBusy(true);
    try {
      if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) {
        throw new Error("Choose a JPEG, PNG or WebP image.");
      }
      if (file.size > 2 * 1024 * 1024) throw new Error("Photo must be under 2 MB.");
      if (demo.family) await saveChildPhoto(demo.family.familyId, file);
      else setPendingPhoto(file);

      if (photoUrl) URL.revokeObjectURL(photoUrl);
      setPhotoUrl(URL.createObjectURL(file));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save photo locally.");
    } finally {
      setPhotoBusy(false);
    }
  }

  async function handleRemovePhoto() {
    if (photoBusy) return;
    setPhotoBusy(true);
    try {
      if (demo.family) await removeChildPhoto(demo.family.familyId);
      else setPendingPhoto(undefined);
      if (photoUrl) URL.revokeObjectURL(photoUrl);
      setPhotoUrl("");
    } catch {
      setError("Could not remove photo.");
    } finally {
      setPhotoBusy(false);
    }
  }

  // Save Child Profile details
  async function handleSaveProfile() {
    if (profileSaving) return;
    setProfileSaving(true);
    setError("");
    try {
      if (demo.family) {
        const updated = await demoRequest("/child-details", "PUT", {
          syntheticOnly: true,
          familyId: demo.family.familyId,
          revision: demo.family.childGenderRevision ?? 0,
          childName: childName.trim(),
          childGender,
        });
        demo.update(updated);
      }
      setProfileSavedToast(true);
      setTimeout(() => setProfileSavedToast(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile details.");
    } finally {
      setProfileSaving(false);
    }
  }

  // Voice clone enrollment
  async function handleCreateVoice() {
    if (!voiceSampleFile || !consentFile || !voiceConsentAcknowledged || voiceEnrolling) return;
    setVoiceEnrolling(true);
    setVoiceToast("Preparing high-fidelity 24 kHz audio and registering voice model…");
    try {
      const [sample, permission] = await Promise.all([
        prepareVoiceWav(voiceSampleFile, "Voice sample", 10),
        prepareVoiceWav(consentFile, "Consent", 2),
      ]);
      const [voiceSampleAudio, consentAudio] = await Promise.all([
        audioBase64(sample),
        audioBase64(permission),
      ]);

      const result = await voiceRequest("/enroll", "POST", {
        voiceSampleAudio,
        consentAudio,
        adultOwnVoice: true,
        consentToGoogleAndBilling: true,
      });

      setStatus((cur) => (cur ? { ...cur, voice: { ...cur.voice, profile: result.profile } } : cur));
      setVoiceSampleFile(null);
      setConsentFile(null);
      setVoiceConsentAcknowledged(false);
      setVoiceToast("Voice model created successfully! Ready for your family bridge.");
      setTimeout(() => setVoiceToast(""), 4500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Voice clone creation failed.");
      setVoiceToast("");
    } finally {
      setVoiceEnrolling(false);
    }
  }

  // Complete First-Time Onboarding
  async function handleCompleteOnboarding() {
    await handleSaveProfile();
    localStorage.setItem("hugback_onboarding_completed", "true");
    setHasCompletedProfile(true);
    setDashboardView("family-room");
  }

  // Wizard chat file parser
  async function handleWizardChatFile(file?: File) {
    if (!file) return;
    setWizardChatParsing(true);
    setError("");
    try {
      if (!/\.txt$/i.test(file.name)) throw new Error("Please select a WhatsApp .txt export without media.");
      if (file.size > MAX_IMPORT_BYTES) throw new Error("File must be smaller than 1 MB.");
      const text = new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
      const parsed = parseChat(text, "whatsapp", "DMY");
      setWizardChatFile(file);
      setWizardChatPreview(parsed);
      if (parsed.participants.length) {
        setWizardChatChildSender(parsed.participants[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not parse chat export.");
    } finally {
      setWizardChatParsing(false);
    }
  }

  // Complete Parent Setup Wizard
  async function handleCompleteWizard() {
    if (!wizardName.trim() || wizardBusy) return;
    setWizardBusy(true);
    setError("");
    try {
      const result = await demoRequest(demo.family ? "/recipients" : "/family", "POST", {
        syntheticOnly: true,
        simulateChildConsent: true,
        simulateParentConsent: true,
        enableMemory: true,
        timeZone: "Asia/Kolkata",
        label: wizardName.trim(),
        relationship: wizardRelationship,
        enableWellbeingSharing: wizardEnableSignals,
        enableToneContinuity: wizardEnableTone,
        simulateToneConsent: wizardEnableTone,
        enableTranscriptSharing: wizardEnableSummaries,
        enableAlertSharing: false,
        language: wizardLanguage,
        ...(!demo.family ? { childName: childName.trim(), childGender } : {}),
      });

      demo.update(result);

      if (identity?.owner && wizardChatPreview && wizardChatChildSender) {
        const parentSender = wizardChatPreview.participants.find((p) => p !== wizardChatChildSender) || "";
        const createdRecipient = result.recipients.find((r) => r.label === wizardName.trim());
        if (createdRecipient && parentSender) {
          try {
            const hash = await crypto.subtle.digest(
              "SHA-256",
              new TextEncoder().encode(`whatsapp:DMY:${wizardChatFile?.name || "chat"}`)
            );
            const fingerprint = Array.from(new Uint8Array(hash), (b) => b.toString(16).padStart(2, "0")).join("");
            await saveImport(identity.owner, {
              recipientId: createdRecipient.recipientId,
              filename: wizardChatFile?.name || "family-chat.txt",
              fingerprint,
              childSender: wizardChatChildSender,
              parentSender,
              timezone: "Asia/Kolkata",
              preview: wizardChatPreview,
            });
          } catch {
            // Non-critical local import save failure
          }
        }
      }

      setWizardStep(1);
      setWizardName("");
      setWizardChatFile(null);
      setWizardChatPreview(null);
      const created = result.recipients.find((r) => r.label === wizardName.trim());
      if (created) setSelectedRecipientId(created.recipientId);
      setDashboardView("family-room");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create loved one bridge.");
    } finally {
      setWizardBusy(false);
    }
  }

  // Fetch Call Summary
  async function fetchSummary(recipientId: string, sessionId: string) {
    if (callSummariesCache[sessionId] || loadingSummaryId === sessionId) return;
    setLoadingSummaryId(sessionId);
    try {
      const summary = await demoCallSummary(recipientId, sessionId);
      setCallSummariesCache((prev) => ({ ...prev, [sessionId]: summary }));
    } catch {
      // Graceful fallback
    } finally {
      setLoadingSummaryId("");
    }
  }

  const recipients = demo.family?.recipients || [];
  const selectedRecipient = recipients.find((r) => r.recipientId === selectedRecipientId) || recipients[0];
  const previewCallHref = parentCallUrl(selectedRecipient?.recipientId);

  const recentSignals = recipients.flatMap((r) =>
    (r.wellbeingSignals || []).map((s) => ({
      ...s,
      recipientLabel: r.label,
      recipientRelationship: r.relationship,
    }))
  ).sort((a, b) => Date.parse(b.observedAt) - Date.parse(a.observedAt));

  // Loading gate
  if (hasCompletedProfile === null && demo.loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[#FAF8F5] via-[#F4F6FD] to-[#EFEBF9]">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-[#56619C]" />
          <p className="font-serif text-sm font-medium text-[#56619C]">Connecting to HugBack…</p>
        </div>
      </main>
    );
  }

  return (
    <main
      className={`min-h-screen bg-gradient-to-br from-[#FAF8F5] via-[#F4F6FD] to-[#EFEBF9] text-[#1F253B] selection:bg-[#9BA5FC]/30 ${
        !hasCompletedProfile ? "h-screen overflow-hidden" : ""
      }`}
    >
      {/* Subtle Ambient Aurora Orbs */}
      <div
        aria-hidden="true"
        className="pointer-events-none fixed -left-32 top-10 h-96 w-96 rounded-full bg-[#72B5FE]/15 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none fixed -right-32 top-80 h-[28rem] w-[28rem] rounded-full bg-[#B69CF2]/15 blur-3xl"
      />

      {/* ===================================================================== */}
      {/* 1. STATE LOGIC: IF NOT COMPLETED -> FULL-SCREEN ONBOARDING WIZARD    */}
      {/* ===================================================================== */}
      {!hasCompletedProfile ? (
        <section className="relative z-10 flex h-screen max-h-screen w-full flex-col items-center justify-center overflow-hidden px-4 py-3 sm:px-6">
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.35, ease: "easeOut" }}
            className="w-full max-w-xl rounded-[2rem] border border-[#9BA5FC]/20 bg-white/90 px-6 py-5 shadow-[0_20px_50px_-15px_rgba(86,97,156,0.12)] backdrop-blur-md sm:px-8 sm:py-6"
          >
            {/* Top Branding Logo */}
            <div className="flex items-center justify-center gap-2 mb-2.5">
              <Image
                src="/logo.png"
                width={727}
                height={343}
                priority
                alt="HugBack"
                className="h-7 w-auto object-contain"
              />
              <div className="flex items-center gap-1.5">
                <span className="font-serif text-lg font-bold tracking-tight text-[#56619C]">HugBack</span>
                <span className="rounded-full bg-[#9BA5FC]/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#56619C]">
                  Child Portal
                </span>
              </div>
            </div>

            {/* Onboarding Header */}
            <div className="text-center">
              <h1 className="font-serif text-2xl font-medium tracking-tight text-[#56619C] sm:text-[1.75rem]">
                Welcome to HugBack.
              </h1>
              <p className="mx-auto mt-1 max-w-md text-xs leading-relaxed text-[#56617F]">
                Before we connect you with your loved ones, let's set up your secure voice bridge.
              </p>
            </div>

            {/* Stepper Indicator */}
            <div className="mt-3.5 flex items-center justify-center gap-2.5">
              <button
                type="button"
                onClick={() => setOnboardingStep(1)}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1 text-xs font-bold transition-all ${
                  onboardingStep === 1
                    ? "bg-[#56619C] text-white shadow-sm shadow-[#56619C]/20"
                    : "bg-[#F1EFFF] text-[#56619C] hover:bg-[#E8E4FF]"
                }`}
              >
                <span>1. Personal Identity</span>
              </button>

              <div className="h-0.5 w-5 bg-[#9BA5FC]/30" />

              <button
                type="button"
                onClick={() => setOnboardingStep(2)}
                className={`flex items-center gap-1.5 rounded-full px-3.5 py-1 text-xs font-bold transition-all ${
                  onboardingStep === 2
                    ? "bg-[#56619C] text-white shadow-sm shadow-[#56619C]/20"
                    : "bg-[#F1EFFF] text-[#56619C] hover:bg-[#E8E4FF]"
                }`}
              >
                <span>2. Carry Your Voice</span>
              </button>
            </div>

            {/* Step 1: Personal Identity */}
            {onboardingStep === 1 && (
              <div className="mt-3.5 space-y-3">
                <div>
                  <h3 className="font-serif text-base font-semibold text-[#252D49]">Personal Identity</h3>
                  <p className="text-[11px] text-stone-500 leading-snug">
                    Set up how your loved ones recognize and hear from you during family check-ins.
                  </p>
                </div>

                {/* Side-by-Side: Avatar on Left, Inputs on Right */}
                <div className="grid grid-cols-[115px_1fr] sm:grid-cols-[130px_1fr] gap-5 items-center">
                  {/* Left: Circular Upload Zone */}
                  <div className="flex flex-col items-center text-center">
                    <label className="group relative flex h-28 w-28 sm:h-32 sm:w-32 cursor-pointer flex-col items-center justify-center overflow-hidden rounded-full border-2 border-dashed border-[#9BA5FC]/40 bg-[#F8F9FF] shadow-inner transition hover:border-[#56619C] hover:bg-[#F2F4FD]">
                      {photoUrl ? (
                        <>
                          <img
                            src={photoUrl}
                            alt="Child Avatar"
                            className="h-full w-full object-cover transition group-hover:opacity-75"
                          />
                          <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition group-hover:opacity-100">
                            <Camera className="h-5 w-5 text-white" />
                          </div>
                        </>
                      ) : (
                        <div className="flex flex-col items-center p-2 text-center">
                          <Camera className="h-7 w-7 text-[#9BA5FC] transition group-hover:scale-110" />
                          <span className="mt-1 text-[10px] font-bold text-[#56619C] leading-tight">Upload Photo</span>
                        </div>
                      )}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="sr-only"
                        disabled={photoBusy}
                        onChange={(e) => void handlePhotoFile(e.target.files?.[0])}
                      />
                    </label>

                    <p className="mt-1.5 text-center text-[10px] leading-tight text-stone-500">
                      Stored locally for privacy.
                    </p>

                    {photoUrl && (
                      <button
                        type="button"
                        onClick={handleRemovePhoto}
                        disabled={photoBusy}
                        className="mt-0.5 text-[10px] font-semibold text-rose-600 hover:underline"
                      >
                        Remove photo
                      </button>
                    )}
                  </div>

                  {/* Right: Text Inputs */}
                  <div className="space-y-2">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      <div>
                        <label className="block mb-1 text-[10px] font-bold uppercase tracking-wider text-[#56619C]">
                          Your Name
                        </label>
                        <input
                          type="text"
                          value={childName}
                          onChange={(e) => setChildName(e.target.value)}
                          placeholder="e.g. Khushi"
                          className="w-full rounded-xl border border-[#9BA5FC]/30 bg-white/90 px-3 py-2 text-xs font-medium text-[#1F253B] shadow-inner transition focus:border-[#56619C] focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                        />
                      </div>

                      <div>
                        <label className="block mb-1 text-[10px] font-bold uppercase tracking-wider text-[#56619C]">
                          Gender Phrasing
                        </label>
                        <select
                          value={childGender}
                          onChange={(e) => setChildGender(e.target.value as typeof childGender)}
                          className="w-full rounded-xl border border-[#9BA5FC]/30 bg-white/90 px-2.5 py-2 text-xs font-medium text-[#1F253B] shadow-inner transition focus:border-[#56619C] focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                        >
                          <option value="female">Female</option>
                          <option value="male">Male</option>
                          <option value="neutral">Neutral</option>
                        </select>
                      </div>
                    </div>

                    <div>
                      <label className="block mb-1 text-[10px] font-bold uppercase tracking-wider text-[#56619C]">
                        Notification Email
                      </label>
                      <input
                        type="email"
                        value={notificationEmail}
                        onChange={(e) => setNotificationEmail(e.target.value)}
                        placeholder="khushi@example.com"
                        className="w-full rounded-xl border border-[#9BA5FC]/30 bg-white/90 px-3 py-2 text-xs font-medium text-[#1F253B] shadow-inner transition focus:border-[#56619C] focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                      />
                      <span className="mt-0.5 block text-[10px] text-stone-500">
                        Optional: Receive brief check-in summaries.
                      </span>
                    </div>
                  </div>
                </div>

                {/* Privacy & Device Storage Note (mirrors Step 2's consent box) */}
                <div className="flex items-start gap-2.5 rounded-xl border border-[#9BA5FC]/15 bg-[#FAF8FF] p-2 text-[11px] leading-relaxed text-[#454E6D]">
                  <LockKeyhole className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[#56619C]" />
                  <span>
                    Your profile and photo stay private in your browser. We only use these details to help HugBack personalize your natural family greetings.
                  </span>
                </div>

                {/* Footer Action */}
                <div className="flex items-center justify-between border-t border-[#9BA5FC]/15 pt-2.5">
                  <span className="text-[11px] font-medium text-stone-400">Step 1 of 2</span>
                  <button
                    type="button"
                    disabled={!childName.trim()}
                    onClick={() => setOnboardingStep(2)}
                    className="flex items-center gap-1.5 rounded-full bg-[#56619C] px-5 py-2 text-xs font-bold text-white shadow-md shadow-[#56619C]/25 transition hover:bg-[#465181] disabled:opacity-40"
                  >
                    <span>Save & Continue to Voice</span>
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            )}

            {/* Step 2: Carry Your Voice */}
            {onboardingStep === 2 && (
              <div className="mt-3.5 space-y-3">
                <div>
                  <h3 className="font-serif text-base font-semibold text-[#252D49]">Carry Your Voice</h3>
                  <p className="text-[11px] text-stone-500 leading-snug">
                    Record short samples to create your secure voice model so your loved ones always hear your genuine warmth.
                  </p>
                </div>

                <div className="space-y-2">
                  <PulsingAudioRecorder
                    compact
                    disabled={voiceEnrolling}
                    label="1. Voice Sample (20-30s)"
                    minimumSeconds={10}
                    promptText="Namaste Maa, I'm having a quiet evening here with a cup of tea, thinking about our garden back home…"
                    onRecorded={(file) => setVoiceSampleFile(file)}
                  />

                  <PulsingAudioRecorder
                    compact
                    disabled={voiceEnrolling}
                    label="2. Consent Recording"
                    minimumSeconds={2}
                    promptText="I am the owner of this voice and I consent to HugBack creating a synthetic voice model for family check-in calls."
                    onRecorded={(file) => setConsentFile(file)}
                  />
                </div>

                <label className="flex items-start gap-2.5 rounded-xl border border-[#9BA5FC]/15 bg-[#FAF8FF] p-2 text-[11px] leading-relaxed text-[#454E6D]">
                  <input
                    type="checkbox"
                    checked={voiceConsentAcknowledged}
                    onChange={(e) => setVoiceConsentAcknowledged(e.target.checked)}
                    className="mt-0.5 h-3.5 w-3.5 shrink-0 rounded accent-[#56619C]"
                  />
                  <span>
                    I am 18 or older, this is my authentic voice, and I authorize HugBack to synthesize this voice model for my family’s check-in bridge.
                  </span>
                </label>

                {voiceToast && (
                  <div className="rounded-xl bg-[#EDF7FF] p-2 text-[11px] font-semibold text-[#315F89]">
                    {voiceToast}
                  </div>
                )}

                <div className="flex items-center justify-between border-t border-[#9BA5FC]/15 pt-2.5">
                  <button
                    type="button"
                    onClick={() => setOnboardingStep(1)}
                    className="text-xs font-bold text-stone-500 hover:text-stone-800"
                  >
                    ← Back to Identity
                  </button>

                  <div className="flex items-center gap-2">
                    {/* Optional sample submit */}
                    {voiceSampleFile && consentFile && voiceConsentAcknowledged && !status?.voice?.profile && (
                      <button
                        type="button"
                        disabled={voiceEnrolling}
                        onClick={handleCreateVoice}
                        className="rounded-full border border-[#9BA5FC] px-3.5 py-2 text-xs font-bold text-[#56619C] transition hover:bg-[#F2F4FD]"
                      >
                        {voiceEnrolling ? "Generating Model…" : "Train Clone Now"}
                      </button>
                    )}

                    {/* Prominent Action Button */}
                    <button
                      type="button"
                      onClick={handleCompleteOnboarding}
                      className="flex items-center gap-1.5 rounded-full bg-gradient-to-r from-[#72B5FE] to-[#B69CF2] px-4 py-2 text-xs font-bold text-white shadow-md shadow-[#9BA5FC]/30 transition hover:scale-[1.02] hover:shadow-lg"
                    >
                      <span>Complete & Enter Family Room</span>
                      <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </section>
      ) : (
        /* =================================================================== */
        /* 2. POST-ONBOARDING: SIMPLIFIED GLOBAL NAVIGATION & DASHBOARD        */
        /* =================================================================== */
        <>
          <header className="sticky top-0 z-40 border-b border-[#9BA5FC]/15 bg-white/75 backdrop-blur-xl">
            <div className="mx-auto flex min-h-[4.75rem] max-w-7xl items-center justify-between gap-4 px-4 sm:px-8">
              {/* Top Left: Logo */}
              <Link href="/" className="flex items-center gap-3 transition hover:opacity-90">
                <Image
                  src="/logo.png"
                  width={727}
                  height={343}
                  priority
                  alt="HugBack"
                  className="h-9 w-auto object-contain"
                />
                <div className="hidden sm:block">
                  <span className="font-serif text-lg font-bold tracking-tight text-[#56619C]">HugBack</span>
                  <span className="ml-1 text-xs font-semibold text-[#9BA5FC]">Child Portal</span>
                </div>
              </Link>

              {/* Top Right: Actions & User Avatar */}
              <div className="flex items-center gap-3">
                {/* Secondary: Preview Call */}
                <Link
                  href={previewCallHref}
                  className="group hidden items-center gap-2 rounded-full border border-[#9BA5FC]/20 bg-white/80 px-3.5 py-2 text-xs font-bold text-[#56619C] shadow-sm transition hover:bg-[#F2F4FD] md:inline-flex"
                >
                  <PhoneCall className="h-3.5 w-3.5 text-[#9BA5FC]" />
                  <span>Preview Parent Call</span>
                </Link>

                {/* Primary Action: Add a Loved One */}
                <button
                  type="button"
                  onClick={() => {
                    setWizardStep(1);
                    setDashboardView("wizard");
                  }}
                  className="flex items-center gap-1.5 rounded-full bg-[#56619C] px-4 py-2 text-xs font-bold text-white shadow-md shadow-[#56619C]/20 transition hover:bg-[#465181] hover:scale-105"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Add a Loved One</span>
                </button>

                {/* Profile Avatar Button (Far Top-Right Corner) */}
                <button
                  type="button"
                  onClick={() => setIsProfileModalOpen(true)}
                  className="group relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 border-[#9BA5FC]/40 bg-gradient-to-br from-[#72B5FE] to-[#B69CF2] text-xs font-bold text-white shadow-sm transition hover:border-[#56619C] hover:scale-105"
                  title="Your Profile & Voice Settings"
                >
                  {photoUrl ? (
                    <img src={photoUrl} alt={childName} className="h-full w-full object-cover" />
                  ) : (
                    <span>{childName ? childName.charAt(0).toUpperCase() : "K"}</span>
                  )}
                  <span className="sr-only">Open Profile Settings</span>
                </button>
              </div>
            </div>
          </header>

          {/* Main Dashboard Container */}
          <div className="mx-auto max-w-7xl px-4 py-8 sm:px-8">
            {error && (
              <div className="mb-6 flex items-center justify-between rounded-2xl border border-rose-200 bg-rose-50/90 p-4 text-xs font-semibold text-rose-900 backdrop-blur-md">
                <span>{error}</span>
                <button onClick={() => setError("")} className="rounded-lg p-1 text-rose-700 hover:bg-rose-100">
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <AnimatePresence mode="wait">
              {/* ============================================================= */}
              {/* VIEW 2: THE FAMILY ROOM (Main Dashboard)                      */}
              {/* ============================================================= */}
              {dashboardView === "family-room" && (
                <motion.section
                  key="family-room"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                  className="space-y-10"
                >
                  {/* Header */}
                  <div className="flex flex-wrap items-end justify-between gap-4">
                    <div>
                      <h1 className="mt-1 font-serif text-3xl font-medium tracking-tight text-[#56619C] sm:text-4xl">
                        The Family Bridge
                      </h1>
                      <p className="mt-2 text-sm leading-relaxed text-[#56617F]">
                        Where everyday conversations bring your family closer. Review signals, listen to comforting
                        check-ins, and keep your family close.
                      </p>
                    </div>
                  </div>

                  {/* Connections Grid */}
                  <div className="space-y-4">
                    <h2 className="text-xs font-extrabold uppercase tracking-wider text-[#56619C]">
                      Active Connections ({recipients.length})
                    </h2>

                    <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
                      {recipients.map((recipient) => {
                        const latestCall = recipient.calls.at(-1);
                        const callHref = parentCallUrl(recipient.recipientId);

                        return (
                          <article
                            key={recipient.recipientId}
                            className="group relative flex flex-col justify-between rounded-3xl border border-[#9BA5FC]/20 bg-white/80 p-8 shadow-[0_15px_40px_rgba(86,97,156,0.06)] backdrop-blur-md transition-all duration-300 hover:-translate-y-1 hover:border-[#9BA5FC]/50 hover:shadow-xl"
                          >
                            <div>
                              {/* Card Top: Avatar & Bridge Status */}
                              <div className="flex items-start justify-between gap-3">
                                <div className="flex items-center gap-3">
                                  <div className="grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-[#72B5FE]/20 via-[#9BA5FC]/20 to-[#B69CF2]/20 font-serif text-lg font-bold text-[#56619C] shadow-inner">
                                    {recipient.label.charAt(0).toUpperCase()}
                                  </div>
                                  <div>
                                    <h3 className="font-serif text-xl font-medium text-[#252D49]">
                                      {recipient.label}
                                    </h3>
                                    <span className="text-xs capitalize text-stone-500">
                                      {recipient.relationship}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              {/* Card Stats / Details */}
                              <div className="mt-6 space-y-2.5 rounded-2xl bg-[#F8F9FF] p-4 text-xs">
                                <div className="flex items-center justify-between text-stone-600">
                                  <span className="flex items-center gap-1.5">
                                    <Clock className="h-3.5 w-3.5 text-[#9BA5FC]" /> Latest Check-in
                                  </span>
                                  <span className="font-semibold text-[#252D49]">
                                    {latestCall ? formatDate(latestCall.startedAt) : "No check-ins yet"}
                                  </span>
                                </div>

                                <div className="flex items-center justify-between text-stone-600">
                                  <span className="flex items-center gap-1.5">
                                    <BookOpen className="h-3.5 w-3.5 text-[#72B5FE]" /> Family Memories
                                  </span>
                                  <span className="font-semibold text-[#252D49]">
                                    {recipient.background?.length || 0} excerpts
                                  </span>
                                </div>

                                <div className="flex items-center justify-between text-stone-600">
                                  <span className="flex items-center gap-1.5">
                                    <Volume2 className="h-3.5 w-3.5 text-[#B69CF2]" /> Voice Mode
                                  </span>
                                  <span className="font-semibold text-[#252D49]">
                                    {recipient.voice.mode === "child" ? "Your Voice Clone" : "Standard Voice"}
                                  </span>
                                </div>
                              </div>
                            </div>

                            {/* Card Actions */}
                            <div className="mt-6 flex items-center gap-2 pt-2">
                              <button
                                type="button"
                                onClick={() => setSignalsModalRecipient(recipient)}
                                className="flex flex-1 items-center justify-center gap-1.5 rounded-xl border border-[#9BA5FC]/30 bg-white px-3 py-2 text-xs font-bold text-[#56619C] shadow-sm transition hover:bg-[#F2F4FD]"
                              >
                                <Heart className="h-3.5 w-3.5 text-[#B69CF2]" />
                                <span>View Daily Signals</span>
                              </button>

                              <Link
                                href={callHref}
                                className="flex items-center justify-center rounded-xl bg-[#56619C] p-2 text-white shadow-sm transition hover:bg-[#465181]"
                                title={`Preview ${recipient.label}'s call`}
                              >
                                <PhoneCall className="h-3.5 w-3.5" />
                              </Link>
                            </div>
                          </article>
                        );
                      })}

                      {/* "Add a Loved One" Empty-State Card */}
                      <button
                        type="button"
                        onClick={() => {
                          setWizardStep(1);
                          setDashboardView("wizard");
                        }}
                        className="group flex min-h-[16rem] flex-col items-center justify-center rounded-3xl border-2 border-dashed border-[#9BA5FC]/30 bg-white/50 p-8 text-center transition-all duration-300 hover:-translate-y-1 hover:border-[#56619C] hover:bg-white/80 hover:shadow-lg"
                      >
                        <div className="grid h-14 w-14 place-items-center rounded-full bg-gradient-to-br from-[#72B5FE]/20 to-[#B69CF2]/20 text-[#56619C] transition group-hover:scale-110 group-hover:bg-[#56619C] group-hover:text-white">
                          <Plus className="h-6 w-6" />
                        </div>
                        <h3 className="mt-4 font-serif text-lg font-medium text-[#252D49]">
                          Add a Loved One
                        </h3>
                        <p className="mt-1 max-w-xs text-xs leading-relaxed text-stone-500">
                          Connect your mother, father, or grandparents with their custom language bridge.
                        </p>
                      </button>
                    </div>
                  </div>

                  {/* Recent Signals Widget */}
                  <div className="rounded-3xl border border-[#9BA5FC]/20 bg-white/80 p-8 shadow-[0_20px_50px_rgba(86,97,156,0.06)] backdrop-blur-md sm:p-10">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3">
                        <div className="grid h-10 w-10 place-items-center rounded-2xl bg-gradient-to-br from-[#EDF7FF] to-[#F5F1FF] text-[#56619C]">
                          <Heart className="h-5 w-5" />
                        </div>
                        <div>
                          <h2 className="font-serif text-2xl font-medium text-[#252D49]">
                            Recent Signals Widget
                          </h2>
                          <p className="text-xs text-stone-500">
                            AI-generated conversation reflections grounded in daily check-in calls.
                          </p>
                        </div>
                      </div>

                      <span className="hidden text-[11px] font-medium text-stone-400 sm:inline-block">
                        Non-medical emotional cues
                      </span>
                    </div>

                    <div className="mt-6 space-y-3">
                      {recentSignals.length > 0 ? (
                        recentSignals.slice(0, 5).map((signal) => (
                          <div
                            key={signal.signalId}
                            className="flex flex-col justify-between gap-3 rounded-2xl border border-stone-100 bg-[#FAF8FF] p-4 text-xs sm:flex-row sm:items-center"
                          >
                            <div className="flex items-center gap-3">
                              <span
                                className={`rounded-full border px-2.5 py-0.5 text-[10px] font-bold capitalize ${getSignalBadgeColor(
                                  signal.category
                                )}`}
                              >
                                {signal.category.replace("_", " ")}
                              </span>
                              <span className="font-semibold text-[#252D49]">
                                {signal.recipientLabel}: “{signal.displayText}”
                              </span>
                            </div>

                            <span className="text-[11px] text-stone-400">
                              {formatDate(signal.observedAt)}
                            </span>
                          </div>
                        ))
                      ) : (
                        <div className="rounded-2xl border border-dashed border-[#9BA5FC]/25 bg-[#FAF8FF] p-8 text-center text-xs text-stone-500">
                          <Heart className="mx-auto h-6 w-6 text-[#9BA5FC]" />
                          <p className="mt-2 font-semibold text-[#252D49]">No check-in signals yet</p>
                          <p className="mt-1 text-stone-500">
                            Once your loved one completes their first tea-time check-in, gentle emotional signals
                            will appear here.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                </motion.section>
              )}

              {/* ============================================================= */}
              {/* VIEW 3: PARENT SETUP WIZARD                                    */}
              {/* ============================================================= */}
              {dashboardView === "wizard" && (
                <motion.section
                  key="wizard"
                  initial={{ opacity: 0, y: 15 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -15 }}
                  transition={{ duration: 0.3 }}
                  className="mx-auto max-w-3xl space-y-8"
                >
                  <button
                    type="button"
                    onClick={() => setDashboardView("family-room")}
                    className="inline-flex items-center gap-2 text-xs font-bold text-[#56619C] transition hover:text-[#454E6D]"
                  >
                    <ArrowLeft className="h-3.5 w-3.5" /> Back to The Family Room
                  </button>

                  <div>
                    <p className="text-[11px] font-extrabold uppercase tracking-[0.2em] text-[#56619C]">
                      Setup Wizard
                    </p>
                    <h1 className="mt-1 font-serif text-3xl font-medium tracking-tight text-[#56619C] sm:text-4xl">
                      Add a Loved One
                    </h1>
                    <p className="mt-2 text-sm leading-relaxed text-[#56617F]">
                      Create a dedicated bridge for someone you love in three simple, thoughtful steps.
                    </p>
                  </div>

                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { step: 1, label: "Relationship Details" },
                      { step: 2, label: "Family Language" },
                      { step: 3, label: "Preferences" },
                    ].map((item) => (
                      <div
                        key={item.step}
                        className={`rounded-2xl border p-3.5 text-left transition-all ${
                          wizardStep === item.step
                            ? "border-[#56619C] bg-white shadow-md shadow-[#56619C]/10"
                            : wizardStep > item.step
                            ? "border-emerald-200 bg-emerald-50/60"
                            : "border-[#9BA5FC]/20 bg-white/50 opacity-60"
                        }`}
                      >
                        <span className="block text-[10px] font-extrabold uppercase tracking-wider text-[#9BA5FC]">
                          Step {item.step}
                        </span>
                        <span className="font-serif text-sm font-semibold text-[#252D49]">{item.label}</span>
                      </div>
                    ))}
                  </div>

                  <div className="rounded-3xl border border-[#9BA5FC]/20 bg-white/80 p-8 shadow-[0_20px_60px_rgba(86,97,156,0.08)] backdrop-blur-md sm:p-10">
                    {wizardStep === 1 && (
                      <div className="space-y-6">
                        <div>
                          <h2 className="font-serif text-2xl font-medium text-[#252D49]">
                            Who are you connecting with?
                          </h2>
                          <p className="mt-1 text-xs text-stone-500">
                            Give them a familiar name or title they'll hear in their calls.
                          </p>
                        </div>

                        <div className="space-y-4">
                          <div>
                            <label className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                              Loved One's Name / Pet Name
                            </label>
                            <input
                              type="text"
                              value={wizardName}
                              onChange={(e) => setWizardName(e.target.value)}
                              placeholder="e.g. Maa, Papa, Dadi"
                              className="mt-1.5 w-full rounded-2xl border border-[#9BA5FC]/30 bg-white px-4 py-3 text-sm font-medium text-[#1F253B] shadow-inner transition focus:border-[#56619C] focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                            />
                          </div>

                          <div>
                            <label className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                              Relationship
                            </label>
                            <select
                              value={wizardRelationship}
                              onChange={(e) =>
                                setWizardRelationship(e.target.value as DemoRecipient["relationship"])
                              }
                              className="mt-1.5 w-full rounded-2xl border border-[#9BA5FC]/30 bg-white px-4 py-3 text-sm font-medium text-[#1F253B] shadow-inner transition focus:border-[#56619C] focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                            >
                              <option value="mother">Mother</option>
                              <option value="father">Father</option>
                              <option value="grandmother">Grandmother</option>
                              <option value="grandfather">Grandfather</option>
                              <option value="other">Other Loved One</option>
                            </select>
                          </div>

                          <div>
                            <label className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                              Conversation Language
                            </label>
                            <select
                              value={wizardLanguage}
                              onChange={(e) =>
                                setWizardLanguage(e.target.value as NonNullable<DemoRecipient["language"]>)
                              }
                              className="mt-1.5 w-full rounded-2xl border border-[#9BA5FC]/30 bg-white px-4 py-3 text-sm font-medium text-[#1F253B] shadow-inner transition focus:border-[#56619C] focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                            >
                              <option value="auto">Follow the speaker (Hindi / English / Hinglish)</option>
                              <option value="en">English only</option>
                              <option value="hi">Hindi only</option>
                              <option value="hi-en">Hindi / English Blend</option>
                            </select>
                          </div>
                        </div>

                        <div className="flex justify-end pt-4">
                          <button
                            type="button"
                            disabled={!wizardName.trim()}
                            onClick={() => setWizardStep(2)}
                            className="flex items-center gap-2 rounded-full bg-[#56619C] px-6 py-3 text-sm font-bold text-white shadow-md shadow-[#56619C]/25 transition hover:bg-[#465181] disabled:opacity-40"
                          >
                            <span>Continue to Family Language</span>
                            <ArrowRight className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    )}

                    {wizardStep === 2 && (
                      <div className="space-y-6">
                        <div>
                          <h2 className="font-serif text-2xl font-medium text-[#252D49]">
                            Teach HugBack Your Family Language
                          </h2>
                          <p className="mt-1 text-xs text-stone-500">
                            Upload past chats to teach HugBack your family’s unique names, phrases, and routines.
                          </p>
                        </div>

                        <label className="flex cursor-pointer flex-col items-center justify-center rounded-3xl border-2 border-dashed border-[#9BA5FC]/40 bg-[#FAF8FF] px-6 py-10 text-center transition hover:border-[#56619C] hover:bg-[#F2F4FD]">
                          <div className="grid h-12 w-12 place-items-center rounded-2xl bg-white shadow-sm text-[#56619C]">
                            <Upload className="h-6 w-6" />
                          </div>
                          <span className="mt-4 font-serif text-lg font-medium text-[#252D49]">
                            {wizardChatFile ? wizardChatFile.name : "Choose a WhatsApp chat export (.txt)"}
                          </span>
                          <span className="mt-1 text-xs text-stone-500">
                            Text files only without media · Up to 1 MB · Parsed entirely on your browser
                          </span>
                          <input
                            type="file"
                            accept=".txt"
                            className="sr-only"
                            disabled={wizardChatParsing}
                            onChange={(e) => void handleWizardChatFile(e.target.files?.[0])}
                          />
                        </label>

                        {wizardChatParsing && (
                          <p className="text-center text-xs text-stone-500">Parsing chat messages safely…</p>
                        )}

                        {wizardChatPreview && (
                          <div className="space-y-4 rounded-2xl border border-[#9BA5FC]/20 bg-white p-5">
                            <div className="flex items-center justify-between">
                              <span className="text-xs font-bold text-emerald-800">
                                ✓ {wizardChatPreview.messages.length} messages recognized
                              </span>
                              <span className="text-[11px] text-stone-400">
                                {wizardChatPreview.skipped} media notices skipped
                              </span>
                            </div>

                            <div>
                              <label className="text-xs font-bold text-[#56619C]">
                                Which participant name is yours?
                              </label>
                              <select
                                value={wizardChatChildSender}
                                onChange={(e) => setWizardChatChildSender(e.target.value)}
                                className="mt-1.5 w-full rounded-xl border border-stone-200 bg-stone-50 p-2 text-xs"
                              >
                                {wizardChatPreview.participants.map((p) => (
                                  <option key={p} value={p}>
                                    {p}
                                  </option>
                                ))}
                              </select>
                            </div>
                          </div>
                        )}

                        <div className="flex items-center justify-between pt-4">
                          <button
                            type="button"
                            onClick={() => setWizardStep(1)}
                            className="text-xs font-bold text-stone-500 hover:text-stone-800"
                          >
                            ← Back
                          </button>

                          <div className="flex items-center gap-3">
                            <button
                              type="button"
                              onClick={() => setWizardStep(3)}
                              className="text-xs font-bold text-stone-500 hover:underline"
                            >
                              Skip for now
                            </button>

                            <button
                              type="button"
                              onClick={() => setWizardStep(3)}
                              className="flex items-center gap-2 rounded-full bg-[#56619C] px-6 py-3 text-sm font-bold text-white shadow-md shadow-[#56619C]/25 transition hover:bg-[#465181]"
                            >
                              <span>Continue to Preferences</span>
                              <ArrowRight className="h-4 w-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    )}

                    {wizardStep === 3 && (
                      <div className="space-y-6">
                        <div>
                          <h2 className="font-serif text-2xl font-medium text-[#252D49]">
                            Preferences for {wizardName}
                          </h2>
                          <p className="mt-1 text-xs text-stone-500">
                            Choose voice assignments and bridge features for this loved one.
                          </p>
                        </div>

                        <div className="space-y-3">
                          <div className="flex items-center justify-between rounded-2xl border border-[#9BA5FC]/20 bg-[#FAF8FF] p-4">
                            <div>
                              <p className="text-xs font-bold text-[#252D49]">Daily Wellbeing Signals</p>
                              <p className="text-[11px] text-stone-500">
                                Receive gentle AI reflections on their mood and conversation tone.
                              </p>
                            </div>
                            <input
                              type="checkbox"
                              checked={wizardEnableSignals}
                              onChange={(e) => setWizardEnableSignals(e.target.checked)}
                              className="h-4 w-4 accent-[#56619C]"
                            />
                          </div>

                          <div className="flex items-center justify-between rounded-2xl border border-[#9BA5FC]/20 bg-[#FAF8FF] p-4">
                            <div>
                              <p className="text-xs font-bold text-[#252D49]">Tone Memory</p>
                              <p className="text-[11px] text-stone-500">
                                Recall gentle vocal warmth cues across calls up to 72 hours.
                              </p>
                            </div>
                            <input
                              type="checkbox"
                              checked={wizardEnableTone}
                              onChange={(e) => setWizardEnableTone(e.target.checked)}
                              className="h-4 w-4 accent-[#56619C]"
                            />
                          </div>

                          <div className="flex items-center justify-between rounded-2xl border border-[#9BA5FC]/20 bg-[#FAF8FF] p-4">
                            <div>
                              <p className="text-xs font-bold text-[#252D49]">Call Summaries</p>
                              <p className="text-[11px] text-stone-500">
                                Keep brief digests of tea-time calls in your Family Room.
                              </p>
                            </div>
                            <input
                              type="checkbox"
                              checked={wizardEnableSummaries}
                              onChange={(e) => setWizardEnableSummaries(e.target.checked)}
                              className="h-4 w-4 accent-[#56619C]"
                            />
                          </div>
                        </div>

                        <div className="flex items-center justify-between pt-4">
                          <button
                            type="button"
                            onClick={() => setWizardStep(2)}
                            className="text-xs font-bold text-stone-500 hover:text-stone-800"
                          >
                            ← Back
                          </button>

                          <button
                            type="button"
                            disabled={wizardBusy}
                            onClick={handleCompleteWizard}
                            className="flex items-center gap-2 rounded-full bg-gradient-to-r from-[#72B5FE] to-[#B69CF2] px-8 py-3 text-sm font-bold text-white shadow-lg shadow-[#9BA5FC]/30 transition hover:scale-[1.02] hover:shadow-xl disabled:opacity-50"
                          >
                            {wizardBusy ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Sparkles className="h-4 w-4" />
                            )}
                            <span>Open Bridge for {wizardName}</span>
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.section>
              )}
            </AnimatePresence>
          </div>
        </>
      )}

      {/* ===================================================================== */}
      {/* PROFILE & VOICE MODAL (Triggered by Circular Avatar in Top Right)     */}
      {/* ===================================================================== */}
      <AnimatePresence>
        {isProfileModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsProfileModalOpen(false)}
              className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm"
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 10 }}
              className="relative z-10 max-h-[92vh] overflow-y-auto w-full max-w-2xl sm:max-w-3xl rounded-3xl border border-[#9BA5FC]/20 bg-white p-6 sm:p-8 shadow-2xl backdrop-blur-md"
            >
              {/* Header */}
              <div className="flex items-start justify-between border-b border-stone-100 pb-4">
                <div>
                  <h3 className="font-serif text-2xl font-medium text-[#252D49]">
                    Your Profile & Voice Settings
                  </h3>
                  <p className="mt-1 text-xs text-stone-500">
                    Manage your personal identity, gender phrasing, and voice bridge clone.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => setIsProfileModalOpen(false)}
                  className="rounded-full p-2 text-stone-400 hover:bg-stone-100 hover:text-stone-700 transition"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              {/* Tabs */}
              <div className="mt-5 flex gap-2 border-b border-stone-100 pb-3">
                <button
                  type="button"
                  onClick={() => setProfileModalTab("identity")}
                  className={`rounded-full px-5 py-2 text-xs font-bold transition-all ${
                    profileModalTab === "identity"
                      ? "bg-[#56619C] text-white shadow-md shadow-[#56619C]/20"
                      : "text-stone-600 hover:bg-stone-100"
                  }`}
                >
                  Personal Identity
                </button>
                <button
                  type="button"
                  onClick={() => setProfileModalTab("voice")}
                  className={`rounded-full px-5 py-2 text-xs font-bold transition-all ${
                    profileModalTab === "voice"
                      ? "bg-[#56619C] text-white shadow-md shadow-[#56619C]/20"
                      : "text-stone-600 hover:bg-stone-100"
                  }`}
                >
                  Carry Your Voice
                </button>
              </div>

              {/* TAB 1: PERSONAL IDENTITY */}
              {profileModalTab === "identity" && (
                <div className="mt-5 space-y-5">
                  {/* Avatar & Photo row */}
                  <div className="flex items-center gap-5 rounded-2xl border border-[#9BA5FC]/20 bg-[#F8F9FF] p-4">
                    <label className="group relative flex h-20 w-20 shrink-0 cursor-pointer items-center justify-center overflow-hidden rounded-full border-2 border-dashed border-[#9BA5FC]/40 bg-white shadow-sm transition hover:border-[#56619C]">
                      {photoUrl ? (
                        <>
                          <img src={photoUrl} alt="Avatar" className="h-full w-full object-cover" />
                          <div className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 transition group-hover:opacity-100">
                            <Camera className="h-5 w-5 text-white" />
                          </div>
                        </>
                      ) : (
                        <Camera className="h-7 w-7 text-[#9BA5FC]" />
                      )}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="sr-only"
                        disabled={photoBusy}
                        onChange={(e) => void handlePhotoFile(e.target.files?.[0])}
                      />
                    </label>

                    <div className="flex-1">
                      <p className="text-sm font-bold text-[#252D49]">Profile Photo</p>
                      <p className="text-xs text-stone-500">Stored locally on your browser for privacy.</p>
                      <div className="mt-2 flex items-center gap-3">
                        <label className="cursor-pointer rounded-full border border-[#9BA5FC]/30 bg-white px-3.5 py-1 text-xs font-semibold text-[#56619C] transition hover:bg-[#F2F4FD]">
                          {photoUrl ? "Change Photo" : "Upload Photo"}
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            className="sr-only"
                            disabled={photoBusy}
                            onChange={(e) => void handlePhotoFile(e.target.files?.[0])}
                          />
                        </label>
                        {photoUrl && (
                          <button
                            type="button"
                            onClick={handleRemovePhoto}
                            disabled={photoBusy}
                            className="text-xs font-semibold text-rose-600 hover:underline"
                          >
                            Remove photo
                          </button>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* Form Fields Grid */}
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div>
                      <label className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                        Your Name
                      </label>
                      <input
                        type="text"
                        value={childName}
                        onChange={(e) => setChildName(e.target.value)}
                        className="mt-1.5 w-full rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-2.5 text-sm font-medium focus:border-[#56619C] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                      />
                    </div>

                    <div>
                      <label className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                        Gender Phrasing
                      </label>
                      <select
                        value={childGender}
                        onChange={(e) => setChildGender(e.target.value as typeof childGender)}
                        className="mt-1.5 w-full rounded-2xl border border-stone-200 bg-stone-50/80 px-3.5 py-2.5 text-sm font-medium focus:border-[#56619C] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                      >
                        <option value="female">Female</option>
                        <option value="male">Male</option>
                        <option value="neutral">Neutral</option>
                      </select>
                    </div>

                    <div className="sm:col-span-2">
                      <label className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                        Notification Email
                      </label>
                      <input
                        type="email"
                        value={notificationEmail}
                        onChange={(e) => setNotificationEmail(e.target.value)}
                        placeholder="khushi@example.com"
                        className="mt-1.5 w-full rounded-2xl border border-stone-200 bg-stone-50/80 px-4 py-2.5 text-sm font-medium focus:border-[#56619C] focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#9BA5FC]/20"
                      />
                    </div>
                  </div>

                  {/* Footer */}
                  <div className="flex items-center justify-between border-t border-stone-100 pt-4">
                    <button
                      type="button"
                      onClick={() => {
                        localStorage.removeItem("hugback_onboarding_completed");
                        setHasCompletedProfile(false);
                        setIsProfileModalOpen(false);
                      }}
                      className="text-xs font-bold text-stone-400 hover:text-stone-700 transition"
                    >
                      Revisit Onboarding Flow
                    </button>

                    <div className="flex items-center gap-3">
                      {profileSavedToast && (
                        <span className="text-xs font-bold text-emerald-700">
                          ✓ Profile updated!
                        </span>
                      )}
                      <button
                        type="button"
                        disabled={profileSaving}
                        onClick={handleSaveProfile}
                        className="flex items-center gap-2 rounded-full bg-[#56619C] px-6 py-2.5 text-xs font-bold text-white shadow-md shadow-[#56619C]/20 transition hover:bg-[#465181]"
                      >
                        {profileSaving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                        Save Changes
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: CARRY YOUR VOICE */}
              {profileModalTab === "voice" && (
                <div className="mt-5 space-y-4">
                  {/* Status Banner */}
                  {status?.voice?.profile && (
                    <div className="flex items-center justify-between rounded-2xl border border-emerald-200 bg-emerald-50/90 p-3.5 text-xs">
                      <div className="flex items-center gap-2.5">
                        <CheckCircle2 className="h-4 w-4 text-emerald-600" />
                        <span className="font-bold text-emerald-900">Your Voice Model is Active</span>
                        <span className="text-emerald-700 text-xs hidden sm:inline">· Ready for your family bridges</span>
                      </div>
                      <span className="rounded-full bg-white px-3 py-1 text-[11px] font-bold text-emerald-800 shadow-xs">
                        Ready
                      </span>
                    </div>
                  )}

                  {/* Two Audio Recorders one below the other */}
                  <div className="space-y-4">
                    <PulsingAudioRecorder
                      disabled={voiceEnrolling}
                      compact={true}
                      label="1. Voice Sample (20-30s)"
                      minimumSeconds={10}
                      promptText="Namaste Maa, I'm having a quiet evening here with a cup of tea, thinking about our garden back home…"
                      onRecorded={(file) => setVoiceSampleFile(file)}
                    />

                    <PulsingAudioRecorder
                      disabled={voiceEnrolling}
                      compact={true}
                      label="2. Consent Recording (2-5s)"
                      minimumSeconds={2}
                      promptText="I am the owner of this voice and I consent to HugBack creating a synthetic voice model for family check-in calls."
                      onRecorded={(file) => setConsentFile(file)}
                    />
                  </div>

                  {/* Consent & Update Row */}
                  <div className="flex flex-wrap items-center justify-between gap-4 border-t border-stone-100 pt-4">
                    <label className="flex items-center gap-2.5 text-xs leading-relaxed text-[#454E6D] max-w-md">
                      <input
                        type="checkbox"
                        checked={voiceConsentAcknowledged}
                        onChange={(e) => setVoiceConsentAcknowledged(e.target.checked)}
                        className="h-4 w-4 rounded accent-[#56619C] shrink-0"
                      />
                      <span>I am 18 or older, this is my voice, and I authorize HugBack voice synthesis.</span>
                    </label>

                    <div className="flex items-center gap-3">
                      {voiceToast && (
                        <span className="text-xs font-semibold text-[#315F89]">
                          {voiceToast}
                        </span>
                      )}
                      <button
                        type="button"
                        disabled={
                          voiceEnrolling ||
                          !voiceSampleFile ||
                          !consentFile ||
                          !voiceConsentAcknowledged
                        }
                        onClick={handleCreateVoice}
                        className="flex items-center gap-2 rounded-full bg-gradient-to-r from-[#9BA5FC] to-[#B69CF2] px-6 py-2.5 text-xs font-bold text-white shadow-md shadow-[#9BA5FC]/25 transition hover:scale-[1.02] disabled:opacity-40"
                      >
                        {voiceEnrolling ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Sparkles className="h-3.5 w-3.5" />
                        )}
                        <span>Update Voice Model</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* ===================================================================== */}
      {/* DAILY SIGNALS & CALL HISTORY MODAL                                    */}
      {/* ===================================================================== */}
      <AnimatePresence>
        {signalsModalRecipient && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setSignalsModalRecipient(null)}
              className="fixed inset-0 bg-stone-900/40 backdrop-blur-sm"
            />

            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="relative z-10 max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-3xl border border-[#9BA5FC]/20 bg-white p-6 shadow-2xl sm:p-8"
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-[10px] font-extrabold uppercase tracking-widest text-[#56619C]">
                    Daily Signals & Check-ins
                  </span>
                  <h3 className="font-serif text-2xl font-medium text-[#252D49]">
                    {signalsModalRecipient.label}’s Bridge
                  </h3>
                </div>

                <button
                  type="button"
                  onClick={() => setSignalsModalRecipient(null)}
                  className="rounded-full p-2 text-stone-400 hover:bg-stone-100 hover:text-stone-700"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>

              <div className="mt-6 rounded-2xl border border-[#C7E6FF] bg-[#EDF7FF] p-5">
                <span className="text-[11px] font-extrabold uppercase tracking-wider text-[#315F89]">
                  Conversation Signal
                </span>
                <p className="mt-2 font-serif text-xl font-medium text-[#1F253B]">
                  {signalsModalRecipient.wellbeingSignals?.at(-1)?.displayText ||
                    "No signals recorded yet. After the next check-in call, updates will appear here."}
                </p>
                <p className="mt-1 text-[11px] text-stone-500">
                  AI-estimated from verbal tone and conversational ease · Not a medical diagnosis
                </p>
              </div>

              <div className="mt-6">
                <h4 className="text-xs font-bold uppercase tracking-wider text-[#56619C]">
                  Call History ({signalsModalRecipient.calls.length})
                </h4>

                <div className="mt-3 space-y-3">
                  {signalsModalRecipient.calls.length > 0 ? (
                    signalsModalRecipient.calls.slice().reverse().map((call) => (
                      <div
                        key={call.sessionId}
                        className="rounded-2xl border border-stone-200 bg-stone-50/70 p-4 text-xs"
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[#252D49]">
                            {readableCallStatus(call.status)}
                          </span>
                          <span className="text-[11px] text-stone-400">
                            {formatDate(call.startedAt)}
                          </span>
                        </div>

                        {callSummariesCache[call.sessionId] ? (
                          <div className="mt-3 rounded-xl border border-stone-200 bg-white p-3 text-stone-700">
                            <p className="font-bold text-[#56619C]">Call Summary:</p>
                            <p className="mt-1">{callSummariesCache[call.sessionId].summary}</p>
                          </div>
                        ) : (
                          <button
                            type="button"
                            onClick={() =>
                              fetchSummary(signalsModalRecipient.recipientId, call.sessionId)
                            }
                            disabled={loadingSummaryId === call.sessionId}
                            className="mt-2 text-[11px] font-bold text-[#56619C] hover:underline"
                          >
                            {loadingSummaryId === call.sessionId
                              ? "Loading summary…"
                              : "Read call digest →"}
                          </button>
                        )}
                      </div>
                    ))
                  ) : (
                    <p className="rounded-2xl border border-dashed border-stone-200 p-6 text-center text-xs text-stone-500">
                      No calls logged yet for {signalsModalRecipient.label}.
                    </p>
                  )}
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Gentle Footer */}
      <footer className="mt-20 border-t border-[#9BA5FC]/15 py-8 text-xs text-stone-500">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 sm:px-8">
          <p className="flex items-center gap-2">
            <LockKeyhole className="h-4 w-4 text-[#56619C]" />
            HugBack is a family AI voice bridge. Your privacy and voice rights are sacred.
          </p>
          <p>© {new Date().getFullYear()} HugBack AI. Deeply human family connections.</p>
        </div>
      </footer>
    </main>
  );
}
