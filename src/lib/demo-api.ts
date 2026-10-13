import { getAuthenticationHeaders } from "./identity";
import { backendUrl } from "./portal-api";
import type { ChatPreview } from "./chat-import";
import type { PortalStatus } from "./portal-api";
import { selectedVoicePayload } from "./voice-api";

export interface DemoExcerpt {
  sourceIndex: number;
  sender: string;
  timestamp: string;
  text: string;
  role: "child" | "parent";
  source: "whatsapp" | "instagram";
  reviewedAt: string;
}
export interface WellbeingSignal {
  signalId: string;
  category: "upbeat" | "calm" | "neutral" | "lower_energy" | "tense";
  confidence: "medium" | "high";
  basis: ("explicit_self_report" | "conversation_content" | "vocal_cues")[];
  displayText: string;
  observedAt: string;
  expiresAt: string;
  policyVersion: string;
  syntheticOnly: true;
}
export interface DemoRecipient {
  recipientId: string;
  label: string;
  relationship: "mother" | "father" | "grandmother" | "grandfather" | "other";
  legacy?: boolean;
  voice: { mode: "standard" | "child"; profileId: string | null };
  timeZone: string;
  revision: number;
  background: DemoExcerpt[];
  memoryEnabled: boolean;
  memoryCount: number;
  memoryCooldownHours: number;
  busy: boolean;
  wellbeingSharingEnabled: boolean;
  toneContinuityEnabled: boolean;
  transcriptSharingEnabled: boolean;
  alertSharingEnabled: boolean;
  wellbeingSignals: WellbeingSignal[];
  language?: "auto" | "en" | "hi" | "hi-en";
  calls: { sessionId: string; startedAt: string; endedAt?: string; status: string;
    transcriptStatus?: "pending" | "available" | "not_enabled" | "unavailable" | "revoked";
    summaryStatus?: "pending" | "available" | "not_enabled" | "unavailable" | "revoked";
    summaryFailureCode?: "missing_text" | "input_too_long" | "model_or_content" | "processing_unavailable";
    canGenerateLegacySummary?: boolean;
    alert?: { category: "fever" | "bereavement"; observedAt: string;
      status: "pending" | "sending" | "sent" | "failed" | "suppressed" | "not_configured" };
    memoryErrorCode?: string;
    workflow?: Partial<Record<"planner" | "reconciler" | "critic", string>> }[];
}
export interface DemoFamily {
  familyId: string;
  childId: string;
  childGender?: "female" | "male" | "neutral" | null;
  childGenderRevision?: number;
  syntheticOnly: true;
  schemaVersion: 2;
  expiresAt: string;
  recipients: DemoRecipient[];
  storageMode?: "sqlite" | "firestore";
  alertEmailSelected?: boolean;
  alertEmailHint?: string | null;
  alertEmailConfigured?: boolean;
}

export class DemoApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function demoRequest(path: "/family" | "/child-details" | "/background" | "/background/clear" | "/recipients" | "/recipient-voice" | "/wellbeing-sharing" | "/tone-continuity" | "/transcript-sharing" | "/alert-sharing" | "/alert-destination", method = "GET", body?: unknown): Promise<DemoFamily> {
  const headers = await getAuthenticationHeaders();
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/demo${path}`, {
      method, headers: { ...headers, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new DemoApiError("Test backend is unavailable. The request outcome is unknown; refresh before retrying a change.", 0);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new DemoApiError(typeof error.detail === "string" ? error.detail :
      "Demo request was rejected. Check participant mapping, timezone and excerpt limits.", response.status);
  }
  const result = await response.json();
  if (result.schemaVersion !== 2 || !Array.isArray(result.recipients)) {
    throw new DemoApiError("The backend needs the multi-recipient update. Call setup is blocked.", 0);
  }
  return result;
}

export interface DemoCallSummary {
  sessionId: string;
  startedAt: string;
  endedAt?: string;
  syntheticOnly: true;
  summary: string;
}

export async function demoCallSummary(recipientId: string, sessionId: string): Promise<DemoCallSummary> {
  const headers = await getAuthenticationHeaders();
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/demo/summaries/${encodeURIComponent(recipientId)}/${encodeURIComponent(sessionId)}`, {
      headers, cache: "no-store", signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new DemoApiError("Test backend is unavailable. Try refreshing the call summaries.", 0);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new DemoApiError(typeof error.detail === "string" ? error.detail : "Call summary is unavailable.", response.status);
  }
  return response.json();
}

