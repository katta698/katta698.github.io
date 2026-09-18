#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Every page the site offers can be reached, at every width.

    python scripts/check_reachable.py
    python scripts/check_reachable.py --live

Why this exists
---------------
Reported as: "but I don't see menu in the desktop."

/how-this-was-made/ was added to the sheet menu, which is the right home for
it -- the nav bar has 11px of slack and the words need 96. What nobody
checked is that the sheet menu is a NARROW-SCREEN affordance: the button that
opens it is display:none above 1080px. Measured on the live site:

    1440px   menu button 0x0   visible links to the page: 0
    1280px   menu button 0x0   visible links to the page: 0
    1100px   menu button 0x0   visible links to the page: 0
     920px   menu button 44x44

So the page shipped, correct in every other way, and could not be reached
from anywhere on a laptop. Every check passed: it had the shell, the star,
the right assets, the right instrument. Being unreachable is not a property
any of them were looking at.

This asks the only question that matters about navigation: starting from a
page, and without typing a URL, can a reader GET to each of the places this
site says it has? At a desktop width and a phone width, because the answer
was different at each and that is exactly how this was missed.

A link inside a closed menu counts only if the control that opens it is
itself visible -- which is the whole point, and the reason this measures
rendered geometry rather than reading hrefs out of the HTML.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Where a reader starts. One of each kind: the hub, a deep page, a post.
FROM = ["/", "/blog/", "/intelligence/", "/intelligence/whats-new/",
        "/how-this-was-made/"]

# Everywhere the site says it has. Taken from the sheet menu, which is the
# site's own answer to "what else is here".
DESTINATIONS = ["/", "/blog/", "/intelligence/", "/intelligence/whats-new/",
                "/intelligence/status/"]

# Reachable from SOMEWHERE rather than from everywhere.
#
# /how-this-was-made/ is a colophon, not a section of the site. It was in the
# footer for a while and taken out again -- "why do we have how it's made in
# the footer section? Just remove it" -- so on a desktop it is reached from
# the About section of the portfolio, which is where somebody wondering about
# it is already standing, and on a phone from the menu as well.
#
# Written as its own rule rather than dropped from the check, because "you can
# still get there from the right place" is the actual requirement and is worth
# failing on. Deleting the destination would have made the check quietly
# weaker, which is the failure mode this whole family of checks exists for.
FROM_SOMEWHERE = {"/how-this-was-made/": "/"}

WIDTHS = [(1440, "desktop"), (390, "phone")]

# Reachable = a link to it is visible, or becomes visible after opening a
# menu whose own button is visible.
PROBE = """
(dest) => {
  const vis = e => {
    const r = e.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return false;
    const cs = getComputedStyle(e);
    return cs.visibility !== 'hidden' && cs.display !== 'none';
  };
  const hit = () => [...document.querySelectorAll('a[href]')].some(a => {
    const h = a.getAttribute('href') || '';
    return (h === dest || h === 'https://jayanthkatta.com' + dest) && vis(a);
  });
  if (hit()) return 'direct';
  const btn = document.querySelector('.ck-btn');
  if (btn && vis(btn)) {
    btn.click();
    if (hit()) { btn.click(); return 'menu'; }
    btn.click();
  }
  return null;
}
"""


class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    for port in range(9701, 9751):
        try:
            srv = _Threaded(("127.0.0.1", port), H)
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
            br = pw.chromium.launch()
            for width, wname in WIDTHS:
                for page in FROM:
                    ctx = br.new_context(viewport={"width": width,
                                                   "height": 860})
                    pg = ctx.new_page()
                    pg.goto(base + page, wait_until="load", timeout=90000)
                    pg.wait_for_timeout(2400)
                    wanted = list(DESTINATIONS)
                    for dest, home in FROM_SOMEWHERE.items():
                        if page == home:
                            wanted.append(dest)
                    how = {}
                    for dest in wanted:
                        if dest == page:
                            continue
                        how[dest] = pg.evaluate(PROBE, dest)
                    gone = [d for d, v in how.items() if not v]
                    print("  %-7s %-26s %d/%d reachable%s"
                          % (wname, page, len(how) - len(gone), len(how),
                             "" if not gone else "   MISSING " + ", ".join(gone)))
                    for d in gone:
                        problems.append(
                            "from %s at %dpx there is no way to reach %s "
                            "without typing the URL" % (page, width, d))
                    ctx.close()
            br.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d UNREACHABLE\n" % len(problems))
        for p in problems[:12]:
            print("  - %s" % p)
        if len(problems) > 12:
            print("  ...and %d more" % (len(problems) - 12))
        print()
        print("  A page can be perfect and still be a page nobody can get to.")
        return 1
    print("  Every destination is reachable from every page, at both widths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
