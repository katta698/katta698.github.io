/* Post-incident write-ups: open one in a dialog, on demand.
 *
 * The store is ~312 KB because it holds the vendors' full published text, so
 * it is NOT embedded in the page. Cards are rendered at build time from the
 * index; the first card opened fetches the store once and every later one is
 * served from memory.
 *
 * Nothing here paraphrases. The dialog shows the vendor's own words, their own
 * section headings where they publish them, and a link to the original. If a
 * field is missing it stays missing and says so -- an outage write-up is
 * exactly the place where a confident-sounding filler sentence would do the
 * most damage.
 */
(function () {
  'use strict';

  var store = null;      // the parsed JSON, once fetched
  var pending = null;    // the in-flight promise, so a double click fetches once
  var dlg = document.getElementById('pm-dialog');
  if (!dlg) return;

  var body = dlg.querySelector('.pm-body');
  var lastFocus = null;

  function esc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Vendor prose arrives as plain text with blank lines between paragraphs.
  // Rendering it into a single block loses that structure and makes a 4,000
  // word summary unreadable, which is the same as not publishing it.
  function paras(t) {
    return String(t || '').split(/\n{2,}/)
      .map(function (p) { return p.trim(); })
      .filter(Boolean)
      .map(function (p) { return '<p>' + esc(p).replace(/\n/g, '<br>') + '</p>'; })
      .join('');
  }

  function load() {
    if (store) return Promise.resolve(store);
    if (pending) return pending;
    pending = fetch('/intelligence/postmortems.json', { cache: 'no-cache' })
      .then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      })
      .then(function (j) { store = j; return j; });
    return pending;
  }

  function render(rec) {
    var head =
      '<p class="pm-meta"><span class="chip ' + esc(rec.cloud) + '">' +
      esc((rec.cloud === 'gcp' ? 'Google Cloud' : rec.cloud).toUpperCase()) +
      '</span>' +
      (rec.date ? '<span class="pm-date">' + esc(rec.date) + '</span>'
                : '<span class="pm-date pm-none">date not stated in the summary</span>') +
      '</p>' +
      '<h3 id="pm-title">' + esc(rec.title) + '</h3>';

    var main;
    if (rec.sections && rec.sections.length) {
      main = rec.sections.map(function (s) {
        return '<section class="pm-sec"><h4>' + esc(s.heading) + '</h4>' +
               paras(s.text) + '</section>';
      }).join('');
    } else {
      // AWS publishes narrative summaries with no headings at all. Inventing
      // some here would imply a structure AWS did not write, so the prose is
      // shown as prose and the difference is stated plainly.
      main = '<p class="pm-shape">Published as a narrative summary. ' +
             'AWS does not break these into sections, so this is the text as ' +
             'written.</p>' + paras(rec.body);
    }

    var vendor = rec.cloud === 'aws' ? 'AWS'
               : rec.cloud === 'azure' ? 'Microsoft' : 'Google';
    var foot =
      '<p class="pm-src">Quoted in full from ' + esc(vendor) + '’s own ' +
      'published write-up. Nothing on this page is summarised or rewritten. ' +
      '<a href="' + esc(rec.url) + '" target="_blank" rel="noopener">' +
      'Read it on ' + esc(vendor) + '’s site →</a></p>';

    body.innerHTML = head + main + foot;
    body.scrollTop = 0;
  }

  function open(id) {
    lastFocus = document.activeElement;
    body.innerHTML = '<p class="pm-loading">Loading the write-up…</p>';
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');

    load().then(function (j) {
      var rec = (j.postmortems || []).filter(function (r) {
        return r.cloud + ':' + r.id === id;
      })[0];
      if (!rec) throw new Error('not found');
      render(rec);
    }).catch(function (err) {
      // Say what failed. A blank dialog reads as "there is nothing here",
      // which is a different and wrong claim.
      body.innerHTML = '<p class="pm-loading">Could not load this write-up (' +
        esc(err.message) + '). It is still on the vendor’s own site.</p>';
    });
  }

  function close() {
    if (typeof dlg.close === 'function' && dlg.open) dlg.close();
    else dlg.removeAttribute('open');
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  document.addEventListener('click', function (ev) {
    var card = ev.target.closest ? ev.target.closest('[data-pm]') : null;
    if (card) {
      ev.preventDefault();
      open(card.getAttribute('data-pm'));
      return;
    }
    if (ev.target.hasAttribute && ev.target.hasAttribute('data-pm-close')) close();
    // Clicking the backdrop closes: the dialog element itself is the backdrop,
    // so a click landing on it rather than on its content means outside.
    if (ev.target === dlg) close();
  });

  dlg.addEventListener('cancel', function () { close(); });

  document.addEventListener('keydown', function (ev) {
    if (ev.key === 'Escape' && dlg.open) close();
  });

  /* Timeline day dialog.
   *
   * Every AWS bar used to link to health.aws.amazon.com/health/status --
   * the same address for all twelve, because AWS's dashboard is a single-page
   * app whose URL does not change when an event is opened. There is no
   * per-incident address to link to, so linking there sent a reader to a list
   * to hunt through.
   *
   * The page already holds what they wanted: the title, service, region,
   * dates and the vendor's own last update. So a cell opens that instead.
   * Where a real per-incident page exists -- Google publishes one -- the
   * dialog links to it. Where it does not, it says so rather than offering a
   * link that goes somewhere general.
   */
  var tlData = document.getElementById('tl-data');
  var incidents = [];
  if (tlData) {
    try { incidents = JSON.parse(tlData.textContent) || []; } catch (e) { incidents = []; }
  }

  var VENDOR = { aws: 'AWS', azure: 'Microsoft', gcp: 'Google' };

  // Both zones, always.
  //
  // The strip buckets days in UTC, and the vendors' own dashboards render in
  // the reader's local time. An AWS event at 02:02 UTC on 21 August is 19:02
  // on the 20th in Pacific and 21:02 on the 20th in Chicago -- so this page
  // said the 21st while AWS's own page said the 20th, for the same instant.
  // A reader checking one against the other finds a date that does not match
  // and has no way to tell it is a timezone rather than an error, which is
  // the worst possible failure on a page whose argument is "go and verify
  // this".
  //
  // Neither zone alone fixes it: UTC is what the strip is built in and cannot
  // change per reader, and local time is what they will compare against. So
  // both are shown, labelled, whenever they fall on different days.
  function parseTs(v) {
    if (!v) return null;
    var n = parseInt(v, 10);
    var d = (String(v).length >= 9 && String(n) === String(v))
          ? new Date(n * 1000) : new Date(v);
    return isNaN(d.getTime()) ? null : d;
  }

  function when(v) {
    var d = parseTs(v);
    if (!d) return '';
    var utc = d.toISOString().slice(0, 16).replace('T', ' ') + ' UTC';
    var pad = function (x) { return (x < 10 ? '0' : '') + x; };
    var local = d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) +
                ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
    // Only worth saying when the calendar day differs -- otherwise it is
    // noise on every line.
    if (local.slice(0, 10) !== utc.slice(0, 10)) {
      return utc + ' (' + local + ' your time)';
    }
    return utc;
  }

  function openDay(day, idxs) {
    lastFocus = document.activeElement;
    var rows = idxs.map(function (i) { return incidents[i]; }).filter(Boolean);

    // A day shows every incident OPEN on it, which includes ones that started
    // months earlier -- the two Middle East events have been open since March,
    // so they appear on all ninety days. Listed plainly that reads as a bug:
    // "3 incidents open on this day" above two entries dated 1 March.
    //
    // So the ones that STARTED that day come first and are labelled as such,
    // and the rest are marked as already running, with the date they began.
    // Same set, ordered and captioned so the old dates explain themselves.
    function began(r) { return String(r.b || '').slice(0, 10) === day || when(r.b).slice(0, 10) === day; }
    rows.sort(function (a, b) { return (began(b) ? 1 : 0) - (began(a) ? 1 : 0); });
    var nNew = rows.filter(began).length;
    var nOld = rows.length - nNew;

    var head = nNew
      ? (nNew + (nNew === 1 ? ' incident began' : ' incidents began') + ' on this day')
      : 'Nothing began on this day';
    if (nOld) head += ' · ' + nOld + ' already running';

    var html = '<p class="pm-meta"><span class="pm-date">' + esc(day) + '</span></p>' +
               '<h3 id="pm-title">' + esc(head) + '</h3>';
    rows.forEach(function (r) {
      var v = VENDOR[r.c] || r.c;
      html += '<section class="pm-sec">' +
        '<h4><span class="chip ' + esc(r.c) + '">' + esc(v) + '</span></h4>' +
        '<p><strong>' + esc(r.t) + '</strong></p>' +
        (r.s ? '<p class="pm-shape">Service: ' + esc(r.s) + '</p>' : '') +
        (r.r ? '<p class="pm-shape">Region: ' + esc(r.r) + '</p>' : '') +
        '<p class="pm-shape">' +
          (began(r) ? 'Began ' : 'Already running — began ') +
          esc(when(r.b) || 'not stated') +
          (r.e ? ' · ended ' + esc(when(r.e)) : ' · still open') + '</p>' +
        (r.m ? '<p>' + esc(r.m) + '</p>' : '') +
        (r.u
          ? '<p class="pm-src"><a href="' + esc(r.u) + '" target="_blank" rel="noopener">Read it on ' + esc(v) + '’s site →</a>' +
            // Azure's history page has no address for one review, so the link
            // lands on the list. Without the tracking id a reader has to scan
            // thirty entries to find the one they clicked.
            (r.k ? ' <span class="pm-shape">Set the Date filter to <b>All</b> and find tracking ID <b>' + esc(r.k) + '</b>.</span>' : '') +
            '</p>'
          // Only reached when a vendor genuinely publishes no address for
          // the incident. AWS does -- ?eventID=<arn> opens its detail panel --
          // so this is now Azure's case, whose feed carries no per-incident
          // link at all.
          : '<p class="pm-src">' + esc(v) +
            ' publishes no address for this incident, so there is nothing to link to' +
            (r.g ? '. Read from <a href="' + esc(r.g) + '" target="_blank" rel="noopener">their status page</a>' : '') +
            '; the text above is theirs.</p>') +
        '</section>';
    });
    body.innerHTML = html;
    body.scrollTop = 0;
    if (typeof dlg.showModal === 'function') dlg.showModal();
    else dlg.setAttribute('open', '');
  }

  document.addEventListener('click', function (ev) {
    var cell = ev.target.closest ? ev.target.closest('[data-inc]') : null;
    if (!cell) return;
    ev.preventDefault();
    var idxs = (cell.getAttribute('data-inc') || '')
      .split(',').filter(Boolean).map(Number);
    openDay(cell.getAttribute('data-day'), idxs);
  });

  /* Filters for the write-up archive: year and cloud, combined.
   *
   * Counts on the chips are RECOMPUTED against the other filter, so each one
   * says how many cards clicking it would actually show. They used to be
   * fixed totals, which meant "AWS 18" sat beside a selected 2026 in which
   * AWS published nothing -- a chip advertising eighteen results and
   * delivering an empty section. A count that does not describe its own click
   * is decoration.
   *
   * Hides, never removes: every card stays in the HTML, so browser search
   * still finds them and the section still works with JavaScript off.
   */
  var yrs = document.querySelector('.pm-yrs');
  var cls = document.querySelector('.pm-cls');
  if (yrs) {
    var onYear = yrs.querySelector('.pm-yr.is-on');
    var curYear = onYear ? onYear.getAttribute('data-yr') : 'all';
    var curCloud = 'all';

    var cards = [].slice.call(document.querySelectorAll('.pm-card'));
    var groups = [].slice.call(document.querySelectorAll('.pm-year'));

    function cloudOf(c) {
      return c.classList.contains('aws') ? 'aws'
           : c.classList.contains('azure') ? 'azure'
           : c.classList.contains('gcp') ? 'gcp' : '';
    }
    function yearOf(c) {
      var g = c.closest('.pm-year');
      return g ? g.getAttribute('data-yr') : '';
    }

    function apply() {
      var total = 0;
      groups.forEach(function (g) {
        var shown = 0;
        [].forEach.call(g.querySelectorAll('.pm-card'), function (c) {
          var ok = (curYear === 'all' || yearOf(c) === curYear) &&
                   (curCloud === 'all' || cloudOf(c) === curCloud);
          c.classList.toggle('is-hidden', !ok);
          if (ok) shown++;
        });
        g.classList.toggle('is-hidden', shown === 0);
        total += shown;
      });

      // Year chips count within the chosen cloud; cloud chips count within
      // the chosen year. Each number is what that click would give you.
      [].forEach.call(yrs.querySelectorAll('.pm-yr'), function (b) {
        var y = b.getAttribute('data-yr');
        var n = cards.filter(function (c) {
          return (y === 'all' || yearOf(c) === y) &&
                 (curCloud === 'all' || cloudOf(c) === curCloud);
        }).length;
        var span = b.querySelector('.pm-yn');
        if (span) span.textContent = n;
        b.classList.toggle('is-empty', n === 0);
      });
      if (cls) {
        [].forEach.call(cls.querySelectorAll('.pm-cl'), function (b) {
          var cl = b.getAttribute('data-cl');
          var n = cards.filter(function (c) {
            return (curYear === 'all' || yearOf(c) === curYear) &&
                   (cl === 'all' || cloudOf(c) === cl);
          }).length;
          var span = b.querySelector('.pm-yn');
          if (span) span.textContent = n;
          b.classList.toggle('is-empty', n === 0);
        });
      }

      var none = document.querySelector('.pm-none');
      if (none) {
        var cn = curCloud === 'all' ? '' :
          ((cls.querySelector('.pm-cl.is-on') || {}).textContent || '')
            .replace(/\s*\d+\s*$/, '').trim();
        var yn = curYear === 'all' ? 'any year' : curYear;
        none.hidden = total !== 0;
        none.textContent = total === 0
          ? (cn ? cn + ' published no write-up dated ' + yn + '.'
                : 'Nothing dated ' + yn + '.')
          : '';
      }
    }

    yrs.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('.pm-yr') : null;
      if (!b) return;
      curYear = b.getAttribute('data-yr');
      [].forEach.call(yrs.querySelectorAll('.pm-yr'), function (x) {
        x.classList.toggle('is-on', x === b);
      });
      apply();
    });

    if (cls) {
      cls.addEventListener('click', function (ev) {
        var b = ev.target.closest ? ev.target.closest('.pm-cl') : null;
        if (!b) return;
        curCloud = b.getAttribute('data-cl');
        [].forEach.call(cls.querySelectorAll('.pm-cl'), function (x) {
          x.classList.toggle('is-on', x === b);
        });
        apply();
      });
    }

    apply();
  }

  /* Year views for the timeline.
   *
   * The strip covers 90 days, which answers "is anything broken now" and not
   * "what broke this year" -- a question the store could already answer from
   * 904 incidents back to 2021 while the page could not.
   *
   * The index is a separate fetch because it is ~200 KB against a ~110 KB
   * page: embedding it would double every visit for a view most readers never
   * open. Fetched once, on the first year clicked, and reused after.
   *
   * Cells behave exactly like the 90-day ones -- click opens the day -- so
   * there is one interaction to learn, not two.
   */
  var winBar = document.querySelector('.tl-win');
  if (winBar) {
    var idx = null, idxPending = null;
    var tl = document.querySelector('.tl');
    var saved90 = null;

    function loadIndex() {
      if (idx) return Promise.resolve(idx);
      if (idxPending) return idxPending;
      idxPending = fetch('/intelligence/timeline-index.json', { cache: 'no-cache' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (j) { idx = j; return j; });
      return idxPending;
    }

    var CLOUDS = [['aws', 'AWS'], ['azure', 'Azure'], ['gcp', 'Google Cloud']];

    function days(year) {
      var out = [], d = new Date(Date.UTC(+year, 0, 1));
      var end = new Date(Date.UTC(+year, 11, 31));
      var today = new Date();
      if (end > today) end = today;
      while (d <= end) {
        out.push(d.toISOString().slice(0, 10));
        d = new Date(d.getTime() + 86400000);
      }
      return out;
    }

    function renderYear(year) {
      var list = days(year);
      var byDay = {};
      idx.incidents.forEach(function (r) {
        if (!r.b) return;
        var start = r.b, stop = r.e || list[list.length - 1];
        if (stop < list[0] || start > list[list.length - 1]) return;
        // Walk the span, clipped to this year.
        var d = start < list[0] ? list[0] : start;
        var guard = 0;
        while (d <= stop && d <= list[list.length - 1] && guard++ < 400) {
          (byDay[d] = byDay[d] || []).push(r);
          var n = new Date(d + 'T00:00:00Z');
          d = new Date(n.getTime() + 86400000).toISOString().slice(0, 10);
        }
      });

      var html = '';
      CLOUDS.forEach(function (pair) {
        var cl = pair[0], label = pair[1], cells = '', began = 0, marked = 0;
        list.forEach(function (day) {
          var here = (byDay[day] || []).filter(function (r) { return r.c === cl; });
          if (!here.length) {
            cells += '<i class="d ok" title="' + day + ' — nothing reported"></i>';
            return;
          }
          marked++;
          var starts = here.filter(function (r) { return r.b === day; });
          if (starts.length) began++;
          var titles = here.map(function (r) { return r.t; }).join(' | ');
          cells += '<button class="d ' + (starts.length ? 'bad' : 'bad cont') +
                   '" data-day="' + day + '" data-y="' + year + '" data-c="' + cl +
                   '" type="button" title="' + esc(day) + '&#10;' + esc(titles.slice(0, 180)) + '"></button>';
        });
        html += '<div class="tl-row"><div class="tl-n">' + label + '</div>' +
                '<div class="tl-cells">' + cells + '</div>' +
                '<div class="tl-s" title="' + began + ' began in ' + year + '">' +
                marked + ' of ' + list.length + '</div></div>';
      });
      tl.innerHTML = html;
      tl.classList.add('is-year');
    }

    function showDay(day, cloud) {
      var here = idx.incidents.filter(function (r) {
        return r.c === cloud && r.b <= day && (r.e || '9999') >= day;
      });
      var began = here.filter(function (r) { return r.b === day; }).length;
      var head = began ? began + (began === 1 ? ' incident began' : ' incidents began') +
                         ' on this day' : 'Nothing began on this day';
      if (here.length - began) head += ' · ' + (here.length - began) + ' already running';
      var v = { aws: 'AWS', azure: 'Microsoft', gcp: 'Google' }[cloud] || cloud;
      var html = '<p class="pm-meta"><span class="pm-date">' + esc(day) + '</span></p>' +
                 '<h3 id="pm-title">' + esc(head) + '</h3>';
      here.sort(function (a, b) { return (b.b === day) - (a.b === day); });
      here.forEach(function (r) {
        html += '<section class="pm-sec">' +
          '<h4><span class="chip ' + esc(r.c) + '">' + esc(v) + '</span></h4>' +
          '<p><strong>' + esc(r.t) + '</strong></p>' +
          '<p class="pm-shape">' + (r.b === day ? 'Began ' : 'Already running — began ') +
          esc(r.b) + (r.e ? ' · ended ' + esc(r.e) : ' · still open') + '</p>' +
          (r.u ? '<p class="pm-src"><a href="' + esc(r.u) + '" target="_blank" rel="noopener">Read it on ' + esc(v) + '’s site →</a></p>' : '') +
          '</section>';
      });
      body.innerHTML = html;
      body.scrollTop = 0;
      if (typeof dlg.showModal === 'function') dlg.showModal();
      else dlg.setAttribute('open', '');
    }

    winBar.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('.tl-w') : null;
      if (!b) return;
      var want = b.getAttribute('data-win');
      [].forEach.call(winBar.querySelectorAll('.tl-w'), function (x) {
        x.classList.toggle('is-on', x === b);
      });
      if (want === '90') {
        if (saved90 !== null) tl.innerHTML = saved90;
        tl.classList.remove('is-year');
        return;
      }
      if (saved90 === null) saved90 = tl.innerHTML;   // keep the server-rendered 90 days
      tl.innerHTML = '<p class="pm-loading">Loading ' + esc(want) + '…</p>';
      loadIndex().then(function () { renderYear(want); })
                 .catch(function (e) {
                   tl.innerHTML = '<p class="pm-loading">Could not load the year view (' +
                                  esc(e.message) + ').</p>';
                 });
    });

    document.addEventListener('click', function (ev) {
      var c = ev.target.closest ? ev.target.closest('.d[data-y]') : null;
      if (!c) return;
      ev.preventDefault();
      showDay(c.getAttribute('data-day'), c.getAttribute('data-c'));
    });
  }
})();
