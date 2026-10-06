/* The re:Invent planner — runs entirely in the reader's browser.
 * ---------------------------------------------------------------------------
 * There is no API behind this and no model. The whole catalogue is already
 * shipped to the page (2.0 MB raw, ~0.5 MB gzipped), so "plan my week around
 * these topics" is a scoring-and-scheduling problem over data the browser
 * already holds, not a question anybody needs to ask a language model.
 *
 * That is a correctness decision before it is a cost one. This site's rule is
 * that if a figure is on a page, something measured it. Every session code,
 * time, room and seat count below is read out of the store; nothing here can
 * invent a session that does not exist, state a room it is not in, or put it
 * at a time the catalogue does not carry. A generated plan is wrong in ways a
 * reader cannot check, and this page would be the one place on the site where
 * that was true.
 *
 * What it does, in order:
 *   1. score every session against the interests the reader ticked
 *   2. drop sponsored sessions, and collapse -R / -R1 repeats to one
 *   3. fill each day greedily by score, refusing any pick that cannot be
 *      reached from the previous one in the time between them
 *   4. anchor each day on whichever venue its best sessions cluster in,
 *      because the Strip is long and the content is not evenly spread
 */
(function () {
  'use strict';

  var STORE = '/intelligence/reinvent2026.json';

  /* Minutes between venues, and from a few hotels to each. Walking times on
   * the Strip, rounded up, with the shuttle assumed for MGM. These are
   * estimates and the page says so -- they are here to stop the planner
   * booking two sessions it is physically impossible to attend, which is a
   * job that tolerates being approximately right. */
  var VENUE_T = {
    'Caesars Forum|Caesars Palace': 12, 'Caesars Forum|Venetian': 15,
    'Caesars Forum|Wynn/Encore': 20, 'Caesars Forum|MGM Grand': 35,
    'Caesars Palace|Venetian': 20, 'Caesars Palace|Wynn/Encore': 25,
    'Caesars Palace|MGM Grand': 30, 'Venetian|Wynn/Encore': 12,
    'Venetian|MGM Grand': 35, 'Wynn/Encore|MGM Grand': 40
  };
  var HOTELS = {
    "Harrah's / LINQ":   {'Caesars Forum': 6, 'Venetian': 12, 'Caesars Palace': 12, 'Wynn/Encore': 18, 'MGM Grand': 35},
    'Venetian / Palazzo': {'Caesars Forum': 15, 'Venetian': 3, 'Caesars Palace': 20, 'Wynn/Encore': 12, 'MGM Grand': 35},
    'Caesars Palace':    {'Caesars Forum': 12, 'Venetian': 20, 'Caesars Palace': 3, 'Wynn/Encore': 25, 'MGM Grand': 30},
    'Wynn / Encore':     {'Caesars Forum': 20, 'Venetian': 12, 'Caesars Palace': 25, 'Wynn/Encore': 3, 'MGM Grand': 40},
    'MGM Grand':         {'Caesars Forum': 35, 'Venetian': 35, 'Caesars Palace': 30, 'Wynn/Encore': 40, 'MGM Grand': 3},
    'Aria / Vdara':      {'Caesars Forum': 22, 'Venetian': 25, 'Caesars Palace': 15, 'Wynn/Encore': 30, 'MGM Grand': 18},
    'Elsewhere':         {'Caesars Forum': 25, 'Venetian': 25, 'Caesars Palace': 25, 'Wynn/Encore': 30, 'MGM Grand': 30}
  };
  function travel(a, b) {
    if (a === b) { return 10; }
    return VENUE_T[a + '|' + b] || VENUE_T[b + '|' + a] || 30;
  }

  /* Interests. Each maps to facet values and to words worth matching in the
   * title and abstract, because the facets are coarse: "Cloud Operations"
   * covers both an AIOps chalk talk and a billing one. */
  var INTERESTS = [
    {k: 'ec2', label: 'EC2 &amp; fleet',
     sv: ['Amazon Elastic Compute Cloud (Amazon EC2)', 'Amazon EC2 Auto Scaling',
          'Amazon EC2 Spot', 'EC2 Image Builder', 'Amazon EC2 Linux',
          'Amazon EC2 - Graviton', 'AWS Systems Manager'],
     tp: ['Compute'], kw: ['ec2', 'fleet', 'instance', 'auto scaling', 'capacity',
          'graviton', 'spot', 'ami', 'patch', 'image builder']},
    {k: 'storage', label: 'EBS, snapshots &amp; storage',
     sv: ['Amazon Elastic Block Store (Amazon EBS)', 'AWS Backup'],
     tp: ['Storage'], kw: ['ebs', 'snapshot', 'volume', 'backup', 'storage']},
    {k: 'finops', label: 'Cost &amp; FinOps',
     sv: ['AWS Compute Optimizer', 'AWS Savings Plans', 'AWS Billing and Cost Management'],
     ai: ['Cost Optimization'], kw: ['finops', 'cost', 'savings plan', 'right-siz',
          'rightsiz', 'budget', 'billing', 'spend', 'price performance']},
    {k: 'obs', label: 'Observability &amp; monitoring',
     sv: ['Amazon CloudWatch', 'Amazon CloudWatch Logs'],
     ai: ['Monitoring & Observability'], tp: ['Cloud Operations'],
     kw: ['observab', 'monitor', 'telemetry', 'opentelemetry', 'anomaly', 'aiops']},
    {k: 'logs', label: 'Logs, audit &amp; compliance',
     sv: ['AWS CloudTrail', 'AWS Config', 'AWS Security Hub', 'AWS Organizations'],
     ai: ['Governance, Risk & Compliance'],
     kw: ['cloudtrail', 'security hub', 'audit', 'compliance', 'log', 'evidence', 'governance']},
    {k: 'sec', label: 'Security &amp; identity',
     sv: ['Amazon GuardDuty', 'Amazon Inspector'], tp: ['Security & Identity'],
     ai: ['Threat Detection & Incident Response', 'DevSecOps', 'Data Protection'],
     kw: ['security', 'threat', 'iam', 'permission', 'guardduty', 'encrypt']},
    {k: 'agents', label: 'AI agents &amp; Bedrock',
     sv: ['Amazon Bedrock'], ai: ['Agentic AI', 'Generative AI'],
     tp: ['Artificial Intelligence'], kw: ['agent', 'bedrock', 'agentcore', 'llm']},
    {k: 'devtools', label: 'Developer tools &amp; Kiro',
     sv: ['Kiro', 'Amazon Q Developer'], tp: ['Developer Tools'],
     ai: ['DevOps'], kw: ['kiro', 'q developer', 'ci/cd', 'pipeline', 'sdlc']},
    {k: 'containers', label: 'Containers &amp; Kubernetes',
     sv: ['Amazon Elastic Kubernetes Service (Amazon EKS)',
          'Amazon Elastic Container Service (Amazon ECS)', 'AWS Fargate'],
     tp: ['Containers'], kw: ['kubernetes', 'eks', 'ecs', 'container', 'fargate']},
    {k: 'data', label: 'Databases',
     tp: ['Databases'], kw: ['aurora', 'rds', 'dynamodb', 'database', 'postgres', 'mysql']},
    {k: 'serverless', label: 'Serverless',
     tp: ['Serverless'], kw: ['lambda', 'serverless', 'step functions', 'eventbridge']},
    {k: 'net', label: 'Networking',
     tp: ['Networking & Content Delivery'], kw: ['vpc', 'network', 'transit gateway', 'dns']},
    {k: 'arch', label: 'Architecture &amp; resilience',
     tp: ['Architecture'], ai: ['Resilience', 'Well-Architected Framework'],
     kw: ['resilien', 'well-architected', 'failover', 'disaster', 'multi-region']},
    {k: 'migrate', label: 'Migration &amp; modernization',
     tp: ['Migration & Modernization'], kw: ['migrat', 'moderniz', 'legacy', 'mainframe']}
  ];

  /* Reservation: read from the catalogue's own scheduleAccess split, not from
   * last year's habits. Every session of a type is either gated or open, with
   * no mixed cases across all 2,177. */
  var RESERVE = {'Chalk talk': 1, 'Workshop': 1, "Builders' session": 1,
                 'Code talk': 1, 'Lab': 1, 'Gamified learning': 1,
                 'Bootcamp': 1, 'Exam prep': 1};

  /* Keynote windows. NOT in the catalogue -- there are no KEY session codes
   * among the 2,177 records, so these cannot be read the way everything else
   * here is. Held as the shape re:Invent has used for years, and labelled on
   * the page as unconfirmed rather than printed as fact. */
  var KEYNOTE = {'2026-12-01': [480, 630], '2026-12-02': [510, 630],
                 '2026-12-03': [510, 630]};

  var DAYS = [
    {d: '2026-11-30', name: 'Monday 30 Nov'},
    {d: '2026-12-01', name: 'Tuesday 1 Dec'},
    {d: '2026-12-02', name: 'Wednesday 2 Dec'},
    {d: '2026-12-03', name: 'Thursday 3 Dec'},
    {d: '2026-12-04', name: 'Friday 4 Dec'}
  ];

  var store = null, flat = [];

  function $(s) { return document.querySelector(s); }
  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) { e.className = cls; }
    if (html != null) { e.innerHTML = html; }
    return e;
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;')
      .replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function hm(m) {
    if (m == null) { return '--'; }
    var h = Math.floor(m / 60), mm = m % 60;
    return (h <= 12 ? h : h - 12) + ':' + (mm < 10 ? '0' : '') + mm +
           (m < 720 ? 'am' : 'pm');
  }
  function baseCode(c) { return c.replace(/-R\d*$/, ''); }
  function dayShort(d) {
    var m = {'2026-11-30': 'Mon', '2026-12-01': 'Tue', '2026-12-02': 'Wed',
             '2026-12-03': 'Thu', '2026-12-04': 'Fri'};
    return m[d] || d;
  }

  function arr(v) {
    if (v == null) { return []; }
    return Object.prototype.toString.call(v) === '[object Array]' ? v : [v];
  }

  /* ------------------------------------------------------------------ data */

  // Every slot a given session runs in, keyed by base code. Most sessions
  // repeat -- across a typical plan 11 of 15 run again later in the week --
  // and a reader who misses a 50-seat builders' session has no way to know
  // that from the catalogue page. At reservation time this is the most
  // useful fact on the page: it turns a lost seat into a rescheduled one.
  var RUNS = {};

  function flatten() {
    var F = store.facets, V = store.venues;
    var TY = F.Type, LV = F.Level, TP = F.Topic, AI = F['Area of Interest'],
        SV = F.Services;
    flat = [];
    for (var i = 0; i < store.sessions.length; i++) {
      var x = store.sessions[i];
      var blob = ((x.t || '') + ' ' + (x.a || '')).toLowerCase();
      var rec = {
        c: x.c, t: x.t, a: x.a || '',
        ty: TY[x.ty],
        lv: x.lv != null ? LV[x.lv].slice(0, 3) : '',
        tp: arr(x.tp).map(function (i2) { return TP[i2]; }),
        ai: arr(x.ai).map(function (i2) { return AI[i2]; }),
        sv: arr(x.sv).map(function (i2) { return SV[i2]; }),
        blob: blob,
        sponsored: /-S$/.test(x.c)
      };
      var w = x.when || [];
      for (var j = 0; j < w.length; j++) {
        if (w[j].e == null) { continue; }   // unknown end: cannot be scheduled
        var slot = {
          s: rec, d: w[j].d, b: w[j].b, e: w[j].e,
          v: V[w[j].v], room: store.rooms ? store.rooms[w[j].r] : '',
          cap: w[j].cap
        };
        flat.push(slot);
        var bc = baseCode(x.c);
        (RUNS[bc] = RUNS[bc] || []).push(slot);
      }
    }
  }

  /* ----------------------------------------------------------------- score */

  function scorer(picked, levelPref, handsOn) {
    var want = INTERESTS.filter(function (i) { return picked[i.k]; });
    return function (f) {
      var s = f.s, sc = 0, hit = [];
      for (var i = 0; i < want.length; i++) {
        var it = want[i], got = 0;
        (it.sv || []).forEach(function (n) {
          if (s.sv.indexOf(n) >= 0) { got += 4; }
        });
        (it.tp || []).forEach(function (n) {
          if (s.tp.indexOf(n) >= 0) { got += 3; }
        });
        (it.ai || []).forEach(function (n) {
          if (s.ai.indexOf(n) >= 0) { got += 3; }
        });
        (it.kw || []).forEach(function (k) {
          if (s.blob.indexOf(k) >= 0) { got += 2; }
        });
        if (got) { sc += got; hit.push(it.label.replace(/&amp;/g, '&')); }
      }
      if (!sc) { return null; }
      // Level: a preference, not a filter -- a 200 that is dead on topic
      // should still beat a 400 that is tangential.
      if (levelPref === 'deep') {
        sc += ({'400': 5, '300': 4, '500': 3, '200': 1}[s.lv] || 0);
      } else if (levelPref === 'broad') {
        sc += ({'100': 4, '200': 4, '300': 2}[s.lv] || 0);
      }
      if (handsOn) {
        sc += (RESERVE[s.ty] ? 4 : 0);
        if (s.ty === "Builders' session" || s.ty === 'Workshop') { sc += 2; }
      }
      if (s.sponsored) { sc -= 10; }
      return {sc: sc, why: hit};
    };
  }

  /* -------------------------------------------------------------- schedule */

  function planDay(day, cands, perDay, hotel, avoidFar, used) {
    var block = KEYNOTE[day];
    var pool = cands.filter(function (f) {
      if (f.d !== day) { return false; }
      if (block && f.b < block[1] && block[0] < f.e) { return false; }
      return true;
    });
    if (!pool.length) { return {picks: [], anchor: null}; }

    // Anchor on whichever venue this day's strongest sessions cluster in --
    // the Strip is long and the content is not evenly spread, so a day that
    // wanders costs a session in walking.
    var byVenue = {};
    pool.slice(0, 40).forEach(function (f) {
      byVenue[f.v] = (byVenue[f.v] || 0) + f.sc;
    });
    var anchor = null, best = -1;
    Object.keys(byVenue).forEach(function (v) {
      var s = byVenue[v];
      if (avoidFar) { s -= (HOTELS[hotel][v] || 30) * 0.8; }
      if (s > best) { best = s; anchor = v; }
    });

    var ranked = pool.map(function (f) {
      var pen = f.v === anchor ? 0 : (travel(f.v, anchor) >= 30 ? 12 : 4);
      if (avoidFar) { pen += (HOTELS[hotel][f.v] || 30) / 6; }
      return {f: f, adj: f.sc - pen};
    }).sort(function (a, b) { return b.adj - a.adj; });

    var picks = [];
    for (var i = 0; i < ranked.length && picks.length < perDay; i++) {
      var f = ranked[i].f;
      if (used[baseCode(f.s.c)]) { continue; }
      var ok = true;
      for (var j = 0; j < picks.length; j++) {
        var p = picks[j], t = travel(f.v, p.v);
        if (f.b < p.e + t && p.b < f.e + t) { ok = false; break; }
      }
      if (!ok) { continue; }
      picks.push(f);
      used[baseCode(f.s.c)] = 1;
    }
    picks.sort(function (a, b) { return a.b - b.b; });
    return {picks: picks, anchor: anchor};
  }

  /* ---------------------------------------------------------------- render */

  function row(f, hotel) {
    var s = f.s;
    var tag = RESERVE[s.ty]
      ? '<span class="pq-tag pq-res">reserve</span>'
      : '<span class="pq-tag pq-open">open seating</span>';
    var cap = f.cap ? (f.cap + ' seats') : 'capacity not published';
    var why = f.why && f.why.length
      ? '<p class="pq-why">Matched: ' + esc(f.why.join(', ')) + '</p>' : '';

    // Does it run again? Only the OTHER slots count, and only ones that have
    // not already happened relative to this booking.
    var others = (RUNS[baseCode(s.c)] || []).filter(function (o) {
      return !(o.d === f.d && o.b === f.b && o.v === f.v);
    }).sort(function (a, b) {
      return a.d === b.d ? a.b - b.b : (a.d < b.d ? -1 : 1);
    });
    var again = others.length
      ? '<p class="pq-again">Runs again: ' + others.slice(0, 2).map(function (o) {
          return esc(dayShort(o.d) + ' ' + hm(o.b) + ', ' + o.v);
        }).join('; ') + (others.length > 2 ? ' and ' + (others.length - 2) +
          ' more' : '') + '</p>'
      : '<p class="pq-again pq-once">Runs once — no second chance</p>';
    return '<div class="pq-row"><div class="pq-t">' + hm(f.b) + '<br>' + hm(f.e) +
      '</div><div><p class="pq-title"><b>' + esc(s.c) + '</b> &mdash; ' +
      esc(s.t) + '</p><div class="pq-meta">' + tag + esc(s.ty) +
      (s.lv ? ' &middot; level ' + esc(s.lv) : '') + ' &middot; ' + esc(f.v) +
      ' &middot; ' + cap + '</div>' + why + again + '</div></div>';
  }

  function render(result, opts) {
    var out = $('#pq-out');
    out.innerHTML = '';
    var total = 0, res = 0;
    result.forEach(function (r) { total += r.picks.length;
      r.picks.forEach(function (f) { if (RESERVE[f.s.ty]) { res += 1; } }); });

    if (!total) {
      out.appendChild(el('p', 'pq-empty',
        'Nothing matched. Tick at least one interest — the planner only ' +
        'schedules sessions it can justify, so an empty selection gives an ' +
        'empty plan rather than a random one.'));
      return;
    }

    var head = el('div', 'pq-sum');
    var nDays = result.filter(function (r) { return r.picks.length; }).length;
    var open = total - res;
    head.innerHTML = '<p><b>' + total + ' session' + (total === 1 ? '' : 's') +
      '</b> across ' + nDays + ' day' + (nDays === 1 ? '' : 's') + '. <b>' +
      res + '</b> need a reservation; ' + open + ' ' +
      (open === 1 ? 'is' : 'are') + ' open seating and cannot be reserved. ' +
      'Staying at ' + esc(opts.hotel) + '.</p>';
    out.appendChild(head);

    result.forEach(function (r) {
      if (!r.picks.length) { return; }
      var sec = el('section', 'pq-day');
      var h = '<div class="pq-h"><h3>' + esc(r.name) + '</h3>';
      if (r.anchor) {
        h += '<span class="pq-anchor">mostly ' + esc(r.anchor) + ' &middot; ~' +
             (HOTELS[opts.hotel][r.anchor] || 30) + ' min from the hotel</span>';
      }
      h += '</div>';
      if (KEYNOTE[r.d]) {
        h += '<p class="pq-key"><b>' + hm(KEYNOTE[r.d][0]) + ' – ' +
             hm(KEYNOTE[r.d][1]) + ' keynote</b> — kept clear. No ' +
             'reservation needed. The catalogue carries no keynote records at ' +
             'all, so this window is the usual shape rather than a measured ' +
             'time: confirm it on the official agenda.</p>';
      }
      sec.innerHTML = h + r.picks.map(function (f) { return row(f, opts.hotel); }).join('');
      out.appendChild(sec);
    });

    var note = el('p', 'pq-note');
    note.innerHTML = 'Every time, room and seat count above is read from the ' +
      'session catalogue in your browser — nothing here is generated, so ' +
      'no session, time or room on this page is invented. Walking times ' +
      'between venues are estimates, used to refuse pairs you could not ' +
      'physically make.';
    out.appendChild(note);
    out.scrollIntoView({behavior: 'smooth', block: 'start'});
  }

  /* ------------------------------------------------------------------- run */

  function run() {
    var picked = {};
    [].forEach.call(document.querySelectorAll('.pq-int:checked'), function (c) {
      picked[c.value] = 1;
    });
    var opts = {
      hotel: $('#pq-hotel').value,
      perDay: parseInt($('#pq-per').value, 10),
      level: $('#pq-level').value,
      handsOn: $('#pq-hands').checked,
      avoidFar: $('#pq-near').checked
    };
    var score = scorer(picked, opts.level, opts.handsOn);
    var cands = [];
    for (var i = 0; i < flat.length; i++) {
      var r = score(flat[i]);
      if (!r) { continue; }
      var f = flat[i];
      cands.push({s: f.s, d: f.d, b: f.b, e: f.e, v: f.v, cap: f.cap,
                  sc: r.sc, why: r.why});
    }
    cands.sort(function (a, b) { return b.sc - a.sc; });

    var used = {}, result = [];
    for (var k = 0; k < DAYS.length; k++) {
      if (!$('#pq-day-' + k).checked) { continue; }
      var p = planDay(DAYS[k].d, cands, opts.perDay, opts.hotel,
                      opts.avoidFar, used);
      result.push({d: DAYS[k].d, name: DAYS[k].name,
                   picks: p.picks, anchor: p.anchor});
    }
    render(result, opts);
  }

  function boot() {
    var chips = $('#pq-chips');
    INTERESTS.forEach(function (it) {
      var l = el('label', 'pq-chip');
      l.innerHTML = '<input type="checkbox" class="pq-int" value="' + it.k +
                    '"> <span>' + it.label + '</span>';
      chips.appendChild(l);
    });
    var days = $('#pq-days');
    DAYS.forEach(function (d, i) {
      var l = el('label', 'pq-chip');
      l.innerHTML = '<input type="checkbox" id="pq-day-' + i + '"' +
                    (i < 4 ? ' checked' : '') + '> <span>' + d.name + '</span>';
      days.appendChild(l);
    });
    var hs = $('#pq-hotel');
    Object.keys(HOTELS).forEach(function (h) {
      var o = document.createElement('option');
      o.value = h; o.textContent = h;
      hs.appendChild(o);
    });
    $('#pq-go').addEventListener('click', run);

    fetch(STORE).then(function (r) { return r.json(); }).then(function (d) {
      store = d;
      flatten();
      $('#pq-state').textContent =
        flat.length + ' scheduled sessions loaded, captured ' +
        (d.captured || 'recently') + '.';
      $('#pq-go').disabled = false;
    }).catch(function () {
      // A planner that cannot read the catalogue must say so rather than
      // offering an empty form that looks ready.
      $('#pq-state').textContent =
        'The session catalogue could not be loaded, so this planner cannot ' +
        'run. Nothing below would be accurate.';
      $('#pq-go').disabled = true;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, {once: true});
  } else {
    boot();
  }
})();
