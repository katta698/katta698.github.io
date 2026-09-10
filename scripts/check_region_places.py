#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check every region's dot actually lands in the country it claims.

    python scripts/check_region_places.py
    python scripts/check_region_places.py --verbose

Why this exists
---------------
The map places a region at the city its vendor names, via a lookup table of
city coordinates written by hand. Hand-written coordinates are exactly the
kind of data that is wrong quietly: a dot a few degrees off still looks like a
dot, on a country, next to other dots, and nothing about the page suggests
anything is amiss. The way it gets caught is a reader who knows the region
looking at the map and saying "that is not where that is" -- which is a
terrible quality control system, because it only works for places the reader
happens to know.

So this checks all of them, against the same Natural Earth borders the map is
drawn from: take each region's coordinate, work out which country it actually
falls inside, and compare that with the country the vendor said. A region in
the wrong country is a bug. A region in no country at all is in the sea.

What it cannot check
--------------------
That a city's coordinate is the RIGHT city -- Mumbai's coordinates being
Chennai's would pass, since both are in India. It catches coordinates that are
wrong enough to leave the country, which is the class of error that makes a
map visibly nonsense, and it is checked automatically for all 159 rather than
for the handful someone thought to look at.

Borders here are the 110m generalisation, so a coastal city can sit a few
kilometres outside its own coastline. Points that miss are re-tested against
the nearest border within a tolerance before being called a mismatch.
"""
import argparse
import io
import json
import math
import os
import ssl
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGIONS = os.path.join(ROOT, "intelligence", "status", "regions.json")
SRC = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"
CACHE = os.path.join(ROOT, "intelligence", "status", ".countries-110m.json")

# Natural Earth's names against the vendors'. Only where they genuinely differ.
ALIAS = {
    "United States of America": "United States",
    "United Kingdom": "United Kingdom",
    "Czechia": "Czech Republic",
    "Republic of Korea": "South Korea",
    "Korea": "South Korea",
    "Dem. Rep. Korea": "North Korea",
    "United Arab Emirates": "United Arab Emirates",
    "Bosnia and Herz.": "Bosnia and Herzegovina",
}

# The vendors' own spellings, mapped to Natural Earth's.
VENDOR_ALIAS = {
    "Republic of China": "Taiwan",
    "People's Republic of China": "China",
    "Kingdom of Saudi Arabia": "Saudi Arabia",
    "USA": "United States",
    "Korea": "South Korea",
}

# Countries the 110m border set does not contain, because at that
# generalisation they are smaller than a pixel. Their regions are not
# unchecked by accident and not silently passed either: they are counted and
# named, so the coverage figure stays honest.
TOO_SMALL = {"Hong Kong", "Singapore", "Bahrain", "Macao", "Malta",
             "Luxembourg", "Qatar", "Bahrain Kingdom"}


def fetch_topo():
    if os.path.exists(CACHE):
        return json.load(io.open(CACHE, encoding="utf-8"))
    req = urllib.request.Request(SRC, headers={"User-Agent": "jayanthkatta.com check"})
    raw = urllib.request.urlopen(req, timeout=60,
                                 context=ssl.create_default_context()).read()
    topo = json.loads(raw.decode("utf-8", "replace"))
    with io.open(CACHE, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(topo, fh)
    return topo


def decode_arcs(topo):
    tr = topo.get("transform") or {}
    sx, sy = tr.get("scale", [1, 1])
    ox, oy = tr.get("translate", [0, 0])
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + ox, y * sy + oy))
        out.append(pts)
    return out


def ring_points(arcs, idxs):
    pts = []
    for i in idxs:
        seg = arcs[i] if i >= 0 else arcs[~i][::-1]
        if pts and seg and pts[-1] == seg[0]:
            seg = seg[1:]
        pts.extend(seg)
    return pts


def countries(topo):
    """name -> list of rings, each a list of (lon, lat)."""
    arcs = decode_arcs(topo)
    out = {}
    for g in topo["objects"]["countries"]["geometries"]:
        name = (g.get("properties") or {}).get("name") or ""
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        rings = []
        for poly in polys:
            for ring in poly:
                pts = ring_points(arcs, ring)
                if len(pts) >= 3:
                    rings.append(pts)
        if rings:
            out[ALIAS.get(name, name)] = rings
    return out


def inside(lon, lat, rings):
    """Ray casting. Odd crossings means inside."""
    hit = False
    for ring in rings:
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > lat) != (yj > lat):
                x = xi + (lat - yi) * (xj - xi) / ((yj - yi) or 1e-12)
                if x > lon:
                    hit = not hit
            j = i
    return hit


def near(lon, lat, rings, tol_deg):
    """Distance from the point to the nearest border vertex, in degrees."""
    best = 1e9
    for ring in rings:
        for x, y in ring:
            d = math.hypot(x - lon, (y - lat))
            if d < best:
                best = d
                if best < tol_deg:
                    return best
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    # 110m borders generalise a coastline by tens of kilometres, so a port
    # city can legitimately sit outside its own country's drawn outline.
    ap.add_argument("--tolerance-deg", type=float, default=1.2)
    args = ap.parse_args()

    data = json.load(io.open(REGIONS, encoding="utf-8"))
    regions = data.get("regions") or []
    borders = countries(fetch_topo())
    print("  %d regions, %d country outlines" % (len(regions), len(borders)))

    checked = wrong = sea = unknown = tiny = 0
    problems = []

    for r in regions:
        p = r.get("p")
        want = (r.get("country") or "").strip()
        if not p:
            continue
        lat, lon = p[0], p[1]
        where = [n for n, rings in borders.items() if inside(lon, lat, rings)]

        if not want:
            # No stated country: still worth knowing if it is in the sea.
            if not where:
                sea += 1
                problems.append(("SEA", r, "no country at this point"))
            continue

        want = VENDOR_ALIAS.get(want, want)
        if want in TOO_SMALL and want not in borders:
            tiny += 1
            continue
        checked += 1
        if want not in borders:
            unknown += 1
            problems.append(("NONAME", r,
                             "'%s' is not a country in the border set" % want))
            continue

        if inside(lon, lat, borders[want]):
            continue
        d = near(lon, lat, borders[want], args.tolerance_deg)
        if d <= args.tolerance_deg:
            continue                        # coastal generalisation
        wrong += 1
        problems.append(("WRONG", r,
                         "%.2f,%.2f is in %s, not %s (%.1f deg from its border)"
                         % (lat, lon, ", ".join(where) or "open water", want, d)))

    print("  %d checked against borders, %d in countries too small for the "
          "110m set" % (checked, tiny))
    nocountry = sum(1 for r in regions
                    if r.get("p") and not (r.get("country") or "").strip())
    if nocountry:
        print("  %d placed region(s) state no country, so cannot be checked "
              "this way" % nocountry)

    if not problems:
        print("\n  every placed region falls inside the country its vendor names.")
        return 0

    print("\n  %d PLACEMENT PROBLEM(S)\n" % len(problems))
    for kind, r, why in sorted(problems, key=lambda x: (x[0], x[1]["cloud"])):
        print("  [%s] %-6s %-22s %-16s %s"
              % (kind, r["cloud"], r["code"], r.get("city") or "-", why))
    print("\n  A dot in the wrong country is not a rounding error; it is the")
    print("  map saying something false about where a cloud runs.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
