#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Real building and road geometry for the re:Invent campus, from OSM.

    python scripts/fetch_vegas_map.py          # fetch, simplify, write
    python scripts/fetch_vegas_map.py --audit  # report, write nothing

Why this exists
---------------
Asked for, after seeing the first version: "what is this map? It doesn't
make any sense. I need some sort of graphical representation ... you don't
have to embed Google Maps, but at least I need to see the buildings, and
the roads ... are we at the north side of the map or south? Just build a
proper map, mimicking some sort of Google Maps."

Fair. Five circles on an empty background is a scatter plot with hotel
names on it. It had the positions right and nothing else: no ground, no
streets, no sense of which way you are facing, nothing a person could
recognise as the place they are standing in.

WHERE THE GEOMETRY COMES FROM. OpenStreetMap, via the Overpass API, baked
into the repo at build time. Not embedded, not fetched at runtime: no API
key, no per-view cost, no third-party script watching the reader, and it
still draws when the conference wifi has gone. That last one is the whole
argument -- an embedded map is the first thing to fail in a packed hall,
which is exactly when somebody is trying to work out how to reach the
Venetian.

OSM data is ODbL, so the page carries "(c) OpenStreetMap contributors".
That attribution is not optional and must not be removed.

WHAT IS KEPT. Named buildings above a floor area, so the Strip's landmarks
are recognisable without drawing 736 outlines including every parking
kiosk; and roads classified above service level, which is what gives the
picture its skeleton. Measured before choosing: 736 buildings, 2,512 road
ways, 23,552 coordinate points, 2.2 MB raw. Shipping that would be absurd
for a decorative layer, so geometry is simplified with Douglas-Peucker at
a tolerance tied to how big a metre is on screen -- past that, detail is
sub-pixel and costs bytes to draw nothing.
"""
import argparse
import io
import json
import math
import os
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "vegas-map.json")

# Overpass is a free, shared, volunteer-run service and it answers 504 when
# it is busy -- which it did on the second query in a minute. Mirrors and
# backoff rather than hammering one host: this runs when the geometry
# changes, which is approximately never, so waiting is free and being a
# good citizen of somebody else's infrastructure is not optional.
OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
)

# Wynn/Encore at the north end down to MGM Grand at the south, with enough
# either side of the Strip to show the cross-streets that frame it.
SOUTH, WEST, NORTH, EAST = 36.0985, -115.1810, 36.1310, -115.1570

# Roads worth drawing. `service` is excluded: it is 2,000 of the 2,512 ways
# and it is car parks and loading bays, which add noise, not orientation.
ROAD_CLASSES = ("motorway", "motorway_link", "trunk", "trunk_link",
                "primary", "primary_link", "secondary", "secondary_link",
                "tertiary", "residential")

# A building has to be either one of ours or big enough to be a landmark.
MIN_AREA_M2 = 2200

# The venues, matched by substring against OSM names. Several are more than
# one OSM way -- the Venetian is a tower plus the Expo, MGM Grand is the
# hotel plus its conference centre -- and all of them are wanted.
VENUE_MATCH = {
    "Wynn/Encore":    ["wynn las vegas", "encore las vegas", "encore"],
    "Venetian":       ["venetian tower", "venetian expo", "the palazzo",
                       "palazzo tower"],
    "Caesars Palace": ["caesars palace", "forum tower",
                       "the forum shops at caesars"],
    "Caesars Forum":  ["caesars forum"],
    "MGM Grand":      ["mgm grand"],
}

# Tolerance for Douglas-Peucker, in degrees. 1e-5 deg of latitude is about
# 1.1 m; at the widths this renders at, a metre is well under a pixel.
SIMPLIFY_DEG = 1.2e-5


def overpass(query):
    import time
    last = None
    for attempt in range(3):
        for url in OVERPASS_MIRRORS:
            try:
                req = urllib.request.Request(
                    url, data=urllib.parse.urlencode({"data": query}).encode(),
                    headers={"User-Agent":
                             "jayanthkatta.com reinvent map builder"})
                with urllib.request.urlopen(req, timeout=180) as r:
                    print("    got it from %s" % url.split("/")[2])
                    return json.loads(r.read().decode("utf-8", "replace"))
            except Exception as e:
                last = "%s: %s" % (url.split("/")[2], str(e)[:60])
                print("    %s" % last)
        wait = 10 * (attempt + 1)
        if attempt < 2:
            print("    all mirrors busy; waiting %ds" % wait)
            time.sleep(wait)
    raise SystemExit(
        "  every Overpass mirror refused. Last: %s\n"
        "  Nothing was written; the existing map file is untouched." % last)


def fetch():
    bbox = "%s,%s,%s,%s" % (SOUTH, WEST, NORTH, EAST)
    q = ("[out:json][timeout:120];\n(\n"
         '  way["building"](%s);\n'
         '  way["highway"~"^(%s)$"](%s);\n'
         ");\nout geom;" % (bbox, "|".join(ROAD_CLASSES), bbox))
    return (overpass(q).get("elements") or [])


# ------------------------------------------------------------- geometry

def area_m2(pts):
    """Shoelace on a local equirectangular projection. Good enough to tell
    a hotel tower from a transformer cabinet, which is all it is for."""
    if len(pts) < 3:
        return 0.0
    lat0 = math.radians(sum(p[0] for p in pts) / len(pts))
    k = math.cos(lat0)
    xy = [((p[1] * k) * 111320.0, p[0] * 110540.0) for p in pts]
    s = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def simplify(pts, tol):
    """Douglas-Peucker, iterative so a long way cannot blow the stack."""
    if len(pts) < 3:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        lo, hi = stack.pop()
        if hi <= lo + 1:
            continue
        ax, ay = pts[lo][1], pts[lo][0]
        bx, by = pts[hi][1], pts[hi][0]
        dx, dy = bx - ax, by - ay
        den = math.hypot(dx, dy)
        worst, wi = -1.0, -1
        for i in range(lo + 1, hi):
            px, py = pts[i][1], pts[i][0]
            if den == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / den
            if d > worst:
                worst, wi = d, i
        if worst > tol and wi > 0:
            keep[wi] = True
            stack.append((lo, wi))
            stack.append((wi, hi))
    return [p for p, k in zip(pts, keep) if k]


# A car park carrying the hotel's name is not the venue. Highlighting
# "MGM Grand Self Parking" as the place your session is would send someone
# to a garage across the road from the conference centre.
NOT_THE_VENUE = ("self parking", "employee parking", "parking garage",
                 "parking", "tram station", "showroom")


def venue_for(name):
    low = (name or "").lower()
    if any(x in low for x in NOT_THE_VENUE):
        return None
    for venue, needles in VENUE_MATCH.items():
        for nd in needles:
            if nd in low:
                return venue
    return None


def round_pts(pts, nd=5):
    """Five decimal places is about a metre. Anything beyond it is noise
    that costs bytes in every reader's download."""
    return [[round(p[0], nd), round(p[1], nd)] for p in pts]


