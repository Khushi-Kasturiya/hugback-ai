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
  PhoneCall,
  RefreshCw,
  Users,
} from "lucide-react";
import { BackgroundImports } from "@/components/BackgroundImports";
import { DemoFamilySetup } from "@/components/DemoFamilySetup";
import { DemoCallHistory } from "@/components/DemoCallHistory";
import { VoiceEnrollment } from "@/components/VoiceEnrollment";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import { parentCallUrl } from "@/lib/demo-api";
import { getBrowserIdentity } from "@/lib/identity";
import { PortalStatus, portalGet } from "@/lib/portal-api";

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
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(true);
  const [revision, setRevision] = useState(0);
  const [now, setNow] = useState(Date.now());
  const [selectedId, setSelectedId] = useState("");
  const demo = useDemoFamily(Boolean(status?.localDemoEnabled));

  const recipient = demo.family?.recipients.find((item) => item.recipientId === selectedId);
  const latestCall = recipient?.calls.at(-1);
  const latestSignal = recipient?.wellbeingSignals?.filter((signal) => Date.parse(signal.expiresAt) > now).at(-1);
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
    setBusy(true); setError(""); setStatus(undefined);
    void (async () => {
      try {
        const browserIdentity = await getBrowserIdentity();
        if (!current) return;
        setIdentity(browserIdentity);
        const capabilities = await portalGet<PortalStatus>("/status");
        if (!current) return;
        setStatus(capabilities);
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

      <section id="family-dashboard" className="scroll-mt-24 py-8 sm:py-12">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#56619C]">Your bridge home</p>
            <h1 className="mt-3 font-serif text-4xl tracking-tight sm:text-5xl">Choose who you are calling.</h1>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-[#4A4B57]">Each person has their own reviewed background, call history and memory.</p>
          </div>
          <span className="rounded-full border border-[#9BA5FC]/20 bg-white/80 px-3 py-2 text-xs font-semibold text-[#56619C]">Test storage: {status?.demoStorage || "checking"}</span>
        </div>
        {identity?.mode === "firebase" && <details className="mt-4 text-xs"><summary>Test operator identity (for server allowlisting)</summary><code>{identity.owner.replace(/^firebase:/, "")}</code></details>}
        {error && <div role="alert" className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-900"><p>{error}</p><button className="font-bold underline" onClick={() => setRevision((value) => value + 1)}>Retry</button></div>}
        <div className="mt-6 rounded-[2rem] border border-[#9BA5FC]/20 bg-white/85 p-5 shadow-[0_20px_60px_-18px_rgba(86,97,156,0.18)] sm:p-8">
          {status?.localDemoEnabled ? <DemoFamilySetup family={demo.family} onChange={demo.update} loading={demo.loading} loadError={demo.error} refresh={demo.refresh} selectedId={selectedId} onSelect={setSelectedId} voice={status.voice} /> : <p className="text-sm text-[#4A4B57]">Family setup is unavailable on this backend.</p>}
        </div>
        {recipient && <div className="mt-5 grid gap-4 md:grid-cols-2">
          <article className="rounded-[1.5rem] border border-[#C7E6FF] bg-[#EDF7FF] p-5">
            <span className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-[#315F89]"><CalendarDays className="h-4 w-4" /> Latest check-in</span>
            <h2 className="mt-4 font-serif text-2xl">{readableCallStatus(latestCall?.status)}</h2>
            <p className="mt-2 text-sm text-[#4A4B57]">{latestCall ? `${recipient.label} · ${formatDate(latestCall.endedAt || latestCall.startedAt)}` : `${recipient.label} has no calls yet.`}</p>
          </article>
          <article className="rounded-[1.5rem] border border-[#D9CDF8] bg-[#F5F1FF] p-5">
            <span className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.16em] text-[#664E9D]"><Heart className="h-4 w-4" /> Conversation signal</span>
            <h2 className="mt-4 font-serif text-2xl">{latestSignal ? latestSignal.displayText : "No signal available"}</h2>
            <p className="mt-2 text-xs leading-5 text-[#4A4B57]">{latestSignal ? `AI-estimated · ${formatDate(latestSignal.observedAt)} · Not medical advice` : recipient.wellbeingSharingEnabled ? "Nothing is shared when the call does not provide enough evidence." : "Call signals are off for this person."}</p>
          </article>
        </div>}
      </section>

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

          {section === "background" && (status?.localDemoEnabled && !recipient
            ? <div className="rounded-[1.5rem] bg-[#F2F8FF] px-6 py-12 text-center"><Users className="mx-auto h-10 w-10 text-[#56619C]" /><h4 className="mt-4 font-serif text-2xl">Choose a family member first</h4><p className="mx-auto mt-2 max-w-md text-sm text-[#4A4B57]">Select a person in Family setup above before reviewing a conversation for their calls.</p></div>
            : <BackgroundImports key={recipient?.recipientId || "local-preview"} owner={identity?.owner} demoRecipient={status?.localDemoEnabled ? recipient : undefined} onDemoChange={demo.update} />)}
          {section === "voice" && <VoiceEnrollment voice={status?.voice} disabled={!identity} onUpdated={refreshVoice} recipient={status?.localDemoEnabled ? recipient : undefined} onAssigned={demo.update} />}
          {section === "summaries" && <div className="space-y-4">
            {status?.localDemoEnabled ? <DemoCallHistory key={`${recipient?.recipientId || "none"}-${recipient?.revision || 0}`} recipient={recipient} refresh={demo.refresh} /> : <div className="rounded-[1.5rem] bg-[#F2F8FF] px-6 py-12 text-center"><h4 className="font-bold">Real call summaries are not connected yet</h4><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-[#4A4B57]">Real phone enrollment, recipient-specific sharing consent and verified child access are required first.</p></div>}
          </div>}
        </section>
      </section>

      <footer className="grid gap-4 border-t border-[#9BA5FC]/15 py-8 text-xs leading-5 text-[#737386] sm:grid-cols-[1fr_auto] sm:items-center"><p className="flex max-w-3xl items-start gap-2"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-[#56619C]" /><span><strong className="text-[#4A4B57]">HugBack is a family voice bridge—not an emergency or monitoring service.</strong> Your browser is your key; clearing site data will reset your access.</span></p><Link href={callUrl} className="inline-flex items-center gap-2 font-bold text-[#56619C] transition hover:gap-3">Preview parent call <ArrowRight className="h-3.5 w-3.5" /></Link></footer>
    </div>
  </main>;
}
