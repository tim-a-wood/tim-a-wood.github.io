/**
 * Minimal service worker for Neon Drifter Infinite (PWA).
 * Caches index.html and critical assets on install; serves from cache when available.
 */

const CACHE_NAME = 'neon-drifter-v1';

const PRECACHE_URLS = [
  'index.html',
  'https://cdn.jsdelivr.net/npm/phaser@3.60.0/dist/phaser.min.js'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS))
      .then(() => self.skipWaiting())
      .catch(() => {})
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  const isRoot = url.origin === self.location.origin && (url.pathname === '/' || url.pathname === '' || url.pathname.endsWith('/'));
  const isPrecached = PRECACHE_URLS.some((u) => url.href === u) || isRoot;
  if (!isPrecached) {
    return;
  }
  const cacheRequest = isRoot ? 'index.html' : event.request;
  event.respondWith(
    caches.match(cacheRequest).then((cached) => cached || fetch(event.request))
  );
});
