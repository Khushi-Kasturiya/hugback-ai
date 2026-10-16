"use client";

import { useEffect, useState } from "react";
import type { ChatPreview } from "@/lib/chat-import";
import { DemoFamily, DemoRecipient, demoRequest, automaticBackgroundExcerpts } from "@/lib/demo-api";

export function DemoBackgroundReview({ recipient, onChange, preview, child, parent, timezone }: {
  recipient: DemoRecipient; onChange: (family: DemoFamily) => void;
  preview: ChatPreview; child: string; parent: string; timezone: string;
}) {
  const [synthetic, setSynthetic] = useState(false);
  const [childConsent, setChildConsent] = useState(false);
  const [parentConsent, setParentConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setSynthetic(false); setChildConsent(false); setParentConsent(false);
    setMessage(""); setError("");
  }, [preview, child, parent, timezone, recipient.recipientId]);
  async function review() {
    setBusy(true); setError(""); setMessage("");
    try {
      const excerpts = automaticBackgroundExcerpts(preview, child, parent);
      onChange(await demoRequest("/background", "PUT", {
        recipientId: recipient.recipientId, revision: recipient.revision, syntheticOnly: true,
        simulateChildConsent: true, simulateParentConsent: true,
        source: preview.source, childSender: child, parentSender: parent, timeZone: timezone, excerpts,
      }));
      const parentExcerpts = excerpts.filter((item) => item.sender === parent).length;
      const childExamples = excerpts.filter((item) => item.sender === child).length;
      setMessage(`${parentExcerpts} parent background excerpts and ${childExamples} child style examples prepared for ${recipient.label}. No model was called to extract them.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Review could not be saved."); }
    finally { setBusy(false); }
  }
  const parentCount = preview.messages.filter((message) => message.sender === parent && message.text.trim()).length;
  return <section className="mt-6 border-t border-stone-200 pt-5">
    <h4 className="font-bold">Prepare background for {recipient.label}</h4>
    <p className="mt-2 text-sm leading-6 text-stone-600">No message-by-message selection. We consider all {parentCount} text messages from {parent || "the selected parent"} and prepare up to 24 dated excerpts for {recipient.label}. When suitable child replies exist, up to four are included for broad conversational style alongside up to 20 parent background messages; otherwise all 24 slots can hold parent messages. Longer parent chats still cover the timeline and favor clear personal interests. Child replies remain attributed and are not a script for HugBack to imitate. This is bounded call context, not a complete searchable copy or an AI summary. Saving replaces the previous background.</p>
    <div className="mt-4 space-y-3 text-sm">
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} className="mt-1" />This entire conversation is fictional, not private family history.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={childConsent} onChange={(e) => setChildConsent(e.target.checked)} className="mt-1" />As the demo child, I approve preparing bounded background from this conversation.</label>
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={parentConsent} onChange={(e) => setParentConsent(e.target.checked)} className="mt-1" />As {recipient.label} in this demo, I agree to use this prepared background in my calls. This simulates consent; it does not verify a real person.</label>
    </div>
    <p className="mt-3 text-xs leading-5 text-stone-500">Only the prepared excerpts go to the demo backend. Starting a call sends its bounded context and audio to Google. The original TXT is not uploaded.</p>
    <button className="portal-primary mt-4" disabled={busy || recipient.busy || !synthetic || !childConsent || !parentConsent || !parentCount || !child || !parent || child === parent} onClick={() => void review()}>{busy ? "Preparing…" : `Prepare ${recipient.label}'s background`}</button>
    {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm text-emerald-800">{message}</p>}
  </section>;
}
