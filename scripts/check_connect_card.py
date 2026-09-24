#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The contact card's artwork sits where it should, and its paper is paper.

Two things were reported from a phone, in one message, and neither is
visible in a screenshot taken at the height the page happens to be on the
machine it was built on:

  "the guy's head is just under AI"     The figure cleared the AI pill by
                                        six pixels, which reads as
                                        touching. Before that he was
                                        behind the LinkedIn button
                                        entirely.

  "the borders don't quite match"       theme-color, left behind by a
                                        repaint. The phone paints the
                                        status bar above the page and the
                                        gesture bar below it with that
                                        colour, so it is part of the card
                                        whether or not the CSS thinks so.

  "the background image stays static    background-attachment: fixed. The
   and the whole page is moving"        paper was pinned to the viewport
                                        while the card slid over it, so
                                        the grain swam against the
                                        content instead of belonging to
                                        it. A sheet of paper moves with
                                        what is printed on it.

And one more, from the same session: the card fits iPhone's screen
without scrolling and does not fit Android's, because Chrome's address
bar and gesture bar take about 85px more than Safari's chrome at the same
nominal height. Not two layouts -- one layout and two viewport heights.
So the height is asserted too, at the three the card is actually read on.

All of it is geometry, so all of it is measurable. The art is positioned
in percentages against a fixed aspect ratio, which means every phone size
resolves it differently -- hence three, not one.

The scroll half is checked by scrolling and comparing a strip of bare
paper against itself: if the strip is identical after scrolling 200px,
the paper did not move, which is the defect. The comparison is against
what a real 200px shift of the same paper looks like, so the assertion
does not depend on a threshold somebody guessed.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import numpy as np
except ImportError:
    print("  playwright or pillow not installed -- skipping")
    sys.exit(0)

PORT = 9002
URL = "http://127.0.0.1:%d/connect/" % PORT
WIDTHS = [(360, 780), (402, 874), (430, 932)]
HEAD = 0.764          # where the figure's head sits in the artwork
FEET = 0.953          # and his feet
GAP = 12              # px of air the head needs under the AI pill
SCENE = os.path.join(ROOT, "connect", "ink-scene.webp")


def birds_at():
    """How far down the artwork the topmost ink sits, as a fraction.

    The birds are the only marks in the top eighth -- above the sun and
    above the pine -- so this finds them without a hardcoded box, and it
    re-derives itself if the crop ever changes.
    """
    im = Image.open(SCENE).convert("RGBA")
    a = np.asarray(im)
    lum = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    ink = (a[..., 3] > 110) & (lum < 120)
    ys, _ = np.where(ink[:int(im.height * 0.13)])
    return (ys.min() / im.height) if len(ys) else 0.0

BOXES = """()=>{
  const r = s => { const e = document.querySelector(s); if (!e) return null;
    const b = e.getBoundingClientRect();
    return {l: Math.round(b.left), t: Math.round(b.top),
            r: Math.round(b.right), b: Math.round(b.bottom)}; };
  return {ai: r('.c-ai'), hero: r('.hero'), btn: r('.act-main'),
          page: document.body.scrollHeight, vh: innerHeight,
          attach: getComputedStyle(document.documentElement).backgroundAttachment};
}"""


