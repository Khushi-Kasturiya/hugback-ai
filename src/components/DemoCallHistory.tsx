"use client";

import { useState } from "react";
import { DemoRecipient, DemoCallSummary, demoCallSummary, generateLegacyCallSummary } from "@/lib/demo-api";

function localDay(value: string, timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date(value));
  const part = (type: string) => parts.find((item) => item.type === type)?.value || "";
  return `${part("year")}-${part("month")}-${part("day")}`;
}

function displayTime(value: string, timeZone: string): string {
  return new Intl.DateTimeFormat(undefined, {
    timeZone, day: "numeric", month: "short", year: "numeric",
    hour: "numeric", minute: "2-digit", timeZoneName: "short",
  }).format(new Date(value));
}

function summaryMessage(call: DemoRecipient["calls"][number]): string {
  if (call.summaryStatus === "pending") return "Preparing summary…";
  if (call.summaryStatus === "revoked") return "Saved summary was erased when sharing stopped.";
  if (call.summaryStatus === "unavailable") {
    if (call.summaryFailureCode === "missing_text") return "No usable speech transcript reached the backend for this call, so it could not prepare a summary.";
    if (call.summaryFailureCode === "input_too_long") return "The speech transcript exceeded the summary limit for this call.";
    if (call.summaryFailureCode === "timeout") return "Google took too long to prepare this summary. Try a new call after the service recovers.";
    if (call.summaryFailureCode === "rate_limited") return "Google's summary limit was reached for this call. Try a new call later.";
    if (call.summaryFailureCode === "provider_unavailable" || call.summaryFailureCode === "network_unavailable") return "Google's summary service was unavailable for this call. Try a new call later.";
    if (call.summaryFailureCode === "provider_access" || call.summaryFailureCode === "model_unavailable" || call.summaryFailureCode === "provider_request_rejected") return "The backend's summary model could not be used. Check its Google model access and configuration.";
    if (call.summaryFailureCode === "invalid_output") return "The summary model returned an invalid result for this call.";
    if (call.summaryFailureCode === "model_or_content") return "The summary model did not return a usable, grounded summary for this call.";
    if (call.summaryFailureCode === "processing_unavailable") return "Call processing ended before summary input was ready.";
    return "A reliable summary could not be prepared for this call.";
  }
  if (call.canGenerateLegacySummary) return "This earlier call has saved text that can be converted to a summary.";
  if (call.summaryStatus === "not_enabled" || call.transcriptStatus === "not_enabled") {
    return "Call summaries were off for this person when the call began. No call text was saved, so this call cannot be summarized later. Enable future call summaries in Family setup before the next call.";
  }
  return "This earlier call has no saved text to summarize.";
}

