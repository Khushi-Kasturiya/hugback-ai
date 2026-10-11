"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  AudioLines,
  BookOpen,
  Check,
  ChevronRight,
  Clock3,
  FileText,
  Heart,
  HeartHandshake,
  Activity,
  LockKeyhole,
  MessageCircle,
  PhoneCall,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { BackgroundImports } from "@/components/BackgroundImports";
import { DemoFamilySetup } from "@/components/DemoFamilySetup";
import { VoiceEnrollment } from "@/components/VoiceEnrollment";
import { useDemoFamily } from "@/hooks/useDemoFamily";
import { parentCallUrl } from "@/lib/demo-api";
import { getBrowserIdentity } from "@/lib/identity";
import { PortalStatus, SharedSummary, portalGet } from "@/lib/portal-api";

const sections = [
  { id: "background", step: "1", label: "Family context", icon: BookOpen, detail: "Add the stories and details that make a check-in personal." },
  { id: "voice", step: "2", label: "Voice setup", icon: AudioLines, detail: "Optionally create a familiar voice for Hugback to use." },
  { id: "summaries", step: "3", label: "Approved updates", icon: FileText, detail: "See only the updates your parent has approved to share." },
] as const;
type Section = typeof sections[number]["id"];

const sectionStyles: Record<Section, { tab: string; active: string; icon: string; panel: string; eyebrow: string }> = {
  background: {
    tab: "border-[#B8DFFE] bg-[#EDF7FF]",
    active: "border-[#72B5FE] bg-[#E4F3FF] shadow-[0_12px_30px_rgba(114,181,254,0.18)]",
    icon: "bg-[#D8EEFF] text-[#315F89]",
    panel: "border-[#C7E6FF] bg-[#F2F9FF]",
    eyebrow: "text-[#315F89]",
  },
  voice: {
    tab: "border-[#D9CDF8] bg-[#F5F1FF]",
    active: "border-[#B69CF2] bg-[#EEE8FF] shadow-[0_12px_30px_rgba(182,156,242,0.18)]",
    icon: "bg-[#E8DFFF] text-[#664E9D]",
    panel: "border-[#DED2FA] bg-[#F8F5FF]",
    eyebrow: "text-[#664E9D]",
  },
  summaries: {
    tab: "border-[#CFCFFE] bg-[#F0F1FF]",
    active: "border-[#9BA5FC] bg-[#E9EBFF] shadow-[0_12px_30px_rgba(155,165,252,0.18)]",
    icon: "bg-[#DFE2FF] text-[#56619C]",
    panel: "border-[#D1D5FF] bg-[#F5F5FF]",
    eyebrow: "text-[#56619C]",
  },
};

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

  const recipient = demo.family?.recipients.find((item) => item.recipientId === selectedId);
  const latestCall = recipient?.calls.at(-1);
  const latestSignal = recipient?.wellbeingSignals?.filter((signal) => Date.parse(signal.expiresAt) > now).at(-1);
  const visibleSummaries = summaries.filter((summary) => Date.parse(summary.expiresAt) > now);
  const latestSummary = visibleSummaries[0];
  const callUrl = demo.family ? parentCallUrl(recipient?.recipientId) : "/";
  const activeSection = sections.find((item) => item.id === section) || sections[0];
  const activeStepIndex = sections.findIndex((item) => item.id === section);
  const nextSection = sections[activeStepIndex + 1];
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

  return <main className="min-h-screen overflow-hidden bg-[#F7F8FF] text-stone-900">
    <div aria-hidden="true" className="dashboard-float pointer-events-none fixed -left-44 top-24 h-80 w-80 rounded-full bg-[#72B5FE]/10 blur-3xl" />
    <div aria-hidden="true" className="dashboard-float pointer-events-none fixed -right-48 top-[34rem] h-96 w-96 rounded-full bg-[#B69CF2]/10 blur-3xl" style={{ animationDelay: "-4s" }} />

    <header className="relative z-20 border-b border-[#E3E6F3] bg-[#F7F8FF]/90 backdrop-blur-xl">
      <div className="mx-auto flex min-h-20 max-w-[1240px] items-center justify-between gap-4 px-4 sm:px-7">
        <Link href="/" className="flex items-center gap-2 rounded-xl focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[#56619C]">
          <Image src="/logo.png" width={727} height={343} priority alt="" className="h-9 w-[4.8rem] object-contain sm:h-10 sm:w-[5.3rem]" />
          <Image src="/hugback.png" width={983} height={254} priority alt="Hugback AI" className="h-auto w-28 sm:w-36" />
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          <span className="hidden items-center gap-2 rounded-full border border-[#DDE2F0] bg-white px-3 py-2 text-[11px] font-semibold text-stone-600 sm:inline-flex"><span className={`h-2 w-2 rounded-full ${identity ? "bg-[#72B5FE]" : "bg-stone-400"}`} />{identity?.mode === "firebase" ? "Private session" : identity ? "Local demo" : "Connecting"}</span>
          <Link href={callUrl} aria-label="Open call test" className="group inline-flex items-center gap-2 rounded-full bg-[#56619C] px-4 py-2.5 text-xs font-bold text-white shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-[#465181] hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#56619C]"><PhoneCall className="h-4 w-4" /><span className="hidden sm:inline">Open call test</span><ArrowRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></Link>
        </div>
      </div>
    </header>

    <div className="relative mx-auto max-w-[1240px] px-4 pb-10 sm:px-7">
      <section className="dashboard-enter grid items-stretch gap-6 py-8 lg:min-h-[620px] lg:grid-cols-[1.02fr_0.98fr] lg:gap-10 lg:py-12">
        <div className="flex flex-col justify-center py-8 lg:py-12">
          <p className="inline-flex w-fit items-center gap-2 rounded-full border border-[#D7EAFE] bg-[#EDF7FF] px-3 py-1.5 text-[11px] font-bold uppercase tracking-[0.16em] text-[#56619C]"><Heart className="h-3.5 w-3.5 fill-[#72B5FE] text-[#72B5FE]" /> For families living apart</p>
          <h1 className="mt-6 max-w-2xl font-serif text-[2.7rem] leading-[1.05] tracking-[-0.04em] text-[#252D49] sm:text-6xl lg:text-[4.25rem]">A caring voice checks in. <span className="text-[#56619C]">You stay close.</span></h1>
          <p className="mt-6 max-w-xl text-base leading-7 text-stone-600 sm:text-lg sm:leading-8">Hugback is an AI voice companion that talks with your elderly parent and helps you stay connected from wherever you are. Your parent is always told they are speaking with AI.</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <a href="#family-dashboard" className="group inline-flex items-center gap-2 rounded-full bg-[#56619C] px-6 py-3.5 text-sm font-bold text-white shadow-[0_10px_24px_rgba(86,97,156,0.22)] transition duration-200 hover:-translate-y-0.5 hover:bg-[#465181] hover:shadow-[0_14px_30px_rgba(86,97,156,0.28)]">View your family dashboard <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></a>
            <a href="#how-it-works" className="inline-flex items-center gap-2 rounded-full px-5 py-3.5 text-sm font-bold text-[#56619C] transition hover:bg-white">How Hugback works <ChevronRight className="h-4 w-4" /></a>
          </div>
          <p className="mt-6 flex max-w-lg items-start gap-2 text-xs leading-5 text-stone-500"><ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[#56619C]" /> Conversations and memories stay separate for each family member. Updates appear only when a parent approves them.</p>
        </div>

        <div className="relative flex items-center justify-center overflow-hidden rounded-[2.25rem] bg-[#EAF5FF] p-5 sm:p-8 lg:p-10">
          <div aria-hidden="true" className="absolute -right-16 -top-20 h-64 w-64 rounded-full bg-[#B69CF2]/24 blur-2xl" />
          <div aria-hidden="true" className="absolute -bottom-20 -left-16 h-64 w-64 rounded-full bg-[#72B5FE]/28 blur-2xl" />
          <div className="relative w-full max-w-md rounded-[2rem] border border-white/90 bg-white p-5 shadow-[0_24px_70px_rgba(86,97,156,0.14)] sm:p-7">
            <div className="flex items-center justify-between gap-4 border-b border-[#E8EAF4] pb-5">
              <div className="flex items-center gap-3"><span className="grid h-11 w-11 place-items-center rounded-full bg-[#E4F3FF] font-serif text-lg font-bold text-[#56619C]">M</span><span><span className="block text-sm font-bold text-stone-800">Check-in with Mum</span><span className="mt-0.5 block text-xs text-stone-500">Hugback voice call</span></span></div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-[#EDF7FF] px-2.5 py-1 text-[10px] font-bold text-[#315F89]"><span className="h-1.5 w-1.5 rounded-full bg-[#72B5FE]" /> Connected</span>
            </div>
            <div className="py-7 text-center">
              <div className="voice-bars mx-auto flex h-16 w-32 items-center justify-center gap-1.5" aria-hidden="true">{[18, 32, 48, 28, 56, 38, 24, 44, 30].map((height, index) => <span key={index} className="w-1.5 rounded-full bg-[#9BA5FC]" style={{ height, animationDelay: `${index * 80}ms` }} />)}</div>
              <p className="mx-auto mt-5 max-w-xs font-serif text-xl leading-7 text-[#2D344E]">“Hi, it’s Hugback, your AI companion. How are you feeling today?”</p>
              <span className="mt-5 inline-flex items-center gap-1.5 rounded-full bg-[#F3EFFF] px-3 py-1.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[#664E9D]"><Sparkles className="h-3 w-3" /> AI identity disclosed</span>
            </div>
            <div className="grid grid-cols-3 gap-2 border-t border-[#E8EAF4] pt-5 text-center text-[10px] font-semibold leading-4 text-stone-500"><span>Gentle<br />check-in</span><span>Opted-in<br />memory</span><span>Approved<br />update</span></div>
          </div>
        </div>
      </section>

      <section id="family-dashboard" className="scroll-mt-24 py-16 sm:py-24">
        <div className="dashboard-enter flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
          <div><p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#56619C]">Family dashboard</p><h2 className="mt-3 max-w-2xl font-serif text-4xl leading-tight tracking-[-0.025em] text-[#252D49] sm:text-5xl">The important things, at a glance.</h2><p className="mt-4 max-w-2xl text-sm leading-7 text-stone-600 sm:text-base">Choose a family member to see their latest check-in, approved update, and the most useful next action.</p></div>
          <span className="inline-flex w-fit items-center gap-2 rounded-full border border-[#DDE2F0] bg-white px-3 py-2 text-xs font-semibold text-stone-600"><LockKeyhole className="h-3.5 w-3.5 text-[#56619C]" /> Each person has a separate history</span>
        </div>

        {error && <div role="alert" className="mt-7 flex items-start justify-between gap-4 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-900"><p>{error}</p><button className="inline-flex shrink-0 items-center gap-1.5 font-bold underline underline-offset-4 disabled:opacity-50" disabled={busy} onClick={() => setRevision((value) => value + 1)}><RefreshCw className="h-3.5 w-3.5" /> Retry</button></div>}

        <div className="mt-10 rounded-[2rem] border border-[#E1E4F1] bg-white p-5 shadow-[0_16px_50px_rgba(55,65,105,0.07)] sm:p-7">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-3"><div><p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#56619C]">Your family</p><h3 className="mt-2 font-serif text-2xl text-[#252D49]">Who is Hugback checking in with?</h3></div>{status?.localDemoEnabled && <span className="rounded-full bg-[#F2F3FA] px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider text-stone-500">Local demo</span>}</div>
          {status?.localDemoEnabled ? <DemoFamilySetup family={demo.family} onChange={demo.update} loading={demo.loading} loadError={demo.error} refresh={demo.refresh} selectedId={selectedId} onSelect={setSelectedId} voice={status.voice} /> : <div className="rounded-2xl bg-[#F7F8FC] p-6 text-sm text-stone-600">Family setup is unavailable on this backend.</div>}
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          <article className="reveal-card group relative overflow-hidden rounded-[2rem] border border-[#C7E6FF] bg-[#EAF6FF] p-6 transition duration-300 hover:-translate-y-1 hover:shadow-[0_20px_50px_rgba(114,181,254,0.18)] sm:p-8 lg:col-span-7">
            <div aria-hidden="true" className="absolute -right-16 -top-20 h-56 w-56 rounded-full bg-[#72B5FE]/18 transition-transform duration-700 group-hover:scale-125" />
            <div className="relative flex h-full min-h-64 flex-col">
              <div className="flex items-center justify-between gap-3"><span className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.18em] text-[#315F89]"><Clock3 className="h-4 w-4" /> Latest check-in</span>{recipient?.busy && <span className="rounded-full bg-white/80 px-3 py-1 text-xs font-bold text-[#56619C]">In progress</span>}</div>
              {recipient ? <><h3 className="mt-8 font-serif text-3xl text-[#252D49] sm:text-4xl">{readableCallStatus(latestCall?.status)}</h3><p className="mt-3 text-sm leading-6 text-stone-600">{latestCall ? `${recipient.label}’s most recent Hugback call${formatDate(latestCall.endedAt || latestCall.startedAt) ? ` · ${formatDate(latestCall.endedAt || latestCall.startedAt)}` : ""}.` : `${recipient.label} has not completed a Hugback check-in yet.`}</p><div className="mt-auto flex flex-wrap gap-3 pt-8"><span className="rounded-full bg-white/80 px-3 py-2 text-xs font-bold text-stone-700">{recipient.calls.length} {recipient.calls.length === 1 ? "check-in" : "check-ins"}</span><span className="rounded-full bg-white/80 px-3 py-2 text-xs font-bold text-stone-700">{recipient.memoryCount} remembered {recipient.memoryCount === 1 ? "note" : "notes"}</span><span className="rounded-full bg-white/80 px-3 py-2 text-xs font-bold text-stone-700">{recipient.memoryEnabled ? "Memory on" : "Memory paused"}</span></div></> : <><h3 className="mt-8 font-serif text-3xl text-[#252D49]">Choose a family member</h3><p className="mt-3 max-w-md text-sm leading-6 text-stone-600">Select someone above to see their check-in history and remembered wellbeing context.</p><Users className="mt-auto h-12 w-12 text-[#72B5FE]" /></>}
            </div>
          </article>

          <aside className="reveal-card flex min-h-64 flex-col rounded-[2rem] bg-[#56619C] p-6 text-white shadow-[0_18px_50px_rgba(86,97,156,0.18)] sm:p-8 lg:col-span-5" style={{ animationDelay: "80ms" }}>
            <span className="text-[11px] font-black uppercase tracking-[0.18em] text-[#D8DCFF]">Next action</span>
            {!demo.family ? <><h3 className="mt-7 font-serif text-3xl">Create your family space</h3><p className="mt-3 text-sm leading-6 text-white/72">Add the first family member before preparing a check-in.</p><a href="#family-dashboard" className="mt-auto inline-flex items-center gap-2 pt-8 text-sm font-bold">Start family setup <ArrowRight className="h-4 w-4" /></a></> : !recipient ? <><h3 className="mt-7 font-serif text-3xl">Choose who you’re helping</h3><p className="mt-3 text-sm leading-6 text-white/72">Select a family member above. Hugback never mixes one person’s calls or memories with another’s.</p><span className="mt-auto inline-flex items-center gap-2 pt-8 text-sm font-bold text-[#D8DCFF]"><Users className="h-4 w-4" /> Waiting for your selection</span></> : !recipient.background.length ? <><h3 className="mt-7 font-serif text-3xl">Help Hugback know {recipient.label}</h3><p className="mt-3 text-sm leading-6 text-white/72">Add a few reviewed conversation excerpts so the first check-in feels personal.</p><button type="button" onClick={() => openStep("background")} className="group mt-auto inline-flex items-center gap-2 pt-8 text-left text-sm font-bold">Add family context <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></button></> : <><h3 className="mt-7 font-serif text-3xl">Test {recipient.label}’s next check-in</h3><p className="mt-3 text-sm leading-6 text-white/72">Their reviewed context is ready. Open the call test to experience the parent side.</p><Link href={callUrl} className="group mt-auto inline-flex items-center gap-2 pt-8 text-sm font-bold">Open call test <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" /></Link></>}
          </aside>

          <article className="reveal-card rounded-[2rem] border border-[#CFE8DE] bg-[#EFF9F4] p-6 sm:p-8 lg:col-span-12" style={{ animationDelay: "110ms" }}>
            <div className="grid gap-8 md:grid-cols-[0.7fr_1.3fr] md:items-start">
              <div><span className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.18em] text-emerald-800"><Activity className="h-4 w-4" /> Today’s conversation signal</span><h3 className="mt-5 font-serif text-3xl text-[#252D49]">A gentle signal, not a diagnosis.</h3></div>
              <div className="rounded-[1.5rem] border border-white bg-white/80 p-5 sm:p-6">
                {!recipient ? <><p className="font-bold text-stone-800">Choose a family member</p><p className="mt-2 text-sm leading-6 text-stone-600">Signals are always kept within the selected person’s separate history.</p></> : recipient.busy ? <p className="flex items-center gap-2 text-sm text-stone-600"><RefreshCw className="h-4 w-4 animate-spin" /> Waiting for this check-in to finish…</p> : latestSignal ? <><div className="flex flex-wrap items-center justify-between gap-2"><span className="rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold capitalize text-emerald-900">{latestSignal.category.replace("_", " ")}</span><time className="text-xs text-stone-500">{formatDate(latestSignal.observedAt)}</time></div><p className="mt-5 text-base leading-7 text-stone-700">{latestSignal.displayText}</p><p className="mt-2 text-xs leading-5 text-stone-500">Based on {latestSignal.basis.map((item) => item.replaceAll("_", " ")).join(", ")}.</p><div className="mt-4 flex flex-wrap gap-2 text-[11px] font-semibold text-stone-500"><span className="rounded-full bg-stone-100 px-2.5 py-1 capitalize">{latestSignal.confidence} confidence</span><span className="rounded-full bg-stone-100 px-2.5 py-1">AI-estimated</span><span className="rounded-full bg-stone-100 px-2.5 py-1">Not medical advice</span></div></> : <><p className="font-bold text-stone-800">No conversation signal available</p><p className="mt-2 text-sm leading-6 text-stone-600">{recipient.wellbeingSharingEnabled ? "Hugback shares nothing when the call does not provide enough evidence." : "This person has not consented to share AI-estimated call signals."}</p></>}
              </div>
            </div>
          </article>

          <article className="reveal-card rounded-[2rem] border border-[#DDD3F7] bg-[#F5F1FF] p-6 sm:p-8 lg:col-span-12" style={{ animationDelay: "140ms" }}>
            <div className="grid gap-8 md:grid-cols-[0.7fr_1.3fr] md:items-start"><div><span className="inline-flex items-center gap-2 text-[11px] font-black uppercase tracking-[0.18em] text-[#664E9D]"><HeartHandshake className="h-4 w-4" /> Parent-approved update</span><h3 className="mt-5 font-serif text-3xl text-[#252D49]">A meaningful update, never a transcript.</h3></div><div className="rounded-[1.5rem] border border-white bg-white/75 p-5 sm:p-6">{busy ? <p className="flex items-center gap-2 text-sm text-stone-600"><RefreshCw className="h-4 w-4 animate-spin" /> Checking for approved updates…</p> : latestSummary ? <><div className="flex flex-wrap items-center justify-between gap-2"><span className="inline-flex items-center gap-1.5 rounded-full bg-[#EDF7FF] px-2.5 py-1 text-xs font-bold text-[#315F89]"><Check className="h-3 w-3" /> Parent approved</span><time className="text-xs text-stone-500">{formatDate(latestSummary.callEndedAt)}</time></div><p className="mt-5 whitespace-pre-wrap text-base leading-7 text-stone-700">{latestSummary.text}</p></> : <><p className="font-bold text-stone-800">No approved update yet</p><p className="mt-2 text-sm leading-6 text-stone-600">{sharing === "ready" ? "When your parent approves a recap, it will appear here." : "Update sharing requires a verified parent relationship and the parent’s approval."}</p></>}</div></div>
          </article>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-24 border-y border-[#E2E5F1] py-16 sm:py-24">
        <div className="grid gap-10 lg:grid-cols-[0.72fr_1.28fr] lg:gap-20">
          <div><p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#56619C]">How Hugback works</p><h2 className="mt-3 font-serif text-4xl leading-tight tracking-[-0.025em] text-[#252D49] sm:text-5xl">Care that continues between your calls.</h2><p className="mt-5 max-w-lg text-sm leading-7 text-stone-600 sm:text-base">Hugback supports the relationship; it does not replace it, monitor emergencies, or pretend to be a family member.</p></div>
          <ol className="space-y-3">
            <li className="reveal-card grid gap-4 rounded-[1.5rem] border border-[#C7E6FF] bg-[#EDF7FF] p-5 sm:grid-cols-[auto_1fr] sm:items-center sm:p-6"><span className="grid h-11 w-11 place-items-center rounded-full bg-[#72B5FE] text-sm font-black text-[#252D49]">1</span><div><h3 className="font-serif text-xl text-[#252D49]">A gentle voice check-in</h3><p className="mt-1 text-sm leading-6 text-stone-600">Hugback calls through the demo experience, introduces itself as AI, listens, and responds in a natural voice conversation.</p></div></li>
            <li className="reveal-card grid gap-4 rounded-[1.5rem] border border-[#D9CDF8] bg-white p-5 sm:grid-cols-[auto_1fr] sm:items-center sm:p-6" style={{ animationDelay: "70ms" }}><span className="grid h-11 w-11 place-items-center rounded-full bg-[#B69CF2] text-sm font-black text-[#252D49]">2</span><div><h3 className="font-serif text-xl text-[#252D49]">Relevant context can carry forward</h3><p className="mt-1 text-sm leading-6 text-stone-600">With consent, the demo can retain bounded wellbeing notes so a future check-in can follow up. Each parent’s memory stays separate.</p></div></li>
            <li className="reveal-card grid gap-4 rounded-[1.5rem] border border-[#CFCFFE] bg-[#F0F1FF] p-5 sm:grid-cols-[auto_1fr] sm:items-center sm:p-6" style={{ animationDelay: "140ms" }}><span className="grid h-11 w-11 place-items-center rounded-full bg-[#9BA5FC] text-sm font-black text-[#252D49]">3</span><div><h3 className="font-serif text-xl text-[#252D49]">Your parent controls what is shared</h3><p className="mt-1 text-sm leading-6 text-stone-600">You see a short recap only after your parent approves its exact content—not a transcript or access to private memories.</p></div></li>
          </ol>
        </div>
      </section>

      <section id="setup-workspace" className="scroll-mt-24 py-16 sm:py-24">
        <div className="max-w-3xl"><p className="text-[11px] font-black uppercase tracking-[0.18em] text-[#56619C]">Setup and manage</p><h2 className="mt-3 font-serif text-4xl leading-tight tracking-[-0.025em] text-[#252D49] sm:text-5xl">Prepare each check-in with care.</h2><p className="mt-4 text-sm leading-7 text-stone-600 sm:text-base">Follow the three steps in order. The optional voice setup changes how Hugback sounds; it never changes whose memories are used.</p></div>

        <nav aria-label="Three-step child portal setup" className="mt-10 grid gap-3 md:grid-cols-3">
          {sections.map(({ id, step, label, icon: Icon, detail }) => {
            const tone = sectionStyles[id];
            const isActive = section === id;
            return <button key={id} type="button" onClick={() => setSection(id)} aria-current={isActive ? "step" : undefined} className={`group rounded-[1.5rem] border p-5 text-left transition duration-200 hover:-translate-y-0.5 hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#56619C] ${isActive ? tone.active : tone.tab}`}>
              <span className="flex items-center justify-between gap-3"><span className={`grid h-10 w-10 place-items-center rounded-xl ${tone.icon}`}><Icon className="h-5 w-5" /></span><span className="text-xs font-black uppercase tracking-[0.16em] text-stone-500">Step {step} of 3</span></span>
              <span className="mt-5 block font-serif text-xl text-[#252D49]">{label}</span><span className="mt-1.5 block text-xs leading-5 text-stone-600">{detail}</span><span className={`mt-4 inline-flex items-center gap-1 text-xs font-bold ${tone.eyebrow}`}>{isActive ? "Open now" : `Go to step ${step}`} <ChevronRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5" /></span>
            </button>;
          })}
        </nav>

        <section key={section} className={`step-panel-enter relative mt-6 overflow-hidden rounded-[2rem] border p-5 sm:p-8 ${sectionStyles[section].panel}`}>
          <div className="mb-7 flex items-center gap-4 border-b border-white pb-6"><span className={`grid h-12 w-12 shrink-0 place-items-center rounded-xl ${sectionStyles[section].icon}`}><ActiveIcon className="h-5 w-5" /></span><div><p className={`text-[10px] font-black uppercase tracking-[0.18em] ${sectionStyles[section].eyebrow}`}>Step {activeStepIndex + 1} of 3</p><h3 className="mt-1 font-serif text-3xl text-[#252D49]">{activeSection.label}</h3></div></div>

          {section === "background" && (status?.localDemoEnabled && demo.family && !recipient ? <div className="rounded-[1.5rem] border border-white bg-white/80 px-6 py-14 text-center"><span className="mx-auto grid h-12 w-12 place-items-center rounded-full bg-[#D8EEFF] text-[#315F89]"><Users className="h-5 w-5" /></span><h4 className="mt-4 font-serif text-2xl text-[#252D49]">Choose a family member first</h4><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-stone-600">Select someone in the family dashboard above, then return here to prepare their context.</p></div> : <BackgroundImports key={recipient?.recipientId || "local-preview"} owner={identity?.owner} demoRecipient={status?.localDemoEnabled ? recipient : undefined} onDemoChange={demo.update} />)}
          {section === "voice" && <VoiceEnrollment voice={status?.voice} disabled={!identity} onUpdated={refreshVoice} />}
          {section === "summaries" && <div className="space-y-4">
            <div className="flex items-center justify-between gap-3 rounded-[1.5rem] border border-white bg-white/75 p-5"><div><h4 className="font-serif text-xl text-[#252D49]">Updates shared with you</h4><p className="mt-1 text-sm leading-6 text-stone-600">Approved recaps only—never a transcript or private memory.</p></div><button className="portal-secondary shrink-0" disabled={busy} onClick={() => setRevision((value) => value + 1)} aria-label="Refresh summaries"><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /></button></div>
            {!visibleSummaries.length && <div className="rounded-[1.5rem] border border-white bg-white/75 px-6 py-12 text-center"><MessageCircle className="mx-auto h-8 w-8 text-[#9BA5FC]" /><h4 className="mt-4 font-bold text-stone-800">{busy ? "Checking for updates…" : "Nothing new to share"}</h4><p className="mx-auto mt-2 max-w-md text-sm leading-6 text-stone-600">{sharing === "ready" ? "An update appears only after your parent approves it." : "Sharing is private by default and requires a verified parent relationship."}</p></div>}
            {visibleSummaries.map((summary, index) => <article key={summary.id} className="dashboard-enter rounded-[1.5rem] border border-white bg-white/85 p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-md" style={{ animationDelay: `${index * 60}ms` }}><div className="flex flex-wrap items-center justify-between gap-2"><time className="text-xs text-stone-500">{formatDate(summary.callEndedAt)}</time><span className="inline-flex items-center gap-1.5 rounded-full bg-[#EDF7FF] px-2.5 py-1 text-xs font-bold text-[#315F89]"><Check className="h-3 w-3" /> Parent approved</span></div><p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-stone-700">{summary.text}</p></article>)}
          </div>}

          <div className={`mt-7 flex flex-col gap-3 rounded-[1.25rem] border p-4 sm:flex-row sm:items-center sm:justify-between ${sectionStyles[section].tab}`}><div><p className={`text-[10px] font-black uppercase tracking-[0.16em] ${sectionStyles[section].eyebrow}`}>{nextSection ? `Next · Step ${activeStepIndex + 2}` : "Setup complete"}</p><p className="mt-1 text-sm font-semibold text-stone-700">{nextSection ? `Continue to ${nextSection.label.toLowerCase()} when you’re ready.` : "Review or update any step whenever you need."}</p></div>{nextSection ? <button type="button" onClick={() => openStep(nextSection.id)} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-[#56619C] px-5 py-2.5 text-sm font-bold text-white transition hover:-translate-y-0.5 hover:bg-[#465181]">Continue <ArrowRight className="h-4 w-4" /></button> : <button type="button" onClick={() => openStep("background")} className="portal-secondary shrink-0">Review from step 1</button>}</div>
        </section>
      </section>

      <footer className="grid gap-4 border-t border-[#E2E5F1] py-8 text-xs leading-5 text-stone-500 sm:grid-cols-[1fr_auto] sm:items-center"><p className="flex max-w-2xl items-start gap-2"><LockKeyhole className="mt-0.5 h-4 w-4 shrink-0 text-[#56619C]" /><span><strong className="text-stone-700">Your browser is your key.</strong> Clearing site data or changing devices can lose access. Hugback is not an emergency or monitoring service.</span></p><Link href={callUrl} className="inline-flex items-center gap-2 font-bold text-[#56619C] transition hover:gap-3">Open call test <ArrowRight className="h-3.5 w-3.5" /></Link></footer>
    </div>
  </main>;
}
