// TradingAgents Web Service Worker.
// Bump CACHE_NAME on each deployment that ships SW changes.
const CACHE_NAME = "ta-v1";
const PRECACHE = ["/_offline.html", "/manifest.json", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE)),
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))),
    ),
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);

  // 1) API: do not interfere — let the browser hit the network.
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  // 2) Static Next assets and our icons: cache-first, fall back to network and store.
  if (url.pathname.startsWith("/_next/static/") || url.pathname.startsWith("/icons/")) {
    event.respondWith(
      caches.match(req).then(
        (hit) =>
          hit ||
          fetch(req).then((res) => {
            const copy = res.clone();
            if (res.ok) caches.open(CACHE_NAME).then((c) => c.put(req, copy));
            return res;
          }),
      ),
    );
    return;
  }

  // 3) Same-origin HTML navigations: network-first, fall back to cache, finally to /_offline.html.
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          if (res.ok) caches.open(CACHE_NAME).then((c) => c.put(req, copy));
          return res;
        })
        .catch(() =>
          caches.match(req).then((hit) => hit || caches.match("/_offline.html")),
        ),
    );
    return;
  }
});
