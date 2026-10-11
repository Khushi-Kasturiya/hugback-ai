"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AudioLines, CheckCircle2, Loader2, RefreshCw, Trash2, Upload } from "lucide-react";
import { prepareVoiceWav } from "@/lib/voice-wav";
import { deleteLocalVoiceProfile, hasLocalVoiceProfile } from "@/lib/voice-profile";
import { PortalStatus, portalGet } from "@/lib/portal-api";
import { audioBase64, voiceRequest } from "@/lib/voice-api";

export function VoiceEnrollment({ disabled = false, voice, onUpdated }: {
  disabled?: boolean;
  voice?: PortalStatus["voice"];
  onUpdated?: () => Promise<void>;
}) {
  const [capability, setCapability] = useState(voice);
  const [reference, setReference] = useState<File | null>(null);
  const [consent, setConsent] = useState<File | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [legacy, setLegacy] = useState(false);
  const [inputVersion, setInputVersion] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const profile = capability?.profile;
  const expired = !!profile && (profile.expired || Date.parse(profile.expiresAt) <= Date.now());
  const available = capability?.replicatedTtsEnabled === true;
  const locked = disabled || busy;

  useEffect(() => { setCapability(voice); }, [voice]);
  useEffect(() => {
    void hasLocalVoiceProfile().then(setLegacy).catch(() => {});
  }, []);

  async function refresh() {
    setBusy(true);
    try {
      const status = await portalGet<PortalStatus>("/status");
      setCapability(status.voice);
      if (status.identityMode === "development") {
        const result = await voiceRequest("/profile", "GET");
        setCapability({ ...status.voice, profile: result.profile });
        setUncertain(!!result.enrolling);
        setMessage(result.enrolling ? "Google voice setup is still processing. Refresh again shortly." : "Voice status refreshed.");
      }
    } catch (error) {
      setUncertain(true);
      setMessage(error instanceof Error ? error.message : "Could not refresh voice status.");
    } finally { setBusy(false); }
  }

  async function enroll() {
    if (!reference || !consent || !acknowledged || !available || locked || uncertain) return;
    setBusy(true);
    setMessage("Preparing mono 24 kHz audio, then uploading the two recordings to Google…");
    let submitted = false;
    try {
      const [sample, permission] = await Promise.all([
        prepareVoiceWav(reference, "Voice sample", 10),
        prepareVoiceWav(consent, "Consent", 2),
      ]);
      const [voiceSampleAudio, consentAudio] = await Promise.all([audioBase64(sample), audioBase64(permission)]);
      submitted = true;
      const result = await voiceRequest("/enroll", "POST", {
        voiceSampleAudio, consentAudio, adultOwnVoice: true, consentToGoogleAndBilling: true,
      });
      setCapability((current) => current ? { ...current, profile: result.profile } : current);
      void onUpdated?.();
      setReference(null); setConsent(null); setAcknowledged(false); setInputVersion((value) => value + 1);
      setMessage("Voice created. Choose “Enable child voice” below, then assign it to each recipient in Family setup. Voice likeness is not independently verified.");
    } catch (error) {
      setUncertain(submitted);
      setMessage(error instanceof Error ? error.message : "Voice setup failed.");
    } finally { setBusy(false); }
  }

  async function select(enabled: boolean) {
    if (!profile || locked) return;
    setBusy(true);
    try {
      const result = await voiceRequest("/profile", "PUT", { profileId: profile.id, enabled });
      setCapability((current) => current ? { ...current, profile: result.profile } : current);
      void onUpdated?.();
      setMessage(enabled ? "Child voice enabled. Assign it separately to each recipient in Family setup." : "Child voice disabled. Recipients still assigned this voice cannot call until you select standard voice for them.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Voice selection failed.");
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm("Remove this voice key from the local backend? Recipients assigned this voice will need a new assignment or an explicit switch to standard voice. End any active call first. This does not revoke Google's temporary key or guarantee provider data deletion.")) return;
    setBusy(true);
    try {
      await voiceRequest("/profile", "DELETE");
      setCapability((current) => current ? { ...current, profile: null } : current);
      void onUpdated?.();
      setMessage("Voice removed from this backend. No recordings were stored by this upload flow.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Voice removal failed.");
    } finally { setBusy(false); }
  }

  async function removeLegacy() {
    if (!window.confirm("Delete recordings saved by the old voice setup from this browser?")) return;
    setBusy(true);
    try { await deleteLocalVoiceProfile(); setLegacy(false); setMessage("Old browser recordings deleted."); }
    catch { setMessage("Could not delete the old browser recordings."); }
    finally { setBusy(false); }
  }

  return (
    <section className="w-full rounded-2xl border border-stone-200 bg-white/90 p-5 shadow-sm sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex gap-3">
          <div className="h-fit rounded-xl bg-violet-100 p-2.5 text-violet-700"><AudioLines className="h-5 w-5" /></div>
          <div><h3 className="font-bold text-stone-900">A familiar voice, always Elara.</h3>
            <p className="mt-1 text-sm text-stone-600">Create one voice. Assign it to Mother, Father or other recipients without sharing their memories.</p></div>
        </div>
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${profile?.enabled && !expired && available ? "bg-emerald-100 text-emerald-800" : "bg-stone-100 text-stone-600"}`}>
          {expired && profile?.enabled ? "Voice expired · assigned calls blocked" : profile?.enabled ? (available ? "Child voice enabled" : "Custom voice unavailable") : "Child voice not enabled"}
        </span>
      </div>

      {!available && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-950">
        {capability ? "Upload is disabled on this backend. This local integration requires development identity, preset Live mode, a Gemini API key and ELARA_REPLICATED_TTS_ENABLED=True. Paid-tier access is checked by Google when you submit." : "Waiting for backend voice capabilities. No recording will be uploaded until setup is available."}
      </p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-2" key={inputVersion}>
        <label className="rounded-xl border border-dashed border-stone-300 bg-stone-50/50 p-4 text-sm font-semibold text-stone-800">
          <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-violet-700">01 · Your voice</span>
          Voice sample <span className="font-normal text-stone-500">· 10–30 seconds</span>
          <input className="mt-3 block w-full text-xs font-normal file:mr-2 file:rounded-lg file:border-0 file:bg-violet-100 file:px-3 file:py-2 file:text-violet-800" type="file" accept="audio/*,.wav" disabled={locked || !available} onChange={(event) => { setReference(event.target.files?.[0] || null); setAcknowledged(false); }} />
          <span className="mt-2 block text-xs font-normal leading-5 text-stone-500">One adult speaker. Speak naturally in a quiet room, without music. Up to 10 MB.</span>
        </label>
        <label className="rounded-xl border border-dashed border-stone-300 bg-stone-50/50 p-4 text-sm font-semibold text-stone-800">
          <span className="mb-2 block text-xs font-bold uppercase tracking-wider text-violet-700">02 · Spoken permission</span>
          Consent recording <span className="font-normal text-stone-500">· 2–30 seconds</span>
          <input className="mt-3 block w-full text-xs font-normal file:mr-2 file:rounded-lg file:border-0 file:bg-violet-100 file:px-3 file:py-2 file:text-violet-800" type="file" accept="audio/*,.wav" disabled={locked || !available} onChange={(event) => { setConsent(event.target.files?.[0] || null); setAcknowledged(false); }} />
          <span className="mt-2 block text-xs font-normal leading-5 text-stone-500">Record separately, using the same speaker. Up to 10 MB.</span>
        </label>
      </div>
      <p className="mt-3 rounded-xl bg-stone-50 p-3 text-sm leading-6 text-stone-600">Read Google’s required English statement exactly: “I am the owner of this voice and I consent to Google using this voice to create a synthetic voice model.” <a href="https://ai.google.dev/gemini-api/docs/voice-replication" target="_blank" rel="noopener noreferrer" className="font-semibold text-violet-700 underline underline-offset-2">Recording requirements & other languages</a>.</p>
      <label className="mt-4 flex items-start gap-3 text-sm leading-6 text-stone-700">
        <input className="mt-1.5 h-4 w-4 shrink-0 accent-violet-600" type="checkbox" checked={acknowledged} disabled={locked || !available} onChange={(event) => setAcknowledged(event.target.checked)} />
        <span>I am 18 or older, both recordings are my own voice, and I authorize sending them to Google to create a synthetic voice. I understand enrollment and call speech may incur charges. Elara will disclose that it is AI, not impersonate me.</span>
      </label>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button type="button" disabled={locked || !available || !reference || !consent || !acknowledged || uncertain} onClick={enroll} className="flex items-center gap-2 rounded-full bg-violet-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}{profile ? "Upload & replace voice" : "Upload & create voice"}
        </button>
        <button type="button" disabled={locked} onClick={refresh} className="flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-stone-600 hover:bg-stone-100 disabled:opacity-50"><RefreshCw className="h-4 w-4" />Refresh status</button>
      </div>

      {profile && <div className="mt-6 rounded-xl border border-emerald-200 bg-emerald-50/50 p-4">
        <div className="flex items-center gap-2 font-bold text-stone-900"><CheckCircle2 className="h-4 w-4 text-emerald-700" />{expired ? "Voice needs renewal" : "Voice created"}</div>
        <p className="mt-2 text-xs leading-5 text-stone-600">{profile.expirySource === "provider" ? "Expires" : "Local validity limit"}: {new Date(profile.expiresAt).toLocaleString()}. {expired ? "Create and assign a fresh profile, or explicitly choose standard voice for each affected recipient." : "Changes apply to new calls; end any active call first."}</p>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={locked || uncertain || !available || expired || profile.enabled} onClick={() => select(true)} className="rounded-full bg-emerald-700 px-4 py-2 text-sm font-bold text-white disabled:opacity-40">Enable child voice</button>
          <button type="button" disabled={locked || uncertain || !profile.enabled} onClick={() => select(false)} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40">Disable child voice</button>
          <button type="button" disabled={locked || uncertain} onClick={remove} className="flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-40"><Trash2 className="h-4 w-4" />Remove voice</button>
        </div>
        {profile.enabled && !expired && available && <Link href="/?demo=parent" className="mt-4 inline-block text-sm font-bold text-emerald-800 underline underline-offset-4">Choose a recipient for a demo call →</Link>}
      </div>}
      {message && <p className="mt-4 rounded-xl bg-stone-100 p-3 text-sm leading-6 text-stone-800" role="status" aria-live="polite">{message}</p>}
      <p className="mt-5 text-xs leading-5 text-stone-500">For local browser tests, not telephone enrollment. This flow does not save recordings in browser storage or Firestore. A temporary Google voice key stays in the private local backend database, scoped to this browser identity. Removing it blocks recipients still assigned this voice until you choose another voice; it does not revoke the provider key or guarantee Google retention/deletion. Custom-voice failure stops the call instead of switching speakers.</p>
      {legacy && <div className="mt-3 border-t border-stone-100 pt-3 text-xs leading-5 text-stone-500">Older recordings are still saved in this browser. They are not automatically uploaded or selected by this flow. <button type="button" disabled={locked} onClick={removeLegacy} className="font-semibold text-rose-700 underline">Delete old browser recordings</button></div>}
    </section>
  );
}
