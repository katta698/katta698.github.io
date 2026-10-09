#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build /intelligence/clouds/ -- the three clouds, as they report themselves.

    python scripts/build_clouds_page.py

Two questions, two sources, and one of them has a hole in it.

THE MONEY comes from intelligence/cloud-economics.json, which
fetch_cloud_economics.py parses out of each company's own 10-Q or 10-K. The
hole is Microsoft: it does not disclose Azure's revenue or operating income,
only a growth rate against an undisclosed base. Its "Microsoft Cloud" figure
bundles Office 365, Dynamics and LinkedIn and is not comparable. So the page
shows two numbers and one absence, and says why -- it does not reach for an
analyst estimate to make the row look complete. Every market-share
percentage in circulation is such an estimate, and this page would rather
print a gap than borrow somebody's guess.

THE FOOTPRINT comes from intelligence/status/regions.json, which the status
page already maintains: 160 regions with coordinates, drawn on the Robinson
basemap in intelligence/status/world.json using the same projection
constants pm.js uses. Reusing both means the two maps on this site agree
about where places are, which they would not if this invented its own.

Rendered server-side, deliberately
----------------------------------
The SVG and every figure are in the HTML, not built by script on load. The
re:Invent countdown taught that lesson the expensive way: it shipped hidden
and was revealed after a 2 MB fetch, so the box arrived late and shoved the
page down. A map that assembles itself after load does the same thing, four
times bigger. This way the page is complete at first paint and works with
JavaScript off.

