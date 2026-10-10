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
import hashlib
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

    [cloud, lon, lat, name, code, city, country, zones] -- the same records
    the flat map plots, so the two cannot disagree about where a region is or
    whose it is. The zone count is the vendor's own az_n, which regions.json
    has always carried and this page had never shown.
    """
    pts = []
    for r in regions:
        if not r.get("p"):
            continue
        pts.append([r.get("cloud"), round(r["p"][1], 2), round(r["p"][0], 2),
                    (r.get("name") or r.get("code") or "")[:46],
                    r.get("code") or "",
                    r.get("city") or "", r.get("country") or "",
                    # az_n OR the length of the zones list. AWS publishes a
                    # count; Google publishes the zone NAMES and no count;
                    # Azure publishes neither. Reading only az_n is the same
                    # singular-vs-list mistake that dropped Google's incident
                    # regions, in a different field -- it would have shown
                    # "zone count not published" for 43 regions whose zones
                    # are listed by name in the same record.
                    (r.get("az_n") or len(r.get("zones") or []) or 0)])
    return pts


def places_json():
    """The label list, built by build_globe_texture.py and committed.

    Read from disk rather than fetched, so the daily rebuild of this page
    never depends on a CDN being up -- same reason the texture is committed.
    """
    path = os.path.join(ROOT, "scripts", "globe-places.json")
    if not os.path.exists(path):
        return "[]"
    with io.open(path, encoding="utf-8") as fh:
        return fh.read().strip() or "[]"


def earth_hi_src():
    """The sharp texture, fetched on demand rather than shipped."""
    path = os.path.join(ROOT, "blog", "assets", "earth-hi.webp")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        h = hashlib.md5(fh.read()).hexdigest()[:8]
    return "/blog/assets/earth-hi.webp?v=%s" % h


def earth_src():
    """The texture URL, carrying its own content hash.

    Hashed rather than versioned by hand for the same reason blog.css is: a
    token someone has to remember to bump is a token that goes stale, and a
    stale globe texture looks like a globe that was never updated.
    """
    path = os.path.join(ROOT, "blog", "assets", "earth.webp")
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        h = hashlib.md5(fh.read()).hexdigest()[:8]
    return "/blog/assets/earth.webp?v=%s" % h


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
    for row in globe_points(regions):
        # [cloud, lon, lat, name, code, city, country, zones]
        by[row[0]].append(row[3])
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
        '<canvas id="cl-globe-earth" class="cl-globe-earth" width="900"'
        ' height="900" aria-hidden="true" data-src="%s" data-hi="%s">'
        '</canvas>'
        '<canvas id="cl-globe" class="cl-globe" width="900" height="900"'
        ' aria-label="A globe showing where AWS, Azure and Google Cloud have'
        ' regions. Drag to turn it, pinch to zoom, double-tap a region to go'
        ' to it. Every region is also listed below."'
        ' role="img"></canvas>'
        '</div>'
        '<figcaption class="cl-globe-cap">%d regions, on their published '
        'coordinates. Drag to turn, pinch or ctrl+scroll to zoom, '
        'double-tap a dot to go to it. Tap it and it takes the whole '
        'gesture until you tap away. The lit half is the lit half '
        '&mdash; the daylight follows real time.'
        '<button type="button" id="cl-globe-reset" class="cl-globe-reset" '
        'hidden>Reset view</button>'
        '<button type="button" id="cl-globe-release" '
        'class="cl-globe-reset cl-globe-release" hidden>Release</button>'
        '</figcaption>'
        '<p id="cl-globe-say" class="cl-globe-say" role="status" '
        'aria-live="polite"></p>'
        '<details class="cl-globe-list"><summary>Every region, as text'
        '</summary>%s</details>'
        '<script id="cl-globe-land" type="application/json">%s</script>'
        '<script id="cl-globe-pts" type="application/json">%s</script>'
        '<script id="cl-globe-places" type="application/json">%s</script>'
        '</figure>' % (earth_src(), earth_hi_src(), plotted,
                       "".join(lists), rings, pts, places_json()))


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
    regions.push({ cloud: pt[0], x: v[0], y: v[1], z: v[2],
                   lon: pt[1], lat: pt[2],
                   name: pt[3], code: pt[4], city: pt[5],
                   country: pt[6], zones: pt[7] });
  }

  /* Named places: oceans and seas, capitals, state capitals, cities.
     Stored as unit vectors for the same reason the regions are -- nothing
     about a place changes when the earth turns, only the viewer. */
  var places = [];
  (function () {
    var el = document.getElementById('cl-globe-places');
    if (!el) { return; }
    var raw;
    try { raw = JSON.parse(el.textContent || '[]'); } catch (e) { return; }
    for (var i = 0; i < raw.length; i++) {
      var q = raw[i], v = vec(q[0], q[1]);
      places.push({ x: v[0], y: v[1], z: v[2],
                    n: q[2], t: q[3], sea: q[4] === 1, w: 0, wf: 0 });
    }
  })();

  /* The zoom each tier earns its place at. Oceans and capitals from the
     start; a sea once you have closed in a little; state capitals and
     ordinary cities only when the view is actually about that country. */
  var TIER_ZOOM = [0, 0, 1.4, 2.0, 2.9];

  /* Where the sun is overhead, right now.
     Declination from the day of the year, subsolar meridian from UTC. Both
     are first-order: good to a fraction of a degree, which is nothing beside
     the width of the dusk band they are used to draw. */
  function subsolar() {
    var now = new Date();
    var start = Date.UTC(now.getUTCFullYear(), 0, 1);
    var day = (Date.UTC(now.getUTCFullYear(), now.getUTCMonth(),
                        now.getUTCDate()) - start) / 86400000;
    var dec = -23.44 * Math.cos((360 / 365.24) * (day + 10) * RAD);
    var utcH = now.getUTCHours() + now.getUTCMinutes() / 60;
    var lon = 180 - utcH * 15;
    return vec(lon, dec);
  }
  var sun = subsolar();
  /* It moves 15 degrees an hour; recomputing once a minute is 0.25 degrees
     of error at worst and costs nothing. */
  setInterval(function () { sun = subsolar(); }, 60000);

  function css(name, dflt) {
    var v = getComputedStyle(document.body).getPropertyValue(name).trim();
    return v || dflt;
  }
  var pal = {};
  /* Taken from the page rather than hardcoded, so the globe's labels are
     set in the same face as everything else. */
  var LAB_FONT = 'system-ui, sans-serif';
  try {
    LAB_FONT = getComputedStyle(document.body).fontFamily || LAB_FONT;
  } catch (e) { /* older engines */ }

  function repalette() {
    var lt = document.body.classList.contains('light');
    pal = {
      sea:  css('--card', lt ? '#E4E7E2' : '#171C1B'),
      land: css('--border', lt ? '#CBCFC6' : '#2B312F'),
      edge: lt ? 'rgba(0,0,0,.18)' : 'rgba(255,255,255,.14)',
      grid: lt ? 'rgba(0,0,0,.07)' : 'rgba(255,255,255,.055)',
      limb: lt ? 'rgba(0,0,0,.25)' : 'rgba(255,255,255,.22)',
      /* Night is warm, not black -- a deep umber rather than a shadow, so
         the dark half still reads as earth. Dawn is almost nothing: a hint
         of warmth on the lit side rather than a brightening, which would
         fight the page. */
      night: lt ? 'rgba(58,48,38,0.30)' : 'rgba(10,9,8,0.62)',
      dawn:  lt ? 'rgba(196,164,132,0.00)' : 'rgba(196,164,132,0.045)',
      /* More saturated than the card accents they come from, and
         deliberately so: the land is warm sand now, and #C4A484 on sand is
         #C4A484 on #C9B59A -- the same colour, so AWS simply disappeared
         over Africa. Same hue families, enough chroma to separate, and a
         dark ring under them so they still read on the ocean. */
      /* NOT theme-dependent, and that was the bug. These sit on the
         texture, which is the same map whichever way the page is set, so a
         light-mode variant meant a dark dot and a dark region code on a dark
         halo -- unreadable, and only in light mode, which is why it survived
         every check run in the dark. */
      aws:  '#E09244',
      azure: '#7FB6E0',
      gcp:  '#A6CC5C',
      halo: 'rgba(12,10,9,0.70)',
      /* Label colours answer to the MAP, not to the page: the texture is the
         same in light mode and dark, so these do not flip with the theme.
         Dark text with a pale halo reads on warm sand and on dark water
         alike -- one colour cannot, which is what the halo is for. */
      lab: '#241F19',
      labHalo: 'rgba(238,233,223,0.72)',
      sealab: '#D6DEE4',
      sealabHalo: 'rgba(10,14,18,0.78)',
      codeHalo: 'rgba(12,10,9,0.82)'
    };
  }

  function resize() {
    var r = cv.getBoundingClientRect();
    if (r.width <= 0) { return; }
    var dpr = Math.min(window.devicePixelRatio || 1, 3);

    /* The overlay -- dots and every label -- always at the device's own
       density. Text is the one thing that must not be upscaled, and a few
       dozen glyphs cost nothing worth measuring. */
    var want = Math.max(1, Math.round(r.width * dpr));
    if (want !== size) { size = want; cv.width = size; cv.height = size; }
    /* How many canvas pixels to a CSS pixel. Anything meant to hold a fixed
       apparent size -- type, dot radius, hit radius -- is written in CSS
       pixels and multiplied by this, rather than taken as a fraction of the
       canvas, which silently halves it on a dense screen. */
    pxr = size / r.width;

    /* The earth is the expensive canvas, so the ladder spends THIS one.
       Tier 3 drops it to one device pixel per CSS pixel: a ninth of the fill
       on a 3x phone, and the browser scales the result back up. Softer
       coastlines under load is a fair trade; soft text was not. */
    var ecap = tier >= 3 ? 1 : (tier >= 2 ? 1.5 : 2);
    var ewant = Math.max(1, Math.round(r.width * Math.min(dpr, ecap)));
    if (ewant !== esize) {
      esize = ewant;
      if (ec) { ec.width = esize; ec.height = esize; }
    }
  }

  /* ---- the earth, on the GPU ----------------------------------------
     A single quad, with the sphere solved per pixel in the fragment shader.
     Same orthographic projection as the 2D code below -- centre of the disc
     is longitude lam, screen x is R*x1, screen y is R*y2 -- so the dots drawn
     on the canvas above land exactly where the texture says they should. */
  var ec = document.getElementById('cl-globe-earth');
  var gl = null, glU = {}, glTex = null, glQuad = null, glOn = false;

  var VERT =
    '#version 300 es\n' +
    'in vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }';

  var FRAG =
    '#version 300 es\n' +
    'precision highp float;\n' +
    'uniform sampler2D uTex; uniform vec2 uC; uniform float uR;\n' +
    'uniform mat3 uInv; uniform vec3 uSun; uniform float uGrat;\n' +
    'uniform float uNight;\n' +
    'out vec4 o;\n' +
    'const float PI = 3.141592653589793;\n' +
    'void main(){\n' +
    '  vec2 p = (gl_FragCoord.xy - uC) / uR;\n' +
    '  float r2 = dot(p, p);\n' +
    '  if (r2 > 1.0) discard;\n' +
    '  float z = sqrt(max(0.0, 1.0 - r2));\n' +
    '  vec3 w = uInv * vec3(p, z);\n' +
    '  float lat = asin(clamp(w.y, -1.0, 1.0));\n' +
    '  float lon = atan(w.x, w.z);\n' +
    '  vec2 uv = vec2(lon / (2.0 * PI) + 0.5, 0.5 - lat / PI);\n' +
    /* The 180th meridian is a discontinuity in uv but not on the earth. Left
       alone, the automatic derivative there is a whole texture wide, the
       sampler picks the smallest mip, and a blurred seam runs pole to pole.
       Taking the wrap out of the derivative is the whole fix. */
    '  vec2 dx = dFdx(uv), dy = dFdy(uv);\n' +
    '  dx.x -= round(dx.x); dy.x -= round(dy.x);\n' +
    /* And cap it. Longitude is singular at the poles -- every meridian
       meets there, so uv.x swings across the whole texture between
       neighbouring pixels and the sampler drops to the smallest mip.
       That drew a smeared dark band across the top of the globe. */
    '  float m = max(max(abs(dx.x), abs(dx.y)), max(abs(dy.x), abs(dy.y)));\n' +
    '  if (m > 0.012) { float k = 0.012 / m; dx *= k; dy *= k; }\n' +
    '  vec3 albedo = textureGrad(uTex, uv, dx, dy).rgb;\n' +
    /* Night is the same map held down and warmed, not a black mask: the
       regions on the dark side still have to be findable, and a cold black
       hemisphere would fight the rest of the page. */
    '  float lt = dot(w, uSun);\n' +
    '  float day = smoothstep(-0.10, 0.10, lt);\n' +
    '  vec3 night = albedo * uNight * vec3(1.06, 0.94, 0.80);\n' +
    '  vec3 col = mix(night, albedo, day);\n' +
    '  float dusk = 1.0 - abs(day * 2.0 - 1.0);\n' +
    '  col += vec3(0.20, 0.09, 0.02) * dusk * 0.55;\n' +
    /* A graticule drawn in screen space: fwidth gives the line a constant
       weight however far you have zoomed in, and the clamp keeps the seam
       from drawing itself as a line. */
    '  float a1 = lon * (180.0 / PI) / 30.0, a2 = lat * (180.0 / PI) / 30.0;\n' +
    '  float w1 = min(fwidth(a1), 0.06), w2 = min(fwidth(a2), 0.06);\n' +
    '  float d1 = abs(fract(a1 + 0.5) - 0.5), d2 = abs(fract(a2 + 0.5) - 0.5);\n' +
    '  float g = 1.0 - min(smoothstep(0.0, w1, d1), smoothstep(0.0, w2, d2));\n' +
    '  col = mix(col, col + vec3(0.05, 0.05, 0.04), g * uGrat);\n' +
    /* Limb darkening, then a thin bright atmosphere just inside the edge.
       Both are functions of z alone, which is what makes a flat disc read as
       a ball rather than as a circle with a map on it. */
    '  col *= 1.0 - 0.34 * pow(1.0 - z, 2.5);\n' +
    '  col += vec3(0.10, 0.12, 0.13) * pow(1.0 - z, 7.0);\n' +
    '  o = vec4(col, 1.0);\n' +
    '}';

  function shader(type, src) {
    var sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) { return null; }
    return sh;
  }

  function glInit() {
    if (!ec || !ec.getContext) { return; }
    var src = ec.getAttribute('data-src');
    if (!src) { return; }
    try {
      gl = ec.getContext('webgl2', { antialias: false, alpha: true,
                                     premultipliedAlpha: false });
    } catch (e) { gl = null; }
    if (!gl) { return; }               /* WebGL1 falls back to the 2D globe */

    var vs = shader(gl.VERTEX_SHADER, VERT);
    var fs = shader(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) { gl = null; return; }
    var pr = gl.createProgram();
    gl.attachShader(pr, vs); gl.attachShader(pr, fs); gl.linkProgram(pr);
    if (!gl.getProgramParameter(pr, gl.LINK_STATUS)) { gl = null; return; }
    gl.useProgram(pr);

    glQuad = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, glQuad);
    gl.bufferData(gl.ARRAY_BUFFER,
      new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    var loc = gl.getAttribLocation(pr, 'a');
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);

    glU = { C: gl.getUniformLocation(pr, 'uC'),
            R: gl.getUniformLocation(pr, 'uR'),
            inv: gl.getUniformLocation(pr, 'uInv'),
            sun: gl.getUniformLocation(pr, 'uSun'),
            grat: gl.getUniformLocation(pr, 'uGrat'),
            night: gl.getUniformLocation(pr, 'uNight') };

    glTex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, glTex);
    /* One opaque pixel until the real thing lands, so a slow connection
       shows the 2D globe rather than a hole. */
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA,
                  gl.UNSIGNED_BYTE, new Uint8Array([43, 55, 64, 255]));

    var im = new Image();
    im.decoding = 'async';
    im.onload = function () {
      gl.bindTexture(gl.TEXTURE_2D, glTex);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im);
      /* REPEAT across longitude because the map wraps; clamp down latitude
         because it does not -- wrapping there would show Antarctica at the
         north pole. */
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER,
                       gl.LINEAR_MIPMAP_LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.generateMipmap(gl.TEXTURE_2D);
      var ext = gl.getExtension('EXT_texture_filter_anisotropic');
      if (ext) {
        gl.texParameterf(gl.TEXTURE_2D, ext.TEXTURE_MAX_ANISOTROPY_EXT,
          Math.min(4, gl.getParameter(ext.MAX_TEXTURE_MAX_ANISOTROPY_EXT)));
      }
      glOn = true;
      ec.setAttribute('data-tex', 'base');
      ec.style.opacity = '1';
    };
    im.onerror = function () { glOn = false; };
    im.src = src;

    ec.addEventListener('webglcontextlost', function (e) {
      /* Preventing the default is what allows a restore; until then the 2D
         globe takes over, so the page never goes blank. */
      e.preventDefault(); glOn = false;
    });
    ec.addEventListener('webglcontextrestored', function () { glInit(); });
  }

  var hiAsked = false;
  function wantHi() {
    /* Past this the base texture is being enlarged rather than reduced, so
       this is the moment the extra 728KB starts buying something. */
    if (hiAsked || !gl || zoom < 2.4) { return; }
    var src = ec.getAttribute('data-hi');
    if (!src) { return; }
    /* 8192 needs 134MB of texture memory with its mipmaps. Most GPUs have
       it; the ones that do not report a smaller maximum, and the upload is
       checked for an error afterwards either way -- if it fails, the base
       texture is still bound and the globe carries on softer rather than
       blank. */
    if (gl.getParameter(gl.MAX_TEXTURE_SIZE) < 8192) { hiAsked = true; return; }
    hiAsked = true;
    var im = new Image();
    im.decoding = 'async';
    im.onload = function () {
      gl.bindTexture(gl.TEXTURE_2D, glTex);
      while (gl.getError() !== gl.NO_ERROR) { /* drain */ }
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, im);
      if (gl.getError() !== gl.NO_ERROR) {
        var fb = new Image();
        fb.onload = function () {
          gl.bindTexture(gl.TEXTURE_2D, glTex);
          gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA,
                        gl.UNSIGNED_BYTE, fb);
          gl.generateMipmap(gl.TEXTURE_2D);
        };
        fb.src = ec.getAttribute('data-src');
        ec.setAttribute('data-tex', 'base-after-hi-failed');
        return;
      }
      gl.generateMipmap(gl.TEXTURE_2D);
      /* Recorded on the element so the state is observable from outside.
         Whether an 8192 upload succeeded is otherwise invisible: it either
         silently works or silently falls back, and both look like a soft
         globe. */
      ec.setAttribute('data-tex', 'hi');
    };
    im.src = src;
  }

  function glDraw() {
    if (!esize) { esize = size; ec.width = esize; ec.height = esize; }
    gl.viewport(0, 0, esize, esize);
    gl.clearColor(0, 0, 0, 0);
    gl.clear(gl.COLOR_BUFFER_BIT);
    /* The earth's canvas may be smaller than the overlay's, so its geometry
       is the same view expressed in its own pixels. One scale factor, applied
       to the centre and the radius, keeps the two layers registered -- a dot
       drawn on the overlay still lands on the country under it. */
    var k = esize / size;
    gl.uniform2f(glU.C, esize / 2, esize / 2);
    gl.uniform1f(glU.R, R * k);
    gl.uniform3f(glU.sun, sun[0], sun[1], sun[2]);
    gl.uniform1f(glU.grat, 0.5);
    /* A night side that works on a cream page is not the one that works on a
       near-black page. The same map either way -- only how far it is held
       down changes, so the terminator stays in the same place. */
    gl.uniform1f(glU.night, document.body.classList.contains('light')
      ? 0.56 : 0.31);
    /* view -> world, which for an orthonormal rotation is its transpose.
       Column-major, because that is how GL reads a mat3. */
    gl.uniformMatrix3fv(glU.inv, false, new Float32Array([
      cl, 0, -sl,
      -sl * sp, cp, -cl * sp,
      sl * cp, sp, cl * cp]));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    wantHi();
  }

  /* The rotation, as four numbers reused by every point in the frame. */
  var sl = 0, cl = 1, sp = 0, cp = 1, R = 1, CX = 0, CY = 0;
  /* Zoom scales the sphere about the centre of the canvas. Six is about where
     a region's dot and its neighbours are clearly separate; past that the
     coastline data itself runs out of detail. */
  /* 12, not 6. The old ceiling was set when 4096 was the only texture and
     everything past about 2x was magnification; the sharp copy lifts that,
     so the limit can be about what is useful to look at rather than about
     what the picture can stand. At 12x the view holds roughly nine degrees
     of longitude -- a country, not a continent. */
  var ZMIN = 1, ZMAX = 12, zoom = 1, pxr = 1, esize = 0;
  /* Cached so the reset button's hidden flag and the canvas's touch-action
     are written on the frame they change rather than on all sixty of them. */
  var rstHome = null, cvOwns = null;
  function setView() {
    var l = lam * RAD, p = phi * RAD;
    sl = Math.sin(l); cl = Math.cos(l);
    sp = Math.sin(p); cp = Math.cos(p);
    R = size * 0.46 * zoom; CX = size / 2; CY = size / 2;
  }

  /* The view axis in world space -- the direction pointing at the viewer.
     A ring whose cap lies entirely on the far side of this is skipped.

     It must be the same direction the exact per-point test uses, and it was
     not: that test is z2 = y*sp + (x*sl + z*cl)*cp, which expands to a dot
     product with [cp*sl, sp, cp*cl], and this returned the x term negated --
     a mirrored axis, worst at 90 degrees from the start view and harmless at
     0. Whether it ever dropped a ring a reader would have seen, I could not
     measure: rendering the same frame with culling off, with this axis, and
     with the corrected one produced differences the same size as the
     run-to-run noise, because the adaptive detail tier and the clock-driven
     terminator both move between runs. The cull threshold is generous
     -- cos(cap + 90) = -sin(cap), so a ring goes only when it is clearly
     behind -- which would explain a mirror rarely changing the answer.

     Corrected regardless. The cheap test now agrees with the exact one, so
     it can only cull more correctly than it did. */
  function axis() {
    return [cp * sl, sp, cp * cl];
  }

  /* Any world vector, into view space. The same four numbers every point
     uses, so this costs no trigonometry either. */
  function toView(v) {
    var x1 = v[0] * cl - v[2] * sl;
    var z1 = v[0] * sl + v[2] * cl;
    return [x1, v[1] * cp - z1 * sp, v[1] * sp + z1 * cp];
  }

  function ringPath(r, ax, ay, az) {
    var d = ax * r.cx + ay * r.cy + az * r.cz;
    /* acos of the dot is the angle between the ring's centre and the
       viewer; anything further than 90 degrees plus its own radius cannot
       show a single point. */
    if (d < Math.cos(Math.min(Math.PI, r.cap + Math.PI / 2))) { return false; }
    var v = r.v, n = r.n, on = false, any = false;
    /* Tier 2 takes every second point. A coastline at 440px is already
       finer than a pixel, so what goes is detail nothing resolves. */
    var step = tier >= 2 ? 2 : 1;
    for (var i = 0; i < n; i += step) {
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

    if (glOn) {
      /* The GPU has the earth; this canvas is only the dots from here on. */
      glDraw();
    } else {

    ctx.beginPath(); ctx.arc(CX, CY, R, 0, 6.283185);
    ctx.fillStyle = pal.sea; ctx.fill();

    /* One path for the whole graticule, one stroke. First thing dropped
       when the frame is running long: it is scaffolding, and the globe
       still reads as a globe without it. */
    if (tier < 1) {
      ctx.lineWidth = Math.max(1, size / 900);
      ctx.strokeStyle = pal.grid;
      ctx.beginPath();
      for (var g = 0; g < grat.length; g++) { ringPath(grat[g], ax, ay, az); }
      ctx.stroke();
    }

    /* One path for every visible landmass, one fill and one stroke. */
    ctx.beginPath();
    for (var i = 0; i < land.length; i++) {
      if (ringPath(land[i], ax, ay, az)) { ctx.closePath(); }
    }
    ctx.fillStyle = pal.land; ctx.fill();
    ctx.strokeStyle = pal.edge; ctx.stroke();

    /* Night, as a band rather than an edge.
       The gradient runs along the projected direction of the sun, and its
       midpoint is pushed along that axis by the sun's z -- the first-order
       correction for the fact that the near side of a sphere leans toward
       or away from the light. The softness is the atmosphere: the real
       terminator is hundreds of kilometres wide, and a hard line would be a
       precise drawing of something that is not precise. */
    var sv = toView(sun);
    var m = Math.sqrt(sv[0] * sv[0] + sv[1] * sv[1]);
    ctx.save();
    ctx.beginPath(); ctx.arc(CX, CY, R, 0, 6.283185); ctx.clip();
    if (m > 0.02) {
      var ux = sv[0] / m, uy = -sv[1] / m;          /* screen-space sunward */
      var g = ctx.createLinearGradient(CX - ux * R, CY - uy * R,
                                       CX + ux * R, CY + uy * R);
      /* sv[2] is how far the sun lies toward the viewer, so it says how
         much of the visible face is lit: the centre of an orthographic disc
         is lit exactly when sv[2] > 0. More sun toward us therefore means
         LESS night, so the night stop has to retreat -- and it was
         advancing. The whole thing was inverted. Measured across twelve
         rotations, eleven showed daylight where the sun was down and night
         where it was up, which is the "every country is showing like day"
         that was reported. The degenerate branch below always had the sign
         right, which is part of why this read as plausible. */
      var mid = Math.max(0.12, Math.min(0.88, 0.5 - sv[2] * 0.42));
      var soft = 0.17;
      g.addColorStop(0, pal.night);
      g.addColorStop(Math.max(0, mid - soft), pal.night);
      g.addColorStop(Math.min(1, mid + soft), pal.dawn);
      g.addColorStop(1, pal.dawn);
      ctx.fillStyle = g;
    } else {
      /* The sun is straight through the globe or straight at the viewer;
         the axis is degenerate, so shade the whole disc evenly. */
      ctx.fillStyle = sv[2] > 0 ? pal.dawn : pal.night;
    }
    ctx.fillRect(CX - R, CY - R, R * 2, R * 2);
    ctx.restore();

    ctx.beginPath(); ctx.arc(CX, CY, R, 0, 6.283185);
    ctx.strokeStyle = pal.limb;
    ctx.lineWidth = Math.max(1, size / 700); ctx.stroke();
    }

    /* Regions last, so a dot is never buried under a coastline. Three
       clouds share a city often enough that an offset is needed -- the flat
       map nudges them apart the same way, by a triangle rather than a line,
       so a stack of three reads as three and not one fat dot.
       Grouped by cloud so the fill colour is set three times, not 147. */
    var off = { aws: [-1.6, -1.0], azure: [1.6, -1.0], gcp: [0, 1.7] };
    /* Just over four CSS pixels of radius. size/155 came out at 2.3 on a
       phone, which is a four-pixel dot carrying the whole point of the page. */
    var rad = Math.max(3.6 * pxr, size / 150);
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
        if (z2 < 0) { rg.on = false; continue; }
        var px = CX + R * x1 + o[0] * sc, py = CY - R * y2 + o[1] * sc;
        /* Kept for the hit test: the position actually drawn, not one
           re-projected a frame later while the earth has moved on. */
        rg.sx = px; rg.sy = py; rg.on = true;
        ctx.moveTo(px + rad, py);
        ctx.arc(px, py, rad, 0, 6.283185);
      }
      /* Ringed before filling, so the dark edge sits under the colour
         rather than over the next dot along. */
      ctx.strokeStyle = pal.halo;
      ctx.lineWidth = Math.max(1.1, size / 420);
      ctx.stroke();
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    drawLabels(rad);

    if (picked && picked.on) {
      ctx.beginPath();
      ctx.arc(picked.sx, picked.sy, rad * 2.6, 0, 6.283185);
      ctx.strokeStyle = pal[picked.cloud] || pal.limb;
      ctx.lineWidth = Math.max(1.2, size / 440);
      ctx.stroke();
    }
  }

  function hits(b, boxes) {
    for (var i = 0; i < boxes.length; i++) {
      var o = boxes[i];
      if (b[0] < o[0] + o[2] && b[0] + b[2] > o[0]
          && b[1] < o[1] + o[3] && b[1] + b[3] > o[1]) { return true; }
    }
    return false;
  }

  function label(txt, px, py, fs, centred, fill, halo, boxes) {
    var w = ctx.measureText(txt).width;
    var bx = centred ? px - w / 2 - 2 : px + 2;
    var box = [bx - 1, py - fs * 0.62, w + 6, fs * 1.24];
    /* Inside the DISC, not merely inside the canvas. A name near the limb
       whose box fits the canvas still hangs off the edge of the globe and
       onto the page behind it, which is where "Baghdad" was ending up. Both
       far corners are tested, so a wide name at the edge is dropped rather
       than half-drawn. */
    if (box[0] < 2 || box[0] + box[2] > size - 2
        || box[1] < 2 || box[1] + box[3] > size - 2) { return false; }
    /* The visible area is the SMALLER of two circles: the sphere's disc, and
       the canvas itself, which CSS clips to a circle with border-radius.
       Zoomed in, R is several times the canvas, so testing against R alone
       let names run under the mask and come out sliced. */
    var lim = Math.min(R, size * 0.5) * 0.985;
    var c1x = box[0] - CX, c2x = box[0] + box[2] - CX;
    var c1y = box[1] - CY, c2y = box[1] + box[3] - CY;
    var far = Math.max(Math.abs(c1x), Math.abs(c2x));
    var fay = Math.max(Math.abs(c1y), Math.abs(c2y));
    if (far * far + fay * fay > lim * lim) { return false; }
    if (hits(box, boxes)) { return false; }
    boxes.push(box);
    /* Stroked first, then filled. The halo is what makes one colour work on
       warm sand and on dark water, which no single text colour does. */
    ctx.strokeStyle = halo;
    ctx.lineWidth = Math.max(1.8, fs * 0.22);
    ctx.lineJoin = 'round';
    ctx.strokeText(txt, bx + 1, py);
    ctx.fillStyle = fill;
    ctx.fillText(txt, bx + 1, py);
    return true;
  }

  function drawLabels(rad) {
    /* About 12 CSS pixels, with a little growth on a large globe. The
       old size/64 was the CSS width over 64 once the device ratio cancelled
       -- five and a half pixels on a phone. */
    var fs = Math.max(10.5 * pxr, size / 58);
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';

    /* The dots reserve their ground before any name is placed, so a label
       never lands on the thing the page is actually about. */
    var boxes = [];
    var i, r;
    for (i = 0; i < regions.length; i++) {
      r = regions[i];
      if (r.on) {
        boxes.push([r.sx - rad * 1.5, r.sy - rad * 1.5, rad * 3, rad * 3]);
      }
    }

    /* The region's own code, once there is room for it. This is the "instead
       of clicking it, at least we know" part -- us-east-1 beside the dot. */
    if (zoom >= 1.7) {
      ctx.font = '600 ' + Math.round(fs * 0.92) + 'px ' + LAB_FONT;
      for (i = 0; i < regions.length; i++) {
        r = regions[i];
        if (!r.on || !r.code) { continue; }
        /* Clear of the dot's own reservation, not inside it. Placed at
           1.6x the radius against a box reserved to 2x, every region code
           collided with its own dot and was dropped -- so not one of them
           ever drew, which is the half of "at least we know what it is"
           that matters most. */
        label(r.code, r.sx + rad * 1.9, r.sy, fs * 0.92, false,
              pal[r.cloud] || pal.lab, pal.codeHalo, boxes);
      }
    }

    /* Density rises with the zoom but more slowly than the room does: at 6x
       the view holds a country, and forty names on one country is a list,
       not a map. */
    var cap = Math.round(10 + 6 * zoom), placed = 0;
    ctx.font = Math.round(fs) + 'px ' + LAB_FONT;
    var lastSea = null;
    for (i = 0; i < places.length && placed < cap; i++) {
      var q = places[i];
      if (zoom < TIER_ZOOM[q.t]) { continue; }
      var x1 = q.x * cl - q.z * sl;
      var z1 = q.x * sl + q.z * cl;
      var y2 = q.y * cp - z1 * sp;
      var z2 = q.y * sp + z1 * cp;
      /* Not merely on the near side: far enough round that the text is not
         sitting edge-on at the limb, where it would read as noise. */
      if (z2 < 0.18) { continue; }
      var px = CX + R * x1, py = CY - R * y2;
      if (px < -40 || px > size + 40 || py < -40 || py > size + 40) { continue; }

      if (q.sea !== lastSea) {
        ctx.font = (q.sea ? 'italic ' : '') + Math.round(fs) + 'px ' + LAB_FONT;
        lastSea = q.sea;
      }
      var ok;
      if (q.sea) {
        ok = label(q.n, px, py, fs, true, pal.sealab, pal.sealabHalo, boxes);
      } else {
        ok = label(q.n, px + 3, py, fs, false, pal.lab, pal.labHalo, boxes);
        if (ok) {
          /* A city is a point, and a name with no anchor floats. */
          ctx.beginPath();
          ctx.arc(px, py, Math.max(1.1, fs * 0.13), 0, 6.283185);
          ctx.fillStyle = pal.lab;
          ctx.fill();
        }
      }
      if (ok) { placed++; }
    }
  }

  /* What the reader last asked about. Drawn with a ring so the panel below
     and the dot above are obviously the same thing. */
  var picked = null;
  var panel = document.getElementById('cl-globe-say');

  var CLOUD_NAME = { aws: 'AWS', azure: 'Azure', gcp: 'Google Cloud' };
  function say(r) {
    if (!panel) { return; }
    if (!r) {
      panel.innerHTML = '<span class="cl-say-idle">Click a dot for the '
        + 'region, where it is, and how many availability zones it has.'
        + '</span>';
      return;
    }
    /* Some regions name a country as their city -- eu-west-1 is "Ireland,
       Ireland" and europe-west is "Netherlands, Netherlands". The vendor
       publishes it that way; repeating it is ours. */
    var where = r.city && r.city !== r.country
      ? r.city + ', ' + r.country
      : (r.city || r.country || '');
    /* Zone counts are the vendor's own az_n. Where a vendor does not
       publish one it says so rather than printing a zero, which would read
       as a region with no zones. */
    var z = r.zones > 0
      ? (r.zones + ' availability zone' + (r.zones === 1 ? '' : 's'))
      : 'zone count not published';
    panel.innerHTML =
      '<b class="cl-say-' + r.cloud + '">' + CLOUD_NAME[r.cloud] + '</b> '
      + '<span class="cl-say-name"></span>'
      + '<span class="cl-say-meta"></span>';
    panel.querySelector('.cl-say-name').textContent = r.name;
    panel.querySelector('.cl-say-meta').textContent =
      (r.code ? r.code + ' \u00b7 ' : '') + (where ? where + ' \u00b7 ' : '')
      + z;
  }

  /* The radius is passed in rather than fixed, because 18 canvas pixels is
     18 CSS pixels on a desktop and six on a 3x phone -- a touch target
     smaller than the dot it is meant to catch. */
  function pick(mx, my, rad) {
    var best = null, bestD = rad * rad;
    for (var i = 0; i < regions.length; i++) {
      var r = regions[i];
      if (!r.on) { continue; }
      var dx = r.sx - mx, dy = r.sy - my, d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = r; }
    }
    return best;
  }

  /* Time, not frames. A 120Hz display span this at double speed when the
     step was a constant per frame. */
  /* Doubled, because a full turn took nearly two minutes and read as
     stalled. Divided by the square root of the zoom so that closing in does
     not turn a slow drift into a blur: at 6x the ground is six times nearer
     the eye, and the same angular rate would sweep past far too fast. */
  var DEG_PER_SEC = 6.4;

  /* Spend detail to hold the frame rate.
     -----------------------------------------------------------------------
     Measured at 4x CPU throttling the full-detail globe runs at 20fps while
     the rest of the site holds 60. Rather than pick one quality and be wrong
     on half the devices, the globe watches its own cost and steps down --
     graticule first, because it is scaffolding; then coastline density,
     because the silhouette survives it; then resolution. It climbs back as
     soon as it can.

     Twelve frames have to agree before the tier moves. One slow frame is a
     garbage collection or another tab waking up, and reacting to it would
     make the picture flicker between levels, which is worse than the
     stutter it was trying to cure. */
  var tier = 0, budget = 0, overCount = 0, underCount = 0;
  function spend(cost) {
    /* cost is the frame INTERVAL, not the time spent in draw(). On the GPU
       path draw() only queues commands and returns, so timing it would
       report a comfortable millisecond on a device dropping half its frames.
       The interval is also simply the better measurement: it is the thing a
       reader can see.

       26ms is about 38fps -- below that it reads as stutter. 18ms is a
       whisker above a healthy 60Hz frame, so a steady 16.7 climbs back. */
    if (cost > 26) {
      overCount++; underCount = 0;
      if (overCount >= 12 && tier < 3) { tier++; overCount = 0; resize(); }
    } else if (cost < 18) {
      underCount++; overCount = 0;
      if (underCount >= 12 && tier > 0) { tier--; underCount = 0; resize(); }
    } else { overCount = 0; underCount = 0; }
  }

  function frame(now) {
    if (!last) { last = now; }
    var dt = Math.min(now - last, 50) / 1000;
    last = now;
    /* Earth turns east, so for a fixed viewer the longitude underneath
       them runs west and the surface drifts to the RIGHT across the disc:
       omega(north) x r(toward viewer) points screen-right. lam is that
       viewer longitude, so it decreases.

       The page already asserts this elsewhere -- subsolar() computes the
       sun's meridian as 180 - utcH * 15, which decreases through the day
       for the same reason. It spun backwards, and against its own sun. */
    if (ease) {
      /* Time-based, so it lands in the same third of a second on a 60Hz
         panel and on a 120Hz one. */
      var ek = 1 - Math.pow(0.0001, dt);
      var ed = ((ease.lam - lam + 540) % 360) - 180;   /* the short way round */
      lam += ed * ek;
      phi += (ease.phi - phi) * ek;
      zoom += (ease.zoom - zoom) * ek;
      idleUntil = now + 2500;
      if (Math.abs(ed) < 0.15 && Math.abs(ease.phi - phi) < 0.15
          && Math.abs(ease.zoom - zoom) < 0.005) {
        lam = ease.lam; phi = ease.phi; zoom = ease.zoom; ease = null;
      }
    }
    if (!drag && !ease && now > idleUntil && !still) {
      lam -= DEG_PER_SEC * dt / Math.sqrt(zoom);
    }
    var home = zoom <= ZMIN + 0.01 && Math.abs(phi - 20) < 0.5;
    if (rst && home !== rstHome) { rstHome = home; rst.hidden = home; }

    /* Who gets a vertical swipe, decided by whether the reader has zoomed in.
       pan-y at rest means the page scrolls past the globe -- it is 45% of a
       phone screen, and trapping that was the first complaint. none once
       zoomed means the globe holds still under your finger while you work
       it, which was the second.

       Only ever changed between gestures. Rewriting touch-action in the
       middle of a pinch makes the browser reconsider the gesture it is
       already delivering, and it cancels the pointers -- so the zoom that
       triggered the change would kill the pinch that caused it. */
    var owns = engaged || zoom > ZMIN + 0.01;
    if (owns !== cvOwns && live.length === 0) {
      cvOwns = owns;
      cv.style.touchAction = owns ? 'none' : 'pan-y';
    }
    draw();
    /* Seeded on the first frame rather than from zero, or the average spends
       its first second climbing out of a value no frame ever had. */
    budget = budget ? budget * 0.85 + (dt * 1000) * 0.15 : dt * 1000;
    spend(budget);
    requestAnimationFrame(frame);
  }

  /* ---- gestures -----------------------------------------------------
     Every pointer is tracked, not only the latest one. The old code kept a
     single `drag` and rewrote it on every pointerdown, so the second finger
     of a pinch moved the rotation origin to itself and the globe lurched --
     which is most of what "the scrolling is not seamless" was.

     One pointer turns the globe. Two pinch to zoom, and their midpoint pans,
     which is how you reach a place rather than only the centre. */
  var live = [], pinch = null, ease = null;
  /* Whether the reader has told the globe they are working it. Tapping says
     so; so does zooming. Until then a vertical swipe belongs to the page,
     because the globe is 45% of a phone screen and trapping the scroll was
     the first thing reported about it. */
  var engaged = false;
  var gbox = cv.parentNode;
  var rel = null;
  function engage(v) {
    if (engaged === v) { return; }
    engaged = v;
    if (gbox && gbox.classList) { gbox.classList.toggle('cl-on', v); }
    if (rel) { rel.hidden = !v; }
  }

  function at(id) {
    for (var i = 0; i < live.length; i++) {
      if (live[i].id === id) { return live[i]; }
    }
    return null;
  }
  function gap() {
    var dx = live[0].x - live[1].x, dy = live[0].y - live[1].y;
    return Math.sqrt(dx * dx + dy * dy) || 1;
  }
  function mid() {
    return [(live[0].x + live[1].x) / 2, (live[0].y + live[1].y) / 2];
  }

  cv.addEventListener('pointerdown', function (e) {
    try { cv.setPointerCapture(e.pointerId); } catch (ex) { /* older engines */ }
    live.push({ id: e.pointerId, x: e.clientX, y: e.clientY,
                x0: e.clientX, y0: e.clientY,
                touch: e.pointerType === 'touch' });
    ease = null;
    if (live.length === 1) {
      drag = { x: e.clientX, y: e.clientY, lam: lam, phi: phi };
    } else if (live.length === 2) {
      var m = mid();
      pinch = { d: gap(), z: zoom, mx: m[0], my: m[1], lam: lam, phi: phi };
      live[0].gest = true; live[1].gest = true;
    }
  });

  cv.addEventListener('pointermove', function (e) {
    var p = at(e.pointerId);
    if (!p) { return; }
    p.x = e.clientX; p.y = e.clientY;

    if (pinch && live.length >= 2) {
      zoom = Math.max(ZMIN, Math.min(ZMAX, pinch.z * (gap() / pinch.d)));
      var m2 = mid(), gz = 0.32 / zoom;
      lam = pinch.lam - (m2[0] - pinch.mx) * gz;
      phi = Math.max(-90, Math.min(90, pinch.phi + (m2[1] - pinch.my) * gz));
      return;
    }
    if (!drag) { return; }

    /* Both deltas subtract because lam and phi describe where the VIEWER is,
       not where the surface is, and dragging moves the surface. A point sits
       at x1 = sin(lon - lam), so raising lam carries it left; raising phi
       lifts the viewer north, which carries the surface down. The arrow keys
       keep the opposite sense on purpose -- they move the viewpoint, which is
       why ArrowRight still looks further east. */
    var dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (p.touch && !engaged && zoom <= ZMIN + 0.01) {
      /* A thumb never swipes straight, and the two axes shared one gain, so
         a 300px swipe left with 40px of drift also tilted the globe 13
         degrees -- "my finger says left and it goes up or down". The first
         10px of travel pick the axis and the rest of the gesture keeps it.

         Only while the globe is at rest. Then vertical belongs to the page,
         so a vertical component is drift by definition and throwing it away
         costs nothing. Zoomed in the globe owns both axes, a vertical swipe
         is a real instruction, and locking it out would be the second half
         of the same bug. */
      /* Discarded outright rather than locked to whichever axis dominates.
         At rest the vertical gesture is the page's, so the globe has no use
         for a vertical component under any circumstances -- and choosing an
         axis would leave the globe tilting on a device or engine that
         delivers the gesture instead of cancelling it for the scroll. One
         rule, no dependence on who cancels what. */
      dy = 0;
    }
    /* Divided by the zoom, or one pixel of finger sweeps six times as far
       when you are six times closer. */
    var g = 0.32 / zoom;
    lam = drag.lam - dx * g;
    /* +-90, not +-78. The old clamp stopped 12 degrees short of the pole,
       so the Arctic and the Antarctic could not be looked at directly. At
       exactly 90 the pole sits at the centre of the disc and lam turns the
       map in its own plane, which is the right behaviour there and not a
       degenerate case. North stays up by design: the globe can bring any
       point on earth to the centre, but it will not tip past the pole and
       hang upside down, because a map that does that is unreadable. */
    phi = Math.max(-90, Math.min(90, drag.phi + dy * g));
    if (Math.abs(dx) + Math.abs(dy) > 6) { p.gest = true; }
  });

  function toCanvas(cx, cy) {
    var b = cv.getBoundingClientRect(), k = size / b.width;
    return [(cx - b.left) * k, (cy - b.top) * k, k];
  }

  var lastTap = 0, lastX = 0, lastY = 0, lastHit = null;
  function tap(cx, cy) {
    var now = performance.now();
    var near = (now - lastTap < 330)
      && (Math.abs(cx - lastX) + Math.abs(cy - lastY) < 30);
    lastTap = now; lastX = cx; lastY = cy;

    /* The tap that asks what a dot is, is also the tap that says "I am
       working this". One gesture, both meanings, which is why it does not
       need a separate control to arm it. */
    engage(true);
    var c = toCanvas(cx, cy);
    var hit = pick(c[0], c[1], 22 * c[2]);
    /* The second tap has to land on the SAME region as the first, or
       quickly inspecting two dots that sit beside each other reads as
       "take me to this one" and the globe flies off mid-sentence. Time and
       distance alone are not enough to tell a double-tap from two taps. */
    var dbl = near && hit === lastHit;
    lastHit = hit;
    picked = hit;
    say(hit);
    if (hit) { idleUntil = performance.now() + 6000; }

    /* Double-tap is "take me there": the region eases to the centre and the
       view closes in on it. A single tap only answers what it is. "I can't
       zoom to a location" was both halves -- no zoom, and no way to say
       which place. */
    if (dbl) {
      if (hit) {
        ease = { lam: hit.lon, phi: Math.max(-90, Math.min(90, hit.lat)),
                 zoom: Math.min(ZMAX, Math.max(2.6, zoom * 1.9)) };
      } else if (zoom > ZMIN + 0.01) {
        ease = { lam: lam, phi: 20, zoom: ZMIN };
      } else {
        ease = { lam: lam, phi: phi, zoom: 2.6 };
      }
    }
  }
  function release(e, cancelled) {
    var p = at(e.pointerId);
    for (var i = live.length - 1; i >= 0; i--) {
      if (live[i].id === e.pointerId) { live.splice(i, 1); }
    }
    if (live.length < 2) { pinch = null; }

    if (live.length === 0) {
      drag = null;
      idleUntil = performance.now() + 2500;
      /* A tap is a question, a drag is a drag, and a gesture the browser took
         over to scroll the page is neither -- pointercancel must not read as
         a tap, or scrolling past the globe would select a region on the way.
         Six pixels of slop, because a finger never lands perfectly still. */
      if (p && !cancelled && !p.gest) {
        var moved = Math.abs(p.x - p.x0) + Math.abs(p.y - p.y0);
        if (moved <= 6) { tap(p.x, p.y); }
      }
    } else if (live.length === 1) {
      /* A finger lifted off a pinch: carry on turning from where the
         remaining one actually is, not from where the first one landed. */
      drag = { x: live[0].x, y: live[0].y, lam: lam, phi: phi };
    }
  }
  cv.addEventListener('pointerup', function (e) { release(e, false); });
  cv.addEventListener('pointercancel', function (e) { release(e, true); });

  /* Ctrl+wheel, not plain wheel. A trackpad pinch arrives as ctrl+wheel, so
     this is the gesture people already use to zoom -- and a plain wheel that
     zoomed would have to preventDefault, which would trap the page scroll on
     a desktop exactly as touch-action:none trapped it on a phone. */
  cv.addEventListener('wheel', function (e) {
    if (!e.ctrlKey) { return; }
    e.preventDefault();
    ease = null;
    zoom = Math.max(ZMIN, Math.min(ZMAX, zoom * Math.exp(-e.deltaY * 0.0022)));
    idleUntil = performance.now() + 2500;
  }, { passive: false });

  var rst = document.getElementById('cl-globe-reset');
  if (rst) {
    rst.addEventListener('click', function () {
      /* Longitude is kept: resetting the view should not also lose the part
         of the world you were looking at. */
      ease = { lam: lam, phi: 20, zoom: ZMIN };
      engage(false);
    });
  }
  rel = document.getElementById('cl-globe-release');
  if (rel) {
    rel.addEventListener('click', function () { engage(false); });
  }
  /* Tapping anywhere else is the plainest way to say you are done with it,
     and it costs no chrome. Escape does the same for a keyboard. */
  document.addEventListener('pointerdown', function (e) {
    if (engaged && gbox && !gbox.contains(e.target)
        && e.target !== rel && e.target !== rst) {
      engage(false);
    }
  }, true);
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && engaged) { engage(false); cv.blur(); }
  });

  cv.setAttribute('tabindex', '0');
  cv.addEventListener('keydown', function (e) {
    var k = e.key, step = e.shiftKey ? 15 : 5, hit = true;
    if (k === 'ArrowLeft') { lam -= step; }
    else if (k === 'ArrowRight') { lam += step; }
    else if (k === 'ArrowUp') { phi = Math.min(90, phi + step); }
    else if (k === 'ArrowDown') { phi = Math.max(-90, phi - step); }
    else if (k === 'Enter' || k === ' ') {
      /* Step through the regions currently facing the reader, so the panel
         is reachable without a pointer. */
      var vis = regions.filter(function (r) { return r.on; });
      if (vis.length) {
        var at = vis.indexOf(picked);
        picked = vis[(at + 1) % vis.length];
        say(picked);
        idleUntil = performance.now() + 6000;
      }
      e.preventDefault(); return;
    }
    else if (k === '+' || k === '=') { zoom = Math.min(ZMAX, zoom * 1.3); }
    else if (k === '-' || k === '_') { zoom = Math.max(ZMIN, zoom / 1.3); }
    else if (k === '0') { ease = { lam: lam, phi: 20, zoom: ZMIN }; }
    else { hit = false; }
    if (hit) { idleUntil = performance.now() + 2500; e.preventDefault(); }
  });

  window.addEventListener('resize', resize);
  if (window.MutationObserver) {
    new MutationObserver(repalette).observe(document.body,
      { attributes: true, attributeFilter: ['class'] });
  }
  glInit();
  repalette();
  resize();
  say(null);
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
/* pan-y, not none. The globe is 352px tall on a 390px phone -- 45% of the
   screen -- and touch-action:none means the browser does no panning at all,
   so a swipe that began on it could never scroll the page. Reported as "I
   can't scroll easily", and it was not a matter of feel: it was impossible.

   Vertical now belongs to the page and horizontal to the globe, which also
   settles "when I say left it has to go left". Tilting by touch moves to two
   fingers, where there is no scroll gesture to compete with. */
/* The earth sits behind the interactive canvas and takes no pointer
   events, so every handler, the focus ring, touch-action and the hit test
   stay attached to #cl-globe exactly as before. */
.cl-globe-earth{position:absolute;left:0;top:0;width:100%;height:100%;
  display:block;border-radius:50%;pointer-events:none;z-index:0}
/* position+z-index on the dot layer, and not only on the earth. A positioned
   element paints above a static one whatever the source order, so the earth
   was covering every dot that fell inside the disc -- the only ones visible
   were those near the limb, showing through where the shader discards. */
.cl-globe{position:relative;z-index:1;
  width:100%;height:100%;display:block;border-radius:50%;
  touch-action:pan-y;cursor:grab}
.cl-globe-reset{display:inline-block;margin-left:.5rem;padding:.12rem .5rem;
  font:inherit;font-size:.72rem;color:var(--text-muted);background:none;
  border:1px solid var(--border, rgba(255,255,255,.16));border-radius:999px;
  cursor:pointer}
.cl-globe-reset:hover{color:#C4A484;border-color:#C4A484}
.cl-globe-release{color:#C4A484;border-color:rgba(196,164,132,.45)}
/* The ring is the whole affordance: without it "the globe has the gesture"
   is a state the reader can only discover by swiping and being surprised. */
.cl-globe-box.cl-on::after{content:"";position:absolute;left:-6px;top:-6px;
  right:-6px;bottom:-6px;border-radius:50%;pointer-events:none;
  border:1px solid rgba(196,164,132,.55)}
.cl-globe:active{cursor:grabbing}
.cl-globe:focus-visible{outline:2px solid var(--accent, #C4A484);
  outline-offset:6px}
.cl-globe-cap{margin:.75rem auto 0;max-width:520px;text-align:center;
  font-size:.78rem;color:var(--text-muted)}
body.light .cl-globe-cap{color:#605F5B}
/* The text the canvas cannot give a screen reader, and what shows when the
   script does not run. Closed by default -- it is 144 names, and it is an
   alternative to the picture rather than a second copy of the page. */
.cl-globe-say{margin:.6rem auto 0;max-width:520px;min-height:3.1em;
  text-align:center;font-size:.82rem;line-height:1.55}
.cl-say-idle{color:var(--text-muted)}
body.light .cl-say-idle{color:#605F5B}
.cl-globe-say b{display:block;font-size:.7rem;letter-spacing:.08em;
  text-transform:uppercase;font-family:var(--mono, ui-monospace, monospace)}
.cl-say-aws{color:#C4A484}   body.light .cl-say-aws{color:#7A5C3C}
.cl-say-azure{color:#8FB0C9} body.light .cl-say-azure{color:#3F5970}
.cl-say-gcp{color:#A8BA77}   body.light .cl-say-gcp{color:#4C6340}
.cl-say-name{display:block;color:var(--text)}
.cl-say-meta{display:block;color:var(--text-muted);font-size:.76rem}
body.light .cl-say-meta{color:#605F5B}
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
