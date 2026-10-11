"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, AudioLines, BookOpen, FileText, HeartHandshake, LockKeyhole, RefreshCw, Sparkles } from "lucide-react";
import { VoiceEnrollment } from "@/components/VoiceEnrollment";
import { BackgroundImports } from "@/components/BackgroundImports";
import { getBrowserIdentity } from "@/lib/identity";
import { PortalStatus, SharedSummary, portalGet } from "@/lib/portal-api";
import { DemoFamilySetup } from "@/components/DemoFamilySetup";
import { parentCallUrl } from "@/lib/demo-api";
import { useDemoFamily } from "@/hooks/useDemoFamily";

const sections = [
  { id: "background", label: "Background", icon: BookOpen, detail: "A little family context" },
  { id: "summaries", label: "Call summaries", icon: FileText, detail: "Only what’s shared with you" },
  { id: "voice", label: "Voice setup", icon: AudioLines, detail: "A familiar way to talk" },
] as const;
type Section = typeof sections[number]["id"];

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
  const callUrl = demo.family ? parentCallUrl(recipient?.recipientId) : "/";

  async function refreshVoice() {
    try { setStatus(await portalGet<PortalStatus>("/status")); }
    catch { setError("Could not refresh voice availability. Retry the backend before assigning a voice."); }
  }

  useEffect(() => {
    if (section !== "summaries") return;
    const refresh = () => {
      setNow(Date.now());
      if (document.visibilityState === "visible") setRevision((n) => n + 1);
    };
    const clock = window.setInterval(() => setNow(Date.now()), 1000);
    const timer = window.setInterval(refresh, 60_000);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(clock); window.clearInterval(timer);
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
      } catch (err) {
        if (current) setError(err instanceof Error ? err.message : "Could not load this browser's portal.");
      } finally { if (current) setBusy(false); }
    })();
    return () => { current = false; };
  }, [revision]);
  const visibleSummaries = summaries.filter((s) => Date.parse(s.expiresAt) > now);

  return <main className="mx-auto min-h-screen max-w-6xl px-5 py-6 sm:px-8 sm:py-8">
    <header className="flex flex-wrap items-center justify-between gap-4 border-b border-stone-200 pb-6">
      <Link href="/" className="flex items-center gap-3 rounded-lg focus-visible:outline-emerald-700">
        <span className="rounded-full bg-amber-100 p-2.5 text-amber-800"><Sparkles className="h-5 w-5" /></span>
        <span><span className="block text-xl font-bold tracking-tight">Elara</span><span className="text-xs text-stone-500">A little closer, every day.</span></span>
      </Link>
      <div className="flex flex-wrap items-center gap-4">
        <span className="inline-flex items-center gap-1.5 rounded-full border border-stone-200 bg-white px-3 py-1.5 text-xs font-medium text-stone-600">
          <span className={`h-1.5 w-1.5 rounded-full ${identity ? "bg-emerald-600" : "bg-stone-400"}`} />
          {identity?.mode === "firebase" ? "Anonymous Firebase session" : identity ? "Local browser session" : "Connecting"}
        </span>
        <Link href={callUrl} className="inline-flex items-center gap-1.5 text-xs font-semibold text-stone-600 hover:text-emerald-800"><ArrowLeft className="h-3.5 w-3.5" /> {demo.family ? "Parent call test" : "Call test"}</Link>
      </div>
    </header>

    <section className="pb-8 pt-10 sm:pt-12">
      <p className="text-xs font-bold uppercase tracking-[0.18em] text-emerald-800">Internal setup simulator · Local testing</p>
      <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">More context. More thoughtful conversations.</h1>
      <p className="mt-3 max-w-2xl text-sm leading-6 text-stone-600">Test recipient-specific background and voice setup with fictional family profiles. The product remains phone-first, with Forms/Drive setup—not a parent app or child dashboard.</p>
    </section>

    <nav aria-label="Child portal sections" className="mb-8 grid grid-cols-3 gap-2 sm:gap-3">
      {sections.map(({ id, label, icon: Icon, detail }) => <button key={id} type="button" onClick={() => setSection(id)} aria-current={section === id ? "page" : undefined}
        className={`flex min-w-0 flex-col items-center gap-2 rounded-2xl border px-2 py-4 text-center transition focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 sm:flex-row sm:gap-3 sm:px-5 sm:text-left ${section === id ? "border-emerald-900 bg-emerald-900 text-white shadow-sm" : "border-stone-200/80 bg-white/70 text-stone-600 hover:border-emerald-200 hover:bg-emerald-50"}`}>
        <Icon aria-hidden="true" className="h-4 w-4 shrink-0 sm:h-5 sm:w-5" />
        <span className="min-w-0"><span className="block text-xs font-semibold sm:text-sm">{label}</span><span className={`mt-1 hidden text-xs leading-5 sm:block ${section === id ? "text-emerald-100" : "text-stone-500"}`}>{detail}</span></span>
      </button>)}
    </nav>

    {status?.localDemoEnabled && <DemoFamilySetup family={demo.family} onChange={demo.update} loading={demo.loading} loadError={demo.error} refresh={demo.refresh} selectedId={selectedId} onSelect={setSelectedId} voice={status.voice} />}

    <div className="min-w-0">
        {error && <div role="alert" className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-950">
          <p>{error}</p><button className="mt-2 inline-flex items-center gap-1.5 font-semibold underline underline-offset-4 disabled:opacity-50" disabled={busy} onClick={() => setRevision((n) => n + 1)}><RefreshCw className="h-3.5 w-3.5" /> Retry backend</button>
        </div>}
        {section === "background" && (status?.localDemoEnabled && demo.family && !recipient
          ? <p className="rounded-2xl border border-stone-200 bg-white p-6 text-sm text-stone-600">Choose a recipient above to prepare their background. Histories are never shared automatically.</p>
          : <BackgroundImports key={recipient?.recipientId || "local-preview"} owner={identity?.owner} demoRecipient={status?.localDemoEnabled ? recipient : undefined} onDemoChange={demo.update} />)}
        {section === "voice" && <div className="space-y-5">
          <div><h2 className="text-2xl font-bold tracking-tight">One clear, disclosed AI voice.</h2><p className="mt-2 text-sm leading-6 text-stone-600">Create and enable your own voice with Google, then assign it separately to recipients above. Elara always introduces itself as AI.</p></div>
          <VoiceEnrollment voice={status?.voice} disabled={!identity} onUpdated={refreshVoice} />
        </div>}
        {section === "summaries" && <div className="space-y-5">
          <div className="flex items-start justify-between gap-3">
            <div><h2 className="text-2xl font-bold tracking-tight">Updates, with permission.</h2><p className="mt-2 text-sm leading-6 text-stone-600">A short recap—not a transcript or a view into private memories.</p></div>
            <button className="portal-secondary shrink-0" disabled={busy} onClick={() => setRevision((n) => n + 1)} aria-label="Refresh summaries"><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} /></button>
          </div>
          {busy ? <p role="status" className="text-sm text-stone-500">Checking approved updates…</p> : !visibleSummaries.length && <div className="rounded-2xl border border-stone-200 bg-white px-6 py-12 text-center">
            <span className="inline-flex rounded-full bg-emerald-50 p-4 text-emerald-800"><HeartHandshake className="h-8 w-8" /></span>
            <h3 className="mt-5 text-lg font-bold">{error ? "Updates are unavailable" : sharing === "ready" ? "No approved updates yet" : "Parent-approved summaries aren’t connected yet"}</h3>
            <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-stone-500">{error ? "We couldn’t confirm the backend state. This does not mean there are no updates." : sharing === "development_only" ? "This local browser ID is for testing only. Private call records are never loaded with a development ID." : sharing === "ready" ? "A recap appears only after your parent approves its exact content for you." : "A verified parent relationship and the parent’s approval are required. Anonymous access alone does not grant permission to read calls."}</p>
          </div>}
          {visibleSummaries.map((summary) => <article key={summary.id} className="rounded-2xl border border-stone-200 bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-2"><time className="text-xs text-stone-500">{new Date(summary.callEndedAt).toLocaleString()}</time><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-800">Parent approved</span></div>
            <p className="mt-4 whitespace-pre-wrap break-words text-sm leading-7">{summary.text}</p>
            <p className="mt-4 text-xs text-stone-400">Available until {new Date(summary.expiresAt).toLocaleString()}</p>
          </article>)}
          <div className="rounded-xl bg-stone-100/70 p-4 text-xs leading-6 text-stone-600"><strong>Email notifications are not connected.</strong> The planned email is a neutral notice linking here, not a sensitive summary. Elara is not an emergency or monitoring service.</div>
        </div>}
    </div>
    <footer className="mt-12 flex flex-wrap items-center justify-between gap-3 border-t border-stone-200 py-6 text-xs leading-5 text-stone-500">
      <p>Elara is AI. Your parent’s conversation stays theirs.</p>
      <Link href={callUrl} className="inline-flex items-center gap-1.5 font-semibold hover:text-emerald-800">Back to {demo.family ? "parent call test" : "call test"} <ArrowRight className="h-3.5 w-3.5" /></Link>
      <p className="flex w-full items-start gap-2"><LockKeyhole aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /><span>Same browser, same origin. Clearing site data, switching devices, or changing from localhost to 127.0.0.1 can lose access. There is no account recovery yet.</span></p>
    </footer>
  </main>;
}
