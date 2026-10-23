# -*- coding: utf-8 -*-
"""Cut the walking figure out of the reference silhouette.

    python scripts/build_hiker_silhouette.py

Writes connect/hiker.webp and connect/hiker-dusk.webp -- the same figure in
the two inks the card already uses, swapped by theme the way ink-scene.webp
and the seal are.

Why a traced image and not a drawing
------------------------------------
This figure was built from capsules and circles and rebuilt twice by hand
before the honest verdict arrived: "doesn't look like human". Every
measurement behind those rebuilds was correct -- the pack really was drawn
larger than the torso, the standing pose really did fuse both legs into one
stalk -- and the result was still wrong, because a person at 17px is
recognised by OUTLINE. The lean, the swing of an arm, the bend of a knee
mid-stride: none of that is reachable from joint radii, and all of it is
already in a photograph of a person walking.

The source is a black-on-white silhouette, so the cut is a threshold.

The ground scribble underneath him is NOT cropped by eye. It is found by
row width: the figure runs 80-140 dark pixels per row and the scribble
jumps to 234 and then past 400, so the first row past the jump is the
ground and everything below it goes. Measured, so re-running this against
a differently-cropped source does not silently keep a slab under his feet.
"""
import os
import sys

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.expanduser("~"), ".claude", "uploads",
                   "40fdb3f0-dbd0-5032-9595-e931e38464fe",
                   "7684a5ec-image.jpg")
OUT_LIGHT = os.path.join(ROOT, "connect", "hiker.webp")
OUT_DARK = os.path.join(ROOT, "connect", "hiker-dusk.webp")

# The inks .walker painted in before this became an image.
INK_LIGHT = (0x24, 0x1F, 0x1A)
INK_DARK = (0xA7, 0xB2, 0xA0)

CUT = 110          # black figure, white page
GROUND_FACTOR = 1.6   # a row this much wider than the body is the ground


def main():
    if not os.path.exists(SRC):
        print("reference not found:", SRC)
        return 1

    g = Image.open(SRC).convert("L")
    w, h = g.size
    px = g.load()

    rows = [sum(1 for x in range(w) if px[x, y] < CUT) for y in range(h)]
    body = [n for n in rows if n]
    if not body:
        print("nothing below the threshold")
        return 1
    # Typical body width, from the middle half of the occupied rows.
    occupied = [y for y, n in enumerate(rows) if n]
    lo, hi = occupied[0], occupied[-1]
    mid = sorted(rows[lo:hi + 1])
    typical = mid[len(mid) // 2] or 1

    ground = hi + 1
    for y in range(lo + (hi - lo) // 2, hi + 1):
        if rows[y] > typical * GROUND_FACTOR:
            ground = y
            break
    print("body rows %d-%d, typical width %d, ground at %d"
          % (lo, hi, typical, ground))

    alpha = g.point(lambda v: 255 if v < CUT - 14 else
                    (0 if v > CUT + 14 else int(255 * (CUT + 14 - v) / 28.0)))
    ap = alpha.load()
    for y in range(ground, h):
        for x in range(w):
            ap[x, y] = 0

    bbox = alpha.getbbox()
    assert bbox, "nothing survived the threshold"
    alpha = alpha.crop(bbox)

    tw = 150
    th = max(1, int(round(alpha.height * tw / float(alpha.width))))
    alpha = alpha.resize((tw, th), Image.LANCZOS)
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.35))

    # No mirror: this reference already walks to the right, which is the way
    # the card's figure travels.
    for ink, out in ((INK_LIGHT, OUT_LIGHT), (INK_DARK, OUT_DARK)):
        flat = Image.new("RGB", alpha.size, ink)
        flat.putalpha(alpha)
        flat.save(out, "WEBP", quality=92, method=6)
        print("%-28s %4dx%-4d %6d bytes"
              % (os.path.relpath(out, ROOT), alpha.width, alpha.height,
                 os.path.getsize(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
