/// <reference lib="webworker" />
import { cleanupOutdatedCaches, precacheAndRoute } from "workbox-precaching";
import { NavigationRoute, registerRoute } from "workbox-routing";
import { StaleWhileRevalidate } from "workbox-strategies";
import { ExpirationPlugin } from "workbox-expiration";

declare const self: ServiceWorkerGlobalScope;

self.addEventListener("message", (event) => {
  if (event.data && event.data.type === "SKIP_WAITING") void self.skipWaiting();
});

cleanupOutdatedCaches();
precacheAndRoute(self.__WB_MANIFEST);

// SPA — 네비게이션: 네트워크 우선(배포 직후 UI 반영), 실패 시 프리캐시 폴백
const handler = new NavigationRoute(
  async ({ event }) => {
    const req = (event as FetchEvent).request;
    try {
      const res = await fetch(req);
      if (res.ok) return res;
    } catch {
      /* offline */
    }
    const cache = await caches.open("workbox-precache-v2");
    const match = await cache.match("/index.html");
    if (match) return match;
    return fetch(req);
  },
  { denylist: [/^\/api\//, /^\/health/] },
);
registerRoute(handler);

// 정적 이미지/폰트만 SWR
registerRoute(
  ({ request }) => request.destination === "image" || request.destination === "font",
  new StaleWhileRevalidate({
    cacheName: "static-assets",
    plugins: [new ExpirationPlugin({ maxEntries: 80, maxAgeSeconds: 60 * 60 * 24 * 30 })],
  }),
);
