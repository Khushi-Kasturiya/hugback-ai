"use client";

import React, { useEffect, useRef, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useLiveAudio } from "@/hooks/useLiveAudio";
import { parentCallUrl } from "@/lib/demo-api";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import {
  AlertCircle,
  ArrowLeft,
  ChevronDown,
  Mic,
  Phone,
  PhoneOff,
  Sparkles,
  Volume2,
} from "lucide-react";
import { loadChildPhoto } from "@/lib/portal-storage";

export function CallTest() {
  const [showSubtitles, setShowSubtitles] = useState(true);
  const params = useSearchParams();
  const router = useRouter();
  const demoParent = process.env.NEXT_PUBLIC_HUGBACK_DEMO_MODE === "true";
  const recipientId = params.get("recipient") || "";
  const demo = useDemoFamily(demoParent === true);
  const wasCallActive = useRef(false);
  const transcriptBox = useRef<HTMLDivElement>(null);
  const [childPhotoUrl, setChildPhotoUrl] = useState<string>("");
  const [workflowAcknowledged, setWorkflowAcknowledged] = useState(false);

  const childName = demoParent ? demo.family?.childName?.trim() || "Khushi" : "HugBack";
  const childInitial = (childName[0] || "K").toUpperCase();

  // Load child photo from local storage / IndexedDB
  useEffect(() => {
    if (!demo.family?.familyId) return;
    let objectUrl = "";
    loadChildPhoto(demo.family.familyId)
      .then((blob) => {
        if (!blob) return;
        objectUrl = URL.createObjectURL(blob);
        setChildPhotoUrl(objectUrl);
      })
      .catch(() => {});
    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [demo.family?.familyId]);

  const recipient = demo.family?.recipients.find((item) => item.recipientId === recipientId);

  useEffect(() => { setWorkflowAcknowledged(false); }, [recipientId]);

  const {
    status,
    errorMessage,
    transcriptEntries,
    userVolume,
    hugbackVolume,
    isCallActive,
    startCall,
    endCall,
  } = useLiveAudio({
    demoParent: demoParent === true,
    recipientId: recipient?.recipientId,
    workflowAcknowledged,
  });

  const canStart = !!recipient && !recipient.busy && !demo.error && workflowAcknowledged;
  const startSelectedCall = () => {
    if (canStart) void startCall();
  };

  useEffect(() => {
    if (demoParent && wasCallActive.current && !isCallActive) {
      setWorkflowAcknowledged(false);
      void demo.refresh();
    }
    wasCallActive.current = isCallActive;
  }, [demoParent, isCallActive, demo.refresh]);

  useEffect(() => {
    if (!showSubtitles || !transcriptBox.current) return;
    transcriptBox.current.scrollTop = transcriptBox.current.scrollHeight;
  }, [showSubtitles, transcriptEntries]);

  // Clean, immersive status display
  const getStatusDisplay = () => {
    switch (status) {
      case "connecting":
        return {
          title: "Connecting...",
          desc: "Starting voice line with HugBack",
          color: "text-amber-700",
        };
      case "speaking":
        return {
          title: "HugBack is Speaking",
          desc: "Speak anytime to interrupt naturally",
          color: "text-emerald-700",
        };
      case "listening":
        return {
          title: "HugBack is Listening",
          desc: "Go ahead, I'm listening to you",
          color: "text-[#56619C]",
        };
      case "interrupted":
        return {
          title: "Listening to You",
          desc: "HugBack paused to hear you",
          color: "text-blue-700",
        };
      case "error":
        return {
          title: "Connection Error",
          desc: errorMessage || "Please check backend connection",
          color: "text-rose-700",
        };
      default:
        if (recipient?.busy) {
          return {
            title: "Finishing Prior Call",
            desc: "Saving memory insights before next session",
            color: "text-amber-800",
          };
        }
        if (demoParent && !recipient && !demo.loading) {
          return {
            title: "Select a Recipient",
            desc: "Choose who is answering in the demo role above",
            color: "text-stone-700",
          };
        }
        return {
          title: "Ready to Connect",
          desc: "Tap Answer Call to start speaking",
          color: "text-[#252D49]",
        };
    }
  };

  const statusInfo = getStatusDisplay();

  // Orb scaling calculation
  const orbScale = isCallActive
    ? status === "speaking"
      ? 1 + hugbackVolume * 0.25
      : 1 + userVolume * 0.35
    : 1;

  return (
    <main className="relative flex min-h-screen flex-col justify-between overflow-x-hidden bg-gradient-to-b from-[#FFFDF9] via-[#F5F2FC] to-[#B69CF2]/35 text-[#252D49] selection:bg-[#9BA5FC]/30">
      {/* Ambient background glows */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -left-28 top-16 h-96 w-96 rounded-full bg-[#D8EEFF]/60 blur-3xl"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -right-28 bottom-20 h-96 w-96 rounded-full bg-[#E5DDFC]/60 blur-3xl"
      />

      {/* Top Floating Navigation Bar */}
      <header className="relative z-30 mx-auto flex w-full max-w-5xl items-center justify-between gap-4 px-5 py-4 sm:px-8">
        <Link href="/" className="flex items-center gap-2.5 transition hover:opacity-90" aria-label="HugBack home">
          <Image
            src="/logo.png"
            width={727}
            height={343}
            priority
            alt="HugBack logo"
            className="h-8 w-auto object-contain sm:h-9"
          />
          <Image
            src="/hugback.png"
            width={983}
            height={254}
            priority
            alt="HugBack AI"
            className="h-auto w-24 sm:w-28"
          />
        </Link>

        {/* Minimal Floating Demo Role Pill */}
        {demoParent && (
          <div className="flex items-center gap-2.5">
            <div className="relative flex items-center rounded-full border border-white/90 bg-white/85 px-3 py-1.5 shadow-[0_4px_20px_rgba(86,97,156,0.08)] backdrop-blur-md">
              <span className="flex items-center gap-1.5 text-xs font-semibold text-[#56619C]">
                <span className="text-sm">⚙️</span>
                <span className="hidden sm:inline">Demo Role:</span>
              </span>

              <div className="relative ml-1.5">
                <select
                  aria-label="Demo Role"
                  value={recipient?.recipientId || ""}
                  disabled={isCallActive}
                  onChange={(event) => {
                    setWorkflowAcknowledged(false);
                    if (event.target.value) {
                      router.replace(parentCallUrl(event.target.value));
                    }
                  }}
                  className="cursor-pointer appearance-none rounded-full bg-[#F3F4FB] py-1 pl-3 pr-7 text-xs font-bold text-[#252D49] outline-none transition hover:bg-[#EAEBFA] focus:ring-2 focus:ring-[#9BA5FC]/30"
                >
                  <option value="">Choose recipient</option>
                  {demo.family?.recipients?.map((item) => (
                    <option key={item.recipientId} value={item.recipientId}>
                      {item.label} {item.busy ? "· busy" : ""}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-2 top-2 h-3 w-3 text-stone-500" />
              </div>

              {/* Discreet Info Tooltip (ℹ️) */}
              {recipient && (
                <div className="group relative ml-1.5">
                  <button
                    type="button"
                    className="flex h-5 w-5 items-center justify-center rounded-full text-stone-400 transition hover:bg-stone-100 hover:text-[#56619C]"
                    aria-label="Role information"
                  >
                    <span className="text-[11px] font-bold">ℹ️</span>
                  </button>
                  <div className="pointer-events-none absolute right-0 top-full z-50 mt-2 w-64 rounded-2xl border border-stone-200 bg-white/95 p-3.5 text-[11px] leading-relaxed text-stone-600 opacity-0 shadow-xl backdrop-blur-xl transition-opacity group-hover:pointer-events-auto group-hover:opacity-100">
                    <p className="font-bold text-[#252D49]">{recipient.label}</p>
                    <p className="mt-1 text-stone-500">
                      Voice: {recipient.voice.mode === "child" ? "Assigned child voice model" : "Standard HugBack AI voice"}
                    </p>
                    <p className="mt-1 text-stone-500">
                      Context: {recipient.background.length} excerpts · {recipient.memoryCount} retained memories
                    </p>
                    <p className="mt-2 text-[10px] text-stone-400">
                      Role-play preview mode with clear AI disclosure.
                    </p>
                  </div>
                </div>
              )}
            </div>

            {!isCallActive && (
              <Link
                href="/childportal"
                className="hidden items-center gap-1.5 rounded-full border border-white/80 bg-white/75 px-3.5 py-1.5 text-xs font-semibold text-[#56619C] shadow-sm backdrop-blur-md transition hover:bg-white sm:inline-flex"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                <span>Child Portal</span>
              </Link>
            )}
          </div>
        )}
      </header>

      {/* Centered Device / Ambient Phone Screen */}
      <div className="relative z-20 flex flex-1 items-center justify-center px-4 py-6 sm:py-8">
        <div className="relative w-full max-w-[420px] overflow-hidden rounded-[40px] border border-white/80 bg-white/85 p-6 shadow-[0_30px_90px_rgba(86,97,156,0.16)] backdrop-blur-2xl transition-all sm:p-8">
          {/* Subtle Ambient Orb Glow inside device */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute left-1/2 top-28 h-64 w-64 -translate-x-1/2 rounded-full bg-gradient-to-br from-[#D8EEFF] via-[#E1E3FF] to-[#EADFFC] opacity-80 blur-3xl"
          />

          {/* Device Header Bar */}
          <div className="relative flex items-center justify-between border-b border-[#E7E9F3]/80 pb-3.5">
            <div className="flex items-center gap-2.5">
              <span
                className={`h-2.5 w-2.5 rounded-full ${
                  isCallActive
                    ? "animate-pulse bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]"
                    : "bg-[#9BA5FC]"
                }`}
              />
              <div>
                <p className="font-serif text-sm font-bold text-[#252D49]">
                  Voice Bridge: Active
                </p>
                <p className="text-[10px] text-stone-400">
                  {recipient?.label ? `Connected for ${recipient.label}` : "Family Connected"}
                </p>
              </div>
            </div>

            <button
              onClick={() => setShowSubtitles((prev) => !prev)}
              className="rounded-full border border-[#DDE2F0] bg-white/90 px-2.5 py-1 text-[10px] font-bold text-[#56619C] shadow-2xs transition hover:bg-[#F3F4FB]"
            >
              {showSubtitles ? "Hide words" : "Show words"}
            </button>
          </div>

          {/* Central Device Screen Content */}
          <div className="relative flex flex-col items-center pt-5 text-center">
            {/* AI Clearly Disclosed Badge */}
            <span className="inline-flex items-center gap-1.5 rounded-full border border-[#DDE2F0] bg-white/90 px-3 py-1 text-[10px] font-extrabold uppercase tracking-[0.14em] text-[#56619C] shadow-2xs">
              <Sparkles className="h-3 w-3 text-[#9BA5FC]" />
              <span>AI clearly disclosed</span>
            </span>

            {/* Prompt Line */}
            <p className="relative mt-4 max-w-xs font-serif text-xl leading-snug text-[#252D49] sm:text-2xl">
              {isCallActive
                ? status === "speaking"
                  ? `${childName} is speaking…`
                  : "Listening warmly—take your time…"
                : `Ready for your chat with ${childName}`}
            </p>

            {/* Child's Avatar surrounded by Glowing Concentric Rings */}
            <div className="relative my-6 flex h-52 w-52 items-center justify-center sm:h-56 sm:w-56">
              {/* Outer expanding animated voice rings */}
              <span
                className={`absolute h-48 w-48 rounded-full border-2 border-[#9BA5FC]/30 transition-transform duration-700 sm:h-52 sm:w-52 ${
                  isCallActive ? "animate-ping opacity-60" : "animate-pulse opacity-45"
                }`}
              />
              <span className="absolute h-40 w-40 rounded-full border border-[#9BA5FC]/40 transition-transform duration-500 sm:h-44 sm:w-44" />
              <span className="absolute h-34 w-34 rounded-full border border-white/90 bg-white/40 shadow-[0_0_60px_rgba(155,165,252,0.35)] sm:h-38 sm:w-38" />

              {/* Child Avatar Button */}
              <button
                type="button"
                aria-label={isCallActive ? "End current call" : "Answer call"}
                disabled={!isCallActive && !canStart}
                onClick={isCallActive ? endCall : startSelectedCall}
                style={{ transform: `scale(${orbScale})` }}
                className="group relative flex h-32 w-32 items-center justify-center rounded-full p-1 shadow-[0_20px_50px_rgba(86,97,156,0.3)] transition-all duration-300 hover:scale-105 sm:h-36 sm:w-36 disabled:cursor-not-allowed"
              >
                {/* Gradient ring border */}
                <div className="h-full w-full overflow-hidden rounded-full border-2 border-white/90 bg-gradient-to-tr from-[#72B5FE] via-[#9BA5FC] to-[#B69CF2] shadow-inner">
                  {childPhotoUrl ? (
                    <img
                      src={childPhotoUrl}
                      alt={childName}
                      className="h-full w-full object-cover transition duration-300 group-hover:scale-105"
                    />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center bg-gradient-to-br from-[#9BA5FC] to-[#B69CF2] font-serif text-5xl font-medium text-white shadow-inner">
                      {childInitial}
                    </div>
                  )}
                </div>

                {/* Floating State Badge on bottom-right */}
                {isCallActive ? (
                  <span className="absolute -bottom-1 -right-1 grid h-8 w-8 place-items-center rounded-full bg-emerald-500 text-white shadow-md ring-2 ring-white">
                    {status === "speaking" ? (
                      <Volume2 className="h-4 w-4" />
                    ) : (
                      <Mic className="h-4 w-4 animate-pulse" />
                    )}
                  </span>
                ) : (
                  <span className="absolute -bottom-1 -right-1 grid h-8 w-8 place-items-center rounded-full bg-emerald-600 text-white shadow-md ring-2 ring-white transition group-hover:scale-110">
                    <Phone className="h-3.5 w-3.5 fill-white" />
                  </span>
                )}
              </button>
            </div>

            {/* Status Text (Cleaned up, no developer warnings!) */}
            <div>
              <h2 className={`text-xl font-bold tracking-tight sm:text-2xl ${statusInfo.color}`}>
                {statusInfo.title}
              </h2>
              <p className="mt-1 text-xs font-medium text-stone-500">
                {statusInfo.desc}
              </p>
            </div>

            {/* Live Volume Meter during Call */}
            {isCallActive && (
              <div className="relative mt-4 w-full max-w-xs" aria-label="Microphone input level">
                <div className="flex justify-between text-[11px] font-medium text-stone-500">
                  <span>Microphone level</span>
                  <span>Volume only</span>
                </div>
                <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-[#E2E5F1]">
                  <div
                    className="h-full rounded-full bg-[#7284D5] transition-[width] duration-150"
                    style={{ width: `${Math.max(0, Math.min(100, userVolume * 100))}%` }}
                  />
                </div>
              </div>
            )}

            {/* Error Message */}
            {errorMessage && (
              <div className="relative mt-4 flex max-w-sm items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-3.5 py-2.5 text-left text-xs font-medium text-rose-800">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            {!isCallActive && recipient && (
              <label className="relative mt-5 flex w-full max-w-xs items-start gap-2 rounded-xl border border-[#DDE2F0] bg-white/90 p-3 text-left text-xs leading-5 text-stone-700">
                <input type="checkbox" checked={workflowAcknowledged} onChange={(event) => setWorkflowAcknowledged(event.target.checked)} className="mt-1" />
                <span>This is a fictional test call. I agree that HugBack may process its synthetic speech and context with Google AI, including Planner and Critic when enabled.</span>
              </label>
            )}

            {/* Live Call Transcript / Subtitles Box */}
            {showSubtitles && (isCallActive || transcriptEntries.length > 0) && (
              <div
                ref={transcriptBox}
                aria-label="Live call words"
                className="relative mt-5 max-h-36 w-full space-y-2 overflow-y-auto rounded-2xl border border-[#E2E5F1] bg-white/85 p-3.5 text-left text-xs shadow-xs"
              >
                {transcriptEntries.map((entry, index) => (
                  <p key={index} className="leading-relaxed">
                    <span
                      className={`font-bold ${
                        entry.role === "user" ? "text-[#56619C]" : "text-[#7664AD]"
                      }`}
                    >
                      {entry.role === "user" ? "You: " : "HugBack: "}
                    </span>
                    <span className="text-stone-700">{entry.text}</span>
                  </p>
                ))}
                {!transcriptEntries.length && (
                  <p className="text-center text-[11px] italic text-stone-400">
                    Spoken conversation will appear here…
                  </p>
                )}
              </div>
            )}

            {/* Bottom Immersive Active Call Button */}
            <div className="mt-6 w-full">
              {!isCallActive ? (
                <button
                  type="button"
                  onClick={startSelectedCall}
                  disabled={!canStart}
                  className="mx-auto flex w-full max-w-xs items-center justify-center gap-2.5 rounded-full bg-emerald-600 px-7 py-3.5 text-base font-bold text-white shadow-[0_12px_28px_rgba(22,163,74,0.3)] transition hover:-translate-y-0.5 hover:bg-emerald-700 hover:shadow-[0_16px_36px_rgba(22,163,74,0.4)] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0"
                >
                  <Phone className="h-5 w-5 fill-white" />
                  <span>Answer Call</span>
                </button>
              ) : (
                <button
                  type="button"
                  onClick={endCall}
                  className="mx-auto flex w-full max-w-xs items-center justify-center gap-2.5 rounded-full bg-rose-600 px-7 py-3.5 text-base font-bold text-white shadow-[0_12px_28px_rgba(225,29,72,0.3)] transition hover:-translate-y-0.5 hover:bg-rose-700"
                >
                  <PhoneOff className="h-5 w-5" />
                  <span>End Call</span>
                </button>
              )}
              <p className="mt-2.5 text-[11px] text-stone-400">
                Tap once to begin · You can end the call at any time
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Discreet bottom footer */}
      <footer className="relative z-10 pb-4 text-center text-[11px] text-[#56619C]/60">
        HugBack AI · Family Voice Bridge Preview
      </footer>
    </main>
  );
}
