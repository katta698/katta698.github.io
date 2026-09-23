#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The two ways out of a page must be thumb-sized on an iPhone.

Reported as: "it's hard to select jayanthkatta.com from here in phone."

Measured at 390px on a post page, before this check existed:

    brand mark        30x30      the smallest live thing in the bar
    breadcrumb Home   34x21      the only home link a post page shows
    the three icons   32x44      already grown, by site-footer.css
    cairn button      44x44      already right

Every control in that bar had been grown to 44px at some point except the
two a reader reaches for when they want the site itself. Which is the
failure mode: a rule written for "the controls" covers whatever was
thought of as a control that day, and the brand mark is a link, so it was
nobody's control.

Two things this asserts, because they are two different claims:

  The reach, not the box. A 30px mark can answer to a 50px touch, and a
  box measurement cannot see that. Each element is probed outward with
  elementFromPoint until the document stops naming it -- which also stops
  at the neighbour, so nothing passes here by stealing a tap that belongs
  to the button beside it.

  That a finger landing there actually goes somewhere. The first fix for
  this bought the mark its width with an absolutely positioned
  pseudo-element, the same trick the three icons use. It measured
  perfectly and, on iPhone, did not work: WebKit reports the anchor as
  the element under the point and synthesises no click for a tap that
  lands on the pseudo. A mouse click followed the link, so it passed
  everywhere except the device it was reported from. Real taps, on the
  engine Safari is built on, are the only way that is visible.

WebKit with Apple's own device metrics, not Chromium at a narrow width.
44 is Apple's figure. The small phone is in the list because it is the
one with no slack in the bar.
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

# The phone this was reported from is an iPhone, so the check is run on one
# -- WebKit with Apple's own device metrics, not Chromium at a narrow width.
# The two engines do not resolve a hit area identically: Chromium had already
# called the mark reachable at a size Safari's hit testing disagreed about,
# and 44 is Apple's own figure from the Human Interface Guidelines. The small
# phone is in the list because it is the one with no slack in the bar; if a
# hit area is going to be squeezed by a neighbour it happens at 375px.
DEVICES = ["iPhone 17 Pro", "iPhone SE (3rd gen)"]

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
        b = p.webkit.launch()
        for device in DEVICES:
            kit = p.devices[device]
            print("  %s  (%dx%d, WebKit)"
                  % (device, kit["viewport"]["width"], kit["viewport"]["height"]))
            ctx = b.new_context(**kit)
            for path, name in PAGES:
                pg = ctx.new_page()
                pg.goto("http://127.0.0.1:%d%s" % (PORT, path),
                        wait_until="domcontentloaded")
                pg.wait_for_timeout(1800)
                for sel, what in ((".nav-logo", "the brand mark"),
                                  (".post-breadcrumb a[href='/']", "Home")):
                    r = pg.evaluate(PROBE, sel)
                    if r is None:
                        continue          # not every page has a breadcrumb
                    ok = r["ownH"] >= MIN and r["ownW"] >= MIN_W
                    print("     %-14s %-14s box %dx%-3d touches %dx%-3d  %s"
                          % (name, what, r["w"], r["h"], r["ownW"], r["ownH"],
                             "ok" if ok else "TOO SMALL"))
                    if not ok:
                        bad.append("%s, %s: %s answers to only %dx%d, under "
                                   "%dx%d"
                                   % (device, name, what, r["ownW"], r["ownH"],
                                      MIN_W, MIN))
                pg.close()

            # Measuring says the area is there. Tapping says a finger landing
            # in it goes somewhere -- which is the thing that was reported,
            # and the two are not the same claim. Each tap lands at the far
            # edge of the reach, not on the glyph.
            for path, sel, dx, dy, want, what in (
                    (PAGES[0][0], ".nav-logo", -14, 0, "/blog/",
                     "the mark, tapped at its left edge"),
                    (PAGES[0][0], ".post-breadcrumb a[href='/']", 0, 14, "/",
                     "Home, tapped below the text")):
                pg = ctx.new_page()
                pg.goto("http://127.0.0.1:%d%s" % (PORT, path),
                        wait_until="domcontentloaded")
                pg.wait_for_timeout(1800)
                # Rounded, because a finger lands on a pixel. Half a pixel
                # of y -- which is what a 9.5px bar offset produces -- is
                # enough for WebKit to dispatch the tap and synthesise no
                # click, and the check then reports a link that works as a
                # link that does not.
                box = pg.evaluate("""(s)=>{const r=document.querySelector(s)
                    .getBoundingClientRect();
                    return {x: Math.round(r.left + r.width / 2),
                            y: Math.round(r.top + r.height / 2)};}""", sel)
                pg.touchscreen.tap(box["x"] + dx, box["y"] + dy)
                # Poll the URL rather than wait_for_url: its glob matched
                # nothing here and reported a tap that had in fact navigated
                # as a tap that went nowhere -- a check that fails on working
                # code gets switched off, which is worse than not having it.
                landed = False
                for _ in range(30):
                    if pg.url.endswith(want):
                        landed = True
                        break
                    pg.wait_for_timeout(200)
                print("     %-31s -> %-8s %s"
                      % (what, want, "ok" if landed else "WENT NOWHERE"))
                if not landed:
                    bad.append("%s: %s did not follow the link (ended at %s)"
                               % (device, what, pg.url))
                pg.close()
            ctx.close()
            print()
        b.close()
finally:
    srv.terminate()

print()
if bad:
    print("  PROBLEMS:")
    for line in bad:
        print("   -", line)
    sys.exit(1)
print("  On both iPhones, the mark and the way home are thumb-sized, and a")
print("  tap at the edge of each one follows the link.")
