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
import datetime
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from back_to_top import TOP_HTML, TOP_CSS, TOP_JS  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE = os.path.join(ROOT, "intelligence", "reinvent2026.json")
OUTDIR = os.path.join(ROOT, "reinvent-2026")

# What AWS says the finished catalog will hold, quoted from its own
# catalog page on 2026-09-22: "the full catalog will include more than
# 2,200 sessions". Used only to tell a reader how much is still to come.
AWS_PLANNED = 2200

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
# The building each venue's sessions are actually IN. A resort is not a
# point: MGM Grand's conference centre is half a kilometre from the middle
# of the hotel, and the Venetian Expo is a different building from the
# Venetian tower.
CONFERENCE_BUILDING = {
    "Venetian":       "Venetian Expo",
    "Wynn/Encore":    "Encore",
    "Caesars Forum":  "Caesars Forum",
    "Caesars Palace": "Caesars Palace",
    "MGM Grand":      "MGM Grand Conference Center",
}

# Fallback only, and deliberately kept: if the OSM geometry is missing the
# page still draws with something sane rather than dividing by nothing.
# These are the hand-written values this started with, and measuring them
# against the real footprints is how their error was found -- up to 508 m
# at MGM Grand, which is a different end of the property from where the
# sessions are. Anything derived from them was wrong by that much.
VENUE_POINTS_FALLBACK = {
    "Venetian":       (36.1212, -115.1697),
    "Wynn/Encore":    (36.1270, -115.1656),
    "Caesars Forum":  (36.1163, -115.1665),
    "Caesars Palace": (36.1162, -115.1745),
    "MGM Grand":      (36.1026, -115.1700),
}
VENUE_POINTS = dict(VENUE_POINTS_FALLBACK)


def polygon_centroid(pts):
    """Area-weighted centroid. The mean of the vertices is not the centre
    of a building -- it drifts towards whichever side OSM happened to map
    in more detail."""
    a = cx = cy = 0.0
    for i in range(len(pts)):
        y1, x1 = pts[i]
        y2, x2 = pts[(i + 1) % len(pts)]
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    if abs(a) < 1e-12:
        return (sum(p[0] for p in pts) / len(pts),
                sum(p[1] for p in pts) / len(pts))
    a *= 0.5
    return (cy / (6 * a), cx / (6 * a))


def locate_venues():
    """Replace the remembered coordinates with measured ones.

    Every distance, every travel estimate and every warning on this page is
    computed from these five points, so they are the last place a rounded
    guess belongs. The OSM footprints are in the repo; the centroid of the
    building the sessions are in is a fact, and it is free to compute.
    """
    path = os.path.join(ROOT, "intelligence", "vegas-map.json")
    if not os.path.exists(path):
        print("    no map geometry; venue points fall back to the "
              "hand-written values")
        return
    try:
        geo = json.load(io.open(path, encoding="utf-8"))
    except (ValueError, OSError):
        print("    map geometry unreadable; using the fallback points")
        return

    by_name = {}
    for b in geo.get("buildings", []):
        if b.get("n"):
            by_name.setdefault(b["n"], b)

    for venue, want in CONFERENCE_BUILDING.items():
        b = by_name.get(want)
        if not b:
            print("    %s: no footprint named %r, keeping the fallback point"
                  % (venue, want))
            continue
        here = polygon_centroid(b["p"])
        moved = metres(VENUE_POINTS[venue], here)
        VENUE_POINTS[venue] = here
        if moved > 100:
            print("    %-16s moved %3d m to the centre of %s"
                  % (venue, round(moved), want))

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


# ------------------------------------------------------- announcements

NEWS = os.path.join(ROOT, "intelligence", "news.json")
NEWS_DAYS = 45          # how far back to carry announcements
NEWS_MAX = 120          # and a ceiling, so the page stays small


def _norm_service(name):
    """Fold a service name to something the two sources can agree on.

    The catalog writes "Amazon Elastic Compute Cloud (Amazon EC2)"; the
    announcement feed writes "Amazon EC2". Dropping the parenthetical and
    the vendor prefix makes 61% of AWS announcements line up with a service
    the catalog also lists -- measured across 219 of them.
    """
    x = name.lower()
    x = re.sub(r"\(.*?\)", "", x)
    x = re.sub(r"^(amazon|aws)\s+", "", x).strip()
    return re.sub(r"[^a-z0-9 ]", "", x)


