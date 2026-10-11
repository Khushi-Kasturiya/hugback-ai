import { getAuthenticationHeaders } from "./identity";
import { backendUrl, PortalStatus } from "./portal-api";

export interface VoiceProfile {
  id: string;
  createdAt: string;
  expiresAt: string;
  enabled: boolean;
  expired: boolean;
  expirySource: "provider" | "local_limit";
}

export async function voiceRequest(
  path: "/enroll" | "/profile", method: "GET" | "POST" | "PUT" | "DELETE",
  body?: unknown,
): Promise<{ profile: VoiceProfile | null; enrolling?: boolean }> {
  const headers = await getAuthenticationHeaders();
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/voice${path}`, {
      method, headers: { ...headers, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined,
      cache: "no-store", signal: AbortSignal.timeout(method === "POST" ? 70_000 : 8000),
    });
  } catch {
    throw new Error("Voice setup could not be confirmed. Refresh status before retrying; the backend may still be processing. No automatic retry was made.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "Voice setup failed. Check the recordings and consent.");
  return data;
}

export async function audioBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let encoded = "";
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    encoded += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return btoa(encoded);
}

/** Never load old recordings or switch to preset after a selected voice expires. */
export function selectedVoicePayload(voice: PortalStatus["voice"]): { voiceProfileId?: string } {
  if (!voice.profile?.enabled) return {};
  if (!voice.replicatedTtsEnabled || voice.mode !== "preset") {
    throw new Error("Your custom voice is selected, but this backend cannot use it. Open Voice setup to choose the standard voice.");
  }
  if (voice.profile.expired || !Number.isFinite(Date.parse(voice.profile.expiresAt)) ||
      Date.parse(voice.profile.expiresAt) <= Date.now()) {
    throw new Error("Your custom voice expired. Open Voice setup to re-enroll or choose the standard voice.");
  }
  return { voiceProfileId: voice.profile.id };
}
