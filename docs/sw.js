// SPDX-License-Identifier: Apache-2.0

const CACHE_VERSION = "adaad-install-shell-v1";
const CACHE_NAME = `adaad-install-${CACHE_VERSION}`;
const SHELL_ASSETS = Object.freeze([
  "/ADAAD/install.html",
  "/ADAAD/manifest.json",
  "/ADAAD/sw.js",
  "/ADAAD/assets/qr/releases.svg",
  "/ADAAD/assets/qr/obtainium.svg",
  "/ADAAD/assets/qr/pwa.svg",
  "/ADAAD/assets/qr/fdroid.svg",
]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(SHELL_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith("adaad-install-") && key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") {
    return;
  }

  const requestUrl = new URL(event.request.url);
  const isSameOrigin = requestUrl.origin === self.location.origin;

  if (!isSameOrigin) {
    return;
  }

  const pathname = requestUrl.pathname;

  if (!SHELL_ASSETS.includes(pathname)) {
    event.respondWith(
      new Response("Route not available offline.", {
        status: 503,
        statusText: "Service Unavailable",
        headers: { "Content-Type": "text/plain; charset=utf-8" },
      })
    );
    return;
  }

  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(event.request).then((response) => {
        if (!response || response.status !== 200) {
          return response;
        }
        const cloned = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        return response;
      });
    })
  );
});
