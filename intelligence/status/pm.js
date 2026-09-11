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
  /* The archive's own cloud filter, by id.
   *
   * This used to be querySelector('.pm-cls'), which was unambiguous until the
   * map above grew a cloud filter built from the same chip markup. From then
   * on this matched the MAP's row -- it comes first in the document -- so the
   * archive's chips had no handler at all and clicking AWS or Azure under
   * Past outages did nothing, while the map's row quietly got a second
   * listener it was never meant to have.
   *
   * Reusing the class was right; reaching for it with querySelector was not.
   */
  var cls = document.getElementById('pm-clouds');
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
    // The regions the vendors publish but do not locate, under whichever cloud
    // filter is showing. The search reads this so it can tell "we have never
    // heard of that" apart from "we carry it and cannot place it".
    var mapUnplaced = [];
    // Every place name and region code the map can currently offer, rebuilt
    // whenever it redraws. What a reader sees is filtered out of this.
    var SUGGESTIONS = [];

    /* Whether the alarm is allowed to move, decided once.
     *
     * A reader who has asked their device for less motion gets none, and the
     * alarm falls back to a heavier static ring plus the strip above the map.
     * Everyone else gets the pulse -- drawn with SVG's own <animate> rather
     * than a CSS transform.
     *
     * That choice is not stylistic. The CSS version scaled the ring about its
     * own centre, which in SVG requires transform-box:fill-box, and that
     * landed in Safari only in 15.4. On an iPad a version behind, the ring
     * scaled about the viewBox origin instead and flew off the map -- which
     * from the reader's chair is indistinguishable from an alarm that does
     * not move at all, and it is exactly what was reported twice. SMIL needs
     * no transform-box, no transform-origin, and has worked in every Safari
     * that has ever shipped on an iPad.
     */
    var stillOnly = false;
    try {
      stillOnly = window.matchMedia &&
                  window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) { stillOnly = false; }

    // Where a region code sits, from whichever feed knows. The footprint is
    // authoritative -- it is the vendors' own region list -- and the incident
    // index fills in codes the footprint has retired.
    function coordOf(code) {
      if (!code) return null;
      return placeOf[code] || placeOf[String(code).toLowerCase()] || null;
    }

    /* Robinson. The same projection build_world_path.py draws the
     * coastlines with, and it has to be, or the dots land where the countries
     * are not.
     *
     * Mollweide was a true ellipse, and its meridians curve hard enough that
     * land near the left and right edges visibly leans -- Alaska, New Zealand,
     * the eastern edge of Russia. Geometrically correct, and it reads as a
     * mistake, which on a page arguing for its own trustworthiness is a real
     * cost.
     *
     * Robinson curves gently and its poles are lines rather than points, so
     * the high latitudes have room and nothing shears. It is neither
     * equal-area nor conformal: it was fitted by eye to look right, which is
     * exactly the job here. Nothing on this map is measured off the
     * projection -- dot size comes from incident counts, not from area.
     *
     * The definition is a table at every fifth parallel, interpolated
     * between: X is that parallel's length against the equator, Y its
     * distance from it. That is not an approximation of Robinson, it is what
     * Robinson is.
     */
    var ROB_X = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600,
                 0.9427, 0.9216, 0.8962, 0.8679, 0.8350, 0.7986, 0.7597,
                 0.7186, 0.6732, 0.6213, 0.5722, 0.5322];
    var ROB_Y = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720,
                 0.4340, 0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903,
                 0.8435, 0.8936, 0.9394, 0.9761, 1.0000];

    function proj(lat, lon) {
      var a = Math.min(Math.abs(lat), 90) / 5;
      var i = Math.min(Math.floor(a), 17);
      var t = a - i;
      var xf = ROB_X[i] + (ROB_X[i + 1] - ROB_X[i]) * t;
      var yf = ROB_Y[i] + (ROB_Y[i + 1] - ROB_Y[i]) * t;
      if (lat < 0) yf = -yf;
      return [W / 2 + (lon / 180) * xf * (W / 2), H / 2 - yf * (H / 2)];
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

    /* The expanding rings on a place that is broken right now.
     *
     * Two of them, half a cycle apart, so it reads as a repeating signal
     * rather than one blink that is easy to look past. Each is an <animate>
     * on the circle's own r and opacity: no transform, so nothing here
     * depends on transform-box, and it runs on Safari versions that predate
     * it by years.
     */
    function ping(xy, rad) {
      var x = xy[0].toFixed(1), y = xy[1].toFixed(1);
      var r0 = (rad + 1.5).toFixed(1), r1 = (rad + 13).toFixed(1);
      function ring(delay) {
        return '<circle class="om-pulse" cx="' + x + '" cy="' + y +
               '" r="' + r0 + '">' +
               (stillOnly
                 ? '<animate attributeName="opacity" values=".35;.95;.35" ' +
                   'dur="3.5s" repeatCount="indefinite"/>' :
                 '<animate attributeName="r" from="' + r0 + '" to="' + r1 +
                 '" dur="2.2s" begin="' + delay + '" repeatCount="indefinite"/>' +
                 '<animate attributeName="opacity" values="0;.95;0" ' +
                 'keyTimes="0;.15;1" dur="2.2s" begin="' + delay +
                 '" repeatCount="indefinite"/>' +
                 '<animate attributeName="stroke-width" values="2.6;.7" ' +
                 'dur="2.2s" begin="' + delay + '" repeatCount="indefinite"/>') +
               '</circle>';
      }
      // With motion off, one ring that stays put and breathes.
      //
      // The same call the diya on the front page already makes: Reduce Motion
      // asks for movement to stop, not for the thing to go out. An expanding
      // ring is movement across the screen and is exactly what the setting is
      // for; a slow opacity fade changes nothing's position and triggers
      // nothing, and without it "broken right now" and "broke last week" are
      // the same still red ring. Three and a half seconds, so it reads as
      // alive rather than as a blink.
      return stillOnly ? ring('0s') : ring('0s') + ring('1.1s');
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

    /* Curved graticule.
     *
     * On a rectangle these were two straight lines each; on an ellipse a
     * meridian is a curve and a parallel is a chord that stops at the
     * outline, so both are sampled and drawn as paths. Straight lines here
     * would cross the ocean outside the map, which is the tell that a
     * projection was changed and its grid was not.
     */
    function graticule() {
      var g = '', lon, lat, pts;
      for (lon = -150; lon <= 150; lon += 30) {
        pts = [];
        for (lat = -90; lat <= 90; lat += 3) pts.push(proj(lat, lon));
        g += '<path d="M' + pts.map(function (p) {
          return p[0].toFixed(1) + ',' + p[1].toFixed(1);
        }).join('L') + '"/>';
      }
      for (lat = -60; lat <= 60; lat += 30) {
        pts = [];
        for (lon = -180; lon <= 180; lon += 3) pts.push(proj(lat, lon));
        g += '<path d="M' + pts.map(function (p) {
          return p[0].toFixed(1) + ',' + p[1].toFixed(1);
        }).join('L') + '"/>';
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
      var unplaceable = [];
      (live || []).forEach(function (i) {
        if (only && i.cloud !== only) return;
        var pt = coordOf(i.region_code) || coordOf(i.region);
        if (!pt) {
          /* An open incident with nowhere to draw it.
           *
           * This used to `return` and the incident vanished -- no dot, no
           * banner, no mention anywhere on the page. That is the common case
           * for Azure, whose global services name no region at all: 33 of the
           * 79 incidents on file arrive with an empty region, so a worldwide
           * Front Door outage would have left this page looking perfectly
           * calm. It is also what a vendor renaming its regions looks like
           * from here.
           *
           * A map that quietly omits what it cannot draw is claiming a
           * completeness it does not have. It cannot be drawn, so it is said
           * instead.
           */
          unplaceable.push(i);
          return;
        }
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
      // The same regions, narrowed to the cloud on screen, for the search.
      mapUnplaced = unplaced.filter(function (r) {
        return !only || r.cloud === only;
      });
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
        /* The city and the country belong in the search text, not just the
         * vendor's name for the place.
         *
         * Azure calls Mumbai "West India" and Pune "Central India". The city
         * is only ever in our own record; it is never in the name Azure
         * publishes. So with Azure selected, searching "Mumbai" found nothing
         * -- while the identical search under AWS ("Asia Pacific (Mumbai)")
         * or Google ("Mumbai, India") worked, because both of those vendors
         * put the city in the region name themselves. Under All clouds it
         * also worked, because AWS's name won the tie. It looked like Azure
         * had no Mumbai region. Azure has two.
         *
         * A reader searches for the city they know, not the name a vendor
         * chose for it.
         */
        var cities = [], alsoKnown = [];
        r.live.forEach(function (x) {
          if (x.city && cities.indexOf(x.city) < 0 &&
              name.toLowerCase().indexOf(x.city.toLowerCase()) < 0) {
            cities.push(x.city);
          }
          // Every vendor's name for this place, not only the first one's.
          //
          // One dot can be four regions across three clouds, and only
          // the first one's name was reaching the search text. So with All
          // clouds selected, "East US" -- Azure's name for Northern Virginia --
          // found
          // nothing, because AWS's "US East (N. Virginia)" had won the tie. 81
          // searches failed that way, all of them for places plainly on the
          // map.
          [x.name, x.country].forEach(function (w) {
            if (w && alsoKnown.indexOf(w) < 0) alsoKnown.push(w);
          });
        });
        if (cities.length) name += ' (' + cities.join(', ') + ')';
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
            // A single vendor is a whole circle, and a whole circle is NOT a
            // wedge from 0 to 2pi: the arc's start and end land on the same
            // point, so SVG draws the line to it and nothing else. Most
            // regions have one cloud, so most dots on the map rendered as a
            // vertical hairline pointing up from their own centre.
            if (vendors.length === 1) {
              return '<circle class="' + esc(v) + '" cx="' + xy[0].toFixed(2) +
                     '" cy="' + xy[1].toFixed(2) + '" r="' + rad.toFixed(2) + '"/>';
            }
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
               '" data-region="' + esc(keys.join('|')) +
               // One place name per code, in the same order as data-region.
               // A dot can cover two cities -- Mumbai and Pune merge into a
               // single light -- and labelling every code on it with the dot's
               // first name told the reader Azure's central-india is in
               // Mumbai. It is in Pune.
               '" data-at="' + esc((r.live.length
                 ? r.live.map(function (x) { return x.city || x.name || ''; })
                 : []).join('|')) +
               // The place in words as well as in codes. Without this a search
               // for "Mumbai" found nothing while "ap-south-1" found the dot --
               // and a reader looking for a city knows the city.
               '" data-place="' + esc(name + ' ' + label +
                 (alsoKnown.length ? '\n' + alsoKnown.join(' · ') : '')) +
               '" tabindex="0" role="button" ' +
               'aria-label="' + esc(here.join(', ')) + ', ' +
               (r.live_now.length ? r.live_now.length + ' open now, ' : '') +
               (r.n ? r.n + ' incidents in 90 days' : 'nothing in 90 days') + ', ' +
               vendors.map(function (v) { return CLOUD[v]; }).join(' and ') +
               ', about ' + localClock(r.p[1]) + ' local, ' +
               (day ? 'daytime' : 'night') + '">' +
               (r.live_now.length ? ping(xy, rad) : '') +
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
      if (openPlaces.length || unplaceable.length) {
        banner = '<div class="om-alert" role="status"><b>' +
          (openPlaces.reduce(function (a, r) { return a + r.live_now.length; }, 0)
           + unplaceable.length) +
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
          }).join('') +
          // Named, not drawn. The label says which cloud and admits there is
          // no region to point at, rather than implying the map is complete.
          unplaceable.map(function (i) {
            var what = i.region || i.region_code || 'no region stated';
            return '<button type="button" class="om-jump om-nowhere" ' +
                   'data-region="' + esc(i.cloud + ':' + (i.region_code || '')) +
                   '" title="' + esc(i.title || '') + '">' +
                   '<i class="' + esc(i.cloud) + '"></i>' +
                   esc(what) + '</button>';
          }).join('') + '</div>';
      }

      mapHost.innerHTML = banner +
        '<svg class="om-svg" viewBox="0 0 ' + W + ' ' + H + '" role="img" ' +
        'aria-label="World map of every AWS, Azure and Google Cloud region, ' +
        'with the ones that have had incidents lit in their vendor colour">' +
          '<defs>' +
          '</defs>' +
          /* The ocean traces the map's own outline. Robinson's edge is the
           * 180th meridian, which is a curve -- not an ellipse and not a box. */
          '<path class="om-sea" d="' + (function () {
            var pts = [], la;
            for (la = 90; la >= -90; la -= 3) pts.push(proj(la, 180));
            for (la = -90; la <= 90; la += 3) pts.push(proj(la, -180));
            return 'M' + pts.map(function (q) {
              return q[0].toFixed(1) + ',' + q[1].toFixed(1);
            }).join('L') + 'Z';
          })() + '"/>' +
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
            '<circle class="azure" cx="5" cy="9" r="2.4"/>' +
            '<circle class="azure" cx="13" cy="9" r="5.4"/></g>') +
            'bigger means more incidents in 90 days</li>' +
          '<li>' + swatch('<g class="om-pie"><circle class="gcp" cx="9" cy="9" r="3.6"/></g>' +
            '<circle class="om-hit" cx="9" cy="9" r="5.8"/>') +
            'dashed ring: it broke in that window</li>' +
          '<li>' + swatch('<g class="om-pie"><circle class="aws is-live-c" ' +
            'cx="9" cy="9" r="3.4"/></g>' +
            '<circle class="om-key-live" cx="9" cy="9" r="5.6"/>' +
            '<circle class="om-key-live" cx="9" cy="9" r="8.2" opacity=".35"/>') +
            'broken <b>right now</b> — click it</li>' +
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
      /* The coastlines, and a check that they were drawn the same way the
       * dots are placed.
       *
       * This was fetched with cache:'force-cache', which tells the browser to
       * use its stored copy without asking whether it changed. That was fine
       * while coastlines never moved. Changing the projection moved all of
       * them: pm.js is versioned so it updated to Mollweide, world.json was
       * not so it stayed equirectangular, and the result was dots computed one
       * way drawn over land drawn another -- regions out in the Indian Ocean.
       *
       * Two changes. It revalidates now, which costs a 304 and not a
       * download. And the file records which projection built it, so a
       * mismatch is caught rather than rendered: one forced refetch, and if
       * that still disagrees the coastlines are dropped entirely. Dots on an
       * empty field are obviously incomplete; dots on the wrong coastlines
       * look authoritative and are worse than nothing.
       */
      (function () {
        var WANT = 'robinson';
        function usable(w) {
          return w && typeof w.projection === 'string' &&
                 w.projection.indexOf(WANT) === 0;
        }
        return fetch('/intelligence/status/world.json')
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (w) {
            if (usable(w)) return w;
            return fetch('/intelligence/status/world.json', { cache: 'reload' })
              .then(function (r) { return r.ok ? r.json() : null; })
              .then(function (w2) { return usable(w2) ? w2 : null; });
          })
          .then(function (w) { world = w; })
          .catch(function () { world = null; });
      })(),
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
      // The suggestions are built FROM the dots, so they can only be filled
      // once the dots exist. Filling them where the search box is wired ran
      // before this line and produced an empty list -- the search worked and
      // suggested nothing, which is the shape of the problem it was added to
      // solve.
      if (window.__omFill) window.__omFill();
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
        if (window.__omFill) window.__omFill();
        if (window.__omApplyFind) window.__omApplyFind();
      });
    }

    /* Find one place among 159.
     *
     * Matching is against what the dot already carries: data-region holds the
     * vendors' region codes, and aria-label holds the city and country -- so
     * "eu-west-1", "Ireland" and "Dublin" all find the same dot without a
     * second index to keep in step with the first.
     *
     * Dimming, not hiding. Removing the other dots empties the map as you
     * type, and an empty map cannot show you where the match IS, which is the
     * only reason to use one rather than a list.
     */
    var omQ = document.getElementById('om-q');
    var omFound = document.getElementById('om-found');

    /* Suggestions, so nobody has to remember that Mumbai is ap-south-1.
     *
     * Built from the dots that are actually on the map, so a suggestion can
     * never offer a place the search would then fail to find. Each place is
     * offered TWICE over: once by its name and once by its region code,
     * because a reader arrives with one or the other -- someone who runs
     * things in eu-west-1 may not think "Ireland", and someone looking for
     * Ireland does not know eu-west-1.
     *
     * A native <datalist> rather than a hand-built dropdown: the browser's own
     * suggestion list is the one a phone keyboard, a screen reader and a
     * keyboard user all already know how to use, and it costs no code to keep
     * accessible.
     */
    function fillSuggestions() {
      var list = document.getElementById('om-sug');
      if (!list) return;
      SUGGESTIONS = [];
      /* Gather first, emit second.
       *
       * A region code is not unique across clouds: us-east-2 is Ohio to AWS
       * and Virginia to Azure. Emitting as we walked the dots meant whichever
       * dot came first claimed the code and the other was dropped, so the
       * suggestion for us-east-2 named one place and silently meant two.
       */
      var byName = {}, byCode = {};
      [].forEach.call(mapHost.querySelectorAll('.om-dot'), function (d) {
        var at = (d.getAttribute('data-at') || '').split('|');
        var names = at.filter(function (x) { return x && x.length <= 34; });
        (d.getAttribute('data-region') || '').split('|').forEach(function (k, i) {
          var bits = k.split(':');
          var cloud = bits.length > 1 ? bits[0] : '';
          var code = bits.length > 1 ? bits[1] : k;
          if (!code) return;
          var e = byCode[code.toLowerCase()] ||
                  (byCode[code.toLowerCase()] = { code: code, where: [] });
          // This region's own city, not the dot's first one.
          var says = ((CLOUD[cloud] ? CLOUD[cloud] + ' ' : '') +
                      (at[i] || names[0] || '')).trim();
          if (says && e.where.indexOf(says) < 0) e.where.push(says);

          // And the place, credited only to the clouds that are in it. A dot
          // covering Mumbai and Pune would otherwise have offered "Pune —
          // AWS · Azure · Google Cloud"; only Azure is in Pune.
          var place = at[i];
          if (!place || place.length > 34) return;
          var pk = place.toLowerCase();
          var p = byName[pk] || (byName[pk] = { name: place, clouds: [] });
          if (CLOUD[cloud] && p.clouds.indexOf(CLOUD[cloud]) < 0) {
            p.clouds.push(CLOUD[cloud]);
          }
        });
      });
      Object.keys(byName).sort().forEach(function (k) {
        var p = byName[k];
        SUGGESTIONS.push({ value: p.name, note: p.clouds.sort().join(' · ') });
      });
      Object.keys(byCode).sort().forEach(function (k) {
        var e = byCode[k];
        var label = e.where.join(' · ');
        if (label.length > 46) label = label.slice(0, 45) + '…';
        SUGGESTIONS.push({ value: e.code, note: label });
      });
    }

    if (omQ) {
      var applyFind = function () {
        var q = (omQ.value || '').trim().toLowerCase();
        var dots = mapHost.querySelectorAll('.om-dot');
        if (!q) {
          [].forEach.call(dots, function (d) { d.classList.remove('om-dim', 'om-match'); });
          mapHost.classList.remove('om-finding');
          if (omFound) omFound.textContent = '';
          return;
        }
        mapHost.classList.add('om-finding');
        var hits = 0;
        [].forEach.call(dots, function (d) {
          var hay = ((d.getAttribute('data-region') || '') + ' ' +
                     (d.getAttribute('data-place') || '') + ' ' +
                     (d.getAttribute('aria-label') || '')).toLowerCase();
          var on = hay.indexOf(q) >= 0;
          d.classList.toggle('om-match', on);
          d.classList.toggle('om-dim', !on);
          if (on) hits++;
        });
        if (omFound) {
          if (hits) {
            omFound.textContent = hits + (hits === 1 ? ' place' : ' places');
          } else {
            /* "We cannot draw it" is a different answer from "it does not
             * exist", and the reader deserves the one that is true.
             *
             * Twelve of the 159 regions publish no location -- GovCloud and
             * DoD, whose sites are deliberately unstated, and regions the
             * vendors have announced but not built. They are real, the site
             * carries them, and the map simply cannot place them. Answering
             * "nothing matches us-gov-east-1" said the opposite, in the same
             * confident tone as a genuine miss.
             */
            var typed = omQ.value.trim();
            var near = mapUnplaced.filter(function (r) {
              return ((r.code || '') + ' ' + (r.name || '') + ' ' +
                      (r.city || '') + ' ' + (r.country || '')
                     ).toLowerCase().indexOf(q) >= 0;
            });
            if (near.length === 1) {
              // Short enough to clear the floating buttons on a phone, where
              // the longer wording ran under the one at the right margin.
              omFound.textContent = near[0].code + ': ' +
                (CLOUD[near[0].cloud] || near[0].cloud) +
                ' publishes no location, so it is not on the map';
            } else if (near.length) {
              omFound.textContent = near.length +
                ' regions match, but none of them publish a location, so ' +
                'they are not on the map: ' +
                near.map(function (r) { return r.code; }).join(', ');
            } else {
              omFound.textContent = 'nothing matches ' + typed;
            }
          }
        }
      };
      omQ.addEventListener('input', applyFind);
      omQ.addEventListener('search', applyFind);
      // Redrawing replaces every dot, so the filter has to be put back --
      // otherwise switching cloud silently clears a search that is still
      // typed into the box.
      /* The suggestion list.
       *
       * This was a native <datalist>, chosen because the browser's own control
       * is the one a phone keyboard and a screen reader already understand.
       * That holds only where the browser draws it. Chrome on Android drew a
       * popup over the site header; Safari on iPad drew nothing at all, with
       * every suggestion sitting in the markup unreachable. A native control
       * cannot be positioned or styled, so neither was fixable.
       *
       * Built here it behaves the same everywhere. The cost is that everything
       * the native one did for free has to be done explicitly: arrow keys,
       * Enter, Escape, tap, and the combobox roles a screen reader needs.
       */
      var omSug = document.getElementById('om-sug');
      var omClear = document.getElementById('om-clear');
      var cursor = -1, shown = [];

      // The cross only exists while there is something to clear. Showing it on
      // an empty box would offer an action that does nothing.
      function paintClear() {
        if (omClear) omClear.hidden = !(omQ.value || '').length;
      }

      function closeSug() {
        if (!omSug) return;
        omSug.hidden = true;
        omSug.innerHTML = '';
        cursor = -1;
        shown = [];
        omQ.setAttribute('aria-expanded', 'false');
        omQ.removeAttribute('aria-activedescendant');
      }

      function paintCursor() {
        [].forEach.call(omSug.children, function (li, i) {
          var on = i === cursor;
          li.classList.toggle('on', on);
          li.setAttribute('aria-selected', on ? 'true' : 'false');
          if (on) {
            omQ.setAttribute('aria-activedescendant', li.id);
            // Keep the highlighted row in view when arrowing past the fold.
            if (li.offsetTop < omSug.scrollTop) omSug.scrollTop = li.offsetTop;
            else if (li.offsetTop + li.offsetHeight >
                     omSug.scrollTop + omSug.clientHeight) {
              omSug.scrollTop = li.offsetTop + li.offsetHeight - omSug.clientHeight;
            }
          }
        });
        if (cursor < 0) omQ.removeAttribute('aria-activedescendant');
      }

      function openSug() {
        if (!omSug) return;
        var q = (omQ.value || '').trim().toLowerCase();
        if (!q) return closeSug();
        // Matches that START with what was typed come first: someone typing
        // "us-e" wants us-east-1 before "Belgium (Google Cloud us-east...)".
        var starts = [], has = [];
        SUGGESTIONS.forEach(function (s) {
          var v = s.value.toLowerCase();
          if (v.indexOf(q) === 0) starts.push(s);
          else if (v.indexOf(q) >= 0 || (s.note || '').toLowerCase().indexOf(q) >= 0) {
            has.push(s);
          }
        });
        shown = starts.concat(has).slice(0, 8);
        if (!shown.length) return closeSug();
        omSug.innerHTML = shown.map(function (s, i) {
          return '<li id="om-sug-' + i + '" role="option" aria-selected="false">' +
                 '<span class="om-sug-v">' + esc(s.value) + '</span>' +
                 (s.note ? '<span class="om-sug-n">' + esc(s.note) + '</span>' : '') +
                 '</li>';
        }).join('');
        omSug.hidden = false;
        cursor = -1;
        omQ.setAttribute('aria-expanded', 'true');
        omQ.removeAttribute('aria-activedescendant');
      }

      function choose(i) {
        if (i < 0 || i >= shown.length) return;
        omQ.value = shown[i].value;
        closeSug();
        paintClear();
        applyFind();
      }

      omQ.addEventListener('input', openSug);
      omQ.addEventListener('focus', openSug);
      omQ.addEventListener('input', paintClear);

      if (omClear) {
        // pointerdown, not click: the input's blur handler closes the list, and
        // on a touch screen blur lands first, so by the time click arrives the
        // press has already been spent elsewhere.
        omClear.addEventListener('pointerdown', function (e) {
          e.preventDefault();
          omQ.value = '';
          closeSug();
          paintClear();
          applyFind();
          // Focus back in the box: clearing is almost always the first half of
          // typing something else.
          omQ.focus();
        });
      }

      omQ.addEventListener('keydown', function (e) {
        var open = omSug && !omSug.hidden;
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
          if (!open) { openSug(); return; }
          e.preventDefault();
          cursor += (e.key === 'ArrowDown' ? 1 : -1);
          if (cursor >= shown.length) cursor = 0;
          if (cursor < 0) cursor = shown.length - 1;
          paintCursor();
          return;
        }
        if (e.key === 'Enter' && open && cursor >= 0) {
          e.preventDefault();
          choose(cursor);
          return;
        }
        if (e.key === 'Escape') {
          // First Escape dismisses the list, second clears the box. Clearing
          // on the first would throw away a search the reader is still typing.
          //
          // preventDefault matters here and only in Chrome: on a type="search"
          // input it clears the field itself on Escape, so without this the
          // first press dismissed the list AND emptied the box. WebKit does
          // not, so the two engines disagreed about what one key did.
          if (open) { e.preventDefault(); closeSug(); return; }
          omQ.value = '';
          paintClear();
          applyFind();
        }
      });

      if (omSug) {
        // pointerdown, not click: click arrives after blur, and blur closes the
        // list, so by then the row being tapped no longer exists.
        omSug.addEventListener('pointerdown', function (e) {
          var li = e.target.closest ? e.target.closest('li') : null;
          if (!li) return;
          e.preventDefault();
          choose([].indexOf.call(omSug.children, li));
        });
        omSug.addEventListener('mousemove', function (e) {
          var li = e.target.closest ? e.target.closest('li') : null;
          if (!li) return;
          cursor = [].indexOf.call(omSug.children, li);
          paintCursor();
        });
      }
      omQ.addEventListener('blur', function () { setTimeout(closeSug, 120); });

      window.__omApplyFind = applyFind;
      window.__omFill = fillSuggestions;
      window.__omSug = { open: openSug, close: closeSug,
                         shown: function () { return shown; } };
    }

    /* Expanding the map.
     *
     * A fixed overlay rather than the Fullscreen API, because
     * Element.requestFullscreen is video-only in Safari on the iPhone: the
     * button would have worked on a desktop and an iPad and done nothing at
     * all on a phone. The same split that made the native suggestion list
     * useless on an iPad.
     *
     * Nothing is redrawn. The map is an SVG with a viewBox, so growing its
     * container is all that is needed -- and a redraw would reshuffle the
     * dot-collision pass and move lights the reader was looking at.
     */
    var omExpand = document.getElementById('om-expand');
    if (omExpand && mapHost) {
      var omBar = null, expandOpener = null, parked = [];

      /* The cloud chips and the region search come WITH the map.
       *
       * Otherwise choosing AWS means closing the expanded map, picking the
       * chip, and expanding again -- and the reason to expand is to study the
       * dots, which is exactly when filtering them matters most.
       *
       * The real controls are moved, not copied. A second set would be a
       * second set to keep in step, and this file has spent the last day
       * undoing copies that drifted. Moving a node keeps its listeners, so
       * everything already wired to these keeps working untouched.
       */
      function park(el) {
        if (!el) return;
        parked.push({ el: el, parent: el.parentNode, next: el.nextSibling });
        omBar.appendChild(el);
      }

      function unpark() {
        // In reverse, so each returns to a sibling that is already home.
        parked.slice().reverse().forEach(function (p) {
          if (p.next && p.next.parentNode === p.parent) {
            p.parent.insertBefore(p.el, p.next);
          } else {
            p.parent.appendChild(p.el);
          }
        });
        parked = [];
      }

      function shrinkMap() {
        unpark();
        mapHost.classList.remove('is-big');
        mapHost.style.paddingTop = '';
        document.body.style.overflow = '';
        omExpand.setAttribute('aria-expanded', 'false');
        omExpand.textContent = 'Expand the map';
        if (omBar) { omBar.remove(); omBar = null; }
        // Back to the button that opened it, or focus lands at the top of the
        // page and a keyboard reader walks down again.
        if (expandOpener && expandOpener.focus) {
          expandOpener.focus({ preventScroll: true });
        }
        expandOpener = null;
      }

      function growMap() {
        expandOpener = document.activeElement;
        mapHost.classList.add('is-big');
        document.body.style.overflow = 'hidden';
        omExpand.setAttribute('aria-expanded', 'true');
        omExpand.textContent = 'Close the map';

        omBar = document.createElement('div');
        omBar.className = 'om-big-bar';
        // Fixed to the viewport rather than placed inside the map, which
        // scrolls sideways -- a bar in there would slide off with Asia.
        document.body.appendChild(omBar);

        park(document.getElementById('om-clouds'));
        park(document.querySelector('.om-find'));

        var close = document.createElement('button');
        close.type = 'button';
        close.className = 'om-close';
        close.setAttribute('aria-label', 'Close the expanded map');
        close.innerHTML = '&times;';
        close.addEventListener('click', shrinkMap);
        omBar.appendChild(close);

        // However tall the bar turns out, the map starts below it. Measured
        // rather than guessed: the chips wrap to two rows on a narrow phone.
        mapHost.style.paddingTop = (omBar.offsetHeight + 8) + 'px';
        mapHost.setAttribute('tabindex', '-1');
        mapHost.focus({ preventScroll: true });
      }

      omExpand.addEventListener('click', function () {
        if (mapHost.classList.contains('is-big')) shrinkMap();
        else growMap();
      });
      document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && mapHost.classList.contains('is-big')) {
          shrinkMap();
        }
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
              } else if (r.az_n) {
                // AWS states a count without naming the zones.
                z = r.az_n + ' zone' + (r.az_n === 1 ? '' : 's');
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
              'AWS states a count without naming them, and each one is taken ' +
              'only where AWS’s own coordinate for the region agrees with ' +
              'the location held here — its page misplaces at least one ' +
              'region, so an unchecked number from it would be a confident ' +
              'wrong answer. Azure publishes whether a region has availability ' +
              'zones and never how many. A dash means nobody states it.</p>'
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
