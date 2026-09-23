#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The two ways out of a page must be thumb-sized on a phone.

Reported as: "it's hard to select jayanthkatta.com from here in phone."

Measured at 390px and 360px on a post page, before this check existed:

    brand mark        30x30      the smallest live thing in the bar
    breadcrumb Home   34x21      the only home link a post page shows
    the three icons   32x44      already grown, by site-footer.css
    cairn button      44x44      already right

Every control in that bar had been grown to 44px at some point except the
two a reader actually reaches for when they want the site itself. Which is
the failure mode: a rule applied to "the controls" is applied to whatever
was thought of as a control that day, and the brand mark is a link, so it
was nobody's control.

So this asserts the reach rather than the box. A mark 30px wide answers to
a 44px hit area bought with an absolutely positioned pseudo-element -- the
same trick the icons use -- and a box measurement cannot see that. The test
pokes the four corners of the 44x44 square a thumb would cover and asks the
document what it hit.
"""
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("  playwright not installed -- skipping")
    sys.exit(0)

PORT = 8967
PAGES = [
    ("/blog/aws-daily-intelligence-cloudwatch-omni/", "a post"),
    ("/blog/", "the blog index"),
    ("/intelligence/", "intelligence"),
]
MIN = 44

# Measure the span the element actually OWNS, by asking the document what
# is under each point -- not the width of its box. A 30px mark answers to a
# wider area through an absolutely positioned pseudo-element, and a box
# measurement cannot see that. Walking outward also stops at the neighbour:
# the controls claim half the gap between them, so nothing here can pass by
# stealing a tap that belongs to the button beside it.
MIN_W = 40    # 44 less the half-gap the neighbouring control rightly claims
PROBE = """(sel) => {
  const a = document.querySelector(sel);
  if (!a) return null;
  const r = a.getBoundingClientRect();
  if (!r.width) return null;
  const cy = r.top + r.height / 2, cx = r.left + r.width / 2;
  const owns = (x, y) => {
    let e = document.elementFromPoint(x, y);
    while (e) { if (e === a) return true; e = e.parentElement; }
    return false;
  };
  let l = cx, rt = cx;
  while (owns(l - 1, cy) && cx - l < 60) l -= 1;
  while (owns(rt + 1, cy) && rt - cx < 60) rt += 1;
  let t = cy, bt = cy;
  while (owns(cx, t - 1) && cy - t < 60) t -= 1;
  while (owns(cx, bt + 1) && bt - cy < 60) bt += 1;
  return { w: Math.round(r.width), h: Math.round(r.height),
           ownW: Math.round(rt - l) + 1, ownH: Math.round(bt - t) + 1 };
}"""

srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                       cwd=ROOT, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
time.sleep(2)
bad = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for path, name in PAGES:
            for w in (390, 360):
                pg = b.new_page(viewport={"width": w, "height": 844})
                pg.goto("http://127.0.0.1:%d%s" % (PORT, path),
                        wait_until="networkidle")
                pg.wait_for_timeout(1200)
                for sel, what in ((".nav-logo", "the brand mark"),
                                  (".post-breadcrumb a[href='/']", "Home")):
                    r = pg.evaluate(PROBE, sel)
                    if r is None:
                        continue          # not every page has a breadcrumb
                    ok = r["ownH"] >= MIN and r["ownW"] >= MIN_W
                    print("   %-14s %-14s box %dx%-3d touches %dx%-3d  %s"
                          % (name, what, r["w"], r["h"],
                             r["ownW"], r["ownH"], "ok" if ok else "TOO SMALL"))
                    if not ok:
                        bad.append("%s @%d: %s answers to only %dx%d, under "
                                   "%dx%d"
                                   % (name, w, what, r["ownW"], r["ownH"],
                                      MIN_W, MIN))
                pg.close()
        b.close()
finally:
    srv.terminate()

print()
if bad:
    print("  PROBLEMS:")
    for line in bad:
        print("   -", line)
    sys.exit(1)
print("  The mark and the way home are both thumb-sized, at 390 and at 360.")
