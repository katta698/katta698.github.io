/* Service worker for jayanthkatta.com.
 *
 * GENERATED FILE — do not edit sw.js at the repo root. Edit
 * scripts/sw.template.js and re-run scripts/sync_blog.py, which stamps
 * 3172392d with the same content hash of blog.css that cache-busts
 * the stylesheet. A CSS change therefore invalidates the whole cache
 * automatically; there is no version constant anyone has to remember to bump.
 *
 * Scope is the whole site ("/"), which is why this file must be served from
 * the repo root — a worker can only claim a scope at or below its own path.
 * Site-wide scope is deliberate: the nav links Home, Blog and Resume, so a
 * /blog/-scoped app would eject the reader to the browser on the second link.
 *
 * Caching strategy, by request type:
 *   navigations  network-first  a live fix to any page takes effect on the
 *                               next load, exactly as it does without a SW
 *   css / js     stale-while-revalidate
 *   images/svg   cache-first, refreshed in the background
 *   everything   network-first (posts.json, stats.json, rss.xml — freshness
 *   else                        matters more than offline)
 *   cross-origin passthrough    fonts, cdnjs, Disqus, the search API
 *
 * CSS and JS are stale-while-revalidate rather than cache-first on purpose.
 * The Architecture Series pages carry a ?v= token that is stamped when the
 * page is built and does not track later blog.css changes, so a cache-first
 * rule could pin a stale stylesheet on those pages. SWR always refetches in
 * the background, bounding staleness to one page load regardless of the token.
 */

const VERSION = '3172392d';
const JS_VERSION = '1005d142';
const CACHE = 'jk-site-' + VERSION;
const OFFLINE_URL = '/offline.html';

const PRECACHE = [
  '/',
  '/blog/',
  '/resume.html',
  '/now.html',
  OFFLINE_URL,
  '/blog/assets/blog.css?v=' + VERSION,
  '/blog/assets/blog.js?v=' + JS_VERSION,
  '/blog/assets/site-footer.js?v=' + JS_VERSION,
  '/blog/assets/site-footer.css?v=' + JS_VERSION,
  '/blog/assets/icons/icon-192.png',
  '/favicon-transparent.png'
];

// Never intercepted, even though they are same-origin.
const EXCLUDED = ['/admin/', '/_archive/', '/_templates/'];

self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE)
      .then(function (cache) {
        // addAll is atomic: one 404 rejects the whole install. Precache is
        // best-effort so a renamed asset cannot wedge the worker.
        return Promise.all(PRECACHE.map(function (url) {
          return cache.add(url).catch(function () { return null; });
        }));
      })
      .then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(keys.map(function (key) {
          // jk-blog-* is the retired /blog/-scoped cache from the first cut.
          if (key !== CACHE && /^jk-(site|blog)-/.test(key)) {
            return caches.delete(key);
          }
          return null;
        }));
      })
      .then(function () { return self.clients.claim(); })
  );
});

function isAsset(pathname) {
  return /\.(css|js)$/.test(pathname);
}

function isImage(pathname) {
  return /\.(png|jpe?g|svg|webp|gif|ico|mp3|mp4|webm|woff2?)$/.test(pathname);
}

// Network-first. Falls back to cache, then to the offline page.
function networkFirst(request) {
  return fetch(request)
    .then(function (response) {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then(function (c) { c.put(request, copy); });
      }
      return response;
    })
    .catch(function () {
      return caches.match(request).then(function (cached) {
        if (cached) return cached;
        // Only a navigation should ever see the offline page; a failed asset
        // must reject so the browser reports it normally.
        if (request.mode === 'navigate') return caches.match(OFFLINE_URL);
        return Promise.reject(new Error('offline'));
      });
    });
}

// Serve cache immediately, refresh in the background.
function staleWhileRevalidate(request) {
  return caches.open(CACHE).then(function (cache) {
    return cache.match(request).then(function (cached) {
      const network = fetch(request)
        .then(function (response) {
          if (response && response.ok) cache.put(request, response.clone());
          return response;
        })
        .catch(function () { return cached; });
      return cached || network;
    });
  });
}

// Serve cache if present, otherwise fetch and store.
function cacheFirst(request) {
  return caches.match(request).then(function (cached) {
    if (cached) return cached;
    return fetch(request).then(function (response) {
      if (response && response.ok) {
        const copy = response.clone();
        caches.open(CACHE).then(function (c) { c.put(request, copy); });
      }
      return response;
    });
  });
}

self.addEventListener('fetch', function (event) {
  const request = event.request;

  if (request.method !== 'GET') return;

  const url = new URL(request.url);

  // Cross-origin (fonts, cdnjs, Disqus, the search API) falls through to the
  // network untouched.
  if (url.origin !== self.location.origin) return;

  for (let i = 0; i < EXCLUDED.length; i++) {
    if (url.pathname.indexOf(EXCLUDED[i]) === 0) return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }
  if (isAsset(url.pathname)) {
    event.respondWith(staleWhileRevalidate(request));
    return;
  }
  if (isImage(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }
  event.respondWith(networkFirst(request));
});
