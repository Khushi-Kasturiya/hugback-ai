"use client";

import { useEffect, useState } from "react";
import type { ChatPreview } from "@/lib/chat-import";
import { DemoFamily, DemoRecipient, demoRequest, automaticBackgroundExcerpts } from "@/lib/demo-api";

export function DemoBackgroundReview({ recipient, onChange, preview, child, parent, timezone }: {
  recipient: DemoRecipient; onChange: (family: DemoFamily) => void;
  preview: ChatPreview; child: string; parent: string; timezone: string;
}) {
  const [synthetic, setSynthetic] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    setSynthetic(false);
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
      setMessage(`${parentExcerpts} parent excerpts and ${childExamples} child style examples were converted into source-linked context for ${recipient.label}.`);
    } catch (err) { setError(err instanceof Error ? err.message : "Review could not be saved."); }
    finally { setBusy(false); }
  }
  const parentCount = preview.messages.filter((message) => message.sender === parent && message.text.trim()).length;
  return <section className="mt-6 border-t border-stone-200 pt-5">
    <h4 className="font-bold">Prepare background for {recipient.label}</h4>
    <p className="mt-2 text-sm leading-6 text-stone-600">The browser considers the conversation and sends at most 24 dated excerpts for structured extraction. HugBack stores source-linked interests, people, routines and style cues, then selects only a small relevant slice for each call. The complete file is not sent to the call model. Saving replaces the previous context.</p>
    <div className="mt-4 space-y-3 text-sm">
      <label className="flex items-start gap-2"><input type="checkbox" disabled={busy} checked={synthetic} onChange={(e) => setSynthetic(e.target.checked)} className="mt-1" />Use this fictional hackathon conversation to prepare {recipient.label}&apos;s demo context.</label>
    </div>
    <p className="mt-3 text-xs leading-5 text-stone-500">Only the prepared excerpts go to the demo backend. Starting a call sends its bounded context and audio to Google. The original TXT is not uploaded.</p>
    <button className="portal-primary mt-4" disabled={busy || recipient.busy || !synthetic || !parentCount || !child || !parent || child === parent} onClick={() => void review()}>{busy ? "Preparing…" : `Prepare ${recipient.label}'s background`}</button>
    {error && <p role="alert" className="mt-3 text-sm text-rose-800">{error}</p>}
    {message && <p role="status" className="mt-3 text-sm text-emerald-800">{message}</p>}
  </section>;
}
