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
NE = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector"
      "/master/geojson")
STATES = NE + "/ne_50m_admin_1_states_provinces_lines.geojson"
PLACES = NE + "/ne_50m_populated_places_simple.geojson"
MARINE = NE + "/ne_50m_geography_marine_polys.geojson"
STATE_CACHE = os.path.join(ROOT, "scripts", ".cache-states-50m.json")
PLACE_CACHE = os.path.join(ROOT, "scripts", ".cache-places-50m.json")
MARINE_CACHE = os.path.join(ROOT, "scripts", ".cache-marine-50m.json")
PLACES_OUT = os.path.join(ROOT, "scripts", "globe-places.json")

# 4096 across is ~11km per pixel at the equator. At the globe's maximum 6x
# zoom the visible hemisphere spans roughly 2,900 device pixels, so the
# texture is still ahead of the screen there; going to 8192 quadrupled the
# file for detail nothing resolves.
# Drawn at 8192 and downsampled to 4096 for the base. The sharp copy is
# the real render; the base is derived from it, which also antialiases it
# better than drawing straight at 4096 does.
#
# The sharp copy is NOT shipped with the page. It is fetched only once the
# reader zooms past the point where the base starts being magnified, so a
# visit that never zooms pays nothing for it.
W, H = 8192, 4096
WB, HB = 4096, 2048
OUT2 = os.path.join(ROOT, "blog", "assets", "earth-hi.webp")
PX = W / 4096.0            # line weights follow the canvas

# The daylight albedo only. Night is the shader's job -- it darkens and warms
# this, rather than a second texture, which keeps one file and means the
# terminator can move without a second download.
OCEAN = (43, 55, 64)        # deep slate, cool enough to read as water
LAND = (201, 181, 154)      # warm sand
BORDER = (139, 122, 100)    # country hairlines, darker than the land
COAST = (112, 96, 78)       # a touch darker again, so coast reads as an edge
SHELF = (54, 69, 80)        # a hint of shallower water around the coast
STATE = (166, 148, 124)     # states and provinces: lighter than a country line,
                            # so the hierarchy reads without having to be told


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


