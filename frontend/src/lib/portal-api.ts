import { getAuthenticationHeaders } from "./identity";
import type { VoiceProfile } from "./voice-api";

export interface PortalStatus {
  identityMode: "development" | "firebase";
  voice: {
    mode: "preset" | "experimental-inline"; name: string;
    replicatedTtsEnabled?: boolean;
    storage?: "firestore" | "sqlite_test_adapter";
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
  remoteTestEnabled?: boolean;
  publicDemoEnabled?: boolean;
  judgeDemoEnabled?: boolean;
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
    if (response.status === 403) {
      const body = await response.json().catch(() => null);
      if (body?.detail === "Demo mode is localhost-only.") {
        throw new Error("This backend only permits the synthetic simulator from localhost. Adding a UID or changing CORS will not enable hosted access; a reviewed remote test gate is required.");
      }
      if (body?.detail === "This identity is not an authorized synthetic test operator.") {
        const local = ["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname);
        throw new Error(local
          ? "This browser is signed in anonymously but is not authorized for the Firestore test. In Local connection details, copy the Backend allowlist UID (without the firebase: prefix). An operator must add it to HUGBACK_TEST_OWNER_UIDS, restart the backend, then Retry connection."
          : "This browser's Firebase UID is not approved for this test. Ask the operator to review the deployed backend's HUGBACK_TEST_OWNER_UIDS. Local connection details are available only on localhost; never share ID or refresh tokens.");
      }
      // An unrelated 403 is not evidence that approving another UID will fix it.
      // Do not echo arbitrary backend/provider response bodies.
      throw new Error("The backend denied portal access. Ask the operator to check the test-mode configuration, permitted origin and browser authorization. No access checks were bypassed.");
    }
    throw new Error(response.status === 401
      ? "The backend could not verify this browser's Firebase session. Check that frontend and backend Firebase projects match."
      : response.status === 403
        ? "This Firebase session is not authorized for the configured demo. Refresh once; if it continues, check the backend judge-demo policy."
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
