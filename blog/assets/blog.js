/* Blog — nav dark mode + search, filter, back-to-top */

// ── Dark mode ─────────────────────────────────────
(function () {
  var POST_CARD_SELS = ['.card','.callout','.challenge-card','.tip-box','.warning-box','[class*="callout"','[class*="box"]','.container'];

  function applyPostBodyDark(dark) {
    var body = document.querySelector('.post-body');
    if (!body) return;
    var els = body.querySelectorAll('.card,.callout,.challenge-card,.challenge-header,.challenge-body,.tip-box,.warning-box,.stat-box,.meta,.stack-badge,.flow-step,.flow,.flow-content,.section,.toc,.week-badge,.subtitle,.grid-2,.code-block,.code-header,.container');
    els.forEach(function(el) {
      if (dark) {
        el.style.setProperty('background', '#162230', 'important');
        el.style.setProperty('border-color', '#2d3a4a', 'important');
        el.style.setProperty('color', '#e6edf3', 'important');
        el.querySelectorAll('*').forEach(function(child) {
          child.style.setProperty('color', '#e6edf3', 'important');
          if (!child.matches('pre,code')) child.style.setProperty('background', 'transparent', 'important');
        });
      } else {
        el.style.removeProperty('background');
        el.style.removeProperty('border-color');
        el.style.removeProperty('color');
        el.querySelectorAll('*').forEach(function(child) {
          child.style.removeProperty('color');
          child.style.removeProperty('background');
        });
      }
    });
  }

  function applyTheme(dark) {
    document.body.classList.toggle('dark', dark);
    applyPostBodyDark(dark);
    var e = dark ? '☀️' : '🌙', l = dark ? 'Light' : 'Dark';
    ['theme-icon-moon','theme-icon-moon-m'].forEach(function(id) {
      var el = document.getElementById(id); if (el) el.textContent = e;
    });
    ['theme-label-text','theme-label-text-m'].forEach(function(id) {
      var el = document.getElementById(id); if (el) el.textContent = l;
    });
  }
  function toggle() {
    var isDark = document.body.classList.toggle('dark');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    applyTheme(isDark);
  }
  applyTheme(localStorage.getItem('theme') === 'dark');
  ['nav-theme-btn','nav-theme-btn-mobile'].forEach(function(id) {
    var btn = document.getElementById(id);
    if (btn) btn.addEventListener('click', function() {
      toggle();
      // Close hamburger menu after theme toggle on mobile
      if (id === 'nav-theme-btn-mobile') {
        var menu = document.getElementById('mobile-menu');
        var ham  = document.getElementById('hamburger-btn');
        if (menu) menu.classList.remove('open');
        if (ham)  ham.classList.remove('open');
      }
    });
  });
})();

// ── Hamburger menu ────────────────────────────────
(function () {
  var btn  = document.getElementById('hamburger-btn');
  var menu = document.getElementById('mobile-menu');
  if (!btn || !menu) return;
  btn.addEventListener('click', function () {
    var open = menu.classList.toggle('open');
    btn.classList.toggle('open', open);
  });
})();

// ── Search icon ───────────────────────────────────
(function () {
  var btn  = document.getElementById('nav-search-btn');
  var wrap = document.getElementById('search-bar-wrap');
  var inp  = document.getElementById('blog-search');
  var isPostPage = !wrap;

  if (!btn) return;

  btn.addEventListener('click', function () {
    if (wrap) {
      var isOpen = wrap.classList.toggle('open');
      if (isOpen && inp) setTimeout(function () { inp.focus(); }, 50);
    } else {
      // On post pages: show inline search bar in nav area
      var postSearch = document.getElementById('post-search-bar');
      if (postSearch) {
        postSearch.classList.toggle('open');
        var pi = document.getElementById('post-search-input');
        if (pi) setTimeout(function () { pi.focus(); }, 50);
      }
    }
  });

  // On blog index: pre-fill search from ?q= param
  var params = new URLSearchParams(window.location.search);
  var q = params.get('q');
  if (q && inp && wrap) {
    wrap.classList.add('open');
    inp.value = q;
    inp.dispatchEvent(new Event('input'));
  }

  // Close on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      if (wrap && wrap.classList.contains('open')) {
        wrap.classList.remove('open');
        if (inp) inp.value = '';
      }
      var postSearch = document.getElementById('post-search-bar');
      if (postSearch && postSearch.classList.contains('open')) {
        postSearch.classList.remove('open');
      }
    }
  });
})();

// ── Post-page inline search ───────────────────────
(function () {
  var pi = document.getElementById('post-search-input');
  if (!pi) return;
  pi.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && pi.value.trim()) {
      window.location.href = '/blog/?q=' + encodeURIComponent(pi.value.trim());
    }
  });
})();

(function () {
  const cards = Array.from(document.querySelectorAll('.post-card'));
  const pills = Array.from(document.querySelectorAll('.filter-pill'));
  const sbTags = Array.from(document.querySelectorAll('.sb-tag'));
  const searchInput = document.getElementById('blog-search');
  const countEl = document.getElementById('results-count');
  const grid = document.getElementById('posts-grid');
  const emptyEl = document.getElementById('empty-state');

  let activeTag = 'all';
  let searchTerm = '';

  function normalize(s) {
    return s.toLowerCase().trim();
  }

  function matchSearch(card, term) {
    if (!term) return true;
    const haystack = [
      card.dataset.title || '',
      card.dataset.excerpt || '',
      card.dataset.tags || '',
    ].join(' ').toLowerCase();
    return term.split(/\s+/).every(w => haystack.includes(w));
  }

  function applyFilters() {
    let visible = 0;
    cards.forEach(card => {
      const tags = (card.dataset.tags || '').toLowerCase();
      const tagMatch = activeTag === 'all' || tags.includes(activeTag.toLowerCase());
      const searchMatch = matchSearch(card, normalize(searchTerm));
      const show = tagMatch && searchMatch;
      card.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    if (countEl) {
      countEl.textContent = visible === cards.length
        ? `${visible} posts`
        : `${visible} of ${cards.length} posts`;
    }
    if (emptyEl) emptyEl.style.display = visible === 0 ? '' : 'none';
  }

  function setTag(tag) {
    activeTag = tag;
    pills.forEach(p => p.classList.toggle('active', p.dataset.tag === tag));
    sbTags.forEach(t => t.classList.toggle('active', t.dataset.tag === tag));
    applyFilters();
  }

  pills.forEach(p => p.addEventListener('click', () => setTag(p.dataset.tag)));
  sbTags.forEach(t => t.addEventListener('click', () => setTag(t.dataset.tag)));

  if (searchInput) {
    searchInput.addEventListener('input', e => {
      searchTerm = e.target.value;
      applyFilters();
    });
  }

  applyFilters();
})();

// ── Back to top ───────────────────────────────────
(function () {
  var btn = document.getElementById('back-top');
  if (!btn) return;
  function checkScroll() {
    var scrolled = window.scrollY || document.documentElement.scrollTop || document.body.scrollTop;
    btn.classList.toggle('show', scrolled > 400);
  }
  window.addEventListener('scroll', checkScroll, { passive: true });
  document.addEventListener('scroll', checkScroll, { passive: true });
  btn.addEventListener('click', function () {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  });
})();
