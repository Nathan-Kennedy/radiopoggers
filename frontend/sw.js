const CACHE_NAME = "radiopoggers-static-v35";
const STATIC_ASSETS = [
  "./",
  "./index.html",
  "./styles.css",
  "./app.js",
  "./config.js",
  "./vendor/hls.min.js",
  "./ascii-guitarist.js",
  "./assets/ascii-frames.json",
  "./assets/ascii-frames%20sentado.json",
  "./assets/ascii-frames%20off.json",
  "./assets/ascii-frames%20falando.json",
  "./assets/ascii-frames%20miku.json",
  "./assets/ascii-frames%20hoshino.json",
  "./assets/ascii-frames%20hoshino%20falando.json",
  "./assets/ascii-animation%20miku.gif",
  "./assets/ascii-animation%20hoshino.gif",
  "./assets/ascii-animation%20hoshino%20falando.gif",
  "./assets/ascii-animation%20off.gif",
  "./manifest.webmanifest",
  "./assets/icons/icon.svg",
  "./assets/icons/maskable.svg",
  "./assets/img/cover-fallback.svg",
  "./assets/narrator-samples/manifest.json",
  "./assets/narrator-samples/miku/01-track-change.mp3",
  "./assets/narrator-samples/miku/02-mid-track.mp3",
  "./assets/narrator-samples/miku/03-vote-pedido.mp3",
  "./assets/narrator-samples/miku/04-track-night.mp3",
  "./assets/narrator-samples/miku/05-mid-info.mp3",
  "./assets/narrator-samples/hoshino/01-vinheta.mp3",
  "./assets/narrator-samples/hoshino/02-madrugada.mp3",
  "./assets/narrator-samples/hoshino/03-pacote.mp3",
  "./assets/narrator-samples/hoshino/04-risada.mp3",
  "./assets/narrator-samples/hoshino/05-track-change.mp3",
  "./data/demo-nowplaying.json"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET") {
    return;
  }

  if (
    url.pathname.includes("/api/nowplaying")
    || url.pathname.includes("/api/library/preview/")
    || url.pathname.includes("/listen/")
    || url.pathname.includes("/hls/")
  ) {
    event.respondWith(fetch(request));
    return;
  }

  if (url.port === "8765" || url.pathname.startsWith("/api/")) {
    event.respondWith(fetch(request));
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }

      return fetch(request).then((response) => {
        if (!response || response.status !== 200 || response.type === "opaque") {
          return response;
        }

        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      });
    })
  );
});

