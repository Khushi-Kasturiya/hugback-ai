"use client";

import Link from "next/link";
import { useState } from "react";
import { DemoFamily, DemoRecipient, demoRequest, parentCallUrl } from "@/lib/demo-api";
import type { PortalStatus } from "@/lib/portal-api";

export function DemoFamilySetup({ family, onChange, loading, loadError, refresh, selectedId, onSelect, voice }: {
  family?: DemoFamily; onChange: (family: DemoFamily) => void;
  loading: boolean; loadError: string; refresh: () => Promise<void>;
  selectedId: string; onSelect: (id: string) => void; voice?: PortalStatus["voice"];
}) {
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("Mother");
  const [relationship, setRelationship] = useState<DemoRecipient["relationship"]>("mother");
  const [synthetic, setSynthetic] = useState(false);
  const [child, setChild] = useState(false);
  const [parent, setParent] = useState(false);
  const [memory, setMemory] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const selected = family?.recipients.find((item) => item.recipientId === selectedId);
  const currentVoice = voice?.profile;
  const childVoiceAvailable = !!(voice?.replicatedTtsEnabled && currentVoice?.enabled && !currentVoice.expired && Date.parse(currentVoice.expiresAt) > Date.now());
  const assignedVoiceUnavailable = selected?.voice.mode === "child" && (!childVoiceAvailable || selected.voice.profileId !== currentVoice?.id);

  async function create() {
    if (!synthetic || !child || !parent || !label.trim() || busy) return;
    setBusy(true); setError("");
    try {
      const result = await demoRequest(family ? "/recipients" : "/family", "POST", {
        syntheticOnly: true, simulateChildConsent: true, simulateParentConsent: true,
        enableMemory: memory, timeZone: "Asia/Kolkata", label: label.trim(), relationship,
      });
      onChange(result);
      const created = result.recipients.find((r) => r.label === label.trim());
      if (created) onSelect(created.recipientId);
      setAdding(false); setSynthetic(false); setChild(false); setParent(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Recipient setup failed."); }
    finally { setBusy(false); }
  }
  async function selectVoice(mode: "standard" | "child") {
    if (!selected || busy || selected.busy || (mode === "child" && !childVoiceAvailable)) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/recipient-voice", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        mode, profileId: mode === "child" ? currentVoice?.id : null,
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Voice assignment failed."); }
    finally { setBusy(false); }
  }
  return <section className="mb-8 rounded-2xl border border-emerald-200 bg-emerald-50/60 p-5 sm:p-6">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><p className="text-xs font-bold uppercase tracking-widest text-emerald-800">Hackathon · Family setup</p>
        <h2 className="mt-2 text-xl font-semibold">One family. A separate memory for each person.</h2></div>
      {family && <button className="portal-secondary" disabled={busy || family.recipients.length >= 8} onClick={() => { setAdding(!adding); setSynthetic(false); setChild(false); setParent(false); setError(""); }}>{adding ? "Cancel adding" : "+ Add recipient"}</button>}
    </div>
    <p className="mt-2 text-sm leading-6 text-stone-600">One adult child can prepare calls for Mother, Father or another relative. Choose the recipient before importing background or calling. This local simulator does not recognize or verify who is speaking.</p>
    {family && <>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="group" aria-label="Family recipients">
        {family.recipients.map((r) => <button key={r.recipientId} type="button" aria-pressed={r.recipientId === selectedId} disabled={busy}
          onClick={() => { onSelect(r.recipientId); setError(""); }}
          className={`min-w-0 rounded-xl border p-4 text-left transition ${r.recipientId === selectedId ? "border-emerald-800 bg-emerald-900 text-white" : "border-stone-200 bg-white text-stone-700 hover:border-emerald-500"}`}>
          <span className="block break-words font-bold">{r.label}</span>
          <span className="mt-1 block text-xs opacity-80">{r.background.length} excerpts · {r.calls.length} calls · {r.voice.mode === "child" ? "Child voice assigned" : "Standard voice"}</span>
          {r.busy && <span className="mt-2 block text-xs font-semibold">Call active / saving memory</span>}
        </button>)}
      </div>
      {selected ? <div className="mt-4 rounded-xl border border-emerald-200 bg-white/80 p-4 text-sm">
        <p className="font-semibold">Preparing for {selected.label}</p>
        <p className="mt-1 text-xs leading-5 text-stone-600">Only this recipient’s background, calls and memory are used. {selected.memoryEnabled ? "Wellbeing memory enabled." : "Wellbeing memory off or paused."}</p>
        {selected.legacy && <p className="mt-2 text-xs leading-5 text-amber-800">Preserved from the old single-parent demo. Its history has not been assumed to belong to Mother or Father. Add new recipients for clean, separate histories; old background remains here.</p>}
        <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label={`Voice for ${selected.label}`}>
          <span className="mr-1 text-xs font-bold uppercase tracking-wide text-stone-500">Elara’s voice</span>
          <button className="portal-secondary" aria-pressed={selected.voice.mode === "standard"} disabled={busy || selected.busy || selected.voice.mode === "standard"} onClick={() => void selectVoice("standard")}>Use standard voice</button>
          <button className="portal-secondary" aria-pressed={selected.voice.mode === "child" && !assignedVoiceUnavailable} disabled={busy || selected.busy || !childVoiceAvailable || (selected.voice.mode === "child" && !assignedVoiceUnavailable)} onClick={() => void selectVoice("child")}>Assign child voice</button>
        </div>
        {!childVoiceAvailable && <p className="mt-2 text-xs leading-5 text-stone-500">Create and enable your own voice in Voice setup first, then assign it here. The same authorized voice can be assigned to multiple recipients without sharing their memories.</p>}
        {assignedVoiceUnavailable && <p role="alert" className="mt-2 text-xs leading-5 text-rose-800">The assigned child voice is unavailable or was replaced. Reassign an enabled voice or explicitly choose standard voice before calling.</p>}
        {selected.busy ? <p role="status" className="mt-3 text-xs text-amber-800">Wait for this recipient’s call and memory update before changing their setup.</p> : !assignedVoiceUnavailable && <Link className="portal-primary mt-4 inline-flex" href={parentCallUrl(selected.recipientId)}>Test a call as {selected.label} →</Link>}
      </div> : <p role="status" className="mt-4 text-sm font-semibold text-emerald-900">Select a recipient above. Nothing is selected automatically.</p>}
      <p className="mt-3 text-xs leading-5 text-stone-500">Separate recipient histories persist in local SQLite until {new Date(family.expiresAt).toLocaleDateString()}. No Firebase storage or recap sharing. Up to eight recipients.</p>
    </>}
    {(!family || adding) && !loading && !loadError && <div className="mt-5 space-y-3 rounded-xl border border-stone-200 bg-white p-4 text-sm">
      <h3 className="font-bold">{family ? "Add a recipient with their own history" : "Create a family and its first recipient"}</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="portal-label">Relationship<select className="portal-input" disabled={busy} value={relationship} onChange={(e) => { setRelationship(e.target.value as DemoRecipient["relationship"]); setLabel(e.target.selectedOptions[0].text); }}>
          <option value="mother">Mother</option><option value="father">Father</option><option value="grandmother">Grandmother</option><option value="grandfather">Grandfather</option><option value="other">Other</option>
        </select></label>
        <label className="portal-label">Recipient label<input className="portal-input" value={label} maxLength={40} disabled={busy} onChange={(e) => setLabel(e.target.value)} /></label>
      </div>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} className="mt-1" />I will use fictional chats and role-play only, not real family data.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={child} onChange={(e) => setChild(e.target.checked)} className="mt-1" />Simulate the child agreeing to setup for this recipient.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={parent} onChange={(e) => setParent(e.target.checked)} className="mt-1" />Simulate this recipient agreeing to their own demo setup.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={memory} onChange={(e) => setMemory(e.target.checked)} className="mt-1" />Simulate this recipient consenting to cross-call wellbeing memory. Google processes their demo transcript after calls; only bounded concerns are saved locally.</label>
      <button className="portal-primary" disabled={busy || !synthetic || !child || !parent || !label.trim()} onClick={() => void create()}>{busy ? "Saving…" : family ? "Add recipient" : "Create local demo family"}</button>
    </div>}
    {loading && !family && <p role="status" className="mt-3 text-sm">Checking local demo family…</p>}
    {(error || loadError) && <p role="alert" className="mt-3 text-sm text-rose-800">{error || loadError}</p>}
    {(error || loadError) && <button className="portal-secondary mt-3" disabled={busy || loading} onClick={() => { setError(""); void refresh(); }}>Refresh family</button>}
  </section>;
}