The derived section
-------------------
"Where one cloud is alone" is the part no vendor will ever publish, because
it is a map of where their competitors are not. It needs country names
normalised first: the three spell things differently, and left alone the
store treats "China", "People's Republic of China" and "Republic of China"
as three countries -- the last of which is Taiwan, which AWS files under
"Taiwan". Counting without fixing that produces a confident wrong answer.
"""
import io
import json
import math
import os
import re
import sys
import collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

ECON = os.path.join(ROOT, "intelligence", "cloud-economics.json")
REGIONS = os.path.join(ROOT, "intelligence", "status", "regions.json")
WORLD = os.path.join(ROOT, "intelligence", "status", "world.json")
OUTDIR = os.path.join(ROOT, "intelligence", "clouds")

W, H = 720, 360
# Byte-identical to pm.js. Robinson is a lookup table every five degrees with
# linear interpolation between -- that is not an approximation of it, it is
# what it is. Copied rather than imported because that file is browser JS.
ROB_X = [1.0000, 0.9986, 0.9954, 0.9900, 0.9822, 0.9730, 0.9600,
         0.9427, 0.9216, 0.8962, 0.8679, 0.8350, 0.7986, 0.7597,
         0.7186, 0.6732, 0.6213, 0.5722, 0.5322]
ROB_Y = [0.0000, 0.0620, 0.1240, 0.1860, 0.2480, 0.3100, 0.3720,
         0.4340, 0.4958, 0.5571, 0.6176, 0.6769, 0.7346, 0.7903,
         0.8435, 0.8936, 0.9394, 0.9761, 1.0000]

# The three vendors spell countries differently. Without this the counts are
# wrong in a way that looks authoritative.
COUNTRY = {
    "People's Republic of China": "China",
    "Republic of China": "Taiwan",          # it is Taiwan; AWS files it so
    "Kingdom of Saudi Arabia": "Saudi Arabia",
}
# The offset is the whole point of the map, not decoration. The three put
# regions in the SAME CITIES -- Virginia, Frankfurt, Tokyo, Sao Paulo -- so
# drawn on their true coordinates the later dot lands exactly on the earlier
# one and hides it. The first version looked like AWS had four regions
# worldwide; it has 37, with Azure and Google painted over them. Each cloud
# is nudged to a fixed corner of a small triangle, so a city with all three
# reads as three dots and a city with one reads as one. A few pixels of lie
# about position, in exchange for the map answering the question it exists
# to answer.
CLOUDS = [("aws", "AWS", "#C4A484", -3.3, -2.0),
          ("azure", "Azure", "#5B7B9A", 3.3, -2.0),
          ("gcp", "Google Cloud", "#8A9A5B", 0.0, 3.4)]


def proj(lat, lon):
    a = min(abs(lat), 90) / 5.0
    i = min(int(a), 17)
    t = a - i
    xf = ROB_X[i] + (ROB_X[i + 1] - ROB_X[i]) * t
    yf = ROB_Y[i] + (ROB_Y[i + 1] - ROB_Y[i]) * t
    if lat < 0:
        yf = -yf
    return (W / 2.0 + (lon / 180.0) * xf * (W / 2.0), H / 2.0 - yf * (H / 2.0))


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def usd(n):
    """Billions to one decimal. These are tens of billions; cents are noise."""
    return "$%.1fB" % (n / 1e9)


def load(path):
    return json.load(io.open(path, encoding="utf-8"))


def money_section(econ):
    order = ["AWS", "Azure", "Google Cloud"]
    cards = []
    for name in order:
        c = econ["clouds"].get(name)
        if not c:
            continue
        colour = dict((n, col) for _, n, col, _dx, _dy in CLOUDS).get(
            name, "#C4A484")
        if c.get("disclosed"):
            qs = c.get("quarters", {})
            ends = sorted(qs)
            if not ends:
                continue
            latest = qs[ends[-1]]
            prior = qs[ends[-2]] if len(ends) > 1 else None
            rev = latest.get("revenue")
            op = latest.get("operating_income")
            growth = ""
            if prior and prior.get("revenue"):
                g = (rev - prior["revenue"]) / float(prior["revenue"]) * 100
                growth = ("<span class=\"cl-growth\">%+.0f%% year on year</span>"
                          % g)
            margin = ""
            if rev and op:
                margin = ("<span class=\"cl-sub\">%.0f%% operating margin%s"
                          "</span>"
                          % (op / float(rev) * 100,
                             " (derived)" if latest.get(
                                 "operating_income_derived") else ""))
            cards.append(
                '<div class="cl-card"><div class="cl-bar" style="background:%s">'
                '</div><h3>%s</h3>'
                '<p class="cl-big">%s</p>'
                '<p class="cl-meta">revenue, quarter to %s %s</p>'
                '<p class="cl-op">%s operating income</p>%s'
                '<p class="cl-src">%s, filed %s</p></div>'
                % (colour, esc(name), usd(rev), esc(ends[-1]), growth,
                   usd(op) if op else "not tagged", margin,
                   esc(c.get("form", "")), esc(c.get("filed", ""))))
        else:
            g = c.get("growth") or {}
            enc = c.get("enclosing_segment") or {}
            ceiling = ""
            if enc.get("revenue"):
                # Deliberately NOT formatted like the two cards beside it.
                # It is a yearly figure for a wider segment; made to look the
                # same it would be read as Azure's quarter, which is the one
                # misreading this whole page exists to prevent.
                yearly = ("year to %s" % enc["end"]) if enc.get("days", 0) > 300                     else ("period to %s" % enc["end"])
                ceiling = (
                    '<p class="cl-ceiling"><b>Upper bound:</b> %s, the segment '
                    'Azure sits inside, reported <b>%s</b> revenue and %s '
                    'operating income for the %s. It also contains Windows '
                    'Server, SQL Server, Visual Studio and Enterprise '
                    'Services &mdash; so it is a ceiling on Azure, not a '
                    'measure of it, and it is a year where the other two '
                    'cards are a quarter.</p>'
                    % (esc(enc.get("segment", "the enclosing segment")),
                       usd(enc["revenue"]),
                       usd(enc.get("operating_income", 0)), esc(yearly)))
            cards.append(
                '<div class="cl-card cl-gap">'
                '<div class="cl-bar" style="background:%s"></div><h3>%s</h3>'
                '<p class="cl-big cl-none">not disclosed</p>'
                '<p class="cl-meta">Microsoft publishes a growth rate, not a '
                'figure</p>'
                '<p class="cl-quote">&ldquo;%s&rdquo;</p>%s'
                '<p class="cl-src">%s, filed %s</p></div>'
                % (colour, esc(name),
                   esc(g.get("sentence", "no Azure line found in the filing")),
                   ceiling,
                   esc(c.get("form", "")), esc(c.get("filed", ""))))
    return "".join(cards)


def normalise(name):
    return COUNTRY.get(name, name)


def _rob_inverse(px, py):
    """Robinson pixel in the 720x360 world.json frame -> (lat, lon).

    Robinson is defined by a table and has no closed form inverse, so the
    latitude is a binary search on the same ROB_Y this file projects with and
    the longitude follows from ROB_X at that latitude. Exact to the precision
    of the table: measured 0.000000 degrees over a 5-degree grid.
    """
    x = (px - W / 2.0) / (W / 2.0) * (0.8487 * math.pi)
    y = (H / 2.0 - py) / (H / 2.0) * 1.3523
    sign = 1.0 if y >= 0 else -1.0
    target = abs(y) / 1.3523
    lo, hi = 0.0, 90.0
    for _ in range(36):
        mid = (lo + hi) / 2.0
        a = mid / 5.0
        i = min(int(a), len(ROB_Y) - 2)
        t = a - i
        if ROB_Y[i] + (ROB_Y[i + 1] - ROB_Y[i]) * t < target:
            lo = mid
        else:
            hi = mid
    lat = sign * (lo + hi) / 2.0
    a = abs(lat) / 5.0
    i = min(int(a), len(ROB_X) - 2)
    t = a - i
    xf = ROB_X[i] + (ROB_X[i + 1] - ROB_X[i]) * t
    lon = math.degrees(x / (0.8487 * xf)) if xf else 0.0
    return lat, max(-180.0, min(180.0, lon))


# A point every 3.6 Robinson units, and rings smaller than 11 square units
# dropped. Both are below a pixel at the size this is drawn.
#
# The number was chosen by measuring, not by eye. Profiled at 4x CPU
# throttling -- roughly a mid-range phone -- a frame of land cost 11.16ms at
# 4,256 points and 4.60ms at half that, against a 16.7ms budget for 60fps.
# Point count dominates: dropping the country borders entirely only saved
# 2.5ms of the same frame, so the detail stays and the density goes.
#
# The full source set is 10,587 points and 138KB, which is detail no screen
# resolves on a 440px globe and three times the frame cost.
GLOBE_STEP, GLOBE_MIN_AREA = 3.6, 11.0


def globe_rings():
    """The same coastlines as the flat map, as latitude and longitude."""
    world = load(WORLD)
    out = []
    for c in world["countries"]:
        for sub in c["d"].split("M"):
            nums = [float(n) for n in re.findall(r"-?\d+\.?\d*", sub)]
            if len(nums) < 6:
                continue
            pts = list(zip(nums[0::2], nums[1::2]))
            xs = [q[0] for q in pts]
            ys = [q[1] for q in pts]
            if (max(xs) - min(xs)) * (max(ys) - min(ys)) < GLOBE_MIN_AREA:
                continue
            ring, last = [], None
            for px, py in pts:
                if last and (abs(px - last[0]) < GLOBE_STEP
                             and abs(py - last[1]) < GLOBE_STEP):
                    continue
                last = (px, py)
                lat, lon = _rob_inverse(px, py)
                ring.append([round(lon, 1), round(lat, 1)])
            if len(ring) >= 4:
                out.append(ring)
    return out


def globe_points(regions):
    """Every region with a published location, for the globe.

    [cloud, lon, lat, label] -- the same records the flat map plots, so the
    two cannot disagree about where a region is or whose it is.
    """
    pts = []
    for r in regions:
        if not r.get("p"):
            continue
        pts.append([r.get("cloud"), round(r["p"][1], 2), round(r["p"][0], 2),
                    (r.get("name") or r.get("code") or "")[:40]])
    return pts


def globe_html(regions, plotted):
    """A globe you can turn, and the same facts in text underneath it.

    Canvas rather than SVG. Every frame of a drag redraws 219 coastline rings
    and 144 points; as DOM that is 363 nodes rewritten per frame, which is how
    a globe comes to stutter on a phone. On a canvas it is one clear and a few
    thousand lineTo calls.

    The list below it is not a fallback bolted on. A canvas is a single
    element with no text in it, so without this the page would say "where
    they are" to a screen reader and then show it nothing. It is also what
    renders if the script never runs.
    """
    rings = json.dumps(globe_rings(), separators=(",", ":"))
    pts = json.dumps(globe_points(regions), separators=(",", ":"))
    by = collections.defaultdict(list)
    for cloud, _lon, _lat, label in globe_points(regions):
        by[cloud].append(label)
    lists = []
    for cloud, label, _c, _dx, _dy in CLOUDS:
        names = sorted(by.get(cloud) or [])
        if not names:
            continue
        lists.append('<p class="cl-globe-row"><b>%s</b> &mdash; %s</p>'
                     % (esc(label), esc(", ".join(names))))
    return (
        '<figure class="cl-globe-fig">'
        '<div class="cl-globe-box">'
        '<canvas id="cl-globe" class="cl-globe" width="900" height="900"'
        ' aria-label="A globe showing where AWS, Azure and Google Cloud have'
        ' regions. Drag to turn it. Every region is also listed below."'
        ' role="img"></canvas>'
        '</div>'
        '<figcaption class="cl-globe-cap">%d regions, on their published '
        'coordinates. Drag to turn; it turns by itself when left alone.'
        '</figcaption>'
        '<details class="cl-globe-list"><summary>Every region, as text'
        '</summary>%s</details>'
        '<script id="cl-globe-land" type="application/json">%s</script>'
        '<script id="cl-globe-pts" type="application/json">%s</script>'
        '</figure>' % (plotted, "".join(lists), rings, pts))


def map_svg(regions):
    world = load(WORLD)
    land = "".join('<path d="%s"/>' % c["d"] for c in world["countries"])
    dots = []
    for cloud, label, colour, dx, dy in CLOUDS:
        pts = []
        for r in regions:
            if r.get("cloud") != cloud or not r.get("p"):
                continue
            lat, lon = r["p"][0], r["p"][1]
            x, y = proj(lat, lon)
            x, y = x + dx, y + dy
            pts.append('<circle cx="%.1f" cy="%.1f" r="2.9"><title>%s &mdash; '
                       '%s</title></circle>'
                       % (x, y, esc(label),
                          esc(r.get("name") or r.get("code") or "")))
        dots.append('<g class="cl-dots cl-%s">%s</g>' % (cloud, "".join(pts)))
    plotted = sum(1 for r in regions if r.get("p"))
    return (plotted, '<svg class="cl-map" viewBox="0 0 %d %d" role="img" '
            'aria-label="Where the three clouds have regions: %d plotted on '
            'a Robinson projection.">'
            '<g class="cl-land">%s</g>%s</svg>'
            % (W, H, plotted, land, "".join(dots)))


def alone_section(regions):
    by_country = collections.defaultdict(set)
    for r in regions:
        if r.get("country"):
            by_country[normalise(r["country"])].add(r["cloud"])
    all3 = sorted(c for c, v in by_country.items() if len(v) == 3)
    two = sorted(c for c, v in by_country.items() if len(v) == 2)
    one = collections.defaultdict(list)
    for c, v in by_country.items():
        if len(v) == 1:
            one[list(v)[0]].append(c)

    rows = []
    for cloud, label, colour, _dx, _dy in CLOUDS:
        names = sorted(one.get(cloud, []))
        if not names:
            continue
        rows.append('<li><span class="cl-dot" style="background:%s"></span>'
                    '<b>%s only</b> &mdash; %s</li>'
                    % (colour, esc(label),
                       esc(", ".join(names))))
    return (len(by_country), len(all3), len(two),
            sum(len(v) for v in one.values()), "".join(rows))


def build():
    econ = load(ECON)
    regions = load(REGIONS)["regions"]
    import build_events_page as bep
    from asset_version import JS_VERSION
    jsv = JS_VERSION

    total, n3, n2, n1, alone_rows = alone_section(regions)
    plotted, svg = map_svg(regions)
    counts = collections.Counter(r["cloud"] for r in regions)

    head = bep.head_html(jsv)
    head = re.sub(r"<title>.*?</title>",
                  "<title>The three clouds, as they report themselves | "
                  "Jayanth Katta</title>", head, count=1, flags=re.S)
    head = re.sub(r'<meta name="description" content=".*?">',
                  '<meta name="description" content="AWS, Azure and Google '
                  'Cloud from their own SEC filings and region lists &mdash; '
                  'including the number Microsoft does not publish. No '
                  'analyst estimates.">', head, count=1, flags=re.S)
    head = re.sub(r'<link rel="canonical" href=".*?">',
                  '<link rel="canonical" '
                  'href="https://jayanthkatta.com/intelligence/clouds/">',
                  head, count=1, flags=re.S)
    head += "<style>%s</style>\n</head>\n" % CSS

    legend = " ".join(
        '<span class="cl-key"><span class="cl-dot" style="background:%s">'
        '</span>%s %d</span>' % (col, esc(label), counts.get(k, 0))
        for k, label, col, _dx, _dy in CLOUDS)

    body = [
        "<body>", bep.nav_html(), '<main class="cl">',
        "<h1>The three clouds, as they report themselves</h1>",
        '<p class="cl-lede">Every figure on this page comes from a company&rsquo;s '
        'own SEC filing or its own published region list. Nothing here is an '
        'analyst estimate, and where a company does not publish something, '
        'the page says so rather than borrowing somebody&rsquo;s guess.</p>',

        '<section class="cl-sec"><h2>What they earn</h2>',
        '<p class="cl-note">Segment figures, read out of the XBRL in each '
        'company&rsquo;s latest 10-Q or 10-K. Captured %s.</p>'
        % esc(econ.get("captured", "")),
        '<div class="cl-cards">%s</div>' % money_section(econ),
        '<p class="cl-note cl-warn">%s</p>' % esc(econ.get("note", "")),
        "</section>",

        '<section class="cl-sec"><h2>Where they are</h2>',
        '<p class="cl-note">%d of the %d regions the three publish. '
        'Drag it to turn the earth. Same basemap and the same published '
        'coordinates as the incident map, read back to latitude and '
        'longitude and drawn on a sphere &mdash; a flat map stretches the '
        'high latitudes, which is where a good deal of this infrastructure '
        'is. The other %d carry no published coordinates &mdash; they are '
        'almost all government and sovereign regions (us-gov, us-dod, '
        'eusc-de) plus a few announced since the geo data was last '
        'refreshed, so they are counted everywhere else on this page but '
        'cannot be drawn.</p>' % (plotted, len(regions), len(regions) - plotted),
        '<p class="cl-legend">%s</p>' % legend,
        globe_html(regions, plotted),
        "</section>",

        '<section class="cl-sec"><h2>Where one cloud is alone</h2>',
        '<p class="cl-note">%d countries have a region from at least one of '
        'the three. <b>%d</b> have all three, <b>%d</b> have two, and '
        '<b>%d</b> have exactly one &mdash; which is a latency and lock-in '
        'fact no vendor publishes, because it is a map of where their '
        'competitors are not.</p>' % (total, n3, n2, n1),
        '<ul class="cl-alone">%s</ul>' % alone_rows,
        '<p class="cl-note">Country names are normalised first: the three '
        'spell them differently, and left alone the data treats China and '
        'the People&rsquo;s Republic of China as two countries, and files '
        'Taiwan under a third name again.</p>',
        "</section>",

        '<section class="cl-sec"><h2>What this page cannot tell you</h2>',
        '<ul class="cl-cant">'
        '<li><b>Market share.</b> Those percentages come from Gartner, IDC, '
        'Synergy and Canalys. They are licensed research, not public data, '
        'and they are estimates &mdash; necessarily so, given the gap above.</li>'
        '<li><b>How many customers each has, or of what kind.</b> None of '
        'the three publishes it. Vendors cite selected logos, never totals.</li>'
        '<li><b>Azure&rsquo;s revenue.</b> It is not that this page has not '
        'found it. Microsoft does not publish it. The Intelligent Cloud '
        'figure above is the audited segment Azure sits inside &mdash; a '
        'ceiling, and an annual one. Subtracting your way from it to Azure '
        'requires numbers Microsoft does not file either.</li>'
        '<li><b>Market capitalisation is not on this page on purpose.</b> It '
        'measures Amazon-the-retailer, Microsoft-including-Office and '
        'Alphabet-including-ads. It moves on holiday retail. It says nothing '
        'about who leads in cloud.</li></ul>',
        "</section>",
        "</main>",
        "<script>%s</script>" % GLOBE_JS,
        bep.tail_html(jsv, "intelligence-clouds"),
    ]

    os.makedirs(OUTDIR, exist_ok=True)
    html = head + "\n".join(body)
    out = os.path.join(OUTDIR, "index.html")
    io.open(out, "w", encoding="utf-8", newline="\n").write(html)
    print("  %d regions, %d countries (%d with all three, %d with one)"
          % (len(regions), total, n3, n1))
    print("  page -> intelligence/clouds/index.html  (%.1fKB)"
          % (len(html) / 1024.0))
    return 0


GLOBE_JS = r"""
/* An orthographic globe, drawn on its own published coordinates.
   -------------------------------------------------------------------------
   The colours are READ FROM THE PAGE rather than written in here. This site
   rotates its palette by day of the week and flips dark/light, and a canvas
   carrying its own hex values is the one element that would ignore both --
   the same class of bug that had /reinvent-2026/ stuck on a Tuesday.

   Why there is no trigonometry in the draw loop
   -----------------------------------------------------------------------
   Nothing about a point on the earth changes when the earth turns; only the
   viewer moves. So every coastline point, graticule point and region becomes
   a unit vector once, at load, and a frame is six multiplies and a compare
   per point. The first version called sin and cos five times per point per
   frame -- about 28,000 trig operations a frame, 1.7 million a second, to
   draw a shape that never changes.
*/
(function () {
  var cv = document.getElementById('cl-globe');
  if (!cv || !cv.getContext) { return; }
  var rawLand, rawPts;
  try {
    rawLand = JSON.parse(document.getElementById('cl-globe-land').textContent);
    rawPts = JSON.parse(document.getElementById('cl-globe-pts').textContent);
  } catch (e) { return; }

  var ctx = cv.getContext('2d', { alpha: true });
  var RAD = Math.PI / 180;
  var lam = -15, phi = 20;
  var drag = null, idleUntil = 0, size = 0, last = 0;
  var still = window.matchMedia &&
              window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function vec(lon, lat) {
    var a = lat * RAD, b = lon * RAD, c = Math.cos(a);
    return [c * Math.sin(b), Math.sin(a), c * Math.cos(b)];
  }

  /* Each ring as a flat Float32Array of xyz, plus a bounding cap: the mean
     direction of its points and the angle to the furthest one. One dot
     product against the view axis then rejects a whole ring. */
  function pack(rings) {
    var out = [];
    for (var i = 0; i < rings.length; i++) {
      var r = rings[i], n = r.length;
      var buf = new Float32Array(n * 3);
      var sx = 0, sy = 0, sz = 0;
      for (var j = 0; j < n; j++) {
        var v = vec(r[j][0], r[j][1]);
        buf[j * 3] = v[0]; buf[j * 3 + 1] = v[1]; buf[j * 3 + 2] = v[2];
        sx += v[0]; sy += v[1]; sz += v[2];
      }
      var m = Math.sqrt(sx * sx + sy * sy + sz * sz) || 1;
      sx /= m; sy /= m; sz /= m;
      var worst = 1;
      for (var k = 0; k < n; k++) {
        var d = sx * buf[k * 3] + sy * buf[k * 3 + 1] + sz * buf[k * 3 + 2];
        if (d < worst) { worst = d; }
      }
      out.push({ v: buf, n: n, cx: sx, cy: sy, cz: sz,
                 cap: Math.acos(Math.max(-1, Math.min(1, worst))) });
    }
    return out;
  }

  var land = pack(rawLand);

  var grat = [];
  for (var la = -60; la <= 60; la += 30) {
    var row = [];
    for (var lo = -180; lo <= 180; lo += 6) { row.push([lo, la]); }
    grat.push(row);
  }
  for (var lo2 = -180; lo2 < 180; lo2 += 30) {
    var col = [];
    for (var la2 = -90; la2 <= 90; la2 += 6) { col.push([lo2, la2]); }
    grat.push(col);
  }
  grat = pack(grat);

  var regions = [];
  for (var q = 0; q < rawPts.length; q++) {
    var pt = rawPts[q], v = vec(pt[1], pt[2]);
    regions.push({ cloud: pt[0], x: v[0], y: v[1], z: v[2] });
  }

  function css(name, dflt) {
    var v = getComputedStyle(document.body).getPropertyValue(name).trim();
    return v || dflt;
  }
  var pal = {};
  function repalette() {
    var lt = document.body.classList.contains('light');
    pal = {
      sea:  css('--card', lt ? '#E4E7E2' : '#171C1B'),
      land: css('--border', lt ? '#CBCFC6' : '#2B312F'),
      edge: lt ? 'rgba(0,0,0,.18)' : 'rgba(255,255,255,.14)',
      grid: lt ? 'rgba(0,0,0,.07)' : 'rgba(255,255,255,.055)',
      limb: lt ? 'rgba(0,0,0,.25)' : 'rgba(255,255,255,.22)',
      aws:  lt ? '#7A5C3C' : '#C4A484',
      azure: lt ? '#3F5970' : '#5B7B9A',
      gcp:  lt ? '#4C6340' : '#8A9A5B'
    };
  }

  function resize() {
    var r = cv.getBoundingClientRect();
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var want = Math.max(1, Math.round(r.width * dpr));
    if (want !== size) { size = want; cv.width = size; cv.height = size; }
  }

  /* The rotation, as four numbers reused by every point in the frame. */
  var sl = 0, cl = 1, sp = 0, cp = 1, R = 1, CX = 0, CY = 0;
  function setView() {
    var l = lam * RAD, p = phi * RAD;
    sl = Math.sin(l); cl = Math.cos(l);
    sp = Math.sin(p); cp = Math.cos(p);
    R = size * 0.46; CX = size / 2; CY = size / 2;
  }

  /* The view axis in world space -- the direction pointing at the viewer.
     A ring whose cap lies entirely on the far side of this is skipped. */
  function axis() {
    return [-cp * sl, sp, cp * cl];
  }

  function ringPath(r, ax, ay, az) {
    var d = ax * r.cx + ay * r.cy + az * r.cz;
    /* acos of the dot is the angle between the ring's centre and the
       viewer; anything further than 90 degrees plus its own radius cannot
       show a single point. */
    if (d < Math.cos(Math.min(Math.PI, r.cap + Math.PI / 2))) { return false; }
    var v = r.v, n = r.n, on = false, any = false;
    for (var i = 0; i < n; i++) {
      var x = v[i * 3], y = v[i * 3 + 1], z = v[i * 3 + 2];
      var x1 = x * cl - z * sl;
      var z1 = x * sl + z * cl;
      var y2 = y * cp - z1 * sp;
      var z2 = y * sp + z1 * cp;
      if (z2 < 0) { on = false; continue; }
      var px = CX + R * x1, py = CY - R * y2;
      if (on) { ctx.lineTo(px, py); } else { ctx.moveTo(px, py); on = true; }
      any = true;
    }
    return any;
  }

  function draw() {
    setView();
    var a = axis(), ax = a[0], ay = a[1], az = a[2];
    ctx.clearRect(0, 0, size, size);

    ctx.beginPath(); ctx.arc(CX, CY, R, 0, 6.283185);
    ctx.fillStyle = pal.sea; ctx.fill();

    /* One path for the whole graticule, one stroke. */
    ctx.lineWidth = Math.max(1, size / 900);
    ctx.strokeStyle = pal.grid;
    ctx.beginPath();
    for (var g = 0; g < grat.length; g++) { ringPath(grat[g], ax, ay, az); }
    ctx.stroke();

    /* One path for every visible landmass, one fill and one stroke. */
    ctx.beginPath();
    for (var i = 0; i < land.length; i++) {
      if (ringPath(land[i], ax, ay, az)) { ctx.closePath(); }
    }
    ctx.fillStyle = pal.land; ctx.fill();
    ctx.strokeStyle = pal.edge; ctx.stroke();

    ctx.beginPath(); ctx.arc(CX, CY, R, 0, 6.283185);
    ctx.strokeStyle = pal.limb;
    ctx.lineWidth = Math.max(1, size / 700); ctx.stroke();

    /* Regions last, so a dot is never buried under a coastline. Three
       clouds share a city often enough that an offset is needed -- the flat
       map nudges them apart the same way, by a triangle rather than a line,
       so a stack of three reads as three and not one fat dot.
       Grouped by cloud so the fill colour is set three times, not 147. */
    var off = { aws: [-1.6, -1.0], azure: [1.6, -1.0], gcp: [0, 1.7] };
    var rad = Math.max(2.2, size / 190);
    var order = ['aws', 'azure', 'gcp'];
    ctx.globalAlpha = 0.92;
    for (var c = 0; c < order.length; c++) {
      var key = order[c], o = off[key] || [0, 0], sc = rad * 0.9;
      ctx.fillStyle = pal[key] || pal.limb;
      ctx.beginPath();
      for (var k = 0; k < regions.length; k++) {
        var rg = regions[k];
        if (rg.cloud !== key) { continue; }
        var x1 = rg.x * cl - rg.z * sl;
        var z1 = rg.x * sl + rg.z * cl;
        var y2 = rg.y * cp - z1 * sp;
        var z2 = rg.y * sp + z1 * cp;
        if (z2 < 0) { continue; }
        var px = CX + R * x1 + o[0] * sc, py = CY - R * y2 + o[1] * sc;
        ctx.moveTo(px + rad, py);
        ctx.arc(px, py, rad, 0, 6.283185);
      }
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }

  /* Time, not frames. A 120Hz display span this at double speed when the
     step was a constant per frame. */
  var DEG_PER_SEC = 3.2;
  function frame(now) {
    if (!last) { last = now; }
    var dt = Math.min(now - last, 50) / 1000;
    last = now;
    if (!drag && now > idleUntil && !still) { lam += DEG_PER_SEC * dt; }
    draw();
    requestAnimationFrame(frame);
  }

  cv.addEventListener('pointerdown', function (e) {
    drag = { x: e.clientX, y: e.clientY, lam: lam, phi: phi };
    try { cv.setPointerCapture(e.pointerId); } catch (ex) { /* older engines */ }
  });
  cv.addEventListener('pointermove', function (e) {
    if (!drag) { return; }
    lam = drag.lam + (e.clientX - drag.x) * 0.32;
    phi = Math.max(-78, Math.min(78, drag.phi - (e.clientY - drag.y) * 0.32));
  });
  function release() {
    if (drag) { drag = null; idleUntil = performance.now() + 2500; }
  }
  cv.addEventListener('pointerup', release);
  cv.addEventListener('pointercancel', release);

  cv.setAttribute('tabindex', '0');
  cv.addEventListener('keydown', function (e) {
    var k = e.key, step = e.shiftKey ? 15 : 5, hit = true;
    if (k === 'ArrowLeft') { lam -= step; }
    else if (k === 'ArrowRight') { lam += step; }
    else if (k === 'ArrowUp') { phi = Math.min(78, phi + step); }
    else if (k === 'ArrowDown') { phi = Math.max(-78, phi - step); }
    else { hit = false; }
    if (hit) { idleUntil = performance.now() + 2500; e.preventDefault(); }
  });

  window.addEventListener('resize', resize);
  if (window.MutationObserver) {
    new MutationObserver(repalette).observe(document.body,
      { attributes: true, attributeFilter: ['class'] });
  }
  repalette();
  resize();
  requestAnimationFrame(frame);
})();
"""

CSS = """
.cl{max-width:900px;margin:0 auto;padding:0 1.2rem 4rem}
.cl-lede{color:var(--text-muted);line-height:1.7;margin:0 0 1.6rem;max-width:62ch}
.cl-sec{margin:2.4rem 0 0;border-top:1px solid var(--border);padding-top:1.4rem}
.cl-sec h2{font-family:var(--serif);font-size:1.45rem;margin:0 0 .5rem}
.cl-note{color:var(--text-muted);font-size:.86rem;line-height:1.7;margin:.4rem 0 1rem;max-width:66ch}
.cl-warn{border-left:2px solid var(--accent);padding-left:.8rem}
.cl-cards{display:grid;gap:.9rem;grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}
.cl-card{background:var(--card);border:1px solid var(--border);border-radius:10px;
         padding:1rem 1.1rem;position:relative;overflow:hidden}
.cl-bar{position:absolute;inset:0 auto 0 0;width:3px}
.cl-card h3{margin:0 0 .5rem;font-size:1rem}
.cl-big{font-family:var(--serif);font-size:2rem;margin:0;line-height:1.1}
.cl-none{font-size:1.25rem;color:var(--text-muted);font-style:italic}
.cl-meta{color:var(--text-muted);font-size:.78rem;margin:.2rem 0 .6rem}
.cl-op{margin:.2rem 0 0;font-size:.95rem}
.cl-sub,.cl-growth{display:block;color:var(--text-muted);font-size:.78rem;margin-top:.15rem}
.cl-quote{font-size:.84rem;line-height:1.6;margin:.5rem 0 0;color:var(--text)}
.cl-ceiling{font-size:.8rem;line-height:1.6;margin:.7rem 0 0;padding-top:.6rem;
            border-top:1px dashed var(--border);color:var(--text-muted)}
.cl-ceiling b{color:var(--text)}
body.light .cl-card .cl-ceiling{color:#605F5B}
.cl-src{color:var(--text-muted);font-size:.72rem;margin:.7rem 0 0;font-family:var(--mono)}
/* These sit on the CARD, which is lighter than the page, so the shared
   --text-muted lands at 4.35:1 there while passing on the page itself.
   Same value the planner uses for the same reason: 5.12:1 on the card
   across every day palette. */
body.light .cl-card .cl-meta,
body.light .cl-card .cl-src,
body.light .cl-card .cl-sub,
body.light .cl-card .cl-growth{color:#605F5B}
.cl-legend{display:flex;flex-wrap:wrap;gap:1rem;margin:0 0 .6rem;font-size:.85rem}
.cl-key{display:inline-flex;align-items:center;gap:.4rem}
.cl-dot{display:inline-block;width:10px;height:10px;border-radius:50%;flex:none}
/* ---- the globe ---------------------------------------------------------
   A square box with its height reserved by aspect-ratio, so the canvas
   cannot change the page's shape when the script sizes it. check_page_settle
   holds this page to 12px and a canvas that reflows on load spends all of
   it. */
.cl-globe-fig{margin:1.1rem 0 0}
.cl-globe-box{position:relative;width:100%;max-width:520px;margin:0 auto;
  aspect-ratio:1/1}
.cl-globe{width:100%;height:100%;display:block;border-radius:50%;
  touch-action:none;cursor:grab}
.cl-globe:active{cursor:grabbing}
.cl-globe:focus-visible{outline:2px solid var(--accent, #C4A484);
  outline-offset:6px}
.cl-globe-cap{margin:.75rem auto 0;max-width:520px;text-align:center;
  font-size:.78rem;color:var(--text-muted)}
body.light .cl-globe-cap{color:#605F5B}
/* The text the canvas cannot give a screen reader, and what shows when the
   script does not run. Closed by default -- it is 144 names, and it is an
   alternative to the picture rather than a second copy of the page. */
.cl-globe-list{margin:.9rem auto 0;max-width:720px;font-size:.8rem}
.cl-globe-list summary{cursor:pointer;color:var(--text-muted);
  font-family:var(--mono, ui-monospace, monospace);font-size:.72rem;
  letter-spacing:.06em;text-transform:uppercase}
body.light .cl-globe-list summary{color:#605F5B}
.cl-globe-row{margin:.5rem 0 0;line-height:1.6;color:var(--text-muted)}
.cl-globe-row b{color:var(--text)}
body.light .cl-globe-row{color:#4A4945}
.cl-map{width:100%;height:auto;display:block;background:var(--card);
        border:1px solid var(--border);border-radius:10px}
.cl-land{fill:var(--border);stroke:none}
.cl-dots circle{opacity:.95}
/* AWS tan is #C4A484 -- almost exactly the lightness of the landmass in
   light mode, so the dots disappeared into the continents. Each theme uses
   the variant the rest of the site already carries for text on its own
   ground. */
.cl-aws{fill:#C4A484}.cl-azure{fill:#5B7B9A}.cl-gcp{fill:#8A9A5B}
body.light .cl-aws{fill:#705539}
body.light .cl-azure{fill:#3C5570}
body.light .cl-gcp{fill:#515C32}
.cl-alone{list-style:none;padding:0;margin:0 0 1rem}
.cl-alone li{display:flex;gap:.5rem;align-items:baseline;padding:.45rem 0;
             border-top:1px solid var(--border);line-height:1.6;font-size:.9rem}
.cl-alone li:first-child{border-top:0}
.cl-cant{color:var(--text-muted);line-height:1.75;font-size:.9rem;
         padding-left:1.1rem;margin:0}
.cl-cant li{margin:.5rem 0}
.cl-cant b{color:var(--text)}
@media(max-width:620px){.cl-big{font-size:1.6rem}}
"""


if __name__ == "__main__":
    sys.exit(build())