def build(elements):
    buildings, roads = [], []
    for e in elements:
        tags = e.get("tags") or {}
        geom = e.get("geometry") or []
        if len(geom) < 2:
            continue
        pts = [[g["lat"], g["lon"]] for g in geom]

        if tags.get("building"):
            name = tags.get("name") or ""
            venue = venue_for(name)
            a = area_m2(pts)
            if not venue and (not name or a < MIN_AREA_M2):
                continue
            simple = round_pts(simplify(pts, SIMPLIFY_DEG))
            if len(simple) < 3:
                continue
            buildings.append({"n": name, "v": venue, "a": int(a),
                              "p": simple})
        elif tags.get("highway"):
            cls = tags["highway"]
            simple = round_pts(simplify(pts, SIMPLIFY_DEG))
            if len(simple) < 2:
                continue
            roads.append({"n": tags.get("name") or "", "c": cls,
                          "p": simple})

    # Biggest first, so a tower draws under its own podium rather than over.
    buildings.sort(key=lambda b: -b["a"])
    return {"bbox": [SOUTH, WEST, NORTH, EAST],
            "buildings": buildings, "roads": roads,
            "attribution": "(c) OpenStreetMap contributors",
            "license": "ODbL 1.0",
            "source": "https://www.openstreetmap.org/copyright"}


def report(data):
    b, r = data["buildings"], data["roads"]
    pts = sum(len(x["p"]) for x in b) + sum(len(x["p"]) for x in r)
    print("  %d building(s), %d road way(s), %d point(s) after simplifying"
          % (len(b), len(r), pts))
    print()
    print("  venue footprints found:")
    got = {}
    for x in b:
        if x["v"]:
            got.setdefault(x["v"], []).append((x["n"], x["a"]))
    for venue in sorted(VENUE_MATCH):
        rows = got.get(venue) or []
        if not rows:
            print("    %-16s NONE -- the map will have a hole where this "
                  "venue should be" % venue)
        else:
            print("    %-16s %s" % (venue, ", ".join(
                "%s (%s m2)" % (n or "unnamed", "{:,}".format(a))
                for n, a in rows[:4])))
    missing = [v for v in VENUE_MATCH if v not in got]
    return missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true",
                    help="fetch and report, write nothing")
    args = ap.parse_args()

    print("  querying Overpass for the campus bounding box...")
    elements = fetch()
    print("  %d element(s) returned" % len(elements))
    data = build(elements)
    missing = report(data)

    if missing:
        print()
        print("  %d venue(s) have no footprint: %s"
              % (len(missing), ", ".join(missing)))
        print("  A map missing the building somebody is trying to walk to is")
        print("  worse than no map. Fix VENUE_MATCH before writing.")
        return 1

    if args.audit:
        print()
        print("  --audit: nothing written")
        return 0

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print()
    print("  wrote %s (%.0f KB)"
          % (os.path.relpath(OUT, ROOT), os.path.getsize(OUT) / 1024.0))
    return 0


if __name__ == "__main__":
    sys.exit(main())
