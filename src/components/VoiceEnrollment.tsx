"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AudioLines, CheckCircle2, Loader2, RefreshCw, Sparkles, Trash2 } from "lucide-react";
import { BrowserAudioRecorder } from "@/components/BrowserAudioRecorder";
import { prepareVoiceWav } from "@/lib/voice-wav";
import { deleteLocalVoiceProfile, hasLocalVoiceProfile } from "@/lib/voice-profile";
import { PortalStatus, portalGet } from "@/lib/portal-api";
import { audioBase64, voiceRequest } from "@/lib/voice-api";
import { DemoFamily, DemoRecipient, demoRequest, parentCallUrl } from "@/lib/demo-api";

export function VoiceEnrollment({ disabled = false, voice, onUpdated, recipient, onAssigned }: {
  disabled?: boolean;
  voice?: PortalStatus["voice"];
  onUpdated?: () => Promise<void>;
  recipient?: DemoRecipient;
  onAssigned?: (family: DemoFamily) => void;
}) {
  const [capability, setCapability] = useState(voice);
  const [reference, setReference] = useState<File | null>(null);
  const [consent, setConsent] = useState<File | null>(null);
  const [acknowledged, setAcknowledged] = useState(false);
  const [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false);
  const [legacy, setLegacy] = useState(false);
  const [recorderVersion, setRecorderVersion] = useState(0);
  const [activeRecorder, setActiveRecorder] = useState<"reference" | "consent" | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const profile = capability?.profile;
  const expired = !!profile && (profile.expired || !Number.isFinite(Date.parse(profile.expiresAt)) || Date.parse(profile.expiresAt) <= Date.now());
  const available = capability?.replicatedTtsEnabled === true;
  const locked = disabled || busy;
  const assigned = !!profile && recipient?.voice.mode === "child" && recipient.voice.profileId === profile.id;

  useEffect(() => { setCapability(voice); }, [voice]);
  useEffect(() => {
    void hasLocalVoiceProfile().then(setLegacy).catch(() => {});
  }, []);

  async function refresh() {
    setBusy(true);
    try {
      const status = await portalGet<PortalStatus>("/status");
      setCapability(status.voice);
      const result = await voiceRequest("/profile", "GET");
      setCapability({ ...status.voice, profile: result.profile });
      setUncertain(!!result.enrolling);
      setMessage(result.enrolling ? "Google voice setup is still processing. Refresh again shortly." : "Voice status refreshed.");
      void onUpdated?.();
    } catch (error) {
      setUncertain(true);
      setMessage(error instanceof Error ? error.message : "Could not refresh voice status.");
    } finally { setBusy(false); }
  }

  async function enroll() {
    if (!reference || !consent || !acknowledged || !available || locked || uncertain || activeRecorder) return;
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
      setReference(null); setConsent(null); setAcknowledged(false); setRecorderVersion((value) => value + 1);
      setMessage("Voice created. Enable this child voice below, then assign it to each recipient. Set the child’s gender in Family setup for Hindi phrasing. Voice likeness is not independently verified.");
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

  async function assign() {
    if (!recipient || !onAssigned || !profile?.enabled || expired || !available ||
        locked || uncertain || recipient.busy || assigned) return;
    setBusy(true);
    try {
      const family = await demoRequest("/recipient-voice", "PUT", {
        syntheticOnly: true, recipientId: recipient.recipientId, revision: recipient.revision,
        mode: "child", profileId: profile.id,
      });
      onAssigned(family);
      setMessage(`This voice is now assigned to ${recipient.label}. Other recipients were not changed.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Voice assignment could not be confirmed. Refresh Family setup before calling.");
    } finally { setBusy(false); }
  }

  async function remove() {
    if (!window.confirm("Remove this voice key from the local backend? Recipients assigned this voice will need a new assignment or an explicit switch to standard voice. End any active call first. This does not revoke Google's temporary key or guarantee provider data deletion.")) return;
    setBusy(true);
    try {
      await voiceRequest("/profile", "DELETE");
      setCapability((current) => current ? { ...current, profile: null } : current);
      void onUpdated?.();
      setMessage("Voice removed from this backend. No recordings were stored by this enrollment flow.");
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
    <section>
      {!available && <p className="mt-4 rounded-xl bg-amber-50 p-3 text-sm leading-6 text-amber-950">
        {capability ? "Voice creation is not available right now." : "Checking voice availability…"}
      </p>}

      <div className="mt-6 grid gap-4 sm:grid-cols-2" key={recorderVersion}>
        <BrowserAudioRecorder disabled={locked || !available || activeRecorder === "consent"} label="1 · Voice sample" minimumSeconds={10} help="Speak in your usual rhythm for 20–30 seconds. Tell a short fictional everyday story and ask a natural question; do not whisper or act." onRecorded={(file) => { setReference(file); setAcknowledged(false); }} onRecordingChange={(recording) => setActiveRecorder(recording ? "reference" : null)} />
        <BrowserAudioRecorder disabled={locked || !available || activeRecorder === "reference"} label="2 · Consent" minimumSeconds={2} help="Read the statement below." onRecorded={(file) => { setConsent(file); setAcknowledged(false); }} onRecordingChange={(recording) => setActiveRecorder(recording ? "consent" : null)} />
      </div>
      <div className="mt-3 rounded-xl bg-violet-50 p-4 text-sm leading-6 text-stone-700"><strong>Read this for recording 2:</strong><br />“I am the owner of this voice and I consent to Google using this voice to create a synthetic voice model.”</div>
      <label className="mt-4 flex items-start gap-3 text-sm leading-6 text-stone-700">
        <input className="mt-1.5 h-4 w-4 shrink-0 accent-violet-600" type="checkbox" checked={acknowledged} disabled={locked || !available} onChange={(event) => setAcknowledged(event.target.checked)} />
        <span>I am 18 or older, this is my voice, and I agree to send these recordings to Google to create the voice.</span>
      </label>
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <button type="button" disabled={locked || !available || !reference || !consent || !acknowledged || uncertain || !!activeRecorder} onClick={enroll} className="flex items-center gap-2 rounded-full bg-violet-600 px-5 py-2.5 text-sm font-bold text-white hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}{profile ? "Create replacement voice" : "Create voice"}
        </button>
        {uncertain && <button type="button" disabled={locked} onClick={refresh} className="flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-stone-600 hover:bg-stone-100 disabled:opacity-50"><RefreshCw className="h-4 w-4" />Refresh status</button>}
      </div>

      {profile && <div className="mt-6 rounded-xl border border-[#9BA5FC]/20 bg-[#F3EFFF]/50 p-4">
        <div className="flex items-center gap-2 font-bold text-stone-900"><CheckCircle2 className="h-4 w-4 text-[#56619C]" />{expired ? "Voice needs renewal" : "Voice created"}</div>
        {expired && <p className="mt-2 text-sm text-stone-600">Create a new voice before using it in calls.</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" disabled={locked || uncertain || !available || expired || profile.enabled} onClick={() => select(true)} className="rounded-full bg-[#56619C] px-4 py-2 text-sm font-bold text-white disabled:opacity-40">Enable child voice</button>
          <button type="button" disabled={locked || uncertain || !profile.enabled} onClick={() => select(false)} className="rounded-full border border-stone-300 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40">Disable child voice</button>
          <button type="button" disabled={locked || uncertain} onClick={remove} className="flex items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-40"><Trash2 className="h-4 w-4" />Remove voice</button>
        </div>
        <div className="mt-4 border-t border-[#9BA5FC]/20 pt-4">
          <p className="font-bold text-stone-800">3 · Assign this voice to a recipient</p>
          <p className="mt-1 text-sm leading-6 text-stone-600">Creating or enabling a replacement does not change a recipient’s voice. Each person keeps their current assignment until you explicitly change it.</p>
          {!recipient ? <a href="#family-dashboard" className="mt-3 inline-block text-sm font-bold text-[#56619C] underline underline-offset-4">Choose a recipient in Family setup, then assign this voice →</a> : <>
            <p className="mt-2 text-sm text-stone-700">{recipient.label}: {assigned ? "this child voice is assigned" : recipient.voice.mode === "standard" ? "still using standard Hugback voice" : "assigned to a different / replaced voice"}.</p>
            {!assigned && <button type="button" disabled={locked || uncertain || !available || expired || !profile.enabled || recipient.busy || !onAssigned} onClick={assign} className="mt-3 rounded-full bg-[#56619C] px-4 py-2 text-sm font-bold text-white disabled:opacity-40">Assign this voice to {recipient.label}</button>}
            {assigned && profile.enabled && !expired && available && !locked && !uncertain && !recipient.busy &&
              <Link href={parentCallUrl(recipient.recipientId)} className="mt-3 inline-block text-sm font-bold text-[#56619C] underline underline-offset-4">Preview {recipient.label}’s call with this voice →</Link>}
            {recipient.busy && <p className="mt-2 text-xs text-stone-600">Wait for this recipient’s current call and memory processing to finish.</p>}
          </>}
        </div>
      </div>}
      {message && <p className="mt-4 rounded-xl bg-stone-100 p-3 text-sm leading-6 text-stone-800" role="status" aria-live="polite">{message}</p>}
      <details className="mt-5 border-t border-stone-100 pt-4 text-xs leading-5 text-stone-500">
        <summary className="cursor-pointer font-semibold text-stone-600">Privacy and recording details</summary>
        <p className="mt-2">The recordings are sent to Google only after you confirm. Hugback does not save them in browser storage or Firestore. Hugback always identifies itself as AI.</p>
      </details>
      {legacy && <div className="mt-3 border-t border-stone-100 pt-3 text-xs leading-5 text-stone-500">Older recordings are still saved in this browser. They are not automatically uploaded or selected by this flow. <button type="button" disabled={locked} onClick={removeLegacy} className="font-semibold text-rose-700 underline">Delete old browser recordings</button></div>}
    </section>
  );
}
