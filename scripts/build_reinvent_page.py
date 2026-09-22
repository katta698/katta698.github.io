#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render /reinvent-2026/ from the catalog store.

    python scripts/build_reinvent_page.py

Why this exists
---------------
The page this replaces was a bookmark. It said "Open catalog" six times, and
everything it offered the official catalog does better -- so it added nothing
a browser favourite would not. Asked for instead:

    "a unified web page ... they can search for a specific service, and the
     sessions are across multiple venues within Vegas, MGM Grand and all
     those stuff ... based on the role or based on the service type ...
     some creative way that adds value to my team during that whole event."

So this page holds the data, and it is built around the one question the
official catalog cannot answer.

THE THING THE CATALOG WILL NOT DO. Every session carries a room string --
"Caesars Palace | Promenade Level | Roman I" -- and a start and end minute.
The catalog will let you favourite a session ending 10:00 at MGM Grand and
another starting 10:30 at the Venetian without a word, because it never
compares the two. Those are at opposite ends of the Strip. This page walks
each day of your plan in order and says so.

WHAT IS A FACT HERE AND WHAT IS AN ESTIMATE. The two are not mixed, because
only one of them is checkable:

  FACT      These two sessions are at different properties, and the gap
            between them is N minutes. That is arithmetic on AWS's own
            published times and rooms, and it is what the warning states.

  ESTIMATE  How long the hop actually takes. AWS was checked and does not
            publish per-venue minutes -- its FAQ says only "allow for
            additional travel time between venues" and that shuttles "run
            continuously during conference hours". So the defaults below
            come from the campus geography, they are labelled as estimates
            on the page, and the reader can change them.

That distinction is the whole reason to trust the warning. A page that
quietly invents a shuttle timetable and presents it as AWS's would be worse
than no page, and it is exactly the sort of claim this repo's checks exist
to stop.

