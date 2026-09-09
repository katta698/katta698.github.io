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

  /* The archive: every incident held, filtered by year and cloud.
   *
   * Rendered here rather than baked into the page: 922 cards is roughly
   * 200 KB of markup against a 108 KB page. The index is the same file the
   * timeline is built from, which is the whole point -- the two used to read
   * different stores and disagreed about 2022 by 210 incidents.
   */
  var yrs = document.querySelector('.pm-yrs');
  var cls = document.querySelector('.pm-cls');
  var list = document.getElementById('pm-list');
  if (yrs && list) {
    var all = null, pending = null, writeups = null;
    var onY = yrs.querySelector('.pm-yr.is-on');
    var curYear = onY ? onY.getAttribute('data-yr') : 'all';
    var curCloud = 'all';

    var VEND = { aws: 'AWS', azure: 'Microsoft', gcp: 'Google' };
    var NAME = { aws: 'AWS', azure: 'Azure', gcp: 'Google Cloud' };

    function index() {
      if (all) return Promise.resolve(all);
      if (pending) return pending;
      pending = fetch('/intelligence/timeline-index.json', { cache: 'no-cache' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (j) { all = j.incidents || []; return all; });
      return pending;
    }

    function yearOf(r) { return (r.b || '').slice(0, 4) || 'Undated'; }

    function matches(r) {
      return (curYear === 'all' || yearOf(r) === curYear) &&
             (curCloud === 'all' || r.c === curCloud);
    }

    function counts() {
      if (!all) return;
      [].forEach.call(yrs.querySelectorAll('.pm-yr'), function (b) {
        var y = b.getAttribute('data-yr');
        var n = all.filter(function (r) {
          return (y === 'all' || yearOf(r) === y) &&
                 (curCloud === 'all' || r.c === curCloud);
        }).length;
        var sp = b.querySelector('.pm-yn'); if (sp) sp.textContent = n;
        b.classList.toggle('is-empty', n === 0);
      });
      if (!cls) return;
      [].forEach.call(cls.querySelectorAll('.pm-cl'), function (b) {
        var c = b.getAttribute('data-cl');
        var n = all.filter(function (r) {
          return (curYear === 'all' || yearOf(r) === curYear) &&
                 (c === 'all' || r.c === c);
        }).length;
        var sp = b.querySelector('.pm-yn'); if (sp) sp.textContent = n;
        b.classList.toggle('is-empty', n === 0);
      });
    }

    // A single year can hold 350 incidents. Rendering all of them is the wall
    // this section was rebuilt to avoid, so it pages.
    var PAGE = 60, shownCount = PAGE;

    function render() {
      var rows = all.filter(matches);
      var none = document.querySelector('.pm-none');
      if (none) {
        none.hidden = rows.length !== 0;
        var earliest = {};
        (all || []).forEach(function (r) {
          if (!r.b) return;
          if (!earliest[r.c] || r.b < earliest[r.c]) earliest[r.c] = r.b;
        });
        var who = curCloud === 'all' ? '' : NAME[curCloud];
        var from = curCloud !== 'all' && earliest[curCloud]
                 ? earliest[curCloud].slice(0, 4) : null;
        none.textContent = rows.length ? '' :
          (who ? who + ' has nothing recorded for ' + curYear +
                 (from ? '. Its published history starts in ' + from +
                         ' — anything earlier is not something it publishes.' : '.')
               : 'Nothing recorded for ' +
                 (curYear === 'all' ? 'any year' : curYear) + '.');
      }
      var html = rows.slice(0, shownCount).map(function (r) {
        return '<button class="pm-card ' + esc(r.c) + '" data-inc-id="' +
          esc(r.c + '|' + (r.i || '')) + '" type="button">' +
          '<span class="pm-c-cloud">' + esc(NAME[r.c] || r.c) + '</span>' +
          '<span class="pm-c-title">' + esc(r.t) + '</span>' +
          '<span class="pm-c-shape">' + esc(r.b || 'undated') +
          (r.w ? ' · full report' : '') + '</span></button>';
      }).join('');
      if (rows.length > shownCount) {
        html += '<button class="pm-more" type="button">Show ' +
                Math.min(PAGE, rows.length - shownCount) + ' more of ' +
                (rows.length - shownCount) + '</button>';
      }
      list.innerHTML = html;
      counts();
    }

    function refresh() { shownCount = PAGE; index().then(render); }

    yrs.addEventListener('click', function (ev) {
      var b = ev.target.closest ? ev.target.closest('.pm-yr') : null;
      if (!b) return;
      curYear = b.getAttribute('data-yr');
      [].forEach.call(yrs.querySelectorAll('.pm-yr'), function (x) {
        x.classList.toggle('is-on', x === b);
      });
      refresh();
    });

    if (cls) {
      cls.addEventListener('click', function (ev) {
        var b = ev.target.closest ? ev.target.closest('.pm-cl') : null;
        if (!b) return;
        curCloud = b.getAttribute('data-cl');
        [].forEach.call(cls.querySelectorAll('.pm-cl'), function (x) {
          x.classList.toggle('is-on', x === b);
        });
        refresh();
      });
    }

    list.addEventListener('click', function (ev) {
      if (ev.target.classList && ev.target.classList.contains('pm-more')) {
        shownCount += PAGE;
        render();
      }
    });

    /* Opening a card shows the vendor's full text when there is one, and the
     * record itself when there is not. Which of the two it is gets said out
     * loud: "they wrote four thousand words about this" and "they logged a
     * line" are different facts, and a reader choosing what to open deserves
     * to know which they are getting. */
    document.addEventListener('click', function (ev) {
      var card = ev.target.closest ? ev.target.closest('[data-inc-id]') : null;
      if (!card) return;
      ev.preventDefault();
      var parts = card.getAttribute('data-inc-id').split('|');
      var cloud = parts[0], id = parts.slice(1).join('|');
      var rec = (all || []).filter(function (r) {
        return r.c === cloud && (r.i || '') === id;
      })[0];
      if (!rec) return;

      lastFocus = document.activeElement;
      body.innerHTML = '<p class="pm-loading">Loading…</p>';
      if (typeof dlg.showModal === 'function') dlg.showModal();
      else dlg.setAttribute('open', '');

      var v = VEND[cloud] || cloud;

      function shell(inner) {
        body.innerHTML =
          '<p class="pm-meta"><span class="chip ' + esc(cloud) + '">' +
          esc(NAME[cloud]) + '</span><span class="pm-date">' +
          esc(rec.b || 'date not stated') + '</span></p>' +
          '<h3 id="pm-title">' + esc(rec.t) + '</h3>' + inner +
          (rec.u ? '<p class="pm-src"><a href="' + esc(rec.u) +
                   '" target="_blank" rel="noopener">Read it on ' + esc(v) +
                   '’s site →</a></p>' : '');
        body.scrollTop = 0;
      }

      if (!rec.w) {
        shell('<p class="pm-shape">' + esc(v) +
              ' recorded this outage but did not publish a full report on it. ' +
              'What they logged: it ran ' + esc(rec.b || 'on an unstated date') +
              (rec.e && rec.e !== rec.b ? ' to ' + esc(rec.e) : '') +
              '. Their page for it is linked below.</p>');
        return;
      }

      (writeups ? Promise.resolve(writeups)
                : fetch('/intelligence/postmortems.json', { cache: 'no-cache' })
                    .then(function (r) { return r.json(); })
                    .then(function (j) { writeups = j.postmortems || []; return writeups; })
      ).then(function (ws) {
        var w = ws.filter(function (x) {
          return x.cloud === cloud && x.id === id;
        })[0];
        if (!w) { shell(''); return; }
        var main = (w.sections && w.sections.length)
          ? w.sections.map(function (sec) {
              return '<section class="pm-sec"><h4>' + esc(sec.heading) + '</h4>' +
                     paras(sec.text) + '</section>';
            }).join('')
          : '<p class="pm-shape">Published as a narrative summary, with no ' +
            'headings of its own.</p>' + paras(w.body);
        shell(main);
      }).catch(function (e) {
        shell('<p class="pm-shape">Could not load the write-up (' +
              esc(e.message) + ').</p>');
      });
    });

    refresh();
  }
})();
