#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Opening one panel in the bar closes the others.

Reported from a phone: open the palette, tap the menu mark, and the
palette stays up underneath the menu. Tapping the palette button again
closed it, and so did tapping anywhere else on the page -- which is the
shape of the bug rather than an inconsistency in it.

The menu's handler lives on the document in the CAPTURE phase and calls
stopPropagation when the tap lands on its own button, deliberately: that
is the only way it survives the nav being rebuilt under it. But capture
runs first, so the palette's "a click outside closes me" listener -- on
the document, in the bubble phase -- never ran for that one tap. Every
other outside tap reached it.

So this drives the real bar: open each panel, then open the next one, and
assert the first is gone. It runs on the blog index and a post, because
those are the two pages whose own nav handlers caused the capture-phase
workaround in the first place.
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

PORT = 9025
PAGES = [("/blog/", "the blog index"),
         ("/blog/aws-daily-intelligence-cloudwatch-omni/", "a post")]

# name, the button that opens it, how to tell it is open
PANELS = [
    ("palette", ".pal-nav-btn",
     "() => { const m = document.querySelector('.pal-menu');"
     " return !!m && !m.hidden; }"),
    ("menu", ".ck-btn",
     "() => { const s = document.querySelector('.ck-sheet');"
     " return !!s && !s.hidden; }"),
]


def main():
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(PORT)],
                           cwd=ROOT, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL)
    time.sleep(2)
    bad = []
    try:
        with sync_playwright() as p:
            b = p.webkit.launch()
            for path, label in PAGES:
                ctx = b.new_context(viewport={"width": 402, "height": 874},
                                    device_scale_factor=2, is_mobile=True,
                                    has_touch=True)
                pg = ctx.new_page()
                pg.goto("http://127.0.0.1:%d%s" % (PORT, path),
                        wait_until="domcontentloaded")
                pg.wait_for_timeout(2000)
                for first, second in ((0, 1), (1, 0)):
                    fname, fsel, fopen = PANELS[first]
                    sname, ssel, sopen = PANELS[second]
                    for sel in (fsel, ssel):
                        if pg.locator(sel).count() == 0:
                            bad.append("%s: no %s in the bar" % (label, sel))
                    if bad:
                        break
                    pg.tap(fsel)
                    pg.wait_for_timeout(500)
                    was = pg.evaluate(fopen)
                    pg.tap(ssel)
                    pg.wait_for_timeout(600)
                    still = pg.evaluate(fopen)
                    now = pg.evaluate(sopen)
                    print("  %-14s %s open: %-5s -> tapped %s: %s open %-5s, "
                          "%s still open %s"
                          % (label, fname, was, sname, sname, now, fname,
                             still))
                    if not was:
                        bad.append("%s: the %s panel did not open at all"
                                   % (label, fname))
                    if not now:
                        bad.append("%s: tapping %s did not open it while %s "
                                   "was up" % (label, sname, fname))
                    if still:
                        bad.append("%s: the %s panel is still open behind the "
                                   "%s -- two panels at once"
                                   % (label, fname, sname))
                    # leave nothing open for the next pass
                    pg.keyboard.press("Escape")
                    pg.wait_for_timeout(300)
                    pg.evaluate("""() => {
                      const m = document.querySelector('.pal-menu');
                      const b = document.querySelector('.pal-nav-btn');
                      if (m) m.hidden = true;
                      if (b) b.setAttribute('aria-expanded', 'false');
                    }""")
                ctx.close()
            b.close()
    finally:
        srv.terminate()

    print()
    if bad:
        print("  PROBLEMS:")
        for line in bad:
            print("   -", line)
        return 1
    print("  One panel at a time, on both pages, in both orders.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
