"""Build the globe's Earth texture from Natural Earth, in the site's palette.

Why a texture at all
--------------------
The globe used to draw coastlines as stroked lines and nothing else, which is
why it had no land-versus-water and why country shapes read as vague: the
rings came from the flat map's Robinson paths, inverse-projected back to
lon/lat and decimated to 3.6px, with every small island dropped. Stroked
outlines also cannot be filled on a sphere without clipping each polygon
against the limb, which is the one genuinely hard part of drawing a globe.

An equirectangular texture sidesteps all of it. The shader samples it per
pixel, so land is filled, borders are real, and the limb is exact because it
is the edge of the sphere rather than the edge of a polygon.

Why we draw it ourselves rather than using satellite imagery
------------------------------------------------------------
Blue Marble is free and public domain and looks like Google Earth, which is
the problem: it is photographic, and this site is warm, desaturated and
deliberate. Natural Earth gives the same geography as vectors, so the map can
be drawn in the site's own palette and still be real. Public domain, no
attribution required, no payment.

This is NOT part of the daily build. It fetches from a CDN, so running it on
the daily backstop would make the clouds page depend on someone else's
uptime. The texture is committed; regenerate it by hand when the palette or
the source changes.

    python scripts/build_globe_texture.py          # only if missing
    python scripts/build_globe_texture.py --force  # always
"""
import argparse
import hashlib
import io
import json
import os
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "blog", "assets", "earth.webp")
CACHE = os.path.join(ROOT, "scripts", ".cache-countries-50m.json")

SRC = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-50m.json"

# 4096 across is ~11km per pixel at the equator. At the globe's maximum 6x
# zoom the visible hemisphere spans roughly 2,900 device pixels, so the
# texture is still ahead of the screen there; going to 8192 quadrupled the
# file for detail nothing resolves.
W, H = 4096, 2048

# The daylight albedo only. Night is the shader's job -- it darkens and warms
# this, rather than a second texture, which keeps one file and means the
# terminator can move without a second download.
OCEAN = (43, 55, 64)        # deep slate, cool enough to read as water
LAND = (201, 181, 154)      # warm sand
BORDER = (139, 122, 100)    # country hairlines, darker than the land
COAST = (112, 96, 78)       # a touch darker again, so coast reads as an edge
SHELF = (54, 69, 80)        # a hint of shallower water around the coast


def fetch(force=False):
    """Natural Earth 1:50m countries, cached so a rebuild needs no network."""
    if os.path.exists(CACHE) and not force:
        with io.open(CACHE, encoding="utf-8") as fh:
            return json.load(fh)
    print("  fetching %s" % SRC)
    req = urllib.request.Request(SRC, headers={"User-Agent": "jayanthkatta.com"})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
    data = json.loads(raw.decode("utf-8"))
    with io.open(CACHE, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    print("  cached %.0fKB -> %s" % (len(raw) / 1024.0, os.path.relpath(CACHE, ROOT)))
    return data


def decode_arcs(topo):
    """TopoJSON arcs into absolute lon/lat.

    Arcs are delta-encoded against a quantised grid, so each one is a running
    sum before the transform is applied. Done once here rather than per
    geometry, because arcs are shared between neighbouring countries -- which
    is the whole point of the format.
    """
    scale = topo["transform"]["scale"]
    translate = topo["transform"]["translate"]
    out = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * scale[0] + translate[0], y * scale[1] + translate[1]))
        out.append(pts)
    return out


def ring_points(arcs, idx):
    """One ring, stitching the arc indices. A negative index means reversed."""
    pts = []
    for i in idx:
        a = arcs[~i][::-1] if i < 0 else arcs[i]
        pts.extend(a[1:] if pts else a)
    return pts


def rings_of(geom, arcs):
    """Every ring of a geometry, outer and holes alike.

    Holes are drawn as ocean afterwards rather than being skipped, so the
    Caspian reads as water instead of as land.
    """
    t = geom.get("type")
    if t == "Polygon":
        return [(r, n > 0) for n, r in enumerate(geom["arcs"])]
    if t == "MultiPolygon":
        out = []
        for poly in geom["arcs"]:
            out.extend((r, n > 0) for n, r in enumerate(poly))
        return out
    return []


def unwrap(pts):
    """Make longitudes continuous so a ring crossing 180 does not smear.

    Natural Earth splits most features at the antimeridian, but not all, and a
    single ring whose longitudes jump from +179 to -179 otherwise draws a band
    straight across the map.
    """
    out = []
    prev = None
    for lon, lat in pts:
        if prev is not None:
            while lon - prev > 180:
                lon -= 360
            while prev - lon > 180:
                lon += 360
        prev = lon
        out.append((lon, lat))
    return out


