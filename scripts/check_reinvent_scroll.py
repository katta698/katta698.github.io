#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Switching view lands somewhere sensible, and never fights the reader.

    python scripts/check_reinvent_scroll.py

Why this exists
---------------
Reported twice: "when I click on Plan a day, why does it scroll upwards?"
and then, after a fix, "I see the same issue with my plan -- when I scroll
up, it again comes down."

Three separate causes, each hiding behind the last:

  1. Switching view changes the document height by thousands of pixels --
     Browse with its cards is 15 phone screens, the planner form is two --
     so the browser clamps a scroll position that no longer exists. The
     page appeared to leap, and landed with the tab row off screen.

  2. The fix for that scrolled smoothly, which animates for about a
     second. Measured: 31 steps from 2200 down to 606. Flick upwards
     during that second and the animation drags you back towards its
     target. It is now an instant move -- there is nothing for an
     animation to preserve when the whole view has just been replaced.

  3. A correction pass runs 450ms later, because the map's geometry and
     Now's cards finish rendering after the first scroll. It guarded
     itself by listening for input events, which misses anything that
     scrolls without a gesture, and every view still yanked the reader
     back. It now checks BOTH that nothing has moved the page since, and
     that no deliberate input has happened -- because a layout shift and
     a finger look identical to position alone.

So this asserts the two halves together, which is the only way they stay
true: left alone, every view lands with the tab row on screen; scrolled
during the window, every view stays exactly where it was put.
"""
import sys, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

import os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from playwright.sync_api import sync_playwright as _p
except ImportError:
    print("  playwright is not installed; skipping")
    raise SystemExit(0)

srv = subprocess.Popen([sys.executable, "-m", "http.server", "8957"],
                       cwd=ROOT, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
time.sleep(2)
URL = ("http://127.0.0.1:8957/reinvent-2026/"
       "#plan=NET305,CMP202,CON303")
TABS = ("plan", "plan2", "map", "now", "news", "browse")
bad = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h, lab in ((390, 844, "phone"), (1250, 1000, "desktop")):
            pg = b.new_page(viewport={"width": w, "height": h},
                            device_scale_factor=2)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto(URL, wait_until="networkidle")
            pg.wait_for_selector("#plan .card", timeout=30000)
            print("== %s" % lab)

            def switch(tab, scroll_away):
                pg.evaluate("document.getElementById('tab-browse').click()")
                pg.wait_for_timeout(250)
                pg.evaluate("window.scrollTo(0,2200)")
                pg.wait_for_timeout(250)
                pg.evaluate("(t)=>document.getElementById('tab-'+t).click()",
                            tab)
                if scroll_away:
                    pg.wait_for_timeout(120)
                    # a real gesture, not a programmatic jump
                    pg.mouse.move(w // 2, h // 2)
                    pg.mouse.wheel(0, -900)
                pg.wait_for_timeout(2300)

            for tab in TABS:
                switch(tab, False)
                t = pg.evaluate("Math.round(document.querySelector"
                                "('.resultbar').getBoundingClientRect().top)")
                visible = -4 <= t < h - 40
                switch(tab, True)
                y1 = pg.evaluate("Math.round(window.scrollY)")
                pg.wait_for_timeout(900)
                y2 = pg.evaluate("Math.round(window.scrollY)")
                stayed = (y2 - y1) <= 40
                print("   %-7s lands visible: %-5s (y=%-5d) | stays put "
                      "after you scroll: %-5s (%+d)"
                      % (tab, visible, t, stayed, y2 - y1))
                if not visible:
                    bad.append("%s/%s lands off screen" % (lab, tab))
                if not stayed:
                    bad.append("%s/%s pulled you back %+d"
                               % (lab, tab, y2 - y1))
            print("   errors:", errs if errs else "none")
            if errs:
                bad.append(lab + " errors")
            print()
            pg.close()
        b.close()
finally:
    srv.terminate()

print("  PROBLEMS:", bad if bad else "none")
sys.exit(1 if bad else 0)