export function DemoCallHistory({ recipient, refresh }: { recipient?: DemoRecipient; refresh: () => Promise<void> }) {
  const [day, setDay] = useState("");
  const [open, setOpen] = useState("");
  const [saved, setSaved] = useState<Record<string, DemoCallSummary>>({});
  const [loading, setLoading] = useState("");
  const [converting, setConverting] = useState("");
  const [error, setError] = useState("");
  const [errorFor, setErrorFor] = useState("");
  const calls = (recipient?.calls || []).filter((call) => !day || localDay(call.startedAt, recipient!.timeZone) === day).slice().reverse();

  async function toggle(sessionId: string) {
    if (!recipient) return;
    if (open === sessionId) { setOpen(""); return; }
    setOpen(sessionId); setError(""); setErrorFor(sessionId);
    if (saved[sessionId]) return;
    setLoading(sessionId);
    try {
      const result = await demoCallSummary(recipient.recipientId, sessionId);
      setSaved((current) => ({ ...current, [sessionId]: result }));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Call summary is unavailable.");
    } finally { setLoading(""); }
  }

  async function convert(sessionId: string) {
    if (!recipient || converting) return;
    setConverting(sessionId); setError(""); setErrorFor(sessionId);
    try {
      await generateLegacyCallSummary(recipient.recipientId, recipient.revision, sessionId);
      await refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Could not prepare this older summary.");
    } finally { setConverting(""); }
  }

  return <section className="rounded-[1.5rem] border border-white bg-white/80 p-5">
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div><h4 className="font-serif text-xl text-[#252D49]">Call summaries</h4></div>
      <button type="button" className="portal-secondary" onClick={() => void refresh()}>Refresh calls</button>
    </div>
    <label className="mt-4 block max-w-xs text-xs font-bold text-stone-700">Filter by call date
      <input className="portal-input mt-1" type="date" value={day} onChange={(event) => { setDay(event.target.value); setOpen(""); }} />
    </label>
    {day && <button type="button" className="mt-2 text-xs font-semibold text-[#56619C] underline" onClick={() => setDay("")}>Show all dates</button>}
    {!recipient ? <p className="mt-5 text-sm text-stone-600">Select a family member above to see their calls.</p> : !calls.length ? <p className="mt-5 text-sm text-stone-600">{day ? "No test calls on this date." : `No test calls for ${recipient.label} yet.`}</p> : <>
      {calls.length > 3 && <p className="mt-4 text-xs text-stone-500">Scroll inside the list to see older calls.</p>}
      <ol className="mt-3 space-y-3 overflow-y-auto overscroll-contain pr-2 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#56619C]" style={{ maxHeight: "min(65vh, 36rem)", scrollbarGutter: "stable" }} tabIndex={0} aria-label={`${recipient.label} call summaries`}>{calls.map((call) => {
      const available = call.summaryStatus === "available" && recipient.transcriptSharingEnabled;
      const expanded = available && open === call.sessionId;
      return <li key={call.sessionId} className="rounded-xl bg-[#F7F8FC] p-4 text-sm">
        <div className="flex flex-wrap items-start justify-between gap-3"><div><p className="font-semibold text-stone-800">{recipient.label} · {call.status === "completed" ? "Completed call" : call.status === "active" || call.status === "processing" ? "Call in progress" : "Call ended"}</p><time className="mt-1 block text-xs text-stone-600" dateTime={call.startedAt}>{displayTime(call.startedAt, recipient.timeZone)}</time></div>
          {available && <button type="button" className="portal-secondary" aria-expanded={expanded} onClick={() => void toggle(call.sessionId)}>{expanded ? "Hide summary" : "View summary"}</button>}
          {!available && call.canGenerateLegacySummary && <button type="button" className="portal-secondary" disabled={!!converting} onClick={() => void convert(call.sessionId)}>{converting === call.sessionId ? "Preparing…" : "Generate summary for earlier call"}</button>}
        </div>
        {call.alert && <p className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-950"><strong>{call.alert.category === "fever" ? "Reported fever" : "Close loss mentioned"}.</strong> {call.alert.status === "sent" ? "Brief email accepted by Gmail SMTP." : call.alert.status === "failed" ? "Email attempt failed; check backend configuration." : call.alert.status === "not_configured" ? "Email not configured; no email was sent." : call.alert.status === "suppressed" ? "Recent notice already covered this topic; no repeat email." : "Email delivery is pending or unconfirmed."} This is an automated topic match, not a diagnosis or emergency alert.</p>}
        {call.summaryEmailStatus && <p className="mt-2 text-xs text-stone-600">Summary email: {call.summaryEmailStatus === "sent" ? "accepted by the email provider" : call.summaryEmailStatus === "failed" ? "delivery attempt failed" : call.summaryEmailStatus === "not_configured" ? "notification email not configured" : "sending"}.</p>}
        {!available && <p className="mt-2 text-xs text-stone-600">{summaryMessage(call)}{call.canGenerateLegacySummary ? " This action sends the older saved fictional text to Google and may incur model charges; the raw text will be erased after a successful summary." : ""}</p>}
        {error && errorFor === call.sessionId && !expanded && <p role="alert" className="mt-2 text-xs text-rose-800">{error}</p>}
        {expanded && <div className="mt-4 border-t border-[#E2E5F1] pt-4" role="region" aria-label={`${recipient.label} call summary`}>
          {loading === call.sessionId && <p className="text-stone-600">Loading summary…</p>}
          {error && errorFor === call.sessionId && <p role="alert" className="text-rose-800">{error}</p>}
          {saved[call.sessionId] && <p className="rounded-lg bg-white p-3 text-sm leading-6 text-stone-800">{saved[call.sessionId].summary}</p>}
        </div>}
      </li>;
    })}</ol></>}
  </section>;
}
