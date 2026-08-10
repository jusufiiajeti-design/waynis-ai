/* Waynis AI — service worker v2 (network-first for pages) */
const CACHE = "waynis-v2";

self.addEventListener("install", e => {
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(
    ks.filter(k => k !== CACHE).map(k => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  // network-first: merr versionin më të ri GJITHMONË, cache vetëm si rezervë
  if (url.pathname.startsWith("/api/") || url.pathname === "/ws") return;
  e.respondWith(
    fetch(e.request)
      .then(r => { const cp = r.clone(); caches.open(CACHE).then(c => c.put(e.request, cp)).catch(()=>{}); return r; })
      .catch(() => caches.match(e.request).then(m => m || caches.match("/")))
  );
});
