self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  if (event.request.method !== 'GET') return;
  const u = new URL(event.request.url);
  if (u.pathname.startsWith('/api/') || u.pathname === '/vitrine') return;
  event.respondWith(fetch(event.request));
});
