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
  // API/WS → gjithmonë network (kurrë cache)
  if (url.pathname.startsWith("/api/") || url.pathname === "/ws") return;
  // HTML/manifest → network-first: merr versionin më të ri GJITHMONË
  // (kjo e zgjidh problemin e faqes "të ngrirë" nga cache-i i vjetër)
  e.respondWith(
    fetch(e.request)
      .then(r => {
        if (r.ok) {
          const cp = r.clone();
          caches.open(CACHE).then(c => c.put(e.request, cp)).catch(()=>{});
        }
        return r;
      })
      .catch(() => caches.match(e.request).then(m => m || caches.match("/")))
  );
});
