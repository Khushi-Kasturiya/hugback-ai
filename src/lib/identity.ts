// Anonymous Firebase identity with a safe local-development fallback.

const STORAGE_KEY = "elara.firebase.identity.v1";
const DEVELOPMENT_KEY = "elara.development.user.v1";
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
    return value ? (JSON.parse(value) as FirebaseIdentity) : null;
  } catch {
    return null;
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
    },
  );
  if (!response.ok) {
    throw new Error("Firebase anonymous sign-in failed");
  }
  const data = await response.json();
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
    },
  );
  if (!response.ok) {
    window.localStorage.removeItem(STORAGE_KEY);
    return createAnonymousIdentity(apiKey);
  }
  const data = await response.json();
  return saveFirebaseIdentity({
    idToken: data.id_token,
    refreshToken: data.refresh_token,
    localId: data.user_id,
    expiresAt: Date.now() + Number(data.expires_in || 3600) * 1000,
  });
}

function developmentIdentity(): AuthenticationMessage {
  let userId = window.localStorage.getItem(DEVELOPMENT_KEY);
  if (!userId) {
    userId = crypto.randomUUID();
    window.localStorage.setItem(DEVELOPMENT_KEY, userId);
  }
  return { type: "authenticate", userId };
}

export async function getAuthenticationMessage(): Promise<AuthenticationMessage> {
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

