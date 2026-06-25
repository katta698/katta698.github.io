/* Blog — nav dark mode + search, filter, back-to-top */

// ── Hero typer (homepage only) ─────────────────────
(function () {
  var el = document.getElementById('hero-typer-text');
  if (!el) return;
  var lines = ['deploying ideas...', 'terraform apply --auto-approve', 'still debugging life, one day at a time'];
  var li = 0, ci = 0;
  function type() {
    var line = lines[li];
    if (ci <= line.length) {
      el.textContent = line.slice(0, ci);
      ci++;
      setTimeout(type, 70);
    } else {
      setTimeout(erase, 1600);
    }
  }
  function erase() {
    var line = lines[li];
    if (ci > 0) {
      ci--;
      el.textContent = line.slice(0, ci);
      setTimeout(erase, 30);
    } else {
      li = (li + 1) % lines.length;
      setTimeout(type, 400);
    }
  }
  type();
})();

// ── Dark mode ─────────────────────────────────────
(function () {
  var POST_CARD_SELS = ['.card','.callout','.challenge-card','.tip-box','.warning-box','[class*="callout"','[class*="box"]','.container'];

  function applyPostBodyDark(dark) {
    var jkPost = document.getElementById('jk-post');
    if (!jkPost) return;
    if (dark) {
      jkPost.style.setProperty('background', 'transparent', 'important');
      jkPost.style.setProperty('color', '#e6edf3', 'important');
      jkPost.querySelectorAll('*').forEach(function(el) {
        if (!el.matches('pre,code,img,svg,span.val')) {
          el.style.setProperty('background', 'transparent', 'important');
          el.style.setProperty('color', '#e6edf3', 'important');
          el.style.setProperty('border-color', '#2d3a4a', 'important');
        }
      });
      // Keep links orange
      jkPost.querySelectorAll('a').forEach(function(a) {
        a.style.setProperty('color', '#FF9900', 'important');
      });
    } else {
      jkPost.style.removeProperty('background');
      jkPost.style.removeProperty('color');
      jkPost.querySelectorAll('*').forEach(function(el) {
        el.style.removeProperty('background');
        el.style.removeProperty('color');
        el.style.removeProperty('border-color');
      });
    }
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

// ── Mobile grid-2 stack ───────────────────────────
(function () {
  if (window.innerWidth > 640) return;
  var grids = document.querySelectorAll('#jk-post .grid-2, #jk-post .before-after');
  grids.forEach(function(el) {
    el.style.setProperty('grid-template-columns', '1fr', 'important');
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

  // Pre-select tag filter from ?tag= param (set by portfolio teaser links)
  var urlParams = new URLSearchParams(window.location.search);
  var tagParam = urlParams.get('tag');
  if (tagParam) {
    setTag(tagParam.toLowerCase());
  } else {
    applyFilters();
  }
})();

// ── Screenshot / diagram lightbox ───────────────────
(function () {
  var jkPost = document.getElementById('jk-post');
  if (!jkPost) return;
  var imgs = Array.prototype.slice.call(jkPost.querySelectorAll('img'));
  // Top-level inline SVG diagrams (architecture/flow diagrams authored
  // directly in a post). Excludes any SVG nested inside one we've already
  // wrapped, so re-running this logic never double-wraps.
  var svgs = Array.prototype.slice.call(jkPost.querySelectorAll('svg')).filter(function (svg) {
    return !svg.closest('.zoomable-img');
  });
  if (!imgs.length && !svgs.length) return;

  var overlay = document.createElement('div');
  overlay.className = 'lightbox-overlay';
  overlay.innerHTML =
    '<button class="lightbox-x" aria-label="Close">&times;</button>' +
    '<img class="lightbox-img" alt=""/>' +
    '<div class="lightbox-svg"></div>' +
    '<button class="lightbox-close" aria-label="Close">Close</button>';
  document.body.appendChild(overlay);
  var lbImg = overlay.querySelector('.lightbox-img');
  var lbSvg = overlay.querySelector('.lightbox-svg');

  // Blogger serves a resized thumbnail in <img src> (e.g. "/s600/" or
  // "=w640-h156") — fine for the inline post, but blurry once stretched
  // to fill the lightbox. Swap in Blogger's "s0" marker (original,
  // unscaled size) so the zoomed view is actually sharp.
  function fullResSrc(src) {
    if (!src || src.indexOf('googleusercontent.com') === -1) return src;
    return src.replace(/\/s\d+\//, '/s0/').replace(/=([a-zA-Z])\d+(-[a-zA-Z]\d+)?$/, '=s0');
  }

  function openImg(src, alt) {
    lbSvg.style.display = 'none';
    lbSvg.innerHTML = '';
    lbImg.style.display = '';
    lbImg.src = fullResSrc(src);
    lbImg.alt = alt || '';
    overlay.classList.add('open');
  }
  function openSvg(svg) {
    lbImg.style.display = 'none';
    lbImg.src = '';
    lbSvg.style.display = '';
    lbSvg.innerHTML = '';
    var clone = svg.cloneNode(true);
    clone.removeAttribute('width');
    clone.removeAttribute('height');
    clone.style.width = 'min(900px, 90vw)';
    clone.style.height = 'auto';
    lbSvg.appendChild(clone);
    overlay.classList.add('open');
  }
  function close() {
    overlay.classList.remove('open');
    lbImg.src = '';
    lbSvg.innerHTML = '';
  }

  function addTrigger(el, onClick) {
    var wrap = document.createElement('span');
    wrap.className = 'zoomable-img';
    el.parentNode.insertBefore(wrap, el);
    wrap.appendChild(el);
    var btn = document.createElement('button');
    btn.className = 'zoom-trigger';
    btn.setAttribute('aria-label', 'Zoom image');
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 4H5a1 1 0 0 0-1 1v4"/><path d="M15 4h4a1 1 0 0 1 1 1v4"/><path d="M4 15v4a1 1 0 0 0 1 1h4"/><path d="M20 15v4a1 1 0 0 1-1 1h-4"/></svg>';
    wrap.appendChild(btn);
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      onClick();
    });
  }

  imgs.forEach(function (img) {
    addTrigger(img, function () { openImg(img.currentSrc || img.src, img.alt); });
  });
  svgs.forEach(function (svg) {
    addTrigger(svg, function () { openSvg(svg); });
  });

  overlay.querySelector('.lightbox-x').addEventListener('click', close);
  overlay.querySelector('.lightbox-close').addEventListener('click', close);
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) close();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && overlay.classList.contains('open')) close();
  });
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
