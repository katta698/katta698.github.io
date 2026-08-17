/* Blog — nav dark mode + search, filter, back-to-top */

// ── Weekly palette rotation ────────────────────────
// Seven boho neutrals, one per weekday, repeating each week. Light mode only:
// the dark palette already sits close to its floor and there is no room to move
// it seven ways, so a reader in dark mode sees no rotation at all.
//
// This sets an attribute and nothing else -- every colour lives in blog.css,
// keyed on [data-palette] and guarded by body:not(.dark). Doing it in CSS keeps
// the values in one place and means a failure here leaves the default palette
// standing rather than an unstyled page.
//
// Runs first in this file on purpose. blog.js loads after </head>, so this is
// post-paint and can flash -- but the seven palettes are within ~10 RGB points
// of each other, where the existing light/dark flash spans the whole page.
// Overridable for testing: ?palette=wed, or localStorage.paletteDay.
(function () {
  var DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  var pick;
  try {
    pick = new URLSearchParams(location.search).get('palette') ||
           localStorage.getItem('paletteDay');
  } catch (e) { pick = null; }
  if (DAYS.indexOf(pick) === -1) pick = DAYS[new Date().getDay()];
  document.documentElement.setAttribute('data-palette', pick);
})();

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
        if (el.closest('.zoom-trigger')) return;
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

  // ── Disqus theme ────────────────────────────────────
  // Disqus is a third-party iframe that picks its own theme by sampling the
  // background behind #disqus_thread, once, when it loads. The embed passes no
  // colorScheme and the toggle never told it anything, so loading in dark and
  // switching to light left white Disqus text on a bone page -- invisible, and
  // invisible to every contrast check we run, because none of them can see
  // inside someone else's iframe.
  //
  // The identifier is read back out of the page's own disqus_config rather than
  // rebuilt. Resetting with a different identifier would point at a DIFFERENT
  // THREAD and appear to lose every existing comment, so it is worth the extra
  // few lines to carry the original through untouched.
  function syncDisqusTheme(dark) {
    if (!window.DISQUS || typeof window.DISQUS.reset !== 'function') return;
    var page = {};
    try {
      if (typeof window.disqus_config === 'function') {
        window.disqus_config.call({ page: page, callbacks: {} });
      }
    } catch (e) { return; }          // never let a reset break the page
    try {
      window.DISQUS.reset({
        reload: true,
        config: function () {
          if (page.url) this.page.url = page.url;
          if (page.identifier) this.page.identifier = page.identifier;
          this.page.colorScheme = dark ? 'dark' : 'light';
        }
      });
    } catch (e) {}
  }

  function applyTheme(dark) {
    document.body.classList.toggle('dark', dark);
    applyPostBodyDark(dark);
    syncDisqusTheme(dark);
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

  // On blog index: pre-fill the search box from ?q=, set by the inline search
  // on post pages. Cosmetic only -- the filtering itself happens further down,
  // once the input listener exists.
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
  // The server now renders only the current page of cards, so this starts as a
  // slice and is topped up from blog/cards.json after first paint. Everything
  // downstream -- filters, search, year pills, sort -- reads this array, so it
  // must end up holding every post or a filter would silently only search the
  // page on screen.
  let cards = Array.from(document.querySelectorAll('.post-card'));
  const pills = Array.from(document.querySelectorAll('.filter-pill'));
  const sbTags = Array.from(document.querySelectorAll('.sb-tag'));
  const searchInput = document.getElementById('blog-search');
  const countEl = document.getElementById('results-count');
  const grid = document.getElementById('posts-grid');
  const emptyEl = document.getElementById('empty-state');

  var MONTH_NAMES = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

  // Slugs the server rendered onto this page, captured before hydration adds
  // the rest. Used to restore the paged view when filters are cleared.
  const serverSlugs = cards.map(c => c.dataset.slug || '');
  let hydrated = false;
  let totalPosts = cards.length;

  // Card markup, kept deliberately in step with the f-string in
  // build_index_page() in sync_blog.py. Two renderers is a real cost, but the
  // alternative -- shipping rendered HTML for every post in cards.json -- puts
  // the page weight straight back, since the two inline SVGs are most of a
  // card's bytes and are identical in all of them.
  const CLOCK_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  const CHEV_SVG = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>';

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function renderCard(c) {
    const a = document.createElement('a');
    a.href = '/blog/' + c.slug + '/';
    a.className = 'post-card' + (c.cloud ? ' ' + c.cloud : '');
    a.dataset.slug = c.slug;
    a.dataset.title = c.title;
    a.dataset.excerpt = c.excerpt;
    a.dataset.tags = c.tags;
    a.dataset.date = c.date;
    a.dataset.services = '|' + (c.services || '') + '|';
    a.dataset.topics = '|' + (c.topics || '') + '|';
    a.innerHTML =
      '<div class="post-card-body">' +
      '<div class="post-meta"><span class="tag-badge">' + esc(c.tag1) + '</span>' +
      '<span class="post-date">' + esc(c.date_fmt) + '</span></div>' +
      '<div class="post-title">' + esc(c.title) + '</div>' +
      '<div class="post-excerpt">' + esc(c.excerpt) + '</div>' +
      '<div class="post-footer">' +
      '<span class="read-time">' + CLOCK_SVG + ' ' + c.read_time + ' min read</span>' +
      '<span class="read-more">Read ' + CHEV_SVG + '</span>' +
      '</div></div>';
    return a;
  }

  // Only this page's cards are in the HTML, so a filter would otherwise search
  // 24 posts and quietly report that as the whole archive. Fetched after first
  // paint: landing on /blog/ and reading the newest posts costs nothing extra.
  function hydrate() {
    if (hydrated) return Promise.resolve();
    return fetch('/blog/cards.json')
      .then(r => (r.ok ? r.json() : Promise.reject(new Error('HTTP ' + r.status))))
      .then(data => {
        const have = new Set(serverSlugs);
        const frag = document.createDocumentFragment();
        data.forEach(c => { if (!have.has(c.slug)) frag.appendChild(renderCard(c)); });
        if (emptyEl) grid.insertBefore(frag, emptyEl);
        else grid.appendChild(frag);
        cards = Array.from(grid.querySelectorAll('.post-card'));
        totalPosts = cards.length;
        hydrated = true;
        applyFilters();
      })
      .catch(() => {
        // Leave the server-rendered page exactly as it is. Filtering then only
        // covers this page, which is worse than the whole archive but better
        // than an empty grid, and paging still works because it is plain links.
        hydrated = false;
      });
  }

  let activeTag = 'all';
  let activeYear = 'all';
  let activeMonth = 'all';
  let activeService = 'all';
  let activeTopic = 'all';
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
      card.dataset.date || '',
    ].join(' ').toLowerCase();
    return term.split(/\s+/).every(w => haystack.includes(w));
  }

  // With no filter active the reader is browsing, and should see this page's
  // slice with the pagination nav. The moment anything is filtered the query
  // runs across every post, so paging by 24 would be meaningless -- the nav is
  // hidden and every match is shown.
  function filtersActive() {
    // Sorting oldest-first counts as a filter for this purpose. The paged view
    // shows the newest 24; re-ordering those and calling it "Oldest" showed the
    // oldest post *on page 1* -- 4 August -- while the archive goes back to
    // 2023. Any non-default view drops pagination and shows the whole set.
    return activeTag !== 'all' || activeYear !== 'all' || activeMonth !== 'all' ||
           activeService !== 'all' || activeTopic !== 'all' || !!searchTerm ||
           sortAsc === true;
  }

  function applyFilters() {
    const pager = document.getElementById('pagination');
    const browsing = !filtersActive();
    if (pager) pager.style.display = browsing ? '' : 'none';
    // Cards the server put on this page; the rest arrive via cards.json.
    const onThisPage = new Set(serverSlugs);
    let visible = 0;
    cards.forEach(card => {
      if (browsing && hydrated && !onThisPage.has(card.dataset.slug)) {
        card.style.display = 'none';
        return;
      }
      const tags = (card.dataset.tags || '').toLowerCase();
      const d = card.dataset.date || '';
      const tagMatch = activeTag === 'all' || tags.includes(activeTag.toLowerCase());
      // Delimited on both sides so "s3" cannot match inside "s3 express".
      const svcMatch = activeService === 'all' ||
        (card.dataset.services || '').includes('|' + activeService + '|');
      // Same delimited test for homepage topics. The badge count and this
      // filter read the same attribute, so they cannot drift apart -- they
      // used to be a title+tags count linking to a full-text search, and 17
      // of 36 topics disagreed.
      const topicMatch = activeTopic === 'all' ||
        (card.dataset.topics || '').includes('|' + activeTopic + '|');
      const yearMatch = activeYear === 'all' || d.startsWith(activeYear);
      const monthMatch = activeMonth === 'all' || d.slice(5, 7) === activeMonth;
      const searchMatch = matchSearch(card, normalize(searchTerm));
      const show = tagMatch && svcMatch && topicMatch && yearMatch && monthMatch && searchMatch;
      card.style.display = show ? '' : 'none';
      if (show) visible++;
    });
    if (countEl) {
      const total = hydrated ? cards.length : totalPosts;
      countEl.textContent = (browsing || visible === total)
        ? `${total} posts`
        : `${visible} of ${total} posts`;
    }
    if (emptyEl) emptyEl.style.display = visible === 0 ? '' : 'none';
  }

  // Clicking a service in the sidebar answers "what have you written about
  // this?" without leaving the page.
  //
  // Clicking the same one twice used to toggle the filter off, so the post
  // list flipped between six posts and all ninety-four and looked like it was
  // changing at random. Selecting is now idempotent -- clicking S3 five times
  // shows the S3 posts five times -- and clearing is its own visible control.
  function setService(svc) {
    activeService = svc;
    document.querySelectorAll('.svc-row').forEach(function (row) {
      const btn = row.querySelector('.svc-name');
      row.classList.toggle('active',
        !!btn && btn.dataset.service === activeService);
    });
    const note = document.getElementById('svc-filter-note');
    if (note) {
      note.style.display = activeService === 'all' ? 'none' : '';
      if (activeService !== 'all') {
        note.textContent = '';
        const label = document.createElement('span');
        const btn = document.querySelector(
          '.svc-name[data-service="' + activeService.replace(/"/g, '') + '"]');
        label.textContent = 'Showing posts mentioning ' +
          (btn ? btn.textContent : activeService) + ' ';
        const clear = document.createElement('button');
        clear.type = 'button';
        clear.className = 'svc-clear';
        clear.textContent = 'Clear';
        clear.addEventListener('click', function () { setService('all'); });
        note.appendChild(label);
        note.appendChild(clear);
      }
    }
    applyFilters();
    // Deliberately does not scroll. It used to jump to the top of the grid,
    // which moved the sidebar out from under the pointer -- so the obvious
    // next click landed on the same service again and cleared the filter,
    // making it look like it took two clicks to work. The results count
    // updates in place and the grid is already alongside the list.
  }

  document.querySelectorAll('.svc-name').forEach(function (btn) {
    btn.addEventListener('click', function () {
      setService(btn.dataset.service);
    });
  });

  // Three ways out, because one control the reader has to find is not a way
  // out: the Clear link in the note, Escape, and the "All" pill that already
  // reads as "show me everything" and previously left a service filter on --
  // which looked like the pill was broken.
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && activeService !== 'all') setService('all');
  });

  function setTag(tag) {
    // "All" means all. Leaving a service filter applied under it is how a
    // reader concludes the pill does nothing.
    if (tag === 'all' && activeService !== 'all') {
      setService('all');
    }
    activeTag = tag;
    pills.forEach(p => p.classList.toggle('active', p.dataset.tag === tag));
    sbTags.forEach(t => t.classList.toggle('active', t.dataset.tag === tag));
    applyFilters();
  }

  function setYear(year) {
    activeYear = year;
    activeMonth = 'all';
    yearPills.forEach(p => p.classList.toggle('active', p.dataset.year === year));
    rebuildMonthRow();
    applyFilters();
  }

  function setMonth(month) {
    activeMonth = month;
    monthPills.forEach(p => p.classList.toggle('active', p.dataset.month === month));
    applyFilters();
  }

  // Month row — rebuilt whenever year changes
  var monthRow = document.createElement('div');
  monthRow.className = 'filters month-filters';
  monthRow.style.display = 'none';
  var monthPills = [];

  function rebuildMonthRow() {
    monthRow.innerHTML = '';
    monthPills = [];
    if (activeYear === 'all') { monthRow.style.display = 'none'; return; }
    var months = [];
    var seenM = {};
    cards.forEach(function(c) {
      var d = c.dataset.date || '';
      if (!d.startsWith(activeYear)) return;
      var m = d.slice(5, 7);
      if (m && !seenM[m]) { seenM[m] = true; months.push(m); }
    });
    months.sort();
    if (months.length < 2) { monthRow.style.display = 'none'; return; }
    var allM = document.createElement('button');
    allM.className = 'filter-pill active';
    allM.dataset.month = 'all';
    allM.textContent = 'All months';
    monthRow.appendChild(allM);
    months.forEach(function(m) {
      var btn = document.createElement('button');
      btn.className = 'filter-pill';
      btn.dataset.month = m;
      btn.textContent = MONTH_NAMES[parseInt(m, 10) - 1];
      monthRow.appendChild(btn);
    });
    monthPills = Array.from(monthRow.querySelectorAll('.filter-pill'));
    monthPills.forEach(function(p) { p.addEventListener('click', function() { setMonth(p.dataset.month); }); });
    monthRow.style.display = '';
  }

  // Year pills come from the server, not from the cards on screen: this runs
  // before cards.json arrives, so scanning the DOM would offer only the years
  // this page's 24 posts happen to cover. Falls back to the DOM scan for any
  // page built before that attribute existed.
  var years = ((grid && grid.dataset.years) || '').split(',').filter(Boolean);
  if (!years.length) {
    var seenYears = {};
    cards.forEach(function(c) {
      var y = (c.dataset.date || '').slice(0, 4);
      if (y && !seenYears[y]) { seenYears[y] = true; years.push(y); }
    });
  }
  years.sort(function(a, b) { return b - a; });

  var yearRow = document.createElement('div');
  yearRow.className = 'filters year-filters';
  var allYearBtn = document.createElement('button');
  allYearBtn.className = 'filter-pill active';
  allYearBtn.dataset.year = 'all';
  allYearBtn.textContent = 'All years';
  yearRow.appendChild(allYearBtn);
  years.forEach(function(yr) {
    var btn = document.createElement('button');
    btn.className = 'filter-pill';
    btn.dataset.year = yr;
    btn.textContent = yr;
    yearRow.appendChild(btn);
  });
  var filtersEl = document.querySelector('.filters');
  if (filtersEl && years.length > 1) {
    // All three rows are position:sticky with the same top offset, so as
    // siblings they pin to the same spot and overlap — the year row lands on
    // top of the topic row's lower half. Nesting them in one sticky wrapper
    // makes them stack normally and pin as a single block, which also keeps
    // working when the topic row wraps to two lines or the month row appears.
    var stack = document.createElement('div');
    stack.className = 'filter-stack';
    filtersEl.parentNode.insertBefore(stack, filtersEl);
    stack.appendChild(filtersEl);
    stack.appendChild(yearRow);
    stack.appendChild(monthRow);
  }

  var yearPills = Array.from(yearRow.querySelectorAll('.filter-pill'));
  yearPills.forEach(function(p) { p.addEventListener('click', function() { setYear(p.dataset.year); }); });

  pills.forEach(p => p.addEventListener('click', () => setTag(p.dataset.tag)));
  sbTags.forEach(t => t.addEventListener('click', () => setTag(t.dataset.tag)));

  if (searchInput) {
    searchInput.addEventListener('input', e => {
      searchTerm = e.target.value;
      applyFilters();
    });

    // ?q= deep link. The caller is the inline search box on every post page,
    // which navigates to /blog/?q=<term> on Enter -- not the homepage topic
    // section, which used to link this way and now uses ?topic= instead,
    // because a full-text search could not reproduce the counts it displayed.
    //
    // Applied here, not where the box is pre-filled further up: that code runs
    // before this listener is registered, so the 'input' event it dispatches is
    // lost and the box ends up populated with nothing filtered.
    const qDeepLink = new URLSearchParams(window.location.search).get('q');
    if (qDeepLink) {
      searchInput.value = qDeepLink;
      searchTerm = qDeepLink;
      applyFilters();
    }
  }

  // ?service= deep link from the homepage AWS coverage section. Same filter
  // the sidebar click uses, so the number on the chip is the number shown.
  const svcLink = new URLSearchParams(window.location.search).get('service');
  if (svcLink) {
    activeService = svcLink.toLowerCase();
    document.querySelectorAll('.svc-row').forEach(function (row) {
      const b = row.querySelector('.svc-name');
      row.classList.toggle('active', !!b && b.dataset.service === activeService);
    });
    applyFilters();
  }

  // ?topic= deep link from the homepage "Tools I work with" section.
  const topicLink = new URLSearchParams(window.location.search).get('topic');
  if (topicLink) {
    activeTopic = topicLink.toLowerCase();
    const note = document.getElementById('results-count');
    applyFilters();
    if (note && !note.dataset.topicNoted) {
      note.dataset.topicNoted = '1';
      note.textContent += ' mentioning ' + topicLink;
    }
  }

  // Sort toggle — inject next to results count
  var sortAsc = false;
  var sortBtn = document.createElement('button');
  sortBtn.className = 'sort-btn';
  sortBtn.title = 'Toggle sort order';
  sortBtn.innerHTML = '<span class="sort-icon">↓</span> Newest';
  if (countEl) countEl.after(sortBtn);

  function applySort() {
    var sorted = Array.from(grid.querySelectorAll('.post-card')).sort(function(a, b) {
      var da = a.dataset.date || '';
      var db = b.dataset.date || '';
      return sortAsc ? da.localeCompare(db) : db.localeCompare(da);
    });
    sorted.forEach(function(c) { grid.appendChild(c); });
  }

  sortBtn.addEventListener('click', function() {
    sortAsc = !sortAsc;
    sortBtn.innerHTML = sortAsc
      ? '<span class="sort-icon">↑</span> Oldest'
      : '<span class="sort-icon">↓</span> Newest';
    // Sorting needs the whole archive, not the 24 cards this page shipped.
    hydrate().then(function () { applySort(); applyFilters(); });
  });

  // Pre-select tag filter from ?tag= param (set by portfolio teaser links)
  var urlParams = new URLSearchParams(window.location.search);
  var tagParam = urlParams.get('tag');
  if (tagParam) {
    setTag(tagParam.toLowerCase());
  } else {
    applyFilters();
  }

  // Pull in the rest of the archive once the page is interactive. Deferred to
  // idle so it never competes with first paint; the paged view is already
  // usable and correct without it.
  if (grid) {
    if (window.requestIdleCallback) requestIdleCallback(hydrate, { timeout: 2500 });
    else setTimeout(hydrate, 400);
    // A reader who types or clicks a filter before idle fires must not get a
    // search over 24 posts, so every entry point waits for the full set first.
    if (searchInput) searchInput.addEventListener('focus', hydrate, { once: true });
    document.addEventListener('click', function (e) {
      if (e.target.closest('.filter-pill, .sb-tag, .svc-name, .topic-chip')) hydrate();
    }, true);
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

// Load the shared automatic copyright footer on every blog surface.
//
// The cache-busting token is carried over from this file's own URL rather than
// hardcoded: sync_blog.py stamps blog.js and site-footer.js with one combined
// hash, so whatever version loaded this script is the correct version of the
// script it injects. Without a token the browser reruns a cached copy — which
// matters because site-footer.js is what registers the service worker.
(function () {
  if (document.querySelector('script[data-site-footer]')) return;

  var version = '';
  var self = document.currentScript ||
             document.querySelector('script[src*="/blog/assets/blog.js"]');
  if (self) {
    var match = /[?&]v=([0-9a-zA-Z]+)/.exec(self.getAttribute('src') || '');
    if (match) version = '?v=' + match[1];
  }

  var script = document.createElement('script');
  script.src = '/blog/assets/site-footer.js' + version;
  script.setAttribute('data-site-footer', '');
  document.body.appendChild(script);

  // The occasion banner, injected the same way and for the same reason. It was
  // inline in index.html, so a reader arriving straight at a post on
  // Independence Day saw nothing and the site looked like two different sites
  // on the same day. Injecting from here reaches every blog surface including
  // the arch pages, which sync_blog.py never rebuilds and so cannot be given a
  // new script tag.
  if (!document.querySelector('script[data-occasion-banner]')) {
    var ob = document.createElement('script');
    ob.src = '/blog/assets/occasion-banner.js' + version;
    ob.setAttribute('data-occasion-banner', '');
    document.body.appendChild(ob);
  }
})();

// Service worker registration lives in site-footer.js, which every page on the
// site loads — the portfolio root and resume include it directly, and the
// block above injects it here. That makes it the one place registration
// reaches the whole origin rather than just /blog/.
