#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""How far apart the seven of them actually stand, in rendered pixels.

Box edges lie about this. A figure's SVG box is a good deal wider than
the figure in it -- his is 17px around 8px of ink -- so the gap you
compute from translateX values is not the gap anyone sees. Offsets that
looked tight on paper left the team standing six to ten pixels apart
while the figures themselves were three to eight pixels wide: the gaps
were wider than the people, which is not what a team standing together
looks like.

So measure it. Hide the road surface and the boards, and whatever dark
columns are left are the team. The `stand` column of FOLLOWERS in
make_connect_chain.py is set from what this reports, and any change to a
pose, a size or the formation needs it run again.

    python scripts/measure_connect_formation.py
"""
import subprocess
import sys
import time
import io as _io

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

PICK = """() => { window.__a = document.getAnimations().filter(a => {
    try { return a.effect.getTiming().iterations === Infinity; }
    catch (e) { return false; } }); window.__a.forEach(a => a.pause()); }"""
SCRUB = """t => window.__a.forEach(a => { const ti = a.effect.getTiming();
  const d = ti.duration || 1, dl = ti.delay || 0;
  try { a.currentTime = ((t - dl) % d + d) % d + dl; } catch (e) {} })"""
HIDE = """() => { for (const sel of ['.tarmac', '.lane', '.sign', '.puff'])
    for (const e of document.querySelectorAll(sel))
      e.style.visibility = 'hidden'; }"""
S = 12   # device scale: one CSS pixel is S image pixels


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "9352"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 402, "height": 874},
                                device_scale_factor=S)
            pg = ctx.new_page()
            pg.goto("http://127.0.0.1:9352/connect/", wait_until="networkidle")
            pg.wait_for_timeout(900)
            pg.evaluate(PICK)
            pg.evaluate(SCRUB, 26000.0 * 0.96 + 0.31)
            pg.evaluate(HIDE)
            r = pg.evaluate("""() => { const b = document.querySelector('.road')
                .getBoundingClientRect();
                return {x: b.x, y: b.y, w: b.width, h: b.height}; }""")
            shot = pg.screenshot(clip={"x": r["x"], "y": r["y"] + 6,
                                       "width": r["w"], "height": 40})
            ctx.close()
            b.close()
    finally:
        srv.terminate()

    arr = np.asarray(Image.open(_io.BytesIO(shot)).convert("L")).astype(float)
    paper = np.percentile(arr, 95)
    on = (arr < paper - 30).sum(axis=0) > 0
    runs, i = [], 0
    while i < len(on):
        if on[i]:
            j = i
            while j < len(on) and on[j]:
                j += 1
            if (j - i) / S > 1.0:
                runs.append((i / S, j / S))
            i = j
        else:
            i += 1
    print("figures found: %d" % len(runs))
    for k, (a, bb) in enumerate(runs):
        gap = "" if k == 0 else "    gap before %.1f" % (a - runs[k - 1][1])
        print("  %6.1f - %6.1f   %4.1f wide%s" % (a, bb, bb - a, gap))
    if runs:
        print("group spans %.1f to %.1f = %.1f wide"
              % (runs[0][0], runs[-1][1], runs[-1][1] - runs[0][0]))
        mid = (runs[0][0] + runs[-1][1]) / 2.0
        print("group centre %.1f" % mid)


if __name__ == "__main__":
    main()
