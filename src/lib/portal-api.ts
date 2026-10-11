import { getAuthenticationHeaders } from "./identity";
import type { VoiceProfile } from "./voice-api";

export interface PortalStatus {
  identityMode: "development" | "firebase";
  voice: {
    mode: "preset" | "experimental-inline"; name: string;
    replicatedTtsEnabled?: boolean;
    profile?: VoiceProfile | null;
  };
  sharingStatus: "development_only" | "not_configured" | "awaiting_parent_link" | "ready";
  importsStatus: "local_preview_only";
  localDemoEnabled?: boolean;
}

export interface SharedSummary {
  id: string;
  callEndedAt: string;
  approvedAt: string;
  expiresAt: string;
  text: string;
}

export function backendUrl(): string {
  const configured = process.env.NEXT_PUBLIC_ELARA_API_URL;
  if (configured) return configured.replace(/\/$/, "");
  const ws = process.env.NEXT_PUBLIC_ELARA_WS_URL;
  if (ws) {
    const url = new URL(ws);
    url.protocol = url.protocol === "wss:" ? "https:" : "http:";
    url.pathname = url.pathname.replace(/\/ws\/?$/, "");
    url.search = "";
    url.hash = "";
    return url.toString().replace(/\/$/, "");
  }
  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

export async function portalGet<T>(path: "/status" | "/summaries"): Promise<T> {
  const headers = await getAuthenticationHeaders();
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/portal${path}`, {
      headers, cache: "no-store", signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new Error("Could not reach the local portal backend. It may be restarting. Local previews still work; retry to check server features.");
  }
  if (!response.ok) {
    throw new Error(response.status === 401 || response.status === 403
      ? "The backend could not verify this browser's identity. Check that frontend and backend authentication modes match."
      : "The child-portal backend is unavailable. Local previews still work; server features have not been confirmed.");
  }
  return response.json() as Promise<T>;
}
