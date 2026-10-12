"use client";

import React, { Suspense, useEffect, useRef, useState } from "react";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { useLiveAudio } from "@/hooks/useLiveAudio";
import { memoryFailureMessage, parentCallUrl } from "@/lib/demo-api";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import { ArrowLeft, Check, ChevronDown, Heart, LockKeyhole, Mic, Phone, PhoneOff, ShieldCheck, Sparkles, Volume2, AlertCircle } from "lucide-react";
import Link from "next/link";
import { LandingPage } from "@/components/LandingPage";

export default function Home() {
  return <Suspense fallback={<main className="min-h-screen bg-[#FFFDF8]" />}><HomeRoute /></Suspense>;
}

function HomeRoute() {
  const params = useSearchParams();
  return params.get("demo") === "parent" ? <CallTest /> : <LandingPage />;
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
  } = useLiveAudio({ demoParent: demoParent === true, recipientId, workflowAcknowledged: demoAcknowledged });
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
    <main className="landing-shell relative min-h-screen overflow-hidden bg-[#F8F9FF] text-[#252D49]">
      <div aria-hidden="true" className="pointer-events-none absolute -left-28 top-20 h-80 w-80 rounded-full bg-[#D8EEFF]/70 blur-3xl" />
      <div aria-hidden="true" className="pointer-events-none absolute -right-28 top-1/3 h-96 w-96 rounded-full bg-[#E5DDFC]/65 blur-3xl" />

      <header className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between gap-4 px-5 py-5 sm:px-8 lg:px-12">
        <Link href="/" className="flex items-center gap-3" aria-label="HugBack home">
          <Image src="/logo.png" width={727} height={343} priority alt="" className="h-9 w-[4.7rem] object-contain sm:h-11 sm:w-[5.8rem]" />
          <Image src="/hugback.png" width={983} height={254} priority alt="HugBack AI" className="h-auto w-28 sm:w-36" />
        </Link>
        <div className="flex items-center gap-2">
          <span className="hidden items-center gap-2 rounded-full border border-[#DDE2F0] bg-white/75 px-3 py-2 text-[11px] font-bold text-[#56619C] backdrop-blur sm:inline-flex"><Heart className="h-3.5 w-3.5 fill-[#9BA5FC] text-[#9BA5FC]" /> Parent experience</span>
          {!isCallActive && <Link href="/childportal" className="inline-flex items-center gap-2 rounded-full bg-[#56619C] px-4 py-2.5 text-xs font-bold text-white transition hover:-translate-y-0.5 hover:bg-[#465181]"><ArrowLeft className="h-3.5 w-3.5" /> Child portal</Link>}
        </div>
      </header>

      <div className="relative z-10 mx-auto grid w-full max-w-7xl gap-6 px-5 pb-10 pt-3 sm:px-8 lg:grid-cols-[minmax(0,0.78fr)_minmax(520px,1.22fr)] lg:gap-8 lg:px-12 lg:pb-14 lg:pt-8">
        <aside className="order-2 flex flex-col lg:order-1 lg:pt-10">
          <p className="text-[11px] font-black uppercase tracking-[0.2em] text-[#56619C]">Close to home, no matter where you roam</p>
          <h1 className="mt-4 max-w-lg font-serif text-4xl leading-[1.06] tracking-[-0.035em] text-[#252D49] sm:text-5xl lg:text-[3.6rem]">A familiar hello, waiting at home.</h1>
          <p className="mt-5 max-w-lg text-sm leading-7 text-stone-600 sm:text-base">This is the local parent-role test screen, not a parent product or verified identity. One tap opens a warm conversation carried in your voice—with HugBack always introduced clearly as AI.</p>

          <div className="mt-7 grid gap-3 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
            <div className="rounded-2xl border border-white bg-white/70 p-4 shadow-[0_12px_40px_rgba(86,97,156,0.07)] backdrop-blur">
              <ShieldCheck className="h-5 w-5 text-[#56619C]" />
              <p className="mt-3 text-sm font-bold">Clear and reassuring</p>
              <p className="mt-1 text-xs leading-5 text-stone-500">AI identity is disclosed before the conversation begins.</p>
            </div>
            <div className="rounded-2xl border border-white bg-white/70 p-4 shadow-[0_12px_40px_rgba(86,97,156,0.07)] backdrop-blur">
              <LockKeyhole className="h-5 w-5 text-[#9BA5FC]" />
              <p className="mt-3 text-sm font-bold">Family context stays separate</p>
              <p className="mt-1 text-xs leading-5 text-stone-500">Each loved one has their own background and memories.</p>
            </div>
          </div>

          {demoParent && <section className="mt-5 rounded-[1.75rem] border border-[#DDE2F0] bg-white/78 p-5 shadow-[0_18px_55px_rgba(86,97,156,0.08)] backdrop-blur sm:p-6">
            <div className="flex items-center justify-between gap-3">
              <div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#56619C]">Demo controls</p><h2 className="mt-1 font-serif text-2xl">Who is answering?</h2></div>
              <span className="rounded-full bg-[#EDF7FF] px-3 py-1.5 text-[10px] font-bold text-[#315F89]">Private preview</span>
            </div>

            {demo.family ? <label className="mt-5 block text-xs font-bold text-stone-600">Call recipient
              <span className="relative mt-2 block">
                <select className="w-full appearance-none rounded-xl border border-[#DDE2F0] bg-white px-4 py-3 pr-10 text-sm text-stone-800 outline-none transition focus:border-[#9BA5FC] focus:ring-2 focus:ring-[#E5E8FF]" aria-label="Call recipient" value={recipient?.recipientId || ""} disabled={isCallActive} onChange={(event) => { setDemoAcknowledged(false); router.replace(parentCallUrl(event.target.value)); }}>
                  <option value="">Choose a recipient</option>
                  {demo.family.recipients.map((item) => <option key={item.recipientId} value={item.recipientId}>{item.label}{item.busy ? " · busy" : ""}</option>)}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-3.5 h-4 w-4 text-stone-400" />
              </span>
            </label> : !demo.loading && !demo.error ? <p className="mt-5 rounded-xl bg-[#F3EFFF] p-4 text-sm leading-6 text-stone-600">Create a local demo family in the <Link className="font-bold text-[#56619C] underline underline-offset-4" href="/childportal">child portal</Link> first.</p> : null}

            {recipientId && demo.family && !recipient && <p role="alert" className="mt-3 text-sm text-rose-700">That recipient is not in this demo family. Choose an available person.</p>}
            {recipient && <div className="mt-4 rounded-xl bg-[#F7F7FC] p-4 text-xs leading-5 text-stone-600">
              <p className="flex items-center gap-2 font-bold text-[#465181]"><Check className="h-3.5 w-3.5" /> {recipient.label} · {recipient.voice.mode === "child" ? "Child voice assigned" : "Standard HugBack voice"}</p>
              {recipient.voice.mode === "standard" && !isCallActive && <p className="mt-2 text-amber-900">This call will use the standard AI voice, not your recording. To use your replacement voice, enable it and assign it to {recipient.label} in <Link href="/childportal#family-dashboard" className="font-bold underline">Child portal</Link> first.</p>}
              <p className="mt-1">{recipient.background.length} reviewed excerpts · {recipient.memoryCount} retained wellbeing records</p>
              {recipient.busy && !isCallActive && <p role="status" className="mt-2 font-semibold text-amber-800">Finishing the previous call and saving memory…</p>}
              {recipient.calls.at(-1)?.workflow && <p className="mt-2">Workflow: {Object.entries(recipient.calls.at(-1)?.workflow || {}).map(([role, state]) => `${role}: ${state}`).join(" · ")}</p>}
              {recipient.calls.at(-1)?.status === "memory_failed" && <div role="alert" className="mt-2 text-rose-700"><p>The last memory update failed; do not assume it was remembered.</p><p className="mt-1">{memoryFailureMessage(recipient.calls.at(-1)?.memoryErrorCode)}</p></div>}
            </div>}
            {demo.error && <p role="alert" className="mt-4 text-sm text-rose-700">{demo.error}</p>}

            <label className="mt-4 flex cursor-pointer items-start gap-3 rounded-xl border border-[#E5E7F2] bg-white/80 p-4 text-xs leading-5 text-stone-600">
              <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-[#56619C]" checked={demoAcknowledged} disabled={isCallActive} onChange={(e) => setDemoAcknowledged(e.target.checked)} />
              <span><strong className="text-stone-800">I’m ready to role-play as {recipient?.label || "the selected recipient"}.</strong> I’ll use fictional details and end the call before switching people. Microphone audio, reviewed context and enabled memory are processed by Google. I also allow the enabled Planner and Quality Critic to process this fictional call; their quality findings are internal, not family recaps. HugBack is AI, not my child.</span>
            </label>
            {callInfo && callInfo.parentId === recipient?.recipientId && <details className="mt-3 text-[11px] leading-5 text-stone-500"><summary className="cursor-pointer font-semibold">Call details</summary><p className="mt-2 break-all">Session {callInfo.sessionId} · Memory {callInfo.memoryStatus} · Voice {callInfo.voice}</p></details>}
          </section>}
        </aside>

        <section className="order-1 overflow-hidden rounded-[2rem] border border-white/90 bg-white/72 shadow-[0_28px_90px_rgba(54,66,118,0.15)] backdrop-blur-xl lg:order-2">
          <div className="flex items-center justify-between border-b border-[#E7E9F3] px-5 py-4 sm:px-7">
            <div className="flex items-center gap-3"><span className={`h-2.5 w-2.5 rounded-full ${isCallActive ? "animate-pulse bg-[#72B5FE]" : "bg-[#9BA5FC]"}`} /><div><p className="text-sm font-bold">Voice bridge {recipient ? `to ${recipient.label}` : "to home"}</p><p className="text-[11px] text-stone-500">Your child’s familiar voice, carried by HugBack</p></div></div>
            <button onClick={() => setShowSubtitles((prev) => !prev)} className="rounded-full border border-[#DDE2F0] bg-white px-3 py-2 text-[11px] font-bold text-[#56619C] transition hover:bg-[#F3F4FB]">{showSubtitles ? "Hide words" : "Show words"}</button>
          </div>

          <div className="relative flex min-h-[570px] flex-col items-center px-5 pb-7 pt-10 text-center sm:px-10 sm:pt-12">
            <div aria-hidden="true" className="absolute left-1/2 top-36 h-72 w-72 -translate-x-1/2 rounded-full bg-gradient-to-br from-[#D8EEFF] via-[#E1E3FF] to-[#EADFFC] opacity-85 blur-3xl" />
            <span className="relative inline-flex items-center gap-2 rounded-full border border-[#DDE2F0] bg-white/80 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-[#56619C]"><Sparkles className="h-3 w-3" /> AI clearly disclosed</span>
            <p className="relative mt-6 max-w-sm font-serif text-2xl leading-8 text-[#2D344E]">{isCallActive ? (status === "speaking" ? "HugBack is speaking in a familiar voice" : "I’m listening—take your time") : `Ready for a little moment with ${recipient?.label || "family"}`}</p>

            <div className="relative mt-5 flex h-64 w-64 items-center justify-center sm:h-72 sm:w-72">
              <span className={`absolute h-56 w-56 rounded-full border border-[#9BA5FC]/35 transition-transform duration-500 sm:h-64 sm:w-64 ${isCallActive ? "animate-ping" : ""}`} />
              <span className="absolute h-44 w-44 rounded-full border border-white/80 bg-white/20 shadow-[0_0_70px_rgba(155,165,252,0.28)] sm:h-52 sm:w-52" />
              <button type="button" aria-label={isCallActive ? "End current call" : "Start selected call"} disabled={!isCallActive && !canStart} onClick={isCallActive ? endCall : startSelectedCall} style={{ transform: `scale(${orbScale})` }} className={`relative grid h-36 w-36 place-items-center rounded-full text-white shadow-[0_22px_55px_rgba(86,97,156,0.32)] transition-all duration-200 sm:h-40 sm:w-40 ${isCallActive ? "bg-gradient-to-br from-[#72B5FE] via-[#9BA5FC] to-[#B69CF2]" : "bg-gradient-to-br from-[#7CC2FF] via-[#8F9CF4] to-[#A98AE7] hover:scale-105"} disabled:cursor-not-allowed disabled:grayscale-[.2] disabled:opacity-55`}>
                {isCallActive ? status === "speaking" ? <Volume2 className="h-14 w-14" /> : <Mic className="h-14 w-14 animate-pulse" /> : <Phone className="h-14 w-14" />}
              </button>
            </div>

            <div className="relative -mt-1">
              <h2 className={`text-2xl font-extrabold tracking-tight ${statusInfo.color}`}>{statusInfo.title}</h2>
              <p className="mt-2 text-sm font-medium text-stone-500">{statusInfo.desc}</p>
            </div>

            {errorMessage && <div className="relative mt-5 flex max-w-md items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-left text-sm font-medium text-rose-800"><AlertCircle className="mt-0.5 h-4 w-4 shrink-0" /><span>{errorMessage}</span></div>}

            {showSubtitles && (isCallActive || hugbackTranscript || userTranscript) && <div className="relative mt-6 max-h-40 w-full max-w-lg space-y-3 overflow-y-auto rounded-2xl border border-[#E2E5F1] bg-white/85 p-4 text-left shadow-sm">
              {userTranscript && <p className="text-sm"><span className="font-bold text-[#56619C]">You: </span><span className="text-stone-700">{userTranscript}</span></p>}
              {hugbackTranscript && <p className="text-sm"><span className="font-bold text-[#7664AD]">HugBack: </span><span className="text-stone-700">{hugbackTranscript}</span></p>}
              {!userTranscript && !hugbackTranscript && <p className="text-center text-xs italic text-stone-400">Conversation words will appear here…</p>}
            </div>}

            <div className="relative mt-auto w-full pt-8">
              {!isCallActive ? <button onClick={startSelectedCall} disabled={!canStart} className="mx-auto flex w-full max-w-sm items-center justify-center gap-3 rounded-full bg-[#56619C] px-8 py-4 text-base font-bold text-white shadow-[0_14px_30px_rgba(86,97,156,0.28)] transition hover:-translate-y-0.5 hover:bg-[#465181] disabled:cursor-not-allowed disabled:opacity-45 disabled:hover:translate-y-0"><Phone className="h-5 w-5" /><span>{demoParent ? "Begin parent preview" : "Start voice bridge"}</span></button> : <button onClick={endCall} className="mx-auto flex w-full max-w-sm items-center justify-center gap-3 rounded-full bg-rose-600 px-8 py-4 text-base font-bold text-white shadow-lg transition hover:-translate-y-0.5 hover:bg-rose-700"><PhoneOff className="h-5 w-5" /><span>End call</span></button>}
              <p className="mt-3 text-[11px] text-stone-400">Tap once to begin. You can end the call at any time.</p>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
