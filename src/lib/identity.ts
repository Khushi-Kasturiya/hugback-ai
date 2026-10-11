// Anonymous Firebase identity with a safe local-development fallback.

const STORAGE_KEY = "hugback.firebase.identity.v1";
const DEVELOPMENT_KEY = "hugback.development.user.v1";
const FIREBASE_API_KEY = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;

interface FirebaseIdentity {
  idToken: string;
  refreshToken: string;
  expiresAt: number;
  localId: string;
}

export type AuthenticationMessage =
  | { type: "authenticate"; idToken: string }
  | { type: "authenticate"; userId: string };

function readFirebaseIdentity(): FirebaseIdentity | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    if (!value) return null;
    const identity = JSON.parse(value) as FirebaseIdentity;
    if (typeof identity.idToken !== "string" || !identity.idToken ||
        typeof identity.refreshToken !== "string" || !identity.refreshToken ||
        typeof identity.localId !== "string" || !identity.localId ||
        !Number.isFinite(identity.expiresAt)) {
      throw new Error("Stored identity is invalid.");
    }
    return identity;
  } catch {
    // Never silently create another owner when stored credentials are damaged.
    throw new Error("This browser's saved identity could not be read. Do not clear browser data if you need to retain access.");
  }
}

function saveFirebaseIdentity(identity: FirebaseIdentity): FirebaseIdentity {
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(identity));
  return identity;
}

async function createAnonymousIdentity(apiKey: string): Promise<FirebaseIdentity> {
  const response = await fetch(
    `https://identitytoolkit.googleapis.com/v1/accounts:signUp?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ returnSecureToken: true }),
      signal: AbortSignal.timeout(8000),
    },
  );
  if (!response.ok) {
    throw new Error("Firebase anonymous sign-in failed");
  }
  const data = await response.json();
  if (typeof data.idToken !== "string" || !data.idToken || typeof data.refreshToken !== "string" ||
      !data.refreshToken || typeof data.localId !== "string" || !data.localId ||
      !Number.isFinite(Number(data.expiresIn)) || Number(data.expiresIn) <= 0) {
    throw new Error("Firebase returned an invalid anonymous identity.");
  }
  return saveFirebaseIdentity({
    idToken: data.idToken,
    refreshToken: data.refreshToken,
    localId: data.localId,
    expiresAt: Date.now() + Number(data.expiresIn || 3600) * 1000,
  });
}

async function refreshAnonymousIdentity(
  apiKey: string,
  identity: FirebaseIdentity,
): Promise<FirebaseIdentity> {
  const response = await fetch(
    `https://securetoken.googleapis.com/v1/token?key=${encodeURIComponent(apiKey)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({
        grant_type: "refresh_token",
        refresh_token: identity.refreshToken,
      }),
      signal: AbortSignal.timeout(8000),
    },
  );
  if (!response.ok) {
    // A network/authentication failure is not permission to abandon this UID.
    throw new Error("Could not renew your anonymous session. Your saved identity has been kept; please retry.");
  }
  const data = await response.json();
  if (data.user_id !== identity.localId || typeof data.id_token !== "string" || !data.id_token ||
      typeof data.refresh_token !== "string" || !data.refresh_token ||
      !Number.isFinite(Number(data.expires_in)) || Number(data.expires_in) <= 0) {
    throw new Error("Firebase session refresh did not preserve this browser's identity.");
  }
  return saveFirebaseIdentity({
    idToken: data.id_token,
    refreshToken: data.refresh_token,
    localId: data.user_id,
    expiresAt: Date.now() + Number(data.expires_in || 3600) * 1000,
  });
}

function developmentIdentity(): AuthenticationMessage {
  if (!["localhost", "127.0.0.1", "[::1]"].includes(window.location.hostname)) {
    throw new Error("Firebase anonymous authentication must be configured outside localhost.");
  }
  let userId = window.localStorage.getItem(DEVELOPMENT_KEY);
  if (!userId) {
    userId = crypto.randomUUID();
    window.localStorage.setItem(DEVELOPMENT_KEY, userId);
  }
  return { type: "authenticate", userId };
}

async function resolveAuthenticationMessage(): Promise<AuthenticationMessage> {
  if (!FIREBASE_API_KEY) {
    return developmentIdentity();
  }

  let identity = readFirebaseIdentity();
  if (!identity) {
    identity = await createAnonymousIdentity(FIREBASE_API_KEY);
  } else if (identity.expiresAt <= Date.now() + 60_000) {
    identity = await refreshAnonymousIdentity(FIREBASE_API_KEY, identity);
  }
  return { type: "authenticate", idToken: identity.idToken };
}

let identityRequest: Promise<AuthenticationMessage> | null = null;

export function getAuthenticationMessage(): Promise<AuthenticationMessage> {
  if (!identityRequest) {
    // Coordinate first enrollment and refresh across tabs on this origin.
    identityRequest = (async () => {
      if (typeof navigator !== "undefined" && navigator.locks) {
        return await navigator.locks.request("hugback-anonymous-identity", resolveAuthenticationMessage);
      }
      return resolveAuthenticationMessage();
    })().finally(() => { identityRequest = null; });
  }
  return identityRequest;
}

export async function getBrowserIdentity(): Promise<{ owner: string; mode: "firebase" | "development" }> {
  const auth = await getAuthenticationMessage();
  if ("userId" in auth) return { owner: `development:${auth.userId}`, mode: "development" };
  const identity = readFirebaseIdentity();
  if (!identity) throw new Error("Anonymous identity is unavailable.");
  return { owner: `firebase:${identity.localId}`, mode: "firebase" };
}

export async function getAuthenticationHeaders(): Promise<Record<string, string>> {
  const auth = await getAuthenticationMessage();
  return "idToken" in auth
    ? { Authorization: `Bearer ${auth.idToken}` }
    : { "X-Hugback-Development-User": auth.userId };
}
