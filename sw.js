/* Waynis AI — service worker (offline shell) */
const CACHE = "waynis-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest",
               "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).catch(()=>{}));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(
    ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  // network-first for API, cache-first for shell
  if (url.pathname.startsWith("/api/") || url.pathname === "/ws") return;
  e.respondWith(
    fetch(e.request)
      .then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)).catch(()=>{}); return r; })
      .catch(() => caches.match(e.request).then(m => m || caches.match("/")))
  );
});