export async function generateLegacyCallSummary(recipientId: string, revision: number, sessionId: string): Promise<void> {
  const headers = await getAuthenticationHeaders();
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/demo/summaries/${encodeURIComponent(recipientId)}/${encodeURIComponent(sessionId)}/generate`, {
      method: "POST", headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({ syntheticOnly: true, recipientId, revision }),
      cache: "no-store", signal: AbortSignal.timeout(15_000),
    });
  } catch {
    throw new DemoApiError("The summary request outcome is unknown. Refresh calls before retrying.", 0);
  }
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new DemoApiError(typeof error.detail === "string" ? error.detail : "Could not prepare this older summary.", response.status);
  }
}

export function needsDemoRefresh(family?: DemoFamily, now = Date.now()): boolean {
  return !!family?.recipients.some((recipient) => {
    const call = recipient.calls?.slice(-1)[0];
    return recipient.busy || (call?.summaryStatus === "pending" &&
      now - Date.parse(call.endedAt || call.startedAt) < 60_000) || ((call?.alert?.status === "pending" || call?.alert?.status === "sending") &&
      now - Date.parse(call.endedAt || call.startedAt) < 60_000) || (call?.workflow?.critic === "pending" &&
      now - Date.parse(call.endedAt || call.startedAt) < 60_000);
  });
}

/** Fixed copy only: never render an arbitrary provider error or private output. */
export function memoryFailureMessage(code?: string): string {
  const messages: Record<string, string> = {
    provider_access: "Google rejected access to the memory model. Check the backend key/project permissions.",
    model_unavailable: "The configured memory model or endpoint was not found. Check FOLLOWUP_EXTRACTION_MODEL.",
    rate_limited: "Google rate-limited the memory request. Check quota; no automatic paid retry was made.",
    provider_unavailable: "Google could not complete memory processing. No automatic paid retry was made.",
    provider_request_rejected: "Google rejected the memory request. Check the structured-output/model configuration.",
    timeout: "The memory update timed out. A working live voice connection does not confirm post-call extraction.",
    network_unavailable: "The backend could not reach Google for the memory update.",
    invalid_output: "The memory model returned output that failed validation. It was not accepted as memory.",
    context_unavailable: "The recipient’s memory context could not be loaded when the call started.",
    storage_unavailable: "Memory storage or finalization was unavailable.",
    processing_interrupted: "Memory processing was interrupted before completion.",
    processing_failed: "Memory processing failed without a more specific category. Check the safe backend diagnostics; no automatic replay was made.",
  };
  return (code && messages[code]) || "No detailed failure reason was recorded for this call. Future calls now record a safe error category; the old transcript is not retained for replay.";
}

export function parentCallUrl(recipientId?: string): string {
  return recipientId ? `/call?recipient=${encodeURIComponent(recipientId)}` : "/call";
}

/** A URL/selector is not authorization. The server rechecks membership + revision. */
export function recipientCallPayload(family: DemoFamily, recipientId: string | undefined, voice: PortalStatus["voice"]) {
  const recipient = family.recipients.find((item) => item.recipientId === recipientId);
  if (!recipient) throw new Error("Choose a recipient from your demo family before calling.");
  if (recipient.busy) throw new Error("This recipient's call is active or still saving memory.");
  let selection: { voiceProfileId?: string } = {};
  if (recipient.voice.mode === "child") {
    if (!recipient.voice.profileId || recipient.voice.profileId !== voice.profile?.id || !voice.profile.enabled) {
      throw new Error("This recipient's assigned child voice is unavailable. Reassign it or choose standard voice in Child setup.");
    }
    selection = selectedVoicePayload(voice);
  }
  return { demoParent: true, demoRecipientId: recipient.recipientId,
    demoRecipientRevision: recipient.revision, ...selection };
}

export function reviewedExcerpts(preview: ChatPreview, indexes: number[], child: string, parent: string) {
  if (child === parent || !preview.participants.includes(child) || !preview.participants.includes(parent)) {
    throw new Error("Choose two different participants before reviewing.");
  }
  if (indexes.length < 1 || indexes.length > 24 || new Set(indexes).size !== indexes.length) {
    throw new Error("Prepare between one and 24 distinct excerpts.");
  }
  return indexes.map((sourceIndex) => {
    const message = preview.messages[sourceIndex];
    if (!Number.isInteger(sourceIndex) || sourceIndex < 0 || !message || !message.text.trim() || message.text.length > 500) {
      throw new Error("Choose excerpts with at most 500 characters.");
    }
    if (![child, parent].includes(message.sender)) throw new Error("Unknown participant.");
    return { ...message, sourceIndex };
  });
}

/** One-action synthetic context: consider every parent-authored text message,
 * preserve clear personal interests and timeline coverage. Raw chat is not sent. */
export function automaticBackgroundExcerpts(preview: ChatPreview, child: string, parent: string) {
  if (child === parent || !preview.participants.includes(child) || !preview.participants.includes(parent)) {
    throw new Error("Choose two different participants before preparing background.");
  }
  const parentMessages = preview.messages.flatMap((message, sourceIndex) =>
    message.sender === parent && message.text.trim() ? [{ ...message, sourceIndex }] : []);
  if (!parentMessages.length) throw new Error("This chat has no text messages from the selected parent.");
  const count = Math.min(24, parentMessages.length);
  let selected = parentMessages;
  if (parentMessages.length > count) {
    const interest = /\b(?:i\s+(?:like|love|enjoy|prefer|used to|remember)|my\s+(?:favourite|favorite|hobby)|mujhe|main\s+pasand)\b|(?:मुझे|मैं|मेरा|मेरी|पसंद)/iu;
    const chosen = new Set<number>();
    const timelineSlots = count - Math.min(12, count);
    for (let index = 0; index < timelineSlots; index++) {
      chosen.add(Math.floor((index + 0.5) * parentMessages.length / timelineSlots));
    }
    // Preserve a few explicit self-descriptions even if they sit between
    // evenly spaced timeline samples. This is selection, not fact extraction.
    const ranked = parentMessages.map((message, index) => ({ index,
      score: Number(interest.test(message.text)) * 2 + Number(message.text.trim().length >= 25),
    })).filter((item) => item.score >= 2).sort((a, b) => b.score - a.score || a.index - b.index);
    for (const item of ranked) {
      if (chosen.size >= count) break;
      chosen.add(item.index);
    }
    for (let index = 0; index < count && chosen.size < count; index++) {
      chosen.add(Math.floor((index + 0.5) * parentMessages.length / count));
    }
    for (let index = 0; chosen.size < count && index < parentMessages.length; index++) chosen.add(index);
    selected = [...chosen].sort((a, b) => a - b).map((index) => parentMessages[index]);
  }
  return selected.map(({ sourceIndex, sender, timestamp, text }) => ({
    sourceIndex, sender, timestamp, text: text.trim().slice(0, 500),
  }));
}
