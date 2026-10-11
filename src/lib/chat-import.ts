/** Strict, local-only preview. Uploaded text is data, never model instructions. */
export type ChatSource = "whatsapp" | "instagram";
export type DateOrder = "DMY" | "MDY";
export interface ChatMessage { sender: string; timestamp: string; text: string }
export interface ChatPreview {
  source: ChatSource;
  participants: string[];
  messages: ChatMessage[];
  skipped: number;
}
export const MAX_IMPORT_BYTES = 1024 * 1024;
const MAX_MESSAGES = 2000;
// Intentionally narrow. Unknown Instagram display exports are not guessed.
const ISO_LINE = /^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:\d{2}))\] ([^:\n]{1,100}): (.*)$/u;
const WA_LINE = /^\[?(\d{1,2}[/.]\d{1,2}[/.]\d{2,4}),? (\d{1,2}:\d{2}(?::\d{2})?(?:\s?[AP]M)?)\]?(?: - | )(.+)$/iu;
const OMITTED = /^(?:<media omitted>|(?:image|video|audio|sticker|document) omitted|this message was deleted|you deleted this message)$/iu;

function whatsappTime(date: string, time: string, order: DateOrder): string {
  const parts = date.split(/[/.]/).map(Number);
  const year = parts[2] < 100 ? parts[2] + 2000 : parts[2];
  const month = order === "DMY" ? parts[1] : parts[0];
  const day = order === "DMY" ? parts[0] : parts[1];
  const match = /^(\d{1,2}):(\d{2})(?::(\d{2}))?\s?(AM|PM)?$/i.exec(time);
  if (!match) throw new Error("A message has an unsupported time.");
  let hour = Number(match[1]);
  const minute = Number(match[2]), second = Number(match[3] || 0);
  if (match[4]) {
    if (hour < 1 || hour > 12) throw new Error("A message has an invalid time.");
    hour = hour % 12 + (match[4].toUpperCase() === "PM" ? 12 : 0);
  }
  const valid = new Date(Date.UTC(year, month - 1, day));
  if (valid.getUTCFullYear() !== year || valid.getUTCMonth() !== month - 1 ||
      valid.getUTCDate() !== day || hour > 23 || minute > 59 || second > 59) {
    throw new Error("A date is invalid. Check the export's day/month order.");
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  // Preserve wall time, deliberately without inventing a timezone.
  return `${year}-${pad(month)}-${pad(day)}T${pad(hour)}:${pad(minute)}:${pad(second)}`;
}

function instagramJson(text: string): { messages: ChatMessage[]; skipped: number } {
  const data = JSON.parse(text);
  if (!data || !Array.isArray(data.participants) || data.participants.length !== 2 ||
      !Array.isArray(data.messages) || data.messages.length > MAX_MESSAGES) {
    throw new Error("Choose one two-person Instagram conversation, not a whole account archive.");
  }
  const participants = data.participants.map((p: { name?: unknown }) => p?.name);
  if (participants.some((p: unknown) => typeof p !== "string" || !p || p.length > 100) ||
      new Set(participants).size !== 2) throw new Error("Instagram participants are ambiguous.");
  const messages: ChatMessage[] = [];
  let skipped = 0;
  for (const item of data.messages) {
    if (!participants.includes(item.sender_name) || !Number.isSafeInteger(item.timestamp_ms) ||
        item.timestamp_ms < 0 || !Number.isFinite(new Date(item.timestamp_ms).getTime())) {
      throw new Error("An Instagram message is missing a valid sender or timestamp.");
    }
    if (item.content === undefined) { skipped++; continue; } // media-only entry
    if (typeof item.content !== "string") throw new Error("Unsupported Instagram message content.");
    messages.push({ sender: item.sender_name, timestamp: new Date(item.timestamp_ms).toISOString(), text: item.content });
  }
  return { messages: messages.sort((a, b) => a.timestamp.localeCompare(b.timestamp)), skipped };
}

function validIso(value: string): boolean {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?/.exec(value);
  if (!match || !Number.isFinite(Date.parse(value))) return false;
  const [, year, month, day, hour, minute, second = "0"] = match;
  const date = new Date(`${year}-${month}-${day}T00:00:00Z`);
  return date.getUTCFullYear() === Number(year) && date.getUTCMonth() + 1 === Number(month)
    && date.getUTCDate() === Number(day) && Number(hour) < 24 && Number(minute) < 60 && Number(second) < 60;
}

export function parseChat(text: string, source: ChatSource, order: DateOrder = "DMY"): ChatPreview {
  if (new TextEncoder().encode(text).length > MAX_IMPORT_BYTES) throw new Error("Choose a file smaller than 1 MB.");
  if (!text.trim() || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\ufffd]/u.test(text)) {
    throw new Error("Choose a valid UTF-8 text export, without binary content.");
  }
  let skipped = 0;
  let messages: ChatMessage[] = [];
  const normalized = text.replace(/^\uFEFF/u, "").replace(/\r\n?/g, "\n");
  if (source === "instagram" && normalized.trimStart().startsWith("{")) {
    try { ({ messages, skipped } = instagramJson(normalized)); }
    catch (error) {
      if (error instanceof SyntaxError) throw new Error("This is not valid Instagram conversation JSON.");
      throw error;
    }
  } else {
    let current: ChatMessage | null = null;
    for (const original of normalized.split("\n")) {
      const line = original.replace(/[\u200e\u200f\u202a-\u202e]/g, "").replace(/[\u202f\u00a0]/g, " ");
      if (!line.trim()) continue;
      const iso = ISO_LINE.exec(line);
      const wa = source === "whatsapp" ? WA_LINE.exec(line) : null;
      if (iso) {
        if (!validIso(iso[1])) throw new Error("Invalid ISO timestamp.");
        current = { timestamp: iso[1], sender: iso[2].trim(), text: iso[3] };
        messages.push(current);
      } else if (wa) {
        const timestamp = whatsappTime(wa[1], wa[2], order);
        const separator = wa[3].indexOf(": ");
        if (separator < 1) { current = null; skipped++; continue; }
        current = { timestamp, sender: wa[3].slice(0, separator).trim(), text: wa[3].slice(separator + 2) };
        messages.push(current);
      } else {
        if (!current || /^(?:\[?\d{1,4}[/-]\d{1,2}[/-]\d{1,4}|\[\d{4}-)/.test(line)) {
          throw new Error("Unrecognized message structure. Keep original sender names and timestamps; use the documented text template for Instagram.");
        }
        current.text += `\n${line}`;
      }
      if (messages.length > MAX_MESSAGES) throw new Error("Limit each import to 2,000 messages.");
    }
  }
  const participants = [...new Set(messages.map((m) => m.sender))];
  if (participants.length !== 2 || participants.some((p) => !p || p.length > 100)) {
    throw new Error("Only direct, two-person conversations are supported. Check the participant names.");
  }
  messages = messages.filter((m) => {
    if (OMITTED.test(m.text.trim()) || !m.text.trim()) { skipped++; return false; }
    return true;
  });
  if (!messages.length) throw new Error("No text messages were found.");
  return { source, participants, messages, skipped };
}

export const SYNTHETIC_CHAT = `[2026-10-01T18:00:00+05:30] Parent: I enjoyed watering my plants today.
[2026-10-01T18:01:00+05:30] Child: Which plants are flowering?
[2026-10-01T18:02:00+05:30] Parent: The jasmine. Please speak to me in Hindi.
[2026-10-01T18:03:00+05:30] Child: Of course.`;