def announcements(store):
    """Recent AWS announcements, each tied to catalog service indexes.

    Why this is here: re:Invent week is when AWS ships, and the thing a
    team actually wants on the Tuesday is "they announced this at the
    keynote -- who is covering it?". The announcement store already exists
    and is refreshed daily by ingest-news.yml, so this is a join rather
    than a new pipeline.

    Absent or unreadable news is not an error. The page simply does not
    show the tab -- a missing join is worth nothing, and a half-built one
    that invents matches is worth less than nothing.
    """
    if not os.path.exists(NEWS):
        return []
    try:
        items = json.load(io.open(NEWS, encoding="utf-8")).get("items") or []
    except (ValueError, OSError):
        return []

    lookup = {}
    for i, name in enumerate(store["facets"]["Services"]):
        lookup.setdefault(_norm_service(name), i)

    cutoff = (datetime.date.today()
              - datetime.timedelta(days=NEWS_DAYS)).isoformat()
    out = []
    for r in items:
        if (r.get("c") or "").lower() != "aws":
            continue
        if (r.get("d") or "") < cutoff:
            continue
        idx = []
        for name in (r.get("s") or []):
            j = lookup.get(_norm_service(name))
            if j is not None and j not in idx:
                idx.append(j)
        if not idx:
            continue                      # nothing to point at; drop it
        out.append({
            "d": r.get("d") or "",
            "t": (r.get("t") or "").strip()[:240],
            "u": r.get("u") or "",
            "sv": idx,
        })
    out.sort(key=lambda r: r["d"], reverse=True)
    return out[:NEWS_MAX]


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
    locate_venues()
    lanes = lane_indexes(store)
    counts = lane_counts(store, lanes)
    sessions = store["sessions"]

    news = announcements(store)
    days = sorted({w["d"] for s in sessions for w in s["when"]})
    scheduled = sum(1 for s in sessions if s["when"])

    os.makedirs(OUTDIR, exist_ok=True)

    # The page reads the store in place, at its absolute path, rather
    # than getting a copy beside it. A copy meant the same 1.3 MB shipped
    # twice, and -- worse -- it could go stale against the store it was
    # copied from, which is the kind of drift nothing here would notice.

    # Lanes carry their services BY NAME as well as by index. The index is
    # what the page filters on and what the Python checks read; the names
    # are what survive a live pull, which rebuilds the Services table from
    # the fresh payload and does not number it the way this build did. With
    # only indices, a lane would go on matching 37 and 103 against whatever
    # had moved into those slots -- showing a reader the wrong sessions
    # under the right heading, and raising nothing.
    svc_names = store["facets"]["Services"]
    config = {
        "lanes": [{"id": l["id"], "name": l["name"], "blurb": l["blurb"],
                   "services": lanes[l["id"]],
                   "sv": [svc_names[i] for i in lanes[l["id"]]],
                   "count": counts[l["id"]]}
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
        "news": news,
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
    # Written in from the measurement rather than typed, because the
    # sentence it replaces cited two distances that silently stopped being
    # true the moment the venue points were corrected.
    worst_fix = 0
    for venue, want in CONFERENCE_BUILDING.items():
        moved = metres(VENUE_POINTS_FALLBACK[venue], VENUE_POINTS[venue])
        worst_fix = max(worst_fix, int(round(moved)))
    html = html.replace("__WORSTFIX__", str(worst_fix))
    # AWS's stated final size, from its own catalog page. Kept as a named
    # constant so the percentage below can never drift from the count.
    html = html.replace("__PCT__",
                        str(int(round(100.0 * len(sessions) / AWS_PLANNED))))
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
    # The one number the app needs that is not in the store: what AWS
    # says the finished programme will hold. Written in here from the
    # same constant the prose uses, so the page can recompute its own
    # percentage after a live pull without a second copy of the figure.
    write(os.path.join(OUTDIR, "app.js"),
          APP.replace("__PLANNED__", str(AWS_PLANNED)))

    print("  reinvent-2026/  %d sessions, %d scheduled, %d day(s)"
          % (len(sessions), scheduled, len(days)))
    for lane in LANES:
        print("    %-18s %4d session(s) across %d service(s)"
              % (lane["name"], counts[lane["id"]], len(lanes[lane["id"]])))
    print("    %-18s %4d AWS announcement(s) in the last %d days tie to a "
          "service the catalog lists" % ("announcements", len(news),
                                         NEWS_DAYS))
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
   <li><span>Sessions</span><strong><b id="n-total">__TOTAL__</b> <em>(<b id="n-scheduled">__SCHEDULED__</b> scheduled)</em></strong></li>
   <li><span>Venues</span><strong>__VENUES__</strong></li>
  </ul>

  <!-- Painted by the page from the event dates in the config, never
       written in at build time: a countdown baked at build time is wrong
       by one the next morning, which is the one number a reader checks
       against their own calendar. Hidden until it has something true to
       say. -->
  <section id="countdown" class="cd" aria-live="polite" hidden>
   <p class="cd-n"><b id="cd-num">&nbsp;</b><span id="cd-unit"><span
     class="cd-live" aria-hidden="true"></span></span></p>
   <div class="cd-side">
    <div id="cd-marks" class="cd-marks" aria-hidden="true"></div>
    <p id="cd-note" class="cd-note"></p>
   </div>
  </section>
 </header>

 <!-- Written by the page itself, in the reader's browser, from the capture
      timestamp in the store. Deliberately not baked in at build time: a
      build-time string says how old the data was when the page was made,
      which is the one number that is always reassuring and never true. -->
 <p id="fresh" class="fresh" role="status">Checking how current this is&hellip;</p>

 <!-- Shown only until the planner has been used or something is
      starred. A banner that keeps selling a feature to somebody already
      using it is nagging, not signposting. -->
 <section id="cta" class="cta" hidden>
  <div>
   <strong><b id="n-cta">__TOTAL__</b> sessions is the problem, not the feature.</strong>
   <span>Tell <b>Plan a day</b> which day you are on and where you will be
    standing, and it builds an itinerary you can actually walk &mdash;
    travel between buildings counted, a real break in the middle, and the
    small rooms flagged before they fill.</span>
  </div>
  <button id="cta-go" class="ctabtn">Plan a day &rarr;</button>
 </section>

 <nav class="lanes" aria-label="Team lanes">
 __LANETABS__
 </nav>

 <section class="controls" aria-label="Search and filters">
  <div class="searchrow">
   <input id="q" type="search" autocomplete="off"
    placeholder="Search title, abstract, code, speaker, or one of __SERVICES__ services">
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
   <button id="tab-now" class="vt" role="tab" aria-selected="false">Now</button>
   <button id="tab-plan2" class="vt vt-primary" role="tab"
    aria-selected="false">Plan a day <span class="vt-hint">start here</span></button>
   <button id="tab-news" class="vt" role="tab" aria-selected="false">Just announced</button>
  </div>
 </section>

 <p id="browsetip" class="browsetip" hidden></p>
 <section id="browse" class="results"></section>

 <section id="plan" class="plan" hidden>
  <p id="storagewarn" class="notebook bad" hidden></p>
  <p class="notebook">Your plan and your notes live <b>in this browser
   only</b> &mdash; nothing is uploaded and there is no account. That keeps
   it private and makes it work with no signal, but it has two
   consequences worth knowing before you rely on it.
   <b>A private or incognito window throws all of it away the moment you
   close the last tab</b>, however many times it said &ldquo;saved&rdquo;
   &mdash; use a normal window. And another device will not see any of it.
   <b>Back up notebook</b> below writes a file that restores everything,
   notes included; do it before the event and after each day.</p>
  <div id="planbody"></div>
  <div class="planfoot">
   <button id="share" class="ghost">Copy a link to this plan</button>
   <button id="verify" class="ghost">Re-check against AWS</button>
   <button id="ics" class="ghost">Add to calendar (.ics)</button>
   <button id="md" class="ghost">Export notes as Markdown</button>
   <button id="backup" class="ghost">Back up notebook</button>
   <button id="restore" class="ghost">Restore&hellip;</button>
   <input id="restore-file" type="file" accept="application/json" hidden>
   <button id="wipe" class="ghost danger">Clear plan</button>
  </div>
 </section>

 <section id="plan2" class="planwrap" hidden>
  <p class="maplede">Tell it the day and where you will be standing at
   08:00, and it builds a day that actually works: travel time between
   buildings honoured, a real break in the middle, and the hands-on
   formats preferred over 20-minute sponsored slots.</p>
  <!-- A form, laid out as one. This was a wrapped row of inline labels
       that read as a ragged sentence and stacked into a scattered pile on
       a phone: "somehow I am not impressed with layout, though I like the
       feature." Label above field, even columns, one card. -->
  <div class="plform">
   <label class="plf"><span>Day</span><select id="pl-day"></select></label>
   <label class="plf"><span>Starting from</span>
    <select id="pl-at"></select></label>
   <label class="plf"><span>Pace</span>
    <select id="pl-pace">
     <option value="relaxed">Relaxed &mdash; 25 min spare</option>
     <option value="standard">Standard &mdash; 15 min spare</option>
     <option value="packed">Packed &mdash; 5 min spare</option>
    </select>
   </label>
   <label class="plf"><span>Focus</span><select id="pl-lane"></select></label>
   <label class="plf"><span>Service</span>
    <select id="pl-service"></select></label>
   <div class="plf-foot">
    <label class="chk"><input id="pl-sponsored" type="checkbox">
     <span>Include sponsored sessions</span></label>
    <button id="pl-reset" class="ghost small" hidden>Reset</button>
   </div>
  </div>
  <div id="planbody2"></div>
 </section>

 <section id="news" class="newswrap" hidden>
  <p class="maplede">What AWS has shipped recently, matched to the sessions
   covering the same service. The match is by <b>service</b>, not by topic:
   it says these are about the same thing, not that the session covers the
   launch. During the event that is the overlap worth chasing &mdash; they
   announce it in the keynote, and someone is running a chalk talk on it
   that afternoon.</p>
  <div id="newsbody"></div>
 </section>

 <section id="now" class="nowwrap" hidden>
  <p id="nownote" class="nownote">&nbsp;</p>
  <!-- "I am at" is OUTSIDE the preview controls on purpose. It used to be
       inside them, and those are hidden once the real clock takes over --
       so during the event, which is the only time this view matters, there
       was no way to say where you were standing. The whole view answers
       "what is near me"; me has to stay settable. -->
  <div class="maprow">
   <label>I am at <select id="now-at"></select></label>
  </div>
  <div id="nowpick" class="maprow">
   <label>day <select id="now-day"></select></label>
   <label>time <input id="now-time" type="time" step="300"></label>
  </div>
  <div id="nowbody"></div>
 </section>

 <section id="map" class="mapwrap" hidden>
  <p class="maplede">Where the sessions actually are. Circle size is how many
   of the <b id="map-n">&nbsp;</b> sessions currently matching your filters sit
   at each property &mdash; so narrowing to a lane shows you where to base
   yourself. Pick a day to draw your plan's route across it.</p>
  <div class="maprow">
   <label>Route for
    <select id="map-day"><option value="">&mdash; star sessions first &mdash;</option></select>
   </label>
   <p id="mapday-hint" class="dayhint">&nbsp;</p>
  </div>
  <div id="mapwrap" class="mapbox">
   <div id="mapsvg"></div>
   <div class="mapctl">
    <button id="z-in"  class="zb" aria-label="Zoom in">+</button>
    <button id="z-out" class="zb" aria-label="Zoom out">&minus;</button>
    <button id="z-fit" class="zb wide">Fit</button>
    <button id="z-full" class="zb wide">Expand</button>
   </div>
   <p class="maphint">Drag to pan &middot; scroll or pinch to zoom &middot;
    tap a venue to filter to it</p>
  </div>
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
  <p>The distances are measured, not remembered. Each venue's position is
   the centroid of the building its sessions are actually in &mdash; the
   Venetian Expo rather than the Venetian tower, the MGM Grand Conference
   Center rather than the middle of the resort &mdash; taken from the
   OpenStreetMap footprints this page draws. The hand-written coordinates
   that preceded them were out by up to __WORSTFIX__&nbsp;m, which is a
   different end of the property from where you would be standing.
   Distance is a fact; only the pace below is an assumption, and it is
   yours to set.</p>
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
  <p><strong>The catalog is not finished yet.</strong> AWS's own catalog
   page says it &ldquo;will include more than 2,200 sessions&rdquo;, and it
   currently publishes <strong id="n-prose">__TOTAL__</strong> &mdash; so roughly
   <strong id="n-pct">__PCT__%</strong> of the final programme exists so far. Expect
   sessions to keep arriving right up to the event. That is what the daily
   refresh is for, and why a plan built today is a first draft.</p>
  <p><strong>Where the room comes from.</strong> Each session carries its
   location in AWS's own catalog data &mdash;
   <code>MGM&nbsp;Grand | Level&nbsp;3 | Room&nbsp;301</code> &mdash; along
   with a venue and a seat count, and this page has one for every scheduled
   session. AWS's catalog <em>page</em> does not currently display the room,
   though it does offer Venue as a filter. Nothing here is inferred: it is
   the field AWS publishes, shown rather than hidden. Room assignments this
   far out should be treated as provisional.</p>
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


/* ---- countdown ----
   Two things, side by side: the number a person actually wants, and a row
   of marks giving it a shape -- one per week while the event is far off,
   one per day inside the last fortnight, one per conference day once it
   starts. The marks are decoration and are hidden from screen readers;
   the sentence beside them says the same thing in words. */
.cd{display:flex; align-items:center; gap:18px; flex-wrap:wrap;
  background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:14px 16px; margin:0 0 20px}
.cd-n{margin:0; display:flex; align-items:baseline; gap:8px}
.cd-n b{font-size:40px; line-height:1; font-weight:600; color:var(--accent);
  font-variant-numeric:tabular-nums}
.cd-n span{font-size:13px; letter-spacing:.08em; text-transform:uppercase;
  color:var(--faint)}
.cd-side{flex:1 1 260px; min-width:0}
.cd-marks{display:flex; flex-wrap:wrap; gap:4px; margin:0 0 7px}
.cd-marks i{display:block; width:14px; height:5px; border-radius:3px;
  background:var(--line)}
.cd-marks i.on{background:var(--accent2)}
.cd-marks i.now{background:var(--accent)}
.cd-note{margin:0; font-size:13px; color:var(--dim)}
.cd-note a{color:var(--accent); text-decoration:none;
  border-bottom:1px dotted var(--accent)}
/* The number breathes, so the strip reads as something running rather
   than something printed. A slow fade rather than a blink on purpose:
   anything flashing between 2 and 55 times a second is a seizure risk and
   is what the WCAG three-flash threshold is about, and a hard blink on a
   page people read for twenty minutes is an irritation besides. Two and a
   half seconds, never fully out, and a dot beside it keeping the same
   time. During the event it quickens -- that is the one time something
   really is happening. */
@keyframes cd-breathe{0%,100%{opacity:1}50%{opacity:.62}}
@keyframes cd-dot{0%,100%{opacity:.9; transform:scale(1)}
  50%{opacity:.25; transform:scale(.72)}}
.cd-n b{animation:cd-breathe 2.6s ease-in-out infinite}
/* The words sit on the dot's centre line rather than on the text
   baseline, which is what keeps the two reading as one label. */
.cd-words{vertical-align:middle}
.cd-live{display:inline-block; width:7px; height:7px; border-radius:50%;
  background:var(--accent); margin-right:7px; vertical-align:middle;
  animation:cd-dot 2.6s ease-in-out infinite}
.cd.is-live .cd-n b{animation-duration:1.4s}
.cd.is-live .cd-live{background:var(--ok); animation-duration:1.4s}
@media (prefers-reduced-motion:reduce){
  .cd-n b, .cd-live{animation:none}
}
.cd.is-live{border-color:var(--accent)}
.cd.is-live .cd-n b{color:var(--ok)}
@media (max-width:520px){
  .cd{gap:12px; padding:12px 13px}
  .cd-n b{font-size:32px}
}

/* ---- map ---- */
.mapwrap{margin:0 0 10px}
.maplede{margin:0 0 12px; font-size:14px; color:var(--dim); max-width:74ch}
.maplede b{color:var(--ink)}
.maprow{margin:0 0 12px}
.maprow label{font-size:13.5px; color:var(--faint)}
.maprow select[disabled]{opacity:.55}
.dayhint{margin:8px 0 0; font-size:13px; color:var(--faint); max-width:64ch}
.maprow select{
  font:inherit; font-size:14px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:7px 10px; margin-left:6px;
}
.mapbox{position:relative}
#mapsvg{background:#0f1413; border:1px solid var(--line);
  border-radius:var(--r); padding:6px; overflow:hidden}
svg.rimap{touch-action:none; cursor:grab}
svg.rimap:active{cursor:grabbing}
.mapctl{position:absolute; top:14px; left:14px; display:flex; gap:6px;
  flex-wrap:wrap; z-index:3}
.zb{
  font:inherit; font-size:15px; line-height:1; cursor:pointer;
  min-width:36px; height:36px; padding:0 6px;
  color:var(--ink); background:rgba(15,20,19,.86);
  border:1px solid var(--line); border-radius:9px;
  touch-action:manipulation; -webkit-tap-highlight-color:transparent;
}
.zb.wide{font-size:13px; padding:0 12px}
.zb:hover{border-color:var(--accent); color:var(--accent)}
.zb[disabled]{opacity:.4; cursor:default}
.maphint{position:absolute; bottom:12px; right:16px; margin:0; z-index:3;
  font-size:11.5px; color:var(--faint); background:rgba(15,20,19,.8);
  padding:3px 9px; border-radius:999px; pointer-events:none}
/* Fullscreen, and the fallback for Safari on iOS which has no element
   fullscreen at all. */
.mapbox:fullscreen{background:#0f1413; padding:10px}
.mapbox:fullscreen #mapsvg{height:100%; border:0}
.mapbox:fullscreen svg.rimap{height:calc(100vh - 40px)}
.mapbox.faux-full{position:fixed; inset:0; z-index:400; background:#0f1413;
  padding:10px; border-radius:0}
.mapbox.faux-full svg.rimap{height:calc(100vh - 40px)}
/* Sized off HEIGHT, not width. The Strip is a 3km line, so north-up makes
   a tall narrow picture; driving the size from the viewport height means
   it fits a phone and a laptop without ever being cropped or absurd. */
/* Fill the box. Sizing by height alone made a 449px strip inside a
   1,080px column, with dead black bands either side -- and the bands did
   not shrink when you zoomed in, so most of a desktop screen showed
   nothing. The camera below takes the box's aspect ratio instead, so the
   picture fills whatever space it is given without distorting. */
svg.rimap{display:block; width:100%; height:min(72vh, 820px)}
.rimap .ground{fill:#0f1413}
.rimap .roadcase path{fill:none; stroke:#1b2422; stroke-linecap:round;
  stroke-linejoin:round}
.rimap .roadfill path{fill:none; stroke:#2c3a36; stroke-linecap:round;
  stroke-linejoin:round}
.rimap .bldg path{fill:#1d2726; stroke:#26332f; stroke-width:2}
.rimap .bldg.venue path{fill:#4a3a2a; stroke:var(--accent); stroke-width:3}
.rimap .pin{cursor:pointer}
/* Labels overlap neighbouring pins at low zoom, and a label that eats the
   tap makes the pin under it unclickable. The circles are the targets. */
.rimap .vnum, .rimap .vname, .rimap .hoplab,
.rimap .scaletxt, .rimap .attrib, .rimap .complab{pointer-events:none}
.rimap .halo{fill:rgba(196,164,132,.14); stroke:var(--accent);
  stroke-width:calc(1.5px * var(--upx,1))}
.rimap .pin.on .halo{fill:rgba(196,164,132,.34)}
.rimap .dot{fill:var(--accent)}
.rimap .vnum{fill:var(--ink);
  font:600 calc(15px * var(--upx,1)) "DM Mono",monospace;
  paint-order:stroke; stroke:#0f1413;
  stroke-width:calc(3px * var(--upx,1))}
.rimap .vname{fill:#e6efec;
  font:600 calc(13px * var(--upx,1)) "DM Sans",sans-serif;
  paint-order:stroke; stroke:#0f1413;
  stroke-width:calc(3px * var(--upx,1))}
.rimap .hop{stroke-width:11; stroke-linecap:round}
.rimap .hop.ok{stroke:#7fb069}
.rimap .hop.warn{stroke:var(--warn); stroke-dasharray:26 18}
.rimap .hop.bad{stroke:var(--bad); stroke-dasharray:12 14}
.rimap .hoplab{font:600 calc(12px * var(--upx,1)) "DM Sans",sans-serif;
  paint-order:stroke; stroke:#0f1413;
  stroke-width:calc(3.5px * var(--upx,1))}
.rimap .hoplab.ok{fill:#9ccf8f}
.rimap .hoplab.warn{fill:var(--warn)}
.rimap .hoplab.bad{fill:var(--bad)}
.rimap .compdisc{fill:rgba(15,20,19,.82); stroke:var(--line);
  stroke-width:calc(1px * var(--upx,1))}
.rimap .needle{fill:var(--accent)}
.rimap .complab{fill:#d8e3df;
  font:700 calc(13px * var(--upx,1)) "DM Sans",sans-serif}
.rimap .scalebar{stroke:#8fa39d; stroke-width:calc(1.5px * var(--upx,1))}
.rimap .scaletxt{fill:#8fa39d;
  font:500 calc(11px * var(--upx,1)) "DM Sans",sans-serif}
.rimap .attrib{fill:#5d6e69;
  font:400 calc(10px * var(--upx,1)) "DM Sans",sans-serif}
/* ---- announcements ---- */
.plform{
  display:grid; gap:14px 16px; margin:0 0 20px; padding:16px 18px;
  border:1px solid var(--line); border-radius:var(--r);
  background:var(--panel);
  grid-template-columns:repeat(auto-fit, minmax(210px, 1fr));
}
.plf{display:flex; flex-direction:column; gap:6px; min-width:0}
.plf > span{font-size:11.5px; letter-spacing:.1em; text-transform:uppercase;
  color:var(--faint)}
.plf select{
  font:inherit; font-size:14.5px; color:var(--ink); background:var(--bg);
  border:1px solid var(--line); border-radius:10px; padding:10px 11px;
  width:100%; max-width:100%; min-width:0;
}
.plf select:focus{outline:2px solid var(--accent); outline-offset:1px;
  border-color:transparent}
.plf.wide{grid-column:1/-1}
.plf-foot{grid-column:1/-1; display:flex; gap:14px; align-items:center;
  justify-content:space-between; flex-wrap:wrap;
  border-top:1px solid var(--line); padding-top:13px; margin-top:2px}
.plf-foot .chk{display:inline-flex; align-items:center; gap:8px;
  font-size:13.5px; color:var(--dim); cursor:pointer}
.plf-foot input[type=checkbox]{width:17px; height:17px;
  accent-color:var(--accent)}
.plstats{
  display:grid; gap:10px; margin:0 0 18px;
  grid-template-columns:repeat(auto-fit, minmax(128px, 1fr));
}
.plstat{padding:12px 14px; border-radius:var(--r);
  border:1px solid #31463f; background:var(--panel)}
.plstat b{display:block; font:600 21px/1.15 "DM Mono",monospace;
  color:var(--accent)}
.plstat span{display:block; margin-top:3px; font-size:12px;
  color:var(--faint); line-height:1.35}
.plrow{display:flex; flex-wrap:wrap; gap:14px; align-items:center;
  margin:0 0 18px}
/* A <select> is as wide as its widest option, and the service list holds
   "Amazon Elastic Kubernetes Service (Amazon EKS)  (85)". Unconstrained
   that made the row 486px inside a 390px phone and dragged the whole
   document 115px past the viewport. min-width:0 is the part that actually
   matters -- a flex item will not shrink below its content without it. */
.plrow label{display:inline-flex; align-items:center; gap:7px;
  max-width:100%; min-width:0}
.plrow select{max-width:100%; min-width:0; flex:1 1 auto;
  text-overflow:ellipsis}
.plrow select[disabled]{opacity:.45}
.ghost.small{font-size:13px; padding:6px 12px}
.plrow label.chk{display:inline-flex; align-items:center; gap:7px}
.plrow input[type=checkbox]{width:17px; height:17px; accent-color:var(--accent)}
.browsetip{
  margin:0 0 14px; padding:10px 14px; border-radius:var(--r);
  border:1px solid #31463f; background:var(--panel);
  font-size:13.5px; color:var(--dim); line-height:1.55;
}
.browsetip b{color:var(--ink)}
.tiplink{
  font:inherit; font-size:13px; cursor:pointer; color:var(--accent);
  background:transparent; border:0; padding:0; text-decoration:underline;
  white-space:nowrap;
}
.tips{display:grid; gap:9px; margin:0 0 20px}
.tip{padding:11px 14px; border-radius:var(--r); border:1px solid var(--line);
  background:var(--panel); font-size:13.5px; color:var(--dim)}
.tip strong{display:block; color:var(--ink); font-size:14.5px;
  margin-bottom:3px}
.tip.ok{border-color:#2f4436}
.tip.warn{border-color:#5c4626; background:#221b12; color:#f0d2a6}
.tip.warn strong{color:#f7e2c2}
.tip.info{border-color:#31463f}
.nowfold{border:1px solid var(--line); border-radius:var(--r);
  background:var(--panel); padding:0 13px}
.nowfold summary{cursor:pointer; padding:12px 0; font-size:13.5px;
  color:var(--dim); font-weight:500}
.nowfold[open] summary{border-bottom:1px solid var(--line);
  margin-bottom:11px}
.nowfold .card{margin-bottom:9px}
.newsitem{
  background:var(--panel); border:1px solid var(--line);
  border-radius:var(--r); padding:12px 15px; margin:0 0 9px;
}
.newsitem .top{display:flex; flex-wrap:wrap; gap:7px; align-items:center;
  font-size:12.5px; margin-bottom:5px}
.newstitle{margin:0 0 6px; font-size:14.5px; line-height:1.45; color:var(--ink)}
.newsitem .where{margin-bottom:6px}
.newsitem a.code{cursor:pointer}

/* ---- now ---- */
.nownote{margin:0 0 12px; font-size:14px; color:var(--faint)}
.nownote.live{color:var(--accent2); font-weight:500}
.nowwrap .maprow{display:flex; flex-wrap:wrap; gap:14px; align-items:center}
.nowwrap input[type=time]{
  font:inherit; font-size:14px; color:var(--ink); background:var(--panel);
  border:1px solid var(--line); border-radius:10px; padding:6px 10px;
}
.card.unreachable{opacity:.55}

/* ---- the live verdict on a plan card ---- */
.vrow{grid-column:1/-1; margin-top:8px; padding:7px 11px; border-radius:10px;
  border:1px solid var(--line); background:var(--bg); font-size:13px;
  color:var(--dim)}
.vrow.ok{border-color:#2f4436; color:#9ccf8f}
.vrow.warn{border-color:#5c4626; color:#f0d2a6}
.vrow.bad{border-color:#5e332a; color:#f2c3b4}

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
/* Six pills do not fit a phone on one line. This was display:flex with no
   wrap, so at 390px the row measured 449px and dragged the whole document
   to 462 -- which is what turned on Chrome's font boosting and cut the
   body text off mid-word. Worse, "Just announced" ended up outside the
   viewport and could not be tapped at all: a whole view unreachable on
   the device most likely to be used at the conference. */
.viewtabs{display:flex; gap:6px; flex-wrap:wrap; justify-content:flex-end}
.vt{
  font:inherit; font-size:14px; cursor:pointer; color:var(--dim);
  background:transparent; border:1px solid var(--line);
  border-radius:999px; padding:6px 14px;
  /* Adding "start here" to one tab widened it, the flex row squeezed the
     lot, and "Plan a day" wrapped to three lines inside its own pill and
     ran under the next one. A tab label is never a paragraph, and the row
     already wraps -- so the pills keep their size and the ROW breaks. */
  white-space:nowrap; flex:0 0 auto;
}
.vt[aria-selected="true"]{background:var(--panel2); color:var(--ink); border-color:var(--accent)}
/* The tab that answers the question the page exists for. It was the
   fifth of six, weighted exactly like "Just announced".

   Named vt-primary, not "star": .star is already the 40x40 favourite
   button on every session card, so `class="vt star"` inherited
   width:40px and the label spilled out of its own pill across the tab
   next to it. Third collision of this kind here -- .cf-num across two
   files, --ink meaning the opposite of itself, and now this. */
.vt.vt-primary{border-color:var(--accent); color:var(--ink);
  background:linear-gradient(var(--panel2), var(--panel))}
.vt.vt-primary .vt-hint{display:inline-block; margin-left:6px;
  font-size:10.5px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--accent)}
.vt.vt-primary[aria-selected="true"] .vt-hint{display:none}

.cta{
  display:flex; gap:16px; align-items:center; justify-content:space-between;
  flex-wrap:wrap; margin:0 0 20px; padding:15px 18px;
  border:1px solid var(--accent); border-radius:var(--r);
  background:linear-gradient(135deg, #1d2624, var(--panel));
}
.cta strong{display:block; color:var(--ink); font-size:16px;
  margin-bottom:4px}
.cta span{font-size:14px; color:var(--dim); max-width:72ch; display:block}
.cta b{color:var(--accent)}
.ctabtn{
  font:inherit; font-size:14.5px; font-weight:600; cursor:pointer;
  color:#1b1410; background:var(--accent); border:0; border-radius:999px;
  padding:11px 20px; white-space:nowrap; flex:none;
  touch-action:manipulation; -webkit-tap-highlight-color:transparent;
}
.ctabtn:hover{filter:brightness(1.07)}
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
.seat{border-radius:999px; padding:1px 8px; font-size:11.5px; border:1px solid}
.seat.small{color:var(--warn); border-color:#5c4626}
.seat.tight{color:var(--bad); border-color:#5e332a; font-weight:600}
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
.notewrap{grid-column:1/-1; margin-top:9px}
textarea.note{
  width:100%; font:inherit; font-size:13.5px; color:var(--ink);
  background:var(--bg); border:1px solid var(--line);
  border-radius:10px; padding:8px 10px; resize:vertical; min-height:44px;
}
textarea.note:focus{outline:2px solid var(--accent); outline-offset:1px;
  border-color:transparent}
textarea.note::placeholder{color:var(--faint)}
.svmark{grid-column:1/-1; margin-top:8px; font-size:12.5px;
  padding:5px 10px; border-radius:8px; border:1px solid var(--line)}
.svmark.hit{color:#9ccf8f; border-color:#2f4436; background:#141d18}
.svmark.fill{color:var(--faint); background:var(--bg)}
.notewrap{position:relative}
.saved{position:absolute; right:10px; bottom:8px; font-size:11.5px;
  color:var(--accent2); opacity:0; transition:opacity .3s;
  pointer-events:none}
.saved.on{opacity:1}
.saved.dim{opacity:.55}
.saved.warn{color:var(--bad); opacity:1}
.notebook.bad{border-color:#5e332a; background:#231613; color:#f2c3b4}
.notebook{margin:0 0 16px; padding:11px 14px; border-radius:var(--r);
  border:1px solid #31463f; background:var(--panel); font-size:13.5px;
  color:var(--dim); line-height:1.55; max-width:76ch}
.notebook b{color:var(--ink)}

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
/* The cost table is six columns of nowrap figures: about 430px of content
   that cannot be reflowed without making it unreadable. So it scrolls
   inside its own box rather than widening the page -- the same answer the
   rest of this site uses for wide tables. */
#matrix{overflow-x:auto; -webkit-overflow-scrolling:touch}
table.mx{border-collapse:collapse; font-size:12.5px; margin:8px 0 14px;
  width:100%; min-width:430px}
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
  /* AWS's stated final size, written in from the builder's constant so
     the percentage the page prints cannot drift from the one it was
     built with. */
  var AWS_PLANNED = __PLANNED__;
  /* 60 cards is fifteen phone screens before the "show more" button.
     Measured in a sweep of every view: nobody reported it, which is not
     the same as nobody suffering it. A phone gets a shorter first page
     and the same button. */
  var PAGE_SIZE = (typeof window !== "undefined" && window.innerWidth < 700)
                  ? 25 : 60;
  var shown = PAGE_SIZE;
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

  /* Does this browser actually keep anything?
     Reported: "it says saved, and when I close the browser and reopen, I
     don't see it." Tested with a persistent profile: a star and a note do
     survive a full close. What does not survive is a PRIVATE window --
     Safari and Chrome both discard localStorage when the last private tab
     closes, and the reporter's own screenshot showed "jayanthkatta.com --
     Private" in the toolbar.

     Sniffing for private mode is unreliable -- measured quota at 10 GB in
     a normal profile and 3 GB in an ephemeral one, and Safari differs
     again -- so this does not guess. It proves the one thing it can prove:
     that a write survives a read. Anything beyond that is stated in words
     rather than detected badly. */
  var storageOK = (function () {
    try {
      var k = "ri2026.probe";
      localStorage.setItem(k, "1");
      var back = localStorage.getItem(k) === "1";
      localStorage.removeItem(k);
      return back;
    } catch (e) { return false; }
  })();

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
  /* "at 17:20 today" reads better than an ISO timestamp and better than
     "3 hours ago" -- the reader is deciding whether to pull again, and a
     clock time is what they can compare against their own day. */
  function agoWords(iso) {
    var t = Date.parse(iso);
    if (!t) return "earlier";
    var d = new Date(t), now = new Date();
    var same = d.toDateString() === now.toDateString();
    var hhmm_ = (d.getHours() < 10 ? "0" : "") + d.getHours() + ":"
              + (d.getMinutes() < 10 ? "0" : "") + d.getMinutes();
    return same ? "at " + hhmm_ + " today"
                : "on " + d.toLocaleDateString(undefined,
                    { day: "numeric", month: "long" });
  }

  function dayLabel(iso) {
    var d = new Date(iso + "T12:00:00");
    return d.toLocaleDateString(undefined,
      { weekday: "long", day: "numeric", month: "long" });
  }

  /* ---- the countdown -------------------------------------------------
     Four states, because a countdown that only knows how to count down is
     wrong for a week either side of the thing it counts to:

       far off      the number of days, with one mark per whole week
       the last     the number of days, with one mark per day, so the
       fortnight    row itself shows the week closing
       during       which conference day it is, out of five, and a way
                    into the Now view rather than a number
       afterwards   it is over, and says so

     Everything comes from CFG.event and CFG.days -- the same dates the
     rest of the page runs on -- and is recomputed every minute, so a page
     left open overnight does not still say yesterday's number. */
  function isoOf(d) {
    return d.getFullYear() + "-"
         + String(d.getMonth() + 1).padStart(2, "0") + "-"
         + String(d.getDate()).padStart(2, "0");
  }

  function daysBetween(isoA, isoB) {
    /* Both parsed as UTC noon: a day difference computed from local
       midnights is off by one on the days either side of a DST change,
       and this number is the one a reader checks against their calendar. */
    var a = Date.parse(isoA + "T12:00:00Z"), b = Date.parse(isoB + "T12:00:00Z");
    return Math.round((b - a) / 86400000);
  }

  function marks(host, total, done, cap) {
    host.textContent = "";
    if (!total || total > cap) return;
    for (var i = 0; i < total; i++) {
      var m = el("i", i < done ? "on" : (i === done ? "now" : null));
      host.appendChild(m);
    }
  }

  function renderCountdown() {
    var box = $("#countdown");
    if (!box || !CFG.event || !CFG.days || !CFG.days.length) return;
    var num = $("#cd-num"), note = $("#cd-note"), row = $("#cd-marks");
    /* The pulsing dot lives inside the unit line, so the words go in a
       span of their own -- setting textContent on the line itself would
       delete the dot on the first repaint, which is the kind of thing
       that works until the minute tick runs. */
    var unitBox = $("#cd-unit"), unit = unitBox.querySelector(".cd-words");
    if (!unit) {
      unit = el("span", "cd-words");
      unitBox.appendChild(unit);
    }
    var today = isoOf(new Date());
    var first = CFG.days[0], last = CFG.days[CFG.days.length - 1];
    var to = daysBetween(today, first);
    box.hidden = false;
    box.classList.remove("is-live");
    note.textContent = "";
    row.textContent = "";

    if (today >= first && today <= last) {
      var n = CFG.days.indexOf(today) + 1;
      box.classList.add("is-live");
      num.textContent = n;
      unit.textContent = "of " + CFG.days.length + " — happening now";
      marks(row, CFG.days.length, n - 1, 14);
      note.appendChild(document.createTextNode(
        dayLabel(today) + ". "));
      var a = el("a", null, "What is on right now");
      a.href = "#now";
      a.addEventListener("click", function (e) {
        e.preventDefault(); view("now", { scroll: true });
      });
      note.appendChild(a);
      note.appendChild(document.createTextNode("."));
      return;
    }

    if (today > last) {
      var since = daysBetween(last, today);
      num.textContent = "—";
      unit.textContent = "that is a wrap";
      note.textContent = "re:Invent 2026 finished " + (
        since === 1 ? "yesterday" : since + " days ago")
        + ". Every session is still here to look back over.";
      return;
    }

    num.textContent = to.toLocaleString();
    unit.textContent = to === 1 ? "day to go" : "days to go";
    if (to <= 14) {
      marks(row, to, 0, 14);
    } else {
      marks(row, Math.floor(to / 7), 0, 30);
    }
    var weeks = Math.floor(to / 7), rest = to % 7, shape;
    if (to <= 14) {
      shape = "";
    } else {
      shape = weeks + (weeks === 1 ? " week" : " weeks")
            + (rest ? " and " + rest + (rest === 1 ? " day" : " days") : "")
            + ". ";
    }
    note.textContent = shape + "Doors open " + dayLabel(first) + ", and the "
      + "catalog is still filling — a plan made today is a first draft.";
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
  function speakerNames(s) {
    if (!s.sp || !DATA.speakers) return [];
    return s.sp.map(function (i) { return DATA.speakers[i]; });
  }

  /* How hard is a seat, from the capacity AWS publishes. Measured across
     the catalog: Builders' sessions are 50 seats, every one of them; chalk
     talks run 70-98; breakouts 100-1000. So a small room is a real
     constraint rather than a guess -- but it is only half the story,
     because demand is published nowhere. The wording therefore says what
     is known (the room is small) and not what is not (that it will fill). */
  var TIGHT = 60, SMALL = 100;

  function seatNote(slot) {
    if (!slot || !slot.cap) return null;
    if (slot.cap <= TIGHT)
      return { cls: "seat tight", txt: slot.cap + " seats \u2014 reserve early" };
    if (slot.cap <= SMALL)
      return { cls: "seat small", txt: slot.cap + " seats" };
    return null;
  }

  function typeName(s) {
    return s.ty == null ? "" : DATA.facets.Type[s.ty];
  }
  function levelName(s) {
    return s.lv == null ? "" : DATA.facets.Level[s.lv];
  }
  function venueName(slot) { return DATA.venues[slot.v]; }
  function roomName(slot) { return DATA.rooms[slot.r]; }

  /* Lanes are defined at build time as indices into the stored Services
     table. A live pull rebuilds that table from the fresh payload, and a
     table built from a different set of sessions does not number its
     services the same way -- so the indices would go on matching, silently,
     against whatever now sits at 37 and 103. The names are resolved once,
     from the store the page booted with, and re-indexed against whatever
     table is current. */
  var LANE_NAMES = null, LANE_SV = {};

  function indexLanes() {
    var svs = (DATA.facets && DATA.facets.Services) || [];
    if (!LANE_NAMES) {
      LANE_NAMES = {};
      CFG.lanes.forEach(function (l) {
        /* The names the build resolved, not names read back out of
           whatever store happens to have loaded first -- which on a live
           pull is already the table that renumbered them. */
        LANE_NAMES[l.id] = (l.sv || []).slice();
      });
    }
    LANE_SV = {};
    CFG.lanes.forEach(function (l) {
      LANE_SV[l.id] = LANE_NAMES[l.id].map(function (n) {
        return svs.indexOf(n);
      }).filter(function (i) { return i >= 0; });
    });
  }

  function laneServices(id) {
    if (LANE_SV[id]) return LANE_SV[id];
    for (var i = 0; i < CFG.lanes.length; i++)
      if (CFG.lanes[i].id === id) return CFG.lanes[i].services;
    return null;
  }

  /* Every session count the page prints, recomputed from whatever DATA now
     holds. Asked directly: "when the live sessions are updated, why does
     everything still show the previous numbers -- are they hard coded?"
     They were: the header, the lane tabs, the callout and the paragraph
     about how much of the programme exists were all written in at build
     time, so a live pull refreshed the results underneath them and left
     every figure around them describing the copy it had just replaced. */
  function renderCounts() {
    var n = DATA.sessions.length;
    var scheduled = 0, i;
    for (i = 0; i < DATA.sessions.length; i++)
      if (DATA.sessions[i].when && DATA.sessions[i].when.length) scheduled++;
    var put = function (id, text) {
      var e = document.getElementById(id);
      if (e) e.textContent = text;
    };
    put("n-total", n.toLocaleString());
    put("n-scheduled", scheduled.toLocaleString());
    put("n-cta", n.toLocaleString());
    put("n-prose", n.toLocaleString());
    put("n-pct", Math.round(100 * n / AWS_PLANNED) + "%");

    var all = document.querySelector('[data-count="all"]');
    if (all) all.textContent = n.toLocaleString();
    CFG.lanes.forEach(function (l) {
      var want = LANE_SV[l.id] || l.services || [], c = 0;
      for (var k = 0; k < DATA.sessions.length; k++) {
        var sv = DATA.sessions[k].sv || [];
        for (var j = 0; j < sv.length; j++) {
          if (want.indexOf(sv[j]) !== -1) { c++; break; }
        }
      }
      var cell = document.querySelector('[data-count="' + l.id + '"]');
      if (cell) cell.textContent = c.toLocaleString();
    });

    var q = document.getElementById("q");
    if (q && DATA.facets && DATA.facets.Services) {
      q.placeholder = "Search title, abstract, code, speaker, or one of "
        + DATA.facets.Services.length + " services";
    }
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
      /* The room string is in here too. Every session has one -- all
         1,561 scheduled ones carry a full "Venetian | Level 2 | Ballroom
         F | Content Hub | Purple Theater" -- and without it, typing the
         name of the building you are standing in returned nothing at all.
         "MGM Grand" found 0 sessions, which is an absurd answer from a
         page whose whole subject is where things are. */
      var where = s.when.map(function (w) {
        return roomName(w); }).join(" ");
      var hay = (s.c + " " + s.t + " " + s.a + " " +
                 svcNames(s).join(" ") + " " +
                 speakerNames(s).join(" ") + " " + where).toLowerCase();
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

    var note = seatNote(slot);
    if (note) top.appendChild(el("span", note.cls, note.txt));

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
      if (speakerNames(s).length)
        abs.appendChild(el("span", null, "\n\nSpeakers: " +
          speakerNames(s).join("; ")));
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
    browseTip(list);

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
  /* Two independent facts, kept apart because they were one field and
     that field was being overwritten. `source` is which copy is on screen
     -- what shipped, one pulled now, or one kept from an earlier visit.
     `state` is what the one-request check against AWS found. The live
     check finishes AFTER a kept copy is adopted, so folding them together
     meant the answer to "where did these numbers come from" was replaced
     by the answer to "is AWS listing the same number", a second later and
     silently. */
  var live = { state: "idle", source: "shipped", total: null,
               checkedAt: null, at: null, kept: false };

  /* What "Load the live catalog" leaves behind.
     ---------------------------------------------------------------------
     Reported as: "when I load live catalog the number changes to 1,599,
     and when I close the session and come back it still shows 1,581. I
     really don't understand."

     Fairly. The pull lived in memory for one visit, so closing the tab
     threw it away and the shipped snapshot came back -- the page looked
     like it had forgotten something it had just been told. This site is
     static: a visitor's browser cannot write to it, and the copy in the
     repository is refreshed by a job every morning. What the browser CAN
     do is keep the pull for itself, which is what this does.

     Kept beside the plan and the notes, in the same localStorage the rest
     of the page uses, and discarded as soon as the shipped copy is newer
     -- a stale live pull outliving the daily refresh would be the same
     bug pointing the other way. */
  var LIVE_KEY = "ri2026.live";
  var LIVE_MAX_DAYS = 3;

  function keepLive(data, when) {
    /* Not save(): that swallows a quota error, and here the difference
       between "kept" and "not kept" is the sentence the reader is about
       to be shown. A slimmed catalog is about 1.5 MB, which fits the
       usual 5 MB budget -- but private windows and a full origin do
       refuse, and the honest thing is to say so rather than to promise
       it will still be here. */
    try {
      localStorage.setItem(LIVE_KEY, JSON.stringify(
        { at: when, n: data.sessions.length, d: data }));
      return true;
    } catch (e) {
      try { localStorage.removeItem(LIVE_KEY); } catch (e2) {}
      return false;
    }
  }

  function adoptCachedLive() {
    var c = load(LIVE_KEY, null);
    if (!c || !c.d || !c.at) return false;
    var age = (Date.now() - Date.parse(c.at)) / 86400000;
    /* captured_utc, not captured: the latter is a date, so it parses as
       midnight and would make a pull from lunchtime look newer than a
       snapshot taken that evening -- the kept copy would then outlive the
       refresh that superseded it. */
    var shipped = Date.parse(DATA.captured_utc
                             || ((DATA.captured || "1970-01-01") + "T23:59:59Z"));
    /* age < 0 is a device whose clock runs ahead, which is common enough
       that treating it as corruption would throw away good copies. A day
       of slack, and beyond that the timestamp is not a time. */
    if (!(age > -1) || age > LIVE_MAX_DAYS
        || Date.parse(c.at) <= shipped) {
      /* The morning job has caught up, or the pull is old enough that it
         is no longer the better answer. Either way the shipped copy wins
         and this one goes. */
      try { localStorage.removeItem(LIVE_KEY); } catch (e) {}
      return false;
    }
    DATA = c.d;
    live.source = "cached";
    live.at = c.at;
    live.kept = true;
    return true;
  }

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
      live.state = "same";
      live.source = "live";
      live.checkedAt = Date.now();
      live.at = new Date().toISOString();
      live.kept = keepLive(DATA, live.at);
      indexLanes(); renderCounts();
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
    if (live.source !== "shipped") {
      var justNow = live.source === "live";
      box.className = "fresh good";
      box.appendChild(el("b", null, justNow
        ? "Showing the live catalog"
        : "Showing the live catalog you loaded " + agoWords(live.at)));
      box.appendChild(el("span", null,
        (justNow ? ", pulled from AWS a moment ago — " : " — ")
        + DATA.sessions.length.toLocaleString() + " sessions. "));
      /* The bit that was missing, and the reason this was confusing: a
         reader has no way to know whether a button labelled "load" wrote
         anything anywhere, or for how long. Say it. */
      box.appendChild(el("span", "livenote", live.kept
        ? "Kept in this browser, so it is still here when you come back. "
          + "The site's own copy refreshes every morning. "
        : "This browser would not store it, so a reload brings back the "
          + "site's saved copy. "));
      box.appendChild(el("span", null, "Seat reservations still live in the "));
      addCatalogLink(box);
      /* And if AWS has moved again since this copy was pulled, say so
         here too -- a kept copy goes stale exactly the way a shipped one
         does, and hiding that would make this worse than what it
         replaced. */
      appendLive(box);
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
      btn.title = "Fetches the whole catalog from AWS in this browser and "
                + "keeps it on this device. The site's own copy refreshes "
                + "every morning.";
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
  /* ---- the map -------------------------------------------------------
     Drawn from real OpenStreetMap geometry -- building footprints and the
     actual street grid -- baked in at build time. The version this
     replaces was five circles on an empty background, which had the
     positions right and nothing else. Reported as: "what is this map? It
     doesn't make any sense ... at least I need to see the buildings, and
     the roads ... are we at the north side of the map or south?"

     NORTH IS UP, because that is what every map a person has ever used
     does, and the previous one's quarter turn was the reason that
     question had to be asked at all. The Strip runs NNE to SSW, so the
     result is tall and narrow -- which is the actual shape of the place,
     and sizing is driven off height so it fits a phone and a laptop
     without ever being cropped.

     No embed, deliberately. No API key, nothing third-party running in
     the reader's browser, and it still draws with the wifi down -- which
     is exactly when somebody in a packed hall needs to know which way the
     Venetian is. */
  var GEO = null, geoState = "idle", mapProj = null;

  /* Equirectangular, which is exact enough across two kilometres and keeps
     north pointing at the top of the screen. Metres, so the scale bar is
     arithmetic rather than a guess. */
  function projector(bbox) {
    var south = bbox[0], west = bbox[1], north = bbox[2], east = bbox[3];
    var mLat = 110540.0;
    var mLon = 111320.0 * Math.cos((south + north) / 2 * Math.PI / 180);
    var w = (east - west) * mLon, h = (north - south) * mLat;
    return {
      w: w, h: h,
      x: function (lon) { return (lon - west) * mLon; },
      y: function (lat) { return (north - lat) * mLat; }
    };
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

  /* Road weights in METRES, so they scale with the map instead of needing
     a stroke-width that means something different at every size. */
  var ROAD_W = { motorway: 26, motorway_link: 14, trunk: 22, trunk_link: 12,
                 primary: 20, primary_link: 11, secondary: 15,
                 secondary_link: 9, tertiary: 12, residential: 8 };

  function loadGeo() {
    if (geoState === "loading" || geoState === "ready") return;
    geoState = "loading";
    fetch("/intelligence/vegas-map.json")
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (g) {
        GEO = g;
        geoState = "ready";
        renderMap();
        // The SVG is thousands of pixels of new layout. Re-align once,
        // and only if the reader has not started scrolling.
        if (!userMoved && !$("#map").hidden) scrollToTabs();
      })
      .catch(function () { geoState = "failed"; renderMap(); });
  }

  function renderMap() {
    var host = $("#mapsvg");
    if (!host) return;

    if (geoState === "idle") { loadGeo(); }
    if (geoState === "loading" || geoState === "idle") {
      host.textContent = "";
      host.appendChild(el("p", "empty", "Drawing the map…"));
      return;
    }
    if (geoState === "failed" || !GEO) {
      host.textContent = "";
      host.appendChild(el("p", "empty",
        "The map geometry did not load. Everything else on this page still "
        + "works, and the distances below are unaffected."));
      renderHops(currentHops());
      return;
    }

    var P = projector(GEO.bbox);
    mapProj = P;
    var pad = padM;
    /* The geographic extent. The frame around it is derived later, in
       refit(), because the element has no height until the SVG is in the
       document -- measuring first gave an aspect near zero and a fit view
       27,474 metres wide, which is most of Nevada. */
    geoExtent = { x: -pad, y: -pad, w: P.w + pad * 2, h: P.h + pad * 2 };
    var fit = { x: geoExtent.x, y: geoExtent.y,
                w: geoExtent.w, h: geoExtent.h };
    var keep = (baseView && cam
                && Math.abs(baseView.w - fit.w) < 1) ? cam : null;
    baseView = fit;
    cam = keep || { x: fit.x, y: fit.y, w: fit.w, h: fit.h };
    var svg = svgEl("svg", {
      viewBox: (-pad) + " " + (-pad) + " " + (P.w + pad * 2) + " "
               + (P.h + pad * 2),
      preserveAspectRatio: "xMidYMid meet",
      class: "rimap", role: "img",
      "aria-label": "Map of the re:Invent venues on the Las Vegas Strip, "
        + "north at the top, showing building footprints and streets."
    });

    svg.appendChild(svgEl("rect", {
      x: -pad, y: -pad, width: P.w + pad * 2, height: P.h + pad * 2,
      class: "ground" }));

    function pathOf(pts, close) {
      var d = "";
      for (var i = 0; i < pts.length; i++)
        d += (i ? "L" : "M") + P.x(pts[i][1]).toFixed(1) + ","
             + P.y(pts[i][0]).toFixed(1);
      return d + (close ? "Z" : "");
    }

    /* Roads twice: a dark casing, then a lighter fill on top. That is how
       a street reads as a street rather than as a line. */
    var casing = svgEl("g", { class: "roadcase" });
    var fill = svgEl("g", { class: "roadfill" });
    GEO.roads.forEach(function (r) {
      var w = ROAD_W[r.c] || 8;
      var d = pathOf(r.p, false);
      casing.appendChild(svgEl("path", { d: d, "stroke-width": w + 6 }));
      fill.appendChild(svgEl("path", { d: d, "stroke-width": w }));
    });
    svg.appendChild(casing);
    svg.appendChild(fill);

    /* Buildings. Everything in muted grey for context; the five venues in
       the accent, because those are the only ones anyone is walking to. */
    var others = svgEl("g", { class: "bldg" });
    var ours = svgEl("g", { class: "bldg venue" });
    GEO.buildings.forEach(function (b) {
      var node = svgEl("path", { d: pathOf(b.p, true) });
      if (b.n) node.appendChild(svgEl("title", {})).textContent = b.n;
      (b.v ? ours : others).appendChild(node);
    });
    svg.appendChild(others);
    svg.appendChild(ours);

    /* The route for the chosen day, over the top of the streets. */
    var hops = currentHops();
    var routeG = svgEl("g", { class: "route" });
    hops.forEach(function (h, i) {
      var a = CFG.travel.points[h.from], b = CFG.travel.points[h.to];
      if (!a || !b || h.from === h.to) return;
      routeG.appendChild(svgEl("line", {
        x1: P.x(a[1]), y1: P.y(a[0]), x2: P.x(b[1]), y2: P.y(b[0]),
        class: "hop " + h.verdict }));
      var mx = (P.x(a[1]) + P.x(b[1])) / 2;
      var my = (P.y(a[0]) + P.y(b[0])) / 2;
      var lab = svgEl("text", { x: mx, y: my - 22,
                                class: "hoplab " + h.verdict,
                                "text-anchor": "middle" });
      lab.textContent = (i + 1) + ". " + h.gapText;
      routeG.appendChild(lab);
    });
    svg.appendChild(routeG);

    /* Venue pins, sized by how many of the filtered sessions are there.
       Tapping one filters the catalogue to that property. */
    var heat = {}, total = 0;
    Object.keys(CFG.travel.matrix).forEach(function (n) { heat[n] = 0; });
    filtered().forEach(function (sn) {
      var seen = {};
      sn.when.forEach(function (w) {
        var v = venueName(w);
        if (state.day && w.d !== state.day) return;
        if (seen[v]) return;
        seen[v] = 1;
        if (heat[v] === undefined) heat[v] = 0;
        heat[v] += 1; total += 1;
      });
    });
    var peak = Math.max.apply(null, Object.keys(heat).map(
      function (n) { return heat[n]; }).concat([1]));
    var nEl = $("#map-n");
    if (nEl) nEl.textContent = total.toLocaleString();

    var pins = svgEl("g", { class: "pins" });
    Object.keys(CFG.travel.points).forEach(function (name) {
      var p = CFG.travel.points[name];
      var cx = P.x(p[1]), cy = P.y(p[0]);
      var r = 34 + Math.round(Math.sqrt(heat[name] / peak || 0) * 56);
      var g = svgEl("g", { class: "pin" + (state.venue === name
                                           ? " on" : "") });
      g.appendChild(svgEl("circle", { cx: cx, cy: cy, r: r,
                                      class: "halo" }));
      g.appendChild(svgEl("circle", { cx: cx, cy: cy, r: 13,
                                      class: "dot" }));
      var num = svgEl("text", { x: cx, y: cy + r + 46, class: "vnum",
                                "text-anchor": "middle" });
      num.textContent = heat[name];
      var nm = svgEl("text", { x: cx, y: cy + r + 86, class: "vname",
                               "text-anchor": "middle" });
      nm.textContent = name;
      g.appendChild(num);
      g.appendChild(nm);
      g.addEventListener("click", function () {
        var turningOn = state.venue !== name;
        state.venue = turningOn ? name : "";
        shown = PAGE_SIZE;
        buildFilters();
        renderChips(); renderBrowse(); renderMap();
        if (turningOn) zoomToVenue(name);
      });
      var t = svgEl("title", {});
      t.textContent = name + " — " + heat[name] + " session(s) matching"
                      + " your filters. Tap to show only these.";
      g.appendChild(t);
      pins.appendChild(g);
    });
    svg.appendChild(pins);

    /* Compass. The question was literally "are we at the north side of the
       map or south", so this is not decoration. */
    var cx = P.w - 80, cy = 80;
    var comp = svgEl("g", { class: "compass" });
    comp.appendChild(svgEl("circle", { cx: cx, cy: cy, r: 54,
                                       class: "compdisc" }));
    comp.appendChild(svgEl("path", {
      d: "M" + cx + "," + (cy - 40) + "L" + (cx + 15) + "," + (cy + 12)
         + "L" + cx + "," + (cy + 2) + "L" + (cx - 15) + "," + (cy + 12) + "Z",
      class: "needle" }));
    var nlab = svgEl("text", { x: cx, y: cy + 40, class: "complab",
                               "text-anchor": "middle" });
    nlab.textContent = "N";
    comp.appendChild(nlab);
    svg.appendChild(comp);

    /* Scale bar, in metres, because the viewBox is already in metres. */
    var barM = 500, bx = 40, by = P.h - 40;
    var scale = svgEl("g", { class: "scale" });
    scale.appendChild(svgEl("line", { x1: bx, y1: by, x2: bx + barM, y2: by,
                                      class: "scalebar" }));
    scale.appendChild(svgEl("line", { x1: bx, y1: by - 10, x2: bx,
                                      y2: by + 10, class: "scalebar" }));
    scale.appendChild(svgEl("line", { x1: bx + barM, y1: by - 10,
                                      x2: bx + barM, y2: by + 10,
                                      class: "scalebar" }));
    var st = svgEl("text", { x: bx + barM / 2, y: by - 20,
                             class: "scaletxt", "text-anchor": "middle" });
    st.textContent = "500 m";
    scale.appendChild(st);
    svg.appendChild(scale);

    var attr = svgEl("text", { x: 10, y: P.h + 18, class: "attrib" });
    attr.textContent = GEO.attribution;
    svg.appendChild(attr);

    host.textContent = "";
    host.appendChild(svg);
    mapSvg = svg;
    refit(true);
    wireMapGestures(svg);
    wireMapButtons();
    renderHops(hops);
  }


  /* ---- pan and zoom ---------------------------------------------------
     Asked for: "can it have some sort of zoom option or expand option ...
     somehow it's kind of very plain".

     The viewBox is the camera. Everything is already drawn in metres, so
     zooming is arithmetic on four numbers and nothing has to be redrawn
     -- which is why this stays smooth on a phone with 1,000 paths on
     screen.

     Labels are the exception. Text in an SVG scales with the viewBox, so
     at 4x a room name would be four times the size of the screen. They
     are scaled inversely by --k so they hold a constant size however far
     in you are, which is what every real map does. */
  /* Named cam, not view: there is already a view(which) function for
     the tab switcher, and `var view` overwrote it -- the whole map
     died with "view is not a function". */
  var baseView = null, cam = null, mapSvg = null, geoExtent = null;
  var MIN_SPAN_M = 180;          // about one hotel across
  var padM = 30;

  function applyView() {
    if (!mapSvg || !cam) return;
    mapSvg.setAttribute("viewBox", cam.x.toFixed(1) + " " + cam.y.toFixed(1)
                        + " " + cam.w.toFixed(1) + " " + cam.h.toFixed(1));
    /* Labels were scaled by --k, the zoom ratio, which held them at a
       constant size but at the WRONG one: tuned against a 2,088px
       screenshot, they came out 6px on a 449px-wide desktop element and
       4.7px on a phone. Unreadable.

       --upx is user units per CSS pixel, measured from the element that
       is actually on screen. font-size: calc(13px * var(--upx)) is then
       exactly 13 CSS pixels at any zoom on any device, rather than
       whatever a ratio happens to produce. */
    var box = mapSvg.getBoundingClientRect();
    if (box.width && box.height) {
      // Match the camera to the element's shape, about its own centre, so
      // "meet" has nothing to letterbox.
      var want = box.height / box.width;
      if (Math.abs(cam.h / cam.w - want) > 0.001) {
        var midY = cam.y + cam.h / 2;
        cam.h = cam.w * want;
        cam.y = midY - cam.h / 2;
      }
      mapSvg.style.setProperty("--upx", (cam.w / box.width).toFixed(4));
    }
    mapSvg.style.setProperty("--k", (cam.w / baseView.w).toFixed(4));
    var fit = Math.abs(cam.w - baseView.w) < 1;
    var btn = $("#z-fit");
    if (btn) btn.disabled = fit;
  }

  /* Frame the whole campus inside a box shaped like the element, so the
     picture fills the space without distorting and without dead bands. */
  function refit(keepZoom) {
    if (!mapSvg || !geoExtent) return;
    var box = mapSvg.getBoundingClientRect();
    if (!box.width || !box.height) return;
    var aspect = box.height / box.width;
    var fw = geoExtent.w, fh = geoExtent.w * aspect;
    if (fh < geoExtent.h) { fh = geoExtent.h; fw = geoExtent.h / aspect; }
    var next = { x: geoExtent.x - (fw - geoExtent.w) / 2,
                 y: geoExtent.y - (fh - geoExtent.h) / 2, w: fw, h: fh };
    var zoomed = keepZoom && baseView && cam
                 && Math.abs(cam.w - baseView.w) > 1;
    var ratio = zoomed ? cam.w / baseView.w : 1;
    var midX = zoomed ? cam.x + cam.w / 2 : next.x + next.w / 2;
    var midY = zoomed ? cam.y + cam.h / 2 : next.y + next.h / 2;
    baseView = next;
    var w = next.w * ratio, h = next.h * ratio;
    cam = clampView({ x: midX - w / 2, y: midY - h / 2, w: w, h: h });
    applyView();
  }

  function clampView(v) {
    if (!baseView) return v;
    var maxW = baseView.w, maxH = baseView.h;
    if (v.w > maxW) { var f = maxW / v.w; v.w = maxW; v.h *= f; }
    if (v.w < MIN_SPAN_M) {
      var g = MIN_SPAN_M / v.w; v.w = MIN_SPAN_M; v.h *= g;
    }
    // Keep at least a corner of the map on screen rather than letting it
    // be dragged into empty space and lost.
    var slackX = v.w * 0.5, slackY = v.h * 0.5;
    v.x = Math.max(baseView.x - slackX,
                   Math.min(v.x, baseView.x + maxW - v.w + slackX));
    v.y = Math.max(baseView.y - slackY,
                   Math.min(v.y, baseView.y + maxH - v.h + slackY));
    return v;
  }

  function zoomAt(factor, clientX, clientY) {
    if (!mapSvg || !cam) return;
    var r = mapSvg.getBoundingClientRect();
    // Where the pointer is, in map coordinates -- so the thing under the
    // finger stays under the finger.
    var fx = (clientX - r.left) / r.width;
    var fy = (clientY - r.top) / r.height;
    var mx = cam.x + fx * cam.w, my = cam.y + fy * cam.h;
    var nw = cam.w / factor, nh = cam.h / factor;
    cam = clampView({ x: mx - fx * nw, y: my - fy * nh, w: nw, h: nh });
    applyView();
  }

  function zoomToVenue(name) {
    if (!baseView) return;
    var p = CFG.travel.points[name];
    if (!p || !mapProj) return;
    var span = 520;
    var cx = mapProj.x(p[1]), cy = mapProj.y(p[0]);
    var h = span * (baseView.h / baseView.w);
    cam = clampView({ x: cx - span / 2, y: cy - h / 2, w: span, h: h });
    applyView();
  }

  function wireMapGestures(svg) {
    var pointers = {}, lastMid = null, lastDist = 0, moved = false;

    svg.addEventListener("wheel", function (e) {
      e.preventDefault();
      zoomAt(e.deltaY < 0 ? 1.18 : 1 / 1.18, e.clientX, e.clientY);
    }, { passive: false });

    svg.addEventListener("pointerdown", function (e) {
      /* Capture is deliberately NOT taken here. Taking it on every press
         retargets the following click at the <svg>, so a tap on a venue
         pin never reached the pin's own handler -- the map panned fine
         and nothing was clickable. It is taken below, once a press has
         actually turned into a drag. */
      pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
      moved = false;
      lastMid = null; lastDist = 0;
    });

    svg.addEventListener("pointermove", function (e) {
      if (!pointers[e.pointerId]) return;
      /* Read where this pointer WAS before overwriting it. Updating first
         made prev and current the same point, so every drag computed a
         delta of zero and the map never moved. */
      var was = pointers[e.pointerId];
      pointers[e.pointerId] = { x: e.clientX, y: e.clientY };
      var ids = Object.keys(pointers);
      var r = svg.getBoundingClientRect();

      if (ids.length === 1) {
        var prev = was;
        var dx = (e.clientX - prev.x) * (cam.w / r.width);
        var dy = (e.clientY - prev.y) * (cam.h / r.height);
        if (Math.abs(e.clientX - prev.x) + Math.abs(e.clientY - prev.y) > 2) {
          if (!moved) {
            moved = true;
            // Now it is a drag: keep the pointer even if it leaves the svg.
            try { svg.setPointerCapture(e.pointerId); } catch (err) {}
          }
        }
        cam = clampView({ x: cam.x - dx, y: cam.y - dy,
                           w: cam.w, h: cam.h });
        applyView();
      } else if (ids.length >= 2) {
        var a = pointers[ids[0]], b2 = pointers[ids[1]];
        var dist = Math.hypot(a.x - b2.x, a.y - b2.y);
        var mid = { x: (a.x + b2.x) / 2, y: (a.y + b2.y) / 2 };
        if (lastDist) {
          zoomAt(dist / lastDist, mid.x, mid.y);
          moved = true;
        }
        lastDist = dist;
        lastMid = null;
      }
    });

    function release(e) {
      delete pointers[e.pointerId];
      try { svg.releasePointerCapture(e.pointerId); } catch (err) {}
      if (!Object.keys(pointers).length) { lastMid = null; lastDist = 0; }
    }
    svg.addEventListener("pointerup", release);
    svg.addEventListener("pointercancel", release);
    svg.addEventListener("pointerleave", release);

    // A drag must not also count as a tap on whatever was underneath.
    svg.addEventListener("click", function (e) {
      if (moved) { e.stopPropagation(); e.preventDefault(); moved = false; }
    }, true);
  }

  function wireMapButtons() {
    function mid() {
      var r = mapSvg.getBoundingClientRect();
      return [r.left + r.width / 2, r.top + r.height / 2];
    }
    $("#z-in").onclick = function () {
      var m = mid(); zoomAt(1.5, m[0], m[1]); };
    $("#z-out").onclick = function () {
      var m = mid(); zoomAt(1 / 1.5, m[0], m[1]); };
    $("#z-fit").onclick = function () {
      cam = { x: baseView.x, y: baseView.y, w: baseView.w, h: baseView.h };
      applyView();
    };
    var box = $("#mapwrap"), full = $("#z-full");
    full.onclick = function () {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else if (box.requestFullscreen) {
        box.requestFullscreen().catch(function () {});
      } else {
        // Safari on iOS has no element fullscreen; fall back to a class
        // that fills the viewport, which is the part people actually want.
        box.classList.toggle("faux-full");
        full.textContent = box.classList.contains("faux-full")
          ? "Close" : "Expand";
      }
    };
    document.addEventListener("fullscreenchange", function () {
      full.textContent = document.fullscreenElement ? "Close" : "Expand";
    });
  }

  /* The element's width is part of the type scale, so a resize or an
     orientation change has to recompute it. */
  window.addEventListener("resize", function () {
    if (mapSvg && cam) refit(true);
  });

  function currentHops() {
    var sel = $("#map-day");
    var day = sel ? sel.value : "";
    return day ? routeFor(day) : [];
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

  /* The route is drawn from YOUR PLAN, so the day list only holds days
     you have starred something on. With an empty plan that left an
     enabled dropdown offering exactly one entry -- "no day selected" --
     and no hint as to why. Reported as "so why it shows no days
     selected", which is the right question to ask of a control that
     appears to work and does nothing.

     A control with nothing to offer should say so and be unusable, not
     sit there looking operable. */
  function fillMapDays() {
    var sel = $("#map-day");
    if (!sel) return;
    var have = {};
    planRows().forEach(function (r) { if (r.w) have[r.d] = 1; });
    var days = CFG.days.filter(function (d) { return have[d]; });
    var keep = sel.value;
    sel.textContent = "";

    if (!days.length) {
      sel.appendChild(new Option(
        plan.length ? "— nothing scheduled in your plan yet —"
                    : "— star sessions first —", ""));
      sel.disabled = true;
      sel.onchange = null;
      setMapHint(plan.length
        ? "The sessions in your plan have no published times yet, so there "
          + "is no route to draw."
        : "Star a few sessions in Browse and their route across the Strip "
          + "appears here, with the tight hops flagged.");
      return;
    }

    sel.disabled = false;
    sel.appendChild(new Option("— no day selected —", ""));
    days.forEach(function (d) {
      sel.appendChild(new Option(dayLabel(d), d));
    });
    sel.value = have[keep] ? keep : "";
    sel.onchange = function () { renderMap(); dayPrompt(days.length); };
    dayPrompt(days.length);
  }

  /* Cleared once a day is chosen: a prompt telling you to do the thing
     you have just done is noise. It was not being cleared, because only
     fillMapDays set it and the dropdown's own change never re-ran it. */
  function dayPrompt(n) {
    var sel = $("#map-day");
    if (sel && sel.value) { setMapHint(""); return; }
    setMapHint(n === 1
      ? "Pick the day above to draw the route."
      : "Pick one of your " + n + " days above to draw the route.");
  }

  function setMapHint(text) {
    var el_ = $("#mapday-hint");
    if (!el_) return;
    el_.textContent = text || "";
    el_.hidden = !text;
  }

  /* A nudge the moment a day or a venue is chosen, because that is when
     somebody is deciding how much to take on. Asked for as "some sort of
     suggestions or tips as soon as you click on a specific day or
     filter". It is one line and it only appears when it has something to
     say -- an unconditional tip bar is just chrome. */
  /* "a and b and c and d" reads like a machine wrote it, because one did. */
  function andList(xs) {
    if (xs.length <= 1) return xs.join("");
    if (xs.length === 2) return xs[0] + " and " + xs[1];
    return xs.slice(0, -1).join(", ") + " and " + xs[xs.length - 1];
  }

  function browseTip(list) {
    var host = $("#browsetip");
    if (!host) return;
    if (!state.day && !state.venue) { host.hidden = true; return; }

    var bits = [];
    if (state.day) {
      bits.push("<b>" + list.length.toLocaleString() + "</b> session"
                + (list.length === 1 ? "" : "s") + " match on "
                + dayLabel(state.day)
                + (state.venue ? " at " + state.venue : ""));
      /* Deliberately no figure here. Working it out means running the
         planner from all five venues, and this fires on every keystroke
         and filter change. Better to say what is true and hand the
         arithmetic to the thing built for it. */
      bits.push("Only a fraction of those fit into one day once travel "
                + "between buildings and a break are honoured.");
    } else if (state.venue) {
      var far = [], here = state.venue;
      Object.keys(CFG.travel.matrix).forEach(function (v) {
        if (v !== here && needFor(here, v) >= 40) far.push(v);
      });
      bits.push("<b>" + list.length.toLocaleString() + "</b> at " + here);
      if (far.length)
        bits.push("From here, " + andList(far)
                  + " " + (far.length === 1 ? "is" : "are")
                  + " 40 minutes or more away — worth not mixing into "
                  + "the same morning.");
    }
    host.innerHTML = bits.join(" ") + " ";
    var a = el("button", "tiplink", "Plan a day from here →");
    a.addEventListener("click", function () {
      if (state.day) planner.day = state.day;
      if (state.venue) planner.at = state.venue;
      if (state.lane && state.lane !== "all") planner.lane = state.lane;
      if (state.service !== "") planner.service = state.service;
      save("ri2026.planner", planner);
      view("plan2");
      fillPlannerControls();
      var d = $("#pl-day"), at = $("#pl-at"), l = $("#pl-lane"),
          sv2 = $("#pl-service");
      if (d) d.value = planner.day;
      if (at) at.value = planner.at;
      if (l) l.value = planner.lane || "all";
      if (sv2) sv2.value = planner.service || "";
      if (l) l.disabled = !!planner.service;
      renderPlanner();
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    host.appendChild(a);
    host.hidden = false;
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
    syncStars(); renderPlan(); showCta();
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
      var c = card(r.s, r.w);
      var vr = verdictRow(r.s.c);
      if (vr) c.appendChild(vr);
      c.appendChild(noteBox(r.s.c));
      host.appendChild(c);
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


  /* ---- taking it with you --------------------------------------------
     Two exports, because a plan that only exists on this page is a plan
     nobody looks at on the day.

     TIMEZONE. Every event is emitted in UTC, which needs no VTIMEZONE
     block and cannot be misread by a client. The conversion is exact
     rather than assumed: all 1,555 scheduled slots in the catalog were
     checked against their own utcEndTime, and every one came back at
     UTC = local + 8h. That is Pacific Standard Time, and re:Invent 2026
     sits wholly after the November DST change, so there is no transition
     inside the event for a fixed offset to get wrong. */
  var VEGAS_OFFSET_H = 8;

  function icsStamp(day, minutes) {
    var d = new Date(day + "T00:00:00Z");
    d.setUTCMinutes(d.getUTCMinutes() + minutes + VEGAS_OFFSET_H * 60);
    return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  }

  /* iCalendar escaping, then folding at 75 octets with CRLF + space.
     Clients genuinely do break on an unfolded 300-character DESCRIPTION,
     and the failure looks like a corrupt file rather than a long line. */
  function icsText(v) {
    return String(v || "").replace(/\\/g, "\\\\").replace(/;/g, "\\;")
      .replace(/,/g, "\\,").replace(/\r?\n/g, "\\n");
  }

  /* RFC 5545 folds at 75 OCTETS, not characters, and a continuation line
     spends one of them on its leading space. Counting characters passed a
     em dash and a middot straight through: 15 lines went out over the
     limit while still looking 74 long. Split on a code point boundary too,
     or a folded line can end mid-character and the client sees mojibake. */
  function icsFold(line) {
    var enc = new TextEncoder();
    if (enc.encode(line).length <= 75) return line;
    var out = [], cur = "", curBytes = 0;
    for (var i = 0; i < line.length; ) {
      var cp = String.fromCodePoint(line.codePointAt(i));
      i += cp.length;
      var b = enc.encode(cp).length;
      var cap = out.length ? 74 : 75;      // continuations carry a space
      if (curBytes + b > cap) {
        out.push(cur);
        cur = ""; curBytes = 0;
      }
      cur += cp; curBytes += b;
    }
    if (cur) out.push(cur);
    return out.map(function (seg, i) {
      return (i ? " " : "") + seg;
    }).join("\r\n");
  }

  function buildICS() {
    var now = new Date().toISOString().replace(/[-:]/g, "")
                .replace(/\.\d{3}/, "");
    var lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
                 "PRODID:-//jayanthkatta.com//re:Invent 2026 planner//EN",
                 "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
                 "X-WR-CALNAME:AWS re:Invent 2026"];
    var count = 0;
    planRows().forEach(function (r) {
      if (r.gone || !r.w) return;
      var s = r.s, w = r.w;
      // The eleven sessions AWS publishes with no duration get an hour,
      // and the description says so rather than pretending otherwise.
      var unknownEnd = (w.e == null);
      var end = unknownEnd ? w.b + 60 : w.e;
      var desc = [];
      if (unknownEnd)
        desc.push("AWS has not published a length for this session; one "
                + "hour is assumed here.");
      if (speakerNames(s).length)
        desc.push("Speakers: " + speakerNames(s).join("; "));
      if (svcNames(s).length)
        desc.push("Services: " + svcNames(s).join(", "));
      if (w.cap) desc.push("Room capacity: " + w.cap);
      desc.push("Confirm in the official catalog: "
              + CATALOG_URL + "?search=" + encodeURIComponent(s.c));
      if (s.a) desc.push("", s.a);

      lines.push("BEGIN:VEVENT");
      lines.push(icsFold("UID:" + s.c + "-" + w.d
                         + "@reinvent2026.jayanthkatta.com"));
      lines.push("DTSTAMP:" + now);
      lines.push("DTSTART:" + icsStamp(w.d, w.b));
      lines.push("DTEND:" + icsStamp(w.d, end));
      lines.push(icsFold("SUMMARY:" + icsText(s.c + " — " + s.t)));
      lines.push(icsFold("LOCATION:" + icsText(roomName(w))));
      lines.push(icsFold("DESCRIPTION:" + icsText(desc.join("\n"))));
      lines.push(icsFold("URL:" + CATALOG_URL + "?search="
                         + encodeURIComponent(s.c)));
      lines.push("END:VEVENT");
      count += 1;
    });
    lines.push("END:VCALENDAR");
    return { text: lines.join("\r\n"), count: count };
  }

  function download(name, text, mime) {
    var blob = new Blob([text], { type: mime + ";charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url; a.download = name;
    document.body.appendChild(a); a.click();
    document.body.removeChild(a);
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
  }

  /* ---- notes, and the trip report they become ------------------------
     You come back from five days having sat in thirty sessions with
     nothing written down. A note per session, kept in this browser, and
     an export that is already the shape of something you would send to
     the team. */
  var NOTE_KEY = "ri2026.notes";
  var notes = load(NOTE_KEY, {}) || {};

  function noteFor(code) { return notes[code] || ""; }

  function setNote(code, text) {
    if (text) notes[code] = text; else delete notes[code];
    save(NOTE_KEY, notes);
  }

  function noteBox(code) {
    var wrap = el("div", "notewrap");
    var ta = document.createElement("textarea");
    ta.className = "note";
    ta.rows = 2;
    ta.placeholder = "What did you take away? (kept on this device)";
    ta.value = noteFor(code);
    var flag = el("span", "saved", "");
    var t = null;
    ta.addEventListener("input", function () {
      setNote(code, ta.value);
      // Writing into a box that gives no feedback feels like writing into
      // nothing, which is why people retype notes elsewhere.
      var now = new Date();
      flag.textContent = storageOK
        ? "saved " + hhmm(now.getHours() * 60 + now.getMinutes())
        : "NOT saved";
      flag.classList.toggle("warn", !storageOK);
      flag.classList.add("on");
      clearTimeout(t);
      // Fades to a quiet standing label rather than vanishing, so the
      // answer to "did that save?" is on screen when you look for it.
      t = setTimeout(function () { flag.classList.add("dim"); }, 2000);
    });
    wrap.appendChild(ta);
    wrap.appendChild(flag);
    return wrap;
  }

  function buildMarkdown() {
    var out = ["# AWS re:Invent 2026 — session notes", ""];
    var seen = 0, group = null;
    planRows().forEach(function (r) {
      if (r.gone) {
        out.push("- ~~" + r.gone + "~~ (no longer in the catalog)");
        return;
      }
      if (r.d !== group) {
        group = r.d;
        out.push("", "## " + (r.w ? dayLabel(r.d) : "Not yet scheduled"), "");
      }
      var s = r.s, w = r.w;
      var when = w ? hhmm(w.b) + (w.e == null ? "" : "–" + hhmm(w.e)) : "";
      out.push("### " + s.c + " — " + s.t);
      var meta = [];
      if (when) meta.push(when);
      if (w) meta.push(roomName(w));
      if (typeName(s)) meta.push(typeName(s));
      if (levelName(s)) meta.push(levelName(s));
      out.push("*" + meta.join(" · ") + "*");
      if (speakerNames(s).length)
        out.push("", "Speakers: " + speakerNames(s).join("; "));
      var note = noteFor(s.c);
      out.push("", note ? note : "_No notes._");
      out.push("", "[Official catalog entry](" + CATALOG_URL + "?search="
               + encodeURIComponent(s.c) + ")", "");
      seen += 1;
    });
    out.push("", "---", "",
             "Generated from jayanthkatta.com/reinvent-2026/ · "
             + seen + " session(s) · catalog captured "
             + (DATA.captured || "unknown"));
    return out.join("\n");
  }


  /* ---- verifying the plan against AWS --------------------------------
     The load-time live check compares session COUNTS, which catches an
     addition or a cancellation and misses a move. Six sessions were
     re-roomed in two hours on 2026-09-22 without the count changing at
     all, so the count check would have said "same" while a plan quietly
     pointed at the wrong building.

     This closes that, on the only sessions it matters for: the ones you
     starred. Measured first -- the API honours search=<code> and returns
     exactly one row -- so a plan costs one small request per session
     rather than a full catalog pull. Paced, because the catalog throttles
     a burst; that was found the hard way when a burst returned 100
     sessions and the page displayed them as live data. */
  var verified = {};      // code -> {state, was, now}

  function slotSig(d, b, e, room) {
    return [d, b, e == null ? "?" : e, room].join("|");
  }

  function verifyPlan() {
    var btn = $("#verify");
    var codes = plan.slice();
    if (!codes.length || !DATA.api) return;
    var done = 0;

    function setLabel(t) { if (btn) btn.textContent = t; }
    if (btn) btn.disabled = true;

    function step(i) {
      if (i >= codes.length) {
        setLabel("Re-check against AWS");
        if (btn) btn.disabled = false;
        renderPlan();
        return;
      }
      var code = codes[i];
      setLabel("Checking " + (i + 1) + " of " + codes.length + "…");
      liveFetch({ search: code }).then(function (d) {
        var items = d.items && d.items.length ? d.items
                  : ((d.sectionList || [{}])[0].items || []);
        var hit = null;
        items.forEach(function (it) { if (it.code === code) hit = it; });
        var mine = null;
        DATA.sessions.forEach(function (x) { if (x.c === code) mine = x; });

        if (!hit) {
          verified[code] = { state: "gone" };
        } else {
          var t = (hit.times || [])[0];
          if (!t || t.startTimeMin == null) {
            verified[code] = { state: "unscheduled" };
          } else {
            var liveEnd = (t.endTimeMin != null
                           && t.endTimeMin > t.startTimeMin)
                        ? (t.endTimeMin | 0) : null;
            var liveSig = slotSig(t.date, t.startTimeMin | 0, liveEnd,
                                  t.room || "");
            var w = mine && mine.when.length ? mine.when[0] : null;
            var mineSig = w ? slotSig(w.d, w.b, w.e, roomName(w)) : "none";
            verified[code] = (liveSig === mineSig)
              ? { state: "ok" }
              : { state: "changed",
                  now: { d: t.date, b: t.startTimeMin | 0, e: liveEnd,
                         room: t.room || "" } };
          }
        }
        done += 1;
        setTimeout(function () { step(i + 1); }, 220);
      }).catch(function () {
        verified[code] = { state: "unchecked" };
        setTimeout(function () { step(i + 1); }, 220);
      });
    }
    step(0);
  }

  function verdictRow(code) {
    var v = verified[code];
    if (!v) return null;
    var row = el("div", "vrow");
    if (v.state === "ok") {
      row.className = "vrow ok";
      row.textContent = "✓ Confirmed against AWS just now.";
    } else if (v.state === "changed") {
      row.className = "vrow bad";
      row.textContent = "⚠ AWS now has this at "
        + hhmm(v.now.b) + (v.now.e == null ? "" : "–" + hhmm(v.now.e))
        + " on " + v.now.d + ", " + v.now.room
        + ". The card above is the stored copy.";
    } else if (v.state === "gone") {
      row.className = "vrow bad";
      row.textContent = "⚠ AWS no longer returns this session code.";
    } else if (v.state === "unscheduled") {
      row.className = "vrow warn";
      row.textContent = "AWS currently lists this with no time.";
    } else {
      row.className = "vrow";
      row.textContent = "Could not reach AWS to check this one.";
    }
    return row;
  }

  /* ---- what is on now, near me ---------------------------------------
     The catalog is least usable at exactly the moment you need it most:
     237 sessions start at 13:00. This answers the standing-in-a-corridor
     question -- what starts soon, here, and what can I still reach.

     Outside the event it has no "now" worth showing, so it says so and
     lets you preview a day and time rather than rendering an empty panel
     and looking broken. */
  var NOW_KEY = "ri2026.where";
  var nowState = load(NOW_KEY, null) || { at: "", day: "", time: 540 };
  var WINDOW_MIN = 90;

  function eventNow() {
    var d = new Date();
    var iso = d.getFullYear() + "-"
            + String(d.getMonth() + 1).padStart(2, "0") + "-"
            + String(d.getDate()).padStart(2, "0");
    if (CFG.days.indexOf(iso) === -1) return null;
    return { day: iso, min: d.getHours() * 60 + d.getMinutes() };
  }

  /* "What can I get to" is a question you ask standing up, holding a
     phone, with somewhere to be. It was answering with 62 cards and
     nineteen screens. The reachable ones are the answer; the rest are
     reference, so they fold away.

     Declared out here, not inside renderNow: it was a `var` in the
     function, so "show the other 20" set it and then the re-render
     immediately reset it to 10 and nothing happened. */
  var NOW_SHOW = 10;

  function renderNow() {
    var host = $("#nowbody");
    if (!host) return;
    host.textContent = "";

    var real = eventNow();
    var live_ = real || { day: nowState.day || CFG.days[0],
                          min: nowState.time };
    var note = $("#nownote");
    if (note) {
      /* Three states, not two. "has not started" was being shown in
         December as well, which is a small lie on a page whose whole
         claim is that it does not tell them. */
      var last = CFG.days[CFG.days.length - 1];
      var today = new Date();
      var iso = today.getFullYear() + "-"
              + String(today.getMonth() + 1).padStart(2, "0") + "-"
              + String(today.getDate()).padStart(2, "0");
      note.textContent = real
        ? "Live: it is " + hhmm(live_.min) + " on " + dayLabel(live_.day) + "."
        : (iso > last
           ? "re:Invent 2026 has finished. You can still look back over any "
             + "day — pick one below."
           : "re:Invent has not started, so this is a preview — pick a "
             + "day and time. During the event it uses the real clock.");
      note.className = real ? "nownote live" : "nownote";
    }
    var picker = $("#nowpick");
    if (picker) picker.hidden = !!real;

    var here = nowState.at;
    var rows = [];
    DATA.sessions.forEach(function (sn) {
      sn.when.forEach(function (w) {
        if (w.d !== live_.day) return;
        var mins = w.b - live_.min;
        if (mins < -5 || mins > WINDOW_MIN) return;
        var v = venueName(w);
        var need = here ? needFor(here, v) : 0;
        rows.push({ s: sn, w: w, in: mins, venue: v,
                    reach: !here || mins >= need, need: need });
      });
    });
    rows.sort(function (a, b) {
      if (a.reach !== b.reach) return a.reach ? -1 : 1;
      return a.in - b.in;
    });

    var can = rows.filter(function (r) { return r.reach; });
    var cant = rows.filter(function (r) { return !r.reach; });

    var head = el("p", "count");
    head.innerHTML = "<b>" + can.length + "</b> session"
      + (can.length === 1 ? "" : "s") + " you can still get to in the next "
      + WINDOW_MIN + " minutes"
      + (here ? ", starting from " + here : "")
      + (cant.length ? "  ·  " + cant.length + " you could not reach in time"
                     : "");
    host.appendChild(head);

    if (!rows.length) {
      host.appendChild(el("p", "empty",
        "Nothing starts in the next " + WINDOW_MIN + " minutes on this day."));
      return;
    }

    function block(title, list, cls, fold) {
      if (!list.length) return;
      var sec = el("section", "daygroup");
      if (fold) {
        var d = document.createElement("details");
        d.className = "nowfold";
        var sm = document.createElement("summary");
        sm.textContent = title + " (" + list.length + ")";
        d.appendChild(sm);
        sec.appendChild(d);
        list.slice(0, 25).forEach(function (r) {
          var c = card(r.s, r.w);
          if (cls) c.classList.add(cls);
          d.appendChild(c);
        });
        host.appendChild(sec);
        return;
      }
      sec.appendChild(el("h2", "dayhead", title));
      var head = list.slice(0, NOW_SHOW);
      head.forEach(function (r) {
        var c = card(r.s, r.w);
        if (cls) c.classList.add(cls);
        var when = el("div", "where");
        when.textContent = (r.in <= 0 ? "started " + (-r.in) + " min ago"
                                      : "starts in " + r.in + " min")
          + (here && r.venue !== here
             ? "  ·  " + km(metresBetween(here, r.venue)) + " away, allow "
               + r.need + " min"
             : here ? "  ·  you are here" : "");
        c.insertBefore(when, c.querySelector(".more") || null);
        sec.appendChild(c);
      });
      if (list.length > head.length) {
        var more = el("button", "ghost",
          "Show the other " + (list.length - head.length));
        more.addEventListener("click", function () {
          NOW_SHOW = list.length;
          renderNow();
        });
        var pager = el("div", "pager");
        pager.appendChild(more);
        sec.appendChild(pager);
      }
      host.appendChild(sec);
    }
    block("You can get to these", can, null, false);
    block("Too far to make it", cant, "unreachable", true);
  }

  function fillNowControls() {
    var at = $("#now-at"), day = $("#now-day"), time = $("#now-time");
    if (!at) return;
    if (!at.options.length) {
      at.appendChild(new Option("— pick where you are —", ""));
      Object.keys(CFG.travel.matrix).sort().forEach(function (v) {
        at.appendChild(new Option(v, v));
      });
      CFG.days.forEach(function (d) {
        day.appendChild(new Option(dayLabel(d), d));
      });
    }
    at.value = nowState.at || "";
    day.value = nowState.day || CFG.days[0];
    time.value = hhmm(nowState.time || 540);
    at.onchange = function () {
      nowState.at = at.value; NOW_SHOW = 10;
      save(NOW_KEY, nowState); renderNow();
    };
    day.onchange = function () {
      nowState.day = day.value; NOW_SHOW = 10;
      save(NOW_KEY, nowState); renderNow();
    };
    time.onchange = function () {
      var p = /^(\d{1,2}):(\d{2})$/.exec(time.value);
      if (p) {
        nowState.time = (+p[1]) * 60 + (+p[2]);
        save(NOW_KEY, nowState); renderNow();
      }
    };
  }


  /* ---- what AWS just shipped, and who is covering it -------------------
     re:Invent week is when AWS ships everything, and the question on the
     Tuesday is not "what sessions exist" but "they announced that at the
     keynote -- is anyone covering it?". The announcement store already
     exists on this site and is refreshed daily, so this is a join, not a
     new pipeline.

     The join is by SERVICE, which is honest but coarse: it says "this
     announcement and these sessions are about the same service", not
     "this session covers this announcement". The wording says so, because
     a session scheduled in September cannot be about a launch made in
     December -- and during the event, that is exactly the overlap worth
     looking at anyway. */
  var NEWS_PAGE = 20, newsShown = NEWS_PAGE;

  function renderNews() {
    var host = $("#newsbody");
    if (!host) return;
    host.textContent = "";
    var items = CFG.news || [];
    if (!items.length) {
      host.appendChild(el("p", "empty",
        "No recent AWS announcements line up with a service in this "
        + "catalog."));
      return;
    }

    var byService = {};
    DATA.sessions.forEach(function (sn) {
      sn.sv.forEach(function (i) {
        (byService[i] = byService[i] || []).push(sn);
      });
    });

    var head = el("p", "count");
    head.innerHTML = "<b>" + items.length + "</b> AWS announcement"
      + (items.length === 1 ? "" : "s") + " from the last few weeks that "
      + "name a service this catalog also covers";
    host.appendChild(head);

    /* 120 announcements is thirty phone screens. Twenty at a time, with
       the same button Browse uses. */
    var slice = items.slice(0, newsShown);
    slice.forEach(function (a) {
      var box = el("article", "newsitem");
      var top = el("div", "top");
      top.appendChild(el("span", "code", a.d));
      a.sv.forEach(function (i) {
        top.appendChild(el("span", "tag", DATA.facets.Services[i]));
      });
      box.appendChild(top);

      var t = el("p", "newstitle", a.t);
      box.appendChild(t);

      var hits = [];
      a.sv.forEach(function (i) {
        (byService[i] || []).forEach(function (sn) {
          if (hits.indexOf(sn) === -1) hits.push(sn);
        });
      });
      var line = el("div", "where");
      /* A service with hundreds of sessions cannot be pointed at. Bedrock
         has 322, so "322 sessions on the same service" followed by eight
         arbitrary codes is noise wearing the shape of a recommendation.
         Say the service is too broad and send them to the filter instead. */
      var TOO_BROAD = 40;
      if (!hits.length) {
        line.textContent = "No sessions on that service.";
      } else if (hits.length > TOO_BROAD) {
        line.textContent = hits.length + " sessions carry that service — "
          + "too many to single any out. ";
        var jump = el("a", "hoplink", "Filter to it in Browse →");
        jump.href = "#";
        jump.addEventListener("click", function (ev) {
          ev.preventDefault();
          state.service = String(a.sv[0]);
          state.lane = "all"; state.q = ""; shown = PAGE_SIZE;
          $("#q").value = "";
          buildFilters(); view("browse"); render();
          window.scrollTo({ top: 0, behavior: "smooth" });
        });
        line.appendChild(jump);
      } else {
        line.textContent = hits.length + " session"
          + (hits.length === 1 ? "" : "s") + " on the same service: ";
        hits.slice(0, 8).forEach(function (sn, i) {
          if (i) line.appendChild(document.createTextNode(", "));
          var lk = el("a", "code", sn.c);
          lk.href = "#";
          lk.title = sn.t;
          lk.addEventListener("click", function (ev) {
            ev.preventDefault();
            state.q = sn.c; state.lane = "all"; shown = PAGE_SIZE;
            $("#q").value = sn.c;
            view("browse"); render();
            window.scrollTo({ top: 0, behavior: "smooth" });
          });
          line.appendChild(lk);
        });
        if (hits.length > 8)
          line.appendChild(document.createTextNode(
            " and " + (hits.length - 8) + " more"));
      }
      box.appendChild(line);

      if (a.u) {
        var src = el("a", "hoplink", "the announcement ↗");
        src.href = a.u; src.target = "_blank"; src.rel = "noopener";
        box.appendChild(src);
      }
      host.appendChild(box);
    });

    if (items.length > slice.length) {
      var pager = el("div", "pager");
      var more = el("button", "ghost", "Show "
        + Math.min(NEWS_PAGE, items.length - slice.length) + " more of "
        + (items.length - slice.length));
      more.addEventListener("click", function () {
        newsShown += NEWS_PAGE;
        renderNews();
      });
      pager.appendChild(more);
      host.appendChild(pager);
    }
  }


  /* ---- planning a day -------------------------------------------------
     Asked for: "let's say I'm at Caesars Palace ... what sessions can I
     book so that I can reach each one in a timely fashion, and how many
     sessions can I book in a day so it's productive and not overwhelming
     ... how can I plan my day, 8am to end of day."

     WHY THIS IS NOT "AS MANY AS POSSIBLE". The first version of this
     maximised session count and produced a genuinely awful day: sixteen
     sessions on the Wednesday, fourteen of them 20-minute sponsored
     lightning talks back to back in one theatre with exactly zero slack.
     Feasible on paper, useless to a person. "Productive and not
     overwhelmed" is a different objective from "maximal".

     So it maximises VALUE under two constraints that make a day humane:

       a real buffer beyond the travel estimate between consecutive
       sessions, so a delayed finish or a queue does not cascade; and

       one proper break between 11:00 and 14:30, because a day with no
       gap to eat in is a plan nobody follows past Tuesday.

     Measured across the catalog, that lands at five to seven substantial
     sessions a day wherever you start -- which is the honest answer to
     "how many can I book", and a long way from sixteen. */
  var SESSION_VALUE = {
    "Workshop": 5, "Builders' session": 5, "Bootcamp": 5, "Lab": 5,
    "Chalk talk": 4, "Code talk": 4, "Breakout session": 4,
    "Exam prep": 3, "Gamified learning": 2, "Lightning talk": 1
  };
  var LUNCH_MIN = 45, LUNCH_FROM = 11 * 60, LUNCH_TO = 14 * 60 + 30;
  var PACE = { relaxed: 25, standard: 15, packed: 5 };

  var planner = load("ri2026.planner", null) || {
    day: "", at: "", lane: "", service: "", pace: "standard",
    sponsored: false };
  if (planner.service === undefined) planner.service = "";

  /* A chosen service is a strong PREFERENCE, never a hard filter, and
     that is a measurement rather than a nicety: 102 of the 169 services
     have five or fewer sessions in the entire week. AWS Transit Gateway
     has four; AWS Cloud WAN has five. Filtering hard on one of those
     returns an empty day, which looks like the page is broken rather than
     like the catalog being thin.

     So a matching session is worth far more and a non-matching one still
     counts for something -- the day fills with the best of what is left,
     and the tips say plainly how much of it actually covers the service
     you asked for. */
  function sessionValue(sn, ty) {
    var v = SESSION_VALUE[ty];
    if (v == null) v = 2;
    if (/-S$/.test(sn.c)) v *= 0.45;          // sponsored
    if (planner.service !== "" && planner.service != null) {
      var want1 = +planner.service;
      v *= (sn.sv.indexOf(want1) !== -1) ? 3.0 : 0.22;
    } else if (planner.lane && planner.lane !== "all") {
      var want = laneServices(planner.lane) || [];
      var hit = sn.sv.some(function (i) { return want.indexOf(i) !== -1; });
      v *= hit ? 1.8 : 0.35;
    }
    return v;
  }

  function serviceName(i) { return DATA.facets.Services[+i]; }

  /* Every slot on this day carrying the chosen service, whether or not it
     made the plan -- so the advice can say "there are only two". */
  function serviceSlotsOn(day, idx) {
    var c = 0;
    DATA.sessions.forEach(function (sn) {
      if (sn.sv.indexOf(+idx) === -1) return;
      sn.when.forEach(function (w) {
        if (w.d === day && w.e != null) c += 1;
      });
    });
    return c;
  }

  function daySlots(day) {
    var out = [];
    DATA.sessions.forEach(function (sn) {
      var ty = typeName(sn);
      if (!planner.sponsored && /-S$/.test(sn.c)) return;
      sn.when.forEach(function (w) {
        if (w.d !== day || w.e == null) return;
        out.push({ s: sn, w: w, b: w.b, e: w.e, venue: venueName(w),
                   ty: ty, val: sessionValue(sn, ty) });
      });
    });
    return out.sort(function (a, b) { return a.e - b.e; });
  }

  /* Weighted interval scheduling, with travel as the compatibility test
     and a second dimension on the state for "has had a break yet". */
  function buildDay(day, startVenue) {
    var items = daySlots(day);
    var buf = PACE[planner.pace] || 15;
    var dayFrom = 8 * 60;
    var n = items.length;
    var best = [], prev = [];
    for (var i = 0; i < n; i++) { best.push([-1, -1]); prev.push([null, null]); }

    for (var i2 = 0; i2 < n; i2++) {
      var it = items[i2];
      var reach = startVenue ? needFor(startVenue, it.venue) : 0;
      if (it.b >= dayFrom + reach) best[i2][0] = it.val;
      for (var j = 0; j < i2; j++) {
        var pj = items[j];
        var gap = it.b - pj.e;
        if (gap < needFor(pj.venue, it.venue) + buf) continue;
        var ate = (gap >= LUNCH_MIN && pj.e >= LUNCH_FROM
                   && it.b <= LUNCH_TO);
        for (var had = 0; had < 2; had++) {
          if (best[j][had] < 0) continue;
          var nh = (had || ate) ? 1 : 0;
          var cand = best[j][had] + it.val;
          if (cand > best[i2][nh]) {
            best[i2][nh] = cand;
            prev[i2][nh] = [j, had];
          }
        }
      }
    }

    function collect(state) {
      var top = -1, ti = -1;
      for (var i3 = 0; i3 < n; i3++)
        if (best[i3][state] > top) { top = best[i3][state]; ti = i3; }
      if (ti < 0) return null;
      var out = [], cur = ti, had = state;
      while (cur !== null && cur !== undefined) {
        out.push(items[cur]);
        var step = prev[cur][had];
        if (!step) break;
        cur = step[0]; had = step[1];
      }
      return out.reverse();
    }
    // A chain that includes a break, or the best one there is.
    return collect(1) || collect(0) || [];
  }

  /* "five to seven" was a real measurement -- I ran this across all five
     days and all five venues -- but it was then frozen into prose, which
     is the exact failure this page has already had twice (two distances
     in the travel paragraph, and a commit message that said "first
     capture" forever). The catalog is about 72% published; when the rest
     arrives the number can move. So it is computed, from the same
     algorithm, across every possible starting point on the day in
     question. Cached, because it is five dynamic programs. */
  var rangeCache = {};

  function feasibleRange(day) {
    var key = [day, planner.pace, planner.lane, planner.service,
               planner.sponsored ? 1 : 0].join("|");
    if (rangeCache[key]) return rangeCache[key];
    var lo = null, hi = null;
    Object.keys(CFG.travel.matrix).forEach(function (v) {
      var n2 = buildDay(day, v).length;
      if (lo === null || n2 < lo) lo = n2;
      if (hi === null || n2 > hi) hi = n2;
    });
    rangeCache[key] = { lo: lo || 0, hi: hi || 0 };
    return rangeCache[key];
  }

  var WORDS = ["zero", "one", "two", "three", "four", "five", "six",
               "seven", "eight", "nine", "ten", "eleven", "twelve"];

  function spell(n2) {
    return (n2 >= 0 && n2 < WORDS.length) ? WORDS[n2] : String(n2);
  }

  function rangeWords(day) {
    var r = feasibleRange(day);
    return r.lo === r.hi ? spell(r.lo)
                         : spell(r.lo) + " to " + spell(r.hi);
  }

  function advise(day, startVenue, chain) {
    var tips = [];
    if (!chain.length) {
      tips.push({ k: "warn", t: "Nothing fits from here",
        d: "No session on this day is reachable from " + startVenue
           + " after 08:00 with the buffer you have set. Try a looser "
           + "pace, or a different starting point." });
      return tips;
    }

    var first = chain[0], last = chain[chain.length - 1];
    tips.push({ k: "ok", t: "Why this many, and not more",
      /* Friday finishes at lunchtime -- calling three sessions ending at
         12:30 "a full day" is a small lie, and the page has spent enough
         effort not telling those. */
      d: ((last.e - first.b) >= 5 * 60
          ? "That is a full day. " : "That is what this day holds. ")
       + "On this day, depending where you start, "
       + rangeWords(day) + " is what actually fits once travel between "
       + "buildings and a break in the middle are honoured. Packing in "
       + "more means 20-minute talks in one room with no gap at all, "
       + "which is not a day anybody finishes." });

    // how much of the day is actually the thing you asked for
    if (planner.service !== "" && planner.service != null) {
      var svcIdx = +planner.service;
      var nm = serviceName(svcIdx);
      var got = chain.filter(function (x) {
        return x.s.sv.indexOf(svcIdx) !== -1; }).length;
      var avail = serviceSlotsOn(day, svcIdx);
      var elsewhere = CFG.days.map(function (dd) {
        return { d: dd, n: serviceSlotsOn(dd, svcIdx) };
      }).filter(function (r) { return r.n > 0 && r.d !== day; })
        .sort(function (a, b) { return b.n - a.n; });
      var alt = elsewhere.length
        ? " It runs on " + andList(elsewhere.map(function (r) {
            return dayLabel(r.d).replace(/,.*/, "") + " (" + r.n + ")"; }))
          + "."
        : " It has none scheduled on any day yet — the catalog is "
          + "still about 72% published.";

      if (avail === 0) {
        tips.push({ k: "warn", t: "No " + nm + " sessions on this day",
          d: "The catalog has none scheduled for " + dayLabel(day) + "."
             + alt + " Everything below is the best day available ignoring "
             + "that preference, and each card says so." });
      } else if (got === avail) {
        tips.push({ k: "ok",
          t: avail === 1
             ? "The one " + nm + " session on this day is in your plan"
             : "All " + avail + " " + nm + " sessions on this day are in "
               + "your plan",
          d: "There are no others to miss." + alt });
      } else {
        tips.push({ k: got ? "ok" : "warn",
          /* "is a AWS Transit Gateway session" -- the a/an rule needs the
             next word, and service names start with anything. Reworded so
             no article is needed at all. */
          t: got + " of these " + (got === 1 ? "covers " : "cover ") + nm,
          d: "The day has " + avail + " in total." + alt + " "
             + (avail - got === 0 ? "" : (avail - got) + " of them could "
                + "not be reached in time or clashed with something "
                + "better. ")
             + (chain.length - got > 0
                ? "The other " + (chain.length - got) + " "
                  + (chain.length - got === 1 ? "slot is" : "slots are")
                  + " filled with the strongest sessions that fit around "
                  + "them, rather than leaving you with gaps."
                : "") });
      }
    }

    // where you spend the day
    var byVenue = {};
    chain.forEach(function (x) {
      byVenue[x.venue] = (byVenue[x.venue] || 0) + 1; });
    var venues = Object.keys(byVenue);
    var moves = 0;
    for (var i = 1; i < chain.length; i++)
      if (chain[i].venue !== chain[i - 1].venue) moves += 1;
    /* The strip above already gives the number. This says the thing the
       number cannot: which buildings, in what order. */
    tips.push(moves === 0
      ? { k: "ok", t: "Everything is in one building",
          d: "You stay at " + venues[0] + " all day, which is the least "
             + "fragile shape a day can have." }
      : { k: "info", t: "Your route: " + venues.join(" → "),
          d: "Each hop below shows the gap you have and what this page "
             + "estimates you need to cover it." });

    // the best base, computed rather than assumed
    var bestBase = null;
    Object.keys(CFG.travel.matrix).forEach(function (v) {
      var only = daySlots(day).filter(function (x) { return x.venue === v; });
      var cnt = only.length ? buildDayFrom(only, v).length : 0;
      if (!bestBase || cnt > bestBase.n) bestBase = { v: v, n: cnt };
    });
    if (bestBase && bestBase.n) {
      tips.push({ k: "info", t: "Best single base: " + bestBase.v,
        d: "Without leaving " + bestBase.v + " you could still do "
           + bestBase.n + " session" + (bestBase.n === 1 ? "" : "s")
           + " on this day. If you want a low-friction day, start there." });
    }

    // the tightest hop in the plan
    var worst = null;
    for (var k = 1; k < chain.length; k++) {
      var g = chain[k].b - chain[k - 1].e;
      var nd = needFor(chain[k - 1].venue, chain[k].venue);
      if (!worst || g - nd < worst.slack)
        worst = { slack: g - nd, from: chain[k - 1], to: chain[k],
                  gap: g, need: nd };
    }
    if (worst && worst.from.venue !== worst.to.venue) {
      tips.push({ k: worst.slack < 10 ? "warn" : "info",
        t: "Tightest hop: " + worst.slack + " min to spare",
        d: worst.from.s.c + " ends " + hhmm(worst.from.e) + " at "
           + worst.from.venue + "; " + worst.to.s.c + " starts "
           + hhmm(worst.to.b) + " at " + worst.to.venue + ". "
           + worst.gap + " minutes for a "
           + km(metresBetween(worst.from.venue, worst.to.venue))
           + " hop this page costs at " + worst.need + "." });
    }

    // the break
    var brk = null;
    for (var m = 1; m < chain.length; m++) {
      var gp = chain[m].b - chain[m - 1].e;
      if (gp >= LUNCH_MIN && chain[m - 1].e >= LUNCH_FROM
          && chain[m].b <= LUNCH_TO) {
        brk = { from: chain[m - 1].e, to: chain[m].b, len: gp };
        break;
      }
    }
    /* The strip states the break when there is one. Only its ABSENCE
       needs explaining. */
    if (!brk) tips.push({ k: "warn",
          t: "No real break in the middle of this day",
          d: "Nothing on this day left a 45-minute gap between 11:00 and "
           + "14:30 at an acceptable pace. Consider dropping one session." });

    // small rooms
    var tight = chain.filter(function (x) {
      return x.w.cap && x.w.cap <= 60; });
    if (tight.length) {
      tips.push({ k: "warn", t: tight.length + " of these are small rooms",
        d: tight.map(function (x) {
             return x.s.c + " (" + x.w.cap + " seats)"; }).join(", ")
           + ". Reserve the moment seating opens; these fill first." });
    }
    return tips;
  }

  /* The same DP, over a pre-filtered list -- used to answer "how much
     could I do without moving at all". */
  function buildDayFrom(items, startVenue) {
    var buf = PACE[planner.pace] || 15, dayFrom = 8 * 60;
    items = items.slice().sort(function (a, b) { return a.e - b.e; });
    var n = items.length, best = [], prev = [];
    for (var i = 0; i < n; i++) { best.push(-1); prev.push(-1); }
    for (var i2 = 0; i2 < n; i2++) {
      var it = items[i2];
      if (it.b < dayFrom + needFor(startVenue, it.venue)) continue;
      best[i2] = it.val;
      for (var j = 0; j < i2; j++) {
        if (best[j] < 0) continue;
        var pj = items[j];
        if (it.b - pj.e < needFor(pj.venue, it.venue) + buf) continue;
        if (best[j] + it.val > best[i2]) {
          best[i2] = best[j] + it.val; prev[i2] = j;
        }
      }
    }
    var top = -1, ti = -1;
    for (var i3 = 0; i3 < n; i3++)
      if (best[i3] > top) { top = best[i3]; ti = i3; }
    if (ti < 0) return [];
    var out = [];
    while (ti !== -1) { out.push(items[ti]); ti = prev[ti]; }
    return out.reverse();
  }

  function renderPlanner() {
    var host = $("#planbody2");
    if (!host) return;
    host.textContent = "";
    if (!planner.day || !planner.at) {
      host.appendChild(el("p", "empty",
        "Pick the day and where you will be starting from, and this builds "
        + "a day that actually works — travel time between buildings "
        + "included, and a break in the middle."));
      return;
    }

    var chain = buildDay(planner.day, planner.at);
    var tips = advise(planner.day, planner.at, chain);

    /* The headline numbers as figures rather than as the first of six
       identical paragraphs. What fits, how long it runs, how much moving,
       and whether you get to eat. */
    if (chain.length) {
      var first0 = chain[0], last0 = chain[chain.length - 1];
      var moves0 = 0;
      for (var q = 1; q < chain.length; q++)
        if (chain[q].venue !== chain[q - 1].venue) moves0 += 1;
      var brk0 = "none";
      for (var r2 = 1; r2 < chain.length; r2++) {
        var g2 = chain[r2].b - chain[r2 - 1].e;
        if (g2 >= LUNCH_MIN && chain[r2 - 1].e >= LUNCH_FROM
            && chain[r2].b <= LUNCH_TO) { brk0 = g2 + " min"; break; }
      }
      var strip = el("div", "plstats");
      [[chain.length, chain.length === 1 ? "session" : "sessions"],
       [hhmm(first0.b) + "\u2013" + hhmm(last0.e), "your day"],
       [moves0, moves0 === 1 ? "move between hotels"
                             : "moves between hotels"],
       [brk0, "break in the middle"]].forEach(function (pair) {
        var cell = el("div", "plstat");
        cell.appendChild(el("b", null, String(pair[0])));
        cell.appendChild(el("span", null, pair[1]));
        strip.appendChild(cell);
      });
      host.appendChild(strip);
    }

    var tipbox = el("div", "tips");
    tips.forEach(function (t) {
      var row = el("div", "tip " + t.k);
      row.appendChild(el("strong", null, t.t));
      row.appendChild(el("span", null, t.d));
      tipbox.appendChild(row);
    });
    host.appendChild(tipbox);

    if (!chain.length) return;

    var list = el("section", "daygroup");
    list.appendChild(el("h2", "dayhead", "Suggested for " + dayLabel(planner.day)));

    var start = el("div", "gap ok");
    start.appendChild(el("span", "ic", "○"));
    start.appendChild(el("span", null,
      "Start at " + planner.at + ", 08:00."));
    list.appendChild(start);

    chain.forEach(function (x, i) {
      if (i) {
        var p2 = chain[i - 1];
        list.appendChild(gapRow({ s: p2.s, w: p2.w, d: planner.day },
                                { s: x.s, w: x.w, d: planner.day }));
      }
      var c = card(x.s, x.w);
      /* The tips at the top said which of these actually cover the chosen
         service; the LIST did not, and a reader who scrolls straight into
         it sees a card with no connection to what they asked for and no
         way to tell why. Asked exactly that: "I searched for AWS Amplify
         and it suggested me this session ... this screenshot doesn't have
         AWS Amplify anywhere."

         So every card says which it is. A page that explains itself only
         at the top explains itself only to people who start at the top. */
      if (planner.service !== "" && planner.service != null) {
        var si = +planner.service;
        var hit = x.s.sv.indexOf(si) !== -1;
        var tag = el("div", hit ? "svmark hit" : "svmark fill");
        tag.textContent = hit
          ? "✓ covers " + serviceName(si)
          : "Fills a gap — nothing on " + serviceName(si)
            + " fitted this slot";
        c.appendChild(tag);
      }
      list.appendChild(c);
    });
    host.appendChild(list);

    /* Adding was one-way: nothing took it back, and nothing cleared the
       form either. Reported as "once we select plan my day, how do we
       undo it? how do we reset it? I don't see any option."

       Undo removes exactly what THIS click added, not the whole plan --
       which may well contain sessions starred by hand, and swallowing
       those would be a worse bug than the one being fixed. */
    var foot = el("div", "planfoot");
    var add = el("button", "ghost", "Star all " + chain.length
                 + " into my plan");
    add.addEventListener("click", function () {
      var added = [];
      chain.forEach(function (x) {
        if (plan.indexOf(x.s.c) === -1) {
          plan.push(x.s.c);
          added.push(x.s.c);
        }
      });
      save(PLAN_KEY, plan);
      syncStars(); renderPlan(); fillMapDays();
      add.disabled = true;
      add.textContent = added.length
        ? "Added " + added.length + " to my plan"
        : "All of these were already starred";
      if (!added.length) return;

      var undo = el("button", "ghost", "Undo");
      undo.addEventListener("click", function () {
        plan = plan.filter(function (c) { return added.indexOf(c) === -1; });
        save(PLAN_KEY, plan);
        syncStars(); renderPlan(); fillMapDays();
        undo.remove();
        add.disabled = false;
        add.textContent = "Star all " + chain.length + " into my plan";
      });
      foot.appendChild(undo);
    });
    foot.appendChild(add);

    host.appendChild(foot);
  }

  /* A control that would do nothing should not be sitting there looking
     operable -- the same rule the map's day picker needed. */
  /* The banner earns its space only while it is still news. Once a day
     has been planned or anything starred, it is in the way. */
  function showCta() {
    var c = $("#cta");
    if (!c) return;
    c.hidden = !!(plan.length || planner.day || planner.at);
  }

  function showReset() {
    var rb = $("#pl-reset");
    if (!rb) return;
    rb.hidden = !(planner.day || planner.at || planner.service
                  || (planner.lane && planner.lane !== "all")
                  || planner.pace !== "standard" || planner.sponsored);
  }

  function fillPlannerControls() {
    var d = $("#pl-day"), a = $("#pl-at"), l = $("#pl-lane"),
        pc = $("#pl-pace"), sp = $("#pl-sponsored");
    if (!d || d.options.length) return;
    d.appendChild(new Option("— pick a day —", ""));
    CFG.days.forEach(function (x) { d.appendChild(new Option(dayLabel(x), x)); });
    a.appendChild(new Option("— where are you starting? —", ""));
    Object.keys(CFG.travel.matrix).sort().forEach(function (v) {
      a.appendChild(new Option(v, v)); });
    l.appendChild(new Option("Anything", "all"));
    CFG.lanes.forEach(function (x) {
      l.appendChild(new Option(x.name, x.id)); });

    // Ordered by how many sessions carry it, like the Browse filter: the
    // head of that list is what anybody is actually looking for.
    var sv = $("#pl-service");
    sv.appendChild(new Option("Any service", ""));
    var count = {};
    DATA.sessions.forEach(function (x) {
      x.sv.forEach(function (i) { count[i] = (count[i] || 0) + 1; });
    });
    Object.keys(count).map(Number).sort(function (a, b) {
      return count[b] - count[a];
    }).forEach(function (i) {
      sv.appendChild(new Option(
        DATA.facets.Services[i] + "  (" + count[i] + ")", String(i)));
    });

    d.value = planner.day; a.value = planner.at;
    l.value = planner.lane || "all"; pc.value = planner.pace;
    sv.value = planner.service || "";
    sp.checked = !!planner.sponsored;
    l.disabled = !!planner.service;

    function change() {
      planner.day = d.value; planner.at = a.value;
      planner.lane = l.value; planner.pace = pc.value;
      planner.service = sv.value; planner.sponsored = sp.checked;
      showReset();
      // A named service is more specific than a lane, so it wins and the
      // lane is greyed rather than silently ignored.
      l.disabled = !!planner.service;
      save("ri2026.planner", planner);
      showCta();
      renderPlanner();
    }
    [d, a, l, sv, pc, sp].forEach(function (x) { x.onchange = change; });

    var rb = $("#pl-reset");
    if (rb) {
      rb.onclick = function () {
        planner = { day: "", at: "", lane: "all", service: "",
                    pace: "standard", sponsored: false };
        save("ri2026.planner", planner);
        rangeCache = {};
        d.value = ""; a.value = ""; l.value = "all";
        sv.value = ""; pc.value = "standard"; sp.checked = false;
        l.disabled = false;
        showReset();
        renderPlanner();
      };
    }
    showReset();
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
                            behavior: "auto" });
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

    $("#tab-browse").addEventListener("click",
      function () { view("browse", { scroll: true }); });
    $("#tab-plan").addEventListener("click",
      function () { view("plan", { scroll: true }); });
    $("#tab-map").addEventListener("click",
      function () { view("map", { scroll: true }); });
    $("#tab-now").addEventListener("click",
      function () { view("now", { scroll: true }); });
    $("#tab-news").addEventListener("click",
      function () { view("news", { scroll: true }); });
    $("#tab-plan2").addEventListener("click",
      function () { view("plan2", { scroll: true }); });

    /* The hero button is the Plan a day TAB, said twice. It used to open
       the view and then scroll to the top of the document, which put the
       header back on screen and the planner form off it -- the button
       appeared to send you upwards, away from the thing you pressed it
       for. Anything that opens a view now goes through the same call the
       tab makes, so there is one scroll behaviour on the page, not two. */
    $("#cta-go").addEventListener("click", function () {
      view("plan2", { scroll: true });
    });


    $("#share").addEventListener("click", function () {
      var url = location.origin + location.pathname +
        "#plan=" + encodeURIComponent(plan.join(","));
      var done = function () { $("#share").textContent = "Link copied";
        setTimeout(function () {
          $("#share").textContent = "Copy a link to this plan"; }, 1800); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, done);
      else { prompt("Copy this link", url); }
    });

    $("#verify").addEventListener("click", verifyPlan);

    $("#ics").addEventListener("click", function () {
      var cal = buildICS();
      if (!cal.count) { alert("Star some sessions first."); return; }
      download("reinvent-2026.ics", cal.text, "text/calendar");
    });

    $("#md").addEventListener("click", function () {
      if (!plan.length) { alert("Star some sessions first."); return; }
      download("reinvent-2026-notes.md", buildMarkdown(), "text/markdown");
    });

    /* A backup that a person can actually move between devices. No
       server, so this is the only honest answer to "how are my notes
       saved" beyond "in this browser". */
    $("#backup").addEventListener("click", function () {
      var payload = {
        kind: "reinvent-2026-notebook", version: 1,
        saved: new Date().toISOString(),
        plan: plan, notes: notes, planner: planner, travel: tune
      };
      download("reinvent-2026-notebook.json",
               JSON.stringify(payload, null, 2), "application/json");
    });

    $("#restore").addEventListener("click", function () {
      $("#restore-file").click();
    });

    $("#restore-file").addEventListener("change", function (e) {
      var f = e.target.files && e.target.files[0];
      if (!f) return;
      var fr = new FileReader();
      fr.onload = function () {
        var d;
        try { d = JSON.parse(fr.result); } catch (err) { d = null; }
        if (!d || d.kind !== "reinvent-2026-notebook") {
          alert("That does not look like a notebook file saved by this "
                + "page.");
          return;
        }
        var howMany = (d.plan || []).length;
        var howManyNotes = Object.keys(d.notes || {}).length;
        if (!confirm("Restore " + howMany + " starred session(s) and "
                     + howManyNotes + " note(s)? This replaces what is in "
                     + "this browser now.")) return;
        plan = d.plan || [];
        notes = d.notes || {};
        if (d.planner) planner = d.planner;
        if (d.travel) tune = d.travel;
        save(PLAN_KEY, plan); save(NOTE_KEY, notes);
        save("ri2026.planner", planner); save(TUNE_KEY, tune);
        syncStars(); renderPlan(); fillMapDays();
        alert("Restored " + howMany + " session(s) and " + howManyNotes
              + " note(s).");
      };
      fr.readAsText(f);
      e.target.value = "";
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

  /* Switching view changes the document height enormously -- Browse with
     60 cards is about 14,700px, the planner form about 1,900 -- so the
     browser clamps a scroll position that no longer exists and the page
     appears to leap upwards. Measured at 1,566px on a phone, landing with
     the tab row 108px ABOVE the viewport: you could not see which tab you
     had just pressed.

     Asked as "why does it scroll upwards? was it a deliberate design?"
     It was not; it was a side effect nobody chose. So now the page does
     choose: every switch puts the tab row at the top of the screen, and
     the new view starts immediately under it. Predictable beats
     accidental. */
  var scrollFix = null, scrollExpect = 0, userMoved = false;

  /* Two different things can move the page after a view switch: the
     reader, and the layout finishing. Position alone cannot tell them
     apart -- the map's geometry arriving shifts scrollY exactly as a
     finger would -- so deliberate input is tracked separately. */
  ["wheel", "touchstart", "pointerdown", "keydown"].forEach(function (ev) {
    window.addEventListener(ev, function () { userMoved = true; }, true);
  });

  function scrollToTabs() {
    var bar = document.querySelector(".resultbar");
    if (!bar) return;
    var y = bar.getBoundingClientRect().top + window.scrollY - 8;

    /* INSTANT, not smooth. A smooth scroll here animated for about a
       second -- measured at 31 steps from 2200 down to 606 -- and the
       browser keeps applying it while it runs. Flick upwards during that
       second and the animation drags you back towards its target, which
       is exactly what "I scroll up and it comes down" is. Cancelling the
       correction did nothing about an animation already in flight.

       There is nothing for an animation to preserve here anyway: the view
       has just been swapped, the document height has changed by thousands
       of pixels, and the browser has already clamped the position without
       asking. An instant move is honest about that, and cannot be fought.
       scrollTo with behavior auto also cancels any smooth scroll still
       running, which is the second half of the fix. */
    var target = Math.max(0, y);
    window.scrollTo({ top: target, behavior: "auto" });
    scrollExpect = Math.round(window.scrollY);

    /* Some views finish rendering after this runs -- the map fetches its
       geometry, and Now builds up to eighty cards -- so the position that
       was correct a moment ago is not any more. Measured: the map landed
       409px below the tab row and Now 223px below it. One correction once
       the layout has settled, and only if it actually drifted.

       BUT NOT IF THE READER HAS TAKEN OVER. Reported as "when I scroll up
       it automatically goes down" -- the correction fired 450ms later and
       dragged them back, which is the page overruling a deliberate act.
       Listening for scroll would not do: our own smooth scroll emits
       those. These are the events only a person produces. */
    /* The correction only runs if NOTHING has moved the page since. That
       is a better guard than listening for input events, which was the
       first attempt: it missed anything that scrolls without a gesture,
       and every view still yanked the reader back. Comparing the position
       to where we left it catches a finger, a wheel, a keyboard, the
       browser restoring a position, and anything else, without having to
       enumerate them. */
    clearTimeout(scrollFix);
    scrollFix = setTimeout(function () {
      if (userMoved) return;
      if (Math.abs(Math.round(window.scrollY) - scrollExpect) > 4) return;
      var top = bar.getBoundingClientRect().top;
      if (top < -4 || top > 40) scrollToTabs();
    }, 450);
  }

  function view(which, opts) {
    $("#browse").hidden = which !== "browse";
    $("#plan").hidden = which !== "plan";
    $("#map").hidden = which !== "map";
    $("#now").hidden = which !== "now";
    $("#news").hidden = which !== "news";
    $("#plan2").hidden = which !== "plan2";
    /* Search, filters and lanes drive Browse AND the map's heat, so they
       stay up for both. In the plan they are dead controls that push the
       plan below the fold -- on a phone, past it entirely. */
    var showControls = (which === "browse" || which === "map");
    $(".controls").hidden = !showControls;
    document.querySelector(".lanes").hidden = !showControls;
    [["#tab-browse", "browse"], ["#tab-plan", "plan"], ["#tab-map", "map"],
     ["#tab-now", "now"], ["#tab-news", "news"],
     ["#tab-plan2", "plan2"]]
      .forEach(function (p) {
        $(p[0]).setAttribute("aria-selected",
                             which === p[1] ? "true" : "false");
      });
    if (which === "plan") renderPlan();
    if (which === "map") { fillMapDays(); renderMap(); }
    if (which === "now") { fillNowControls(); renderNow(); }
    if (which === "news") renderNews();
    if (which === "plan2") { fillPlannerControls(); renderPlanner(); }
    if (opts && opts.scroll) { userMoved = false; scrollToTabs(); }
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
  /* ---- offline ---------------------------------------------------------
     The site already has a service worker at /sw.js with scope "/", and its
     strategies happen to be exactly right for this page: navigations and
     CSS/JS are stale-while-revalidate, and everything else -- which is where
     the catalog JSON lands -- is network-first with a cache fallback. So a
     page that has been opened once keeps working when the wifi dies in a
     keynote hall, which it will.

     What was missing is the registration. site-footer.js does it for the
     rest of the site and this page is self-contained, so a teammate handed
     only this link would never have registered anything and would have got
     no offline at all. One line, guarded, and failure is silent: offline is
     a bonus, not a dependency. */
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    });
  }

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
      adoptCachedLive();
      indexLanes(); renderCounts(); renderCountdown();
      /* Recomputed on the minute rather than on load only: the page is
         left open, and a countdown that is right when you open it and
         wrong by morning is worse than none. */
      setInterval(renderCountdown, 60000);
      buildFilters(); wire(); renderFreshness(); renderMatrix();
      showCta();
      if (!storageOK) {
        var wn = $("#storagewarn");
        if (wn) {
          wn.textContent = "This browser is refusing to store anything, so "
            + "nothing you star or write here will survive the page being "
            + "reloaded. That is usually a private window with storage "
            + "blocked, or cookies disabled for this site. Use a normal "
            + "window, or export as you go.";
          wn.hidden = false;
        }
      }
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
