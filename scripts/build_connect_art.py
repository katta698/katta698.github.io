#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cut the contact card's artwork from the poster, day and night.

Both cuts are built here rather than by hand, because the thing that went
wrong with them twice is not the picture -- it is the alpha channel.

  the staircase   WebP's lossy alpha quantises the channel to about eleven
                  levels. The card's fades are IN the alpha, so the bottom
                  of the picture came down in six visible steps and every
                  soft ink edge acquired a contour. It reads as dirt on the
                  paper. Alpha is written losslessly here; only the colour
                  is compressed.

  the polarity    the man is drawn dark on a light sheet. A night cut that
                  lifts his ink instead of dimming the sheet inverts him,
                  and an inverted picture traces its own edges: the
                  anti-aliased pixels between his dark hair and the
                  darkened sky belong to neither side and end up brighter
                  than both. So the night cut is ONE MONOTONE CURVE over
                  the whole picture. Dark stays darkest, light stays
                  lightest, and a rim cannot exist.

The alpha is keyed from ink density, so the page's own paper shows through
the picture and the two share a texture instead of meeting at a seam.
"""
import hashlib
import io
import os
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "connect")

CROP = (304, 216, 684, 1283)        # the card's frame within the poster
PAPER = np.array([0xE0, 0xCC, 0xB3], dtype=float)     # the day sheet
SHEET = np.array([0x19, 0x1E, 0x17], dtype=float)     # the night sheet
LEFT_FADE = 112                     # into the text column, so there is no edge
BOTTOM_FADE = 86                    # into the buttons


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def source():
    src = Image.open(os.path.join(ART, "print-art.png")).convert("RGB")
    return np.asarray(src.crop(CROP)).astype(float)


def key_and_fade(rgb):
    """How much ink is in each pixel, and how the picture leaves the page."""
    lum = 0.299 * rgb[..., 0] + 0.587 * rgb[..., 1] + 0.114 * rgb[..., 2]
    paper = np.percentile(lum, 97)
    key = np.clip((paper - lum) / (paper - 8.0), 0, 1)
    h, w = lum.shape
    xx = np.arange(w)[None, :]
    yy = np.arange(h)[:, None]
    fade = (smoothstep(xx / float(LEFT_FADE))
            * smoothstep((h - yy) / float(BOTTOM_FADE)))
    return lum, key, np.broadcast_to(fade, lum.shape).copy()


def sun_disc(seen):
    """The sun as a filled body.

    Keying it on red alone punches holes through its own pale blossoms,
    and every later step -- the night curve, the bird mask -- needs to
    know where it is rather than where its red pixels are."""
    h, w = seen.shape[:2]
    yy = np.mgrid[0:h, 0:w][0]
    warm = (seen[..., 0] - seen[..., 2] > 46) & (yy < h * 0.66)
    disc = ndimage.binary_fill_holes(
        ndimage.binary_closing(warm, np.ones((9, 9))))
    return ndimage.binary_opening(disc, np.ones((7, 7)))


def birds(lum, key, disc):
    """The small marks high in the sky, so they can be lit at night.

    The sun and its margin are excluded, and that is not a refinement.
    The poster paints dashes of blossom around the rim, each with its own
    dark outline: small, dark, high in the picture -- indistinguishable
    from a bird by every test this uses. They were being lit as birds, so
    the night moon wore a broken ring of white ticks. Reported as "what
    are those white dots around the moon"; the fix is not to dim them but
    to stop calling them birds."""
    h, w = lum.shape
    ink = key > 0.30
    top = np.zeros_like(ink)
    top[:int(h * 0.20)] = True
    top &= ~ndimage.binary_dilation(disc, iterations=10)
    lab, n = ndimage.label(ink & top)
    seed = np.zeros(ink.shape, dtype=bool)
    for i, size in enumerate(ndimage.sum(ink & top, lab, range(1, n + 1)), 1):
        if size <= 180:
            seed |= (lab == i)
    reach = np.clip(ndimage.gaussian_filter(seed.astype(float), 1.6), 0, 1)
    reach /= max(reach.max(), 1e-6)
    dens = np.clip(key / 0.62, 0, 1)
    return np.clip(ndimage.gaussian_filter(
        np.clip(dens * (reach > 0.02) * (0.35 + 0.65 * reach), 0, 1), 0.6),
        0, 1) ** 0.40


def each_bird(bird):
    """One mask per bird, and where its body is.

    Labelled on a dilated mask, because each bird's wing tips break into
    their own specks otherwise -- eleven marks for four birds. The body is
    the vertex of the V: the lowest ink in the column where the mark is
    heaviest. That point is what the wings have to pivot about, so it is
    measured rather than assumed to be the middle of the box."""
    solid = ndimage.binary_dilation(bird > 0.25, iterations=3)
    lab, n = ndimage.label(solid)
    keep = [i for i, size in enumerate(ndimage.sum(solid, lab, range(1, n + 1)), 1)
            if size >= 200]
    h, w = bird.shape
    out = []
    for i in sorted(keep, key=lambda i: ndimage.find_objects(lab)[i - 1][0].start):
        mask = bird * (lab == i)
        cols = mask.sum(0)
        cx = int(np.argmax(ndimage.uniform_filter1d(cols, 5)))
        rows = np.nonzero(mask[:, max(cx - 2, 0):cx + 3].sum(1) > 0.05)[0]
        by = int(rows.max()) if len(rows) else int(np.argmax(mask.sum(1)))
        out.append((mask, 100.0 * cx / w, 100.0 * by / h))
    return out


def erase_flock(key, bird):
    """Close the sky over the birds, so the drawn ones do not sit under the
    flying ones and show as a second, stationary flock a few pixels off."""
    near = ndimage.binary_dilation(bird > 0.02, iterations=6)
    return np.where(near, np.minimum(key, ndimage.grey_opening(key, size=9)), key)


def save(rgb, alpha, name):
    """Colour lossy, alpha lossless -- the fades live in the alpha."""
    img = Image.fromarray(np.dstack([np.clip(rgb, 0, 255),
                                     np.clip(alpha, 0, 255)]).astype("uint8"))
    path = os.path.join(ART, name)
    img.save(path, "WEBP", quality=72, method=6, alpha_quality=100)
    levels = len(np.unique(np.asarray(Image.open(path).convert("RGBA"))[..., 3]))
    print("  %-22s %6d bytes   %3d alpha levels" %
          (name, os.path.getsize(path), levels))
    return img


def envelope(key, fade):
    """How much of the page the picture covers -- broad, not per-fibre.

    Keying the alpha pixel by pixel put every fibre of the poster's paper
    into the channel, which costs more to store than the picture does and
    says nothing the colour does not already say. The envelope is smooth,
    so it compresses to nothing, and the detail lives in the colour where
    it belongs."""
    env = np.clip(ndimage.gaussian_filter(key, 16) * 1.9, 0, 1)
    # ...but never below the ink it has to carry. A pixel at 55% alpha
    # cannot be darker than 55% of the way to black, however dark the ink
    # in it is, so a smooth envelope alone washed out everything the
    # picture draws THINLY -- the birds came out at 159 where they should
    # be 93, and the mist with them, while the dense mass round the man
    # stayed at full strength. That is what made him look cut out and
    # pasted on: it was not his edge, it was everything else fading.
    return np.maximum(env, key) * fade


def unmultiply(target, sheet, a):
    """What the ink must be, for this much of it over the sheet to look right."""
    safe = np.maximum(a, 0.03)[..., None]
    return np.clip((target - sheet * (1 - safe)) / safe, 0, 255)


def quiet(rgb, a, toward):
    """Where almost nothing shows, hold the colour still.

    A pixel at 2% alpha is invisible, but its colour is still coded, and
    noise there costs more bytes than the whole sun does. Settling it on
    the sheet it will be composited over changes nothing on screen and
    roughly halves the file."""
    w = np.clip(a * 3.0, 0, 1)[..., None]
    return rgb * w + toward * (1 - w)


def build_day(rgb, key, fade, bird):
    seen = rgb * key[..., None] + PAPER * (1 - key[..., None])
    a = envelope(key, fade)
    return save(quiet(unmultiply(seen, PAPER, a), a, PAPER), a * 255.0,
                "ink-scene.webp")


DAY_BIRD = np.array([44, 42, 39], dtype=float)     # inked, as before
NIGHT_BIRD = np.array([238, 244, 234], dtype=float)


# Seconds per wingbeat and seconds per soar, one pair per bird. Deliberately
# not round multiples of each other: four birds beating in step is a machine,
# not a flock, and the eye catches that immediately.
BEAT = [0.62, 0.74, 0.55, 0.68]
SOAR = [37, 44, 41, 49]


def build_flock(bird):
    """One full-size sheet per bird, plus the CSS that flies them.

    Full-size and mostly empty on purpose: each layer then takes exactly
    the same `right bottom / contain` sizing as the picture it sits over,
    so it lands on the same pixels at every screen width without a single
    hand-measured offset. An empty alpha channel is what WebP compresses
    best, so four of them cost less than 8KB.

    The CSS is written from the measured bodies rather than typed, because
    a pivot that is two per cent out makes the bird lurch instead of beat,
    and nothing about the file would show it."""
    found = each_bird(bird)
    lines = []
    for i, (mask, cx, by) in enumerate(found):
        for tag, ink in (("", DAY_BIRD), ("-dusk", NIGHT_BIRD)):
            rgbv = np.broadcast_to(ink, mask.shape + (3,)).copy()
            save(rgbv, np.clip(mask * 0.92, 0, 1) * 250.0,
                 "ink-bird-%d%s.webp" % (i + 1, tag))
        n = i + 1
        lines += [
            "  .b%d { animation-duration: %ds; animation-delay: -%ds; }"
            % (n, SOAR[i], SOAR[i] * n // 5),
            "  .b%d::before {" % n,
            "    background-image: url(\"/connect/ink-bird-%d.webp\");" % n,
            "    transform-origin: %.2f%% %.2f%%;" % (cx, by),
            "    animation-duration: %.2fs; animation-delay: -%.2fs;"
            % (BEAT[i], BEAT[i] * i * 0.37),
            "  }",
            "  [data-theme=\"dark\"] .b%d::before {" % n,
            "    background-image: url(\"/connect/ink-bird-%d-dusk.webp\");" % n,
            "  }",
        ]
    path = os.path.join(ROOT, "_sweep", "flock.css")
    if os.path.isdir(os.path.dirname(path)):
        io.open(path, "w", encoding="utf-8").write(chr(10).join(lines) + chr(10))
    return len(found)


def build_night(rgb, lum, key, fade, bird):
    h, w = lum.shape
    yy, xx = np.mgrid[0:h, 0:w]
    seen = rgb * key[..., None] + PAPER * (1 - key[..., None])
    seen_l = 0.299 * seen[..., 0] + 0.587 * seen[..., 1] + 0.114 * seen[..., 2]

    disc = sun_disc(seen)
    d = np.clip(ndimage.gaussian_filter(disc.astype(float), 2.5), 0, 1)

    # The blossom dashes straddle the rim: some sit on the disc and some
    # in the sky just outside it, so cleaning only what the disc mask
    # covers leaves a broken ring of white ticks around the moon. The
    # margin is generous and costs nothing -- an opening removes small
    # bright strokes and the night sky has none.
    near = ndimage.binary_dilation(disc, iterations=8)
    # A median rather than an opening: an opening only pulls brightness
    # down, so where a stroke sat ON the rim it left a notch, and the
    # moon came out castellated. A median takes small light and small
    # dark features alike and leaves the edge where it found it.
    clean_l = np.where(near, ndimage.median_filter(seen_l, size=7), seen_l)

    moon = np.exp(-(((xx - 0.53 * w) / (0.30 * w)) ** 2
                    + ((yy - 0.86 * h) / (0.11 * h)) ** 2))
    t = np.clip(clean_l / 255.0, 0, 1)

    night_l = 15 + (56 - 15) * t ** 1.3 + 16 * moon
    hue = np.clip(seen / np.maximum(seen_l, 1e-6)[..., None], 0, 4)
    hue = hue * 0.12 + np.array([0.95, 1.03, 0.94]) * 0.88
    out = np.clip(hue * night_l[..., None], 0, 255)

    # The poster paints dashes of blossom around the sun's rim. By day
    # they are petals; at night, against a dark sheet, they are the
    # brightest thing on the page and read as white speckle on the moon.
    # Removing them takes an opening rather than a curve: they are the top
    # of the range, so anything that keeps the disc keeps them too.
    ember_l = 12 + (72 - 12) * t ** 2.0
    ehue = np.clip(seen / np.maximum(seen_l, 1e-6)[..., None], 0, 4) * 0.88 + 0.12
    out = out * (1 - d[..., None]) + np.clip(ehue * ember_l[..., None], 0, 255) * d[..., None]

    # the night cut is keyed exactly like the day one, so the pale sky is
    # the page's own sheet and the picture has no top edge to see. The
    # colour is then solved backwards: what must the ink be, for the sheet
    # showing through this much of it to land on the tone above?
    a = envelope(key, fade)
    out = quiet(unmultiply(out, SHEET, a), a, SHEET)
    return save(out, a * 255.0, "ink-scene-dusk.webp")


def build_seals():
    """The stamp, cut off the paper it was printed on.

    Both seals carried a rectangle of the poster's own paper around the
    stamp. On the day sheet it passes; on the night sheet it is a pale
    grey box sitting on dark paper, which is what a reader sees first.
    The stamp is found as a filled body -- keying on red alone would drop
    the white characters out of its middle -- and everything outside it
    goes transparent, so the page's paper runs right up to the deckle.

    The threshold is well above the paper's own warmth. At 40 the poster's
    cream (231, 213, 187) cleared it by four, and the cut kept ragged tabs
    of paper down both sides of the stamp."""
    day = np.asarray(Image.open(os.path.join(ART, "ink-seal.webp"))
                     .convert("RGBA")).astype(float)
    rgb = day[..., :3]
    sat = rgb.max(-1) - rgb.min(-1)
    body = ndimage.binary_fill_holes(
        ndimage.binary_closing(sat > 82, np.ones((7, 7))))
    body = ndimage.binary_opening(body, np.ones((5, 5)))
    a = np.clip(ndimage.gaussian_filter(body.astype(float), 0.8), 0, 1)
    save(rgb, a * 255.0, "ink-seal.webp")
    # at night the same stamp, banked down to the sheet's light
    night = np.clip(rgb * 0.78, 0, 255)
    save(night, a * 255.0, "ink-seal-dusk.webp")


def main():
    rgb = source()
    lum, key, fade = key_and_fade(rgb)
    seen = rgb * key[..., None] + PAPER * (1 - key[..., None])
    bird = birds(lum, key, sun_disc(seen))
    key = erase_flock(key, bird)
    print("  from print-art.png %s, keyed on ink and faded in the alpha"
          % (CROP,))
    build_day(rgb, key, fade, bird)
    build_night(rgb, lum, key, fade, bird)
    print("  %d birds lifted onto their own layers" % build_flock(bird))
    build_seals()
    return 0


if __name__ == "__main__":
    sys.exit(main())
