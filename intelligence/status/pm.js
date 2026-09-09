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
  /* The outage map.
   *
   * A bar chart of region names told you which regions appeared most often and
   * nothing about where they are, which is the one thing a reader has an
   * intuition for: cloud regions are places, and "us-east-1 again" means
   * something different once you can see how much of the world is downstream
   * of Northern Virginia.
   *
   * Positions are the regions' own published locations, at city resolution,
   * which is what the vendors themselves publish. No datacentre is pinpointed.
   *
   * The day/night band is computed, not decorated. The subsolar point is
   * derived from the current UTC time, so the lit half of the map is really
   * the lit half of the earth right now -- and the regions sitting in
   * darkness are the ones whose on-call engineers are asleep, which is the
   * detail that makes an outage map worth looking at rather than pretty.
   */
  var mapHost = document.getElementById('outage-map');
  if (mapHost) {
    var W = 720, H = 360;               // 2:1, equirectangular
    var mapIdx = null, mapPending = null, world = null;
    var mapCloud = '', mapFoot = [], mapRegions = null;
    // The archive has its own copy; this block is a separate scope.
    var CLOUD = { aws: 'AWS', azure: 'Azure', gcp: 'Google Cloud' };
    var mapLive = [], placeOf = {}, footMeta = null;

    // Where a region code sits, from whichever feed knows. The footprint is
    // authoritative -- it is the vendors' own region list -- and the incident
    // index fills in codes the footprint has retired.
    function coordOf(code) {
      if (!code) return null;
      return placeOf[code] || placeOf[String(code).toLowerCase()] || null;
    }

    function proj(lat, lon) {
      return [(lon + 180) / 360 * W, (90 - lat) / 180 * H];
    }

    // Solar declination and the subsolar longitude, from UTC. Standard
    // low-precision formulae -- good to a fraction of a degree, which is far
    // finer than a dot on a 720px map.
    function sun(now) {
      var start = Date.UTC(now.getUTCFullYear(), 0, 0);
      var day = (now - start) / 86400000;
      var g = (357.529 + 0.98560028 * day) * Math.PI / 180;
      var q = 280.459 + 0.98564736 * day;
      var L = (q + 1.915 * Math.sin(g) + 0.020 * Math.sin(2 * g)) * Math.PI / 180;
      var e = 23.439 * Math.PI / 180;
      var dec = Math.asin(Math.sin(e) * Math.sin(L)) * 180 / Math.PI;
      var utcHours = now.getUTCHours() + now.getUTCMinutes() / 60;
      var subLon = -15 * (utcHours - 12);
      return { dec: dec, lon: subLon };
    }

    // One key swatch: an 18x18 window onto the same shapes the map draws.
    function swatch(inner) {
      return '<svg class="om-sw" viewBox="0 0 18 18" aria-hidden="true">' +
             inner + '</svg>';
    }

    // A filled slice, for the vendor split inside each dot.
    function wedge(cx, cy, r, a0, a1) {
      var p0 = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)];
      var p1 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
      return 'M' + cx.toFixed(2) + ',' + cy.toFixed(2) +
             'L' + p0[0].toFixed(2) + ',' + p0[1].toFixed(2) +
             'A' + r.toFixed(2) + ',' + r.toFixed(2) + ' 0 ' +
             (a1 - a0 > Math.PI ? 1 : 0) + ' 1 ' +
             p1[0].toFixed(2) + ',' + p1[1].toFixed(2) + 'Z';
    }

    // A slice of a ring, for the vendor collar around each light.
    function arc(cx, cy, r, a0, a1) {
      var p0 = [cx + r * Math.cos(a0), cy + r * Math.sin(a0)];
      var p1 = [cx + r * Math.cos(a1), cy + r * Math.sin(a1)];
      return 'M' + p0[0].toFixed(2) + ',' + p0[1].toFixed(2) +
             'A' + r.toFixed(2) + ',' + r.toFixed(2) + ' 0 ' +
             (a1 - a0 > Math.PI ? 1 : 0) + ' 1 ' +
             p1[0].toFixed(2) + ',' + p1[1].toFixed(2);
    }

    function graticule() {
      var g = '';
      for (var lon = -150; lon <= 150; lon += 30) {
        var x = proj(0, lon)[0].toFixed(1);
        g += '<line x1="' + x + '" y1="0" x2="' + x + '" y2="' + H + '"/>';
      }
      for (var lat = -60; lat <= 60; lat += 30) {
        var y = proj(lat, 0)[1].toFixed(1);
        g += '<line x1="0" y1="' + y + '" x2="' + W + '" y2="' + y + '"/>';
      }
      return g;
    }

    /* Local time at one place, rather than a shape across the whole map.
     *
     * This started as a filled terminator, which was an arch cutting the
     * continents in half, and became a glow on every dot in darkness, which
     * was quieter but no more use: "33 lights are dark" is not a fact anyone
     * can do anything with, and it competed with the four encodings that
     * carry the actual subject.
     *
     * What is worth knowing is local and specific -- it is four in the
     * morning in Sydney, so somebody was woken up for this -- so it is said
     * on the one light you are pointing at, and nowhere else.
     */
    function isDay(lat, lon, s) {
      var ha = (lon - s.lon) * Math.PI / 180;
      var d = s.dec * Math.PI / 180, p = lat * Math.PI / 180;
      // Solar elevation: positive is above the horizon.
      return Math.sin(p) * Math.sin(d) + Math.cos(p) * Math.cos(d) * Math.cos(ha) > 0;
    }

    // The hour at a longitude, to the nearest minute. This is solar time, not
    // the civil clock -- a country's legal timezone can sit an hour or two off
    // its meridian, and there is no per-region timezone in anything the
    // vendors publish. It is close enough to answer "is it the middle of the
    // night there", which is the only question being asked of it, and it is
    // labelled as approximate rather than dressed up as a clock reading.
    function localClock(lon) {
      var mins = (Date.now() / 60000) + lon * 4;
      var h = ((Math.floor(mins / 60) % 24) + 24) % 24;
      var m = ((Math.floor(mins) % 60) + 60) % 60;
      return (h < 10 ? '0' : '') + h + ':' + (m < 10 ? '0' : '') + m;
    }

    /* One light per place.
     *
     * The map used to draw only regions that had broken, which answered
     * "where did it fail" and left out the question underneath it: how much
     * cloud is there, and how much of it is fine. A dot on Virginia means
     * little until you can see it is one of a hundred-odd places.
     *
     * So every region the three clouds run today is a point of light, and the
     * ones that have had incidents burn in their vendor's colour on top. It
     * reads as a night-lights photograph of the earth where the lights happen
     * to be datacentres -- which is close to literally true, and is why the
     * day/night fact needs no arch drawn across the continents any more:
     * lights show at night. A place in darkness glows; a place in daylight is
     * a plain point, washed out the way a city is at noon.
     */
    function draw(regions, footprint, only, live) {
      // How old the region list is, in the reader's words rather than an
      // ISO timestamp. A footprint refreshed daily is worth trusting; one
      // that quietly stopped refreshing is worth knowing about, and the
      // only way to tell the two apart is to print it.
      var footAge = '', footStale = false;
      if (footMeta && footMeta.updated) {
        var days = Math.floor((Date.now() - Date.parse(footMeta.updated)) / 86400000);
        footAge = days <= 0 ? 'today'
                : days === 1 ? 'yesterday'
                : days + ' days ago';
        // Past three days the daily refresh has missed more than once, and a
        // reader should not have to open the explainer to find that out.
        footStale = days > 3;
      }
      // Merge everything that shares a location.
      //
      // us-east-1 and us-east4 are both Northern Virginia; West Europe and
      // europe-west4 are both Amsterdam. Different regions, same point on a
      // map -- drawn separately they produced dots at identical coordinates
      // that no amount of shrinking could separate. One light per place,
      // carrying every region there; the click still lists them individually.
      var byPlace = {};
      function at(p) {
        var k = p[0] + ',' + p[1];
        if (!byPlace[k]) {
          byPlace[k] = { p: p, n: 0, all: 0, by: {}, regions: [], live: [],
                         clouds: {}, live_now: [] };
        }
        return byPlace[k];
      }
      // Tier one: the footprint. Every region the vendors run today.
      (footprint || []).filter(function (r) {
        return r.p && (!only || r.cloud === only);
      }).forEach(function (r) {
        var g = at(r.p);
        g.live.push(r);
        g.clouds[r.cloud] = (g.clouds[r.cloud] || 0) + 1;
      });
      // Tier two: the ones that have broken. Under a filter, a place is
      // sized by that vendor's incidents alone -- otherwise picking "AWS"
      // would still show a light swollen by Google's record.
      regions.filter(function (r) {
        return r.p && (!only || (r.by[only] || (r.by90 || {})[only]));
      }).forEach(function (r) {
        var g = at(r.p);
        // n is the 90-day count, which is what sizes the light; all is the
        // whole record, which is context in the tooltip and nothing more.
        g.n += only ? ((r.by90 || {})[only] || 0) : (r.n90 || 0);
        g.all += only ? (r.by[only] || 0) : r.n;
        g.regions.push(r.r);
        Object.keys(r.by).forEach(function (c) {
          if (!only || c === only) g.by[c] = (g.by[c] || 0) + r.by[c];
        });
      });
      /* Tier three: what is broken right now.
       *
       * The lights were a record of what had happened, which made the map a
       * history and not a status board -- the page it sits on is called Cloud
       * Status, and an outage in progress was the one thing it could not
       * show. The live feed names a region_code per open incident, so an
       * affected place can be found exactly rather than inferred, and it
       * pulses until the vendor closes it.
       */
      (live || []).forEach(function (i) {
        if (only && i.cloud !== only) return;
        var pt = coordOf(i.region_code) || coordOf(i.region);
        if (!pt) return;
        var g = at(pt);
        g.live_now.push(i);
      });
      var placed = Object.keys(byPlace).map(function (k) { return byPlace[k]; })
                         .sort(function (a, b) { return b.n - a.n; });
      // Fold together places closer than a light is wide.
      //
      // The shrink-to-fit pass below caps each light at half the distance to
      // its neighbour, but it also has a floor: below about 1.3px a light
      // stops being findable. Where two cities sit within a couple of pixels
      // of each other the floor wins and they overlap regardless. At this
      // scale they are the same point on the map, so they become one light
      // carrying both -- which is the same treatment two regions in one city
      // already get, applied one step out.
      var merged = [];
      placed.forEach(function (r) {
        var xy = proj(r.p[0], r.p[1]);
        for (var i = 0; i < merged.length; i++) {
          var m = merged[i], mxy = proj(m.p[0], m.p[1]);
          if (Math.hypot(xy[0] - mxy[0], xy[1] - mxy[1]) < 3.2) {
            m.n += r.n;
            m.all += r.all;
            m.regions = m.regions.concat(r.regions);
            m.live = m.live.concat(r.live);
            m.live_now = m.live_now.concat(r.live_now);
            Object.keys(r.by).forEach(function (c) { m.by[c] = (m.by[c] || 0) + r.by[c]; });
            Object.keys(r.clouds).forEach(function (c) {
              m.clouds[c] = (m.clouds[c] || 0) + r.clouds[c];
            });
            return;
          }
        }
        merged.push(r);
      });
      placed = merged.sort(function (a, b) { return b.n - a.n; });
      var unplaced = (footprint || []).filter(function (r) { return !r.p; });
      var most = Math.max.apply(null, placed.map(function (r) { return r.n; }).concat([1]));
      var s = sun(new Date());

      // Size each light, then shrink it until it cannot touch its neighbour.
      //
      // The European places sit within a few pixels of one another, so at full
      // size they merged into blobs and a reader could not tell three
      // incidents from one. The radius is capped at half the distance to the
      // nearest other light, which keeps every position exactly where the
      // region is: the light gets smaller, it never moves.
      var taken = placed.map(function (r) {
        var xy = proj(r.p[0], r.p[1]);
        // A place with nothing recorded against it is still a light, just a
        // quiet one, scaled by how many regions sit there.
        // A pie needs to be wide enough for its widest split to read, so
        // the floor is higher than it was for a plain dot.
        var want = r.n ? 2.8 + 7.2 * Math.sqrt(r.n / most)
                       : 2.2 + 0.45 * Math.min(r.live.length, 4);
        // Something broken right now outranks the history: never shrink it
        // below a size a reader will notice.
        if (r.live_now.length) want = Math.max(want, 4.2);
        return { x: xy[0], y: xy[1], want: want, r: 0 };
      });
      taken.forEach(function (a, i) {
        var room = Infinity;
        taken.forEach(function (b, j) {
          if (i === j) return;
          var d = Math.hypot(a.x - b.x, a.y - b.y);
          if (d < room) room = d;
        });
        // A little air between neighbours, and never smaller than findable.
        a.r = Math.max(placed[i].live_now.length ? 3.6 : 1.9,
                       Math.min(a.want, room / 2 - 0.4));
      });

      // Move a country label clear of the lights rather than dropping it.
      //
      // Hiding on collision cost the United States its name -- the Iowa
      // cluster sits right on the label anchor -- and losing the biggest
      // country on the map is worse than a couple of pixels of overlap.
      function hits(x, y) {
        return taken.some(function (t) {
          return Math.abs(t.x - x) < (t.r + 14) && Math.abs(t.y - y) < (t.r + 5);
        });
      }
      // Labels already placed, so a name can also avoid its neighbours.
      var lbls = [];
      function clash(x, y, w) {
        return lbls.some(function (l) {
          return Math.abs(l.x - x) < (l.w + w) / 2 + 1 && Math.abs(l.y - y) < 5;
        });
      }
      function nudge(c, w) {
        w = w || 0;
        if (!hits(c[0], c[1]) && !clash(c[0], c[1], w)) return c[1];
        for (var d = 5; d <= 26; d += 3) {
          if (c[1] - d > 8 && !hits(c[0], c[1] - d) && !clash(c[0], c[1] - d, w)) {
            return c[1] - d;
          }
          if (c[1] + d < H - 6 && !hits(c[0], c[1] + d) && !clash(c[0], c[1] + d, w)) {
            return c[1] + d;
          }
        }
        return null;
      }

      var liveCount = placed.reduce(function (a, r) { return a + r.live_now.length; }, 0);
      placed.forEach(function (r) {
        r.keys = r.live.length
          ? r.live.map(function (x) { return x.cloud + ':' + x.code; })
          : r.regions;
      });
      var dots = placed.map(function (r, i) {
        var xy = proj(r.p[0], r.p[1]);
        var rad = taken[i].r;
        var day = isDay(r.p[0], r.p[1], s);
        /* What colour a light is allowed to be.
         *
         * Tinting each place for whichever vendor had the most incidents
         * there turned the map green: Google's published history reaches
         * furthest back, so it wins that count almost everywhere, and the
         * map read as "Google breaks the most" when what it measured was
         * who discloses the most. That is the same trap the timeline had,
         * in visual form.
         *
         * So with no filter on, a light that has broken is simply lit --
         * one colour, no vendor named, size carrying the only claim the
         * data supports. Pick a cloud and the tint becomes honest, because
         * then every light on the map is that vendor's.
         */
        var cloud = only ? only : (r.n ? 'om-flare' : '');
        var here = r.live.length ? r.live.map(function (x) { return x.code; }) : r.regions;
        // cloud:code, because two clouds use some of the same codes.
        var keys = r.live.length
          ? r.live.map(function (x) { return x.cloud + ':' + x.code; })
          : r.regions;
        r.keys = keys;                 // the alert strip reuses these
        var name = (r.live[0] && r.live[0].name) || here.join(' · ');
        var label = here.join(' · ') + (r.n
          ? ' — ' + r.n + ' incident' + (r.n === 1 ? '' : 's') + ' in 90 days'
          : ' — nothing in 90 days') +
          (r.all ? ', ' + r.all + ' on record' : '') +
          (r.live_now.length ? '\n' + r.live_now.length + ' open right now'
                             : '') +
          '\nabout ' + localClock(r.p[1]) + ' there, ' +
          (day ? 'daytime' : 'the middle of the night');
        /* The dot IS the vendor split.
         *
         * This began as a grey core with a thin coloured ring around it,
         * which meant a place with nothing recorded against it was a grey
         * dot -- the cloud colours only showed up as a hairline, and on most
         * of the map the mark carried no vendor identity at all.
         *
         * So the dot is now a pie of the clouds that run a region there:
         * one wedge is a single-cloud town, three wedges is Northern
         * Virginia. Cloud colour is on every dot on the map, always, and it
         * is still saying something true -- presence is a fact each vendor
         * publishes, so unlike incident counts it can be coloured per vendor
         * without implying a ranking.
         *
         * That frees the incident count to be carried by size, plus a bright
         * ring on the places that actually broke.
         */
        var vendors = Object.keys(r.clouds).sort();
        var pie = '';
        if (vendors.length) {
          var step = (Math.PI * 2) / vendors.length;
          var gap = vendors.length > 1 ? 0.05 : 0;
          pie = '<g class="om-pie">' + vendors.map(function (v, k) {
            return '<path class="' + esc(v) + '" d="' +
                   wedge(xy[0], xy[1], rad,
                         -Math.PI / 2 + k * step + gap / 2,
                         -Math.PI / 2 + (k + 1) * step - gap / 2) + '"/>';
          }).join('') + '</g>';
        } else {
          // A place known only from an incident, with no live region behind
          // it. Rare, and it still gets a mark rather than vanishing.
          pie = '<circle class="om-orphan" cx="' + xy[0].toFixed(1) + '" cy="' +
                xy[1].toFixed(1) + '" r="' + rad.toFixed(1) + '"/>';
        }
        return '<g class="om-dot ' + (r.n ? esc(cloud) : 'om-quiet') +
               (r.live_now.length ? ' is-live' : '') +
               '" data-region="' + esc(keys.join('|')) + '" tabindex="0" role="button" ' +
               'aria-label="' + esc(here.join(', ')) + ', ' +
               (r.live_now.length ? r.live_now.length + ' open now, ' : '') +
               (r.n ? r.n + ' incidents in 90 days' : 'nothing in 90 days') + ', ' +
               vendors.map(function (v) { return CLOUD[v]; }).join(' and ') +
               ', about ' + localClock(r.p[1]) + ' local, ' +
               (day ? 'daytime' : 'night') + '">' +
               (r.live_now.length
                 ? '<circle class="om-pulse" cx="' + xy[0].toFixed(1) + '" cy="' +
                   xy[1].toFixed(1) + '" r="' + (rad + 5).toFixed(1) + '"/>' +
                   '<circle class="om-pulse om-pulse-b" cx="' + xy[0].toFixed(1) +
                   '" cy="' + xy[1].toFixed(1) + '" r="' + (rad + 5).toFixed(1) + '"/>'
                 : '') +
               pie +
               // The bright ring is "something broke here in 90 days". Size
               // already says how much; this says whether at all, which is
               // the difference a reader scans for first.
               (r.n
                 ? '<circle class="om-hit" cx="' + xy[0].toFixed(1) + '" cy="' +
                   xy[1].toFixed(1) + '" r="' + (rad + 2.2).toFixed(1) + '"/>'
                 : '') +
               '<circle class="om-halo" cx="' + xy[0].toFixed(1) + '" cy="' + xy[1].toFixed(1) +
               '" r="' + (rad + 4).toFixed(1) + '"><title>' + esc(name) + '\n' +
               esc(label) + '</title></circle></g>';
      }).join('');

      // Under a filter this has to be that vendor's count, not the total:
      // "160 regions of AWS" was three clouds' worth wearing one name.
      var sites = (footprint || []).filter(function (r) {
        return !only || r.cloud === only;
      }).length;
      var quiet = placed.filter(function (r) { return !r.n; }).length;
      /* A strip above the map, when something is open.
       *
       * The pulse says where, but only once you are already looking at the
       * map -- and the question "is anything broken right now" should be
       * answerable before the reader has found anything. So the open ones
       * are named in a row above the picture, each one a button that opens
       * the same dialog the dot does. Nothing renders here when nothing is
       * broken; an alarm that is always present is furniture.
       */
      var openPlaces = placed.filter(function (r) { return r.live_now.length; });
      var banner = '';
      if (openPlaces.length) {
        banner = '<div class="om-alert" role="status"><b>' +
          openPlaces.reduce(function (a, r) { return a + r.live_now.length; }, 0) +
          ' open right now</b>' +
          openPlaces.map(function (r) {
            var label = (r.live[0] && r.live[0].city) ||
                        (r.live[0] && r.live[0].name) || r.regions[0] || 'a region';
            var who = Object.keys(r.by).sort()[0] ||
                      (r.live_now[0] && r.live_now[0].cloud) || '';
            return '<button type="button" class="om-jump" data-region="' +
                   esc(r.keys.join('|')) + '">' +
                   (who ? '<i class="' + esc(who) + '"></i>' : '') +
                   esc(label) + '</button>';
          }).join('') + '</div>';
      }

      mapHost.innerHTML = banner +
        '<svg class="om-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" ' +
        'aria-label="World map of every AWS, Azure and Google Cloud region, ' +
        'with the ones that have had incidents lit in their vendor colour">' +
          '<defs>' +
          '</defs>' +
          '<rect class="om-sea" x="0" y="0" width="' + W + '" height="' + H + '"/>' +
          (world ? '<g class="om-land">' + world.countries.map(function (c) {
              return '<path d="' + c.d + '"/>'; }).join('') + '</g>' : '') +
          '<g class="om-grat">' + graticule() + '</g>' +
          (world ? '<g class="om-water">' + world.water.map(function (w) {
              // Same clamp the country names get: "Bering Sea" sits near the
              // dateline and was rendering as "ing Sea".
              var ww = w.n.length * (w.big ? 4.4 : 2.6);
              var x = Math.min(Math.max(w.c[0], ww / 2 + 2), W - ww / 2 - 2);
              return '<text x="' + x.toFixed(1) + '" y="' + w.c[1] + '" class="' +
                     (w.big ? 'om-ocean' : 'om-sea-lbl') + '">' + esc(w.n) + '</text>';
            }).join('') + '</g>' : '') +
          (world ? '<g class="om-names">' + world.countries.filter(function (c) {
              return c.n;
            }).map(function (c) {
              // Keep the whole label inside the frame. "NEW ZEALAND" and
              // "JAPAN" are centred on land near the edge, so half of each
              // ran off the map.
              var w = c.n.length * 3.4;
              var x = Math.min(Math.max(c.c[0], w / 2 + 2), W - w / 2 - 2);
              var y = nudge([x, c.c[1]], w);
              if (y === null) return '';      // no room anywhere: yield
              lbls.push({ x: x, y: y, w: w });
              return '<text x="' + x.toFixed(1) + '" y="' + y.toFixed(1) +
                     '">' + esc(c.n) + '</text>';
            }).join('') + '</g>' : '') +
          dots +
        '</svg>' +
        /* A caption, and the rest folded away.
         *
         * Everything the map encodes needed saying, and saying all of it
         * inline produced fifteen lines of prose under a picture whose whole
         * point was that it did not need explaining. The four facts a reader
         * needs to decode it fit in two sentences; the reasoning behind them
         * is worth keeping and is not worth the space, so it opens on demand.
         */
        '<p class="note-sm om-legend">' +
        '<b>' + sites + ' regions</b>' + (only ? ' of ' + CLOUD[only] : '') +
        ', from the vendors’ own live lists. Each dot is split into a wedge ' +
        'per cloud running a region there, so three wedges means all three are ' +
        'in that city. Size is incidents in the last 90 days and a ring means ' +
        'it broke in that window — ' + quiet + ' places had none. ' +
        (liveCount
          ? '<b class="om-k-live">' + liveCount + ' pulsing red</b> ' +
            (liveCount === 1 ? 'is' : 'are') + ' broken right now — click to ' +
            'open the vendor’s record. '
          : 'Nothing is broken right now. ') +
        'Hover or click one for what it is, and what time it is there. ' +
        (footStale
          ? '<b class="om-k-live">The region list has not refreshed in ' +
            footAge.replace(' ago', '') + ', so it may be missing a new ' +
            'region.</b>'
          : '') +
        '</p>' +
        /* A key, drawn in the same ink as the map.
         *
         * The caption says what the encodings mean in words, which works
         * once and then has to be re-read every visit. Four swatches drawn
         * with the same markup as the map itself are checked against the
         * picture rather than remembered -- and they are generated from the
         * live figures, so the key cannot drift from what is on screen.
         */
        '<ul class="om-key">' +
          '<li>' + swatch('<g class="om-pie">' +
            '<path class="aws" d="' + wedge(9, 9, 6, -1.571, 0.524) + '"/>' +
            '<path class="azure" d="' + wedge(9, 9, 6, 0.524, 2.618) + '"/>' +
            '<path class="gcp" d="' + wedge(9, 9, 6, 2.618, 4.712) + '"/></g>') +
            'a wedge per cloud running a region there</li>' +
          '<li>' + swatch('<g class="om-pie">' +
            '<path class="azure" d="' + wedge(5, 9, 2.4, 0, 6.28) + '"/>' +
            '<path class="azure" d="' + wedge(13, 9, 5.4, 0, 6.28) + '"/></g>') +
            'bigger means more incidents in 90 days</li>' +
          '<li>' + swatch('<g class="om-pie"><path class="gcp" d="' +
            wedge(9, 9, 3.6, 0, 6.28) + '"/></g>' +
            '<circle class="om-hit" cx="9" cy="9" r="5.8"/>') +
            'ringed means it broke in that window</li>' +
          '<li>' + swatch('<g class="om-pie"><path class="aws" d="' +
            wedge(9, 9, 3.4, 0, 6.28) + '"/></g>' +
            '<circle class="om-key-live" cx="9" cy="9" r="6.4"/>') +
            'broken right now — click it</li>' +
        '</ul>' +
        '<details class="om-how"><summary>How this map is built</summary>' +
        '<p class="note-sm">' +
        (footAge
          ? 'The region list was last read from the three vendors <b>' + footAge +
            '</b>, and refreshes daily; what is broken right now comes from ' +
            'their live feeds and refreshes hourly. '
          : '') +
        ((footMeta && footMeta.stale && footMeta.stale.length)
          ? '<b>' + footMeta.stale.map(function (c) { return CLOUD[c] || c; })
              .join(' and ') + '</b> could not be re-read on that run, so those ' +
            'regions are the previous list rather than today’s — kept ' +
            'deliberately, because a list that silently shrank would look ' +
            'exactly like a complete one. '
          : '') +
        /* How complete this is, in numbers.
         *
         * "Trust it" is not something a page can assert; it is something a
         * reader decides after being told where the gaps are. So the
         * coverage is counted here and printed, and it moves on its own as
         * the vendors publish more.
         */
        (function () {
          var f = footprint || [];
          if (!f.length) return '';
          var withCity = f.filter(function (r) { return r.city; }).length;
          var withZone = f.filter(function (r) {
            return (r.zones && r.zones.length) || r.az === true || r.az === false;
          }).length;
          return 'Of ' + f.length + ' regions, <b>' + withCity + '</b> carry a ' +
                 'city their vendor states and <b>' + withZone + '</b> carry ' +
                 'zone information. The rest are named but not described by ' +
                 'the vendor — mostly the Jio, China and Government regions, ' +
                 'which are documented separately from the public ones. ';
        })() +
        'Positions are the cities the vendors themselves ' +
        'name for each region, not datacentres — several regions share one, ' +
        'so places with more than one region are drawn as a single light ' +
        'carrying all of them. The 90-day window is the same one the strip ' +
        'above uses, and it is the only span all three report alike: their ' +
        'published histories reach back different distances, so sizing a ' +
        'light on the whole record would show which vendor discloses most ' +
        'rather than which broke most. For the same reason the lights carry ' +
        'no vendor colour unless you pick one above; the ring can, because ' +
        'running a region somewhere is a fact all three publish. The local ' +
        'hour shown when you hover a light is solar time worked out from its ' +
        'longitude: nothing the vendors publish carries a timezone, and a ' +
        'country’s legal clock can sit an hour or two off its meridian, so ' +
        'it is close enough to tell you somebody was woken up and is not ' +
        'offered as a clock reading.' +
        (unplaced.length
          ? ' ' + unplaced.length + ' region' + (unplaced.length === 1 ? '' : 's') +
            ' publish no location and cannot be drawn, so they are named here ' +
            'rather than quietly left out: ' +
            unplaced.map(function (r) { return esc(r.code); }).join(', ') + '.'
          : '') +
        '</p></details>';
    }

    function loadMap() {
      if (mapIdx) return Promise.resolve(mapIdx);
      if (mapPending) return mapPending;
      mapPending = fetch('/intelligence/timeline-index.json', { cache: 'no-cache' })
        .then(function (r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
        .then(function (j) { mapIdx = j; return j; });
      return mapPending;
    }

    // The coastline is a separate small fetch so the map can draw without it
    // if that ever fails -- dots in the right places beat no map at all.
    Promise.all([
      loadMap(),
      fetch('/intelligence/status/world.json', { cache: 'force-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (w) { world = w; })
        .catch(function () { world = null; }),
      // The footprint is a separate fetch for the same reason as the
      // coastline: if the region list fails, the incident lights still draw.
      fetch('/intelligence/status/regions.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; }),
      // And what is broken right now. Same file the rest of the page reads,
      // so the map cannot disagree with the cards above it.
      fetch('/intelligence/status.json', { cache: 'no-cache' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .catch(function () { return null; })
    ]).then(function (res) {
      var j = res[0];
      mapFoot = (res[2] && res[2].regions) || [];
      footMeta = res[2] || null;
      mapRegions = j.regions || [];
      mapFoot.forEach(function (r) { if (r.p) placeOf[r.code] = r.p; });
      mapRegions.forEach(function (r) { if (r.p && !placeOf[r.r]) placeOf[r.r] = r.p; });
      var st = res[3];
      if (st && st.clouds) {
        Object.keys(st.clouds).forEach(function (c) {
          (st.clouds[c] || []).forEach(function (i) {
            mapLive.push({
              cloud: c, title: i.title || '', service: i.service || '',
              region: i.region || '', region_code: i.region_code || '',
              url: i.url || '', update: i.update || ''
            });
          });
        });
      }
      draw(mapRegions, mapFoot, mapCloud, mapLive);
      // Redraw periodically so the lit half does not go stale on a tab left
      // open. Cheap: it is one SVG rebuild against data already in memory.
      setInterval(function () {
        draw(mapRegions, mapFoot, mapCloud, mapLive);
      }, 15 * 60 * 1000);
    }).catch(function (e) {
      mapHost.innerHTML = '<p class="pm-loading">Could not load the map (' +
                          esc(e.message) + ').</p>';
    });

    var omCls = document.getElementById('om-clouds');
    if (omCls) {
      omCls.addEventListener('click', function (ev) {
        var b = ev.target.closest ? ev.target.closest('.pm-cl') : null;
        if (!b || !mapRegions) return;
        mapCloud = b.getAttribute('data-cl') === 'all' ? '' : b.getAttribute('data-cl');
        [].forEach.call(omCls.querySelectorAll('.pm-cl'), function (x) {
          x.classList.toggle('is-on', x === b);
        });
        draw(mapRegions, mapFoot, mapCloud, mapLive);
      });
    }

    // Clicking a region opens what happened there -- from the map, or from
    // the alert strip above it, which carries the same keys.
    mapHost.addEventListener('click', function (ev) {
      var jump = ev.target.closest ? ev.target.closest('.om-jump') : null;
      var g = jump || (ev.target.closest ? ev.target.closest('.om-dot') : null);
      if (!g || !mapIdx) return;
      var keys = g.getAttribute('data-region').split('|');
      // The bare code, for matching against incident titles and the index,
      // which are per-cloud already and never carry the prefix.
      var names = keys.map(function (k) {
        var i = k.indexOf(':');
        return i < 0 ? k : k.slice(i + 1);
      });
      var rows = (mapIdx.incidents || []).filter(function (r) {
        var hay = (r.t || '');
        return names.some(function (n) { return hay.indexOf(n) >= 0; });
      }).slice(0, 40);
      var total = (mapIdx.regions || []).filter(function (r) {
        return names.indexOf(r.r) >= 0;
      }).reduce(function (a, r) { return a + r.n; }, 0);
      var meta = { n: total };
      var name = names.join(' · ');
      lastFocus = document.activeElement;

      // Which cloud runs what here, which is the thing a single dot cannot
      // say. Grouped by vendor so "Northern Virginia has all three" reads at
      // a glance rather than as a list of codes.
      var here = mapFoot.filter(function (r) {
        return keys.indexOf(r.cloud + ':' + r.code) >= 0;
      });
      var byCloud = {};
      here.forEach(function (r) {
        (byCloud[r.cloud] = byCloud[r.cloud] || []).push(r);
      });
      var openNow = mapLive.filter(function (i) {
        return keys.indexOf(i.cloud + ':' + i.region_code) >= 0 ||
               keys.indexOf(i.cloud + ':' + i.region) >= 0;
      });

      var pt = here.length && here[0].p ? here[0].p : null;
      var when = pt ? localClock(pt[1]) : '';
      /* What is actually here.
       *
       * A dot used to open with a count of incidents and a list of region
       * codes, which answers a question nobody asked first. What a reader
       * wants on clicking a place is what is there: which city, which
       * country, whose regions, and how many zones -- "Mumbai: AWS, Azure
       * and Google, six regions between them".
       *
       * Every field here is the vendor's own words. Where one of them does
       * not publish something, this says so rather than filling the gap:
       * AWS states its zone counts only on a JavaScript-rendered page, and
       * Azure publishes whether a region has zones and never how many, so
       * neither gets a number invented for it.
       */
      // Every city in the cluster, not just the first.
      //
      // Places within a couple of pixels of each other are drawn as one dot,
      // and Mumbai and Pune are one of those pairs. Titling the dot "Mumbai"
      // while listing a Pune region underneath reads as a mistake even
      // though both lines are true, so the heading names both.
      var cities = [], countries = [], seenAt = {};
      here.forEach(function (r) {
        var at = r.p ? r.p.join(',') : r.code;
        if (r.city && !seenAt[at]) {
          seenAt[at] = 1;
          cities.push(r.city);
        }
        if (r.country && countries.indexOf(r.country) < 0) countries.push(r.country);
      });
      var city = cities.join(' · ');
      var where = [city, countries.join(' · ')].filter(Boolean).join(', ') || name;

      var html = '<p class="pm-meta"><span class="pm-date">' + esc(where) + '</span>' +
                 (when ? '<span class="pm-date">about ' + esc(when) +
                         ' there</span>' : '') + '</p>' +
                 '<h3 id="pm-title">' + esc(city || name) + '</h3>';

      if (Object.keys(byCloud).length) {
        var zoneNote = false;
        html += '<table class="om-reg"><tbody>' + Object.keys(byCloud).sort()
          .map(function (c) {
            return byCloud[c].map(function (r) {
              var z;
              if (r.zones && r.zones.length) {
                z = r.zones.length + ' zone' + (r.zones.length === 1 ? '' : 's');
              } else if (r.az === true) {
                z = 'has zones';               // Azure says whether, not how many
                zoneNote = true;
              } else if (r.az === false) {
                z = 'no zones';
                zoneNote = true;
              } else {
                z = '—';                      // AWS publishes nothing readable
                zoneNote = true;
              }
              return '<tr><td><span class="chip ' + esc(c) + '">' +
                     esc(CLOUD[c]) + '</span></td><td><code>' + esc(r.code) +
                     '</code></td><td>' + esc(r.city || '') + '</td>' +
                     '<td class="om-z">' + esc(z) + '</td></tr>';
            }).join('');
          }).join('') + '</tbody></table>' +
          (zoneNote
            ? '<p class="note-sm">Google names its zones, so those are counted. ' +
              'Azure publishes whether a region has availability zones and not ' +
              'how many. AWS publishes its counts only on a page this cannot ' +
              'read, so it is left blank rather than guessed at.</p>'
            : '');
      }
      if (openNow.length) {
        html += '<div class="om-open"><h4>Open right now</h4>' + openNow.map(function (i) {
          return '<section class="pm-sec"><p><strong>' + esc(i.title) + '</strong>' +
            (i.service ? ' — ' + esc(i.service) : '') + '</p>' +
            (i.update ? '<p class="pm-shape">' + esc(i.update.slice(0, 400)) + '</p>' : '') +
            (i.url ? '<p class="pm-src"><a href="' + esc(i.url) + '" target="_blank" ' +
                     'rel="noopener">' + esc(CLOUD[i.cloud]) +
                     '’s live record →</a></p>' : '') +
            '</section>';
        }).join('') + '</div>';
      }
      if (!rows.length) {
        html += '<p class="pm-shape">The region is named in the vendors’ own ' +
                'incident records, but not in a title this page can match back ' +
                'to an individual entry.</p>';
      }
      rows.forEach(function (r) {
        html += '<section class="pm-sec"><p><strong>' + esc(r.t) + '</strong></p>' +
          '<p class="pm-shape">' + esc(r.b || 'date not stated') + '</p>' +
          (r.u ? '<p class="pm-src"><a href="' + esc(r.u) + '" target="_blank" rel="noopener">Vendor’s record →</a></p>' : '') +
          '</section>';
      });
      body.innerHTML = html;
      body.scrollTop = 0;
      if (typeof dlg.showModal === 'function') dlg.showModal();
      else dlg.setAttribute('open', '');
    });
  }
})();
