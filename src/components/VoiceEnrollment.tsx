"use client";

import { useEffect, useState } from "react";
import { AudioLines, CheckCircle2, Loader2, Trash2, Upload } from "lucide-react";
import { prepareVoiceWav } from "@/lib/voice-wav";
import {
  deleteLocalVoiceProfile,
  hasLocalVoiceProfile,
  saveLocalVoiceProfile,
} from "@/lib/voice-profile";

export function VoiceEnrollment({ disabled = false }: { disabled?: boolean }) {
  const [enrolled, setEnrolled] = useState(false);
  const [reference, setReference] = useState<File | null>(null);
  const [consent, setConsent] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void hasLocalVoiceProfile()
      .then(setEnrolled)
      .catch(() => setMessage("This browser could not open private voice storage."));
  }, []);

  async function enroll() {
    if (!reference || !consent) {
      setMessage("Choose both your voice sample and consent recording.");
      return;
    }
    setBusy(true);
    setMessage("Preparing and securing audio in this browser…");
    try {
      const [preparedReference, preparedConsent] = await Promise.all([
        prepareVoiceWav(reference, "Voice sample", 10),
        prepareVoiceWav(consent, "Consent", 2),
      ]);
      await saveLocalVoiceProfile(preparedReference, preparedConsent);
      setReference(null);
      setConsent(null);
      setEnrolled(true);
      setMessage("Your voice is ready. New calls from this browser will use it.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Voice setup failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Delete your voice recordings from this browser?")) return;
    setBusy(true);
    try {
      await deleteLocalVoiceProfile();
      setEnrolled(false);
      setMessage("Your local voice recordings have been deleted.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Voice deletion failed");
    } finally {
      setBusy(false);
    }
  }

  const locked = disabled || busy;
  return (
    <section className="w-full rounded-2xl border border-stone-200 bg-white/90 p-5 shadow-sm mb-6">
      <div className="flex items-start justify-between gap-4">
        <div className="flex gap-3">
          <div className="rounded-xl bg-violet-100 p-2.5 text-violet-700">
            <AudioLines className="h-5 w-5" />
          </div>
          <div>
            <h2 className="font-bold text-stone-900">Your voice for Elara</h2>
            <p className="mt-1 text-sm text-stone-600">
              Upload a clear 10–30 second sample and a separate consent recording.
            </p>
          </div>
        </div>
        {enrolled && (
          <span className="flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800">
            <CheckCircle2 className="h-3.5 w-3.5" /> Ready
          </span>
        )}
      </div>

      <p className="mt-4 rounded-xl bg-stone-50 p-3 text-xs leading-5 text-stone-600">
        Consent recording: say, “I am the owner of this voice and I consent to Google using it to create a synthetic voice.” Recordings stay in this browser and are sent to Gemini only when you start a call; Elara never stores them on its server.
      </p>

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        <label className="rounded-xl border border-dashed border-stone-300 p-3 text-sm font-semibold text-stone-700 hover:bg-stone-50">
          Voice sample
          <input
            className="mt-2 block w-full text-xs font-normal file:mr-2 file:rounded-lg file:border-0 file:bg-stone-100 file:px-3 file:py-2"
            type="file"
            accept="audio/*,.wav"
            disabled={locked}
            onChange={(event) => setReference(event.target.files?.[0] || null)}
          />
        </label>
        <label className="rounded-xl border border-dashed border-stone-300 p-3 text-sm font-semibold text-stone-700 hover:bg-stone-50">
          Consent recording
          <input
            className="mt-2 block w-full text-xs font-normal file:mr-2 file:rounded-lg file:border-0 file:bg-stone-100 file:px-3 file:py-2"
            type="file"
            accept="audio/*,.wav"
            disabled={locked}
            onChange={(event) => setConsent(event.target.files?.[0] || null)}
          />
        </label>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          disabled={locked || !reference || !consent}
          onClick={enroll}
          className="flex items-center gap-2 rounded-full bg-violet-600 px-4 py-2 text-sm font-bold text-white transition hover:bg-violet-700 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
          {enrolled ? "Replace voice" : "Set up my voice"}
        </button>
        {enrolled && (
          <button
            type="button"
            disabled={locked}
            onClick={remove}
            className="flex items-center gap-2 rounded-full border border-rose-200 px-4 py-2 text-sm font-bold text-rose-700 hover:bg-rose-50 disabled:opacity-50"
          >
            <Trash2 className="h-4 w-4" /> Delete voice
          </button>
        )}
        {disabled && <span className="text-xs text-stone-500">End the call to change voice.</span>}
      </div>
      {message && <p className="mt-3 text-sm text-stone-700" role="status">{message}</p>}
    </section>
  );
}
