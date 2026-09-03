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
    // Carry this file's own ?v= token onto the stylesheet. Without it the CSS
    // was the one asset on the site with no cache-busting at all, so an edit
    // here shipped behind a stale copy -- the same silent failure that left
    // returning visitors running a site-footer.js that predated the service
    // worker registration. sync_blog.py includes site-footer.css in the
    // JS_VERSION hash, so editing the CSS changes this script's token too.
    var self = document.querySelector('script[src*="site-footer.js"]');
    var v = self && (self.getAttribute('src').split('?v=')[1] || '');
    link.href = '/blog/assets/site-footer.css' + (v ? '?v=' + v : '');
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
    footer.innerHTML =
      '<p>&copy; <span data-current-year></span> Jayanth Katta &mdash; ' +
      '<a href="https://jayanthkatta.com/">jayanthkatta.com</a></p>' +
      paletteNoteMarkup();
    updateYear();
    wirePaletteNote();
    scheduleMidnightRefresh();
  }

  // ---- "why does this site change colour?" -------------------------------
  //
  // The seven grounds rotate by weekday and nothing on the site said so, which
  // makes a returning reader's own memory look unreliable. This names today's
  // colour in the footer and, on click, explains the rotation and shows the
  // whole week.
  //
  // Two things it deliberately does NOT do:
  //
  //  * It does not compute the day. It reads <html data-palette>, which is set
  //    before first paint by the inline script in every page's <head> and which
  //    honours the ?palette= override. Recomputing here would disagree with the
  //    page whenever that override is in use, and would need the same seven-key
  //    day table in a second place.
  //
  //  * It does not decide light/dark from a class. The blog uses `body.dark`
  //    and the portfolio pages use `body.light` for the same intent, so a class
  //    check has to know which page it is on. Measuring the body's own
  //    background luminance cannot make that mistake -- the same reasoning as
  //    site-footer.css using currentColor instead of a token chain.
  var DAYS = ['sun', 'mon', 'tue', 'wed', 'thu', 'fri', 'sat'];
  var DAY_NAMES = {
    sun: 'Sunday', mon: 'Monday', tue: 'Tuesday', wed: 'Wednesday',
    thu: 'Thursday', fri: 'Friday', sat: 'Saturday'
  };
  // Ground colours, copied from the seven rotation rules in blog.css. Hardcoded
  // here on purpose: a swatch of Tuesday's bone has to render bone on a Friday,
  // so it cannot come from a live token.
  //
  // `note` describes the COLOUR, never the day. The day-to-colour assignment was
  // solved arithmetically -- 720 permutations, maximise the smallest consecutive
  // gap -- so "Thursday is clay because Thursday is grounded" would be invented
  // symbolism attached to the output of a sort. Each line is instead a fact from
  // the palette itself: its hue, or its R-B warmth in the comment block that
  // defines these seven rules in blog.css.
  var GROUND = {
    mon: { name: 'stone blue',  light: '#EFF7FB', dark: '#191E20',
           note: 'the coolest of the seven',
           mean: 'distance, and cold water' },
    tue: { name: 'bone',        light: '#F7F4EF', dark: '#1F1D1B',
           note: 'paper, not cream',
           mean: 'what remains — paper, age, patience' },
    wed: { name: 'teal stone',  light: '#EFF8F7', dark: '#191F1E',
           note: 'slate with water on it',
           mean: 'still water over slate' },
    thu: { name: 'clay',        light: '#FAF2F2', dark: '#211C1C',
           note: 'earth, warmed',
           mean: 'earth in the hands; the material you shape' },
    fri: { name: 'sage',        light: '#F2F8F3', dark: '#1B1E1B',
           note: 'green gone grey',
           mean: 'the herb garden — healing, and keeping' },
    sat: { name: 'ash violet',  light: '#F4F4FA', dark: '#1D1D21',
           note: 'the last of the light',
           mean: 'last light, and what follows it' },
    sun: { name: 'moss grey',   light: '#F5F7F2', dark: '#1D1E1B',
           note: 'green under grey',
           mean: 'what grows on things left alone' }
  };

  // Null on a page that does not rotate. resume.html is the case: it is pinned
  // to bone on purpose -- a resume is read once and often printed, so a colour
  // that depends on the weekday is invisible to whoever is reading it -- and it
  // therefore has no data-palette setter. Falling back to the computed day here
  // made the footer announce "Thursday is clay" on a page that was bone, which
  // is worse than saying nothing: it describes the rotation to the one reader
  // who cannot see it.
  function cap(s) { return s.charAt(0).toUpperCase() + s.slice(1); }

  // Has the reader pinned a colour? The <head> setter on every page already
  // reads localStorage.paletteDay before first paint, so writing that key is
  // all a choice needs -- it survives navigation and reloads with no work here.
  function chosen() {
    try { return GROUND[localStorage.getItem('paletteDay')] ? true : false; }
    catch (e) { return false; }
  }

  function todayKey() {
    var k = document.documentElement.getAttribute('data-palette');
    return GROUND[k] ? k : null;
  }

  function pageIsDark() {
    var bg = getComputedStyle(document.body).backgroundColor || '';
    var m = bg.match(/\d+/g);
    if (!m || m.length < 3) return false;
    // Rec. 601 luma is enough to sort a #181818 ground from a #F7F4EF one.
    return (0.299 * m[0] + 0.587 * m[1] + 0.114 * m[2]) < 128;
  }

  function paletteNoteMarkup() {
    var k = todayKey();
    if (!k) return '';                 // page does not rotate; claim nothing
    return '' +
      '<p class="pal-note">' +
        '<button type="button" class="pal-toggle" aria-expanded="false" ' +
                'aria-controls="pal-why">' +
          DAY_NAMES[k] + ' is <span class="pal-name">' + GROUND[k].name + '</span>' +
          '<span class="pal-caret" aria-hidden="true">&#8964;</span>' +
        '</button>' +
      '</p>' +
      '<div class="pal-why" id="pal-why" hidden></div>';
  }

  function whyMarkup() {
    var k = todayKey();
    var dark = pageIsDark();
    var swatches = DAYS.map(function (d) {
      return '<button type="button" class="pal-day' + (d === k ? ' is-today' : '') +
                   '" data-day="' + d + '" ' +
                   'title="Preview ' + DAY_NAMES[d] + ' &mdash; ' + GROUND[d].name + '">' +
               '<span class="pal-sw" style="background:' +
                 GROUND[d][dark ? 'dark' : 'light'] + '"></span>' +
               '<span class="pal-ini">' + DAY_NAMES[d].charAt(0) + '</span>' +
             '</button>';
    }).join('');
    return '' +
      '<p><strong>' + cap(GROUND[k].name) + '</strong> &mdash; ' + GROUND[k].note +
        '.<br><span class="pal-mean">' + GROUND[k].mean + '</span></p>' +
      '<div class="pal-week" role="img" aria-label="The seven weekday grounds, ' +
        'Sunday through Saturday">' + swatches + '</div>' +
      '<p class="pal-legend">' + DAYS.map(function (d) {
        return (d === k ? '<b>' : '') + GROUND[d].name + (d === k ? '</b>' : '');
      }).join(' &middot; ') + '</p>' +
      '<p class="pal-hint">' +
        (chosen() ? 'Yours, until you change it. ' +
                    '<button type="button" class="pal-reset">Follow the day instead</button>'
                  : 'Pick one to keep it, or let it follow the day.') +
      '</p>';
  }

  function relabel(d) {
    var lbl = document.querySelector('.pal-toggle');
    if (!lbl) return;
    lbl.innerHTML = DAY_NAMES[d] + ' is <span class="pal-name">' + GROUND[d].name +
      '</span><span class="pal-caret" aria-hidden="true">&#8964;</span>';
  }

  function wirePaletteNote() {
    if (!todayKey()) return;
    var btn = document.querySelector('.pal-toggle');
    var why = document.getElementById('pal-why');
    if (!btn || !why) return;
    // Clicking a day repaints the whole page, live. The seven grounds differ by
    // 4-5 deltaE -- real, but far below what a row of 24px swatches can show, so
    // describing the rotation in words was never going to land. Applying it to
    // the page the reader is already looking at is the only demonstration that
    // works. data-palette is the same attribute the <head> setter writes, so
    // every rule keyed on it follows with no reload.
    why.addEventListener('click', function (e) {
      if (e.target.classList && e.target.classList.contains('pal-reset')) {
        try { localStorage.removeItem('paletteDay'); } catch (e3) {}
        var back = DAYS[new Date().getDay()];
        document.documentElement.setAttribute('data-palette', back);
        why.innerHTML = whyMarkup();
        relabel(back);
        return;
      }
      var day = e.target.closest && e.target.closest('[data-day]');
      if (!day) return;
      var d = day.getAttribute('data-day');
      document.documentElement.setAttribute('data-palette', d);
      try { localStorage.setItem('paletteDay', d); } catch (e2) {}
      why.innerHTML = whyMarkup();                       // redraw for the new day
      relabel(d);
    });

    btn.addEventListener('click', function () {
      var open = btn.getAttribute('aria-expanded') === 'true';
      if (!open && !why.innerHTML) why.innerHTML = whyMarkup();   // build on first open
      btn.setAttribute('aria-expanded', open ? 'false' : 'true');
      why.hidden = open;
    });
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

// "Was this useful?" — post feedback.
//
// Lives here rather than in sync_blog.py for the same reason the service
// worker registration does: this is the one script every page loads, so one
// copy reaches all 113 posts and every future one — including the Architecture
// Series pages, which sync_blog.py never rebuilds and which would otherwise
// need editing by hand, one file at a time, forever.
//
// It stores no free text and nothing identifying. Readers with something
// specific to say get a mailto instead, which routes the detail to a human
// rather than into a table nobody moderates.
(function () {
  'use strict';

  var API = 'https://37arp5b92a.execute-api.us-east-1.amazonaws.com/feedback';
  var CONTACT = 'katta.jayant@gmail.com';

  // Below this, a score says more about who happened to click than about the
  // post — "1 of 1 found this useful" reads worse than showing nothing.
  var MIN_VOTES_FOR_COUNT = 5;

  // Must match REASONS in the query Lambda; anything else is rejected there.
  var REASONS = [
    ['too-shallow',         'Too shallow'],
    ['too-long',            'Too long'],
    ['not-what-i-expected', 'Not what I expected']
  ];

  var THUMB_UP = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7 22V11m0 0 4.2-8.4a2 2 0 0 1 3.6 1.4L14 9h5.3a2 2 0 0 1 2 2.5l-2 8A2 2 0 0 1 17.3 21H7Z"/><rect x="2" y="11" width="5" height="11" rx="1"/></svg>';
  var THUMB_DOWN = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 2v11m0 0-4.2 8.4a2 2 0 0 1-3.6-1.4L10 15H4.7a2 2 0 0 1-2-2.5l2-8A2 2 0 0 1 6.7 3H17Z"/><rect x="17" y="2" width="5" height="11" rx="1"/></svg>';

  // Only post pages: /blog/<slug>/. Not /blog/ itself, not /blog/assets/*.
  var m = location.pathname.match(/^\/blog\/([a-z0-9][a-z0-9-]*)\/?$/);
  if (!m || m[1] === 'assets') return;
  var slug = m[1];

  // localStorage throws outright in some privacy modes rather than failing
  // soft, and a feedback widget must never be what breaks a page.
  function remembered() {
    try { return window.localStorage.getItem('jk-feedback-' + slug); }
    catch (e) { return null; }
  }
  function remember(vote) {
    try { window.localStorage.setItem('jk-feedback-' + slug, vote); }
    catch (e) { /* asked again next visit; harmless */ }
  }
  function forget() {
    try { window.localStorage.removeItem('jk-feedback-' + slug); }
    catch (e) { /* nothing to undo if storage is unavailable */ }
  }

  // A random id for this browser, made once and kept. It is the sort key on the
  // server, so a second vote from here overwrites the first instead of being
  // counted as another reader -- which is what lets someone change their mind.
  //
  // It identifies a browser, not a person: no address, no fingerprint, gone the
  // moment site data is cleared, and shared across posts only with itself.
  function voterId() {
    try {
      var id = window.localStorage.getItem('jk-voter');
      if (id) return id;
      var buf = new Uint8Array(10);
      (window.crypto || window.msCrypto).getRandomValues(buf);
      id = Array.prototype.map.call(buf, function (b) {
        return ('0' + b.toString(16)).slice(-2);
      }).join('');
      window.localStorage.setItem('jk-voter', id);
      return id;
    } catch (e) {
      // Storage blocked (private mode) or no crypto. Fall back to a throwaway
      // id for this page view: the server requires one, so returning nothing
      // would turn a blocked cookie jar into a rejected vote. It cannot be
      // revised on a later visit, because nothing here outlives the page.
      if (!fallbackVoter) {
        fallbackVoter = '';
        for (var i = 0; i < 20; i++) {
          fallbackVoter += Math.floor(Math.random() * 16).toString(16);
        }
      }
      return fallbackVoter;
    }
  }
  var fallbackVoter = null;

  function el(tag, cls, html) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (html != null) n.innerHTML = html;
    return n;
  }

  function send(vote, reason) {
    // The voter id keys the row, so every one of these -- the thumb, a reason
    // chip a moment later, a change of mind next week -- writes to the same
    // place. There is no second insert to guard against.
    var payload = { slug: slug, vote: vote, voter: voterId() };
    if (reason) payload.reason = reason;
    // keepalive so a vote cast as the reader leaves still goes out.
    //
    // The catch is not optional: every call site fires and forgets, so without
    // it a failed POST becomes an unhandled rejection in the reader's console.
    // A vote that does not reach the table is a lost vote, not a broken page --
    // it must never surface as an error, and the UI advances either way.
    return fetch(API, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true
    }).catch(function () { /* lost vote; the reader should never know */ });
  }

  function thanksRow(root) {
    root.innerHTML = '';
    root.appendChild(el('span', 'qs-feedback-thanks', 'Thanks &mdash; noted.'));

    // Someone who misclicks, or reads the rest and changes their mind, has to
    // be able to say so. Without this the only way back is clearing site data,
    // and doing that used to register as a whole second reader.
    var again = el('button', 'qs-feedback-change', 'change');
    again.type = 'button';
    again.addEventListener('click', function () {
      forget();
      root.innerHTML = '';
      buildInto(root);
    });
    root.appendChild(again);

    showCount(root);
  }

  function showCount(root) {
    fetch(API + '?slug=' + encodeURIComponent(slug))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d) return;
        var total = (d.up || 0) + (d.down || 0);
        if (total < MIN_VOTES_FOR_COUNT) return;
        root.appendChild(el('span', 'qs-feedback-count',
          d.up + ' of ' + total + ' found this useful'));
      })
      .catch(function () { /* a missing count is not worth a visible error */ });
  }

  function askWhy(root) {
    root.innerHTML = '';
    root.appendChild(el('span', 'qs-feedback-q', 'What was off?'));

    var chips = el('div', 'qs-feedback-reasons');
    REASONS.forEach(function (r) {
      var b = el('button', 'qs-reason', r[1]);
      b.type = 'button';
      b.addEventListener('click', function () {
        send('down', r[0]);
        thanksRow(root);
      });
      chips.appendChild(b);
    });

    // The one response worth more than the score. document.title carries the
    // " | Jayanth Katta Blog" suffix, which is noise in a subject line.
    var title = document.title.replace(/\s*\|\s*Jayanth Katta Blog\s*$/, '');
    var mail = el('a', 'qs-reason qs-reason-mail', 'Something&rsquo;s wrong &#8594;');
    mail.href = 'mailto:' + CONTACT +
      '?subject=' + encodeURIComponent('Correction: ' + title) +
      '&body=' + encodeURIComponent('Page: ' + location.href + '\n\nWhat looks wrong:\n');
    mail.addEventListener('click', function () { send('down', 'something-is-wrong'); });
    chips.appendChild(mail);

    root.appendChild(chips);
  }

  function build() {
    var root = el('div', 'qs-feedback');
    if (remembered()) {
      thanksRow(root);
    } else {
      buildInto(root);
    }
    return root;
  }

  // Fills an element with the question and the thumbs. Separate from build()
  // so the "change" link can re-ask inside the element already on the page,
  // rather than replacing it and losing where it sits in the box.
  function buildInto(root) {
    root.appendChild(el('span', 'qs-feedback-q', 'Was this useful?'));
    var btns = el('div', 'qs-feedback-btns');

    [['up', THUMB_UP, 'Yes, this was useful'],
     ['down', THUMB_DOWN, 'No, this was not useful']].forEach(function (v) {
      var b = el('button', 'qs-vote', v[1]);
      b.type = 'button';
      b.setAttribute('aria-pressed', 'false');
      b.setAttribute('aria-label', v[2]);
      b.addEventListener('click', function () {
        remember(v[0]);
        if (v[0] === 'up') {
          send('up');
          thanksRow(root);
        } else {
          // The vote is recorded now, not on the follow-up: most readers pick
          // no reason, and losing those down-votes would flatter every post.
          send('down');
          askWhy(root);
        }
      });
      btns.appendChild(b);
    });

    root.appendChild(btns);
  }

  function mount() {
    if (document.querySelector('.qs-feedback')) return true;
    var box = document.querySelector('.quick-summary-content');
    if (box) { box.appendChild(build()); return true; }
    return false;
  }

  // The At a glance box is written by a separate script after its own API call
  // (mount.outerHTML = ...), so it does not exist at DOMContentLoaded and may
  // never exist at all: a post the indexer has not summarised yet renders no
  // box, silently and by design. Watch for it, and fall back to the foot of the
  // post body so new posts — the ones feedback is most useful on — still ask.
  function start() {
    if (mount()) return;

    var observer = new MutationObserver(function () {
      if (mount()) observer.disconnect();
    });
    observer.observe(document.body, { childList: true, subtree: true });

    window.setTimeout(function () {
      observer.disconnect();
      if (document.querySelector('.qs-feedback')) return;
      var body = document.querySelector('.post-body');
      if (!body) return;
      var strip = build();
      strip.classList.add('qs-feedback-standalone');
      body.appendChild(strip);
    }, 5000);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
