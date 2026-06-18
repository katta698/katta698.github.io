/* Blog — nav dark mode + search, filter, back-to-top */

// ── Dark mode ─────────────────────────────────────
(function () {
  var themeBtn = document.getElementById('nav-theme-btn');
  var icon  = document.getElementById('theme-icon-moon');
  var label = document.getElementById('theme-label-text');
  function applyTheme(dark) {
    document.body.classList.toggle('dark', dark);
    if (icon)  icon.textContent  = dark ? '☀️' : '🌙';
    if (label) label.textContent = dark ? 'Light' : 'Dark';
  }
  applyTheme(localStorage.getItem('theme') === 'dark');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var isDark = document.body.classList.toggle('dark');
      localStorage.setItem('theme', isDark ? 'dark' : 'light');
      if (icon)  icon.textContent  = isDark ? '☀️' : '🌙';
      if (label) label.textContent = isDark ? 'Light' : 'Dark';
    });
  }
})();

// ── Search icon ───────────────────────────────────
(function () {
  var btn  = document.getElementById('nav-search-btn');
  var wrap = document.getElementById('search-bar-wrap');
  var inp  = document.getElementById('blog-search');
  if (!btn) return;
  btn.addEventListener('click', function () {
    if (wrap) {
      var isOpen = wrap.classList.toggle('open');
      if (isOpen && inp) setTimeout(function () { inp.focus(); }, 220);
    } else {
      window.location.href = '/blog/#search';
    }
  });
  // Close on Escape
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && wrap && wrap.classList.contains('open')) {
      wrap.classList.remove('open');
      if (inp) inp.value = '';
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

  // Back to top
  const btn = document.getElementById('back-top');
  if (btn) {
    window.addEventListener('scroll', () => {
      btn.classList.toggle('show', window.scrollY > 400);
    }, { passive: true });
    btn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));
  }

  applyFilters();
})();
