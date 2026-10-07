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
        'Robinson projection, same basemap and same maths as the incident '
        'map. The other %d carry no published coordinates &mdash; they are '
        'almost all government and sovereign regions (us-gov, us-dod, '
        'eusc-de) plus a few announced since the geo data was last '
        'refreshed, so they are counted everywhere else on this page but '
        'cannot be drawn.</p>' % (plotted, len(regions), len(regions) - plotted),
        '<p class="cl-legend">%s</p>' % legend,
        svg,
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
