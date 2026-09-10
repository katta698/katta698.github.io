#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check every dot on the map lands inside the country it belongs to.

    python scripts/check_map_alignment.py
    python scripts/check_map_alignment.py --url https://jayanthkatta.com/...

Why this exists
---------------
A reader found cloud regions sitting in the Indian Ocean and the South
Atlantic. Nothing on the site had said anything was wrong, and every check
that existed passed:

  check_region_places.py compared each region's LATITUDE AND LONGITUDE with
  the country its vendor names, and those were right all along

  the map render check confirmed the dots drew, animated and did not overflow

Both were true and neither could see the fault, because the fault was not in
the data or in the drawing. It was that the dots and the coastlines had been
put through different projections -- correct coordinates, correct outlines,
plotted to two different pictures.

So this checks the only thing that actually matters to someone looking at the
page: the pixel a dot is drawn at, against the pixels the country is drawn as.
It reads both out of the rendered SVG, so it does not know or care which
projection is in use -- change the projection tomorrow and this still tells
you whether Mumbai is in India.

What it does not do
-------------------
It does not verify the coastlines are the right shape, or that the projection
is a good one. A map drawn entirely wrong but consistently wrong would pass.
It catches disagreement between the two halves, which is the failure that
actually happened and the one that looks authoritative while being nonsense.
"""
import argparse
import http.server
import json
import os
import re
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8951
LOCAL = "http://127.0.0.1:%d/intelligence/status/" % PORT_USED

# Natural Earth's names against the vendors'.
ALIAS = {
    "United States of America": "United States",
    "USA": "United States",
    "Republic of China": "Taiwan",
    "People's Republic of China": "China",
    "Kingdom of Saudi Arabia": "Saudi Arabia",
    "Czechia": "Czech Republic",
    "Korea": "South Korea",
}
# Countries the 110m outline set does not contain at all.
TOO_SMALL = {"Hong Kong", "Singapore", "Bahrain", "Qatar", "Malta",
             "Luxembourg", "Macao"}


def rings_from_path(d):
    """Every closed subpath of an SVG path, as a list of (x, y)."""
    out = []
    for chunk in d.split("M")[1:]:
        pts = []
        for pair in re.findall(r"(-?\d+\.?\d*),(-?\d+\.?\d*)", chunk):
            pts.append((float(pair[0]), float(pair[1])))
        if len(pts) >= 3:
            out.append(pts)
    return out


def inside(x, y, rings):
    hit = False
    for ring in rings:
        n = len(ring)
        j = n - 1
        for i in range(n):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y):
                cx = xi + (y - yi) * (xj - xi) / ((yj - yi) or 1e-12)
                if cx > x:
                    hit = not hit
            j = i
    return hit


def near(x, y, rings):
    best = 1e9
    for ring in rings:
        for px, py in ring:
            d = ((px - x) ** 2 + (py - y) ** 2) ** 0.5
            if d < best:
                best = d
    return best


def _serve(handler, port):
    """A local server on `port`, or the next free one after it.

    Every one of these checks hardcodes a port, and a run that is interrupted
    leaves the socket held -- so the next run dies with WinError 10048 and
    reports nothing at all. That is worse than a failure: a check that cannot
    start looks exactly like a check that was not run, and it cost several
    rounds today at exactly the moment the answer mattered.
    """
    import socketserver as _ss
    _ss.TCPServer.allow_reuse_address = True
    for p in range(port, port + 40):
        try:
            return _ss.TCPServer(("127.0.0.1", p), handler), p
        except OSError:
            continue
    raise SystemExit("no free port in %d-%d" % (port, port + 40))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default=None)
    # A dot sits at a city, and a 110m coastline can miss a coastal city by a
    # few units. This is generous on purpose: it is looking for dots in the
    # middle of an ocean, not for cartographic precision.
    ap.add_argument("--tolerance", type=float, default=6.0)
    args = ap.parse_args()

    os.chdir(ROOT)
    srv = None
    url = args.url
    if not url:
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *a):
                pass
        srv, PORT_USED = _serve(Quiet, PORT)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = LOCAL

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        b = pw.webkit.launch()
        pg = b.new_page(viewport={"width": 1180, "height": 1400})
        pg.goto(url, wait_until="networkidle", timeout=90000)
        pg.wait_for_selector(".om-pie", timeout=40000)
        pg.wait_for_timeout(1800)

        data = pg.evaluate("""() => {
          const dots = [...document.querySelectorAll('.om-dot')].map(d => {
            const c = d.querySelector('.om-halo');
            return { keys: (d.getAttribute('data-region') || '').split('|'),
                     x: +c.getAttribute('cx'), y: +c.getAttribute('cy') };
          });
          const land = [...document.querySelectorAll('.om-land path')]
            .map(p => p.getAttribute('d'));
          return { dots, land, landCount: land.length };
        }""")
        regions = pg.evaluate(
            "() => fetch('/intelligence/status/regions.json', {cache:'no-cache'})"
            ".then(r => r.json()).then(j => j.regions)")
        world = pg.evaluate(
            "() => fetch('/intelligence/status/world.json').then(r => r.json())")
        b.close()
    if srv:
        srv.shutdown()

    if not data["landCount"]:
        print("  no coastlines drawn -- the page refused to draw them, which is")
        print("  the projection guard doing its job. Nothing to align against.")
        return 1

    # Country name -> rings, taken from the SAME rendered picture as the dots.
    named = {}
    for i, c in enumerate(world.get("countries") or []):
        if i < len(data["land"]) and c.get("n"):
            named.setdefault(c["n"], []).extend(rings_from_path(data["land"][i]))

    ref = {}
    for r in regions:
        ref[r["cloud"] + ":" + r["code"]] = r

    print("  %d dots, %d coastline paths, %d named outlines"
          % (len(data["dots"]), data["landCount"], len(named)))

    checked = skipped = 0
    problems = []

    for d in data["dots"]:
        want, city = None, None
        for k in d["keys"]:
            r = ref.get(k)
            if r and r.get("country"):
                want = ALIAS.get(r["country"], r["country"])
                city = r.get("city") or r["code"]
                break
        if not want:
            skipped += 1
            continue
        # The map labels a subset of countries; only those have outlines here.
        key = None
        for n in named:
            if n.upper() == want.upper() or n.upper() == want.upper().replace(
                    "UNITED STATES", "UNITED STATES"):
                key = n
                break
        if key is None or want in TOO_SMALL:
            skipped += 1
            continue

        checked += 1
        if inside(d["x"], d["y"], named[key]):
            continue
        gap = near(d["x"], d["y"], named[key])
        if gap <= args.tolerance:
            continue
        problems.append("%s (%s) is %.0f units from %s"
                        % (city, ",".join(d["keys"][:2]), gap, want))

    print("  %d checked against their country's outline, %d skipped "
          "(no outline drawn for that country)" % (checked, skipped))

    if problems:
        print("\n  %d DOT(S) NOT ON THEIR COUNTRY\n" % len(problems))
        for p in problems[:20]:
            print("  - %s" % p)
        print("\n  The dots and the coastlines disagree. That is what put cloud")
        print("  regions in the Indian Ocean, and it looks authoritative.")
        return 1

    print("\n  every dot checked sits on the country it belongs to.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
