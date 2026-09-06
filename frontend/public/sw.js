/* Pomogator Mini App shell cache: network-first, offline fallback. API is not cached here. */
const SHELL = "pomogator-shell-v1";

self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(keys.filter((key) => key !== SHELL).map((key) => caches.delete(key)));
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;

  event.respondWith(
    (async () => {
      try {
        const fresh = await fetch(request);
        if (fresh.ok) {
          const cache = await caches.open(SHELL);
          void cache.put(request, fresh.clone());
        }
        return fresh;
      } catch {
        const cached = await caches.match(request);
        if (cached) return cached;
        if (request.mode === "navigate") {
          const index = await caches.match("/") || (await caches.match("/index.html"));
          if (index) return index;
        }
        throw new Error("offline shell miss");
      }
    })(),
  );
});