def close_pole(pts):
    """Close a ring that encircles a pole, by running it over the pole itself.

    Antarctica's outline goes right round the earth and relies on the map's
    bottom edge to close it. In equirectangular that means its first and last
    longitudes are a whole turn apart, so filling it as given produces a
    hairline along the bottom and no continent -- which is exactly what the
    first build drew.
    """
    if not pts:
        return pts
    span = abs(pts[-1][0] - pts[0][0])
    if span < 350:
        return pts
    pole = -90.0 if sum(p[1] for p in pts) / len(pts) < 0 else 90.0
    return pts + [(pts[-1][0], pole), (pts[0][0], pole)]


def to_px(pts, shift=0.0):
    return [(((lon + shift) + 180.0) / 360.0 * W, (90.0 - lat) / 180.0 * H)
            for lon, lat in pts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="rebuild even if the texture is already there")
    ap.add_argument("--refetch", action="store_true",
                    help="ignore the cached Natural Earth copy")
    args = ap.parse_args()

    if os.path.exists(OUT) and not (args.force or args.refetch):
        print("  %s already there; pass --force to rebuild"
              % os.path.relpath(OUT, ROOT))
        return 0

    topo = fetch(args.refetch)
    arcs = decode_arcs(topo)
    geoms = topo["objects"]["countries"]["geometries"]
    print("  %d countries, %d arcs" % (len(geoms), len(arcs)))

    img = Image.new("RGB", (W, H), OCEAN)
    dr = ImageDraw.Draw(img)

    # Land first, then holes back to water, then the lines on top. Three
    # passes rather than one, because a border drawn before its neighbour's
    # fill would be painted over.
    # Each outer is (fill, stroke, closed): what to flood and what to trace
    # are not always the same ring, because a polar ring is filled over the
    # pole and traced along its own coast.
    outers, holes = [], []
    degenerate = polar = 0
    for g in geoms:
        for ring, is_hole in rings_of(g, arcs):
            pts = unwrap(ring_points(arcs, ring))
            # Antarctica, and why it came out hollow the first two times.
            # Natural Earth gives it as a polygon whose OUTER ring is a
            # degenerate strip of 257 points all at lat -90 -- the bottom edge
            # of the map -- with the actual coastline as the hole. On a sphere
            # that is unambiguous: the pole is a point, and the continent is
            # everything between it and the coastline. Flattened to a
            # rectangle it inverts, so the fill went to the zero-area strip
            # and the coastline punched a hole in nothing.
            if min(abs(lat) for _, lat in pts) > 89.9:
                # Zero area, and it must be dropped before the span test or it
                # is promoted to an outer ring and stroked -- which drew a
                # hairline straight across the bottom of the map.
                degenerate += 1
                continue
            if abs(pts[-1][0] - pts[0][0]) >= 350:
                # Filled over the pole, traced open: closing the trace draws a
                # line from one edge of the map to the other, across
                # Antarctica.
                outers.append((close_pole(pts), pts, False))
                polar += 1
                continue
            if is_hole:
                holes.append(pts)
            else:
                outers.append((pts, pts, True))
    print("  %d outer, %d hole, %d polar (closed over the pole), "
          "%d degenerate (dropped)" % (len(outers), len(holes), polar, degenerate))

    # A soft shelf: the land mask, blurred, painted under the coast so the
    # water does not meet the land at a hard edge. Cheap, and it is most of
    # what makes a flat two-colour map stop looking like a diagram.
    mask = Image.new("L", (W, H), 0)
    mdr = ImageDraw.Draw(mask)
    for fill, _stroke, _closed in outers:
        for shift in (-360.0, 0.0, 360.0):
            mdr.polygon(to_px(fill, shift), fill=255)
    for pts in holes:
        for shift in (-360.0, 0.0, 360.0):
            mdr.polygon(to_px(pts, shift), fill=0)
    shelf = mask.filter(ImageFilter.GaussianBlur(9))
    img = Image.composite(Image.new("RGB", (W, H), SHELF), img, shelf)
    img.paste(Image.new("RGB", (W, H), LAND), (0, 0), mask)
    dr = ImageDraw.Draw(img)

    for _fill, stroke, closed in outers:
        for shift in (-360.0, 0.0, 360.0):
            px = to_px(stroke, shift)
            dr.line(px + ([px[0]] if closed else []),
                    fill=COAST, width=2, joint="curve")
    for pts in holes:
        for shift in (-360.0, 0.0, 360.0):
            dr.line(to_px(pts, shift) + [to_px(pts, shift)[0]],
                    fill=BORDER, width=2, joint="curve")

    img.save(OUT, "WEBP", quality=88, method=6)
    size = os.path.getsize(OUT)
    h = hashlib.md5(io.open(OUT, "rb").read()).hexdigest()[:8]
    print("  %s  %dx%d  %.0fKB  hash %s"
          % (os.path.relpath(OUT, ROOT), W, H, size / 1024.0, h))
    return 0


if __name__ == "__main__":
    sys.exit(main())
