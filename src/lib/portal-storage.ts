import type { ChatPreview } from "./chat-import";

export interface BackgroundImport {
  id: string;
  owner: string;
  recipientId?: string;
  filename: string;
  fingerprint: string;
  createdAt: number;
  expiresAt: number;
  childSender: string;
  parentSender: string;
  timezone: string;
  preview: ChatPreview;
  status: "local_only";
}

const RETENTION_MS = 7 * 24 * 60 * 60 * 1000;

async function database(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open("elara-child-portal", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("imports", { keyPath: "id" });
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(new Error("This browser could not open local background storage."));
  });
}

async function transaction<T>(mode: IDBTransactionMode, work: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("imports", mode);
      const request = work(tx.objectStore("imports"));
      tx.oncomplete = () => resolve(request.result);
      tx.onerror = tx.onabort = () => reject(new Error("Local storage could not complete the change."));
    });
  } finally { db.close(); }
}

async function updateImports<T>(work: (store: IDBObjectStore, records: BackgroundImport[]) => T): Promise<T> {
  const db = await database();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction("imports", "readwrite");
      const store = tx.objectStore("imports");
      const read = store.getAll();
      let result: T;
      let failure: unknown;
      read.onsuccess = () => {
        try {
          const all = read.result as BackgroundImport[];
          const now = Date.now();
          // Expiry cleanup and count checks share the write transaction, so
          // another tab cannot race cleanup or bypass the five-file limit.
          for (const record of all) if (record.expiresAt <= now) store.delete(record.id);
          result = work(store, all.filter((r) => r.expiresAt > now));
        } catch (error) { failure = error; tx.abort(); }
      };
      tx.oncomplete = () => resolve(result);
      tx.onerror = tx.onabort = () => reject(failure || new Error("Local storage could not complete the change."));
    });
  } finally { db.close(); }
}

export function importsForRecipient(records: BackgroundImport[], owner: string, recipientId?: string, includeUnassigned = false) {
  return records.filter((r) => r.owner === owner &&
    (r.recipientId === recipientId || (includeUnassigned && !r.recipientId)));
}

export async function listImports(owner: string, recipientId?: string, includeUnassigned = false): Promise<BackgroundImport[]> {
  return updateImports((_store, all) => importsForRecipient(all, owner, recipientId, includeUnassigned).sort((a, b) => b.createdAt - a.createdAt));
}

export async function saveImport(owner: string, input: Omit<BackgroundImport, "id" | "owner" | "createdAt" | "expiresAt" | "status">): Promise<void> {
  if (input.recipientId && !/^demo-parent-[a-f0-9]{32}$/.test(input.recipientId)) {
    throw new Error("Choose a valid demo recipient before saving.");
  }
  if (!input.preview.participants.includes(input.childSender) ||
      !input.preview.participants.includes(input.parentSender) || input.childSender === input.parentSender) {
    throw new Error("Map each participant to a different role.");
  }
  try { new Intl.DateTimeFormat("en", { timeZone: input.timezone }).format(); }
  catch { throw new Error("Enter a valid timezone, such as Asia/Kolkata."); }
  const now = Date.now();
  await updateImports((store, all) => {
    const records = importsForRecipient(all, owner, input.recipientId);
    if (records.length >= 5 && !records.some((r) => r.fingerprint === input.fingerprint)) {
      throw new Error("Keep at most five local imports per recipient. Remove an older file first.");
    }
    const id = `${owner}:${input.recipientId ? `${input.recipientId}:` : ""}${input.fingerprint}`;
    if (all.filter((r) => r.owner === owner).length >= 40 && !all.some((r) => r.id === id)) {
      throw new Error("Keep at most forty local previews for this browser identity.");
    }
    store.put({
      ...input, id, owner,
      createdAt: now, expiresAt: now + RETENTION_MS, status: "local_only",
    } satisfies BackgroundImport);
  });
}

export async function removeImport(owner: string, id: string): Promise<void> {
  if (!id.startsWith(`${owner}:`)) throw new Error("Import does not belong to this identity.");
  await transaction("readwrite", (store) => store.delete(id));
}