def grab(url, cache, refetch=False):
    """Any Natural Earth file, cached so a rebuild needs no network."""
    if os.path.exists(cache) and not refetch:
        with io.open(cache, encoding="utf-8") as fh:
            return json.load(fh)
    print("  fetching %s" % url.rsplit("/", 1)[-1])
    req = urllib.request.Request(url, headers={"User-Agent": "jayanthkatta.com"})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    data = json.loads(raw.decode("utf-8"))
    with io.open(cache, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return data


def line_strings(geo):
    """Every LineString in a GeoJSON feature collection, as lon/lat lists."""
    out = []
    for f in geo.get("features", []):
        g = f.get("geometry") or {}
        t = g.get("type")
        if t == "LineString":
            out.append(g["coordinates"])
        elif t == "MultiLineString":
            out.extend(g["coordinates"])
    return out


def biggest_centroid(geom):
    """A label point for a polygon: the centroid of its largest ring.

    Largest rather than first, because a sea's geometry often leads with a
    sliver -- an inlet or an island's coastline -- and a label pinned to that
    ends up somewhere nobody would call by that name.
    """
    polys = []
    t = geom.get("type")
    if t == "Polygon":
        polys = [geom["coordinates"]]
    elif t == "MultiPolygon":
        polys = geom["coordinates"]
    best, best_area = None, -1.0
    for poly in polys:
        if not poly:
            continue
        ring = poly[0]
        if len(ring) < 3:
            continue
        a = cx = cy = 0.0
        for i in range(len(ring) - 1):
            x0, y0 = ring[i][0], ring[i][1]
            x1, y1 = ring[i + 1][0], ring[i + 1][1]
            f = x0 * y1 - x1 * y0
            a += f
            cx += (x0 + x1) * f
            cy += (y0 + y1) * f
        if abs(a) < 1e-12:
            continue
        area = abs(a) / 2.0
        if area > best_area:
            best_area = area
            best = (cx / (3.0 * a), cy / (3.0 * a))
    return best


def export_marine(refetch=False):
    """Oceans first, then the named seas and the larger gulfs and straits."""
    geo = grab(MARINE, MARINE_CACHE, refetch)
    rows = []
    for f in geo.get("features", []):
        pr = f.get("properties") or {}
        # name_en first: Natural Earth's own label field is sometimes the
        # local form, so the map ended up reading "Golfo de California"
        # beside "Gulf of Alaska".
        name = pr.get("name_en") or pr.get("label") or pr.get("name")
        cls = (pr.get("featurecla") or "").lower()
        if not name:
            continue
        pt = biggest_centroid(f.get("geometry") or {})
        if not pt:
            continue
        # Natural Earth shouts some of these and not others. Rendered in one
        # voice, so the map does not look like two maps.
        if name.isupper():
            name = name.title()
        tier = 0 if cls == "ocean" else 2
        if cls in ("reef", "river"):
            continue
        rows.append([round(pt[0], 3), round(pt[1], 3), name, tier, 1])
    rows.sort(key=lambda r: r[3])
    print("  %d marine labels (%d oceans)"
          % (len(rows), sum(1 for r in rows if r[3] == 0)))
    return rows


def export_places(refetch=False):
    """The cities the page will label, ranked so the important ones win.

    Three tiers, because at a glance a reader wants capitals, zoomed in they
    want the state capital, and closer still they want whatever large city is
    actually there. Scientific stations are dropped -- forty Antarctic huts
    outranking Chicago is not a useful map.
    """
    geo = grab(PLACES, PLACE_CACHE, refetch)
    rows = []
    for f in geo.get("features", []):
        pr = f.get("properties") or {}
        cls = pr.get("featurecla") or ""
        if "Scientific" in cls:
            continue
        name = pr.get("name") or pr.get("nameascii")
        if not name:
            continue
        lon, lat = pr.get("longitude"), pr.get("latitude")
        if lon is None or lat is None:
            continue
        # Tiers are a single ranking across land and water, because they
        # compete for the same pixels: oceans 0, country capitals 1, seas 2,
        # state capitals 3, everything else 4.
        if pr.get("adm0cap") == 1:
            tier = 1
        elif "Admin-1" in cls:
            tier = 3
        else:
            tier = 4
        pop = int(pr.get("pop_max") or 0)
        rows.append([round(float(lon), 3), round(float(lat), 3),
                     name, tier, pop])
    # Within a tier, the larger city wins a contested spot on screen.
    rows.sort(key=lambda r: (r[3], -r[4]))
    rows = [r[:4] + [0] for r in rows]
    rows += export_marine(refetch)
    rows.sort(key=lambda r: r[3])
    with io.open(PLACES_OUT, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))
    by = {}
    for r in rows:
        by[r[3]] = by.get(r[3], 0) + 1
    print("  %d labels -> %s  (%d oceans, %d capitals, %d seas, "
          "%d state capitals, %d other)"
          % (len(rows), os.path.relpath(PLACES_OUT, ROOT),
             by.get(0, 0), by.get(1, 0), by.get(2, 0), by.get(3, 0),
             by.get(4, 0)))


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
    shelf = mask.filter(ImageFilter.GaussianBlur(9 * PX))
    img = Image.composite(Image.new("RGB", (W, H), SHELF), img, shelf)
    img.paste(Image.new("RGB", (W, H), LAND), (0, 0), mask)
    dr = ImageDraw.Draw(img)

    # States and provinces first, so a country line always wins where the
    # two run together -- which they do along most of a country's edge.
    states = line_strings(grab(STATES, STATE_CACHE, args.refetch))
    for ls in states:
        pts = unwrap([(c[0], c[1]) for c in ls])
        for shift in (-360.0, 0.0, 360.0):
            dr.line(to_px(pts, shift), fill=STATE,
                    width=int(round(1 * PX)), joint="curve")
    print("  %d state and province lines" % len(states))

    for _fill, stroke, closed in outers:
        for shift in (-360.0, 0.0, 360.0):
            px = to_px(stroke, shift)
            dr.line(px + ([px[0]] if closed else []),
                    fill=COAST, width=int(round(2 * PX)), joint="curve")
    for pts in holes:
        for shift in (-360.0, 0.0, 360.0):
            dr.line(to_px(pts, shift) + [to_px(pts, shift)[0]],
                    fill=BORDER, width=int(round(2 * PX)), joint="curve")

    export_places(args.refetch)

    img.save(OUT2, "WEBP", quality=86, method=6)
    print("  %s  %dx%d  %.0fKB  (fetched only when zoomed in)"
          % (os.path.relpath(OUT2, ROOT), W, H,
             os.path.getsize(OUT2) / 1024.0))
    img = img.resize((WB, HB), Image.LANCZOS)
    img.save(OUT, "WEBP", quality=88, method=6)
    size = os.path.getsize(OUT)
    h = hashlib.md5(io.open(OUT, "rb").read()).hexdigest()[:8]
    print("  %s  %dx%d  %.0fKB  hash %s"
          % (os.path.relpath(OUT, ROOT), WB, HB, size / 1024.0, h))
    return 0


if __name__ == "__main__":
    sys.exit(main())
