"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
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
  const [wellbeingSharing, setWellbeingSharing] = useState(false);
  const [toneContinuity, setToneContinuity] = useState(false);
  const [transcriptSharing, setTranscriptSharing] = useState(false);
  const [transcriptConsent, setTranscriptConsent] = useState(false);
  const [alertSharing, setAlertSharing] = useState(false);
  const [alertConsent, setAlertConsent] = useState(false);
  const [testEmail, setTestEmail] = useState("");
  const [testEmailConfirmation, setTestEmailConfirmation] = useState(false);
  const [signalConsent, setSignalConsent] = useState(false);
  const [toneConsent, setToneConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState<NonNullable<DemoRecipient["language"]>>("auto");
  const [childGender, setChildGender] = useState<"female" | "male" | "neutral" | "">(family?.childGender ?? "");
  useEffect(() => { setSignalConsent(false); setToneConsent(false); setTranscriptConsent(false); setAlertConsent(false); setError(""); }, [selectedId]);
  useEffect(() => { setChildGender(family?.childGender ?? ""); }, [family?.familyId, family?.childGender]);
  const selected = family?.recipients.find((item) => item.recipientId === selectedId);
  const currentVoice = voice?.profile;
  const childVoiceAvailable = !!(voice?.replicatedTtsEnabled && currentVoice?.enabled && !currentVoice.expired && Date.parse(currentVoice.expiresAt) > Date.now());
  const assignedVoiceUnavailable = selected?.voice.mode === "child" && (!childVoiceAvailable || selected.voice.profileId !== currentVoice?.id);

  async function create() {
    if (!synthetic || !child || !parent || !label.trim() || busy || (!family && !childGender)) return;
    setBusy(true); setError("");
    try {
      const result = await demoRequest(family ? "/recipients" : "/family", "POST", {
        syntheticOnly: true, simulateChildConsent: true, simulateParentConsent: true,
        enableMemory: memory, timeZone: "Asia/Kolkata", label: label.trim(), relationship,
        enableWellbeingSharing: wellbeingSharing, enableToneContinuity: toneContinuity,
        simulateToneConsent: toneContinuity,
        enableTranscriptSharing: transcriptSharing,
        enableAlertSharing: alertSharing && transcriptSharing, language,
        ...(!family ? { childGender } : {}),
      });
      onChange(result);
      const created = result.recipients.find((r) => r.label === label.trim());
      if (created) onSelect(created.recipientId);
      setAdding(false); setSynthetic(false); setChild(false); setParent(false); setWellbeingSharing(false); setToneContinuity(false); setTranscriptSharing(false); setAlertSharing(false);
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
  async function saveChildGender() {
    if (!family || !childGender || childGender === family.childGender || busy) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/child-details", "PUT", {
        syntheticOnly: true, familyId: family.familyId,
        revision: family.childGenderRevision ?? 0, childGender,
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Child details could not be saved."); }
    finally { setBusy(false); }
  }
  async function setSignalSharing(enabled: boolean) {
    if (!selected || busy || selected.busy || (enabled && !signalConsent)) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/wellbeing-sharing", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
      setSignalConsent(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Call signal sharing update failed."); }
    finally { setBusy(false); }
  }
  async function setToneMemory(enabled: boolean) {
    if (!selected || busy || selected.busy || (enabled && !toneConsent)) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/tone-continuity", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
      setToneConsent(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Voice-tone setting update failed."); }
    finally { setBusy(false); }
  }
  async function setCallHistory(enabled: boolean) {
    if (!selected || busy || selected.busy || (enabled && !transcriptConsent)) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/transcript-sharing", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
      setTranscriptConsent(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Call history update failed."); }
    finally { setBusy(false); }
  }
  async function setTopicAlerts(enabled: boolean) {
    if (!selected || busy || selected.busy || (enabled && (!alertConsent || !selected.transcriptSharingEnabled))) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/alert-sharing", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
      setAlertConsent(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Call alert update failed."); }
    finally { setBusy(false); }
  }
  async function saveTestEmail(enabled: boolean) {
    if (!family || busy || (enabled && (!testEmailConfirmation || !testEmail.trim()))) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/alert-destination", "PUT", {
        syntheticOnly: true, familyId: family.familyId,
        email: enabled ? testEmail.trim() : null,
        confirmTestRecipient: enabled,
      }));
      setTestEmailConfirmation(false);
    } catch (err) { setError(err instanceof Error ? err.message : "Test email setup failed."); }
    finally { setBusy(false); }
  }
  return <section>
    <div className="flex flex-wrap items-start justify-between gap-3">
      <p className="max-w-2xl text-sm leading-6 text-stone-600">Choose the person whose bridge you want to prepare. Their family language, calls and signals always stay separate from everyone else’s.</p>
      {family && <button className="portal-secondary" disabled={busy || family.recipients.length >= 8} onClick={() => { setAdding(!adding); setSynthetic(false); setChild(false); setParent(false); setWellbeingSharing(false); setToneContinuity(false); setTranscriptSharing(false); setAlertSharing(false); setSignalConsent(false); setToneConsent(false); setTranscriptConsent(false); setAlertConsent(false); setError(""); }}>{adding ? "Cancel" : "+ Add recipient"}</button>}
    </div>
    {family && <>
      <div className="mt-5 rounded-2xl border border-[#DDE2F0] bg-white p-4 text-sm">
        <p className="font-bold text-stone-800">Child details</p>
        <p className="mt-1 text-xs leading-5 text-stone-600">Used only for HugBack’s Hindi/Hinglish first-person wording when it speaks in the child’s recorded voice. The standard voice stays feminine. This does not analyze the recording or identify a speaker.</p>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <label className="portal-label">Child gender
            <select className="portal-input" value={childGender} disabled={busy} onChange={(event) => setChildGender(event.target.value as typeof childGender)}>
              <option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="neutral">Another identity · use neutral phrasing</option>
            </select>
          </label>
          <button type="button" className="portal-secondary" disabled={busy || !childGender || childGender === family.childGender} onClick={() => void saveChildGender()}>Save child details</button>
        </div>
        {!family.childGender && <p className="mt-2 text-xs text-amber-800">Set this before the next child-voice call. Existing families keep neutral phrasing until you save it.</p>}
      </div>
      <div className="mt-5 flex flex-wrap gap-3" role="group" aria-label="Family recipients">
        {family.recipients.map((r) => <button key={r.recipientId} type="button" aria-pressed={r.recipientId === selectedId} disabled={busy}
          onClick={() => { onSelect(r.recipientId); setError(""); }}
          className={`min-w-32 rounded-full border px-5 py-3 text-left transition-all duration-200 ${r.recipientId === selectedId ? "-translate-y-0.5 border-[#56619C] bg-[#56619C] text-white shadow-md" : "border-[#DDE2F0] bg-[#F7F8FC] text-stone-700 hover:-translate-y-0.5 hover:border-[#9BA5FC] hover:bg-white"}`}>
          <span className="block break-words text-sm font-bold">{r.label}</span>
          <span className="mt-0.5 block text-[10px] opacity-75">{r.calls.length} {r.calls.length === 1 ? "check-in" : "check-ins"}{r.busy ? " · active" : ""}</span>
        </button>)}
      </div>
      {selected ? <div className="dashboard-enter mt-5 rounded-2xl border border-[#D7EAFE] bg-[#F1F8FF] p-5 text-sm">
        <div className="flex flex-wrap items-center justify-between gap-3"><div><p className="font-bold text-stone-800">{selected.label} is selected</p><p className="mt-1 text-xs leading-5 text-stone-600">{selected.background.length} reviewed excerpts · {selected.memoryEnabled ? "Memory on" : "Memory paused"} · {selected.wellbeingSharingEnabled ? "Call signals shared" : "Call signals private"} · {selected.toneContinuityEnabled ? "Gentle tone check-ins on" : "Tone check-ins off"} · {selected.transcriptSharingEnabled ? "Future call summaries on" : "Future call summaries off"}</p></div>{selected.busy && <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-[#56619C]">Check-in active</span>}</div>
        {selected.legacy && <p className="mt-2 text-xs leading-5 text-amber-800">Preserved from the old single-parent demo. Its history has not been assumed to belong to Mother or Father. Add new recipients for clean, separate histories; old background remains here.</p>}
        <div className="mt-4 flex flex-wrap items-center gap-2" role="group" aria-label={`Voice for ${selected.label}`}>
          <span className="mr-1 text-xs font-bold text-stone-600">Voice</span>
          <button className="portal-secondary" aria-pressed={selected.voice.mode === "standard"} disabled={busy || selected.busy || selected.voice.mode === "standard"} onClick={() => void selectVoice("standard")}>Use standard voice</button>
          <button className="portal-secondary" aria-pressed={selected.voice.mode === "child" && !assignedVoiceUnavailable} disabled={busy || selected.busy || !childVoiceAvailable || (selected.voice.mode === "child" && !assignedVoiceUnavailable)} onClick={() => void selectVoice("child")}>Assign child voice</button>
        </div>
        {selected.voice.mode === "child" && !family.childGender && <p className="mt-2 text-xs leading-5 text-amber-800">Save the child’s gender in Child details above for matching Hindi/Hinglish wording. No new recording is needed.</p>}
        {!childVoiceAvailable && <p className="mt-2 text-xs leading-5 text-stone-500">Create and enable your own voice in Voice setup first, then assign it here. The same authorized voice can be assigned to multiple recipients without sharing their memories.</p>}
        {assignedVoiceUnavailable && <p role="alert" className="mt-2 text-xs leading-5 text-rose-800">The assigned child voice is unavailable or was replaced. Reassign an enabled voice or explicitly choose standard voice before calling.</p>}
        <div className="mt-4 border-t border-[#D7EAFE] pt-4">
          <p className="text-xs font-bold text-stone-700">AI-estimated call signals</p>
          {selected.wellbeingSharingEnabled ? <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setSignalSharing(false)}>Stop sharing call signals</button> : <><label className="mt-2 flex items-start gap-2 text-xs leading-5 text-stone-600"><input type="checkbox" checked={signalConsent} disabled={busy || selected.busy} onChange={(event) => setSignalConsent(event.target.checked)} className="mt-1" />Simulate both the child and {selected.label} agreeing to share bounded, non-medical call signals.</label><button className="portal-secondary mt-2" disabled={busy || selected.busy || !signalConsent} onClick={() => void setSignalSharing(true)}>Enable call signals</button></>}
        </div>
        <div className="mt-4 border-t border-[#D7EAFE] pt-4">
          <p className="text-xs font-bold text-stone-700">Gentle voice-tone check-ins</p>
          <p className="mt-1 text-xs leading-5 text-stone-600">HugBack may ask once if a clear vocal cue suggests {selected.label} sounds quieter or more upbeat. After a call, only one model-marked high-confidence cue can be kept for up to 72 hours to guide the next selected-recipient call. This is an estimate, not a mood measurement. No recording or voiceprint is saved, and this does not identify who is speaking or send an email.</p>
          {selected.toneContinuityEnabled ? <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setToneMemory(false)}>Stop tone check-ins and erase tone note</button> : <><label className="mt-2 flex items-start gap-2 text-xs leading-5 text-stone-600"><input type="checkbox" checked={toneConsent} disabled={busy || selected.busy} onChange={(event) => setToneConsent(event.target.checked)} className="mt-1" />Simulate both the child and {selected.label} agreeing to these tentative voice-tone check-ins across fictional calls.</label><button className="portal-secondary mt-2" disabled={busy || selected.busy || !toneConsent} onClick={() => void setToneMemory(true)}>Enable gentle tone check-ins</button></>}
        </div>
        <div className="mt-4 border-t border-[#D7EAFE] pt-4">
          <p className="text-xs font-bold text-stone-700">Future call summaries</p>
          <p className="mt-1 text-xs leading-5 text-stone-600">When enabled, future fictional calls may produce a short AI summary for this recipient. Signals back shows the summary, not the turn-by-turn text. Calls made while this setting was off have no saved text and cannot be summarized later.</p>
          {selected.transcriptSharingEnabled ? <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setCallHistory(false)}>Stop sharing and erase saved call text and summaries</button> : <><label className="mt-2 flex items-start gap-2 text-xs leading-5 text-stone-600"><input type="checkbox" checked={transcriptConsent} disabled={busy || selected.busy} onChange={(event) => setTranscriptConsent(event.target.checked)} className="mt-1" />Simulate both the child and {selected.label} agreeing once to share AI summaries of future fictional calls.</label><button className="portal-secondary mt-2" disabled={busy || selected.busy || !transcriptConsent} onClick={() => void setCallHistory(true)}>Enable future call summaries</button></>}
        </div>
        <div className="mt-4 border-t border-[#D7EAFE] pt-4">
          <p className="text-xs font-bold text-stone-700">Automatic topic email</p>
          <p className="mt-1 text-xs leading-5 text-stone-600">After a fictional call, a parent’s own report of fever or a close loss can create one brief notice. Repeated notices for the same topic are limited to once per 24 hours. No transcript or medical claim goes in the email.</p>
          <p className="mt-1 text-xs leading-5 text-stone-600">Enter the child's test inbox here. HugBack saves it only for this local SQLite demo family; no address is needed in the backend `.env`.</p>
          {family.storageMode === "sqlite" ? <div className="mt-3 rounded-xl border border-[#D7EAFE] bg-white p-3">
            <label className="portal-label">Child test email
              <input className="portal-input" type="email" autoComplete="email" value={testEmail} onChange={(event) => { setTestEmail(event.target.value); setTestEmailConfirmation(false); }} placeholder="you@example.com" disabled={busy} />
            </label>
            <label className="mt-2 flex items-start gap-2 text-xs leading-5 text-stone-600"><input type="checkbox" className="mt-1" checked={testEmailConfirmation} disabled={busy} onChange={(event) => setTestEmailConfirmation(event.target.checked)} />I own this inbox or its owner expects a fictional HugBack test email.</label>
            <div className="mt-2 flex flex-wrap gap-2"><button className="portal-secondary" disabled={busy || !testEmailConfirmation || !testEmail.trim()} onClick={() => void saveTestEmail(true)}>Save test email for this family</button>{family.alertEmailSelected && <button className="portal-secondary" disabled={busy} onClick={() => void saveTestEmail(false)}>Clear test email</button>}</div>
            <p className="mt-2 text-xs leading-5 text-stone-600">{family.alertEmailConfigured ? `Ready: Gmail sender is configured and this family's test inbox is saved (${family.alertEmailHint || "selected"}).` : family.alertEmailSelected ? `Test inbox saved (${family.alertEmailHint || "selected"}), but backend Gmail sending is still off.` : "No email destination selected for this family. Matching calls will show email not configured."}</p>
          </div> : <p className="mt-2 text-xs text-amber-800">Browser-selected test email is available only with local SQLite demo storage.</p>}
          {selected.alertSharingEnabled ? <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setTopicAlerts(false)}>Stop future topic emails</button> : <><label className="mt-2 flex items-start gap-2 text-xs leading-5 text-stone-600"><input type="checkbox" checked={alertConsent} disabled={busy || selected.busy || !selected.transcriptSharingEnabled} onChange={(event) => setAlertConsent(event.target.checked)} className="mt-1" />Simulate {selected.label} agreeing once to these automatic notices to the child. Enable future call summaries first.</label><button className="portal-secondary mt-2" disabled={busy || selected.busy || !alertConsent || !selected.transcriptSharingEnabled} onClick={() => void setTopicAlerts(true)}>Enable future topic notices</button></>}
        </div>
        {selected.busy ? <p role="status" className="mt-3 text-xs text-amber-800">Wait for this recipient’s call and memory update before changing their setup.</p> : !assignedVoiceUnavailable && <Link className="portal-primary mt-4 inline-flex" href={parentCallUrl(selected.recipientId)}>Test a call as {selected.label} →</Link>}
      </div> : <p role="status" className="mt-4 text-sm font-semibold text-emerald-900">Select a recipient above. Nothing is selected automatically.</p>}
      <details className="mt-4 text-xs leading-5 text-stone-500"><summary className="cursor-pointer font-semibold">Test storage details</summary><p className="mt-2">Synthetic histories use {family.storageMode === "firestore" ? "the isolated Firestore test database" : "local SQLite"} and are usable until {new Date(family.expiresAt).toLocaleDateString()}. Up to eight recipients. This simulator does not verify who is speaking. Voice keys remain in the separate local vault.</p></details>
    </>}
    {(!family || adding) && !loading && !loadError && <div className="mt-5 space-y-3 rounded-2xl border border-[#DDE2F0] bg-[#F7F8FC] p-5 text-sm">
      <h3 className="font-bold">{family ? "Add a recipient with their own history" : "Create a family and its first recipient"}</h3>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="portal-label">Relationship<select className="portal-input" disabled={busy} value={relationship} onChange={(e) => { setRelationship(e.target.value as DemoRecipient["relationship"]); setLabel(e.target.selectedOptions[0].text); }}>
          <option value="mother">Mother</option><option value="father">Father</option><option value="grandmother">Grandmother</option><option value="grandfather">Grandfather</option><option value="other">Other</option>
        </select></label>
        <label className="portal-label">Recipient label<input className="portal-input" value={label} maxLength={40} disabled={busy} onChange={(e) => setLabel(e.target.value)} /></label>
      </div>
      {!family && <label className="portal-label">Child gender for recorded-voice phrasing
        <select className="portal-input" value={childGender} disabled={busy} onChange={(event) => setChildGender(event.target.value as typeof childGender)}>
          <option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="neutral">Another identity · use neutral phrasing</option>
        </select>
      </label>}
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} className="mt-1" />I will use fictional chats and role-play only, not real family data.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={child} onChange={(e) => setChild(e.target.checked)} className="mt-1" />Simulate the child agreeing to setup for this recipient.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={parent} onChange={(e) => setParent(e.target.checked)} className="mt-1" />Simulate this recipient agreeing to their own demo setup.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={memory} onChange={(e) => setMemory(e.target.checked)} className="mt-1" />Simulate this recipient consenting to cross-call wellbeing memory. Google processes their demo transcript after calls; only bounded concerns are saved in the selected test database.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={toneContinuity} onChange={(e) => setToneContinuity(e.target.checked)} className="mt-1" />Simulate both participants agreeing to gentle voice-tone check-ins across fictional calls. One model-marked high-confidence cue may be retained for 72 hours, without audio or voice matching.</label>
      <label className="block">Conversation language <select disabled={busy} value={language} onChange={(e) => setLanguage(e.target.value as NonNullable<DemoRecipient["language"]>)} className="ml-2 rounded border p-2">
        <option value="auto">Follow the speaker</option><option value="en">English</option><option value="hi">Hindi</option><option value="hi-en">Hindi / English</option>
      </select></label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={wellbeingSharing} onChange={(e) => setWellbeingSharing(e.target.checked)} className="mt-1" />Simulate this recipient consenting to share a short AI-estimated conversation signal with the child. No audio or transcript is stored.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={transcriptSharing} onChange={(e) => setTranscriptSharing(e.target.checked)} className="mt-1" />Simulate both participants agreeing once to share AI summaries of future fictional calls with the child. No per-call approval is needed.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy || !transcriptSharing} checked={alertSharing && transcriptSharing} onChange={(e) => setAlertSharing(e.target.checked)} className="mt-1" />Simulate this recipient agreeing once to brief automatic fever or loss notices by email. Enable call summaries first.</label>
      <button className="portal-primary" disabled={busy || !synthetic || !child || !parent || !label.trim() || (!family && !childGender)} onClick={() => void create()}>{busy ? "Saving…" : family ? "Add recipient" : "Create local demo family"}</button>
    </div>}
    {loading && !family && <p role="status" className="mt-3 text-sm">Checking local demo family…</p>}
    {(error || loadError) && <p role="alert" className="mt-3 text-sm text-rose-800">{error || loadError}</p>}
    {(error || loadError) && <button className="portal-secondary mt-3" disabled={busy || loading} onClick={() => { setError(""); void refresh(); }}>Refresh family</button>}
  </section>;
}
