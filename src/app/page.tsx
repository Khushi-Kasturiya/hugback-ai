"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useLiveAudio } from "@/hooks/useLiveAudio";
import { parentCallUrl } from "@/lib/demo-api";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import { Phone, PhoneOff, Mic, Volume2, AlertCircle } from "lucide-react";
import Link from "next/link";

export default function Home() {
  return <Suspense fallback={<main className="p-8 text-stone-600">Loading call test…</main>}><CallTest /></Suspense>;
}

function CallTest() {
  const [showSubtitles, setShowSubtitles] = useState(true);
  const params = useSearchParams();
  const router = useRouter();
  const demoParent = params.get("demo") === "parent";
  const recipientId = params.get("recipient") || "";
  const [demoAcknowledged, setDemoAcknowledged] = useState(false);
  const demo = useDemoFamily(demoParent === true);
  const wasCallActive = useRef(false);

  const recipient = demo.family?.recipients.find((item) => item.recipientId === recipientId);
  useEffect(() => { setDemoAcknowledged(false); }, [recipientId]);

  const {
    status,
    errorMessage,
    userTranscript,
    hugbackTranscript,
    userVolume,
    hugbackVolume,
    isCallActive,
    startCall,
    endCall,
    callInfo,
  } = useLiveAudio({ demoParent: demoParent === true, recipientId });
  const canStart = !demoParent ||
    (demoAcknowledged && !!recipient && !recipient.busy && !demo.error);
  const startSelectedCall = () => { if (canStart) void startCall(); };
  useEffect(() => {
    if (demoParent && wasCallActive.current && !isCallActive) void demo.refresh();
    wasCallActive.current = isCallActive;
  }, [demoParent, isCallActive, demo.refresh]);

  // Status message text
  const getStatusDisplay = () => {
    switch (status) {
      case "connecting":
        return { title: "Connecting...", desc: "Starting voice line with Hugback", color: "text-amber-700" };
      case "speaking":
        return { title: "Hugback is Speaking", desc: "Speak at any time to interrupt", color: "text-emerald-700" };
      case "listening":
        return { title: "Hugback is Listening", desc: "Go ahead, I'm listening to you", color: "text-amber-800" };
      case "interrupted":
        return { title: "You Interrupted", desc: "Hugback paused to listen to you", color: "text-blue-700" };
      case "error":
        return { title: "Connection Error", desc: errorMessage || "Please check backend", color: "text-rose-700" };
      default:
        if (demoParent && !canStart) {
          return { title: recipient?.busy ? "Finishing the Previous Call" : "Prepare Your Demo Call",
            desc: recipient?.busy ? "Waiting for its memory update before the next call" :
              demo.family ? (recipient ? `Confirm role-play as ${recipient.label} above` : "Choose the recipient you are role-playing") : "Complete Child setup first",
            color: "text-stone-700" };
        }
        return { title: "Ready to Call", desc: "Tap the big button below to begin", color: "text-stone-700" };
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
    <main className="flex min-h-screen max-w-3xl flex-col items-center justify-between p-6 sm:p-10 mx-auto">
      {/* Top Header */}
      <header className="w-full flex items-center justify-between gap-4 pt-2 pb-4 border-b border-stone-200/80">
        <div className="flex items-center gap-3">
          <Image src="/logo.png" width={727} height={343} priority alt="" className="h-8 w-[4.25rem] object-contain sm:h-11 sm:w-[5.8rem]" />
          <div>
            <Image src="/hugback.png" width={983} height={254} priority alt="Hugback AI" className="h-auto w-28 sm:w-40" />
            <p className="hidden text-xs text-stone-500 font-medium sm:block">Google Cloud AI Companion • Phase 1</p>
          </div>
        </div>

        <button
          onClick={() => setShowSubtitles((prev) => !prev)}
          className="shrink-0 text-xs font-semibold px-3 py-1.5 rounded-full border border-stone-300 bg-white/80 text-stone-600 hover:border-amber-300 hover:bg-amber-50 transition-colors"
        >
          {showSubtitles ? "Hide Subtitles" : "Show Subtitles"}
        </button>
      </header>

      {demoParent && <section className="mt-6 w-full rounded-2xl border border-emerald-200 bg-emerald-50/70 p-5 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-bold text-emerald-900">Hackathon · Parent call test</h2>
          {!isCallActive && <Link href="/childportal" className="font-semibold text-emerald-800 underline">← Child setup</Link>}
        </div>
        <p className="mt-2 leading-6 text-stone-600">Choose exactly one recipient for this call. Their background and memory stay separate from everyone else’s, even when Hugback uses the same child voice. End the call before another person takes over; speaker identity is not verified.</p>
        {demo.family && <label className="portal-label mt-4 block">Call recipient
          <select className="portal-input" aria-label="Call recipient" value={recipient?.recipientId || ""} disabled={isCallActive} onChange={(event) => { setDemoAcknowledged(false); router.replace(parentCallUrl(event.target.value)); }}>
            <option value="">Choose a recipient</option>
            {demo.family.recipients.map((item) => <option key={item.recipientId} value={item.recipientId}>{item.label}{item.busy ? " · busy" : ""}</option>)}
          </select>
        </label>}
        {recipientId && demo.family && !recipient && <p role="alert" className="mt-3 text-rose-800">This recipient is not in your demo family. Choose an available recipient; no call can start.</p>}
        {recipient && <div className="mt-3 space-y-2">
          <p className="font-bold text-emerald-900">Calling as {recipient.label} · {recipient.voice.mode === "child" ? "Assigned child voice" : "Standard Hugback voice"}</p>
          <p>{recipient.background.length} reviewed background excerpts · {recipient.memoryCount} retained wellbeing records</p>
          <p className="break-all text-xs text-stone-500">Recipient: {recipient.recipientId}</p>
          <p className="text-xs text-stone-600">{recipient.memoryEnabled ? `Memory enabled: new concerns may be followed up in the next call. Once selected, follow-ups have a ${recipient.memoryCooldownHours}-hour cooldown.` : "Memory is off or paused. Calls do not enable it automatically."}</p>
          {recipient.busy && !isCallActive && <p role="status" className="font-semibold text-amber-800">Previous call active or saving memory. Please wait; this view refreshes automatically.</p>}
          {recipient.calls.length > 0 && <p className="text-xs text-stone-600">Last session: {recipient.calls.at(-1)?.status.replaceAll("_", " ")}. No transcript or recap is shared here.</p>}
          {recipient.calls.at(-1)?.status === "memory_failed" && <p role="alert" className="text-rose-800">The last call’s memory update failed. Do not assume it was remembered; check the backend’s extraction model configuration.</p>}
        </div>}
        {!demo.family && !demo.loading && !demo.error && <p className="mt-3">Create a local demo family in <Link className="underline" href="/childportal">Child setup</Link> first.</p>}
        {demo.error && <p role="alert" className="mt-3 text-rose-800">{demo.error}</p>}
        {callInfo && callInfo.parentId === recipient?.recipientId && <p className="mt-3 break-all text-xs text-stone-500">Call: {callInfo.sessionId} · Memory: {callInfo.memoryStatus} · Voice: {callInfo.voice}</p>}
        <label className="mt-4 flex items-start gap-3 leading-6">
          <input type="checkbox" className="mt-1.5 shrink-0" checked={demoAcknowledged} disabled={isCallActive} onChange={(e) => setDemoAcknowledged(e.target.checked)} />
          I will role-play only as {recipient?.label || "the selected recipient"}, using fictional details. I will end the call before switching people. Starting this call sends microphone audio and reviewed demo context to Google; enabled memory also processes the demo transcript. Configured provider usage may incur charges. Hugback is AI, not my child.
        </label>
      </section>}

      {/* Center Interactive Orb & Visual Feedback */}
      <section className="flex flex-col items-center justify-center my-auto w-full py-10">
        {/* Animated Breathing Orb */}
        <div className="relative flex items-center justify-center w-64 h-64 sm:w-80 sm:h-80">
          {/* Subtle Outer Glow */}
          <div
            className={`absolute inset-0 rounded-full transition-all duration-300 blur-2xl opacity-40 ${
              status === "speaking"
                ? "bg-emerald-300"
                : isCallActive
                ? "bg-amber-300"
                : "bg-stone-300"
            }`}
            style={{ transform: `scale(${orbScale * 1.15})` }}
          />

          {/* Core Orb */}
          <button
            type="button"
            aria-label={isCallActive ? "End current call" : "Start selected call"}
            disabled={!isCallActive && !canStart}
            className={`relative w-48 h-48 sm:w-56 sm:h-56 rounded-full flex flex-col items-center justify-center shadow-xl transition-all duration-200 cursor-pointer select-none disabled:cursor-not-allowed ${
              status === "speaking"
                ? "bg-gradient-to-tr from-hugback-indigo via-hugback-periwinkle to-hugback-sky text-white"
                : isCallActive
                ? "bg-gradient-to-tr from-hugback-sky via-hugback-periwinkle to-hugback-violet text-stone-900"
                : "bg-gradient-to-tr from-stone-200 to-stone-100 text-stone-600 border border-stone-300"
            }`}
            style={{ transform: `scale(${orbScale})` }}
            onClick={isCallActive ? endCall : startSelectedCall}
          >
            {isCallActive ? (
              status === "speaking" ? (
                <Volume2 className="w-16 h-16 animate-bounce" />
              ) : (
                <Mic className="w-16 h-16 animate-pulse" />
              )
            ) : (
              <Phone className="w-16 h-16" />
            )}
          </button>
        </div>

        {/* Big Legible Status Text */}
        <div className="text-center mt-8">
          <h2 className={`text-2xl sm:text-3xl font-extrabold tracking-tight ${statusInfo.color}`}>
            {statusInfo.title}
          </h2>
          <p className="text-base sm:text-lg text-stone-600 mt-2 font-medium">
            {statusInfo.desc}
          </p>
        </div>

        {/* Error notification banner */}
        {errorMessage && (
          <div className="mt-6 flex items-center gap-2 px-4 py-2.5 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-sm font-medium">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{errorMessage}</span>
          </div>
        )}
      </section>

      {/* Live Transcript / Subtitles Section */}
      {showSubtitles && (isCallActive || hugbackTranscript || userTranscript) && (
        <section className="w-full bg-white/90 backdrop-blur rounded-2xl p-5 border border-stone-200 shadow-sm mb-6 max-h-48 overflow-y-auto space-y-3">
          {userTranscript && (
            <div className="text-sm">
              <span className="font-bold text-amber-800">You: </span>
              <span className="text-stone-800">{userTranscript}</span>
            </div>
          )}
          {hugbackTranscript && (
            <div className="text-sm">
              <span className="font-bold text-emerald-800">Hugback: </span>
              <span className="text-stone-800">{hugbackTranscript}</span>
            </div>
          )}
          {!userTranscript && !hugbackTranscript && (
            <p className="text-xs text-stone-400 italic text-center">
              Transcripts will appear here in real-time as you converse...
            </p>
          )}
        </section>
      )}

      {!isCallActive && (
        <Link href="/childportal" className="mb-6 rounded-full border border-stone-300 px-5 py-2.5 text-sm font-semibold text-stone-700 hover:bg-white">
          Child portal · Voice, background &amp; summaries
        </Link>
      )}

      {/* Accessible Action Controls */}
      <footer className="w-full flex items-center justify-center gap-4 pb-4">
        {!isCallActive ? (
          <button
            onClick={startSelectedCall}
            disabled={!canStart}
            className="w-full sm:w-auto min-w-[240px] px-8 py-5 rounded-full bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-bold text-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-3 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <Phone className="w-6 h-6" />
            <span>{demoParent ? "Call as demo parent" : "Call Hugback"}</span>
          </button>
        ) : (
          <button
            onClick={endCall}
            className="w-full sm:w-auto min-w-[240px] px-8 py-5 rounded-full bg-rose-600 hover:bg-rose-700 active:scale-95 text-white font-bold text-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-3"
          >
            <PhoneOff className="w-6 h-6" />
            <span>End Call</span>
          </button>
        )}
      </footer>
    </main>
  );
}
