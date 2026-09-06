/** IndexedDB helpers for offline Mini App content. */

const DB_NAME = "pomogator-offline";
const DB_VERSION = 2;

type StoreName = "json" | "images" | "fieldQueue";

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onerror = () => reject(request.error ?? new Error("indexedDB open failed"));
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains("json")) db.createObjectStore("json");
      if (!db.objectStoreNames.contains("images")) db.createObjectStore("images");
      if (db.objectStoreNames.contains("checkQueue")) db.deleteObjectStore("checkQueue");
      if (!db.objectStoreNames.contains("fieldQueue")) {
        db.createObjectStore("fieldQueue", { keyPath: "id" });
      }
    };
    request.onsuccess = () => resolve(request.result);
  });
}

async function withStore<T>(
  storeName: StoreName,
  mode: IDBTransactionMode,
  run: (store: IDBObjectStore) => IDBRequest<T> | void,
): Promise<T | undefined> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, mode);
    const store = tx.objectStore(storeName);
    let request: IDBRequest<T> | undefined;
    try {
      const result = run(store);
      request = result || undefined;
    } catch (error) {
      reject(error);
      return;
    }
    tx.oncomplete = () => resolve(request ? request.result : undefined);
    tx.onerror = () => reject(tx.error ?? new Error("indexedDB transaction failed"));
    if (request) {
      request.onerror = () => reject(request?.error ?? new Error("indexedDB request failed"));
    }
  });
}

export async function idbGetJson<T>(key: string): Promise<T | undefined> {
  const value = await withStore<T>("json", "readonly", (store) => store.get(key));
  return value;
}

export async function idbSetJson(key: string, value: unknown): Promise<void> {
  await withStore("json", "readwrite", (store) => {
    store.put(value, key);
  });
}

export async function idbGetImage(digest: string): Promise<Blob | undefined> {
  const value = await withStore<Blob>("images", "readonly", (store) => store.get(digest));
  return value;
}

export async function idbSetImage(digest: string, blob: Blob): Promise<void> {
  await withStore("images", "readwrite", (store) => {
    store.put(blob, digest);
  });
}

export type QueuedField = {
  id: string;
  pageId: string;
  fieldKey: string;
  value: string;
  savedAt: number;
};

export async function idbEnqueueField(entry: QueuedField): Promise<void> {
  await withStore("fieldQueue", "readwrite", (store) => {
    store.put(entry);
  });
}

export async function idbListQueuedFields(): Promise<QueuedField[]> {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction("fieldQueue", "readonly");
    const request = tx.objectStore("fieldQueue").getAll();
    request.onsuccess = () => resolve((request.result as QueuedField[]) ?? []);
    request.onerror = () => reject(request.error ?? new Error("queued fields read failed"));
  });
}

export async function idbRemoveQueuedField(id: string): Promise<void> {
  await withStore("fieldQueue", "readwrite", (store) => {
    store.delete(id);
  });
}
