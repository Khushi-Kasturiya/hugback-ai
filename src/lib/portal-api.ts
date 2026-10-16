import { getAuthenticationHeaders } from "./identity";
import type { VoiceProfile } from "./voice-api";

export interface PortalStatus {
  identityMode: "development" | "firebase";
  voice: {
    mode: "preset" | "experimental-inline"; name: string;
    replicatedTtsEnabled?: boolean;
    profile?: VoiceProfile | null;
  };
  sharingStatus: "development_only" | "not_configured" | "awaiting_parent_link" | "ready" | "synthetic_test_only";
  importsStatus: "local_preview_only";
  localDemoEnabled?: boolean;
  demoStorage?: "sqlite" | "firestore";
  canonicalStateStore?: "firestore";
  selectedStateAdapter?: "firestore" | "sqlite_test_adapter";
  browserDraftStore?: "indexeddb_private_preconsent_staging";
  workflowEnabled?: boolean;
}

export interface ArchitectureManifest {
  version: string;
  principle: string;
  canonicalDeployment: Record<string, string>;
  runtime: Record<string, string>;
  stages: Array<{ name: string; when: string; authority: string; output: string }>;
  trustControls: string[];
  storageBoundaries: Array<{ data: string; store: string; reason: string }>;
  configured: Record<string, boolean>;
  notes: string[];
}

export interface SharedSummary {
  id: string;
  callEndedAt: string;
  approvedAt: string;
  expiresAt: string;
  text: string;
}

export function backendUrl(): string {
  const configured = process.env.NEXT_PUBLIC_HUGBACK_API_URL;
  if (configured) return configured.replace(/\/$/, "");
  const ws = process.env.NEXT_PUBLIC_HUGBACK_WS_URL;
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
    throw new Error(response.status === 401
      ? "The backend could not verify this browser's Firebase session. Check that frontend and backend Firebase projects match."
      : response.status === 403
        ? "This browser is signed in anonymously but is not authorized for the Firestore test. Add the Test operator identity shown above to HUGBACK_TEST_OWNER_UIDS, then restart the backend."
        : "The child-portal backend is unavailable. Local previews still work; server features have not been confirmed.");
  }
  return response.json() as Promise<T>;
}

export async function architectureGet(): Promise<ArchitectureManifest> {
  let response: Response;
  try {
    response = await fetch(`${backendUrl()}/api/architecture`, {
      cache: "no-store", signal: AbortSignal.timeout(8000),
    });
  } catch {
    throw new Error("The architecture manifest is unavailable because the backend could not be reached.");
  }
  if (!response.ok) throw new Error("The backend did not return its architecture manifest.");
  return response.json() as Promise<ArchitectureManifest>;
}