ROLE LANES, NOT ROLE FACETS. The catalog publishes 18 roles and
"Solution / Systems Architect" returns 729 sessions, which is not a filter.
The three lanes below are service clusters instead, and they are sharp:
connectivity, platform and compute land at a size a person can actually read
through. They are a starting point, not a cage -- every lane is one tap away
from the full catalog.
"""
import io
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from back_to_top import TOP_HTML, TOP_CSS, TOP_JS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "reinvent2026.json")
OUTDIR = os.path.join(ROOT, "reinvent-2026")

EVENT = {
    "name": "AWS re:Invent 2026",
    "start": "2026-11-30",
    "end": "2026-12-04",
    "city": "Las Vegas, NV",
}

# Each lane is matched case-insensitively as a substring against the
# catalog's own service names, so "elastic compute" catches
# "Amazon Elastic Compute Cloud (Amazon EC2)" without hardcoding the
# parenthetical AWS likes to change.
LANES = [
    {
        "id": "connectivity",
        "name": "Connectivity",
        "blurb": "Hybrid links, transit, edge, DNS and the paths between them.",
        "match": ["transit gateway", "direct connect", "cloud wan", "vpn",
                  "privatelink", "virtual private cloud", "vpc lattice",
                  "route 53", "global accelerator", "cloudfront",
                  "network firewall"],
    },
    {
        "id": "platform",
        "name": "Platform",
        "blurb": "Landing zones, identity, governance, observability, config.",
        "match": ["identity and access", "organizations", "control tower",
                  "cloudformation", "cloudwatch", "aws config", "cloudtrail",
                  "systems manager", "service catalog", "appconfig",
                  "well-architected", "trusted advisor"],
    },
    {
        "id": "compute",
        "name": "Compute / managed",
        "blurb": "EC2, containers, serverless and day-2 operations.",
        "match": ["elastic compute", "elastic container", "elastic kubernetes",
                  "lambda", "auto scaling", "fargate", "batch", "outposts",
                  "graviton", "image builder", "lightsail", "app runner"],
    },
]

# ---------------------------------------------------------------- geography
#
# The first version of this costed every hop with three numbers: 10 minutes
# inside a property, 30 within the northern run, 45 to or from MGM Grand.
# Measuring the actual distances showed that middle bucket was hiding a
# factor of two and was wrong in the direction that under-warns:
#
#     Venetian       -> Caesars Forum     616 m     a walk
#     Wynn/Encore    -> Caesars Palace   1443 m     nearly as far as...
#     Caesars Palace -> MGM Grand        1565 m     ...the "far" bucket
#
# So Wynn/Encore to Caesars Palace was costed at 30 minutes while a hop
# barely longer was costed at 45. Distance is a fact, and deriving the
# estimate from it is both more honest and less work to defend.
#
# Public landmark coordinates for the centre of each property. They are
# approximate -- these are large buildings -- and that is fine, because the
# quantity being derived is a rounded number of minutes.
VENUE_POINTS = {
    "Venetian":       (36.1212, -115.1697),
    "Wynn/Encore":    (36.1270, -115.1656),
    "Caesars Forum":  (36.1163, -115.1665),
    "Caesars Palace": (36.1162, -115.1745),
    "MGM Grand":      (36.1026, -115.1700),
}

# The model, with every number stated so it can be argued with. A straight
# line between two hotels is not a route, and walking the Strip is not
# walking down a street: it is casino floors, escalators, pedestrian
# bridges and crowds.
DETOUR = 1.30          # straight line -> the path you actually walk
PACE_M_PER_MIN = 60.0  # ~1 m/s, which is slow, because this is not a pavement
OVERHEAD_MIN = 10      # out of one room and into the next, at either end

OUTLIER = "MGM Grand"  # still named, for the page's plain-English wording


def metres(a, b):
    """Great-circle distance between two venue points."""
    import math
    lat1, lon1 = [math.radians(x) for x in a]
    lat2, lon2 = [math.radians(x) for x in b]
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371000.0 * math.asin(math.sqrt(h))


def venue_xy(venues):
    """Normalised 0..1 positions plus the true aspect of the bounding box.

    An equirectangular projection is wrong for a continent and exact enough
    for five buildings inside a square mile. Metres are computed on both
    axes so the drawing keeps the real proportions: the Strip runs roughly
    north-south, these venues span about 2.7 km that way and 0.8 km across,
    and a map that quietly squared that off would make MGM Grand look like
    a neighbour of the Venetian.
    """
    lats = [VENUE_POINTS[v][0] for v in venues]
    lons = [VENUE_POINTS[v][1] for v in venues]
    lo_la, hi_la = min(lats), max(lats)
    lo_lo, hi_lo = min(lons), max(lons)
    mid_la = (lo_la + hi_la) / 2.0

    span_y = metres((lo_la, lo_lo), (hi_la, lo_lo))      # north-south
    span_x = metres((mid_la, lo_lo), (mid_la, hi_lo))    # east-west

    out = {}
    for v in venues:
        la, lo = VENUE_POINTS[v]
        x = 0.5 if hi_lo == lo_lo else (lo - lo_lo) / (hi_lo - lo_lo)
        # y inverted: north at the top, which is how a map is read.
        y = 0.5 if hi_la == lo_la else 1.0 - (la - lo_la) / (hi_la - lo_la)
        out[v] = [round(x, 4), round(y, 4)]
    return {"pos": out, "span_x_m": int(round(span_x)),
            "span_y_m": int(round(span_y))}


def travel_model(venues):
    """{venue: {venue: {min, m}}} for every pair the store actually uses.

    Built here rather than in the browser so an unknown venue is a build
    failure with a name in it, not a silently missing warning for a reader
    standing in the wrong hotel.
    """
    unknown = [v for v in venues if v not in VENUE_POINTS]
    if unknown:
        raise SystemExit(
            "  the catalog now uses venue(s) with no coordinates: %s\n"
            "  Add them to VENUE_POINTS. Until then every hop involving one "
            "would be costed as if it were\n  next door, which is the "
            "failure that sends somebody to the wrong end of the Strip."
            % ", ".join(sorted(unknown)))

    out = {}
    for a in venues:
        out[a] = {}
        for b in venues:
            if a == b:
                out[a][b] = {"min": OVERHEAD_MIN, "m": 0}
                continue
            d = metres(VENUE_POINTS[a], VENUE_POINTS[b])
            mins = OVERHEAD_MIN + int(round(d * DETOUR / PACE_M_PER_MIN))
            out[a][b] = {"min": mins, "m": int(round(d))}
    return out


def read_store():
    if not os.path.exists(STORE):
        raise SystemExit(
            "  %s does not exist. Run:\n      python scripts/fetch_reinvent.py"
            % os.path.relpath(STORE, ROOT))
    return json.load(io.open(STORE, encoding="utf-8"))


def lane_indexes(store):
    """Resolve each lane's substrings to service indexes in this store.

    Done at build time rather than in the browser so that a lane which has
    stopped matching anything is a build failure here, not a silently empty
    tab for a reader.
    """
    services = store["facets"]["Services"]
    out = {}
    for lane in LANES:
        idx = [i for i, name in enumerate(services)
               if any(m in name.lower() for m in lane["match"])]
        if not idx:
            raise SystemExit(
                "  lane %r matched none of the %d service names in the store. "
                "AWS has renamed something; fix LANES rather than shipping an "
                "empty tab." % (lane["name"], len(services)))
        out[lane["id"]] = idx
    return out


def lane_counts(store, lanes):
    """How many sessions each lane holds, for the tab labels."""
    out = {}
    for lane_id, idx in lanes.items():
        want = set(idx)
        out[lane_id] = sum(1 for s in store["sessions"]
                           if want.intersection(s["sv"]))
    return out


def esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def pretty_date(iso):
    import datetime
    d = datetime.date(*[int(x) for x in iso.split("-")])
    return d.strftime("%a %-d %b") if os.name != "nt" else d.strftime(
        "%a %#d %b")


def build():
    store = read_store()
    lanes = lane_indexes(store)
    counts = lane_counts(store, lanes)
    sessions = store["sessions"]

    days = sorted({w["d"] for s in sessions for w in s["when"]})
    scheduled = sum(1 for s in sessions if s["when"])

    os.makedirs(OUTDIR, exist_ok=True)

    # The page reads the store in place, at its absolute path, rather
    # than getting a copy beside it. A copy meant the same 1.3 MB shipped
    # twice, and -- worse -- it could go stale against the store it was
    # copied from, which is the kind of drift nothing here would notice.

    config = {
        "lanes": [{"id": l["id"], "name": l["name"], "blurb": l["blurb"],
                   "services": lanes[l["id"]], "count": counts[l["id"]]}
                  for l in LANES],
        "travel": {
            "matrix": travel_model(store["venues"]),
            "outlier": OUTLIER,
            "overhead": OVERHEAD_MIN,
            "detour": DETOUR,
            "pace": PACE_M_PER_MIN,
            "points": {v: VENUE_POINTS[v] for v in store["venues"]},
        },
        "map": venue_xy(store["venues"]),
        "days": days,
        "event": EVENT,
    }

    html = PAGE.replace("__CONFIG__", json.dumps(config, separators=(",", ":")))
    html = html.replace("__TOTAL__", "{:,}".format(len(sessions)))
    html = html.replace("__SCHEDULED__", "{:,}".format(scheduled))
    html = html.replace("__CAPTURED__", esc(store.get("captured", "")))
    html = html.replace("__VENUES__", esc(", ".join(sorted(store["venues"]))))
    html = html.replace("__SERVICES__", str(len(store["facets"]["Services"])))
    html = html.replace("__LANETABS__", lane_tabs(config))
    html = html.replace("__OVERHEAD__", str(OVERHEAD_MIN))
    html = html.replace("__PACE__", str(int(PACE_M_PER_MIN)))
    html = html.replace("__DETOUR__", "%.2f" % DETOUR)
    html = html.replace("__OUTLIER__", esc(OUTLIER))
    html = html.replace("__TOP__", TOP_HTML + TOP_JS)

    write(os.path.join(OUTDIR, "index.html"), html)
    # The same control every other long page on the site carries, from the
    # one module that defines it -- not a second implementation. Its CSS
    # carries a literal on every var() because this page defines none of
    # blog.css's tokens, and an undefined custom property invalidates the
    # whole declaration rather than falling back: a transparent circle that
    # happens to be clickable. That has happened five times in this repo.
    write(os.path.join(OUTDIR, "page.css"), CSS + TOP_CSS + TOP_FIX)
    write(os.path.join(OUTDIR, "app.js"), APP)

    print("  reinvent-2026/  %d sessions, %d scheduled, %d day(s)"
          % (len(sessions), scheduled, len(days)))
    for lane in LANES:
        print("    %-18s %4d session(s) across %d service(s)"
              % (lane["name"], counts[lane["id"]], len(lanes[lane["id"]])))
    for name in ("index.html", "page.css", "app.js"):
        p = os.path.join(OUTDIR, name)
        print("    %-12s %7.1f KB" % (name, os.path.getsize(p) / 1024.0))
    print("    %-12s %7.1f KB  (read in place, not copied)"
          % ("the store", os.path.getsize(STORE) / 1024.0))
    return 0


def lane_tabs(config):
    # The "Everything" count is filled in by the app once the store loads,
    # so the number and the data it describes can never disagree.
    out = ['<button class="lane" data-lane="all" aria-pressed="true">'
           '<span class="ln">Everything</span>'
           '<span class="lc" data-count="all">&nbsp;</span></button>']
    for lane in config["lanes"]:
        out.append(
            '<button class="lane" data-lane="%s" aria-pressed="false">'
            '<span class="ln">%s</span>'
            '<span class="lc" data-count="%s">%d</span>'
            '<span class="lb">%s</span></button>'
            % (esc(lane["id"]), esc(lane["name"]), esc(lane["id"]),
               lane["count"], esc(lane["blurb"])))
    return "\n ".join(out)


def write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- the page

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#121816">
<meta name="color-scheme" content="dark">
<title>re:Invent 2026 planner - Jayanth Katta</title>
<link rel="canonical" href="https://jayanthkatta.com/reinvent-2026/">
<meta name="description" content="All __TOTAL__ AWS re:Invent 2026 sessions, searchable by service and filtered into connectivity, platform and compute lanes - with a plan that checks whether you can actually get between venues in time.">
<meta property="og:title" content="re:Invent 2026 planner">
<meta property="og:description" content="All __TOTAL__ sessions, searchable by service, with venue-hop checking the official catalog does not do.">
<meta property="og:url" content="https://jayanthkatta.com/reinvent-2026/">
<link rel="icon" href="/favicon-transparent.png" type="image/png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Mono:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="./page.css">
</head>
<body>
<main class="page">

 <header class="header">
  <p class="eyebrow">jayanthkatta.com</p>
  <h1>re:Invent 2026</h1>
  <p class="lede">Every session in the official catalog, searchable by service
   and grouped the way our teams actually split &mdash; with one thing the
   catalog will not do for you: tell you when two sessions you picked are at
   opposite ends of the Strip.</p>
  <ul class="facts">
   <li><span>When</span><strong>Nov 30 &ndash; Dec 4, 2026</strong></li>
   <li><span>Where</span><strong>Las Vegas, NV</strong></li>
   <li><span>Sessions</span><strong>__TOTAL__ <em>(__SCHEDULED__ scheduled)</em></strong></li>
   <li><span>Venues</span><strong>__VENUES__</strong></li>
  </ul>
 </header>

 <!-- Written by the page itself, in the reader's browser, from the capture
      timestamp in the store. Deliberately not baked in at build time: a
      build-time string says how old the data was when the page was made,
      which is the one number that is always reassuring and never true. -->
 <p id="fresh" class="fresh" role="status">Checking how current this is&hellip;</p>

 <nav class="lanes" aria-label="Team lanes">
 __LANETABS__
 </nav>

 <section class="controls" aria-label="Search and filters">
  <div class="searchrow">
   <input id="q" type="search" autocomplete="off"
    placeholder="Search title, abstract, session code, or one of __SERVICES__ services">
   <button id="clear" class="ghost" hidden>Clear</button>
  </div>
  <div id="filters" class="filters"></div>
  <div id="chips" class="chips"></div>
 </section>

 <section class="resultbar">
  <p id="count" class="count">Loading the catalog&hellip;</p>
  <div class="viewtabs" role="tablist">
   <button id="tab-browse" class="vt" role="tab" aria-selected="true">Browse</button>
   <button id="tab-plan" class="vt" role="tab" aria-selected="false">
    My plan <span id="planN" class="badge">0</span></button>
   <button id="tab-map" class="vt" role="tab" aria-selected="false">Map</button>
  </div>
 </section>

 <section id="browse" class="results"></section>

 <section id="plan" class="plan" hidden>
  <div id="planbody"></div>
  <div class="planfoot">
   <button id="share" class="ghost">Copy a link to this plan</button>
   <button id="wipe" class="ghost danger">Clear plan</button>
  </div>
 </section>

 <section id="map" class="mapwrap" hidden>
  <p class="maplede">Where the sessions actually are. Circle size is how many
   of the <b id="map-n">&nbsp;</b> sessions currently matching your filters sit
   at each property &mdash; so narrowing to a lane shows you where to base
   yourself. Pick a day to draw your plan's route across it.</p>
  <div class="maprow">
   <label>Route for
    <select id="map-day"><option value="">&mdash; no day selected &mdash;</option></select>
   </label>
  </div>
  <div id="mapsvg"></div>
  <div id="maphops" class="hops"></div>
 </section>

 <details class="about">
  <summary>How the venue warnings work, and what is a fact versus an estimate</summary>
  <p><strong>The fact.</strong> Every session in the catalog carries its room
   &mdash; <code>Caesars Palace | Promenade Level | Roman I</code> &mdash; and
   a start and end time. When two sessions in your plan are at different
   properties, the gap between them is arithmetic on AWS's own published data.
   That number is what the warning states, and you can check it against the
   official catalog using the session code on every card.</p>
  <p><strong>The estimate.</strong> How long the hop takes is not published
   &mdash; AWS's FAQ says only to &ldquo;allow for additional travel time
   between venues&rdquo; and that shuttles &ldquo;run continuously during
   conference hours&rdquo;. So it is derived rather than guessed: the
   straight-line distance between the two properties, multiplied by
   <strong>__DETOUR__</strong> because a line between two hotels is not a
   route, divided by a walking pace of <strong>__PACE__ m/min</strong>
   &mdash; slow on purpose, because this is casino floors and pedestrian
   bridges, not pavement &mdash; plus <strong>__OVERHEAD__ min</strong> to
   get out of one room and into the next.</p>
  <p>An earlier version used three flat numbers and was wrong in the
   direction that under-warns: it costed Wynn/Encore to Caesars Palace
   (1,443&nbsp;m) at 30 minutes while costing Caesars Palace to MGM Grand
   (1,565&nbsp;m) at 45. Distance is a fact; only the pace below is an
   assumption, and it is yours to set.</p>
  <p class="tune">Adjust:
   <label>room to room <input id="t-overhead" type="number" min="0" max="60" value="__OVERHEAD__"> min</label>
   <label>pace
    <select id="t-pace">
     <option value="80">brisk, moving early</option>
     <option value="60">steady (default)</option>
     <option value="45">slow, peak crowds</option>
    </select>
   </label>
  </p>
  <details class="matrix"><summary>Every pair, as this page costs it</summary>
   <div id="matrix"></div></details>
  <p><strong>The lanes</strong> are service clusters, not the catalog's Role
   facet. Role is too broad to filter on &mdash; &ldquo;Solution / Systems
   Architect&rdquo; alone returns hundreds of sessions. Each lane is a set of
   services, and every lane is one tap from the full catalog.</p>
  <p><strong>How current this is, and how you can tell.</strong> The catalog
   is re-fetched from AWS every day by a scheduled job, and the line at the
   top of this page works out its own age <em>in your browser</em> from the
   capture timestamp &mdash; so if the job ever stops running, the page says
   how old it is rather than quietly implying it is current. Three things
   guard the refresh: a fetch that comes back more than a fifth smaller than
   the stored catalog is refused rather than written, so a partial fetch
   cannot overwrite good data; the checks run before the commit, not after;
   and every session code on this page links to that session in AWS's own
   catalog, so nothing here has to be taken on trust. If a session you
   starred disappears from the catalog, your plan says so instead of quietly
   dropping it.</p>
  <p class="src">Session data captured from the official catalog on
   <time datetime="__CAPTURED__">__CAPTURED__</time>. This page is not
   affiliated with AWS and is not the system of record: sessions get added,
   moved and cancelled, and reserved seating happens in the
   <a href="https://registration.awsevents.com/flow/awsevents/reinvent2026/eventcatalog/page/eventcatalog" target="_blank" rel="noopener">official catalog</a>,
   not here.</p>
 </details>

 <footer class="footer">
  <p>Not affiliated with Amazon Web Services. Session data belongs to AWS.</p>
  <p><a href="/">jayanthkatta.com</a></p>
 </footer>
</main>
__TOP__

<script>window.RI_CONFIG = __CONFIG__;</script>
<script src="./app.js" defer></script>
</body>
</html>
"""


