"use client";

import { useEffect, useState } from "react";
import type { ChatPreview } from "@/lib/chat-import";
import { DemoFamily, DemoRecipient, demoRequest, reviewedExcerpts } from "@/lib/demo-api";

export function DemoBackgroundReview({ recipient, onChange, preview, child, parent, timezone }: {
  recipient: DemoRecipient; onChange: (family: DemoFamily) => void;
  preview: ChatPreview; child: string; parent: string; timezone: string;
}) {
  const [selected, setSelected] = useState<number[]>([]);
  const [synthetic, setSynthetic] = useState(false);
  const [childConsent, setChildConsent] = useState(false);
  const [parentConsent, setParentConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setSelected([]); setSynthetic(false); setChildConsent(false); setParentConsent(false);
    setMessage(""); setError("");
  }, [preview, child, parent, timezone, recipient.recipientId]);
  async function review() {
    setBusy(true); setError(""); setMessage("");
    try {
      const excerpts = reviewedExcerpts(preview, selected, child, parent);
      onChange(await demoRequest("/background", "PUT", {
        recipientId: recipient.recipientId, revision: recipient.revision, syntheticOnly: true,
        simulateChildConsent: true, simulateParentConsent: true,
        source: preview.source, childSender: child, parentSender: parent, timeZone: timezone, excerpts,
      }));
      setMessage(`Reviewed excerpts saved only for ${recipient.label}. No model or cloud storage was called.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Review could not be saved."); }
    finally { setBusy(false); }
  }
  return <section className="mt-6 border-t border-stone-200 pt-5">
    <h4 className="font-bold">Choose the background for {recipient.label}</h4>
    <p className="mt-2 text-sm leading-6 text-stone-600">Select up to eight relevant messages, 500 characters each. These become attributed historical context—not AI-extracted facts or instructions. Saving replaces the previous reviewed background.</p>
    <div className="mt-4 max-h-64 space-y-3 overflow-auto rounded-xl bg-stone-50 p-4">
      {preview.messages.slice(0, 100).map((m, index) => <label key={index} className="flex items-start gap-3 text-sm">
        <input type="checkbox" className="mt-1 shrink-0" checked={selected.includes(index)}
          disabled={busy || m.text.length > 500 || (!selected.includes(index) && selected.length >= 8)}
          onChange={(e) => setSelected(e.target.checked ? [...selected, index] : selected.filter((i) => i !== index))} />
        <span className="min-w-0"><span className="block text-xs text-stone-500">{m.sender} · {m.timestamp}{m.text.length > 500 ? " · Too long for demo context" : ""}</span>
          <span className="block whitespace-pre-wrap break-words">{m.text}</span></span>
      </label>)}
    </div>
    {preview.messages.length > 100 && <p className="mt-2 text-xs text-stone-500">Demo selection shows the first 100 messages. Use a smaller fictional export to review a later passage.</p>}
    <div className="mt-4 space-y-3 text-sm">
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} className="mt-1" />These selected messages are fictional, not private family history.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={childConsent} onChange={(e) => setChildConsent(e.target.checked)} className="mt-1" />As the demo child, I approve these exact excerpts.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={parentConsent} onChange={(e) => setParentConsent(e.target.checked)} className="mt-1" />As {recipient.label} in this demo, I agree to use these excerpts in my calls. This simulates consent; it does not verify a real person.</label>
    </div>
    <p className="mt-3 text-xs leading-5 text-stone-500">Only selected excerpts go to the local backend. Starting a demo call sends its reviewed context and audio to Google. The original TXT is not uploaded.</p>
    <button className="portal-primary mt-4" disabled={busy || recipient.busy || !synthetic || !childConsent || !parentConsent || !selected.length || !child || !parent || child === parent} onClick={() => void review()}>{busy ? "Saving review…" : `Use ${selected.length} reviewed excerpts for ${recipient.label}`}</button>
    {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm text-emerald-800">{message}</p>}
  </section>;
}