def main():
    top_f = birds_at()
    print("  the topmost ink in the artwork sits at %.3f of its height"
          % top_f)
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = []
    try:
        with sync_playwright() as p:
            b = p.webkit.launch()
            for w, h in WIDTHS:
                ctx = b.new_context(viewport={"width": w, "height": h},
                                    device_scale_factor=2, is_mobile=True,
                                    has_touch=True)
                pg = ctx.new_page()
                pg.goto(URL, wait_until="domcontentloaded")
                pg.wait_for_timeout(1600)
                m = pg.evaluate(BOXES)
                hero, ai, btn = m["hero"], m["ai"], m["btn"]
                H = hero["b"] - hero["t"]
                head = round(hero["t"] + HEAD * H)
                feet = round(hero["t"] + FEET * H)
                over_ai = head - ai["b"]
                over_btn = btn["t"] - feet
                # Horizontal: if the figure is clear to the right of the
                # pill row there is nothing to clear vertically.
                beside = hero["l"] >= ai["r"]
                print("  %4dx%-3d head clears AI by %+3d   feet clear the "
                      "button by %+3d   birds at %+4d   page %d in %d%s"
                      % (w, h, over_ai, over_btn,
                         round(hero["t"] + top_f * H), m["page"], m["vh"],
                         "  [figure is beside the pills]" if beside else ""))
                if not beside and over_ai < GAP:
                    bad.append("%dpx: the figure's head clears the AI pill by "
                               "%dpx, under the %dpx that stops it reading as "
                               "touching" % (w, over_ai, GAP))
                if over_btn < 0:
                    bad.append("%dpx: the figure runs %dpx behind the LinkedIn "
                               "button" % (w, -over_btn))
                # "Are all the birds at the top visible or cut?" On one
                # size of three they were cut: the panel is anchored to
                # the buttons, and on a short screen the buttons sit high
                # enough to push its top off the viewport.
                birds = hero["t"] + top_f * H
                if birds < 0:
                    bad.append("%dx%d: the birds at the top of the artwork "
                               "are cut off by %dpx -- the panel starts "
                               "above the screen" % (w, h, -birds))

                over = m["page"] - m["vh"]
                if over > 2:
                    bad.append("%dx%d: the card is %dpx taller than the "
                               "screen, so the footer needs a scroll -- it is "
                               "meant to be one screen" % (w, h, over))
                if m["attach"] == "fixed":
                    bad.append("%dpx: the paper is attachment:fixed, so it "
                               "stays still while the card scrolls" % w)
                ctx.close()

                    # ---- the colour the phone paints around the page ---------
            #
            # Sampled from the render rather than compared against a
            # constant, so the day the paper changes again this fails
            # instead of quietly going stale -- which is how it got three
            # points out in the first place.
            ctx = b.new_context(viewport={"width": 402, "height": 874},
                                device_scale_factor=2)
            pg = ctx.new_page()
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1600)
            declared = pg.evaluate(
                "()=>document.querySelector('meta[name=theme-color]')"
                ".getAttribute('content')")
            pg.screenshot(path=os.path.join(ROOT, "_paper_top.png"))
            ctx.close()
            shot = np.asarray(Image.open(os.path.join(ROOT, "_paper_top.png"))
                              .convert("RGB"), dtype=float)
            os.remove(os.path.join(ROOT, "_paper_top.png"))
            edge = np.median(shot[0:24].reshape(-1, 3), axis=0)
            want = tuple(int(declared.lstrip("#")[i:i + 2], 16)
                         for i in (0, 2, 4))
            off = max(abs(edge[i] - want[i]) for i in range(3))
            print("  theme-color %s, page's top edge #%02X%02X%02X, "
                  "worst channel off by %d"
                  % (declared, int(edge[0]), int(edge[1]), int(edge[2]), off))
            if off > 6:
                bad.append("theme-color %s is %d off the colour the page "
                           "actually paints at its top edge, so the band the "
                           "phone draws above the card does not match it"
                           % (declared, off))

            # ---- and the same page at night -----------------------------
            #
            # Dark mode is the same sheet stained dark, not a second
            # design, so the things that can go wrong are the same ones:
            # a band round the page that does not match it, type that
            # stops carrying, and -- the one that actually happened -- the
            # artwork's pale wash lighting up a rectangle, because low
            # alpha over white pixels lightens whatever is behind it.
            # The page follows the SUN now, not the OS preference, so
            # asking for a dark colour-scheme is no longer enough to see
            # the night sheet -- at 07:00 in Chicago it correctly ignores
            # you. The clock is pinned to 22:00 local instead.
            ctx = b.new_context(viewport={"width": 412, "height": 915},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True, timezone_id="America/Chicago")
            pg = ctx.new_page()
            pg.clock.install(time="2026-09-25T03:00:00Z")
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1800)
            night = pg.evaluate("""()=>{
              const cs = getComputedStyle(document.documentElement);
              const g = n => cs.getPropertyValue(n).trim();
              const meta = [...document.querySelectorAll('meta[name=theme-color]')]
                .filter(m => (m.media||'').includes('dark'))[0];
              return {paper: g('--paper'), ink: g('--ink'), muted: g('--muted'),
                      theme: meta ? meta.getAttribute('content') : null,
                      scene: getComputedStyle(document.querySelector('.hero'))
                               .backgroundImage};
            }""")
            pg.screenshot(path=os.path.join(ROOT, "_night.png"))
            ctx.close()
            shot = np.asarray(Image.open(os.path.join(ROOT, "_night.png"))
                              .convert("RGB"), dtype=float)
            os.remove(os.path.join(ROOT, "_night.png"))
            edge = np.median(shot[0:24].reshape(-1, 3), axis=0)
            field = np.median(shot[900:1500, 8:120].reshape(-1, 3), axis=0)

            def lin(c):
                c = c / 255.0
                return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

            def lum(t):
                return (0.2126 * lin(t[0]) + 0.7152 * lin(t[1])
                        + 0.0722 * lin(t[2]))

            def ratio(hexc, bg):
                t = tuple(int(hexc.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
                a, c = lum(t), lum(bg)
                hi, lo = max(a, c), min(a, c)
                return (hi + 0.05) / (lo + 0.05)

            ink_cr = ratio(night["ink"], field)
            muted_cr = ratio(night["muted"], field)
            want = tuple(int(night["theme"].lstrip("#")[i:i + 2], 16)
                         for i in (0, 2, 4))
            off = max(abs(edge[i] - want[i]) for i in range(3))
            print("  night: paper %s  ink %.1f:1  muted %.1f:1  "
                  "theme-color %s off by %d"
                  % (night["paper"], ink_cr, muted_cr, night["theme"], off))
            if ink_cr < 7:
                bad.append("at night the body ink is %.1f:1 on the page's own "
                           "background" % ink_cr)
            if muted_cr < 4.5:
                bad.append("at night the muted text is %.1f:1, under 4.5"
                           % muted_cr)
            if off > 8:
                bad.append("the dark theme-color is %d off the page's top "
                           "edge at night" % off)
            if "dusk" not in night["scene"]:
                bad.append("at night the artwork is the daylight cut -- its "
                           "pale wash lights a rectangle on the dark sheet")

            # ---- the switch ---------------------------------------------
            #
            # It is deliberately a small mark rather than a labelled
            # control, which makes it exactly the kind of thing that ends
            # up too small to hit and too quiet to find. So: the target is
            # measured, the tap has to actually change the sheet, and the
            # choice has to survive a reload.
            ctx = b.new_context(viewport={"width": 412, "height": 915},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True, timezone_id="America/Chicago")
            pg = ctx.new_page()
            pg.clock.install(time="2026-09-24T17:00:00Z")   # midday, so light
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1500)
            lamp = pg.evaluate("""()=>{
              const e = document.getElementById('lamp');
              if (!e) return null;
              const r = e.getBoundingClientRect();
              return {w: Math.round(r.width), h: Math.round(r.height),
                      x: Math.round(r.x + r.width/2),
                      y: Math.round(r.y + r.height/2),
                      theme: document.documentElement.dataset.theme};
            }""")
            if not lamp:
                bad.append("the card has no day/night switch")
            else:
                if lamp["w"] < 44 or lamp["h"] < 44:
                    bad.append("the switch is %dx%d, under the 44px floor "
                               "every other target on this site holds"
                               % (lamp["w"], lamp["h"]))
                pg.touchscreen.tap(lamp["x"], lamp["y"])
                pg.wait_for_timeout(600)
                flipped = pg.evaluate(
                    "()=>document.documentElement.dataset.theme")
                pg.reload(wait_until="domcontentloaded")
                pg.wait_for_timeout(900)
                kept = pg.evaluate(
                    "()=>document.documentElement.dataset.theme")
                print("  switch %dx%d: %s -> %s, still %s after a reload"
                      % (lamp["w"], lamp["h"], lamp["theme"], flipped, kept))
                if flipped == lamp["theme"]:
                    bad.append("tapping the switch did not change the sheet")
                if kept != flipped:
                    bad.append("the chosen sheet did not survive a reload "
                               "(%s became %s)" % (flipped, kept))
            ctx.close()

            # ---- the paper moves with the page --------------------------
            ctx = b.new_context(viewport={"width": 402, "height": 620},
                                device_scale_factor=2, is_mobile=True,
                                has_touch=True)
            pg = ctx.new_page()
            pg.goto(URL, wait_until="domcontentloaded")
            pg.wait_for_timeout(1600)
            pg.screenshot(path=os.path.join(ROOT, "_paper_s0.png"))
            pg.evaluate("window.scrollTo(0,200)")
            pg.wait_for_timeout(500)
            moved = pg.evaluate("()=>window.scrollY")
            pg.screenshot(path=os.path.join(ROOT, "_paper_s1.png"))
            ctx.close()
            b.close()

            a0 = np.asarray(Image.open(os.path.join(ROOT, "_paper_s0.png"))
                            .convert("L"), dtype=float)
            a1 = np.asarray(Image.open(os.path.join(ROOT, "_paper_s1.png"))
                            .convert("L"), dtype=float)
            os.remove(os.path.join(ROOT, "_paper_s0.png"))
            os.remove(os.path.join(ROOT, "_paper_s1.png"))
            # a strip of the left margin: bare paper at either position
            strip = (slice(200, 800), slice(4, 60))
            after = float(np.abs(a0[strip] - a1[strip]).mean())
            # what a genuine shift of this paper looks like, for scale
            genuine = float(np.abs(a0[200:800, 4:60]
                                   - a0[600:1200, 4:60]).mean())
            print("  scrolled %dpx: the paper strip changed by %.1f, and a "
                  "real shift of it changes by %.1f" % (moved, after, genuine))
            if after < genuine * 0.4:
                bad.append("the paper did not move when the page scrolled -- "
                           "it is pinned to the viewport while the card "
                           "slides over it")
    finally:
        srv.terminate()

    print()
    if bad:
        print("  PROBLEMS:")
        for line in bad:
            print("   -", line)
        return 1
    print("  The figure clears the pills and the first button at every width,")
    print("  and the paper moves with the page rather than under it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
