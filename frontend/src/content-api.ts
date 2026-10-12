/** Network-only API access for the Mini App. */

import { authHeaders } from "./session";

export type Child = { id: string; title: string; locked: boolean };
export type Page = {
  id: string;
  title: string;
  document: import("./document").Block[];
  fields?: Record<string, string>;
  children: Child[];
};
export type Country = {
  title: string;
  flag: string;
  root_page_id: string | null;
  paid: boolean;
  slug?: string;
  content_version?: number;
  sync_status?: string;
};

export type SyncStatus = {
  slug: string;
  content_version: number;
  status: string;
  error: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  accepted?: boolean;
  queued?: boolean;
};

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function networkJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
    cache: "no-store",
  });
  if (response.status === 401) throw new ApiError(401, "unauthorized");
  if (response.status === 402) throw new ApiError(402, "paid");
  if (!response.ok) throw new ApiError(response.status, `http:${response.status}`);
  return response.json() as Promise<T>;
}

export async function getCountry(slug: string): Promise<Country> {
  return networkJson<Country>(`/api/countries/${slug}`);
}

export async function getPage(pageId: string): Promise<Page> {
  return networkJson<Page>(`/api/pages/${pageId}`);
}

export async function getImageBlob(digest: string): Promise<Blob> {
  const response = await fetch(`/api/images/${digest}`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (response.status === 401) throw new ApiError(401, "unauthorized");
  if (!response.ok) throw new ApiError(response.status, `http:${response.status}`);
  return response.blob();
}

export async function purchaseCountry(slug: string): Promise<void> {
  await networkJson(`/api/countries/${slug}/purchase`, { method: "POST" });
}

export async function requestCountrySync(slug: string): Promise<SyncStatus> {
  return networkJson<SyncStatus>(`/api/countries/${slug}/sync`, { method: "POST" });
}

export async function getCountrySyncStatus(slug: string): Promise<SyncStatus> {
  return networkJson<SyncStatus>(`/api/countries/${slug}/sync`);
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

/** Poll until content_version advances or sync fails / times out. */
export async function waitForCountrySync(
  slug: string,
  baselineVersion: number,
  options?: {
    timeoutMs?: number;
    onTick?: (info: { elapsedMs: number; status: SyncStatus }) => void;
  },
): Promise<SyncStatus> {
  const timeoutMs = options?.timeoutMs ?? 180_000;
  const started = Date.now();
  let last: SyncStatus | undefined;
  while (Date.now() - started < timeoutMs) {
    last = await getCountrySyncStatus(slug);
    options?.onTick?.({ elapsedMs: Date.now() - started, status: last });
    if (last.content_version > baselineVersion) return last;
    if (last.status === "failed") return last;
    await sleep(1500);
  }
  throw new ApiError(408, last?.error || "sync timeout");
}

export async function downloadPagePdf(pageId: string, title: string): Promise<void> {
  const fallbackName = `${title.replace(/[\\/:*?"<>|]+/g, "").trim() || "guide"}.pdf`;
  const link = await networkJson<{ url: string; file_name: string }>(
    `/api/pages/${pageId}/pdf`,
    { method: "POST" },
  );
  const absoluteUrl = new URL(link.url, window.location.origin).href;
  const fileName = link.file_name || fallbackName;
  const tg = window.Telegram?.WebApp;

  if (typeof tg?.downloadFile === "function") {
    await new Promise<void>((resolve, reject) => {
      let settled = false;
      const finish = (action: () => void) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        action();
      };
      const timer = window.setTimeout(() => finish(resolve), 2500);
      try {
        tg.downloadFile!({ url: absoluteUrl, file_name: fileName }, (accepted) => {
          if (accepted === false) {
            finish(() => reject(new ApiError(0, "download denied")));
          } else {
            finish(resolve);
          }
        });
      } catch (error) {
        finish(() =>
          reject(error instanceof Error ? error : new Error("download failed")),
        );
      }
    });
    return;
  }

  if (typeof tg?.openLink === "function") {
    tg.openLink(absoluteUrl, { try_instant_view: false });
    return;
  }

  const response = await fetch(absoluteUrl, { cache: "no-store" });
  if (!response.ok) throw new ApiError(response.status, `http:${response.status}`);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

export async function setPageField(
  pageId: string,
  fieldKey: string,
  value: string,
): Promise<Record<string, string>> {
  const response = await networkJson<{ fields: Record<string, string> }>(
    `/api/pages/${pageId}/fields/${encodeURIComponent(fieldKey)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value }),
    },
  );
  return response.fields;
}

/** Drop leftover service worker / IndexedDB from the removed offline shell. */
export function dropLegacyOffline(): void {
  if ("serviceWorker" in navigator) {
    void navigator.serviceWorker.getRegistrations().then((regs) => {
      for (const reg of regs) void reg.unregister();
    });
  }
  if ("caches" in window) {
    void caches.keys().then((keys) => {
      for (const key of keys) {
        if (key.startsWith("pomogator-")) void caches.delete(key);
      }
    });
  }
  try {
    indexedDB.deleteDatabase("pomogator-offline");
  } catch {
    // ignore
  }
}
