"use client";

import React, { useState } from "react";
import { useLiveAudio } from "@/hooks/useLiveAudio";
import { Phone, PhoneOff, Mic, Volume2, Sparkles, AlertCircle } from "lucide-react";
import { VoiceEnrollment } from "@/components/VoiceEnrollment";

export default function Home() {
  const [showSubtitles, setShowSubtitles] = useState(true);

  const {
    status,
    errorMessage,
    userTranscript,
    elaraTranscript,
    userVolume,
    elaraVolume,
    isCallActive,
    startCall,
    endCall,
  } = useLiveAudio();

  // Status message text
  const getStatusDisplay = () => {
    switch (status) {
      case "connecting":
        return { title: "Connecting...", desc: "Starting voice line with Elara", color: "text-amber-700" };
      case "speaking":
        return { title: "Elara is Speaking", desc: "Speak at any time to interrupt", color: "text-emerald-700" };
      case "listening":
        return { title: "Elara is Listening", desc: "Go ahead, I'm listening to you", color: "text-amber-800" };
      case "interrupted":
        return { title: "You Interrupted", desc: "Elara paused to listen to you", color: "text-blue-700" };
      case "error":
        return { title: "Connection Error", desc: errorMessage || "Please check backend", color: "text-rose-700" };
      default:
        return { title: "Ready to Call", desc: "Tap the big button below to begin", color: "text-stone-700" };
    }
  };

  const statusInfo = getStatusDisplay();

  // Orb scaling calculation
  const orbScale = isCallActive
    ? status === "speaking"
      ? 1 + elaraVolume * 0.25
      : 1 + userVolume * 0.35
    : 1;

  return (
    <main className="flex flex-col items-center justify-between min-h-screen p-6 sm:p-10 max-w-3xl mx-auto selection:bg-amber-100">
      {/* Top Header */}
      <header className="w-full flex items-center justify-between pt-4 pb-2 border-b border-stone-200">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center text-amber-800 shadow-sm">
            <Sparkles className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-stone-900">Elara</h1>
            <p className="text-xs text-stone-500 font-medium">Google Cloud AI Companion • Phase 1</p>
          </div>
        </div>

        <button
          onClick={() => setShowSubtitles((prev) => !prev)}
          className="text-xs font-semibold px-3 py-1.5 rounded-full border border-stone-300 text-stone-600 hover:bg-stone-100 transition-colors"
        >
          {showSubtitles ? "Hide Subtitles" : "Show Subtitles"}
        </button>
      </header>

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
          <div
            className={`w-48 h-48 sm:w-56 sm:h-56 rounded-full flex flex-col items-center justify-center shadow-xl transition-all duration-200 cursor-pointer select-none ${
              status === "speaking"
                ? "bg-gradient-to-tr from-emerald-500 to-teal-400 text-white"
                : isCallActive
                ? "bg-gradient-to-tr from-amber-500 to-amber-300 text-stone-900"
                : "bg-gradient-to-tr from-stone-200 to-stone-100 text-stone-600 border border-stone-300"
            }`}
            style={{ transform: `scale(${orbScale})` }}
            onClick={isCallActive ? endCall : startCall}
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
          </div>
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
      {showSubtitles && (isCallActive || elaraTranscript || userTranscript) && (
        <section className="w-full bg-white/90 backdrop-blur rounded-2xl p-5 border border-stone-200 shadow-sm mb-6 max-h-48 overflow-y-auto space-y-3">
          {userTranscript && (
            <div className="text-sm">
              <span className="font-bold text-amber-800">You: </span>
              <span className="text-stone-800">{userTranscript}</span>
            </div>
          )}
          {elaraTranscript && (
            <div className="text-sm">
              <span className="font-bold text-emerald-800">Elara: </span>
              <span className="text-stone-800">{elaraTranscript}</span>
            </div>
          )}
          {!userTranscript && !elaraTranscript && (
            <p className="text-xs text-stone-400 italic text-center">
              Transcripts will appear here in real-time as you converse...
            </p>
          )}
        </section>
      )}

      <VoiceEnrollment disabled={isCallActive} />

      {/* Accessible Action Controls */}
      <footer className="w-full flex items-center justify-center gap-4 pb-4">
        {!isCallActive ? (
          <button
            onClick={startCall}
            className="w-full sm:w-auto min-w-[240px] px-8 py-5 rounded-full bg-emerald-600 hover:bg-emerald-700 active:scale-95 text-white font-bold text-xl shadow-lg hover:shadow-xl transition-all flex items-center justify-center gap-3"
          >
            <Phone className="w-6 h-6" />
            <span>Call Elara</span>
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
