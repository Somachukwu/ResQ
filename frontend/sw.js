/* ResQ Service Worker — Offline First Aid Protocol Caching (S/N 12) */
const CACHE_NAME = "resq-offline-v3";
const CACHE_NAME = "resq-offline-v4";
const CACHE_NAME = "resq-offline-v5";
const OFFLINE_URLS = [
  "/civilian",
  "/static/css/resq.css",
  "/static/css/civilian.css",
  "/static/js/civilian.js",
  "/static/js/resq-protocols.js",
  "/static/js/resq-theme.js",
  "/resources/ResQ_Icon.png",
  "/resources/ResQ_Logo.png",
  "/favicon.ico"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(OFFLINE_URLS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            return caches.delete(key);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  // Only cache GET requests
  if (event.request.method !== "GET") return;

  // Network first with cache fallback for HTML pages
  if (event.request.headers.get("accept")?.includes("text/html")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request).then((res) => res || caches.match("/civilian")))
    );
    return;
  }

  // Cache first with network refresh for static assets
  event.respondWith(
    caches.match(event.request).then((cached) => {
      const networked = fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return response;
        })
        .catch(() => cached);
      return cached || networked;
    })
  );
});

