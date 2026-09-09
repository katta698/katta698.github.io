#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Turn Natural Earth into an atlas: country borders, names, and ocean labels.

    python scripts/build_world_path.py

The first version drew a single merged landmass -- correct coastlines and no
borders, no names, nothing to orient by. It looked like a silhouette rather
than a map, and a reader cannot tell that a dot is in Iowa from a grey blob.

This emits every country as its own path with a name and a label anchor, so
the map can draw borders and name the places, plus the ocean labels an atlas
has. Written to intelligence/status/world.json and cached in the repo: a build
that reaches out to a CDN breaks when the CDN does, and coastlines change
roughly never.

Natural Earth is public domain. The projection is computed here rather than
taken from anywhere, so the only thing borrowed is the geometry.
"""
import io
import json
import os
import ssl
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "intelligence", "status", "world.json")
SRC = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"

W, H = 720.0, 360.0

# Oceans and seas are not in the country layer -- they are labels a cartographer
# places, so they are placed here, at the middle of the water they name.
WATER = [
    ("ARCTIC OCEAN", 78, -60, 1),
    ("NORTH ATLANTIC OCEAN", 32, -42, 1),
    ("SOUTH ATLANTIC OCEAN", -28, -18, 1),
    ("NORTH PACIFIC OCEAN", 28, -160, 1),
    ("SOUTH PACIFIC OCEAN", -28, -130, 1),
    ("INDIAN OCEAN", -22, 78, 1),
    ("SOUTHERN OCEAN", -62, 20, 1),
    ("Caribbean Sea", 15, -75, 0),
    ("Mediterranean Sea", 35, 18, 0),
    ("Gulf of Mexico", 25, -91, 0),
    ("Bay of Bengal", 15, 88, 0),
    ("Arabian Sea", 15, 63, 0),
    ("South China Sea", 14, 114, 0),
    ("Coral Sea", -17, 155, 0),
    ("Tasman Sea", -39, 162, 0),
    ("Bering Sea", 58, -178, 0),
    ("North Sea", 56, 3, 0),
]

# Named only where a label fits and helps. A 110m map cannot letter Europe
# exhaustively without turning into a wall of type.
LABEL = {
    "United States of America": "UNITED STATES", "Canada": "CANADA",
    "Mexico": "MEXICO", "Brazil": "BRAZIL", "Argentina": "ARGENTINA",
    "Chile": "CHILE", "Peru": "PERU", "Colombia": "COLOMBIA",
    "United Kingdom": "UK", "Ireland": "IRELAND", "France": "FRANCE",
    "Spain": "SPAIN", "Portugal": "PORTUGAL", "Germany": "GERMANY",
    "Italy": "ITALY", "Poland": "POLAND", "Sweden": "SWEDEN",
    "Norway": "NORWAY", "Finland": "FINLAND", "Netherlands": "NETH.",
    "Switzerland": "SWITZ.", "Ukraine": "UKRAINE", "Russia": "RUSSIA",
    "Turkey": "TURKEY", "Egypt": "EGYPT", "Nigeria": "NIGERIA",
    "South Africa": "SOUTH AFRICA", "Kenya": "KENYA", "Ethiopia": "ETHIOPIA",
    "Algeria": "ALGERIA", "Libya": "LIBYA", "Sudan": "SUDAN",
    "Saudi Arabia": "SAUDI ARABIA", "Iran": "IRAN", "Iraq": "IRAQ",
    "United Arab Emirates": "UAE", "Israel": "ISRAEL", "Qatar": "QATAR",
    "India": "INDIA", "Pakistan": "PAKISTAN", "China": "CHINA",
    "Mongolia": "MONGOLIA", "Japan": "JAPAN", "South Korea": "S. KOREA",
    "Indonesia": "INDONESIA", "Malaysia": "MALAYSIA", "Thailand": "THAILAND",
    "Vietnam": "VIETNAM", "Philippines": "PHILIPPINES", "Singapore": "SINGAPORE",
    "Australia": "AUSTRALIA", "New Zealand": "NEW ZEALAND",
    "Kazakhstan": "KAZAKHSTAN", "Greenland": "GREENLAND",
}


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


def project(lon, lat):
    return ((lon + 180) / 360 * W, (90 - lat) / 180 * H)


def ring_area(pts):
    a = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def main():
    ctx = ssl.create_default_context()
    req = urllib.request.Request(SRC, headers={"User-Agent": "jayanthkatta.com build"})
    topo = json.loads(urllib.request.urlopen(req, timeout=60, context=ctx)
                      .read().decode("utf-8", "replace"))
    arcs = decode_arcs(topo)

    countries = []
    for g in topo["objects"]["countries"]["geometries"]:
        name = (g.get("properties") or {}).get("name") or ""
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        d, best, best_area = "", None, 0.0
        for poly in polys:
            for k, ring in enumerate(poly):
                pts = ring_points(arcs, ring)
                if len(pts) < 3:
                    continue
                proj = [project(lon, lat) for lon, lat in pts]
                d += "M" + "L".join("%.1f,%.1f" % p for p in proj) + "Z"
                if k == 0:
                    # Label the biggest landmass, not an outlying island:
                    # labelling Alaska "UNITED STATES" is worse than no label.
                    a = ring_area(proj)
                    if a > best_area:
                        best_area = a
                        cx = sum(p[0] for p in proj) / len(proj)
                        cy = sum(p[1] for p in proj) / len(proj)
                        best = (round(cx, 1), round(cy, 1))
        if not d:
            continue
        rec = {"d": d}
        if name in LABEL and best and best_area > 60:
            rec["n"] = LABEL[name]
            rec["c"] = best
        countries.append(rec)

    water = [{"n": n, "c": [round(project(lon, lat)[0], 1),
                           round(project(lon, lat)[1], 1)], "big": big}
             for n, lat, lon, big in WATER]

    payload = {
        "source": SRC,
        "licence": "Natural Earth, public domain",
        "projection": "equirectangular %dx%d" % (W, H),
        "countries": countries,
        "water": water,
    }
    with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    size = os.path.getsize(OUT) / 1024
    print("  %d countries, %d labelled, %d water labels -> %.0f KB"
          % (len(countries), sum(1 for c in countries if c.get("n")),
             len(water), size))
    print("  -> %s" % OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
