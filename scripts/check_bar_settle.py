#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nothing in the bar is at a different x after paint than it was during it.

    python scripts/check_bar_settle.py
    python scripts/check_bar_settle.py --live

Why this exists
---------------
Reported as: "things look good in mobile except blog. When I click on blog, it
still shakes a little bit." Measured at 390px, the blog's control run sat at
x=64 while the page was settling and at x=55 once it had -- nine pixels,
sideways, on every arrival.

check_shift already existed and passed. It missed this twice over:

  - it opens a real Chrome at whatever size that window is, so it had never
    looked at a phone, and both faults behind this were inside a max-width
    media query;
  - it reads layout-shift SOURCES and keeps the ones named .nav-links,
    .nav-actions or .nav-logo. What moved here was .audio-toggle, .pal-nav
    and .theme-toggle. The shift was real, observed, and filtered out by name.

So this does not ask the browser what it thinks shifted. It samples the x of
every child of nav every 60ms from navigation commit, and requires the first
layout it ever sees to equal the last. That has no list of element names to
fall out of and no threshold to sit under: a control either was somewhere else
earlier or it was not.

Both faults it was written for were reservations that held the wrong thing:

  - nav::after reserved the cairn's WIDTH but not its margin-left:auto, so
    the free space landed somewhere else until the real cairn arrived;
  - the blog's emptied .nav-links was still a flex item, collecting the bar's
    8.8px gap, until a script added a class at 277ms.

Both are invisible in a screenshot and in any check that waits for the page to
settle before measuring it. Settled is exactly when they stop being wrong.
"""
import argparse
import http.server
import os
import random
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = [("portfolio", "/"), ("blog", "/blog/"), ("hub", "/intelligence/"),
         ("whats-new", "/intelligence/whats-new/"),
         ("status", "/intelligence/status/")]
WIDTHS = (390, 1440)

# The cairn is BUILT during the window this samples -- it is absent early and
# present late by design, and its own arrival is the thing the reservation
# exists to absorb. What must not move is everything else.
IGNORE = ("ck-here", "ck-btn", "ck-sheet")

WATCH = """window.__bar = [];
(function sample() {
  var nav = document.querySelector('nav') || document.querySelector('.nav');
  /* Not before the shared stylesheet is in effect.
     -----------------------------------------------------------------------
     site-footer.css declares --nav-h on :root, so an empty value means the
     bar is being drawn with the page's own CSS only and none of the rules
     that place these controls have applied yet.

     Sampling those frames made this check flaky: it reported the blog's
     nav-links at 814 settling to 806 once, during a preflight run with six
     browsers competing for the local server, and passed three times in a row
     on its own immediately after. That is the stylesheet arriving late under
     load, not a reservation holding the wrong space, and the two need
     different fixes. A gate that fails once in four for a reason the change
     did not cause is a gate that gets bypassed, which is what this one was
     written to stop.

     It narrows what is checked, deliberately and visibly: this asks whether
     the bar is stable once its own CSS is applied. Whether that CSS arrives
     late enough to show an unstyled frame is a real question and a different
     one -- check_shift and the critical-CSS work cover it. */
  if (nav && getComputedStyle(document.documentElement)
               .getPropertyValue('--nav-h').trim()) {
    var at = {};
    [].slice.call(nav.children).forEach(function (c) {
      var r = c.getBoundingClientRect();
      if (!r.width && !r.height) return;      /* hidden: not in the layout */
      var n = ((c.className || '') + '').trim().split(/\s+/)[0] ||
              c.tagName.toLowerCase();
      at[n] = Math.round(r.x);
    });
    window.__bar.push(at);
  }
  if (window.__bar.length < 60) setTimeout(sample, 60);
})();"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(9621, 9671):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true")
    args = ap.parse_args()
    os.chdir(ROOT)

    srv = None
    base = "https://jayanthkatta.com"
    if not args.live:
        srv, port = serve()
        base = "http://127.0.0.1:%d" % port

    from playwright.sync_api import sync_playwright

    problems = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for width in WIDTHS:
                print("  %dpx" % width)
                for name, path in PAGES:
                    ctx = b.new_context(viewport={"width": width, "height": 844})
                    ctx.add_init_script(WATCH)
                    pg = ctx.new_page()
                    # a fresh query string, so --live measures the arrival a
                    # reader gets rather than one the CDN has already warmed
                    url = base + path
                    if args.live:
                        url += "?n=%d" % random.randint(1, 999999)
                    pg.goto(url, wait_until="commit", timeout=60000)
                    pg.wait_for_timeout(3000)
                    frames = [f for f in pg.evaluate("() => window.__bar") if f]
                    ctx.close()

                    if not frames:
                        problems.append("%s at %dpx: no bar was ever sampled"
                                        % (name, width))
                        continue
                    last = frames[-1]
                    moved = {}
                    for f in frames:
                        for k, x in f.items():
                            if k in IGNORE or k not in last:
                                continue
                            if x != last[k] and k not in moved:
                                moved[k] = (x, last[k])
                    if moved:
                        detail = ", ".join("%s %d->%d" % (k, a, b_)
                                           for k, (a, b_) in
                                           sorted(moved.items()))
                        problems.append("%s at %dpx: %s" % (name, width, detail))
                        print("     FAIL %-11s %s" % (name, detail))
                    else:
                        print("     ok   %-11s %d frame(s), nothing moves"
                              % (name, len(frames)))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PAGE/SIZE COMBINATION(S) WHERE THE BAR MOVES\n"
              % len(problems))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  Reserving a placeholder's WIDTH is not enough. It has to")
        print("  stand in for how the real thing is positioned too, and a")
        print("  zero-width flex item still collects the row's gap.")
        return 1
    print("  Nothing in the bar moves after paint: %d pages, %d widths."
          % (len(PAGES), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
