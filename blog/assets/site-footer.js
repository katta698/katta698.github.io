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