# ------------------------------------------------------------------- styles

CSS = """/* Generated by scripts/build_reinvent_page.py -- do not edit by hand. */
:root{
  --bg:#121816; --panel:#182220; --panel2:#1e2a27; --line:#2b3a36;
  --ink:#e8efec; --dim:#9fb3ad; --faint:#7d918c;
  --accent:#c4a484; --accent2:#8fb3a6;
  --warn:#e0a458; --bad:#d97757; --ok:#7fb069;
  --r:12px;
}
*{box-sizing:border-box}
/* A class that sets `display` outranks the user-agent rule for [hidden],
   so .lanes{display:grid} kept the lane tabs on screen in the plan view
   even with the attribute set. Anything hidden here must stay hidden. */
[hidden]{display:none!important}
html{-webkit-text-size-adjust:100%}
body{
  margin:0; background:var(--bg); color:var(--ink);
  font:400 16px/1.55 "DM Sans",system-ui,-apple-system,sans-serif;
}
.page{max-width:1080px; margin:0 auto; padding:28px 18px 64px}
a{color:var(--accent)}
code{font-family:"DM Mono",ui-monospace,monospace; font-size:.9em}

/* ---- header ---- */
.eyebrow{margin:0; font-size:12px; letter-spacing:.14em; text-transform:uppercase; color:var(--faint)}
h1{margin:.2em 0 .25em; font-size:clamp(30px,6vw,46px); line-height:1.05; letter-spacing:-.02em}
.lede{margin:0 0 20px; max-width:62ch; color:var(--dim)}
.facts{list-style:none; display:grid; gap:10px; padding:0; margin:0 0 26px;
  grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.facts li{background:var(--panel); border:1px solid var(--line); border-radius:var(--r); padding:10px 13px}
.facts span{display:block; font-size:11px; letter-spacing:.1em; text-transform:uppercase; color:var(--faint)}
.facts strong{font-weight:600; font-size:15px}
.facts em{font-style:normal; color:var(--faint); font-weight:400}


/* ---- map ---- */
.mapwrap{margin:0 0 10px}
.maplede{margin:0 0 12px; font-size:14px; color:var(--dim); max-width:74ch}
.maplede b{color:var(--ink)}
.maprow{margin:0 0 12px}
.maprow label{font-size:13.5px; color:var(--faint)}
.maprow select{
  font:inherit; font-size:14px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:7px 10px; margin-left:6px;
}
#mapsvg{background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:8px}
svg.rimap{width:100%; height:auto; display:block}
.rimap .vdot{fill:rgba(196,164,132,.16); stroke:var(--accent); stroke-width:1.5}
.rimap .vnum{fill:var(--ink); font:600 13px "DM Mono",monospace}
.rimap .vname{fill:var(--dim); font:500 12.5px "DM Sans",sans-serif}
.rimap .hop{stroke-width:3; stroke-linecap:round}
.rimap .hop.ok{stroke:#7fb069}
.rimap .hop.warn{stroke:var(--warn); stroke-dasharray:7 5}
.rimap .hop.bad{stroke:var(--bad); stroke-dasharray:3 4}
.rimap .hoplab{font:500 11.5px "DM Sans",sans-serif;
  paint-order:stroke; stroke:var(--panel); stroke-width:4px; stroke-linejoin:round}
.rimap .hoplab.ok{fill:#7fb069}
.rimap .hoplab.warn{fill:var(--warn)}
.rimap .hoplab.bad{fill:var(--bad)}
.rimap .scalebar{stroke:var(--faint); stroke-width:2}
.rimap .scaletxt{fill:var(--faint); font:500 11px "DM Sans",sans-serif}
.hops{margin:12px 0 0}
.hoprow{display:flex; gap:10px; align-items:center; flex-wrap:wrap;
  padding:8px 12px; margin:0 0 7px; border-radius:var(--r);
  border:1px solid var(--line); background:var(--panel); font-size:13.5px}
.hoprow.ok{border-color:#2f4436}
.hoprow.warn{border-color:#5c4626; background:#221b12; color:#f0d2a6}
.hoprow.bad{border-color:#5e332a; background:#231613; color:#f2c3b4}
.hopn{display:inline-flex; align-items:center; justify-content:center;
  width:22px; height:22px; border-radius:50%; background:var(--panel2);
  color:var(--dim); font-size:12px; font-weight:600; flex:none}
.hopt{flex:1; min-width:0}
.hoplink{color:var(--accent); text-decoration:none; white-space:nowrap;
  border-bottom:1px dotted var(--accent)}

/* ---- freshness ---- */
.fresh{
  margin:0 0 18px; padding:9px 13px; border-radius:var(--r);
  border:1px solid var(--line); background:var(--panel);
  font-size:13.5px; color:var(--dim);
}
.fresh b{color:var(--ink); font-weight:600}
.fresh.good{border-color:#2f4436}
.fresh.aging{border-color:#5c4626; background:#221b12; color:#f0d2a6}
.fresh.stale{border-color:#5e332a; background:#231613; color:#f2c3b4}
.fresh a{color:inherit; text-decoration:underline}
.livenote{color:var(--faint)}
.livebtn{
  font:inherit; font-size:13px; cursor:pointer; color:var(--ink);
  background:var(--panel2); border:1px solid var(--accent);
  border-radius:999px; padding:4px 12px; margin-left:2px;
}
.livebtn:hover{background:var(--accent); color:#1b1410}
.livebtn[disabled]{opacity:.6; cursor:default}

/* ---- lanes ---- */
.lanes{display:grid; gap:10px; margin:0 0 22px;
  grid-template-columns:repeat(auto-fit,minmax(210px,1fr))}
.lane{
  text-align:left; cursor:pointer; font:inherit; color:var(--ink);
  background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:13px 15px; display:grid; gap:3px;
  transition:border-color .15s, background .15s;
}
.lane:hover{border-color:var(--accent)}
.lane[aria-pressed="true"]{background:var(--panel2); border-color:var(--accent); box-shadow:inset 0 0 0 1px var(--accent)}
.ln{font-weight:600}
.lc{font-family:"DM Mono",monospace; font-size:22px; color:var(--accent); line-height:1.1}
.lb{font-size:12.5px; color:var(--faint); line-height:1.4}

/* ---- controls ---- */
.controls{margin:0 0 18px}
.searchrow{display:flex; gap:8px}
#q{
  flex:1; font:inherit; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:var(--r); padding:12px 14px;
}
#q:focus{outline:2px solid var(--accent); outline-offset:1px; border-color:transparent}
#q::placeholder{color:var(--faint)}
.ghost{
  font:inherit; cursor:pointer; color:var(--dim); background:transparent;
  border:1px solid var(--line); border-radius:var(--r); padding:8px 14px;
}
.ghost:hover{border-color:var(--accent); color:var(--ink)}
.ghost.danger:hover{border-color:var(--bad); color:var(--bad)}
.filters{display:flex; flex-wrap:wrap; gap:8px; margin-top:10px}
.filters select{
  font:inherit; font-size:14px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:8px 10px; max-width:100%;
}
.chips{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px}
.chip{
  font-size:12.5px; border:1px solid var(--line); border-radius:999px;
  padding:4px 10px; color:var(--dim); background:var(--panel);
  display:inline-flex; gap:6px; align-items:center;
}
.chip button{background:none; border:0; color:var(--faint); cursor:pointer; font:inherit; padding:0 0 0 2px}
.chip button:hover{color:var(--bad)}

/* ---- result bar ---- */
.resultbar{display:flex; flex-wrap:wrap; gap:12px; align-items:center;
  justify-content:space-between; margin:0 0 14px; padding-top:6px;
  border-top:1px solid var(--line)}
.count{margin:0; color:var(--dim); font-size:14px}
.count b{color:var(--ink)}
.viewtabs{display:flex; gap:6px}
.vt{
  font:inherit; font-size:14px; cursor:pointer; color:var(--dim);
  background:transparent; border:1px solid var(--line);
  border-radius:999px; padding:6px 14px;
}
.vt[aria-selected="true"]{background:var(--panel2); color:var(--ink); border-color:var(--accent)}
.badge{
  display:inline-block; min-width:20px; text-align:center; margin-left:4px;
  background:var(--accent); color:#1b1410; border-radius:999px;
  font-size:12px; font-weight:600; padding:0 6px;
}

/* ---- results ---- */
.daygroup{margin:0 0 26px}
.dayhead{
  position:sticky; top:0; z-index:2; margin:0 0 10px; padding:8px 0;
  background:linear-gradient(var(--bg) 70%,transparent);
  font-size:13px; letter-spacing:.1em; text-transform:uppercase; color:var(--accent2);
}
.card{
  background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:13px 15px; margin:0 0 9px;
  display:grid; grid-template-columns:1fr auto; gap:4px 12px;
}
.card .top{grid-column:1; display:flex; flex-wrap:wrap; gap:7px; align-items:center; font-size:12.5px}
.card .code{font-family:"DM Mono",monospace; color:var(--accent); font-weight:500;
  text-decoration:none; border-bottom:1px dotted transparent}
a.code:hover{border-bottom-color:var(--accent)}
.tag{border:1px solid var(--line); border-radius:999px; padding:1px 8px; color:var(--dim); font-size:11.5px}
.tag.lvl{color:var(--accent2); border-color:#31463f}
.card h3{grid-column:1; margin:2px 0 3px; font-size:16px; line-height:1.35; font-weight:600}
.card .where{grid-column:1; font-size:13px; color:var(--faint)}
.card .where b{color:var(--dim); font-weight:500}
.star{
  grid-column:2; grid-row:1/4; align-self:start;
  font:inherit; font-size:20px; line-height:1; cursor:pointer;
  background:transparent; border:1px solid var(--line); border-radius:10px;
  color:var(--faint); width:40px; height:40px;
}
.star:hover{border-color:var(--accent); color:var(--accent)}
.star[aria-pressed="true"]{color:var(--accent); border-color:var(--accent); background:var(--panel2)}
.abstract{grid-column:1/-1; margin:7px 0 0; font-size:14px; color:var(--dim); display:none}
.card.open .abstract{display:block}
.more{
  grid-column:1; justify-self:start; margin-top:5px; padding:0;
  background:none; border:0; color:var(--faint); font:inherit; font-size:13px; cursor:pointer;
}
.more:hover{color:var(--accent)}
.card.gone{border-color:#5e332a; background:#1f1512}
.card.gone .code{color:var(--bad)}
.card.gone h3{color:#f2c3b4; font-size:15px}
.empty{padding:34px 4px; color:var(--faint); text-align:center}
.pager{display:flex; justify-content:center; padding:10px 0 4px}

/* ---- plan ---- */
.plan .daygroup{margin-bottom:20px}
.gap{
  display:flex; gap:9px; align-items:baseline;
  margin:0 0 9px; padding:8px 13px; border-radius:var(--r);
  border:1px solid var(--line); background:var(--panel);
  font-size:13.5px; color:var(--dim);
}
.gap.ok{border-color:#2f4436}
.gap.warn{border-color:#5c4626; background:#221b12; color:#f0d2a6}
.gap.bad{border-color:#5e332a; background:#231613; color:#f2c3b4}
.gap .ic{font-size:14px}
.gap b{color:inherit}
.planfoot{display:flex; gap:8px; flex-wrap:wrap; margin-top:12px}

/* ---- about ---- */
.about{
  margin:34px 0 0; border:1px solid var(--line); border-radius:var(--r);
  background:var(--panel); padding:0 15px;
}
.about summary{cursor:pointer; padding:13px 0; font-weight:600; font-size:14.5px}
.about p{font-size:14px; color:var(--dim); max-width:72ch}
.about .tune{display:flex; flex-wrap:wrap; gap:12px; align-items:center}
.about .tune label{font-size:13px; color:var(--faint)}
.about .tune input{
  width:64px; font:inherit; font-size:13px; color:var(--ink);
  background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:4px 6px;
}
.about .matrix summary{cursor:pointer; font-size:13.5px; color:var(--dim); padding:6px 0}
table.mx{border-collapse:collapse; font-size:12.5px; margin:8px 0 14px; width:100%}
table.mx th{text-align:left; font-weight:600; color:var(--faint); padding:5px 8px;
  border-bottom:1px solid var(--line); font-size:11.5px}
table.mx td{padding:5px 8px; border-bottom:1px solid var(--line); white-space:nowrap}
table.mx td.self{color:var(--faint)}
.mn{display:block; color:var(--ink); font-family:"DM Mono",monospace}
.md{display:block; color:var(--faint); font-size:11px}
.about .src{font-size:13px; color:var(--faint); border-top:1px solid var(--line); padding-top:12px}

.footer{margin-top:34px; padding-top:16px; border-top:1px solid var(--line);
  font-size:13px; color:var(--faint)}
.footer p{margin:.3em 0}

@media (max-width:560px){
  .page{padding:20px 13px 52px}
  .card{grid-template-columns:1fr auto}
  .dayhead{top:0}
  /* On a phone this page is used one-handed, standing up, to answer "what
     is near me now". Four stacked fact panels and four stacked lane cards
     put the search box a full screen and a half down, so both go to two
     columns and the lane blurbs -- which are orientation, not navigation --
     step aside. The desktop layout above is untouched. */
  h1{font-size:34px}
  .lede{font-size:15px; margin-bottom:16px}
  .facts{grid-template-columns:1fr 1fr; gap:8px}
  .facts li{padding:8px 10px}
  .facts strong{font-size:13.5px}
  .facts li:nth-child(4){grid-column:1/-1}
  .lanes{grid-template-columns:1fr 1fr; gap:8px}
  .lane{padding:10px 12px}
  .lb{display:none}
  .lc{font-size:19px}
  .filters select{flex:1 1 44%; min-width:0}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


# The shared back-to-top resolves its arrow colour as var(--ink, #1D2322).
# That literal is the right answer everywhere it was written for, because
# blog.css defines --ink as a near-black. THIS page defines --ink as #e8efec
# -- it is dark-themed, so its ink is light -- and the var is therefore
# found rather than falling back. The result is a light arrow on the tan
# button: measured 2.00:1, under even the 3:1 floor for a graphical
# control, where the intended dark ink gives 6.83:1.
#
# A third variant of the same trap. The module's docstring warns about an
# UNDEFINED token taking the declaration with it; this is a token that is
# defined and means the opposite. Overridden explicitly rather than by
# renaming this page's --ink, which the whole page is built on.
TOP_FIX = """
.back-top{color:#1D2322}
"""


# ---------------------------------------------------------------- behaviour

APP = r"""/* Generated by scripts/build_reinvent_page.py -- do not edit by hand. */
(function () {
  "use strict";
  var CFG = window.RI_CONFIG, DATA = null;
  var PAGE_SIZE = 60, shown = PAGE_SIZE;
  var PLAN_KEY = "ri2026.plan", TUNE_KEY = "ri2026.travel";
  var CATALOG_URL = "https://registration.awsevents.com/flow/awsevents/"
                  + "reinvent2026/eventcatalog/page/eventcatalog";

  var state = { lane: "all", q: "", day: "", type: "", level: "",
                venue: "", service: "" };
  var plan = load(PLAN_KEY, []);
  var tune = load(TUNE_KEY, null) || {
    overhead: CFG.travel.overhead, pace: CFG.travel.pace };
  if (tune.pace == null || tune.overhead == null) {      // an old saved shape
    tune = { overhead: CFG.travel.overhead, pace: CFG.travel.pace };
  }

  function load(key, dflt) {
    try { var v = JSON.parse(localStorage.getItem(key)); return v || dflt; }
    catch (e) { return dflt; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {}
  }
  function $(sel) { return document.querySelector(sel); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text != null) n.textContent = text;
    return n;
  }
  function km(m) {
    return m >= 1000 ? (m / 1000).toFixed(1) + " km" : m + " m";
  }

  function hhmm(min) {
    var h = Math.floor(min / 60), m = min % 60;
    return (h < 10 ? "0" : "") + h + ":" + (m < 10 ? "0" : "") + m;
  }
  function dayLabel(iso) {
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString(undefined,
      { weekday: "long", day: "numeric", month: "long" });
  }

  /* ---- the venue-hop rule -------------------------------------------
     The gap is a fact from AWS's own times. The distance is a fact from
     the venues' coordinates. Only the PACE is an assumption, and it is
     the one thing exposed as a control -- so the estimate is arithmetic
     on two facts and one number the reader owns. */
  function metresBetween(a, b) {
    var row = CFG.travel.matrix[a];
    return row && row[b] ? row[b].m : 0;
  }

  function needFor(fromVenue, toVenue) {
    var m = metresBetween(fromVenue, toVenue);
    if (!m) return tune.overhead;
    return tune.overhead
         + Math.round(m * CFG.travel.detour / tune.pace);
  }

  /* ---- data --------------------------------------------------------- */
  function firstSlot(s) { return s.when && s.when.length ? s.when[0] : null; }
  function svcNames(s) {
    return s.sv.map(function (i) { return DATA.facets.Services[i]; });
  }
  function typeName(s) {
    return s.ty == null ? "" : DATA.facets.Type[s.ty];
  }
  function levelName(s) {
    return s.lv == null ? "" : DATA.facets.Level[s.lv];
  }
  function venueName(slot) { return DATA.venues[slot.v]; }
  function roomName(slot) { return DATA.rooms[slot.r]; }

  function laneServices(id) {
    for (var i = 0; i < CFG.lanes.length; i++)
      if (CFG.lanes[i].id === id) return CFG.lanes[i].services;
    return null;
  }

  function matches(s) {
    if (state.lane !== "all") {
      var want = laneServices(state.lane), hit = false;
      for (var i = 0; i < s.sv.length && !hit; i++)
        if (want.indexOf(s.sv[i]) !== -1) hit = true;
      if (!hit) return false;
    }
    if (state.type && typeName(s) !== state.type) return false;
    if (state.level && levelName(s) !== state.level) return false;
    if (state.service && s.sv.indexOf(+state.service) === -1) return false;
    if (state.day || state.venue) {
      var ok = false;
      for (var j = 0; j < s.when.length && !ok; j++) {
        var w = s.when[j];
        if (state.day && w.d !== state.day) continue;
        if (state.venue && venueName(w) !== state.venue) continue;
        ok = true;
      }
      if (!ok) return false;
    }
    if (state.q) {
      var hay = (s.c + " " + s.t + " " + s.a + " " +
                 svcNames(s).join(" ")).toLowerCase();
      var terms = state.q.toLowerCase().split(/\s+/);
      for (var k = 0; k < terms.length; k++)
        if (terms[k] && hay.indexOf(terms[k]) === -1) return false;
    }
    return true;
  }

  function filtered() { return DATA.sessions.filter(matches); }

  /* ---- rendering ----------------------------------------------------- */
  function card(s, slot) {
    var c = el("article", "card");
    c.dataset.code = s.c;

    var top = el("div", "top");
    /* The code is the link. ?search=<code> was verified against a control:
       the /sessionDetails?sessionId= form silently falls back to the full
       catalog list, which looks like it worked. This one resolves, and the
       code is stable and human-readable where the internal id is neither. */
    var code = el("a", "code", s.c);
    code.href = CATALOG_URL + "?search=" + encodeURIComponent(s.c);
    code.target = "_blank";
    code.rel = "noopener";
    code.title = "Open " + s.c + " in the official AWS catalog";
    top.appendChild(code);
    if (typeName(s)) top.appendChild(el("span", "tag", typeName(s)));
    if (levelName(s)) top.appendChild(el("span", "tag lvl", levelName(s)));
    if (slot && slot.e != null) {
      top.appendChild(el("span", "tag",
        hhmm(slot.b) + "–" + hhmm(slot.e)));
    } else if (slot) {
      /* AWS publishes a start and no duration for a few sponsored
         sessions. Saying so beats inventing an end time. */
      top.appendChild(el("span", "tag",
        hhmm(slot.b) + " · length not published"));
    } else {
      top.appendChild(el("span", "tag", "not yet scheduled"));
    }
    c.appendChild(top);

    c.appendChild(el("h3", null, s.t));

    var where = el("div", "where");
    if (slot) {
      var b = el("b", null, venueName(slot));
      where.appendChild(b);
      var rest = roomName(slot).split("|").slice(1).join(" · ").trim();
      where.appendChild(document.createTextNode(
        (rest ? " · " + rest : "") +
        (slot.cap ? " · " + slot.cap + " seats" : "")));
    } else {
      where.textContent = "Venue to be announced";
    }
    c.appendChild(where);

    var star = el("button", "star", inPlan(s.c) ? "★" : "☆");
    star.setAttribute("aria-pressed", inPlan(s.c) ? "true" : "false");
    star.title = inPlan(s.c) ? "Remove from my plan" : "Add to my plan";
    star.addEventListener("click", function () { toggle(s.c); });
    c.appendChild(star);

    if (s.a) {
      var more = el("button", "more", "What is in it ›");
      var abs = el("p", "abstract", s.a);
      if (svcNames(s).length)
        abs.appendChild(el("span", null, "\n\nServices: " +
          svcNames(s).join(", ")));
      more.addEventListener("click", function () {
        c.classList.toggle("open");
        more.textContent = c.classList.contains("open")
          ? "Hide ‹" : "What is in it ›";
      });
      c.appendChild(more);
      c.appendChild(abs);
    }
    return c;
  }

  function renderBrowse() {
    var box = $("#browse");
    box.textContent = "";
    var list = filtered();

    $("#count").innerHTML = "<b>" + list.length.toLocaleString() +
      "</b> session" + (list.length === 1 ? "" : "s") +
      (state.lane === "all" ? "" : " in " + laneName(state.lane));

    if (!list.length) {
      box.appendChild(el("p", "empty",
        "Nothing matches. Try clearing a filter."));
      return;
    }

    /* One row per scheduled slot, so a repeated session appears on each
       day it actually runs -- which is the thing you are choosing between. */
    var rows = [];
    list.forEach(function (s) {
      if (!s.when.length) { rows.push({ s: s, w: null, d: "zzz" }); return; }
      s.when.forEach(function (w) {
        if (state.day && w.d !== state.day) return;
        if (state.venue && venueName(w) !== state.venue) return;
        rows.push({ s: s, w: w, d: w.d });
      });
    });
    rows.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      if (!a.w || !b.w) return a.w ? -1 : 1;
      return a.w.b - b.w.b;
    });

    var slice = rows.slice(0, shown), group = null, host = null;
    slice.forEach(function (r) {
      if (r.d !== group) {
        group = r.d;
        var g = el("section", "daygroup");
        g.appendChild(el("h2", "dayhead",
          r.w ? dayLabel(r.d) : "Not yet scheduled"));
        box.appendChild(g);
        host = g;
      }
      host.appendChild(card(r.s, r.w));
    });

    if (rows.length > shown) {
      var pager = el("div", "pager");
      var btn = el("button", "ghost",
        "Show " + Math.min(PAGE_SIZE, rows.length - shown) + " more of " +
        (rows.length - shown).toLocaleString());
      btn.addEventListener("click", function () {
        shown += PAGE_SIZE; renderBrowse();
      });
      pager.appendChild(btn);
      box.appendChild(pager);
    }
  }


  /* ---- the live check -------------------------------------------------
     The snapshot is what makes this page fast and usable on conference
     wifi; it is not what makes it true. On load the page asks the catalog
     itself -- one request -- how many sessions it currently has, and says
     so if that disagrees with the copy being shown.

     Measured 2026-09-22 before building this: the catalog reflects any
     Origin back in Access-Control-Allow-Origin, its preflight names
     rfApiProfileId and rfWidgetId in Access-Control-Allow-Headers, and a
     real browser on another origin fetched all 1,582 sessions. So this
     needs no proxy and no server.

     Every failure path is silent and falls back to the snapshot, because
     the snapshot is already correct and a red banner about a CORS error
     helps nobody standing in a corridor. The only thing a failure costs
     is the live confirmation, and the age line still tells the truth.

     One request, not thirty-two: counting is cheap, and pulling the whole
     catalog on every page view would be rude to AWS and slow for the
     reader. The full pull happens only if they ask for it. */
  var live = { state: "idle", total: null, checkedAt: null };

  function liveHeaders() {
    var api = DATA.api;
    if (!api || !api.headers) return null;
    var h = { "Content-Type":
                "application/x-www-form-urlencoded; charset=UTF-8" };
    for (var k in api.headers) if (api.headers.hasOwnProperty(k))
      h[k] = api.headers[k];
    return h;
  }

  function liveFetch(extra) {
    var h = liveHeaders();
    if (!h) return Promise.reject(new Error("no api details in the store"));
    var body = new URLSearchParams({
      type: "session", browserTimezone: "America/Chicago",
      catalogDisplay: "list" });
    for (var k in (extra || {})) body.set(k, extra[k]);
    return fetch(DATA.api.url,
                 { method: "POST", headers: h, body: body.toString() })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      });
  }

  function checkLive() {
    if (!DATA.api) return;
    live.state = "checking";
    liveFetch().then(function (d) {
      var total = parseInt(d.totalSearchItems, 10);
      if (isNaN(total)) throw new Error("no total in the response");
      live.total = total;
      live.checkedAt = Date.now();
      live.state = (total === DATA.sessions.length) ? "same" : "drift";
      renderFreshness();
    }).catch(function () {
      /* Silent on purpose. The snapshot stands, and the age line already
         tells the reader how old it is. */
      live.state = "unreachable";
      renderFreshness();
    });
  }

  function pullLive() {
    var btn = $("#live-pull");
    if (btn) { btn.disabled = true; btn.textContent = "Loading…"; }
    var all = [], PAGE = 50;

    function items(d) {
      if (d.items && d.items.length) return d.items;
      var sl = d.sectionList || [];
      return sl.length ? (sl[0].items || []) : [];
    }
    var expected = 0;

    /* Paced, because the catalog throttles a burst. Without the pause this
       stopped dead after two pages and handed back 100 sessions -- and the
       page then displayed those 100 as "live data", having thrown away a
       complete snapshot for a partial pull. That is the same failure the
       fetcher's shrink guard exists to prevent, so it gets the same
       answer: reconcile against the catalog's own total, and if the pull
       is short, keep the snapshot and say the pull failed. */
    function page(from) {
      return liveFetch(from ? { from: String(from) } : null)
        .then(function (d) {
          var got = items(d);
          all = all.concat(got);
          expected = parseInt(d.totalSearchItems, 10) || expected;
          if (got.length && all.length < expected)
            return new Promise(function (go) { setTimeout(go, 250); })
              .then(function () { return page(from + PAGE); });
          return all;
        });
    }
    page(0).then(function (raw) {
      if (!expected || raw.length < expected) {
        throw new Error("short pull: " + raw.length + " of " + expected);
      }
      DATA = reslim(raw, DATA);
      live.state = "live";
      live.checkedAt = Date.now();
      buildFilters();
      renderFreshness();
      render();
      if (!$("#plan").hidden) renderPlan();
      if (!$("#map").hidden) { fillMapDays(); renderMap(); }
    }).catch(function () {
      /* The snapshot is untouched and still on screen. */
      live.state = "pullfailed";
      renderFreshness();
    });
  }

  /* The browser's own copy of the slimming the fetcher does, so live data
     and stored data are exactly the same shape downstream. Facet tables are
     rebuilt from scratch rather than reusing the snapshot's, because an
     index into the wrong table renders as the wrong service name -- which
     would look like data rather than like a bug. */
  function reslim(raw, prev) {
    var FACETS = ["Type", "Level", "Role", "Services", "Topic",
                  "Area of Interest", "Industry"];
    var KEY = { "Type": "ty", "Level": "lv", "Role": "ro", "Services": "sv",
                "Topic": "tp", "Area of Interest": "ai", "Industry": "in" };
    var SINGLE = { "Type": 1, "Level": 1 };
    var tables = {}, venues = [], rooms = [];
    FACETS.forEach(function (f) { tables[f] = []; });

    function intern(list, v) {
      var i = list.indexOf(v);
      if (i === -1) { list.push(v); i = list.length - 1; }
      return i;
    }
    var out = raw.map(function (s) {
      var f = {};
      (s.attributevalues || []).forEach(function (av) {
        if (FACETS.indexOf(av.attribute) === -1 || !av.value) return;
        (f[av.attribute] = f[av.attribute] || []);
        if (f[av.attribute].indexOf(av.value) === -1)
          f[av.attribute].push(av.value);
      });
      var when = [];
      (s.times || []).forEach(function (t) {
        if (t.startTimeMin == null || t.endTimeMin == null) return;
        var b = t.startTimeMin | 0, e = t.endTimeMin | 0;
        var room = t.room || "";
        when.push({ d: t.date || "", b: b, e: e <= b ? null : e,
                    v: intern(venues, room.split("|")[0].trim()),
                    r: intern(rooms, room),
                    cap: /^\d+$/.test(String(t.capacity)) ? +t.capacity : null });
      });
      var rec = { c: s.code || "", t: (s.title || "").trim(),
                  a: (s.abstract || "").replace(/\s+/g, " ").trim(),
                  len: s.length ? (s.length | 0) : null, when: when };
      FACETS.forEach(function (name) {
        var idx = (f[name] || []).map(function (v) {
          return intern(tables[name], v); });
        rec[KEY[name]] = SINGLE[name] ? (idx.length ? idx[0] : null) : idx;
      });
      return rec;
    });

    var facets = {};
    FACETS.forEach(function (f) { facets[f] = tables[f]; });
    return { sessions: out, facets: facets, venues: venues, rooms: rooms,
             captured: prev.captured, captured_utc: prev.captured_utc,
             api: prev.api, live: true };
  }

  /* ---- how old is this, really ---------------------------------------
     Computed here rather than written in at build time, because the
     honest number is the one the reader is looking at now. A page built
     in September and opened in November has not got fresher, and a
     baked-in "captured 22 Sep" invites it to be read as if it had. */
  var AGING_DAYS = 10, STALE_DAYS = 21;

  function daysSince(iso) {
    if (!iso) return null;
    var then = new Date(iso);
    if (isNaN(then.getTime())) return null;
    return Math.floor((Date.now() - then.getTime()) / 86400000);
  }

  function renderFreshness() {
    var box = $("#fresh");
    var age = daysSince(DATA.captured_utc || DATA.captured);
    var when = DATA.captured || "an unrecorded date";
    box.textContent = "";

    /* Pulled live this session: the snapshot's age is no longer the
       interesting number, so it stops being the headline. */
    if (live.state === "live") {
      box.className = "fresh good";
      box.appendChild(el("b", null, "Showing live data"));
      box.appendChild(el("span", null,
        ", pulled from the AWS catalog a moment ago — "
        + DATA.sessions.length.toLocaleString() + " sessions. Seat "
        + "reservations still live in the "));
      addCatalogLink(box);
      return;
    }

    if (age === null) {
      box.className = "fresh stale";
      box.appendChild(el("span", null,
        "This copy of the catalog carries no capture date, so there is no "
        + "way to tell how old it is. Treat every time and room here as "
        + "unconfirmed and check the official catalog."));
      addCatalogLink(box);
      return;
    }

    var howLong = age === 0 ? "earlier today"
                : age === 1 ? "yesterday"
                : age + " days ago";
    var b = el("b", null, "Catalog checked " + howLong);
    box.appendChild(b);

    if (age >= STALE_DAYS) {
      box.className = "fresh stale";
      box.appendChild(el("span", null,
        " (" + when + "). That is old enough that sessions have probably "
        + "been added, moved or cancelled since. Confirm anything you are "
        + "relying on — every card links to its entry in the "));
      addCatalogLink(box);
    } else if (age >= AGING_DAYS) {
      box.className = "fresh aging";
      box.appendChild(el("span", null,
        " (" + when + "). Sessions move as the event gets closer, so check "
        + "anything you are relying on against the "));
      addCatalogLink(box);
    } else {
      box.className = "fresh good";
      box.appendChild(el("span", null,
        " (" + when + "), against " + DATA.sessions.length.toLocaleString()
        + " sessions. Seat reservations and last-minute changes still live "
        + "in the "));
      addCatalogLink(box);
    }
    appendLive(box);
  }

  /* What the one live request found, appended to whatever the age line
     already said. Drift is the case worth shouting about: it means the
     catalog has moved under this copy, and the reader can pull it now. */
  function appendLive(box) {
    if (live.state === "drift") {
      box.className = "fresh aging";
      box.appendChild(el("span", null,
        " AWS is currently listing " + live.total.toLocaleString()
        + " sessions against this copy's "
        + DATA.sessions.length.toLocaleString() + ". "));
      var btn = el("button", "livebtn", "Load the live catalog");
      btn.id = "live-pull";
      btn.addEventListener("click", pullLive);
      box.appendChild(btn);
    } else if (live.state === "same") {
      box.appendChild(el("span", "livenote",
        " Confirmed against AWS just now — same session count."));
    } else if (live.state === "pullfailed") {
      box.className = "fresh aging";
      box.appendChild(el("span", null,
        " The live catalog did not come back complete, so this is still "
        + "the stored copy rather than a half-loaded one. "));
      var again = el("button", "livebtn", "Try again");
      again.id = "live-pull";
      again.addEventListener("click", pullLive);
      box.appendChild(again);
    } else if (live.state === "unreachable") {
      box.appendChild(el("span", "livenote",
        " (Could not reach AWS to confirm just now; showing the stored "
        + "copy.)"));
    }
  }

  function addCatalogLink(box) {
    var a = el("a", null, "official catalog");
    a.href = CATALOG_URL;
    a.target = "_blank";
    a.rel = "noopener";
    box.appendChild(a);
    box.appendChild(document.createTextNode("."));
  }

  /* The whole cost table, visible. A number a reader cannot inspect is a
     number they have to take on faith, and this one changes their day. */
  function renderMatrix() {
    var host = $("#matrix");
    if (!host) return;
    var names = Object.keys(CFG.travel.matrix).sort();
    var t = el("table", "mx");
    var head = el("tr");
    head.appendChild(el("th", null, ""));
    names.forEach(function (n) { head.appendChild(el("th", null, n)); });
    t.appendChild(head);
    names.forEach(function (a) {
      var tr = el("tr");
      tr.appendChild(el("th", null, a));
      names.forEach(function (b) {
        var td = el("td");
        if (a === b) {
          td.textContent = tune.overhead + " min";
          td.className = "self";
        } else {
          var m = CFG.travel.matrix[a][b].m;
          td.appendChild(el("span", "mn", needFor(a, b) + " min"));
          td.appendChild(el("span", "md", km(m)));
        }
        tr.appendChild(td);
      });
      t.appendChild(tr);
    });
    host.textContent = "";
    host.appendChild(t);
  }


  /* ---- the map -------------------------------------------------------
     Drawn from the venues' real coordinates, to scale, with a bar showing
     what the scale is. It is rotated a quarter turn so the Strip runs
     left to right instead of producing a column 3.4 times taller than it
     is wide -- north is marked, because a map that silently reorients the
     world is worse than no map.

     No Google Maps embed, deliberately. A traffic layer here would be
     showing CAR congestion on Las Vegas Boulevard, which is not how
     anyone moves between these venues: it is walking, the conference
     shuttle and the monorail. It would look authoritative and mean
     nothing. Each hop instead links out to Google Maps for a real routed
     walking time, which costs no API key and opens the app already on
     the reader's phone. */
  var MAP_W = 1000;

  function mapH() {
    return Math.round(MAP_W * CFG.map.span_x_m / CFG.map.span_y_m);
  }

  /* geo (x=east/west, y=north/south) -> screen, quarter-turned */
  function project(v) {
    var p = CFG.map.pos[v];
    return { x: p[1] * MAP_W, y: p[0] * mapH() };
  }

  function svgEl(tag, attrs) {
    var n = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (var k in attrs) if (attrs.hasOwnProperty(k))
      n.setAttribute(k, attrs[k]);
    return n;
  }

  function mapsLink(a, b) {
    var pa = CFG.travel.points[a], pb = CFG.travel.points[b];
    return "https://www.google.com/maps/dir/?api=1"
         + "&origin=" + pa[0] + "," + pa[1]
         + "&destination=" + pb[0] + "," + pb[1]
         + "&travelmode=walking";
  }

  /* Padding is derived, not guessed. The biggest circle can reach r=39 and
     its label sits 18px below that, so a venue sitting on the edge of the
     plot -- Wynn/Encore does, it is the northern end -- needs room for both
     or it gets clipped off the corner. It was. */
  var R_MAX = 39, LABEL_DROP = 22, SCALE_BAND = 34;

  function renderMap() {
    var host = $("#mapsvg");
    if (!host) return;
    var H = mapH();
    var padX = 84, padT = 34 + R_MAX, padB = R_MAX + LABEL_DROP + SCALE_BAND;
    var names = Object.keys(CFG.map.pos);

    // How many of the CURRENTLY FILTERED sessions sit at each venue.
    // This is the heat: narrow to a lane and the map shows where that
    // lane actually lives.
    var heat = {}, total = 0;
    names.forEach(function (n) { heat[n] = 0; });
    filtered().forEach(function (s) {
      var seen = {};
      s.when.forEach(function (w) {
        var v = venueName(w);
        if (state.day && w.d !== state.day) return;
        if (seen[v]) return;
        seen[v] = 1; heat[v] += 1; total += 1;
      });
    });
    var peak = Math.max.apply(null, names.map(function (n) { return heat[n]; }));
    var nEl = $("#map-n");
    if (nEl) nEl.textContent = total.toLocaleString();

    var svg = svgEl("svg", {
      viewBox: "0 0 " + (MAP_W + padX * 2) + " " + (H + padT + padB),
      class: "rimap", role: "img",
      "aria-label": "The five re:Invent venues positioned to scale, "
        + "sized by how many matching sessions each holds."
    });
    var g = svgEl("g", { transform: "translate(" + padX + "," + padT + ")" });
    svg.appendChild(g);

    // the route for the chosen day, drawn under the venues
    var day = $("#map-day") ? $("#map-day").value : "";
    var hops = day ? routeFor(day) : [];
    hops.forEach(function (h, i) {
      var a = project(h.from), b = project(h.to);
      var line = svgEl("line", {
        x1: a.x, y1: a.y, x2: b.x, y2: b.y,
        class: "hop " + h.verdict
      });
      g.appendChild(line);
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      var lab = svgEl("text", { x: mx, y: my - 8, class: "hoplab " + h.verdict,
                                "text-anchor": "middle" });
      lab.textContent = (i + 1) + ". " + h.gapText;
      g.appendChild(lab);
    });

    names.forEach(function (n) {
      var p = project(n);
      var frac = peak ? heat[n] / peak : 0;
      var r = 9 + Math.round(Math.sqrt(frac) * 30);
      var grp = svgEl("g", { class: "venue" });
      grp.appendChild(svgEl("circle", { cx: p.x, cy: p.y, r: r,
                                        class: "vdot" }));
      var t1 = svgEl("text", { x: p.x, y: p.y + 4, class: "vnum",
                               "text-anchor": "middle" });
      t1.textContent = heat[n];
      grp.appendChild(t1);
      var t2 = svgEl("text", { x: p.x, y: p.y + r + 18, class: "vname",
                               "text-anchor": "middle" });
      t2.textContent = n;
      grp.appendChild(t2);
      g.appendChild(grp);
    });

    // scale bar: 500 m, so the distances are readable rather than implied
    var perM = MAP_W / CFG.map.span_y_m;
    var barLen = Math.round(500 * perM);
    var by = H + R_MAX + LABEL_DROP + 14;
    g.appendChild(svgEl("line", { x1: 0, y1: by, x2: barLen, y2: by,
                                  class: "scalebar" }));
    var st = svgEl("text", { x: 0, y: by - 6, class: "scaletxt" });
    st.textContent = "500 m";
    g.appendChild(st);

    var nt = svgEl("text", { x: 0, y: -(R_MAX + 12), class: "scaletxt" });
    nt.textContent = "← north (Wynn/Encore end)    south (MGM Grand) →";
    g.appendChild(nt);

    host.textContent = "";
    host.appendChild(svg);
    renderHops(hops);
  }

  /* The day's hops, reusing exactly the plan's own feasibility rule so the
     map and the plan can never disagree with each other. */
  function routeFor(day) {
    var rows = planRows().filter(function (r) {
      return r.d === day && r.w;
    });
    var out = [];
    for (var i = 1; i < rows.length; i++) {
      var a = rows[i - 1], b = rows[i];
      var from = venueName(a.w), to = venueName(b.w);
      if (a.w.e == null) {
        out.push({ from: from, to: to, verdict: "warn", a: a, b: b,
                   gapText: "end time not published" });
        continue;
      }
      var gap = b.w.b - a.w.e, need = needFor(from, to);
      var verdict = gap < 0 ? "bad" : gap < need ? "warn" : "ok";
      out.push({ from: from, to: to, verdict: verdict, a: a, b: b,
                 gap: gap, need: need,
                 gapText: gap < 0 ? "overlap" : gap + " min / needs " + need });
    }
    return out;
  }

  function renderHops(hops) {
    var host = $("#maphops");
    if (!host) return;
    host.textContent = "";
    if (!hops.length) return;
    hops.forEach(function (h, i) {
      var row = el("div", "hoprow " + h.verdict);
      row.appendChild(el("span", "hopn", String(i + 1)));
      var txt = el("span", "hopt");
      txt.textContent = h.from + " → " + h.to
        + (h.from === h.to ? " (same property)"
           : "  ·  " + km(metresBetween(h.from, h.to)) + "  ·  "
             + h.gapText);
      row.appendChild(txt);
      if (h.from !== h.to) {
        var a = el("a", "hoplink", "walking route ↗");
        a.href = mapsLink(h.from, h.to);
        a.target = "_blank"; a.rel = "noopener";
        a.title = "Open this hop in Google Maps for a live routed time";
        row.appendChild(a);
      }
      host.appendChild(row);
    });
  }

  function fillMapDays() {
    var sel = $("#map-day");
    if (!sel) return;
    var have = {};
    planRows().forEach(function (r) { if (r.w) have[r.d] = 1; });
    var keep = sel.value;
    sel.textContent = "";
    sel.appendChild(new Option("— no day selected —", ""));
    CFG.days.forEach(function (d) {
      if (have[d]) sel.appendChild(new Option(dayLabel(d), d));
    });
    sel.value = have[keep] ? keep : "";
    sel.onchange = renderMap;
  }

  function laneName(id) {
    for (var i = 0; i < CFG.lanes.length; i++)
      if (CFG.lanes[i].id === id) return CFG.lanes[i].name;
    return id;
  }

  /* ---- the plan ------------------------------------------------------ */
  function inPlan(code) { return plan.indexOf(code) !== -1; }
  function toggle(code) {
    var i = plan.indexOf(code);
    if (i === -1) plan.push(code); else plan.splice(i, 1);
    save(PLAN_KEY, plan);
    syncStars(); renderPlan();
    if (!$("#map").hidden) { fillMapDays(); renderMap(); }
  }
  function syncStars() {
    $("#planN").textContent = plan.length;
    Array.prototype.forEach.call(
      document.querySelectorAll(".card"), function (c) {
        var on = inPlan(c.dataset.code), b = c.querySelector(".star");
        if (!b) return;
        b.textContent = on ? "★" : "☆";
        b.setAttribute("aria-pressed", on ? "true" : "false");
        b.title = on ? "Remove from my plan" : "Add to my plan";
      });
  }

  function planRows() {
    var by = {}, rows = [];
    DATA.sessions.forEach(function (s) { by[s.c] = s; });
    plan.forEach(function (code) {
      var s = by[code];
      if (!s) {
        /* The session is starred and is no longer in the catalog. Dropping
           it silently was the worst thing this page could do: the plan
           would simply be one session shorter than the person built, with
           nothing to say a talk they were counting on has gone. */
        rows.push({ gone: code, d: "zzzz" });
        return;
      }
      if (!s.when.length) { rows.push({ s: s, w: null, d: "zzz" }); return; }
      s.when.forEach(function (w) { rows.push({ s: s, w: w, d: w.d }); });
    });
    rows.sort(function (a, b) {
      if (a.d !== b.d) return a.d < b.d ? -1 : 1;
      if (!a.w || !b.w) return a.w ? -1 : 1;
      return a.w.b - b.w.b;
    });
    return rows;
  }

  function renderPlan() {
    var box = $("#planbody");
    box.textContent = "";
    var rows = planRows();
    if (!rows.length) {
      box.appendChild(el("p", "empty",
        "Nothing starred yet. Star a session in Browse and it lands here, "
        + "with the travel between them checked."));
      return;
    }

    var group = null, host = null, prev = null;
    rows.forEach(function (r) {
      if (r.d !== group) {
        group = r.d; prev = null;
        host = el("section", "daygroup");
        host.appendChild(el("h2", "dayhead",
          r.gone ? "No longer in the catalog"
                 : r.w ? dayLabel(r.d) : "Not yet scheduled"));
        box.appendChild(host);
      }
      if (r.gone) { host.appendChild(goneCard(r.gone)); prev = null; return; }
      if (prev && prev.w && r.w) host.appendChild(gapRow(prev, r));
      host.appendChild(card(r.s, r.w));
      prev = r;
    });
  }

  function goneCard(code) {
    var c = el("article", "card gone");
    c.dataset.code = code;
    var top = el("div", "top");
    top.appendChild(el("span", "code", code));
    top.appendChild(el("span", "tag", "withdrawn or renamed"));
    c.appendChild(top);
    c.appendChild(el("h3", null, "This session is no longer in the catalog"));
    var where = el("div", "where");
    where.appendChild(document.createTextNode(
      "You starred it, and the capture of " + (DATA.captured || "the catalog")
      + " does not contain it. AWS may have withdrawn, merged or renumbered "
      + "it. Check "));
    var a = el("a", null, code + " in the official catalog");
    a.href = CATALOG_URL + "?search=" + encodeURIComponent(code);
    a.target = "_blank"; a.rel = "noopener";
    where.appendChild(a);
    where.appendChild(document.createTextNode("."));
    c.appendChild(where);
    var drop = el("button", "star", "×");
    drop.title = "Remove it from my plan";
    drop.addEventListener("click", function () { toggle(code); });
    c.appendChild(drop);
    return c;
  }

  function gapRow(a, b) {
    var from = venueName(a.w), to = venueName(b.w);
    var need = needFor(from, to);
    var row = el("div", "gap"), msg;

    if (a.w.e == null) {
      /* No published end, so there is no gap to measure. The page says
         that rather than measuring from the start time and calling the
         result a gap -- which would under-warn on exactly the hop this
         feature exists to catch. */
      row.className = "gap warn";
      row.appendChild(el("span", "ic", "○"));
      row.appendChild(el("span", null,
        "AWS does not publish how long " + a.s.c + " runs, so the time "
        + "before " + b.s.c + " cannot be checked."
        + (from === to ? "" : " They are at different properties — "
           + from + " to " + to + " — so allow about " + need + " min.")));
      return row;
    }

    var gap = b.w.b - a.w.e;
    if (gap < 0) {
      row.className = "gap bad";
      row.appendChild(el("span", "ic", "●"));
      msg = "These overlap by " + (-gap) + " min. " +
        (from === to ? "Same property, but you cannot be in both."
                     : from + " and " + to + " at once is not possible.");
    } else if (gap < need) {
      row.className = "gap warn";
      row.appendChild(el("span", "ic", "●"));
      msg = gap + " min between them" +
        (from === to ? " inside " + from
                     : ", and they are " + km(metresBetween(from, to))
                       + " apart — " + from + " to " + to) +
        ". Allow about " + need + ". You would be late.";
    } else {
      row.className = "gap ok";
      row.appendChild(el("span", "ic", "○"));
      msg = gap + " min" +
        (from === to ? " to change rooms inside " + from
                     : " to cover the " + km(metresBetween(from, to))
                       + " from " + from + " to " + to) + ".";
    }
    row.appendChild(el("span", null, msg));
    return row;
  }

  /* ---- filters ------------------------------------------------------- */
  function buildFilters() {
    var host = $("#filters");
    host.textContent = "";

    function pick(key, label, options, valueOf) {
      var sel = el("select");
      sel.setAttribute("aria-label", label);
      sel.appendChild(new Option(label, ""));
      options.forEach(function (o) {
        sel.appendChild(new Option(o.label, o.value));
      });
      sel.value = state[key];
      sel.addEventListener("change", function () {
        state[key] = sel.value; shown = PAGE_SIZE; render();
      });
      host.appendChild(sel);
    }

    pick("day", "Any day", CFG.days.map(function (d) {
      return { label: dayLabel(d), value: d };
    }));
    pick("type", "Any format", DATA.facets.Type.map(function (t) {
      return { label: t, value: t };
    }));
    pick("level", "Any level", DATA.facets.Level.slice().sort()
      .map(function (l) { return { label: l, value: l }; }));
    pick("venue", "Any venue", DATA.venues.slice().sort()
      .map(function (v) { return { label: v, value: v }; }));

    /* Services is the long one -- 169 entries -- so it is sorted by how
       many sessions carry it, not alphabetically. The head of that list
       is what people are actually looking for. */
    var count = {};
    DATA.sessions.forEach(function (s) {
      s.sv.forEach(function (i) { count[i] = (count[i] || 0) + 1; });
    });
    var svc = Object.keys(count).map(Number).sort(function (a, b) {
      return count[b] - count[a];
    }).map(function (i) {
      return { label: DATA.facets.Services[i] + "  (" + count[i] + ")",
               value: String(i) };
    });
    pick("service", "Any service", svc);
  }

  function renderChips() {
    var host = $("#chips");
    host.textContent = "";
    var live = [];
    if (state.lane !== "all")
      live.push(["lane", laneName(state.lane)]);
    [["day", state.day && dayLabel(state.day)],
     ["type", state.type], ["level", state.level], ["venue", state.venue],
     ["service", state.service &&
       DATA.facets.Services[+state.service]]].forEach(function (p) {
      if (p[1]) live.push(p);
    });
    live.forEach(function (p) {
      var chip = el("span", "chip", p[1]);
      var x = el("button", null, "×");
      x.title = "Remove this filter";
      x.addEventListener("click", function () {
        state[p[0]] = p[0] === "lane" ? "all" : "";
        shown = PAGE_SIZE; buildFilters(); render();
      });
      chip.appendChild(x);
      host.appendChild(chip);
    });
  }

  function syncLaneTabs() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".lane"), function (b) {
        b.setAttribute("aria-pressed",
          b.dataset.lane === state.lane ? "true" : "false");
      });
  }

  function render() {
    syncLaneTabs(); renderChips(); renderBrowse(); syncStars();
    $("#clear").hidden = !state.q;
    if (!$("#map").hidden) renderMap();
  }

  /* ---- wiring -------------------------------------------------------- */
  function wire() {
    Array.prototype.forEach.call(
      document.querySelectorAll(".lane"), function (b) {
        b.addEventListener("click", function () {
          state.lane = b.dataset.lane; shown = PAGE_SIZE; render();
          window.scrollTo({ top: $(".controls").offsetTop - 12,
                            behavior: "smooth" });
        });
      });

    var timer = null;
    $("#q").addEventListener("input", function (e) {
      clearTimeout(timer);
      var v = e.target.value;
      timer = setTimeout(function () {
        state.q = v.trim(); shown = PAGE_SIZE; render();
      }, 140);
    });
    $("#clear").addEventListener("click", function () {
      $("#q").value = ""; state.q = ""; shown = PAGE_SIZE; render();
    });

    $("#tab-browse").addEventListener("click", function () { view("browse"); });
    $("#tab-plan").addEventListener("click", function () { view("plan"); });
    $("#tab-map").addEventListener("click", function () { view("map"); });

    $("#share").addEventListener("click", function () {
      var url = location.origin + location.pathname +
        "#plan=" + encodeURIComponent(plan.join(","));
      var done = function () { $("#share").textContent = "Link copied";
        setTimeout(function () {
          $("#share").textContent = "Copy a link to this plan"; }, 1800); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done);
      else { prompt("Copy this link", url); }
    });

    $("#wipe").addEventListener("click", function () {
      if (!plan.length) return;
      if (!confirm("Clear all " + plan.length + " starred sessions?")) return;
      plan = []; save(PLAN_KEY, plan); syncStars(); renderPlan();
    });

    var over = $("#t-overhead"), pace = $("#t-pace");
    over.value = tune.overhead;
    pace.value = String(tune.pace);
    over.addEventListener("change", function () {
      var v = parseInt(over.value, 10);
      if (isNaN(v) || v < 0) { over.value = tune.overhead; return; }
      tune.overhead = v; save(TUNE_KEY, tune); renderPlan(); renderMatrix();
    });
    pace.addEventListener("change", function () {
      tune.pace = parseInt(pace.value, 10) || CFG.travel.pace;
      save(TUNE_KEY, tune); renderPlan(); renderMatrix();
    });
  }

  function view(which) {
    $("#browse").hidden = which !== "browse";
    $("#plan").hidden = which !== "plan";
    $("#map").hidden = which !== "map";
    /* Search, filters and lanes drive Browse AND the map's heat, so they
       stay up for both. In the plan they are dead controls that push the
       plan below the fold -- on a phone, past it entirely. */
    var showControls = which !== "plan";
    $(".controls").hidden = !showControls;
    document.querySelector(".lanes").hidden = !showControls;
    [["#tab-browse", "browse"], ["#tab-plan", "plan"], ["#tab-map", "map"]]
      .forEach(function (p) {
        $(p[0]).setAttribute("aria-selected",
                             which === p[1] ? "true" : "false");
      });
    if (which === "plan") renderPlan();
    if (which === "map") { fillMapDays(); renderMap(); }
  }

  function adoptSharedPlan() {
    var m = /[#&]plan=([^&]*)/.exec(location.hash);
    if (!m) return false;
    var codes = decodeURIComponent(m[1]).split(",").filter(Boolean);
    if (!codes.length) return false;
    plan = codes; save(PLAN_KEY, plan);
    history.replaceState(null, "", location.pathname);
    return true;
  }

  /* ---- boot ---------------------------------------------------------- */
  fetch("/intelligence/reinvent2026.json")
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (d) {
      DATA = d;
      var shared = adoptSharedPlan();
      /* A shared link opened while the page is already up changes only the
         fragment, which is a same-document navigation -- no reload, so the
         boot path below never runs again. Without this, a teammate clicking
         someone's plan link from this very page sees nothing happen. */
      window.addEventListener("hashchange", function () {
        if (adoptSharedPlan()) { syncStars(); renderPlan(); view("plan"); }
      });
      var all = document.querySelector('[data-count="all"]');
      if (all) all.textContent = DATA.sessions.length.toLocaleString();
      buildFilters(); wire(); renderFreshness(); renderMatrix();
      checkLive();
      render();
      if (shared) view("plan");
    })
    .catch(function (err) {
      $("#count").textContent =
        "The session data did not load (" + err.message +
        "). The official catalog still works.";
    });
})();
"""


if __name__ == "__main__":
    sys.exit(build())
