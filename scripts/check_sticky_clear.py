#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Nothing that sticks to the top ends up underneath the header.

    python scripts/check_sticky_clear.py
    python scripts/check_sticky_clear.py --live

Why this exists
---------------
Reported from a desktop: scrolling on What's New leaves the filter row half
hidden -- "I just see parts of it... All clouds, AWS, Azure, Google Cloud,
seven days, thirty days".

.controls was pinned at a flat top:56px while the nav is 64px tall. Eight
pixels of the row had been behind the nav since it was written, which reads as
a slightly clipped edge rather than a bug. Then the occasion banner began
showing on that page, the nav moved from 0 to 33px, and eight pixels became
forty-one -- enough to swallow the whole row.

    scrollY 600   nav bottom 97, controls top 56, overlap 41px
                  all six pills report the nav as the element at their centre

Two lessons, both in what is checked here. A hardcoded offset is a copy of a
number that lives somewhere else, and it goes stale silently -- the blog had no
such bug because blog.css says calc(var(--nav-h) + var(--occasion-banner-h)).
And a small constant error stays invisible until something shifts the baseline,
at which point it arrives looking like a brand new fault in whatever moved.

So this scrolls each page and asserts that anything sticky or fixed near the
top is still fully clear of the header. It runs at desktop widths because that
is where these rows are sticky at all -- What's New drops to position:static
below 820px.
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES = ["/", "/blog/", "/intelligence/status/", "/intelligence/whats-new/"]
WIDTHS = [1024, 1440]
SCROLLS = [600, 1800]

PROBE = r"""() => {
  const nav = document.querySelector('nav.nav') || document.querySelector('nav');
  if (!nav) return {skip: true};
  const nr = nav.getBoundingClientRect();
  const banner = document.getElementById('occasion-banner');
  const out = [];
  document.querySelectorAll('*').forEach(function (e) {
    if (e === nav || e === banner || nav.contains(e)) return;
    const cs = getComputedStyle(e);
    if (cs.position !== 'sticky' && cs.position !== 'fixed') return;
    // Closed modals are full-screen, fixed at top:0, and laid out -- the ask
    // terminal's overlay reported itself as 64px under the header on every
    // page. It is not under anything; it is not being shown. Anything the
    // reader cannot see cannot be obscured, so test visibility rather than
    // geometry alone.
    if (cs.visibility === 'hidden' || cs.display === 'none') return;
    if (parseFloat(cs.opacity) < 0.05) return;
    if (cs.pointerEvents === 'none') return;
    const r = e.getBoundingClientRect();
    if (r.height < 4 || r.width < 4) return;
    // Only things sitting at the top of the viewport can be under the header.
    if (r.top > nr.bottom + 40) return;
    const overlap = Math.round(Math.min(nr.bottom, r.bottom) - Math.max(nr.top, r.top));
    if (overlap <= 0) return;
    out.push({
      tag: e.tagName.toLowerCase() + '.' + (e.className || '').toString().split(' ')[0],
      overlap: overlap,
      top: Math.round(r.top),
      navBottom: Math.round(nr.bottom),
      cssTop: cs.top
    });
  });
  return {navBottom: Math.round(nr.bottom), hits: out};
}"""


# One connection at a time was the whole problem.
#
# socketserver.TCPServer is single-threaded: it serves one request, then the
# next. A browser opening a page wants the HTML, two stylesheets, three
# scripts and two font files, and it asks for them at once -- so they queued,
# and with six checks running in parallel they queued behind each other's
# queues too.
#
# That is why check_brand reported the wordmark at 114.8px (the fallback
# serif) instead of 96.6px (Playfair) only during a full run, and why
# check_bar_settle saw the portfolio's bar slide 18px only during a full run.
# Neither was a fault in the site. Both were this line.
#
# ThreadingTCPServer serves them concurrently. daemon_threads so a hung
# request cannot keep the process alive after the check is done.
class _Threaded(socketserver.ThreadingTCPServer):
    daemon_threads = True
    allow_reuse_address = True


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    for port in range(8901, 8951):
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
            b = pw.chromium.launch()
            for p in PAGES:
                worst = 0
                for w in WIDTHS:
                    ctx = b.new_context(viewport={"width": w, "height": 900})
                    pg = ctx.new_page()
                    pg.goto(base + p, wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(2600)
                    for y in SCROLLS:
                        pg.evaluate("(y) => window.scrollTo(0, y)", y)
                        pg.wait_for_timeout(400)
                        r = pg.evaluate(PROBE)
                        if r.get("skip"):
                            continue
                        for hit in r["hits"]:
                            worst = max(worst, hit["overlap"])
                            problems.append(
                                "%s at %dpx, scrolled %d: %s is %dpx under the "
                                "header (its top:%s puts it at %d, header ends "
                                "at %d)"
                                % (p, w, y, hit["tag"], hit["overlap"],
                                   hit["cssTop"], hit["top"], hit["navBottom"]))
                    ctx.close()
                print("    %-28s worst overlap %dpx" % (p, worst))
            b.close()
    finally:
        if srv:
            srv.shutdown()

    print()
    if problems:
        print("  %d PROBLEM(S)\n" % len(problems))
        for x in problems[:10]:
            print("  - %s" % x)
        print("\n  A row pinned with a hardcoded offset drifts the moment the")
        print("  header's height or position changes. Use")
        print("  calc(var(--nav-h) + var(--occasion-banner-h, 0px)).")
        return 1
    print("  Nothing sticky sits under the header, on %d pages x %d widths."
          % (len(PAGES), len(WIDTHS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
