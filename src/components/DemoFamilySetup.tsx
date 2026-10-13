"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { DemoFamily, DemoRecipient, demoRequest, parentCallUrl } from "@/lib/demo-api";
import type { PortalStatus } from "@/lib/portal-api";
import { loadChildPhoto, removeChildPhoto, saveChildPhoto } from "@/lib/portal-storage";

export function DemoFamilySetup({ family, onChange, loading, loadError, refresh, selectedId, onSelect, voice }: {
  family?: DemoFamily; onChange: (family: DemoFamily) => void;
  loading: boolean; loadError: string; refresh: () => Promise<void>;
  selectedId: string; onSelect: (id: string) => void; voice?: PortalStatus["voice"];
}) {
  const [adding, setAdding] = useState(false);
  const [label, setLabel] = useState("Mother");
  const [relationship, setRelationship] = useState<DemoRecipient["relationship"]>("mother");
  const [testEmail, setTestEmail] = useState("");
  const [testEmailConfirmation, setTestEmailConfirmation] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [language, setLanguage] = useState<NonNullable<DemoRecipient["language"]>>("auto");
  const [childName, setChildName] = useState(family?.childName ?? "");
  const [childGender, setChildGender] = useState<"female" | "male" | "neutral" | "">(family?.childGender ?? "");
  const [photoUrl, setPhotoUrl] = useState("");
  const [pendingPhoto, setPendingPhoto] = useState<File>();
  const [photoBusy, setPhotoBusy] = useState(false);
  useEffect(() => { setError(""); }, [selectedId]);
  useEffect(() => { setChildName(family?.childName ?? ""); setChildGender(family?.childGender ?? ""); }, [family?.familyId, family?.childName, family?.childGender]);
  useEffect(() => {
    if (typeof window === "undefined" || !family?.familyId) return;
    let active = true;
    void loadChildPhoto(family.familyId).then((blob) => {
      if (!active || !blob) return;
      setPhotoUrl(URL.createObjectURL(blob));
    }).catch(() => { if (active) setError("The browser-local child photo could not be loaded."); });
    return () => { active = false; };
  }, [family?.familyId]);
  useEffect(() => () => { if (photoUrl) URL.revokeObjectURL(photoUrl); }, [photoUrl]);
  const selected = family?.recipients.find((item) => item.recipientId === selectedId);
  const currentVoice = voice?.profile;
  const childVoiceAvailable = !!(voice?.replicatedTtsEnabled && currentVoice?.enabled && !currentVoice.expired && Date.parse(currentVoice.expiresAt) > Date.now());
  const assignedVoiceUnavailable = selected?.voice.mode === "child" && (!childVoiceAvailable || selected.voice.profileId !== currentVoice?.id);

  async function create() {
    if (!label.trim() || busy || (!family && (!childName.trim() || !childGender))) return;
    setBusy(true); setError("");
    try {
      const result = await demoRequest(family ? "/recipients" : "/family", "POST", {
        syntheticOnly: true, simulateChildConsent: true, simulateParentConsent: true,
        enableMemory: true, timeZone: "Asia/Kolkata", label: label.trim(), relationship,
        enableWellbeingSharing: false, enableToneContinuity: false,
        simulateToneConsent: false, enableTranscriptSharing: false,
        enableAlertSharing: false, language,
        ...(!family ? { childName: childName.trim(), childGender } : {}),
      });
      onChange(result);
      if (!family && pendingPhoto) {
        try { await saveChildPhoto(result.familyId, pendingPhoto); }
        catch { setError("The family was created, but the photo could not be saved in this browser."); }
      }
      const created = result.recipients.find((r) => r.label === label.trim());
      if (created) onSelect(created.recipientId);
      setAdding(false);
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
  async function saveChildDetails() {
    if (!family || !childName.trim() || !childGender ||
        (childName.trim() === family.childName && childGender === family.childGender) || busy) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/child-details", "PUT", {
        syntheticOnly: true, familyId: family.familyId,
        revision: family.childGenderRevision ?? 0, childName: childName.trim(), childGender,
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Child details could not be saved."); }
    finally { setBusy(false); }
  }
  async function chooseChildPhoto(file?: File) {
    if (!file || photoBusy) return;
    setPhotoBusy(true); setError("");
    try {
      if (!new Set(["image/jpeg", "image/png", "image/webp"]).has(file.type)) throw new Error("Choose a JPEG, PNG or WebP photo.");
      if (!file.size || file.size > 2 * 1024 * 1024) throw new Error("Keep the child photo under 2 MB.");
      if (family) await saveChildPhoto(family.familyId, file);
      else setPendingPhoto(file);
      if (photoUrl) URL.revokeObjectURL(photoUrl);
      setPhotoUrl(URL.createObjectURL(file));
    } catch (err) { setError(err instanceof Error ? err.message : "The child photo could not be saved locally."); }
    finally { setPhotoBusy(false); }
  }
  async function clearChildPhoto() {
    if (photoBusy) return;
    setPhotoBusy(true); setError("");
    try {
      if (family) await removeChildPhoto(family.familyId);
      else setPendingPhoto(undefined);
      if (photoUrl) URL.revokeObjectURL(photoUrl);
      setPhotoUrl("");
    } catch (err) { setError(err instanceof Error ? err.message : "The child photo could not be removed."); }
    finally { setPhotoBusy(false); }
  }
  async function setSignalSharing(enabled: boolean) {
    if (!selected || busy || selected.busy) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/wellbeing-sharing", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Call signal sharing update failed."); }
    finally { setBusy(false); }
  }
  async function setToneMemory(enabled: boolean) {
    if (!selected || busy || selected.busy) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/tone-continuity", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Voice-tone setting update failed."); }
    finally { setBusy(false); }
  }
  async function setCallHistory(enabled: boolean) {
    if (!selected || busy || selected.busy) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/transcript-sharing", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
    } catch (err) { setError(err instanceof Error ? err.message : "Call history update failed."); }
    finally { setBusy(false); }
  }
  async function setTopicAlerts(enabled: boolean) {
    if (!selected || busy || selected.busy || (enabled && !selected.transcriptSharingEnabled)) return;
    setBusy(true); setError("");
    try {
      onChange(await demoRequest("/alert-sharing", "PUT", {
        syntheticOnly: true, recipientId: selected.recipientId, revision: selected.revision,
        enabled, simulateChildConsent: enabled, simulateParentConsent: enabled,
      }));
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
      {family && <button className="portal-secondary" disabled={busy || family.recipients.length >= 8} onClick={() => { setAdding(!adding); setError(""); }}>{adding ? "Cancel" : "+ Add parent"}</button>}
    </div>
    {family && <>
      <div className="mt-5 rounded-2xl border border-[#DDE2F0] bg-white p-4 text-sm">
        <p className="font-bold text-stone-800">Child details</p>
        <p className="mt-1 text-xs leading-5 text-stone-600">Name and gender are saved with this synthetic family in the selected database. The picture stays only in this browser and is never uploaded.</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="portal-label">Child name
            <input className="portal-input" value={childName} maxLength={40} disabled={busy} onChange={(event) => setChildName(event.target.value)} />
          </label>
          <label className="portal-label">Child gender
            <select className="portal-input" value={childGender} disabled={busy} onChange={(event) => setChildGender(event.target.value as typeof childGender)}>
              <option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="neutral">Another identity · use neutral phrasing</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {photoUrl && <img src={photoUrl} alt={`${childName || "Child"} browser-local profile`} className="h-16 w-16 rounded-full object-cover" />}
          <label className="portal-secondary cursor-pointer">{photoUrl ? "Replace local photo" : "Choose local photo"}
            <input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" disabled={photoBusy} onChange={(event) => void chooseChildPhoto(event.target.files?.[0])} />
          </label>
          {photoUrl && <button type="button" className="portal-secondary" disabled={photoBusy} onClick={() => void clearChildPhoto()}>Remove local photo</button>}
          <button type="button" className="portal-secondary" disabled={busy || !childName.trim() || !childGender || (childName.trim() === family.childName && childGender === family.childGender)} onClick={() => void saveChildDetails()}>Save child details</button>
        </div>
        <p className="mt-2 text-xs text-stone-500">JPEG, PNG or WebP, up to 2 MB. The local copy expires after seven days; clearing browser site data also removes it.</p>
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
        <details className="mt-4 border-t border-[#D7EAFE] pt-4">
          <summary className="cursor-pointer font-bold text-stone-700">Optional demo features</summary>
          <p className="mt-1 text-xs leading-5 text-stone-600">Each enable button confirms simulated permission for this fictional hackathon demo. You can turn any feature off again.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl bg-white p-3">
              <p className="font-bold text-stone-700">Call signals</p>
              <p className="mt-1 text-xs text-stone-600">Share a short, non-medical conversation signal.</p>
              <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setSignalSharing(!selected.wellbeingSharingEnabled)}>{selected.wellbeingSharingEnabled ? "Turn off signals" : "Enable call signals"}</button>
            </div>
            <div className="rounded-xl bg-white p-3">
              <p className="font-bold text-stone-700">Tone check-ins</p>
              <p className="mt-1 text-xs text-stone-600">Keep one tentative voice cue for up to 72 hours.</p>
              <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setToneMemory(!selected.toneContinuityEnabled)}>{selected.toneContinuityEnabled ? "Turn off and erase tone note" : "Enable tone check-ins"}</button>
            </div>
            <div className="rounded-xl bg-white p-3">
              <p className="font-bold text-stone-700">Call summaries</p>
              <p className="mt-1 text-xs text-stone-600">Show short summaries in Signals back.</p>
              <button className="portal-secondary mt-2" disabled={busy || selected.busy} onClick={() => void setCallHistory(!selected.transcriptSharingEnabled)}>{selected.transcriptSharingEnabled ? "Turn off and erase summaries" : "Enable call summaries"}</button>
            </div>
            <div className="rounded-xl bg-white p-3">
              <p className="font-bold text-stone-700">Topic email</p>
              <p className="mt-1 text-xs text-stone-600">Send a brief test notice for supported fictional topics.</p>
              <p className="mt-1 text-xs text-stone-500">{family.alertEmailConfigured ? `Inbox ready: ${family.alertEmailHint || "configured"}` : "Test inbox is not configured."}</p>
              <button className="portal-secondary mt-2" disabled={busy || selected.busy || (!selected.alertSharingEnabled && !selected.transcriptSharingEnabled)} onClick={() => void setTopicAlerts(!selected.alertSharingEnabled)}>{selected.alertSharingEnabled ? "Turn off topic email" : "Enable topic email"}</button>
              {!selected.transcriptSharingEnabled && <p className="mt-1 text-xs text-stone-500">Enable call summaries first.</p>}
            </div>
          </div>
          {family.storageMode === "sqlite" && <div className="mt-3 rounded-xl bg-white p-3">
            <label className="portal-label">Child test email
              <input className="portal-input" type="email" autoComplete="email" value={testEmail} onChange={(event) => { setTestEmail(event.target.value); setTestEmailConfirmation(false); }} placeholder="you@example.com" disabled={busy} />
            </label>
            <label className="mt-2 flex items-start gap-2 text-xs text-stone-600"><input type="checkbox" checked={testEmailConfirmation} disabled={busy} onChange={(event) => setTestEmailConfirmation(event.target.checked)} />This inbox expects a fictional test email.</label>
            <div className="mt-2 flex gap-2"><button className="portal-secondary" disabled={busy || !testEmailConfirmation || !testEmail.trim()} onClick={() => void saveTestEmail(true)}>Save email</button>{family.alertEmailSelected && <button className="portal-secondary" disabled={busy} onClick={() => void saveTestEmail(false)}>Clear</button>}</div>
          </div>}
        </details>
        {selected.busy ? <p role="status" className="mt-3 text-xs text-amber-800">Wait for this recipient’s call and memory update before changing their setup.</p> : !assignedVoiceUnavailable && <Link className="portal-primary mt-4 inline-flex" href={parentCallUrl(selected.recipientId)}>Test a call as {selected.label} →</Link>}
      </div> : <p role="status" className="mt-4 text-sm font-semibold text-emerald-900">Select a recipient above. Nothing is selected automatically.</p>}
      <details className="mt-4 text-xs leading-5 text-stone-500"><summary className="cursor-pointer font-semibold">Test storage details</summary><p className="mt-2">Synthetic histories use {family.storageMode === "firestore" ? "the isolated Firestore test database" : "local SQLite"} and are usable until {new Date(family.expiresAt).toLocaleDateString()}. Up to eight recipients. This simulator does not verify who is speaking. Voice keys remain in the separate local vault.</p></details>
    </>}
    {(!family || adding) && !loading && !loadError && <div className="mt-5 space-y-4 rounded-2xl border border-[#DDE2F0] bg-[#F7F8FC] p-5 text-sm">
      <h3 className="text-lg font-bold text-stone-800">{family ? "Add another parent" : "Set up your family bridge"}</h3>
      {!family && <div className="rounded-2xl bg-white p-4">
        <p className="font-bold text-[#56619C]">1. Child information</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="portal-label">Child name
            <input className="portal-input" value={childName} maxLength={40} disabled={busy} onChange={(event) => setChildName(event.target.value)} placeholder="Fictional child name" />
          </label>
          <label className="portal-label">Child gender
            <select className="portal-input" value={childGender} disabled={busy} onChange={(event) => setChildGender(event.target.value as typeof childGender)}>
              <option value="">Select</option><option value="female">Female</option><option value="male">Male</option><option value="neutral">Use neutral phrasing</option>
            </select>
          </label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          {photoUrl && <img src={photoUrl} alt="Child profile preview" className="h-14 w-14 rounded-full object-cover" />}
          <label className="portal-secondary cursor-pointer">{photoUrl ? "Replace photo" : "Add photo"}
            <input className="sr-only" type="file" accept="image/jpeg,image/png,image/webp" disabled={photoBusy} onChange={(event) => void chooseChildPhoto(event.target.files?.[0])} />
          </label>
          {photoUrl && <button type="button" className="portal-secondary" disabled={photoBusy} onClick={() => void clearChildPhoto()}>Remove photo</button>}
          <span className="text-xs text-stone-500">Browser-only · up to 2 MB</span>
        </div>
      </div>}
      <div className="rounded-2xl bg-white p-4">
        <p className="font-bold text-[#56619C]">{family ? "Parent information" : "2. Parent information"}</p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="portal-label">Relationship<select className="portal-input" disabled={busy} value={relationship} onChange={(e) => { setRelationship(e.target.value as DemoRecipient["relationship"]); setLabel(e.target.selectedOptions[0].text); }}>
            <option value="mother">Mother</option><option value="father">Father</option><option value="grandmother">Grandmother</option><option value="grandfather">Grandfather</option><option value="other">Other</option>
          </select></label>
          <label className="portal-label">Name or label<input className="portal-input" value={label} maxLength={40} disabled={busy} onChange={(e) => setLabel(e.target.value)} /></label>
          <label className="portal-label sm:col-span-2">Conversation language<select className="portal-input" disabled={busy} value={language} onChange={(e) => setLanguage(e.target.value as NonNullable<DemoRecipient["language"]>)}>
            <option value="auto">Follow the speaker</option><option value="en">English</option><option value="hi">Hindi</option><option value="hi-en">Hindi / English</option>
          </select></label>
        </div>
      </div>
      <p className="text-xs leading-5 text-stone-500">Hackathon demo only. By continuing, you confirm the details are fictional and simulate both participants agreeing to this demo setup. Cross-call memory is enabled; optional signals, summaries and email notices start off.</p>
      <button className="portal-primary" disabled={busy || !label.trim() || (!family && (!childName.trim() || !childGender))} onClick={() => void create()}>{busy ? "Saving…" : family ? "Add parent" : "Create family bridge"}</button>
    </div>}
    {loading && !family && <p role="status" className="mt-3 text-sm">Checking local demo family…</p>}
    {(error || loadError) && <p role="alert" className="mt-3 text-sm text-rose-800">{error || loadError}</p>}
    {(error || loadError) && <button className="portal-secondary mt-3" disabled={busy || loading} onClick={() => { setError(""); void refresh(); }}>Refresh family</button>}
  </section>;
}
