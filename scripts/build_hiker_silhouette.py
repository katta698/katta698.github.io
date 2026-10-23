# -*- coding: utf-8 -*-
"""Cut the hiker silhouette out of the reference photograph.

    python scripts/build_hiker_silhouette.py

Writes connect/hiker.webp and connect/hiker-dusk.webp -- the same figure in
the two inks the card already uses for its artwork, swapped by theme the way
ink-scene.webp and ink-scene-dusk.webp are.

Why a traced photograph and not a drawing
-----------------------------------------
The figure on this card was built from capsules and circles, and it was
twice rebuilt by hand before the honest verdict arrived: "doesn't look like
human". Every measurement behind those rebuilds was correct and the result
was still wrong, because a person at 17px is recognised by outline alone --
the weight of a loaded pack pulling the shoulders forward, the forward lean,
the particular bend of a knee mid-stride. Those are not things you reason
your way to from joint radii. A photograph already has them.

The reference is a backlit hiker against a sunset: the subject is almost
black and the sky is almost white, so the cut is a threshold rather than a
matting problem, and the edge it produces is the real edge of a person.
"""
import os
import sys

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(os.path.expanduser("~"), ".claude", "uploads",
                   "40fdb3f0-dbd0-5032-9595-e931e38464fe",
                   "bf55d461-image.jpg")
OUT_LIGHT = os.path.join(ROOT, "connect", "hiker.webp")
OUT_DARK = os.path.join(ROOT, "connect", "hiker-dusk.webp")

# The inks the card paints its figures in today, read off .walker:
#   light theme  #241f1a
#   dark theme   #a7b2a0
INK_LIGHT = (0x24, 0x1F, 0x1A)
INK_DARK = (0xA7, 0xB2, 0xA0)

# Where he is in the 2576x1719 frame, found by counting dark pixels per
# column rather than by eye. Generous margins; the crop is tightened to the
# silhouette's own bounding box afterwards.
BOX = (1170, 560, 1700, 1620)

# Everything below 92 is him. The sky bottoms out around 150 even at its
# darkest, and his edge is hard because he is backlit.
CUT = 92


def main():
    if not os.path.exists(SRC):
        print("reference photo not found:", SRC)
        return 1

    g = Image.open(SRC).convert("L").crop(BOX)

    # Alpha straight from the luminance: fully opaque where he is, fading
    # over a few levels at the edge so the outline is not stair-stepped.
    alpha = g.point(lambda v: 255 if v < CUT - 10 else
                    (0 if v > CUT + 14 else int(255 * (CUT + 14 - v) / 24.0)))

    # The ground he stands on is part of the dark mass and must go, or he
    # arrives with a slab under his feet. Everything below the lowest point
    # of his shoes is cut; the shoes themselves are found as the lowest row
    # that is still narrow.
    w, h = alpha.size
    px = alpha.load()
    ground = h
    for y in range(h - 1, 0, -1):
        run = sum(1 for x in range(w) if px[x, y] > 128)
        if run and run < w * 0.45:          # narrow => feet, not horizon
            ground = y + 1
            break
    for y in range(ground, h):
        for x in range(w):
            px[x, y] = 0

    bbox = alpha.getbbox()
    assert bbox, "nothing survived the threshold"
    alpha = alpha.crop(bbox)

    # Down to the size it is actually drawn at, with a little headroom.
    tw = 150
    th = max(1, int(round(alpha.height * tw / float(alpha.width))))
    alpha = alpha.resize((tw, th), Image.LANCZOS)
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.4))

    # He walks LEFT in the photograph and RIGHT on the card -- the existing
    # figure's foot wedges point +x. Mirrored here rather than with a CSS
    # transform so nothing downstream has to know.
    alpha = alpha.transpose(Image.FLIP_LEFT_RIGHT)

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
