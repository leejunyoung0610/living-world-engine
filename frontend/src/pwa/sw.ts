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

// SPA — 네비게이션 폴백 (단, /api/*, /health 는 제외)
const handler = new NavigationRoute(
  // index.html를 precache에서 찾아서 응답
  async ({ event }) => {
    const cache = await caches.open("workbox-precache-v2");
    const match = await cache.match("/index.html");
    if (match) return match;
    return fetch((event as FetchEvent).request);
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
