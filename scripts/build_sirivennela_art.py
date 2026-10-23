# -*- coding: utf-8 -*-
"""Derive the two Sirivennela images the connect card uses.

    python scripts/build_sirivennela_art.py

connect/siri-mist.webp
    Head and shoulders, softened and faded to nothing at every edge, for
    the mist behind the tree. The falloff is baked into the file's ALPHA
    rather than applied as a CSS mask, which is the same decision the card
    already made for the ink scene's own fades and for the same reason:
    two mask layers need mask-composite, and WebKit's legacy
    -webkit-mask-composite takes different values from the standard
    property, so a masked element simply does not fade on iPhone.

The source is the same file the home page tribute card uses, so there is
one picture of him in the repo, not two.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "blog", "assets", "sirivennela-seetharama-sastry.jpg")
MIST = os.path.join(ROOT, "connect", "siri-mist.webp")

# Measured off the source, which is 1540x1021: the head runs about
# x 760-1360 and y 30-650, with the eyes near y=400.
HEAD = (700, 0, 1410, 915)


def radial_alpha(size, cx, cy, inner, outer):
    """A soft elliptical falloff, 255 inside `inner`, 0 past `outer`.

    Drawn as concentric ellipses rather than computed per pixel: at these
    sizes it is indistinguishable and it does not need numpy, which is not
    a dependency of this repo.
    """
    w, h = size
    a = Image.new("L", size, 0)
    d = ImageDraw.Draw(a)
    steps = 160
    for i in range(steps, -1, -1):
        t = i / float(steps)
        r = outer * t + inner * (1 - t)
        v = int(255 * (1 - t) ** 1.35)
        # The vertical radius is a FIXED multiple, not one derived from the
        # aspect ratio. Deriving it (h/w * 1.15 = 1.48 here) pushed the
        # ellipse past the top edge, so alpha stopped at 55 there instead
        # of 0 and the mist kept a straight horizon across his hair.
        d.ellipse([cx - r, cy - r * 1.30, cx + r, cy + r * 1.30], fill=v)
    return a.filter(ImageFilter.GaussianBlur(size[0] * 0.035))


def main():
    if not os.path.exists(SRC):
        print("source portrait missing:", SRC)
        return 1
    im = Image.open(SRC).convert("L")

    # ── the mist ────────────────────────────────────────────────────────
    m = im.crop(HEAD).resize((380, 489), Image.LANCZOS)
    # Flatten him toward the paper's midtone. At full contrast a photograph
    # among brush strokes reads as a photograph someone pasted on.
    m = ImageEnhance.Contrast(m).enhance(0.62)
    m = ImageEnhance.Brightness(m).enhance(1.06)
    m = m.filter(ImageFilter.GaussianBlur(0.6))
    # The outer radius must land INSIDE the canvas. At 265 on a 380-wide
    # image the falloff ran past the edge, so the alpha never reached zero
    # and the card showed a faint rectangle around him -- the one thing a
    # figure in mist must not have. 178 clears the 190px half-width.
    out = Image.merge("RGBA", (m, m, m, radial_alpha(m.size, 190, 215, 58, 170)))
    out.save(MIST, "WEBP", quality=82, method=6)

    for p in (MIST,):
        print("%-34s %6d bytes" % (os.path.relpath(p, ROOT),
                                   os.path.getsize(p)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
