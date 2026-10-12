"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  AudioLines,
  BookOpen,
  CalendarDays,
  Check,
  FileText,
  Heart,
  LockKeyhole,
  MessageCircle,
  PhoneCall,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import { BackgroundImports } from "@/components/BackgroundImports";
import { VoiceEnrollment } from "@/components/VoiceEnrollment";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import { parentCallUrl } from "@/lib/demo-api";
import { getBrowserIdentity } from "@/lib/identity";
import { PortalStatus, SharedSummary, portalGet } from "@/lib/portal-api";

const sections = [
  { id: "background", step: "1", label: "Family language", icon: BookOpen },
  { id: "voice", step: "2", label: "Your voice", icon: AudioLines },
  { id: "summaries", step: "3", label: "Signals back", icon: FileText },
] as const;
type Section = typeof sections[number]["id"];

function readableCallStatus(status?: string) {
  if (!status) return "No check-ins yet";
  if (status === "active" || status === "processing") return "Check-in in progress";
  if (status === "memory_failed") return "Check-in finished · memory needs attention";
  if (status === "privacy_hold") return "Check-in finished · privacy hold";
  if (status === "failed" || status === "interrupted") return "Check-in ended early";
  return "Check-in completed";
}

function formatDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

export default function ChildPortal() {
  const [section, setSection] = useState<Section>("background");
  const [identity, setIdentity] = useState<{ owner: string; mode: "development" | "firebase" }>();
  const [status, setStatus] = useState<PortalStatus>();
  const [summaries, setSummaries] = useState<SharedSummary[]>([]);
  const [sharing, setSharing] = useState<PortalStatus["sharingStatus"]>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [selectedId, setSelectedId] = useState("");
  const demo = useDemoFamily(Boolean(status?.localDemoEnabled));

  const recipient = demo.family?.recipients.find((item) => item.recipientId === selectedId) || demo.family?.recipients[0];
  const latestCall = recipient?.calls.at(-1);
  const latestSignal = recipient?.wellbeingSignals?.filter((signal) => Date.parse(signal.expiresAt) > now).at(-1);
  const visibleSummaries = summaries.filter((summary) => Date.parse(summary.expiresAt) > now);
  const callUrl = parentCallUrl(recipient?.recipientId);
  const activeSection = sections.find((item) => item.id === section) || sections[0];
  const activeStepIndex = sections.findIndex((item) => item.id === section);
  const ActiveIcon = activeSection.icon;

  function openStep(next: Section) {
    setSection(next);
    window.requestAnimationFrame(() => document.getElementById("setup-workspace")?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  async function refreshVoice() {
    try { setStatus(await portalGet<PortalStatus>("/status")); }
    catch { setError("Could not refresh voice availability. Retry the backend before assigning a voice."); }
  }

  useEffect(() => {
    if (section !== "summaries") return;
    const refresh = () => {
      setNow(Date.now());
      if (document.visibilityState === "visible") setRevision((value) => value + 1);
    };
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    const timer = window.setInterval(refresh, 60_000);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(clock);
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [section]);

  useEffect(() => {
    let current = true;
    setBusy(true); setError(""); setStatus(undefined); setSummaries([]); setSharing(undefined);
    void (async () => {
      try {
        const browserIdentity = await getBrowserIdentity();
        if (!current) return;
        setIdentity(browserIdentity);
        const capabilities = await portalGet<PortalStatus>("/status");
        if (!current) return;
        setStatus(capabilities);
        const updates = await portalGet<{ status: PortalStatus["sharingStatus"]; summaries: SharedSummary[] }>("/summaries");
        if (!current) return;
        setSharing(updates.status); setSummaries(updates.summaries);
      } catch (loadError) {
        if (current) setError(loadError instanceof Error ? loadError.message : "Could not load this browser's portal.");
      } finally { if (current) setBusy(false); }
    })();
    return () => { current = false; };
  }, [revision]);

  return <main className="min-h-screen overflow-hidden bg-gradient-to-br from-[#F8F9FF] via-[#FCFAFF] to-[#F4F1FF] text-[#1F2550]">
    <div aria-hidden="true" className="dashboard-float pointer-events-none fixed -left-40 top-20 h-80 w-80 rounded-full bg-[#72B5FE]/12 blur-3xl" />
    <div aria-hidden="true" className="dashboard-float pointer-events-none fixed -right-40 top-[30rem] h-96 w-96 rounded-full bg-[#B69CF2]/12 blur-3xl" style={{ animationDelay: "-4s" }} />

    <header className="sticky top-0 z-30 border-b border-[#9BA5FC]/15 bg-[#F8F9FF]/90 backdrop-blur-xl">
      <div className="mx-auto flex min-h-20 max-w-[1240px] items-center justify-between gap-4 px-4 sm:px-7">
        <Link href="/" className="flex items-center gap-2 rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#56619C]">
          <Image src="/logo.png" width={727} height={343} priority alt="" className="h-9 w-[4.8rem] object-contain sm:h-10 sm:w-[5.3rem]" />
          <Image src="/hugback.png" width={983} height={254} priority alt="HugBack AI" className="h-auto w-28 sm:w-36" />
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          <span className="hidden items-center gap-2 rounded-full border border-[#9BA5FC]/20 bg-white/75 px-3 py-2 text-[11px] font-semibold text-[#4A4B57] sm:inline-flex"><span className={`h-2 w-2 rounded-full ${identity ? "bg-[#72B5FE] shadow-[0_0_10px_#72B5FE]" : "bg-stone-400"}`} />{identity?.mode === "firebase" ? "Private session" : identity ? "Demo environment" : "Connecting"}</span>
          <Link href={callUrl} aria-label="Preview the parent experience" className="group inline-flex items-center gap-2 rounded-full bg-[#56619C] px-4 py-2.5 text-xs font-bold text-white shadow-[0_10px_24px_rgba(86,97,156,0.2)] transition hover:-translate-y-0.5 hover:bg-[#465181]"><PhoneCall className="h-4 w-4" /><span className="hidden sm:inline">Preview parent call</span><ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></Link>
        </div>
      </div>
    </header>

    <div className="relative mx-auto max-w-[1240px] px-4 pb-10 sm:px-7">

      <section id="setup-workspace" className="py-2 sm:py-4">
        <div className="max-w-4xl">
          <div className="mt-3 flex items-center gap-3.5 sm:gap-4">
            <div className="voice-bars flex h-14 shrink-0 items-center gap-1" aria-hidden="true">
              {[18, 34, 48, 26, 54, 38, 22, 42].map((height, index) => (
                <span
                  key={index}
                  className="w-1 rounded-full bg-gradient-to-t from-[#56619C] to-[#72B5FE]"
                  style={{ height, animationDelay: `${index * 80}ms` }}
                />
              ))}
            </div>
            <h2 className="font-serif text-4xl leading-tight tracking-[-0.03em] sm:text-5xl">
              Build a bridge that sounds like home.
            </h2>
          </div>
          <p className="mt-4 text-[#4A4B57]">
            Three thoughtful steps, from family language to a familiar hello and a gentle signal back.
          </p>
        </div>

        <nav aria-label="Three-step child portal setup" className="relative mt-10 grid gap-3 md:grid-cols-3">
          <div aria-hidden="true" className="absolute left-[16%] right-[16%] top-7 hidden border-t-2 border-dotted border-[#9BA5FC]/35 md:block" />
          {sections.map(({ id, step, label, icon: Icon }, index) => {
            const isActive = section === id;
            const isComplete = index < activeStepIndex || (id === "background" && !!recipient?.background.length) || (id === "voice" && recipient?.voice.mode === "child");
            return <button key={id} type="button" onClick={() => setSection(id)} aria-current={isActive ? "step" : undefined} className={`step-tab relative z-10 flex items-center gap-3 rounded-[24px] border p-4 text-left transition duration-300 hover:-translate-y-1 ${isActive ? "border-[#9BA5FC] bg-white shadow-[0_18px_40px_rgba(139,92,246,0.14)]" : "border-[#9BA5FC]/20 bg-white/65 hover:bg-white"}`}>
              <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-full transition ${isComplete ? "bg-[#56619C] text-white" : isActive ? "bg-gradient-to-br from-[#72B5FE] to-[#B69CF2] text-white" : "bg-[#F1EFFF] text-[#56619C]"}`}>{isComplete ? <Check className="h-5 w-5" /> : <Icon className="h-5 w-5" />}</span><span><span className="block text-[10px] font-black uppercase tracking-[0.15em] text-[#737386]">Step {step}</span><span className="mt-0.5 block font-serif text-lg">{label}</span></span>
            </button>;
          })}
        </nav>

        <section key={section} className="step-panel-enter relative mt-5 overflow-hidden rounded-[32px] border border-[#9BA5FC]/20 bg-white/85 p-5 shadow-[0_20px_60px_-18px_rgba(86,97,156,0.18)] backdrop-blur-md sm:p-8">
          <div className="mb-7 flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
            <div className="flex items-start gap-4"><span className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#E5F2FF] to-[#EEE7FF] text-[#56619C]"><ActiveIcon className="h-5 w-5" /></span><div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#56619C]">Step {activeStepIndex + 1} of 3</p><h3 className="mt-1 font-serif text-3xl">{section === "background" ? "Family Language" : section === "voice" ? "Carry Your Voice" : "Close the loop"}</h3><p className="mt-2 max-w-2xl text-sm leading-6 text-[#4A4B57]">{section === "background" ? "Upload past chats to teach HugBack your family’s unique names and phrases." : section === "voice" ? "A short recording captures your warmth and tone so they never hear a cold robot." : "After a natural tea-time chat, a quick summary keeps you in the loop on their mood."}</p></div></div>
          </div>

          {section === "background" && (
            <BackgroundImports
              owner={identity?.owner}
              demoRecipient={recipient}
              demoFamily={demo.family}
              onDemoChange={demo.update}
              onRecipientSelect={setSelectedId}
            />
          )}
          {section === "voice" && <VoiceEnrollment voice={status?.voice} disabled={!identity} onUpdated={refreshVoice} recipient={status?.localDemoEnabled ? recipient : undefined} onAssigned={demo.update} />}
          {section === "summaries" && <div className="space-y-4">
            <div className="rounded-[28px] border border-[#9BA5FC]/20 bg-gradient-to-br from-white to-[#F3EFFF] p-6 shadow-[0_16px_36px_rgba(86,97,156,0.1)] sm:p-7"><div className="flex flex-wrap items-center justify-between gap-3"><span className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.18em] text-[#56619C]"><CalendarDays className="h-4 w-4" /> Today</span><Heart className="h-7 w-7 fill-[#8878D7] text-[#8878D7]" /></div><p className="mt-5 font-serif text-2xl text-[#1D1E2C]">{latestSignal?.displayText || `${recipient?.label || "Mom"} sounded cheerful today.`}</p><div className="mt-5 flex flex-wrap gap-2 text-[11px] font-bold text-[#56619C]"><span className="rounded-full bg-indigo-50 px-3 py-1.5">Estimated via AI</span><span className="rounded-full bg-blue-50 px-3 py-1.5">Zero raw audio saved</span><span className="rounded-full bg-violet-50 px-3 py-1.5">No medical advice</span></div><p className="mt-4 text-xs leading-5 text-[#737386]">No transcripts, spy apps, or medical diagnoses. Just a gentle nudge.</p></div>
            <div className="flex items-center justify-between gap-3 rounded-[24px] border border-[#9BA5FC]/15 bg-white/80 p-5"><div><h4 className="font-serif text-xl">Updates shared with you</h4><p className="mt-1 text-sm leading-6 text-[#4A4B57]">Approved recaps only—never a transcript or private memory.</p></div><button className="portal-secondary shrink-0" disabled={busy} onClick={() => setRevision((value) => value + 1)} aria-label="Refresh summaries"><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /></button></div>
            {!visibleSummaries.length && <div className="rounded-[24px] border border-[#9BA5FC]/15 bg-white/75 px-6 py-10 text-center"><MessageCircle className="mx-auto h-8 w-8 text-[#9BA5FC]" /><h4 className="mt-4 font-bold">{busy ? "Checking for updates…" : "Nothing new to share"}</h4><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#4A4B57]">{sharing === "ready" ? "An update appears only after your parent approves it." : "Sharing is private by default and requires a verified parent relationship."}</p></div>}
            {visibleSummaries.map((summary, index) => <article key={summary.id} className="dashboard-enter rounded-[24px] border border-[#9BA5FC]/15 bg-white/85 p-5 transition hover:-translate-y-0.5 hover:shadow-md" style={{ animationDelay: `${index * 60}ms` }}><div className="flex flex-wrap items-center justify-between gap-2"><time className="text-xs text-[#737386]">{formatDate(summary.callEndedAt)}</time><span className="inline-flex items-center gap-1.5 rounded-full bg-[#EDF7FF] px-2.5 py-1 text-xs font-bold text-[#315F89]"><Check className="h-3 w-3" /> Parent approved</span></div><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-[#4A4B57]">{summary.text}</p></article>)}
          </div>}
        </section>
      </section>

      <footer className="grid gap-4 border-t border-[#9BA5FC]/15 py-8 text-xs leading-5 text-[#737386] sm:grid-cols-[1fr_auto] sm:items-center"><p className="flex max-w-3xl items-start gap-2"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-[#56619C]" /><span><strong className="text-[#4A4B57]">HugBack is a family voice bridge—not an emergency or monitoring service.</strong> Your browser is your key; clearing site data will reset your access.</span></p><Link href={callUrl} className="inline-flex items-center gap-2 font-bold text-[#56619C] transition hover:gap-3">Preview parent call <ArrowRight className="h-3.5 w-3.5" /></Link></footer>
    </div>
  </main>;
}
