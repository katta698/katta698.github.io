(function () {
  'use strict';

  var timer;

  function updateYear() {
    var year = String(new Date().getFullYear());
    document.querySelectorAll('[data-current-year]').forEach(function (node) {
      node.textContent = year;
    });
  }

  function scheduleMidnightRefresh() {
    var now = new Date();
    var nextMidnight = new Date(now);
    nextMidnight.setHours(24, 0, 0, 0);
    window.clearTimeout(timer);
    timer = window.setTimeout(function () {
      updateYear();
      scheduleMidnightRefresh();
    }, nextMidnight.getTime() - now.getTime() + 50);
  }

  function ensureStyles() {
    if (document.querySelector('link[data-site-footer-style]')) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/blog/assets/site-footer.css';
    link.setAttribute('data-site-footer-style', '');
    document.head.appendChild(link);
  }

  function initFooter() {
    ensureStyles();
    var footer = document.querySelector('footer');
    if (!footer) {
      footer = document.createElement('footer');
      document.body.appendChild(footer);
    }
    footer.classList.add('site-footer');
    footer.innerHTML = '<p>&copy; <span data-current-year></span> Jayanth Katta &mdash; <a href="https://jayanthkatta.com/">jayanthkatta.com</a></p>';
    updateYear();
    scheduleMidnightRefresh();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initFooter, { once: true });
  } else {
    initFooter();
  }
})();

// Installed-app window title.
//
// Each page's <title> is written for search results and browser tabs
// ("Jayanth Katta — AWS Platform Engineer", "… | Jayanth Katta Blog"), but the
// installed app's title bar should read just "Jayanth Katta". Only the app
// window sees this override: display-mode: standalone matches solely when the
// site runs as an installed PWA, so browser tabs and SEO keep the full titles.
(function () {
  var standalone =
    (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
    window.navigator.standalone === true;
  if (standalone) document.title = 'Jayanth Katta';
})();

// Register the PWA service worker for the whole site.
//
// This file is the only script every page loads — index.html, resume.html and
// now.html include it directly, and blog.js injects it on every blog surface,
// including the Architecture Series pages that sync_blog.py never rebuilds.
// Registering here therefore covers the whole origin with no per-page edits.
//
// Scope is "/" so the installed app owns the entire site: the nav's Home and
// Resume links stay inside the app instead of bouncing the reader out to the
// browser. That requires sw.js to be served from the site root — a worker can
// only claim a scope at or below its own path.
//
// localhost is left enabled: service workers are allowed there without HTTPS,
// which is what makes this testable before it ships.
(function () {
  if (!('serviceWorker' in navigator)) return;

  function register() {
    navigator.serviceWorker.register('/sw.js', { scope: '/' })
      .catch(function () { /* offline support is optional; never block the page */ });
  }

  // Registration is deferred to load so it never competes with the page's own
  // resources — but blog.js injects this file dynamically, often after load has
  // already fired, and a listener added then would never run. Check first.
  if (document.readyState === 'complete') {
    register();
  } else {
    window.addEventListener('load', register, { once: true });
  }
})();
