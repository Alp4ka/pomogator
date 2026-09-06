/** Network-first API access with IndexedDB offline fallback. */

import { authHeaders } from "../session";
import {
  idbEnqueueField,
  idbGetImage,
  idbGetJson,
  idbListQueuedFields,
  idbRemoveQueuedField,
  idbSetImage,
  idbSetJson,
  type QueuedField,
} from "./db";

export type Child = { id: string; title: string; locked: boolean };
export type Page = {
  id: string;
  title: string;
  document: import("../document").Block[];
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

export type FetchMeta = { fromCache: boolean };

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function countryKey(slug: string): string {
  return `country:${slug}`;
}

function pageKey(pageId: string): string {
  return `page:${pageId}`;
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

function isOfflineLike(error: unknown): boolean {
  if (error instanceof ApiError) {
    return error.status === 0 || error.status >= 500;
  }
  if (error instanceof TypeError) return true;
  if (error instanceof Error) {
    const message = error.message.toLowerCase();
    return (
      message.includes("failed to fetch") ||
      message.includes("network") ||
      message.includes("offline") ||
      message.includes("load failed")
    );
  }
  return false;
}

export async function getCountry(
  slug: string,
): Promise<{ data: Country; meta: FetchMeta }> {
  const key = countryKey(slug);
  try {
    const data = await networkJson<Country>(`/api/countries/${slug}`);
    await idbSetJson(key, data);
    return { data, meta: { fromCache: false } };
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 402)) throw error;
    const cached = await idbGetJson<Country>(key);
    if (cached) return { data: cached, meta: { fromCache: true } };
    throw error;
  }
}

export async function getPage(pageId: string): Promise<{ data: Page; meta: FetchMeta }> {
  const key = pageKey(pageId);
  try {
    const data = await networkJson<Page>(`/api/pages/${pageId}`);
    await idbSetJson(key, data);
    return { data, meta: { fromCache: false } };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    if (error instanceof ApiError && error.status === 402) throw error;
    const cached = await idbGetJson<Page>(key);
    if (cached) return { data: cached, meta: { fromCache: true } };
    throw error;
  }
}

export async function getImageBlob(digest: string): Promise<{ blob: Blob; meta: FetchMeta }> {
  try {
    const response = await fetch(`/api/images/${digest}`, {
      headers: authHeaders(),
      cache: "no-store",
    });
    if (response.status === 401) throw new ApiError(401, "unauthorized");
    if (!response.ok) throw new ApiError(response.status, `http:${response.status}`);
    const blob = await response.blob();
    await idbSetImage(digest, blob);
    return { blob, meta: { fromCache: false } };
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) throw error;
    const cached = await idbGetImage(digest);
    if (cached) return { blob: cached, meta: { fromCache: true } };
    throw error;
  }
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
  options?: { timeoutMs?: number },
): Promise<SyncStatus> {
  const timeoutMs = options?.timeoutMs ?? 180_000;
  const started = Date.now();
  let last: SyncStatus | undefined;
  while (Date.now() - started < timeoutMs) {
    last = await getCountrySyncStatus(slug);
    if (last.content_version > baselineVersion) return last;
    if (last.status === "failed") return last;
    await sleep(1500);
  }
  throw new ApiError(408, last?.error || "sync timeout");
}

export async function downloadPagePdf(pageId: string, title: string): Promise<void> {
  const response = await fetch(`/api/pages/${pageId}/pdf`, {
    headers: authHeaders(),
    cache: "no-store",
  });
  if (response.status === 401) throw new ApiError(401, "unauthorized");
  if (response.status === 402) throw new ApiError(402, "paid");
  if (!response.ok) throw new ApiError(response.status, `http:${response.status}`);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = `${title.replace(/[\\/:*?"<>|]+/g, "").trim() || "guide"}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

async function patchCachedPageFields(
  pageId: string,
  fieldKey: string,
  value: string,
): Promise<Page | undefined> {
  const key = pageKey(pageId);
  const cached = await idbGetJson<Page>(key);
  if (!cached) return undefined;
  const next: Page = {
    ...cached,
    fields: { ...(cached.fields ?? {}), [fieldKey]: value },
  };
  await idbSetJson(key, next);
  return next;
}

export async function setPageField(
  pageId: string,
  fieldKey: string,
  value: string,
): Promise<{ fields: Record<string, string>; meta: FetchMeta }> {
  try {
    const response = await networkJson<{ fields: Record<string, string> }>(
      `/api/pages/${pageId}/fields/${encodeURIComponent(fieldKey)}`,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value }),
      },
    );
    const cached = await idbGetJson<Page>(pageKey(pageId));
    if (cached) {
      await idbSetJson(pageKey(pageId), { ...cached, fields: response.fields });
    }
    return { fields: response.fields, meta: { fromCache: false } };
  } catch (error) {
    if (error instanceof ApiError && (error.status === 401 || error.status === 402)) throw error;
    if (!isOfflineLike(error) && !(error instanceof ApiError)) throw error;
    const queued: QueuedField = {
      id: `${pageId}:${fieldKey}`,
      pageId,
      fieldKey,
      value,
      savedAt: Date.now(),
    };
    await idbEnqueueField(queued);
    const patched = await patchCachedPageFields(pageId, fieldKey, value);
    return {
      fields: patched?.fields ?? { [fieldKey]: value },
      meta: { fromCache: true },
    };
  }
}

export async function flushFieldQueue(): Promise<void> {
  const queued = await idbListQueuedFields();
  for (const entry of queued) {
    try {
      await networkJson(`/api/pages/${entry.pageId}/fields/${encodeURIComponent(entry.fieldKey)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ value: entry.value }),
      });
      await idbRemoveQueuedField(entry.id);
    } catch {
      // Keep queued until connectivity returns.
      break;
    }
  }
}

/** Warm the offline cache with the reachable (unlocked) page tree + images. */
export async function prefetchCountryTree(rootPageId: string): Promise<void> {
  const queue = [rootPageId];
  const seen = new Set<string>();
  while (queue.length) {
    const pageId = queue.shift()!;
    if (seen.has(pageId)) continue;
    seen.add(pageId);
    try {
      const { data } = await getPage(pageId);
      for (const child of data.children) {
        if (!child.locked) queue.push(child.id);
      }
      const imageIds = data.document.flatMap((block) =>
        block.image_id ? [block.image_id] : [],
      );
      await Promise.all(
        imageIds.map(async (digest) => {
          try {
            await getImageBlob(digest);
          } catch {
            // Ignore individual image failures while warming cache.
          }
        }),
      );
    } catch {
      // Stop branch on hard failures; other branches may still cache.
    }
  }
}

export function registerOfflineShellWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  window.addEventListener("load", () => {
    void navigator.serviceWorker.register("/sw.js").catch(() => undefined);
  });
}
