/* Service worker for jayanthkatta.com.
 *
 * GENERATED FILE — do not edit sw.js at the repo root. Edit
 * scripts/sw.template.js and re-run scripts/sync_blog.py, which stamps
 * f612e7fb with the same content hash of blog.css that cache-busts
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

const VERSION = 'f612e7fb';
const JS_VERSION = 'aba9c379';
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
  // The 30px brand mark in the bar. A separate file from the favicon: the
  // bar used to point at favicon-transparent.png, which is 512x512 and
  // 398KB, so every page downloaded and decoded a half-megabyte image to
  // draw a 30-pixel circle.
  '/brand-mark-96.png',
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

// Pages that must never be served stale: their content IS the data.
const LIVE_DATA = ['/intelligence/status/', '/intelligence/whats-new/'];

// A post page: /blog/<slug>/ and nothing deeper or shallower. NOT /blog/
// itself and NOT /blog/page/2/ -- those are the index, the 610KB page this
// cache-first strategy was introduced to make fast, and an index that is one
// visit behind is not wrong, only late.
//
// A post is different on exactly one day: the day it publishes, or the day it
// is corrected. On that day the cached copy is wrong in the same way a stale
// Live status page is wrong, which is why those two are already exempt. The
// cost of getting this wrong was measured rather than imagined: a post
// published on 10 September appeared to lack both floating controls for four
// days, and again on the next publish. The controls were in the deployed HTML
// the entire time. Every reload returned the copy from before they landed, and
// a reload that returns the previous page is indistinguishable from a fix that
// did not work.
//
// site-footer.js does auto-reload on the worker's page-updated message, and
// deliberately does nothing if the reader has scrolled, typed or clicked, or
// after ten seconds. That is right for a reader and wrong for an author
// opening their own post to check it, who scrolls immediately.
const POST_PAGE = /^\/blog\/[^/]+\/$/;

function isImage(pathname) {
  return /\.(png|jpe?g|svg|webp|gif|ico|mp3|mp4|webm|woff2?)$/.test(pathname);
}

// Network-first. Falls back to cache, then to the offline page.
//
// `fresh` asks the browser to revalidate with the server rather than trusting
// its own copy. Without it "network-first" only means "the HTTP cache first":
// GitHub Pages serves these with a max-age, so a live-data page came back in
// 5ms having transferred nothing -- exactly the staleness the exclusion exists
// to prevent, just from a different cache. It is no-cache rather than reload,
// so an unchanged page still costs a 304 and not the whole document.
function networkFirst(request, fresh) {
  return fetch(request, fresh ? { cache: 'no-cache' } : undefined)
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
/* Serve the copy we have, fetch the current one, and SAY SO if it changed.
 *
 * The serving half is what makes moving between pages instant. The saying-so
 * half was missing, and its absence cost an entire evening: every fix shipped
 * invisible until the reader happened to load the page a second time. A fault
 * would be reported, fixed, deployed and verified live from another machine
 * -- and still be there on his phone, because his phone was showing the copy
 * from before the fix with no way to know a newer one existed.
 *
 * His own diagnostic, after a pull-to-refresh, said it plainly:
 *
 *     entered by: reload
 *     served from: cache / offline copy
 *
 * A reload that returns the previous page is indistinguishable from a fix
 * that did not work.
 *
 * So when the revalidated HTML differs from what was served, every open
 * window is told and decides what to do -- see site-footer.js. Bodies are
 * compared rather than headers because GitHub Pages sends no useful ETag
 * here, and a byte comparison cannot be wrong about whether the reader is
 * looking at something out of date.
 */
function staleWhileRevalidate(request) {
  return caches.open(CACHE).then(function (cache) {
    return cache.match(request).then(function (cached) {
      const network = fetch(request)
        .then(function (response) {
          if (response && response.ok) {
            const fresh = response.clone();
            cache.put(request, response.clone());
            if (cached && request.mode === 'navigate') {
              Promise.all([cached.clone().text(), fresh.text()])
                .then(function (both) {
                  if (both[0] === both[1]) return null;
                  return self.clients.matchAll({ type: 'window' });
                })
                .then(function (clients) {
                  (clients || []).forEach(function (c) {
                    c.postMessage({ type: 'page-updated', url: request.url });
                  });
                })
                .catch(function () { /* never break the response */ });
            }
          }
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
    /* Serve the page we already have, then refresh it for next time.
     *
     * Every navigation used to wait for the whole HTML document over the
     * network before painting anything. On a phone that is 150ms of latency
     * plus the transfer -- the blog index is 610KB -- so moving between pages
     * took seconds even though the browser already had the page. Reported as
     * "navigating between pages is not seamless", twice.
     *
     * The cost is honest and worth stating: a returning reader sees the copy
     * from their last visit, and the fresh one arrives a moment later for the
     * visit after that. For writing, that is fine.
     *
     * It is NOT fine for the two pages whose entire claim is that their
     * numbers are current. Live status has incidents rendered into the HTML,
     * and What's New has this week's announcements; serving either from
     * yesterday's cache would make the site quietly wrong in exactly the way
     * the rest of it argues against. Those two keep waiting for the network.
     */
    if (LIVE_DATA.some(function (p) { return url.pathname.indexOf(p) === 0; }) ||
        POST_PAGE.test(url.pathname)) {
      event.respondWith(networkFirst(request, true));
    } else {
      event.respondWith(staleWhileRevalidate(request));
    }
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
