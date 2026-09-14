#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""The festival banner reaches every page, and costs nothing on ordinary days.

    python scripts/check_occasion_banner.py
    python scripts/check_occasion_banner.py --live

Why this exists
---------------
Asked as: "why don't I see festivals note on others except portfolio page? Is
that deliberate?" It was not. The banner was extracted from index.html in
August 2026 specifically so it would show everywhere -- the commit is titled
"Show the occasion banner on the blog and posts, not just the home page" -- and
it then showed on the home page and nowhere else for a month. Three faults,
each hiding the next:

  blog + posts   blog.js injects the banner, but the block began with a single
                 early return if a data-site-footer script already existed.
                 That was correct when blog.js was the only thing that loaded
                 site-footer.js. Once every page shipped its own tag -- 426 of
                 them -- the guard matched everywhere and returned before ever
                 reaching the banner.
  the rest       the status page, What's New, /intelligence/ and now.html never
                 load blog.js at all. Nothing was ever going to inject it
                 there. It is injected from site-footer.js now, the one file
                 all 144 pages load.
  the alarm      validate_occasions.py still read the LUNAR table out of
                 index.html, where it had not been since the extraction, and
                 printed "has the banner been restructured?" on every run. The
                 check that exists to make a silent failure loud had itself
                 failed, silently.

None of this could show up as an error. There is simply no banner on a day
there should be one, and the first sign is noticing a missing Diwali greeting a
year late.

What is checked, and why it does not depend on today's date
-----------------------------------------------------------
A festival banner only appears on a festival, so asserting "a banner is
showing" would pass on about eight days a year and tell us nothing on the rest.
Instead this checks the two halves of the contract separately:

  DELIVERY      the banner element exists on every page type. occasion-banner.js
                creates it on load and only makes it visible when a date
                matches, so its presence proves the script arrived -- on any
                day of the year.
  COMPENSATION  with --occasion-banner-h forced to a known value, every fixed
                or sticky header moves down by exactly that much; with the
                property unset, every header sits at 0. The second half matters
                most: the rules are live on all 144 pages every day, and on the
                357 days with no festival they must cost precisely nothing.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["/", "/blog/", "/intelligence/status/", "/intelligence/whats-new/",
         "/now.html"]
FORCED = 40


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8801, 8851):
        try:
            srv = socketserver.TCPServer(("127.0.0.1", port), H)
            threading.Thread(target=srv.serve_forever, daemon=True).start()
            return srv, port
        except OSError:
            continue
    raise SystemExit("no free port")


NAV_TOP = """() => {
  const n = document.querySelector('nav.nav') || document.querySelector('nav');
  if (!n) return null;
  const cs = getComputedStyle(n);
  return {top: Math.round(n.getBoundingClientRect().top),
          pos: cs.position,
          pad: getComputedStyle(document.body).paddingTop};
}"""

HAS_EL = "() => !!document.getElementById('occasion-banner')"
SET = "(h) => document.documentElement.style.setProperty('--occasion-banner-h', h + 'px')"


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
            for p in PAGES:
                # The ordinary day, measured by BLOCKING the script rather than
                # by hoping today is not a festival. The first version of this
                # check simply loaded the page and asserted the header was at
                # 0 -- and was written on Ganesh Chaturthi, so it failed on all
                # five pages for the one reason that was not a fault. A check
                # whose result depends on the date tells you about the date.
                ctx = b.new_context(viewport={"width": 390, "height": 844})
                ctx.route("**/occasion-banner.js*", lambda r: r.abort())
                pg = ctx.new_page()
                pg.goto(base + p, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(2000)
                rest = pg.evaluate(NAV_TOP)
                ctx.close()

                ctx = b.new_context(viewport={"width": 390, "height": 844})
                pg = ctx.new_page()
                pg.goto(base + p, wait_until="domcontentloaded", timeout=45000)
                pg.wait_for_timeout(2500)

                if not pg.evaluate(HAS_EL):
                    problems.append(
                        "%s: occasion-banner.js never arrived, so no festival "
                        "will ever show here" % p)
                if rest is None:
                    problems.append("%s: no header found to measure" % p)
                    ctx.close()
                    continue
                # An ordinary day: the property is unset and must cost nothing.
                if rest["top"] != 0 or rest["pad"] not in ("0px", "0"):
                    problems.append(
                        "%s: with no banner the header sits at %dpx and the "
                        "body is padded %s -- it should be 0 and 0px on the "
                        "357 days a year with no festival"
                        % (p, rest["top"], rest["pad"]))

                pg.evaluate(SET, FORCED)
                pg.wait_for_timeout(250)
                moved = pg.evaluate(NAV_TOP)
                if moved["top"] != FORCED:
                    problems.append(
                        "%s: with a %dpx banner the header is at %dpx, so the "
                        "banner would be drawn over it (position: %s)"
                        % (p, FORCED, moved["top"], moved["pos"]))

                print("    %-26s banner delivered, header 0 -> %dpx"
                      % (p, moved["top"]))
                ctx.close()
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:12]:
            print("  - %s" % x)
        print("\n  A banner that does not arrive looks exactly like a day with")
        print("  no festival. Nothing else will report this.")
        return 1
    print("  The banner reaches all %d page types, and every header returns to"
          % len(PAGES))
    print("  0 when there is no festival.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
