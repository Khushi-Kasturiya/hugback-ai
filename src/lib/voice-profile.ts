const DATABASE_NAME = "hugback-private-voice";
const STORE_NAME = "profiles";
const PROFILE_KEY = "active";

interface StoredVoiceProfile {
  reference: Blob;
  consent: Blob;
  savedAt: number;
}

export interface InlineVoicePayload {
  voiceSampleAudio: string;
  consentAudio: string;
}

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DATABASE_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME);
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error || new Error("Could not open private voice storage"));
  });
}

async function withStore<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  try {
    return await new Promise<T>((resolve, reject) => {
      const transaction = database.transaction(STORE_NAME, mode);
      const request = action(transaction.objectStore(STORE_NAME));
      transaction.oncomplete = () => resolve(request.result);
      transaction.onerror = transaction.onabort = () => reject(transaction.error || new Error("Private voice storage failed"));
    });
  } finally {
    database.close();
  }
}

export async function hasLocalVoiceProfile(): Promise<boolean> {
  return Boolean(await withStore("readonly", (store) => store.get(PROFILE_KEY)));
}

export async function saveLocalVoiceProfile(reference: Blob, consent: Blob): Promise<void> {
  await withStore("readwrite", (store) =>
    store.put({ reference, consent, savedAt: Date.now() } satisfies StoredVoiceProfile, PROFILE_KEY),
  );
}

export async function deleteLocalVoiceProfile(): Promise<void> {
  await withStore("readwrite", (store) => store.delete(PROFILE_KEY));
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const value = String(reader.result || "");
      const separator = value.indexOf(",");
      separator >= 0 ? resolve(value.slice(separator + 1)) : reject(new Error("Could not encode voice recording"));
    };
    reader.onerror = () => reject(reader.error || new Error("Could not read voice recording"));
    reader.readAsDataURL(blob);
  });
}

export async function getInlineVoicePayload(): Promise<InlineVoicePayload | null> {
  const profile = await withStore<StoredVoiceProfile | undefined>(
    "readonly",
    (store) => store.get(PROFILE_KEY),
  );
  if (!profile) return null;
  const [voiceSampleAudio, consentAudio] = await Promise.all([
    blobToBase64(profile.reference),
    blobToBase64(profile.consent),
  ]);
  return { voiceSampleAudio, consentAudio };
}
