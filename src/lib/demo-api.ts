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
  wellbeingSignals: WellbeingSignal[];
  calls: { sessionId: string; startedAt: string; endedAt?: string; status: string }[];
}
export interface DemoFamily {
  familyId: string;
  childId: string;
  syntheticOnly: true;
  schemaVersion: 2;
  expiresAt: string;
  recipients: DemoRecipient[];
}

export class DemoApiError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

export async function demoRequest(path: "/family" | "/background" | "/background/clear" | "/recipients" | "/recipient-voice" | "/wellbeing-sharing", method = "GET", body?: unknown): Promise<DemoFamily> {
  const headers = await getAuthenticationHeaders();
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/demo${path}`, {
      method, headers: { ...headers, ...(body ? { "Content-Type": "application/json" } : {}) },
      ...(body ? { body: JSON.stringify(body) } : {}),
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new DemoApiError("Local demo backend is unavailable. Nothing was sent to cloud storage.", 0);
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
  if (indexes.length < 1 || indexes.length > 8 || new Set(indexes).size !== indexes.length) {
    throw new Error("Select between one and eight distinct excerpts.");
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
