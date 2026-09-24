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

Both are geometry, so both are measurable. The art is positioned in
percentages against a fixed aspect ratio, which means every phone width
resolves it differently -- the clearances are checked at three.

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

BOXES = """()=>{
  const r = s => { const e = document.querySelector(s); if (!e) return null;
    const b = e.getBoundingClientRect();
    return {l: Math.round(b.left), t: Math.round(b.top),
            r: Math.round(b.right), b: Math.round(b.bottom)}; };
  return {ai: r('.c-ai'), hero: r('.hero'), btn: r('.act-main'),
          attach: getComputedStyle(document.documentElement).backgroundAttachment};
}"""


def main():
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
                print("  %4dpx  head %3d (AI ends %3d, clear by %+d)  "
                      "feet %3d (button at %3d, clear by %+d)%s"
                      % (w, head, ai["b"], over_ai, feet, btn["t"], over_btn,
                         "  [figure is beside the pills]" if beside else ""))
                if not beside and over_ai < GAP:
                    bad.append("%dpx: the figure's head clears the AI pill by "
                               "%dpx, under the %dpx that stops it reading as "
                               "touching" % (w, over_ai, GAP))
                if over_btn < 0:
                    bad.append("%dpx: the figure runs %dpx behind the LinkedIn "
                               "button" % (w, -over_btn))
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
